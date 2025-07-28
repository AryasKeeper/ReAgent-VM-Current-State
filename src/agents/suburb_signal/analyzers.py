"""
Statistical Analysis Algorithms for Suburb Signal Agent

Implements sophisticated mathematical models for trend detection, price momentum analysis,
volume analysis, and market segmentation across Sydney's property markets.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum
import logging
from decimal import Decimal
import asyncio

from reagent_sydney.data.models.market_models import TrendDirection, MarketSegment


class AnalysisPeriod(str, Enum):
    """Analysis time period options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class TrendStrength(str, Enum):
    """Trend strength classification."""
    WEAK = "weak"           # 0.0 - 0.3
    MODERATE = "moderate"   # 0.3 - 0.6
    STRONG = "strong"       # 0.6 - 0.8
    VERY_STRONG = "very_strong"  # 0.8 - 1.0


@dataclass
class TrendMetrics:
    """Container for trend analysis results."""
    
    direction: TrendDirection
    strength: float  # 0.0 to 1.0
    strength_category: TrendStrength
    confidence: float  # 0.0 to 1.0
    
    # Price metrics
    current_price: Optional[Decimal] = None
    price_change: Optional[Decimal] = None
    price_change_percent: Optional[float] = None
    
    # Technical indicators
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    
    # Volume metrics
    volume_ratio: Optional[float] = None
    absorption_rate: Optional[float] = None
    
    # Momentum indicators
    momentum: Optional[float] = None
    acceleration: Optional[float] = None
    
    # Statistical measures
    volatility: Optional[float] = None
    r_squared: Optional[float] = None
    
    # Metadata
    analysis_period: Optional[AnalysisPeriod] = None
    data_points: Optional[int] = None
    calculated_at: datetime = None
    
    def __post_init__(self):
        if self.calculated_at is None:
            self.calculated_at = datetime.utcnow()
        
        # Classify strength
        if self.strength <= 0.3:
            self.strength_category = TrendStrength.WEAK
        elif self.strength <= 0.6:
            self.strength_category = TrendStrength.MODERATE
        elif self.strength <= 0.8:
            self.strength_category = TrendStrength.STRONG
        else:
            self.strength_category = TrendStrength.VERY_STRONG


@dataclass
class VolumeMetrics:
    """Container for volume analysis results."""
    
    current_volume: int
    historical_average: float
    volume_ratio: float
    velocity_index: float
    activity_score: float
    
    # Anomaly detection
    is_anomaly: bool
    z_score: float
    
    # Market dynamics
    absorption_rate: float
    inventory_turnover: float
    days_on_market_trend: float
    
    # Segmentation
    new_listings: int
    sales_volume: int
    withdrawn_listings: int
    
    analysis_period: AnalysisPeriod
    calculated_at: datetime = None
    
    def __post_init__(self):
        if self.calculated_at is None:
            self.calculated_at = datetime.utcnow()


@dataclass
class ComparativeMetrics:
    """Container for comparative analysis results."""
    
    suburb_name: str
    comparison_group: str  # 'lga', 'region', 'sydney_metro'
    
    # Rankings
    price_rank: int
    growth_rank: int
    volume_rank: int
    composite_rank: int
    
    # Scores (normalized -3 to +3 standard deviations)
    price_score: float
    growth_score: float
    volume_score: float
    composite_score: float
    
    # Percentiles
    price_percentile: float
    growth_percentile: float
    volume_percentile: float
    
    # Raw values
    median_price: Decimal
    growth_rate_12m: float
    sales_volume_30d: int
    
    # Comparison context
    total_suburbs: int
    analysis_period: AnalysisPeriod
    calculated_at: datetime = None
    
    def __post_init__(self):
        if self.calculated_at is None:
            self.calculated_at = datetime.utcnow()


class StatisticalAnalyzer:
    """
    Core statistical analysis engine for property market data.
    
    Implements mathematical models for trend detection, momentum analysis,
    and statistical measures optimized for real estate time-series data.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        
        # Configuration parameters
        self.ema_short_period = 12
        self.ema_long_period = 26
        self.macd_signal_period = 9
        self.momentum_period = 14
        self.volatility_period = 30
        
        # Thresholds
        self.trend_threshold = 0.05  # 5% change minimum for trend
        self.anomaly_threshold = 2.0  # Z-score threshold for anomalies
        self.confidence_threshold = 0.7  # Minimum confidence for signals
    
    async def calculate_price_trends(
        self, 
        price_data: pd.DataFrame,
        period: AnalysisPeriod = AnalysisPeriod.WEEKLY
    ) -> TrendMetrics:
        """
        Calculate comprehensive trend metrics using MACD and momentum indicators.
        
        Args:
            price_data: DataFrame with columns ['date', 'price', 'volume']
            period: Analysis time period
            
        Returns:
            TrendMetrics object with calculated indicators
        """
        try:
            if len(price_data) < max(self.ema_long_period, self.momentum_period):
                raise ValueError(f"Insufficient data points: {len(price_data)} required: {max(self.ema_long_period, self.momentum_period)}")
            
            # Sort by date
            df = price_data.sort_values('date').copy()
            
            # Calculate EMAs
            ema_short = self._calculate_ema(df['price'], self.ema_short_period)
            ema_long = self._calculate_ema(df['price'], self.ema_long_period)
            
            # MACD calculation
            macd = ema_short - ema_long
            macd_signal = self._calculate_ema(macd, self.macd_signal_period)
            macd_histogram = macd - macd_signal
            
            # Current values
            current_macd = macd.iloc[-1] if not macd.empty else 0
            current_signal = macd_signal.iloc[-1] if not macd_signal.empty else 0
            current_histogram = macd_histogram.iloc[-1] if not macd_histogram.empty else 0
            
            # Price momentum
            momentum = self._calculate_momentum(df['price'], self.momentum_period)
            current_momentum = momentum.iloc[-1] if not momentum.empty else 0
            
            # Price acceleration
            momentum_change = momentum.diff()
            acceleration = momentum_change.iloc[-1] if not momentum_change.empty else 0
            
            # Trend direction and strength
            direction = self._determine_trend_direction(current_macd, current_momentum)
            strength = self._calculate_trend_strength(current_macd, current_momentum, current_histogram)
            
            # Volatility
            volatility = self._calculate_volatility(df['price'], self.volatility_period)
            
            # Statistical confidence
            confidence = self._calculate_confidence(df['price'], current_macd, volatility)
            
            # Price changes
            current_price = Decimal(str(df['price'].iloc[-1]))
            if len(df) > 1:
                previous_price = df['price'].iloc[-2]
                price_change = Decimal(str(df['price'].iloc[-1] - previous_price))
                price_change_percent = float((df['price'].iloc[-1] - previous_price) / previous_price * 100)
            else:
                price_change = Decimal('0')
                price_change_percent = 0.0
            
            # Volume metrics if available
            volume_ratio = None
            absorption_rate = None
            if 'volume' in df.columns and df['volume'].notna().any():
                volume_ratio = self._calculate_volume_ratio(df['volume'])
                if 'listings' in df.columns:
                    absorption_rate = self._calculate_absorption_rate(df['volume'], df['listings'])
            
            return TrendMetrics(
                direction=direction,
                strength=strength,
                confidence=confidence,
                current_price=current_price,
                price_change=price_change,
                price_change_percent=price_change_percent,
                macd=current_macd,
                macd_signal=current_signal,
                macd_histogram=current_histogram,
                momentum=current_momentum,
                acceleration=acceleration,
                volatility=volatility,
                volume_ratio=volume_ratio,
                absorption_rate=absorption_rate,
                analysis_period=period,
                data_points=len(df)
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating price trends: {e}")
            raise
    
    async def analyze_volume_patterns(
        self,
        volume_data: pd.DataFrame,
        period: AnalysisPeriod = AnalysisPeriod.WEEKLY
    ) -> VolumeMetrics:
        """
        Analyze volume patterns and detect anomalies.
        
        Args:
            volume_data: DataFrame with columns ['date', 'volume', 'listings', 'sales']
            period: Analysis time period
            
        Returns:
            VolumeMetrics object with volume analysis
        """
        try:
            df = volume_data.sort_values('date').copy()
            
            current_volume = int(df['volume'].iloc[-1])
            historical_average = float(df['volume'].mean())
            volume_ratio = current_volume / historical_average if historical_average > 0 else 0
            
            # Calculate velocity index (sales/listings ratio)
            if 'sales' in df.columns and 'listings' in df.columns:
                sales = df['sales'].iloc[-1] if df['sales'].iloc[-1] > 0 else 0
                listings = df['listings'].iloc[-1] if df['listings'].iloc[-1] > 0 else 1
                velocity_index = sales / listings
            else:
                velocity_index = 0.5  # Default neutral value
            
            # Activity score
            activity_score = (volume_ratio + velocity_index) / 2
            
            # Anomaly detection
            z_score = self._calculate_z_score(df['volume'])
            is_anomaly = abs(z_score) > self.anomaly_threshold
            
            # Market dynamics
            absorption_rate = velocity_index  # Same as velocity for this context
            
            # Inventory turnover calculation
            if 'active_listings' in df.columns:
                avg_active = df['active_listings'].mean()
                inventory_turnover = (df['sales'].sum() / avg_active) if avg_active > 0 else 0
            else:
                inventory_turnover = velocity_index * 12  # Rough estimate
            
            # Days on market trend
            if 'days_on_market' in df.columns:
                dom_trend = self._calculate_trend_slope(df['days_on_market'])
            else:
                dom_trend = 0.0
            
            # Volume breakdown
            new_listings = int(df['listings'].iloc[-1]) if 'listings' in df.columns else 0
            sales_volume = int(df['sales'].iloc[-1]) if 'sales' in df.columns else 0
            withdrawn_listings = int(df['withdrawn'].iloc[-1]) if 'withdrawn' in df.columns else 0
            
            return VolumeMetrics(
                current_volume=current_volume,
                historical_average=historical_average,
                volume_ratio=volume_ratio,
                velocity_index=velocity_index,
                activity_score=activity_score,
                is_anomaly=is_anomaly,
                z_score=z_score,
                absorption_rate=absorption_rate,
                inventory_turnover=inventory_turnover,
                days_on_market_trend=dom_trend,
                new_listings=new_listings,
                sales_volume=sales_volume,
                withdrawn_listings=withdrawn_listings,
                analysis_period=period
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing volume patterns: {e}")
            raise
    
    async def perform_comparative_analysis(
        self,
        suburb_data: Dict[str, pd.DataFrame],
        target_suburb: str,
        comparison_type: str = "lga"
    ) -> ComparativeMetrics:
        """
        Perform comparative analysis against peer suburbs.
        
        Args:
            suburb_data: Dict mapping suburb names to their data DataFrames
            target_suburb: Name of suburb to analyze
            comparison_type: Type of comparison ('lga', 'region', 'sydney_metro')
            
        Returns:
            ComparativeMetrics object with comparative analysis
        """
        try:
            if target_suburb not in suburb_data:
                raise ValueError(f"Target suburb {target_suburb} not found in data")
            
            # Calculate metrics for all suburbs
            suburb_metrics = {}
            for suburb, data in suburb_data.items():
                if len(data) > 0:
                    median_price = data['price'].median()
                    if len(data) >= 12:  # Need at least 12 periods for 12m growth
                        growth_12m = (data['price'].iloc[-1] - data['price'].iloc[-12]) / data['price'].iloc[-12] * 100
                    else:
                        growth_12m = 0.0
                    
                    sales_30d = data['sales'].sum() if 'sales' in data.columns else 0
                    
                    suburb_metrics[suburb] = {
                        'median_price': median_price,
                        'growth_12m': growth_12m,
                        'sales_30d': sales_30d
                    }
            
            # Calculate regional statistics
            prices = [m['median_price'] for m in suburb_metrics.values()]
            growth_rates = [m['growth_12m'] for m in suburb_metrics.values()]
            volumes = [m['sales_30d'] for m in suburb_metrics.values()]
            
            price_mean, price_std = np.mean(prices), np.std(prices)
            growth_mean, growth_std = np.mean(growth_rates), np.std(growth_rates)
            volume_mean, volume_std = np.mean(volumes), np.std(volumes)
            
            # Calculate scores for target suburb
            target_metrics = suburb_metrics[target_suburb]
            
            price_score = (target_metrics['median_price'] - price_mean) / price_std if price_std > 0 else 0
            growth_score = (target_metrics['growth_12m'] - growth_mean) / growth_std if growth_std > 0 else 0
            volume_score = (target_metrics['sales_30d'] - volume_mean) / volume_std if volume_std > 0 else 0
            
            # Composite score (weighted)
            composite_score = 0.4 * price_score + 0.4 * growth_score + 0.2 * volume_score
            
            # Calculate rankings
            sorted_by_price = sorted(suburb_metrics.items(), key=lambda x: x[1]['median_price'], reverse=True)
            sorted_by_growth = sorted(suburb_metrics.items(), key=lambda x: x[1]['growth_12m'], reverse=True)
            sorted_by_volume = sorted(suburb_metrics.items(), key=lambda x: x[1]['sales_30d'], reverse=True)
            
            price_rank = next(i for i, (name, _) in enumerate(sorted_by_price, 1) if name == target_suburb)
            growth_rank = next(i for i, (name, _) in enumerate(sorted_by_growth, 1) if name == target_suburb)
            volume_rank = next(i for i, (name, _) in enumerate(sorted_by_volume, 1) if name == target_suburb)
            
            # Composite ranking
            composite_scores = {name: 0.4 * ((m['median_price'] - price_mean) / price_std if price_std > 0 else 0) + 
                                      0.4 * ((m['growth_12m'] - growth_mean) / growth_std if growth_std > 0 else 0) + 
                                      0.2 * ((m['sales_30d'] - volume_mean) / volume_std if volume_std > 0 else 0)
                              for name, m in suburb_metrics.items()}
            
            sorted_by_composite = sorted(composite_scores.items(), key=lambda x: x[1], reverse=True)
            composite_rank = next(i for i, (name, _) in enumerate(sorted_by_composite, 1) if name == target_suburb)
            
            # Calculate percentiles
            price_percentile = (len(prices) - price_rank + 1) / len(prices) * 100
            growth_percentile = (len(growth_rates) - growth_rank + 1) / len(growth_rates) * 100
            volume_percentile = (len(volumes) - volume_rank + 1) / len(volumes) * 100
            
            return ComparativeMetrics(
                suburb_name=target_suburb,
                comparison_group=comparison_type,
                price_rank=price_rank,
                growth_rank=growth_rank,
                volume_rank=volume_rank,
                composite_rank=composite_rank,
                price_score=price_score,
                growth_score=growth_score,
                volume_score=volume_score,
                composite_score=composite_score,
                price_percentile=price_percentile,
                growth_percentile=growth_percentile,
                volume_percentile=volume_percentile,
                median_price=Decimal(str(target_metrics['median_price'])),
                growth_rate_12m=target_metrics['growth_12m'],
                sales_volume_30d=target_metrics['sales_30d'],
                total_suburbs=len(suburb_metrics),
                analysis_period=AnalysisPeriod.MONTHLY
            )
            
        except Exception as e:
            self.logger.error(f"Error in comparative analysis: {e}")
            raise
    
    # Private helper methods
    
    def _calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return prices.ewm(span=period, adjust=False).mean()
    
    def _calculate_momentum(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate price momentum."""
        return (prices - prices.shift(period)) / prices.shift(period) * 100
    
    def _calculate_volatility(self, prices: pd.Series, period: int) -> float:
        """Calculate price volatility (standard deviation of returns)."""
        returns = prices.pct_change().dropna()
        if len(returns) >= period:
            return float(returns.rolling(window=period).std().iloc[-1] * 100)
        return 0.0
    
    def _determine_trend_direction(self, macd: float, momentum: float) -> TrendDirection:
        """Determine trend direction based on MACD and momentum."""
        if macd > 0 and momentum > 0:
            return TrendDirection.UP
        elif macd < 0 and momentum < 0:
            return TrendDirection.DOWN
        elif abs(macd) < 0.01 and abs(momentum) < 1.0:  # Small thresholds
            return TrendDirection.STABLE
        else:
            return TrendDirection.VOLATILE
    
    def _calculate_trend_strength(self, macd: float, momentum: float, histogram: float) -> float:
        """Calculate trend strength (0.0 to 1.0)."""
        # Normalize MACD and momentum contributions
        macd_strength = min(abs(macd) / 10.0, 1.0)  # Normalize to reasonable scale
        momentum_strength = min(abs(momentum) / 20.0, 1.0)  # Normalize momentum
        histogram_strength = min(abs(histogram) / 5.0, 1.0)  # Histogram contribution
        
        # Weighted combination
        strength = (0.4 * macd_strength + 0.4 * momentum_strength + 0.2 * histogram_strength)
        return min(strength, 1.0)
    
    def _calculate_confidence(self, prices: pd.Series, macd: float, volatility: float) -> float:
        """Calculate confidence score based on data quality and signal strength."""
        # Data quality score based on number of data points
        data_quality = min(len(prices) / 30.0, 1.0)  # Ideal: 30+ data points
        
        # Signal strength
        signal_strength = min(abs(macd) / 5.0, 1.0)
        
        # Volatility penalty (high volatility reduces confidence)
        volatility_factor = max(0.2, 1.0 - (volatility / 50.0))  # Normalize volatility
        
        confidence = data_quality * signal_strength * volatility_factor
        return min(confidence, 1.0)
    
    def _calculate_volume_ratio(self, volumes: pd.Series) -> float:
        """Calculate current volume vs historical average ratio."""
        if len(volumes) > 1:
            current = volumes.iloc[-1]
            historical_avg = volumes.iloc[:-1].mean()
            return current / historical_avg if historical_avg > 0 else 1.0
        return 1.0
    
    def _calculate_absorption_rate(self, sales: pd.Series, listings: pd.Series) -> float:
        """Calculate absorption rate (sales/listings)."""
        if len(sales) > 0 and len(listings) > 0:
            total_sales = sales.sum()
            total_listings = listings.sum()
            return total_sales / total_listings if total_listings > 0 else 0.0
        return 0.0
    
    def _calculate_z_score(self, data: pd.Series) -> float:
        """Calculate Z-score for anomaly detection."""
        if len(data) > 1:
            current = data.iloc[-1]
            mean = data.mean()
            std = data.std()
            return (current - mean) / std if std > 0 else 0.0
        return 0.0
    
    def _calculate_trend_slope(self, data: pd.Series) -> float:
        """Calculate trend slope using linear regression."""
        if len(data) < 3:
            return 0.0
        
        x = np.arange(len(data))
        y = data.values
        
        # Simple linear regression
        n = len(x)
        sum_xy = np.sum(x * y)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_x2 = np.sum(x * x)
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope


class TrendDetector:
    """
    Advanced trend detection engine with configurable parameters.
    
    Detects various types of trends: short-term momentum, medium-term cycles,
    long-term growth patterns, and seasonal variations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize statistical analyzer
        self.analyzer = StatisticalAnalyzer(self.logger)
        
        # Configurable parameters
        self.short_term_window = self.config.get('short_term_window', 7)   # 1 week
        self.medium_term_window = self.config.get('medium_term_window', 30)  # 1 month
        self.long_term_window = self.config.get('long_term_window', 90)   # 3 months
        
        # Detection thresholds
        self.significance_threshold = self.config.get('significance_threshold', 0.05)
        self.trend_threshold = self.config.get('trend_threshold', 0.02)  # 2% minimum change
        self.confidence_threshold = self.config.get('confidence_threshold', 0.7)
    
    async def detect_multi_timeframe_trends(
        self,
        data: pd.DataFrame,
        suburb: str
    ) -> Dict[str, TrendMetrics]:
        """
        Detect trends across multiple timeframes.
        
        Args:
            data: Property data DataFrame
            suburb: Suburb name for context
            
        Returns:
            Dict mapping timeframe to TrendMetrics
        """
        trends = {}
        
        try:
            # Short-term trend (1 week)
            if len(data) >= self.short_term_window:
                short_data = data.tail(self.short_term_window)
                trends['short_term'] = await self.analyzer.calculate_price_trends(
                    short_data, AnalysisPeriod.DAILY
                )
            
            # Medium-term trend (1 month)
            if len(data) >= self.medium_term_window:
                medium_data = data.tail(self.medium_term_window)
                trends['medium_term'] = await self.analyzer.calculate_price_trends(
                    medium_data, AnalysisPeriod.WEEKLY
                )
            
            # Long-term trend (3 months)
            if len(data) >= self.long_term_window:
                long_data = data.tail(self.long_term_window)
                trends['long_term'] = await self.analyzer.calculate_price_trends(
                    long_data, AnalysisPeriod.MONTHLY
                )
            
            self.logger.info(f"Detected trends for {suburb} across {len(trends)} timeframes")
            
        except Exception as e:
            self.logger.error(f"Error detecting trends for {suburb}: {e}")
            raise
        
        return trends
    
    async def detect_trend_changes(
        self,
        current_trends: Dict[str, TrendMetrics],
        historical_trends: Dict[str, List[TrendMetrics]]
    ) -> Dict[str, bool]:
        """
        Detect significant changes in trend patterns.
        
        Args:
            current_trends: Current trend analysis
            historical_trends: Historical trend data for comparison
            
        Returns:
            Dict indicating which timeframes show significant changes
        """
        changes = {}
        
        for timeframe, current in current_trends.items():
            if timeframe in historical_trends and historical_trends[timeframe]:
                previous = historical_trends[timeframe][-1]  # Most recent historical
                
                # Check for direction change
                direction_changed = current.direction != previous.direction
                
                # Check for significant strength change
                strength_change = abs(current.strength - previous.strength) > 0.3
                
                # Check for confidence change
                confidence_change = abs(current.confidence - previous.confidence) > 0.2
                
                # Overall change assessment
                changes[timeframe] = direction_changed or strength_change or confidence_change
            else:
                changes[timeframe] = True  # New trend data always considered a change
        
        return changes


class AnomalyDetector:
    """
    Anomaly detection for property market data.
    
    Detects unusual patterns in price movements, volume spikes,
    and other market anomalies that may indicate opportunities or risks.
    """
    
    def __init__(self, sensitivity: float = 2.0):
        self.sensitivity = sensitivity  # Z-score threshold
        self.logger = logging.getLogger(__name__)
    
    async def detect_price_anomalies(
        self,
        price_data: pd.DataFrame,
        lookback_period: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Detect price anomalies using statistical methods.
        
        Args:
            price_data: DataFrame with price history
            lookback_period: Number of periods to look back for baseline
            
        Returns:
            List of detected anomalies with details
        """
        anomalies = []
        
        try:
            if len(price_data) < lookback_period:
                return anomalies
            
            # Calculate rolling statistics
            prices = price_data['price']
            rolling_mean = prices.rolling(window=lookback_period).mean()
            rolling_std = prices.rolling(window=lookback_period).std()
            
            # Calculate Z-scores
            z_scores = (prices - rolling_mean) / rolling_std
            
            # Identify anomalies
            anomaly_indices = z_scores.abs() > self.sensitivity
            
            for idx in z_scores[anomaly_indices].index:
                anomaly_data = {
                    'date': price_data.loc[idx, 'date'],
                    'price': price_data.loc[idx, 'price'],
                    'z_score': z_scores.loc[idx],
                    'expected_range': {
                        'lower': rolling_mean.loc[idx] - self.sensitivity * rolling_std.loc[idx],
                        'upper': rolling_mean.loc[idx] + self.sensitivity * rolling_std.loc[idx]
                    },
                    'anomaly_type': 'price_spike' if z_scores.loc[idx] > 0 else 'price_drop',
                    'severity': min(abs(z_scores.loc[idx]) / self.sensitivity, 3.0)
                }
                anomalies.append(anomaly_data)
            
            self.logger.info(f"Detected {len(anomalies)} price anomalies")
            
        except Exception as e:
            self.logger.error(f"Error detecting price anomalies: {e}")
            raise
        
        return anomalies
    
    async def detect_volume_anomalies(
        self,
        volume_data: pd.DataFrame,
        lookback_period: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Detect volume anomalies.
        
        Args:
            volume_data: DataFrame with volume history
            lookback_period: Number of periods for baseline
            
        Returns:
            List of volume anomalies
        """
        anomalies = []
        
        try:
            if 'volume' not in volume_data.columns or len(volume_data) < lookback_period:
                return anomalies
            
            volumes = volume_data['volume']
            rolling_mean = volumes.rolling(window=lookback_period).mean()
            rolling_std = volumes.rolling(window=lookback_period).std()
            
            # Volume Z-scores
            z_scores = (volumes - rolling_mean) / rolling_std
            anomaly_indices = z_scores.abs() > self.sensitivity
            
            for idx in z_scores[anomaly_indices].index:
                anomaly_data = {
                    'date': volume_data.loc[idx, 'date'],
                    'volume': volume_data.loc[idx, 'volume'],
                    'z_score': z_scores.loc[idx],
                    'expected_volume': rolling_mean.loc[idx],
                    'anomaly_type': 'volume_surge' if z_scores.loc[idx] > 0 else 'volume_drought',
                    'severity': min(abs(z_scores.loc[idx]) / self.sensitivity, 3.0)
                }
                anomalies.append(anomaly_data)
            
            self.logger.info(f"Detected {len(anomalies)} volume anomalies")
            
        except Exception as e:
            self.logger.error(f"Error detecting volume anomalies: {e}")
            raise
        
        return anomalies