"""
ReAgent Sydney - Opportunity Ranker

Advanced ranking system for prioritizing off-market opportunities based on
ROI potential, acquisition difficulty, time sensitivity, and market conditions.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from dataclasses import dataclass
import statistics
import math

from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import sessionmaker
import structlog

from ...core.database.engine import get_db_session
from ...data.models.property_models import Property, PropertyMarketMetrics
from ...data.models.market_models import SuburbMetrics
from ...core.exceptions import ValidationError, DatabaseQueryError, AgentExecutionError
from .data_models import OffMarketOpportunity, OpportunityScore, OpportunityType


@dataclass
class RankingCriteria:
    """Criteria for ranking opportunities."""
    
    # Weight factors (must sum to 1.0)
    roi_weight: float = 0.35          # Return on investment potential
    urgency_weight: float = 0.25      # Time sensitivity
    confidence_weight: float = 0.20   # Confidence in the opportunity
    acquisition_weight: float = 0.15  # Ease of acquisition (inverse of difficulty)
    market_weight: float = 0.05       # Market conditions
    
    # Minimum thresholds
    min_roi_potential: float = 0.3
    min_confidence_level: float = 0.4
    min_overall_score: float = 0.5
    
    # Bonus factors
    multiple_signals_bonus: float = 0.1  # Bonus for multiple opportunity types
    recent_discovery_bonus: float = 0.05  # Bonus for recently discovered
    location_premium_bonus: float = 0.05  # Bonus for premium locations
    
    def __post_init__(self):
        """Validate that weights sum to 1.0."""
        total_weight = (self.roi_weight + self.urgency_weight + 
                       self.confidence_weight + self.acquisition_weight + 
                       self.market_weight)
        
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Ranking weights must sum to 1.0, got {total_weight}")


@dataclass
class MarketContext:
    """Market context for ranking decisions."""
    
    suburb_performance: float  # 0.0 to 1.0
    market_velocity: float     # How quickly properties sell
    price_trend: float         # Price appreciation trend
    competition_level: float   # Level of buyer competition
    seasonal_factor: float     # Seasonal market conditions
    economic_indicators: Dict[str, float]


class OpportunityRanker:
    """
    Advanced opportunity ranking system.
    
    Ranks opportunities based on:
    1. ROI potential and profit margins
    2. Time sensitivity and urgency
    3. Confidence level and data quality
    4. Acquisition difficulty and barriers
    5. Market conditions and timing
    6. Strategic fit and portfolio alignment
    """
    
    def __init__(self, radar_config):
        self.radar_config = radar_config
        self.logger = structlog.get_logger("off_market_radar.opportunity_ranker")
        
        # Default ranking criteria
        self.default_criteria = RankingCriteria()
        
        # Market context cache
        self.market_context_cache = {}
        self.cache_expiry = {}
        
        # Premium suburb list for location bonuses
        self.premium_suburbs = {
            'double bay', 'point piper', 'vaucluse', 'bellevue hill',
            'mosman', 'kirribilli', 'milsons point', 'neutral bay',
            'woollahra', 'paddington', 'bondi beach', 'bronte',
            'tamarama', 'dover heights', 'rose bay', 'watsons bay'
        }
    
    async def initialize(self) -> None:
        """Initialize the opportunity ranker."""
        try:
            # Preload market context for major suburbs
            await self._preload_market_context()
            
            self.logger.info("Opportunity Ranker initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Opportunity Ranker: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup opportunity ranker resources."""
        try:
            # Clear caches
            self.market_context_cache.clear()
            self.cache_expiry.clear()
            
            self.logger.info("Opportunity Ranker cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Opportunity Ranker cleanup: {e}")
    
    async def rank_opportunities(
        self, 
        opportunities: List[OffMarketOpportunity],
        criteria: Optional[RankingCriteria] = None,
        max_results: Optional[int] = None
    ) -> List[OffMarketOpportunity]:
        """
        Rank opportunities by their potential value.
        
        Args:
            opportunities: List of opportunities to rank
            criteria: Custom ranking criteria (uses default if None)
            max_results: Maximum number of results to return
            
        Returns:
            Ranked list of opportunities
        """
        if not opportunities:
            return []
        
        criteria = criteria or self.default_criteria
        
        try:
            self.logger.info(f"Ranking {len(opportunities)} opportunities")
            
            # Calculate comprehensive scores for each opportunity
            scored_opportunities = []
            for opportunity in opportunities:
                try:
                    comprehensive_score = await self._calculate_comprehensive_score(
                        opportunity, criteria
                    )
                    
                    # Update the opportunity's scoring
                    opportunity.scoring = comprehensive_score
                    opportunity.priority_score = comprehensive_score.priority_score
                    
                    # Only include opportunities that meet minimum thresholds
                    if (comprehensive_score.overall_score >= criteria.min_overall_score and
                        comprehensive_score.roi_potential >= criteria.min_roi_potential and
                        opportunity.confidence_level >= criteria.min_confidence_level):
                        
                        scored_opportunities.append(opportunity)
                    
                except Exception as e:
                    self.logger.warning(f"Error scoring opportunity {opportunity.id}: {e}")
                    continue
            
            # Sort by priority score (descending)
            scored_opportunities.sort(
                key=lambda x: x.priority_score, 
                reverse=True
            )
            
            # Apply max results limit
            if max_results:
                scored_opportunities = scored_opportunities[:max_results]
            
            # Add ranking metadata
            for i, opportunity in enumerate(scored_opportunities):
                opportunity.opportunity_details['ranking'] = {
                    'rank': i + 1,
                    'percentile': ((len(scored_opportunities) - i) / len(scored_opportunities)) * 100,
                    'ranking_criteria': criteria.__dict__,
                    'ranked_at': datetime.utcnow().isoformat()
                }
            
            self.logger.info(f"Ranked {len(scored_opportunities)} qualifying opportunities")
            
            return scored_opportunities
            
        except Exception as e:
            self.logger.error(f"Error ranking opportunities: {e}")
            return opportunities  # Return unranked if ranking fails
    
    async def _calculate_comprehensive_score(
        self, 
        opportunity: OffMarketOpportunity,
        criteria: RankingCriteria
    ) -> OpportunityScore:
        """Calculate comprehensive opportunity score."""
        try:
            # Get market context
            market_context = await self._get_market_context(opportunity.suburb)
            
            # Calculate component scores
            roi_score = await self._calculate_roi_score(opportunity, market_context)
            urgency_score = await self._calculate_urgency_score(opportunity, market_context)
            confidence_score = self._calculate_confidence_score(opportunity)
            acquisition_score = await self._calculate_acquisition_score(opportunity, market_context)
            market_score = self._calculate_market_score(market_context)
            
            # Calculate weighted overall score
            overall_score = (
                roi_score * criteria.roi_weight +
                urgency_score * criteria.urgency_weight +
                confidence_score * criteria.confidence_weight +
                acquisition_score * criteria.acquisition_weight +
                market_score * criteria.market_weight
            )
            
            # Apply bonus factors
            bonus_score = self._calculate_bonus_factors(opportunity, criteria)
            overall_score = min(1.0, overall_score + bonus_score)
            
            # Calculate additional scoring components
            price_attractiveness = await self._calculate_price_attractiveness(opportunity, market_context)
            location_desirability = self._calculate_location_desirability(opportunity, market_context)
            seller_motivation = self._calculate_seller_motivation(opportunity)
            
            # Risk assessments
            legal_risk = self._calculate_legal_risk(opportunity)
            market_risk = self._calculate_market_risk(opportunity, market_context)
            execution_risk = self._calculate_execution_risk(opportunity)
            
            # Create comprehensive score object
            comprehensive_score = OpportunityScore(
                overall_score=overall_score,
                roi_potential=roi_score,
                acquisition_difficulty=1.0 - acquisition_score,  # Invert for difficulty
                time_sensitivity=urgency_score,
                market_conditions=market_score,
                price_attractiveness=price_attractiveness,
                location_desirability=location_desirability,
                property_condition=0.5,  # Would need property inspection data
                seller_motivation=seller_motivation,
                legal_risk=legal_risk,
                market_risk=market_risk,
                execution_risk=execution_risk
            )
            
            return comprehensive_score
            
        except Exception as e:
            self.logger.error(f"Error calculating comprehensive score: {e}")
            # Return default score if calculation fails
            return opportunity.scoring or OpportunityScore()
    
    async def _calculate_roi_score(
        self, 
        opportunity: OffMarketOpportunity,
        market_context: MarketContext
    ) -> float:
        """Calculate ROI potential score."""
        try:
            roi_score = 0.0
            
            # Base ROI from estimated percentage
            if opportunity.estimated_roi_percent:
                # Normalize ROI percentage to 0-1 score
                # 20% ROI = 1.0 score, 5% ROI = 0.25 score
                roi_score = min(1.0, opportunity.estimated_roi_percent / 20)
            
            # Price discount potential
            if opportunity.current_price and opportunity.potential_purchase_price:
                discount_pct = ((opportunity.current_price - opportunity.potential_purchase_price) 
                               / opportunity.current_price) * 100
                discount_score = min(1.0, discount_pct / 15)  # 15% discount = max score
                roi_score = max(roi_score, discount_score)
            
            # Market appreciation potential
            if market_context.price_trend > 0:
                appreciation_bonus = min(0.2, market_context.price_trend * 0.1)
                roi_score += appreciation_bonus
            
            # Opportunity type multipliers
            type_multipliers = {
                OpportunityType.DISTRESS_SIGNAL: 1.2,    # Higher ROI potential
                OpportunityType.EXPIRED_LISTING: 1.1,    # Good ROI potential
                OpportunityType.COUNCIL_DA: 1.3,         # Development potential
                OpportunityType.MARKET_ANOMALY: 1.0,     # Standard ROI
                OpportunityType.OWNER_MOTIVATION: 1.1,   # Good negotiation potential
            }
            
            multiplier = type_multipliers.get(opportunity.opportunity_type, 1.0)
            roi_score *= multiplier
            
            return min(1.0, roi_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating ROI score: {e}")
            return 0.5  # Default moderate score
    
    async def _calculate_urgency_score(
        self, 
        opportunity: OffMarketOpportunity,
        market_context: MarketContext
    ) -> float:
        """Calculate time sensitivity/urgency score."""
        try:
            urgency_score = 0.0
            
            # Time since discovery
            days_since_discovery = (datetime.utcnow() - opportunity.discovered_at).days
            
            # Fresher opportunities get higher urgency
            if days_since_discovery <= 7:
                urgency_score += 0.4
            elif days_since_discovery <= 30:
                urgency_score += 0.2
            
            # Expiry date proximity
            if opportunity.expires_at:
                days_to_expiry = (opportunity.expires_at - datetime.utcnow()).days
                if days_to_expiry <= 30:
                    urgency_score += 0.3
                elif days_to_expiry <= 90:
                    urgency_score += 0.1
            
            # Market velocity impact
            if market_context.market_velocity > 0.7:
                urgency_score += 0.2  # Fast-moving market increases urgency
            
            # Opportunity type urgency factors
            type_urgency = {
                OpportunityType.DISTRESS_SIGNAL: 0.8,    # High urgency
                OpportunityType.EXPIRED_LISTING: 0.6,    # Moderate urgency
                OpportunityType.COUNCIL_DA: 0.4,         # Lower urgency
                OpportunityType.MARKET_ANOMALY: 0.5,     # Moderate urgency
            }
            
            base_urgency = type_urgency.get(opportunity.opportunity_type, 0.5)
            urgency_score = max(urgency_score, base_urgency)
            
            # Competition level impact
            if market_context.competition_level > 0.7:
                urgency_score += 0.1  # High competition increases urgency
            
            return min(1.0, urgency_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating urgency score: {e}")
            return 0.5
    
    def _calculate_confidence_score(self, opportunity: OffMarketOpportunity) -> float:
        """Calculate confidence in the opportunity."""
        try:
            confidence_score = opportunity.confidence_level
            
            # Data source quality boost
            quality_sources = ['price_history', 'market_metrics', 'council_da', 'distress_analysis']
            quality_source_count = len([s for s in opportunity.data_sources if s in quality_sources])
            
            if quality_source_count >= 3:
                confidence_score += 0.1
            elif quality_source_count >= 2:
                confidence_score += 0.05
            
            # Multiple evidence types boost confidence
            if len(opportunity.evidence) >= 2:
                confidence_score += 0.05
            
            # Compliance check boost
            if (opportunity.compliance_checked and 
                opportunity.ethical_approval and 
                opportunity.data_privacy_compliant):
                confidence_score += 0.1
            
            return min(1.0, confidence_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence score: {e}")
            return opportunity.confidence_level
    
    async def _calculate_acquisition_score(
        self, 
        opportunity: OffMarketOpportunity,
        market_context: MarketContext
    ) -> float:
        """Calculate ease of acquisition score."""
        try:
            # Start with base acquisition ease
            acquisition_score = 1.0 - (opportunity.scoring.acquisition_difficulty or 0.5)
            
            # Market competition impact
            if market_context.competition_level < 0.3:
                acquisition_score += 0.2  # Low competition makes acquisition easier
            elif market_context.competition_level > 0.7:
                acquisition_score -= 0.2  # High competition makes acquisition harder
            
            # Seller motivation boost
            seller_motivation = self._calculate_seller_motivation(opportunity)
            acquisition_score += seller_motivation * 0.3
            
            # Property characteristics that affect acquisition
            if opportunity.current_price:
                # Properties under $2M might be easier to acquire (more buyers)
                if opportunity.current_price < 2000000:
                    acquisition_score += 0.1
                # Very expensive properties might be harder
                elif opportunity.current_price > 5000000:
                    acquisition_score -= 0.1
            
            # Legal/regulatory barriers
            legal_risk = self._calculate_legal_risk(opportunity)
            acquisition_score -= legal_risk * 0.2
            
            return min(1.0, max(0.0, acquisition_score))
            
        except Exception as e:
            self.logger.error(f"Error calculating acquisition score: {e}")
            return 0.5
    
    def _calculate_market_score(self, market_context: MarketContext) -> float:
        """Calculate market conditions score."""
        try:
            # Weighted average of market factors
            market_score = (
                market_context.suburb_performance * 0.4 +
                market_context.market_velocity * 0.3 +
                (1.0 - market_context.competition_level) * 0.2 +  # Lower competition is better
                market_context.seasonal_factor * 0.1
            )
            
            return min(1.0, max(0.0, market_score))
            
        except Exception as e:
            self.logger.error(f"Error calculating market score: {e}")
            return 0.5
    
    def _calculate_bonus_factors(
        self, 
        opportunity: OffMarketOpportunity,
        criteria: RankingCriteria
    ) -> float:
        """Calculate bonus factors for the opportunity."""
        try:
            bonus = 0.0
            
            # Multiple signals bonus
            if hasattr(opportunity.opportunity_details, 'get'):
                signal_count = opportunity.opportunity_details.get('signal_count', 1)
                if signal_count > 1:
                    bonus += criteria.multiple_signals_bonus
            
            # Recent discovery bonus
            days_since_discovery = (datetime.utcnow() - opportunity.discovered_at).days
            if days_since_discovery <= 7:
                bonus += criteria.recent_discovery_bonus
            
            # Premium location bonus
            if opportunity.suburb.lower() in self.premium_suburbs:
                bonus += criteria.location_premium_bonus
            
            # High-value property bonus (for sophisticated investors)
            if opportunity.current_price and opportunity.current_price > 3000000:
                bonus += 0.02  # Small bonus for high-value properties
            
            return bonus
            
        except Exception as e:
            self.logger.error(f"Error calculating bonus factors: {e}")
            return 0.0
    
    async def _calculate_price_attractiveness(
        self, 
        opportunity: OffMarketOpportunity,
        market_context: MarketContext
    ) -> float:
        """Calculate price attractiveness score."""
        try:
            if not opportunity.current_price:
                return 0.5
            
            price_attractiveness = 0.5  # Default
            
            # Compare to market median
            suburb_median = await self._get_suburb_median_price(
                opportunity.suburb, 
                opportunity.property_type
            )
            
            if suburb_median:
                price_ratio = opportunity.current_price / suburb_median
                if price_ratio < 0.8:  # 20% below median
                    price_attractiveness = 0.9
                elif price_ratio < 0.9:  # 10% below median
                    price_attractiveness = 0.8
                elif price_ratio < 1.1:  # Within 10% of median
                    price_attractiveness = 0.6
                elif price_ratio < 1.2:  # 20% above median
                    price_attractiveness = 0.4
                else:  # More than 20% above median
                    price_attractiveness = 0.2
            
            # Adjust for potential discount
            if opportunity.potential_purchase_price and opportunity.current_price:
                discount_pct = ((opportunity.current_price - opportunity.potential_purchase_price) 
                               / opportunity.current_price)
                price_attractiveness += discount_pct * 0.5  # Boost for potential discount
            
            return min(1.0, price_attractiveness)
            
        except Exception as e:
            self.logger.error(f"Error calculating price attractiveness: {e}")
            return 0.5
    
    def _calculate_location_desirability(
        self, 
        opportunity: OffMarketOpportunity,
        market_context: MarketContext
    ) -> float:
        """Calculate location desirability score."""
        try:
            # Base score from market context
            location_score = market_context.suburb_performance
            
            # Premium suburb bonus
            if opportunity.suburb.lower() in self.premium_suburbs:
                location_score += 0.2
            
            # Postcode-based scoring (Sydney Metro areas)
            postcode = opportunity.postcode
            if postcode:
                postcode_int = int(postcode) if postcode.isdigit() else 0
                
                # Premium postcodes (approximate)
                if 2000 <= postcode_int <= 2099:  # Inner Sydney
                    location_score += 0.15
                elif 2100 <= postcode_int <= 2199:  # North Shore
                    location_score += 0.1
                elif 2030 <= postcode_int <= 2039:  # Eastern Suburbs
                    location_score += 0.1
            
            return min(1.0, location_score)
            
        except Exception as e:
            self.logger.error(f"Error calculating location desirability: {e}")
            return 0.6
    
    def _calculate_seller_motivation(self, opportunity: OffMarketOpportunity) -> float:
        """Calculate seller motivation score."""
        try:
            # Base score from opportunity scoring
            motivation = opportunity.scoring.seller_motivation if opportunity.scoring else 0.5
            
            # Opportunity type indicators
            type_motivation = {
                OpportunityType.DISTRESS_SIGNAL: 0.8,    # High motivation
                OpportunityType.EXPIRED_LISTING: 0.7,    # Good motivation
                OpportunityType.COUNCIL_DA: 0.4,         # Variable motivation
                OpportunityType.MARKET_ANOMALY: 0.5,     # Moderate motivation
            }
            
            base_motivation = type_motivation.get(opportunity.opportunity_type, 0.5)
            motivation = max(motivation, base_motivation)
            
            # Evidence-based adjustments
            if 'multiple_price_drops' in opportunity.tags:
                motivation += 0.2
            if 'expired_listing' in opportunity.tags:
                motivation += 0.1
            if 'financial_pressure' in opportunity.tags:
                motivation += 0.2
            if 'extended_market_time' in opportunity.tags:
                motivation += 0.1
            
            return min(1.0, motivation)
            
        except Exception as e:
            self.logger.error(f"Error calculating seller motivation: {e}")
            return 0.5
    
    def _calculate_legal_risk(self, opportunity: OffMarketOpportunity) -> float:
        """Calculate legal risk score."""
        try:
            legal_risk = 0.1  # Base low risk
            
            # Opportunity type risks
            if opportunity.opportunity_type == OpportunityType.DISTRESS_SIGNAL:
                legal_risk += 0.2  # Distress situations may have legal complications
            elif opportunity.opportunity_type == OpportunityType.COUNCIL_DA:
                legal_risk += 0.1  # DA-related properties may have planning risks
            
            # Tag-based risk adjustments
            if 'legal_risk' in opportunity.tags:
                legal_risk += 0.3
            if 'bankruptcy' in opportunity.tags:
                legal_risk += 0.4
            if 'court_order' in opportunity.tags:
                legal_risk += 0.5
            
            # Compliance check reduces risk
            if (opportunity.compliance_checked and 
                opportunity.ethical_approval and 
                opportunity.data_privacy_compliant):
                legal_risk -= 0.05
            
            return min(1.0, max(0.0, legal_risk))
            
        except Exception as e:
            self.logger.error(f"Error calculating legal risk: {e}")
            return 0.2
    
    def _calculate_market_risk(
        self, 
        opportunity: OffMarketOpportunity,
        market_context: MarketContext
    ) -> float:
        """Calculate market risk score."""
        try:
            # Base market risk from context
            market_risk = 1.0 - market_context.suburb_performance
            
            # Price trend risk
            if market_context.price_trend < -0.05:  # Declining prices
                market_risk += 0.2
            elif market_context.price_trend > 0.10:  # Rapid price growth (bubble risk)
                market_risk += 0.1
            
            # Market velocity risk
            if market_context.market_velocity < 0.3:  # Very slow market
                market_risk += 0.1
            elif market_context.market_velocity > 0.9:  # Overheated market
                market_risk += 0.1
            
            # Seasonal risk
            if market_context.seasonal_factor < 0.4:  # Poor season
                market_risk += 0.05
            
            return min(1.0, max(0.0, market_risk))
            
        except Exception as e:
            self.logger.error(f"Error calculating market risk: {e}")
            return 0.3
    
    def _calculate_execution_risk(self, opportunity: OffMarketOpportunity) -> float:
        """Calculate execution risk score."""
        try:
            execution_risk = 0.2  # Base execution risk
            
            # Confidence level affects execution risk
            if opportunity.confidence_level < 0.5:
                execution_risk += 0.3  # Low confidence increases execution risk
            elif opportunity.confidence_level > 0.8:
                execution_risk -= 0.1  # High confidence reduces execution risk
            
            # Data source quality affects execution risk
            if len(opportunity.data_sources) < 2:
                execution_risk += 0.1  # Limited data sources increase risk
            elif len(opportunity.data_sources) >= 3:
                execution_risk -= 0.05  # Multiple data sources reduce risk
            
            # Opportunity type execution risks
            type_risks = {
                OpportunityType.DISTRESS_SIGNAL: 0.3,    # Higher execution complexity
                OpportunityType.EXPIRED_LISTING: 0.2,    # Moderate execution risk
                OpportunityType.COUNCIL_DA: 0.4,         # Complex development execution
                OpportunityType.MARKET_ANOMALY: 0.2,     # Moderate execution risk
            }
            
            type_risk = type_risks.get(opportunity.opportunity_type, 0.2)
            execution_risk = max(execution_risk, type_risk)
            
            return min(1.0, max(0.0, execution_risk))
            
        except Exception as e:
            self.logger.error(f"Error calculating execution risk: {e}")
            return 0.3
    
    async def _get_market_context(self, suburb: str) -> MarketContext:
        """Get market context for a suburb."""
        try:
            # Check cache first
            cache_key = suburb.lower()
            if cache_key in self.market_context_cache:
                if datetime.utcnow() < self.cache_expiry.get(cache_key, datetime.min):
                    return self.market_context_cache[cache_key]
            
            # Get suburb metrics from database
            async with get_db_session() as session:
                result = await session.execute(
                    select(SuburbMetrics).where(
                        SuburbMetrics.suburb.ilike(f"%{suburb}%")
                    ).order_by(desc(SuburbMetrics.created_at)).limit(1)
                )
                
                metrics = result.scalar_one_or_none()
            
            # Create market context
            if metrics:
                context = MarketContext(
                    suburb_performance=min(1.0, max(0.0, metrics.market_activity_score or 0.5)),
                    market_velocity=min(1.0, max(0.0, (100 - (metrics.median_days_on_market or 60)) / 100)),
                    price_trend=min(1.0, max(-1.0, (metrics.price_trend_percent or 0) / 100)),
                    competition_level=min(1.0, max(0.0, (metrics.sold_listings or 10) / (metrics.total_listings or 20))),
                    seasonal_factor=self._get_seasonal_factor(),
                    economic_indicators={}
                )
            else:
                # Default context for unknown suburbs
                context = MarketContext(
                    suburb_performance=0.5,
                    market_velocity=0.5,
                    price_trend=0.02,  # 2% growth
                    competition_level=0.5,
                    seasonal_factor=self._get_seasonal_factor(),
                    economic_indicators={}
                )
            
            # Cache the result
            self.market_context_cache[cache_key] = context
            self.cache_expiry[cache_key] = datetime.utcnow() + timedelta(hours=6)
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error getting market context for {suburb}: {e}")
            # Return default context
            return MarketContext(
                suburb_performance=0.5,
                market_velocity=0.5,
                price_trend=0.02,
                competition_level=0.5,
                seasonal_factor=self._get_seasonal_factor(),
                economic_indicators={}
            )
    
    def _get_seasonal_factor(self) -> float:
        """Get current seasonal factor for Australian property market."""
        try:
            current_month = datetime.utcnow().month
            
            # Australian property seasons
            seasonal_scores = {
                1: 0.7, 2: 0.7, 3: 0.6,   # Summer/Early Autumn
                4: 0.6, 5: 0.5, 6: 0.3,   # Autumn/Winter
                7: 0.3, 8: 0.3, 9: 0.8,   # Winter/Spring
                10: 0.9, 11: 0.9, 12: 0.8  # Spring/Summer
            }
            
            return seasonal_scores.get(current_month, 0.5)
            
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.warning(f"Failed to calculate seasonal multiplier: {e}", exc_info=True)
            return 0.5
    
    async def _get_suburb_median_price(
        self, 
        suburb: str, 
        property_type: Optional[str] = None
    ) -> Optional[float]:
        """Get median price for suburb and property type."""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(SuburbMetrics.median_price).where(
                        SuburbMetrics.suburb.ilike(f"%{suburb}%")
                    ).order_by(desc(SuburbMetrics.created_at)).limit(1)
                )
                
                median_price = result.scalar_one_or_none()
                return float(median_price) if median_price else None
                
        except Exception as e:
            self.logger.error(f"Error getting suburb median price: {e}")
            return None
    
    async def _preload_market_context(self) -> None:
        """Preload market context for major suburbs."""
        try:
            major_suburbs = [
                'sydney', 'bondi', 'manly', 'newtown', 'paddington',
                'double bay', 'mosman', 'neutral bay', 'balmain', 'leichhardt'
            ]
            
            for suburb in major_suburbs:
                await self._get_market_context(suburb)
            
            self.logger.info(f"Preloaded market context for {len(major_suburbs)} suburbs")
            
        except Exception as e:
            self.logger.warning(f"Failed to preload market context: {e}")
    
    async def get_ranking_analytics(
        self, 
        opportunities: List[OffMarketOpportunity]
    ) -> Dict[str, Any]:
        """Get analytics on opportunity rankings."""
        try:
            if not opportunities:
                return {'error': 'No opportunities provided'}
            
            # Calculate statistics
            priority_scores = [opp.priority_score for opp in opportunities]
            roi_potentials = [opp.scoring.roi_potential for opp in opportunities]
            confidence_levels = [opp.confidence_level for opp in opportunities]
            
            # Opportunity type distribution
            type_distribution = {}
            for opp in opportunities:
                opp_type = opp.opportunity_type.value
                type_distribution[opp_type] = type_distribution.get(opp_type, 0) + 1
            
            # Suburb distribution
            suburb_distribution = {}
            for opp in opportunities:
                suburb = opp.suburb
                suburb_distribution[suburb] = suburb_distribution.get(suburb, 0) + 1
            
            # Top opportunities
            top_opportunities = sorted(opportunities, key=lambda x: x.priority_score, reverse=True)[:5]
            
            return {
                'total_opportunities': len(opportunities),
                'score_statistics': {
                    'priority_score': {
                        'mean': statistics.mean(priority_scores),
                        'median': statistics.median(priority_scores),
                        'std': statistics.stdev(priority_scores) if len(priority_scores) > 1 else 0,
                        'min': min(priority_scores),
                        'max': max(priority_scores)
                    },
                    'roi_potential': {
                        'mean': statistics.mean(roi_potentials),
                        'median': statistics.median(roi_potentials),
                        'std': statistics.stdev(roi_potentials) if len(roi_potentials) > 1 else 0
                    },
                    'confidence_level': {
                        'mean': statistics.mean(confidence_levels),
                        'median': statistics.median(confidence_levels),
                        'std': statistics.stdev(confidence_levels) if len(confidence_levels) > 1 else 0
                    }
                },
                'type_distribution': type_distribution,
                'suburb_distribution': dict(sorted(suburb_distribution.items(), key=lambda x: x[1], reverse=True)[:10]),
                'top_opportunities': [
                    {
                        'id': opp.id,
                        'title': opp.title,
                        'suburb': opp.suburb,
                        'priority_score': opp.priority_score,
                        'opportunity_type': opp.opportunity_type.value,
                        'estimated_roi_percent': opp.estimated_roi_percent
                    }
                    for opp in top_opportunities
                ],
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating ranking analytics: {e}")
            return {'error': str(e)}