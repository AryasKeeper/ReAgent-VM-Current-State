"""
Multi-Layer Cache Management for Suburb Signal Agent

Implements intelligent caching strategy with multiple cache layers, smart invalidation,
and performance optimization for high-frequency market analysis queries.
"""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import pickle
import zlib

from reagent.core.cache.redis_client import get_cache_manager
from reagent.core.exceptions import CacheError


class CacheLayer(str, Enum):
    """Cache layer types."""
    QUERY = "query"           # Raw query results
    RESULT = "result"         # Processed analysis results
    METRIC = "metric"         # Individual metric calculations
    INSIGHT = "insight"       # Generated insights and signals
    TREND = "trend"          # Trend analysis results
    RANKING = "ranking"       # Suburb rankings
    SUMMARY = "summary"       # Market summaries


class CacheStrategy(str, Enum):
    """Cache update strategies."""
    WRITE_THROUGH = "write_through"      # Update cache on every write
    WRITE_BEHIND = "write_behind"        # Async cache updates
    REFRESH_AHEAD = "refresh_ahead"      # Proactive cache refresh
    LAZY_LOAD = "lazy_load"             # Load on cache miss


@dataclass
class CacheConfig:
    """Configuration for cache layers."""
    
    layer: CacheLayer
    ttl: int  # Time to live in seconds
    strategy: CacheStrategy
    compression: bool = False
    serialization: str = "json"  # json, pickle
    max_size: Optional[int] = None
    invalidation_tags: List[str] = None
    
    def __post_init__(self):
        if self.invalidation_tags is None:
            self.invalidation_tags = []


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    
    layer: CacheLayer
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    invalidations: int = 0
    total_requests: int = 0
    avg_response_time_ms: float = 0.0
    cache_size_mb: float = 0.0
    compression_ratio: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 100.0 - self.hit_rate


class AnalysisCacheManager:
    """
    Multi-layer cache manager optimized for market analysis data.
    
    Provides intelligent caching with automatic invalidation, compression,
    and performance monitoring for high-frequency suburb analysis queries.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.redis_client = get_cache_manager()
        
        # Cache layer configurations
        self.layer_configs = {
            CacheLayer.QUERY: CacheConfig(
                layer=CacheLayer.QUERY,
                ttl=1800,  # 30 minutes
                strategy=CacheStrategy.WRITE_THROUGH,
                compression=True,
                serialization="pickle"
            ),
            CacheLayer.RESULT: CacheConfig(
                layer=CacheLayer.RESULT,
                ttl=3600,  # 1 hour
                strategy=CacheStrategy.WRITE_BEHIND,
                compression=True,
                serialization="json"
            ),
            CacheLayer.METRIC: CacheConfig(
                layer=CacheLayer.METRIC,
                ttl=7200,  # 2 hours
                strategy=CacheStrategy.REFRESH_AHEAD,
                compression=False,
                serialization="json"
            ),
            CacheLayer.INSIGHT: CacheConfig(
                layer=CacheLayer.INSIGHT,
                ttl=14400,  # 4 hours
                strategy=CacheStrategy.LAZY_LOAD,
                compression=True,
                serialization="json",
                invalidation_tags=["market_data", "price_change"]
            ),
            CacheLayer.TREND: CacheConfig(
                layer=CacheLayer.TREND,
                ttl=21600,  # 6 hours
                strategy=CacheStrategy.REFRESH_AHEAD,
                compression=True,
                serialization="pickle",
                invalidation_tags=["market_data", "trend_change"]
            ),
            CacheLayer.RANKING: CacheConfig(
                layer=CacheLayer.RANKING,
                ttl=43200,  # 12 hours
                strategy=CacheStrategy.LAZY_LOAD,
                compression=False,
                serialization="json",
                invalidation_tags=["ranking_change"]
            ),
            CacheLayer.SUMMARY: CacheConfig(
                layer=CacheLayer.SUMMARY,
                ttl=86400,  # 24 hours
                strategy=CacheStrategy.WRITE_BEHIND,
                compression=True,
                serialization="json",
                invalidation_tags=["market_summary"]
            )
        }
        
        # Performance tracking
        self.metrics: Dict[CacheLayer, CacheMetrics] = {
            layer: CacheMetrics(layer=layer) for layer in CacheLayer
        }
        
        # Invalidation tracking
        self.invalidation_tags: Dict[str, Set[str]] = {}
        self.pending_invalidations: Set[Tuple[CacheLayer, str]] = set()
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.max_key_length = 250
        self.batch_size = 100
        self.cleanup_interval = 3600  # 1 hour
        
    async def initialize(self):
        """Initialize cache manager and start background tasks."""
        try:
            # Test Redis connection
            if self.redis_client:
                await self.redis_client.ping()
                self.logger.info("Cache manager initialized successfully")
            
            # Start background cleanup task
            self._cleanup_task = asyncio.create_task(self._background_cleanup())
            
        except Exception as e:
            self.logger.error(f"Failed to initialize cache manager: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown cache manager and cleanup background tasks."""
        try:
            # Cancel background tasks
            if self._cleanup_task:
                self._cleanup_task.cancel()
            
            for task in self._background_tasks:
                task.cancel()
            
            # Wait for tasks to complete
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
            self.logger.info("Cache manager shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during cache manager shutdown: {e}")
    
    async def get(
        self,
        layer: CacheLayer,
        key: str,
        default: Any = None
    ) -> Any:
        """
        Retrieve data from cache layer.
        
        Args:
            layer: Cache layer to query
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached data or default value
        """
        try:
            start_time = datetime.utcnow()
            
            # Generate full cache key
            cache_key = self._generate_cache_key(layer, key)
            
            # Get from Redis
            cached_data = await self.redis_client.get(cache_key)
            
            # Update metrics
            self.metrics[layer].total_requests += 1
            
            if cached_data is not None:
                # Cache hit
                self.metrics[layer].hits += 1
                
                # Deserialize data
                data = await self._deserialize_data(layer, cached_data)
                
                # Update response time
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                self._update_avg_response_time(layer, response_time)
                
                self.logger.debug(f"Cache hit for {layer.value}:{key}")
                return data
            else:
                # Cache miss
                self.metrics[layer].misses += 1
                self.logger.debug(f"Cache miss for {layer.value}:{key}")
                return default
                
        except Exception as e:
            self.logger.error(f"Error retrieving from cache {layer.value}:{key}: {e}")
            self.metrics[layer].misses += 1
            return default
    
    async def set(
        self,
        layer: CacheLayer,
        key: str,
        data: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Store data in cache layer.
        
        Args:
            layer: Cache layer to store in
            key: Cache key
            data: Data to cache
            ttl: Custom TTL (overrides layer default)
            tags: Invalidation tags
            
        Returns:
            True if successful
        """
        try:
            config = self.layer_configs[layer]
            cache_ttl = ttl or config.ttl
            
            # Generate full cache key
            cache_key = self._generate_cache_key(layer, key)
            
            # Serialize data
            serialized_data = await self._serialize_data(layer, data)
            
            # Store in Redis
            success = await self.redis_client.set(cache_key, serialized_data, ttl=cache_ttl)
            
            if success:
                # Update metrics
                self.metrics[layer].sets += 1
                
                # Track invalidation tags
                if tags or config.invalidation_tags:
                    all_tags = (tags or []) + config.invalidation_tags
                    await self._track_invalidation_tags(cache_key, all_tags)
                
                # Handle write strategies
                if config.strategy == CacheStrategy.WRITE_BEHIND:
                    # Schedule async processing
                    task = asyncio.create_task(self._process_write_behind(layer, key, data))
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
                
                self.logger.debug(f"Cached data for {layer.value}:{key} (TTL: {cache_ttl}s)")
                return True
            else:
                self.logger.warning(f"Failed to cache data for {layer.value}:{key}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error caching data for {layer.value}:{key}: {e}")
            return False
    
    async def delete(
        self,
        layer: CacheLayer,
        key: str
    ) -> bool:
        """
        Delete data from cache layer.
        
        Args:
            layer: Cache layer
            key: Cache key to delete
            
        Returns:
            True if successful
        """
        try:
            # Generate full cache key
            cache_key = self._generate_cache_key(layer, key)
            
            # Delete from Redis
            success = await self.redis_client.delete(cache_key)
            
            if success:
                self.metrics[layer].deletes += 1
                self.logger.debug(f"Deleted cache key {layer.value}:{key}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error deleting cache key {layer.value}:{key}: {e}")
            return False
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate all cache entries with specified tag.
        
        Args:
            tag: Invalidation tag
            
        Returns:
            Number of keys invalidated
        """
        try:
            invalidated_count = 0
            
            if tag in self.invalidation_tags:
                keys_to_invalidate = list(self.invalidation_tags[tag])
                
                # Delete keys in batches
                for i in range(0, len(keys_to_invalidate), self.batch_size):
                    batch = keys_to_invalidate[i:i + self.batch_size]
                    
                    # Delete batch
                    deleted_count = await self.redis_client.delete(*batch)
                    invalidated_count += deleted_count
                
                # Update metrics
                for layer in CacheLayer:
                    self.metrics[layer].invalidations += invalidated_count
                
                # Clear tag tracking
                del self.invalidation_tags[tag]
                
                self.logger.info(f"Invalidated {invalidated_count} cache entries for tag '{tag}'")
            
            return invalidated_count
            
        except Exception as e:
            self.logger.error(f"Error invalidating cache by tag '{tag}': {e}")
            return 0
    
    async def invalidate_suburb_data(self, suburb: str) -> int:
        """
        Invalidate all cache entries related to a specific suburb.
        
        Args:
            suburb: Suburb name
            
        Returns:
            Number of keys invalidated
        """
        try:
            # Find all keys containing the suburb
            pattern = f"*:*{suburb}*"
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                # Delete in batches
                invalidated_count = 0
                for i in range(0, len(keys), self.batch_size):
                    batch = keys[i:i + self.batch_size]
                    deleted_count = await self.redis_client.delete(*batch)
                    invalidated_count += deleted_count
                
                # Update metrics
                for layer in CacheLayer:
                    self.metrics[layer].invalidations += invalidated_count // len(CacheLayer)
                
                self.logger.info(f"Invalidated {invalidated_count} cache entries for suburb '{suburb}'")
                return invalidated_count
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error invalidating suburb cache for '{suburb}': {e}")
            return 0
    
    async def warm_cache(
        self,
        layer: CacheLayer,
        suburbs: List[str],
        warm_function: callable,
        **kwargs
    ) -> int:
        """
        Warm cache by pre-loading data for specified suburbs.
        
        Args:
            layer: Cache layer to warm
            suburbs: List of suburbs to warm
            warm_function: Function to generate data for caching
            **kwargs: Additional arguments for warm_function
            
        Returns:
            Number of items cached
        """
        try:
            cached_count = 0
            
            # Process suburbs in batches
            for i in range(0, len(suburbs), self.batch_size):
                batch = suburbs[i:i + self.batch_size]
                
                # Generate data for batch
                batch_data = await warm_function(batch, **kwargs)
                
                # Cache each item
                for suburb, data in batch_data.items():
                    cache_key = f"warm_{suburb}_{datetime.utcnow().strftime('%Y%m%d')}"
                    success = await self.set(layer, cache_key, data)
                    if success:
                        cached_count += 1
            
            self.logger.info(f"Warmed {cached_count} cache entries for {layer.value}")
            return cached_count
            
        except Exception as e:
            self.logger.error(f"Error warming cache for {layer.value}: {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            stats = {
                'layers': {},
                'overall': {
                    'total_hits': 0,
                    'total_misses': 0,
                    'total_requests': 0,
                    'overall_hit_rate': 0.0,
                    'cache_size_mb': 0.0
                },
                'redis': {}
            }
            
            # Layer-specific stats
            for layer, metrics in self.metrics.items():
                stats['layers'][layer.value] = {
                    'hits': metrics.hits,
                    'misses': metrics.misses,
                    'hit_rate': metrics.hit_rate,
                    'total_requests': metrics.total_requests,
                    'sets': metrics.sets,
                    'deletes': metrics.deletes,
                    'invalidations': metrics.invalidations,
                    'avg_response_time_ms': metrics.avg_response_time_ms,
                    'cache_size_mb': metrics.cache_size_mb,
                    'compression_ratio': metrics.compression_ratio
                }
                
                # Aggregate overall stats
                stats['overall']['total_hits'] += metrics.hits
                stats['overall']['total_misses'] += metrics.misses
                stats['overall']['total_requests'] += metrics.total_requests
                stats['overall']['cache_size_mb'] += metrics.cache_size_mb
            
            # Calculate overall hit rate
            if stats['overall']['total_requests'] > 0:
                stats['overall']['overall_hit_rate'] = (
                    stats['overall']['total_hits'] / stats['overall']['total_requests'] * 100
                )
            
            # Redis stats
            if self.redis_client:
                redis_info = await self.redis_client.info()
                stats['redis'] = {
                    'memory_used_mb': redis_info.get('used_memory', 0) / (1024 * 1024),
                    'connected_clients': redis_info.get('connected_clients', 0),
                    'total_commands_processed': redis_info.get('total_commands_processed', 0),
                    'keyspace_hits': redis_info.get('keyspace_hits', 0),
                    'keyspace_misses': redis_info.get('keyspace_misses', 0)
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {e}")
            return {}
    
    async def optimize_cache(self) -> Dict[str, Any]:
        """
        Perform cache optimization operations.
        
        Returns:
            Dictionary with optimization results
        """
        try:
            optimization_results = {
                'expired_cleaned': 0,
                'memory_reclaimed_mb': 0,
                'keys_compressed': 0,
                'optimization_time_ms': 0
            }
            
            start_time = datetime.utcnow()
            
            # Clean expired keys
            expired_count = await self._cleanup_expired_keys()
            optimization_results['expired_cleaned'] = expired_count
            
            # Compress large values
            compressed_count = await self._compress_large_values()
            optimization_results['keys_compressed'] = compressed_count
            
            # Calculate optimization time
            optimization_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            optimization_results['optimization_time_ms'] = optimization_time
            
            self.logger.info(f"Cache optimization completed: {optimization_results}")
            return optimization_results
            
        except Exception as e:
            self.logger.error(f"Error during cache optimization: {e}")
            return {}
    
    # Private helper methods
    
    def _generate_cache_key(self, layer: CacheLayer, key: str) -> str:
        """Generate full cache key with layer prefix."""
        # Sanitize key
        safe_key = key.replace(' ', '_').replace(':', '_')
        
        # Truncate if too long
        if len(safe_key) > self.max_key_length:
            # Use hash for very long keys
            key_hash = hashlib.md5(safe_key.encode()).hexdigest()[:16]
            safe_key = f"{safe_key[:self.max_key_length-17]}_{key_hash}"
        
        return f"suburb_signal:{layer.value}:{safe_key}"
    
    async def _serialize_data(self, layer: CacheLayer, data: Any) -> bytes:
        """Serialize data based on layer configuration."""
        config = self.layer_configs[layer]
        
        try:
            if config.serialization == "json":
                # Convert to JSON
                if hasattr(data, '__dict__'):
                    # Handle dataclass objects
                    if hasattr(data, '__dataclass_fields__'):
                        json_data = asdict(data)
                    else:
                        json_data = data.__dict__
                else:
                    json_data = data
                
                serialized = json.dumps(json_data, default=str).encode('utf-8')
                
            elif config.serialization == "pickle":
                serialized = pickle.dumps(data)
            else:
                raise ValueError(f"Unknown serialization method: {config.serialization}")
            
            # Apply compression if enabled
            if config.compression:
                compressed = zlib.compress(serialized)
                
                # Update compression ratio metric
                if len(serialized) > 0:
                    ratio = len(compressed) / len(serialized)
                    self.metrics[layer].compression_ratio = (
                        self.metrics[layer].compression_ratio + ratio
                    ) / 2
                
                return compressed
            else:
                return serialized
                
        except Exception as e:
            self.logger.error(f"Error serializing data for {layer.value}: {e}")
            raise
    
    async def _deserialize_data(self, layer: CacheLayer, cached_data: bytes) -> Any:
        """Deserialize cached data based on layer configuration."""
        config = self.layer_configs[layer]
        
        try:
            # Decompress if needed
            if config.compression:
                decompressed = zlib.decompress(cached_data)
            else:
                decompressed = cached_data
            
            # Deserialize based on method
            if config.serialization == "json":
                return json.loads(decompressed.decode('utf-8'))
            elif config.serialization == "pickle":
                return pickle.loads(decompressed)
            else:
                raise ValueError(f"Unknown serialization method: {config.serialization}")
                
        except Exception as e:
            self.logger.error(f"Error deserializing data for {layer.value}: {e}")
            raise
    
    async def _track_invalidation_tags(self, cache_key: str, tags: List[str]):
        """Track cache key for invalidation tags."""
        for tag in tags:
            if tag not in self.invalidation_tags:
                self.invalidation_tags[tag] = set()
            self.invalidation_tags[tag].add(cache_key)
    
    def _update_avg_response_time(self, layer: CacheLayer, response_time_ms: float):
        """Update average response time for layer."""
        current_avg = self.metrics[layer].avg_response_time_ms
        total_requests = self.metrics[layer].total_requests
        
        if total_requests == 1:
            self.metrics[layer].avg_response_time_ms = response_time_ms
        else:
            # Calculate running average
            self.metrics[layer].avg_response_time_ms = (
                (current_avg * (total_requests - 1) + response_time_ms) / total_requests
            )
    
    async def _process_write_behind(self, layer: CacheLayer, key: str, data: Any):
        """Process write-behind cache operations."""
        try:
            # This would typically involve:
            # 1. Persisting to database
            # 2. Updating search indexes
            # 3. Triggering downstream processes
            
            self.logger.debug(f"Processing write-behind for {layer.value}:{key}")
            
            # Placeholder for actual implementation
            await asyncio.sleep(0.1)
            
        except Exception as e:
            self.logger.error(f"Error in write-behind processing for {layer.value}:{key}: {e}")
    
    async def _background_cleanup(self):
        """Background task for cache cleanup and maintenance."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # Perform maintenance operations
                await self._cleanup_expired_keys()
                await self._update_cache_size_metrics()
                await self._process_pending_invalidations()
                
                self.logger.debug("Background cache cleanup completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in background cache cleanup: {e}")
    
    async def _cleanup_expired_keys(self) -> int:
        """Clean up expired cache keys."""
        try:
            # This would scan for expired keys and remove them
            # Redis handles TTL automatically, but we might want additional cleanup
            
            # For now, just return 0 as Redis handles expiration
            return 0
            
        except Exception as e:
            self.logger.error(f"Error cleaning up expired keys: {e}")
            return 0
    
    async def _update_cache_size_metrics(self):
        """Update cache size metrics for each layer."""
        try:
            for layer in CacheLayer:
                # Get approximate size for layer keys
                pattern = f"suburb_signal:{layer.value}:*"
                keys = await self.redis_client.keys(pattern)
                
                if keys:
                    # Sample some keys to estimate size
                    sample_size = min(10, len(keys))
                    sample_keys = keys[:sample_size]
                    
                    total_size = 0
                    for key in sample_keys:
                        try:
                            key_size = await self.redis_client.memory_usage(key)
                            if key_size:
                                total_size += key_size
                        except Exception as e:
                            # Log warning but continue with other keys
                            logger = structlog.get_logger(__name__)
                            logger.warning(f"Failed to get memory usage for key {key}: {e}", key=key)
                            continue
                    
                    if sample_size > 0:
                        avg_key_size = total_size / sample_size
                        estimated_total_size = avg_key_size * len(keys)
                        self.metrics[layer].cache_size_mb = estimated_total_size / (1024 * 1024)
                
        except Exception as e:
            self.logger.error(f"Error updating cache size metrics: {e}")
    
    async def _compress_large_values(self) -> int:
        """Compress large cached values to save memory."""
        try:
            # This would identify and compress large values
            # For now, return 0 as compression is handled during serialization
            return 0
            
        except Exception as e:
            self.logger.error(f"Error compressing large values: {e}")
            return 0
    
    async def _process_pending_invalidations(self):
        """Process any pending cache invalidations."""
        try:
            if self.pending_invalidations:
                invalidations_to_process = list(self.pending_invalidations)
                self.pending_invalidations.clear()
                
                for layer, key in invalidations_to_process:
                    await self.delete(layer, key)
                
                self.logger.debug(f"Processed {len(invalidations_to_process)} pending invalidations")
                
        except Exception as e:
            self.logger.error(f"Error processing pending invalidations: {e}")


# Cache decorator for automatic caching
def cache_result(
    layer: CacheLayer,
    key_generator: callable,
    ttl: Optional[int] = None,
    tags: Optional[List[str]] = None
):
    """
    Decorator for automatic result caching.
    
    Args:
        layer: Cache layer to use
        key_generator: Function to generate cache key from arguments
        ttl: Custom TTL
        tags: Invalidation tags
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            cache_manager = AnalysisCacheManager()
            
            # Generate cache key
            cache_key = key_generator(*args, **kwargs)
            
            # Try to get from cache
            cached_result = await cache_manager.get(layer, cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache_manager.set(layer, cache_key, result, ttl=ttl, tags=tags)
            
            return result
        return wrapper
    return decorator


# Example usage:
# @cache_result(
#     layer=CacheLayer.TREND,
#     key_generator=lambda suburb, period: f"trend_{suburb}_{period}",
#     ttl=3600,
#     tags=["trend_analysis"]
# )
# async def analyze_suburb_trend(suburb: str, period: str):
#     # Analysis logic here
#     pass