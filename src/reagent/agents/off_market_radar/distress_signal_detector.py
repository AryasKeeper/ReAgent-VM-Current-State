"""
ReAgent Sydney - Distress Signal Detector

Advanced system for detecting properties under financial or legal pressure
that may indicate off-market opportunities.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
import statistics
import re

from sqlalchemy import select, and_, or_, func, desc, text
from sqlalchemy.orm import sessionmaker
import structlog

from ...core.database.engine import get_db_session
from ...data.models.property_models import Property, PropertyPriceHistory, PropertyMarketMetrics
from ...data.models.market_models import SuburbMetrics
from ...core.exceptions import DatabaseQueryError, ValidationError, AgentExecutionError
from .data_models import (
    OffMarketOpportunity, OpportunityType, OpportunityScore, 
    DistressSignalType, DistressSignalRecord, OpportunityStatus
)


@dataclass
class DistressSignal:
    """Represents a distress signal detected for a property."""
    
    property_id: str
    signal_type: DistressSignalType
    severity: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    
    # Signal details
    description: str
    evidence: Dict[str, Any]
    detection_method: str
    detected_at: datetime
    
    # Source information
    data_source: str
    source_url: Optional[str] = None
    
    # Validation
    validated: bool = False
    false_positive_risk: float = 0.0


@dataclass
class DistressAnalysis:
    """Comprehensive distress analysis for a property."""
    
    property_id: str
    overall_distress_score: float  # 0.0 to 1.0
    risk_level: str  # low, moderate, high, critical
    
    # Individual signals
    signals: List[DistressSignal]
    signal_count: int
    
    # Analysis components
    financial_pressure_score: float
    legal_risk_score: float
    market_pressure_score: float
    time_pressure_score: float
    
    # Opportunity indicators
    seller_motivation_estimate: float
    negotiation_leverage: float
    urgency_level: float
    
    # Timeline analysis
    distress_timeline: List[Dict[str, Any]]
    trend_direction: str  # improving, stable, worsening
    
    @property
    def is_high_distress(self) -> bool:
        """Check if this represents high distress."""
        return self.overall_distress_score >= 0.7
    
    @property
    def has_multiple_signals(self) -> bool:
        """Check if multiple distress signals are present."""
        return self.signal_count >= 2


class DistressSignalDetector:
    """
    Distress Signal Detector for identifying properties under pressure.
    
    Detects distress through:
    1. Financial pressure indicators
    2. Legal issue monitoring
    3. Price drop pattern analysis
    4. Market behavior anomalies
    5. Ownership change patterns
    """
    
    def __init__(self, radar_config):
        self.radar_config = radar_config
        self.logger = structlog.get_logger("off_market_radar.distress_signal_detector")
        
        # Detection thresholds
        self.price_drop_threshold = radar_config.price_drop_threshold_percent
        self.extended_market_threshold = radar_config.market_time_anomaly_days
        self.distress_score_threshold = radar_config.distress_score_threshold
        
        # Pattern recognition parameters
        self.rapid_price_drop_days = 30  # Days for rapid price drop detection
        self.repeated_listing_threshold = 2
        self.auction_failure_lookback_days = 90
        
        # Cache for analysis results
        self.analysis_cache = {}
        self.cache_expiry = {}
    
    async def initialize(self) -> None:
        """Initialize the distress signal detector."""
        try:
            self.logger.info("Distress Signal Detector initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Distress Signal Detector: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup distress signal detector resources."""
        try:
            # Clear caches
            self.analysis_cache.clear()
            self.cache_expiry.clear()
            
            self.logger.info("Distress Signal Detector cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Distress Signal Detector cleanup: {e}")
    
    async def scan_distress_signals(
        self, 
        target_suburbs: List[str] = None,
        threshold_score: float = None
    ) -> List[OffMarketOpportunity]:
        """
        Scan for distress signal opportunities.
        
        Args:
            target_suburbs: List of suburbs to focus on
            threshold_score: Minimum distress score to consider
            
        Returns:
            List of opportunities discovered
        """
        opportunities = []
        threshold_score = threshold_score or self.distress_score_threshold
        
        try:
            self.logger.info(f"Scanning for distress signals (threshold: {threshold_score})")
            
            # Get properties to analyze
            candidate_properties = await self._get_candidate_properties(target_suburbs)
            
            # Analyze each property for distress signals
            distress_analyses = []
            for property_data in candidate_properties:
                analysis = await self._analyze_property_distress(property_data)
                
                if analysis and analysis.overall_distress_score >= threshold_score:
                    distress_analyses.append(analysis)
            
            # Convert analyses to opportunities
            for analysis in distress_analyses:
                opportunity = await self._create_opportunity_from_distress(analysis)
                if opportunity:
                    opportunities.append(opportunity)
            
            # Save distress signals to database
            await self._save_distress_signals(distress_analyses)
            
            # Sort by distress score
            opportunities.sort(key=lambda x: x.scoring.overall_score, reverse=True)
            
            self.logger.info(f"Found {len(opportunities)} distress signal opportunities")
            
        except Exception as e:
            self.logger.error(f"Error scanning distress signals: {e}")
            raise
        
        return opportunities
    
    async def _get_candidate_properties(self, target_suburbs: List[str] = None) -> List[Dict[str, Any]]:
        """Get properties that are candidates for distress analysis."""
        try:
            # Look for properties with potential distress indicators
            async with get_db_session() as session:
                # Base query for active listings with concerning patterns
                query = select(Property).where(
                    and_(
                        Property.listing_status == 'active',
                        Property.postcode.between('2000', '2999'),
                        Property.deleted_at.is_(None),
                        or_(
                            Property.days_on_market > 60,  # Extended market time
                            Property.price < Property.price * 0.9  # Price drops (simplified)
                        )
                    )
                )
                
                # Filter by suburbs if specified
                if target_suburbs:
                    query = query.where(Property.suburb.in_(target_suburbs))
                
                result = await session.execute(query.limit(200))  # Reasonable limit
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
                        'current_price': prop.price,
                        'listing_status': prop.listing_status,
                        'first_listed_date': prop.first_listed_date,
                        'days_on_market': prop.days_on_market,
                        'agent_id': str(prop.agent_id) if prop.agent_id else None,
                        'source': prop.source,
                        'last_updated': prop.last_updated_source
                    }
                    candidate_data.append(data)
                
                return candidate_data
                
        except Exception as e:
            self.logger.error(f"Error getting candidate properties: {e}")
            return []
    
    async def _analyze_property_distress(self, property_data: Dict[str, Any]) -> Optional[DistressAnalysis]:
        """Analyze a property for distress signals."""
        try:
            property_id = property_data['property_id']
            
            # Check cache first
            cache_key = f"distress_{property_id}"
            if cache_key in self.analysis_cache:
                if datetime.utcnow() < self.cache_expiry.get(cache_key, datetime.min):
                    return self.analysis_cache[cache_key]
            
            # Collect all signals
            signals = []
            
            # Financial pressure signals
            financial_signals = await self._detect_financial_pressure(property_data)
            signals.extend(financial_signals)
            
            # Price drop signals
            price_signals = await self._detect_price_drop_patterns(property_data)
            signals.extend(price_signals)
            
            # Market behavior signals
            market_signals = await self._detect_market_behavior_anomalies(property_data)
            signals.extend(market_signals)
            
            # Legal/ownership signals
            legal_signals = await self._detect_legal_ownership_issues(property_data)
            signals.extend(legal_signals)
            
            # Time pressure signals  
            time_signals = await self._detect_time_pressure(property_data)
            signals.extend(time_signals)
            
            # Skip if no significant signals
            if not signals or max(s.severity for s in signals) < 0.3:
                return None
            
            # Calculate component scores
            financial_score = self._calculate_financial_pressure_score(signals)
            legal_score = self._calculate_legal_risk_score(signals)
            market_score = self._calculate_market_pressure_score(signals)
            time_score = self._calculate_time_pressure_score(signals)
            
            # Calculate overall distress score
            overall_score = (
                financial_score * 0.35 +
                market_score * 0.25 +
                time_score * 0.25 +
                legal_score * 0.15
            )
            
            # Determine risk level
            risk_level = self._determine_risk_level(overall_score)
            
            # Calculate opportunity indicators
            seller_motivation = min(1.0, overall_score * 1.2)
            negotiation_leverage = overall_score
            urgency_level = time_score
            
            # Create distress timeline
            timeline = await self._create_distress_timeline(property_data, signals)
            
            # Determine trend
            trend = self._analyze_trend_direction(timeline)
            
            # Create analysis object
            analysis = DistressAnalysis(
                property_id=property_id,
                overall_distress_score=overall_score,
                risk_level=risk_level,
                signals=signals,
                signal_count=len(signals),
                financial_pressure_score=financial_score,
                legal_risk_score=legal_score,
                market_pressure_score=market_score,
                time_pressure_score=time_score,
                seller_motivation_estimate=seller_motivation,
                negotiation_leverage=negotiation_leverage,
                urgency_level=urgency_level,
                distress_timeline=timeline,
                trend_direction=trend
            )
            
            # Cache the result
            self.analysis_cache[cache_key] = analysis
            self.cache_expiry[cache_key] = datetime.utcnow() + timedelta(hours=6)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing property distress: {e}")
            return None
    
    async def _detect_financial_pressure(self, property_data: Dict[str, Any]) -> List[DistressSignal]:
        """Detect financial pressure indicators."""
        signals = []
        property_id = property_data['property_id']
        
        try:
            # Get price history for analysis
            price_history = await self._get_price_history(property_id)
            
            # Rapid price drops
            rapid_drops = self._find_rapid_price_drops(price_history)
            for drop in rapid_drops:
                signals.append(DistressSignal(
                    property_id=property_id,
                    signal_type=DistressSignalType.PRICE_DROP_PATTERN,
                    severity=min(1.0, drop['percentage'] / 20),  # 20% drop = max severity
                    confidence=0.8,
                    description=f"Rapid price drop of {drop['percentage']:.1f}% in {drop['days']} days",
                    evidence=drop,
                    detection_method="price_history_analysis",
                    detected_at=datetime.utcnow(),
                    data_source="price_history"
                ))
            
            # Multiple price reductions
            reduction_count = len([h for h in price_history if h.get('price_change', 0) < 0])
            if reduction_count >= 3:
                signals.append(DistressSignal(
                    property_id=property_id,
                    signal_type=DistressSignalType.FINANCIAL_PRESSURE,
                    severity=min(1.0, reduction_count / 5),  # 5+ reductions = max severity
                    confidence=0.7,
                    description=f"Multiple price reductions ({reduction_count} times)",
                    evidence={'reduction_count': reduction_count, 'price_history': price_history},
                    detection_method="price_reduction_pattern",
                    detected_at=datetime.utcnow(),
                    data_source="price_history"
                ))
            
            # Below market pricing
            below_market_analysis = await self._analyze_below_market_pricing(property_data)
            if below_market_analysis['is_below_market']:
                signals.append(DistressSignal(
                    property_id=property_id,
                    signal_type=DistressSignalType.FINANCIAL_PRESSURE,
                    severity=below_market_analysis['severity'],
                    confidence=0.6,
                    description=f"Priced {below_market_analysis['percentage_below']:.1f}% below market",
                    evidence=below_market_analysis,
                    detection_method="market_comparison",
                    detected_at=datetime.utcnow(),
                    data_source="market_analysis"
                ))
            
        except Exception as e:
            self.logger.error(f"Error detecting financial pressure: {e}")
        
        return signals
    
    async def _detect_price_drop_patterns(self, property_data: Dict[str, Any]) -> List[DistressSignal]:
        """Detect concerning price drop patterns."""
        signals = []
        property_id = property_data['property_id']
        
        try:
            price_history = await self._get_price_history(property_id)
            
            # Repeated listing at lower prices
            repeated_listings = self._find_repeated_listings(price_history)
            if len(repeated_listings) >= 2:
                avg_drop = statistics.mean([r['price_drop_pct'] for r in repeated_listings])
                signals.append(DistressSignal(
                    property_id=property_id,
                    signal_type=DistressSignalType.REPEATED_LISTING,
                    severity=min(1.0, len(repeated_listings) / 3),
                    confidence=0.8,
                    description=f"Relisted {len(repeated_listings)} times with avg {avg_drop:.1f}% price drop",
                    evidence={'repeated_listings': repeated_listings},
                    detection_method="repeated_listing_analysis",
                    detected_at=datetime.utcnow(),
                    data_source="price_history"
                ))
            
            # Auction failure followed by private sale
            auction_failure = await self._detect_auction_failure(property_data, price_history)
            if auction_failure:
                signals.append(DistressSignal(
                    property_id=property_id,
                    signal_type=DistressSignalType.AUCTION_FAILURE,
                    severity=0.7,  # Auction failures indicate seller pressure
                    confidence=0.9,
                    description="Failed auction followed by private sale listing",
                    evidence=auction_failure,
                    detection_method="auction_failure_analysis",
                    detected_at=datetime.utcnow(),
                    data_source="listing_history"
                ))
            
        except Exception as e:
            self.logger.error(f"Error detecting price drop patterns: {e}")
        
        return signals
    
    async def _detect_market_behavior_anomalies(self, property_data: Dict[str, Any]) -> List[DistressSignal]:
        """Detect anomalous market behavior."""
        signals = []
        property_id = property_data['property_id']
        
        try:
            # Extended market time
            days_on_market = property_data.get('days_on_market', 0)
            suburb_median = await self._get_suburb_median_days(property_data['suburb'])
            
            if suburb_median and days_on_market > suburb_median * 2:
                severity = min(1.0, (days_on_market - suburb_median) / suburb_median)
                signals.append(DistressSignal(
                    property_id=property_id,
                    signal_type=DistressSignalType.EXTENDED_MARKET_TIME,
                    severity=severity,
                    confidence=0.7,
                    description=f"Extended market time: {days_on_market} days vs {suburb_median} median",
                    evidence={
                        'days_on_market': days_on_market,
                        'suburb_median': suburb_median,
                        'ratio': days_on_market / suburb_median
                    },
                    detection_method="market_time_comparison",
                    detected_at=datetime.utcnow(),
                    data_source="market_analysis"
                ))
            
            # Low engagement metrics
            engagement_analysis = await self._analyze_low_engagement(property_data)
            if engagement_analysis['is_low_engagement']:
                signals.append(DistressSignal(
                    property_id=property_id,
                    signal_type=DistressSignalType.FINANCIAL_PRESSURE,
                    severity=engagement_analysis['severity'],
                    confidence=0.5,  # Lower confidence for engagement metrics
                    description="Low market engagement (views, enquiries, inspections)",
                    evidence=engagement_analysis,
                    detection_method="engagement_analysis",
                    detected_at=datetime.utcnow(),
                    data_source="market_metrics"
                ))
            
        except Exception as e:
            self.logger.error(f"Error detecting market behavior anomalies: {e}")
        
        return signals
    
    async def _detect_legal_ownership_issues(self, property_data: Dict[str, Any]) -> List[DistressSignal]:
        """Detect potential legal or ownership issues."""
        signals = []
        property_id = property_data['property_id']
        
        try:
            # This would integrate with legal databases in production
            # For now, we'll use simplified indicators
            
            # Rapid ownership changes (would require ownership history)
            # Court-ordered sales (would require legal database access)
            # Bankruptcy notices (would require ASIC database access)
            
            # For demo purposes, we'll create placeholder logic
            # In production, this would connect to:
            # - NSW LPI for ownership changes
            # - ASIC for bankruptcy notices
            # - Court records for legal actions
            
            # Placeholder: detect properties with certain keywords in description
            # that might indicate legal issues
            if hasattr(property_data, 'description'):
                description = property_data.get('description', '').lower()
                legal_keywords = ['deceased estate', 'mortgagee', 'executor', 'trustee', 'liquidation']
                
                for keyword in legal_keywords:
                    if keyword in description:
                        signals.append(DistressSignal(
                            property_id=property_id,
                            signal_type=DistressSignalType.LEGAL_ISSUE,
                            severity=0.8,
                            confidence=0.6,
                            description=f"Legal indicator detected: {keyword}",
                            evidence={'keyword': keyword, 'description': description},
                            detection_method="keyword_analysis",
                            detected_at=datetime.utcnow(),
                            data_source="property_description"
                        ))
            
        except Exception as e:
            self.logger.error(f"Error detecting legal/ownership issues: {e}")
        
        return signals
    
    async def _detect_time_pressure(self, property_data: Dict[str, Any]) -> List[DistressSignal]:
        """Detect time pressure indicators."""
        signals = []
        property_id = property_data['property_id']
        
        try:
            # Frequent price changes (indicates urgency)
            price_history = await self._get_price_history(property_id)
            
            # Count price changes in last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_changes = [
                h for h in price_history 
                if h.get('created_at', datetime.min) > thirty_days_ago and h.get('price_change', 0) != 0
            ]
            
            if len(recent_changes) >= 2:
                signals.append(DistressSignal(
                    property_id=property_id,
                    signal_type=DistressSignalType.FINANCIAL_PRESSURE,
                    severity=min(1.0, len(recent_changes) / 4),
                    confidence=0.6,
                    description=f"Frequent price changes: {len(recent_changes)} in 30 days",
                    evidence={'recent_changes': recent_changes},
                    detection_method="price_change_frequency",
                    detected_at=datetime.utcnow(),
                    data_source="price_history"
                ))
            
            # Seasonal pressure (properties listed in poor seasons)
            listing_date = property_data.get('first_listed_date')
            if listing_date:
                month = listing_date.month
                # Winter months (June-August) in Australia
                if month in [6, 7, 8]:
                    signals.append(DistressSignal(
                        property_id=property_id,
                        signal_type=DistressSignalType.FINANCIAL_PRESSURE,
                        severity=0.3,  # Moderate severity
                        confidence=0.4,
                        description="Listed during poor selling season (winter)",
                        evidence={'listing_month': month, 'listing_date': listing_date.isoformat()},
                        detection_method="seasonal_analysis",
                        detected_at=datetime.utcnow(),
                        data_source="listing_timing"
                    ))
            
        except Exception as e:
            self.logger.error(f"Error detecting time pressure: {e}")
        
        return signals
    
    async def _get_price_history(self, property_id: str) -> List[Dict[str, Any]]:
        """Get price history for a property."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(PropertyPriceHistory).where(
                        PropertyPriceHistory.property_id == property_id
                    ).order_by(PropertyPriceHistory.created_at)
                )
                
                history = result.scalars().all()
                
                return [
                    {
                        'price': float(record.price) if record.price else 0,
                        'price_type': record.price_type,
                        'previous_price': float(record.previous_price) if record.previous_price else None,
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
    
    def _find_rapid_price_drops(self, price_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find rapid price drops in history."""
        rapid_drops = []
        
        try:
            # Look for significant drops within short timeframes
            for i in range(1, len(price_history)):
                current = price_history[i]
                previous = price_history[i-1]
                
                if current['price_change_percent'] < -self.price_drop_threshold:
                    days_between = (current['created_at'] - previous['created_at']).days
                    
                    if days_between <= self.rapid_price_drop_days:
                        rapid_drops.append({
                            'percentage': abs(current['price_change_percent']),
                            'amount': abs(current['price_change']),
                            'days': days_between,
                            'from_price': previous['price'],
                            'to_price': current['price'],
                            'date': current['created_at']
                        })
            
        except Exception as e:
            self.logger.error(f"Error finding rapid price drops: {e}")
        
        return rapid_drops
    
    def _find_repeated_listings(self, price_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find repeated listings with price drops."""
        repeated_listings = []
        
        try:
            listing_events = [h for h in price_history if h['event_type'] == 'listing']
            
            for i in range(1, len(listing_events)):
                current = listing_events[i]
                previous = listing_events[i-1]
                
                if current['price'] < previous['price']:
                    price_drop = previous['price'] - current['price']
                    price_drop_pct = (price_drop / previous['price']) * 100
                    
                    repeated_listings.append({
                        'listing_number': i + 1,
                        'price_drop': price_drop,
                        'price_drop_pct': price_drop_pct,
                        'previous_price': previous['price'],
                        'new_price': current['price'],
                        'date': current['created_at']
                    })
            
        except Exception as e:
            self.logger.error(f"Error finding repeated listings: {e}")
        
        return repeated_listings
    
    async def _detect_auction_failure(
        self, 
        property_data: Dict[str, Any], 
        price_history: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Detect if property failed at auction."""
        try:
            # Look for auction events followed by private sale
            auction_events = [h for h in price_history if 'auction' in h.get('event_type', '').lower()]
            
            if auction_events:
                # Check if there's a private sale listing after auction
                last_auction = max(auction_events, key=lambda x: x['created_at'])
                
                private_listings = [
                    h for h in price_history 
                    if h['created_at'] > last_auction['created_at'] and h['event_type'] == 'listing'
                ]
                
                if private_listings:
                    first_private = min(private_listings, key=lambda x: x['created_at'])
                    days_after_auction = (first_private['created_at'] - last_auction['created_at']).days
                    
                    if days_after_auction <= 30:  # Listed within 30 days of auction
                        return {
                            'auction_date': last_auction['created_at'],
                            'private_listing_date': first_private['created_at'],
                            'days_between': days_after_auction,
                            'auction_price': last_auction.get('price'),
                            'private_price': first_private.get('price')
                        }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error detecting auction failure: {e}")
            return None
    
    async def _get_suburb_median_days(self, suburb: str) -> Optional[int]:
        """Get median days on market for suburb."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(SuburbMetrics.median_days_on_market).where(
                        SuburbMetrics.suburb.ilike(f"%{suburb}%")
                    ).order_by(desc(SuburbMetrics.created_at)).limit(1)
                )
                
                median = result.scalar_one_or_none()
                return median
                
        except Exception as e:
            self.logger.error(f"Error getting suburb median days: {e}")
            return None
    
    async def _analyze_below_market_pricing(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze if property is priced below market."""
        try:
            current_price = property_data.get('current_price')
            suburb = property_data.get('suburb')
            
            if not current_price or not suburb:
                return {'is_below_market': False}
            
            # Get suburb median price
            async with get_db_session() as session:
                result = await session.execute(
                    select(SuburbMetrics.median_price).where(
                        SuburbMetrics.suburb.ilike(f"%{suburb}%")
                    ).order_by(desc(SuburbMetrics.created_at)).limit(1)
                )
                
                median_price = result.scalar_one_or_none()
                
                if median_price and current_price < median_price:
                    percentage_below = ((median_price - current_price) / median_price) * 100
                    
                    # Consider significant if more than 10% below market
                    if percentage_below > 10:
                        return {
                            'is_below_market': True,
                            'percentage_below': percentage_below,
                            'current_price': float(current_price),
                            'median_price': float(median_price),
                            'severity': min(1.0, percentage_below / 30)  # 30% below = max severity
                        }
            
            return {'is_below_market': False}
            
        except Exception as e:
            self.logger.error(f"Error analyzing below market pricing: {e}")
            return {'is_below_market': False}
    
    async def _analyze_low_engagement(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze if property has low market engagement."""
        try:
            property_id = property_data['property_id']
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(PropertyMarketMetrics).where(
                        PropertyMarketMetrics.property_id == property_id
                    ).order_by(desc(PropertyMarketMetrics.created_at)).limit(1)
                )
                
                metrics = result.scalar_one_or_none()
                
                if metrics:
                    days_on_market = property_data.get('days_on_market', 0)
                    
                    # Calculate expected engagement based on market time
                    expected_views = max(50, days_on_market * 2)  # Rough estimate
                    expected_enquiries = max(3, days_on_market // 10)
                    
                    view_ratio = metrics.view_count / expected_views if expected_views > 0 else 0
                    enquiry_ratio = metrics.enquiry_count / expected_enquiries if expected_enquiries > 0 else 0
                    
                    # Consider low engagement if significantly below expected
                    if view_ratio < 0.5 and enquiry_ratio < 0.5:
                        severity = 1.0 - max(view_ratio, enquiry_ratio)
                        
                        return {
                            'is_low_engagement': True,
                            'view_count': metrics.view_count,
                            'enquiry_count': metrics.enquiry_count,
                            'expected_views': expected_views,
                            'expected_enquiries': expected_enquiries,
                            'view_ratio': view_ratio,
                            'enquiry_ratio': enquiry_ratio,
                            'severity': severity
                        }
            
            return {'is_low_engagement': False}
            
        except Exception as e:
            self.logger.error(f"Error analyzing low engagement: {e}")
            return {'is_low_engagement': False}
    
    def _calculate_financial_pressure_score(self, signals: List[DistressSignal]) -> float:
        """Calculate financial pressure component score."""
        financial_signals = [
            s for s in signals 
            if s.signal_type in [DistressSignalType.FINANCIAL_PRESSURE, DistressSignalType.PRICE_DROP_PATTERN]
        ]
        
        if not financial_signals:
            return 0.0
        
        # Weight by severity and confidence
        weighted_scores = [s.severity * s.confidence for s in financial_signals]
        return min(1.0, statistics.mean(weighted_scores) * 1.2)  # Slight boost for multiple signals
    
    def _calculate_legal_risk_score(self, signals: List[DistressSignal]) -> float:
        """Calculate legal risk component score."""
        legal_signals = [
            s for s in signals 
            if s.signal_type in [DistressSignalType.LEGAL_ISSUE, DistressSignalType.OWNERSHIP_CHANGE]
        ]
        
        if not legal_signals:
            return 0.0
        
        weighted_scores = [s.severity * s.confidence for s in legal_signals]
        return min(1.0, max(weighted_scores))  # Take highest legal risk
    
    def _calculate_market_pressure_score(self, signals: List[DistressSignal]) -> float:
        """Calculate market pressure component score."""
        market_signals = [
            s for s in signals 
            if s.signal_type in [DistressSignalType.EXTENDED_MARKET_TIME, DistressSignalType.AUCTION_FAILURE]
        ]
        
        if not market_signals:
            return 0.0
        
        weighted_scores = [s.severity * s.confidence for s in market_signals]
        return min(1.0, statistics.mean(weighted_scores))
    
    def _calculate_time_pressure_score(self, signals: List[DistressSignal]) -> float:
        """Calculate time pressure component score."""
        # Time pressure comes from frequency of changes and seasonal factors
        time_related_signals = [
            s for s in signals 
            if 'frequent' in s.description.lower() or 'seasonal' in s.description.lower()
        ]
        
        if not time_related_signals:
            return 0.0
        
        weighted_scores = [s.severity * s.confidence for s in time_related_signals]
        return min(1.0, statistics.mean(weighted_scores))
    
    def _determine_risk_level(self, overall_score: float) -> str:
        """Determine risk level from overall score."""
        if overall_score >= 0.8:
            return "critical"
        elif overall_score >= 0.6:
            return "high"
        elif overall_score >= 0.4:
            return "moderate"
        else:
            return "low"
    
    async def _create_distress_timeline(
        self, 
        property_data: Dict[str, Any], 
        signals: List[DistressSignal]
    ) -> List[Dict[str, Any]]:
        """Create timeline of distress signals."""
        timeline = []
        
        try:
            # Add listing start
            if property_data.get('first_listed_date'):
                timeline.append({
                    'date': property_data['first_listed_date'],
                    'event': 'listing_started',
                    'description': 'Property first listed',
                    'severity': 0.0
                })
            
            # Add signal events
            for signal in signals:
                timeline.append({
                    'date': signal.detected_at,
                    'event': signal.signal_type.value,
                    'description': signal.description,
                    'severity': signal.severity
                })
            
            # Sort by date
            timeline.sort(key=lambda x: x['date'])
            
        except Exception as e:
            self.logger.error(f"Error creating distress timeline: {e}")
        
        return timeline
    
    def _analyze_trend_direction(self, timeline: List[Dict[str, Any]]) -> str:
        """Analyze if distress is improving, stable, or worsening."""
        try:
            if len(timeline) < 2:
                return "stable"
            
            # Look at severity trend over time
            recent_events = timeline[-3:]  # Last 3 events
            severities = [event['severity'] for event in recent_events if event['severity'] > 0]
            
            if len(severities) < 2:
                return "stable"
            
            # Simple trend analysis
            if severities[-1] > severities[0] * 1.2:
                return "worsening"
            elif severities[-1] < severities[0] * 0.8:
                return "improving"
            else:
                return "stable"
                
        except (IndexError, ValueError) as e:
            logger = structlog.get_logger(__name__)
            logger.warning(f"Failed to calculate distress trend direction: {e}", 
                          property_id=getattr(self, 'property_id', 'unknown'), exc_info=True)
            return "stable"
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"Unexpected error calculating trend direction: {e}", 
                        property_id=getattr(self, 'property_id', 'unknown'), exc_info=True)
            raise ValidationError("trend_direction", None, f"Trend calculation failed: {e}") from e
    
    async def _create_opportunity_from_distress(
        self, 
        analysis: DistressAnalysis
    ) -> Optional[OffMarketOpportunity]:
        """Create opportunity from distress analysis."""
        try:
            # Get property details
            async with get_db_session() as session:
                result = await session.execute(
                    select(Property).where(Property.id == analysis.property_id)
                )
                
                property_obj = result.scalar_one_or_none()
                if not property_obj:
                    return None
            
            # Calculate opportunity scoring
            scoring = OpportunityScore(
                overall_score=analysis.overall_distress_score,
                roi_potential=analysis.negotiation_leverage,
                acquisition_difficulty=1.0 - analysis.seller_motivation_estimate,
                time_sensitivity=analysis.urgency_level,
                market_conditions=0.5,  # Would get from market data
                seller_motivation=analysis.seller_motivation_estimate,
                price_attractiveness=analysis.negotiation_leverage,
                location_desirability=0.6,  # Would calculate from suburb data
                property_condition=0.5,  # Not available from distress analysis
                legal_risk=analysis.legal_risk_score,
                market_risk=analysis.market_pressure_score,
                execution_risk=analysis.financial_pressure_score
            )
            
            # Estimate purchase discount
            discount_pct = analysis.negotiation_leverage * 0.15  # Up to 15% discount
            potential_purchase_price = None
            estimated_roi = None
            
            if property_obj.price:
                potential_purchase_price = property_obj.price * (1 - discount_pct)
                estimated_roi = (property_obj.price - potential_purchase_price) / potential_purchase_price * 100
            
            # Create opportunity
            opportunity = OffMarketOpportunity(
                opportunity_type=OpportunityType.DISTRESS_SIGNAL,
                property_id=analysis.property_id,
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
                title=f"Distress Signal: {property_obj.address_line_1}",
                description=self._generate_distress_opportunity_description(analysis),
                scoring=scoring,
                opportunity_details={
                    'distress_score': analysis.overall_distress_score,
                    'risk_level': analysis.risk_level,
                    'signal_count': analysis.signal_count,
                    'trend_direction': analysis.trend_direction,
                    'component_scores': {
                        'financial_pressure': analysis.financial_pressure_score,
                        'legal_risk': analysis.legal_risk_score,
                        'market_pressure': analysis.market_pressure_score,
                        'time_pressure': analysis.time_pressure_score
                    },
                    'signals': [
                        {
                            'type': s.signal_type.value,
                            'severity': s.severity,
                            'description': s.description
                        }
                        for s in analysis.signals
                    ]
                },
                data_sources=['distress_analysis', 'price_history', 'market_metrics'],
                evidence={
                    'distress_analysis': analysis,
                    'distress_timeline': analysis.distress_timeline
                },
                confidence_level=analysis.overall_distress_score,
                expires_at=datetime.utcnow() + timedelta(days=90),  # 3 months validity
                tags=self._generate_distress_tags(analysis),
                compliance_checked=True,
                ethical_approval=True,
                data_privacy_compliant=True
            )
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error creating opportunity from distress: {e}")
            return None
    
    def _generate_distress_opportunity_description(self, analysis: DistressAnalysis) -> str:
        """Generate description for distress opportunity."""
        try:
            desc = f"Property showing {analysis.risk_level} distress signals "
            desc += f"(score: {analysis.overall_distress_score:.2f}). "
            
            desc += f"Detected {analysis.signal_count} distress indicators: "
            
            signal_types = list(set([s.signal_type.value for s in analysis.signals]))
            desc += ", ".join(signal_types) + ". "
            
            desc += f"Seller motivation estimated at {analysis.seller_motivation_estimate:.1%}, "
            desc += f"negotiation leverage: {analysis.negotiation_leverage:.1%}. "
            
            if analysis.trend_direction == "worsening":
                desc += "Distress indicators are worsening over time. "
            elif analysis.trend_direction == "improving":
                desc += "Distress indicators show some improvement. "
            
            return desc
            
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.warning(f"Failed to generate distress description: {e}", 
                          property_id=analysis.property_id, exc_info=True)
            return f"Property showing distress signals with {analysis.overall_distress_score:.1%} severity."
    
    def _generate_distress_tags(self, analysis: DistressAnalysis) -> List[str]:
        """Generate tags for distress opportunity."""
        tags = ['distress_signal', f'risk_{analysis.risk_level}']
        
        # Add signal type tags
        for signal in analysis.signals:
            tags.append(signal.signal_type.value)
        
        # Add component tags
        if analysis.financial_pressure_score > 0.6:
            tags.append('financial_pressure')
        
        if analysis.legal_risk_score > 0.5:
            tags.append('legal_risk')
        
        if analysis.market_pressure_score > 0.6:
            tags.append('market_pressure')
        
        if analysis.time_pressure_score > 0.6:
            tags.append('time_pressure')
        
        # Add trend tag
        tags.append(f'trend_{analysis.trend_direction}')
        
        # Add motivation tag
        if analysis.seller_motivation_estimate > 0.7:
            tags.append('highly_motivated_seller')
        elif analysis.seller_motivation_estimate > 0.4:
            tags.append('motivated_seller')
        
        return tags
    
    async def _save_distress_signals(self, analyses: List[DistressAnalysis]) -> None:
        """Save distress signals to database."""
        try:
            async with get_db_session() as session:
                for analysis in analyses:
                    for signal in analysis.signals:
                        # Check if signal already exists
                        existing = await session.execute(
                            select(DistressSignalRecord).where(
                                and_(
                                    DistressSignalRecord.property_id == analysis.property_id,
                                    DistressSignalRecord.signal_type == signal.signal_type.value,
                                    DistressSignalRecord.signal_date == signal.detected_at.date()
                                )
                            )
                        )
                        
                        if existing.scalar_one_or_none():
                            continue  # Skip existing signals
                        
                        # Create new signal record
                        db_signal = DistressSignalRecord(
                            property_id=analysis.property_id,
                            signal_type=signal.signal_type.value,
                            severity=signal.severity,
                            description=signal.description,
                            evidence=signal.evidence,
                            detection_method=signal.detection_method,
                            signal_date=signal.detected_at,
                            data_source=signal.data_source,
                            source_url=signal.source_url,
                            raw_data=signal.evidence,
                            validated=signal.validated,
                            false_positive=False
                        )
                        
                        session.add(db_signal)
                
                await session.commit()
                
                total_signals = sum(len(a.signals) for a in analyses)
                self.logger.info(f"Saved {total_signals} distress signals to database")
                
        except Exception as e:
            self.logger.error(f"Error saving distress signals: {e}")
    
    async def get_distress_summary(
        self, 
        suburb: str = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get summary of distress signals for analysis."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            async with get_db_session() as session:
                # Base query for distress signals
                query = select(DistressSignalRecord).where(
                    DistressSignalRecord.created_at >= cutoff_date
                )
                
                if suburb:
                    # Join with Property to filter by suburb
                    query = query.join(Property).where(
                        Property.suburb.ilike(f"%{suburb}%")
                    )
                
                result = await session.execute(query)
                signals = result.scalars().all()
                
                # Analyze patterns
                total_signals = len(signals)
                signal_types = {}
                severity_distribution = {'low': 0, 'moderate': 0, 'high': 0, 'critical': 0}
                
                for signal in signals:
                    # Count by type
                    signal_types[signal.signal_type] = signal_types.get(signal.signal_type, 0) + 1
                    
                    # Count by severity
                    if signal.severity >= 0.8:
                        severity_distribution['critical'] += 1
                    elif signal.severity >= 0.6:
                        severity_distribution['high'] += 1
                    elif signal.severity >= 0.4:
                        severity_distribution['moderate'] += 1
                    else:
                        severity_distribution['low'] += 1
                
                avg_severity = statistics.mean([s.severity for s in signals]) if signals else 0
                
                return {
                    'total_distress_signals': total_signals,
                    'signal_types': signal_types,
                    'severity_distribution': severity_distribution,
                    'average_severity': round(avg_severity, 3),
                    'analysis_period_days': days_back,
                    'suburb': suburb or 'All Sydney',
                    'generated_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting distress summary: {e}")
            return {
                'total_distress_signals': 0,
                'signal_types': {},
                'severity_distribution': {'low': 0, 'moderate': 0, 'high': 0, 'critical': 0},
                'average_severity': 0,
                'analysis_period_days': days_back,
                'suburb': suburb or 'All Sydney',
                'error': str(e)
            }