-- ReAgent Sydney - Performance Indexes
-- Create optimized indexes for common query patterns

-- Function to create index if it doesn't exist
CREATE OR REPLACE FUNCTION create_index_if_not_exists(
    index_name TEXT,
    table_name TEXT,
    index_definition TEXT
)
RETURNS VOID AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = index_name
    ) THEN
        EXECUTE format('CREATE INDEX %I ON %I %s', index_name, table_name, index_definition);
        RAISE NOTICE 'Created index: %', index_name;
    ELSE
        RAISE NOTICE 'Index already exists: %', index_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to create all performance indexes
CREATE OR REPLACE FUNCTION create_performance_indexes()
RETURNS VOID AS $$
BEGIN
    -- =================================================================
    -- PROPERTIES TABLE INDEXES
    -- =================================================================
    
    -- Core location searches
    PERFORM create_index_if_not_exists(
        'idx_properties_suburb_postcode', 'properties',
        '(suburb, postcode)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_properties_location_active', 'properties',
        '(suburb, status) WHERE status = ''active'''
    );
    
    -- Price-based searches
    PERFORM create_index_if_not_exists(
        'idx_properties_price_guide_type', 'properties',
        '(price_guide, property_type) WHERE price_guide IS NOT NULL'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_properties_bedrooms_price', 'properties',
        '(bedrooms, price_guide) WHERE bedrooms IS NOT NULL AND price_guide IS NOT NULL'
    );
    
    -- Listing lifecycle
    PERFORM create_index_if_not_exists(
        'idx_properties_listing_date_desc', 'properties',
        '(listing_date DESC) WHERE listing_date IS NOT NULL'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_properties_status_updated', 'properties',
        '(status, updated_at DESC)'
    );
    
    -- External system integration
    PERFORM create_index_if_not_exists(
        'idx_properties_listing_id_unique', 'properties',
        '(listing_id)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_properties_source_scraped', 'properties',
        '(source, last_scraped_at DESC)'
    );
    
    -- Geographic search (PostGIS)
    PERFORM create_index_if_not_exists(
        'idx_properties_location_gist', 'properties',
        'USING GIST (ll_to_earth(latitude::float8, longitude::float8)) WHERE latitude IS NOT NULL AND longitude IS NOT NULL'
    );
    
    -- Full text search
    PERFORM create_index_if_not_exists(
        'idx_properties_address_gin', 'properties',
        'USING GIN (to_tsvector(''english'', address_line_1 || '' '' || COALESCE(address_line_2, '''')))'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_properties_description_gin', 'properties',
        'USING GIN (to_tsvector(''english'', description)) WHERE description IS NOT NULL'
    );
    
    -- JSONB feature searches
    PERFORM create_index_if_not_exists(
        'idx_properties_features_gin', 'properties',
        'USING GIN (features) WHERE features IS NOT NULL'
    );
    
    -- =================================================================
    -- PROPERTY PRICE HISTORY INDEXES (TimescaleDB Hypertable)
    -- =================================================================
    
    PERFORM create_index_if_not_exists(
        'idx_price_history_property_time', 'property_price_history',
        '(property_id, recorded_at DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_price_history_price_type_time', 'property_price_history',
        '(price_type, recorded_at DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_price_history_amount_change', 'property_price_history',
        '(amount, change_percentage) WHERE change_percentage IS NOT NULL'
    );
    
    -- =================================================================
    -- BUYERS TABLE INDEXES
    -- =================================================================
    
    -- Contact and identification
    PERFORM create_index_if_not_exists(
        'idx_buyers_email_unique', 'buyers',
        '(email)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_buyers_status_type', 'buyers',
        '(status, buyer_type)'
    );
    
    -- Financial filtering
    PERFORM create_index_if_not_exists(
        'idx_buyers_pre_approval', 'buyers',
        '(pre_approval_status, pre_approval_amount) WHERE pre_approval_amount IS NOT NULL'
    );
    
    -- Timeline and urgency
    PERFORM create_index_if_not_exists(
        'idx_buyers_urgency_timeline', 'buyers',
        '(urgency_level, purchase_timeline) WHERE status = ''active'''
    );
    
    -- =================================================================
    -- BUYER PREFERENCES INDEXES
    -- =================================================================
    
    -- Location preferences
    PERFORM create_index_if_not_exists(
        'idx_preferences_suburbs_gin', 'buyer_preferences',
        'USING GIN (preferred_suburbs) WHERE preferred_suburbs IS NOT NULL'
    );
    
    -- Price range filtering
    PERFORM create_index_if_not_exists(
        'idx_preferences_price_range', 'buyer_preferences',
        '(min_price, max_price) WHERE is_active = true'
    );
    
    -- Property requirements
    PERFORM create_index_if_not_exists(
        'idx_preferences_bedrooms_bathrooms', 'buyer_preferences',
        '(min_bedrooms, min_bathrooms) WHERE is_active = true'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_preferences_property_types_gin', 'buyer_preferences',
        'USING GIN (property_types)'
    );
    
    -- Feature requirements
    PERFORM create_index_if_not_exists(
        'idx_preferences_required_features_gin', 'buyer_preferences',
        'USING GIN (required_features) WHERE required_features IS NOT NULL'
    );
    
    -- =================================================================
    -- PROPERTY MATCHES INDEXES
    -- =================================================================
    
    -- Core matching queries
    PERFORM create_index_if_not_exists(
        'idx_matches_buyer_score', 'property_matches',
        '(buyer_id, match_score DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_matches_property_score', 'property_matches',
        '(property_id, match_score DESC)'
    );
    
    -- Status and interaction tracking
    PERFORM create_index_if_not_exists(
        'idx_matches_status_created', 'property_matches',
        '(status, created_at DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_matches_buyer_status_score', 'property_matches',
        '(buyer_id, status, match_score DESC)'
    );
    
    -- Urgency and expiration
    PERFORM create_index_if_not_exists(
        'idx_matches_urgent_expires', 'property_matches',
        '(is_urgent, expires_at) WHERE expires_at IS NOT NULL'
    );
    
    -- =================================================================
    -- PROPERTY INTERACTIONS INDEXES (TimescaleDB Hypertable)
    -- =================================================================
    
    PERFORM create_index_if_not_exists(
        'idx_interactions_buyer_time', 'property_interactions',
        '(buyer_id, interaction_timestamp DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_interactions_property_time', 'property_interactions',
        '(property_id, interaction_timestamp DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_interactions_type_time', 'property_interactions',
        '(interaction_type, interaction_timestamp DESC)'
    );
    
    -- Session analysis
    PERFORM create_index_if_not_exists(
        'idx_interactions_session_id', 'property_interactions',
        '(session_id, interaction_timestamp) WHERE session_id IS NOT NULL'
    );
    
    -- =================================================================
    -- MARKET TRENDS INDEXES (TimescaleDB Hypertable)  
    -- =================================================================
    
    PERFORM create_index_if_not_exists(
        'idx_trends_geography_period', 'market_trends',
        '(geography_name, period_start DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_trends_postcode_period', 'market_trends',
        '(postcode, period_start DESC) WHERE postcode IS NOT NULL'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_trends_direction_confidence', 'market_trends',
        '(trend_direction, confidence_level DESC)'
    );
    
    -- =================================================================
    -- AGENT EXECUTION INDEXES (TimescaleDB Hypertable)
    -- =================================================================
    
    PERFORM create_index_if_not_exists(
        'idx_executions_agent_started', 'agent_executions',
        '(agent_name, started_at DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_executions_status_started', 'agent_executions',
        '(status, started_at DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_executions_execution_id', 'agent_executions',
        '(execution_id)'
    );
    
    -- Performance monitoring
    PERFORM create_index_if_not_exists(
        'idx_executions_duration_performance', 'agent_executions',
        '(agent_name, duration_seconds) WHERE duration_seconds IS NOT NULL'
    );
    
    -- =================================================================
    -- AGENT TASKS INDEXES
    -- =================================================================
    
    PERFORM create_index_if_not_exists(
        'idx_tasks_execution_order', 'agent_tasks',
        '(execution_id, task_order)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_tasks_status_started', 'agent_tasks',
        '(status, started_at DESC)'
    );
    
    -- =================================================================
    -- AGENT LOGS INDEXES (TimescaleDB Hypertable)
    -- =================================================================
    
    PERFORM create_index_if_not_exists(
        'idx_logs_execution_timestamp', 'agent_logs',
        '(execution_id, timestamp DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_logs_level_timestamp', 'agent_logs',
        '(log_level, timestamp DESC)'
    );
    
    PERFORM create_index_if_not_exists(
        'idx_logs_agent_timestamp', 'agent_logs',
        '(agent_name, timestamp DESC) WHERE agent_name IS NOT NULL'
    );
    
    -- Error analysis
    PERFORM create_index_if_not_exists(
        'idx_logs_errors', 'agent_logs',
        '(log_level, exception_type, timestamp DESC) WHERE log_level IN (''ERROR'', ''CRITICAL'')'
    );
    
END;
$$ LANGUAGE plpgsql;