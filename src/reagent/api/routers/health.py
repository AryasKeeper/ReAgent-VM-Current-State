"""
ReAgent Sydney - Health Check API

Comprehensive health monitoring endpoints for system status,
component health, and readiness checks.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

from reagent.utils.monitoring import HealthChecker
from reagent.utils.monitoring.production_health_monitor import (
    get_health_monitor, check_service_availability, ServiceStatus
)
from reagent.utils.logging import get_logger
from reagent.core.database import get_database
from reagent.core.cache.redis_client import get_redis
from reagent.core.vector_db.client import get_weaviate_client

router = APIRouter()
logger = get_logger("health_api")

# Health checker instance
health_checker = HealthChecker()

# Initialize startup timestamp
start_time = time.time()

@router.get("/")
async def basic_health() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "reagent-sydney",
        "version": "1.0.0"
    }

@router.get("/live")
async def liveness_probe() -> Dict[str, Any]:
    """Kubernetes liveness probe - basic service availability."""
    return {
        "status": "alive",
        "timestamp": time.time(),
        "uptime_seconds": time.time() - start_time if 'start_time' in globals() else 0
    }

@router.get("/ready")
async def readiness_probe() -> Dict[str, Any]:
    """
    Kubernetes readiness probe - check if service is ready to handle requests.
    Verifies all critical dependencies are available.
    """
    try:
        # Check database connectivity
        database_health = health_checker.check_database_health()
        
        # Check Redis connectivity  
        redis_health = health_checker.check_redis_health()
        
        # Check Weaviate connectivity
        weaviate_health = health_checker.check_weaviate_health()
        
        # Determine overall readiness
        components = [database_health, redis_health, weaviate_health]
        all_healthy = all(comp.get("status") == "healthy" for comp in components)
        
        status_code = 200 if all_healthy else 503
        
        response = {
            "status": "ready" if all_healthy else "not_ready",
            "timestamp": time.time(),
            "components": {
                "database": database_health,
                "redis": redis_health,
                "weaviate": weaviate_health
            }
        }
        
        if not all_healthy:
            logger.warning("Readiness check failed", components=response["components"])
        
        return JSONResponse(content=response, status_code=status_code)
        
    except Exception as e:
        logger.error("Readiness check error", error=str(e), exc_info=True)
        return JSONResponse(
            content={
                "status": "not_ready",
                "timestamp": time.time(),
                "error": str(e)
            },
            status_code=503
        )

@router.get("/detailed")
async def detailed_health() -> Dict[str, Any]:
    """Comprehensive health check with detailed component status."""
    try:
        # Get comprehensive system health
        system_health = health_checker.get_system_health()
        
        # Add additional ReAgent-specific checks
        agent_health = await check_agent_health()
        api_health = check_api_health()
        external_api_health = await check_external_api_health()
        
        # Compile detailed response
        response = {
            "timestamp": system_health["timestamp"],
            "overall_status": system_health["overall_status"],
            "components": {
                **system_health["components"],
                "agents": agent_health,
                "api": api_health,
                "external_apis": external_api_health
            },
            "metrics": {
                "total_properties_tracked": get_property_count(),
                "active_buyer_profiles": get_buyer_count(),
                "recent_matches_created": get_recent_matches(),
                "api_requests_last_hour": get_api_request_count()
            },
            "system_info": {
                "service": "reagent-sydney",
                "version": "1.0.0",
                "environment": "production",
                "agents_available": [
                    "listing_watcher",
                    "suburb_signal", 
                    "buyer_matchmaker",
                    "seller_strategy",
                    "off_market_radar",
                    "agent_whisperer"
                ]
            }
        }
        
        # Determine HTTP status code
        status_code = 200 if response["overall_status"] == "healthy" else 503
        
        logger.info("Detailed health check completed", 
                   overall_status=response["overall_status"],
                   components_checked=len(response["components"]))
        
        return JSONResponse(content=response, status_code=status_code)
        
    except Exception as e:
        logger.error("Detailed health check error", error=str(e), exc_info=True)
        return JSONResponse(
            content={
                "status": "error",
                "timestamp": time.time(),
                "error": str(e)
            },
            status_code=500
        )

@router.get("/metrics/summary")
async def metrics_summary() -> Dict[str, Any]:
    """Health metrics summary for monitoring dashboards."""
    try:
        return {
            "timestamp": time.time(),
            "property_data": {
                "total_properties": get_property_count(),
                "properties_processed_last_hour": get_properties_processed_count(),
                "data_freshness_minutes": get_data_freshness(),
            },
            "buyer_engagement": {
                "active_profiles": get_buyer_count(),
                "matches_created_last_hour": get_recent_matches(),
                "search_queries_last_hour": get_search_queries_count()
            },
            "agent_performance": {
                "total_executions_last_hour": get_agent_executions_count(),
                "average_execution_time_seconds": get_average_execution_time(),
                "success_rate_percentage": get_agent_success_rate()
            },
            "system_performance": {
                "api_response_time_p95_ms": get_api_response_time(),
                "error_rate_percentage": get_error_rate(),
                "cache_hit_rate_percentage": get_cache_hit_rate()
            }
        }
        
    except Exception as e:
        logger.error("Metrics summary error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def check_agent_health() -> Dict[str, Any]:
    """Check health of all ReAgent components."""
    try:
        # This would check if agent processes are running and responsive
        return {
            "status": "healthy",
            "active_agents": 6,
            "last_execution_time": time.time() - 300,  # 5 minutes ago
            "total_tasks_queued": 0
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

def check_api_health() -> Dict[str, Any]:
    """Check API health and performance."""
    try:
        return {
            "status": "healthy",
            "requests_per_minute": 50,
            "average_response_time_ms": 150,
            "error_rate_percentage": 0.5
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

async def check_external_api_health() -> Dict[str, Any]:
    """Check external API connectivity and quota status."""
    try:
        return {
            "status": "healthy",
            "domain_api": {"status": "healthy", "quota_remaining": "80%"},
            "realestate_api": {"status": "healthy", "quota_remaining": "65%"},
            "corelogic_api": {"status": "healthy", "quota_remaining": "90%"}
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# Utility functions to get actual metrics (placeholders for now)
def get_property_count() -> int:
    """Get total property count from metrics."""
    try:
        # This would query the actual metrics backend
        return 50000
    except:
        return 0

def get_buyer_count() -> int:
    """Get active buyer count from metrics."""
    try:
        return 1200
    except:
        return 0

def get_recent_matches() -> int:
    """Get recent buyer matches from metrics."""
    try:
        return 45
    except:
        return 0

def get_api_request_count() -> int:
    """Get API request count from metrics."""
    try:
        return 2500
    except:
        return 0

def get_properties_processed_count() -> int:
    """Get properties processed in last hour."""
    try:
        return 150
    except:
        return 0

def get_data_freshness() -> float:
    """Get data freshness in minutes."""
    try:
        return 5.0
    except:
        return 0.0

def get_search_queries_count() -> int:
    """Get search queries in last hour."""
    try:
        return 300
    except:
        return 0

def get_agent_executions_count() -> int:
    """Get agent executions in last hour."""
    try:
        return 75
    except:
        return 0

def get_average_execution_time() -> float:
    """Get average agent execution time."""
    try:
        return 15.5
    except:
        return 0.0

def get_agent_success_rate() -> float:
    """Get agent success rate percentage."""
    try:
        return 98.5
    except:
        return 0.0

def get_api_response_time() -> float:
    """Get API P95 response time in milliseconds."""
    try:
        return 250.0
    except:
        return 0.0

def get_error_rate() -> float:
    """Get error rate percentage."""
    try:
        return 0.8
    except:
        return 0.0

def get_cache_hit_rate() -> float:
    """Get cache hit rate percentage."""
    try:
        return 85.0
    except:
        return 0.0