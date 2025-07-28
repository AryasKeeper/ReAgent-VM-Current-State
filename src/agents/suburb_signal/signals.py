"""
Signal Generation and Alert Management for Suburb Signal Agent

Implements intelligent signal generation with confidence scoring, threshold management,
and automated alert systems for market opportunities and risks.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
from decimal import Decimal

from .analyzers import TrendMetrics, VolumeMetrics, ComparativeMetrics, TrendDirection, TrendStrength


class SignalType(str, Enum):
    """Types of market signals."""
    TREND_CHANGE = "trend_change"
    MOMENTUM_SHIFT = "momentum_shift"
    VOLUME_ANOMALY = "volume_anomaly"
    PRICE_BREAKOUT = "price_breakout"
    OPPORTUNITY = "opportunity"
    RISK_WARNING = "risk_warning"
    COMPARATIVE_SHIFT = "comparative_shift"
    SEASONAL_PATTERN = "seasonal_pattern"


class SignalStrength(str, Enum):
    """Signal strength levels."""
    WEAK = "weak"           # 0.0 - 0.4
    MODERATE = "moderate"   # 0.4 - 0.6
    STRONG = "strong"       # 0.6 - 0.8
    VERY_STRONG = "very_strong"  # 0.8 - 1.0


class AlertPriority(str, Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MarketSignal:
    """Container for market signal data."""
    
    signal_id: str
    signal_type: SignalType
    suburb_name: str
    strength: float  # 0.0 to 1.0
    strength_category: SignalStrength
    confidence: float  # 0.0 to 1.0
    
    # Signal description
    title: str
    description: str
    implications: str
    
    # Supporting data
    current_value: Optional[Union[Decimal, float, int]] = None
    previous_value: Optional[Union[Decimal, float, int]] = None
    change_value: Optional[Union[Decimal, float]] = None
    change_percent: Optional[float] = None
    
    # Thresholds and triggers
    trigger_threshold: Optional[float] = None
    next_threshold: Optional[float] = None
    
    # Metadata
    data_sources: List[str] = field(default_factory=list)
    analysis_period: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Supporting metrics
    supporting_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Classify strength
        if self.strength <= 0.4:
            self.strength_category = SignalStrength.WEAK
        elif self.strength <= 0.6:
            self.strength_category = SignalStrength.MODERATE
        elif self.strength <= 0.8:
            self.strength_category = SignalStrength.STRONG
        else:
            self.strength_category = SignalStrength.VERY_STRONG
    
    @property
    def is_actionable(self) -> bool:
        """Check if signal is actionable (high confidence and strength)."""
        return self.confidence >= 0.7 and self.strength >= 0.6
    
    @property
    def is_expired(self) -> bool:
        """Check if signal has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class MarketAlert:
    """Container for market alert data."""
    
    alert_id: str
    alert_type: SignalType
    priority: AlertPriority
    suburb_name: str
    
    # Alert content
    title: str
    message: str
    recommended_actions: List[str]
    
    # Triggering signal
    triggering_signal: MarketSignal
    related_signals: List[MarketSignal] = field(default_factory=list)
    
    # Alert metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    
    # Delivery tracking
    delivery_channels: List[str] = field(default_factory=list)
    delivered_at: Optional[datetime] = None
    
    @property
    def is_active(self) -> bool:
        """Check if alert is still active."""
        return self.resolved_at is None
    
    @property
    def age_hours(self) -> float:
        """Get alert age in hours."""
        return (datetime.utcnow() - self.created_at).total_seconds() / 3600


class SignalGenerator:
    """
    Advanced signal generation engine with confidence scoring.
    
    Analyzes market data and generates actionable signals with quantified
    confidence levels and supporting evidence.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Signal generation thresholds
        self.min_confidence = self.config.get('min_confidence', 0.6)
        self.min_strength = self.config.get('min_strength', 0.4)
        
        # Trend change thresholds
        self.trend_change_threshold = self.config.get('trend_change_threshold', 0.05)  # 5%
        self.momentum_threshold = self.config.get('momentum_threshold', 0.1)  # 10%
        
        # Volume thresholds
        self.volume_spike_threshold = self.config.get('volume_spike_threshold', 2.0)  # 2x normal
        self.volume_drought_threshold = self.config.get('volume_drought_threshold', 0.5)  # 0.5x normal
        
        # Price breakout thresholds
        self.price_breakout_threshold = self.config.get('price_breakout_threshold', 0.15)  # 15%
        
        # Signal expiry times (hours)
        self.signal_expiry = {
            SignalType.TREND_CHANGE: 168,      # 1 week
            SignalType.MOMENTUM_SHIFT: 72,     # 3 days
            SignalType.VOLUME_ANOMALY: 24,     # 1 day
            SignalType.PRICE_BREAKOUT: 48,     # 2 days
            SignalType.OPPORTUNITY: 120,       # 5 days
            SignalType.RISK_WARNING: 336,      # 2 weeks
            SignalType.COMPARATIVE_SHIFT: 168, # 1 week
            SignalType.SEASONAL_PATTERN: 720   # 30 days
        }
    
    async def generate_trend_signals(
        self,
        suburb: str,
        current_trends: Dict[str, TrendMetrics],
        historical_trends: Optional[Dict[str, List[TrendMetrics]]] = None
    ) -> List[MarketSignal]:
        """
        Generate trend-based signals.
        
        Args:
            suburb: Suburb name
            current_trends: Current trend analysis
            historical_trends: Historical trend data for comparison
            
        Returns:
            List of generated signals
        """
        signals = []
        
        try:
            for timeframe, trend in current_trends.items():
                # Trend change signals
                if historical_trends and timeframe in historical_trends:
                    trend_signals = await self._detect_trend_changes(
                        suburb, timeframe, trend, historical_trends[timeframe]
                    )
                    signals.extend(trend_signals)
                
                # Momentum signals
                momentum_signals = await self._detect_momentum_shifts(
                    suburb, timeframe, trend
                )
                signals.extend(momentum_signals)
                
                # Strength-based signals
                strength_signals = await self._detect_strength_changes(
                    suburb, timeframe, trend
                )
                signals.extend(strength_signals)
            
            self.logger.info(f"Generated {len(signals)} trend signals for {suburb}")
            
        except Exception as e:
            self.logger.error(f"Error generating trend signals for {suburb}: {e}")
            raise
        
        return signals
    
    async def generate_volume_signals(
        self,
        suburb: str,
        volume_metrics: VolumeMetrics,
        historical_volumes: Optional[List[VolumeMetrics]] = None
    ) -> List[MarketSignal]:
        """
        Generate volume-based signals.
        
        Args:
            suburb: Suburb name
            volume_metrics: Current volume analysis
            historical_volumes: Historical volume data
            
        Returns:
            List of volume signals
        """
        signals = []
        
        try:
            # Volume anomaly signals
            if volume_metrics.is_anomaly:
                signal = await self._create_volume_anomaly_signal(suburb, volume_metrics)
                if signal:
                    signals.append(signal)
            
            # Activity level signals
            activity_signals = await self._detect_activity_changes(
                suburb, volume_metrics, historical_volumes
            )
            signals.extend(activity_signals)
            
            # Absorption rate signals
            absorption_signals = await self._detect_absorption_changes(
                suburb, volume_metrics, historical_volumes
            )
            signals.extend(absorption_signals)
            
            self.logger.info(f"Generated {len(signals)} volume signals for {suburb}")
            
        except Exception as e:
            self.logger.error(f"Error generating volume signals for {suburb}: {e}")
            raise
        
        return signals
    
    async def generate_comparative_signals(
        self,
        suburb: str,
        comparative_metrics: ComparativeMetrics,
        historical_comparatives: Optional[List[ComparativeMetrics]] = None
    ) -> List[MarketSignal]:
        """
        Generate comparative analysis signals.
        
        Args:
            suburb: Suburb name
            comparative_metrics: Current comparative analysis
            historical_comparatives: Historical comparative data
            
        Returns:
            List of comparative signals
        """
        signals = []
        
        try:
            # Ranking change signals
            if historical_comparatives:
                ranking_signals = await self._detect_ranking_changes(
                    suburb, comparative_metrics, historical_comparatives
                )
                signals.extend(ranking_signals)
            
            # Performance signals
            performance_signals = await self._detect_performance_signals(
                suburb, comparative_metrics
            )
            signals.extend(performance_signals)
            
            # Opportunity signals
            opportunity_signals = await self._detect_opportunity_signals(
                suburb, comparative_metrics
            )
            signals.extend(opportunity_signals)
            
            self.logger.info(f"Generated {len(signals)} comparative signals for {suburb}")
            
        except Exception as e:
            self.logger.error(f"Error generating comparative signals for {suburb}: {e}")
            raise
        
        return signals
    
    async def generate_composite_signals(
        self,
        suburb: str,
        trend_metrics: Dict[str, TrendMetrics],
        volume_metrics: VolumeMetrics,
        comparative_metrics: ComparativeMetrics
    ) -> List[MarketSignal]:
        """
        Generate composite signals based on multiple data sources.
        
        Args:
            suburb: Suburb name
            trend_metrics: Trend analysis data
            volume_metrics: Volume analysis data
            comparative_metrics: Comparative analysis data
            
        Returns:
            List of composite signals
        """
        signals = []
        
        try:
            # Market opportunity signals
            opportunity_signals = await self._detect_market_opportunities(
                suburb, trend_metrics, volume_metrics, comparative_metrics
            )
            signals.extend(opportunity_signals)
            
            # Risk warning signals
            risk_signals = await self._detect_risk_warnings(
                suburb, trend_metrics, volume_metrics, comparative_metrics
            )
            signals.extend(risk_signals)
            
            # Breakout signals
            breakout_signals = await self._detect_breakout_patterns(
                suburb, trend_metrics, volume_metrics, comparative_metrics
            )
            signals.extend(breakout_signals)
            
            self.logger.info(f"Generated {len(signals)} composite signals for {suburb}")
            
        except Exception as e:
            self.logger.error(f"Error generating composite signals for {suburb}: {e}")
            raise
        
        return signals
    
    # Private signal generation methods
    
    async def _detect_trend_changes(
        self,
        suburb: str,
        timeframe: str,
        current: TrendMetrics,
        historical: List[TrendMetrics]
    ) -> List[MarketSignal]:
        """Detect trend direction changes."""
        signals = []
        
        if not historical:
            return signals
        
        previous = historical[-1]
        
        # Direction change detection
        if current.direction != previous.direction:
            # Calculate signal strength based on confidence and trend strength
            strength = (current.confidence + current.strength) / 2
            
            if strength >= self.min_strength:
                signal = MarketSignal(
                    signal_id=f"trend_change_{suburb}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    signal_type=SignalType.TREND_CHANGE,
                    suburb_name=suburb,
                    strength=strength,
                    confidence=current.confidence,
                    title=f"Trend Direction Change in {suburb}",
                    description=f"{timeframe.title()} trend changed from {previous.direction.value} to {current.direction.value}",
                    implications=self._get_trend_change_implications(previous.direction, current.direction),
                    current_value=current.current_price,
                    previous_value=previous.current_price,
                    change_percent=current.price_change_percent,
                    data_sources=["property_price_history", "market_trends"],
                    analysis_period=timeframe,
                    expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.TREND_CHANGE]),
                    supporting_metrics={
                        "current_macd": current.macd,
                        "previous_macd": previous.macd,
                        "current_momentum": current.momentum,
                        "previous_momentum": previous.momentum,
                        "confidence_change": current.confidence - previous.confidence
                    }
                )
                signals.append(signal)
        
        return signals
    
    async def _detect_momentum_shifts(
        self,
        suburb: str,
        timeframe: str,
        trend: TrendMetrics
    ) -> List[MarketSignal]:
        """Detect momentum shifts."""
        signals = []
        
        if trend.momentum is None or trend.acceleration is None:
            return signals
        
        # Strong momentum detection
        if abs(trend.momentum) > self.momentum_threshold and trend.confidence > self.min_confidence:
            strength = min(abs(trend.momentum) / 20.0, 1.0) * trend.confidence
            
            if strength >= self.min_strength:
                signal = MarketSignal(
                    signal_id=f"momentum_{suburb}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    signal_type=SignalType.MOMENTUM_SHIFT,
                    suburb_name=suburb,
                    strength=strength,
                    confidence=trend.confidence,
                    title=f"Strong Momentum Detected in {suburb}",
                    description=f"Significant {trend.direction.value.lower()} momentum in {timeframe} analysis",
                    implications=self._get_momentum_implications(trend.momentum, trend.acceleration),
                    current_value=trend.momentum,
                    analysis_period=timeframe,
                    expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.MOMENTUM_SHIFT]),
                    supporting_metrics={
                        "momentum": trend.momentum,
                        "acceleration": trend.acceleration,
                        "macd": trend.macd,
                        "trend_strength": trend.strength
                    }
                )
                signals.append(signal)
        
        return signals
    
    async def _detect_strength_changes(
        self,
        suburb: str,
        timeframe: str,
        trend: TrendMetrics
    ) -> List[MarketSignal]:
        """Detect changes in trend strength."""
        signals = []
        
        # Very strong trend detection
        if trend.strength >= 0.8 and trend.confidence > self.min_confidence:
            signal = MarketSignal(
                signal_id=f"strong_trend_{suburb}_{timeframe}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                signal_type=SignalType.TREND_CHANGE,
                suburb_name=suburb,
                strength=trend.strength,
                confidence=trend.confidence,
                title=f"Very Strong Trend in {suburb}",
                description=f"Exceptionally strong {trend.direction.value.lower()} trend detected",
                implications=f"High probability of continued {trend.direction.value.lower()} movement",
                current_value=trend.strength,
                analysis_period=timeframe,
                expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.TREND_CHANGE]),
                supporting_metrics={
                    "trend_strength": trend.strength,
                    "trend_direction": trend.direction.value,
                    "confidence": trend.confidence,
                    "volatility": trend.volatility
                }
            )
            signals.append(signal)
        
        return signals
    
    async def _create_volume_anomaly_signal(
        self,
        suburb: str,
        volume_metrics: VolumeMetrics
    ) -> Optional[MarketSignal]:
        """Create volume anomaly signal."""
        if not volume_metrics.is_anomaly:
            return None
        
        # Determine anomaly type and strength
        is_surge = volume_metrics.z_score > 0
        strength = min(abs(volume_metrics.z_score) / 3.0, 1.0)  # Normalize to 0-1
        
        if strength < self.min_strength:
            return None
        
        anomaly_type = "surge" if is_surge else "drought"
        
        signal = MarketSignal(
            signal_id=f"volume_{anomaly_type}_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            signal_type=SignalType.VOLUME_ANOMALY,
            suburb_name=suburb,
            strength=strength,
            confidence=min(strength, 0.9),  # High confidence for clear anomalies
            title=f"Volume {anomaly_type.title()} in {suburb}",
            description=f"Unusual {anomaly_type} in property activity detected",
            implications=self._get_volume_anomaly_implications(is_surge, volume_metrics),
            current_value=volume_metrics.current_volume,
            previous_value=volume_metrics.historical_average,
            change_percent=(volume_metrics.volume_ratio - 1) * 100,
            data_sources=["property_listings", "sales_data"],
            analysis_period=volume_metrics.analysis_period.value,
            expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.VOLUME_ANOMALY]),
            supporting_metrics={
                "z_score": volume_metrics.z_score,
                "volume_ratio": volume_metrics.volume_ratio,
                "activity_score": volume_metrics.activity_score,
                "absorption_rate": volume_metrics.absorption_rate
            }
        )
        
        return signal
    
    async def _detect_activity_changes(
        self,
        suburb: str,
        current: VolumeMetrics,
        historical: Optional[List[VolumeMetrics]]
    ) -> List[MarketSignal]:
        """Detect significant changes in activity levels."""
        signals = []
        
        if not historical:
            return signals
        
        # Compare with recent historical data
        recent_activity = np.mean([h.activity_score for h in historical[-5:]])  # Last 5 periods
        activity_change = current.activity_score - recent_activity
        
        if abs(activity_change) > 0.3:  # 30% change threshold
            strength = min(abs(activity_change), 1.0)
            
            if strength >= self.min_strength:
                change_type = "increase" if activity_change > 0 else "decrease"
                
                signal = MarketSignal(
                    signal_id=f"activity_{change_type}_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    signal_type=SignalType.VOLUME_ANOMALY,
                    suburb_name=suburb,
                    strength=strength,
                    confidence=0.8,
                    title=f"Market Activity {change_type.title()} in {suburb}",
                    description=f"Significant {change_type} in overall market activity",
                    implications=self._get_activity_change_implications(change_type, activity_change),
                    current_value=current.activity_score,
                    previous_value=recent_activity,
                    change_percent=activity_change * 100,
                    analysis_period=current.analysis_period.value,
                    expires_at=datetime.utcnow() + timedelta(hours=48),
                    supporting_metrics={
                        "activity_change": activity_change,
                        "current_activity": current.activity_score,
                        "historical_average": recent_activity
                    }
                )
                signals.append(signal)
        
        return signals
    
    async def _detect_absorption_changes(
        self,
        suburb: str,
        current: VolumeMetrics,
        historical: Optional[List[VolumeMetrics]]
    ) -> List[MarketSignal]:
        """Detect changes in absorption rate."""
        signals = []
        
        if not historical or current.absorption_rate is None:
            return signals
        
        # Historical absorption rate
        historical_absorption = np.mean([h.absorption_rate for h in historical[-5:] if h.absorption_rate is not None])
        
        if historical_absorption > 0:
            absorption_change = (current.absorption_rate - historical_absorption) / historical_absorption
            
            if abs(absorption_change) > 0.25:  # 25% change threshold
                strength = min(abs(absorption_change), 1.0)
                
                if strength >= self.min_strength:
                    change_type = "improvement" if absorption_change > 0 else "deterioration"
                    
                    signal = MarketSignal(
                        signal_id=f"absorption_{change_type}_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        signal_type=SignalType.VOLUME_ANOMALY,
                        suburb_name=suburb,
                        strength=strength,
                        confidence=0.75,
                        title=f"Absorption Rate {change_type.title()} in {suburb}",
                        description=f"Significant {change_type} in market absorption rate",
                        implications=self._get_absorption_implications(change_type, absorption_change),
                        current_value=current.absorption_rate,
                        previous_value=historical_absorption,
                        change_percent=absorption_change * 100,
                        analysis_period=current.analysis_period.value,
                        expires_at=datetime.utcnow() + timedelta(hours=72),
                        supporting_metrics={
                            "absorption_change": absorption_change,
                            "current_absorption": current.absorption_rate,
                            "historical_absorption": historical_absorption
                        }
                    )
                    signals.append(signal)
        
        return signals
    
    async def _detect_ranking_changes(
        self,
        suburb: str,
        current: ComparativeMetrics,
        historical: List[ComparativeMetrics]
    ) -> List[MarketSignal]:
        """Detect significant ranking changes."""
        signals = []
        
        if not historical:
            return signals
        
        previous = historical[-1]
        
        # Check for significant ranking improvements/declines
        ranking_changes = {
            'composite': previous.composite_rank - current.composite_rank,
            'price': previous.price_rank - current.price_rank,
            'growth': previous.growth_rank - current.growth_rank,
            'volume': previous.volume_rank - current.volume_rank
        }
        
        for metric, change in ranking_changes.items():
            if abs(change) >= 5:  # Significant ranking change
                strength = min(abs(change) / 20.0, 1.0)  # Normalize based on ranking change
                
                if strength >= self.min_strength:
                    change_type = "improvement" if change > 0 else "decline"
                    
                    signal = MarketSignal(
                        signal_id=f"ranking_{metric}_{change_type}_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        signal_type=SignalType.COMPARATIVE_SHIFT,
                        suburb_name=suburb,
                        strength=strength,
                        confidence=0.8,
                        title=f"{metric.title()} Ranking {change_type.title()} in {suburb}",
                        description=f"Significant {change_type} in {metric} ranking relative to peers",
                        implications=self._get_ranking_implications(metric, change_type, change),
                        current_value=getattr(current, f"{metric}_rank"),
                        previous_value=getattr(previous, f"{metric}_rank"),
                        change_value=change,
                        analysis_period=current.analysis_period.value,
                        expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.COMPARATIVE_SHIFT]),
                        supporting_metrics={
                            f"{metric}_rank_change": change,
                            f"current_{metric}_rank": getattr(current, f"{metric}_rank"),
                            f"previous_{metric}_rank": getattr(previous, f"{metric}_rank"),
                            "total_suburbs": current.total_suburbs
                        }
                    )
                    signals.append(signal)
        
        return signals
    
    async def _detect_performance_signals(
        self,
        suburb: str,
        comparative: ComparativeMetrics
    ) -> List[MarketSignal]:
        """Detect outstanding performance signals."""
        signals = []
        
        # Top performer detection
        if comparative.composite_rank <= 5:  # Top 5 performer
            strength = max(0.6, 1.0 - (comparative.composite_rank - 1) / 10.0)
            
            signal = MarketSignal(
                signal_id=f"top_performer_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                signal_type=SignalType.OPPORTUNITY,
                suburb_name=suburb,
                strength=strength,
                confidence=0.85,
                title=f"Top Market Performer: {suburb}",
                description=f"Ranked #{comparative.composite_rank} out of {comparative.total_suburbs} suburbs",
                implications="Strong market performance suggests continued investor interest",
                current_value=comparative.composite_rank,
                analysis_period=comparative.analysis_period.value,
                expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.OPPORTUNITY]),
                supporting_metrics={
                    "composite_score": comparative.composite_score,
                    "price_percentile": comparative.price_percentile,
                    "growth_percentile": comparative.growth_percentile,
                    "volume_percentile": comparative.volume_percentile
                }
            )
            signals.append(signal)
        
        # Underperformer detection
        elif comparative.composite_rank > comparative.total_suburbs * 0.8:  # Bottom 20%
            strength = min(0.8, (comparative.composite_rank - comparative.total_suburbs * 0.8) / (comparative.total_suburbs * 0.2))
            
            signal = MarketSignal(
                signal_id=f"underperformer_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                signal_type=SignalType.RISK_WARNING,
                suburb_name=suburb,
                strength=strength,
                confidence=0.75,
                title=f"Market Underperformer: {suburb}",
                description=f"Ranked #{comparative.composite_rank} out of {comparative.total_suburbs} suburbs",
                implications="Below-average performance may indicate market challenges",
                current_value=comparative.composite_rank,
                analysis_period=comparative.analysis_period.value,
                expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.RISK_WARNING]),
                supporting_metrics={
                    "composite_score": comparative.composite_score,
                    "price_percentile": comparative.price_percentile,
                    "growth_percentile": comparative.growth_percentile,
                    "volume_percentile": comparative.volume_percentile
                }
            )
            signals.append(signal)
        
        return signals
    
    async def _detect_opportunity_signals(
        self,
        suburb: str,
        comparative: ComparativeMetrics
    ) -> List[MarketSignal]:
        """Detect market opportunity signals."""
        signals = []
        
        # Value opportunity (low price, high growth)
        if (comparative.price_percentile < 40 and  # Below average price
            comparative.growth_percentile > 70):   # Above average growth
            
            strength = (comparative.growth_percentile - comparative.price_percentile) / 100.0
            
            if strength >= 0.3:
                signal = MarketSignal(
                    signal_id=f"value_opportunity_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    signal_type=SignalType.OPPORTUNITY,
                    suburb_name=suburb,
                    strength=strength,
                    confidence=0.75,
                    title=f"Value Opportunity in {suburb}",
                    description="Below-average prices with above-average growth potential",
                    implications="Potential for capital appreciation with relatively lower entry cost",
                    current_value=comparative.median_price,
                    analysis_period=comparative.analysis_period.value,
                    expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.OPPORTUNITY]),
                    supporting_metrics={
                        "price_percentile": comparative.price_percentile,
                        "growth_percentile": comparative.growth_percentile,
                        "growth_rate_12m": comparative.growth_rate_12m,
                        "value_score": strength
                    }
                )
                signals.append(signal)
        
        return signals
    
    async def _detect_market_opportunities(
        self,
        suburb: str,
        trend_metrics: Dict[str, TrendMetrics],
        volume_metrics: VolumeMetrics,
        comparative_metrics: ComparativeMetrics
    ) -> List[MarketSignal]:
        """Detect composite market opportunities."""
        signals = []
        
        # Multi-factor opportunity analysis
        factors = []
        
        # Strong upward trends
        if 'medium_term' in trend_metrics:
            trend = trend_metrics['medium_term']
            if trend.direction == TrendDirection.UP and trend.strength > 0.6:
                factors.append(('trend', trend.strength * trend.confidence))
        
        # High activity
        if volume_metrics.activity_score > 0.7:
            factors.append(('volume', volume_metrics.activity_score))
        
        # Good comparative position
        if comparative_metrics.composite_percentile > 60:
            factors.append(('comparative', comparative_metrics.composite_percentile / 100.0))
        
        if len(factors) >= 2:  # Multiple positive factors
            strength = np.mean([f[1] for f in factors])
            
            if strength >= 0.6:
                signal = MarketSignal(
                    signal_id=f"market_opportunity_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    signal_type=SignalType.OPPORTUNITY,
                    suburb_name=suburb,
                    strength=strength,
                    confidence=0.8,
                    title=f"Strong Market Opportunity in {suburb}",
                    description="Multiple positive factors align for market opportunity",
                    implications="Favorable conditions across trend, volume, and comparative metrics",
                    analysis_period="composite",
                    expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.OPPORTUNITY]),
                    supporting_metrics={
                        "positive_factors": [f[0] for f in factors],
                        "factor_scores": {f[0]: f[1] for f in factors},
                        "composite_strength": strength
                    }
                )
                signals.append(signal)
        
        return signals
    
    async def _detect_risk_warnings(
        self,
        suburb: str,
        trend_metrics: Dict[str, TrendMetrics],
        volume_metrics: VolumeMetrics,
        comparative_metrics: ComparativeMetrics
    ) -> List[MarketSignal]:
        """Detect composite risk warnings."""
        signals = []
        
        # Multi-factor risk analysis
        risk_factors = []
        
        # Declining trends
        if 'medium_term' in trend_metrics:
            trend = trend_metrics['medium_term']
            if trend.direction == TrendDirection.DOWN and trend.strength > 0.5:
                risk_factors.append(('declining_trend', trend.strength * trend.confidence))
        
        # Low activity
        if volume_metrics.activity_score < 0.3:
            risk_factors.append(('low_activity', 1.0 - volume_metrics.activity_score))
        
        # Poor comparative position
        if comparative_metrics.composite_percentile < 30:
            risk_factors.append(('poor_performance', 1.0 - comparative_metrics.composite_percentile / 100.0))
        
        # High volatility
        if 'short_term' in trend_metrics and trend_metrics['short_term'].volatility and trend_metrics['short_term'].volatility > 20:
            risk_factors.append(('high_volatility', min(trend_metrics['short_term'].volatility / 50.0, 1.0)))
        
        if len(risk_factors) >= 2:  # Multiple risk factors
            strength = np.mean([f[1] for f in risk_factors])
            
            if strength >= 0.5:
                signal = MarketSignal(
                    signal_id=f"risk_warning_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    signal_type=SignalType.RISK_WARNING,
                    suburb_name=suburb,
                    strength=strength,
                    confidence=0.75,
                    title=f"Market Risk Warning for {suburb}",
                    description="Multiple risk factors identified in market analysis",
                    implications="Caution advised due to negative market indicators",
                    analysis_period="composite",
                    expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.RISK_WARNING]),
                    supporting_metrics={
                        "risk_factors": [f[0] for f in risk_factors],
                        "risk_scores": {f[0]: f[1] for f in risk_factors},
                        "composite_risk": strength
                    }
                )
                signals.append(signal)
        
        return signals
    
    async def _detect_breakout_patterns(
        self,
        suburb: str,
        trend_metrics: Dict[str, TrendMetrics],
        volume_metrics: VolumeMetrics,
        comparative_metrics: ComparativeMetrics
    ) -> List[MarketSignal]:
        """Detect price breakout patterns."""
        signals = []
        
        # Look for strong momentum with volume confirmation
        if 'short_term' in trend_metrics:
            trend = trend_metrics['short_term']
            
            # Strong momentum + high volume = potential breakout
            if (trend.momentum and abs(trend.momentum) > 15 and  # Strong momentum
                volume_metrics.volume_ratio > 1.5 and           # Above average volume
                trend.confidence > 0.7):                        # High confidence
                
                strength = min((abs(trend.momentum) / 20.0) * (volume_metrics.volume_ratio / 2.0), 1.0)
                
                if strength >= 0.6:
                    breakout_type = "upward" if trend.momentum > 0 else "downward"
                    
                    signal = MarketSignal(
                        signal_id=f"breakout_{breakout_type}_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                        signal_type=SignalType.PRICE_BREAKOUT,
                        suburb_name=suburb,
                        strength=strength,
                        confidence=trend.confidence,
                        title=f"{breakout_type.title()} Price Breakout in {suburb}",
                        description=f"Strong {breakout_type} momentum with volume confirmation",
                        implications=f"Potential for continued {breakout_type} price movement",
                        current_value=trend.current_price,
                        change_percent=trend.price_change_percent,
                        analysis_period="short_term",
                        expires_at=datetime.utcnow() + timedelta(hours=self.signal_expiry[SignalType.PRICE_BREAKOUT]),
                        supporting_metrics={
                            "momentum": trend.momentum,
                            "volume_ratio": volume_metrics.volume_ratio,
                            "macd": trend.macd,
                            "trend_strength": trend.strength
                        }
                    )
                    signals.append(signal)
        
        return signals
    
    # Helper methods for generating implications text
    
    def _get_trend_change_implications(self, from_direction: TrendDirection, to_direction: TrendDirection) -> str:
        """Generate implications text for trend changes."""
        transitions = {
            (TrendDirection.DOWN, TrendDirection.UP): "Potential market recovery - consider buying opportunities",
            (TrendDirection.UP, TrendDirection.DOWN): "Market correction beginning - consider profit-taking",
            (TrendDirection.STABLE, TrendDirection.UP): "Market gaining momentum - watch for acceleration",
            (TrendDirection.STABLE, TrendDirection.DOWN): "Market losing momentum - monitor for further decline",
            (TrendDirection.VOLATILE, TrendDirection.UP): "Volatility resolving to upside - positive momentum",
            (TrendDirection.VOLATILE, TrendDirection.DOWN): "Volatility resolving to downside - negative momentum"
        }
        return transitions.get((from_direction, to_direction), "Trend direction change detected - monitor closely")
    
    def _get_momentum_implications(self, momentum: float, acceleration: float) -> str:
        """Generate implications text for momentum changes."""
        if momentum > 10:
            if acceleration > 0:
                return "Strong upward momentum accelerating - potential for continued gains"
            else:
                return "Strong upward momentum but decelerating - may be peaking"
        elif momentum < -10:
            if acceleration < 0:
                return "Strong downward momentum accelerating - potential for continued losses"
            else:
                return "Strong downward momentum but decelerating - may be bottoming"
        else:
            return "Moderate momentum detected - monitor for strengthening signals"
    
    def _get_volume_anomaly_implications(self, is_surge: bool, volume_metrics: VolumeMetrics) -> str:
        """Generate implications text for volume anomalies."""
        if is_surge:
            if volume_metrics.absorption_rate > 0.7:
                return "Volume surge with strong absorption - high buyer demand"
            else:
                return "Volume surge with weak absorption - potential supply pressure"
        else:
            return "Volume drought detected - limited market activity and liquidity"
    
    def _get_activity_change_implications(self, change_type: str, change_value: float) -> str:
        """Generate implications text for activity changes."""
        if change_type == "increase":
            return f"Market activity increased by {change_value:.1%} - rising interest and engagement"
        else:
            return f"Market activity decreased by {abs(change_value):.1%} - cooling market conditions"
    
    def _get_absorption_implications(self, change_type: str, change_value: float) -> str:
        """Generate implications text for absorption rate changes."""
        if change_type == "improvement":
            return f"Absorption rate improved by {change_value:.1%} - stronger buyer demand relative to supply"
        else:
            return f"Absorption rate deteriorated by {abs(change_value):.1%} - weakening demand or increasing supply"
    
    def _get_ranking_implications(self, metric: str, change_type: str, change_value: int) -> str:
        """Generate implications text for ranking changes."""
        if change_type == "improvement":
            return f"Significant improvement in {metric} ranking (+{change_value} positions) - outperforming peer suburbs"
        else:
            return f"Significant decline in {metric} ranking ({change_value} positions) - underperforming peer suburbs"


class ConfidenceScorer:
    """
    Advanced confidence scoring system for market signals.
    
    Evaluates signal reliability based on data quality, statistical significance,
    and supporting evidence from multiple sources.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Scoring weights
        self.weights = {
            'data_quality': 0.25,      # Data completeness and recency
            'statistical_significance': 0.30,  # Statistical confidence
            'cross_validation': 0.25,  # Multiple sources agreement
            'historical_consistency': 0.20     # Historical pattern consistency
        }
    
    async def calculate_signal_confidence(
        self,
        signal: MarketSignal,
        data_quality_metrics: Dict[str, float],
        cross_validation_results: Optional[Dict[str, bool]] = None
    ) -> float:
        """
        Calculate comprehensive confidence score for a signal.
        
        Args:
            signal: Market signal to evaluate
            data_quality_metrics: Data quality measurements
            cross_validation_results: Results from cross-validation with other sources
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        try:
            scores = {}
            
            # Data quality score
            scores['data_quality'] = self._calculate_data_quality_score(data_quality_metrics)
            
            # Statistical significance score
            scores['statistical_significance'] = self._calculate_statistical_score(signal)
            
            # Cross-validation score
            scores['cross_validation'] = self._calculate_cross_validation_score(
                cross_validation_results or {}
            )
            
            # Historical consistency score
            scores['historical_consistency'] = self._calculate_consistency_score(signal)
            
            # Weighted average
            confidence = sum(
                self.weights[key] * scores[key] 
                for key in self.weights.keys()
            )
            
            self.logger.debug(f"Confidence calculation for {signal.signal_id}: {scores} -> {confidence:.3f}")
            
            return min(confidence, 1.0)
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence for signal {signal.signal_id}: {e}")
            return 0.5  # Default moderate confidence
    
    def _calculate_data_quality_score(self, metrics: Dict[str, float]) -> float:
        """Calculate data quality component score."""
        # Default scores
        completeness = metrics.get('completeness', 0.8)
        recency = metrics.get('recency', 0.8)
        accuracy = metrics.get('accuracy', 0.8)
        sample_size = metrics.get('sample_size_score', 0.7)
        
        # Weighted average of data quality factors
        quality_score = (0.3 * completeness + 
                        0.3 * recency + 
                        0.2 * accuracy + 
                        0.2 * sample_size)
        
        return min(quality_score, 1.0)
    
    def _calculate_statistical_score(self, signal: MarketSignal) -> float:
        """Calculate statistical significance score."""
        base_confidence = signal.confidence
        
        # Adjust based on signal strength
        strength_factor = signal.strength * 0.3
        
        # Adjust based on supporting metrics quality
        metrics_factor = 0.2
        if signal.supporting_metrics:
            # More supporting metrics = higher confidence
            metrics_count = len(signal.supporting_metrics)
            metrics_factor = min(metrics_count / 10.0, 0.3)
        
        statistical_score = base_confidence + strength_factor + metrics_factor
        return min(statistical_score, 1.0)
    
    def _calculate_cross_validation_score(self, validation_results: Dict[str, bool]) -> float:
        """Calculate cross-validation score."""
        if not validation_results:
            return 0.7  # Default moderate score when no cross-validation
        
        # Count confirmations vs contradictions
        confirmations = sum(1 for confirmed in validation_results.values() if confirmed)
        total_checks = len(validation_results)
        
        if total_checks == 0:
            return 0.7
        
        validation_ratio = confirmations / total_checks
        
        # Scale to 0.3 - 1.0 range (never penalize too heavily for lack of cross-validation)
        return 0.3 + (validation_ratio * 0.7)
    
    def _calculate_consistency_score(self, signal: MarketSignal) -> float:
        """Calculate historical consistency score."""
        # This would ideally compare with historical signal performance
        # For now, use heuristics based on signal type and strength
        
        consistency_scores = {
            SignalType.TREND_CHANGE: 0.8,      # Generally predictive
            SignalType.MOMENTUM_SHIFT: 0.75,   # Good but can be noisy
            SignalType.VOLUME_ANOMALY: 0.7,    # Useful but context-dependent
            SignalType.PRICE_BREAKOUT: 0.8,    # Strong historical accuracy
            SignalType.OPPORTUNITY: 0.65,      # Subjective assessment
            SignalType.RISK_WARNING: 0.75,     # Important for risk management
            SignalType.COMPARATIVE_SHIFT: 0.7, # Relative metric reliability
            SignalType.SEASONAL_PATTERN: 0.85  # Highly predictable patterns
        }
        
        base_score = consistency_scores.get(signal.signal_type, 0.7)
        
        # Adjust based on signal strength (stronger signals more consistent)
        strength_adjustment = signal.strength * 0.2
        
        return min(base_score + strength_adjustment, 1.0)


class AlertManager:
    """
    Manages market alerts with priority-based delivery and tracking.
    
    Handles alert generation, prioritization, delivery coordination,
    and lifecycle management.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Alert thresholds
        self.priority_thresholds = {
            AlertPriority.CRITICAL: {'strength': 0.9, 'confidence': 0.85},
            AlertPriority.HIGH: {'strength': 0.7, 'confidence': 0.75},
            AlertPriority.MEDIUM: {'strength': 0.5, 'confidence': 0.65},
            AlertPriority.LOW: {'strength': 0.3, 'confidence': 0.5}
        }
        
        # Alert suppression to prevent spam
        self.suppression_windows = {  # Hours
            AlertPriority.CRITICAL: 1,
            AlertPriority.HIGH: 4,
            AlertPriority.MEDIUM: 12,
            AlertPriority.LOW: 24
        }
        
        # Active alerts tracking
        self.active_alerts: Dict[str, MarketAlert] = {}
        self.recent_alerts: Dict[str, List[datetime]] = {}
    
    async def create_alert_from_signal(
        self,
        signal: MarketSignal,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Optional[MarketAlert]:
        """
        Create a market alert from a signal.
        
        Args:
            signal: Market signal to convert to alert
            additional_context: Additional context for alert generation
            
        Returns:
            Created alert or None if not warranted
        """
        try:
            # Determine alert priority
            priority = self._determine_alert_priority(signal)
            
            # Check if alert should be suppressed
            if await self._should_suppress_alert(signal, priority):
                self.logger.debug(f"Suppressing alert for signal {signal.signal_id}")
                return None
            
            # Generate alert content
            alert_content = await self._generate_alert_content(signal, priority, additional_context)
            
            # Create alert
            alert = MarketAlert(
                alert_id=f"alert_{signal.signal_id}",
                alert_type=signal.signal_type,
                priority=priority,
                suburb_name=signal.suburb_name,
                title=alert_content['title'],
                message=alert_content['message'],
                recommended_actions=alert_content['actions'],
                triggering_signal=signal,
                delivery_channels=self._get_delivery_channels(priority)
            )
            
            # Store active alert
            self.active_alerts[alert.alert_id] = alert
            
            # Track for suppression
            suburb_key = f"{signal.suburb_name}_{signal.signal_type.value}"
            if suburb_key not in self.recent_alerts:
                self.recent_alerts[suburb_key] = []
            self.recent_alerts[suburb_key].append(datetime.utcnow())
            
            self.logger.info(f"Created {priority.value} priority alert: {alert.alert_id}")
            
            return alert
            
        except Exception as e:
            self.logger.error(f"Error creating alert from signal {signal.signal_id}: {e}")
            return None
    
    async def create_composite_alert(
        self,
        signals: List[MarketSignal],
        suburb: str,
        alert_type: SignalType = SignalType.OPPORTUNITY
    ) -> Optional[MarketAlert]:
        """
        Create a composite alert from multiple related signals.
        
        Args:
            signals: List of related signals
            suburb: Suburb name
            alert_type: Type of composite alert
            
        Returns:
            Created composite alert or None
        """
        try:
            if not signals:
                return None
            
            # Calculate composite strength and confidence
            avg_strength = np.mean([s.strength for s in signals])
            avg_confidence = np.mean([s.confidence for s in signals])
            
            # Create composite signal for alert generation
            composite_signal = MarketSignal(
                signal_id=f"composite_{suburb}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                signal_type=alert_type,
                suburb_name=suburb,
                strength=avg_strength,
                confidence=avg_confidence,
                title=f"Multiple Market Signals in {suburb}",
                description=f"Composite analysis of {len(signals)} market signals",
                implications="Multiple factors suggest significant market development"
            )
            
            # Create alert
            alert = await self.create_alert_from_signal(composite_signal)
            
            if alert:
                # Add related signals
                alert.related_signals = signals
                
                # Update message to reflect composite nature
                alert.message = f"Multiple market signals detected in {suburb}:\n\n"
                for i, signal in enumerate(signals[:3], 1):  # Limit to top 3
                    alert.message += f"{i}. {signal.title}\n"
                
                if len(signals) > 3:
                    alert.message += f"\n...and {len(signals) - 3} additional signals"
            
            return alert
            
        except Exception as e:
            self.logger.error(f"Error creating composite alert for {suburb}: {e}")
            return None
    
    async def get_active_alerts(
        self,
        suburb: Optional[str] = None,
        priority: Optional[AlertPriority] = None,
        alert_type: Optional[SignalType] = None
    ) -> List[MarketAlert]:
        """
        Get active alerts with optional filtering.
        
        Args:
            suburb: Filter by suburb name
            priority: Filter by alert priority
            alert_type: Filter by alert type
            
        Returns:
            List of matching active alerts
        """
        alerts = list(self.active_alerts.values())
        
        # Apply filters
        if suburb:
            alerts = [a for a in alerts if a.suburb_name == suburb]
        
        if priority:
            alerts = [a for a in alerts if a.priority == priority]
        
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        
        # Sort by priority and creation time
        priority_order = {
            AlertPriority.CRITICAL: 4,
            AlertPriority.HIGH: 3,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 1
        }
        
        alerts.sort(
            key=lambda a: (priority_order[a.priority], a.created_at),
            reverse=True
        )
        
        return alerts
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID to acknowledge
            
        Returns:
            True if acknowledged successfully
        """
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged_at = datetime.utcnow()
            self.logger.info(f"Alert acknowledged: {alert_id}")
            return True
        return False
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID to resolve
            
        Returns:
            True if resolved successfully
        """
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved_at = datetime.utcnow()
            self.logger.info(f"Alert resolved: {alert_id}")
            return True
        return False
    
    async def cleanup_expired_alerts(self) -> int:
        """
        Clean up expired and resolved alerts.
        
        Returns:
            Number of alerts cleaned up
        """
        cleanup_count = 0
        current_time = datetime.utcnow()
        
        # Remove resolved alerts older than 24 hours
        resolved_cutoff = current_time - timedelta(hours=24)
        
        alerts_to_remove = []
        for alert_id, alert in self.active_alerts.items():
            if (alert.resolved_at and alert.resolved_at < resolved_cutoff):
                alerts_to_remove.append(alert_id)
        
        for alert_id in alerts_to_remove:
            del self.active_alerts[alert_id]
            cleanup_count += 1
        
        # Clean up recent alerts tracking
        suppression_cutoff = current_time - timedelta(hours=48)
        for key in list(self.recent_alerts.keys()):
            self.recent_alerts[key] = [
                timestamp for timestamp in self.recent_alerts[key]
                if timestamp > suppression_cutoff
            ]
            if not self.recent_alerts[key]:
                del self.recent_alerts[key]
        
        if cleanup_count > 0:
            self.logger.info(f"Cleaned up {cleanup_count} expired alerts")
        
        return cleanup_count
    
    # Private helper methods
    
    def _determine_alert_priority(self, signal: MarketSignal) -> AlertPriority:
        """Determine alert priority based on signal characteristics."""
        # Check critical thresholds
        if (signal.strength >= self.priority_thresholds[AlertPriority.CRITICAL]['strength'] and
            signal.confidence >= self.priority_thresholds[AlertPriority.CRITICAL]['confidence']):
            return AlertPriority.CRITICAL
        
        # Check high priority
        if (signal.strength >= self.priority_thresholds[AlertPriority.HIGH]['strength'] and
            signal.confidence >= self.priority_thresholds[AlertPriority.HIGH]['confidence']):
            return AlertPriority.HIGH
        
        # Check medium priority
        if (signal.strength >= self.priority_thresholds[AlertPriority.MEDIUM]['strength'] and
            signal.confidence >= self.priority_thresholds[AlertPriority.MEDIUM]['confidence']):
            return AlertPriority.MEDIUM
        
        return AlertPriority.LOW
    
    async def _should_suppress_alert(self, signal: MarketSignal, priority: AlertPriority) -> bool:
        """Check if alert should be suppressed due to recent similar alerts."""
        suburb_key = f"{signal.suburb_name}_{signal.signal_type.value}"
        
        if suburb_key not in self.recent_alerts:
            return False
        
        suppression_window = timedelta(hours=self.suppression_windows[priority])
        cutoff_time = datetime.utcnow() - suppression_window
        
        # Check for recent alerts of same type in same suburb
        recent_similar = [
            timestamp for timestamp in self.recent_alerts[suburb_key]
            if timestamp > cutoff_time
        ]
        
        return len(recent_similar) > 0
    
    async def _generate_alert_content(
        self,
        signal: MarketSignal,
        priority: AlertPriority,
        additional_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate alert content based on signal and priority."""
        
        # Base content from signal
        title = f"[{priority.value.upper()}] {signal.title}"
        message = f"{signal.description}\n\n{signal.implications}"
        
        # Generate recommended actions based on signal type
        actions = self._generate_recommended_actions(signal, priority)
        
        # Add additional context if provided
        if additional_context:
            if 'market_context' in additional_context:
                message += f"\n\nMarket Context: {additional_context['market_context']}"
            
            if 'additional_actions' in additional_context:
                actions.extend(additional_context['additional_actions'])
        
        return {
            'title': title,
            'message': message,
            'actions': actions
        }
    
    def _generate_recommended_actions(self, signal: MarketSignal, priority: AlertPriority) -> List[str]:
        """Generate recommended actions based on signal type and priority."""
        actions = []
        
        signal_actions = {
            SignalType.TREND_CHANGE: [
                "Review property portfolios in affected area",
                "Consider timing of buy/sell decisions",
                "Monitor trend strength over next period"
            ],
            SignalType.MOMENTUM_SHIFT: [
                "Evaluate momentum sustainability",
                "Consider position sizing adjustments",
                "Watch for confirmation signals"
            ],
            SignalType.VOLUME_ANOMALY: [
                "Investigate underlying volume drivers",
                "Assess market liquidity implications",
                "Monitor for sustained volume changes"
            ],
            SignalType.PRICE_BREAKOUT: [
                "Confirm breakout with additional analysis",
                "Consider entry/exit timing",
                "Set appropriate stop-loss levels"
            ],
            SignalType.OPPORTUNITY: [
                "Conduct detailed opportunity assessment",
                "Compare with alternative investments",
                "Consider portfolio allocation"
            ],
            SignalType.RISK_WARNING: [
                "Review risk exposure in affected area",
                "Consider defensive positioning",
                "Monitor risk indicators closely"
            ],
            SignalType.COMPARATIVE_SHIFT: [
                "Analyze relative performance drivers",
                "Compare with benchmark metrics",
                "Assess competitive positioning"
            ]
        }
        
        base_actions = signal_actions.get(signal.signal_type, ["Monitor situation closely"])
        actions.extend(base_actions)
        
        # Add priority-specific actions
        if priority in [AlertPriority.CRITICAL, AlertPriority.HIGH]:
            actions.append("Take immediate action if applicable")
            actions.append("Notify relevant stakeholders")
        
        return actions[:5]  # Limit to 5 actions for clarity
    
    def _get_delivery_channels(self, priority: AlertPriority) -> List[str]:
        """Get appropriate delivery channels based on alert priority."""
        channels = {
            AlertPriority.CRITICAL: ["email", "sms", "push_notification", "dashboard"],
            AlertPriority.HIGH: ["email", "push_notification", "dashboard"],
            AlertPriority.MEDIUM: ["email", "dashboard"],
            AlertPriority.LOW: ["dashboard"]
        }
        
        return channels.get(priority, ["dashboard"])