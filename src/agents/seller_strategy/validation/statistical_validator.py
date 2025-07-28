"""
Statistical Validator

Comprehensive statistical validation for pricing algorithms including
confidence intervals, significance testing, and model diagnostics.
"""

import numpy as np
import pandas as pd
import scipy.stats as stats
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
from decimal import Decimal
import math

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from scipy.stats import pearsonr, spearmanr, normaltest, jarque_bera
from statsmodels.stats.diagnostic import het_breuschpagan, het_white
from statsmodels.stats.stattools import durbin_watson
import statsmodels.api as sm

from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session

from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.data.models.property_models import Property, PropertyPriceHistory


@dataclass
class ValidationMetrics:
    """Comprehensive validation metrics for pricing models."""
    
    # Accuracy Metrics
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Square Error
    mape: float  # Mean Absolute Percentage Error
    r2_score: float  # R-squared
    adjusted_r2: float  # Adjusted R-squared  
    
    # Statistical Tests
    normality_test: Dict[str, Any]  # Residuals normality
    heteroscedasticity_test: Dict[str, Any]  # Variance homogeneity
    autocorrelation_test: Dict[str, Any]  # Serial correlation
    
    # Confidence Intervals
    confidence_intervals: Dict[str, Tuple[float, float]]
    prediction_intervals: Dict[str, Tuple[float, float]]
    
    # Model Diagnostics
    outlier_percentage: float
    leverage_points: int
    influential_points: int
    
    # Sample Statistics
    sample_size: int
    degrees_of_freedom: int
    statistical_power: float
    
    # Quality Scores
    overall_quality_score: float  # 0-100
    reliability_rating: str  # High, Medium, Low
    recommendations: List[str]


@dataclass
class BacktestResult:
    """Backtest validation result."""
    
    test_period: Tuple[datetime, datetime]
    predictions: List[float]
    actual_values: List[float]
    property_ids: List[str]
    
    # Performance Metrics
    hit_rate: float  # % within 10% of actual
    median_error: float
    error_distribution: Dict[str, float]
    
    # Temporal Analysis
    performance_by_month: Dict[str, float]
    trend_accuracy: float
    
    # Market Segment Analysis
    performance_by_segment: Dict[str, ValidationMetrics]
    
    validation_metrics: ValidationMetrics


class StatisticalValidator:
    """
    Advanced statistical validation framework for pricing algorithms.
    
    Provides comprehensive validation including:
    - Cross-validation and backtesting
    - Statistical significance testing
    - Model diagnostic analysis
    - Confidence interval calculation
    - Performance benchmarking
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Validation parameters
        self.significance_level = 0.05
        self.confidence_level = 0.95
        self.min_sample_size = 30
        self.outlier_threshold = 3.0  # Standard deviations
        self.acceptable_mape = 15.0  # 15% MAPE threshold
        
        # Quality thresholds
        self.quality_thresholds = {
            'excellent': {'r2': 0.85, 'mape': 8.0, 'hit_rate': 0.85},
            'good': {'r2': 0.75, 'mape': 12.0, 'hit_rate': 0.75},
            'acceptable': {'r2': 0.65, 'mape': 18.0, 'hit_rate': 0.65},
            'poor': {'r2': 0.50, 'mape': 25.0, 'hit_rate': 0.50}
        }
    
    async def validate_pricing_model(
        self,
        model_predictions: List[float],
        actual_prices: List[float],
        property_features: Optional[pd.DataFrame] = None,
        model_name: str = "pricing_model"
    ) -> ValidationMetrics:
        """
        Comprehensive statistical validation of pricing model performance.
        
        Args:
            model_predictions: Model predicted values
            actual_prices: Actual sale prices
            property_features: Optional property features for advanced diagnostics
            model_name: Name of the model being validated
            
        Returns:
            ValidationMetrics with comprehensive validation results
        """
        try:
            self.logger.info(f"Starting statistical validation for {model_name}")
            
            # Convert to numpy arrays
            predictions = np.array(model_predictions)
            actuals = np.array(actual_prices)
            
            # Validate input data
            if len(predictions) != len(actuals):
                raise ValueError("Predictions and actuals must have same length")
            
            if len(predictions) < self.min_sample_size:
                raise ValueError(f"Insufficient sample size: {len(predictions)} < {self.min_sample_size}")
            
            # Calculate residuals
            residuals = actuals - predictions
            
            # Basic accuracy metrics
            mae = mean_absolute_error(actuals, predictions)
            rmse = np.sqrt(mean_squared_error(actuals, predictions))
            mape = np.mean(np.abs((actuals - predictions) / actuals)) * 100
            r2 = r2_score(actuals, predictions)
            
            # Adjusted R-squared
            n = len(predictions)
            p = property_features.shape[1] if property_features is not None else 1
            adjusted_r2 = 1 - (1 - r2) * (n - 1) / (n - p - 1)
            
            # Statistical tests
            normality_test = self._test_normality(residuals)
            heteroscedasticity_test = self._test_heteroscedasticity(predictions, residuals)
            autocorrelation_test = self._test_autocorrelation(residuals)
            
            # Confidence intervals
            confidence_intervals = self._calculate_confidence_intervals(predictions, residuals)
            prediction_intervals = self._calculate_prediction_intervals(predictions, residuals)
            
            # Model diagnostics
            outlier_percentage = self._calculate_outlier_percentage(residuals)
            leverage_points = self._count_leverage_points(property_features, residuals) if property_features is not None else 0
            influential_points = self._count_influential_points(predictions, residuals, actuals)
            
            # Statistical power
            statistical_power = self._calculate_statistical_power(r2, n, p)
            
            # Overall quality assessment
            quality_score, reliability_rating, recommendations = self._assess_overall_quality(
                mae, rmse, mape, r2, normality_test, heteroscedasticity_test, n
            )
            
            # Build validation metrics
            metrics = ValidationMetrics(
                mae=mae,
                rmse=rmse,
                mape=mape,
                r2_score=r2,
                adjusted_r2=adjusted_r2,
                normality_test=normality_test,
                heteroscedasticity_test=heteroscedasticity_test,
                autocorrelation_test=autocorrelation_test,
                confidence_intervals=confidence_intervals,
                prediction_intervals=prediction_intervals,
                outlier_percentage=outlier_percentage,
                leverage_points=leverage_points,
                influential_points=influential_points,
                sample_size=n,
                degrees_of_freedom=n - p - 1,
                statistical_power=statistical_power,
                overall_quality_score=quality_score,
                reliability_rating=reliability_rating,
                recommendations=recommendations
            )
            
            self.logger.info(
                f"Validation completed for {model_name}: "
                f"R²={r2:.3f}, MAPE={mape:.1f}%, Quality={reliability_rating}"
            )
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Statistical validation failed: {str(e)}")
            raise
    
    async def backtest_pricing_model(
        self,
        model_func,
        start_date: datetime,
        end_date: datetime,
        market_segments: Optional[List[str]] = None
    ) -> BacktestResult:
        """
        Perform comprehensive backtesting of pricing model.
        
        Args:
            model_func: Function that takes property data and returns prediction
            start_date: Start of backtest period
            end_date: End of backtest period
            market_segments: Optional market segments to analyze separately
            
        Returns:
            BacktestResult with temporal and segmented analysis
        """
        try:
            self.logger.info(f"Starting backtest from {start_date} to {end_date}")
            
            # Get historical data for backtesting
            test_data = await self._get_backtest_data(start_date, end_date)
            
            if len(test_data) < self.min_sample_size:
                raise ValueError(f"Insufficient backtest data: {len(test_data)}")
            
            # Generate predictions
            predictions = []
            actual_values = []
            property_ids = []
            
            for _, row in test_data.iterrows():
                property_data = row.to_dict()
                
                try:
                    # Generate prediction (this would call the actual model)
                    prediction = await model_func(property_data)
                    predictions.append(float(prediction))
                    actual_values.append(float(row['actual_price']))
                    property_ids.append(row['property_id'])
                    
                except Exception as e:
                    self.logger.warning(f"Prediction failed for property {row['property_id']}: {e}")
                    continue
            
            # Calculate performance metrics
            hit_rate = self._calculate_hit_rate(predictions, actual_values)
            median_error = np.median(np.abs(np.array(actual_values) - np.array(predictions)))
            error_distribution = self._analyze_error_distribution(predictions, actual_values)
            
            # Temporal analysis
            performance_by_month = self._analyze_temporal_performance(
                test_data, predictions, actual_values
            )
            trend_accuracy = self._calculate_trend_accuracy(predictions, actual_values)
            
            # Market segment analysis
            performance_by_segment = {}
            if market_segments:
                for segment in market_segments:
                    segment_data = self._filter_by_segment(test_data, predictions, actual_values, segment)
                    if len(segment_data['predictions']) >= 10:  # Minimum for segment analysis
                        segment_metrics = await self.validate_pricing_model(
                            segment_data['predictions'], 
                            segment_data['actuals']
                        )
                        performance_by_segment[segment] = segment_metrics
            
            # Overall validation metrics
            validation_metrics = await self.validate_pricing_model(predictions, actual_values)
            
            # Build backtest result
            result = BacktestResult(
                test_period=(start_date, end_date),
                predictions=predictions,
                actual_values=actual_values,
                property_ids=property_ids,
                hit_rate=hit_rate,
                median_error=median_error,
                error_distribution=error_distribution,
                performance_by_month=performance_by_month,
                trend_accuracy=trend_accuracy,
                performance_by_segment=performance_by_segment,
                validation_metrics=validation_metrics
            )
            
            self.logger.info(
                f"Backtest completed: {len(predictions)} predictions, "
                f"{hit_rate:.1%} hit rate, {median_error:,.0f} median error"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Backtesting failed: {str(e)}")
            raise
    
    def _test_normality(self, residuals: np.ndarray) -> Dict[str, Any]:
        """Test residuals for normality using multiple tests."""
        
        # Shapiro-Wilk test (best for small samples)
        if len(residuals) <= 5000:
            shapiro_stat, shapiro_p = stats.shapiro(residuals)
        else:
            shapiro_stat, shapiro_p = None, None
        
        # Jarque-Bera test (good for large samples)
        jb_stat, jb_p = jarque_bera(residuals)
        
        # D'Agostino's normality test
        dagostino_stat, dagostino_p = normaltest(residuals)
        
        # Determine overall normality
        tests = [jb_p, dagostino_p]
        if shapiro_p is not None:
            tests.append(shapiro_p)
        
        is_normal = all(p > self.significance_level for p in tests)
        
        return {
            'is_normal': is_normal,
            'shapiro_wilk': {'statistic': shapiro_stat, 'p_value': shapiro_p},
            'jarque_bera': {'statistic': jb_stat, 'p_value': jb_p},
            'dagostino': {'statistic': dagostino_stat, 'p_value': dagostino_p},
            'interpretation': 'Residuals are normally distributed' if is_normal else 'Residuals show non-normal distribution'
        }
    
    def _test_heteroscedasticity(self, predictions: np.ndarray, residuals: np.ndarray) -> Dict[str, Any]:
        """Test for heteroscedasticity (non-constant variance)."""
        
        try:
            # Prepare data for statsmodels
            X = sm.add_constant(predictions.reshape(-1, 1))
            
            # Breusch-Pagan test
            bp_stat, bp_p, bp_f_stat, bp_f_p = het_breuschpagan(residuals, X)
            
            # White test
            white_stat, white_p, white_f_stat, white_f_p = het_white(residuals, X)
            
            # Determine homoscedasticity
            is_homoscedastic = bp_p > self.significance_level and white_p > self.significance_level
            
            return {
                'is_homoscedastic': is_homoscedastic,
                'breusch_pagan': {'statistic': bp_stat, 'p_value': bp_p},
                'white_test': {'statistic': white_stat, 'p_value': white_p},
                'interpretation': 'Constant variance (homoscedastic)' if is_homoscedastic else 'Non-constant variance (heteroscedastic)'
            }
            
        except Exception as e:
            self.logger.warning(f"Heteroscedasticity test failed: {e}")
            return {
                'is_homoscedastic': None,
                'error': str(e),
                'interpretation': 'Test could not be performed'
            }
    
    def _test_autocorrelation(self, residuals: np.ndarray) -> Dict[str, Any]:
        """Test for autocorrelation in residuals."""
        
        # Durbin-Watson test
        dw_stat = durbin_watson(residuals)
        
        # Ljung-Box test for higher-order autocorrelation
        lb_stat, lb_p = stats.acorr_ljungbox(residuals, lags=10, return_df=False)
        
        # Interpret Durbin-Watson (values near 2 indicate no autocorrelation)
        if 1.5 <= dw_stat <= 2.5:
            dw_interpretation = "No significant autocorrelation"
            has_autocorrelation = False
        elif dw_stat < 1.5:
            dw_interpretation = "Positive autocorrelation detected"
            has_autocorrelation = True
        else:
            dw_interpretation = "Negative autocorrelation detected"
            has_autocorrelation = True
        
        # Overall assessment
        overall_autocorr = has_autocorrelation or (lb_p[-1] < self.significance_level)
        
        return {
            'has_autocorrelation': overall_autocorr,
            'durbin_watson': {'statistic': dw_stat, 'interpretation': dw_interpretation},
            'ljung_box': {'statistic': lb_stat[-1], 'p_value': lb_p[-1]},
            'interpretation': 'Serial correlation detected' if overall_autocorr else 'No significant serial correlation'
        }
    
    def _calculate_confidence_intervals(
        self, 
        predictions: np.ndarray, 
        residuals: np.ndarray,
        confidence_level: float = 0.95
    ) -> Dict[str, Tuple[float, float]]:
        """Calculate confidence intervals for predictions."""
        
        alpha = 1 - confidence_level
        t_value = stats.t.ppf(1 - alpha/2, len(residuals) - 1)
        
        # Standard error of predictions
        mse = np.mean(residuals**2)
        se = np.sqrt(mse)
        
        # Confidence intervals
        intervals = {}
        
        # Overall prediction confidence interval
        margin = t_value * se
        intervals['prediction'] = (
            float(np.mean(predictions) - margin),
            float(np.mean(predictions) + margin)
        )
        
        # Residual confidence interval
        residual_margin = t_value * np.std(residuals)
        intervals['residual'] = (
            float(-residual_margin),
            float(residual_margin)
        )
        
        return intervals
    
    def _calculate_prediction_intervals(
        self,
        predictions: np.ndarray,
        residuals: np.ndarray,
        confidence_level: float = 0.95
    ) -> Dict[str, Tuple[float, float]]:
        """Calculate prediction intervals for new observations."""
        
        alpha = 1 - confidence_level
        t_value = stats.t.ppf(1 - alpha/2, len(residuals) - 1)
        
        # Prediction interval is wider than confidence interval
        mse = np.mean(residuals**2)
        se_pred = np.sqrt(mse * (1 + 1/len(predictions)))  # Extra uncertainty for new prediction
        
        margin = t_value * se_pred
        
        return {
            'individual_prediction': (
                float(np.mean(predictions) - margin),
                float(np.mean(predictions) + margin)
            )
        }
    
    def _calculate_outlier_percentage(self, residuals: np.ndarray) -> float:
        """Calculate percentage of outliers using z-score method."""
        
        z_scores = np.abs(stats.zscore(residuals))
        outliers = z_scores > self.outlier_threshold
        
        return float(np.sum(outliers) / len(residuals) * 100)
    
    def _count_leverage_points(self, features: pd.DataFrame, residuals: np.ndarray) -> int:
        """Count high leverage points that may influence the model."""
        
        if features is None:
            return 0
        
        try:
            # Calculate hat matrix diagonal (leverage values)
            X = sm.add_constant(features.values)
            hat_matrix = X @ np.linalg.inv(X.T @ X) @ X.T
            leverage = np.diag(hat_matrix)
            
            # Threshold for high leverage: 2p/n or 3p/n
            p = X.shape[1]
            n = X.shape[0]
            threshold = 2 * p / n
            
            high_leverage = leverage > threshold
            return int(np.sum(high_leverage))
            
        except Exception as e:
            self.logger.warning(f"Leverage calculation failed: {e}")
            return 0
    
    def _count_influential_points(
        self, 
        predictions: np.ndarray, 
        residuals: np.ndarray, 
        actuals: np.ndarray
    ) -> int:
        """Count influential points using Cook's distance."""
        
        try:
            # Calculate standardized residuals
            standardized_residuals = residuals / np.std(residuals)
            
            # Simplified Cook's distance approximation
            # In practice, would use full Cook's distance calculation
            cooks_d = (standardized_residuals**2) / len(predictions)
            
            # Threshold: 4/n
            threshold = 4 / len(predictions)
            
            influential = cooks_d > threshold
            return int(np.sum(influential))
            
        except Exception as e:
            self.logger.warning(f"Cook's distance calculation failed: {e}")
            return 0
    
    def _calculate_statistical_power(self, r2: float, n: int, p: int) -> float:
        """Calculate statistical power of the model."""
        
        try:
            # Effect size (Cohen's f²)
            f_squared = r2 / (1 - r2)
            
            # Approximate power calculation
            # This is a simplified calculation; full power analysis would use more sophisticated methods
            if f_squared > 0.35:  # Large effect
                power = 0.95
            elif f_squared > 0.15:  # Medium effect
                power = 0.80
            elif f_squared > 0.02:  # Small effect
                power = 0.60
            else:
                power = 0.40
            
            # Adjust for sample size
            if n < 30:
                power *= 0.8
            elif n > 100:
                power = min(0.99, power * 1.1)
            
            return power
            
        except Exception:
            return 0.5  # Default moderate power
    
    def _assess_overall_quality(
        self,
        mae: float,
        rmse: float,
        mape: float,
        r2: float,
        normality_test: Dict[str, Any],
        heteroscedasticity_test: Dict[str, Any],
        sample_size: int
    ) -> Tuple[float, str, List[str]]:
        """Assess overall model quality and provide recommendations."""
        
        # Calculate quality score (0-100)
        quality_components = {
            'accuracy': self._score_accuracy(r2, mape),
            'statistical_validity': self._score_statistical_validity(normality_test, heteroscedasticity_test),
            'sample_adequacy': self._score_sample_adequacy(sample_size),
            'precision': self._score_precision(mae, rmse)
        }
        
        # Weighted quality score
        weights = {'accuracy': 0.4, 'statistical_validity': 0.3, 'sample_adequacy': 0.15, 'precision': 0.15}
        quality_score = sum(score * weights[component] for component, score in quality_components.items())
        
        # Determine reliability rating
        if quality_score >= 85:
            reliability_rating = "Excellent"
        elif quality_score >= 75:
            reliability_rating = "Good"
        elif quality_score >= 65:
            reliability_rating = "Acceptable"
        elif quality_score >= 50:
            reliability_rating = "Poor"
        else:
            reliability_rating = "Inadequate"
        
        # Generate recommendations
        recommendations = []
        
        if r2 < 0.7:
            recommendations.append("Consider adding more predictive features or using ensemble methods")
        
        if mape > 15:
            recommendations.append("High prediction error - review model assumptions and feature engineering")
        
        if not normality_test.get('is_normal', True):
            recommendations.append("Non-normal residuals - consider data transformation or robust regression")
        
        if not heteroscedasticity_test.get('is_homoscedastic', True):
            recommendations.append("Heteroscedasticity detected - consider weighted regression or variance modeling")
        
        if sample_size < 100:
            recommendations.append("Small sample size - collect more data for improved reliability")
        
        if quality_score < 70:
            recommendations.append("Overall model quality is below acceptable threshold - consider model redesign")
        
        return quality_score, reliability_rating, recommendations
    
    def _score_accuracy(self, r2: float, mape: float) -> float:
        """Score model accuracy component."""
        
        r2_score = min(100, r2 * 100)
        mape_score = max(0, 100 - mape * 2)  # Penalty for high MAPE
        
        return (r2_score + mape_score) / 2
    
    def _score_statistical_validity(
        self,
        normality_test: Dict[str, Any], 
        heteroscedasticity_test: Dict[str, Any]
    ) -> float:
        """Score statistical validity component."""
        
        score = 100
        
        if not normality_test.get('is_normal', True):
            score -= 30
        
        if not heteroscedasticity_test.get('is_homoscedastic', True):
            score -= 25
        
        return max(0, score)
    
    def _score_sample_adequacy(self, sample_size: int) -> float:
        """Score sample size adequacy."""
        
        if sample_size >= 200:
            return 100
        elif sample_size >= 100:
            return 85
        elif sample_size >= 50:
            return 70
        elif sample_size >= 30:
            return 50
        else:
            return 25
    
    def _score_precision(self, mae: float, rmse: float) -> float:
        """Score model precision based on error metrics."""
        
        # Assume typical property price of $1M for scaling
        typical_price = 1000000
        
        mae_ratio = mae / typical_price
        rmse_ratio = rmse / typical_price
        
        # Score based on error ratios
        mae_score = max(0, 100 - mae_ratio * 1000)  # Penalty for high relative error
        rmse_score = max(0, 100 - rmse_ratio * 800)
        
        return (mae_score + rmse_score) / 2
    
    def _calculate_hit_rate(self, predictions: List[float], actuals: List[float], threshold: float = 0.10) -> float:
        """Calculate hit rate (percentage within threshold of actual)."""
        
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        
        relative_errors = np.abs((predictions - actuals) / actuals)
        hits = relative_errors <= threshold
        
        return float(np.mean(hits))
    
    def _analyze_error_distribution(self, predictions: List[float], actuals: List[float]) -> Dict[str, float]:
        """Analyze distribution of prediction errors."""
        
        errors = np.array(predictions) - np.array(actuals)
        relative_errors = errors / np.array(actuals) * 100
        
        return {
            'mean_error': float(np.mean(errors)),
            'median_error': float(np.median(errors)),
            'std_error': float(np.std(errors)),
            'skewness': float(stats.skew(errors)),
            'kurtosis': float(stats.kurtosis(errors)),
            '5th_percentile': float(np.percentile(relative_errors, 5)),
            '95th_percentile': float(np.percentile(relative_errors, 95))
        }
    
    def _analyze_temporal_performance(
        self,
        test_data: pd.DataFrame,
        predictions: List[float],
        actuals: List[float]
    ) -> Dict[str, float]:
        """Analyze model performance over time."""
        
        # This would analyze performance by month/quarter
        # For brevity, returning simplified temporal analysis
        
        performance_by_month = {}
        
        # Group by month and calculate MAPE
        test_data['prediction'] = predictions
        test_data['actual'] = actuals
        test_data['month'] = pd.to_datetime(test_data['sale_date']).dt.to_period('M')
        
        for month, group in test_data.groupby('month'):
            if len(group) >= 5:  # Minimum for monthly analysis
                mape = np.mean(np.abs((group['prediction'] - group['actual']) / group['actual'])) * 100
                performance_by_month[str(month)] = mape
        
        return performance_by_month
    
    def _calculate_trend_accuracy(self, predictions: List[float], actuals: List[float]) -> float:
        """Calculate accuracy of trend prediction (directional accuracy)."""
        
        if len(predictions) < 2:
            return 0.0
        
        pred_changes = np.diff(predictions)
        actual_changes = np.diff(actuals)
        
        # Direction agreement
        same_direction = np.sign(pred_changes) == np.sign(actual_changes)
        
        return float(np.mean(same_direction))
    
    def _filter_by_segment(
        self,
        test_data: pd.DataFrame,
        predictions: List[float],
        actuals: List[float],
        segment: str
    ) -> Dict[str, List[float]]:
        """Filter data by market segment for segmented analysis."""
        
        # This would implement actual segmentation logic
        # For now, return a subset based on segment criteria
        
        segment_mask = test_data['property_type'] == segment  # Simplified segmentation
        
        segment_predictions = [p for i, p in enumerate(predictions) if segment_mask.iloc[i]]
        segment_actuals = [a for i, a in enumerate(actuals) if segment_mask.iloc[i]]
        
        return {
            'predictions': segment_predictions,
            'actuals': segment_actuals
        }
    
    async def _get_backtest_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Get historical data for backtesting."""
        
        async with get_db_session() as session:
            query = text("""
                SELECT 
                    p.id as property_id,
                    p.property_type,
                    p.suburb,
                    p.postcode,
                    p.bedrooms,
                    p.bathrooms,
                    p.car_spaces,
                    p.land_size,
                    p.building_size,
                    p.latitude,
                    p.longitude,
                    ph.price as actual_price,
                    ph.created_at as sale_date
                FROM properties p
                JOIN property_price_history ph ON p.id = ph.property_id
                WHERE ph.price_type = 'sold'
                AND ph.created_at BETWEEN :start_date AND :end_date
                AND p.latitude IS NOT NULL
                AND p.longitude IS NOT NULL
                AND ph.price > 0
                ORDER BY ph.created_at
            """)
            
            result = await session.execute(query, {
                'start_date': start_date,
                'end_date': end_date
            })
            
            data = []
            for row in result.fetchall():
                data.append({
                    'property_id': row.property_id,
                    'property_type': row.property_type,
                    'suburb': row.suburb,
                    'postcode': row.postcode,
                    'bedrooms': row.bedrooms or 0,
                    'bathrooms': row.bathrooms or 0,
                    'car_spaces': row.car_spaces or 0,
                    'land_size': row.land_size or 0,
                    'building_size': row.building_size or 0,
                    'latitude': float(row.latitude),
                    'longitude': float(row.longitude),
                    'actual_price': float(row.actual_price),
                    'sale_date': row.sale_date
                })
            
            return pd.DataFrame(data)