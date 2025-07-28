"""
Seller Strategy Agent

Main agent class for comprehensive seller strategy analysis and recommendations.
Integrates pricing models, strategic advisory components, and market intelligence.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging
from dataclasses import dataclass

from langchain.tools import Tool
from crewai import Agent

from reagent_sydney.agents.base import BaseReAgentAgent, AgentConfig, AgentRole, AgentPriority
from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.data.models.property_models import Property
from reagent_sydney.utils.validation.property_validation import validate_property_data

from .pricing.pricing_coordinator import PricingCoordinator, PricingRecommendation
from .strategy.sale_method_recommender import SaleMethodRecommender, SaleMethodRecommendation
from .strategy.property_enhancement_advisor import PropertyEnhancementAdvisor, PropertyEnhancementPlan


@dataclass
class SellerStrategyResult:
    """Comprehensive seller strategy result."""
    property_id: str
    analysis_date: datetime
    execution_time: float
    
    # Core Analysis Results
    pricing_recommendation: PricingRecommendation
    sale_method_recommendation: SaleMethodRecommendation
    enhancement_plan: PropertyEnhancementPlan
    
    # Strategic Summary
    recommended_listing_price: Decimal
    expected_sale_price: Decimal
    optimal_sale_method: str
    timeline_weeks: int
    total_investment_required: Decimal
    expected_net_return: Decimal
    
    # Key Insights
    market_position: str
    competitive_advantages: List[str]
    key_risks: List[str]
    success_probability: float
    
    # Action Plan
    immediate_actions: List[str]
    preparation_timeline: Dict[str, int]  # Action -> weeks
    success_metrics: Dict[str, Any]
    
    # Confidence Metrics
    overall_confidence: float
    data_quality_score: float
    recommendation_reliability: str


class SellerStrategyAgent(BaseReAgentAgent):
    """
    Advanced seller strategy agent providing comprehensive pricing and sale strategy.
    
    Key Capabilities:
    - Multi-model pricing analysis (CMA, AVM, Market Timing)
    - Sale method optimization (Auction vs Private Sale)  
    - Property enhancement ROI analysis
    - Strategic timeline planning
    - Risk assessment and mitigation
    - Performance tracking and validation
    """
    
    def __init__(self):
        # Initialize agent configuration
        config = AgentConfig(
            name="Seller Strategy Agent",
            role=AgentRole.STRATEGIST,
            description="Provides comprehensive pricing and strategic advice for property sellers",
            version="1.0.0",
            max_execution_time=300,  # 5 minutes max
            max_retries=2,
            priority=AgentPriority.HIGH,
            required_services=["database", "cache"],
            required_tools=["property_lookup", "market_analysis", "pricing_analysis"],
            enable_metrics=True,
            custom_settings={
                "pricing_confidence_threshold": 0.7,
                "enhancement_roi_threshold": 1.2,
                "max_enhancement_budget_ratio": 0.15  # Max 15% of property value
            }
        )
        
        super().__init__(config)
        
        # Initialize component analyzers
        self.pricing_coordinator = PricingCoordinator()
        self.sale_method_recommender = SaleMethodRecommender()
        self.enhancement_advisor = PropertyEnhancementAdvisor()
        
        # Performance tracking
        self.analysis_count = 0
        self.average_execution_time = 0.0
        self.accuracy_metrics = {
            'pricing_accuracy': 0.0,
            'timing_accuracy': 0.0,
            'sale_method_accuracy': 0.0
        }
    
    async def _initialize_agent(self) -> None:
        """Initialize agent-specific components."""
        try:
            # Initialize ML models
            await self.pricing_coordinator.avm_model.train_model()
            
            # Warm up caches
            await self._warm_up_caches()
            
            self.logger.info("Seller Strategy Agent initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Seller Strategy Agent: {e}")
            raise
    
    async def _cleanup_agent(self) -> None:
        """Cleanup agent resources."""
        try:
            # Save any pending metrics
            await self._save_performance_metrics()
            
            self.logger.info("Seller Strategy Agent cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during agent cleanup: {e}")
    
    async def _execute_agent_logic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main agent execution logic."""
        start_time = time.time()
        
        try:
            # Validate input
            property_id = input_data.get('property_id')
            if not property_id:
                raise ValueError("property_id is required")
            
            # Get property data
            property_data = await self._get_property_data(property_id)
            
            # Validate property data
            validation_result = validate_property_data(property_data)
            if not validation_result['is_valid']:
                raise ValueError(f"Invalid property data: {validation_result['errors']}")
            
            # Execute comprehensive analysis
            result = await self._execute_comprehensive_analysis(property_data, input_data)
            
            # Track performance
            execution_time = time.time() - start_time
            await self._update_performance_metrics(execution_time, result)
            
            # Return structured result
            return {
                'success': True,
                'result': result,
                'execution_time': execution_time,
                'property_id': property_id
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Agent execution failed: {str(e)}", exc_info=True)
            
            return {
                'success': False,
                'error': str(e),
                'execution_time': execution_time,
                'property_id': input_data.get('property_id', 'unknown')
            }
    
    async def _execute_comprehensive_analysis(
        self,
        property_data: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> SellerStrategyResult:
        """Execute comprehensive seller strategy analysis."""
        
        analysis_start = time.time()
        
        # Extract analysis parameters
        budget_limit = input_data.get('budget_limit')
        timeframe_weeks = input_data.get('timeframe_weeks', 12)
        pricing_strategy = input_data.get('pricing_strategy', 'market')
        
        self.logger.info(f"Starting comprehensive analysis for property {property_data['id']}")
        
        # Run core analyses in parallel for performance
        pricing_task = asyncio.create_task(
            self.pricing_coordinator.generate_pricing_strategy(property_data)
        )
        
        sale_method_task = asyncio.create_task(
            self.sale_method_recommender.recommend_sale_method(property_data)
        )
        
        enhancement_task = asyncio.create_task(
            self.enhancement_advisor.analyze_property_enhancements(
                property_data, 
                Decimal(str(budget_limit)) if budget_limit else None,
                timeframe_weeks
            )
        )
        
        # Wait for all analyses to complete
        pricing_result, sale_method_result, enhancement_result = await asyncio.gather(
            pricing_task, sale_method_task, enhancement_task
        )
        
        # Cross-reference and optimize recommendations
        optimized_recommendations = self._optimize_cross_recommendations(
            pricing_result, sale_method_result, enhancement_result, property_data
        )
        
        # Generate strategic summary
        strategic_summary = self._generate_strategic_summary(
            optimized_recommendations, property_data
        )
        
        # Calculate execution time
        execution_time = time.time() - analysis_start
        
        # Build comprehensive result
        result = SellerStrategyResult(
            property_id=property_data['id'],
            analysis_date=datetime.utcnow(),
            execution_time=execution_time,
            pricing_recommendation=optimized_recommendations['pricing'],
            sale_method_recommendation=optimized_recommendations['sale_method'],
            enhancement_plan=optimized_recommendations['enhancements'],
            recommended_listing_price=strategic_summary['listing_price'],
            expected_sale_price=strategic_summary['expected_price'],
            optimal_sale_method=strategic_summary['sale_method'],
            timeline_weeks=strategic_summary['timeline_weeks'],
            total_investment_required=strategic_summary['investment_required'],
            expected_net_return=strategic_summary['net_return'],
            market_position=strategic_summary['market_position'],
            competitive_advantages=strategic_summary['advantages'],
            key_risks=strategic_summary['risks'],
            success_probability=strategic_summary['success_probability'],
            immediate_actions=strategic_summary['immediate_actions'],
            preparation_timeline=strategic_summary['preparation_timeline'],
            success_metrics=strategic_summary['success_metrics'],
            overall_confidence=strategic_summary['confidence'],
            data_quality_score=strategic_summary['data_quality'],
            recommendation_reliability=strategic_summary['reliability']
        )
        
        self.logger.info(
            f"Comprehensive analysis completed in {execution_time:.2f}s: "
            f"${result.recommended_listing_price:,.2f} listing price, "
            f"{result.optimal_sale_method} method, "
            f"{result.timeline_weeks} week timeline"
        )
        
        return result
    
    def _optimize_cross_recommendations(
        self,
        pricing_result: PricingRecommendation,
        sale_method_result: SaleMethodRecommendation,
        enhancement_result: PropertyEnhancementPlan,
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize recommendations across all analysis components."""
        
        # Start with original recommendations
        optimized = {
            'pricing': pricing_result,
            'sale_method': sale_method_result,
            'enhancements': enhancement_result
        }
        
        # Cross-optimize pricing and enhancements
        if enhancement_result.total_expected_return > 0:
            # Adjust pricing recommendation to account for enhancement value
            enhanced_value = float(pricing_result.recommended_price) + float(enhancement_result.total_expected_return)
            
            # Create adjusted pricing recommendation
            adjusted_pricing = pricing_result
            adjusted_pricing.recommended_price = Decimal(str(round(enhanced_value, 2)))
            adjusted_pricing.price_range_low = Decimal(str(round(enhanced_value * 0.95, 2)))
            adjusted_pricing.price_range_high = Decimal(str(round(enhanced_value * 1.05, 2)))
            
            optimized['pricing'] = adjusted_pricing
        
        # Optimize sale method based on enhancements
        if enhancement_result.total_investment_required > 0:
            # High-quality enhancements may favor auction method
            enhancement_score = float(enhancement_result.overall_roi)
            if enhancement_score > 30:  # High ROI enhancements
                # Check if auction wasn't already recommended
                if sale_method_result.recommended_method.value != 'Auction':
                    auction_analysis = next(
                        (analysis for method, analysis in sale_method_result.method_analyses.items() 
                         if method.value == 'Auction'), None
                    )
                    if auction_analysis and auction_analysis.suitability_score > 70:
                        # Switch to auction if it scores well
                        optimized_sale_method = sale_method_result
                        optimized_sale_method.recommended_method = next(
                            method for method in sale_method_result.method_analyses.keys() 
                            if method.value == 'Auction'
                        )
                        optimized['sale_method'] = optimized_sale_method
        
        # Timeline optimization
        enhancement_weeks = enhancement_result.total_timeframe_weeks
        sale_method_weeks = 4  # Default marketing period
        
        if enhancement_weeks + sale_method_weeks > 16:  # Too long
            # Prioritize highest ROI enhancements only
            high_roi_enhancements = [
                r for r in (enhancement_result.essential_improvements + enhancement_result.high_priority_improvements)
                if r.roi_percentage > 50
            ]
            
            if high_roi_enhancements:
                # Create streamlined enhancement plan
                streamlined_plan = enhancement_result
                streamlined_plan.essential_improvements = high_roi_enhancements[:3]  # Top 3
                streamlined_plan.high_priority_improvements = []
                streamlined_plan.optional_improvements = []
                
                # Recalculate totals
                total_cost = sum(float(r.estimated_cost) for r in high_roi_enhancements[:3])
                total_return = sum(float(r.expected_value_add) for r in high_roi_enhancements[:3])
                
                streamlined_plan.total_investment_required = Decimal(str(round(total_cost, 2)))
                streamlined_plan.total_expected_return = Decimal(str(round(total_return, 2)))
                streamlined_plan.overall_roi = ((total_return - total_cost) / total_cost * 100) if total_cost > 0 else 0
                streamlined_plan.total_timeframe_weeks = min(8, sum(r.timeframe_weeks for r in high_roi_enhancements[:3]))
                
                optimized['enhancements'] = streamlined_plan
        
        return optimized
    
    def _generate_strategic_summary(
        self,
        optimized_recommendations: Dict[str, Any],
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate strategic summary and action plan."""
        
        pricing = optimized_recommendations['pricing']
        sale_method = optimized_recommendations['sale_method']
        enhancements = optimized_recommendations['enhancements']
        
        # Determine listing price based on sale method
        if sale_method.recommended_method.value == 'Auction':
            listing_price = pricing.auction_reserve
        else:
            listing_price = pricing.listing_price
        
        # Calculate expected sale price
        method_analysis = sale_method.method_analyses[sale_method.recommended_method]
        expected_price = method_analysis.expected_price
        
        # Timeline calculation
        enhancement_weeks = enhancements.total_timeframe_weeks
        sale_weeks = method_analysis.expected_days_to_sell // 7
        total_timeline = enhancement_weeks + sale_weeks
        
        # Investment and returns
        investment_required = enhancements.total_investment_required
        enhancement_return = enhancements.total_expected_return
        sale_price_after_enhancements = float(expected_price) + float(enhancement_return)
        net_return = sale_price_after_enhancements - float(investment_required)
        
        # Market position assessment
        suburb_median = 1200000  # Would come from market data
        property_value = float(pricing.recommended_price)
        
        if property_value > suburb_median * 1.5:
            market_position = "Premium Market Position"
        elif property_value > suburb_median * 1.1:
            market_position = "Above Market Average"
        elif property_value > suburb_median * 0.9:
            market_position = "Market Average"
        else:
            market_position = "Below Market Average"
        
        # Competitive advantages
        advantages = []
        advantages.extend(pricing.market_opportunities[:2])
        advantages.extend(enhancements.competitive_advantages[:2])
        
        if sale_method.confidence_score > 0.8:
            advantages.append(f"Optimal {sale_method.recommended_method.value} strategy")
        
        # Key risks
        risks = []
        risks.extend(pricing.pricing_risks[:2])
        risks.extend(sale_method.method_analyses[sale_method.recommended_method].risks[:2])
        risks.extend(enhancements.market_risks[:1])
        
        # Success probability (weighted average)
        pricing_confidence = pricing.confidence_score
        method_probability = method_analysis.sale_probability
        enhancement_impact = min(0.2, float(enhancements.overall_roi) / 100 * 0.1)
        
        success_probability = (pricing_confidence * 0.4 + method_probability * 0.5 + enhancement_impact * 0.1)
        
        # Immediate actions
        immediate_actions = [
            "Complete property condition assessment",
            f"Prepare for {sale_method.recommended_method.value.lower()} marketing strategy"
        ]
        
        if enhancements.essential_improvements:
            immediate_actions.append("Begin essential property improvements")
        
        immediate_actions.extend(sale_method.preparation_requirements[:2])
        
        # Preparation timeline
        timeline = {}
        if enhancements.essential_improvements:
            timeline["Essential Improvements"] = 4
        if enhancements.high_priority_improvements:
            timeline["High Priority Enhancements"] = 6
        timeline["Marketing Launch"] = enhancement_weeks + 1
        timeline["Expected Sale"] = total_timeline
        
        # Success metrics
        metrics = {
            'target_sale_price': float(expected_price),
            'maximum_days_on_market': method_analysis.expected_days_to_sell + 14,
            'minimum_roi_threshold': float(enhancements.overall_roi),
            'confidence_threshold': 0.7
        }
        
        # Overall confidence
        confidence_factors = [
            pricing.confidence_score,
            sale_method.confidence_score,
            min(1.0, enhancements.overall_roi / 50)  # Cap at 50% ROI for confidence
        ]
        overall_confidence = sum(confidence_factors) / len(confidence_factors)
        
        # Data quality score
        data_quality = 0.8  # Would be calculated from actual data completeness
        
        # Recommendation reliability
        if overall_confidence > 0.8:
            reliability = "High"
        elif overall_confidence > 0.6:
            reliability = "Moderate"
        else:
            reliability = "Low"
        
        return {
            'listing_price': listing_price,
            'expected_price': Decimal(str(round(sale_price_after_enhancements, 2))),
            'sale_method': sale_method.recommended_method.value,
            'timeline_weeks': total_timeline,
            'investment_required': investment_required,
            'net_return': Decimal(str(round(net_return, 2))),
            'market_position': market_position,
            'advantages': advantages[:5],  # Top 5
            'risks': list(set(risks))[:4],  # Top 4 unique risks
            'success_probability': success_probability,
            'immediate_actions': immediate_actions,
            'preparation_timeline': timeline,
            'success_metrics': metrics,
            'confidence': overall_confidence,
            'data_quality': data_quality,
            'reliability': reliability
        }
    
    async def _get_property_data(self, property_id: str) -> Dict[str, Any]:
        """Retrieve property data from database."""
        
        async with get_db_session() as session:
            property_obj = await session.get(Property, property_id)
            
            if not property_obj:
                raise ValueError(f"Property {property_id} not found")
            
            # Convert to dictionary
            property_data = {
                'id': str(property_obj.id),
                'listing_id': property_obj.listing_id,
                'title': property_obj.title,
                'description': property_obj.description,
                'property_type': property_obj.property_type,
                'address_line_1': property_obj.address_line_1,
                'suburb': property_obj.suburb,
                'postcode': property_obj.postcode,
                'latitude': float(property_obj.latitude) if property_obj.latitude else None,
                'longitude': float(property_obj.longitude) if property_obj.longitude else None,
                'bedrooms': property_obj.bedrooms,
                'bathrooms': property_obj.bathrooms,
                'car_spaces': property_obj.car_spaces,
                'land_size': property_obj.land_size,
                'building_size': property_obj.building_size,
                'price': float(property_obj.price) if property_obj.price else None,
                'estimated_price': float(property_obj.price) if property_obj.price else 1000000,
                'listing_status': property_obj.listing_status,
                'listing_type': property_obj.listing_type,
                'features': property_obj.features or [],
                'days_on_market': property_obj.days_on_market
            }
            
            return property_data
    
    async def _warm_up_caches(self) -> None:
        """Warm up frequently accessed caches."""
        try:
            # Warm up suburb statistics cache
            # This would pre-load common suburb data
            pass
        except Exception as e:
            self.logger.warning(f"Cache warm-up failed: {e}")
    
    async def _update_performance_metrics(self, execution_time: float, result: SellerStrategyResult) -> None:
        """Update agent performance metrics."""
        
        self.analysis_count += 1
        
        # Update average execution time
        self.average_execution_time = (
            (self.average_execution_time * (self.analysis_count - 1) + execution_time) / 
            self.analysis_count
        )
        
        # Cache performance metrics
        if self.cache_manager:
            metrics = {
                'analysis_count': self.analysis_count,
                'average_execution_time': self.average_execution_time,
                'last_analysis': datetime.utcnow().isoformat(),
                'overall_confidence': result.overall_confidence
            }
            
            await self.cache_manager.set(
                f"seller_strategy_metrics",
                metrics,
                ttl=3600
            )
    
    async def _save_performance_metrics(self) -> None:
        """Save performance metrics to persistent storage."""
        try:
            # This would save to database or monitoring system
            pass
        except Exception as e:
            self.logger.warning(f"Failed to save performance metrics: {e}")
    
    async def _initialize_tools(self) -> List[Tool]:
        """Initialize agent-specific tools."""
        
        tools = []
        
        # Property lookup tool
        def property_lookup(property_id: str) -> str:
            """Look up property information by ID."""
            try:
                # This would be implemented as an async wrapper
                return f"Property data retrieved for {property_id}"
            except Exception as e:
                return f"Error retrieving property {property_id}: {str(e)}"
        
        tools.append(Tool(
            name="property_lookup",
            description="Look up property information by property ID",
            func=property_lookup
        ))
        
        # Market analysis tool
        def market_analysis(suburb: str, property_type: str) -> str:
            """Analyze market conditions for suburb and property type."""
            try:
                return f"Market analysis completed for {property_type} in {suburb}"
            except Exception as e:
                return f"Market analysis failed: {str(e)}"
        
        tools.append(Tool(
            name="market_analysis", 
            description="Analyze current market conditions",
            func=market_analysis
        ))
        
        return tools
    
    def _get_agent_goal(self) -> str:
        """Get agent goal for CrewAI."""
        return (
            "Provide comprehensive seller strategy recommendations including optimal pricing, "
            "sale method selection, and property enhancement advice to maximize sale outcomes "
            "for property sellers and their agents."
        )
    
    def _get_agent_backstory(self) -> str:
        """Get agent backstory for CrewAI."""
        return (
            "You are an expert real estate strategist with deep knowledge of Sydney property "
            "markets, pricing methodologies, and sales optimization. You combine statistical "
            "analysis, market intelligence, and strategic planning to help sellers achieve "
            "optimal outcomes. Your recommendations are data-driven, practical, and tailored "
            "to current market conditions and individual property characteristics."
        )