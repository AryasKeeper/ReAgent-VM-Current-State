"""
Pricing Coordinator

Orchestrates all pricing models to provide comprehensive pricing strategy
with confidence-weighted recommendations and risk analysis.
"""

import asyncio
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
import logging

from .comparable_sales_analyzer import ComparableSalesAnalyzer, CMAResult
from .automated_valuation_model import AutomatedValuationModel, AVMPrediction
from .market_timing_analyzer import MarketTimingAnalyzer, MarketTimingResult


@dataclass
class PricingRecommendation:
    """Comprehensive pricing recommendation."""
    property_id: str
    analysis_date: datetime
    
    # Primary Valuation
    recommended_price: Decimal
    price_range_low: Decimal
    price_range_high: Decimal
    confidence_score: float
    
    # Supporting Analysis
    cma_result: CMAResult
    avm_result: AVMPrediction
    timing_result: MarketTimingResult
    
    # Strategy Recommendations
    pricing_strategy: str
    listing_price: Decimal
    auction_reserve: Optional[Decimal]
    private_sale_price: Optional[Decimal]
    
    # Risk Analysis
    pricing_risks: List[str]
    market_opportunities: List[str]
    sensitivity_analysis: Dict[str, Decimal]
    
    # Methodology
    model_weights: Dict[str, float]
    methodology_summary: str


class PricingCoordinator:
    """
    Central coordinator for all pricing models and strategies.
    
    Combines CMA, AVM, and market timing analysis to provide
    comprehensive pricing recommendations with confidence weighting.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize component analyzers
        self.cma_analyzer = ComparableSalesAnalyzer()
        self.avm_model = AutomatedValuationModel()
        self.timing_analyzer = MarketTimingAnalyzer()
        
        # Default model weights (can be adjusted based on confidence)
        self.default_weights = {
            'cma': 0.45,      # Comparable sales - highest weight
            'avm': 0.35,      # ML model - good for pattern recognition
            'timing': 0.20    # Market timing - adjustment factor
        }
        
        # Confidence thresholds for weight adjustment
        self.confidence_thresholds = {
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4
        }
    
    async def generate_pricing_strategy(
        self,
        property_data: Dict[str, Any],
        include_sensitivity: bool = True
    ) -> PricingRecommendation:
        """
        Generate comprehensive pricing strategy using all models.
        
        Args:
            property_data: Property information dictionary
            include_sensitivity: Whether to include sensitivity analysis
            
        Returns:
            PricingRecommendation with all analysis components
        """
        try:
            self.logger.info(f"Generating pricing strategy for property {property_data.get('id')}")
            
            # Run all analyses in parallel
            cma_task = asyncio.create_task(
                self.cma_analyzer.analyze_comparables(property_data)
            )
            avm_task = asyncio.create_task(
                self.avm_model.predict_value(property_data)
            )
            timing_task = asyncio.create_task(
                self.timing_analyzer.analyze_optimal_timing(property_data)
            )
            
            # Wait for all analyses to complete
            cma_result, avm_result, timing_result = await asyncio.gather(
                cma_task, avm_task, timing_task
            )
            
            # Calculate confidence-weighted valuation
            recommended_price, confidence_score, model_weights = self._calculate_weighted_valuation(
                cma_result, avm_result, timing_result
            )
            
            # Determine price range
            price_range_low, price_range_high = self._calculate_price_range(
                cma_result, avm_result, recommended_price, confidence_score
            )
            
            # Generate pricing strategy recommendations
            pricing_strategy, listing_price, auction_reserve, private_sale_price = self._generate_pricing_strategy(
                recommended_price, timing_result, confidence_score
            )
            
            # Analyze risks and opportunities
            pricing_risks, market_opportunities = self._analyze_pricing_risks_opportunities(
                cma_result, avm_result, timing_result, recommended_price
            )
            
            # Perform sensitivity analysis if requested
            sensitivity_analysis = {}
            if include_sensitivity:
                sensitivity_analysis = await self._perform_sensitivity_analysis(
                    property_data, recommended_price
                )
            
            # Build comprehensive result
            result = PricingRecommendation(
                property_id=property_data.get('id', 'unknown'),
                analysis_date=datetime.utcnow(),
                recommended_price=recommended_price,
                price_range_low=price_range_low,
                price_range_high=price_range_high,
                confidence_score=confidence_score,
                cma_result=cma_result,
                avm_result=avm_result,
                timing_result=timing_result,
                pricing_strategy=pricing_strategy,
                listing_price=listing_price,
                auction_reserve=auction_reserve,
                private_sale_price=private_sale_price,
                pricing_risks=pricing_risks,
                market_opportunities=market_opportunities,
                sensitivity_analysis=sensitivity_analysis,
                model_weights=model_weights,
                methodology_summary=self._generate_methodology_summary(model_weights, confidence_score)
            )
            
            self.logger.info(
                f"Pricing strategy completed: ${recommended_price:,.2f} "
                f"(${price_range_low:,.2f} - ${price_range_high:,.2f}, confidence: {confidence_score:.2f})"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Pricing strategy generation failed: {str(e)}")
            raise
    
    def _calculate_weighted_valuation(
        self,
        cma_result: CMAResult,
        avm_result: AVMPrediction,
        timing_result: MarketTimingResult
    ) -> Tuple[Decimal, float, Dict[str, float]]:
        """Calculate confidence-weighted valuation from all models."""
        
        # Extract base valuations
        cma_value = float(cma_result.estimated_value)
        avm_value = float(avm_result.predicted_value)
        timing_adjustment = timing_result.price_timing_adjustment
        
        # Calculate confidence scores
        cma_confidence = cma_result.confidence_level
        avm_confidence = avm_result.confidence_score
        timing_confidence = timing_result.timing_score / 100.0
        
        # Adjust weights based on confidence levels
        weights = self._adjust_model_weights(
            cma_confidence, avm_confidence, timing_confidence
        )
        
        # Apply timing adjustment to base valuations
        cma_adjusted = cma_value * (1 + timing_adjustment)
        avm_adjusted = avm_value * (1 + timing_adjustment)
        
        # Calculate weighted average
        weighted_value = (
            weights['cma'] * cma_adjusted +
            weights['avm'] * avm_adjusted
        )
        
        # Overall confidence score
        overall_confidence = (
            weights['cma'] * cma_confidence +
            weights['avm'] * avm_confidence +
            weights['timing'] * timing_confidence
        )
        
        return Decimal(str(round(weighted_value, 2))), overall_confidence, weights
    
    def _adjust_model_weights(
        self,
        cma_confidence: float,
        avm_confidence: float,
        timing_confidence: float
    ) -> Dict[str, float]:
        """Adjust model weights based on confidence levels."""
        
        # Start with default weights
        weights = self.default_weights.copy()
        
        # Adjust CMA weight based on confidence
        if cma_confidence >= self.confidence_thresholds['high']:
            weights['cma'] += 0.10
        elif cma_confidence <= self.confidence_thresholds['low']:
            weights['cma'] -= 0.10
        
        # Adjust AVM weight based on confidence
        if avm_confidence >= self.confidence_thresholds['high']:
            weights['avm'] += 0.05
        elif avm_confidence <= self.confidence_thresholds['low']:
            weights['avm'] -= 0.05
        
        # Adjust timing weight based on confidence
        if timing_confidence >= self.confidence_thresholds['high']:
            weights['timing'] += 0.05
        elif timing_confidence <= self.confidence_thresholds['low']:
            weights['timing'] -= 0.05
        
        # Normalize weights to sum to 1.0 (excluding timing which is multiplicative)
        total_base_weight = weights['cma'] + weights['avm']
        if total_base_weight > 0:
            weights['cma'] = weights['cma'] / total_base_weight
            weights['avm'] = weights['avm'] / total_base_weight
        
        # Ensure weights are within reasonable bounds
        weights['cma'] = max(0.3, min(0.7, weights['cma']))
        weights['avm'] = 1.0 - weights['cma']
        weights['timing'] = max(0.1, min(0.3, weights['timing']))
        
        return weights
    
    def _calculate_price_range(
        self,
        cma_result: CMAResult,
        avm_result: AVMPrediction,
        recommended_price: Decimal,
        confidence_score: float
    ) -> Tuple[Decimal, Decimal]:
        """Calculate realistic price range based on model uncertainties."""
        
        recommended_value = float(recommended_price)
        
        # Get individual model ranges
        cma_range = (
            float(cma_result.confidence_interval_low),
            float(cma_result.confidence_interval_high)
        )
        
        avm_range = (
            float(avm_result.prediction_interval_low) if avm_result.prediction_interval_low else recommended_value * 0.9,
            float(avm_result.prediction_interval_high) if avm_result.prediction_interval_high else recommended_value * 1.1
        )
        
        # Calculate combined range using confidence weighting
        combined_low = min(cma_range[0], avm_range[0])
        combined_high = max(cma_range[1], avm_range[1])
        
        # Adjust range based on overall confidence
        if confidence_score >= self.confidence_thresholds['high']:
            # High confidence - narrower range
            range_factor = 0.10  # ±10%
        elif confidence_score >= self.confidence_thresholds['medium']:
            # Medium confidence - moderate range
            range_factor = 0.15  # ±15%
        else:
            # Low confidence - wider range
            range_factor = 0.20  # ±20%
        
        # Calculate final range
        range_low = max(
            combined_low,
            recommended_value * (1 - range_factor)
        )
        range_high = min(
            combined_high,
            recommended_value * (1 + range_factor)
        )
        
        return Decimal(str(round(range_low, 2))), Decimal(str(round(range_high, 2)))
    
    def _generate_pricing_strategy(
        self,
        recommended_price: Decimal,
        timing_result: MarketTimingResult,
        confidence_score: float
    ) -> Tuple[str, Decimal, Optional[Decimal], Optional[Decimal]]:
        """Generate specific pricing strategy recommendations."""
        
        base_price = float(recommended_price)
        
        # Determine strategy based on timing and confidence
        if timing_result.timing_score >= 80 and confidence_score >= 0.8:
            strategy = "Aggressive Pricing"
            listing_multiplier = 1.05  # List 5% above recommended
            auction_multiplier = 0.95   # Reserve 5% below recommended
        elif timing_result.timing_score >= 70:
            strategy = "Market Pricing"
            listing_multiplier = 1.02  # List 2% above recommended
            auction_multiplier = 0.97   # Reserve 3% below recommended
        elif timing_result.timing_score >= 50:
            strategy = "Conservative Pricing"
            listing_multiplier = 1.00  # List at recommended
            auction_multiplier = 0.92   # Reserve 8% below recommended
        else:
            strategy = "Defensive Pricing"
            listing_multiplier = 0.98  # List 2% below recommended
            auction_multiplier = 0.90   # Reserve 10% below recommended
        
        # Calculate specific prices
        listing_price = Decimal(str(round(base_price * listing_multiplier, 2)))
        auction_reserve = Decimal(str(round(base_price * auction_multiplier, 2)))
        private_sale_price = Decimal(str(round(base_price * 0.98, 2)))  # Slightly below for negotiation
        
        return strategy, listing_price, auction_reserve, private_sale_price
    
    def _analyze_pricing_risks_opportunities(
        self,
        cma_result: CMAResult,
        avm_result: AVMPrediction,
        timing_result: MarketTimingResult,
        recommended_price: Decimal
    ) -> Tuple[List[str], List[str]]:
        """Analyze pricing risks and market opportunities."""
        
        risks = []
        opportunities = []
        
        # Model disagreement risk
        cma_value = float(cma_result.estimated_value)
        avm_value = float(avm_result.predicted_value)
        price_variance = abs(cma_value - avm_value) / ((cma_value + avm_value) / 2)
        
        if price_variance > 0.15:
            risks.append(f"High model disagreement ({price_variance:.1%}) indicates valuation uncertainty")
        
        # Confidence-based risks
        if cma_result.confidence_level < 0.7:
            risks.append("Limited comparable sales data reduces pricing confidence")
        
        if avm_result.confidence_score < 0.7:
            risks.append("ML model shows lower confidence for this property type/location")
        
        # Market timing risks and opportunities
        risks.extend(timing_result.risk_factors)
        opportunities.extend(timing_result.opportunity_factors)
        
        # Competition analysis
        competition_level = timing_result.competition_analysis.get('level', 'Unknown')
        if competition_level in ['High', 'Very High']:
            risks.append(f"{competition_level} competition may pressure pricing and extend sale time")
        elif competition_level == 'Low':
            opportunities.append("Low competition provides pricing flexibility and faster sale potential")
        
        # Market condition opportunities
        if timing_result.current_market_condition.value in ['Strong Sellers Market', 'Moderate Sellers Market']:
            opportunities.append(f"{timing_result.current_market_condition.value} supports premium pricing")
        
        # Seasonal factors
        if timing_result.price_timing_adjustment > 0.03:
            opportunities.append(f"Seasonal market conditions support {timing_result.price_timing_adjustment:.1%} pricing premium")
        elif timing_result.price_timing_adjustment < -0.03:
            risks.append(f"Seasonal market weakness may reduce pricing by {abs(timing_result.price_timing_adjustment):.1%}")
        
        return risks, opportunities
    
    async def _perform_sensitivity_analysis(
        self,
        property_data: Dict[str, Any],
        base_price: Decimal
    ) -> Dict[str, Decimal]:
        """Perform sensitivity analysis on key pricing factors."""
        
        sensitivity = {}
        base_value = float(base_price)
        
        # Price sensitivity to market timing
        timing_scenarios = [
            ("Immediate Sale", 0.0),
            ("Market Improvement (+2%)", 0.02),
            ("Market Decline (-3%)", -0.03),
            ("Seasonal Peak (+5%)", 0.05)
        ]
        
        for scenario, adjustment in timing_scenarios:
            adjusted_price = base_value * (1 + adjustment)
            sensitivity[scenario] = Decimal(str(round(adjusted_price, 2)))
        
        # Competition sensitivity
        competition_scenarios = [
            ("Low Competition (+3%)", 0.03),
            ("High Competition (-5%)", -0.05)
        ]
        
        for scenario, adjustment in competition_scenarios:
            adjusted_price = base_value * (1 + adjustment)
            sensitivity[scenario] = Decimal(str(round(adjusted_price, 2)))
        
        # Feature sensitivity (if data available)
        if property_data.get('bedrooms'):
            bedroom_scenarios = [
                ("Extra Bedroom (+15%)", 0.15),
                ("One Less Bedroom (-15%)", -0.15)
            ]
            
            for scenario, adjustment in bedroom_scenarios:
                adjusted_price = base_value * (1 + adjustment)
                sensitivity[scenario] = Decimal(str(round(adjusted_price, 2)))
        
        return sensitivity
    
    def _generate_methodology_summary(
        self,
        model_weights: Dict[str, float],
        confidence_score: float
    ) -> str:
        """Generate comprehensive methodology summary."""
        
        return (
            f"Comprehensive pricing analysis combining Comparable Sales Analysis "
            f"({model_weights['cma']:.0%} weight), Automated Valuation Model "
            f"({model_weights['avm']:.0%} weight), and Market Timing Analysis "
            f"({model_weights['timing']:.0%} weight). Model weights dynamically adjusted "
            f"based on data quality and confidence levels. Overall confidence score: "
            f"{confidence_score:.2f}. Recommendations include auction reserves, "
            f"private sale pricing, and market timing optimization based on current "
            f"market conditions, seasonal patterns, and competitive landscape analysis."
        )