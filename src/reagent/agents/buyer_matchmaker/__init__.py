"""
Buyer Matchmaker AU - Intelligent Property Recommendation Agent

Advanced ML-powered matching system that provides personalized property recommendations
using vector search, behavioral analytics, and market intelligence.

Components:
- BuyerMatchmakerAgent: Main agent class with CrewAI integration
- MatchingEngine: Core matching algorithms and scoring logic
- Tools: Specialized CrewAI tools for matching operations
- Utils: Vector DB management, performance monitoring, and utilities

Usage:
    from src.agents.buyer_matchmaker import BuyerMatchmakerAgent
    
    agent = BuyerMatchmakerAgent()
    await agent.initialize()
    
    result = await agent.execute({
        "operation": "generate_matches",
        "buyer_ids": ["buyer-uuid"],
        "force_refresh": False
    })
"""

from .agent import BuyerMatchmakerAgent, MatchResult, MatchingConfig
from .matching_engine import MatchingEngine, MatchExplanation, PriceAssessment, MatchQuality
from .tools import get_buyer_matchmaker_tools, BUYER_MATCHMAKER_TOOLS

__all__ = [
    # Main agent
    "BuyerMatchmakerAgent",
    "MatchResult", 
    "MatchingConfig",
    
    # Matching engine
    "MatchingEngine",
    "MatchExplanation",
    "PriceAssessment",
    "MatchQuality",
    
    # Tools
    "get_buyer_matchmaker_tools",
    "BUYER_MATCHMAKER_TOOLS",
]