"""
Caching Infrastructure

Redis-based caching implementations for improving application performance.
Provides caching decorators and direct cache access methods.
"""

import structlog
from reagent.core.cache.redis_client import get_redis_client, close_cache, check_cache_health, CacheManager
from reagent.core.config import get_settings

logger = structlog.get_logger(__name__)

async def init_redis():
    """Initialize production Redis connection."""
    settings = get_settings()
    
    if not settings.redis.url:
        raise RuntimeError("Redis URL not configured for production")
    
    try:
        # Test Redis connection
        redis_client = get_redis_client()
        await redis_client.ping()
        
        logger.info("Redis client initialized successfully", 
                   url=settings.redis.url,
                   max_connections=settings.redis.max_connections)
        
        return redis_client
        
    except Exception as e:
        logger.error("Failed to initialize Redis client", error=str(e))
        raise RuntimeError(f"Redis initialization failed: {e}")

async def close_redis():  
    """Close Redis connections."""
    try:
        await close_cache()
        logger.info("Redis connections closed successfully")
    except Exception as e:
        logger.warning("Error closing Redis connections", error=str(e))

__all__ = ["init_redis", "close_redis", "get_redis_client", "check_cache_health", "CacheManager"]