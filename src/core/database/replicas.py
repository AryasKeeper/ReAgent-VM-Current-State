"""
Database Replica Configuration

Provides read/write splitting and load balancing across database replicas.
Supports primary-secondary replication patterns for scalability.
"""

from enum import Enum
from typing import Dict, List, Optional, Union
import random

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import QueuePool
import structlog

from src.config.settings import get_settings

logger = structlog.get_logger(__name__)


class QueryType(Enum):
    """Query type classification for routing."""
    READ = "read"
    WRITE = "write"
    ANALYTICS = "analytics"


class DatabaseReplica:
    """Represents a database replica configuration."""
    
    def __init__(
        self,
        name: str,
        url: str,
        is_primary: bool = False,
        weight: int = 1,
        max_connections: int = 20,
        query_types: Optional[List[QueryType]] = None
    ):
        self.name = name
        self.url = url
        self.is_primary = is_primary
        self.weight = weight
        self.max_connections = max_connections
        self.query_types = query_types or [QueryType.READ, QueryType.WRITE]
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self.is_healthy = True
        self.connection_count = 0


class ReplicaManager:
    """Manages database replicas and routing logic."""
    
    def __init__(self):
        self.replicas: Dict[str, DatabaseReplica] = {}
        self.primary_replica: Optional[DatabaseReplica] = None
        self.read_replicas: List[DatabaseReplica] = []
        self.analytics_replicas: List[DatabaseReplica] = []
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize replica configuration from settings."""
        if self._initialized:
            return
        
        settings = get_settings()
        
        # Primary database (always handles writes)
        primary_replica = DatabaseReplica(
            name="primary",
            url=str(settings.database.url),
            is_primary=True,
            max_connections=settings.database.pool_size + settings.database.max_overflow,
            query_types=[QueryType.READ, QueryType.WRITE, QueryType.ANALYTICS]
        )
        
        self.add_replica(primary_replica)
        
        # Add read replicas if configured
        if hasattr(settings.database, 'read_replicas') and settings.database.read_replicas:
            for i, replica_url in enumerate(settings.database.read_replicas):
                read_replica = DatabaseReplica(
                    name=f"read_replica_{i+1}",
                    url=replica_url,
                    is_primary=False,
                    weight=1,
                    max_connections=settings.database.pool_size,
                    query_types=[QueryType.READ]
                )
                self.add_replica(read_replica)
        
        # Add analytics replica if configured
        if hasattr(settings.database, 'analytics_replica_url') and settings.database.analytics_replica_url:
            analytics_replica = DatabaseReplica(
                name="analytics",
                url=settings.database.analytics_replica_url,
                is_primary=False,
                weight=1,
                max_connections=10,  # Lower connection limit for analytics
                query_types=[QueryType.ANALYTICS, QueryType.READ]
            )
            self.add_replica(analytics_replica)
        
        self._initialized = True
        logger.info(
            "Replica manager initialized",
            total_replicas=len(self.replicas),
            read_replicas=len(self.read_replicas),
            analytics_replicas=len(self.analytics_replicas)
        )
    
    def add_replica(self, replica: DatabaseReplica) -> None:
        """Add a replica to the manager."""
        self.replicas[replica.name] = replica
        
        if replica.is_primary:
            self.primary_replica = replica
        
        if QueryType.READ in replica.query_types:
            self.read_replicas.append(replica)
        
        if QueryType.ANALYTICS in replica.query_types:
            self.analytics_replicas.append(replica)
        
        # Create engine for this replica
        self._create_replica_engine(replica)
    
    def _create_replica_engine(self, replica: DatabaseReplica) -> None:
        """Create SQLAlchemy engine for a replica."""
        settings = get_settings()
        
        engine_kwargs = {
            "url": replica.url,
            "echo": settings.database.echo,
            "poolclass": QueuePool,
            "pool_size": min(replica.max_connections // 2, 10),  # Conservative pool size
            "max_overflow": replica.max_connections // 2,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "pool_timeout": 30,
            "pool_reset_on_return": "commit",
            "connect_args": {
                "server_settings": {
                    "application_name": f"reagent-sydney-{replica.name}-{settings.environment}",
                    "timezone": "UTC",
                    "jit": "off",
                    "random_page_cost": "1.1",
                    "shared_preload_libraries": "timescaledb",
                },
                "options": "-c search_path=public,timescaledb_information"
            }
        }
        
        # Analytics replicas get special configuration
        if QueryType.ANALYTICS in replica.query_types and not replica.is_primary:
            engine_kwargs["connect_args"]["server_settings"].update({
                "work_mem": "256MB",  # More memory for analytics queries
                "maintenance_work_mem": "512MB",
                "random_page_cost": "1.0",  # Optimize for sequential scans
                "cpu_tuple_cost": "0.03",   # Adjust for analytics workload
                "default_statistics_target": "1000"  # Better query planning
            })
        
        replica.engine = create_async_engine(**engine_kwargs)
        replica.session_factory = async_sessionmaker(
            bind=replica.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
        
        logger.info(f"Created engine for replica: {replica.name}")
    
    def get_replica_for_query(
        self, 
        query_type: QueryType,
        prefer_replica: Optional[str] = None
    ) -> DatabaseReplica:
        """
        Get the best replica for a given query type.
        
        Args:
            query_type: Type of query to route
            prefer_replica: Preferred replica name (optional)
            
        Returns:
            DatabaseReplica: Selected replica
        """
        if not self._initialized:
            self.initialize()
        
        # Handle specific replica preference
        if prefer_replica and prefer_replica in self.replicas:
            replica = self.replicas[prefer_replica]
            if query_type in replica.query_types and replica.is_healthy:
                return replica
        
        # Route based on query type
        if query_type == QueryType.WRITE:
            # Writes always go to primary
            if self.primary_replica and self.primary_replica.is_healthy:
                return self.primary_replica
            raise RuntimeError("Primary database replica is not available")
        
        elif query_type == QueryType.ANALYTICS:
            # Analytics queries prefer dedicated analytics replicas
            healthy_analytics = [r for r in self.analytics_replicas if r.is_healthy]
            if healthy_analytics:
                return self._select_weighted_replica(healthy_analytics)
            
            # Fallback to read replicas
            healthy_reads = [r for r in self.read_replicas if r.is_healthy and not r.is_primary]
            if healthy_reads:
                return self._select_weighted_replica(healthy_reads)
        
        elif query_type == QueryType.READ:
            # Read queries use read replicas with load balancing
            healthy_reads = [r for r in self.read_replicas if r.is_healthy]
            if healthy_reads:
                return self._select_weighted_replica(healthy_reads)
        
        # Fallback to primary if no suitable replica found
        if self.primary_replica and self.primary_replica.is_healthy:
            logger.warning(
                f"Falling back to primary for {query_type.value} query",
                query_type=query_type.value
            )
            return self.primary_replica
        
        raise RuntimeError("No healthy database replicas available")
    
    def _select_weighted_replica(self, replicas: List[DatabaseReplica]) -> DatabaseReplica:
        """Select a replica using weighted random selection."""
        if not replicas:
            raise ValueError("No replicas provided for selection")
        
        if len(replicas) == 1:
            return replicas[0]
        
        # Simple weighted selection based on replica weight and current load
        weighted_replicas = []
        for replica in replicas:
            # Adjust weight based on current connection load
            load_factor = max(0.1, 1.0 - (replica.connection_count / replica.max_connections))
            effective_weight = replica.weight * load_factor
            weighted_replicas.extend([replica] * int(effective_weight * 10))
        
        return random.choice(weighted_replicas) if weighted_replicas else replicas[0]
    
    async def check_replica_health(self, replica: DatabaseReplica) -> bool:
        """Check if a replica is healthy and responsive."""
        try:
            if not replica.engine:
                return False
            
            async with replica.engine.begin() as conn:
                await conn.execute("SELECT 1")
                replica.is_healthy = True
                return True
        
        except Exception as e:
            replica.is_healthy = False
            logger.error(
                f"Replica health check failed: {replica.name}",
                error=str(e)
            )
            return False
    
    async def check_all_replicas_health(self) -> Dict[str, bool]:
        """Check health of all replicas."""
        health_status = {}
        
        for name, replica in self.replicas.items():
            health_status[name] = await self.check_replica_health(replica)
        
        return health_status
    
    async def get_session(
        self, 
        query_type: QueryType = QueryType.READ,
        prefer_replica: Optional[str] = None
    ) -> AsyncSession:
        """
        Get a database session for the specified query type.
        
        Args:
            query_type: Type of query to route
            prefer_replica: Preferred replica name
            
        Returns:
            AsyncSession: Database session
        """
        replica = self.get_replica_for_query(query_type, prefer_replica)
        
        if not replica.session_factory:
            raise RuntimeError(f"Session factory not initialized for replica: {replica.name}")
        
        # Track connection usage
        replica.connection_count += 1
        
        try:
            session = replica.session_factory()
            logger.debug(f"Created session for replica: {replica.name}")
            return session
        
        finally:
            # This will be decremented when session is closed
            # In practice, you'd want more sophisticated connection tracking
            pass
    
    async def close_all_connections(self) -> None:
        """Close all replica connections."""
        for replica in self.replicas.values():
            if replica.engine:
                await replica.engine.dispose()
                logger.info(f"Closed connections for replica: {replica.name}")


# Global replica manager instance
replica_manager = ReplicaManager()


def get_replica_manager() -> ReplicaManager:
    """Get the global replica manager instance."""
    return replica_manager


async def get_read_session() -> AsyncSession:
    """Get a session optimized for read queries."""
    return await replica_manager.get_session(QueryType.READ)


async def get_write_session() -> AsyncSession:
    """Get a session for write queries (always uses primary)."""
    return await replica_manager.get_session(QueryType.WRITE)


async def get_analytics_session() -> AsyncSession:
    """Get a session optimized for analytics queries."""
    return await replica_manager.get_session(QueryType.ANALYTICS)