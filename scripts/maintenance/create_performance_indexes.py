#!/usr/bin/env python3
"""
Performance Index Creation Script

Creates optimized database indexes for ReAgent Sydney to support
50+ concurrent users with sub-2s response times.
"""

import asyncio
import logging
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.core.database import get_engine, get_db_session
from src.config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Performance indexes categorized by agent/functionality
PERFORMANCE_INDEXES = [
    # Listing Watcher indexes
    {
        "name": "idx_properties_domain_listing_id",
        "table": "properties",
        "columns": ["domain_listing_id"],
        "type": "btree",
        "unique": True,
        "description": "Fast lookup for Domain API property matching"
    },
    {
        "name": "idx_properties_suburb_status_updated",
        "table": "properties", 
        "columns": ["suburb_id", "status", "updated_at DESC"],
        "type": "btree",
        "description": "Listing Watcher delta detection by suburb"
    },
    {
        "name": "idx_properties_price_updated_at",
        "table": "properties",
        "columns": ["price", "updated_at DESC"],
        "type": "btree", 
        "description": "Price change monitoring"
    },
    
    # Buyer Matchmaker indexes
    {
        "name": "idx_buyer_profiles_preferences_gin",
        "table": "buyer_profiles",
        "columns": ["preferences"],
        "type": "gin",
        "description": "Fast JSON preference matching for buyer profiles"
    },
    {
        "name": "idx_properties_features_gin", 
        "table": "properties",
        "columns": ["features"],
        "type": "gin",
        "description": "Property feature matching for buyer preferences"
    },
    {
        "name": "idx_buyer_profiles_budget_range",
        "table": "buyer_profiles",
        "columns": ["min_price", "max_price"],
        "type": "btree",
        "description": "Budget range filtering for property matching"
    },
    
    # Suburb Signal indexes
    {
        "name": "idx_market_trends_suburb_period",
        "table": "market_trends", 
        "columns": ["suburb_id", "period_start", "period_end"],
        "type": "btree",
        "description": "Suburb trend analysis by time period"
    },
    {
        "name": "idx_price_changes_suburb_created_at",
        "table": "price_changes",
        "columns": ["suburb_id", "created_at DESC"],
        "type": "btree",
        "description": "Recent price changes by suburb"
    },
    
    # Seller Strategy indexes
    {
        "name": "idx_comparable_sales_suburb_sold_date",
        "table": "comparable_sales",
        "columns": ["suburb_id", "sold_date DESC"],
        "type": "btree", 
        "description": "Recent comparable sales for pricing analysis"
    },
    {
        "name": "idx_properties_bedrooms_bathrooms_parking",
        "table": "properties",
        "columns": ["bedrooms", "bathrooms", "parking_spaces"],
        "type": "btree",
        "description": "Property feature comparison for valuation"
    },
    
    # Off-Market Radar indexes
    {
        "name": "idx_off_market_opportunities_suburb_score",
        "table": "off_market_opportunities", 
        "columns": ["suburb_id", "opportunity_score DESC"],
        "type": "btree",
        "description": "High-scoring opportunities by suburb"
    },
    {
        "name": "idx_council_da_applications_suburb_status",
        "table": "council_da_applications",
        "columns": ["suburb_id", "status", "lodged_date DESC"],
        "type": "btree",
        "description": "Development application tracking"
    },
    
    # Agent Whisperer indexes
    {
        "name": "idx_agent_logs_session_created_at",
        "table": "agent_logs",
        "columns": ["session_id", "created_at DESC"],
        "type": "btree",
        "description": "Chat session message history"
    },
    {
        "name": "idx_agent_execution_logs_agent_type_status",
        "table": "agent_execution_logs",
        "columns": ["agent_type", "status", "created_at DESC"],
        "type": "btree",
        "description": "Agent performance monitoring"
    },
    
    # Time-series performance indexes (TimescaleDB optimized)
    {
        "name": "idx_property_price_history_property_time",
        "table": "property_price_history",
        "columns": ["property_id", "created_at DESC"],
        "type": "btree", 
        "description": "Property price history lookup"
    },
    {
        "name": "idx_property_market_metrics_suburb_time",
        "table": "property_market_metrics",
        "columns": ["suburb_id", "created_at DESC"],
        "type": "btree",
        "description": "Market metrics time-series queries"
    },
    
    # Full-text search indexes
    {
        "name": "idx_properties_address_fts",
        "table": "properties",
        "columns": ["to_tsvector('english', address)"],
        "type": "gin",
        "description": "Full-text search on property addresses"
    },
    {
        "name": "idx_suburbs_name_fts",
        "table": "suburbs", 
        "columns": ["to_tsvector('english', name)"],
        "type": "gin",
        "description": "Full-text search on suburb names"
    },
    
    # Geospatial indexes (if using PostGIS)
    {
        "name": "idx_properties_location_gist",
        "table": "properties",
        "columns": ["location"],
        "type": "gist",
        "description": "Geospatial queries for property location",
        "conditional": "WHERE location IS NOT NULL"
    },
    
    # Multi-column covering indexes for hot queries
    {
        "name": "idx_properties_covering_listing_search",
        "table": "properties",
        "columns": ["suburb_id", "property_type", "status", "price", "bedrooms", "bathrooms"],
        "type": "btree",
        "description": "Covering index for common property search queries"
    },
    {
        "name": "idx_buyer_profiles_covering_matching", 
        "table": "buyer_profiles",
        "columns": ["status", "min_price", "max_price", "preferred_suburbs", "property_types"],
        "type": "btree",
        "description": "Covering index for buyer matching queries"
    }
]


async def create_index(engine: AsyncEngine, index_config: Dict) -> bool:
    """
    Create a single database index.
    
    Args:
        engine: Database engine
        index_config: Index configuration dictionary
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        async with engine.begin() as conn:
            # Check if index already exists
            check_query = text("""
                SELECT COUNT(*) FROM pg_indexes 
                WHERE indexname = :index_name
            """)
            
            result = await conn.execute(check_query, {"index_name": index_config["name"]})
            if result.scalar() > 0:
                logger.info(f"Index {index_config['name']} already exists, skipping")
                return True
            
            # Build CREATE INDEX statement
            columns_str = ", ".join(index_config["columns"])
            index_type = index_config.get("type", "btree").upper()
            
            # Handle different index types
            if index_type == "GIN":
                create_sql = f"""
                    CREATE INDEX CONCURRENTLY {index_config["name"]} 
                    ON {index_config["table"]} 
                    USING gin ({columns_str})
                """
            elif index_type == "GIST":
                create_sql = f"""
                    CREATE INDEX CONCURRENTLY {index_config["name"]} 
                    ON {index_config["table"]} 
                    USING gist ({columns_str})
                """
            else:  # BTREE (default)
                unique_clause = "UNIQUE " if index_config.get("unique", False) else ""
                create_sql = f"""
                    CREATE {unique_clause}INDEX CONCURRENTLY {index_config["name"]} 
                    ON {index_config["table"]} ({columns_str})
                """
            
            # Add conditional clause if specified
            if "conditional" in index_config:
                create_sql += f" {index_config['conditional']}"
            
            # Execute index creation
            await conn.execute(text(create_sql))
            await conn.commit()
            
            logger.info(
                f"Created index: {index_config['name']} on {index_config['table']} "
                f"({index_config.get('description', 'No description')})"
            )
            return True
            
    except Exception as e:
        logger.error(f"Failed to create index {index_config['name']}: {str(e)}")
        return False


async def analyze_table_statistics(engine: AsyncEngine, tables: List[str]) -> None:
    """
    Update table statistics for better query planning.
    
    Args:
        engine: Database engine
        tables: List of table names to analyze
    """
    try:
        async with engine.begin() as conn:
            for table in tables:
                analyze_query = text(f"ANALYZE {table}")
                await conn.execute(analyze_query)
                logger.info(f"Updated statistics for table: {table}")
                
    except Exception as e:
        logger.error(f"Failed to analyze table statistics: {str(e)}")


async def create_performance_indexes() -> None:
    """Create all performance indexes for ReAgent Sydney."""
    logger.info("Starting performance index creation...")
    
    engine = get_engine()
    successful_indexes = 0
    total_indexes = len(PERFORMANCE_INDEXES)
    
    # Create indexes
    for index_config in PERFORMANCE_INDEXES:
        if await create_index(engine, index_config):
            successful_indexes += 1
        
        # Small delay to prevent overwhelming the database
        await asyncio.sleep(0.1)
    
    # Update table statistics
    unique_tables = list(set(idx["table"] for idx in PERFORMANCE_INDEXES))
    await analyze_table_statistics(engine, unique_tables)
    
    logger.info(
        f"Performance index creation completed: {successful_indexes}/{total_indexes} successful"
    )
    
    # Generate index creation report
    await generate_index_report(engine)


async def generate_index_report(engine: AsyncEngine) -> None:
    """Generate a report of created indexes and their sizes."""
    try:
        async with engine.begin() as conn:
            # Get index information
            index_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    idx_scan as times_used,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes 
                WHERE indexname LIKE 'idx_%'
                ORDER BY pg_relation_size(indexrelid) DESC
            """)
            
            result = await conn.execute(index_query)
            indexes = result.fetchall()
            
            logger.info("=== Performance Index Report ===")
            for idx in indexes:
                logger.info(
                    f"Index: {idx.indexname} | Table: {idx.tablename} | "
                    f"Size: {idx.index_size} | Used: {idx.times_used} times"
                )
            
            # Get total index size
            total_size_query = text("""
                SELECT pg_size_pretty(
                    SUM(pg_relation_size(indexrelid))
                ) as total_index_size
                FROM pg_stat_user_indexes 
                WHERE indexname LIKE 'idx_%'
            """)
            
            total_result = await conn.execute(total_size_query)
            total_size = total_result.scalar()
            logger.info(f"Total performance index size: {total_size}")
            
    except Exception as e:
        logger.error(f"Failed to generate index report: {str(e)}")


if __name__ == "__main__":
    asyncio.run(create_performance_indexes())