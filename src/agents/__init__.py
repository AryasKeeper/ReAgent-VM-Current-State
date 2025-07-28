"""
ReAgent Sydney - Agent Framework

Multi-agent real estate intelligence system using CrewAI.
"""

from .base import BaseReAgentAgent, AgentConfig, AgentMetrics
from .orchestrator import CrewOrchestrator

# Import specific agents
from .listing_watcher import ListingWatcherAgent
from .buyer_matchmaker import BuyerMatchmakerAgent
from .suburb_signal import SuburbSignalAgent
from .seller_strategy import SellerStrategyAgent
from .off_market_radar import OffMarketRadarAgent
from .agent_whisperer import AgentWhispererAgent

__all__ = [
    # Base Classes
    "BaseReAgentAgent",
    "AgentConfig", 
    "AgentMetrics",
    "CrewOrchestrator",
    
    # Specific Agents
    "ListingWatcherAgent",
    "BuyerMatchmakerAgent", 
    "SuburbSignalAgent",
    "SellerStrategyAgent",
    "OffMarketRadarAgent",
    "AgentWhispererAgent",
]