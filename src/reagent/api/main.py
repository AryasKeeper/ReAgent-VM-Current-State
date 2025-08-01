"""FastAPI main application."""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import make_asgi_app
import uvicorn

from reagent.core.config import settings
from reagent.core.database import init_database, close_database, create_tables
from reagent.core.cache import init_redis, close_redis
from reagent.utils.logging import setup_logging_for_production, get_logger
from reagent.api.routers import router as api_router
from reagent.api.middleware import LoggingMiddleware, MetricsMiddleware, RateLimitMiddleware


# Configure structured logging for production
setup_logging_for_production()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting ReAgent Sydney API")
    
    try:
        # Initialize database
        await init_database()
        await create_tables()
        
        # Initialize Redis
        await init_redis()
        
        logger.info("ReAgent Sydney API started successfully")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down ReAgent Sydney API")
        await close_database()
        await close_redis()
        logger.info("ReAgent Sydney API shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Multi-agent real estate intelligence system for Sydney, Australia",
    lifespan=lifespan,
    debug=settings.debug,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts,
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# Include routers
app.include_router(api_router, prefix="/api/v1")

# Include buyer matchmaker endpoints (commented out for testing)
# from ..agents.buyer_matchmaker.api_endpoints import router as buyer_matchmaker_router
# app.include_router(buyer_matchmaker_router)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "status": "operational",
        "docs_url": "/docs",
        "metrics_url": "/metrics"
    }


@app.get("/info")
async def info() -> Dict[str, Any]:
    """Get application information."""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment,
        "python_version": "3.11",
        "agents": [
            "Listing Watcher AU",
            "Suburb Signal Agent", 
            "Buyer Matchmaker AU",
            "Seller Strategy Agent",
            "Off-Market Radar AU",
            "Agent Whisperer"
        ],
        "data_sources": [
            "Domain API",
            "RealEstate.com.au",
            "CoreLogic",
            "NSW LPI"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        "reagent.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )