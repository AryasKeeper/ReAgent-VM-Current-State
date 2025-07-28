"""
Seller Strategy Agent - Tools

Specialized tools for property seller strategy analysis and recommendations.
"""

import asyncio
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging

from langchain.tools import Tool
from pydantic import BaseModel, Field

from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.data.models.property_models import Property, PropertyPriceHistory
from reagent_sydney.data.models.market_models import SuburbStats, MarketTrend

from .pricing.pricing_coordinator import PricingCoordinator
from .strategy.sale_method_recommender import SaleMethodRecommender
from .strategy.property_enhancement_advisor import PropertyEnhancementAdvisor


class PropertyAnalysisInput(BaseModel):
    """Input schema for property analysis."""
    property_id: str = Field(description="Property ID to analyze")
    budget_limit: Optional[float] = Field(None, description="Enhancement budget limit")
    timeframe_weeks: Optional[int] = Field(12, description="Available timeframe in weeks")


class PricingAnalysisInput(BaseModel):
    """Input schema for pricing analysis."""
    property_id: str = Field(description="Property ID for pricing analysis")
    include_sensitivity: bool = Field(True, description="Include sensitivity analysis")


class SaleMethodInput(BaseModel):
    """Input schema for sale method analysis."""
    property_id: str = Field(description="Property ID for sale method analysis")


class EnhancementInput(BaseModel):
    """Input schema for enhancement analysis."""
    property_id: str = Field(description="Property ID for enhancement analysis")
    budget_limit: Optional[float] = Field(None, description="Budget constraint")
    timeframe_weeks: Optional[int] = Field(12, description="Available timeframe")


class SellerStrategyTools:
    """Collection of tools for seller strategy analysis."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.pricing_coordinator = PricingCoordinator()
        self.sale_method_recommender = SaleMethodRecommender()
        self.enhancement_advisor = PropertyEnhancementAdvisor()
    
    def get_tools(self) -> List[Tool]:
        """Get all seller strategy tools."""
        
        return [
            self._create_comprehensive_analysis_tool(),
            self._create_pricing_analysis_tool(),
            self._create_sale_method_tool(),
            self._create_enhancement_analysis_tool(),
            self._create_market_comparison_tool(),
            self._create_property_lookup_tool()
        ]
    
    def _create_comprehensive_analysis_tool(self) -> Tool:
        """Create comprehensive seller strategy analysis tool."""
        
        async def comprehensive_analysis(input_str: str) -> str:
            """
            Perform comprehensive seller strategy analysis including pricing,
            sale method recommendation, and enhancement planning.
            """
            try:
                # Parse input
                import json
                input_data = json.loads(input_str)
                property_id = input_data.get('property_id')
                budget_limit = input_data.get('budget_limit')
                timeframe_weeks = input_data.get('timeframe_weeks', 12)
                
                if not property_id:
                    return "Error: property_id is required"
                
                # Get property data
                property_data = await self._get_property_data(property_id)
                if not property_data:
                    return f"Error: Property {property_id} not found"
                
                # Run comprehensive analysis
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
                
                # Wait for results
                pricing_result, sale_method_result, enhancement_result = await asyncio.gather(
                    pricing_task, sale_method_task, enhancement_task
                )
                
                # Format comprehensive response
                response = {
                    'property_id': property_id,
                    'recommended_listing_price': float(pricing_result.listing_price),
                    'price_range': {
                        'low': float(pricing_result.price_range_low),
                        'high': float(pricing_result.price_range_high)
                    },
                    'confidence_score': pricing_result.confidence_score,
                    'recommended_sale_method': sale_method_result.recommended_method.value,
                    'expected_days_to_sell': sale_method_result.method_analyses[sale_method_result.recommended_method].expected_days_to_sell,
                    'sale_probability': sale_method_result.method_analyses[sale_method_result.recommended_method].sale_probability,
                    'enhancement_roi': float(enhancement_result.overall_roi),
                    'total_enhancement_cost': float(enhancement_result.total_investment_required),
                    'expected_enhancement_return': float(enhancement_result.total_expected_return),
                    'timeline_weeks': enhancement_result.total_timeframe_weeks + 4,  # Add sale time
                    'key_recommendations': [
                        f"List at ${float(pricing_result.listing_price):,.0f} via {sale_method_result.recommended_method.value}",
                        f"Invest ${float(enhancement_result.total_investment_required):,.0f} in improvements for {enhancement_result.overall_roi:.1f}% ROI",
                        f"Expected sale within {sale_method_result.method_analyses[sale_method_result.recommended_method].expected_days_to_sell} days"
                    ]
                }
                
                return json.dumps(response, indent=2)
                
            except Exception as e:
                self.logger.error(f"Comprehensive analysis failed: {str(e)}")
                return f"Error in comprehensive analysis: {str(e)}"
        
        def sync_wrapper(input_str: str) -> str:
            """Synchronous wrapper for async function."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(comprehensive_analysis(input_str))
            finally:
                loop.close()
        
        return Tool(
            name="comprehensive_seller_analysis",
            description="Perform comprehensive seller strategy analysis including pricing, sale method, and enhancements. Input: JSON with property_id, optional budget_limit and timeframe_weeks",
            func=sync_wrapper
        )
    
    def _create_pricing_analysis_tool(self) -> Tool:
        """Create pricing analysis tool."""
        
        async def pricing_analysis(input_str: str) -> str:
            """Analyze property pricing using multiple valuation methods."""
            try:
                import json
                input_data = json.loads(input_str)
                property_id = input_data.get('property_id')
                
                if not property_id:
                    return "Error: property_id is required"
                
                property_data = await self._get_property_data(property_id)
                if not property_data:
                    return f"Error: Property {property_id} not found"
                
                # Perform pricing analysis
                result = await self.pricing_coordinator.generate_pricing_strategy(property_data)
                
                response = {
                    'property_id': property_id,
                    'recommended_price': float(result.recommended_price),
                    'price_range_low': float(result.price_range_low),
                    'price_range_high': float(result.price_range_high),
                    'confidence_score': result.confidence_score,
                    'pricing_strategy': result.pricing_strategy,
                    'auction_reserve': float(result.auction_reserve) if result.auction_reserve else None,
                    'private_sale_price': float(result.private_sale_price) if result.private_sale_price else None,
                    'cma_valuation': float(result.cma_result.estimated_value),
                    'avm_valuation': float(result.avm_result.predicted_value),
                    'market_timing_adjustment': result.timing_result.price_timing_adjustment,
                    'model_weights': result.model_weights,
                    'pricing_risks': result.pricing_risks[:3],
                    'market_opportunities': result.market_opportunities[:3]
                }
                
                return json.dumps(response, indent=2)
                
            except Exception as e:
                self.logger.error(f"Pricing analysis failed: {str(e)}")
                return f"Error in pricing analysis: {str(e)}"
        
        def sync_wrapper(input_str: str) -> str:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(pricing_analysis(input_str))
            finally:
                loop.close()
        
        return Tool(
            name="pricing_analysis",
            description="Analyze property pricing using CMA, AVM, and market timing. Input: JSON with property_id",
            func=sync_wrapper
        )
    
    def _create_sale_method_tool(self) -> Tool:
        """Create sale method recommendation tool."""
        
        async def sale_method_analysis(input_str: str) -> str:
            """Recommend optimal sale method (auction vs private sale)."""
            try:
                import json
                input_data = json.loads(input_str)
                property_id = input_data.get('property_id')
                
                if not property_id:
                    return "Error: property_id is required"
                
                property_data = await self._get_property_data(property_id)
                if not property_data:
                    return f"Error: Property {property_id} not found"
                
                # Perform sale method analysis
                result = await self.sale_method_recommender.recommend_sale_method(property_data)
                
                # Format response
                recommended_analysis = result.method_analyses[result.recommended_method]
                alternative_analysis = result.method_analyses[result.alternative_method]
                
                response = {
                    'property_id': property_id,
                    'recommended_method': result.recommended_method.value,
                    'confidence_score': result.confidence_score,
                    'recommended_analysis': {
                        'suitability_score': recommended_analysis.suitability_score,
                        'expected_price': float(recommended_analysis.expected_price),
                        'expected_days': recommended_analysis.expected_days_to_sell,
                        'sale_probability': recommended_analysis.sale_probability,
                        'cost_estimate': float(recommended_analysis.cost_estimate),
                        'advantages': recommended_analysis.advantages[:3],
                        'risks': recommended_analysis.risks[:3]
                    },
                    'alternative_method': result.alternative_method.value,
                    'alternative_analysis': {
                        'suitability_score': alternative_analysis.suitability_score,
                        'expected_price': float(alternative_analysis.expected_price),
                        'expected_days': alternative_analysis.expected_days_to_sell,
                        'sale_probability': alternative_analysis.sale_probability
                    },
                    'optimal_timing': result.optimal_timing,
                    'preparation_requirements': result.preparation_requirements[:4],
                    'success_factors': result.success_factors[:3]
                }
                
                return json.dumps(response, indent=2)
                
            except Exception as e:
                self.logger.error(f"Sale method analysis failed: {str(e)}")
                return f"Error in sale method analysis: {str(e)}"
        
        def sync_wrapper(input_str: str) -> str:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(sale_method_analysis(input_str))
            finally:
                loop.close()
        
        return Tool(
            name="sale_method_analysis",
            description="Recommend optimal sale method (auction vs private sale) with analysis. Input: JSON with property_id",
            func=sync_wrapper
        )
    
    def _create_enhancement_analysis_tool(self) -> Tool:
        """Create property enhancement analysis tool."""
        
        async def enhancement_analysis(input_str: str) -> str:
            """Analyze property enhancement opportunities with ROI calculations."""
            try:
                import json
                input_data = json.loads(input_str)
                property_id = input_data.get('property_id')
                budget_limit = input_data.get('budget_limit')
                timeframe_weeks = input_data.get('timeframe_weeks', 12)
                
                if not property_id:
                    return "Error: property_id is required"
                
                property_data = await self._get_property_data(property_id)
                if not property_data:
                    return f"Error: Property {property_id} not found"
                
                # Perform enhancement analysis
                result = await self.enhancement_advisor.analyze_property_enhancements(
                    property_data,
                    Decimal(str(budget_limit)) if budget_limit else None,
                    timeframe_weeks
                )
                
                # Format response
                response = {
                    'property_id': property_id,
                    'total_investment': float(result.total_investment_required),
                    'total_expected_return': float(result.total_expected_return),
                    'overall_roi': result.overall_roi,
                    'net_benefit': float(result.net_benefit),
                    'timeframe_weeks': result.total_timeframe_weeks,
                    'essential_improvements': [
                        {
                            'title': imp.title,
                            'cost': float(imp.estimated_cost),
                            'value_add': float(imp.expected_value_add),
                            'roi': imp.roi_percentage,
                            'timeframe': imp.timeframe_weeks
                        }
                        for imp in result.essential_improvements
                    ],
                    'high_priority_improvements': [
                        {
                            'title': imp.title,
                            'cost': float(imp.estimated_cost),
                            'value_add': float(imp.expected_value_add),
                            'roi': imp.roi_percentage,
                            'timeframe': imp.timeframe_weeks
                        }
                        for imp in result.high_priority_improvements[:3]  # Top 3
                    ],
                    'competitive_advantages': result.competitive_advantages,
                    'market_risks': result.market_risks[:3],
                    'budget_scenarios': {
                        scenario: {
                            'budget': data['budget'],
                            'expected_return': data['expected_return']
                        }
                        for scenario, data in result.budget_scenarios.items()
                    }
                }
                
                return json.dumps(response, indent=2)
                
            except Exception as e:
                self.logger.error(f"Enhancement analysis failed: {str(e)}")
                return f"Error in enhancement analysis: {str(e)}"
        
        def sync_wrapper(input_str: str) -> str:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(enhancement_analysis(input_str))
            finally:
                loop.close()
        
        return Tool(
            name="enhancement_analysis",
            description="Analyze property enhancement opportunities with ROI calculations. Input: JSON with property_id, optional budget_limit and timeframe_weeks",
            func=sync_wrapper
        )
    
    def _create_market_comparison_tool(self) -> Tool:
        """Create market comparison tool."""
        
        async def market_comparison(input_str: str) -> str:
            """Compare property against market benchmarks."""
            try:
                import json
                input_data = json.loads(input_str)
                property_id = input_data.get('property_id')
                
                if not property_id:
                    return "Error: property_id is required"
                
                property_data = await self._get_property_data(property_id)
                if not property_data:
                    return f"Error: Property {property_id} not found"
                
                # Get market statistics
                async with get_db_session() as session:
                    suburb_stats = session.query(SuburbStats).filter(
                        SuburbStats.suburb_name == property_data['suburb']
                    ).order_by(SuburbStats.stats_date.desc()).first()
                    
                    market_trend = session.query(MarketTrend).filter(
                        MarketTrend.geography_name == property_data['suburb']
                    ).order_by(MarketTrend.period_end.desc()).first()
                
                # Calculate comparisons
                property_price = property_data.get('estimated_price', 0)
                suburb_median = float(suburb_stats.house_median_price) if suburb_stats and suburb_stats.house_median_price else 1200000
                
                price_vs_median = ((property_price - suburb_median) / suburb_median) * 100
                
                response = {
                    'property_id': property_id,
                    'property_price': property_price,
                    'suburb_median': suburb_median,
                    'price_vs_median_percent': round(price_vs_median, 1),
                    'market_position': (
                        'Premium' if price_vs_median > 20 else
                        'Above Average' if price_vs_median > 5 else
                        'Market Average' if price_vs_median > -5 else
                        'Below Average'
                    ),
                    'suburb_stats': {
                        'median_price': suburb_median,
                        'price_growth_12m': float(suburb_stats.house_price_growth_12m) if suburb_stats and suburb_stats.house_price_growth_12m else 0,
                        'sales_last_30d': suburb_stats.sales_last_30d if suburb_stats else 0,
                        'active_listings': suburb_stats.active_listings if suburb_stats else 0,
                        'avg_days_on_market': float(suburb_stats.avg_time_on_market) if suburb_stats and suburb_stats.avg_time_on_market else 30
                    },
                    'market_trend': {
                        'trend_direction': market_trend.trend_direction if market_trend else 'Stable',
                        'price_change_percent': float(market_trend.price_change_percent) if market_trend and market_trend.price_change_percent else 0,
                        'absorption_rate': float(market_trend.absorption_rate) if market_trend and market_trend.absorption_rate else 0.5
                    }
                }
                
                return json.dumps(response, indent=2)
                
            except Exception as e:
                self.logger.error(f"Market comparison failed: {str(e)}")
                return f"Error in market comparison: {str(e)}"
        
        def sync_wrapper(input_str: str) -> str:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(market_comparison(input_str))
            finally:
                loop.close()
        
        return Tool(
            name="market_comparison",
            description="Compare property against market benchmarks and suburb statistics. Input: JSON with property_id",
            func=sync_wrapper
        )
    
    def _create_property_lookup_tool(self) -> Tool:
        """Create property lookup tool."""
        
        async def property_lookup(input_str: str) -> str:
            """Look up property details by ID."""
            try:
                property_id = input_str.strip()
                
                property_data = await self._get_property_data(property_id)
                if not property_data:
                    return f"Error: Property {property_id} not found"
                
                response = {
                    'property_id': property_id,
                    'title': property_data.get('title', 'N/A'),
                    'address': property_data.get('address_line_1', 'N/A'),
                    'suburb': property_data.get('suburb', 'N/A'),
                    'postcode': property_data.get('postcode', 'N/A'),
                    'property_type': property_data.get('property_type', 'N/A'),
                    'bedrooms': property_data.get('bedrooms', 0),
                    'bathrooms': property_data.get('bathrooms', 0),
                    'car_spaces': property_data.get('car_spaces', 0),
                    'land_size': property_data.get('land_size', 0),
                    'building_size': property_data.get('building_size', 0),
                    'current_price': property_data.get('price', 0),
                    'listing_status': property_data.get('listing_status', 'N/A'),
                    'days_on_market': property_data.get('days_on_market', 0)
                }
                
                import json
                return json.dumps(response, indent=2)
                
            except Exception as e:
                self.logger.error(f"Property lookup failed: {str(e)}")
                return f"Error looking up property: {str(e)}"
        
        def sync_wrapper(input_str: str) -> str:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(property_lookup(input_str))
            finally:
                loop.close()
        
        return Tool(
            name="property_lookup",
            description="Look up property details by property ID. Input: property_id as string",
            func=sync_wrapper
        )
    
    async def _get_property_data(self, property_id: str) -> Optional[Dict[str, Any]]:
        """Get property data from database."""
        
        try:
            async with get_db_session() as session:
                property_obj = await session.get(Property, property_id)
                
                if not property_obj:
                    return None
                
                return {
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
                
        except Exception as e:
            self.logger.error(f"Error retrieving property data: {str(e)}")
            return None