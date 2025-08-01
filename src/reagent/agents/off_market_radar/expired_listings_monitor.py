"""
ReAgent Sydney - Expired Listings Monitor

Advanced monitoring system for detecting expired property listings and analyzing
patterns that indicate off-market opportunities.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
import statistics

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import sessionmaker
import structlog

from ...core.database.engine import get_db_session
from ...data.models.property_models import Property, PropertyPriceHistory, PropertyMarketMetrics
from ...data.models.market_models import SuburbMetrics
from ...core.exceptions import ValidationError, DatabaseQueryError, AgentExecutionError
from .data_models import (
    OffMarketOpportunity, OpportunityType, OpportunityScore, 
    DistressSignalType, OpportunityStatus
)


@dataclass
class ExpiredListingPattern:
    """Pattern analysis for expired listings."""
    
    property_id: str
    listing_id: str
    address: str
    suburb: str
    postcode: str
    
    # Listing history
    first_listed_date: datetime
    last_active_date: datetime
    total_days_on_market: int
    listing_count: int  # Number of times relisted
    
    # Price analysis
    original_price: Optional[Decimal]
    final_price: Optional[Decimal]
    price_reductions: int
    total_price_drop: Optional[Decimal]
    price_drop_percentage: Optional[float]
    
    # Market comparison
    suburb_median_days: Optional[int]
    market_position_percentile: Optional[float]
    price_vs_suburb_median: Optional[float]
    
    # Expiry analysis
    expiry_reason: str  # 'time_expired', 'agent_withdrawal', 'price_resistance', 'market_conditions'
    motivation_indicators: List[str]
    seller_behavior_score: float  # 0.0 to 1.0, higher = more motivated
    
    # Opportunity assessment
    reactivation_probability: float  # Likelihood of relisting
    negotiation_potential: float  # Potential for price negotiation
    urgency_score: float  # How urgently seller might want to sell
    
    @property
    def days_since_expired(self) -> int:
        """Days since listing expired."""
        return (datetime.utcnow() - self.last_active_date).days
    
    @property
    def is_recent_expiry(self) -> bool:
        """Check if this is a recent expiry (within 30 days)."""
        return self.days_since_expired <= 30
    
    @property
    def has_price_resistance(self) -> bool:
        """Check if listing showed price resistance."""
        return self.price_reductions == 0 and self.total_days_on_market > 90


class ExpiredListingsMonitor:
    """
    Monitor for expired property listings with advanced pattern analysis.
    
    Identifies opportunities through:
    1. Recent expiry detection
    2. Multiple listing pattern analysis
    3. Price resistance identification
    4. Seller motivation assessment
    5. Market timing analysis
    """
    
    def __init__(self, radar_config):
        self.radar_config = radar_config
        self.logger = structlog.get_logger("off_market_radar.expired_listings_monitor")
        
        # Analysis parameters
        self.expiry_threshold_days = radar_config.expired_listing_days
        self.recent_expiry_days = 30
        self.extended_market_time_days = radar_config.market_time_anomaly_days
        
        # Pattern cache
        self.pattern_cache = {}
        self.suburb_stats_cache = {}
        self.cache_expiry = {}
    
    async def initialize(self) -> None:
        """Initialize the expired listings monitor."""
        try:
            # Pre-load suburb statistics for faster analysis
            await self._preload_suburb_statistics()
            
            self.logger.info("Expired Listings Monitor initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Expired Listings Monitor: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup expired listings monitor resources."""
        try:
            # Clear caches
            self.pattern_cache.clear()
            self.suburb_stats_cache.clear()
            self.cache_expiry.clear()
            
            self.logger.info("Expired Listings Monitor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Expired Listings Monitor cleanup: {e}")
    
    async def scan_expired_listings(
        self, 
        target_suburbs: List[str] = None,
        cutoff_days: int = None
    ) -> List[OffMarketOpportunity]:
        """
        Scan for expired listing opportunities.
        
        Args:
            target_suburbs: List of suburbs to focus on
            cutoff_days: Days since expiry to consider
            
        Returns:
            List of opportunities discovered
        """
        opportunities = []
        cutoff_days = cutoff_days or self.expiry_threshold_days
        
        try:
            self.logger.info(f"Scanning expired listings (cutoff: {cutoff_days} days)")
            
            # Get expired listings from database
            expired_listings = await self._get_expired_listings(target_suburbs, cutoff_days)
            
            # Analyze each expired listing for patterns
            patterns = []
            for listing in expired_listings:
                pattern = await self._analyze_listing_pattern(listing)
                if pattern:
                    patterns.append(pattern)
            
            # Convert patterns to opportunities
            for pattern in patterns:
                opportunity = await self._create_opportunity_from_pattern(pattern)
                if opportunity:
                    opportunities.append(opportunity)
            
            # Sort by priority score
            opportunities.sort(key=lambda x: x.priority_score, reverse=True)
            
            self.logger.info(f"Found {len(opportunities)} expired listing opportunities")
            
        except Exception as e:
            self.logger.error(f"Error scanning expired listings: {e}")
            raise
        
        return opportunities
    
    async def _get_expired_listings(
        self, 
        target_suburbs: List[str] = None,
        cutoff_days: int = 90
    ) -> List[Dict[str, Any]]:
        """Get expired listings from the database."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=cutoff_days)
            
            async with get_db_session() as session:
                # Build query for expired listings
                query = select(Property).where(
                    and_(
                        Property.listing_status.in_(['withdrawn', 'off_market', 'expired']),
                        Property.last_updated_source < cutoff_date,
                        Property.deleted_at.is_(None)
                    )
                )
                
                # Filter by suburbs if specified
                if target_suburbs:
                    query = query.where(Property.suburb.in_(target_suburbs))
                
                # Filter by Sydney postcodes
                query = query.where(
                    Property.postcode.between('2000', '2999')
                )
                
                result = await session.execute(query.order_by(desc(Property.last_updated_source)))
                properties = result.scalars().all()
                
                # Convert to dictionaries with additional data
                listings = []
                for prop in properties:
                    listing_data = {
                        'property_id': str(prop.id),
                        'listing_id': prop.listing_id,
                        'address': prop.address_line_1,
                        'suburb': prop.suburb,
                        'postcode': prop.postcode,
                        'property_type': prop.property_type,
                        'bedrooms': prop.bedrooms,
                        'bathrooms': prop.bathrooms,
                        'price': prop.price,
                        'listing_status': prop.listing_status,
                        'first_listed_date': prop.first_listed_date,
                        'last_updated_source': prop.last_updated_source,
                        'days_on_market': prop.days_on_market,
                        'agent_id': str(prop.agent_id) if prop.agent_id else None,
                        'source': prop.source
                    }
                    listings.append(listing_data)
                
                return listings
                
        except Exception as e:
            self.logger.error(f"Error getting expired listings: {e}")
            return []
    
    async def _analyze_listing_pattern(self, listing: Dict[str, Any]) -> Optional[ExpiredListingPattern]:
        """Analyze a listing for expiry patterns and seller motivation."""
        try:
            property_id = listing['property_id']
            
            # Get price history for this property
            price_history = await self._get_property_price_history(property_id)
            
            # Get market metrics
            market_metrics = await self._get_property_market_metrics(property_id)
            
            # Get suburb statistics
            suburb_stats = await self._get_suburb_statistics(listing['suburb'])
            
            # Analyze price patterns
            price_analysis = self._analyze_price_patterns(price_history, listing)
            
            # Determine expiry reason
            expiry_reason = self._determine_expiry_reason(listing, price_analysis, market_metrics)
            
            # Assess seller motivation
            motivation_analysis = self._assess_seller_motivation(
                listing, price_analysis, market_metrics, suburb_stats
            )
            
            # Calculate opportunity scores
            scores = self._calculate_expiry_opportunity_scores(
                listing, price_analysis, motivation_analysis, suburb_stats
            )
            
            # Create pattern object
            pattern = ExpiredListingPattern(
                property_id=property_id,
                listing_id=listing['listing_id'],
                address=listing['address'],
                suburb=listing['suburb'],
                postcode=listing['postcode'],
                first_listed_date=listing['first_listed_date'] or datetime.utcnow(),
                last_active_date=listing['last_updated_source'] or datetime.utcnow(),
                total_days_on_market=listing['days_on_market'] or 0,
                listing_count=price_analysis['listing_count'],
                original_price=price_analysis['original_price'],
                final_price=price_analysis['final_price'],
                price_reductions=price_analysis['price_reductions'],
                total_price_drop=price_analysis['total_price_drop'],
                price_drop_percentage=price_analysis['price_drop_percentage'],
                suburb_median_days=suburb_stats.get('median_days_on_market'),
                market_position_percentile=self._calculate_market_position_percentile(
                    listing, suburb_stats
                ),
                price_vs_suburb_median=self._calculate_price_vs_median(
                    listing, suburb_stats
                ),
                expiry_reason=expiry_reason,
                motivation_indicators=motivation_analysis['indicators'],
                seller_behavior_score=motivation_analysis['behavior_score'],
                reactivation_probability=scores['reactivation_probability'],
                negotiation_potential=scores['negotiation_potential'],
                urgency_score=scores['urgency_score']
            )
            
            return pattern
            
        except Exception as e:
            self.logger.error(f"Error analyzing listing pattern: {e}")
            return None
    
    async def _get_property_price_history(self, property_id: str) -> List[Dict[str, Any]]:
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
                        'price': record.price,
                        'price_type': record.price_type,
                        'previous_price': record.previous_price,
                        'price_change': record.price_change,
                        'event_type': record.event_type,
                        'created_at': record.created_at
                    }
                    for record in history
                ]
                
        except Exception as e:
            self.logger.error(f"Error getting price history for {property_id}: {e}")
            return []
    
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
                        'days_on_market': metrics.days_on_market,
                        'suburb_price_percentile': metrics.suburb_price_percentile,
                        'sale_probability': metrics.sale_probability
                    }
                
                return {}
                
        except Exception as e:
            self.logger.error(f"Error getting market metrics for {property_id}: {e}")
            return {}
    
    async def _get_suburb_statistics(self, suburb: str) -> Dict[str, Any]:
        """Get suburb market statistics."""
        try:
            # Check cache first
            cache_key = suburb.lower()
            if cache_key in self.suburb_stats_cache:
                if datetime.utcnow() < self.cache_expiry.get(cache_key, datetime.min):
                    return self.suburb_stats_cache[cache_key]
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(SuburbMetrics).where(
                        SuburbMetrics.suburb.ilike(f"%{suburb}%")
                    ).order_by(desc(SuburbMetrics.created_at)).limit(1)
                )
                
                metrics = result.scalar_one_or_none()
                
                stats = {}
                if metrics:
                    stats = {
                        'median_price': float(metrics.median_price) if metrics.median_price else None,
                        'median_days_on_market': metrics.median_days_on_market,
                        'total_listings': metrics.total_listings,
                        'sold_listings': metrics.sold_listings,
                        'price_trend': metrics.price_trend_percent,
                        'market_activity': metrics.market_activity_score
                    }
                
                # Cache results
                self.suburb_stats_cache[cache_key] = stats
                self.cache_expiry[cache_key] = datetime.utcnow() + timedelta(hours=6)
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Error getting suburb statistics for {suburb}: {e}")
            return {}
    
    def _analyze_price_patterns(
        self, 
        price_history: List[Dict[str, Any]], 
        listing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze price change patterns."""
        try:
            if not price_history:
                return {
                    'listing_count': 1,
                    'original_price': listing.get('price'),
                    'final_price': listing.get('price'),
                    'price_reductions': 0,
                    'total_price_drop': None,
                    'price_drop_percentage': None,
                    'price_pattern': 'no_history'
                }
            
            # Sort by date
            sorted_history = sorted(price_history, key=lambda x: x['created_at'])
            
            # Count listings (new listing events)
            listing_count = len([h for h in sorted_history if h['event_type'] == 'listing'])
            if listing_count == 0:
                listing_count = 1
            
            # Get original and final prices
            original_price = None
            final_price = None
            
            for record in sorted_history:
                if record['price_type'] == 'asking' and original_price is None:
                    original_price = record['price']
                if record['price_type'] == 'asking':
                    final_price = record['price']
            
            # If no asking prices found, use listing price
            if original_price is None:
                original_price = listing.get('price')
            if final_price is None:
                final_price = listing.get('price')
            
            # Count price reductions
            price_reductions = len([
                h for h in sorted_history 
                if h['event_type'] == 'update' and h['price_change'] and h['price_change'] < 0
            ])
            
            # Calculate total price drop
            total_price_drop = None
            price_drop_percentage = None
            
            if original_price and final_price and original_price != final_price:
                total_price_drop = original_price - final_price
                if original_price > 0:
                    price_drop_percentage = float(total_price_drop / original_price * 100)
            
            # Determine price pattern
            price_pattern = 'stable'
            if price_reductions > 2:
                price_pattern = 'multiple_reductions'
            elif price_reductions > 0:
                price_pattern = 'single_reduction'
            elif listing_count > 1:
                price_pattern = 'relisted_same_price'
            
            return {
                'listing_count': listing_count,
                'original_price': original_price,
                'final_price': final_price,
                'price_reductions': price_reductions,
                'total_price_drop': total_price_drop,
                'price_drop_percentage': price_drop_percentage,
                'price_pattern': price_pattern
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing price patterns: {e}")
            return {
                'listing_count': 1,
                'original_price': listing.get('price'),
                'final_price': listing.get('price'),
                'price_reductions': 0,
                'total_price_drop': None,
                'price_drop_percentage': None,
                'price_pattern': 'error'
            }
    
    def _determine_expiry_reason(
        self, 
        listing: Dict[str, Any],
        price_analysis: Dict[str, Any],
        market_metrics: Dict[str, Any]
    ) -> str:
        """Determine the likely reason for listing expiry."""
        try:
            days_on_market = listing.get('days_on_market', 0)
            price_reductions = price_analysis.get('price_reductions', 0)
            enquiry_count = market_metrics.get('enquiry_count', 0)
            view_count = market_metrics.get('view_count', 0)
            
            # Time-based expiry
            if days_on_market > self.extended_market_time_days:
                if price_reductions == 0:
                    return 'price_resistance'
                else:
                    return 'market_conditions'
            
            # Low interest indicators
            if enquiry_count < 5 and view_count < 100:
                return 'low_interest'
            
            # Agent or seller decision
            if days_on_market < 60:
                return 'agent_withdrawal'
            
            # Price resistance
            if price_reductions == 0 and days_on_market > 90:
                return 'price_resistance'
            
            # Default
            return 'time_expired'
            
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.warning(f"Failed to determine expired listing reason: {e}", 
                          listing_id=listing.get('id', 'unknown'), exc_info=True)
            return 'unknown'
    
    def _assess_seller_motivation(
        self,
        listing: Dict[str, Any],
        price_analysis: Dict[str, Any],
        market_metrics: Dict[str, Any],
        suburb_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess seller motivation based on behavior patterns."""
        try:
            indicators = []
            behavior_score = 0.0
            
            # Price reduction indicators (higher motivation)
            price_reductions = price_analysis.get('price_reductions', 0)
            if price_reductions >= 3:
                indicators.append('multiple_price_drops')
                behavior_score += 0.3
            elif price_reductions >= 1:
                indicators.append('price_reduction')
                behavior_score += 0.15
            
            # Price drop percentage
            price_drop_pct = price_analysis.get('price_drop_percentage', 0)
            if price_drop_pct and price_drop_pct > 15:
                indicators.append('significant_price_drop')
                behavior_score += 0.25
            elif price_drop_pct and price_drop_pct > 5:
                indicators.append('moderate_price_drop')
                behavior_score += 0.1
            
            # Extended market time
            days_on_market = listing.get('days_on_market', 0)
            suburb_median_days = suburb_stats.get('median_days_on_market', 60)
            
            if days_on_market > suburb_median_days * 2:
                indicators.append('extended_market_time')
                behavior_score += 0.2
            
            # Multiple listing attempts
            listing_count = price_analysis.get('listing_count', 1)
            if listing_count > 2:
                indicators.append('repeated_listing')
                behavior_score += 0.15
            elif listing_count > 1:
                indicators.append('relisted')
                behavior_score += 0.1
            
            # Low market engagement
            enquiry_count = market_metrics.get('enquiry_count', 0)
            if enquiry_count < 3:
                indicators.append('low_enquiry')
                behavior_score += 0.05
            
            # Price position vs market
            suburb_median = suburb_stats.get('median_price')
            listing_price = listing.get('price')
            
            if suburb_median and listing_price:
                price_premium = (listing_price - suburb_median) / suburb_median
                if price_premium > 0.2:  # 20% above median
                    indicators.append('overpriced')
                    behavior_score -= 0.1  # Actually reduces motivation score
                elif price_premium < -0.1:  # 10% below median
                    indicators.append('competitively_priced')
                    behavior_score += 0.1
            
            # Seasonal factors (simplified)
            current_month = datetime.utcnow().month
            if current_month in [6, 7, 8]:  # Winter months in Australia
                indicators.append('winter_listing')
                behavior_score += 0.05  # Slight increase due to off-season
            
            # Normalize behavior score
            behavior_score = min(1.0, max(0.0, behavior_score))
            
            return {
                'indicators': indicators,
                'behavior_score': behavior_score,
                'motivation_level': self._categorize_motivation(behavior_score)
            }
            
        except Exception as e:
            self.logger.error(f"Error assessing seller motivation: {e}")
            return {
                'indicators': [],
                'behavior_score': 0.0,
                'motivation_level': 'unknown'
            }
    
    def _categorize_motivation(self, behavior_score: float) -> str:
        """Categorize motivation level."""
        if behavior_score >= 0.7:
            return 'highly_motivated'
        elif behavior_score >= 0.4:
            return 'motivated'
        elif behavior_score >= 0.2:
            return 'somewhat_motivated'
        else:
            return 'low_motivation'
    
    def _calculate_market_position_percentile(
        self, 
        listing: Dict[str, Any], 
        suburb_stats: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate market position percentile for the listing."""
        try:
            days_on_market = listing.get('days_on_market', 0)
            suburb_median_days = suburb_stats.get('median_days_on_market')
            
            if not suburb_median_days:
                return None
            
            # Simple percentile calculation (would be more sophisticated in production)
            if days_on_market <= suburb_median_days * 0.5:
                return 25.0  # Fast sale
            elif days_on_market <= suburb_median_days:
                return 50.0  # Average
            elif days_on_market <= suburb_median_days * 1.5:
                return 75.0  # Slow
            else:
                return 90.0  # Very slow
                
        except (ValueError, ZeroDivisionError, TypeError) as e:
            logger = structlog.get_logger(__name__)
            logger.warning(f"Failed to calculate days on market percentile: {e}", exc_info=True)
            return None
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"Unexpected error calculating market percentile: {e}", exc_info=True)
            raise ValidationError("market_percentile", None, f"Calculation failed: {e}") from e
    
    def _calculate_price_vs_median(
        self, 
        listing: Dict[str, Any], 
        suburb_stats: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate price position vs suburb median."""
        try:
            listing_price = listing.get('price')
            suburb_median = suburb_stats.get('median_price')
            
            if not listing_price or not suburb_median or suburb_median == 0:
                return None
            
            return float((listing_price - suburb_median) / suburb_median)
            
        except (ValueError, ZeroDivisionError, TypeError) as e:
            logger = structlog.get_logger(__name__)
            logger.warning(f"Failed to calculate price vs median: {e}", exc_info=True)
            return None
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"Unexpected error calculating price comparison: {e}", exc_info=True)
            raise ValidationError("price_comparison", None, f"Price calculation failed: {e}") from e
    
    def _calculate_expiry_opportunity_scores(
        self,
        listing: Dict[str, Any],
        price_analysis: Dict[str, Any],
        motivation_analysis: Dict[str, Any],
        suburb_stats: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate opportunity scores for expired listing."""
        try:
            behavior_score = motivation_analysis.get('behavior_score', 0.0)
            days_since_expired = (
                datetime.utcnow() - listing.get('last_updated_source', datetime.utcnow())
            ).days
            
            # Reactivation probability
            reactivation_probability = 0.5  # Base probability
            
            # Increase if highly motivated seller
            if behavior_score > 0.6:
                reactivation_probability += 0.3
            elif behavior_score > 0.3:
                reactivation_probability += 0.1
            
            # Decrease over time since expiry
            if days_since_expired > 60:
                reactivation_probability -= 0.2
            elif days_since_expired > 30:
                reactivation_probability -= 0.1
            
            # Adjust for price reductions (more reductions = higher reactivation)
            price_reductions = price_analysis.get('price_reductions', 0)
            reactivation_probability += min(0.2, price_reductions * 0.05)
            
            # Negotiation potential
            negotiation_potential = behavior_score  # Base on seller motivation
            
            # Increase if property has been on market long
            days_on_market = listing.get('days_on_market', 0)
            if days_on_market > 120:
                negotiation_potential += 0.2
            elif days_on_market > 90:
                negotiation_potential += 0.1
            
            # Increase if multiple price drops
            if price_reductions >= 2:
                negotiation_potential += 0.15
            
            # Urgency score
            urgency_score = 0.0
            
            # Recent expiry increases urgency
            if days_since_expired <= 14:
                urgency_score += 0.4
            elif days_since_expired <= 30:
                urgency_score += 0.2
            
            # High motivation increases urgency
            urgency_score += behavior_score * 0.3
            
            # Market conditions affect urgency
            market_activity = suburb_stats.get('market_activity', 0.5)
            if market_activity < 0.3:  # Low market activity
                urgency_score += 0.1
            
            # Normalize scores
            reactivation_probability = min(1.0, max(0.0, reactivation_probability))
            negotiation_potential = min(1.0, max(0.0, negotiation_potential))
            urgency_score = min(1.0, max(0.0, urgency_score))
            
            return {
                'reactivation_probability': reactivation_probability,
                'negotiation_potential': negotiation_potential,
                'urgency_score': urgency_score
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating opportunity scores: {e}")
            return {
                'reactivation_probability': 0.3,
                'negotiation_potential': 0.3,
                'urgency_score': 0.3
            }
    
    async def _create_opportunity_from_pattern(
        self, 
        pattern: ExpiredListingPattern
    ) -> Optional[OffMarketOpportunity]:
        """Create an opportunity from an expired listing pattern."""
        try:
            # Calculate overall opportunity score
            overall_score = (
                pattern.seller_behavior_score * 0.4 +
                pattern.negotiation_potential * 0.3 +
                pattern.urgency_score * 0.2 +
                pattern.reactivation_probability * 0.1
            )
            
            # Must meet minimum threshold
            if overall_score < 0.3:
                return None
            
            # Create opportunity score object
            scoring = OpportunityScore(
                overall_score=overall_score,
                roi_potential=pattern.negotiation_potential,
                acquisition_difficulty=1.0 - pattern.reactivation_probability,
                time_sensitivity=pattern.urgency_score,
                market_conditions=0.5,  # Would get from market data
                seller_motivation=pattern.seller_behavior_score,
                price_attractiveness=min(1.0, abs(pattern.price_drop_percentage or 0) / 20),
                location_desirability=0.6  # Would calculate from suburb data
            )
            
            # Estimate potential purchase price
            potential_purchase_price = None
            estimated_roi = None
            
            if pattern.final_price:
                # Estimate 5-15% discount based on motivation
                discount_pct = 0.05 + (pattern.seller_behavior_score * 0.1)
                potential_purchase_price = pattern.final_price * (1 - discount_pct)
                
                if pattern.suburb_median_days:
                    # Simple ROI estimate based on market conditions
                    estimated_roi = (pattern.final_price - potential_purchase_price) / potential_purchase_price * 100
                    estimated_roi = min(30.0, max(0.0, estimated_roi))  # Cap at reasonable range
            
            # Create opportunity
            opportunity = OffMarketOpportunity(
                opportunity_type=OpportunityType.EXPIRED_LISTING,
                property_id=pattern.property_id,
                listing_id=pattern.listing_id,
                address=pattern.address,
                suburb=pattern.suburb,
                postcode=pattern.postcode,
                title=f"Expired Listing: {pattern.address}",
                description=self._generate_expired_listing_description(pattern),
                current_price=pattern.final_price,
                potential_purchase_price=potential_purchase_price,
                estimated_roi_percent=estimated_roi,
                scoring=scoring,
                opportunity_details={
                    'days_on_market': pattern.total_days_on_market,
                    'listing_count': pattern.listing_count,
                    'price_reductions': pattern.price_reductions,
                    'total_price_drop': float(pattern.total_price_drop) if pattern.total_price_drop else None,
                    'price_drop_percentage': pattern.price_drop_percentage,
                    'expiry_reason': pattern.expiry_reason,
                    'days_since_expired': pattern.days_since_expired,
                    'seller_behavior_score': pattern.seller_behavior_score,
                    'motivation_level': self._categorize_motivation(pattern.seller_behavior_score)
                },
                data_sources=['expired_listings', 'price_history', 'market_metrics'],
                evidence={
                    'pattern_analysis': {
                        'reactivation_probability': pattern.reactivation_probability,
                        'negotiation_potential': pattern.negotiation_potential,
                        'urgency_score': pattern.urgency_score,
                        'motivation_indicators': pattern.motivation_indicators
                    }
                },
                confidence_level=overall_score,
                expires_at=datetime.utcnow() + timedelta(days=180),  # 6 months validity
                tags=self._generate_expired_listing_tags(pattern),
                compliance_checked=True,
                ethical_approval=True,
                data_privacy_compliant=True
            )
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error creating opportunity from pattern: {e}")
            return None
    
    def _generate_expired_listing_description(self, pattern: ExpiredListingPattern) -> str:
        """Generate description for expired listing opportunity."""
        try:
            desc = f"Expired listing at {pattern.address} ({pattern.suburb}) "
            desc += f"after {pattern.total_days_on_market} days on market. "
            
            if pattern.price_reductions > 0:
                desc += f"Property had {pattern.price_reductions} price reduction{'s' if pattern.price_reductions > 1 else ''}"
                if pattern.price_drop_percentage:
                    desc += f" totaling {pattern.price_drop_percentage:.1f}% decrease"
                desc += ". "
            
            if pattern.listing_count > 1:
                desc += f"Property was relisted {pattern.listing_count} times. "
            
            motivation_level = self._categorize_motivation(pattern.seller_behavior_score)
            desc += f"Seller appears {motivation_level.replace('_', ' ')} "
            desc += f"(score: {pattern.seller_behavior_score:.2f}). "
            
            desc += f"Estimated negotiation potential: {pattern.negotiation_potential:.1%}, "
            desc += f"reactivation probability: {pattern.reactivation_probability:.1%}."
            
            return desc
            
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.warning(f"Failed to generate expired listing description: {e}", 
                          address=getattr(pattern, 'address', 'unknown'), exc_info=True)
            return f"Expired listing opportunity at {getattr(pattern, 'address', 'unknown address')}"
    
    def _generate_expired_listing_tags(self, pattern: ExpiredListingPattern) -> List[str]:
        """Generate tags for expired listing opportunity."""
        tags = ['expired_listing', 'price_negotiation']
        
        # Add expiry reason tag
        tags.append(f'expiry_{pattern.expiry_reason}')
        
        # Add motivation level tag
        motivation_level = self._categorize_motivation(pattern.seller_behavior_score)
        tags.append(motivation_level)
        
        # Add price drop tags
        if pattern.price_reductions > 0:
            tags.append('price_reduced')
            if pattern.price_reductions >= 3:
                tags.append('multiple_reductions')
        
        # Add market time tags
        if pattern.total_days_on_market > 120:
            tags.append('extended_market_time')
        
        # Add relisting tags
        if pattern.listing_count > 1:
            tags.append('relisted')
            if pattern.listing_count > 2:
                tags.append('multiple_listings')
        
        # Add urgency tags
        if pattern.is_recent_expiry:
            tags.append('recent_expiry')
        
        if pattern.urgency_score > 0.7:
            tags.append('high_urgency')
        
        return tags
    
    async def _preload_suburb_statistics(self) -> None:
        """Preload suburb statistics for faster analysis."""
        try:
            # Get list of active suburbs from recent properties
            async with get_db_session() as session:
                result = await session.execute(
                    select(Property.suburb).distinct().where(
                        and_(
                            Property.postcode.between('2000', '2999'),
                            Property.created_at >= datetime.utcnow() - timedelta(days=90)
                        )
                    )
                )
                
                suburbs = [row[0] for row in result.fetchall()]
            
            # Preload statistics for each suburb
            for suburb in suburbs[:50]:  # Limit to avoid overload
                await self._get_suburb_statistics(suburb)
            
            self.logger.info(f"Preloaded statistics for {len(suburbs)} suburbs")
            
        except Exception as e:
            self.logger.warning(f"Failed to preload suburb statistics: {e}")
    
    async def get_expired_listing_summary(
        self, 
        suburb: str = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get summary of expired listings for analysis."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            async with get_db_session() as session:
                query = select(Property).where(
                    and_(
                        Property.listing_status.in_(['withdrawn', 'off_market', 'expired']),
                        Property.last_updated_source >= cutoff_date,
                        Property.postcode.between('2000', '2999')
                    )
                )
                
                if suburb:
                    query = query.where(Property.suburb.ilike(f"%{suburb}%"))
                
                result = await session.execute(query)
                properties = result.scalars().all()
                
                # Analyze patterns
                total_expired = len(properties)
                with_price_drops = len([p for p in properties if p.days_on_market > 90])
                recent_expiries = len([
                    p for p in properties 
                    if (datetime.utcnow() - (p.last_updated_source or datetime.utcnow())).days <= 14
                ])
                
                avg_days_on_market = statistics.mean([
                    p.days_on_market for p in properties if p.days_on_market
                ]) if properties else 0
                
                return {
                    'total_expired_listings': total_expired,
                    'recent_expiries': recent_expiries,
                    'extended_market_time_count': with_price_drops,
                    'average_days_on_market': round(avg_days_on_market, 1),
                    'analysis_period_days': days_back,
                    'suburb': suburb or 'All Sydney',
                    'generated_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting expired listing summary: {e}")
            return {
                'total_expired_listings': 0,
                'recent_expiries': 0,
                'extended_market_time_count': 0,
                'average_days_on_market': 0,
                'analysis_period_days': days_back,
                'suburb': suburb or 'All Sydney',
                'error': str(e)
            }