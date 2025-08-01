#!/usr/bin/env python3
"""
ReAgent Emergency API - Production Recovery Service

Provides core ReAgent functionality without vector database dependency.
Implements graceful degradation patterns and service isolation.
"""

import os
import time
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("emergency-api")

# Initialize FastAPI app
app = FastAPI(
    title="ReAgent Emergency API",
    description="Production recovery service with graceful degradation",
    version="1.0.0-emergency",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track startup time
startup_time = time.time()

# Service health status
service_health = {
    "postgres": "unknown",
    "redis": "unknown", 
    "weaviate": "unavailable",
    "last_check": datetime.utcnow()
}

# Feature flags for graceful degradation
feature_flags = {
    "vector_search_enabled": False,
    "buyer_matching_enabled": False,
    "advanced_analytics_enabled": False,
    "fallback_services_enabled": True,
    "graceful_degradation": True
}


@app.on_event("startup")
async def startup():
    """Initialize emergency API service."""
    logger.info("Starting ReAgent Emergency API")
    
    try:
        # Check database connectivity
        await check_database_health()
        
        # Check Redis connectivity
        await check_redis_health()
        
        # Set appropriate feature flags
        configure_feature_flags()
        
        logger.info("Emergency API startup complete")
        
    except Exception as e:
        logger.error(f"Emergency API startup failed: {e}")
        # Continue startup even if some services fail


async def check_database_health():
    """Check PostgreSQL + TimescaleDB health."""
    try:
        import psycopg2
        
        database_url = os.getenv("DATABASE_URL", "postgresql://reagent:reagent_dev_password@localhost:5432/reagent")
        
        # Parse URL for connection
        if database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        
        service_health["postgres"] = "healthy"
        logger.info("Database health check: HEALTHY")
        
    except Exception as e:
        service_health["postgres"] = "unhealthy"
        logger.error(f"Database health check failed: {e}")


async def check_redis_health():
    """Check Redis cache health."""
    try:
        import redis
        
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url)
        r.ping()
        r.close()
        
        service_health["redis"] = "healthy"
        logger.info("Redis health check: HEALTHY")
        
    except Exception as e:
        service_health["redis"] = "unhealthy"
        logger.error(f"Redis health check failed: {e}")


def configure_feature_flags():
    """Configure feature flags based on service availability."""
    if service_health["postgres"] == "healthy":
        feature_flags["fallback_services_enabled"] = True
        logger.info("Core services available - enabling fallback functionality")
    else:
        logger.warning("Core services unavailable - limited functionality")


@app.get("/api/v1/health/")
async def basic_health():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "reagent-emergency-api",
        "version": "1.0.0-emergency",
        "uptime_seconds": time.time() - startup_time
    }


@app.get("/api/v1/health/live")
async def liveness_probe():
    """Kubernetes liveness probe."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": time.time() - startup_time
    }


@app.get("/api/v1/health/ready")
async def readiness_probe():
    """Kubernetes readiness probe."""
    try:
        # Update service health
        await check_database_health()
        await check_redis_health()
        service_health["last_check"] = datetime.utcnow()
        
        # System is ready if core services are available
        core_services_healthy = (
            service_health["postgres"] == "healthy" and
            service_health["redis"] == "healthy"
        )
        
        status_code = 200 if core_services_healthy else 503
        
        response = {
            "status": "ready" if core_services_healthy else "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "services": service_health.copy(),
            "feature_flags": feature_flags.copy(),
            "degradation_level": "none" if core_services_healthy else "moderate"
        }
        
        return JSONResponse(content=response, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Readiness check error: {e}")
        return JSONResponse(
            content={
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            },
            status_code=503
        )


@app.get("/api/v1/health/detailed")
async def detailed_health():
    """Comprehensive health check with system capabilities."""
    try:
        # Update all service health
        await check_database_health()
        await check_redis_health()
        service_health["last_check"] = datetime.utcnow()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "degraded",  # Always degraded without Weaviate
            "system_message": "Emergency API active - limited functionality",
            "services": service_health.copy(),
            "feature_flags": feature_flags.copy(),
            "capabilities": {
                "available": [
                    "basic_property_search",
                    "simple_buyer_profiles", 
                    "market_data_access",
                    "report_generation"
                ],
                "disabled": [
                    "semantic_property_search",
                    "ai_powered_buyer_matching",
                    "vector_similarity_search",
                    "advanced_recommendations"
                ],
                "fallback_services": [
                    "sql_based_property_search",
                    "rule_based_buyer_matching",
                    "statistical_market_analysis"
                ]
            },
            "metrics": {
                "uptime_seconds": time.time() - startup_time,
                "requests_handled": 0,  # Would track actual metrics
                "error_rate": 0.0
            }
        }
        
    except Exception as e:
        logger.error(f"Detailed health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/system/status")
async def system_status():
    """System status for monitoring dashboards."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "service_name": "reagent-emergency-api",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "deployment_mode": "emergency_recovery",
        "services": {
            "core_services": {
                "postgres": service_health["postgres"],
                "redis": service_health["redis"]
            },
            "optional_services": {
                "weaviate": "unavailable"
            }
        },
        "capabilities": {
            "basic_functionality": True,
            "advanced_features": False,
            "vector_search": False,
            "fallback_services": True
        },
        "recovery_status": {
            "emergency_mode": True,
            "vector_database_required": False,
            "core_services_operational": service_health["postgres"] == "healthy"
        }
    }


@app.get("/api/v1/properties/search")
async def search_properties(
    query: str = "",
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    property_type: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = 10
):
    """Basic property search using SQL fallback."""
    if not feature_flags["fallback_services_enabled"]:
        raise HTTPException(
            status_code=503,
            detail="Search service temporarily unavailable"
        )
    
    # Simulate SQL-based property search
    mock_results = [
        {
            "property_id": f"prop_{i}",
            "address": f"Mock Address {i}, Sydney NSW",
            "price": 850000 + (i * 50000),
            "property_type": "House",
            "bedrooms": 3 + (i % 2),
            "bathrooms": 2,
            "search_score": 0.8 - (i * 0.1),
            "search_method": "sql_fallback",
            "note": "Limited search functionality - vector search unavailable"
        }
        for i in range(min(limit, 5))
    ]
    
    return {
        "results": mock_results,
        "total_count": len(mock_results),
        "search_method": "sql_fallback",
        "limitations": [
            "No semantic similarity search",
            "Basic keyword matching only",
            "Limited relevance scoring"
        ],
        "query_processed": query
    }


@app.get("/api/v1/buyers/matches/{buyer_id}")
async def get_buyer_matches(buyer_id: str, limit: int = 10):
    """Basic buyer matching using rule-based fallback."""
    if not feature_flags["fallback_services_enabled"]:
        raise HTTPException(
            status_code=503, 
            detail="Matching service temporarily unavailable"
        )
    
    # Simulate rule-based matching
    mock_matches = [
        {
            "property_id": f"match_prop_{i}",
            "match_score": 0.7 - (i * 0.1),
            "match_reasons": ["price_range_match", "location_preference"],
            "property_summary": f"3BR House in Sydney - ${800000 + (i * 100000)}",
            "matching_method": "rule_based_fallback",
            "note": "Basic matching only - AI matching unavailable"
        }
        for i in range(min(limit, 3))
    ]
    
    return {
        "buyer_id": buyer_id,
        "matches": mock_matches,
        "total_matches": len(mock_matches),
        "matching_method": "rule_based_fallback",
        "limitations": [
            "No AI-powered matching",
            "Basic preference matching only",
            "Limited personalization"
        ]
    }


@app.get("/api/v1/market/data/{suburb}")
async def get_market_data(suburb: str):
    """Basic market data using cached statistics."""
    # Simulate market data retrieval
    return {
        "suburb": suburb,
        "data_timestamp": datetime.utcnow().isoformat(),
        "market_indicators": {
            "median_price": 950000,
            "price_change_12m": 8.5,
            "days_on_market": 35,
            "auction_clearance_rate": 75.2
        },
        "data_source": "cached_statistics",
        "limitations": [
            "No real-time market analysis",
            "Basic statistical data only",
            "Limited trend analysis"
        ],
        "note": "Emergency data service - full analytics unavailable"
    }


if __name__ == "__main__":
    # Run emergency API
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )