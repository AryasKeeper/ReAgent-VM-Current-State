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
import structlog

from src.config.settings import get_settings
from src.data.models.base import Base

logger = structlog.get_logger(__name__)

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
        "pool_pre_ping": True,
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "pool_timeout": 30,     # Timeout when getting connection from pool
        "pool_reset_on_return": "commit",  # Reset connections on return
        "connect_args": {
            "server_settings": {
                "application_name": f"reagent-sydney-{settings.environment}",
                "timezone": "UTC",
                "jit": "off",  # Disable JIT for consistent performance
                "random_page_cost": "1.1",  # Optimize for SSD storage
                "effective_cache_size": "4GB",  # Adjust based on available memory
                "shared_preload_libraries": "timescaledb",
                "max_connections": "100",
                "work_mem": "16MB"
            },
            "options": "-c search_path=public,timescaledb_information"
        }
    }
    
    async_engine = create_async_engine(**engine_kwargs)
    
    # Add event listeners for connection management
    @event.listens_for(async_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set database-specific pragmas on connection."""
        # Enable TimescaleDB extension if not already enabled
        if "postgresql" in str(settings.database.url):
            try:
                with dbapi_connection.cursor() as cursor:
                    # Enable TimescaleDB extension
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
                    # Set optimal settings for time-series data
                    cursor.execute("SET timezone = 'UTC';")
                    cursor.execute("SET statement_timeout = '300s';")
                    cursor.execute("SET lock_timeout = '30s';")
            except Exception as e:
                logger.warning("Failed to set database pragmas", error=str(e))
    
    @event.listens_for(async_engine.sync_engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Log when connection is checked out from pool."""
        logger.debug("Database connection checked out from pool")
    
    @event.listens_for(async_engine.sync_engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """Log when connection is checked back into pool."""
        logger.debug("Database connection checked back into pool")
    
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
    Create TimescaleDB hypertables for time-series data.
    
    Args:
        conn: Database connection
    """
    hypertables = [
        {
            "table": "property_price_history",
            "time_column": "created_at",
            "chunk_time_interval": "INTERVAL '1 month'"
        },
        {
            "table": "property_market_metrics",
            "time_column": "created_at", 
            "chunk_time_interval": "INTERVAL '1 day'"
        },
        {
            "table": "market_trends",
            "time_column": "period_end",
            "chunk_time_interval": "INTERVAL '1 month'"
        },
        {
            "table": "price_changes",
            "time_column": "created_at",
            "chunk_time_interval": "INTERVAL '1 week'"
        },
        {
            "table": "agent_logs",
            "time_column": "created_at",
            "chunk_time_interval": "INTERVAL '1 day'"
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
                # Create hypertable
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
                "invalid": pool.invalid()
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