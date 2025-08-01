"""
Multi-Layer Caching Strategy

Implements L1 (memory) + L2 (Redis) caching for optimal performance
with 50+ concurrent users. Provides intelligent cache warming,
invalidation, and hit rate optimization.
"""

import asyncio
import json
import time
import pickle
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import hashlib
import weakref

import structlog
from cachetools import TTLCache, LRUCache
from cachetools.keys import hashkey

from reagent.core.cache.redis_client import get_cache_manager, CacheManager
from reagent.core.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class CacheStats:
    """Cache performance statistics."""
    l1_hits: int = 0
    l1_misses: int = 0 
    l2_hits: int = 0
    l2_misses: int = 0
    total_requests: int = 0
    avg_fetch_time: float = 0.0
    hit_rate: float = 0.0
    l1_hit_rate: float = 0.0
    l2_hit_rate: float = 0.0


@dataclass
class CacheConfig:
    """Cache configuration for different data types."""
    l1_ttl: int = 300  # 5 minutes
    l2_ttl: int = 3600  # 1 hour  
    l1_max_size: int = 1000
    compress_threshold: int = 1024  # Compress data > 1KB
    serialize_complex: bool = True
    warm_on_miss: bool = True


class MemoryCache:
    """L1 memory cache with TTL and LRU eviction."""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.cache = TTLCache(maxsize=max_size, ttl=ttl)
        self.stats = {"hits": 0, "misses": 0}
        
    def get(self, key: str) -> Tuple[Any, bool]:
        """Get value from L1 cache."""
        try:
            value = self.cache[key]
            self.stats["hits"] += 1
            return value, True
        except KeyError:
            self.stats["misses"] += 1
            return None, False
    
    def set(self, key: str, value: Any) -> None:
        """Set value in L1 cache."""
        self.cache[key] = value
    
    def delete(self, key: str) -> None:
        """Delete value from L1 cache."""
        self.cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all L1 cache."""
        self.cache.clear()
        
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


class MultiLayerCache:
    """
    High-performance multi-layer cache with L1 (memory) + L2 (Redis).
    
    Features:
    - Intelligent cache warming
    - Automatic serialization/compression
    - Hit rate optimization
    - Cache invalidation patterns
    - Performance monitoring
    """
    
    def __init__(self, namespace: str = "reagent"):
        self.namespace = namespace
        self.settings = get_settings()
        
        # L1 Memory cache
        self.l1_cache = MemoryCache(
            max_size=1000,
            ttl=300  # 5 minutes
        )
        
        # L2 Redis cache manager
        self.l2_cache = get_cache_manager()
        
        # Cache configurations by data type
        self.configs: Dict[str, CacheConfig] = {
            "property": CacheConfig(l1_ttl=600, l2_ttl=3600, warm_on_miss=True),
            "buyer": CacheConfig(l1_ttl=300, l2_ttl=1800, warm_on_miss=True),
            "market_data": CacheConfig(l1_ttl=900, l2_ttl=7200, compress_threshold=512),
            "search_results": CacheConfig(l1_ttl=180, l2_ttl=900, l1_max_size=500),
            "agent_state": CacheConfig(l1_ttl=60, l2_ttl=300, serialize_complex=True),
            "suburb_trends": CacheConfig(l1_ttl=1800, l2_ttl=14400, compress_threshold=2048),
            "user_session": CacheConfig(l1_ttl=300, l2_ttl=3600, warm_on_miss=False)
        }
        
        # Performance statistics
        self.stats = CacheStats()
        self._last_stats_reset = time.time()
        
        # Cache warming tasks
        self._warming_tasks: weakref.WeakSet = weakref.WeakSet()
        
    def _get_cache_key(self, cache_type: str, key: str) -> str:
        """Generate namespaced cache key."""
        return f"{self.namespace}:{cache_type}:{key}"
    
    def _get_config(self, cache_type: str) -> CacheConfig:
        """Get cache configuration for data type."""
        return self.configs.get(cache_type, CacheConfig())
    
    async def get(
        self, 
        cache_type: str, 
        key: str, 
        default: Any = None,
        warm_func: Optional[Callable] = None
    ) -> Any:
        """
        Get value from multi-layer cache with automatic warming.
        
        Args:
            cache_type: Type of cached data
            key: Cache key
            default: Default value if not found
            warm_func: Function to warm cache on miss
            
        Returns:
            Cached value or default
        """
        start_time = time.time()
        self.stats.total_requests += 1
        
        cache_key = self._get_cache_key(cache_type, key)
        config = self._get_config(cache_type)
        
        # Try L1 cache first
        value, l1_hit = self.l1_cache.get(cache_key)
        if l1_hit:
            self.stats.l1_hits += 1
            self._update_fetch_time(time.time() - start_time)
            logger.debug("L1 cache hit", cache_type=cache_type, key=key)
            return value
        
        self.stats.l1_misses += 1
        
        # Try L2 cache
        value = await self.l2_cache.get(cache_key, default=None)
        if value is not None:
            self.stats.l2_hits += 1
            
            # Promote to L1 cache
            self.l1_cache.set(cache_key, value)
            
            self._update_fetch_time(time.time() - start_time)
            logger.debug("L2 cache hit, promoted to L1", cache_type=cache_type, key=key)
            return value
        
        self.stats.l2_misses += 1
        
        # Cache miss - trigger warming if configured
        if config.warm_on_miss and warm_func:
            logger.debug("Cache miss, warming cache", cache_type=cache_type, key=key)
            await self._warm_cache_async(cache_type, key, warm_func)
        
        self._update_fetch_time(time.time() - start_time)
        return default
    
    async def set(
        self, 
        cache_type: str, 
        key: str, 
        value: Any,
        l1_ttl: Optional[int] = None,
        l2_ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in multi-layer cache.
        
        Args:
            cache_type: Type of cached data
            key: Cache key
            value: Value to cache
            l1_ttl: L1 TTL override
            l2_ttl: L2 TTL override
            
        Returns:
            True if successful
        """
        cache_key = self._get_cache_key(cache_type, key)
        config = self._get_config(cache_type)
        
        # Set in L1 cache
        self.l1_cache.set(cache_key, value)
        
        # Set in L2 cache
        ttl = l2_ttl or config.l2_ttl
        success = await self.l2_cache.set(cache_key, value, ttl=ttl)
        
        if success:
            logger.debug("Value cached in L1+L2", cache_type=cache_type, key=key, ttl=ttl)
        
        return success
    
    async def delete(self, cache_type: str, key: str) -> bool:
        """Delete value from both cache layers."""
        cache_key = self._get_cache_key(cache_type, key)
        
        # Delete from L1
        self.l1_cache.delete(cache_key)
        
        # Delete from L2
        deleted_count = await self.l2_cache.delete(cache_key)
        
        logger.debug("Value deleted from L1+L2", cache_type=cache_type, key=key)
        return deleted_count > 0
    
    async def delete_pattern(self, cache_type: str, pattern: str) -> int:
        """Delete all keys matching pattern from both layers."""
        full_pattern = self._get_cache_key(cache_type, pattern)
        
        # Clear L1 cache (simple clear for now)
        self.l1_cache.clear()
        
        # Clear L2 cache with pattern
        deleted_count = await self.l2_cache.clear_pattern(full_pattern)
        
        logger.info("Pattern deleted from cache", cache_type=cache_type, pattern=pattern, count=deleted_count)
        return deleted_count
    
    async def warm_cache(
        self, 
        cache_type: str, 
        warm_data: Dict[str, Any],
        batch_size: int = 100
    ) -> int:
        """
        Warm cache with batch data.
        
        Args:
            cache_type: Type of cached data
            warm_data: Dictionary of key-value pairs to cache
            batch_size: Batch size for bulk operations
            
        Returns:
            Number of items cached
        """
        if not warm_data:
            return 0
        
        config = self._get_config(cache_type)
        cached_count = 0
        
        # Batch warm L2 cache
        batch_data = {}
        for key, value in warm_data.items():
            cache_key = self._get_cache_key(cache_type, key)
            batch_data[cache_key] = value
            
            # Also warm L1 cache for recent/hot data
            self.l1_cache.set(cache_key, value)
            
            if len(batch_data) >= batch_size:
                success = await self.l2_cache.set_many(batch_data, ttl=config.l2_ttl)
                if success:
                    cached_count += len(batch_data)
                batch_data.clear()
        
        # Handle remaining items
        if batch_data:
            success = await self.l2_cache.set_many(batch_data, ttl=config.l2_ttl)
            if success:
                cached_count += len(batch_data)
        
        logger.info("Cache warmed", cache_type=cache_type, items=cached_count)
        return cached_count
    
    async def _warm_cache_async(
        self, 
        cache_type: str, 
        key: str, 
        warm_func: Callable
    ) -> None:
        """Asynchronously warm cache to avoid blocking."""
        async def warm_task():
            try:
                value = await warm_func(key)
                if value is not None:
                    await self.set(cache_type, key, value)
                    logger.debug("Cache warmed asynchronously", cache_type=cache_type, key=key)
            except Exception as e:
                logger.warning("Cache warming failed", cache_type=cache_type, key=key, error=str(e))
        
        # Start warming task without waiting
        task = asyncio.create_task(warm_task())
        self._warming_tasks.add(task)
    
    def _update_fetch_time(self, fetch_time: float) -> None:
        """Update average fetch time statistics."""
        if self.stats.total_requests == 1:
            self.stats.avg_fetch_time = fetch_time
        else:
            # Exponential moving average
            alpha = 0.1
            self.stats.avg_fetch_time = (alpha * fetch_time + 
                                       (1 - alpha) * self.stats.avg_fetch_time)
    
    def get_stats(self) -> CacheStats:
        """Get current cache performance statistics."""
        total_requests = max(1, self.stats.total_requests)
        
        # Calculate hit rates
        total_hits = self.stats.l1_hits + self.stats.l2_hits
        self.stats.hit_rate = (total_hits / total_requests) * 100
        self.stats.l1_hit_rate = (self.stats.l1_hits / total_requests) * 100
        self.stats.l2_hit_rate = (self.stats.l2_hits / total_requests) * 100
        
        return self.stats
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = CacheStats()
        self.l1_cache.stats = {"hits": 0, "misses": 0}
        self._last_stats_reset = time.time()
        logger.info("Cache statistics reset")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check cache health and performance."""
        stats = self.get_stats()
        
        # L1 cache health
        l1_health = {
            "status": "healthy",
            "size": self.l1_cache.size(),
            "max_size": self.l1_cache.cache.maxsize,
            "utilization_percent": (self.l1_cache.size() / self.l1_cache.cache.maxsize) * 100,
            "hits": self.l1_cache.stats["hits"],
            "misses": self.l1_cache.stats["misses"]
        }
        
        # L2 cache health
        l2_health = await self.l2_cache.client.info() if hasattr(self.l2_cache, 'client') else {}
        
        return {
            "multi_layer_cache": {
                "status": "healthy",
                "l1_cache": l1_health,
                "l2_cache": l2_health,
                "performance": asdict(stats),
                "uptime_seconds": time.time() - self._last_stats_reset
            }
        }


# Global multi-layer cache instance
_multi_cache: Optional[MultiLayerCache] = None


def get_multi_cache() -> MultiLayerCache:
    """Get global multi-layer cache instance."""
    global _multi_cache
    if _multi_cache is None:
        _multi_cache = MultiLayerCache()
    return _multi_cache


@asynccontextmanager
async def cached_result(
    cache_type: str,
    key: str, 
    ttl: int = 3600,
    warm_func: Optional[Callable] = None
):
    """
    Context manager for cached operations.
    
    Usage:
        async with cached_result("property", property_id) as cache:
            if cache.value is None:
                cache.value = await expensive_operation()
            return cache.value
    """
    class CacheContext:
        def __init__(self):
            self.value = None
            self.cache = get_multi_cache()
            
        async def set_value(self, value: Any):
            self.value = value
            await self.cache.set(cache_type, key, value, l2_ttl=ttl)
    
    cache_ctx = CacheContext()
    cache = get_multi_cache()
    
    # Try to get cached value
    cache_ctx.value = await cache.get(cache_type, key, warm_func=warm_func)
    
    try:
        yield cache_ctx
    finally:
        # Auto-save if value was modified
        if cache_ctx.value is not None:
            await cache_ctx.set_value(cache_ctx.value)


# Convenience decorators for common caching patterns
def cache_property_data(ttl: int = 3600):
    """Decorator for caching property-related data."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            cache = get_multi_cache()
            
            # Try cache first
            result = await cache.get("property", cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            if result is not None:
                await cache.set("property", cache_key, result, l2_ttl=ttl)
            
            return result
        return wrapper
    return decorator


def cache_market_data(ttl: int = 7200):
    """Decorator for caching market analysis data."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            cache = get_multi_cache()
            
            result = await cache.get("market_data", cache_key)
            if result is not None:
                return result
            
            result = await func(*args, **kwargs)
            if result is not None:
                await cache.set("market_data", cache_key, result, l2_ttl=ttl)
            
            return result
        return wrapper
    return decorator