"""
Redis Cache Client

Provides async Redis client with connection pooling, serialization,
and caching utilities for the ReAgent Sydney system.
"""

import asyncio
import json
import pickle
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Union
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio import ConnectionPool
import structlog

from reagent.core.config import get_settings

logger = structlog.get_logger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None
_connection_pool: Optional[ConnectionPool] = None


def create_redis_client() -> redis.Redis:
    """
    Create and configure Redis client with connection pooling.
    
    Returns:
        redis.Redis: Configured Redis client
    """
    global _connection_pool
    
    settings = get_settings()
    
    if _connection_pool is None:
        _connection_pool = ConnectionPool.from_url(
            str(settings.cache.url),
            max_connections=settings.cache.max_connections,
            retry_on_timeout=True,
            health_check_interval=30,
            socket_keepalive=True,
            socket_keepalive_options={
                1: 1,  # TCP_KEEPIDLE
                2: 3,  # TCP_KEEPINTVL
                3: 5,  # TCP_KEEPCNT
            }
        )
    
    client = redis.Redis(
        connection_pool=_connection_pool,
        decode_responses=False,  # We handle encoding/decoding manually
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_error=[
            redis.ConnectionError,
            redis.TimeoutError,
        ]
    )
    
    logger.info(
        "Redis client created",
        url=str(settings.cache.url),
        max_connections=settings.cache.max_connections
    )
    
    return client


def get_redis_client() -> redis.Redis:
    """
    Get the global Redis client instance.
    
    Returns:
        redis.Redis: Redis client
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = create_redis_client()
    return _redis_client


class CacheManager:
    """High-level cache manager with serialization and utilities."""
    
    def __init__(self, client: Optional[redis.Redis] = None):
        """
        Initialize cache manager.
        
        Args:
            client: Redis client instance (uses global if None)
        """
        self.client = client or get_redis_client()
        self.settings = get_settings()
        self.default_ttl = self.settings.cache.ttl
    
    async def get(
        self, 
        key: str, 
        default: Any = None,
        deserialize: bool = True
    ) -> Any:
        """
        Get value from cache with automatic deserialization.
        
        Args:
            key: Cache key
            default: Default value if key not found
            deserialize: Whether to deserialize the value
            
        Returns:
            Cached value or default
        """
        try:
            value = await self.client.get(key)
            if value is None:
                return default
            
            if deserialize:
                try:
                    # Try JSON first (faster and more interoperable)
                    return json.loads(value.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Fall back to pickle for complex objects
                    return pickle.loads(value)
            else:
                return value.decode('utf-8') if isinstance(value, bytes) else value
                
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[Union[int, timedelta]] = None,
        serialize: bool = True
    ) -> bool:
        """
        Set value in cache with automatic serialization.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live (uses default if None)
            serialize: Whether to serialize the value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if ttl is None:
                ttl = self.default_ttl
            elif isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            
            if serialize:
                try:
                    # Try JSON first for simple types
                    serialized = json.dumps(value, default=str)
                except (TypeError, ValueError):
                    # Fall back to pickle for complex objects
                    serialized = pickle.dumps(value)
            else:
                serialized = str(value)
            
            result = await self.client.setex(key, ttl, serialized)
            return bool(result)
            
        except Exception as e:
            logger.error("Cache set failed", key=key, error=str(e))
            return False
    
    async def delete(self, *keys: str) -> int:
        """
        Delete keys from cache.
        
        Args:
            keys: Cache keys to delete
            
        Returns:
            Number of keys deleted
        """
        try:
            if not keys:
                return 0
            result = await self.client.delete(*keys)
            return int(result)
        except Exception as e:
            logger.error("Cache delete failed", keys=keys, error=str(e))
            return 0
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            result = await self.client.exists(key)
            return bool(result)
        except Exception as e:
            logger.warning("Cache exists check failed", key=key, error=str(e))
            return False
    
    async def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """
        Set expiration time for key.
        
        Args:
            key: Cache key
            ttl: Time to live
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            result = await self.client.expire(key, ttl)
            return bool(result)
        except Exception as e:
            logger.error("Cache expire failed", key=key, error=str(e))
            return False
    
    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment numeric value in cache.
        
        Args:
            key: Cache key
            amount: Amount to increment by
            
        Returns:
            New value after increment, None if failed
        """
        try:
            result = await self.client.incr(key, amount)
            return int(result)
        except Exception as e:
            logger.error("Cache increment failed", key=key, error=str(e))
            return None
    
    async def get_many(self, *keys: str) -> Dict[str, Any]:
        """
        Get multiple values from cache.
        
        Args:
            keys: Cache keys to retrieve
            
        Returns:
            Dictionary of key-value pairs
        """
        try:
            if not keys:
                return {}
            
            values = await self.client.mget(*keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        result[key] = pickle.loads(value)
                        
            return result
            
        except Exception as e:
            logger.error("Cache get_many failed", keys=keys, error=str(e))
            return {}
    
    async def set_many(
        self, 
        mapping: Dict[str, Any], 
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """
        Set multiple values in cache.
        
        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live for all keys
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not mapping:
                return True
            
            if ttl is None:
                ttl = self.default_ttl
            elif isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            
            # Serialize all values
            serialized = {}
            for key, value in mapping.items():
                try:
                    serialized[key] = json.dumps(value, default=str)
                except (TypeError, ValueError):
                    serialized[key] = pickle.dumps(value)
            
            # Use pipeline for atomic operation
            async with self.client.pipeline() as pipe:
                await pipe.mset(serialized)
                for key in serialized.keys():
                    await pipe.expire(key, ttl)
                results = await pipe.execute()
                
            return all(results)
            
        except Exception as e:
            logger.error("Cache set_many failed", error=str(e))
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern.
        
        Args:
            pattern: Redis pattern (supports * wildcards)
            
        Returns:
            Number of keys deleted
        """
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self.delete(*keys)
            return 0
            
        except Exception as e:
            logger.error("Cache clear_pattern failed", pattern=pattern, error=str(e))
            return 0


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """
    Get the global cache manager instance.
    
    Returns:
        CacheManager: Cache manager
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


@asynccontextmanager
async def cache_lock(
    key: str, 
    timeout: int = 10,
    blocking_timeout: Optional[int] = None
) -> AsyncGenerator[bool, None]:
    """
    Distributed lock using Redis.
    
    Args:
        key: Lock key
        timeout: Lock timeout in seconds
        blocking_timeout: How long to wait for lock
        
    Yields:
        bool: True if lock acquired, False otherwise
    """
    client = get_redis_client()
    lock = client.lock(
        f"lock:{key}",
        timeout=timeout,
        blocking_timeout=blocking_timeout
    )
    
    try:
        acquired = await lock.acquire()
        yield acquired
    finally:
        if acquired:
            try:
                await lock.release()
            except Exception as e:
                logger.warning("Failed to release lock", key=key, error=str(e))


async def check_cache_health() -> Dict[str, Any]:
    """
    Check Redis cache health and connection status.
    
    Returns:
        dict: Health check results
    """
    health_status = {
        "cache": "unknown",
        "response_time_ms": None,
        "memory_usage": None,
        "connected_clients": None,
        "details": {}
    }
    
    try:
        client = get_redis_client()
        start_time = asyncio.get_event_loop().time()
        
        # Basic connectivity test
        await client.ping()
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        health_status["response_time_ms"] = round(response_time, 2)
        health_status["cache"] = "healthy"
        
        # Get Redis info
        info = await client.info()
        health_status["memory_usage"] = info.get("used_memory_human", "unknown")
        health_status["connected_clients"] = info.get("connected_clients", "unknown")
        health_status["details"] = {
            "redis_version": info.get("redis_version", "unknown"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
        }
        
        # Calculate hit rate
        hits = health_status["details"]["keyspace_hits"]
        misses = health_status["details"]["keyspace_misses"]
        if hits + misses > 0:
            health_status["details"]["hit_rate"] = hits / (hits + misses)
        
    except Exception as e:
        health_status["cache"] = "unhealthy"
        health_status["details"]["error"] = str(e)
        logger.error("Cache health check failed", error=str(e))
    
    return health_status


async def close_cache() -> None:
    """
    Close Redis connections and cleanup resources.
    Should be called during application shutdown.
    """
    global _redis_client, _connection_pool, _cache_manager
    
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client closed")
    
    if _connection_pool:
        await _connection_pool.aclose()
        _connection_pool = None
        logger.info("Redis connection pool closed")
    
    _cache_manager = None
    logger.info("Cache connections closed")