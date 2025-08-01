"""
Monitoring and Observability

Comprehensive monitoring suite for ReAgent Sydney including:
- Prometheus metrics collection
- Agent performance tracking
- Business intelligence metrics
- Health checks and alerting
- System performance monitoring
- Production readiness validation
- Service isolation and graceful degradation
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from reagent.utils.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Service health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthChecker:
    """
    Production-ready health checker with service isolation.
    
    Features:
    - Independent service health checks
    - Graceful degradation when services unavailable
    - Circuit breaker patterns to prevent cascade failures
    - Feature flag management based on service availability
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.last_check_time = {}
        self.service_status = {}
        
    def check_database_health(self) -> Dict[str, Any]:
        """Check PostgreSQL + TimescaleDB health."""
        start_time = time.time()
        
        try:
            from reagent.core.config import get_settings
            from sqlalchemy import create_engine, text
            
            settings = get_settings()
            engine = create_engine(settings.database.url)
            
            with engine.connect() as conn:
                # Basic connectivity test
                conn.execute(text("SELECT 1"))
                
                # TimescaleDB extension test
                result = conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'"))
                has_timescaledb = result.fetchone() is not None
                
                # Performance test
                conn.execute(text("SELECT COUNT(*) FROM pg_stat_activity"))
                
            engine.dispose()
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "features": {
                    "timescaledb_enabled": has_timescaledb,
                    "connection_pool": "active"
                },
                "checks_passed": ["connectivity", "extensions", "performance"]
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.logger.error("Database health check failed", error=str(e))
            
            return {
                "status": "unhealthy",
                "response_time_ms": response_time,
                "error": str(e),
                "checks_passed": []
            }
    
    def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis cache health."""
        start_time = time.time()
        
        try:
            from reagent.core.config import get_settings
            import redis
            
            settings = get_settings()
            r = redis.from_url(settings.redis.url)
            
            # Basic connectivity
            r.ping()
            
            # Memory usage
            info = r.info()
            memory_usage = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            
            # Performance test
            test_key = f"health_check:{int(time.time())}"
            r.set(test_key, "test", ex=10)
            r.get(test_key)
            r.delete(test_key)
            
            r.close()
            
            response_time = (time.time() - start_time) * 1000
            memory_usage_mb = memory_usage / (1024 * 1024)
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "memory_usage_mb": memory_usage_mb,
                "max_memory_mb": max_memory / (1024 * 1024) if max_memory > 0 else None,
                "checks_passed": ["connectivity", "memory", "read_write"]
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.logger.error("Redis health check failed", error=str(e))
            
            return {
                "status": "unhealthy", 
                "response_time_ms": response_time,
                "error": str(e),
                "checks_passed": []
            }
    
    def check_weaviate_health(self) -> Dict[str, Any]:
        """Check Weaviate vector database health."""
        start_time = time.time()
        
        try:
            from reagent.core.config import get_settings
            import weaviate
            
            settings = get_settings()
            client = weaviate.Client(url=settings.weaviate.url)
            
            # Basic connectivity
            is_ready = client.is_ready()
            
            if not is_ready:
                response_time = (time.time() - start_time) * 1000
                return {
                    "status": "degraded",
                    "response_time_ms": response_time,
                    "error": "Weaviate not ready",
                    "checks_passed": ["connectivity"]
                }
            
            # Schema validation
            schema = client.schema.get()
            class_count = len(schema.get('classes', []))
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "schema_classes": class_count,
                "checks_passed": ["connectivity", "readiness", "schema"]
            }
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.logger.warning("Weaviate health check failed", error=str(e))
            
            # Weaviate failure is non-critical - we can operate without it
            return {
                "status": "unavailable",
                "response_time_ms": response_time,
                "error": str(e),
                "checks_passed": [],
                "fallback_available": True,
                "impact": "Vector search disabled, using SQL fallback"
            }
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status."""
        timestamp = datetime.utcnow()
        
        # Check all components
        database_health = self.check_database_health()
        redis_health = self.check_redis_health()
        weaviate_health = self.check_weaviate_health() 
        
        # Determine overall system status
        critical_services = [database_health, redis_health]
        optional_services = [weaviate_health]
        
        # System is healthy if critical services are up
        critical_healthy = all(svc["status"] == "healthy" for svc in critical_services)
        all_healthy = critical_healthy and all(svc["status"] == "healthy" for svc in optional_services)
        
        if all_healthy:
            overall_status = "healthy"
            system_message = "All services operational"
        elif critical_healthy:
            overall_status = "degraded"
            system_message = "Core services healthy, some features disabled"
        else:
            overall_status = "unhealthy"
            system_message = "Critical services unavailable"
        
        return {
            "timestamp": timestamp.isoformat(),
            "overall_status": overall_status,
            "system_message": system_message,
            "components": {
                "database": database_health,
                "redis": redis_health,
                "weaviate": weaviate_health
            },
            "service_availability": {
                "core_api": critical_healthy,
                "property_listings": critical_healthy,
                "buyer_profiles": critical_healthy,
                "market_analytics": critical_healthy,
                "vector_search": weaviate_health["status"] == "healthy",
                "advanced_matching": weaviate_health["status"] == "healthy"
            },
            "degradation_info": {
                "level": "none" if all_healthy else "moderate" if critical_healthy else "severe",
                "disabled_features": self._get_disabled_features(weaviate_health),
                "fallback_services": self._get_fallback_services(weaviate_health)
            }
        }
    
    def _get_disabled_features(self, weaviate_health: Dict[str, Any]) -> List[str]:
        """Get list of disabled features based on service health."""
        disabled = []
        
        if weaviate_health["status"] != "healthy":
            disabled.extend([
                "semantic_property_search",
                "ai_powered_buyer_matching", 
                "similarity_based_recommendations",
                "advanced_market_predictions"
            ])
        
        return disabled
    
    def _get_fallback_services(self, weaviate_health: Dict[str, Any]) -> List[str]:
        """Get list of available fallback services."""
        fallbacks = []
        
        if weaviate_health["status"] != "healthy":
            fallbacks.extend([
                "sql_based_property_search",
                "rule_based_buyer_matching",
                "statistical_market_analysis",
                "basic_property_recommendations"
            ])
        
        return fallbacks


try:
    from .metrics import (
        # Agent metrics
        track_agent_execution,
        track_external_api_call,
        agent_executions_total,
        agent_execution_duration_seconds,
        agent_executions_failed_total,
        
        # Business metrics
        record_property_processed,
        record_buyer_match,
        record_vector_search,
        update_data_quality_score,
        
        # Cache metrics
        record_cache_operation,
        update_cache_hit_rate,
    )
except ImportError:
    # Fallback when metrics module not available
    logger.warning("Metrics module not available, using stubs")
    def track_agent_execution(*args, **kwargs): pass
    def track_external_api_call(*args, **kwargs): pass
    def record_property_processed(*args, **kwargs): pass
    def record_buyer_match(*args, **kwargs): pass
    def record_vector_search(*args, **kwargs): pass
    def update_data_quality_score(*args, **kwargs): pass
    def record_cache_operation(*args, **kwargs): pass
    def update_cache_hit_rate(*args, **kwargs): pass
    
    # Stub metrics
    agent_executions_total = None
    agent_execution_duration_seconds = None
    agent_executions_failed_total = None

from .business_metrics import (
    # Business metric collectors
    BusinessMetricsCollector,
    PropertyMarketUpdate,
    BuyerBehaviorSnapshot,
    
    # Business counters and gauges
    listing_status_changes_total,
    buyer_search_queries_total,
    market_anomaly_detection_events,
    off_market_opportunities_found,
    
    # Performance metrics
    agent_task_completion_rate,
    match_accuracy_score,
    pricing_recommendation_accuracy,
)

__all__ = [
    # Core decorators
    "track_agent_execution",
    "track_external_api_call",
    
    # Metric recording functions
    "record_property_processed",
    "record_buyer_match", 
    "record_vector_search",
    "update_data_quality_score",
    "record_cache_operation",
    "update_cache_hit_rate",
    
    # Business metrics
    "BusinessMetricsCollector",
    "PropertyMarketUpdate",
    "BuyerBehaviorSnapshot",
    
    # Health checking
    "HealthChecker",
    
    # Prometheus metrics (for direct access if needed)
    "agent_executions_total",
    "agent_execution_duration_seconds",
    "listing_status_changes_total",
    "buyer_search_queries_total",
    "market_anomaly_detection_events",
    "off_market_opportunities_found",
    "agent_task_completion_rate",
    "match_accuracy_score",
    "pricing_recommendation_accuracy",
]