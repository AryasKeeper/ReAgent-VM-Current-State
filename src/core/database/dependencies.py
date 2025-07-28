"""
Database Dependencies for FastAPI

Provides dependency injection for database sessions and transactions.
Includes context managers for different transaction patterns.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from .engine import get_db_session

logger = structlog.get_logger(__name__)


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with get_db_session() as session:
        try:
            yield session
        except Exception as e:
            logger.error("Database session error in dependency", error=str(e))
            raise


@asynccontextmanager
async def database_transaction() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database transactions with automatic rollback on error.
    
    Yields:
        AsyncSession: Database session within transaction
    """
    async with get_db_session() as session:
        async with session.begin():
            try:
                yield session
            except Exception as e:
                logger.error("Transaction error, rolling back", error=str(e))
                raise


@asynccontextmanager
async def read_only_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for read-only database operations.
    
    Yields:
        AsyncSession: Read-only database session
    """
    async with get_db_session() as session:
        # Set session to read-only mode
        await session.execute("SET TRANSACTION READ ONLY")
        try:
            yield session
        finally:
            # Sessions are automatically closed by get_db_session
            pass


# Convenience dependency aliases
DatabaseSession = Depends(get_database_session)