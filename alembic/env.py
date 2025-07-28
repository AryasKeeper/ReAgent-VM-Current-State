"""
ReAgent Sydney - Alembic Environment Configuration

This module configures Alembic for database migrations with TimescaleDB support.
"""

import logging
from logging.config import fileConfig
from pathlib import Path
import sys
import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the project root to sys.path so we can import our models
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import all models so Alembic can detect them
from src.data.models.base import Base
from src.data.models.property_models import *
from src.data.models.buyer_models import *
from src.data.models.market_models import *
from src.data.models.agent_models import *

# Import settings for database configuration
try:
    from src.config.settings import get_settings
    settings = get_settings()
except ImportError:
    # Fallback if settings not available
    settings = None

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set up logging
logger = logging.getLogger('alembic.env')

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_database_url():
    """Get database URL from settings or config file."""
    if settings and hasattr(settings, 'database_url'):
        return settings.database_url
    
    # Fallback to environment variable
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url
    
    # Fallback to config file
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Override the sqlalchemy.url with our dynamic URL
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_database_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
            # TimescaleDB specific configuration
            render_as_batch=False,  # TimescaleDB doesn't need batch mode
        )

        with context.begin_transaction():
            # Check if we're working with TimescaleDB
            result = connection.execute("SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'")
            has_timescaledb = result.scalar() > 0
            
            if has_timescaledb:
                logger.info("TimescaleDB detected - running migrations with time-series support")
                
                # Run the main migrations
                context.run_migrations()
                
                # After migrations, set up TimescaleDB features
                logger.info("Setting up TimescaleDB hypertables...")
                try:
                    connection.execute("SELECT setup_timescale_hypertables();")
                    logger.info("✅ TimescaleDB hypertables configured")
                except Exception as e:
                    logger.warning(f"TimescaleDB hypertable setup skipped: {e}")
                
                logger.info("Setting up performance indexes...")
                try:
                    connection.execute("SELECT create_performance_indexes();")
                    logger.info("✅ Performance indexes created")
                except Exception as e:
                    logger.warning(f"Performance index creation skipped: {e}")
                
                logger.info("Setting up continuous aggregates...")
                try:
                    connection.execute("SELECT create_continuous_aggregates();")
                    logger.info("✅ Continuous aggregates configured")
                except Exception as e:
                    logger.warning(f"Continuous aggregate setup skipped: {e}")
                    
            else:
                logger.info("Standard PostgreSQL detected - running basic migrations")
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()