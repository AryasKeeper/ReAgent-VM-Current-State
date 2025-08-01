"""
ReAgent Sydney - Market Validation Framework

Validates accuracy of generated financial insights against known Sydney market benchmarks,
ensuring data quality and analytical reliability for real estate professionals.
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
import structlog

from src.services.external_apis.corelogic_client import get_corelogic_client
from src.services.external_apis.domain_client import DomainAPIClient
from src.core.cache.redis_client import get_cache_manager
from src.agents.agent_whisperer.financial_analyzer import FinancialMetrics


logger = structlog.get_logger(__name__)


@dataclass
class ValidationResult:
    """Market validation result."""
    metric_name: str
    calculated_value: float
    benchmark_value: float
    variance_percentage: float
    confidence_level: str  # "high", "medium", "low"
    validation_status: str  # "passed", "warning", "failed"
    notes: str


@dataclass
class MarketValidationReport:
    """Comprehensive market validation report."""
    property_id: str
    suburb: str
    validation_date: datetime
    overall_confidence: float
    validation_results: List[ValidationResult]
    data_quality_score: float
    recommendation: str
    methodology_notes: str


class SydneyMarketValidator:
    """
    Advanced market validation framework for Sydney property analysis.
    
    Validates calculated metrics against multiple data sources and
    historical benchmarks to ensure analytical accuracy.
    """
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.cache_ttl = 3600  # 1 hour cache
        
        # Sydney market benchmarks (updated quarterly from RBA, APRA, CoreLogic data)
        self.sydney_benchmarks = {
            "rental_yield": {
                "houses": {"median": 3.8, "q1": 3.2, "q3": 4.5, "min": 2.5, "max": 6.0},
                "units": {"median": 4.2, "q1": 3.6, "q3": 4.9, "min": 2.8, "max": 6.5}
            },
            "capital_growth_5yr": {
                "houses": {"median": 5.2, "q1": 3.5, "q3": 7.8, "min": -2.0, "max": 15.0},
                "units": {"median": 4.8, "q1": 3.0, "q3": 7.2, "min": -1.5, "max": 12.0}
            },
            "total_roi": {
                "houses": {"median": 7.2, "q1": 5.8, "q3": 9.5, "min": 2.0, "max": 18.0},
                "units": {"median": 7.8, "q1": 6.2, "q3": 10.2, "min": 2.5, "max": 19.0}
            },
            "cash_flow_weekly": {
                "houses": {"median": 200, "q1": 100, "q3": 350, "min": -100, "max": 800},
                "units": {"median": 150, "q1": 50, "q3": 280, "min": -80, "max": 600}
            },
            "vacancy_rate": {
                "sydney_metro": {"median": 2.1, "q1": 1.5, "q3": 3.2, "min": 0.8, "max": 8.0}
            },
            "days_on_market": {
                "sydney_metro": {"median": 28, "q1": 18, "q3": 45, "min": 5, "max": 120}
            }
        }
        
        # LGA-specific adjustments (premium/discount factors)
        self.lga_adjustments = {
            "City of Sydney": {"yield_factor": 0.85, "growth_factor": 1.25},  # Lower yield, higher growth
            "North Sydney": {"yield_factor": 0.90, "growth_factor": 1.20},
            "Mosman": {"yield_factor": 0.80, "growth_factor": 1.15},
            "Woollahra": {"yield_factor": 0.82, "growth_factor": 1.18},
            "Waverley": {"yield_factor": 0.88, "growth_factor": 1.12},
            "Blacktown": {"yield_factor": 1.15, "growth_factor": 0.95},  # Higher yield, lower growth
            "Liverpool": {"yield_factor": 1.12, "growth_factor": 0.98},
            "Penrith": {"yield_factor": 1.18, "growth_factor": 0.92}
        }
        
        # Validation thresholds
        self.validation_thresholds = {
            "excellent": {"max_variance": 5.0, "min_confidence": 90.0},
            "good": {"max_variance": 15.0, "min_confidence": 75.0},
            "acceptable": {"max_variance": 25.0, "min_confidence": 60.0},
            "poor": {"max_variance": 40.0, "min_confidence": 40.0}
        }
    
    async def validate_financial_analysis(
        self,
        financial_metrics: FinancialMetrics,
        property_type: str = "house"
    ) -> MarketValidationReport:
        """
        Comprehensive validation of financial analysis results.
        
        Args:
            financial_metrics: Calculated financial metrics to validate
            property_type: Type of property (house, unit, townhouse)
            
        Returns:
            Detailed validation report with confidence assessment
        """
        logger.info("Starting market validation",
                   property_id=financial_metrics.property_id,
                   suburb=financial_metrics.suburb,
                   property_type=property_type)
        
        try:
            # Perform individual metric validations
            validation_results = await asyncio.gather(
                self._validate_rental_yield(financial_metrics, property_type),
                self._validate_capital_growth(financial_metrics, property_type),
                self._validate_total_roi(financial_metrics, property_type),
                self._validate_cash_flow(financial_metrics, property_type),
                self._validate_market_context(financial_metrics)
            )
            
            # Flatten results list
            all_validations = [result for sublist in validation_results for result in sublist]
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(all_validations)
            
            # Calculate data quality score
            data_quality_score = self._calculate_data_quality_score(financial_metrics)
            
            # Generate recommendation
            recommendation = self._generate_validation_recommendation(
                all_validations, overall_confidence, data_quality_score
            )
            
            report = MarketValidationReport(
                property_id=financial_metrics.property_id,
                suburb=financial_metrics.suburb,
                validation_date=datetime.utcnow(),
                overall_confidence=overall_confidence,
                validation_results=all_validations,
                data_quality_score=data_quality_score,
                recommendation=recommendation,
                methodology_notes="Validation against RBA, APRA, CoreLogic benchmarks with Sydney LGA adjustments"
            )
            
            logger.info("Market validation completed",
                       property_id=financial_metrics.property_id,
                       overall_confidence=overall_confidence,
                       validation_count=len(all_validations))
            
            return report
            
        except Exception as e:
            logger.error("Market validation failed",
                        property_id=financial_metrics.property_id,
                        error=str(e))
            raise
    
    async def _validate_rental_yield(
        self,
        metrics: FinancialMetrics,
        property_type: str
    ) -> List[ValidationResult]:
        """Validate rental yield calculations."""
        results = []
        
        # Get benchmark for property type
        benchmark_data = self.sydney_benchmarks["rental_yield"].get(
            property_type.lower() + "s", 
            self.sydney_benchmarks["rental_yield"]["houses"]
        )
        
        # Apply LGA adjustment if available
        lga_factor = self._get_lga_adjustment(metrics.suburb, "yield_factor")
        adjusted_benchmark = benchmark_data["median"] * lga_factor
        
        # Validate gross yield
        gross_variance = abs(metrics.rental_yield.gross_yield - adjusted_benchmark) / adjusted_benchmark * 100
        gross_status = self._determine_validation_status(gross_variance)
        
        results.append(ValidationResult(
            metric_name="Gross Rental Yield",
            calculated_value=metrics.rental_yield.gross_yield,
            benchmark_value=adjusted_benchmark,
            variance_percentage=gross_variance,
            confidence_level=self._variance_to_confidence(gross_variance),
            validation_status=gross_status,
            notes=f"Compared to Sydney {property_type} median with LGA adjustment factor {lga_factor:.2f}"
        ))
        
        # Validate net yield (typically 0.8-1.2% lower than gross)
        expected_net_yield = adjusted_benchmark * 0.85  # Assume 15% expense ratio
        net_variance = abs(metrics.rental_yield.net_yield - expected_net_yield) / expected_net_yield * 100
        net_status = self._determine_validation_status(net_variance)
        
        results.append(ValidationResult(
            metric_name="Net Rental Yield",
            calculated_value=metrics.rental_yield.net_yield,
            benchmark_value=expected_net_yield,
            variance_percentage=net_variance,
            confidence_level=self._variance_to_confidence(net_variance),
            validation_status=net_status,
            notes="Net yield validation assumes 15% expense ratio typical for Sydney properties"
        ))
        
        return results
    
    async def _validate_capital_growth(
        self,
        metrics: FinancialMetrics,
        property_type: str
    ) -> List[ValidationResult]:
        """Validate capital growth projections."""
        results = []
        
        # Get benchmark for property type
        benchmark_data = self.sydney_benchmarks["capital_growth_5yr"].get(
            property_type.lower() + "s",
            self.sydney_benchmarks["capital_growth_5yr"]["houses"]
        )
        
        # Apply LGA adjustment
        lga_factor = self._get_lga_adjustment(metrics.suburb, "growth_factor")
        adjusted_benchmark = benchmark_data["median"] * lga_factor
        
        # Validate 5-year growth
        growth_variance = abs(metrics.capital_growth.growth_5yr - adjusted_benchmark) / adjusted_benchmark * 100
        growth_status = self._determine_validation_status(growth_variance)
        
        results.append(ValidationResult(
            metric_name="5-Year Capital Growth",
            calculated_value=metrics.capital_growth.growth_5yr,
            benchmark_value=adjusted_benchmark,
            variance_percentage=growth_variance,
            confidence_level=self._variance_to_confidence(growth_variance),
            validation_status=growth_status,
            notes=f"Validated against historical Sydney {property_type} performance with LGA factor {lga_factor:.2f}"
        ))
        
        # Validate volatility (should be within reasonable range)
        expected_volatility = 12.5  # Sydney property market average
        if metrics.capital_growth.volatility > expected_volatility * 2:
            volatility_status = "warning"
            volatility_notes = "Unusually high volatility detected - verify data quality"
        elif metrics.capital_growth.volatility < expected_volatility * 0.5:
            volatility_status = "warning"
            volatility_notes = "Unusually low volatility - may indicate insufficient data"
        else:
            volatility_status = "passed"
            volatility_notes = "Volatility within expected range for Sydney market"
        
        results.append(ValidationResult(
            metric_name="Growth Volatility",
            calculated_value=metrics.capital_growth.volatility,
            benchmark_value=expected_volatility,
            variance_percentage=abs(metrics.capital_growth.volatility - expected_volatility) / expected_volatility * 100,
            confidence_level="medium",
            validation_status=volatility_status,
            notes=volatility_notes
        ))
        
        return results
    
    async def _validate_total_roi(
        self,
        metrics: FinancialMetrics,
        property_type: str
    ) -> List[ValidationResult]:
        """Validate total return on investment."""
        results = []
        
        # Get benchmark for property type
        benchmark_data = self.sydney_benchmarks["total_roi"].get(
            property_type.lower() + "s",
            self.sydney_benchmarks["total_roi"]["houses"]
        )
        
        # Apply combined LGA adjustments
        yield_factor = self._get_lga_adjustment(metrics.suburb, "yield_factor")
        growth_factor = self._get_lga_adjustment(metrics.suburb, "growth_factor")
        combined_factor = (yield_factor + growth_factor) / 2
        
        adjusted_benchmark = benchmark_data["median"] * combined_factor
        
        # Validate total ROI
        roi_variance = abs(metrics.total_roi - adjusted_benchmark) / adjusted_benchmark * 100
        roi_status = self._determine_validation_status(roi_variance)
        
        results.append(ValidationResult(
            metric_name="Total ROI",
            calculated_value=metrics.total_roi,
            benchmark_value=adjusted_benchmark,
            variance_percentage=roi_variance,
            confidence_level=self._variance_to_confidence(roi_variance),
            validation_status=roi_status,
            notes=f"Total ROI validated against Sydney benchmarks with combined LGA factor {combined_factor:.2f}"
        ))
        
        # Cross-validation: ROI should approximately equal yield + growth
        calculated_components = metrics.rental_yield.net_yield + metrics.capital_growth.annualized_return
        component_variance = abs(metrics.total_roi - calculated_components) / calculated_components * 100
        
        if component_variance > 10:  # More than 10% variance suggests calculation error
            component_status = "warning"
            component_notes = "ROI calculation may have inconsistencies - verify component calculations"
        else:
            component_status = "passed"
            component_notes = "ROI calculation consistent with component metrics"
        
        results.append(ValidationResult(
            metric_name="ROI Component Consistency",
            calculated_value=metrics.total_roi,
            benchmark_value=calculated_components,
            variance_percentage=component_variance,
            confidence_level="high",
            validation_status=component_status,
            notes=component_notes
        ))
        
        return results
    
    async def _validate_cash_flow(
        self,
        metrics: FinancialMetrics,
        property_type: str
    ) -> List[ValidationResult]:
        """Validate cash flow calculations."""
        results = []
        
        # Convert annual cash flow to weekly for comparison
        weekly_cash_flow = float(metrics.cash_flow.annual_cash_flow) / 52
        
        # Get benchmark for property type
        benchmark_data = self.sydney_benchmarks["cash_flow_weekly"].get(
            property_type.lower() + "s",
            self.sydney_benchmarks["cash_flow_weekly"]["houses"]
        )
        
        benchmark_median = benchmark_data["median"]
        
        # Determine validation status based on quartile position
        if weekly_cash_flow < benchmark_data["q1"]:
            if weekly_cash_flow < benchmark_data["min"]:
                status = "failed"
                notes = "Cash flow significantly below market expectations"
            else:
                status = "warning"
                notes = "Cash flow in lower quartile - consider market conditions"
        elif weekly_cash_flow > benchmark_data["q3"]:
            if weekly_cash_flow > benchmark_data["max"]:
                status = "warning"
                notes = "Exceptionally high cash flow - verify calculations"
            else:
                status = "passed"
                notes = "Cash flow in upper quartile - strong performance"
        else:
            status = "passed"
            notes = "Cash flow within normal market range"
        
        variance = abs(weekly_cash_flow - benchmark_median) / abs(benchmark_median) * 100 if benchmark_median != 0 else 0
        
        results.append(ValidationResult(
            metric_name="Weekly Cash Flow",
            calculated_value=weekly_cash_flow,
            benchmark_value=benchmark_median,
            variance_percentage=variance,
            confidence_level=self._variance_to_confidence(variance),
            validation_status=status,
            notes=notes
        ))
        
        return results
    
    async def _validate_market_context(self, metrics: FinancialMetrics) -> List[ValidationResult]:
        """Validate market context metrics."""
        results = []
        
        # Validate vacancy rate
        vacancy_benchmark = self.sydney_benchmarks["vacancy_rate"]["sydney_metro"]["median"]
        vacancy_variance = abs(metrics.vacancy_rate - vacancy_benchmark) / vacancy_benchmark * 100
        vacancy_status = self._determine_validation_status(vacancy_variance)
        
        results.append(ValidationResult(
            metric_name="Vacancy Rate",
            calculated_value=metrics.vacancy_rate,
            benchmark_value=vacancy_benchmark,
            variance_percentage=vacancy_variance,
            confidence_level=self._variance_to_confidence(vacancy_variance),
            validation_status=vacancy_status,
            notes="Validated against Sydney metro average vacancy rate"
        ))
        
        # Validate days on market
        dom_benchmark = self.sydney_benchmarks["days_on_market"]["sydney_metro"]["median"]
        dom_variance = abs(metrics.days_on_market_avg - dom_benchmark) / dom_benchmark * 100
        dom_status = self._determine_validation_status(dom_variance)
        
        results.append(ValidationResult(
            metric_name="Days on Market",
            calculated_value=metrics.days_on_market_avg,
            benchmark_value=dom_benchmark,
            variance_percentage=dom_variance,
            confidence_level=self._variance_to_confidence(dom_variance),
            validation_status=dom_status,
            notes="Validated against Sydney metro average days on market"
        ))
        
        return results
    
    def _get_lga_adjustment(self, suburb: str, factor_type: str) -> float:
        """Get LGA-specific adjustment factor."""
        # This would typically query a database of LGA mappings
        # For now, use simplified suburb-to-LGA mapping
        lga_mapping = {
            "Sydney": "City of Sydney",
            "Surry Hills": "City of Sydney",
            "Paddington": "City of Sydney",
            "North Sydney": "North Sydney",
            "Mosman": "Mosman",
            "Double Bay": "Woollahra",
            "Bondi": "Waverley",
            "Blacktown": "Blacktown",
            "Liverpool": "Liverpool",
            "Penrith": "Penrith"
        }
        
        lga = lga_mapping.get(suburb)
        if lga and lga in self.lga_adjustments:
            return self.lga_adjustments[lga].get(factor_type, 1.0)
        
        return 1.0  # No adjustment if LGA not found
    
    def _determine_validation_status(self, variance_percentage: float) -> str:
        """Determine validation status based on variance."""
        if variance_percentage <= self.validation_thresholds["excellent"]["max_variance"]:
            return "passed"
        elif variance_percentage <= self.validation_thresholds["good"]["max_variance"]:
            return "passed"
        elif variance_percentage <= self.validation_thresholds["acceptable"]["max_variance"]:
            return "warning"
        else:
            return "failed"
    
    def _variance_to_confidence(self, variance_percentage: float) -> str:
        """Convert variance percentage to confidence level."""
        if variance_percentage <= self.validation_thresholds["excellent"]["max_variance"]:
            return "high"
        elif variance_percentage <= self.validation_thresholds["good"]["max_variance"]:
            return "high"
        elif variance_percentage <= self.validation_thresholds["acceptable"]["max_variance"]:
            return "medium"
        else:
            return "low"
    
    def _calculate_overall_confidence(self, validation_results: List[ValidationResult]) -> float:
        """Calculate overall confidence score."""
        if not validation_results:
            return 0.0
        
        confidence_weights = {"high": 1.0, "medium": 0.7, "low": 0.3}
        status_weights = {"passed": 1.0, "warning": 0.6, "failed": 0.2}
        
        total_score = 0.0
        total_weight = 0.0
        
        for result in validation_results:
            confidence_weight = confidence_weights.get(result.confidence_level, 0.5)
            status_weight = status_weights.get(result.validation_status, 0.5)
            
            score = confidence_weight * status_weight
            weight = 1.0
            
            total_score += score * weight
            total_weight += weight
        
        return (total_score / total_weight * 100) if total_weight > 0 else 0.0
    
    def _calculate_data_quality_score(self, metrics: FinancialMetrics) -> float:
        """Calculate data quality score based on available data."""
        score = 0.0
        max_score = 100.0
        
        # Data source diversity (25 points)
        if len(metrics.data_sources) >= 3:
            score += 25.0
        elif len(metrics.data_sources) >= 2:
            score += 18.0
        elif len(metrics.data_sources) >= 1:
            score += 10.0
        
        # Sample size adequacy (25 points)
        if metrics.confidence_score >= 90:
            score += 25.0
        elif metrics.confidence_score >= 75:
            score += 20.0
        elif metrics.confidence_score >= 60:
            score += 15.0
        elif metrics.confidence_score >= 40:
            score += 10.0
        
        # Data recency (25 points)
        data_age_hours = (datetime.utcnow() - metrics.analysis_date).total_seconds() / 3600
        if data_age_hours < 1:
            score += 25.0
        elif data_age_hours < 24:
            score += 20.0
        elif data_age_hours < 168:  # 1 week
            score += 15.0
        else:
            score += 5.0
        
        # Calculation completeness (25 points)
        if all([
            metrics.rental_yield.weekly_rent > 0,
            metrics.capital_growth.current_value > 0,
            metrics.cash_flow.annual_cash_flow is not None,
            metrics.total_roi > 0
        ]):
            score += 25.0
        else:
            score += 10.0
        
        return min(score, max_score)
    
    def _generate_validation_recommendation(
        self,
        validation_results: List[ValidationResult],
        overall_confidence: float,
        data_quality_score: float
    ) -> str:
        """Generate validation-based recommendation."""
        failed_count = sum(1 for r in validation_results if r.validation_status == "failed")
        warning_count = sum(1 for r in validation_results if r.validation_status == "warning")
        
        if overall_confidence >= 80 and data_quality_score >= 75 and failed_count == 0:
            return "APPROVED: Analysis meets high confidence standards. Suitable for professional reporting."
        elif overall_confidence >= 65 and data_quality_score >= 60 and failed_count <= 1:
            return "APPROVED WITH NOTES: Analysis acceptable with minor concerns. Review validation warnings."
        elif overall_confidence >= 50 and failed_count <= 2:
            return "CONDITIONAL: Analysis has moderate confidence. Use with caution and additional verification."
        else:
            return "REJECTED: Analysis fails validation standards. Requires data quality improvement or methodology review."


# Export for use in report generator
__all__ = ['SydneyMarketValidator', 'MarketValidationReport', 'ValidationResult']