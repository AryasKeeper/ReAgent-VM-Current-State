"""Advanced Redis-backed rate limiting for ReAgent Sydney."""

import time
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import redis.asyncio as redis
from prometheus_client import Counter, Histogram

from ...config.settings import settings
from ...utils.logging import get_reagent_logger

logger = get_reagent_logger("rate_limiter")

# Prometheus metrics
rate_limit_exceeded_total = Counter(
    'rate_limit_exceeded_total',
    'Number of requests that exceeded rate limits',
    ['endpoint', 'limit_type', 'user_type']
)

rate_limit_check_duration = Histogram(
    'rate_limit_check_duration_seconds',
    'Time spent checking rate limits',
    ['limit_type']
)


class RateLimitConfig:
    """Rate limiting configuration for different endpoints and user types."""
    
    # Default limits (requests per window)
    DEFAULT_LIMITS = {
        # General API limits
        "global": {"requests": 1000, "window": 3600},  # 1000/hour
        "per_ip": {"requests": 100, "window": 300},    # 100/5min
        "per_user": {"requests": 500, "window": 3600}, # 500/hour
        
        # Endpoint-specific limits
        "property_search": {"requests": 100, "window": 3600},     # 100/hour
        "buyer_matching": {"requests": 50, "window": 3600},       # 50/hour
        "agent_query": {"requests": 200, "window": 3600},         # 200/hour
        "suburb_analysis": {"requests": 75, "window": 3600},      # 75/hour
        "off_market_search": {"requests": 25, "window": 3600},    # 25/hour
        
        # Auth endpoints
        "login": {"requests": 5, "window": 300},          # 5/5min
        "register": {"requests": 3, "window": 3600},      # 3/hour
        "password_reset": {"requests": 3, "window": 3600}, # 3/hour
    }
    
    # Role-based multipliers
    ROLE_MULTIPLIERS = {
        "admin": 5.0,
        "agent": 3.0,
        "analyst": 2.0,
        "viewer": 1.0,
        "api_client": 10.0  # Higher limits for API clients
    }
    
    @classmethod
    def get_limit(cls, endpoint: str, user_role: Optional[str] = None) -> Tuple[int, int]:
        """
        Get rate limit for endpoint and user role.
        
        Args:
            endpoint: Endpoint identifier
            user_role: User role for multiplier
            
        Returns:
            Tuple of (requests, window_seconds)
        """
        base_limit = cls.DEFAULT_LIMITS.get(endpoint, cls.DEFAULT_LIMITS["global"])
        
        requests = base_limit["requests"]
        window = base_limit["window"]
        
        # Apply role multiplier
        if user_role and user_role in cls.ROLE_MULTIPLIERS:
            requests = int(requests * cls.ROLE_MULTIPLIERS[user_role])
        
        return requests, window


class RateLimiter:
    """Redis-backed distributed rate limiter with sliding window."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or self._create_redis_client()
        
    def _create_redis_client(self) -> redis.Redis:
        """Create Redis client from settings."""
        return redis.from_url(
            settings.redis.url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis.max_connections
        )
    
    async def check_rate_limit(
        self,
        key: str,
        requests_limit: int,
        window_seconds: int,
        identifier: str = "unknown"
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is within rate limit using sliding window.
        
        Args:
            key: Redis key for this rate limit bucket
            requests_limit: Maximum requests allowed
            window_seconds: Time window in seconds
            identifier: Request identifier for logging
            
        Returns:
            Tuple of (is_allowed, limit_info)
        """
        start_time = time.time()
        
        try:
            current_time = time.time()
            window_start = current_time - window_seconds
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration for cleanup
            pipe.expire(key, window_seconds + 60)
            
            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1] + 1  # +1 for current request
            
            # Check if limit exceeded
            is_allowed = current_count <= requests_limit
            
            # Prepare response info
            limit_info = {
                "limit": requests_limit,
                "remaining": max(0, requests_limit - current_count),
                "reset_time": int(current_time + window_seconds),
                "window_seconds": window_seconds,
                "current_count": current_count
            }
            
            # Log rate limit check
            if not is_allowed:
                logger.warning(
                    "Rate limit exceeded",
                    key=key,
                    identifier=identifier,
                    current_count=current_count,
                    limit=requests_limit,
                    window_seconds=window_seconds
                )
                
                # Record metrics
                endpoint = key.split(":")[1] if ":" in key else "unknown"
                user_type = key.split(":")[0] if ":" in key else "unknown"
                rate_limit_exceeded_total.labels(
                    endpoint=endpoint,
                    limit_type="sliding_window",
                    user_type=user_type
                ).inc()
            
            return is_allowed, limit_info
            
        except Exception as e:
            logger.error(
                "Rate limit check failed",
                error=str(e),
                key=key,
                identifier=identifier,
                exc_info=True
            )
            # Fail open - allow request if Redis is down
            return True, {"error": "rate_limit_check_failed"}
            
        finally:
            # Record metrics
            duration = time.time() - start_time
            rate_limit_check_duration.labels(limit_type="sliding_window").observe(duration)
    
    async def check_progressive_limit(
        self,
        key: str,
        base_limit: int,
        window_seconds: int,
        violation_count: int
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Progressive rate limiting - stricter limits for repeated violators.
        
        Args:
            key: Redis key for rate limit bucket
            base_limit: Base request limit
            window_seconds: Time window
            violation_count: Number of previous violations
            
        Returns:
            Tuple of (is_allowed, limit_info)
        """
        # Reduce limit based on violation history
        penalty_factor = min(0.1, 1.0 - (violation_count * 0.2))
        adjusted_limit = max(1, int(base_limit * penalty_factor))
        
        return await self.check_rate_limit(key, adjusted_limit, window_seconds)
    
    async def get_violation_count(self, identifier: str) -> int:
        """Get violation count for an identifier."""
        try:
            violation_key = f"violations:{identifier}"
            count = await self.redis.get(violation_key)
            return int(count) if count else 0
        except Exception:
            return 0
    
    async def increment_violation_count(self, identifier: str, ttl_hours: int = 24):
        """Increment violation count with TTL."""
        try:
            violation_key = f"violations:{identifier}"
            pipe = self.redis.pipeline()
            pipe.incr(violation_key)
            pipe.expire(violation_key, ttl_hours * 3600)
            await pipe.execute()
        except Exception as e:
            logger.error(f"Failed to increment violation count: {e}")
    
    async def clear_rate_limit(self, key: str) -> bool:
        """Clear rate limit for a key (admin function)."""
        try:
            result = await self.redis.delete(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to clear rate limit: {e}")
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for distributed rate limiting."""
    
    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or RateLimiter()
        
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)
        
        # Get client identifier
        client_ip = self._get_client_ip(request)
        user_info = await self._get_user_info(request)
        
        # Check multiple rate limits
        rate_limit_checks = []
        
        # 1. Per-IP rate limiting
        ip_key = f"ip:{client_ip}:global"
        requests_limit, window = RateLimitConfig.get_limit("per_ip")
        rate_limit_checks.append((ip_key, requests_limit, window, f"IP:{client_ip}"))
        
        # 2. Per-user rate limiting (if authenticated)
        if user_info:
            user_key = f"user:{user_info['user_id']}:global"
            user_requests, user_window = RateLimitConfig.get_limit("per_user", user_info.get("role"))
            rate_limit_checks.append((user_key, user_requests, user_window, f"User:{user_info['username']}"))
        
        # 3. Endpoint-specific rate limiting
        endpoint = self._get_endpoint_identifier(request.url.path)
        if endpoint:
            endpoint_key = f"endpoint:{client_ip}:{endpoint}"
            endpoint_requests, endpoint_window = RateLimitConfig.get_limit(endpoint, user_info.get("role") if user_info else None)
            rate_limit_checks.append((endpoint_key, endpoint_requests, endpoint_window, f"Endpoint:{endpoint}"))
        
        # Perform rate limit checks
        for key, limit, window, identifier in rate_limit_checks:
            # Check for progressive penalties
            violation_count = await self.rate_limiter.get_violation_count(identifier)
            
            if violation_count > 0:
                is_allowed, limit_info = await self.rate_limiter.check_progressive_limit(
                    key, limit, window, violation_count
                )
            else:
                is_allowed, limit_info = await self.rate_limiter.check_rate_limit(
                    key, limit, window, identifier
                )
            
            if not is_allowed:
                # Increment violation count
                await self.rate_limiter.increment_violation_count(identifier)
                
                # Return rate limit error
                return Response(
                    content=json.dumps({
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests for {identifier}",
                        "limit": limit_info.get("limit"),
                        "remaining": limit_info.get("remaining", 0),
                        "reset_time": limit_info.get("reset_time"),
                        "retry_after": limit_info.get("window_seconds", 60)
                    }),
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={
                        "Content-Type": "application/json",
                        "X-RateLimit-Limit": str(limit_info.get("limit", limit)),
                        "X-RateLimit-Remaining": str(limit_info.get("remaining", 0)),
                        "X-RateLimit-Reset": str(limit_info.get("reset_time", int(time.time()) + window)),
                        "Retry-After": str(limit_info.get("window_seconds", 60))
                    }
                )
        
        # Add rate limit headers to successful responses
        response = await call_next(request)
        
        # Add rate limit headers
        if rate_limit_checks:
            key, limit, window, identifier = rate_limit_checks[0]  # Use first check for headers
            _, limit_info = await self.rate_limiter.check_rate_limit(key, limit, window, identifier)
            
            response.headers["X-RateLimit-Limit"] = str(limit_info.get("limit", limit))
            response.headers["X-RateLimit-Remaining"] = str(limit_info.get("remaining", 0))
            response.headers["X-RateLimit-Reset"] = str(limit_info.get("reset_time", int(time.time()) + window))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check for forwarded headers (for proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    async def _get_user_info(self, request: Request) -> Optional[Dict[str, any]]:
        """Extract user information from request."""
        try:
            # Try to get user from JWT token
            authorization = request.headers.get("Authorization")
            if authorization and authorization.startswith("Bearer "):
                from ...core.auth.jwt_handler import verify_token
                token = authorization.split(" ")[1]
                token_data = verify_token(token)
                
                return {
                    "user_id": token_data.user_id,
                    "username": token_data.username,
                    "role": token_data.role.value if token_data.role else None
                }
        except Exception:
            pass
        
        # Try API key authentication
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Would need to validate API key here
            # For now, return generic API client info
            return {
                "user_id": f"api:{api_key[:8]}",
                "username": "api_client",
                "role": "api_client"
            }
        
        return None
    
    def _get_endpoint_identifier(self, path: str) -> Optional[str]:
        """Map URL path to endpoint identifier for rate limiting."""
        # Define endpoint mappings
        endpoint_mappings = {
            "/api/v1/listings/search": "property_search",
            "/api/v1/buyers/match": "buyer_matching",
            "/api/v1/agents/query": "agent_query",
            "/api/v1/suburbs/analyze": "suburb_analysis",
            "/api/v1/off-market/search": "off_market_search",
            "/auth/login": "login",
            "/auth/register": "register",
            "/auth/reset-password": "password_reset",
        }
        
        # Direct mapping
        if path in endpoint_mappings:
            return endpoint_mappings[path]
        
        # Pattern matching for parameterized endpoints
        if path.startswith("/api/v1/listings"):
            return "property_search"
        elif path.startswith("/api/v1/buyers"):
            return "buyer_matching"
        elif path.startswith("/api/v1/agents"):
            return "agent_query"
        elif path.startswith("/api/v1/suburbs"):
            return "suburb_analysis"
        elif path.startswith("/api/v1/off-market"):
            return "off_market_search"
        
        return None


# FastAPI dependency for endpoint-specific rate limiting
async def rate_limit_dependency(
    endpoint: str,
    requests_limit: int,
    window_seconds: int = 3600,
    request: Request = None
):
    """
    FastAPI dependency for custom rate limiting.
    
    Usage:
        @app.get("/expensive-endpoint")
        async def expensive_endpoint(
            _: None = Depends(
                lambda req: rate_limit_dependency("expensive", 10, 3600, req)
            )
        ):
            return {"data": "expensive computation"}
    """
    if not request:
        return
    
    rate_limiter = RateLimiter()
    client_ip = request.client.host if request.client else "unknown"
    
    key = f"custom:{client_ip}:{endpoint}"
    is_allowed, limit_info = await rate_limiter.check_rate_limit(
        key, requests_limit, window_seconds, f"Custom:{endpoint}"
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit_info.get("limit"),
                "remaining": limit_info.get("remaining", 0),
                "reset_time": limit_info.get("reset_time")
            },
            headers={
                "X-RateLimit-Limit": str(limit_info.get("limit")),
                "X-RateLimit-Remaining": str(limit_info.get("remaining", 0)),
                "X-RateLimit-Reset": str(limit_info.get("reset_time")),
                "Retry-After": str(window_seconds)
            }
        )