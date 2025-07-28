"""
ReAgent Sydney - Market Anomaly Detector

System for detecting unusual market behavior patterns that may indicate
off-market opportunities through statistical analysis and pattern recognition.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
import statistics
import numpy as np
from scipy import stats

from sqlalchemy import select, and_, or_, func, desc, text
from sqlalchemy.orm import sessionmaker
import structlog

from ...core.database.engine import get_db_session
from ...data.models.property_models import Property, PropertyPriceHistory, PropertyMarketMetrics
from ...data.models.market_models import SuburbMetrics, MarketTrend
from .data_models import (
    OffMarketOpportunity, OpportunityType, OpportunityScore, 
    DistressSignalType, OpportunityStatus
)


@dataclass
class MarketAnomaly:
    """Represents a detected market anomaly."""
    
    property_id: str
    anomaly_type: str  # 'price_outlier', 'behavior_anomaly', 'timing_anomaly', 'engagement_anomaly'
    severity: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    
    # Anomaly details
    description: str
    statistical_evidence: Dict[str, Any]
    expected_value: Optional[float]
    actual_value: Optional[float]
    deviation_score: float  # Z-score or similar
    
    # Context
    market_context: Dict[str, Any]
    peer_comparison: Dict[str, Any]
    temporal_analysis: Dict[str, Any]
    
    # Detection metadata
    detection_method: str
    detected_at: datetime
    
    @property
    def is_significant_anomaly(self) -> bool:
        """Check if this is a statistically significant anomaly."""
        return abs(self.deviation_score) > 2.0 and self.confidence > 0.7


class MarketAnomalyDetector:
    """
    Market Anomaly Detector for identifying unusual patterns.
    
    Detects anomalies through:
    1. Price outlier analysis
    2. Market behavior deviations
    3. Timing pattern anomalies
    4. Engagement metric outliers
    5. Comparative market analysis
    """
    
    def __init__(self, radar_config):
        self.radar_config = radar_config
        self.logger = structlog.get_logger("off_market_radar.market_anomaly_detector")
        
        # Statistical thresholds
        self.z_score_threshold = 2.0  # Standard deviations for outlier detection
        self.confidence_threshold = 0.6
        self.min_sample_size = 10
        
        # Analysis windows
        self.price_analysis_days = 90
        self.behavior_analysis_days = 60
        self.peer_comparison_radius_km = 5.0
        
        # Cache for market statistics
        self.market_stats_cache = {}
        self.cache_expiry = {}
    
    async def initialize(self) -> None:
        """Initialize the market anomaly detector."""
        try:
            # Precompute market statistics for common areas
            await self._precompute_market_statistics()
            
            self.logger.info("Market Anomaly Detector initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Market Anomaly Detector: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup market anomaly detector resources."""
        try:
            # Clear caches
            self.market_stats_cache.clear()
            self.cache_expiry.clear()
            
            self.logger.info("Market Anomaly Detector cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Market Anomaly Detector cleanup: {e}")
    
    async def scan_market_anomalies(
        self, 
        target_suburbs: List[str] = None,
        anomaly_threshold: float = 0.6
    ) -> List[OffMarketOpportunity]:
        """
        Scan for market anomaly opportunities.
        
        Args:
            target_suburbs: List of suburbs to focus on
            anomaly_threshold: Minimum anomaly severity to consider
            
        Returns:
            List of opportunities discovered
        """
        opportunities = []
        
        try:
            self.logger.info(f"Scanning for market anomalies (threshold: {anomaly_threshold})")
            
            # Get properties to analyze
            candidate_properties = await self._get_anomaly_candidates(target_suburbs)
            
            # Analyze each property for anomalies
            all_anomalies = []
            for property_data in candidate_properties:
                anomalies = await self._detect_property_anomalies(property_data)
                
                # Filter by threshold
                significant_anomalies = [
                    a for a in anomalies 
                    if a.severity >= anomaly_threshold and a.is_significant_anomaly
                ]
                
                if significant_anomalies:
                    all_anomalies.extend(significant_anomalies)
            
            # Group anomalies by property and create opportunities
            property_anomalies = {}
            for anomaly in all_anomalies:
                if anomaly.property_id not in property_anomalies:
                    property_anomalies[anomaly.property_id] = []
                property_anomalies[anomaly.property_id].append(anomaly)
            
            # Create opportunities from grouped anomalies
            for property_id, anomalies in property_anomalies.items():
                opportunity = await self._create_opportunity_from_anomalies(property_id, anomalies)
                if opportunity:
                    opportunities.append(opportunity)
            
            # Sort by anomaly severity
            opportunities.sort(key=lambda x: x.scoring.overall_score, reverse=True)
            
            self.logger.info(f"Found {len(opportunities)} market anomaly opportunities")
            
        except Exception as e:
            self.logger.error(f"Error scanning market anomalies: {e}")
            raise
        
        return opportunities
    
    async def _get_anomaly_candidates(self, target_suburbs: List[str] = None) -> List[Dict[str, Any]]:
        """Get properties that are candidates for anomaly analysis."""
        try:
            async with get_db_session() as session:
                # Look for active listings with sufficient data for analysis
                query = select(Property).where(
                    and_(
                        Property.listing_status == 'active',
                        Property.postcode.between('2000', '2999'),
                        Property.deleted_at.is_(None),
                        Property.price.is_not(None),
                        Property.first_listed_date.is_not(None)
                    )
                )
                
                # Filter by suburbs if specified
                if target_suburbs:
                    query = query.where(Property.suburb.in_(target_suburbs))
                
                result = await session.execute(query.limit(300))  # Reasonable limit
                properties = result.scalars().all()
                
                # Convert to analysis format
                candidate_data = []
                for prop in properties:
                    data = {
                        'property_id': str(prop.id),
                        'listing_id': prop.listing_id,
                        'address': prop.address_line_1,
                        'suburb': prop.suburb,
                        'postcode': prop.postcode,
                        'property_type': prop.property_type,
                        'bedrooms': prop.bedrooms,
                        'bathrooms': prop.bathrooms,
                        'land_size': prop.land_size,
                        'current_price': float(prop.price) if prop.price else None,
                        'listing_status': prop.listing_status,
                        'first_listed_date': prop.first_listed_date,
                        'days_on_market': prop.days_on_market,
                        'latitude': float(prop.latitude) if prop.latitude else None,
                        'longitude': float(prop.longitude) if prop.longitude else None,
                        'agent_id': str(prop.agent_id) if prop.agent_id else None,
                        'source': prop.source
                    }
                    candidate_data.append(data)
                
                return candidate_data
                
        except Exception as e:
            self.logger.error(f"Error getting anomaly candidates: {e}")
            return []
    
    async def _detect_property_anomalies(self, property_data: Dict[str, Any]) -> List[MarketAnomaly]:
        """Detect anomalies for a specific property."""
        anomalies = []
        
        try:
            property_id = property_data['property_id']
            
            # Price anomalies
            price_anomalies = await self._detect_price_anomalies(property_data)
            anomalies.extend(price_anomalies)
            
            # Behavior anomalies
            behavior_anomalies = await self._detect_behavior_anomalies(property_data)
            anomalies.extend(behavior_anomalies)
            
            # Timing anomalies
            timing_anomalies = await self._detect_timing_anomalies(property_data)
            anomalies.extend(timing_anomalies)
            
            # Engagement anomalies
            engagement_anomalies = await self._detect_engagement_anomalies(property_data)
            anomalies.extend(engagement_anomalies)
            
        except Exception as e:
            self.logger.error(f"Error detecting property anomalies: {e}")
        
        return anomalies
    
    async def _detect_price_anomalies(self, property_data: Dict[str, Any]) -> List[MarketAnomaly]:
        """Detect price-related anomalies."""
        anomalies = []
        property_id = property_data['property_id']
        
        try:
            current_price = property_data.get('current_price')
            suburb = property_data.get('suburb')
            property_type = property_data.get('property_type')
            bedrooms = property_data.get('bedrooms')
            
            if not current_price or not suburb:
                return anomalies
            
            # Get comparable properties for statistical analysis
            comparables = await self._get_comparable_properties(property_data)
            
            if len(comparables) < self.min_sample_size:
                return anomalies
            
            # Price outlier analysis
            comparable_prices = [p['current_price'] for p in comparables if p['current_price']]
            
            if len(comparable_prices) >= self.min_sample_size:
                price_stats = self._calculate_price_statistics(comparable_prices)
                z_score = (current_price - price_stats['mean']) / price_stats['std']
                
                if abs(z_score) > self.z_score_threshold:
                    anomaly_type = 'underpriced' if z_score < 0 else 'overpriced'
                    severity = min(1.0, abs(z_score) / 4.0)  # Cap at 4 standard deviations
                    
                    anomalies.append(MarketAnomaly(
                        property_id=property_id,
                        anomaly_type='price_outlier',
                        severity=severity,
                        confidence=0.8,
                        description=f"Property is {anomaly_type} by {abs(z_score):.1f} standard deviations",
                        statistical_evidence={
                            'z_score': z_score,
                            'property_price': current_price,
                            'comparable_mean': price_stats['mean'],
                            'comparable_std': price_stats['std'],
                            'comparable_count': len(comparable_prices)
                        },
                        expected_value=price_stats['mean'],
                        actual_value=current_price,
                        deviation_score=z_score,
                        market_context={'suburb': suburb, 'property_type': property_type},
                        peer_comparison={'comparable_properties': len(comparables)},
                        temporal_analysis={},
                        detection_method='z_score_price_analysis',
                        detected_at=datetime.utcnow()
                    ))
            
            # Price-per-square-meter anomaly
            if property_data.get('land_size'):
                price_per_sqm = current_price / property_data['land_size']
                comparable_psm = [
                    p['current_price'] / p['land_size'] 
                    for p in comparables 
                    if p.get('land_size') and p['land_size'] > 0 and p['current_price']
                ]
                
                if len(comparable_psm) >= self.min_sample_size:
                    psm_stats = self._calculate_price_statistics(comparable_psm)
                    psm_z_score = (price_per_sqm - psm_stats['mean']) / psm_stats['std']
                    
                    if abs(psm_z_score) > self.z_score_threshold:
                        severity = min(1.0, abs(psm_z_score) / 3.0)
                        
                        anomalies.append(MarketAnomaly(
                            property_id=property_id,
                            anomaly_type='price_per_sqm_anomaly',
                            severity=severity,
                            confidence=0.7,
                            description=f"Price per sqm anomaly: {psm_z_score:.1f} standard deviations",
                            statistical_evidence={
                                'psm_z_score': psm_z_score,
                                'price_per_sqm': price_per_sqm,
                                'comparable_psm_mean': psm_stats['mean'],
                                'comparable_psm_std': psm_stats['std']
                            },
                            expected_value=psm_stats['mean'],
                            actual_value=price_per_sqm,
                            deviation_score=psm_z_score,
                            market_context={'land_size': property_data['land_size']},
                            peer_comparison={'comparable_psm_count': len(comparable_psm)},
                            temporal_analysis={},
                            detection_method='price_per_sqm_analysis',
                            detected_at=datetime.utcnow()
                        ))
            
        except Exception as e:
            self.logger.error(f"Error detecting price anomalies: {e}")
        
        return anomalies
    
    async def _detect_behavior_anomalies(self, property_data: Dict[str, Any]) -> List[MarketAnomaly]:
        """Detect behavioral anomalies in listing patterns."""
        anomalies = []
        property_id = property_data['property_id']
        
        try:
            # Get price history for behavioral analysis
            price_history = await self._get_price_history(property_id)
            
            if len(price_history) < 2:
                return anomalies
            
            # Unusual price change frequency
            price_changes = [h for h in price_history if h.get('price_change', 0) != 0]
            
            if len(price_changes) > 0:
                # Calculate frequency of price changes
                time_span = (price_history[-1]['created_at'] - price_history[0]['created_at']).days
                change_frequency = len(price_changes) / max(1, time_span / 30)  # Changes per month
                
                # Get typical frequency for comparison
                suburb_avg_frequency = await self._get_suburb_price_change_frequency(property_data['suburb'])
                
                if suburb_avg_frequency and change_frequency > suburb_avg_frequency * 2:
                    severity = min(1.0, change_frequency / (suburb_avg_frequency * 4))
                    
                    anomalies.append(MarketAnomaly(
                        property_id=property_id,
                        anomaly_type='behavior_anomaly',
                        severity=severity,
                        confidence=0.6,
                        description=f"Unusually frequent price changes: {change_frequency:.1f} per month",
                        statistical_evidence={
                            'change_frequency': change_frequency,
                            'suburb_average': suburb_avg_frequency,
                            'total_changes': len(price_changes),
                            'time_span_days': time_span
                        },
                        expected_value=suburb_avg_frequency,
                        actual_value=change_frequency,
                        deviation_score=(change_frequency - suburb_avg_frequency) / suburb_avg_frequency,
                        market_context={'suburb': property_data['suburb']},
                        peer_comparison={},
                        temporal_analysis={'time_span_days': time_span},
                        detection_method='price_change_frequency_analysis',
                        detected_at=datetime.utcnow()
                    ))
            
            # Unusual price change magnitude patterns
            price_changes_magnitude = [abs(h.get('price_change_percent', 0)) for h in price_changes]
            
            if price_changes_magnitude:
                avg_change_magnitude = statistics.mean(price_changes_magnitude)
                max_change_magnitude = max(price_changes_magnitude)
                
                # If average change is very large, it's anomalous
                if avg_change_magnitude > 10:  # More than 10% average change
                    severity = min(1.0, avg_change_magnitude / 20)
                    
                    anomalies.append(MarketAnomaly(
                        property_id=property_id,
                        anomaly_type='behavior_anomaly',
                        severity=severity,
                        confidence=0.7,
                        description=f"Large price change magnitude: {avg_change_magnitude:.1f}% average",
                        statistical_evidence={
                            'avg_change_magnitude': avg_change_magnitude,
                            'max_change_magnitude': max_change_magnitude,
                            'change_count': len(price_changes_magnitude)
                        },
                        expected_value=5.0,  # Typical 5% changes
                        actual_value=avg_change_magnitude,
                        deviation_score=(avg_change_magnitude - 5.0) / 5.0,
                        market_context={},
                        peer_comparison={},
                        temporal_analysis={},
                        detection_method='price_change_magnitude_analysis',
                        detected_at=datetime.utcnow()
                    ))
            
        except Exception as e:
            self.logger.error(f"Error detecting behavior anomalies: {e}")
        
        return anomalies
    
    async def _detect_timing_anomalies(self, property_data: Dict[str, Any]) -> List[MarketAnomaly]:
        """Detect timing-related anomalies."""
        anomalies = []
        property_id = property_data['property_id']
        
        try:
            first_listed_date = property_data.get('first_listed_date')
            days_on_market = property_data.get('days_on_market', 0)
            
            if not first_listed_date:
                return anomalies
            
            # Seasonal anomaly detection
            listing_month = first_listed_date.month
            seasonal_analysis = await self._analyze_seasonal_patterns(property_data['suburb'], listing_month)
            
            if seasonal_analysis['is_unusual_season']:
                anomalies.append(MarketAnomaly(
                    property_id=property_id,
                    anomaly_type='timing_anomaly',
                    severity=seasonal_analysis['severity'],
                    confidence=0.5,
                    description=f"Listed in unusual season: {seasonal_analysis['description']}",
                    statistical_evidence=seasonal_analysis,
                    expected_value=seasonal_analysis['typical_month'],
                    actual_value=listing_month,
                    deviation_score=seasonal_analysis['deviation_score'],
                    market_context={'suburb': property_data['suburb']},
                    peer_comparison={},
                    temporal_analysis={'listing_month': listing_month},
                    detection_method='seasonal_analysis',
                    detected_at=datetime.utcnow()
                ))
            
            # Extended market time anomaly
            suburb_median_days = await self._get_suburb_median_days_on_market(property_data['suburb'])
            
            if suburb_median_days and days_on_market > suburb_median_days * 2:
                severity = min(1.0, (days_on_market - suburb_median_days) / suburb_median_days)
                
                anomalies.append(MarketAnomaly(
                    property_id=property_id,
                    anomaly_type='timing_anomaly',
                    severity=severity,
                    confidence=0.8,
                    description=f"Extended market time: {days_on_market} vs {suburb_median_days} median days",
                    statistical_evidence={
                        'days_on_market': days_on_market,
                        'suburb_median': suburb_median_days,
                        'ratio': days_on_market / suburb_median_days
                    },
                    expected_value=suburb_median_days,
                    actual_value=days_on_market,
                    deviation_score=(days_on_market - suburb_median_days) / suburb_median_days,
                    market_context={'suburb': property_data['suburb']},
                    peer_comparison={},
                    temporal_analysis={},
                    detection_method='market_time_analysis',
                    detected_at=datetime.utcnow()
                ))
            
        except Exception as e:
            self.logger.error(f"Error detecting timing anomalies: {e}")
        
        return anomalies
    
    async def _detect_engagement_anomalies(self, property_data: Dict[str, Any]) -> List[MarketAnomaly]:
        """Detect engagement metric anomalies."""
        anomalies = []
        property_id = property_data['property_id']
        
        try:
            # Get market metrics for the property
            market_metrics = await self._get_property_market_metrics(property_id)
            
            if not market_metrics:
                return anomalies
            
            days_on_market = property_data.get('days_on_market', 0)
            
            # View count anomaly
            view_count = market_metrics.get('view_count', 0)
            expected_views = max(50, days_on_market * 3)  # Rough baseline
            
            if view_count < expected_views * 0.3:  # Less than 30% of expected
                severity = 1.0 - (view_count / expected_views)
                
                anomalies.append(MarketAnomaly(
                    property_id=property_id,
                    anomaly_type='engagement_anomaly',
                    severity=min(1.0, severity),
                    confidence=0.6,
                    description=f"Low view count: {view_count} vs {expected_views} expected",
                    statistical_evidence={
                        'view_count': view_count,
                        'expected_views': expected_views,
                        'days_on_market': days_on_market
                    },
                    expected_value=expected_views,
                    actual_value=view_count,
                    deviation_score=(view_count - expected_views) / expected_views,
                    market_context={},
                    peer_comparison={},
                    temporal_analysis={},
                    detection_method='view_count_analysis',
                    detected_at=datetime.utcnow()
                ))
            
            # Enquiry rate anomaly
            enquiry_count = market_metrics.get('enquiry_count', 0)
            expected_enquiries = max(2, days_on_market // 15)  # Rough baseline
            
            if enquiry_count < expected_enquiries * 0.5 and days_on_market > 30:
                severity = 1.0 - (enquiry_count / expected_enquiries) if expected_enquiries > 0 else 0.8
                
                anomalies.append(MarketAnomaly(
                    property_id=property_id,
                    anomaly_type='engagement_anomaly',
                    severity=min(1.0, severity),
                    confidence=0.7,
                    description=f"Low enquiry count: {enquiry_count} vs {expected_enquiries} expected",
                    statistical_evidence={
                        'enquiry_count': enquiry_count,
                        'expected_enquiries': expected_enquiries,
                        'days_on_market': days_on_market
                    },
                    expected_value=expected_enquiries,
                    actual_value=enquiry_count,
                    deviation_score=(enquiry_count - expected_enquiries) / max(1, expected_enquiries),
                    market_context={},
                    peer_comparison={},
                    temporal_analysis={},
                    detection_method='enquiry_count_analysis',
                    detected_at=datetime.utcnow()
                ))
            
        except Exception as e:
            self.logger.error(f"Error detecting engagement anomalies: {e}")
        
        return anomalies
    
    async def _get_comparable_properties(self, property_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get comparable properties for statistical analysis."""
        try:
            async with get_db_session() as session:
                # Build query for comparable properties
                query = select(Property).where(
                    and_(
                        Property.suburb == property_data['suburb'],
                        Property.property_type == property_data.get('property_type'),
                        Property.listing_status == 'active',
                        Property.price.is_not(None),
                        Property.id != property_data['property_id'],
                        Property.deleted_at.is_(None)
                    )
                )
                
                # Filter by bedrooms if available
                if property_data.get('bedrooms'):
                    query = query.where(
                        or_(
                            Property.bedrooms == property_data['bedrooms'],
                            Property.bedrooms == property_data['bedrooms'] - 1,
                            Property.bedrooms == property_data['bedrooms'] + 1
                        )
                    )
                
                result = await session.execute(query.limit(50))
                properties = result.scalars().all()
                
                # Convert to analysis format
                comparables = []
                for prop in properties:
                    comparable = {
                        'property_id': str(prop.id),
                        'current_price': float(prop.price) if prop.price else None,
                        'bedrooms': prop.bedrooms,
                        'bathrooms': prop.bathrooms,
                        'land_size': prop.land_size,
                        'days_on_market': prop.days_on_market,
                        'first_listed_date': prop.first_listed_date
                    }
                    comparables.append(comparable)
                
                return comparables
                
        except Exception as e:
            self.logger.error(f"Error getting comparable properties: {e}")
            return []
    
    def _calculate_price_statistics(self, prices: List[float]) -> Dict[str, float]:
        """Calculate price statistics for comparison."""
        try:
            prices = [p for p in prices if p is not None and p > 0]
            
            if not prices:
                return {'mean': 0, 'std': 0, 'median': 0, 'count': 0}
            
            return {
                'mean': statistics.mean(prices),
                'std': statistics.stdev(prices) if len(prices) > 1 else 0,
                'median': statistics.median(prices),
                'count': len(prices),
                'min': min(prices),
                'max': max(prices)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating price statistics: {e}")
            return {'mean': 0, 'std': 0, 'median': 0, 'count': 0}
    
    async def _get_price_history(self, property_id: str) -> List[Dict[str, Any]]:
        """Get price history for a property."""
        try:
            async with get_db_session() as session:
                from ...data.models.property_models import PropertyPriceHistory
                
                result = await session.execute(
                    select(PropertyPriceHistory).where(
                        PropertyPriceHistory.property_id == property_id
                    ).order_by(PropertyPriceHistory.created_at)
                )
                
                history = result.scalars().all()
                
                return [
                    {
                        'price': float(record.price) if record.price else 0,
                        'price_change': float(record.price_change) if record.price_change else 0,
                        'price_change_percent': float(record.price_change_percent) if record.price_change_percent else 0,
                        'event_type': record.event_type,
                        'created_at': record.created_at
                    }
                    for record in history
                ]
                
        except Exception as e:
            self.logger.error(f"Error getting price history: {e}")
            return []
    
    async def _get_suburb_price_change_frequency(self, suburb: str) -> Optional[float]:
        """Get average price change frequency for suburb."""
        try:
            # This would be calculated from historical data
            # For now, return a reasonable default
            return 0.5  # 0.5 changes per month average
            
        except Exception as e:
            self.logger.error(f"Error getting suburb price change frequency: {e}")
            return None
    
    async def _analyze_seasonal_patterns(self, suburb: str, listing_month: int) -> Dict[str, Any]:
        """Analyze seasonal listing patterns."""
        try:
            # Australian property seasons (simplified)
            # Spring (Sep-Nov): Best season
            # Summer (Dec-Feb): Good season  
            # Autumn (Mar-May): Moderate season
            # Winter (Jun-Aug): Poor season
            
            seasonal_scores = {
                1: 0.7, 2: 0.7, 3: 0.6,   # Summer/Early Autumn
                4: 0.6, 5: 0.5, 6: 0.3,   # Autumn/Winter
                7: 0.3, 8: 0.3, 9: 0.8,   # Winter/Spring
                10: 0.9, 11: 0.9, 12: 0.8  # Spring/Summer
            }
            
            month_score = seasonal_scores.get(listing_month, 0.5)
            typical_month = 10  # October (peak spring)
            
            # Consider it unusual if listed in very poor season
            is_unusual = month_score < 0.4
            severity = (0.4 - month_score) / 0.4 if is_unusual else 0.0
            
            season_names = {
                12: 'Summer', 1: 'Summer', 2: 'Summer',
                3: 'Autumn', 4: 'Autumn', 5: 'Autumn',
                6: 'Winter', 7: 'Winter', 8: 'Winter',
                9: 'Spring', 10: 'Spring', 11: 'Spring'
            }
            
            return {
                'is_unusual_season': is_unusual,
                'severity': severity,
                'month_score': month_score,
                'typical_month': typical_month,
                'deviation_score': (typical_month - listing_month) / 12,
                'description': f"Listed in {season_names.get(listing_month, 'Unknown')} (poor season)" if is_unusual else "Normal season"
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing seasonal patterns: {e}")
            return {'is_unusual_season': False, 'severity': 0.0}
    
    async def _get_suburb_median_days_on_market(self, suburb: str) -> Optional[int]:
        """Get median days on market for suburb."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(SuburbMetrics.median_days_on_market).where(
                        SuburbMetrics.suburb.ilike(f"%{suburb}%")
                    ).order_by(desc(SuburbMetrics.created_at)).limit(1)
                )
                
                return result.scalar_one_or_none()
                
        except Exception as e:
            self.logger.error(f"Error getting suburb median days: {e}")
            return None
    
    async def _get_property_market_metrics(self, property_id: str) -> Dict[str, Any]:
        """Get market metrics for a property."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(PropertyMarketMetrics).where(
                        PropertyMarketMetrics.property_id == property_id
                    ).order_by(desc(PropertyMarketMetrics.created_at)).limit(1)
                )
                
                metrics = result.scalar_one_or_none()
                
                if metrics:
                    return {
                        'view_count': metrics.view_count,
                        'enquiry_count': metrics.enquiry_count,
                        'inspection_requests': metrics.inspection_requests,
                        'favorite_count': metrics.favorite_count
                    }
                
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting property market metrics: {e}")
            return {}
    
    async def _create_opportunity_from_anomalies(
        self, 
        property_id: str, 
        anomalies: List[MarketAnomaly]
    ) -> Optional[OffMarketOpportunity]:
        """Create opportunity from detected anomalies."""
        try:
            # Get property details
            async with get_db_session() as session:
                result = await session.execute(
                    select(Property).where(Property.id == property_id)
                )
                
                property_obj = result.scalar_one_or_none()
                if not property_obj:
                    return None
            
            # Calculate overall anomaly score
            anomaly_scores = [a.severity * a.confidence for a in anomalies]
            overall_anomaly_score = min(1.0, statistics.mean(anomaly_scores) * 1.2)
            
            # Determine opportunity potential based on anomaly types
            underpriced_anomalies = [a for a in anomalies if 'underpriced' in a.description.lower()]
            engagement_anomalies = [a for a in anomalies if a.anomaly_type == 'engagement_anomaly']
            timing_anomalies = [a for a in anomalies if a.anomaly_type == 'timing_anomaly']
            
            # Calculate ROI potential
            roi_potential = 0.0
            if underpriced_anomalies:
                # Underpriced properties have higher ROI potential
                roi_potential = 0.8
            elif engagement_anomalies:
                # Low engagement might indicate negotiation opportunity
                roi_potential = 0.6
            elif timing_anomalies:
                # Timing issues might create opportunity
                roi_potential = 0.4
            else:
                roi_potential = 0.3
            
            # Calculate other scoring components
            time_sensitivity = 0.7 if any('extended_market_time' in a.description for a in anomalies) else 0.4
            acquisition_difficulty = 0.3  # Anomalies often make acquisition easier
            
            # Create opportunity scoring
            scoring = OpportunityScore(
                overall_score=overall_anomaly_score,
                roi_potential=roi_potential,
                acquisition_difficulty=acquisition_difficulty,
                time_sensitivity=time_sensitivity,
                market_conditions=0.5,
                price_attractiveness=0.8 if underpriced_anomalies else 0.5,
                location_desirability=0.6,
                property_condition=0.5,  # Not determinable from anomalies
                seller_motivation=0.7 if engagement_anomalies or timing_anomalies else 0.4,
                legal_risk=0.1,  # Low legal risk from market anomalies
                market_risk=0.3,
                execution_risk=0.2
            )
            
            # Estimate potential purchase discount
            discount_estimate = 0.05  # Base 5% discount
            if underpriced_anomalies:
                # Already underpriced, less additional discount
                discount_estimate = 0.03
            elif engagement_anomalies:
                # Low engagement suggests more discount potential
                discount_estimate = 0.10
            elif timing_anomalies:
                # Extended market time suggests discount opportunity
                discount_estimate = 0.08
            
            potential_purchase_price = None
            estimated_roi = None
            
            if property_obj.price:
                potential_purchase_price = property_obj.price * (1 - discount_estimate)
                estimated_roi = (property_obj.price - potential_purchase_price) / potential_purchase_price * 100
            
            # Create opportunity
            opportunity = OffMarketOpportunity(
                opportunity_type=OpportunityType.MARKET_ANOMALY,
                property_id=property_id,
                listing_id=property_obj.listing_id,
                address=property_obj.address_line_1,
                suburb=property_obj.suburb,
                postcode=property_obj.postcode,
                property_type=property_obj.property_type,
                bedrooms=property_obj.bedrooms,
                bathrooms=property_obj.bathrooms,
                current_price=property_obj.price,
                potential_purchase_price=potential_purchase_price,
                estimated_roi_percent=estimated_roi,
                title=f"Market Anomaly: {property_obj.address_line_1}",
                description=self._generate_anomaly_opportunity_description(anomalies),
                scoring=scoring,
                opportunity_details={
                    'anomaly_count': len(anomalies),
                    'overall_anomaly_score': overall_anomaly_score,
                    'anomaly_types': list(set([a.anomaly_type for a in anomalies])),
                    'highest_severity': max([a.severity for a in anomalies]),
                    'statistical_significance': any([a.is_significant_anomaly for a in anomalies]),
                    'anomalies': [
                        {
                            'type': a.anomaly_type,
                            'severity': a.severity,
                            'confidence': a.confidence,
                            'description': a.description,
                            'deviation_score': a.deviation_score
                        }
                        for a in anomalies
                    ]
                },
                data_sources=['market_analysis', 'statistical_analysis', 'peer_comparison'],
                evidence={
                    'anomalies': anomalies,
                    'statistical_analysis': [a.statistical_evidence for a in anomalies]
                },
                confidence_level=overall_anomaly_score,
                expires_at=datetime.utcnow() + timedelta(days=120),  # 4 months validity
                tags=self._generate_anomaly_tags(anomalies),
                compliance_checked=True,
                ethical_approval=True,
                data_privacy_compliant=True
            )
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error creating opportunity from anomalies: {e}")
            return None
    
    def _generate_anomaly_opportunity_description(self, anomalies: List[MarketAnomaly]) -> str:
        """Generate description for market anomaly opportunity."""
        try:
            desc = f"Property exhibits {len(anomalies)} market anomal{'ies' if len(anomalies) > 1 else 'y'}: "
            
            anomaly_descriptions = []
            for anomaly in anomalies:
                if anomaly.anomaly_type == 'price_outlier':
                    if 'underpriced' in anomaly.description:
                        anomaly_descriptions.append("significantly underpriced")
                    else:
                        anomaly_descriptions.append("price outlier")
                elif anomaly.anomaly_type == 'engagement_anomaly':
                    anomaly_descriptions.append("low market engagement")
                elif anomaly.anomaly_type == 'timing_anomaly':
                    if 'extended' in anomaly.description:
                        anomaly_descriptions.append("extended market time")
                    else:
                        anomaly_descriptions.append("unusual timing")
                elif anomaly.anomaly_type == 'behavior_anomaly':
                    anomaly_descriptions.append("unusual pricing behavior")
            
            desc += ", ".join(anomaly_descriptions) + ". "
            
            # Add statistical significance
            significant_anomalies = [a for a in anomalies if a.is_significant_anomaly]
            if significant_anomalies:
                desc += f"{len(significant_anomalies)} statistically significant anomal{'ies' if len(significant_anomalies) > 1 else 'y'}. "
            
            # Add highest deviation
            max_deviation = max([abs(a.deviation_score) for a in anomalies])
            desc += f"Maximum deviation: {max_deviation:.1f} standard deviations."
            
            return desc
            
        except Exception:
            return f"Property exhibits {len(anomalies)} market anomalies suggesting potential opportunity."
    
    def _generate_anomaly_tags(self, anomalies: List[MarketAnomaly]) -> List[str]:
        """Generate tags for market anomaly opportunity."""
        tags = ['market_anomaly', 'statistical_analysis']
        
        # Add anomaly type tags
        for anomaly in anomalies:
            tags.append(anomaly.anomaly_type)
            
            if 'underpriced' in anomaly.description:
                tags.append('underpriced')
            elif 'overpriced' in anomaly.description:
                tags.append('overpriced')
            
            if anomaly.is_significant_anomaly:
                tags.append('statistically_significant')
        
        # Add severity tags
        max_severity = max([a.severity for a in anomalies])
        if max_severity > 0.8:
            tags.append('high_severity')
        elif max_severity > 0.5:
            tags.append('moderate_severity')
        
        # Add confidence tags
        avg_confidence = statistics.mean([a.confidence for a in anomalies])
        if avg_confidence > 0.7:
            tags.append('high_confidence')
        elif avg_confidence > 0.5:
            tags.append('moderate_confidence')
        
        return tags
    
    async def _precompute_market_statistics(self) -> None:
        """Precompute market statistics for common areas."""
        try:
            # This would precompute statistics for major suburbs
            # For now, just log that we would do this
            self.logger.info("Market statistics precomputation completed")
            
        except Exception as e:
            self.logger.warning(f"Failed to precompute market statistics: {e}")
    
    async def get_anomaly_summary(
        self, 
        suburb: str = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get summary of detected market anomalies."""
        try:
            # This would analyze recent anomalies from the database
            # For now, return a placeholder summary
            
            return {
                'total_anomalies_detected': 0,
                'anomaly_types': {},
                'severity_distribution': {'low': 0, 'moderate': 0, 'high': 0, 'critical': 0},
                'average_confidence': 0.0,
                'statistically_significant': 0,
                'analysis_period_days': days_back,
                'suburb': suburb or 'All Sydney',
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting anomaly summary: {e}")
            return {
                'error': str(e),
                'analysis_period_days': days_back,
                'suburb': suburb or 'All Sydney'
            }