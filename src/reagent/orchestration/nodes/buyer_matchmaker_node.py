"""
ReAgent Sydney - Buyer Matchmaker LangGraph Node

LangGraph node implementation for the Buyer Matchmaker AU agent.
Performs vector-based matching between buyer profiles and property listings.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from .base_node import BaseReAgentNode
from ..state import ReAgentState
from ...agents.buyer_matchmaker.agent import BuyerMatchmakerAgent
from ...core.database.engine import get_db_session
from ...data.models.buyer_models import BuyerProfile


class BuyerMatchmakerNode(BaseReAgentNode):
    """
    LangGraph node for Buyer Matchmaker AU agent.
    
    Responsibilities:
    - Match buyer profiles with available properties
    - Use vector similarity search for intelligent matching
    - Generate match scores and explanations
    - Create buyer alerts and notifications
    - Track matching performance metrics
    """
    
    def __init__(self):
        super().__init__("Buyer Matchmaker AU")
        
        # Initialize the actual agent
        self.agent = BuyerMatchmakerAgent()
        
        # Node-specific configuration
        self.min_match_score = 0.7
        self.max_matches_per_buyer = 10
        self.vector_search_limit = 50

    async def _execute_agent_logic(self, state: ReAgentState) -> Dict[str, Any]:
        """
        Execute buyer matching logic within LangGraph context.
        
        Args:
            state: Current workflow state containing properties from listing watcher
            
        Returns:
            Dictionary containing matches and buyer alerts
        """
        # Get properties from previous agents (listing watcher)
        properties = state.get("properties", [])
        
        if not properties:
            self.logger.warning("No properties available for buyer matching")
            return {
                "matches": [],
                "buyer_alerts": [],
                "statistics": {
                    "properties_processed": 0,
                    "buyers_processed": 0,
                    "matches_generated": 0,
                    "alerts_created": 0
                }
            }
        
        # Get configuration
        config = state.get("config", {})
        input_data = state.get("input_data", {})
        
        # Extract parameters
        min_score = config.get("min_match_score", self.min_match_score)
        max_matches = config.get("max_matches_per_buyer", self.max_matches_per_buyer)
        buyer_ids = input_data.get("buyer_ids", [])  # Specific buyers to match, empty = all active
        
        # Check cache for recent matching results
        cache_key = f"buyer_matcher:recent:{datetime.utcnow().strftime('%Y%m%d_%H')}"
        
        # Initialize agent if not already done
        if not self.agent.is_initialized:
            await self.agent.initialize()
        
        try:
            # Get active buyer profiles
            active_buyers = await self._get_active_buyers(buyer_ids)
            
            if not active_buyers:
                self.logger.info("No active buyers found for matching")
                return {
                    "matches": [],
                    "buyer_alerts": [],
                    "statistics": {
                        "properties_processed": len(properties),
                        "buyers_processed": 0,
                        "matches_generated": 0,
                        "alerts_created": 0
                    }
                }
            
            # Execute buyer matching
            agent_result = await self.agent.execute({
                "properties": properties,
                "buyer_profiles": active_buyers,
                "min_match_score": min_score,
                "max_matches_per_buyer": max_matches,
                "vector_search_limit": self.vector_search_limit
            })
            
            if not agent_result.get("success"):
                raise RuntimeError(f"Buyer matcher agent failed: {agent_result.get('error')}")
            
            # Extract and process results
            matching_data = agent_result.get("data", {})
            
            # Structure results for downstream agents
            result = {
                "matches": matching_data.get("matches", []),
                "buyer_alerts": matching_data.get("buyer_alerts", []),
                "match_insights": matching_data.get("match_insights", {}),
                "statistics": {
                    "properties_processed": len(properties),
                    "buyers_processed": len(active_buyers),
                    "matches_generated": len(matching_data.get("matches", [])),
                    "alerts_created": len(matching_data.get("buyer_alerts", [])),
                    "avg_match_score": matching_data.get("avg_match_score", 0.0),
                    "execution_time": agent_result.get("execution_time", 0)
                },
                "metadata": {
                    "matching_timestamp": datetime.utcnow().isoformat(),
                    "min_score_threshold": min_score,
                    "max_matches_per_buyer": max_matches,
                    "vector_search_enabled": True
                }
            }
            
            # Update workflow state with matches
            self._update_state_matches(state, result["matches"])
            
            # Cache results
            await self._cache_set(cache_key, result, ttl=3600)
            
            # Cache metrics
            await self._cache_metrics(result["statistics"])
            
            self.logger.info(
                f"Buyer matching completed: {result['statistics']['matches_generated']} matches for "
                f"{result['statistics']['buyers_processed']} buyers from {result['statistics']['properties_processed']} properties"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Buyer matching execution failed: {e}", exc_info=True)
            raise

    async def _get_active_buyers(self, buyer_ids: List[str] = None) -> List[Dict[str, Any]]:
        """Get active buyer profiles from database."""
        try:
            async with get_db_session() as session:
                if buyer_ids:
                    # Get specific buyers
                    query = """
                        SELECT * FROM buyer_profiles 
                        WHERE id = ANY(:buyer_ids) AND is_active = true
                        ORDER BY updated_at DESC
                    """
                    result = await session.execute(query, {"buyer_ids": buyer_ids})
                else:
                    # Get all active buyers
                    query = """
                        SELECT * FROM buyer_profiles 
                        WHERE is_active = true 
                        AND (expires_at IS NULL OR expires_at > NOW())
                        ORDER BY updated_at DESC
                        LIMIT 1000
                    """
                    result = await session.execute(query)
                
                buyers = []
                for row in result.fetchall():
                    buyer_data = dict(row)
                    # Convert database fields to agent format
                    buyers.append({
                        "id": buyer_data["id"],
                        "name": buyer_data["name"],
                        "email": buyer_data["email"],
                        "phone": buyer_data["phone"],
                        "preferences": buyer_data["preferences"] or {},
                        "budget_min": buyer_data["budget_min"],
                        "budget_max": buyer_data["budget_max"],
                        "preferred_suburbs": buyer_data["preferred_suburbs"] or [],
                        "property_types": buyer_data["property_types"] or [],
                        "min_bedrooms": buyer_data["min_bedrooms"],
                        "min_bathrooms": buyer_data["min_bathrooms"],
                        "required_features": buyer_data["required_features"] or [],
                        "exclusions": buyer_data["exclusions"] or [],
                        "urgency_level": buyer_data["urgency_level"],
                        "matching_enabled": buyer_data["matching_enabled"],
                        "last_matched_at": buyer_data["last_matched_at"],
                        "created_at": buyer_data["created_at"],
                        "updated_at": buyer_data["updated_at"]
                    })
                
                return buyers
                
        except Exception as e:
            self.logger.error(f"Failed to get active buyers: {e}")
            return []

    def _update_state_matches(self, state: ReAgentState, matches: List[Dict[str, Any]]) -> None:
        """Update the workflow state with generated matches."""
        # Standardize match format for downstream agents
        standardized_matches = []
        
        for match in matches:
            match_data = {
                "id": match.get("id"),
                "buyer_id": match.get("buyer_id"),
                "property_id": match.get("property_id"),
                "match_score": match.get("match_score", 0.0),
                "match_reasons": match.get("match_reasons", []),
                "price_match": match.get("price_match", {}),
                "location_match": match.get("location_match", {}),
                "feature_match": match.get("feature_match", {}),
                "buyer_info": match.get("buyer_info", {}),
                "property_info": match.get("property_info", {}),
                "recommended_action": match.get("recommended_action"),
                "priority": match.get("priority", "medium"),
                "expires_at": match.get("expires_at"),
                "matched_at": datetime.utcnow().isoformat()
            }
            standardized_matches.append(match_data)
        
        # Update workflow state
        state["matches"] = standardized_matches

    async def _cache_metrics(self, statistics: Dict[str, Any]) -> None:
        """Cache key metrics for monitoring."""
        try:
            # Cache individual metrics
            await self._cache_set("buyer_matcher:last_run", datetime.utcnow().isoformat(), ttl=86400)
            await self._cache_set("buyer_matcher:matches_generated", statistics["matches_generated"], ttl=3600)
            await self._cache_set("buyer_matcher:buyers_processed", statistics["buyers_processed"], ttl=3600)
            
            # Cache performance metrics
            await self._cache_set("buyer_matcher:avg_match_score", statistics.get("avg_match_score", 0.0), ttl=3600)
            await self._cache_set("buyer_matcher:execution_time", statistics.get("execution_time", 0), ttl=3600)
            
            # Cache aggregated daily statistics
            daily_key = f"buyer_matcher:daily:{datetime.utcnow().strftime('%Y%m%d')}"
            daily_stats = await self._cache_get(daily_key) or {
                "runs": 0,
                "total_matches": 0,
                "total_buyers": 0,
                "total_alerts": 0
            }
            
            daily_stats["runs"] += 1
            daily_stats["total_matches"] += statistics["matches_generated"]
            daily_stats["total_buyers"] += statistics["buyers_processed"]
            daily_stats["total_alerts"] += statistics["alerts_created"]
            
            await self._cache_set(daily_key, daily_stats, ttl=86400)
            
        except Exception as e:
            self.logger.warning(f"Failed to cache metrics: {e}")

    async def get_buyer_matches(self, buyer_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent matches for a specific buyer."""
        try:
            cache_key = f"buyer_matcher:buyer_matches:{buyer_id}:{limit}"
            cached = await self._cache_get(cache_key)
            if cached:
                return cached
            
            async with get_db_session() as session:
                result = await session.execute(
                    """
                    SELECT * FROM buyer_matches 
                    WHERE buyer_id = :buyer_id 
                    AND created_at >= NOW() - INTERVAL '7 days'
                    ORDER BY match_score DESC, created_at DESC 
                    LIMIT :limit
                    """,
                    {"buyer_id": buyer_id, "limit": limit}
                )
                
                matches = [dict(row) for row in result.fetchall()]
                
                # Cache for 30 minutes
                await self._cache_set(cache_key, matches, ttl=1800)
                
                return matches
                
        except Exception as e:
            self.logger.error(f"Failed to get buyer matches for {buyer_id}: {e}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get current matching statistics."""
        try:
            stats = {}
            
            # Get current hour stats
            current_hour_key = f"buyer_matcher:recent:{datetime.utcnow().strftime('%Y%m%d_%H')}"
            current_data = await self._cache_get(current_hour_key)
            if current_data:
                stats["current_hour"] = current_data.get("statistics", {})
            
            # Get daily stats
            daily_key = f"buyer_matcher:daily:{datetime.utcnow().strftime('%Y%m%d')}"
            daily_data = await self._cache_get(daily_key)
            if daily_data:
                stats["today"] = daily_data
            
            # Get performance metrics
            stats["performance"] = {
                "avg_match_score": await self._cache_get("buyer_matcher:avg_match_score") or 0.0,
                "last_execution_time": await self._cache_get("buyer_matcher:execution_time") or 0.0,
                "last_run": await self._cache_get("buyer_matcher:last_run")
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}

    def __repr__(self) -> str:
        return f"<BuyerMatchmakerNode(min_score={self.min_match_score})>"