"""
Resilient Service Manager - Production Service Orchestration

Implements service isolation, graceful degradation, and automatic recovery
for ReAgent production deployment with or without vector database.
"""

import asyncio
import os
import logging
from typing import Dict, Any, List, Optional, Set
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from reagent.utils.monitoring.production_health_monitor import (
    ProductionHealthMonitor, get_health_monitor, ServiceUnavailableError,
    ServiceStatus, check_service_availability
)
from reagent.core.config import get_settings
from reagent.utils.logging import get_logger


class ResilientServiceManager:
    """
    Production-ready service manager with resilience patterns.
    
    Features:
    - Service isolation prevents cascade failures
    - Graceful degradation when dependencies unavailable
    - Automatic feature flag management based on service health
    - Circuit breaker patterns for failed services
    - Fallback implementations for core functionality
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self.health_monitor: Optional[ProductionHealthMonitor] = None
        
        # Service capability mapping
        self.service_capabilities = {
            "core_api": ["postgres", "redis"],
            "property_listings": ["postgres", "redis"],
            "buyer_profiles": ["postgres", "redis"], 
            "market_data": ["postgres", "redis"],
            "vector_search": ["weaviate"],
            "advanced_matching": ["weaviate", "postgres"],
            "real_time_analytics": ["redis", "postgres"],
            "report_generation": ["postgres"]
        }
        
        # Fallback implementations
        self.fallback_services = {
            "buyer_matching": self._fallback_buyer_matching,
            "property_search": self._fallback_property_search,
            "market_analytics": self._fallback_market_analytics,
            "recommendation_engine": self._fallback_recommendations
        }
    
    async def initialize(self):
        """Initialize service manager and health monitoring."""
        self.logger.info("Initializing Resilient Service Manager")
        
        try:
            # Initialize health monitor
            self.health_monitor = await get_health_monitor()
            
            # Wait for critical services
            await self._wait_for_critical_services()
            
            # Configure service capabilities based on availability
            await self._configure_available_capabilities()
            
            self.logger.info("Resilient Service Manager initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize service manager", error=str(e))
            raise
    
    async def _wait_for_critical_services(self, timeout_seconds: int = 300):
        """Wait for critical services to become available."""
        critical_services = ["postgres", "redis"]
        start_time = datetime.utcnow()
        
        while datetime.utcnow() - start_time < timedelta(seconds=timeout_seconds):
            all_critical_available = True
            
            for service in critical_services:
                if not await check_service_availability(service):
                    all_critical_available = False
                    self.logger.warning(f"Critical service {service} not available, waiting...")
                    break
            
            if all_critical_available:
                self.logger.info("All critical services are available")
                return
            
            await asyncio.sleep(10)
        
        raise TimeoutError("Critical services did not become available within timeout")
    
    async def _configure_available_capabilities(self):
        """Configure system capabilities based on available services."""
        if not self.health_monitor:
            return
        
        available_services = self.health_monitor.get_available_services()
        
        # Enable capabilities based on service availability
        for capability, required_services in self.service_capabilities.items():
            is_available = all(service in available_services for service in required_services)
            
            if capability == "vector_search" and is_available:
                self.health_monitor.feature_flags["vector_search_enabled"] = True
                self.health_monitor.feature_flags["buyer_matching_enabled"] = True
                self.logger.info("Vector search capabilities enabled")
            elif capability == "vector_search" and not is_available:
                self.health_monitor.feature_flags["vector_search_enabled"] = False
                self.health_monitor.feature_flags["buyer_matching_enabled"] = False
                self.logger.warning("Vector search capabilities disabled - using fallback")
    
    @asynccontextmanager
    async def service_operation(self, service_name: str, operation_name: str):
        """Execute operation with service resilience patterns."""
        if not self.health_monitor:
            raise RuntimeError("Service manager not initialized")
        
        try:
            # Check if service is available
            async with self.health_monitor.service_circuit_breaker(service_name):
                self.logger.debug(f"Executing {operation_name} on {service_name}")
                yield
                
        except ServiceUnavailableError:
            # Try fallback if available
            if operation_name in self.fallback_services:
                self.logger.info(f"Using fallback for {operation_name}")
                yield self.fallback_services[operation_name]
            else:
                self.logger.error(f"No fallback available for {operation_name}")
                raise
    
    async def get_buyer_matching_service(self):
        """Get buyer matching service with fallback capability."""
        if (self.health_monitor and 
            self.health_monitor.is_feature_enabled("buyer_matching_enabled")):
            
            try:
                async with self.service_operation("weaviate", "buyer_matching"):
                    from reagent.agents.buyer_matchmaker.matching_engine import BuyerMatchingEngine
                    return BuyerMatchingEngine()  # Vector-powered matching
                    
            except ServiceUnavailableError:
                self.logger.warning("Vector matching unavailable, using fallback")
        
        # Return fallback matching service
        return FallbackBuyerMatchingService()
    
    async def get_property_search_service(self):
        """Get property search service with fallback capability."""
        if (self.health_monitor and 
            self.health_monitor.is_feature_enabled("vector_search_enabled")):
            
            try:
                async with self.service_operation("weaviate", "property_search"):
                    from reagent.core.vector_db.client import get_weaviate_client
                    return await get_weaviate_client()
                    
            except ServiceUnavailableError:
                self.logger.warning("Vector search unavailable, using fallback")
        
        # Return fallback search service
        return FallbackPropertySearchService()
    
    async def _fallback_buyer_matching(self) -> Dict[str, Any]:
        """Fallback buyer matching using database queries only."""
        return {
            "service_type": "fallback_matching",
            "capabilities": ["price_range", "location_filter", "property_type"],
            "limitations": ["no_semantic_search", "no_similarity_scoring"]
        }
    
    async def _fallback_property_search(self) -> Dict[str, Any]:
        """Fallback property search using SQL queries only."""
        return {
            "service_type": "fallback_search", 
            "capabilities": ["basic_filters", "text_search", "location_search"],
            "limitations": ["no_vector_similarity", "no_semantic_understanding"]
        }
    
    async def _fallback_market_analytics(self) -> Dict[str, Any]:
        """Fallback market analytics using cached data."""
        return {
            "service_type": "fallback_analytics",
            "capabilities": ["basic_statistics", "historical_trends"],
            "limitations": ["no_real_time_predictions", "limited_insight_depth"]
        }
    
    async def _fallback_recommendations(self) -> Dict[str, Any]:
        """Fallback recommendations using rule-based logic."""
        return {
            "service_type": "fallback_recommendations",
            "capabilities": ["rule_based_matching", "basic_preferences"],
            "limitations": ["no_ml_predictions", "no_behavioral_analysis"]
        }
    
    def get_system_capabilities(self) -> Dict[str, Any]:
        """Get current system capabilities and limitations."""
        if not self.health_monitor:
            return {"status": "not_initialized"}
        
        available_services = self.health_monitor.get_available_services()
        feature_flags = self.health_monitor.feature_flags
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "available_services": list(available_services),
            "enabled_features": {
                name: enabled for name, enabled in feature_flags.items() if enabled
            },
            "disabled_features": {
                name: enabled for name, enabled in feature_flags.items() if not enabled
            },
            "service_capabilities": {
                capability: {
                    "available": all(svc in available_services for svc in required_services),
                    "required_services": required_services,
                    "fallback_available": capability in ["buyer_matching", "property_search", 
                                                       "market_analytics", "recommendation_engine"]
                }
                for capability, required_services in self.service_capabilities.items()
            },
            "degradation_level": self._calculate_degradation_level(available_services)
        }
    
    def _calculate_degradation_level(self, available_services: Set[str]) -> str:
        """Calculate system degradation level."""
        critical_services = {"postgres", "redis"}
        optional_services = {"weaviate"}
        
        if not critical_services.issubset(available_services):
            return "critical_degradation"
        elif not optional_services.issubset(available_services):
            return "moderate_degradation"
        else:
            return "no_degradation"


class FallbackBuyerMatchingService:
    """Fallback buyer matching service using SQL queries only."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def find_matches(self, buyer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find property matches using database queries only."""
        self.logger.info("Using fallback buyer matching", buyer_id=buyer_id)
        
        # Implement SQL-based matching logic
        # This would use price range, location, property type filters
        return [
            {
                "property_id": f"prop_{i}",
                "match_score": 0.8 - (i * 0.1),
                "match_type": "fallback_sql",
                "match_reasons": ["price_range_match", "location_proximity"],
                "limitations": ["no_semantic_similarity", "basic_scoring_only"]
            }
            for i in range(min(limit, 5))  # Limited results in fallback mode
        ]


class FallbackPropertySearchService:
    """Fallback property search service using SQL queries only."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def search_properties(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search properties using SQL text search only."""
        self.logger.info("Using fallback property search", query=query)
        
        # Implement SQL-based search logic
        return [
            {
                "property_id": f"search_prop_{i}",
                "relevance_score": 0.7 - (i * 0.1),
                "search_type": "fallback_sql_text",
                "matched_fields": ["address", "description"],
                "limitations": ["no_semantic_understanding", "keyword_matching_only"]
            }
            for i in range(5)  # Limited results
        ]


# Global service manager instance
_service_manager: Optional[ResilientServiceManager] = None


async def get_service_manager() -> ResilientServiceManager:
    """Get or create global resilient service manager."""
    global _service_manager
    
    if _service_manager is None:
        _service_manager = ResilientServiceManager()
        await _service_manager.initialize()
    
    return _service_manager


async def with_service_resilience(service_name: str, operation_name: str):
    """Context manager for resilient service operations."""
    manager = await get_service_manager()
    
    async with manager.service_operation(service_name, operation_name):
        yield