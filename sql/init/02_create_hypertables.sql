-- ReAgent Sydney - TimescaleDB Hypertable Setup
-- Convert time-series tables to hypertables for optimal performance

-- Function to create hypertables safely
CREATE OR REPLACE FUNCTION create_hypertable_if_not_exists(
    table_name TEXT,
    time_column TEXT,
    chunk_time_interval INTERVAL DEFAULT INTERVAL '1 day'
)
RETURNS VOID AS $$
BEGIN
    -- Check if table is already a hypertable
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables 
        WHERE hypertable_name = table_name
    ) THEN
        PERFORM create_hypertable(table_name, time_column, chunk_time_interval => chunk_time_interval);
        RAISE NOTICE 'Created hypertable: %', table_name;
    ELSE
        RAISE NOTICE 'Hypertable already exists: %', table_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create hypertables for time-series data after tables are created
-- This will be called after SQLAlchemy creates the base tables

CREATE OR REPLACE FUNCTION setup_timescale_hypertables()
RETURNS VOID AS $$
BEGIN
    -- Wait for tables to be created by SQLAlchemy/DDL
    -- Then convert to hypertables
    
    -- Property price history (high frequency updates)
    PERFORM create_hypertable_if_not_exists(
        'property_price_history', 
        'recorded_at', 
        INTERVAL '6 hours'
    );
    
    -- Market trends (daily/weekly analysis)
    PERFORM create_hypertable_if_not_exists(
        'market_trends', 
        'period_start', 
        INTERVAL '1 day'
    );
    
    -- Price changes (event-driven updates)
    PERFORM create_hypertable_if_not_exists(
        'price_changes', 
        'change_date', 
        INTERVAL '1 day'
    );
    
    -- Property interactions (user behavior tracking)
    PERFORM create_hypertable_if_not_exists(
        'property_interactions', 
        'interaction_timestamp', 
        INTERVAL '1 day'
    );
    
    -- Buyer search history (analytics)
    PERFORM create_hypertable_if_not_exists(
        'buyer_search_history', 
        'search_timestamp', 
        INTERVAL '1 day'
    );
    
    -- Agent execution logs (monitoring)
    PERFORM create_hypertable_if_not_exists(
        'agent_executions', 
        'started_at', 
        INTERVAL '1 day'
    );
    
    -- Agent logs (high volume debugging data)
    PERFORM create_hypertable_if_not_exists(
        'agent_logs', 
        'timestamp', 
        INTERVAL '6 hours'
    );
    
END;
$$ LANGUAGE plpgsql;

-- Create continuous aggregates for common queries
CREATE OR REPLACE FUNCTION create_continuous_aggregates()
RETURNS VOID AS $$
BEGIN
    -- Daily property price changes summary
    DROP MATERIALIZED VIEW IF EXISTS daily_price_changes CASCADE;
    CREATE MATERIALIZED VIEW daily_price_changes
    WITH (timescaledb.continuous) AS
    SELECT 
        time_bucket('1 day', pph.recorded_at) AS day,
        p.suburb,
        p.property_type,
        COUNT(*) as change_count,
        AVG(pph.change_percentage) as avg_change_pct,
        AVG(pph.amount) as avg_price,
        COUNT(CASE WHEN pph.price_type = 'guide' THEN 1 END) as guide_changes,
        COUNT(CASE WHEN pph.price_type = 'sold' THEN 1 END) as sales
    FROM property_price_history pph
    JOIN properties p ON pph.property_id = p.id
    WHERE pph.recorded_at > NOW() - INTERVAL '1 year'
    GROUP BY day, p.suburb, p.property_type;
    
    -- Add refresh policy (refresh every hour)
    SELECT add_continuous_aggregate_policy('daily_price_changes',
        start_offset => INTERVAL '1 month',
        end_offset => INTERVAL '1 hour',
        schedule_interval => INTERVAL '1 hour');
    
    -- Weekly suburb property trends
    DROP MATERIALIZED VIEW IF EXISTS weekly_suburb_trends CASCADE;
    CREATE MATERIALIZED VIEW weekly_suburb_trends
    WITH (timescaledb.continuous) AS
    SELECT 
        time_bucket('1 week', p.listing_date) AS week,
        p.suburb,
        p.postcode,
        COUNT(*) as new_listings,
        AVG(p.price_guide) as avg_price_guide,
        COUNT(CASE WHEN p.status = 'sold' THEN 1 END) as sales_count,
        COUNT(DISTINCT p.property_type) as property_variety,
        AVG(p.bedrooms) as avg_bedrooms
    FROM properties p
    WHERE p.listing_date > NOW() - INTERVAL '2 years'
      AND p.price_guide IS NOT NULL
    GROUP BY week, p.suburb, p.postcode;
    
    -- Add refresh policy
    SELECT add_continuous_aggregate_policy('weekly_suburb_trends',
        start_offset => INTERVAL '3 months',
        end_offset => INTERVAL '1 day',
        schedule_interval => INTERVAL '6 hours');
    
    -- Daily buyer interaction patterns
    DROP MATERIALIZED VIEW IF EXISTS daily_buyer_interactions CASCADE;
    CREATE MATERIALIZED VIEW daily_buyer_interactions
    WITH (timescaledb.continuous) AS
    SELECT 
        time_bucket('1 day', pi.interaction_timestamp) AS day,
        pi.interaction_type,
        COUNT(*) as interaction_count,
        COUNT(DISTINCT pi.buyer_id) as unique_buyers,
        COUNT(DISTINCT pi.property_id) as unique_properties,
        AVG(pi.time_spent_seconds) as avg_time_spent
    FROM property_interactions pi
    WHERE pi.interaction_timestamp > NOW() - INTERVAL '1 year'
    GROUP BY day, pi.interaction_type;
    
    -- Add refresh policy
    SELECT add_continuous_aggregate_policy('daily_buyer_interactions',
        start_offset => INTERVAL '1 month',
        end_offset => INTERVAL '2 hours',
        schedule_interval => INTERVAL '2 hours');
    
    -- Hourly agent performance metrics
    DROP MATERIALIZED VIEW IF EXISTS hourly_agent_performance CASCADE;
    CREATE MATERIALIZED VIEW hourly_agent_performance
    WITH (timescaledb.continuous) AS
    SELECT 
        time_bucket('1 hour', ae.started_at) AS hour,
        ae.agent_name,
        COUNT(*) as execution_count,
        AVG(ae.duration_seconds) as avg_duration,
        COUNT(CASE WHEN ae.status = 'Completed' THEN 1 END) as successful_runs,
        COUNT(CASE WHEN ae.status = 'Failed' THEN 1 END) as failed_runs,
        AVG(ae.items_processed) as avg_items_processed,
        SUM(ae.api_calls_made) as total_api_calls
    FROM agent_executions ae
    WHERE ae.started_at > NOW() - INTERVAL '30 days'
    GROUP BY hour, ae.agent_name;
    
    -- Add refresh policy
    SELECT add_continuous_aggregate_policy('hourly_agent_performance',
        start_offset => INTERVAL '7 days',
        end_offset => INTERVAL '30 minutes',
        schedule_interval => INTERVAL '30 minutes');
        
END;
$$ LANGUAGE plpgsql;