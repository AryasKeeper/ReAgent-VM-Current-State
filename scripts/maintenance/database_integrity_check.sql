-- ============================================================================
-- ReAgent Sydney - Database Integrity and Data Quality Validation Queries
-- ============================================================================
-- 
-- Comprehensive SQL queries for validating data integrity, detecting corruption,
-- and analyzing data quality across all ReAgent Sydney database tables.
--
-- Usage:
--   psql -d reagent_sydney_dev -f src/scripts/database_integrity_check.sql
--
-- Author: Property Data Detective
-- Date: 2025-07-28
-- ============================================================================

\echo '🔍 ReAgent Sydney - Database Integrity Check Starting'
\echo '============================================================================'

-- Set output formatting for better readability
\pset format wrapped
\pset columns 120

-- ============================================================================
-- SECTION 1: BASIC DATABASE HEALTH CHECKS
-- ============================================================================
\echo ''
\echo '>>> SECTION 1: Basic Database Health Checks'
\echo '----------------------------------------------------------------------------'

-- Check table sizes and record counts
\echo '📊 Table Sizes and Record Counts:'
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as table_size,
    (SELECT count(*) FROM information_schema.tables WHERE table_name = t.tablename) as record_count_placeholder
FROM pg_tables t
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check for tables with no data
\echo ''
\echo '⚠️  Empty Tables Check:'
DO $$
DECLARE
    table_record RECORD;
    row_count INTEGER;
    empty_tables TEXT[] := '{}';
BEGIN
    FOR table_record IN 
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    LOOP
        EXECUTE format('SELECT count(*) FROM %I', table_record.tablename) INTO row_count;
        IF row_count = 0 THEN
            empty_tables := array_append(empty_tables, table_record.tablename);
        END IF;
    END LOOP;
    
    IF array_length(empty_tables, 1) > 0 THEN
        RAISE NOTICE 'Empty tables found: %', array_to_string(empty_tables, ', ');
    ELSE
        RAISE NOTICE '✅ All tables contain data';
    END IF;
END $$;

-- ============================================================================
-- SECTION 2: PROPERTY DATA INTEGRITY CHECKS
-- ============================================================================
\echo ''
\echo '>>> SECTION 2: Property Data Integrity Analysis'
\echo '----------------------------------------------------------------------------'

-- Check for duplicate listing IDs
\echo '🔍 Duplicate Listing ID Check:'
SELECT 
    listing_id,
    COUNT(*) as duplicate_count,
    ARRAY_AGG(DISTINCT source) as sources,
    ARRAY_AGG(DISTINCT suburb) as suburbs
FROM properties 
WHERE deleted_at IS NULL
GROUP BY listing_id 
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC
LIMIT 20;

-- Check for properties with missing critical fields
\echo ''
\echo '⚠️  Properties with Missing Critical Data:'
SELECT 
    'Missing Title' as issue_type,
    COUNT(*) as count
FROM properties 
WHERE (title IS NULL OR title = '') AND deleted_at IS NULL

UNION ALL

SELECT 
    'Missing Suburb' as issue_type,
    COUNT(*) as count
FROM properties 
WHERE (suburb IS NULL OR suburb = '') AND deleted_at IS NULL

UNION ALL

SELECT 
    'Missing Postcode' as issue_type,
    COUNT(*) as count
FROM properties 
WHERE (postcode IS NULL OR postcode = '') AND deleted_at IS NULL

UNION ALL

SELECT 
    'Missing Price' as issue_type,
    COUNT(*) as count
FROM properties 
WHERE price IS NULL AND listing_type = 'sale' AND deleted_at IS NULL

UNION ALL

SELECT 
    'Missing Coordinates' as issue_type,
    COUNT(*) as count
FROM properties 
WHERE (latitude IS NULL OR longitude IS NULL) AND deleted_at IS NULL
ORDER BY count DESC;

-- Check for invalid postcodes (Sydney focus)
\echo ''
\echo '🏠 Invalid Postcode Analysis:'
SELECT 
    'Total Properties' as metric,
    COUNT(*) as count
FROM properties WHERE deleted_at IS NULL

UNION ALL

SELECT 
    'Valid 4-digit Postcodes' as metric,
    COUNT(*) as count
FROM properties 
WHERE postcode ~ '^[0-9]{4}$' AND deleted_at IS NULL

UNION ALL

SELECT 
    'Sydney Metro Postcodes (2000-2999)' as metric,
    COUNT(*) as count
FROM properties 
WHERE postcode ~ '^2[0-9]{3}$' AND deleted_at IS NULL

UNION ALL

SELECT 
    'Invalid Postcode Format' as metric,
    COUNT(*) as count
FROM properties 
WHERE NOT (postcode ~ '^[0-9]{4}$') AND deleted_at IS NULL;

-- Show sample invalid postcodes
\echo ''
\echo '📋 Sample Invalid Postcodes:'
SELECT DISTINCT 
    postcode,
    COUNT(*) as property_count,
    ARRAY_AGG(DISTINCT suburb) as suburbs
FROM properties 
WHERE NOT (postcode ~ '^[0-9]{4}$') AND deleted_at IS NULL
GROUP BY postcode
ORDER BY property_count DESC
LIMIT 15;

-- Check for properties with extreme values
\echo ''
\echo '💰 Properties with Extreme Values:'
SELECT 
    'Price > $50M' as extreme_type,
    COUNT(*) as count,
    MAX(price) as max_value
FROM properties 
WHERE price > 50000000 AND deleted_at IS NULL

UNION ALL

SELECT 
    'Price < $100K' as extreme_type,
    COUNT(*) as count,
    MIN(price) as max_value
FROM properties 
WHERE price < 100000 AND price > 0 AND deleted_at IS NULL

UNION ALL

SELECT 
    'Bedrooms > 10' as extreme_type,
    COUNT(*) as count,
    MAX(bedrooms) as max_value
FROM properties 
WHERE bedrooms > 10 AND deleted_at IS NULL

UNION ALL

SELECT 
    'Land Size > 10,000 sqm' as extreme_type,
    COUNT(*) as count,
    MAX(land_size) as max_value
FROM properties 
WHERE land_size > 10000 AND deleted_at IS NULL;

-- ============================================================================
-- SECTION 3: GEOGRAPHIC DATA VALIDATION
-- ============================================================================
\echo ''
\echo '>>> SECTION 3: Geographic Data Validation'
\echo '----------------------------------------------------------------------------'

-- Check coordinate validity
\echo '🗺️  Coordinate Validation:'
SELECT 
    'Properties with Coordinates' as metric,
    COUNT(*) as count,
    ROUND(COUNT(*)::decimal / (SELECT COUNT(*) FROM properties WHERE deleted_at IS NULL) * 100, 2) as percentage
FROM properties 
WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND deleted_at IS NULL

UNION ALL

SELECT 
    'Invalid Latitude (outside -90 to 90)' as metric,
    COUNT(*) as count,
    0 as percentage
FROM properties 
WHERE latitude IS NOT NULL AND (latitude < -90 OR latitude > 90) AND deleted_at IS NULL

UNION ALL

SELECT 
    'Invalid Longitude (outside -180 to 180)' as metric,
    COUNT(*) as count,
    0 as percentage
FROM properties 
WHERE longitude IS NOT NULL AND (longitude < -180 OR longitude > 180) AND deleted_at IS NULL

UNION ALL

SELECT 
    'Properties outside Sydney approx bounds' as metric,
    COUNT(*) as count,
    0 as percentage
FROM properties 
WHERE latitude IS NOT NULL AND longitude IS NOT NULL 
    AND (latitude < -34.5 OR latitude > -33.0 OR longitude < 150.5 OR longitude > 151.5)
    AND deleted_at IS NULL;

-- Suburb to postcode mapping consistency
\echo ''
\echo '🏘️  Suburb-Postcode Mapping Analysis:'
SELECT 
    suburb,
    COUNT(DISTINCT postcode) as postcode_count,
    ARRAY_AGG(DISTINCT postcode ORDER BY postcode) as postcodes,
    COUNT(*) as property_count
FROM properties 
WHERE deleted_at IS NULL
GROUP BY suburb
HAVING COUNT(DISTINCT postcode) > 3  -- Suburbs with many postcodes (potential issues)
ORDER BY postcode_count DESC, property_count DESC
LIMIT 20;

-- ============================================================================
-- SECTION 4: PRICE HISTORY DATA VALIDATION
-- ============================================================================
\echo ''
\echo '>>> SECTION 4: Price History Data Validation'
\echo '----------------------------------------------------------------------------'

-- Price history completeness
\echo '💰 Price History Completeness:'
SELECT 
    'Properties with Price' as metric,
    COUNT(*) as count
FROM properties 
WHERE price IS NOT NULL AND deleted_at IS NULL

UNION ALL

SELECT 
    'Properties with Price History' as metric,
    COUNT(DISTINCT property_id) as count
FROM property_price_history

UNION ALL

SELECT 
    'Properties Missing Price History' as metric,
    COUNT(*) as count
FROM properties p
LEFT JOIN property_price_history pph ON p.id = pph.property_id
WHERE p.price IS NOT NULL AND p.deleted_at IS NULL AND pph.property_id IS NULL;

-- Check for price anomalies
\echo ''
\echo '📈 Price History Anomalies:'
WITH price_stats AS (
    SELECT 
        property_id,
        COUNT(*) as history_count,
        MIN(price) as min_price,
        MAX(price) as max_price,
        MAX(price) - MIN(price) as price_range,
        STDDEV(price) as price_stddev
    FROM property_price_history
    WHERE created_at >= NOW() - INTERVAL '90 days'
    GROUP BY property_id
)
SELECT 
    'High Volatility (>$500K stddev)' as anomaly_type,
    COUNT(*) as count,
    AVG(price_stddev) as avg_stddev
FROM price_stats
WHERE price_stddev > 500000

UNION ALL

SELECT 
    'Extreme Range (>$2M difference)' as anomaly_type,
    COUNT(*) as count,
    AVG(price_range) as avg_stddev
FROM price_stats
WHERE price_range > 2000000

UNION ALL

SELECT 
    'Many Updates (>10 in 90 days)' as anomaly_type,
    COUNT(*) as count,
    AVG(history_count) as avg_stddev
FROM price_stats
WHERE history_count > 10;

-- ============================================================================
-- SECTION 5: REFERENTIAL INTEGRITY CHECKS
-- ============================================================================
\echo ''
\echo '>>> SECTION 5: Referential Integrity Analysis'
\echo '----------------------------------------------------------------------------'

-- Check for orphaned records
\echo '🔗 Orphaned Records Check:'
SELECT 
    'Price History without Property' as orphan_type,
    COUNT(*) as count
FROM property_price_history pph
LEFT JOIN properties p ON pph.property_id = p.id
WHERE p.id IS NULL

UNION ALL

SELECT 
    'Properties with Invalid Agent Reference' as orphan_type,
    COUNT(*) as count
FROM properties p
LEFT JOIN agents a ON p.agent_id = a.id
WHERE p.agent_id IS NOT NULL AND a.id IS NULL

UNION ALL

SELECT 
    'Properties with Invalid Agency Reference' as orphan_type,
    COUNT(*) as count
FROM properties p
LEFT JOIN agencies ag ON p.agency_id = ag.id
WHERE p.agency_id IS NOT NULL AND ag.id IS NULL

UNION ALL

SELECT 
    'Inspections without Property' as orphan_type,
    COUNT(*) as count
FROM property_inspections pi
LEFT JOIN properties p ON pi.property_id = p.id
WHERE p.id IS NULL;

-- ============================================================================
-- SECTION 6: DATA SOURCE ANALYSIS
-- ============================================================================
\echo ''
\echo '>>> SECTION 6: Data Source Quality Analysis'
\echo '----------------------------------------------------------------------------'

-- Properties by source
\echo '📡 Properties by Data Source:'
SELECT 
    source,
    COUNT(*) as total_properties,
    COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) as active_properties,
    ROUND(AVG(CASE WHEN price IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 2) as price_completeness_pct,
    ROUND(AVG(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 2) as coord_completeness_pct,
    MIN(created_at) as first_listing,
    MAX(created_at) as latest_listing
FROM properties
GROUP BY source
ORDER BY total_properties DESC;

-- Cross-source property analysis
\echo ''
\echo '🔄 Cross-Source Property Analysis:'
WITH cross_source AS (
    SELECT 
        address_line_1, suburb, postcode,
        COUNT(DISTINCT source) as source_count,
        ARRAY_AGG(DISTINCT source) as sources,
        COUNT(*) as total_listings
    FROM properties 
    WHERE deleted_at IS NULL
    GROUP BY address_line_1, suburb, postcode
)
SELECT 
    source_count,
    COUNT(*) as property_groups,
    SUM(total_listings) as total_listings
FROM cross_source
GROUP BY source_count
ORDER BY source_count;

-- Sample properties from multiple sources
\echo ''
\echo '📋 Sample Properties from Multiple Sources:'
SELECT 
    address_line_1 || ', ' || suburb as address,
    postcode,
    ARRAY_AGG(DISTINCT source) as sources,
    ARRAY_AGG(DISTINCT price) as prices,
    COUNT(*) as listing_count
FROM properties 
WHERE deleted_at IS NULL
GROUP BY address_line_1, suburb, postcode
HAVING COUNT(DISTINCT source) > 1
ORDER BY COUNT(*) DESC
LIMIT 10;

-- ============================================================================
-- SECTION 7: TIMESCALEDB HEALTH CHECK
-- ============================================================================
\echo ''
\echo '>>> SECTION 7: TimescaleDB Health Analysis'
\echo '----------------------------------------------------------------------------'

-- Check hypertable status
\echo '⏰ TimescaleDB Hypertables Status:'
SELECT 
    hypertable_name,
    num_dimensions,
    num_chunks,
    compression_enabled,
    compressed_chunks,
    uncompressed_chunks
FROM timescaledb_information.hypertables
ORDER BY hypertable_name;

-- Check continuous aggregates
\echo ''
\echo '📊 Continuous Aggregates Status:'
SELECT 
    view_name,
    refresh_lag,
    refresh_interval,
    materialized_only
FROM timescaledb_information.continuous_aggregates
ORDER BY view_name;

-- ============================================================================
-- SECTION 8: PERFORMANCE ANALYSIS
-- ============================================================================
\echo ''
\echo '>>> SECTION 8: Performance Analysis'
\echo '----------------------------------------------------------------------------'

-- Check index usage
\echo '🚀 Index Usage Statistics:'
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    CASE 
        WHEN idx_tup_read > 0 
        THEN ROUND((idx_tup_fetch::decimal / idx_tup_read) * 100, 2)
        ELSE 0 
    END as efficiency_pct
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_tup_read DESC
LIMIT 20;

-- Table statistics
\echo ''
\echo '📈 Table Access Statistics:'
SELECT 
    schemaname,
    relname as tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY seq_tup_read + idx_tup_fetch DESC
LIMIT 15;

-- ============================================================================
-- SECTION 9: SUMMARY AND RECOMMENDATIONS
-- ============================================================================
\echo ''
\echo '>>> SECTION 9: Data Quality Summary'
\echo '----------------------------------------------------------------------------'

-- Overall data quality score calculation
WITH quality_metrics AS (
    SELECT 
        -- Basic completeness metrics
        COUNT(*) as total_properties,
        COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as properties_with_title,
        COUNT(CASE WHEN price IS NOT NULL THEN 1 END) as properties_with_price,
        COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as properties_with_coords,
        COUNT(CASE WHEN postcode ~ '^[0-9]{4}$' THEN 1 END) as properties_valid_postcode,
        
        -- Data consistency metrics
        COUNT(DISTINCT listing_id) as unique_listings,
        COUNT(*) - COUNT(DISTINCT listing_id) as duplicate_listings
        
    FROM properties 
    WHERE deleted_at IS NULL
)
SELECT 
    '📊 OVERALL DATA QUALITY SUMMARY' as summary_section,
    '' as spacer,
    CONCAT('Total Properties: ', total_properties) as metric_1,
    CONCAT('Title Completeness: ', ROUND((properties_with_title::decimal / total_properties) * 100, 1), '%') as metric_2,
    CONCAT('Price Completeness: ', ROUND((properties_with_price::decimal / total_properties) * 100, 1), '%') as metric_3,
    CONCAT('Coordinate Completeness: ', ROUND((properties_with_coords::decimal / total_properties) * 100, 1), '%') as metric_4,
    CONCAT('Valid Postcodes: ', ROUND((properties_valid_postcode::decimal / total_properties) * 100, 1), '%') as metric_5,
    CONCAT('Potential Duplicates: ', duplicate_listings) as metric_6
FROM quality_metrics;

-- ============================================================================
-- FINAL STATUS
-- ============================================================================
\echo ''
\echo '============================================================================'
\echo '✅ ReAgent Sydney Database Integrity Check Complete'
\echo '============================================================================'
\echo ''
\echo 'Next Steps:'
\echo '1. Review any identified issues above'
\echo '2. Run the Python data validation script for detailed analysis'
\echo '3. Address critical data quality issues'
\echo '4. Implement monitoring for ongoing data quality assurance'
\echo ''
\echo 'For detailed programmatic analysis, run:'
\echo '  python src/scripts/data_validation_audit.py --comprehensive'
\echo '============================================================================'