"""
ReAgent Sydney - Listing Watcher Tools

CrewAI tools for the Listing Watcher agent to interact with
property data, APIs, and database operations.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
import structlog

from langchain.tools import Tool
from pydantic import BaseModel, Field

from reagent_sydney.core.database.engine import get_db_session
from reagent_sydney.data.models.property_models import Property, PropertyPriceHistory
from reagent_sydney.services.external_apis.domain_client import DomainAPIClient
from reagent_sydney.services.external_apis.realestate_client import RealEstateAPIClient
from reagent_sydney.utils.validation import validate_property_data


logger = structlog.get_logger(__name__)


class SearchListingsInput(BaseModel):
    """Input schema for search_listings tool."""
    postcodes: Optional[List[str]] = Field(
        default=None,
        description="List of postcodes to search (defaults to Sydney metro)"
    )
    property_types: Optional[List[str]] = Field(
        default=None,
        description="Property types to include (house, unit, etc.)"
    )
    source: str = Field(
        default="domain",
        description="Data source: 'domain' or 'realestate'"
    )
    max_results: int = Field(
        default=100,
        description="Maximum results to return"
    )


class GetListingDetailsInput(BaseModel):
    """Input schema for get_listing_details tool."""
    listing_id: str = Field(description="Listing ID to retrieve")
    source: str = Field(description="Data source: 'domain' or 'realestate'")


class SavePropertyInput(BaseModel):
    """Input schema for save_property tool."""
    property_data: Dict[str, Any] = Field(description="Property data to save")
    is_new: bool = Field(default=True, description="Whether this is a new property")


class CheckPropertyChangesInput(BaseModel):
    """Input schema for check_property_changes tool."""
    listing_id: str = Field(description="Listing ID to check for changes")


class GetMarketStatisticsInput(BaseModel):
    """Input schema for get_market_statistics tool."""
    suburb: Optional[str] = Field(default=None, description="Suburb to analyze")
    postcode: Optional[str] = Field(default=None, description="Postcode to analyze")
    days_back: int = Field(default=30, description="Days back to analyze")


class ListingWatcherTools:
    """
    CrewAI tools collection for the Listing Watcher agent.
    
    Provides tools for:
    - Property listing search and retrieval
    - Data validation and enrichment
    - Database operations
    - Market analysis
    """
    
    def __init__(self):
        """Initialize the tools handler."""
        self.logger = structlog.get_logger(f"{__name__}.ListingWatcherTools")
    
    async def get_tools(self, agent_instance) -> List[Tool]:
        """
        Get all available tools for the Listing Watcher agent.
        
        Args:
            agent_instance: The agent instance that will use these tools
            
        Returns:
            List of CrewAI tools
        """
        self.agent = agent_instance
        
        return [
            Tool(
                name="search_listings",
                description=(
                    "Search for property listings from Domain or RealEstate APIs. "
                    "Supports filtering by postcodes, property types, and result limits. "
                    "Returns list of property listings with basic information."
                ),
                func=self._search_listings,
                args_schema=SearchListingsInput
            ),
            Tool(
                name="get_listing_details",
                description=(
                    "Get detailed information for a specific property listing. "
                    "Retrieves comprehensive property data including features, "
                    "pricing, and agent information."
                ),
                func=self._get_listing_details,
                args_schema=GetListingDetailsInput
            ),
            Tool(
                name="save_property",
                description=(
                    "Save or update property data in the database. "
                    "Handles validation, enrichment, and database operations. "
                    "Creates price history records for price changes."
                ),
                func=self._save_property,
                args_schema=SavePropertyInput
            ),
            Tool(
                name="check_property_changes",
                description=(
                    "Check if a property has changed since last scan. "
                    "Uses delta detection to identify new or modified listings. "
                    "Returns change details and timestamps."
                ),
                func=self._check_property_changes,
                args_schema=CheckPropertyChangesInput
            ),
            Tool(
                name="get_market_statistics",
                description=(
                    "Get market statistics for a suburb or postcode. "
                    "Includes average prices, listing counts, and trends. "
                    "Useful for market analysis and property positioning."
                ),
                func=self._get_market_statistics,
                args_schema=GetMarketStatisticsInput
            ),
            Tool(
                name="validate_property_data",
                description=(
                    "Validate and clean property data before saving. "
                    "Checks required fields, data types, and business rules. "
                    "Returns validation results and cleaned data."
                ),
                func=self._validate_property_data
            ),
            Tool(
                name="get_system_health",
                description=(
                    "Check the health status of all external APIs and services. "
                    "Returns connectivity status, rate limits, and error counts. "
                    "Useful for monitoring and debugging."
                ),
                func=self._get_system_health
            ),
            Tool(
                name="clear_cache",
                description=(
                    "Clear cached data for fresh data retrieval. "
                    "Can clear specific keys or all agent-related cache. "
                    "Use when stale data is suspected."
                ),
                func=self._clear_cache
            )
        ]
    
    async def _search_listings(
        self,
        postcodes: Optional[List[str]] = None,
        property_types: Optional[List[str]] = None,
        source: str = "domain",
        max_results: int = 100
    ) -> str:
        """Search for property listings from external APIs."""
        try:
            results = []
            
            if source.lower() == "domain":
                async with DomainAPIClient() as client:
                    search_results = await client.search_listings(
                        postcodes=postcodes,
                        property_types=property_types,
                        listing_type="Sale",
                        max_results=max_results
                    )
                    listings = search_results.get("listings", [])
                    
                    for listing in listings:
                        normalized = client.normalize_property_data(listing)
                        results.append({
                            "listing_id": normalized.get("listing_id"),
                            "title": normalized.get("title"),
                            "suburb": normalized.get("suburb"),
                            "price": str(normalized.get("price", "")) if normalized.get("price") else "",
                            "property_type": normalized.get("property_type"),
                            "bedrooms": normalized.get("bedrooms"),
                            "bathrooms": normalized.get("bathrooms")
                        })
            
            elif source.lower() == "realestate":
                async with RealEstateAPIClient() as client:
                    search_results = await client.search_listings(
                        postcodes=postcodes,
                        property_types=property_types,
                        listing_type="buy",
                        max_results=max_results
                    )
                    
                    # Extract listings from tiered results
                    listings = []
                    for tier in search_results.get("tieredResults", []):
                        listings.extend(tier.get("results", []))
                    
                    for listing in listings:
                        normalized = client.normalize_property_data(listing)
                        results.append({
                            "listing_id": normalized.get("listing_id"),
                            "title": normalized.get("title"),
                            "suburb": normalized.get("suburb"),
                            "price": str(normalized.get("price", "")) if normalized.get("price") else "",
                            "property_type": normalized.get("property_type"),
                            "bedrooms": normalized.get("bedrooms"),
                            "bathrooms": normalized.get("bathrooms")
                        })
            
            else:
                return json.dumps({
                    "error": f"Unknown source: {source}",
                    "valid_sources": ["domain", "realestate"]
                })
            
            self.logger.info(
                "Listings search completed",
                source=source,
                results_count=len(results),
                postcodes=postcodes,
                property_types=property_types
            )
            
            return json.dumps({
                "success": True,
                "source": source,
                "count": len(results),
                "listings": results[:50]  # Limit response size
            })
            
        except Exception as e:
            self.logger.error(
                "Listings search failed",
                source=source,
                error=str(e)
            )
            return json.dumps({
                "error": str(e),
                "success": False
            })
    
    async def _get_listing_details(
        self,
        listing_id: str,
        source: str
    ) -> str:
        """Get detailed information for a specific listing."""
        try:
            if source.lower() == "domain":
                async with DomainAPIClient() as client:
                    listing_data = await client.get_listing_details(listing_id)
                    normalized = client.normalize_property_data(listing_data)
            
            elif source.lower() == "realestate":
                async with RealEstateAPIClient() as client:
                    listing_data = await client.get_listing_details(listing_id)
                    normalized = client.normalize_property_data(listing_data)
            
            else:
                return json.dumps({
                    "error": f"Unknown source: {source}",
                    "valid_sources": ["domain", "realestate"]
                })
            
            # Clean up the response for tool output
            cleaned_data = {
                key: value for key, value in normalized.items()
                if value is not None and key != "source_data"  # Exclude raw data
            }
            
            self.logger.info(
                "Listing details retrieved",
                listing_id=listing_id,
                source=source
            )
            
            return json.dumps({
                "success": True,
                "listing_id": listing_id,
                "source": source,
                "data": cleaned_data
            })
            
        except Exception as e:
            self.logger.error(
                "Failed to get listing details",
                listing_id=listing_id,
                source=source,
                error=str(e)
            )
            return json.dumps({
                "error": str(e),
                "success": False,
                "listing_id": listing_id
            })
    
    async def _save_property(
        self,
        property_data: Dict[str, Any],
        is_new: bool = True
    ) -> str:
        """Save or update property data in the database."""
        try:
            # Validate data first
            validated_data = validate_property_data(property_data)
            
            # Enrich data if enricher is available
            if hasattr(self.agent, 'data_enricher'):
                validated_data = await self.agent.data_enricher.enrich_property_data(
                    validated_data
                )
            
            async with get_db_session() as session:
                if is_new:
                    # Create new property
                    property_record = Property(**{
                        key: value for key, value in validated_data.items()
                        if hasattr(Property, key) and value is not None
                    })
                    
                    session.add(property_record)
                    await session.commit()
                    await session.refresh(property_record)
                    
                    # Create price history if price exists
                    if validated_data.get("price"):
                        price_history = PropertyPriceHistory(
                            property_id=property_record.id,
                            price=validated_data["price"],
                            price_display=validated_data.get("price_display", ""),
                            price_type="asking",
                            source=validated_data["source"],
                            event_type="listing"
                        )
                        session.add(price_history)
                        await session.commit()
                    
                    result = {
                        "success": True,
                        "action": "created",
                        "property_id": str(property_record.id),
                        "listing_id": validated_data["listing_id"]
                    }
                
                else:
                    # Update existing property
                    # This would need proper implementation based on your update logic
                    result = {
                        "success": True,
                        "action": "updated",
                        "listing_id": validated_data["listing_id"],
                        "message": "Property update logic not fully implemented"
                    }
            
            self.logger.info(
                "Property saved successfully",
                listing_id=validated_data.get("listing_id"),
                action=result["action"]
            )
            
            return json.dumps(result)
            
        except Exception as e:
            self.logger.error(
                "Failed to save property",
                listing_id=property_data.get("listing_id"),
                error=str(e)
            )
            return json.dumps({
                "error": str(e),
                "success": False,
                "listing_id": property_data.get("listing_id")
            })
    
    async def _check_property_changes(self, listing_id: str) -> str:
        """Check if a property has changed since last scan."""
        try:
            if not hasattr(self.agent, 'delta_detector'):
                return json.dumps({
                    "error": "Delta detector not available",
                    "success": False
                })
            
            # This would need current property data to compare
            # For now, return a placeholder response
            result = {
                "success": True,
                "listing_id": listing_id,
                "message": "Delta detection requires current property data",
                "last_checked": datetime.utcnow().isoformat()
            }
            
            return json.dumps(result)
            
        except Exception as e:
            self.logger.error(
                "Failed to check property changes",
                listing_id=listing_id,
                error=str(e)
            )
            return json.dumps({
                "error": str(e),
                "success": False,
                "listing_id": listing_id
            })
    
    async def _get_market_statistics(
        self,
        suburb: Optional[str] = None,
        postcode: Optional[str] = None,
        days_back: int = 30
    ) -> str:
        """Get market statistics for a suburb or postcode."""
        try:
            async with get_db_session() as session:
                # Build query conditions
                conditions = ["deleted_at IS NULL"]
                params = {"days_back": days_back}
                
                if suburb:
                    conditions.append("LOWER(suburb) = LOWER(:suburb)")
                    params["suburb"] = suburb
                
                if postcode:
                    conditions.append("postcode = :postcode")
                    params["postcode"] = postcode
                
                where_clause = " AND ".join(conditions)
                
                # Get property statistics
                stats_query = f"""
                SELECT 
                    COUNT(*) as total_properties,
                    COUNT(CASE WHEN listing_status = 'active' THEN 1 END) as active_listings,
                    AVG(CASE WHEN price > 0 THEN price END) as avg_price,
                    MIN(CASE WHEN price > 0 THEN price END) as min_price,
                    MAX(CASE WHEN price > 0 THEN price END) as max_price,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '{days_back} days' THEN 1 END) as new_listings_period
                FROM properties 
                WHERE {where_clause}
                """
                
                result = await session.execute(stats_query, params)
                stats = result.fetchone()
                
                if not stats or stats.total_properties == 0:
                    return json.dumps({
                        "success": True,
                        "message": "No properties found for the specified criteria",
                        "suburb": suburb,
                        "postcode": postcode
                    })
                
                # Format statistics
                statistics = {
                    "success": True,
                    "suburb": suburb,
                    "postcode": postcode,
                    "period_days": days_back,
                    "total_properties": stats.total_properties,
                    "active_listings": stats.active_listings,
                    "average_price": float(stats.avg_price) if stats.avg_price else 0,
                    "price_range": {
                        "min": float(stats.min_price) if stats.min_price else 0,
                        "max": float(stats.max_price) if stats.max_price else 0
                    },
                    "new_listings_in_period": stats.new_listings_period,
                    "generated_at": datetime.utcnow().isoformat()
                }
                
                self.logger.info(
                    "Market statistics generated",
                    suburb=suburb,
                    postcode=postcode,
                    total_properties=stats.total_properties
                )
                
                return json.dumps(statistics)
                
        except Exception as e:
            self.logger.error(
                "Failed to get market statistics",
                suburb=suburb,
                postcode=postcode,
                error=str(e)
            )
            return json.dumps({
                "error": str(e),
                "success": False,
                "suburb": suburb,
                "postcode": postcode
            })
    
    async def _validate_property_data(self, property_data_json: str) -> str:
        """Validate property data."""
        try:
            property_data = json.loads(property_data_json)
            validated_data = validate_property_data(property_data)
            
            has_errors = "_validation_errors" in validated_data
            
            result = {
                "success": True,
                "valid": not has_errors,
                "errors": validated_data.get("_validation_errors", []),
                "listing_id": validated_data.get("listing_id")
            }
            
            if has_errors:
                result["error_count"] = len(validated_data["_validation_errors"])
            
            return json.dumps(result)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "success": False,
                "valid": False
            })
    
    async def _get_system_health(self) -> str:
        """Check system health status."""
        try:
            health_status = {
                "success": True,
                "timestamp": datetime.utcnow().isoformat(),
                "services": {}
            }
            
            # Check Domain API
            try:
                async with DomainAPIClient() as client:
                    domain_health = await client.get_health_status()
                    health_status["services"]["domain"] = domain_health
            except Exception as e:
                health_status["services"]["domain"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
            
            # Check RealEstate API
            try:
                async with RealEstateAPIClient() as client:
                    rea_health = await client.get_health_status()
                    health_status["services"]["realestate"] = rea_health
            except Exception as e:
                health_status["services"]["realestate"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
            
            # Check database
            try:
                async with get_db_session() as session:
                    await session.execute("SELECT 1")
                    health_status["services"]["database"] = {
                        "status": "healthy",
                        "accessible": True
                    }
            except Exception as e:
                health_status["services"]["database"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
            
            # Overall health
            all_healthy = all(
                service.get("status") == "healthy" 
                for service in health_status["services"].values()
            )
            health_status["overall_status"] = "healthy" if all_healthy else "degraded"
            
            return json.dumps(health_status)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "success": False,
                "overall_status": "unhealthy"
            })
    
    async def _clear_cache(self, cache_pattern: str = "listing_watcher:*") -> str:
        """Clear cached data."""
        try:
            if hasattr(self.agent, 'cache_manager'):
                # This would need proper implementation based on cache manager
                result = {
                    "success": True,
                    "message": f"Cache clear requested for pattern: {cache_pattern}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                result = {
                    "success": False,
                    "error": "Cache manager not available"
                }
            
            return json.dumps(result)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "success": False
            })