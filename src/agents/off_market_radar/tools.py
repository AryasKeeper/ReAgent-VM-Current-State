"""
ReAgent Sydney - Off-Market Radar CrewAI Tools

CrewAI tools for the Off-Market Radar agent to perform various scanning,
tracking, and analysis operations.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import json

from langchain.tools import Tool
from pydantic import BaseModel, Field
import structlog

from .data_models import OpportunityType


# Pydantic models for tool inputs

class ExpiredListingsInput(BaseModel):
    """Input for expired listings scan tool."""
    target_suburbs: Optional[List[str]] = Field(default=None, description="List of suburbs to scan")
    cutoff_days: Optional[int] = Field(default=90, description="Days since expiry to consider")
    force_refresh: bool = Field(default=False, description="Force refresh of cached data")


class CouncilDAInput(BaseModel):
    """Input for council DA tracking tool."""
    target_suburbs: Optional[List[str]] = Field(default=None, description="List of suburbs to scan")
    lookback_days: int = Field(default=30, description="Days back to search for DAs")
    force_refresh: bool = Field(default=False, description="Force refresh of cached data")


class DistressSignalsInput(BaseModel):
    """Input for distress signals detection tool."""
    target_suburbs: Optional[List[str]] = Field(default=None, description="List of suburbs to scan")
    threshold_score: float = Field(default=0.7, description="Minimum distress score threshold")
    force_refresh: bool = Field(default=False, description="Force refresh of cached data")


class MarketAnomaliesInput(BaseModel):
    """Input for market anomalies detection tool."""
    target_suburbs: Optional[List[str]] = Field(default=None, description="List of suburbs to scan")
    anomaly_threshold: float = Field(default=0.6, description="Minimum anomaly severity threshold")
    force_refresh: bool = Field(default=False, description="Force refresh of cached data")


class OpportunityReportInput(BaseModel):
    """Input for opportunity report generation tool."""
    opportunity_types: Optional[List[str]] = Field(default=None, description="Types of opportunities to include")
    suburbs: Optional[List[str]] = Field(default=None, description="Suburbs to include in report")
    min_priority_score: Optional[float] = Field(default=0.5, description="Minimum priority score")
    max_results: Optional[int] = Field(default=50, description="Maximum number of opportunities")
    include_analytics: bool = Field(default=True, description="Include analytics and statistics")


# Tool creation functions

def scan_expired_listings_tool(agent) -> Tool:
    """Create tool for scanning expired listings."""
    
    async def scan_expired_listings(input_str: str) -> str:
        """
        Scan for expired listing opportunities.
        
        Args:
            input_str: JSON string with scan parameters
            
        Returns:
            JSON string with scan results
        """
        logger = structlog.get_logger("tools.scan_expired_listings")
        
        try:
            # Parse input
            if isinstance(input_str, str):
                input_data = json.loads(input_str)
            else:
                input_data = input_str
            
            scan_input = ExpiredListingsInput(**input_data)
            
            logger.info(f"Scanning expired listings for {len(scan_input.target_suburbs or [])} suburbs")
            
            # Call the expired listings monitor
            opportunities = await agent.expired_listings_monitor.scan_expired_listings(
                target_suburbs=scan_input.target_suburbs,
                cutoff_days=scan_input.cutoff_days
            )
            
            # Format results
            results = {
                'scan_type': 'expired_listings',
                'opportunities_found': len(opportunities),
                'scan_parameters': {
                    'target_suburbs': scan_input.target_suburbs,
                    'cutoff_days': scan_input.cutoff_days,
                    'force_refresh': scan_input.force_refresh
                },
                'opportunities': [opp.to_dict() for opp in opportunities[:10]],  # Limit for response size
                'scan_timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Found {len(opportunities)} expired listing opportunities")
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            logger.error(f"Error scanning expired listings: {e}")
            return json.dumps({
                'error': str(e),
                'scan_type': 'expired_listings',
                'opportunities_found': 0
            }, indent=2)
    
    return Tool(
        name="scan_expired_listings",
        description=(
            "Scan for expired listing opportunities. Identifies properties that have "
            "expired without selling and analyzes seller motivation patterns. "
            "Input should be JSON with optional target_suburbs, cutoff_days, and force_refresh."
        ),
        func=scan_expired_listings
    )


def track_council_das_tool(agent) -> Tool:
    """Create tool for tracking council development applications."""
    
    async def track_council_das(input_str: str) -> str:
        """
        Track council development applications for opportunities.
        
        Args:
            input_str: JSON string with tracking parameters
            
        Returns:
            JSON string with DA tracking results
        """
        logger = structlog.get_logger("tools.track_council_das")
        
        try:
            # Parse input
            if isinstance(input_str, str):
                input_data = json.loads(input_str)
            else:
                input_data = input_str
            
            da_input = CouncilDAInput(**input_data)
            
            logger.info(f"Tracking council DAs for {len(da_input.target_suburbs or [])} suburbs")
            
            # Call the council DA tracker
            opportunities = await agent.council_da_tracker.scan_development_applications(
                target_suburbs=da_input.target_suburbs,
                lookback_days=da_input.lookback_days
            )
            
            # Format results
            results = {
                'scan_type': 'council_da',
                'opportunities_found': len(opportunities),
                'scan_parameters': {
                    'target_suburbs': da_input.target_suburbs,
                    'lookback_days': da_input.lookback_days,
                    'force_refresh': da_input.force_refresh
                },
                'opportunities': [opp.to_dict() for opp in opportunities[:10]],
                'scan_timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Found {len(opportunities)} council DA opportunities")
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            logger.error(f"Error tracking council DAs: {e}")
            return json.dumps({
                'error': str(e),
                'scan_type': 'council_da',
                'opportunities_found': 0
            }, indent=2)
    
    return Tool(
        name="track_council_das",
        description=(
            "Track council development applications to identify off-market opportunities. "
            "Monitors DA status changes, approvals, and rejections that may indicate "
            "seller motivation. Input should be JSON with optional target_suburbs, "
            "lookback_days, and force_refresh."
        ),
        func=track_council_das
    )


def detect_distress_signals_tool(agent) -> Tool:
    """Create tool for detecting distress signals."""
    
    async def detect_distress_signals(input_str: str) -> str:
        """
        Detect distress signals indicating financial or legal pressure.
        
        Args:
            input_str: JSON string with detection parameters
            
        Returns:
            JSON string with distress signal results
        """
        logger = structlog.get_logger("tools.detect_distress_signals")
        
        try:
            # Parse input
            if isinstance(input_str, str):
                input_data = json.loads(input_str)
            else:
                input_data = input_str
            
            distress_input = DistressSignalsInput(**input_data)
            
            logger.info(f"Detecting distress signals for {len(distress_input.target_suburbs or [])} suburbs")
            
            # Call the distress signal detector
            opportunities = await agent.distress_signal_detector.scan_distress_signals(
                target_suburbs=distress_input.target_suburbs,
                threshold_score=distress_input.threshold_score
            )
            
            # Format results
            results = {
                'scan_type': 'distress_signals',
                'opportunities_found': len(opportunities),
                'scan_parameters': {
                    'target_suburbs': distress_input.target_suburbs,
                    'threshold_score': distress_input.threshold_score,
                    'force_refresh': distress_input.force_refresh
                },
                'opportunities': [opp.to_dict() for opp in opportunities[:10]],
                'scan_timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Found {len(opportunities)} distress signal opportunities")
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            logger.error(f"Error detecting distress signals: {e}")
            return json.dumps({
                'error': str(e),
                'scan_type': 'distress_signals',
                'opportunities_found': 0
            }, indent=2)
    
    return Tool(
        name="detect_distress_signals",
        description=(
            "Detect properties showing distress signals such as financial pressure, "
            "legal issues, or other indicators of motivated sellers. Analyzes price "
            "patterns, market behavior, and other signals. Input should be JSON with "
            "optional target_suburbs, threshold_score, and force_refresh."
        ),
        func=detect_distress_signals
    )


def analyze_market_anomalies_tool(agent) -> Tool:
    """Create tool for analyzing market anomalies."""
    
    async def analyze_market_anomalies(input_str: str) -> str:
        """
        Analyze market anomalies to identify unusual patterns.
        
        Args:
            input_str: JSON string with analysis parameters
            
        Returns:
            JSON string with market anomaly results
        """
        logger = structlog.get_logger("tools.analyze_market_anomalies")
        
        try:
            # Parse input
            if isinstance(input_str, str):
                input_data = json.loads(input_str)
            else:
                input_data = input_str
            
            anomaly_input = MarketAnomaliesInput(**input_data)
            
            logger.info(f"Analyzing market anomalies for {len(anomaly_input.target_suburbs or [])} suburbs")
            
            # Call the market anomaly detector
            opportunities = await agent.market_anomaly_detector.scan_market_anomalies(
                target_suburbs=anomaly_input.target_suburbs,
                anomaly_threshold=anomaly_input.anomaly_threshold
            )
            
            # Format results
            results = {
                'scan_type': 'market_anomalies',
                'opportunities_found': len(opportunities),
                'scan_parameters': {
                    'target_suburbs': anomaly_input.target_suburbs,
                    'anomaly_threshold': anomaly_input.anomaly_threshold,
                    'force_refresh': anomaly_input.force_refresh
                },
                'opportunities': [opp.to_dict() for opp in opportunities[:10]],
                'scan_timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Found {len(opportunities)} market anomaly opportunities")
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            logger.error(f"Error analyzing market anomalies: {e}")
            return json.dumps({
                'error': str(e),
                'scan_type': 'market_anomalies',
                'opportunities_found': 0
            }, indent=2)
    
    return Tool(
        name="analyze_market_anomalies",
        description=(
            "Analyze market data to identify statistical anomalies and unusual patterns "
            "that may indicate off-market opportunities. Detects price outliers, behavioral "
            "anomalies, and timing irregularities. Input should be JSON with optional "
            "target_suburbs, anomaly_threshold, and force_refresh."
        ),
        func=analyze_market_anomalies
    )


def generate_opportunity_reports_tool(agent) -> Tool:
    """Create tool for generating comprehensive opportunity reports."""
    
    async def generate_opportunity_reports(input_str: str) -> str:
        """
        Generate comprehensive opportunity reports with analytics.
        
        Args:
            input_str: JSON string with report parameters
            
        Returns:
            JSON string with opportunity report
        """
        logger = structlog.get_logger("tools.generate_opportunity_reports")
        
        try:
            # Parse input
            if isinstance(input_str, str):
                input_data = json.loads(input_str)
            else:
                input_data = input_str
            
            report_input = OpportunityReportInput(**input_data)
            
            logger.info("Generating comprehensive opportunity report")
            
            # Get all active opportunities
            all_opportunities = agent.active_opportunities
            
            # Apply filters
            filtered_opportunities = []
            for opp in all_opportunities:
                # Filter by opportunity type
                if (report_input.opportunity_types and 
                    opp.opportunity_type.value not in report_input.opportunity_types):
                    continue
                
                # Filter by suburbs
                if (report_input.suburbs and 
                    opp.suburb not in report_input.suburbs):
                    continue
                
                # Filter by priority score
                if (report_input.min_priority_score and 
                    opp.priority_score < report_input.min_priority_score):
                    continue
                
                filtered_opportunities.append(opp)
            
            # Sort and limit results
            filtered_opportunities.sort(key=lambda x: x.priority_score, reverse=True)
            if report_input.max_results:
                filtered_opportunities = filtered_opportunities[:report_input.max_results]
            
            # Generate analytics if requested
            analytics = {}
            if report_input.include_analytics:
                analytics = await agent.opportunity_ranker.get_ranking_analytics(filtered_opportunities)
            
            # Create comprehensive report
            report = {
                'report_type': 'comprehensive_opportunities',
                'generated_at': datetime.utcnow().isoformat(),
                'parameters': {
                    'opportunity_types': report_input.opportunity_types,
                    'suburbs': report_input.suburbs,
                    'min_priority_score': report_input.min_priority_score,
                    'max_results': report_input.max_results,
                    'include_analytics': report_input.include_analytics
                },
                'summary': {
                    'total_opportunities': len(filtered_opportunities),
                    'high_priority_count': len([o for o in filtered_opportunities if o.priority_score > 0.8]),
                    'average_priority_score': sum(o.priority_score for o in filtered_opportunities) / len(filtered_opportunities) if filtered_opportunities else 0,
                    'opportunity_types': list(set(o.opportunity_type.value for o in filtered_opportunities)),
                    'suburbs_covered': list(set(o.suburb for o in filtered_opportunities))
                },
                'opportunities': [opp.to_dict() for opp in filtered_opportunities],
                'analytics': analytics if report_input.include_analytics else None,
                'compliance_status': await agent.compliance_monitor.generate_scan_report(filtered_opportunities)
            }
            
            logger.info(f"Generated report with {len(filtered_opportunities)} opportunities")
            
            return json.dumps(report, indent=2)
            
        except Exception as e:
            logger.error(f"Error generating opportunity report: {e}")
            return json.dumps({
                'error': str(e),
                'report_type': 'comprehensive_opportunities',
                'generated_at': datetime.utcnow().isoformat()
            }, indent=2)
    
    return Tool(
        name="generate_opportunity_reports",
        description=(
            "Generate comprehensive reports of off-market opportunities with detailed "
            "analytics, rankings, and compliance information. Supports filtering by "
            "opportunity type, suburbs, and priority scores. Input should be JSON with "
            "optional opportunity_types, suburbs, min_priority_score, max_results, and "
            "include_analytics parameters."
        ),
        func=generate_opportunity_reports
    )


def get_opportunity_details_tool(agent) -> Tool:
    """Create tool for getting detailed information about specific opportunities."""
    
    def get_opportunity_details(opportunity_id: str) -> str:
        """
        Get detailed information about a specific opportunity.
        
        Args:
            opportunity_id: ID of the opportunity to retrieve
            
        Returns:
            JSON string with opportunity details
        """
        logger = structlog.get_logger("tools.get_opportunity_details")
        
        try:
            logger.info(f"Retrieving details for opportunity {opportunity_id}")
            
            # Find the opportunity
            opportunity = None
            for opp in agent.active_opportunities:
                if opp.id == opportunity_id:
                    opportunity = opp
                    break
            
            if not opportunity:
                return json.dumps({
                    'error': 'Opportunity not found',
                    'opportunity_id': opportunity_id
                }, indent=2)
            
            # Get detailed information
            details = {
                'opportunity_id': opportunity.id,
                'basic_info': {
                    'title': opportunity.title,
                    'address': opportunity.address,
                    'suburb': opportunity.suburb,
                    'postcode': opportunity.postcode,
                    'property_type': opportunity.property_type,
                    'opportunity_type': opportunity.opportunity_type.value,
                    'status': opportunity.status.value
                },
                'financial_info': {
                    'current_price': float(opportunity.current_price) if opportunity.current_price else None,
                    'estimated_market_value': float(opportunity.estimated_market_value) if opportunity.estimated_market_value else None,
                    'potential_purchase_price': float(opportunity.potential_purchase_price) if opportunity.potential_purchase_price else None,
                    'estimated_roi_percent': opportunity.estimated_roi_percent
                },
                'scoring': {
                    'priority_score': opportunity.priority_score,
                    'confidence_level': opportunity.confidence_level,
                    'overall_score': opportunity.scoring.overall_score,
                    'roi_potential': opportunity.scoring.roi_potential,
                    'time_sensitivity': opportunity.scoring.time_sensitivity,
                    'acquisition_difficulty': opportunity.scoring.acquisition_difficulty
                },
                'opportunity_details': opportunity.opportunity_details,
                'timeline': {
                    'discovered_at': opportunity.discovered_at.isoformat(),
                    'expires_at': opportunity.expires_at.isoformat() if opportunity.expires_at else None,
                    'estimated_timeline_days': opportunity.estimated_timeline_days
                },
                'data_sources': opportunity.data_sources,
                'tags': opportunity.tags,
                'compliance': {
                    'compliance_checked': opportunity.compliance_checked,
                    'ethical_approval': opportunity.ethical_approval,
                    'data_privacy_compliant': opportunity.data_privacy_compliant
                },
                'investigation_notes': opportunity.investigation_notes,
                'action_items': opportunity.action_items
            }
            
            logger.info(f"Retrieved details for opportunity {opportunity_id}")
            
            return json.dumps(details, indent=2)
            
        except Exception as e:
            logger.error(f"Error retrieving opportunity details: {e}")
            return json.dumps({
                'error': str(e),
                'opportunity_id': opportunity_id
            }, indent=2)
    
    return Tool(
        name="get_opportunity_details",
        description=(
            "Get detailed information about a specific off-market opportunity including "
            "financial analysis, scoring breakdown, timeline, compliance status, and "
            "investigation notes. Input should be the opportunity ID."
        ),
        func=get_opportunity_details
    )


def search_opportunities_tool(agent) -> Tool:
    """Create tool for searching opportunities with filters."""
    
    def search_opportunities(search_criteria: str) -> str:
        """
        Search opportunities using various filters.
        
        Args:
            search_criteria: JSON string with search parameters
            
        Returns:
            JSON string with matching opportunities
        """
        logger = structlog.get_logger("tools.search_opportunities")
        
        try:
            # Parse search criteria
            if isinstance(search_criteria, str):
                criteria = json.loads(search_criteria)
            else:
                criteria = search_criteria
            
            logger.info(f"Searching opportunities with criteria: {criteria}")
            
            # Apply filters
            matching_opportunities = []
            for opp in agent.active_opportunities:
                # Filter by suburb
                if criteria.get('suburb') and opp.suburb.lower() != criteria['suburb'].lower():
                    continue
                
                # Filter by opportunity type
                if criteria.get('opportunity_type') and opp.opportunity_type.value != criteria['opportunity_type']:
                    continue
                
                # Filter by price range
                if criteria.get('min_price') and opp.current_price and opp.current_price < criteria['min_price']:
                    continue
                if criteria.get('max_price') and opp.current_price and opp.current_price > criteria['max_price']:
                    continue
                
                # Filter by priority score
                if criteria.get('min_priority') and opp.priority_score < criteria['min_priority']:
                    continue
                
                # Filter by ROI
                if criteria.get('min_roi') and opp.estimated_roi_percent and opp.estimated_roi_percent < criteria['min_roi']:
                    continue
                
                # Filter by tags
                if criteria.get('tags'):
                    required_tags = criteria['tags'] if isinstance(criteria['tags'], list) else [criteria['tags']]
                    if not any(tag in opp.tags for tag in required_tags):
                        continue
                
                # Filter by high priority only
                if criteria.get('high_priority_only') and not opp.is_high_priority():
                    continue
                
                # Filter by time sensitive only
                if criteria.get('time_sensitive_only') and not opp.is_time_sensitive():
                    continue
                
                matching_opportunities.append(opp)
            
            # Sort by priority score
            matching_opportunities.sort(key=lambda x: x.priority_score, reverse=True)
            
            # Limit results
            max_results = criteria.get('max_results', 20)
            matching_opportunities = matching_opportunities[:max_results]
            
            # Format results
            results = {
                'search_criteria': criteria,
                'matches_found': len(matching_opportunities),
                'opportunities': [opp.to_dict() for opp in matching_opportunities],
                'search_timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Found {len(matching_opportunities)} matching opportunities")
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            logger.error(f"Error searching opportunities: {e}")
            return json.dumps({
                'error': str(e),
                'matches_found': 0
            }, indent=2)
    
    return Tool(
        name="search_opportunities",
        description=(
            "Search and filter off-market opportunities using various criteria such as "
            "suburb, opportunity_type, price range (min_price, max_price), priority score "
            "(min_priority), ROI (min_roi), tags, high_priority_only, time_sensitive_only, "
            "and max_results. Input should be JSON with desired filter criteria."
        ),
        func=search_opportunities
    )


def get_scan_status_tool(agent) -> Tool:
    """Create tool for getting current scan status."""
    
    def get_scan_status(input_str: str = "") -> str:
        """
        Get current scan status and statistics.
        
        Args:
            input_str: Optional input (not used)
            
        Returns:
            JSON string with scan status
        """
        logger = structlog.get_logger("tools.get_scan_status")
        
        try:
            logger.info("Retrieving scan status")
            
            # Get scan status from agent
            status = {
                'agent_status': {
                    'is_running': agent.is_running,
                    'current_execution': agent.current_execution.execution_id if agent.current_execution else None,
                    'active_opportunities_count': len(agent.active_opportunities)
                },
                'scan_history': {
                    'last_scan_times': {k: v.isoformat() for k, v in agent.last_scan_times.items()},
                    'scan_statistics': agent.scan_statistics
                },
                'component_status': {
                    'expired_listings_monitor': 'active',
                    'council_da_tracker': 'active',
                    'distress_signal_detector': 'active',
                    'market_anomaly_detector': 'active',
                    'opportunity_ranker': 'active',
                    'compliance_monitor': 'active'
                },
                'opportunities_summary': {
                    'total_active': len(agent.active_opportunities),
                    'high_priority': len([o for o in agent.active_opportunities if o.priority_score > 0.8]),
                    'time_sensitive': len([o for o in agent.active_opportunities if o.is_time_sensitive()]),
                    'by_type': {}
                },
                'compliance_status': agent.compliance_monitor.get_compliance_status(),
                'status_timestamp': datetime.utcnow().isoformat()
            }
            
            # Calculate opportunities by type
            for opp in agent.active_opportunities:
                opp_type = opp.opportunity_type.value
                status['opportunities_summary']['by_type'][opp_type] = status['opportunities_summary']['by_type'].get(opp_type, 0) + 1
            
            logger.info("Retrieved scan status successfully")
            
            return json.dumps(status, indent=2)
            
        except Exception as e:
            logger.error(f"Error retrieving scan status: {e}")
            return json.dumps({
                'error': str(e),
                'status_timestamp': datetime.utcnow().isoformat()
            }, indent=2)
    
    return Tool(
        name="get_scan_status",
        description=(
            "Get current scan status including agent state, last scan times, component "
            "status, opportunities summary, and compliance status. No input required."
        ),
        func=get_scan_status
    )