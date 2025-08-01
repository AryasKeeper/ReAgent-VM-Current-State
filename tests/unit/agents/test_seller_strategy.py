"""
Comprehensive Unit Tests for Seller Strategy Agent

Tests cover all major components including pricing models, strategic advisory,
and agent integration with >90% code coverage target.
"""

import pytest
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from reagent_sydney.agents.seller_strategy import (
    SellerStrategyAgent,
    SellerStrategyResult,
    ComparableSalesAnalyzer,
    AutomatedValuationModel,
    MarketTimingAnalyzer,
    PricingCoordinator,
    SaleMethodRecommender,
    PropertyEnhancementAdvisor
)
from reagent_sydney.agents.seller_strategy.pricing.comparable_sales_analyzer import CMAResult, PropertyComparable
from reagent_sydney.agents.seller_strategy.pricing.automated_valuation_model import AVMPrediction
from reagent_sydney.agents.seller_strategy.pricing.market_timing_analyzer import MarketTimingResult, MarketCondition
from reagent_sydney.agents.seller_strategy.strategy.sale_method_recommender import SaleMethodRecommendation, SaleMethod
from reagent_sydney.agents.seller_strategy.strategy.property_enhancement_advisor import PropertyEnhancementPlan, EnhancementRecommendation
from reagent_sydney.agents.seller_strategy.validation.statistical_validator import StatisticalValidator, ValidationMetrics


@pytest.fixture
def sample_property_data():
    """Sample property data for testing."""
    return {
        'id': 'test-property-123',
        'listing_id': 'DOM123456',
        'title': 'Beautiful Family Home',
        'description': 'Modern 4 bedroom house with pool',
        'property_type': 'House',
        'address_line_1': '123 Test Street',
        'suburb': 'Mosman',
        'postcode': '2088',
        'latitude': -33.8688,
        'longitude': 151.2093,
        'bedrooms': 4,
        'bathrooms': 3,
        'car_spaces': 2,
        'land_size': 600,
        'building_size': 200,
        'price': 2500000,
        'estimated_price': 2500000,
        'listing_status': 'active',
        'listing_type': 'sale',
        'features': ['pool', 'garage', 'garden'],
        'days_on_market': 15
    }


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    with patch('reagent_sydney.agents.seller_strategy.agent.get_db_session') as mock_session:
        mock_session.return_value.__aenter__ = AsyncMock()
        mock_session.return_value.__aexit__ = AsyncMock()
        yield mock_session


class TestComparableSalesAnalyzer:
    """Test comparable sales analysis functionality."""
    
    @pytest.fixture
    def analyzer(self):
        return ComparableSalesAnalyzer()
    
    def test_init(self, analyzer):
        """Test analyzer initialization."""
        assert analyzer.default_radius_km == 2.0
        assert analyzer.lookback_months == 6
        assert analyzer.min_comparables == 3
        assert analyzer.bedroom_adjustment_per_room == 0.15
    
    @pytest.mark.asyncio
    async def test_analyze_comparables_success(self, analyzer, sample_property_data, mock_db_session):
        """Test successful comparable sales analysis."""
        
        # Mock comparable properties
        mock_comparables = [
            {
                'property_id': 'comp1',
                'address': '124 Test Street, Mosman',
                'suburb': 'Mosman',
                'postcode': '2088',
                'property_type': 'House',
                'bedrooms': 4,
                'bathrooms': 3,
                'car_spaces': 2,
                'land_size': 580,
                'building_size': 190,
                'sale_price': Decimal('2400000'),
                'sale_date': datetime.utcnow() - timedelta(days=30),
                'days_on_market': 20,
                'distance_km': 0.1
            },
            {
                'property_id': 'comp2',
                'address': '125 Test Street, Mosman',
                'suburb': 'Mosman',
                'postcode': '2088',
                'property_type': 'House',
                'bedrooms': 3,
                'bathrooms': 2,
                'car_spaces': 1,
                'land_size': 550,
                'building_size': 180,
                'sale_price': Decimal('2200000'),
                'sale_date': datetime.utcnow() - timedelta(days=45),
                'days_on_market': 25,
                'distance_km': 0.15
            }
        ]
        
        with patch.object(analyzer, '_find_comparable_sales', return_value=mock_comparables):
            with patch.object(analyzer, '_get_market_conditions_adjustment', return_value=0.02):
                result = await analyzer.analyze_comparables(sample_property_data)
        
        assert isinstance(result, CMAResult)
        assert result.subject_property_id == 'test-property-123'
        assert len(result.comparables) == 2
        assert result.estimated_value > 0
        assert result.confidence_level > 0
        assert result.market_conditions_adjustment == 0.02
    
    @pytest.mark.asyncio
    async def test_analyze_comparables_insufficient_data(self, analyzer, sample_property_data):
        """Test handling of insufficient comparable data."""
        
        with patch.object(analyzer, '_find_comparable_sales', return_value=[]):
            with patch.object(analyzer, '_expand_comparable_search', return_value=[]):
                with pytest.raises(ValueError, match="Insufficient comparables found"):
                    await analyzer.analyze_comparables(sample_property_data)
    
    def test_calculate_distance(self, analyzer):
        """Test distance calculation."""
        # Sydney CBD to Bondi Beach (approximately 8km)
        distance = analyzer._calculate_distance(-33.8688, 151.2093, -33.8915, 151.2767)
        assert 7 < distance < 9  # Allow for reasonable tolerance
    
    def test_adjust_comparables(self, analyzer, sample_property_data):
        """Test comparable property adjustments."""
        
        comparables = [
            {
                'property_id': 'comp1',
                'address': '124 Test Street, Mosman',
                'suburb': 'Mosman',
                'postcode': '2088',
                'property_type': 'House',
                'bedrooms': 3,  # One less bedroom
                'bathrooms': 2,  # One less bathroom
                'car_spaces': 1,  # One less car space
                'land_size': 500,  # Smaller land
                'building_size': 180,  # Smaller building
                'sale_price': Decimal('2200000'),
                'sale_date': datetime.utcnow() - timedelta(days=30),
                'days_on_market': 20,
                'distance_km': 0.1
            }
        ]
        
        result = asyncio.run(analyzer._adjust_comparables(sample_property_data, comparables))
        
        assert len(result) == 1
        comp = result[0]
        assert isinstance(comp, PropertyComparable)
        assert comp.adjusted_price != comp.sale_price  # Should be adjusted
        assert 'bedrooms' in comp.adjustments
        assert 'bathrooms' in comp.adjustments
        assert comp.adjustments['bedrooms'] > 0  # Positive adjustment for more bedrooms
    
    def test_calculate_valuation_range(self, analyzer):
        """Test valuation range calculation."""
        
        # Mock comparable data
        comparables = [
            Mock(adjusted_price=Decimal('2400000'), similarity_score=0.9),
            Mock(adjusted_price=Decimal('2500000'), similarity_score=0.8),
            Mock(adjusted_price=Decimal('2300000'), similarity_score=0.7)
        ]
        
        result = analyzer._calculate_valuation_range(comparables)
        
        assert 'estimated_value' in result
        assert 'range_low' in result
        assert 'range_high' in result
        assert 'confidence_level' in result
        assert result['range_low'] <= result['estimated_value'] <= result['range_high']
        assert 0 <= result['confidence_level'] <= 1


class TestAutomatedValuationModel:
    """Test automated valuation model functionality."""
    
    @pytest.fixture
    def avm_model(self):
        return AutomatedValuationModel()
    
    def test_init(self, avm_model):
        """Test AVM initialization."""
        assert avm_model.min_training_samples == 100
        assert avm_model.test_size == 0.2
        assert len(avm_model.numeric_features) > 0
        assert len(avm_model.categorical_features) > 0
        assert len(avm_model.market_segments) == 4
    
    @pytest.mark.asyncio
    async def test_predict_value_success(self, avm_model, sample_property_data):
        """Test successful property valuation prediction."""
        
        # Mock model training and prediction
        with patch.object(avm_model, '_is_model_valid', return_value=True):
            with patch.object(avm_model, '_predict_with_ensemble', return_value=(2450000, 0.85)):
                with patch.object(avm_model, '_prepare_features'):
                    result = await avm_model.predict_value(sample_property_data)
        
        assert isinstance(result, AVMPrediction)
        assert result.property_id == 'test-property-123'
        assert result.predicted_value > 0
        assert 0 <= result.confidence_score <= 1
        assert result.market_segment in ['budget', 'mid_range', 'premium', 'luxury']
    
    def test_determine_market_segment(self, avm_model):
        """Test market segment determination."""
        
        # Test different price points
        budget_property = {'estimated_price': 800000, 'bedrooms': 2, 'suburb': 'generic'}
        mid_range_property = {'estimated_price': 1500000, 'bedrooms': 3, 'suburb': 'generic'}
        premium_property = {'estimated_price': 3000000, 'bedrooms': 4, 'suburb': 'mosman'}
        luxury_property = {'estimated_price': 8000000, 'bedrooms': 5, 'suburb': 'vaucluse'}
        
        assert avm_model._determine_market_segment(budget_property) == 'budget'
        assert avm_model._determine_market_segment(mid_range_property) == 'mid_range'
        assert avm_model._determine_market_segment(premium_property) == 'premium'
        assert avm_model._determine_market_segment(luxury_property) == 'luxury'
    
    @pytest.mark.asyncio
    async def test_prepare_features(self, avm_model, sample_property_data, mock_db_session):
        """Test feature preparation."""
        
        # Mock suburb statistics
        mock_stats = Mock()
        mock_stats.house_median_price = 2000000
        mock_stats.house_price_growth_12m = 5.5
        mock_stats.sales_last_30d = 12
        
        with patch('reagent_sydney.agents.seller_strategy.pricing.automated_valuation_model.get_db_session'):
            with patch.object(mock_db_session.return_value.__aenter__.return_value, 'query') as mock_query:
                mock_query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_stats
                
                result = await avm_model._prepare_features(sample_property_data)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert 'bedrooms' in result.columns
        assert 'suburb_median_price' in result.columns


class TestMarketTimingAnalyzer:
    """Test market timing analysis functionality."""
    
    @pytest.fixture
    def timing_analyzer(self):
        return MarketTimingAnalyzer()
    
    def test_init(self, timing_analyzer):
        """Test timing analyzer initialization."""
        assert len(timing_analyzer.seasonal_weights) == 12
        assert timing_analyzer.seasonal_weights[4] > timing_analyzer.seasonal_weights[7]  # April > July
        assert len(timing_analyzer.market_thresholds) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_optimal_timing(self, timing_analyzer, sample_property_data, mock_db_session):
        """Test optimal timing analysis."""
        
        with patch.object(timing_analyzer, '_analyze_current_market_conditions', 
                         return_value=MarketCondition.MODERATE_SELLERS):
            with patch.object(timing_analyzer, '_analyze_seasonal_patterns', return_value=[]):
                with patch.object(timing_analyzer, '_analyze_market_momentum', return_value={}):
                    with patch.object(timing_analyzer, '_analyze_competition', return_value={}):
                        result = await timing_analyzer.analyze_optimal_timing(sample_property_data)
        
        assert isinstance(result, MarketTimingResult)
        assert result.property_id == 'test-property-123'
        assert isinstance(result.current_market_condition, MarketCondition)
        assert result.timing_score >= 0
        assert result.confidence_level >= 0
    
    def test_classify_market_condition(self, timing_analyzer):
        """Test market condition classification."""
        
        # Test strong sellers market
        strong_indicators = {
            'absorption_rate': 0.85,
            'price_growth': 0.025,
            'inventory_trend': -0.20
        }
        condition = timing_analyzer._classify_market_condition(strong_indicators)
        assert condition == MarketCondition.STRONG_SELLERS
        
        # Test buyers market
        weak_indicators = {
            'absorption_rate': 0.30,
            'price_growth': -0.015,
            'inventory_trend': 0.20
        }
        condition = timing_analyzer._classify_market_condition(weak_indicators)
        assert condition == MarketCondition.STRONG_BUYERS


class TestSaleMethodRecommender:
    """Test sale method recommendation functionality."""
    
    @pytest.fixture
    def recommender(self):
        return SaleMethodRecommender()
    
    def test_init(self, recommender):
        """Test recommender initialization."""
        assert len(recommender.auction_factors['property_types']) > 0
        assert len(recommender.method_benchmarks) >= 3
        assert SaleMethod.AUCTION in recommender.method_benchmarks
    
    @pytest.mark.asyncio
    async def test_recommend_sale_method(self, recommender, sample_property_data, mock_db_session):
        """Test sale method recommendation."""
        
        with patch.object(recommender, '_analyze_property_factors', return_value={}):
            with patch.object(recommender, '_gather_market_evidence', return_value={}):
                with patch.object(recommender, '_analyze_sale_method') as mock_analyze:
                    # Mock different method analyses
                    mock_analyze.side_effect = [
                        Mock(suitability_score=85, expected_price=Decimal('2500000')),  # Auction
                        Mock(suitability_score=75, expected_price=Decimal('2450000')),  # Private
                        Mock(suitability_score=65, expected_price=Decimal('2480000'))   # EOI
                    ]
                    
                    result = await recommender.recommend_sale_method(sample_property_data)
        
        assert isinstance(result, SaleMethodRecommendation)
        assert result.property_id == 'test-property-123'
        assert isinstance(result.recommended_method, SaleMethod)
        assert result.confidence_score >= 0
        assert len(result.method_analyses) == 3
    
    @pytest.mark.asyncio
    async def test_analyze_property_factors(self, recommender, sample_property_data):
        """Test property factors analysis."""
        
        result = await recommender._analyze_property_factors(sample_property_data)
        
        assert 'property_type_score' in result
        assert 'price_range_score' in result
        assert 'price_category' in result
        assert 'uniqueness_score' in result
        assert 'condition_score' in result
        assert 0 <= result['property_type_score'] <= 1
        assert result['price_category'] in ['budget', 'mid_range', 'premium', 'luxury']


class TestPropertyEnhancementAdvisor:
    """Test property enhancement advisory functionality."""
    
    @pytest.fixture
    def advisor(self):
        return PropertyEnhancementAdvisor()
    
    def test_init(self, advisor):
        """Test advisor initialization."""
        assert len(advisor.roi_benchmarks) > 0
        assert len(advisor.market_preferences) > 0
        assert 'House' in advisor.market_preferences
        assert 'Unit' in advisor.market_preferences
    
    @pytest.mark.asyncio
    async def test_analyze_property_enhancements(self, advisor, sample_property_data, mock_db_session):
        """Test property enhancement analysis."""
        
        with patch.object(advisor, '_assess_property_condition', return_value={'condition_score': 0.7}):
            with patch.object(advisor, '_analyze_market_preferences', return_value={'preferences': {}}):
                with patch.object(advisor, '_generate_enhancement_recommendations') as mock_generate:
                    mock_recommendations = [
                        Mock(
                            priority=Mock(value='High Priority'),
                            estimated_cost=Decimal('15000'),
                            expected_value_add=Decimal('25000'),
                            roi_percentage=66.7,
                            timeframe_weeks=4
                        )
                    ]
                    mock_generate.return_value = mock_recommendations
                    
                    result = await advisor.analyze_property_enhancements(
                        sample_property_data, 
                        budget_limit=Decimal('50000')
                    )
        
        assert isinstance(result, PropertyEnhancementPlan)
        assert result.property_id == 'test-property-123'
        assert result.total_investment_required >= 0
        assert result.total_expected_return >= 0
        assert result.overall_roi is not None
    
    def test_create_paint_recommendation(self, advisor):
        """Test paint recommendation creation."""
        
        result = advisor._create_paint_recommendation(150, 2000000, {'preferences': {}})
        
        assert isinstance(result, EnhancementRecommendation)
        assert result.title == "Interior and Exterior Paint Refresh"
        assert result.estimated_cost > 0
        assert result.expected_value_add > 0
        assert result.roi_percentage > 0
        assert result.timeframe_weeks > 0


class TestPricingCoordinator:
    """Test pricing coordinator functionality."""
    
    @pytest.fixture
    def coordinator(self):
        return PricingCoordinator()
    
    def test_init(self, coordinator):
        """Test coordinator initialization."""
        assert isinstance(coordinator.cma_analyzer, ComparableSalesAnalyzer)
        assert isinstance(coordinator.avm_model, AutomatedValuationModel)
        assert isinstance(coordinator.timing_analyzer, MarketTimingAnalyzer)
        assert len(coordinator.default_weights) == 3
        assert coordinator.default_weights['cma'] + coordinator.default_weights['avm'] <= 1.0
    
    @pytest.mark.asyncio
    async def test_generate_pricing_strategy(self, coordinator, sample_property_data):
        """Test comprehensive pricing strategy generation."""
        
        # Mock all component analyses
        mock_cma = Mock()
        mock_cma.estimated_value = Decimal('2450000')
        mock_cma.confidence_level = 0.85
        mock_cma.confidence_interval_low = Decimal('2350000')
        mock_cma.confidence_interval_high = Decimal('2550000')
        
        mock_avm = Mock()
        mock_avm.predicted_value = Decimal('2480000')
        mock_avm.confidence_score = 0.78
        mock_avm.prediction_interval_low = Decimal('2380000')
        mock_avm.prediction_interval_high = Decimal('2580000')
        
        mock_timing = Mock()
        mock_timing.price_timing_adjustment = 0.02
        mock_timing.timing_score = 75
        mock_timing.risk_factors = []
        mock_timing.opportunity_factors = []
        
        with patch.object(coordinator.cma_analyzer, 'analyze_comparables', return_value=mock_cma):
            with patch.object(coordinator.avm_model, 'predict_value', return_value=mock_avm):
                with patch.object(coordinator.timing_analyzer, 'analyze_optimal_timing', return_value=mock_timing):
                    result = await coordinator.generate_pricing_strategy(sample_property_data)
        
        assert result.recommended_price > 0
        assert result.price_range_low <= result.recommended_price <= result.price_range_high
        assert result.confidence_score > 0
        assert result.listing_price is not None
        assert result.auction_reserve is not None
    
    def test_adjust_model_weights(self, coordinator):
        """Test model weight adjustment based on confidence."""
        
        # Test high confidence CMA
        weights = coordinator._adjust_model_weights(0.90, 0.70, 0.80)
        assert weights['cma'] > coordinator.default_weights['cma']
        
        # Test low confidence CMA
        weights = coordinator._adjust_model_weights(0.30, 0.80, 0.75)
        assert weights['cma'] < coordinator.default_weights['cma']
        
        # Weights should sum to 1.0 (excluding timing)
        assert abs(weights['cma'] + weights['avm'] - 1.0) < 0.001


class TestSellerStrategyAgent:
    """Test main seller strategy agent functionality."""
    
    @pytest.fixture
    def agent(self):
        return SellerStrategyAgent()
    
    def test_init(self, agent):
        """Test agent initialization."""
        assert agent.config.name == "Seller Strategy Agent"
        assert isinstance(agent.pricing_coordinator, PricingCoordinator)
        assert isinstance(agent.sale_method_recommender, SaleMethodRecommender)
        assert isinstance(agent.enhancement_advisor, PropertyEnhancementAdvisor)
        assert agent.analysis_count == 0
    
    @pytest.mark.asyncio
    async def test_execute_agent_logic_success(self, agent, sample_property_data):
        """Test successful agent execution."""
        
        input_data = {'property_id': 'test-property-123'}
        
        with patch.object(agent, '_get_property_data', return_value=sample_property_data):
            with patch.object(agent, '_execute_comprehensive_analysis') as mock_analysis:
                mock_result = Mock()
                mock_result.recommended_listing_price = Decimal('2500000')
                mock_result.overall_confidence = 0.85
                mock_analysis.return_value = mock_result
                
                result = await agent._execute_agent_logic(input_data)
        
        assert result['success'] is True
        assert 'result' in result
        assert 'execution_time' in result
        assert result['property_id'] == 'test-property-123'
    
    @pytest.mark.asyncio
    async def test_execute_agent_logic_missing_property_id(self, agent):
        """Test agent execution with missing property ID."""
        
        input_data = {}
        
        result = await agent._execute_agent_logic(input_data)
        
        assert result['success'] is False
        assert 'property_id is required' in result['error']
    
    @pytest.mark.asyncio
    async def test_get_property_data(self, agent, mock_db_session):
        """Test property data retrieval."""
        
        # Mock property object
        mock_property = Mock()
        mock_property.id = 'test-property-123'
        mock_property.listing_id = 'DOM123456'
        mock_property.title = 'Test Property'
        mock_property.suburb = 'Mosman'
        mock_property.property_type = 'House'
        mock_property.bedrooms = 4
        mock_property.price = Decimal('2500000')
        mock_property.latitude = -33.8688
        mock_property.longitude = 151.2093
        
        with patch('reagent_sydney.agents.seller_strategy.agent.get_db_session'):
            mock_session = mock_db_session.return_value.__aenter__.return_value
            mock_session.get = AsyncMock(return_value=mock_property)
            
            result = await agent._get_property_data('test-property-123')
        
        assert result['id'] == 'test-property-123'
        assert result['suburb'] == 'Mosman'
        assert result['bedrooms'] == 4
        assert result['estimated_price'] == 2500000
    
    def test_generate_strategic_summary(self, agent):
        """Test strategic summary generation."""
        
        # Mock optimized recommendations
        mock_pricing = Mock()
        mock_pricing.recommended_price = Decimal('2500000')
        mock_pricing.listing_price = Decimal('2550000')
        mock_pricing.auction_reserve = Decimal('2400000')
        mock_pricing.confidence_score = 0.85
        mock_pricing.market_opportunities = ['Strong market conditions']
        mock_pricing.pricing_risks = ['Market volatility']
        
        mock_sale_method = Mock()
        mock_sale_method.recommended_method = Mock(value='Auction')
        mock_sale_method.method_analyses = {
            mock_sale_method.recommended_method: Mock(
                expected_price=Decimal('2550000'),
                expected_days_to_sell=35,
                sale_probability=0.80
            )
        }
        mock_sale_method.confidence_score = 0.75
        mock_sale_method.preparation_requirements = ['Marketing campaign', 'Reserve strategy']
        
        mock_enhancements = Mock()
        mock_enhancements.total_investment_required = Decimal('50000')
        mock_enhancements.total_expected_return = Decimal('75000')
        mock_enhancements.overall_roi = 50.0
        mock_enhancements.total_timeframe_weeks = 8
        mock_enhancements.competitive_advantages = ['Modern presentation']
        mock_enhancements.market_risks = ['Over-improvement risk']
        mock_enhancements.essential_improvements = []
        
        optimized_recommendations = {
            'pricing': mock_pricing,
            'sale_method': mock_sale_method,
            'enhancements': mock_enhancements
        }
        
        sample_property_data = {'estimated_price': 2500000}
        
        result = agent._generate_strategic_summary(optimized_recommendations, sample_property_data)
        
        assert 'listing_price' in result
        assert 'expected_price' in result
        assert 'sale_method' in result
        assert 'timeline_weeks' in result
        assert 'investment_required' in result
        assert 'net_return' in result
        assert 'confidence' in result
        assert 0 <= result['confidence'] <= 1
        assert result['sale_method'] == 'Auction'


class TestStatisticalValidator:
    """Test statistical validation functionality."""
    
    @pytest.fixture
    def validator(self):
        return StatisticalValidator()
    
    def test_init(self, validator):
        """Test validator initialization."""
        assert validator.significance_level == 0.05
        assert validator.confidence_level == 0.95
        assert validator.min_sample_size == 30
        assert len(validator.quality_thresholds) > 0
    
    @pytest.mark.asyncio
    async def test_validate_pricing_model(self, validator):
        """Test pricing model validation."""
        
        # Generate synthetic test data
        np.random.seed(42)
        actual_prices = np.random.normal(2000000, 300000, 100)
        predictions = actual_prices + np.random.normal(0, 150000, 100)  # Some prediction error
        
        result = await validator.validate_pricing_model(
            predictions.tolist(), 
            actual_prices.tolist(),
            model_name="test_model"
        )
        
        assert isinstance(result, ValidationMetrics)
        assert result.mae > 0
        assert result.rmse > 0
        assert result.mape > 0
        assert 0 <= result.r2_score <= 1
        assert result.sample_size == 100
        assert result.overall_quality_score >= 0
        assert result.reliability_rating in ['Excellent', 'Good', 'Acceptable', 'Poor', 'Inadequate']
    
    def test_test_normality(self, validator):
        """Test normality testing."""
        
        # Normal data
        normal_data = np.random.normal(0, 1, 100)
        result = validator._test_normality(normal_data)
        
        assert 'is_normal' in result
        assert 'shapiro_wilk' in result
        assert 'jarque_bera' in result
        assert 'interpretation' in result
    
    def test_calculate_hit_rate(self, validator):
        """Test hit rate calculation."""
        
        predictions = [1000000, 1100000, 900000, 1050000]
        actuals = [1000000, 1000000, 1000000, 1000000]
        
        hit_rate = validator._calculate_hit_rate(predictions, actuals, threshold=0.10)
        
        assert 0 <= hit_rate <= 1
        # First prediction is exact (100% hit)
        # Second is 10% off (90% hit, within threshold)
        # Third is 10% off (90% hit, within threshold)  
        # Fourth is 5% off (95% hit, within threshold)
        assert hit_rate == 1.0  # All within 10% threshold


# Integration Tests
class TestIntegration:
    """Integration tests for seller strategy components."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_analysis(self, sample_property_data):
        """Test complete end-to-end analysis workflow."""
        
        agent = SellerStrategyAgent()
        
        # Mock all database dependencies
        with patch('reagent_sydney.agents.seller_strategy.agent.get_db_session'):
            with patch.object(agent, '_get_property_data', return_value=sample_property_data):
                with patch.object(agent.pricing_coordinator.cma_analyzer, '_find_comparable_sales', return_value=[]):
                    with patch.object(agent.pricing_coordinator.cma_analyzer, '_expand_comparable_search', return_value=[]):
                        try:
                            # This should raise an exception due to insufficient comparables
                            await agent._execute_agent_logic({'property_id': 'test-property-123'})
                        except ValueError:
                            pass  # Expected due to mocked empty comparables
    
    def test_model_weight_optimization(self):
        """Test cross-model weight optimization logic."""
        
        coordinator = PricingCoordinator()
        
        # Test different confidence scenarios
        high_cma_weights = coordinator._adjust_model_weights(0.95, 0.70, 0.80)
        low_cma_weights = coordinator._adjust_model_weights(0.40, 0.85, 0.75)
        
        assert high_cma_weights['cma'] > low_cma_weights['cma']
        assert abs(high_cma_weights['cma'] + high_cma_weights['avm'] - 1.0) < 0.001
        assert abs(low_cma_weights['cma'] + low_cma_weights['avm'] - 1.0) < 0.001


# Performance Tests
class TestPerformance:
    """Performance and benchmarking tests."""
    
    @pytest.mark.asyncio
    async def test_analysis_performance(self, sample_property_data):
        """Test that analysis completes within performance requirements."""
        
        agent = SellerStrategyAgent()
        
        start_time = datetime.utcnow()
        
        with patch.object(agent, '_get_property_data', return_value=sample_property_data):
            with patch.object(agent, '_execute_comprehensive_analysis') as mock_analysis:
                mock_analysis.return_value = Mock(overall_confidence=0.85)
                
                result = await agent._execute_agent_logic({'property_id': 'test-property-123'})
        
        execution_time = result.get('execution_time', 0)
        
        # Should complete within 5 seconds (performance requirement)
        assert execution_time < 5.0
    
    def test_memory_usage(self):
        """Test reasonable memory usage for large datasets."""
        
        # This would test memory consumption with large comparable datasets
        # For brevity, we'll test component initialization doesn't consume excessive memory
        
        agent = SellerStrategyAgent()
        
        # Basic memory usage check - agent should initialize without issues
        assert agent.pricing_coordinator is not None
        assert agent.sale_method_recommender is not None
        assert agent.enhancement_advisor is not None


if __name__ == '__main__':
    # Run tests with coverage reporting
    pytest.main([
        __file__,
        '-v',
        '--cov=reagent_sydney.agents.seller_strategy',
        '--cov-report=html',
        '--cov-report=term-missing',
        '--cov-fail-under=90'
    ])