"""
ReAgent Sydney - Monitoring Metrics

Comprehensive metrics collection for agents, business logic, and system performance.
This module provides Prometheus metrics for all ReAgent components.
"""

import time
import functools
from typing import Dict, Any, Optional, Callable
from prometheus_client import Counter, Histogram, Gauge, Info
from reagent.utils.logging import get_logger

# =================================================================
# AGENT EXECUTION METRICS
# =================================================================

agent_executions_total = Counter(
    'agent_executions_total',
    'Total agent executions',
    ['agent_name', 'status']
)

agent_execution_duration_seconds = Histogram(
    'agent_execution_duration_seconds',
    'Agent execution duration in seconds',
    ['agent_name', 'execution_type'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, float('inf')]
)

agent_executions_failed_total = Counter(
    'agent_executions_failed_total',
    'Total failed agent executions',
    ['agent_name', 'error_type']
)

agent_memory_usage_bytes = Gauge(
    'agent_memory_usage_bytes',
    'Memory usage by agent',
    ['agent_name']
)

agent_active_tasks = Gauge(
    'agent_active_tasks',
    'Number of active tasks per agent',
    ['agent_name']
)

# =================================================================
# BUSINESS METRICS
# =================================================================

# Property listing metrics
properties_processed_total = Counter(
    'properties_processed_total',
    'Total properties processed',
    ['source', 'status']
)

properties_current_count = Gauge(
    'properties_current_count',
    'Current number of properties in database',
    ['property_type', 'suburb']
)

property_market_changes_total = Counter(
    'property_market_changes_total',
    'Total property market changes detected',
    ['change_type', 'suburb']
)

last_successful_scrape_timestamp = Gauge(
    'last_successful_scrape_timestamp',
    'Timestamp of last successful property scrape',
    ['source']
)

# Buyer matching metrics
buyer_matches_created_total = Counter(
    'buyer_matches_created_total',
    'Total buyer matches created',
    ['match_quality', 'property_type']
)

buyer_notifications_sent_total = Counter(
    'buyer_notifications_sent_total',
    'Total buyer notifications sent',
    ['notification_type', 'channel']
)

buyer_profiles_active = Gauge(
    'buyer_profiles_active',
    'Number of active buyer profiles'
)

# Vector search metrics
vector_searches_total = Counter(
    'vector_searches_total',
    'Total vector searches performed',
    ['search_type', 'status']
)

vector_search_duration_seconds = Histogram(
    'vector_search_duration_seconds',
    'Vector search duration in seconds',
    ['search_type'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, float('inf')]
)

vector_embeddings_created_total = Counter(
    'vector_embeddings_created_total',
    'Total vector embeddings created',
    ['content_type']
)

# External API metrics
external_api_requests_total = Counter(
    'external_api_requests_total',
    'Total external API requests',
    ['api_name', 'endpoint', 'status']
)

external_api_requests_failed_total = Counter(
    'external_api_requests_failed_total',
    'Total failed external API requests',
    ['api_name', 'error_type']
)

external_api_response_time_seconds = Histogram(
    'external_api_response_time_seconds',
    'External API response time in seconds',
    ['api_name', 'endpoint'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, float('inf')]
)

external_api_rate_limit_hits_total = Counter(
    'external_api_rate_limit_hits_total',
    'Total external API rate limit hits',
    ['api_name']
)

external_api_cache_hits_total = Counter(
    'external_api_cache_hits_total',
    'Total external API requests served from cache',
    ['api_name', 'endpoint']
)

# =================================================================
# DATA QUALITY METRICS
# =================================================================

data_validation_errors_total = Counter(
    'data_validation_errors_total',
    'Total data validation errors',
    ['data_type', 'error_type']
)

data_quality_score = Gauge(
    'data_quality_score',
    'Data quality score (0-1)',
    ['data_type']
)

duplicate_records_detected_total = Counter(
    'duplicate_records_detected_total',
    'Total duplicate records detected',
    ['record_type']
)

# =================================================================
# CACHE PERFORMANCE METRICS
# =================================================================

cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'cache_type', 'status']
)

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate (0-1)',
    ['cache_type']
)

cache_memory_usage_bytes = Gauge(
    'cache_memory_usage_bytes',
    'Cache memory usage in bytes',
    ['cache_type']
)

# =================================================================
# SYSTEM INFO METRICS
# =================================================================

reagent_info = Info(
    'reagent_info',
    'ReAgent Sydney system information'
)

# Initialize system info
reagent_info.info({
    'version': '1.0.0',
    'environment': 'production',
    'agents': 'listing_watcher,suburb_signal,buyer_matchmaker,seller_strategy,off_market_radar,agent_whisperer',
    'data_sources': 'domain,realestate_com_au,corelogic,nsw_lpi'
})

# =================================================================
# METRIC DECORATORS AND UTILITIES
# =================================================================

def track_agent_execution(agent_name: str, execution_type: str = "default"):
    """Decorator to track agent execution metrics."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            agent_active_tasks.labels(agent_name=agent_name).inc()
            
            try:
                result = await func(*args, **kwargs)
                
                # Record success metrics
                duration = time.time() - start_time
                agent_executions_total.labels(
                    agent_name=agent_name,
                    status="success"
                ).inc()
                
                agent_execution_duration_seconds.labels(
                    agent_name=agent_name,
                    execution_type=execution_type
                ).observe(duration)
                
                logger.info(
                    "Agent execution completed",
                    agent_name=agent_name,
                    execution_type=execution_type,
                    duration_seconds=duration
                )
                
                return result
                
            except Exception as e:
                # Record failure metrics
                duration = time.time() - start_time
                error_type = type(e).__name__
                
                agent_executions_total.labels(
                    agent_name=agent_name,
                    status="failed"
                ).inc()
                
                agent_executions_failed_total.labels(
                    agent_name=agent_name,
                    error_type=error_type
                ).inc()
                
                agent_execution_duration_seconds.labels(
                    agent_name=agent_name,
                    execution_type=execution_type
                ).observe(duration)
                
                logger.error(
                    "Agent execution failed",
                    agent_name=agent_name,
                    execution_type=execution_type,
                    error=str(e),
                    duration_seconds=duration,
                    exc_info=True
                )
                
                raise
                
            finally:
                agent_active_tasks.labels(agent_name=agent_name).dec()
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            agent_active_tasks.labels(agent_name=agent_name).inc()
            
            try:
                result = func(*args, **kwargs)
                
                # Record success metrics
                duration = time.time() - start_time
                agent_executions_total.labels(
                    agent_name=agent_name,
                    status="success"
                ).inc()
                
                agent_execution_duration_seconds.labels(
                    agent_name=agent_name,
                    execution_type=execution_type
                ).observe(duration)
                
                return result
                
            except Exception as e:
                # Record failure metrics
                duration = time.time() - start_time
                error_type = type(e).__name__
                
                agent_executions_total.labels(
                    agent_name=agent_name,
                    status="failed"
                ).inc()
                
                agent_executions_failed_total.labels(
                    agent_name=agent_name,
                    error_type=error_type
                ).inc()
                
                raise
                
            finally:
                agent_active_tasks.labels(agent_name=agent_name).dec()
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

def track_external_api_call(api_name: str, endpoint: str, cache_hit: bool = False):
    """Decorator to track external API call metrics."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if cache_hit:
                external_api_cache_hits_total.labels(
                    api_name=api_name,
                    endpoint=endpoint
                ).inc()
                return await func(*args, **kwargs)

            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                
                # Record success metrics
                duration = time.time() - start_time
                external_api_requests_total.labels(
                    api_name=api_name,
                    endpoint=endpoint,
                    status="success"
                ).inc()
                
                external_api_response_time_seconds.labels(
                    api_name=api_name,
                    endpoint=endpoint
                ).observe(duration)
                
                return result
                
            except Exception as e:
                # Record failure metrics
                duration = time.time() - start_time
                error_type = type(e).__name__
                
                external_api_requests_total.labels(
                    api_name=api_name,
                    endpoint=endpoint,
                    status="failed"
                ).inc()
                
                external_api_requests_failed_total.labels(
                    api_name=api_name,
                    error_type=error_type
                ).inc()
                
                external_api_response_time_seconds.labels(
                    api_name=api_name,
                    endpoint=endpoint
                ).observe(duration)
                
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if cache_hit:
                external_api_cache_hits_total.labels(
                    api_name=api_name,
                    endpoint=endpoint
                ).inc()
                return func(*args, **kwargs)

            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Record success metrics
                duration = time.time() - start_time
                external_api_requests_total.labels(
                    api_name=api_name,
                    endpoint=endpoint,
                    status="success"
                ).inc()
                
                external_api_response_time_seconds.labels(
                    api_name=api_name,
                    endpoint=endpoint
                ).observe(duration)
                
                return result
                
            except Exception as e:
                # Record failure metrics
                error_type = type(e).__name__
                
                external_api_requests_total.labels(
                    api_name=api_name,
                    endpoint=endpoint,
                    status="failed"
                ).inc()
                
                external_api_requests_failed_total.labels(
                    api_name=api_name,
                    error_type=error_type
                ).inc()
                
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

def record_property_processed(source: str, status: str):
    """Record a property processing event."""
    properties_processed_total.labels(source=source, status=status).inc()

def record_buyer_match(match_quality: str, property_type: str):
    """Record a buyer match event."""
    buyer_matches_created_total.labels(
        match_quality=match_quality,
        property_type=property_type
    ).inc()

def record_vector_search(search_type: str, duration: float, status: str = "success"):
    """Record a vector search event."""
    vector_searches_total.labels(search_type=search_type, status=status).inc()
    vector_search_duration_seconds.labels(search_type=search_type).observe(duration)

def update_data_quality_score(data_type: str, score: float):
    """Update data quality score for a data type."""
    data_quality_score.labels(data_type=data_type).set(score)

def record_cache_operation(operation: str, cache_type: str, status: str):
    """Record a cache operation."""
    cache_operations_total.labels(
        operation=operation,
        cache_type=cache_type,
        status=status
    ).inc()

def update_cache_hit_rate(cache_type: str, hit_rate: float):
    """Update cache hit rate."""
    cache_hit_rate.labels(cache_type=cache_type).set(hit_rate)

# =================================================================
# SYSTEM PERFORMANCE METRICS
# =================================================================

system_cpu_usage_percent = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

system_memory_usage_percent = Gauge(
    'system_memory_usage_percent', 
    'System memory usage percentage'
)

system_disk_usage_percent = Gauge(
    'system_disk_usage_percent',
    'System disk usage percentage',
    ['mount_point']
)

system_network_bytes_sent = Counter(
    'system_network_bytes_sent',
    'Total network bytes sent',
    ['interface']
)

system_network_bytes_received = Counter(
    'system_network_bytes_received', 
    'Total network bytes received',
    ['interface']
)

# Component health status gauges
component_health_status = Gauge(
    'component_health_status',
    'Component health status (1=healthy, 0.5=degraded, 0=unhealthy)',
    ['component']
)

component_response_time_seconds = Gauge(
    'component_response_time_seconds',
    'Component response time in seconds',
    ['component']
)

# =================================================================
# HEALTH CHECK UTILITIES
# =================================================================

class HealthChecker:
    """System health checking utilities with real implementation."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity and performance with actual queries."""
        start_time = time.time()
        try:
            from reagent.core.database.engine import get_database
            
            # Test basic connectivity
            async with get_database() as db:
                # Test basic query
                result = await db.execute("SELECT 1 as health_check")
                health_row = result.fetchone()
                
                # Get connection pool stats
                pool_stats = await db.execute(
                    "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active'"
                )
                active_connections = pool_stats.fetchone()[0]
                
                # Get max connections
                max_conn_result = await db.execute("SHOW max_connections")
                max_connections = int(max_conn_result.fetchone()[0])
                
                # Check replication lag if replica exists
                try:
                    lag_result = await db.execute(
                        "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) as lag_seconds"
                    )
                    replication_lag = lag_result.fetchone()[0] or 0
                except:
                    replication_lag = None
                
                response_time_ms = (time.time() - start_time) * 1000
                
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time_ms, 2),
                    "connections_active": active_connections,
                    "connections_max": max_connections,
                    "connection_usage_percent": round((active_connections / max_connections) * 100, 2),
                    "replication_lag_seconds": replication_lag,
                    "timestamp": time.time()
                }
                
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            self.logger.error("Database health check failed", error=str(e), exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round(response_time_ms, 2),
                "timestamp": time.time()
            }
    
    async def check_redis_health(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance with actual commands."""
        start_time = time.time()
        try:
            from reagent.core.cache.redis_client import get_redis_client
            
            redis_client = await get_redis_client()
            
            # Test basic connectivity with ping
            ping_result = await redis_client.ping()
            
            # Get Redis info
            redis_info = await redis_client.info()
            memory_info = await redis_client.info('memory')
            
            # Test read/write operations
            test_key = "health_check_test"
            await redis_client.set(test_key, "test_value", ex=5)
            test_value = await redis_client.get(test_key)
            await redis_client.delete(test_key)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy" if ping_result and test_value == "test_value" else "degraded",
                "response_time_ms": round(response_time_ms, 2),
                "memory_usage_mb": round(memory_info.get('used_memory', 0) / 1024 / 1024, 2),
                "memory_peak_mb": round(memory_info.get('used_memory_peak', 0) / 1024 / 1024, 2),
                "connected_clients": redis_info.get('connected_clients', 0),
                "total_commands_processed": redis_info.get('total_commands_processed', 0),
                "keyspace_hits": redis_info.get('keyspace_hits', 0),
                "keyspace_misses": redis_info.get('keyspace_misses', 0),
                "hit_rate": self._calculate_hit_rate(redis_info),
                "uptime_seconds": redis_info.get('uptime_in_seconds', 0),
                "timestamp": time.time()
            }
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            self.logger.error("Redis health check failed", error=str(e), exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round(response_time_ms, 2),
                "timestamp": time.time()
            }
    
    async def check_weaviate_health(self) -> Dict[str, Any]:
        """Check Weaviate connectivity and performance with actual queries."""
        start_time = time.time()
        try:
            from reagent.core.vector_db.client import get_weaviate_client
            
            client = await get_weaviate_client()
            
            # Check if Weaviate is ready
            is_ready = client.is_ready()
            
            # Get cluster info
            cluster_meta = client.cluster.get_nodes_status()
            
            # Get schema info
            schema = client.schema.get()
            class_count = len(schema.get('classes', []))
            
            # Get object counts for each class
            object_counts = {}
            total_objects = 0
            
            for class_info in schema.get('classes', []):
                class_name = class_info['class']
                try:
                    aggregate_result = client.query.aggregate(class_name).with_meta_count().do()
                    count = aggregate_result['data']['Aggregate'][class_name][0]['meta']['count']
                    object_counts[class_name] = count
                    total_objects += count
                except:
                    object_counts[class_name] = 0
            
            # Test a simple query
            try:
                # Try to query the first class if it exists
                if schema.get('classes'):
                    first_class = schema['classes'][0]['class']
                    query_result = (
                        client.query
                        .get(first_class)
                        .with_limit(1)
                        .do()
                    )
                    query_success = True
                else:
                    query_success = False
            except:
                query_success = False
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return {
                "status": "healthy" if is_ready and query_success else "degraded",
                "response_time_ms": round(response_time_ms, 2),
                "is_ready": is_ready,
                "cluster_status": cluster_meta,
                "schema_classes": class_count,
                "total_objects": total_objects,
                "objects_by_class": object_counts,
                "query_test_passed": query_success,
                "timestamp": time.time()
            }
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            self.logger.error("Weaviate health check failed", error=str(e), exc_info=True)
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": round(response_time_ms, 2),
                "timestamp": time.time()
            }
    
    async def check_external_apis_health(self) -> Dict[str, Any]:
        """Check external API endpoints health."""
        api_health = {}
        
        # Check Domain API
        try:
            from reagent.services.external_apis.domain_client import DomainClient
            domain_client = DomainClient()
            start_time = time.time()
            
            # Simple test request (adjust based on actual API)
            test_result = await domain_client.test_connection()
            response_time_ms = (time.time() - start_time) * 1000
            
            api_health['domain'] = {
                "status": "healthy" if test_result else "unhealthy",
                "response_time_ms": round(response_time_ms, 2),
                "timestamp": time.time()
            }
        except Exception as e:
            api_health['domain'] = {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        
        # Check RealEstate.com.au API
        try:
            from reagent.services.external_apis.realestate_client import RealEstateClient
            rea_client = RealEstateClient()
            start_time = time.time()
            
            test_result = await rea_client.test_connection()
            response_time_ms = (time.time() - start_time) * 1000
            
            api_health['realestate'] = {
                "status": "healthy" if test_result else "unhealthy",
                "response_time_ms": round(response_time_ms, 2),
                "timestamp": time.time()
            }
        except Exception as e:
            api_health['realestate'] = {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        
        return api_health
    
    def _calculate_hit_rate(self, redis_info: Dict) -> float:
        """Calculate Redis cache hit rate."""
        hits = redis_info.get('keyspace_hits', 0)
        misses = redis_info.get('keyspace_misses', 0)
        total = hits + misses
        return round(hits / total if total > 0 else 0, 4)
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status with actual checks."""
        health_checks = {
            "database": await self.check_database_health(),
            "redis": await self.check_redis_health(), 
            "weaviate": await self.check_weaviate_health(),
            "external_apis": await self.check_external_apis_health()
        }
        
        # Calculate overall system status
        unhealthy_components = [
            name for name, health in health_checks.items() 
            if health.get('status') == 'unhealthy'
        ]
        
        degraded_components = [
            name for name, health in health_checks.items()
            if health.get('status') == 'degraded'
        ]
        
        if unhealthy_components:
            overall_status = "unhealthy"
        elif degraded_components:
            overall_status = "degraded"
        else:
            overall_status = "healthy"
        
        return {
            "timestamp": time.time(),
            "overall_status": overall_status,
            "unhealthy_components": unhealthy_components,
            "degraded_components": degraded_components,
            "components": health_checks,
            "system_info": {
                "version": "1.0.0",
                "environment": "production",
                "uptime_seconds": self._get_system_uptime()
            }
        }
    
    def _get_system_uptime(self) -> float:
        """Get system uptime in seconds."""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                return uptime_seconds
        except:
            return 0