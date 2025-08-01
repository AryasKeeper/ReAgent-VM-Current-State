"""
Database Engine Configuration

Provides async database engine and session management for PostgreSQL + TimescaleDB.
Includes connection pooling, health checks, and migration support.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.pool import QueuePool

from reagent.core.config import get_settings
from reagent.data.models.base import Base
from reagent.utils.logging import get_logger

logger = get_logger(__name__)

# Global engine instance
engine: Optional[AsyncEngine] = None
SessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def create_database_engine() -> AsyncEngine:
    """
    Create and configure the async database engine.
    
    Returns:
        AsyncEngine: Configured SQLAlchemy async engine
    """
    settings = get_settings()
    
    engine_kwargs = {
        "url": str(settings.database.url),
        "echo": settings.database.echo,
        "poolclass": QueuePool,
        "pool_size": settings.database.pool_size,
        "max_overflow": settings.database.max_overflow,
        "pool_pre_ping": settings.database.pool_pre_ping,
        "pool_recycle": settings.database.pool_recycle,
        "pool_timeout": settings.database.pool_timeout,
        "pool_reset_on_return": "commit",
        # Performance optimizations for concurrent load
        "isolation_level": "READ_COMMITTED",
        "connect_args": {
            "server_settings": {
                "application_name": f"reagent-sydney-{settings.environment}",
                "timezone": "UTC",
                "jit": "off",  # Disable JIT for consistent performance
                "random_page_cost": "1.1",  # Optimize for SSD storage
                "effective_cache_size": "4GB",
                "shared_preload_libraries": "timescaledb,pg_stat_statements",
                "max_connections": "200",  # Increased for concurrent load
                "work_mem": "32MB",  # Increased for better query performance
                "maintenance_work_mem": "256MB",
                "shared_buffers": "512MB",
                "wal_buffers": "16MB",
                "checkpoint_completion_target": "0.9",
                "statement_timeout": f"{settings.database.statement_timeout}s",
                "lock_timeout": f"{settings.database.lock_timeout}s",
                # TimescaleDB specific optimizations
                "timescaledb.max_background_workers": "8",
                "max_parallel_workers_per_gather": "4",
                "max_parallel_workers": "8"
            },
            "options": "-c search_path=public,timescaledb_information",
            "command_timeout": 60,
            "prepared_statement_cache_size": 100
        }
    }
    
    async_engine = create_async_engine(**engine_kwargs)
    
    # Add event listeners for connection management
    @event.listens_for(async_engine.sync_engine, "connect")
    def set_database_optimizations(dbapi_connection, connection_record):
        """Set database-specific optimizations on connection."""
        if "postgresql" in str(settings.database.url):
            try:
                with dbapi_connection.cursor() as cursor:
                    # Enable required extensions
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements CASCADE;")
                    
                    # Performance optimizations for concurrent workload
                    cursor.execute("SET timezone = 'UTC';")
                    cursor.execute(f"SET statement_timeout = '{settings.database.statement_timeout}s';")
                    cursor.execute(f"SET lock_timeout = '{settings.database.lock_timeout}s';")
                    cursor.execute("SET synchronous_commit = 'off';")  # Better write performance
                    cursor.execute("SET commit_delay = 10000;")  # Batch commits for better throughput
                    cursor.execute("SET commit_siblings = 5;")  # Commit batching threshold
                    cursor.execute("SET log_min_duration_statement = 1000;")  # Log slow queries
                    
                    # Connection-specific optimizations
                    cursor.execute("SET tcp_keepalives_idle = 600;")  # Keep connections alive
                    cursor.execute("SET tcp_keepalives_interval = 30;")
                    cursor.execute("SET tcp_keepalives_count = 3;")
                    
            except Exception as e:
                logger.warning("Failed to set database optimizations", error=str(e))
    
    # Connection pool monitoring and metrics
    @event.listens_for(async_engine.sync_engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Monitor connection checkout with metrics."""
        pool_status = async_engine.pool.status()
        logger.debug(
            "Database connection checked out",
            pool_size=async_engine.pool.size(),
            checked_out=async_engine.pool.checkedout(),
            overflow=async_engine.pool.overflow(),
            checked_in=async_engine.pool.checkedin()
        )
    
    @event.listens_for(async_engine.sync_engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """Monitor connection checkin."""
        logger.debug(
            "Database connection checked in",
            checked_out=async_engine.pool.checkedout(),
            available=async_engine.pool.checkedin()
        )
    
    @event.listens_for(async_engine.sync_engine, "invalidate")
    def receive_invalidate(dbapi_connection, connection_record, exception):
        """Handle connection invalidation."""
        logger.warning(
            "Database connection invalidated",
            error=str(exception) if exception else "Unknown"
        )
    
    logger.info(
        "Database engine created",
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        echo=settings.database.echo
    )
    
    return async_engine


def get_session_local() -> async_sessionmaker[AsyncSession]:
    """
    Get the session local factory.
    
    Returns:
        async_sessionmaker: Session factory
    """
    global SessionLocal
    if SessionLocal is None:
        engine = get_engine()
        SessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
    return SessionLocal


def get_engine() -> AsyncEngine:
    """
    Get the global database engine instance.
    
    Returns:
        AsyncEngine: Database engine
    """
    global engine
    if engine is None:
        engine = create_database_engine()
    return engine


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session with automatic cleanup.
    
    Yields:
        AsyncSession: Database session
    """
    session_factory = get_session_local()
    async with session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error, rolling back", error=str(e))
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize the database by creating all tables.
    This should be called during application startup.
    """
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Create TimescaleDB hypertables for time-series data
        await _create_hypertables(conn)
        
        logger.info("Database initialized successfully")


async def _create_hypertables(conn) -> None:
    """
    Create TimescaleDB hypertables for time-series data with performance optimizations.
    
    Args:
        conn: Database connection
    """
    hypertables = [
        {
            "table": "property_price_history",
            "time_column": "created_at",
            "chunk_time_interval": "INTERVAL '1 month'",
            "compression": True,
            "compression_interval": "INTERVAL '3 months'"
        },
        {
            "table": "property_market_metrics",
            "time_column": "created_at", 
            "chunk_time_interval": "INTERVAL '1 day'",
            "compression": True,
            "compression_interval": "INTERVAL '7 days'"
        },
        {
            "table": "market_trends",
            "time_column": "period_end",
            "chunk_time_interval": "INTERVAL '1 month'",
            "compression": True,
            "compression_interval": "INTERVAL '6 months'"
        },
        {
            "table": "price_changes",
            "time_column": "created_at",
            "chunk_time_interval": "INTERVAL '1 week'",
            "compression": True,
            "compression_interval": "INTERVAL '1 month'"
        },
        {
            "table": "agent_logs",
            "time_column": "created_at",
            "chunk_time_interval": "INTERVAL '1 day'",
            "compression": True,
            "compression_interval": "INTERVAL '7 days'"
        }
    ]
    
    for hypertable in hypertables:
        try:
            # Check if table exists as hypertable already
            check_query = text("""
                SELECT COUNT(*) FROM timescaledb_information.hypertables 
                WHERE hypertable_name = :table_name
            """)
            
            result = await conn.execute(check_query, {"table_name": hypertable["table"]})
            count = result.scalar()
            
            if count == 0:
                # Create hypertable with performance optimizations
                create_query = text(f"""
                    SELECT create_hypertable(
                        '{hypertable["table"]}', 
                        '{hypertable["time_column"]}',
                        chunk_time_interval => {hypertable["chunk_time_interval"]},
                        if_not_exists => TRUE
                    )
                """)
                
                await conn.execute(create_query)
                logger.info(f"Created hypertable for {hypertable['table']}")
                
                # Enable compression if specified
                if hypertable.get("compression", False):
                    compression_query = text(f"""
                        ALTER TABLE {hypertable["table"]} SET (
                            timescaledb.compress,
                            timescaledb.compress_segmentby = 'property_id',
                            timescaledb.compress_orderby = '{hypertable["time_column"]} DESC'
                        )
                    """)
                    
                    await conn.execute(compression_query)
                    
                    # Add compression policy
                    if "compression_interval" in hypertable:
                        policy_query = text(f"""
                            SELECT add_compression_policy(
                                '{hypertable["table"]}',
                                {hypertable["compression_interval"]}
                            )
                        """)
                        await conn.execute(policy_query)
                        logger.info(f"Added compression policy for {hypertable['table']}")
            else:
                logger.debug(f"Hypertable {hypertable['table']} already exists")
                
        except Exception as e:
            logger.warning(
                f"Failed to create hypertable for {hypertable['table']}",
                error=str(e)
            )


async def check_db_health() -> dict:
    """
    Check database health and connection status.
    
    Returns:
        dict: Health check results
    """
    health_status = {
        "database": "unknown",
        "connection_pool": "unknown", 
        "timescale_extension": "unknown",
        "response_time_ms": None,
        "active_connections": None,
        "details": {}
    }
    
    try:
        engine = get_engine()
        start_time = asyncio.get_event_loop().time()
        
        async with engine.begin() as conn:
            # Basic connectivity test
            await conn.execute(text("SELECT 1"))
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            health_status["response_time_ms"] = round(response_time, 2)
            health_status["database"] = "healthy"
            
            # Check TimescaleDB extension
            try:
                result = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'"))
                if result.scalar():
                    health_status["timescale_extension"] = "available"
                else:
                    health_status["timescale_extension"] = "not_installed"
            except Exception as e:
                health_status["timescale_extension"] = f"error: {str(e)}"
            
            # Get connection pool status
            pool = engine.pool
            health_status["connection_pool"] = "healthy"
            health_status["active_connections"] = pool.checkedout()
            health_status["details"] = {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
                "pool_usage_percent": round((pool.checkedout() / (pool.size() + pool.overflow())) * 100, 2),
                "connection_efficiency": round(pool.checkedin() / max(1, pool.size()) * 100, 2)
            }
            
    except Exception as e:
        health_status["database"] = "unhealthy"
        health_status["details"]["error"] = str(e)
        logger.error("Database health check failed", error=str(e))
    
    return health_status


async def close_db() -> None:
    """
    Close database connections and cleanup resources.
    Should be called during application shutdown.
    """
    global engine, SessionLocal
    
    if engine:
        await engine.dispose()
        engine = None
        logger.info("Database engine disposed")
    
    SessionLocal = None
    logger.info("Database connections closed")