"""
ReAgent Sydney - Off-Market Radar AU Agent

Advanced off-market opportunity detection system for Sydney real estate market.

This agent identifies hidden opportunities through:
- Expired listings analysis with seller motivation assessment
- Council Development Application tracking and analysis
- Financial distress signal detection and pattern recognition
- Market anomaly identification through statistical analysis
- Comprehensive opportunity ranking with ROI estimation
- Strict compliance monitoring and ethical data collection

Key Components:
- OffMarketRadarAgent: Main agent coordinating all detection systems
- ExpiredListingsMonitor: Tracks expired listings and seller behavior patterns
- CouncilDATracker: Monitors development applications for opportunities
- DistressSignalDetector: Identifies properties under financial/legal pressure
- MarketAnomalyDetector: Detects statistical anomalies and unusual patterns
- OpportunityRanker: Advanced ranking system with ROI and risk analysis
- ComplianceMonitor: Ensures legal and ethical compliance
"""

from .agent import OffMarketRadarAgent, OffMarketRadarConfig
from .data_models import (
    OffMarketOpportunity, OpportunityType, OpportunityStatus, OpportunityScore,
    DistressSignalType, CouncilDAStatus, OffMarketOpportunityDB,
    CouncilDARecord, DistressSignalRecord,
    OpportunityCreateRequest, OpportunityResponse, OpportunitySearchFilters,
    ScanRequest, ScanResponse
)
from .expired_listings_monitor import ExpiredListingsMonitor, ExpiredListingPattern
from .council_da_tracker import CouncilDATracker, CouncilAPIConfig
from .distress_signal_detector import DistressSignalDetector, DistressSignal, DistressAnalysis
from .market_anomaly_detector import MarketAnomalyDetector, MarketAnomaly
from .opportunity_ranker import OpportunityRanker, RankingCriteria, MarketContext
from .compliance_monitor import ComplianceMonitor, ComplianceRule, ComplianceViolation, ComplianceReport
from .tools import (
    scan_expired_listings_tool, track_council_das_tool, detect_distress_signals_tool,
    analyze_market_anomalies_tool, generate_opportunity_reports_tool,
    get_opportunity_details_tool, search_opportunities_tool, get_scan_status_tool
)

__all__ = [
    # Main agent
    'OffMarketRadarAgent',
    'OffMarketRadarConfig',
    
    # Data models
    'OffMarketOpportunity',
    'OpportunityType',
    'OpportunityStatus', 
    'OpportunityScore',
    'DistressSignalType',
    'CouncilDAStatus',
    'OffMarketOpportunityDB',
    'CouncilDARecord',
    'DistressSignalRecord',
    'OpportunityCreateRequest',
    'OpportunityResponse',
    'OpportunitySearchFilters',
    'ScanRequest',
    'ScanResponse',
    
    # Detection components
    'ExpiredListingsMonitor',
    'ExpiredListingPattern',
    'CouncilDATracker',
    'CouncilAPIConfig',
    'DistressSignalDetector',
    'DistressSignal',
    'DistressAnalysis',
    'MarketAnomalyDetector',
    'MarketAnomaly',
    
    # Analysis and ranking
    'OpportunityRanker',
    'RankingCriteria',
    'MarketContext',
    
    # Compliance and monitoring
    'ComplianceMonitor',
    'ComplianceRule',
    'ComplianceViolation',
    'ComplianceReport',
    
    # CrewAI tools
    'scan_expired_listings_tool',
    'track_council_das_tool',
    'detect_distress_signals_tool',
    'analyze_market_anomalies_tool',
    'generate_opportunity_reports_tool',
    'get_opportunity_details_tool',
    'search_opportunities_tool',
    'get_scan_status_tool'
]