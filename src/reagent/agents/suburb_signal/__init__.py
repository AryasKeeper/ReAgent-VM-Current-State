"""
Suburb Signal Agent

Analyzes suburb-level market trends and signals. Identifies emerging markets,
gentrification patterns, and investment opportunities at the suburb level.

This agent performs sophisticated statistical analysis on property market data
to detect trends, anomalies, and investment opportunities across Sydney suburbs.
"""

from .agent import SuburbSignalAgent
from .analyzers import StatisticalAnalyzer, TrendDetector, AnomalyDetector
from .signals import SignalGenerator, AlertManager, ConfidenceScorer
from .data_aggregator import DataAggregator
from .cache_manager import AnalysisCacheManager

__all__ = [
    "SuburbSignalAgent",
    "StatisticalAnalyzer", 
    "TrendDetector",
    "AnomalyDetector",
    "SignalGenerator",
    "AlertManager",
    "ConfidenceScorer",
    "DataAggregator",
    "AnalysisCacheManager"
]