"""
Database Infrastructure

PostgreSQL + TimescaleDB database setup, session management,
and migration utilities. Provides async database connections and ORM setup.
"""

from .engine import get_db_session, get_engine, get_session_local, check_db_health, init_db, close_db
from .replicas import ReplicaManager, get_replica_manager
from .dependencies import get_database_session, database_transaction, read_only_session

# For backwards compatibility
DatabaseManager = ReplicaManager
init_database = init_db
close_database = close_db

# create_tables is actually handled by init_db
async def create_tables():
    """Create database tables - wrapper for init_db."""
    await init_db()

__all__ = [
    "get_db_session",
    "get_engine", 
    "get_session_local",
    "check_db_health",
    "init_db",
    "close_db",
    "ReplicaManager",
    "get_replica_manager",
    "DatabaseManager",  # Alias for backwards compatibility
    "init_database",  # Alias for init_db
    "close_database",  # Alias for close_db
    "create_tables",
    "get_database_session",
    "database_transaction",
    "read_only_session"
]