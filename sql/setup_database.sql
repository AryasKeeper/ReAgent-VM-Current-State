-- ReAgent Sydney - Complete Database Setup Script
-- This script sets up the entire database from scratch with TimescaleDB optimization
-- 
-- Usage:
--   psql -d reagent_sydney_dev -f sql/setup_database.sql
--
-- Requirements:
--   - PostgreSQL 13+
--   - TimescaleDB extension
--   - PostGIS extension (for geo features)

\echo '==================================================================='
\echo 'ReAgent Sydney - Database Setup Starting'
\echo '==================================================================='

-- Set client configuration for better output
\set ON_ERROR_STOP on
\set ECHO all

-- =================================================================
-- STEP 1: Extensions and Types
-- =================================================================
\echo ''
\echo '>>> STEP 1: Creating extensions and custom types...'

\i sql/init/01_create_extensions.sql
\echo '✅ Extensions and types created'

-- =================================================================
-- STEP 2: Create All Tables
-- =================================================================
\echo ''
\echo '>>> STEP 2: Creating database tables...'

\i sql/init/04_create_tables.sql
\echo '✅ All tables created'

-- =================================================================
-- STEP 3: Convert to TimescaleDB Hypertables
-- =================================================================
\echo ''
\echo '>>> STEP 3: Setting up TimescaleDB hypertables...'

-- Execute the hypertable setup function
SELECT setup_timescale_hypertables();
\echo '✅ TimescaleDB hypertables configured'

-- =================================================================
-- STEP 4: Create Performance Indexes
-- =================================================================
\echo ''
\echo '>>> STEP 4: Creating performance indexes...'

-- Execute the index creation function
SELECT create_performance_indexes();
\echo '✅ Performance indexes created'

-- =================================================================
-- STEP 5: Set up Continuous Aggregates
-- =================================================================
\echo ''
\echo '>>> STEP 5: Setting up continuous aggregates...'

-- Execute the continuous aggregates function
SELECT create_continuous_aggregates();
\echo '✅ Continuous aggregates configured'

-- =================================================================
-- STEP 6: Create Additional Database Objects
-- =================================================================
\echo ''
\echo '>>> STEP 6: Creating additional database objects...'

-- Create a view for active property listings with computed metrics
CREATE OR REPLACE VIEW active_properties_enriched AS
SELECT 
    p.*,
    -- Price per square meter calculations
    CASE 
        WHEN p.building_size_sqm > 0 AND p.price_guide > 0 
        THEN ROUND(p.price_guide / p.building_size_sqm, 2)
    END as price_per_sqm_building,
    
    CASE 
        WHEN p.land_size_sqm > 0 AND p.price_guide > 0 
        THEN ROUND(p.price_guide / p.land_size_sqm, 2)
    END as price_per_sqm_land,
    
    -- Days on market calculation
    CASE 
        WHEN p.listing_date IS NOT NULL 
        THEN EXTRACT(days FROM NOW() - p.listing_date)::INTEGER
    END as days_on_market,
    
    -- Full address concatenation
    CONCAT_WS(', ', 
        p.address_line_1, 
        NULLIF(p.address_line_2, ''), 
        p.suburb, 
        p.state, 
        p.postcode
    ) as full_address,
    
    -- Price range categorization
    CASE 
        WHEN p.price_guide < 1000000 THEN 'Budget'
        WHEN p.price_guide < 2000000 THEN 'Mid-Range'
        WHEN p.price_guide < 5000000 THEN 'Premium'
        ELSE 'Luxury'
    END as price_category

FROM properties p
WHERE p.status = 'active' 
  AND p.deleted_at IS NULL;

-- Create helper functions for common operations
CREATE OR REPLACE FUNCTION get_suburb_price_stats(
    p_suburb VARCHAR(100),
    p_postcode VARCHAR(10) DEFAULT NULL,
    p_days_back INTEGER DEFAULT 30
)
RETURNS TABLE(
    suburb VARCHAR(100),
    postcode VARCHAR(10),
    property_count BIGINT,
    avg_price DECIMAL(12,2),
    median_price DECIMAL(12,2),
    min_price DECIMAL(12,2),
    max_price DECIMAL(12,2),
    avg_days_on_market DECIMAL(8,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.suburb,
        p.postcode,
        COUNT(*) as property_count,
        AVG(p.price_guide) as avg_price,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.price_guide) as median_price,
        MIN(p.price_guide) as min_price,
        MAX(p.price_guide) as max_price,
        AVG(EXTRACT(days FROM NOW() - p.listing_date)) as avg_days_on_market
    FROM properties p
    WHERE p.suburb = p_suburb
      AND (p_postcode IS NULL OR p.postcode = p_postcode)
      AND p.price_guide IS NOT NULL
      AND p.listing_date >= NOW() - (p_days_back || ' days')::INTERVAL
      AND p.deleted_at IS NULL
    GROUP BY p.suburb, p.postcode;
END;
$$ LANGUAGE plpgsql;

-- Create function to find similar properties
CREATE OR REPLACE FUNCTION find_similar_properties(
    p_property_id UUID,
    p_radius_km INTEGER DEFAULT 5,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE(
    property_id UUID,
    similarity_score DECIMAL(5,3),
    price_difference DECIMAL(12,2),
    distance_km DECIMAL(8,2)
) AS $$
DECLARE
    base_property RECORD;
BEGIN
    -- Get the base property details
    SELECT * INTO base_property 
    FROM properties 
    WHERE id = p_property_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Property with ID % not found', p_property_id;
    END IF;
    
    RETURN QUERY
    SELECT 
        p.id as property_id,
        -- Similarity scoring (higher = more similar)
        (
            -- Property type match (40% weight)
            CASE WHEN p.property_type = base_property.property_type THEN 0.4 ELSE 0.0 END +
            -- Bedroom similarity (20% weight)
            CASE 
                WHEN ABS(COALESCE(p.bedrooms, 0) - COALESCE(base_property.bedrooms, 0)) = 0 THEN 0.2
                WHEN ABS(COALESCE(p.bedrooms, 0) - COALESCE(base_property.bedrooms, 0)) = 1 THEN 0.1
                ELSE 0.0 
            END +
            -- Bathroom similarity (15% weight)
            CASE 
                WHEN ABS(COALESCE(p.bathrooms, 0) - COALESCE(base_property.bathrooms, 0)) = 0 THEN 0.15
                WHEN ABS(COALESCE(p.bathrooms, 0) - COALESCE(base_property.bathrooms, 0)) = 1 THEN 0.075
                ELSE 0.0 
            END +
            -- Price similarity (25% weight)
            CASE 
                WHEN p.price_guide IS NOT NULL AND base_property.price_guide IS NOT NULL THEN
                    GREATEST(0, 0.25 - (ABS(p.price_guide - base_property.price_guide) / GREATEST(p.price_guide, base_property.price_guide) * 0.25))
                ELSE 0.0
            END
        ) as similarity_score,
        
        -- Price difference
        CASE 
            WHEN p.price_guide IS NOT NULL AND base_property.price_guide IS NOT NULL 
            THEN p.price_guide - base_property.price_guide
            ELSE NULL
        END as price_difference,
        
        -- Distance calculation (if coordinates available)
        CASE 
            WHEN p.latitude IS NOT NULL AND p.longitude IS NOT NULL 
                 AND base_property.latitude IS NOT NULL AND base_property.longitude IS NOT NULL
            THEN earth_distance(
                ll_to_earth(p.latitude::float8, p.longitude::float8),
                ll_to_earth(base_property.latitude::float8, base_property.longitude::float8)
            ) / 1000.0  -- Convert to kilometers
            ELSE NULL
        END as distance_km
        
    FROM properties p
    WHERE p.id != p_property_id
      AND p.suburb = base_property.suburb
      AND p.status = 'active'
      AND p.deleted_at IS NULL
      AND (
          -- If coordinates available, filter by radius
          (p.latitude IS NOT NULL AND p.longitude IS NOT NULL 
           AND base_property.latitude IS NOT NULL AND base_property.longitude IS NOT NULL
           AND earth_distance(
               ll_to_earth(p.latitude::float8, p.longitude::float8),
               ll_to_earth(base_property.latitude::float8, base_property.longitude::float8)
           ) <= p_radius_km * 1000)
          OR
          -- If no coordinates, fall back to suburb matching
          (p.latitude IS NULL OR p.longitude IS NULL 
           OR base_property.latitude IS NULL OR base_property.longitude IS NULL)
      )
    ORDER BY similarity_score DESC, distance_km ASC NULLS LAST
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Create function to update property market metrics
CREATE OR REPLACE FUNCTION update_property_market_metrics(p_property_id UUID)
RETURNS VOID AS $$
DECLARE
    property_rec RECORD;
    similar_count INTEGER;
    similar_avg_price DECIMAL(12,2);
    suburb_rank INTEGER;
BEGIN
    -- Get property details
    SELECT * INTO property_rec FROM properties WHERE id = p_property_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Property with ID % not found', p_property_id;
    END IF;
    
    -- Calculate similar properties metrics
    SELECT 
        COUNT(*),
        AVG(price_guide)
    INTO similar_count, similar_avg_price
    FROM find_similar_properties(p_property_id, 5, 100);
    
    -- Calculate suburb ranking
    SELECT ranking INTO suburb_rank
    FROM (
        SELECT id, 
               ROW_NUMBER() OVER (ORDER BY price_guide DESC) as ranking
        FROM properties 
        WHERE suburb = property_rec.suburb 
          AND status = 'active' 
          AND price_guide IS NOT NULL
    ) ranked
    WHERE id = p_property_id;
    
    -- Insert or update market metrics
    INSERT INTO property_market_metrics (
        property_id,
        calculated_at,
        suburb_rank,
        similar_properties_count,
        avg_similar_price,
        days_on_market
    ) VALUES (
        p_property_id,
        NOW(),
        suburb_rank,
        similar_count,
        similar_avg_price,
        EXTRACT(days FROM NOW() - property_rec.listing_date)::INTEGER
    )
    ON CONFLICT (property_id) 
    DO UPDATE SET
        calculated_at = NOW(),
        suburb_rank = EXCLUDED.suburb_rank,
        similar_properties_count = EXCLUDED.similar_properties_count,
        avg_similar_price = EXCLUDED.avg_similar_price,
        days_on_market = EXCLUDED.days_on_market;
END;
$$ LANGUAGE plpgsql;

\echo '✅ Additional database objects created'

-- =================================================================
-- STEP 7: Create Sample Data (Optional)
-- =================================================================
\echo ''
\echo '>>> STEP 7: Creating sample data for testing...'

-- Insert sample buyer segments
INSERT INTO buyer_segments (name, description, segment_type, criteria, is_active, priority_level) VALUES
('First Home Buyers', 'First-time property buyers under 35', 'demographic', 
 '{"max_age": 35, "buyer_type": "first_home_buyer", "max_budget": 1200000}', true, 8),
('Investors', 'Property investors looking for yield', 'behavioral',
 '{"buyer_type": "investor", "min_rental_yield": 4.0}', true, 7),
('Upgraders', 'Families upgrading to larger homes', 'demographic',
 '{"buyer_type": "upgrader", "min_bedrooms": 3, "min_budget": 800000}', true, 6),
('Luxury Buyers', 'High-end property purchasers', 'demographic',
 '{"min_budget": 3000000, "property_types": ["house", "penthouse"]}', true, 9);

-- Insert schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version VARCHAR(20) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_version (version, description) VALUES
('1.0.0', 'Initial ReAgent Sydney database schema with TimescaleDB integration');

\echo '✅ Sample data created'

-- =================================================================
-- STEP 8: Set up Security and Permissions
-- =================================================================
\echo ''
\echo '>>> STEP 8: Setting up security...'

-- Create application roles (if they don't exist)
DO $$
BEGIN
    -- Application read-write role
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'reagent_app') THEN
        CREATE ROLE reagent_app WITH LOGIN;
        RAISE NOTICE 'Created role: reagent_app';
    END IF;
    
    -- Read-only analytics role
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'reagent_readonly') THEN
        CREATE ROLE reagent_readonly WITH LOGIN;
        RAISE NOTICE 'Created role: reagent_readonly';
    END IF;
END $$;

-- Grant permissions to application role
GRANT USAGE ON SCHEMA public TO reagent_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO reagent_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO reagent_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO reagent_app;

-- Grant read-only permissions to analytics role
GRANT USAGE ON SCHEMA public TO reagent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reagent_readonly;
GRANT EXECUTE ON FUNCTION get_suburb_price_stats(VARCHAR, VARCHAR, INTEGER) TO reagent_readonly;
GRANT EXECUTE ON FUNCTION find_similar_properties(UUID, INTEGER, INTEGER) TO reagent_readonly;

\echo '✅ Security and permissions configured'

-- =================================================================
-- FINAL VERIFICATION
-- =================================================================
\echo ''
\echo '>>> Final verification checks...'

-- Verify all tables exist
\echo 'Checking table creation...'
SELECT 
    schemaname,
    tablename,
    hasindexes,
    hasrules,
    hastriggers
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;

-- Verify hypertables
\echo 'Checking TimescaleDB hypertables...'
SELECT 
    hypertable_name,
    num_dimensions,
    num_chunks,
    compression_enabled
FROM timescaledb_information.hypertables
ORDER BY hypertable_name;

-- Verify continuous aggregates
\echo 'Checking continuous aggregates...'
SELECT 
    view_name,
    refresh_lag,
    refresh_interval
FROM timescaledb_information.continuous_aggregates
ORDER BY view_name;

-- Final success message
\echo ''
\echo '==================================================================='
\echo '✅ ReAgent Sydney Database Setup Complete!'
\echo '==================================================================='
\echo ''
\echo 'Summary:'
\echo '- ✅ Extensions: TimescaleDB, PostGIS, UUID, Full-text search'
\echo '- ✅ Tables: 17 core tables created'
\echo '- ✅ Hypertables: 7 time-series tables optimized'
\echo '- ✅ Indexes: 50+ performance indexes created'
\echo '- ✅ Continuous Aggregates: 4 real-time analytics views'
\echo '- ✅ Functions: Helper functions for common operations'
\echo '- ✅ Security: Application roles and permissions'
\echo '- ✅ Sample Data: Basic segments and configuration'
\echo ''
\echo 'Next Steps:'
\echo '1. Update your .env file with database connection details'
\echo '2. Run: python -m alembic stamp head'
\echo '3. Test the connection: python -c "from src.core.database import engine; print(engine.execute(\"SELECT version()\").scalar())"'
\echo ''
\echo 'Database is ready for ReAgent Sydney development! 🚀'