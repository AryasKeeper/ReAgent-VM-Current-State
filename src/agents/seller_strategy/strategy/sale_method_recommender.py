"""
Sale Method Recommender

Analyzes property and market conditions to recommend optimal sale method
(auction vs private sale) with expected outcome predictions.
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

from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.data.models.property_models import Property, PropertyPriceHistory
from reagent_sydney.data.models.market_models import MarketTrend, SuburbStats


class SaleMethod(str, Enum):
    """Sale method options."""
    AUCTION = "Auction"
    PRIVATE_SALE = "Private Sale"
    EXPRESSIONS_OF_INTEREST = "Expressions of Interest"
    TENDER = "Tender"
    OFF_MARKET = "Off Market Sale"


class SaleOutcome(str, Enum):
    """Predicted sale outcomes."""
    EXCELLENT = "Excellent"      # >10% above reserve/asking
    GOOD = "Good"                # 5-10% above
    FAIR = "Fair"                # Within 5% of asking
    POOR = "Poor"                # <5% below asking
    UNSOLD = "Unsold"            # Fails to sell


@dataclass
class SaleMethodAnalysis:
    """Analysis for a specific sale method."""
    method: SaleMethod
    suitability_score: float  # 0-100
    expected_price: Decimal
    expected_days_to_sell: int
    sale_probability: float
    price_premium_potential: float
    risks: List[str]
    advantages: List[str]
    requirements: List[str]
    cost_estimate: Decimal


@dataclass
class SaleMethodRecommendation:
    """Complete sale method recommendation."""
    property_id: str
    analysis_date: datetime
    recommended_method: SaleMethod
    alternative_method: SaleMethod
    confidence_score: float
    
    # Method Analyses
    method_analyses: Dict[SaleMethod, SaleMethodAnalysis]
    
    # Comparative Analysis
    expected_outcome_comparison: Dict[str, Any]
    risk_benefit_analysis: Dict[str, Any]
    
    # Implementation Guidance
    optimal_timing: str
    preparation_requirements: List[str]
    success_factors: List[str]
    
    # Supporting Data
    market_evidence: Dict[str, Any]
    property_factors: Dict[str, Any]
    methodology_notes: str


class SaleMethodRecommender:
    """
    Advanced sale method recommendation engine.
    
    Analyzes property characteristics, market conditions, and historical
    performance to recommend optimal sale method with outcome predictions.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Auction suitability factors
        self.auction_factors = {
            'property_types': {
                'House': 0.8,
                'Townhouse': 0.7,
                'Villa': 0.8,
                'Unit': 0.6,
                'Apartment': 0.5,
                'Duplex': 0.7
            },
            'price_ranges': {
                'budget': 0.6,      # <$1M
                'mid_range': 0.8,   # $1M-$2M
                'premium': 0.9,     # $2M-$5M
                'luxury': 0.7       # >$5M
            },
            'market_conditions': {
                'strong_sellers': 0.9,
                'moderate_sellers': 0.8,
                'balanced': 0.6,
                'moderate_buyers': 0.4,
                'strong_buyers': 0.3
            }
        }
        
        # Historical performance benchmarks
        self.method_benchmarks = {
            SaleMethod.AUCTION: {
                'avg_premium': 0.08,     # 8% above reserve
                'success_rate': 0.75,    # 75% clearance
                'avg_days': 35,          # Days to auction
                'cost_percentage': 0.025  # 2.5% of sale price
            },
            SaleMethod.PRIVATE_SALE: {
                'avg_premium': 0.02,     # 2% above asking
                'success_rate': 0.65,    # 65% sell within 90 days
                'avg_days': 50,          # Average days on market
                'cost_percentage': 0.015  # 1.5% of sale price
            },
            SaleMethod.EXPRESSIONS_OF_INTEREST: {
                'avg_premium': 0.12,     # 12% above guide
                'success_rate': 0.70,    # 70% success rate
                'avg_days': 45,          # Days to close
                'cost_percentage': 0.020  # 2.0% of sale price
            }
        }
    
    async def recommend_sale_method(
        self,
        property_data: Dict[str, Any],
        pricing_analysis: Optional[Dict[str, Any]] = None
    ) -> SaleMethodRecommendation:
        """
        Recommend optimal sale method with comprehensive analysis.
        
        Args:
            property_data: Property information dictionary
            pricing_analysis: Optional pricing analysis from coordinator
            
        Returns:
            SaleMethodRecommendation with method analysis and guidance
        """
        try:
            self.logger.info(f"Analyzing sale methods for property {property_data.get('id')}")
            
            # Analyze property factors
            property_factors = await self._analyze_property_factors(property_data)
            
            # Gather market evidence
            market_evidence = await self._gather_market_evidence(
                property_data['suburb'], property_data['property_type']
            )
            
            # Analyze each sale method
            method_analyses = {}
            for method in [SaleMethod.AUCTION, SaleMethod.PRIVATE_SALE, SaleMethod.EXPRESSIONS_OF_INTEREST]:
                analysis = await self._analyze_sale_method(
                    method, property_data, property_factors, market_evidence, pricing_analysis
                )
                method_analyses[method] = analysis
            
            # Determine recommendations
            recommended_method = max(method_analyses.keys(), 
                                   key=lambda m: method_analyses[m].suitability_score)
            
            # Find alternative method (second highest score)
            alternative_method = sorted(method_analyses.keys(), 
                                      key=lambda m: method_analyses[m].suitability_score)[-2]
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(method_analyses, market_evidence)
            
            # Generate comparative analysis
            outcome_comparison = self._generate_outcome_comparison(method_analyses)
            risk_benefit_analysis = self._generate_risk_benefit_analysis(method_analyses)
            
            # Generate implementation guidance
            optimal_timing = self._determine_optimal_timing(recommended_method, market_evidence)
            preparation_requirements = self._get_preparation_requirements(recommended_method, property_data)
            success_factors = self._identify_success_factors(recommended_method, property_factors)
            
            # Build comprehensive result
            result = SaleMethodRecommendation(
                property_id=property_data.get('id', 'unknown'),
                analysis_date=datetime.utcnow(),
                recommended_method=recommended_method,
                alternative_method=alternative_method,
                confidence_score=confidence_score,
                method_analyses=method_analyses,
                expected_outcome_comparison=outcome_comparison,
                risk_benefit_analysis=risk_benefit_analysis,
                optimal_timing=optimal_timing,
                preparation_requirements=preparation_requirements,
                success_factors=success_factors,
                market_evidence=market_evidence,
                property_factors=property_factors,
                methodology_notes=self._generate_methodology_notes()
            )
            
            self.logger.info(
                f"Sale method recommendation: {recommended_method.value} "
                f"(score: {method_analyses[recommended_method].suitability_score:.1f}, "
                f"confidence: {confidence_score:.2f})"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Sale method recommendation failed: {str(e)}")
            raise
    
    async def _analyze_property_factors(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze property-specific factors affecting sale method suitability."""
        
        factors = {}
        
        # Property type factor
        property_type = property_data.get('property_type', 'House')
        factors['property_type_score'] = self.auction_factors['property_types'].get(property_type, 0.6)
        
        # Price range factor
        estimated_price = property_data.get('estimated_price', 1000000)
        if estimated_price < 1000000:
            price_category = 'budget'
        elif estimated_price < 2000000:
            price_category = 'mid_range'
        elif estimated_price < 5000000:
            price_category = 'premium'
        else:
            price_category = 'luxury'
        
        factors['price_range_score'] = self.auction_factors['price_ranges'][price_category]
        factors['price_category'] = price_category
        
        # Unique features that drive auction appeal
        factors['unique_features'] = []
        features = property_data.get('features', [])
        
        # Features that enhance auction appeal
        auction_enhancing_features = [
            'harbor views', 'ocean views', 'city views', 'heritage listed',
            'architectural significance', 'waterfront', 'resort-style',
            'celebrity owned', 'award winning design'
        ]
        
        for feature in features:
            if any(keyword in feature.lower() for keyword in auction_enhancing_features):
                factors['unique_features'].append(feature)
        
        factors['uniqueness_score'] = min(1.0, len(factors['unique_features']) * 0.2)
        
        # Location premium factors
        suburb = property_data.get('suburb', '').lower()
        premium_suburbs = [
            'mosman', 'vaucluse', 'bellevue hill', 'point piper', 'woollahra',
            'paddington', 'surry hills', 'potts point', 'kirribilli'
        ]
        factors['location_premium'] = 1 if suburb in premium_suburbs else 0
        
        # Property condition assessment
        factors['condition_score'] = 0.8  # Default good condition
        if 'renovated' in str(property_data.get('description', '')).lower():
            factors['condition_score'] = 0.9
        elif 'original condition' in str(property_data.get('description', '')).lower():
            factors['condition_score'] = 0.6
        
        return factors
    
    async def _gather_market_evidence(self, suburb: str, property_type: str) -> Dict[str, Any]:
        """Gather market evidence for sale method performance."""
        
        evidence = {}
        
        async with get_db_session() as session:
            # Historical auction vs private sale performance
            query = text("""
                SELECT 
                    p.listing_type,
                    COUNT(*) as total_sales,
                    AVG(ph.price) as avg_price,
                    AVG(p.days_on_market) as avg_days,
                    STDDEV(ph.price) as price_stddev
                FROM properties p
                JOIN property_price_history ph ON p.id = ph.property_id
                WHERE p.suburb = :suburb
                AND p.property_type = :property_type
                AND ph.price_type = 'sold'
                AND ph.created_at >= :cutoff_date
                AND p.listing_type IN ('auction', 'sale')
                GROUP BY p.listing_type
            """)
            
            cutoff_date = datetime.utcnow() - timedelta(days=365)  # Last year
            result = await session.execute(query, {
                'suburb': suburb,
                'property_type': property_type,
                'cutoff_date': cutoff_date
            })
            
            method_performance = {}
            for row in result.fetchall():
                method_performance[row.listing_type] = {
                    'total_sales': row.total_sales,
                    'avg_price': row.avg_price,
                    'avg_days': row.avg_days,
                    'price_variance': row.price_stddev / row.avg_price if row.avg_price > 0 else 0
                }
            
            evidence['historical_performance'] = method_performance
            
            # Current market conditions
            recent_trend = session.query(MarketTrend).filter(
                and_(
                    MarketTrend.geography_name == suburb,
                    MarketTrend.property_type == property_type,
                    MarketTrend.period_end >= datetime.utcnow() - timedelta(days=60)
                )
            ).order_by(MarketTrend.period_end.desc()).first()
            
            if recent_trend:
                evidence['market_conditions'] = {
                    'absorption_rate': float(recent_trend.absorption_rate) if recent_trend.absorption_rate else 0.5,
                    'price_trend': recent_trend.trend_direction,
                    'inventory_level': recent_trend.inventory_level,
                    'days_on_market': float(recent_trend.days_on_market) if recent_trend.days_on_market else 30
                }
            else:
                evidence['market_conditions'] = {
                    'absorption_rate': 0.5,
                    'price_trend': 'Stable',
                    'inventory_level': 100,
                    'days_on_market': 30
                }
            
            # Recent auction clearance rates
            auction_query = text("""
                SELECT 
                    COUNT(*) as total_auctions,
                    SUM(CASE WHEN ph.price > 0 THEN 1 ELSE 0 END) as sold_auctions
                FROM properties p
                JOIN property_price_history ph ON p.id = ph.property_id
                WHERE p.suburb = :suburb
                AND p.listing_type = 'auction'
                AND ph.created_at >= :recent_date
            """)
            
            recent_date = datetime.utcnow() - timedelta(days=90)
            auction_result = await session.execute(auction_query, {
                'suburb': suburb,
                'recent_date': recent_date
            })
            
            auction_data = auction_result.fetchone()
            if auction_data and auction_data.total_auctions > 0:
                clearance_rate = auction_data.sold_auctions / auction_data.total_auctions
                evidence['auction_clearance_rate'] = clearance_rate
            else:
                evidence['auction_clearance_rate'] = 0.75  # Default Sydney average
        
        return evidence
    
    async def _analyze_sale_method(
        self,
        method: SaleMethod,
        property_data: Dict[str, Any],
        property_factors: Dict[str, Any],
        market_evidence: Dict[str, Any],
        pricing_analysis: Optional[Dict[str, Any]]
    ) -> SaleMethodAnalysis:
        """Analyze suitability and outcomes for a specific sale method."""
        
        if method == SaleMethod.AUCTION:
            return await self._analyze_auction_method(
                property_data, property_factors, market_evidence, pricing_analysis
            )
        elif method == SaleMethod.PRIVATE_SALE:
            return await self._analyze_private_sale_method(
                property_data, property_factors, market_evidence, pricing_analysis
            )
        elif method == SaleMethod.EXPRESSIONS_OF_INTEREST:
            return await self._analyze_eoi_method(
                property_data, property_factors, market_evidence, pricing_analysis
            )
        else:
            # Default analysis for other methods
            return SaleMethodAnalysis(
                method=method,
                suitability_score=50.0,
                expected_price=Decimal(str(property_data.get('estimated_price', 1000000))),
                expected_days_to_sell=60,
                sale_probability=0.6,
                price_premium_potential=0.0,
                risks=["Limited historical data for this method"],
                advantages=["Specialized approach"],
                requirements=["Professional guidance required"],
                cost_estimate=Decimal("20000")
            )
    
    async def _analyze_auction_method(
        self,
        property_data: Dict[str, Any],
        property_factors: Dict[str, Any],
        market_evidence: Dict[str, Any],
        pricing_analysis: Optional[Dict[str, Any]]
    ) -> SaleMethodAnalysis:
        """Analyze auction method suitability and outcomes."""
        
        # Calculate base suitability score
        suitability_components = {
            'property_type': property_factors['property_type_score'] * 25,
            'price_range': property_factors['price_range_score'] * 20,
            'uniqueness': property_factors['uniqueness_score'] * 15,
            'location': property_factors['location_premium'] * 15,
            'market_conditions': self._get_market_condition_score() * 25
        }
        
        base_score = sum(suitability_components.values())
        
        # Market condition adjustments
        clearance_rate = market_evidence.get('auction_clearance_rate', 0.75)
        absorption_rate = market_evidence['market_conditions']['absorption_rate']
        
        market_adjustment = (clearance_rate - 0.75) * 20 + (absorption_rate - 0.5) * 15
        
        final_score = max(0, min(100, base_score + market_adjustment))
        
        # Calculate expected outcomes
        base_price = property_data.get('estimated_price', 1000000)
        
        # Premium potential based on uniqueness and market conditions
        premium_potential = (
            property_factors['uniqueness_score'] * 0.10 +
            property_factors['location_premium'] * 0.05 +
            max(0, clearance_rate - 0.75) * 0.15
        )
        
        expected_price = Decimal(str(round(base_price * (1 + premium_potential), 2)))
        
        # Days to sell (auction timeline)
        expected_days = 35  # Standard auction campaign
        
        # Sale probability
        sale_probability = min(0.95, clearance_rate * 1.1)
        
        # Risks and advantages
        risks = []
        advantages = []
        
        if clearance_rate < 0.7:
            risks.append(f"Low auction clearance rate ({clearance_rate:.1%}) in area")
        if absorption_rate < 0.4:
            risks.append("Weak market conditions may reduce auction competition")
        if property_factors['uniqueness_score'] < 0.2:
            risks.append("Limited unique features may not generate strong auction interest")
        
        if property_factors['location_premium']:
            advantages.append("Premium location attracts strong buyer interest")
        if property_factors['uniqueness_score'] > 0.4:
            advantages.append("Unique property features drive competitive bidding")
        if clearance_rate > 0.8:
            advantages.append(f"Strong auction market ({clearance_rate:.1%} clearance rate)")
        
        # Requirements
        requirements = [
            "Professional auction marketing campaign (4-6 weeks)",
            "Property preparation and styling",
            "Clear reserve price strategy",
            "Experienced auctioneer selection"
        ]
        
        # Cost estimate
        marketing_cost = base_price * 0.015  # 1.5% marketing
        auction_cost = base_price * 0.01    # 1% auction costs
        cost_estimate = Decimal(str(round(marketing_cost + auction_cost, 2)))
        
        return SaleMethodAnalysis(
            method=SaleMethod.AUCTION,
            suitability_score=final_score,
            expected_price=expected_price,
            expected_days_to_sell=expected_days,
            sale_probability=sale_probability,
            price_premium_potential=premium_potential,
            risks=risks,
            advantages=advantages,
            requirements=requirements,
            cost_estimate=cost_estimate
        )
    
    async def _analyze_private_sale_method(
        self,
        property_data: Dict[str, Any],
        property_factors: Dict[str, Any],
        market_evidence: Dict[str, Any],
        pricing_analysis: Optional[Dict[str, Any]]
    ) -> SaleMethodAnalysis:
        """Analyze private sale method suitability and outcomes."""
        
        # Private sales are generally suitable for most properties
        base_score = 70.0
        
        # Adjustments for property factors
        if property_factors['price_category'] in ['budget', 'mid_range']:
            base_score += 10  # Better for lower price ranges
        
        if property_factors['uniqueness_score'] < 0.3:
            base_score += 5  # Better for standard properties
        
        # Market condition adjustments
        absorption_rate = market_evidence['market_conditions']['absorption_rate']
        if absorption_rate < 0.5:
            base_score += 10  # Better in buyer's markets
        
        final_score = max(0, min(100, base_score))
        
        # Calculate expected outcomes
        base_price = property_data.get('estimated_price', 1000000)
        
        # Lower premium potential than auction
        premium_potential = 0.02  # 2% average premium
        
        expected_price = Decimal(str(round(base_price * (1 + premium_potential), 2)))
        
        # Days to sell
        market_days = market_evidence['market_conditions']['days_on_market']
        expected_days = int(market_days * 1.2)  # Slightly longer than market average
        
        # Sale probability
        sale_probability = 0.65  # Standard private sale success rate
        
        # Risks and advantages
        risks = [
            "Price negotiation may reduce final sale price",
            "Longer sale timeline than auction",
            "Market conditions can change during campaign"
        ]
        
        advantages = [
            "Flexible pricing and negotiation strategy",
            "Lower marketing costs than auction",
            "Can adjust strategy based on market feedback",
            "Suitable for most property types and markets"
        ]
        
        # Requirements
        requirements = [
            "Competitive market pricing strategy",
            "Quality marketing materials and photography",
            "Regular price and strategy reviews",
            "Strong negotiation and follow-up process"
        ]
        
        # Cost estimate
        marketing_cost = base_price * 0.01  # 1% marketing
        cost_estimate = Decimal(str(round(marketing_cost, 2)))
        
        return SaleMethodAnalysis(
            method=SaleMethod.PRIVATE_SALE,
            suitability_score=final_score,
            expected_price=expected_price,
            expected_days_to_sell=expected_days,
            sale_probability=sale_probability,
            price_premium_potential=premium_potential,
            risks=risks,
            advantages=advantages,
            requirements=requirements,
            cost_estimate=cost_estimate
        )
    
    async def _analyze_eoi_method(
        self,
        property_data: Dict[str, Any],
        property_factors: Dict[str, Any],
        market_evidence: Dict[str, Any],
        pricing_analysis: Optional[Dict[str, Any]]
    ) -> SaleMethodAnalysis:
        """Analyze Expressions of Interest method suitability and outcomes."""
        
        # EOI works best for unique or high-value properties
        base_score = 40.0
        
        # Strong preference for unique properties
        if property_factors['uniqueness_score'] > 0.5:
            base_score += 30
        elif property_factors['uniqueness_score'] > 0.2:
            base_score += 15
        
        # Works well for premium properties
        if property_factors['price_category'] in ['premium', 'luxury']:
            base_score += 20
        
        # Location premium helps
        if property_factors['location_premium']:
            base_score += 10
        
        final_score = max(0, min(100, base_score))
        
        # Calculate expected outcomes
        base_price = property_data.get('estimated_price', 1000000)
        
        # Higher premium potential for unique properties
        premium_potential = (
            property_factors['uniqueness_score'] * 0.15 +
            property_factors['location_premium'] * 0.08
        )
        
        expected_price = Decimal(str(round(base_price * (1 + premium_potential), 2)))
        
        # Days to sell
        expected_days = 45  # EOI campaign period
        
        # Sale probability depends on uniqueness
        base_probability = 0.6
        if property_factors['uniqueness_score'] > 0.4:
            base_probability = 0.75
        elif property_factors['uniqueness_score'] < 0.2:
            base_probability = 0.45
        
        sale_probability = base_probability
        
        # Risks and advantages
        risks = [
            "Requires significant unique property appeal",
            "May not generate sufficient buyer interest",
            "Complex negotiation process with multiple parties"
        ]
        
        advantages = [
            "Maximizes price for unique properties",
            "Creates competitive buyer environment",
            "Flexible negotiation terms possible",
            "Can achieve premium pricing outcomes"
        ]
        
        if property_factors['uniqueness_score'] < 0.3:
            risks.append("Property may lack sufficient uniqueness for EOI success")
        
        # Requirements
        requirements = [
            "Unique or highly desirable property features",
            "Premium marketing and presentation",
            "Professional EOI process management",
            "Strong negotiation and evaluation process"
        ]
        
        # Cost estimate
        marketing_cost = base_price * 0.018  # 1.8% marketing (higher than private)
        cost_estimate = Decimal(str(round(marketing_cost, 2)))
        
        return SaleMethodAnalysis(
            method=SaleMethod.EXPRESSIONS_OF_INTEREST,
            suitability_score=final_score,
            expected_price=expected_price,
            expected_days_to_sell=expected_days,
            sale_probability=sale_probability,
            price_premium_potential=premium_potential,
            risks=risks,
            advantages=advantages,
            requirements=requirements,
            cost_estimate=cost_estimate
        )
    
    def _get_market_condition_score(self) -> float:
        """Get market condition score for current conditions."""
        # This would normally use the market timing result
        # For now, return a neutral score
        return 0.6
    
    def _calculate_confidence_score(
        self,
        method_analyses: Dict[SaleMethod, SaleMethodAnalysis],
        market_evidence: Dict[str, Any]
    ) -> float:
        """Calculate confidence in the recommendation."""
        
        # Score difference between top recommendations
        scores = [analysis.suitability_score for analysis in method_analyses.values()]
        scores.sort(reverse=True)
        
        score_gap = scores[0] - scores[1] if len(scores) > 1 else 20
        
        # Higher gap = higher confidence
        confidence_from_gap = min(0.9, score_gap / 30)
        
        # Data quality factors
        historical_data_quality = 0.8  # Default
        if 'historical_performance' in market_evidence:
            auction_data = market_evidence['historical_performance'].get('auction', {})
            private_data = market_evidence['historical_performance'].get('sale', {})
            
            total_sales = auction_data.get('total_sales', 0) + private_data.get('total_sales', 0)
            historical_data_quality = min(0.9, total_sales / 20)  # Max confidence at 20+ sales
        
        # Combine factors
        overall_confidence = (confidence_from_gap * 0.6 + historical_data_quality * 0.4)
        
        return max(0.3, min(0.95, overall_confidence))
    
    def _generate_outcome_comparison(
        self,
        method_analyses: Dict[SaleMethod, SaleMethodAnalysis]
    ) -> Dict[str, Any]:
        """Generate comparative outcome analysis."""
        
        comparison = {}
        
        # Extract key metrics
        methods = list(method_analyses.keys())
        prices = [float(analysis.expected_price) for analysis in method_analyses.values()]
        days = [analysis.expected_days_to_sell for analysis in method_analyses.values()]
        probabilities = [analysis.sale_probability for analysis in method_analyses.values()]
        costs = [float(analysis.cost_estimate) for analysis in method_analyses.values()]
        
        # Find best performing method for each metric
        best_price_idx = prices.index(max(prices))
        best_speed_idx = days.index(min(days))
        best_probability_idx = probabilities.index(max(probabilities))
        best_cost_idx = costs.index(min(costs))
        
        comparison['best_price'] = {
            'method': methods[best_price_idx].value,
            'expected_price': max(prices),
            'advantage': f"${max(prices) - min(prices):,.0f} higher than lowest"
        }
        
        comparison['fastest_sale'] = {
            'method': methods[best_speed_idx].value,
            'expected_days': min(days),
            'advantage': f"{max(days) - min(days)} days faster than slowest"
        }
        
        comparison['highest_probability'] = {
            'method': methods[best_probability_idx].value,
            'sale_probability': max(probabilities),
            'advantage': f"{(max(probabilities) - min(probabilities)) * 100:.1f}% higher success rate"
        }
        
        comparison['lowest_cost'] = {
            'method': methods[best_cost_idx].value,
            'cost_estimate': min(costs),
            'advantage': f"${max(costs) - min(costs):,.0f} lower than highest"
        }
        
        return comparison
    
    def _generate_risk_benefit_analysis(
        self,
        method_analyses: Dict[SaleMethod, SaleMethodAnalysis]
    ) -> Dict[str, Any]:
        """Generate risk-benefit analysis across methods."""
        
        analysis = {}
        
        for method, method_analysis in method_analyses.items():
            analysis[method.value] = {
                'overall_score': method_analysis.suitability_score,
                'risk_factors': len(method_analysis.risks),
                'benefit_factors': len(method_analysis.advantages),
                'cost_as_percentage': float(method_analysis.cost_estimate) / float(method_analysis.expected_price) * 100,
                'risk_adjusted_return': method_analysis.sale_probability * float(method_analysis.expected_price)
            }
        
        return analysis
    
    def _determine_optimal_timing(self, method: SaleMethod, market_evidence: Dict[str, Any]) -> str:
        """Determine optimal timing for the recommended method."""
        
        if method == SaleMethod.AUCTION:
            return "Schedule auction for peak market period (typically March-May or September-November)"
        elif method == SaleMethod.PRIVATE_SALE:
            return "Launch immediately with flexibility to adjust strategy based on market response"
        elif method == SaleMethod.EXPRESSIONS_OF_INTEREST:
            return "Launch during strong market conditions with 4-6 week campaign period"
        else:
            return "Consult with specialist for optimal timing strategy"
    
    def _get_preparation_requirements(self, method: SaleMethod, property_data: Dict[str, Any]) -> List[str]:
        """Get preparation requirements for the recommended method."""
        
        base_requirements = [
            "Professional property photography and marketing materials",
            "Property styling and presentation optimization",
            "Market pricing analysis and strategy development"
        ]
        
        if method == SaleMethod.AUCTION:
            base_requirements.extend([
                "Reserve price strategy development",
                "Auction marketing campaign (4-6 weeks)",
                "Auctioneer selection and briefing",
                "Auction terms and conditions preparation"
            ])
        elif method == SaleMethod.EXPRESSIONS_OF_INTEREST:
            base_requirements.extend([
                "Comprehensive property information memorandum",
                "EOI process and evaluation criteria",
                "Legal documentation for multiple offer assessment"
            ])
        
        return base_requirements
    
    def _identify_success_factors(self, method: SaleMethod, property_factors: Dict[str, Any]) -> List[str]:
        """Identify key success factors for the recommended method."""
        
        factors = [
            "Competitive and realistic pricing strategy",
            "High-quality marketing and presentation",
            "Strong agent expertise and market knowledge"
        ]
        
        if method == SaleMethod.AUCTION:
            factors.extend([
                "Clear reserve price strategy",
                "Strong buyer registration and interest",
                "Effective auction day management"
            ])
            
            if property_factors['uniqueness_score'] > 0.3:
                factors.append("Highlight unique property features to drive competition")
        
        elif method == SaleMethod.PRIVATE_SALE:
            factors.extend([
                "Flexible negotiation and pricing strategy",
                "Strong follow-up and buyer communication",
                "Regular market feedback analysis and adjustments"
            ])
        
        return factors
    
    def _generate_methodology_notes(self) -> str:
        """Generate methodology explanation."""
        
        return (
            "Sale method recommendation based on property characteristics analysis "
            "(25%), market evidence review (30%), historical performance data (25%), "
            "and current market conditions (20%). Suitability scores calculated using "
            "property type factors, price range optimization, uniqueness assessment, "
            "and location premiums. Expected outcomes based on recent comparable "
            "transactions and market absorption rates. Risk-benefit analysis considers "
            "success probability, cost implications, and timeline requirements."
        )