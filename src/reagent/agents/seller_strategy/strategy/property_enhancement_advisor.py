"""
Property Enhancement Advisor

ROI analysis for property improvements and staging recommendations
to maximize sale price and market appeal.
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
import logging
from enum import Enum

from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session

from src.core.database.dependencies import get_db_session
from src.data.models.property_models import Property
from src.data.models.market_models import SuburbStats


class EnhancementCategory(str, Enum):
    """Property enhancement categories."""
    COSMETIC = "Cosmetic Improvements"
    STRUCTURAL = "Structural Renovations"
    LANDSCAPE = "Landscaping & Outdoor"
    KITCHEN = "Kitchen Renovation"
    BATHROOM = "Bathroom Renovation"
    FLOORING = "Flooring Upgrades"
    PAINT = "Paint & Finishes"
    STAGING = "Property Staging"
    ENERGY = "Energy Efficiency"
    TECHNOLOGY = "Technology Upgrades"


class EnhancementPriority(str, Enum):
    """Enhancement priority levels."""
    ESSENTIAL = "Essential"
    HIGH = "High Priority"
    MEDIUM = "Medium Priority"
    LOW = "Low Priority"
    OPTIONAL = "Optional"


@dataclass
class EnhancementRecommendation:
    """Individual enhancement recommendation."""
    category: EnhancementCategory
    title: str
    description: str
    priority: EnhancementPriority
    
    # Financial Analysis
    estimated_cost: Decimal
    expected_value_add: Decimal
    roi_percentage: float
    payback_period_months: int
    
    # Market Impact
    buyer_appeal_increase: float  # 0-1 scale
    days_on_market_reduction: int
    sale_probability_increase: float
    
    # Implementation Details
    timeframe_weeks: int
    difficulty_level: str  # Easy, Moderate, Complex
    required_permits: bool
    recommended_professionals: List[str]
    
    # Risk Factors
    risks: List[str]
    market_dependence: str  # Low, Medium, High
    
    # Evidence
    supporting_data: Dict[str, Any]


@dataclass
class PropertyEnhancementPlan:
    """Comprehensive property enhancement plan."""
    property_id: str
    analysis_date: datetime
    current_estimated_value: Decimal
    
    # Recommendations
    essential_improvements: List[EnhancementRecommendation]
    high_priority_improvements: List[EnhancementRecommendation]
    optional_improvements: List[EnhancementRecommendation]
    
    # Financial Summary
    total_investment_required: Decimal
    total_expected_return: Decimal
    overall_roi: float
    net_benefit: Decimal
    
    # Implementation Strategy
    recommended_sequence: List[str]
    total_timeframe_weeks: int
    budget_scenarios: Dict[str, Dict[str, Any]]
    
    # Market Context
    market_priorities: List[str]
    buyer_preferences: Dict[str, float]
    competitive_advantages: List[str]
    
    # Risk Assessment
    market_risks: List[str]
    implementation_risks: List[str]
    
    methodology_notes: str


class PropertyEnhancementAdvisor:
    """
    Advanced property enhancement analysis with ROI optimization.
    
    Analyzes property condition, market preferences, and buyer behavior
    to recommend improvements that maximize sale price and marketability.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # ROI benchmarks by enhancement type (industry averages)
        self.roi_benchmarks = {
            EnhancementCategory.PAINT: {
                'cost_per_sqm': 25,
                'value_add_multiplier': 2.5,
                'buyer_appeal': 0.3,
                'dom_reduction': 7
            },
            EnhancementCategory.KITCHEN: {
                'cost_per_sqm': 2500,
                'value_add_multiplier': 1.2,
                'buyer_appeal': 0.7,
                'dom_reduction': 15
            },
            EnhancementCategory.BATHROOM: {
                'cost_per_sqm': 1800,
                'value_add_multiplier': 1.3,
                'buyer_appeal': 0.6,
                'dom_reduction': 12
            },
            EnhancementCategory.FLOORING: {
                'cost_per_sqm': 180,
                'value_add_multiplier': 1.8,
                'buyer_appeal': 0.5,
                'dom_reduction': 10
            },
            EnhancementCategory.LANDSCAPE: {
                'cost_per_sqm': 120,
                'value_add_multiplier': 1.5,
                'buyer_appeal': 0.4,
                'dom_reduction': 8
            },
            EnhancementCategory.STAGING: {
                'cost_flat': 15000,
                'value_add_multiplier': 1.1,
                'buyer_appeal': 0.6,
                'dom_reduction': 20
            }
        }
        
        # Market preference weights by property type
        self.market_preferences = {
            'House': {
                EnhancementCategory.KITCHEN: 0.9,
                EnhancementCategory.BATHROOM: 0.8,
                EnhancementCategory.LANDSCAPE: 0.7,
                EnhancementCategory.PAINT: 0.8,
                EnhancementCategory.FLOORING: 0.7
            },
            'Unit': {
                EnhancementCategory.KITCHEN: 0.9,
                EnhancementCategory.BATHROOM: 0.8,
                EnhancementCategory.PAINT: 0.9,
                EnhancementCategory.FLOORING: 0.8,
                EnhancementCategory.STAGING: 0.7
            },
            'Townhouse': {
                EnhancementCategory.KITCHEN: 0.9,
                EnhancementCategory.BATHROOM: 0.8,
                EnhancementCategory.LANDSCAPE: 0.6,
                EnhancementCategory.PAINT: 0.8,
                EnhancementCategory.FLOORING: 0.7
            }
        }
    
    async def analyze_property_enhancements(
        self,
        property_data: Dict[str, Any],
        budget_limit: Optional[Decimal] = None,
        timeframe_weeks: Optional[int] = 12
    ) -> PropertyEnhancementPlan:
        """
        Analyze property enhancement opportunities with ROI optimization.
        
        Args:
            property_data: Property information dictionary
            budget_limit: Optional budget constraint
            timeframe_weeks: Available timeframe for improvements
            
        Returns:
            PropertyEnhancementPlan with prioritized recommendations
        """
        try:
            self.logger.info(f"Analyzing enhancements for property {property_data.get('id')}")
            
            # Assess current property condition
            condition_assessment = await self._assess_property_condition(property_data)
            
            # Analyze market preferences
            market_context = await self._analyze_market_preferences(
                property_data['suburb'], property_data['property_type']
            )
            
            # Generate enhancement recommendations
            all_recommendations = await self._generate_enhancement_recommendations(
                property_data, condition_assessment, market_context
            )
            
            # Filter and prioritize based on constraints
            filtered_recommendations = self._filter_recommendations(
                all_recommendations, budget_limit, timeframe_weeks
            )
            
            # Categorize by priority
            essential = [r for r in filtered_recommendations if r.priority == EnhancementPriority.ESSENTIAL]
            high_priority = [r for r in filtered_recommendations if r.priority == EnhancementPriority.HIGH]
            optional = [r for r in filtered_recommendations if r.priority in [EnhancementPriority.MEDIUM, EnhancementPriority.LOW]]
            
            # Calculate financial summary
            financial_summary = self._calculate_financial_summary(filtered_recommendations)
            
            # Generate implementation strategy
            implementation_strategy = self._generate_implementation_strategy(
                filtered_recommendations, timeframe_weeks
            )
            
            # Create budget scenarios
            budget_scenarios = self._create_budget_scenarios(
                all_recommendations, property_data.get('estimated_price', 1000000)
            )
            
            # Build comprehensive plan
            plan = PropertyEnhancementPlan(
                property_id=property_data.get('id', 'unknown'),
                analysis_date=datetime.utcnow(),
                current_estimated_value=Decimal(str(property_data.get('estimated_price', 1000000))),
                essential_improvements=essential,
                high_priority_improvements=high_priority,
                optional_improvements=optional,
                total_investment_required=financial_summary['total_cost'],
                total_expected_return=financial_summary['total_return'],
                overall_roi=financial_summary['overall_roi'],
                net_benefit=financial_summary['net_benefit'],
                recommended_sequence=implementation_strategy['sequence'],
                total_timeframe_weeks=implementation_strategy['total_weeks'],
                budget_scenarios=budget_scenarios,
                market_priorities=market_context['top_priorities'],
                buyer_preferences=market_context['preferences'],
                competitive_advantages=self._identify_competitive_advantages(filtered_recommendations),
                market_risks=market_context['risks'],
                implementation_risks=self._identify_implementation_risks(filtered_recommendations),
                methodology_notes=self._generate_methodology_notes()
            )
            
            self.logger.info(
                f"Enhancement analysis completed: {len(filtered_recommendations)} recommendations, "
                f"${financial_summary['total_cost']:,.0f} investment, "
                f"{financial_summary['overall_roi']:.1f}% ROI"
            )
            
            return plan
            
        except Exception as e:
            self.logger.error(f"Property enhancement analysis failed: {str(e)}")
            raise
    
    async def _assess_property_condition(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess current property condition and identify improvement needs."""
        
        assessment = {
            'overall_condition': 'Good',  # Good, Fair, Poor
            'condition_score': 0.7,      # 0-1 scale
            'issues_identified': [],
            'strengths': [],
            'improvement_needs': {}
        }
        
        # Analyze property age and description for condition indicators
        description = str(property_data.get('description', '')).lower()
        year_built = property_data.get('year_built')
        
        # Age-based condition assessment
        if year_built:
            current_year = datetime.utcnow().year
            age = current_year - year_built
            
            if age > 40:
                assessment['condition_score'] *= 0.8
                assessment['issues_identified'].append("Property age suggests potential renovation needs")
            elif age > 20:
                assessment['condition_score'] *= 0.9
        
        # Description-based condition indicators
        positive_indicators = [
            'renovated', 'updated', 'modern', 'new', 'fresh', 'contemporary',
            'stylish', 'designer', 'quality', 'premium'
        ]
        
        negative_indicators = [
            'original', 'dated', 'needs work', 'potential', 'fixer', 'opportunity',
            'renovation required', 'tired', 'worn'
        ]
        
        positive_count = sum(1 for indicator in positive_indicators if indicator in description)
        negative_count = sum(1 for indicator in negative_indicators if indicator in description)
        
        if positive_count > negative_count:
            assessment['condition_score'] = min(1.0, assessment['condition_score'] + 0.1)
            assessment['strengths'].append("Property appears well-maintained")
        elif negative_count > positive_count:
            assessment['condition_score'] = max(0.3, assessment['condition_score'] - 0.2)
            assessment['issues_identified'].append("Property shows signs of requiring updates")
        
        # Identify specific improvement needs based on condition
        if assessment['condition_score'] < 0.6:
            assessment['improvement_needs']['structural'] = True
            assessment['improvement_needs']['cosmetic'] = True
        elif assessment['condition_score'] < 0.8:
            assessment['improvement_needs']['cosmetic'] = True
        
        # Always consider staging for properties under $2M
        if property_data.get('estimated_price', 0) < 2000000:
            assessment['improvement_needs']['staging'] = True
        
        return assessment
    
    async def _analyze_market_preferences(self, suburb: str, property_type: str) -> Dict[str, Any]:
        """Analyze market preferences and buyer priorities in the area."""
        
        context = {
            'preferences': {},
            'top_priorities': [],
            'risks': [],
            'buyer_profile': 'General'
        }
        
        # Get market preferences for property type
        type_preferences = self.market_preferences.get(property_type, self.market_preferences['House'])
        context['preferences'] = type_preferences
        
        # Identify top priorities
        sorted_preferences = sorted(type_preferences.items(), key=lambda x: x[1], reverse=True)
        context['top_priorities'] = [category.value for category, _ in sorted_preferences[:3]]
        
        # Analyze suburb characteristics for buyer profile
        async with get_db_session() as session:
            suburb_stats = session.query(SuburbStats).filter(
                SuburbStats.suburb_name == suburb
            ).order_by(SuburbStats.stats_date.desc()).first()
            
            if suburb_stats:
                median_price = float(suburb_stats.house_median_price) if suburb_stats.house_median_price else 1000000
                
                if median_price > 3000000:
                    context['buyer_profile'] = 'Luxury'
                    context['top_priorities'].extend(['Quality finishes', 'Unique features'])
                elif median_price > 1500000:
                    context['buyer_profile'] = 'Premium'
                    context['top_priorities'].extend(['Modern amenities', 'Quality presentation'])
                else:
                    context['buyer_profile'] = 'Value-conscious'
                    context['top_priorities'].extend(['Value improvements', 'Move-in ready'])
        
        # Market-specific risks
        if context['buyer_profile'] == 'Luxury':
            context['risks'].append("Luxury buyers have high expectations for quality")
        elif context['buyer_profile'] == 'Value-conscious':
            context['risks'].append("Budget-conscious buyers sensitive to over-improvement")
        
        return context
    
    async def _generate_enhancement_recommendations(
        self,
        property_data: Dict[str, Any],
        condition_assessment: Dict[str, Any],
        market_context: Dict[str, Any]
    ) -> List[EnhancementRecommendation]:
        """Generate comprehensive enhancement recommendations."""
        
        recommendations = []
        property_value = property_data.get('estimated_price', 1000000)
        building_size = property_data.get('building_size', 150)  # Default 150 sqm
        
        # Paint and cosmetic improvements
        if condition_assessment['condition_score'] < 0.8:
            paint_rec = self._create_paint_recommendation(building_size, property_value, market_context)
            recommendations.append(paint_rec)
        
        # Kitchen renovation
        kitchen_rec = self._create_kitchen_recommendation(property_data, property_value, market_context)
        recommendations.append(kitchen_rec)
        
        # Bathroom renovation
        bathroom_rec = self._create_bathroom_recommendation(property_data, property_value, market_context)
        recommendations.append(bathroom_rec)
        
        # Flooring upgrades
        if 'carpet' in str(property_data.get('description', '')).lower():
            flooring_rec = self._create_flooring_recommendation(building_size, property_value, market_context)
            recommendations.append(flooring_rec)
        
        # Landscaping (for houses and townhouses)
        if property_data.get('property_type') in ['House', 'Townhouse']:
            landscape_rec = self._create_landscaping_recommendation(property_data, property_value, market_context)
            recommendations.append(landscape_rec)
        
        # Property staging
        staging_rec = self._create_staging_recommendation(property_data, property_value, market_context)
        recommendations.append(staging_rec)
        
        return recommendations
    
    def _create_paint_recommendation(
        self,
        building_size: int,
        property_value: float,
        market_context: Dict[str, Any]
    ) -> EnhancementRecommendation:
        """Create paint and cosmetic improvement recommendation."""
        
        benchmark = self.roi_benchmarks[EnhancementCategory.PAINT]
        
        # Calculate costs and returns
        estimated_cost = building_size * benchmark['cost_per_sqm']
        expected_return = estimated_cost * benchmark['value_add_multiplier']
        roi = ((expected_return - estimated_cost) / estimated_cost) * 100
        
        return EnhancementRecommendation(
            category=EnhancementCategory.PAINT,
            title="Interior and Exterior Paint Refresh",
            description="Fresh neutral paint throughout to modernize appearance and create move-in ready appeal",
            priority=EnhancementPriority.HIGH,
            estimated_cost=Decimal(str(round(estimated_cost, 2))),
            expected_value_add=Decimal(str(round(expected_return, 2))),
            roi_percentage=roi,
            payback_period_months=0,  # Immediate return on sale
            buyer_appeal_increase=benchmark['buyer_appeal'],
            days_on_market_reduction=benchmark['dom_reduction'],
            sale_probability_increase=0.1,
            timeframe_weeks=2,
            difficulty_level="Easy",
            required_permits=False,
            recommended_professionals=["Professional painters", "Color consultant"],
            risks=["Color choice may not appeal to all buyers"],
            market_dependence="Low",
            supporting_data={
                'benchmark_roi': f"{roi:.1f}%",
                'market_appeal': 'High across all buyer segments'
            }
        )
    
    def _create_kitchen_recommendation(
        self,
        property_data: Dict[str, Any],
        property_value: float,
        market_context: Dict[str, Any]
    ) -> EnhancementRecommendation:
        """Create kitchen renovation recommendation."""
        
        benchmark = self.roi_benchmarks[EnhancementCategory.KITCHEN]
        
        # Kitchen size estimation
        kitchen_size = 20  # Average kitchen size in sqm
        if property_value > 2000000:
            kitchen_size = 25  # Larger kitchens in premium properties
        
        # Calculate costs based on renovation level
        renovation_level = "Mid-range"  # Budget, Mid-range, Premium
        if property_value > 3000000:
            renovation_level = "Premium"
        elif property_value < 1000000:
            renovation_level = "Budget"
        
        cost_multipliers = {"Budget": 0.7, "Mid-range": 1.0, "Premium": 1.5}
        estimated_cost = kitchen_size * benchmark['cost_per_sqm'] * cost_multipliers[renovation_level]
        
        # ROI varies by property value segment
        if property_value > 2000000:
            roi_multiplier = 1.3  # Higher ROI in premium market
        else:
            roi_multiplier = 1.0
        
        expected_return = estimated_cost * benchmark['value_add_multiplier'] * roi_multiplier
        roi = ((expected_return - estimated_cost) / estimated_cost) * 100
        
        # Priority based on current condition and market preferences
        priority = EnhancementPriority.HIGH
        if 'kitchen' in str(property_data.get('description', '')).lower():
            if any(word in str(property_data.get('description', '')).lower() 
                   for word in ['new kitchen', 'renovated kitchen', 'modern kitchen']):
                priority = EnhancementPriority.LOW
        
        return EnhancementRecommendation(
            category=EnhancementCategory.KITCHEN,
            title=f"{renovation_level} Kitchen Renovation",
            description=f"Complete kitchen renovation with {renovation_level.lower()} finishes, modern appliances, and improved functionality",
            priority=priority,
            estimated_cost=Decimal(str(round(estimated_cost, 2))),
            expected_value_add=Decimal(str(round(expected_return, 2))),
            roi_percentage=roi,
            payback_period_months=0,
            buyer_appeal_increase=benchmark['buyer_appeal'],
            days_on_market_reduction=benchmark['dom_reduction'],
            sale_probability_increase=0.15,
            timeframe_weeks=8,
            difficulty_level="Complex",
            required_permits=True,
            recommended_professionals=["Kitchen designer", "Licensed builder", "Plumber", "Electrician"],
            risks=[
                "High upfront investment",
                "Potential construction delays",
                "Design choices may not appeal to all buyers"
            ],
            market_dependence="Medium",
            supporting_data={
                'renovation_level': renovation_level,
                'market_preference_score': market_context['preferences'].get(EnhancementCategory.KITCHEN, 0.8)
            }
        )
    
    def _create_bathroom_recommendation(
        self,
        property_data: Dict[str, Any],
        property_value: float,
        market_context: Dict[str, Any]
    ) -> EnhancementRecommendation:
        """Create bathroom renovation recommendation."""
        
        benchmark = self.roi_benchmarks[EnhancementCategory.BATHROOM]
        
        # Estimate number and size of bathrooms
        bedrooms = property_data.get('bedrooms', 3)
        num_bathrooms = min(bedrooms, 3)  # Typical ratio
        avg_bathroom_size = 8  # sqm
        
        total_bathroom_area = num_bathrooms * avg_bathroom_size
        estimated_cost = total_bathroom_area * benchmark['cost_per_sqm']
        
        # Adjust cost based on property value
        if property_value > 2000000:
            estimated_cost *= 1.4  # Premium finishes
        elif property_value < 800000:
            estimated_cost *= 0.8  # Budget renovation
        
        expected_return = estimated_cost * benchmark['value_add_multiplier']
        roi = ((expected_return - estimated_cost) / estimated_cost) * 100
        
        return EnhancementRecommendation(
            category=EnhancementCategory.BATHROOM,
            title="Bathroom Renovation",
            description=f"Renovation of {num_bathrooms} bathroom(s) with modern fixtures, quality finishes, and improved functionality",
            priority=EnhancementPriority.HIGH,
            estimated_cost=Decimal(str(round(estimated_cost, 2))),
            expected_value_add=Decimal(str(round(expected_return, 2))),
            roi_percentage=roi,
            payback_period_months=0,
            buyer_appeal_increase=benchmark['buyer_appeal'],
            days_on_market_reduction=benchmark['dom_reduction'],
            sale_probability_increase=0.12,
            timeframe_weeks=6,
            difficulty_level="Moderate",
            required_permits=True,
            recommended_professionals=["Bathroom designer", "Licensed builder", "Plumber", "Tiler"],
            risks=[
                "Waterproofing compliance requirements",
                "Potential structural issues discovery"
            ],
            market_dependence="Medium",
            supporting_data={
                'num_bathrooms': num_bathrooms,
                'total_area': total_bathroom_area
            }
        )
    
    def _create_flooring_recommendation(
        self,
        building_size: int,
        property_value: float,
        market_context: Dict[str, Any]
    ) -> EnhancementRecommendation:
        """Create flooring upgrade recommendation."""
        
        benchmark = self.roi_benchmarks[EnhancementCategory.FLOORING]
        
        # Estimate flooring area (typically 70% of building size)
        flooring_area = building_size * 0.7
        
        # Choose flooring type based on property value
        if property_value > 2000000:
            flooring_type = "Premium engineered hardwood"
            cost_multiplier = 1.5
        elif property_value > 1000000:
            flooring_type = "Quality hybrid flooring"
            cost_multiplier = 1.0
        else:
            flooring_type = "Laminate flooring"
            cost_multiplier = 0.7
        
        estimated_cost = flooring_area * benchmark['cost_per_sqm'] * cost_multiplier
        expected_return = estimated_cost * benchmark['value_add_multiplier']
        roi = ((expected_return - estimated_cost) / estimated_cost) * 100
        
        return EnhancementRecommendation(
            category=EnhancementCategory.FLOORING,
            title=f"{flooring_type} Installation",
            description=f"Replace existing flooring with {flooring_type.lower()} throughout main living areas",
            priority=EnhancementPriority.MEDIUM,
            estimated_cost=Decimal(str(round(estimated_cost, 2))),
            expected_value_add=Decimal(str(round(expected_return, 2))),
            roi_percentage=roi,
            payback_period_months=0,
            buyer_appeal_increase=benchmark['buyer_appeal'],
            days_on_market_reduction=benchmark['dom_reduction'],
            sale_probability_increase=0.08,
            timeframe_weeks=3,
            difficulty_level="Moderate",
            required_permits=False,
            recommended_professionals=["Flooring specialist", "Carpenter"],
            risks=["Dust and noise during installation"],
            market_dependence="Low",
            supporting_data={
                'flooring_type': flooring_type,
                'area_coverage': flooring_area
            }
        )
    
    def _create_landscaping_recommendation(
        self,
        property_data: Dict[str, Any],
        property_value: float,
        market_context: Dict[str, Any]
    ) -> EnhancementRecommendation:
        """Create landscaping improvement recommendation."""
        
        benchmark = self.roi_benchmarks[EnhancementCategory.LANDSCAPE]
        
        # Estimate garden area
        land_size = property_data.get('land_size', 400)  # Default 400 sqm
        garden_area = land_size * 0.6  # Assume 60% is garden
        
        estimated_cost = garden_area * benchmark['cost_per_sqm']
        expected_return = estimated_cost * benchmark['value_add_multiplier']
        roi = ((expected_return - estimated_cost) / estimated_cost) * 100
        
        return EnhancementRecommendation(
            category=EnhancementCategory.LANDSCAPE,
            title="Garden and Landscaping Enhancement",
            description="Professional landscaping with low-maintenance plants, improved lawn, and enhanced outdoor entertainment areas",
            priority=EnhancementPriority.MEDIUM,
            estimated_cost=Decimal(str(round(estimated_cost, 2))),
            expected_value_add=Decimal(str(round(expected_return, 2))),
            roi_percentage=roi,
            payback_period_months=0,
            buyer_appeal_increase=benchmark['buyer_appeal'],
            days_on_market_reduction=benchmark['dom_reduction'],
            sale_probability_increase=0.05,
            timeframe_weeks=4,
            difficulty_level="Easy",
            required_permits=False,
            recommended_professionals=["Landscape designer", "Gardener"],
            risks=["Seasonal planting considerations", "Maintenance requirements"],
            market_dependence="Medium",
            supporting_data={
                'garden_area': garden_area,
                'land_size': land_size
            }
        )
    
    def _create_staging_recommendation(
        self,
        property_data: Dict[str, Any],
        property_value: float,
        market_context: Dict[str, Any]
    ) -> EnhancementRecommendation:
        """Create property staging recommendation."""
        
        benchmark = self.roi_benchmarks[EnhancementCategory.STAGING]
        
        # Staging cost based on property value
        if property_value > 2000000:
            estimated_cost = benchmark['cost_flat'] * 1.5
            staging_level = "Premium staging"
        elif property_value > 1000000:
            estimated_cost = benchmark['cost_flat']
            staging_level = "Professional staging"
        else:
            estimated_cost = benchmark['cost_flat'] * 0.7
            staging_level = "Basic staging"
        
        # ROI calculation
        expected_return = property_value * 0.05  # Typical 5% price improvement
        roi = ((expected_return - estimated_cost) / estimated_cost) * 100
        
        return EnhancementRecommendation(
            category=EnhancementCategory.STAGING,
            title=f"{staging_level}",
            description="Professional furniture and styling to showcase the property's potential and create emotional buyer connection",
            priority=EnhancementPriority.HIGH,
            estimated_cost=Decimal(str(round(estimated_cost, 2))),
            expected_value_add=Decimal(str(round(expected_return, 2))),
            roi_percentage=roi,
            payback_period_months=0,
            buyer_appeal_increase=benchmark['buyer_appeal'],
            days_on_market_reduction=benchmark['dom_reduction'],
            sale_probability_increase=0.2,
            timeframe_weeks=1,
            difficulty_level="Easy",
            required_permits=False,
            recommended_professionals=["Property stylist", "Staging company"],
            risks=["Additional monthly costs if sale extends"],
            market_dependence="Low",
            supporting_data={
                'staging_level': staging_level,
                'typical_duration': '2-3 months'
            }
        )
    
    def _filter_recommendations(
        self,
        recommendations: List[EnhancementRecommendation],
        budget_limit: Optional[Decimal],
        timeframe_weeks: Optional[int]
    ) -> List[EnhancementRecommendation]:
        """Filter recommendations based on budget and timeframe constraints."""
        
        filtered = recommendations.copy()
        
        # Filter by budget if specified
        if budget_limit:
            filtered = [r for r in filtered if r.estimated_cost <= budget_limit]
        
        # Filter by timeframe if specified
        if timeframe_weeks:
            filtered = [r for r in filtered if r.timeframe_weeks <= timeframe_weeks]
        
        # Sort by ROI within priority levels
        def sort_key(rec):
            priority_order = {
                EnhancementPriority.ESSENTIAL: 0,
                EnhancementPriority.HIGH: 1,
                EnhancementPriority.MEDIUM: 2,
                EnhancementPriority.LOW: 3,
                EnhancementPriority.OPTIONAL: 4
            }
            return (priority_order[rec.priority], -rec.roi_percentage)
        
        filtered.sort(key=sort_key)
        
        return filtered
    
    def _calculate_financial_summary(
        self,
        recommendations: List[EnhancementRecommendation]
    ) -> Dict[str, Any]:
        """Calculate overall financial impact of recommendations."""
        
        total_cost = sum(float(r.estimated_cost) for r in recommendations)
        total_return = sum(float(r.expected_value_add) for r in recommendations)
        
        overall_roi = ((total_return - total_cost) / total_cost * 100) if total_cost > 0 else 0
        net_benefit = total_return - total_cost
        
        return {
            'total_cost': Decimal(str(round(total_cost, 2))),
            'total_return': Decimal(str(round(total_return, 2))),
            'overall_roi': overall_roi,
            'net_benefit': Decimal(str(round(net_benefit, 2)))
        }
    
    def _generate_implementation_strategy(
        self,
        recommendations: List[EnhancementRecommendation],
        timeframe_weeks: Optional[int]
    ) -> Dict[str, Any]:
        """Generate optimal implementation sequence and timeline."""
        
        # Sort by priority and dependencies
        essential = [r for r in recommendations if r.priority == EnhancementPriority.ESSENTIAL]
        high_priority = [r for r in recommendations if r.priority == EnhancementPriority.HIGH]
        others = [r for r in recommendations if r.priority not in [EnhancementPriority.ESSENTIAL, EnhancementPriority.HIGH]]
        
        # Create implementation sequence
        sequence = []
        
        # Phase 1: Essential structural work
        structural = [r for r in essential if r.required_permits or r.difficulty_level == "Complex"]
        if structural:
            sequence.append("Phase 1: Structural and permit-required work")
            sequence.extend([r.title for r in structural])
        
        # Phase 2: Major renovations
        major = [r for r in high_priority if r.category in [EnhancementCategory.KITCHEN, EnhancementCategory.BATHROOM]]
        if major:
            sequence.append("Phase 2: Kitchen and bathroom renovations")
            sequence.extend([r.title for r in major])
        
        # Phase 3: Cosmetic improvements
        cosmetic = [r for r in recommendations if r.category in [EnhancementCategory.PAINT, EnhancementCategory.FLOORING]]
        if cosmetic:
            sequence.append("Phase 3: Cosmetic improvements")
            sequence.extend([r.title for r in cosmetic])
        
        # Phase 4: Final touches
        final = [r for r in recommendations if r.category in [EnhancementCategory.LANDSCAPE, EnhancementCategory.STAGING]]
        if final:
            sequence.append("Phase 4: Landscaping and staging")
            sequence.extend([r.title for r in final])
        
        # Calculate total timeframe
        total_weeks = sum(r.timeframe_weeks for r in recommendations)
        
        # Account for parallel work where possible
        if len(recommendations) > 1:
            total_weeks = int(total_weeks * 0.8)  # 20% time savings from parallel work
        
        return {
            'sequence': sequence,
            'total_weeks': min(total_weeks, timeframe_weeks) if timeframe_weeks else total_weeks
        }
    
    def _create_budget_scenarios(
        self,
        all_recommendations: List[EnhancementRecommendation],
        property_value: float
    ) -> Dict[str, Dict[str, Any]]:
        """Create different budget scenarios with expected outcomes."""
        
        scenarios = {}
        
        # Essential only scenario
        essential = [r for r in all_recommendations if r.priority == EnhancementPriority.ESSENTIAL]
        scenarios['Essential Only'] = {
            'budget': sum(float(r.estimated_cost) for r in essential),
            'expected_return': sum(float(r.expected_value_add) for r in essential),
            'recommendations': [r.title for r in essential]
        }
        
        # High priority scenario
        high_priority = [r for r in all_recommendations if r.priority in [EnhancementPriority.ESSENTIAL, EnhancementPriority.HIGH]]
        scenarios['High Priority'] = {
            'budget': sum(float(r.estimated_cost) for r in high_priority),
            'expected_return': sum(float(r.expected_value_add) for r in high_priority),
            'recommendations': [r.title for r in high_priority]
        }
        
        # Comprehensive scenario
        scenarios['Comprehensive'] = {
            'budget': sum(float(r.estimated_cost) for r in all_recommendations),
            'expected_return': sum(float(r.expected_value_add) for r in all_recommendations),
            'recommendations': [r.title for r in all_recommendations]
        }
        
        return scenarios
    
    def _identify_competitive_advantages(
        self,
        recommendations: List[EnhancementRecommendation]
    ) -> List[str]:
        """Identify competitive advantages from recommended improvements."""
        
        advantages = []
        
        categories = {r.category for r in recommendations}
        
        if EnhancementCategory.STAGING in categories:
            advantages.append("Professional presentation creates strong first impression")
        
        if EnhancementCategory.KITCHEN in categories:
            advantages.append("Modern kitchen appeals to majority of buyers")
        
        if EnhancementCategory.PAINT in categories:
            advantages.append("Fresh, move-in ready appearance")
        
        if len(categories) >= 3:
            advantages.append("Comprehensive renovation reduces buyer concerns")
        
        return advantages
    
    def _identify_implementation_risks(
        self,
        recommendations: List[EnhancementRecommendation]
    ) -> List[str]:
        """Identify implementation risks across all recommendations."""
        
        risks = []
        
        # Budget risks
        total_cost = sum(float(r.estimated_cost) for r in recommendations)
        if total_cost > 100000:
            risks.append("High investment amount may require careful project management")
        
        # Timeline risks
        complex_projects = [r for r in recommendations if r.difficulty_level == "Complex"]
        if complex_projects:
            risks.append("Complex renovations may experience delays")
        
        # Permit risks
        permit_projects = [r for r in recommendations if r.required_permits]
        if permit_projects:
            risks.append("Permit approvals may delay project commencement")
        
        # Market risks
        risks.append("Market conditions may change during improvement period")
        
        return risks
    
    def _generate_methodology_notes(self) -> str:
        """Generate methodology explanation."""
        
        return (
            "Property enhancement analysis based on current condition assessment, "
            "market preference analysis, and ROI benchmarking using industry data. "
            "Recommendations prioritized by expected return on investment, buyer appeal "
            "impact, and market timing considerations. Cost estimates include materials, "
            "labor, and professional fees based on current Sydney market rates. "
            "ROI calculations assume improvements completed before sale with immediate "
            "market realization of value improvements."
        )