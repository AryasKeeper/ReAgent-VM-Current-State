"""
ReAgent Sydney - Listing Watcher LangGraph Node

LangGraph node implementation for the Listing Watcher AU agent.
Monitors Australian property listings with hourly delta detection.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

from .base_node import BaseReAgentNode
from ..state import ReAgentState
from ...agents.listing_watcher.agent import ListingWatcherAgent
from ...core.database.engine import get_db_session
from ...data.models.property_models import Property


class ListingWatcherNode(BaseReAgentNode):
    """
    LangGraph node for Listing Watcher AU agent.
    
    Responsibilities:
    - Monitor Domain.com.au and RealEstate.com.au listings
    - Detect new and updated property listings
    - Enrich property data with additional information
    - Store results in PostgreSQL/TimescaleDB
    - Cache frequently accessed data in Redis
    """
    
    def __init__(self):
        super().__init__("Listing Watcher AU")
        
        # Initialize the actual agent
        self.agent = ListingWatcherAgent()
        
        # Node-specific configuration
        self.batch_size = 100
        self.max_concurrent_requests = 5
        self.sydney_postcodes = [str(pc) for pc in range(2000, 3000)]

    async def _execute_agent_logic(self, state: ReAgentState) -> Dict[str, Any]:
        """
        Execute listing watcher logic within LangGraph context.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dictionary containing discovered listings and metrics
        """
        # Get input configuration
        config = state.get("config", {})
        input_data = state.get("input_data", {})
        
        # Extract parameters
        postcodes = input_data.get("postcodes", self.sydney_postcodes)
        property_types = input_data.get("property_types", ["house", "unit", "townhouse"])
        max_listings = config.get("max_listings", 1000)
        enable_enrichment = config.get("enable_enrichment", True)
        
        # Check cache for recent results
        cache_key = f"listing_watcher:recent:{datetime.utcnow().strftime('%Y%m%d_%H')}"
        cached_results = await self._cache_get(cache_key)
        
        if cached_results and not config.get("force_refresh", False):
            self.logger.info("Using cached listing results")
            return cached_results
        
        # Initialize agent if not already done
        if not self.agent.is_initialized:
            await self.agent.initialize()
        
        try:
            # Execute the listing watcher agent
            agent_result = await self.agent.execute({
                "postcodes": postcodes,
                "property_types": property_types,
                "max_listings": max_listings,
                "enable_enrichment": enable_enrichment,
                "batch_size": self.batch_size
            })
            
            if not agent_result.get("success"):
                raise RuntimeError(f"Listing watcher agent failed: {agent_result.get('error')}")
            
            # Extract results
            listings_data = agent_result.get("data", {})
            
            # Process and structure the results for downstream agents
            result = {
                "listings": listings_data.get("listings", []),
                "new_listings": listings_data.get("new_listings", []),
                "updated_listings": listings_data.get("updated_listings", []),
                "removed_listings": listings_data.get("removed_listings", []),
                "statistics": {
                    "total_processed": len(listings_data.get("listings", [])),
                    "new_count": len(listings_data.get("new_listings", [])),
                    "updated_count": len(listings_data.get("updated_listings", [])),
                    "removed_count": len(listings_data.get("removed_listings", [])),
                    "postcodes_scanned": len(postcodes),
                    "execution_time": agent_result.get("execution_time", 0)
                },
                "metadata": {
                    "last_scan": datetime.utcnow().isoformat(),
                    "postcodes": postcodes,
                    "property_types": property_types,
                    "enrichment_enabled": enable_enrichment
                }
            }
            
            # Update workflow state with discovered properties
            self._update_state_properties(state, result["listings"])
            
            # Cache results for 1 hour
            await self._cache_set(cache_key, result, ttl=3600)
            
            # Store summary metrics in cache for monitoring
            await self._cache_metrics(result["statistics"])
            
            self.logger.info(
                f"Listing watcher completed: {result['statistics']['total_processed']} properties processed, "
                f"{result['statistics']['new_count']} new, {result['statistics']['updated_count']} updated"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Listing watcher execution failed: {e}", exc_info=True)
            raise

    def _update_state_properties(self, state: ReAgentState, listings: List[Dict[str, Any]]) -> None:
        """Update the workflow state with discovered properties."""
        # Convert listings to standardized format for downstream agents
        standardized_properties = []
        
        for listing in listings:
            property_data = {
                "id": listing.get("id"),
                "address": listing.get("address"),
                "suburb": listing.get("suburb"),
                "postcode": listing.get("postcode"),
                "state": listing.get("state", "NSW"),
                "property_type": listing.get("property_type"),
                "bedrooms": listing.get("bedrooms"),
                "bathrooms": listing.get("bathrooms"),
                "parking": listing.get("parking"),
                "land_size": listing.get("land_size"),
                "floor_area": listing.get("floor_area"),
                "price": listing.get("price"),
                "price_display": listing.get("price_display"),
                "listing_type": listing.get("listing_type"),  # sale/rent
                "listing_date": listing.get("listing_date"),
                "updated_date": listing.get("updated_date"),
                "source": listing.get("source"),  # domain/rea
                "url": listing.get("url"),
                "images": listing.get("images", []),
                "description": listing.get("description"),
                "features": listing.get("features", []),
                "agent_info": listing.get("agent_info", {}),
                "geo_location": listing.get("geo_location", {}),
                "market_insights": listing.get("market_insights", {}),
                "discovered_at": datetime.utcnow().isoformat()
            }
            standardized_properties.append(property_data)
        
        # Update workflow state
        state["properties"] = standardized_properties

    async def _cache_metrics(self, statistics: Dict[str, Any]) -> None:
        """Cache key metrics for monitoring and alerting."""
        try:
            # Cache individual metrics
            await self._cache_set("listing_watcher:last_run", datetime.utcnow().isoformat(), ttl=86400)
            await self._cache_set("listing_watcher:total_processed", statistics["total_processed"], ttl=3600)
            await self._cache_set("listing_watcher:new_count", statistics["new_count"], ttl=3600)
            await self._cache_set("listing_watcher:updated_count", statistics["updated_count"], ttl=3600)
            
            # Cache aggregated daily statistics
            daily_key = f"listing_watcher:daily:{datetime.utcnow().strftime('%Y%m%d')}"
            daily_stats = await self._cache_get(daily_key) or {
                "runs": 0,
                "total_processed": 0,
                "new_listings": 0,
                "updated_listings": 0
            }
            
            daily_stats["runs"] += 1
            daily_stats["total_processed"] += statistics["total_processed"]
            daily_stats["new_listings"] += statistics["new_count"]
            daily_stats["updated_listings"] += statistics["updated_count"]
            
            await self._cache_set(daily_key, daily_stats, ttl=86400)
            
        except Exception as e:
            self.logger.warning(f"Failed to cache metrics: {e}")

    async def get_recent_listings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent listings from cache or database."""
        try:
            # Try cache first
            cache_key = f"listing_watcher:recent_listings:{limit}"
            cached = await self._cache_get(cache_key)
            if cached:
                return cached
            
            # Fallback to database
            async with get_db_session() as session:
                result = await session.execute(
                    """
                    SELECT * FROM properties 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY created_at DESC 
                    LIMIT :limit
                    """,
                    {"limit": limit}
                )
                
                listings = [dict(row) for row in result.fetchall()]
                
                # Cache for 15 minutes
                await self._cache_set(cache_key, listings, ttl=900)
                
                return listings
                
        except Exception as e:
            self.logger.error(f"Failed to get recent listings: {e}")
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """Get current statistics from cache."""
        try:
            stats = {}
            
            # Get current hour stats
            current_hour_key = f"listing_watcher:recent:{datetime.utcnow().strftime('%Y%m%d_%H')}"
            current_data = await self._cache_get(current_hour_key)
            if current_data:
                stats["current_hour"] = current_data.get("statistics", {})
            
            # Get daily stats
            daily_key = f"listing_watcher:daily:{datetime.utcnow().strftime('%Y%m%d')}"
            daily_data = await self._cache_get(daily_key)
            if daily_data:
                stats["today"] = daily_data
            
            # Get last run time
            last_run = await self._cache_get("listing_watcher:last_run")
            if last_run:
                stats["last_run"] = last_run
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}

    def __repr__(self) -> str:
        return f"<ListingWatcherNode(postcodes={len(self.sydney_postcodes)})>"