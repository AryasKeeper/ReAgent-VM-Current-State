"""
ReAgent Sydney - Off-Market Radar AU Agent

Sophisticated detection system for identifying off-market opportunities through
expired listings, council DA tracking, and distress signals.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
import asyncio
import logging

from langchain.tools import Tool
from crewai import Agent, Task
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import sessionmaker

from ..base import BaseReAgentAgent, AgentConfig, AgentRole, AgentPriority
from ...core.database.engine import get_db_session
from ...data.models.property_models import Property, PropertyPriceHistory, PropertyMarketMetrics
from ...data.models.market_models import SuburbMetrics, MarketTrend
from ...config.settings import get_settings

from .council_da_tracker import CouncilDATracker
from .expired_listings_monitor import ExpiredListingsMonitor
from .distress_signal_detector import DistressSignalDetector
from .market_anomaly_detector import MarketAnomalyDetector
from .opportunity_ranker import OpportunityRanker
from .compliance_monitor import ComplianceMonitor
from .data_models import OffMarketOpportunity, OpportunityType, OpportunityScore
from .tools import (
    scan_expired_listings_tool,
    track_council_das_tool,
    detect_distress_signals_tool,
    analyze_market_anomalies_tool,
    generate_opportunity_reports_tool
)


@dataclass
class OffMarketRadarConfig:
    """Configuration for Off-Market Radar operations."""
    
    # Scanning intervals
    expired_listings_scan_hours: int = 24
    council_da_scan_hours: int = 24
    distress_signal_scan_hours: int = 6
    market_anomaly_scan_hours: int = 12
    
    # Detection thresholds
    expired_listing_days: int = 90
    price_drop_threshold_percent: float = 10.0
    market_time_anomaly_days: int = 120
    distress_score_threshold: float = 0.7
    
    # Geographic scope
    target_postcodes: List[str] = None
    max_suburb_radius_km: float = 50.0
    
    # Data source priorities
    council_apis_enabled: bool = True
    legal_records_enabled: bool = True
    market_data_enabled: bool = True
    
    # Performance settings
    max_concurrent_requests: int = 10
    request_delay_seconds: float = 1.0
    data_retention_days: int = 365
    
    def __post_init__(self):
        if self.target_postcodes is None:
            # Sydney metro postcodes (2000-2999)
            self.target_postcodes = [str(pc) for pc in range(2000, 3000)]


class OffMarketRadarAgent(BaseReAgentAgent):
    """
    Off-Market Radar AU Agent for detecting hidden real estate opportunities.
    
    This agent identifies off-market opportunities through:
    1. Expired listings analysis
    2. Council Development Application tracking
    3. Distress signal detection
    4. Market anomaly identification
    5. ROI-based opportunity ranking
    """
    
    def __init__(self, config: Optional[AgentConfig] = None, radar_config: Optional[OffMarketRadarConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Off-Market Radar AU",
                role=AgentRole.ANALYZER,
                description="Sophisticated detection system for identifying off-market real estate opportunities",
                version="1.0.0",
                max_execution_time=1800,  # 30 minutes
                max_retries=3,
                priority=AgentPriority.HIGH,
                required_services=["database", "cache"],
                required_tools=["expired_listings_scanner", "council_da_tracker", "distress_detector"],
                custom_settings={
                    "geographic_scope": "Sydney Metro (2000-2999)",
                    "compliance_level": "strict",
                    "data_sources": ["council", "market", "legal_public"]
                }
            )
        
        super().__init__(config)
        
        self.radar_config = radar_config or OffMarketRadarConfig()
        self.settings = get_settings()
        
        # Initialize detection components
        self.council_da_tracker = CouncilDATracker(self.radar_config)
        self.expired_listings_monitor = ExpiredListingsMonitor(self.radar_config)
        self.distress_signal_detector = DistressSignalDetector(self.radar_config)
        self.market_anomaly_detector = MarketAnomalyDetector(self.radar_config)
        self.opportunity_ranker = OpportunityRanker(self.radar_config)
        self.compliance_monitor = ComplianceMonitor(self.radar_config)
        
        # Tracking state
        self.last_scan_times: Dict[str, datetime] = {}
        self.active_opportunities: List[OffMarketOpportunity] = []
        self.scan_statistics: Dict[str, Any] = {}
    
    async def _initialize_agent(self) -> None:
        """Initialize Off-Market Radar specific components."""
        try:
            # Initialize detection components
            await self.council_da_tracker.initialize()
            await self.expired_listings_monitor.initialize()
            await self.distress_signal_detector.initialize()
            await self.market_anomaly_detector.initialize()
            await self.opportunity_ranker.initialize()
            await self.compliance_monitor.initialize()
            
            # Load last scan times from cache
            await self._load_scan_state()
            
            self.logger.info("Off-Market Radar AU agent initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Off-Market Radar components: {e}")
            raise
    
    async def _cleanup_agent(self) -> None:
        """Cleanup Off-Market Radar resources."""
        try:
            # Save scan state
            await self._save_scan_state()
            
            # Cleanup components
            await self.council_da_tracker.cleanup()
            await self.expired_listings_monitor.cleanup()
            await self.distress_signal_detector.cleanup()
            await self.market_anomaly_detector.cleanup()
            await self.opportunity_ranker.cleanup()
            await self.compliance_monitor.cleanup()
            
            self.logger.info("Off-Market Radar AU agent cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during Off-Market Radar cleanup: {e}")
    
    async def _execute_agent_logic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution logic for Off-Market Radar AU.
        
        Args:
            input_data: Input parameters including scan type, filters, etc.
            
        Returns:
            Dict containing discovered opportunities and scan results
        """
        scan_type = input_data.get("scan_type", "full")
        target_suburbs = input_data.get("target_suburbs", [])
        force_refresh = input_data.get("force_refresh", False)
        
        start_time = datetime.utcnow()
        results = {
            "scan_type": scan_type,
            "scan_started": start_time.isoformat(),
            "opportunities_discovered": [],
            "scan_statistics": {},
            "compliance_report": {},
            "errors": []
        }
        
        try:
            # Compliance check before scanning
            compliance_check = await self.compliance_monitor.pre_scan_check()
            if not compliance_check["approved"]:
                raise RuntimeError(f"Compliance check failed: {compliance_check['reason']}")
            
            # Execute scans based on type
            if scan_type == "full" or scan_type == "expired":
                expired_opportunities = await self._scan_expired_listings(target_suburbs, force_refresh)
                results["opportunities_discovered"].extend(expired_opportunities)
            
            if scan_type == "full" or scan_type == "council":
                da_opportunities = await self._scan_council_das(target_suburbs, force_refresh)
                results["opportunities_discovered"].extend(da_opportunities)
            
            if scan_type == "full" or scan_type == "distress":
                distress_opportunities = await self._scan_distress_signals(target_suburbs, force_refresh)
                results["opportunities_discovered"].extend(distress_opportunities)
            
            if scan_type == "full" or scan_type == "anomalies":
                anomaly_opportunities = await self._scan_market_anomalies(target_suburbs, force_refresh)
                results["opportunities_discovered"].extend(anomaly_opportunities)
            
            # Rank and prioritize opportunities
            if results["opportunities_discovered"]:
                ranked_opportunities = await self.opportunity_ranker.rank_opportunities(
                    results["opportunities_discovered"]
                )
                results["opportunities_discovered"] = ranked_opportunities
            
            # Generate compliance report
            results["compliance_report"] = await self.compliance_monitor.generate_scan_report(
                results["opportunities_discovered"]
            )
            
            # Update scan statistics
            results["scan_statistics"] = {
                "total_opportunities": len(results["opportunities_discovered"]),
                "high_priority_count": len([o for o in results["opportunities_discovered"] 
                                          if o.priority_score > 0.8]),
                "scan_duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "suburbs_scanned": len(target_suburbs) if target_suburbs else "all",
                "data_sources_used": self._get_active_data_sources()
            }
            
            # Update active opportunities list
            self.active_opportunities = results["opportunities_discovered"]
            
            # Cache results
            await self._cache_scan_results(results)
            
            self.logger.info(
                f"Off-Market Radar scan completed: {len(results['opportunities_discovered'])} opportunities found"
            )
            
        except Exception as e:
            error_msg = f"Off-Market Radar scan failed: {str(e)}"
            self.logger.error(error_msg)
            results["errors"].append(error_msg)
            raise
        
        return results
    
    async def _scan_expired_listings(self, target_suburbs: List[str], force_refresh: bool) -> List[OffMarketOpportunity]:
        """Scan for expired listing opportunities."""
        if not self._should_scan("expired_listings", force_refresh):
            return []
        
        try:
            self.logger.info("Scanning expired listings...")
            
            opportunities = await self.expired_listings_monitor.scan_expired_listings(
                target_suburbs=target_suburbs,
                cutoff_days=self.radar_config.expired_listing_days
            )
            
            self.last_scan_times["expired_listings"] = datetime.utcnow()
            self.logger.info(f"Found {len(opportunities)} expired listing opportunities")
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error scanning expired listings: {e}")
            return []
    
    async def _scan_council_das(self, target_suburbs: List[str], force_refresh: bool) -> List[OffMarketOpportunity]:
        """Scan for council DA opportunities."""
        if not self._should_scan("council_das", force_refresh) or not self.radar_config.council_apis_enabled:
            return []
        
        try:
            self.logger.info("Scanning council DAs...")
            
            opportunities = await self.council_da_tracker.scan_development_applications(
                target_suburbs=target_suburbs,
                lookback_days=30
            )
            
            self.last_scan_times["council_das"] = datetime.utcnow()
            self.logger.info(f"Found {len(opportunities)} council DA opportunities")
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error scanning council DAs: {e}")
            return []
    
    async def _scan_distress_signals(self, target_suburbs: List[str], force_refresh: bool) -> List[OffMarketOpportunity]:
        """Scan for distress signal opportunities."""
        if not self._should_scan("distress_signals", force_refresh):
            return []
        
        try:
            self.logger.info("Scanning distress signals...")
            
            opportunities = await self.distress_signal_detector.scan_distress_signals(
                target_suburbs=target_suburbs,
                threshold_score=self.radar_config.distress_score_threshold
            )
            
            self.last_scan_times["distress_signals"] = datetime.utcnow()
            self.logger.info(f"Found {len(opportunities)} distress signal opportunities")
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error scanning distress signals: {e}")
            return []
    
    async def _scan_market_anomalies(self, target_suburbs: List[str], force_refresh: bool) -> List[OffMarketOpportunity]:
        """Scan for market anomaly opportunities."""
        if not self._should_scan("market_anomalies", force_refresh):
            return []
        
        try:
            self.logger.info("Scanning market anomalies...")
            
            opportunities = await self.market_anomaly_detector.scan_market_anomalies(
                target_suburbs=target_suburbs,
                anomaly_threshold=0.6
            )
            
            self.last_scan_times["market_anomalies"] = datetime.utcnow()
            self.logger.info(f"Found {len(opportunities)} market anomaly opportunities")
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error scanning market anomalies: {e}")
            return []
    
    def _should_scan(self, scan_type: str, force_refresh: bool) -> bool:
        """Check if a scan type should be executed based on timing."""
        if force_refresh:
            return True
        
        last_scan = self.last_scan_times.get(scan_type)
        if not last_scan:
            return True
        
        scan_intervals = {
            "expired_listings": self.radar_config.expired_listings_scan_hours,
            "council_das": self.radar_config.council_da_scan_hours,
            "distress_signals": self.radar_config.distress_signal_scan_hours,
            "market_anomalies": self.radar_config.market_anomaly_scan_hours
        }
        
        interval = scan_intervals.get(scan_type, 24)
        time_since_scan = datetime.utcnow() - last_scan
        
        return time_since_scan >= timedelta(hours=interval)
    
    def _get_active_data_sources(self) -> List[str]:
        """Get list of active data sources."""
        sources = ["database", "market_data"]
        
        if self.radar_config.council_apis_enabled:
            sources.append("council_apis")
        
        if self.radar_config.legal_records_enabled:
            sources.append("legal_records")
        
        return sources
    
    async def _load_scan_state(self) -> None:
        """Load scan state from cache."""
        try:
            cache_key = f"off_market_radar:scan_state:{self.config.name}"
            scan_state = await self.cache_manager.get(cache_key)
            
            if scan_state:
                self.last_scan_times = {
                    k: datetime.fromisoformat(v) for k, v in scan_state.get("last_scan_times", {}).items()
                }
                
        except Exception as e:
            self.logger.warning(f"Failed to load scan state: {e}")
    
    async def _save_scan_state(self) -> None:
        """Save scan state to cache."""
        try:
            cache_key = f"off_market_radar:scan_state:{self.config.name}"
            scan_state = {
                "last_scan_times": {
                    k: v.isoformat() for k, v in self.last_scan_times.items()
                },
                "updated_at": datetime.utcnow().isoformat()
            }
            
            await self.cache_manager.set(cache_key, scan_state, ttl=86400)  # 24 hours
            
        except Exception as e:
            self.logger.warning(f"Failed to save scan state: {e}")
    
    async def _cache_scan_results(self, results: Dict[str, Any]) -> None:
        """Cache scan results for quick access."""
        try:
            cache_key = f"off_market_radar:results:{self.config.name}"
            await self.cache_manager.set(cache_key, results, ttl=3600)  # 1 hour
            
        except Exception as e:
            self.logger.warning(f"Failed to cache scan results: {e}")
    
    async def _initialize_tools(self) -> List[Tool]:
        """Initialize CrewAI tools for Off-Market Radar."""
        return [
            scan_expired_listings_tool(self),
            track_council_das_tool(self),
            detect_distress_signals_tool(self),
            analyze_market_anomalies_tool(self),
            generate_opportunity_reports_tool(self)
        ]
    
    def _get_agent_goal(self) -> str:
        """Get agent goal for CrewAI."""
        return (
            "Identify and analyze off-market real estate opportunities in Sydney through "
            "comprehensive monitoring of expired listings, council development applications, "
            "distress signals, and market anomalies while maintaining strict compliance "
            "with legal and ethical standards."
        )
    
    def _get_agent_backstory(self) -> str:
        """Get agent backstory for CrewAI."""
        return (
            "I am the Off-Market Radar AU, a sophisticated real estate intelligence system "
            "specializing in detecting hidden opportunities before they reach the public market. "
            "I combine multiple data sources including council records, market analytics, and "
            "pattern recognition to identify properties with high potential for off-market "
            "transactions. My analysis respects all privacy laws and ethical guidelines while "
            "providing valuable insights for real estate professionals and investors."
        )
    
    # Public API methods
    
    async def get_opportunities_by_suburb(self, suburb: str, opportunity_types: List[str] = None) -> List[OffMarketOpportunity]:
        """Get opportunities filtered by suburb and type."""
        filtered_opportunities = [
            opp for opp in self.active_opportunities
            if opp.suburb.lower() == suburb.lower()
        ]
        
        if opportunity_types:
            filtered_opportunities = [
                opp for opp in filtered_opportunities
                if opp.opportunity_type.value in opportunity_types
            ]
        
        return filtered_opportunities
    
    async def get_opportunity_details(self, opportunity_id: str) -> Optional[OffMarketOpportunity]:
        """Get detailed information about a specific opportunity."""
        for opportunity in self.active_opportunities:
            if opportunity.id == opportunity_id:
                return opportunity
        return None
    
    async def get_scan_status(self) -> Dict[str, Any]:
        """Get current scan status and statistics."""
        return {
            "last_scan_times": {k: v.isoformat() for k, v in self.last_scan_times.items()},
            "active_opportunities_count": len(self.active_opportunities),
            "high_priority_count": len([o for o in self.active_opportunities if o.priority_score > 0.8]),
            "scan_statistics": self.scan_statistics,
            "is_running": self.is_running
        }