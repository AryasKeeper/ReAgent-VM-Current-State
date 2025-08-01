"""
FastAPI Middleware Components

Contains custom middleware for authentication, rate limiting, 
CORS handling, and request/response processing.
"""

import time
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge
import structlog

logger = structlog.get_logger(__name__)

# Prometheus metrics for API monitoring
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed'
)

api_rate_limit_exceeded_total = Counter(
    'api_rate_limit_exceeded_total',
    'Number of requests that exceeded rate limits',
    ['endpoint']
)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Enhanced logging middleware with structured logging."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract useful request information
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Log successful requests
            logger.info(
                "Request processed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2),
                client_ip=client_ip,
                user_agent=user_agent,
                content_length=response.headers.get("content-length", 0)
            )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            # Log failed requests
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                process_time_ms=round(process_time * 1000, 2),
                client_ip=client_ip,
                user_agent=user_agent,
                exc_info=True
            )
            
            raise

class MetricsMiddleware(BaseHTTPMiddleware):
    """Comprehensive metrics middleware for Prometheus."""
    
    async def dispatch(self, request: Request, call_next):
        # Extract endpoint for metrics (remove query params and IDs)
        endpoint = self._normalize_endpoint(request.url.path)
        method = request.method
        
        # Track requests in progress
        http_requests_in_progress.inc()
        
        # Start timing
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            status_code = str(response.status_code)
            
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            return response
            
        except Exception as e:
            # Record error metrics
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status="500"
            ).inc()
            
            duration = time.time() - start_time
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            raise
            
        finally:
            # Decrement in-progress counter
            http_requests_in_progress.dec()
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for consistent metrics labeling."""
        # Remove common ID patterns to group similar endpoints
        import re
        
        # Replace UUIDs and numeric IDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Limit path length and remove query parameters
        if '?' in path:
            path = path.split('?')[0]
            
        return path[:100]  # Limit length to prevent metric explosion

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware with metrics."""
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
        
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = int(time.time() / 60)  # Current minute
        
        # Clean old entries
        self.request_counts = {
            timestamp: counts for timestamp, counts in self.request_counts.items()
            if timestamp >= current_time - 1
        }
        
        # Check rate limit
        if current_time not in self.request_counts:
            self.request_counts[current_time] = {}
            
        client_requests = self.request_counts[current_time].get(client_ip, 0)
        
        if client_requests >= self.requests_per_minute:
            # Record rate limit exceeded
            endpoint = self._normalize_endpoint(request.url.path)
            api_rate_limit_exceeded_total.labels(endpoint=endpoint).inc()
            
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"Retry-After": "60"}
            )
        
        # Increment counter
        self.request_counts[current_time][client_ip] = client_requests + 1
        
        return await call_next(request)
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path (same as MetricsMiddleware)."""
        import re
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        path = re.sub(r'/\d+', '/{id}', path)
        if '?' in path:
            path = path.split('?')[0]
        return path[:100]

__all__ = ["LoggingMiddleware", "MetricsMiddleware", "RateLimitMiddleware"]