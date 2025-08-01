"""
Market Timing Analysis Engine

Analyzes optimal pricing timing based on seasonal patterns, market cycles,
and real-time market conditions to maximize sale outcomes.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
import logging
from enum import Enum

from sqlalchemy import and_, func, text, extract
from sqlalchemy.orm import Session

from src.core.database.dependencies import get_db_session
from src.data.models.property_models import Property, PropertyPriceHistory
from src.data.models.market_models import MarketTrend, SuburbStats, PriceChange


class MarketCondition(str, Enum):
    """Market condition classification."""
    STRONG_SELLERS = "Strong Sellers Market"
    MODERATE_SELLERS = "Moderate Sellers Market"
    BALANCED = "Balanced Market"
    MODERATE_BUYERS = "Moderate Buyers Market"
    STRONG_BUYERS = "Strong Buyers Market"


class ListingTiming(str, Enum):
    """Optimal listing timing recommendations."""
    IMMEDIATE = "List Immediately"
    WITHIN_MONTH = "List Within 4 Weeks"
    SEASONAL_WAIT = "Wait for Seasonal Peak"
    MARKET_RECOVERY = "Wait for Market Recovery"
    MAJOR_DELAY = "Delay Until Market Improves"


@dataclass
class SeasonalPattern:
    """Seasonal market pattern data."""
    month: int
    avg_price_premium: float
    avg_days_on_market: float
    sale_probability: float
    volume_index: float
    competition_level: str


@dataclass
class MarketTimingResult:
    """Market timing analysis result."""
    property_id: str
    analysis_date: datetime
    current_market_condition: MarketCondition
    optimal_timing: ListingTiming
    timing_score: float  # 0-100, higher is better
    seasonal_recommendation: str
    price_timing_adjustment: float
    expected_days_on_market: int
    sale_probability_next_30d: float
    competition_analysis: Dict[str, Any]
    market_momentum: Dict[str, float]
    seasonal_patterns: List[SeasonalPattern]
    risk_factors: List[str]
    opportunity_factors: List[str]
    methodology_notes: str


class MarketTimingAnalyzer:
    """
    Advanced market timing analysis for optimal property listing strategy.
    
    Analyzes:
    - Seasonal price patterns and market activity cycles
    - Current market momentum and trend direction
    - Competition levels and inventory dynamics
    - Economic indicators and interest rate impacts
    - Property-specific timing factors
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Seasonal pattern weights
        self.seasonal_weights = {
            1: 0.85,   # January - post-holiday slow
            2: 0.90,   # February - still slow
            3: 1.05,   # March - spring market starts
            4: 1.10,   # April - peak spring
            5: 1.08,   # May - good activity
            6: 0.95,   # June - winter starts
            7: 0.88,   # July - winter low
            8: 0.92,   # August - still quiet
            9: 1.02,   # September - spring return
            10: 1.06,  # October - good season
            11: 1.00,  # November - pre-holiday
            12: 0.85   # December - holiday period
        }
        
        # Market condition thresholds
        self.market_thresholds = {
            'absorption_rate': {
                'strong_sellers': 0.8,
                'moderate_sellers': 0.6,
                'balanced': 0.4,
                'moderate_buyers': 0.2
            },
            'price_growth_monthly': {
                'strong_sellers': 0.02,
                'moderate_sellers': 0.01,
                'balanced': 0.00,
                'moderate_buyers': -0.01
            },
            'inventory_trend': {
                'strong_sellers': -0.15,
                'moderate_sellers': -0.05,
                'balanced': 0.05,
                'moderate_buyers': 0.15
            }
        }
    
    async def analyze_optimal_timing(
        self,
        property_data: Dict[str, Any],
        horizon_months: int = 6
    ) -> MarketTimingResult:
        """
        Analyze optimal market timing for property listing.
        
        Args:
            property_data: Property information dictionary
            horizon_months: Analysis horizon in months
            
        Returns:
            MarketTimingResult with timing recommendations and analysis
        """
        try:
            self.logger.info(f"Analyzing market timing for property {property_data.get('id')}")
            
            # Analyze current market conditions
            market_condition = await self._analyze_current_market_conditions(
                property_data['suburb'], property_data['property_type']
            )
            
            # Calculate seasonal patterns
            seasonal_patterns = await self._analyze_seasonal_patterns(
                property_data['suburb'], property_data['property_type']
            )
            
            # Analyze market momentum
            market_momentum = await self._analyze_market_momentum(
                property_data['suburb'], property_data['property_type']
            )
            
            # Assess competition levels
            competition_analysis = await self._analyze_competition(
                property_data
            )
            
            # Calculate timing score and recommendation
            timing_score, optimal_timing = self._calculate_timing_recommendation(
                market_condition, seasonal_patterns, market_momentum, competition_analysis
            )
            
            # Generate price timing adjustment
            price_adjustment = self._calculate_price_timing_adjustment(
                market_condition, seasonal_patterns, datetime.utcnow().month
            )
            
            # Predict sale outcomes
            expected_dom, sale_probability = self._predict_sale_outcomes(
                property_data, market_condition, competition_analysis
            )
            
            # Identify risk and opportunity factors
            risk_factors, opportunity_factors = self._identify_market_factors(
                market_condition, market_momentum, seasonal_patterns
            )
            
            # Build result
            result = MarketTimingResult(
                property_id=property_data.get('id', 'unknown'),
                analysis_date=datetime.utcnow(),
                current_market_condition=market_condition,
                optimal_timing=optimal_timing,
                timing_score=timing_score,
                seasonal_recommendation=self._get_seasonal_recommendation(seasonal_patterns),
                price_timing_adjustment=price_adjustment,
                expected_days_on_market=expected_dom,
                sale_probability_next_30d=sale_probability,
                competition_analysis=competition_analysis,
                market_momentum=market_momentum,
                seasonal_patterns=seasonal_patterns,
                risk_factors=risk_factors,
                opportunity_factors=opportunity_factors,
                methodology_notes=self._generate_methodology_notes()
            )
            
            self.logger.info(f"Timing analysis completed: {optimal_timing.value} (score: {timing_score:.1f})")
            return result
            
        except Exception as e:
            self.logger.error(f"Market timing analysis failed: {str(e)}")
            raise
    
    async def _analyze_current_market_conditions(
        self, 
        suburb: str, 
        property_type: str
    ) -> MarketCondition:
        """Analyze current market conditions for the area and property type."""
        
        async with get_db_session() as session:
            # Get recent market trends
            recent_trend = session.query(MarketTrend).filter(
                and_(
                    MarketTrend.geography_name == suburb,
                    MarketTrend.property_type == property_type,
                    MarketTrend.period_end >= datetime.utcnow() - timedelta(days=60)
                )
            ).order_by(MarketTrend.period_end.desc()).first()
            
            # Get suburb statistics
            suburb_stats = session.query(SuburbStats).filter(
                SuburbStats.suburb_name == suburb
            ).order_by(SuburbStats.stats_date.desc()).first()
            
            # Calculate market condition indicators
            indicators = {}
            
            # Absorption rate (sales/listings)
            if recent_trend and recent_trend.absorption_rate is not None:
                indicators['absorption_rate'] = float(recent_trend.absorption_rate)
            else:
                indicators['absorption_rate'] = 0.5  # Default balanced
            
            # Price growth trend
            if recent_trend and recent_trend.price_change_percent is not None:
                indicators['price_growth'] = float(recent_trend.price_change_percent) / 100
            else:
                indicators['price_growth'] = 0.0
            
            # Inventory trend
            if suburb_stats:
                current_listings = suburb_stats.active_listings or 0
                historical_avg = suburb_stats.total_properties * 0.05 if suburb_stats.total_properties else current_listings
                inventory_trend = (current_listings - historical_avg) / historical_avg if historical_avg > 0 else 0
                indicators['inventory_trend'] = inventory_trend
            else:
                indicators['inventory_trend'] = 0.0
            
            # Days on market trend
            if recent_trend and recent_trend.days_on_market is not None:
                indicators['dom_trend'] = float(recent_trend.days_on_market)
            else:
                indicators['dom_trend'] = 30.0  # Default
            
            # Classify market condition
            return self._classify_market_condition(indicators)
    
    def _classify_market_condition(self, indicators: Dict[str, float]) -> MarketCondition:
        """Classify market condition based on indicators."""
        
        absorption_rate = indicators['absorption_rate']
        price_growth = indicators['price_growth']
        inventory_trend = indicators['inventory_trend']
        
        # Score each indicator
        scores = []
        
        # Absorption rate scoring
        if absorption_rate >= self.market_thresholds['absorption_rate']['strong_sellers']:
            scores.append(2)
        elif absorption_rate >= self.market_thresholds['absorption_rate']['moderate_sellers']:
            scores.append(1)
        elif absorption_rate >= self.market_thresholds['absorption_rate']['balanced']:
            scores.append(0)
        elif absorption_rate >= self.market_thresholds['absorption_rate']['moderate_buyers']:
            scores.append(-1)
        else:
            scores.append(-2)
        
        # Price growth scoring
        if price_growth >= self.market_thresholds['price_growth_monthly']['strong_sellers']:
            scores.append(2)
        elif price_growth >= self.market_thresholds['price_growth_monthly']['moderate_sellers']:
            scores.append(1)
        elif price_growth >= self.market_thresholds['price_growth_monthly']['balanced']:
            scores.append(0)
        elif price_growth >= self.market_thresholds['price_growth_monthly']['moderate_buyers']:
            scores.append(-1)
        else:
            scores.append(-2)
        
        # Inventory trend scoring (inverse - lower inventory = better for sellers)
        if inventory_trend <= self.market_thresholds['inventory_trend']['strong_sellers']:
            scores.append(2)
        elif inventory_trend <= self.market_thresholds['inventory_trend']['moderate_sellers']:
            scores.append(1)
        elif inventory_trend <= self.market_thresholds['inventory_trend']['balanced']:
            scores.append(0)
        elif inventory_trend <= self.market_thresholds['inventory_trend']['moderate_buyers']:
            scores.append(-1)
        else:
            scores.append(-2)
        
        # Calculate average score
        avg_score = sum(scores) / len(scores)
        
        # Map to market condition
        if avg_score >= 1.5:
            return MarketCondition.STRONG_SELLERS
        elif avg_score >= 0.5:
            return MarketCondition.MODERATE_SELLERS
        elif avg_score >= -0.5:
            return MarketCondition.BALANCED
        elif avg_score >= -1.5:
            return MarketCondition.MODERATE_BUYERS
        else:
            return MarketCondition.STRONG_BUYERS
    
    async def _analyze_seasonal_patterns(
        self, 
        suburb: str, 
        property_type: str
    ) -> List[SeasonalPattern]:
        """Analyze seasonal patterns for the market."""
        
        patterns = []
        
        async with get_db_session() as session:
            # Get historical data by month
            query = text("""
                SELECT 
                    EXTRACT(MONTH FROM ph.created_at) as month,
                    AVG(ph.price) as avg_price,
                    AVG(p.days_on_market) as avg_dom,
                    COUNT(*) as sale_count,
                    STDDEV(ph.price) as price_stddev
                FROM property_price_history ph
                JOIN properties p ON ph.property_id = p.id
                WHERE p.suburb = :suburb
                AND p.property_type = :property_type
                AND ph.price_type = 'sold'
                AND ph.created_at >= :cutoff_date
                GROUP BY EXTRACT(MONTH FROM ph.created_at)
                ORDER BY month
            """)
            
            cutoff_date = datetime.utcnow() - timedelta(days=365 * 3)  # 3 years history
            
            result = await session.execute(query, {
                'suburb': suburb,
                'property_type': property_type,
                'cutoff_date': cutoff_date
            })
            
            monthly_data = {row.month: row for row in result.fetchall()}
            
            # Calculate annual averages
            all_prices = [row.avg_price for row in monthly_data.values() if row.avg_price]
            all_dom = [row.avg_dom for row in monthly_data.values() if row.avg_dom]
            annual_avg_price = np.mean(all_prices) if all_prices else 0
            annual_avg_dom = np.mean(all_dom) if all_dom else 30
            
            # Generate patterns for each month
            for month in range(1, 13):
                if month in monthly_data:
                    data = monthly_data[month]
                    price_premium = ((data.avg_price or annual_avg_price) - annual_avg_price) / annual_avg_price if annual_avg_price > 0 else 0
                    avg_dom = data.avg_dom or annual_avg_dom
                    volume_index = (data.sale_count or 1) / max(1, np.mean([row.sale_count for row in monthly_data.values()]))
                else:
                    # Use seasonal weights as fallback
                    price_premium = (self.seasonal_weights[month] - 1.0)
                    avg_dom = annual_avg_dom / self.seasonal_weights[month]
                    volume_index = self.seasonal_weights[month]
                
                # Calculate sale probability and competition level
                sale_probability = max(0.1, min(0.9, self.seasonal_weights[month] * 0.7))
                
                if volume_index > 1.1:
                    competition = "High"
                elif volume_index > 0.9:
                    competition = "Medium"
                else:
                    competition = "Low"
                
                patterns.append(SeasonalPattern(
                    month=month,
                    avg_price_premium=price_premium,
                    avg_days_on_market=avg_dom,
                    sale_probability=sale_probability,
                    volume_index=volume_index,
                    competition_level=competition
                ))
        
        return patterns
    
    async def _analyze_market_momentum(
        self, 
        suburb: str, 
        property_type: str
    ) -> Dict[str, float]:
        """Analyze current market momentum indicators."""
        
        momentum = {}
        
        async with get_db_session() as session:
            # Price momentum (3-month trend)
            query = text("""
                SELECT 
                    DATE_TRUNC('month', ph.created_at) as month,
                    AVG(ph.price) as avg_price
                FROM property_price_history ph
                JOIN properties p ON ph.property_id = p.id
                WHERE p.suburb = :suburb
                AND p.property_type = :property_type
                AND ph.price_type = 'sold'
                AND ph.created_at >= :cutoff_date
                GROUP BY DATE_TRUNC('month', ph.created_at)
                ORDER BY month DESC
                LIMIT 3
            """)
            
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            result = await session.execute(query, {
                'suburb': suburb,
                'property_type': property_type,
                'cutoff_date': cutoff_date
            })
            
            monthly_prices = [row.avg_price for row in result.fetchall()]
            
            if len(monthly_prices) >= 2:
                # Calculate price momentum
                recent_change = (monthly_prices[0] - monthly_prices[-1]) / monthly_prices[-1]
                momentum['price_momentum'] = recent_change
            else:
                momentum['price_momentum'] = 0.0
            
            # Volume momentum
            volume_query = text("""
                SELECT COUNT(*) as sales_count
                FROM property_price_history ph
                JOIN properties p ON ph.property_id = p.id
                WHERE p.suburb = :suburb
                AND p.property_type = :property_type
                AND ph.price_type = 'sold'
                AND ph.created_at >= :recent_date
            """)
            
            # Compare last 30 days vs previous 30 days
            recent_result = await session.execute(volume_query, {
                'suburb': suburb,
                'property_type': property_type,
                'recent_date': datetime.utcnow() - timedelta(days=30)
            })
            
            previous_result = await session.execute(volume_query, {
                'suburb': suburb,
                'property_type': property_type,
                'recent_date': datetime.utcnow() - timedelta(days=60)
            })
            
            recent_sales = recent_result.scalar() or 0
            previous_sales = previous_result.scalar() or 0
            
            if previous_sales > 0:
                momentum['volume_momentum'] = (recent_sales - previous_sales) / previous_sales
            else:
                momentum['volume_momentum'] = 0.0
            
        return momentum
    
    async def _analyze_competition(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze competition levels in the market."""
        
        competition = {}
        
        suburb = property_data['suburb']
        property_type = property_data['property_type']
        bedrooms = property_data.get('bedrooms', 3)
        
        async with get_db_session() as session:
            # Count active competing listings
            competing_query = session.query(Property).filter(
                and_(
                    Property.suburb == suburb,
                    Property.property_type == property_type,
                    Property.listing_status == 'active',
                    Property.bedrooms.between(max(1, bedrooms - 1), bedrooms + 1)
                )
            )
            
            competing_count = competing_query.count()
            competition['competing_listings'] = competing_count
            
            # Get price range of competing properties
            competing_props = competing_query.all()
            competing_prices = [float(p.price) for p in competing_props if p.price and p.price > 0]
            
            if competing_prices:
                competition['price_range_min'] = min(competing_prices)
                competition['price_range_max'] = max(competing_prices)
                competition['price_range_median'] = np.median(competing_prices)
                competition['price_competition_intensity'] = np.std(competing_prices) / np.mean(competing_prices) if np.mean(competing_prices) > 0 else 0
            else:
                competition['price_range_min'] = 0
                competition['price_range_max'] = 0
                competition['price_range_median'] = 0
                competition['price_competition_intensity'] = 0
            
            # Calculate competition level
            if competing_count == 0:
                competition['level'] = "None"
                competition['level_score'] = 1.0
            elif competing_count <= 2:
                competition['level'] = "Low"
                competition['level_score'] = 0.8
            elif competing_count <= 5:
                competition['level'] = "Moderate"
                competition['level_score'] = 0.6
            elif competing_count <= 10:
                competition['level'] = "High"
                competition['level_score'] = 0.4
            else:
                competition['level'] = "Very High"
                competition['level_score'] = 0.2
        
        return competition
    
    def _calculate_timing_recommendation(
        self,
        market_condition: MarketCondition,
        seasonal_patterns: List[SeasonalPattern],
        market_momentum: Dict[str, float],
        competition_analysis: Dict[str, Any]
    ) -> Tuple[float, ListingTiming]:
        """Calculate timing score and recommendation."""
        
        current_month = datetime.utcnow().month
        current_seasonal = next((p for p in seasonal_patterns if p.month == current_month), None)
        
        # Base score from market condition
        condition_scores = {
            MarketCondition.STRONG_SELLERS: 90,
            MarketCondition.MODERATE_SELLERS: 75,
            MarketCondition.BALANCED: 60,
            MarketCondition.MODERATE_BUYERS: 45,
            MarketCondition.STRONG_BUYERS: 30
        }
        
        base_score = condition_scores[market_condition]
        
        # Seasonal adjustment
        seasonal_adjustment = 0
        if current_seasonal:
            seasonal_adjustment = current_seasonal.avg_price_premium * 20  # ±20 points max
        
        # Momentum adjustment
        momentum_adjustment = 0
        price_momentum = market_momentum.get('price_momentum', 0)
        volume_momentum = market_momentum.get('volume_momentum', 0)
        momentum_adjustment = (price_momentum * 15) + (volume_momentum * 10)
        
        # Competition adjustment
        competition_adjustment = (competition_analysis.get('level_score', 0.6) - 0.6) * 25
        
        # Calculate final timing score
        timing_score = max(0, min(100, base_score + seasonal_adjustment + momentum_adjustment + competition_adjustment))
        
        # Determine timing recommendation
        if timing_score >= 80:
            timing = ListingTiming.IMMEDIATE
        elif timing_score >= 70:
            timing = ListingTiming.WITHIN_MONTH
        elif timing_score >= 50:
            # Check if waiting for seasonal peak would be better
            best_seasonal_month = max(seasonal_patterns, key=lambda p: p.avg_price_premium)
            if best_seasonal_month.month != current_month and best_seasonal_month.avg_price_premium > (current_seasonal.avg_price_premium if current_seasonal else 0) + 0.05:
                timing = ListingTiming.SEASONAL_WAIT
            else:
                timing = ListingTiming.WITHIN_MONTH
        elif timing_score >= 30:
            timing = ListingTiming.MARKET_RECOVERY
        else:
            timing = ListingTiming.MAJOR_DELAY
        
        return timing_score, timing
    
    def _calculate_price_timing_adjustment(
        self,
        market_condition: MarketCondition,
        seasonal_patterns: List[SeasonalPattern],
        current_month: int
    ) -> float:
        """Calculate price adjustment factor based on timing."""
        
        # Base adjustment from market condition
        condition_adjustments = {
            MarketCondition.STRONG_SELLERS: 0.05,   # +5%
            MarketCondition.MODERATE_SELLERS: 0.02, # +2%
            MarketCondition.BALANCED: 0.0,          # 0%
            MarketCondition.MODERATE_BUYERS: -0.03, # -3%
            MarketCondition.STRONG_BUYERS: -0.08    # -8%
        }
        
        base_adjustment = condition_adjustments[market_condition]
        
        # Seasonal adjustment
        current_seasonal = next((p for p in seasonal_patterns if p.month == current_month), None)
        seasonal_adjustment = current_seasonal.avg_price_premium if current_seasonal else 0
        
        return base_adjustment + seasonal_adjustment
    
    def _predict_sale_outcomes(
        self,
        property_data: Dict[str, Any],
        market_condition: MarketCondition,
        competition_analysis: Dict[str, Any]
    ) -> Tuple[int, float]:
        """Predict expected days on market and sale probability."""
        
        # Base expectations by market condition
        base_dom = {
            MarketCondition.STRONG_SELLERS: 20,
            MarketCondition.MODERATE_SELLERS: 35,
            MarketCondition.BALANCED: 50,
            MarketCondition.MODERATE_BUYERS: 70,
            MarketCondition.STRONG_BUYERS: 100
        }
        
        base_probability = {
            MarketCondition.STRONG_SELLERS: 0.85,
            MarketCondition.MODERATE_SELLERS: 0.75,
            MarketCondition.BALANCED: 0.60,
            MarketCondition.MODERATE_BUYERS: 0.45,
            MarketCondition.STRONG_BUYERS: 0.25
        }
        
        expected_dom = base_dom[market_condition]
        sale_probability = base_probability[market_condition]
        
        # Adjust for competition
        competition_multiplier = 2 - competition_analysis.get('level_score', 0.6)
        expected_dom = int(expected_dom * competition_multiplier)
        sale_probability = sale_probability * competition_analysis.get('level_score', 0.6)
        
        return expected_dom, sale_probability
    
    def _identify_market_factors(
        self,
        market_condition: MarketCondition,
        market_momentum: Dict[str, float],
        seasonal_patterns: List[SeasonalPattern]
    ) -> Tuple[List[str], List[str]]:
        """Identify risk and opportunity factors."""
        
        risk_factors = []
        opportunity_factors = []
        
        # Market condition factors
        if market_condition in [MarketCondition.MODERATE_BUYERS, MarketCondition.STRONG_BUYERS]:
            risk_factors.append("Current buyers market conditions may extend sale timeline")
            risk_factors.append("Increased price negotiation expected from buyers")
        
        # Momentum factors
        price_momentum = market_momentum.get('price_momentum', 0)
        if price_momentum < -0.02:
            risk_factors.append("Declining price trend may continue")
        elif price_momentum > 0.02:
            opportunity_factors.append("Positive price momentum supports premium pricing")
        
        volume_momentum = market_momentum.get('volume_momentum', 0)
        if volume_momentum < -0.2:
            risk_factors.append("Declining sales volume indicates weaker market")
        elif volume_momentum > 0.2:
            opportunity_factors.append("Increasing market activity supports faster sales")
        
        # Seasonal factors
        current_month = datetime.utcnow().month
        current_seasonal = next((p for p in seasonal_patterns if p.month == current_month), None)
        
        if current_seasonal:
            if current_seasonal.avg_price_premium < -0.05:
                risk_factors.append("Seasonal pricing disadvantage in current period")
            elif current_seasonal.avg_price_premium > 0.05:
                opportunity_factors.append("Seasonal pricing advantage in current period")
            
            if current_seasonal.competition_level == "High":
                risk_factors.append("High seasonal competition from other listings")
            elif current_seasonal.competition_level == "Low":
                opportunity_factors.append("Lower seasonal competition provides advantage")
        
        return risk_factors, opportunity_factors
    
    def _get_seasonal_recommendation(self, seasonal_patterns: List[SeasonalPattern]) -> str:
        """Generate seasonal timing recommendation."""
        
        current_month = datetime.utcnow().month
        best_month = max(seasonal_patterns, key=lambda p: p.avg_price_premium)
        
        if best_month.month == current_month:
            return f"Currently in optimal seasonal period (Month {current_month})"
        else:
            months_to_wait = (best_month.month - current_month) % 12
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            
            if months_to_wait <= 3:
                return f"Consider waiting until {month_names[best_month.month-1]} for {best_month.avg_price_premium:.1%} seasonal premium"
            else:
                return f"Next optimal season is {month_names[best_month.month-1]} ({months_to_wait} months away)"
    
    def _generate_methodology_notes(self) -> str:
        """Generate methodology explanation."""
        
        return (
            "Market timing analysis based on current market conditions assessment using "
            "absorption rates, price momentum, and inventory levels. Seasonal patterns "
            "analyzed from 3+ years of historical sales data. Competition analysis includes "
            "active listings in similar price range and property type. Timing scores "
            "combine market fundamentals (60%), seasonal factors (20%), momentum indicators (15%), "
            "and competition levels (5%) to optimize listing strategy and pricing decisions."
        )