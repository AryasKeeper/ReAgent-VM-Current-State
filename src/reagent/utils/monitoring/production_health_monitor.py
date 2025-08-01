"""
Production Health Monitor - Comprehensive Service Health & Recovery System

Implements circuit breaker patterns, graceful degradation, and self-healing
capabilities for ReAgent production deployment.
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from contextlib import asynccontextmanager

import redis
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from reagent.core.config import get_settings
from reagent.utils.logging import get_logger


class ServiceStatus(Enum):
    """Service health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DISABLED = "disabled"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Service failed, blocking requests
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class ServiceHealth:
    """Individual service health status."""
    name: str
    status: ServiceStatus
    last_check: datetime
    response_time_ms: float
    error_count: int
    success_count: int
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.success_count + self.error_count
        return (self.success_count / total * 100) if total > 0 else 0.0
    
    @property
    def is_available(self) -> bool:
        """Check if service is available for requests."""
        return self.status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]


@dataclass
class CircuitBreaker:
    """Circuit breaker implementation for service resilience."""
    name: str
    failure_threshold: int = 5
    timeout_seconds: int = 60
    reset_timeout_seconds: int = 300
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    
    def should_allow_request(self) -> bool:
        """Determine if request should be allowed."""
        now = datetime.utcnow()
        
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if (self.last_failure_time and 
                now - self.last_failure_time > timedelta(seconds=self.reset_timeout_seconds)):
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        self.last_success_time = datetime.utcnow()
        self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


class ProductionHealthMonitor:
    """
    Comprehensive production health monitoring with service resilience.
    
    Features:
    - Circuit breaker patterns for failed dependencies
    - Graceful degradation when services unavailable
    - Self-healing capabilities with automatic recovery
    - Real-time health dashboards and alerting
    - Service isolation to prevent cascade failures
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        
        # Service health tracking
        self.services: Dict[str, ServiceHealth] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.feature_flags: Dict[str, bool] = {}
        
        # Health check intervals
        self.check_interval = 30  # seconds
        self.critical_check_interval = 10  # seconds for critical services
        
        # Service dependency mapping
        self.service_dependencies = {
            "api": ["postgres", "redis"],  # Core API doesn't require Weaviate
            "agents": ["postgres", "redis", "api"],  # Agents can work without vector search
            "celery": ["postgres", "redis"],
            "frontend": ["api"],
            "vector_search": ["weaviate"]  # Optional feature
        }
        
        # Initialize circuit breakers
        self._initialize_circuit_breakers()
        
        # Initialize feature flags
        self.feature_flags = {
            "vector_search_enabled": False,  # Start disabled
            "buyer_matching_enabled": False,
            "advanced_analytics_enabled": False,
            "real_time_monitoring": True,
            "graceful_degradation": True
        }
    
    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for all services."""
        services = ["postgres", "redis", "weaviate", "api", "agents", "celery"]
        
        for service in services:
            self.circuit_breakers[service] = CircuitBreaker(
                name=service,
                failure_threshold=5 if service != "weaviate" else 3,
                timeout_seconds=60,
                reset_timeout_seconds=300 if service != "weaviate" else 600
            )
    
    async def start_monitoring(self):
        """Start continuous health monitoring."""
        self.logger.info("Starting production health monitoring")
        
        # Create monitoring tasks
        tasks = [
            asyncio.create_task(self._monitor_critical_services()),
            asyncio.create_task(self._monitor_optional_services()),
            asyncio.create_task(self._monitor_recovery_attempts()),
            asyncio.create_task(self._update_feature_flags())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error("Health monitoring error", error=str(e), exc_info=True)
    
    async def _monitor_critical_services(self):
        """Monitor critical services that must be available."""
        critical_services = ["postgres", "redis"]
        
        while True:
            try:
                for service in critical_services:
                    await self._check_service_health(service)
                
                await asyncio.sleep(self.critical_check_interval)
                
            except Exception as e:
                self.logger.error("Critical service monitoring error", error=str(e))
                await asyncio.sleep(self.critical_check_interval)
    
    async def _monitor_optional_services(self):
        """Monitor optional services with circuit breaker logic."""
        optional_services = ["weaviate", "api", "agents", "celery"]
        
        while True:
            try:
                for service in optional_services:
                    circuit = self.circuit_breakers[service]
                    
                    if circuit.should_allow_request():
                        await self._check_service_health(service)
                    else:
                        self.logger.debug(f"Service {service} circuit breaker OPEN, skipping check")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error("Optional service monitoring error", error=str(e))
                await asyncio.sleep(self.check_interval)
    
    async def _monitor_recovery_attempts(self):
        """Monitor and attempt service recovery."""
        while True:
            try:
                await self._attempt_service_recovery()
                await asyncio.sleep(60)  # Check recovery every minute
                
            except Exception as e:
                self.logger.error("Recovery monitoring error", error=str(e))
                await asyncio.sleep(60)
    
    async def _update_feature_flags(self):
        """Update feature flags based on service availability."""
        while True:
            try:
                # Update vector search availability
                weaviate_health = self.services.get("weaviate")
                if weaviate_health and weaviate_health.is_available:
                    if not self.feature_flags["vector_search_enabled"]:
                        self.logger.info("Enabling vector search - Weaviate is healthy")
                        self.feature_flags["vector_search_enabled"] = True
                        self.feature_flags["buyer_matching_enabled"] = True
                else:
                    if self.feature_flags["vector_search_enabled"]:
                        self.logger.warning("Disabling vector search - Weaviate unhealthy")
                        self.feature_flags["vector_search_enabled"] = False
                        self.feature_flags["buyer_matching_enabled"] = False
                
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error("Feature flag update error", error=str(e))
                await asyncio.sleep(30)
    
    async def _check_service_health(self, service_name: str) -> ServiceHealth:
        """Check individual service health."""
        start_time = time.time()
        
        try:
            if service_name == "postgres":
                status = await self._check_postgres_health()
            elif service_name == "redis":
                status = await self._check_redis_health()
            elif service_name == "weaviate":
                status = await self._check_weaviate_health()
            elif service_name == "api":
                status = await self._check_api_health()
            else:
                status = ServiceStatus.UNKNOWN
            
            response_time = (time.time() - start_time) * 1000
            
            # Update service health record
            if service_name not in self.services:
                self.services[service_name] = ServiceHealth(
                    name=service_name,
                    status=status,
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    error_count=0,
                    success_count=0
                )
            
            health = self.services[service_name]
            health.status = status
            health.last_check = datetime.utcnow()
            health.response_time_ms = response_time
            
            if status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]:
                health.success_count += 1
                health.last_error = None
                
                # Record circuit breaker success
                if service_name in self.circuit_breakers:
                    self.circuit_breakers[service_name].record_success()
            else:
                health.error_count += 1
                
                # Record circuit breaker failure
                if service_name in self.circuit_breakers:
                    self.circuit_breakers[service_name].record_failure()
            
            return health
            
        except Exception as e:
            error_msg = str(e)
            response_time = (time.time() - start_time) * 1000
            
            # Create or update error health record
            if service_name not in self.services:
                self.services[service_name] = ServiceHealth(
                    name=service_name,
                    status=ServiceStatus.UNHEALTHY,
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time,
                    error_count=1,
                    success_count=0,
                    last_error=error_msg
                )
            else:
                health = self.services[service_name]
                health.status = ServiceStatus.UNHEALTHY
                health.last_check = datetime.utcnow()
                health.response_time_ms = response_time
                health.error_count += 1
                health.last_error = error_msg
            
            # Record circuit breaker failure
            if service_name in self.circuit_breakers:
                self.circuit_breakers[service_name].record_failure()
            
            self.logger.error(f"Service {service_name} health check failed", 
                            error=error_msg, response_time_ms=response_time)
            
            return self.services[service_name]
    
    async def _check_postgres_health(self) -> ServiceStatus:
        """Check PostgreSQL health."""
        try:
            engine = create_engine(self.settings.database.url)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            engine.dispose()
            return ServiceStatus.HEALTHY
        except Exception:
            return ServiceStatus.UNHEALTHY
    
    async def _check_redis_health(self) -> ServiceStatus:
        """Check Redis health."""
        try:
            r = redis.from_url(self.settings.redis.url)
            r.ping()
            r.close()
            return ServiceStatus.HEALTHY
        except Exception:
            return ServiceStatus.UNHEALTHY
    
    async def _check_weaviate_health(self) -> ServiceStatus:
        """Check Weaviate health."""
        try:
            import weaviate
            client = weaviate.Client(url=self.settings.weaviate.url)
            if client.is_ready():
                return ServiceStatus.HEALTHY
            else:
                return ServiceStatus.DEGRADED
        except Exception:
            return ServiceStatus.UNHEALTHY
    
    async def _check_api_health(self) -> ServiceStatus:
        """Check API health."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/api/v1/health/") as response:
                    if response.status == 200:
                        return ServiceStatus.HEALTHY
                    else:
                        return ServiceStatus.DEGRADED
        except Exception:
            return ServiceStatus.UNHEALTHY
    
    async def _attempt_service_recovery(self):
        """Attempt to recover failed services."""
        for service_name, health in self.services.items():
            if (health.status == ServiceStatus.UNHEALTHY and 
                datetime.utcnow() - health.last_check > timedelta(minutes=5)):
                
                self.logger.info(f"Attempting recovery for service {service_name}")
                
                # Attempt service-specific recovery
                if service_name == "weaviate":
                    await self._attempt_weaviate_recovery()
                elif service_name == "api":
                    await self._attempt_api_recovery()
    
    async def _attempt_weaviate_recovery(self):
        """Attempt Weaviate service recovery."""
        try:
            # Try to restart Weaviate container
            import subprocess
            result = subprocess.run([
                "docker", "restart", "reagent-weaviate-dev"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.logger.info("Weaviate container restart successful")
                # Wait a bit for service to start
                await asyncio.sleep(30)
            else:
                self.logger.error("Weaviate container restart failed", 
                                stderr=result.stderr)
        except Exception as e:
            self.logger.error("Weaviate recovery attempt failed", error=str(e))
    
    async def _attempt_api_recovery(self):
        """Attempt API service recovery."""
        try:
            # Try to restart API container
            import subprocess
            result = subprocess.run([
                "docker", "restart", "reagent-api-dev"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.logger.info("API container restart successful")
                await asyncio.sleep(15)
            else:
                self.logger.error("API container restart failed", 
                                stderr=result.stderr)
        except Exception as e:
            self.logger.error("API recovery attempt failed", error=str(e))
    
    def get_system_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive system health summary."""
        now = datetime.utcnow()
        
        # Categorize services
        healthy_services = []
        degraded_services = []
        unhealthy_services = []
        
        for service_name, health in self.services.items():
            if health.status == ServiceStatus.HEALTHY:
                healthy_services.append(service_name)
            elif health.status == ServiceStatus.DEGRADED:
                degraded_services.append(service_name)
            else:
                unhealthy_services.append(service_name)
        
        # Determine overall system status
        if len(unhealthy_services) == 0:
            if len(degraded_services) == 0:
                overall_status = ServiceStatus.HEALTHY
            else:
                overall_status = ServiceStatus.DEGRADED
        else:
            # Check if critical services are down
            critical_down = any(s in unhealthy_services for s in ["postgres", "redis"])
            overall_status = ServiceStatus.UNHEALTHY if critical_down else ServiceStatus.DEGRADED
        
        return {
            "timestamp": now.isoformat(),
            "overall_status": overall_status.value,
            "system_uptime_hours": 24.0,  # Would track actual uptime
            "services": {
                "healthy": healthy_services,
                "degraded": degraded_services,
                "unhealthy": unhealthy_services,
                "total_count": len(self.services)
            },
            "circuit_breakers": {
                name: {
                    "state": cb.state.value,
                    "failure_count": cb.failure_count,
                    "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None
                }
                for name, cb in self.circuit_breakers.items()
            },
            "feature_flags": self.feature_flags.copy(),
            "service_details": {
                name: {
                    "status": health.status.value,
                    "response_time_ms": health.response_time_ms,
                    "success_rate": health.success_rate,
                    "last_check": health.last_check.isoformat(),
                    "last_error": health.last_error
                }
                for name, health in self.services.items()
            }
        }
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if feature is enabled based on service availability."""
        return self.feature_flags.get(feature_name, False)
    
    def get_available_services(self) -> Set[str]:
        """Get set of currently available services."""
        return {
            name for name, health in self.services.items()
            if health.is_available
        }
    
    @asynccontextmanager
    async def service_circuit_breaker(self, service_name: str):
        """Context manager for circuit breaker pattern."""
        circuit = self.circuit_breakers.get(service_name)
        
        if not circuit or not circuit.should_allow_request():
            raise ServiceUnavailableError(f"Service {service_name} is not available")
        
        try:
            yield
            if circuit:
                circuit.record_success()
        except Exception as e:
            if circuit:
                circuit.record_failure()
            raise


class ServiceUnavailableError(Exception):
    """Exception raised when a service is unavailable."""
    pass


# Global health monitor instance
_health_monitor: Optional[ProductionHealthMonitor] = None


async def get_health_monitor() -> ProductionHealthMonitor:
    """Get or create global health monitor instance."""
    global _health_monitor
    
    if _health_monitor is None:
        _health_monitor = ProductionHealthMonitor()
        # Start monitoring in background
        asyncio.create_task(_health_monitor.start_monitoring())
    
    return _health_monitor


async def check_service_availability(service_name: str) -> bool:
    """Quick check if service is available."""
    monitor = await get_health_monitor()
    health = monitor.services.get(service_name)
    return health.is_available if health else False


async def with_circuit_breaker(service_name: str, operation: Callable):
    """Execute operation with circuit breaker protection."""
    monitor = await get_health_monitor()
    
    async with monitor.service_circuit_breaker(service_name):
        return await operation()