"""
Cache Decorators

Provides decorators for caching function results with automatic key generation,
TTL management, and cache invalidation patterns.
"""

import asyncio
import hashlib
import inspect
from functools import wraps
from typing import Any, Callable, Optional, Union
from datetime import timedelta

import structlog

from .redis_client import get_cache_manager

logger = structlog.get_logger(__name__)


def cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from function arguments.
    
    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        str: Generated cache key
    """
    # Create a string representation of all arguments
    key_parts = []
    
    for arg in args:
        if hasattr(arg, '__dict__'):
            # For objects, use class name and relevant attributes
            key_parts.append(f"{arg.__class__.__name__}:{id(arg)}")
        else:
            key_parts.append(str(arg))
    
    for k, v in sorted(kwargs.items()):
        if hasattr(v, '__dict__'):
            key_parts.append(f"{k}:{v.__class__.__name__}:{id(v)}")
        else:
            key_parts.append(f"{k}:{v}")
    
    # Create hash of the key parts to ensure consistent length
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(
    ttl: Optional[Union[int, timedelta]] = None,
    key_prefix: Optional[str] = None,
    key_builder: Optional[Callable] = None,
    include_self: bool = False,
    cache_none: bool = False
):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time to live for cached values
        key_prefix: Prefix for cache keys
        key_builder: Custom function to build cache keys
        include_self: Whether to include 'self' in key generation
        cache_none: Whether to cache None results
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        func_name = f"{func.__module__}.{func.__qualname__}"
        cache_manager = get_cache_manager()
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key_str = key_builder(*args, **kwargs)
            else:
                # Filter out 'self' if not included
                filtered_args = args
                if not include_self and args and hasattr(args[0], '__dict__'):
                    filtered_args = args[1:]
                
                key_suffix = cache_key(*filtered_args, **kwargs)
                cache_key_str = f"{key_prefix or func_name}:{key_suffix}"
            
            # Try to get from cache
            try:
                cached_result = await cache_manager.get(cache_key_str)
                if cached_result is not None or (cache_none and await cache_manager.exists(cache_key_str)):
                    logger.debug("Cache hit", function=func_name, key=cache_key_str)
                    return cached_result
            except Exception as e:
                logger.warning("Cache get failed", function=func_name, error=str(e))
            
            # Call original function
            logger.debug("Cache miss", function=func_name, key=cache_key_str)
            result = await func(*args, **kwargs)
            
            # Cache the result
            if result is not None or cache_none:
                try:
                    success = await cache_manager.set(cache_key_str, result, ttl)
                    if success:
                        logger.debug("Cache set", function=func_name, key=cache_key_str)
                    else:
                        logger.warning("Cache set failed", function=func_name, key=cache_key_str)
                except Exception as e:
                    logger.warning("Cache set error", function=func_name, error=str(e))
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, create async wrapper
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If event loop is running, create a task
                return asyncio.create_task(async_wrapper(*args, **kwargs))
            else:
                # If no event loop is running, run the async function
                return loop.run_until_complete(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def cached_property(
    ttl: Optional[Union[int, timedelta]] = None,
    key_prefix: Optional[str] = None
):
    """
    Decorator for caching property values.
    
    Args:
        ttl: Time to live for cached values
        key_prefix: Prefix for cache keys
        
    Returns:
        Decorated property
    """
    def decorator(func: Callable) -> property:
        cache_manager = get_cache_manager()
        prop_name = func.__name__
        
        async def getter(self):
            # Build cache key using object id and property name
            cache_key_str = f"{key_prefix or self.__class__.__name__}:{id(self)}:{prop_name}"
            
            # Try to get from cache
            try:
                cached_result = await cache_manager.get(cache_key_str)
                if cached_result is not None:
                    return cached_result
            except Exception as e:
                logger.warning("Property cache get failed", property=prop_name, error=str(e))
            
            # Call original property getter
            result = await func(self)
            
            # Cache the result
            try:
                await cache_manager.set(cache_key_str, result, ttl)
            except Exception as e:
                logger.warning("Property cache set failed", property=prop_name, error=str(e))
            
            return result
        
        return property(getter)
    
    return decorator


def cache_invalidate(
    pattern: Optional[str] = None,
    keys: Optional[list] = None,
    key_builder: Optional[Callable] = None
):
    """
    Decorator for invalidating cache entries after function execution.
    
    Args:
        pattern: Pattern to match keys for invalidation
        keys: Specific keys to invalidate
        key_builder: Function to build keys from function arguments
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        cache_manager = get_cache_manager()
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Execute original function
            result = await func(*args, **kwargs)
            
            # Invalidate cache entries
            try:
                if key_builder:
                    # Use custom key builder
                    keys_to_invalidate = key_builder(*args, **kwargs)
                    if isinstance(keys_to_invalidate, str):
                        keys_to_invalidate = [keys_to_invalidate]
                    await cache_manager.delete(*keys_to_invalidate)
                elif keys:
                    # Use specific keys
                    await cache_manager.delete(*keys)
                elif pattern:
                    # Use pattern matching
                    await cache_manager.clear_pattern(pattern)
                    
            except Exception as e:
                logger.warning("Cache invalidation failed", function=func.__name__, error=str(e))
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Run invalidation in background
            try:
                loop = asyncio.get_event_loop()
                if key_builder:
                    keys_to_invalidate = key_builder(*args, **kwargs)
                    if isinstance(keys_to_invalidate, str):
                        keys_to_invalidate = [keys_to_invalidate]
                    loop.create_task(cache_manager.delete(*keys_to_invalidate))
                elif keys:
                    loop.create_task(cache_manager.delete(*keys))
                elif pattern:
                    loop.create_task(cache_manager.clear_pattern(pattern))
            except Exception as e:
                logger.warning("Cache invalidation failed", function=func.__name__, error=str(e))
            
            return result
        
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def memoize(
    maxsize: int = 128,
    ttl: Optional[Union[int, timedelta]] = None
):
    """
    In-memory memoization decorator with LRU eviction.
    Use for frequently called functions with limited argument variations.
    
    Args:
        maxsize: Maximum number of cached results
        ttl: Time to live for cached values
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        access_order = []
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Create cache key
            key = cache_key(*args, **kwargs)
            current_time = asyncio.get_event_loop().time()
            
            # Check if cached and not expired
            if key in cache:
                cached_result, cached_time = cache[key]
                
                # Check TTL
                if ttl is None or (current_time - cached_time) < (
                    ttl if isinstance(ttl, (int, float)) else ttl.total_seconds()
                ):
                    # Move to end of access order (most recently used)
                    access_order.remove(key)
                    access_order.append(key)
                    return cached_result
                else:
                    # Expired, remove from cache
                    del cache[key]
                    access_order.remove(key)
            
            # Call original function
            result = await func(*args, **kwargs)
            
            # Cache the result
            cache[key] = (result, current_time)
            access_order.append(key)
            
            # Evict oldest entries if cache is full
            while len(cache) > maxsize:
                oldest_key = access_order.pop(0)
                del cache[oldest_key]
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Create cache key
            key = cache_key(*args, **kwargs)
            import time
            current_time = time.time()
            
            # Check if cached and not expired
            if key in cache:
                cached_result, cached_time = cache[key]
                
                # Check TTL
                if ttl is None or (current_time - cached_time) < (
                    ttl if isinstance(ttl, (int, float)) else ttl.total_seconds()
                ):
                    # Move to end of access order (most recently used)
                    access_order.remove(key)
                    access_order.append(key)
                    return cached_result
                else:
                    # Expired, remove from cache
                    del cache[key]
                    access_order.remove(key)
            
            # Call original function
            result = func(*args, **kwargs)
            
            # Cache the result
            cache[key] = (result, current_time)
            access_order.append(key)
            
            # Evict oldest entries if cache is full
            while len(cache) > maxsize:
                oldest_key = access_order.pop(0)
                del cache[oldest_key]
            
            return result
        
        # Add cache inspection methods
        def cache_info():
            return {
                "hits": len([k for k in access_order if k in cache]),
                "misses": len(access_order) - len(cache),
                "maxsize": maxsize,
                "currsize": len(cache)
            }
        
        def cache_clear():
            cache.clear()
            access_order.clear()
        
        wrapper = async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
        wrapper.cache_info = cache_info
        wrapper.cache_clear = cache_clear
        
        return wrapper
    
    return decorator