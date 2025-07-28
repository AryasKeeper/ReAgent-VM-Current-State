"""
ReAgent Sydney - Listing Watcher AU Agent

The most critical component of the ReAgent Sydney system, responsible for
hourly monitoring of Australian property listings with delta detection.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from decimal import Decimal
import structlog

from langchain.tools import Tool
from crewai import Agent, Task

from reagent_sydney.agents.base import (
    BaseReAgentAgent, AgentConfig, AgentRole, AgentPriority
)
from reagent_sydney.core.database.engine import get_db_session
from reagent_sydney.core.cache.redis_client import get_cache_manager
from reagent_sydney.data.models.property_models import (
    Property, PropertyPriceHistory, Agent as PropertyAgent, Agency
)
from reagent_sydney.services.external_apis.domain_client import DomainAPIClient
from reagent_sydney.services.external_apis.realestate_client import RealEstateAPIClient
from reagent_sydney.utils.validation import validate_property_data
from reagent_sydney.config.settings import get_settings

from .delta_detector import PropertyDeltaDetector
from .data_enricher import PropertyDataEnricher
from .tools import ListingWatcherTools


logger = structlog.get_logger(__name__)


class ListingWatcherAgent(BaseReAgentAgent):
    """
    Production-ready Listing Watcher AU agent for continuous property monitoring.
    
    Features:
    - Hourly monitoring of Domain.com.au and RealEstate.com.au
    - Delta detection for new and changed listings
    - Data enrichment and validation
    - Database integration with TimescaleDB
    - Rate limiting and error recovery
    - Comprehensive logging and metrics
    """
    
    # Sydney Metro postcodes (2000-2999)
    SYDNEY_POSTCODES = [str(pc) for pc in range(2000, 3000)]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the Listing Watcher agent."""
        if not config:
            config = AgentConfig(
                name="Listing Watcher AU",
                role=AgentRole.DATA_COLLECTOR,
                description="Monitors Australian property listings with hourly delta detection",
                version="1.0.0",
                priority=AgentPriority.CRITICAL,
                max_execution_time=3600,  # 1 hour
                max_retries=3,
                max_api_calls_per_hour=2000,  # Combined Domain + REA limits
                required_services=["database", "cache"],
                required_tools=["search_listings", "detect_deltas", "enrich_data"],
                custom_settings={
                    "scraping_interval": 3600,  # 1 hour
                    "batch_size": 100,
                    "max_concurrent_requests": 5,
                    "sydney_only": True,
                    "enable_delta_detection": True,
                    "enable_data_enrichment": True
                }
            )
        
        super().__init__(config)
        
        # Initialize services
        self.settings = get_settings()
        self.delta_detector = PropertyDeltaDetector()
        self.data_enricher = PropertyDataEnricher()
        self.tools_handler = ListingWatcherTools()
        
        # API clients (initialized in _initialize_agent)
        self.domain_client: Optional[DomainAPIClient] = None
        self.realestate_client: Optional[RealEstateAPIClient] = None
        
        # Execution state
        self.last_scan_time: Optional[datetime] = None
        self.processed_listings: Set[str] = set()
        self.scan_statistics = {
            "total_listings": 0,
            "new_listings": 0,
            "updated_listings": 0,
            "errors": 0
        }
    
    async def _initialize_agent(self) -> None:
        """Initialize agent-specific components."""
        # Initialize API clients
        self.domain_client = DomainAPIClient()
        self.realestate_client = RealEstateAPIClient()
        
        # Initialize delta detector
        await self.delta_detector.initialize()
        
        # Initialize data enricher
        await self.data_enricher.initialize()
        
        # Load last scan time from cache
        last_scan = await self.cache_manager.get("listing_watcher:last_scan")
        if last_scan:
            self.last_scan_time = datetime.fromisoformat(last_scan)
        
        logger.info(
            "Listing Watcher AU agent initialized",
            last_scan_time=self.last_scan_time,
            sydney_postcodes_count=len(self.SYDNEY_POSTCODES)
        )
    
    async def _cleanup_agent(self) -> None:
        """Cleanup agent resources."""
        if self.domain_client:
            await self.domain_client.__aexit__(None, None, None)
        
        if self.realestate_client:
            await self.realestate_client.__aexit__(None, None, None)
        
        # Save last scan time to cache
        if self.last_scan_time:
            await self.cache_manager.set(
                "listing_watcher:last_scan",
                self.last_scan_time.isoformat(),
                ttl=86400 * 7  # 1 week
            )
    
    async def _execute_agent_logic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main agent execution logic for property listing monitoring.
        
        Args:
            input_data: Execution parameters
            
        Returns:
            Execution results with statistics
        """
        start_time = datetime.utcnow()
        self.scan_statistics = {
            "total_listings": 0,
            "new_listings": 0,
            "updated_listings": 0,
            "errors": 0,
            "sources_processed": []
        }
        
        try:
            # Extract configuration
            config = input_data.get("config", {})
            postcodes = config.get("postcodes", self.SYDNEY_POSTCODES)
            property_types = config.get("property_types")
            force_full_scan = config.get("force_full_scan", False)
            
            # Check if we should run (hourly by default)
            if not force_full_scan and not self._should_run_scan():
                return {
                    "status": "skipped",
                    "reason": "Too soon since last scan",
                    "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None
                }
            
            logger.info(
                "Starting property listing scan",
                postcodes_count=len(postcodes),
                property_types=property_types,
                force_full_scan=force_full_scan
            )
            
            # Process Domain.com.au listings
            if self.settings.apis.domain_api_key:
                await self._process_domain_listings(postcodes, property_types)
                self.scan_statistics["sources_processed"].append("domain")
            
            # Process RealEstate.com.au listings
            if self.settings.apis.rea_api_key:
                await self._process_realestate_listings(postcodes, property_types)
                self.scan_statistics["sources_processed"].append("realestate")
            
            # Update scan timestamp
            self.last_scan_time = start_time
            
            # Generate summary
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "status": "completed",
                "scan_time": start_time.isoformat(),
                "execution_time_seconds": execution_time,
                "statistics": self.scan_statistics,
                "next_scan_due": (start_time + timedelta(hours=1)).isoformat()
            }
            
            logger.info(
                "Property listing scan completed",
                **self.scan_statistics,
                execution_time=execution_time
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Property listing scan failed",
                error=str(e),
                **self.scan_statistics
            )
            raise
    
    async def _process_domain_listings(
        self, 
        postcodes: List[str], 
        property_types: Optional[List[str]]
    ) -> None:
        """Process listings from Domain.com.au."""
        async with self.domain_client as client:
            page = 1
            processed_count = 0
            
            while True:
                try:
                    # Search listings
                    search_results = await client.search_listings(
                        postcodes=postcodes,
                        property_types=property_types,
                        listing_type="Sale",
                        max_results=100,
                        page=page
                    )
                    
                    listings = search_results.get("listings", [])
                    if not listings:
                        break
                    
                    # Process listings in batches
                    batch_size = self.config.custom_settings.get("batch_size", 100)
                    for i in range(0, len(listings), batch_size):
                        batch = listings[i:i + batch_size]
                        await self._process_listing_batch(batch, "domain", client)
                    
                    processed_count += len(listings)
                    self.scan_statistics["total_listings"] += len(listings)
                    
                    # Check if we should continue
                    if len(listings) < 100:  # Last page
                        break
                    
                    page += 1
                    
                    # Rate limiting delay
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(
                        "Error processing Domain listings",
                        page=page,
                        error=str(e)
                    )
                    self.scan_statistics["errors"] += 1
                    break
            
            logger.info(
                "Domain listings processed",
                processed_count=processed_count,
                pages=page
            )
    
    async def _process_realestate_listings(
        self, 
        postcodes: List[str], 
        property_types: Optional[List[str]]
    ) -> None:
        """Process listings from RealEstate.com.au."""
        async with self.realestate_client as client:
            page = 1
            processed_count = 0
            
            while True:
                try:
                    # Search listings
                    search_results = await client.search_listings(
                        postcodes=postcodes,
                        property_types=property_types,
                        listing_type="buy",
                        max_results=100,
                        page=page
                    )
                    
                    # Extract listings from tiered results
                    listings = []
                    for tier in search_results.get("tieredResults", []):
                        listings.extend(tier.get("results", []))
                    
                    if not listings:
                        break
                    
                    # Process listings in batches
                    batch_size = self.config.custom_settings.get("batch_size", 100)
                    for i in range(0, len(listings), batch_size):
                        batch = listings[i:i + batch_size]
                        await self._process_listing_batch(batch, "realestate", client)
                    
                    processed_count += len(listings)
                    self.scan_statistics["total_listings"] += len(listings)
                    
                    # Check if we should continue
                    if len(listings) < 100:  # Last page
                        break
                    
                    page += 1
                    
                    # Rate limiting delay
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(
                        "Error processing RealEstate listings",
                        page=page,
                        error=str(e)
                    )
                    self.scan_statistics["errors"] += 1
                    break
            
            logger.info(
                "RealEstate listings processed",
                processed_count=processed_count,
                pages=page
            )
    
    async def _process_listing_batch(
        self,
        listings: List[Dict[str, Any]],
        source: str,
        client: Any
    ) -> None:
        """Process a batch of listings with delta detection."""
        tasks = []
        semaphore = asyncio.Semaphore(
            self.config.custom_settings.get("max_concurrent_requests", 5)
        )
        
        for listing_data in listings:
            task = self._process_single_listing(listing_data, source, client, semaphore)
            tasks.append(task)
        
        # Execute all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_single_listing(
        self,
        listing_data: Dict[str, Any],
        source: str,
        client: Any,
        semaphore: asyncio.Semaphore
    ) -> None:
        """Process a single property listing."""
        async with semaphore:
            try:
                # Normalize data
                if source == "domain":
                    normalized_data = client.normalize_property_data(listing_data)
                else:
                    normalized_data = client.normalize_property_data(listing_data)
                
                # Validate data
                validated_data = validate_property_data(normalized_data)
                
                if "_validation_errors" in validated_data:
                    logger.warning(
                        "Property data validation issues",
                        listing_id=validated_data.get("listing_id"),
                        errors=validated_data["_validation_errors"]
                    )
                
                # Check for delta
                listing_id = validated_data["listing_id"]
                delta_result = await self.delta_detector.detect_changes(
                    listing_id, validated_data
                )
                
                if delta_result["is_new"]:
                    await self._handle_new_listing(validated_data)
                    self.scan_statistics["new_listings"] += 1
                    
                elif delta_result["has_changes"]:
                    await self._handle_updated_listing(
                        validated_data, 
                        delta_result["changes"]
                    )
                    self.scan_statistics["updated_listings"] += 1
                
                self.processed_listings.add(listing_id)
                
            except Exception as e:
                logger.error(
                    "Error processing listing",
                    listing_id=listing_data.get("id"),
                    source=source,
                    error=str(e)
                )
                self.scan_statistics["errors"] += 1
    
    async def _handle_new_listing(self, property_data: Dict[str, Any]) -> None:
        """Handle a new property listing."""
        try:
            # Enrich data if enabled
            if self.config.custom_settings.get("enable_data_enrichment", True):
                property_data = await self.data_enricher.enrich_property_data(property_data)
            
            # Save to database
            async with get_db_session() as session:
                # Create property record
                property_record = Property(**{
                    key: value for key, value in property_data.items()
                    if hasattr(Property, key) and value is not None
                })
                
                session.add(property_record)
                await session.commit()
                await session.refresh(property_record)
                
                # Create initial price history record
                if property_data.get("price"):
                    price_history = PropertyPriceHistory(
                        property_id=property_record.id,
                        price=property_data["price"],
                        price_display=property_data.get("price_display", ""),
                        price_type="asking",
                        source=property_data["source"],
                        event_type="listing"
                    )
                    session.add(price_history)
                    await session.commit()
            
            logger.info(
                "New property listing saved",
                listing_id=property_data["listing_id"],
                suburb=property_data.get("suburb"),
                price=property_data.get("price")
            )
            
        except Exception as e:
            logger.error(
                "Failed to save new listing",
                listing_id=property_data.get("listing_id"),
                error=str(e)
            )
            raise
    
    async def _handle_updated_listing(
        self, 
        property_data: Dict[str, Any], 
        changes: Dict[str, Any]
    ) -> None:
        """Handle an updated property listing."""
        try:
            async with get_db_session() as session:
                # Find existing property
                existing_property = await session.execute(
                    "SELECT * FROM properties WHERE listing_id = :listing_id",
                    {"listing_id": property_data["listing_id"]}
                )
                existing_property = existing_property.fetchone()
                
                if not existing_property:
                    logger.warning(
                        "Property not found for update",
                        listing_id=property_data["listing_id"]
                    )
                    return
                
                # Update property record
                update_data = {
                    key: value for key, value in property_data.items()
                    if hasattr(Property, key) and value is not None
                }
                update_data["updated_at"] = datetime.utcnow()
                
                await session.execute(
                    "UPDATE properties SET updated_at = :updated_at WHERE listing_id = :listing_id",
                    {
                        "updated_at": update_data["updated_at"],
                        "listing_id": property_data["listing_id"]
                    }
                )
                
                # Handle price changes
                if "price" in changes and property_data.get("price"):
                    price_history = PropertyPriceHistory(
                        property_id=existing_property.id,
                        price=property_data["price"],
                        price_display=property_data.get("price_display", ""),
                        price_type="asking",
                        previous_price=changes["price"]["old_value"],
                        price_change=property_data["price"] - changes["price"]["old_value"],
                        source=property_data["source"],
                        event_type="update"
                    )
                    session.add(price_history)
                
                await session.commit()
            
            logger.info(
                "Property listing updated",
                listing_id=property_data["listing_id"],
                changes=list(changes.keys())
            )
            
        except Exception as e:
            logger.error(
                "Failed to update listing",
                listing_id=property_data.get("listing_id"),
                error=str(e)
            )
            raise
    
    def _should_run_scan(self) -> bool:
        """Determine if we should run a scan based on timing."""
        if not self.last_scan_time:
            return True
        
        interval = self.config.custom_settings.get("scraping_interval", 3600)
        next_scan_time = self.last_scan_time + timedelta(seconds=interval)
        
        return datetime.utcnow() >= next_scan_time
    
    async def _initialize_tools(self) -> List[Tool]:
        """Initialize CrewAI tools for the agent."""
        return await self.tools_handler.get_tools(self)
    
    def _get_agent_goal(self) -> str:
        """Get agent goal for CrewAI."""
        return (
            "Monitor Australian property listings from multiple sources, "
            "detect changes in real-time, and maintain accurate property "
            "data for the Sydney real estate market."
        )
    
    def _get_agent_backstory(self) -> str:
        """Get agent backstory for CrewAI."""
        return (
            "You are the Listing Watcher AU, the foundation of the ReAgent Sydney "
            "real estate intelligence system. Your role is critical - you continuously "
            "monitor Domain.com.au and RealEstate.com.au for property listings across "
            "Sydney, detecting new listings and price changes with sub-hour accuracy. "
            "You process thousands of listings daily, ensuring the system has the most "
            "up-to-date property data for agents, investors, and buyers."
        )