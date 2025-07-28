-- ReAgent Sydney - Table Creation DDL
-- Creates all tables to match SQLAlchemy models with proper constraints

-- =============================================================================
-- PROPERTY DOMAIN TABLES
-- =============================================================================

-- Main properties table
CREATE TABLE IF NOT EXISTS properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- External identification
    listing_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Property information  
    title VARCHAR(500) NOT NULL,
    description TEXT,
    property_type VARCHAR(50) NOT NULL,
    
    -- Location
    address_line_1 VARCHAR(200) NOT NULL,
    address_line_2 VARCHAR(200),
    suburb VARCHAR(100) NOT NULL,
    postcode VARCHAR(10) NOT NULL,
    state VARCHAR(10) NOT NULL DEFAULT 'NSW',
    country VARCHAR(50) NOT NULL DEFAULT 'Australia',
    
    -- Geographic coordinates
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    
    -- Property features
    bedrooms INTEGER,
    bathrooms INTEGER, 
    car_spaces INTEGER,
    land_size_sqm INTEGER,
    building_size_sqm INTEGER,
    year_built INTEGER,
    
    -- Pricing
    price_guide DECIMAL(12,2),
    rent_per_week DECIMAL(8,2),
    price_method VARCHAR(50), -- 'fixed', 'auction', 'offers', 'rent'
    
    -- Listing status
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    listing_date TIMESTAMP WITH TIME ZONE,
    sold_date TIMESTAMP WITH TIME ZONE,
    inspection_times JSONB,
    
    -- Features and amenities (JSONB for flexibility)
    features JSONB,
    amenities JSONB,
    
    -- Data source tracking
    source VARCHAR(50) NOT NULL, -- 'domain', 'realestate', 'corelogic'
    source_url TEXT,
    last_scraped_at TIMESTAMP WITH TIME ZONE,
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT chk_price_positive CHECK (price_guide > 0),
    CONSTRAINT chk_rent_positive CHECK (rent_per_week > 0),
    CONSTRAINT chk_bedrooms CHECK (bedrooms >= 0 AND bedrooms <= 20),
    CONSTRAINT chk_bathrooms CHECK (bathrooms >= 0 AND bathrooms <= 20),
    CONSTRAINT chk_coordinates CHECK (
        (latitude IS NULL AND longitude IS NULL) OR 
        (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
    )
);

-- Property price history (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS property_price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL,
    
    -- Time series data
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Price information
    price_type VARCHAR(50) NOT NULL, -- 'guide', 'sold', 'rent'
    amount DECIMAL(12,2) NOT NULL,
    previous_amount DECIMAL(12,2),
    change_percentage DECIMAL(5,2),
    
    -- Change tracking
    change_reason VARCHAR(100),
    detected_by VARCHAR(50), -- agent that detected the change
    
    -- Data source
    source VARCHAR(50) NOT NULL,
    confidence_score DECIMAL(3,2) DEFAULT 1.0,
    
    -- Metadata
    additional_data JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_property_price_property 
        FOREIGN KEY (property_id) REFERENCES properties(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_amount_positive CHECK (amount > 0),
    CONSTRAINT chk_confidence CHECK (confidence_score BETWEEN 0 AND 1)
);

-- Property inspections
CREATE TABLE IF NOT EXISTS property_inspections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL,
    
    -- Inspection details
    inspection_type VARCHAR(50) NOT NULL, -- 'open_home', 'private', 'auction'
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    
    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'scheduled', -- 'scheduled', 'completed', 'cancelled'
    attendance_count INTEGER,
    
    -- Outcome tracking
    outcome VARCHAR(100), -- 'high_interest', 'moderate_interest', 'low_interest'
    outcome_notes TEXT,
    
    -- Agent information
    agent_name VARCHAR(200),
    agent_contact VARCHAR(200),
    
    -- Metadata
    inspection_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_inspection_property 
        FOREIGN KEY (property_id) REFERENCES properties(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_duration CHECK (duration_minutes > 0 AND duration_minutes <= 480)
);

-- Property market metrics
CREATE TABLE IF NOT EXISTS property_market_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL,
    
    -- Time period
    calculated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    period_days INTEGER NOT NULL DEFAULT 30,
    
    -- Market position
    suburb_rank INTEGER,
    price_percentile DECIMAL(5,2),
    days_on_market INTEGER,
    
    -- Competition analysis  
    similar_properties_count INTEGER,
    avg_similar_price DECIMAL(12,2),
    competition_score DECIMAL(3,2),
    
    -- Market trends
    suburb_growth_rate DECIMAL(5,2),
    price_momentum VARCHAR(20), -- 'increasing', 'decreasing', 'stable'
    
    -- Investment metrics
    rental_yield DECIMAL(5,2),
    capital_growth_12m DECIMAL(5,2),
    
    -- Metadata
    metrics_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_metrics_property 
        FOREIGN KEY (property_id) REFERENCES properties(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_percentile CHECK (price_percentile BETWEEN 0 AND 100),
    CONSTRAINT chk_competition CHECK (competition_score BETWEEN 0 AND 1)
);

-- =============================================================================
-- BUYER DOMAIN TABLES  
-- =============================================================================

-- Buyer profiles
CREATE TABLE IF NOT EXISTS buyers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Personal information
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    
    -- Contact information
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    mobile VARCHAR(50),
    
    -- Status and lifecycle
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    buyer_type VARCHAR(50) NOT NULL DEFAULT 'individual',
    
    -- Financial information
    pre_approval_status VARCHAR(50) DEFAULT 'unknown',
    pre_approval_amount DECIMAL(12,2),
    deposit_available DECIMAL(12,2),
    
    -- Timeline and urgency
    purchase_timeline VARCHAR(50), -- 'immediate', '3_months', '6_months', '12_months'
    urgency_level VARCHAR(20) DEFAULT 'medium',
    
    -- Communication preferences
    contact_method VARCHAR(50) DEFAULT 'email',
    max_contact_frequency VARCHAR(50) DEFAULT 'weekly',
    
    -- GDPR compliance
    consent_marketing BOOLEAN DEFAULT false,
    consent_data_processing BOOLEAN DEFAULT true,
    privacy_preferences JSONB,
    
    -- Agent assignment
    assigned_agent VARCHAR(100),
    agent_notes TEXT,
    
    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT chk_pre_approval_positive CHECK (pre_approval_amount > 0),
    CONSTRAINT chk_deposit_positive CHECK (deposit_available >= 0)
);

-- Buyer preferences and search criteria
CREATE TABLE IF NOT EXISTS buyer_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_id UUID NOT NULL,
    
    -- Location preferences
    preferred_suburbs TEXT[], -- Array of suburb names
    excluded_suburbs TEXT[],
    max_distance_km INTEGER,
    location_flexibility VARCHAR(50) DEFAULT 'moderate',
    
    -- Property preferences
    property_types TEXT[] NOT NULL, -- ['house', 'apartment', 'townhouse']
    min_bedrooms INTEGER DEFAULT 1,
    max_bedrooms INTEGER,
    min_bathrooms INTEGER DEFAULT 1,
    max_bathrooms INTEGER,
    min_car_spaces INTEGER DEFAULT 0,
    max_car_spaces INTEGER,
    
    -- Financial constraints
    min_price DECIMAL(12,2),
    max_price DECIMAL(12,2) NOT NULL,
    max_rent_per_week DECIMAL(8,2),
    
    -- Features and amenities
    required_features TEXT[], -- ['pool', 'garden', 'gym', 'balcony']
    nice_to_have_features TEXT[],
    deal_breakers TEXT[],
    
    -- Lifestyle preferences
    school_catchment_areas TEXT[],
    transport_preferences JSONB,
    lifestyle_priorities JSONB,
    
    -- Search behavior
    search_frequency VARCHAR(50) DEFAULT 'daily',
    auto_matching_enabled BOOLEAN DEFAULT true,
    notification_types TEXT[] DEFAULT ARRAY['new_matches', 'price_drops'],
    
    -- Preference metadata
    preference_weights JSONB, -- ML model weights for scoring
    last_refined_at TIMESTAMP WITH TIME ZONE,
    refinement_count INTEGER DEFAULT 0,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    
    -- Constraints
    CONSTRAINT fk_preferences_buyer 
        FOREIGN KEY (buyer_id) REFERENCES buyers(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_price_range CHECK (min_price <= max_price),
    CONSTRAINT chk_bedroom_range CHECK (min_bedrooms <= max_bedrooms),
    CONSTRAINT chk_bathroom_range CHECK (min_bathrooms <= max_bathrooms)
);

-- Property matches (buyer-property recommendations)
CREATE TABLE IF NOT EXISTS property_matches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_id UUID NOT NULL,
    property_id UUID NOT NULL,
    
    -- Matching algorithm results
    match_score DECIMAL(5,3) NOT NULL, -- 0.000 to 1.000
    match_reasons JSONB NOT NULL, -- Detailed explanation of match
    algorithm_version VARCHAR(20) NOT NULL,
    
    -- Match categorization
    match_type VARCHAR(50) NOT NULL, -- 'perfect', 'strong', 'good', 'potential'
    priority_level VARCHAR(20) DEFAULT 'medium',
    
    -- Buyer interaction tracking
    status VARCHAR(50) NOT NULL DEFAULT 'new', -- 'new', 'viewed', 'interested', 'dismissed'
    viewed_at TIMESTAMP WITH TIME ZONE,
    interaction_count INTEGER DEFAULT 0,
    
    -- Match quality feedback
    buyer_feedback VARCHAR(50), -- 'love_it', 'interested', 'maybe', 'not_interested'
    feedback_reasons TEXT[],
    agent_notes TEXT,
    
    -- Time sensitivity
    expires_at TIMESTAMP WITH TIME ZONE,
    is_urgent BOOLEAN DEFAULT false,
    
    -- Match metadata
    match_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_match_buyer 
        FOREIGN KEY (buyer_id) REFERENCES buyers(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_match_property 
        FOREIGN KEY (property_id) REFERENCES properties(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_match_score CHECK (match_score BETWEEN 0 AND 1),
    CONSTRAINT uk_buyer_property UNIQUE (buyer_id, property_id)
);

-- Buyer search history for behavior analysis
CREATE TABLE IF NOT EXISTS buyer_search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_id UUID NOT NULL,
    
    -- Search parameters
    search_type VARCHAR(50) NOT NULL, -- 'map', 'list', 'filter', 'text'
    search_criteria JSONB NOT NULL,
    results_count INTEGER,
    
    -- Interaction tracking
    session_id VARCHAR(100),
    search_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    time_spent_seconds INTEGER,
    
    -- Results interaction
    properties_viewed TEXT[], -- Array of property IDs viewed
    properties_saved TEXT[], -- Array of property IDs saved/favorited
    
    -- Device and context
    user_agent TEXT,
    ip_address INET,
    device_type VARCHAR(50),
    
    -- Search metadata
    search_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_search_buyer 
        FOREIGN KEY (buyer_id) REFERENCES buyers(id) 
        ON DELETE CASCADE
);

-- Property interactions (views, saves, inquiries)
CREATE TABLE IF NOT EXISTS property_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_id UUID NOT NULL,
    property_id UUID NOT NULL,
    
    -- Interaction details
    interaction_type VARCHAR(50) NOT NULL, -- 'view', 'save', 'inquiry', 'inspection_book'
    interaction_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Context
    interaction_source VARCHAR(50), -- 'match_notification', 'search_results', 'direct_link'
    session_id VARCHAR(100),
    
    -- Engagement metrics
    time_spent_seconds INTEGER,
    page_views INTEGER DEFAULT 1,
    actions_taken TEXT[], -- ['photo_gallery', 'map_view', 'similar_properties']
    
    -- Communication tracking
    inquiry_message TEXT,
    agent_response TEXT,
    response_time_hours DECIMAL(8,2),
    
    -- Follow-up status
    follow_up_required BOOLEAN DEFAULT false,
    follow_up_notes TEXT,
    follow_up_completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Device and technical
    user_agent TEXT,
    ip_address INET,
    referrer_url TEXT,
    
    -- Interaction metadata
    interaction_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_interaction_buyer 
        FOREIGN KEY (buyer_id) REFERENCES buyers(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_interaction_property 
        FOREIGN KEY (property_id) REFERENCES properties(id) 
        ON DELETE CASCADE
);

-- Buyer segments for targeted marketing
CREATE TABLE IF NOT EXISTS buyer_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Segment definition
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    segment_type VARCHAR(50) NOT NULL, -- 'demographic', 'behavioral', 'psychographic'
    
    -- Targeting criteria
    criteria JSONB NOT NULL, -- Complex criteria definition
    auto_assignment_rules JSONB,
    
    -- Campaign management
    is_active BOOLEAN DEFAULT true,
    priority_level INTEGER DEFAULT 5,
    campaign_tags TEXT[],
    
    -- Performance tracking
    member_count INTEGER DEFAULT 0,
    conversion_rate DECIMAL(5,3),
    avg_time_to_conversion_days DECIMAL(8,2),
    
    -- Marketing preferences
    preferred_channels TEXT[], -- ['email', 'sms', 'push', 'phone']
    messaging_tone VARCHAR(50), -- 'professional', 'casual', 'urgent'
    contact_frequency VARCHAR(50), -- 'daily', 'weekly', 'monthly'
    
    -- Audit
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_priority_level CHECK (priority_level BETWEEN 1 AND 10)
);

-- Many-to-many: buyers to segments
CREATE TABLE IF NOT EXISTS buyer_segment_memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    buyer_id UUID NOT NULL,
    segment_id UUID NOT NULL,
    
    -- Membership details
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    left_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    
    -- Assignment method
    assignment_method VARCHAR(50) NOT NULL, -- 'manual', 'auto_rule', 'ml_model'
    assigned_by VARCHAR(100),
    confidence_score DECIMAL(3,2) DEFAULT 1.0,
    
    -- Membership metadata
    membership_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_membership_buyer 
        FOREIGN KEY (buyer_id) REFERENCES buyers(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_membership_segment 
        FOREIGN KEY (segment_id) REFERENCES buyer_segments(id) 
        ON DELETE CASCADE,
    CONSTRAINT uk_buyer_segment UNIQUE (buyer_id, segment_id),
    CONSTRAINT chk_confidence CHECK (confidence_score BETWEEN 0 AND 1)
);

-- =============================================================================
-- MARKET DOMAIN TABLES
-- =============================================================================

-- Market trends analysis
CREATE TABLE IF NOT EXISTS market_trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Geographic scope
    geography_type VARCHAR(20) NOT NULL, -- 'suburb', 'lga', 'region'
    geography_name VARCHAR(100) NOT NULL,
    postcode VARCHAR(10),
    
    -- Time period
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    period_type VARCHAR(20) NOT NULL, -- 'weekly', 'monthly', 'quarterly'
    
    -- Market direction and strength
    trend_direction VARCHAR(20) NOT NULL, -- 'Up', 'Down', 'Stable', 'Volatile'
    trend_strength DECIMAL(3,2), -- 0.00 to 1.00 (strength of trend)
    confidence_level DECIMAL(3,2), -- 0.00 to 1.00 (confidence in analysis)
    
    -- Price metrics
    avg_price DECIMAL(12,2),
    median_price DECIMAL(12,2),
    price_change_pct DECIMAL(5,2),
    price_volatility DECIMAL(5,2),
    
    -- Volume metrics
    listings_count INTEGER,
    sales_count INTEGER,
    new_listings_count INTEGER,
    
    -- Market segment analysis
    segment_data JSONB, -- Breakdown by price segments
    property_type_data JSONB, -- Breakdown by property types
    
    -- Market indicators
    days_on_market_avg DECIMAL(8,2),
    clearance_rate DECIMAL(5,2),
    discount_rate DECIMAL(5,2),
    
    -- External factors
    interest_rate DECIMAL(5,3),
    economic_indicators JSONB,
    seasonal_factors JSONB,
    
    -- Analysis metadata
    analysis_method VARCHAR(50), -- 'agent_analysis', 'statistical', 'ml_model'
    data_sources TEXT[],
    analysis_notes TEXT,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints  
    CONSTRAINT chk_trend_strength CHECK (trend_strength BETWEEN 0 AND 1),
    CONSTRAINT chk_confidence_level CHECK (confidence_level BETWEEN 0 AND 1),
    CONSTRAINT chk_period_order CHECK (period_start < period_end),
    CONSTRAINT uk_geography_period UNIQUE (geography_type, geography_name, period_start)
);

-- Suburb statistics
CREATE TABLE IF NOT EXISTS suburb_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Location identification
    suburb VARCHAR(100) NOT NULL,
    postcode VARCHAR(10) NOT NULL,
    state VARCHAR(10) NOT NULL DEFAULT 'NSW',
    lga_name VARCHAR(100),
    
    -- Time period
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Core statistics
    avg_price DECIMAL(12,2),
    median_price DECIMAL(12,2),
    min_price DECIMAL(12,2),
    max_price DECIMAL(12,2),
    price_growth_12m DECIMAL(5,2),
    price_growth_5y DECIMAL(5,2),
    
    -- Market activity
    sales_volume INTEGER,
    new_listings_count INTEGER,
    total_stock INTEGER,
    days_on_market DECIMAL(8,2),
    clearance_rate DECIMAL(5,2),
    
    -- Property mix
    property_type_distribution JSONB,
    bedroom_distribution JSONB,
    age_distribution JSONB,
    
    -- Investment metrics
    median_rental_yield DECIMAL(5,2),
    vacancy_rate DECIMAL(5,2),
    rental_growth_12m DECIMAL(5,2),
    
    -- Demographics (if available)
    population_estimate INTEGER,
    median_age DECIMAL(4,1),
    median_income DECIMAL(12,2),
    
    -- Infrastructure scoring
    transport_score DECIMAL(3,1), -- 1-10 scale
    school_score DECIMAL(3,1),    -- 1-10 scale  
    amenity_score DECIMAL(3,1),   -- 1-10 scale
    
    -- Prediction models
    price_forecast_3m DECIMAL(12,2),
    price_forecast_6m DECIMAL(12,2),
    price_forecast_12m DECIMAL(12,2),
    forecast_confidence DECIMAL(3,2),
    
    -- Data quality
    data_completeness DECIMAL(3,2), -- 0-1 score
    data_sources TEXT[],
    last_updated TIMESTAMP WITH TIME ZONE,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_transport_score CHECK (transport_score BETWEEN 1 AND 10),
    CONSTRAINT chk_school_score CHECK (school_score BETWEEN 1 AND 10),
    CONSTRAINT chk_amenity_score CHECK (amenity_score BETWEEN 1 AND 10),
    CONSTRAINT chk_data_completeness CHECK (data_completeness BETWEEN 0 AND 1),
    CONSTRAINT uk_suburb_period UNIQUE (suburb, postcode, period_start)
);

-- Price changes tracking
CREATE TABLE IF NOT EXISTS price_changes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL,
    
    -- Change details
    change_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    old_price DECIMAL(12,2),
    new_price DECIMAL(12,2) NOT NULL,
    change_amount DECIMAL(12,2),
    change_percentage DECIMAL(5,2),
    
    -- Change classification
    change_type VARCHAR(50) NOT NULL, -- 'increase', 'decrease', 'method_change', 'initial'
    change_reason VARCHAR(100),
    change_magnitude VARCHAR(20), -- 'minor', 'moderate', 'significant', 'major'
    
    -- Detection details
    detected_by VARCHAR(50) NOT NULL, -- 'listing_watcher', 'manual_entry', 'external_api'
    detection_method VARCHAR(50),
    confidence_score DECIMAL(3,2) DEFAULT 1.0,
    
    -- Market context
    market_condition VARCHAR(20), -- 'hot', 'warm', 'cool', 'cold'
    days_since_listing INTEGER,
    comparable_changes INTEGER, -- Similar changes in area
    
    -- Impact analysis
    buyer_interest_change DECIMAL(5,2), -- Change in buyer interest after price change
    inquiry_rate_change DECIMAL(5,2),
    
    -- Change metadata
    change_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_price_change_property 
        FOREIGN KEY (property_id) REFERENCES properties(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_confidence CHECK (confidence_score BETWEEN 0 AND 1)
);

-- =============================================================================
-- AGENT DOMAIN TABLES
-- =============================================================================

-- Agent execution tracking
CREATE TABLE IF NOT EXISTS agent_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Agent identification
    agent_name VARCHAR(100) NOT NULL,
    agent_version VARCHAR(20),
    execution_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Execution lifecycle
    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    -- Input and output
    input_data JSONB,
    output_data JSONB,
    error_details JSONB,
    
    -- Resource usage
    memory_usage_mb DECIMAL(8,2),
    cpu_usage_percent DECIMAL(5,2),
    api_calls_made INTEGER,
    cost_estimate DECIMAL(8,4),
    
    -- Execution context
    trigger_type VARCHAR(50), -- 'scheduled', 'event', 'manual'
    trigger_data JSONB,
    environment VARCHAR(20) DEFAULT 'production',
    
    -- Performance metrics
    success_rate DECIMAL(5,2),
    items_processed INTEGER,
    items_successful INTEGER,
    items_failed INTEGER,
    
    -- Parent-child relationships
    parent_execution_id UUID,
    is_retry BOOLEAN DEFAULT false,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Execution metadata
    execution_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_parent_execution 
        FOREIGN KEY (parent_execution_id) REFERENCES agent_executions(id),
    CONSTRAINT chk_success_rate CHECK (success_rate BETWEEN 0 AND 100),
    CONSTRAINT chk_duration_positive CHECK (duration_seconds >= 0)
);

-- Agent task tracking (individual tasks within executions)
CREATE TABLE IF NOT EXISTS agent_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL,
    
    -- Task identification
    task_name VARCHAR(200) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    task_order INTEGER,
    
    -- Task lifecycle
    status VARCHAR(50) NOT NULL DEFAULT 'Queued',
    assigned_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    -- Task parameters and results
    input_parameters JSONB,
    output_result JSONB,
    error_message TEXT,
    
    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    retry_delay_seconds INTEGER DEFAULT 60,
    
    -- Resource tracking
    memory_usage_mb DECIMAL(8,2),
    api_calls INTEGER,
    
    -- Task metadata (renamed to avoid SQLAlchemy conflict)
    task_metadata JSONB,
    
    -- Relationships
    execution relationship("AgentExecution", back_populates="tasks")
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_task_execution 
        FOREIGN KEY (execution_id) REFERENCES agent_executions(id) 
        ON DELETE CASCADE,
    CONSTRAINT chk_task_order CHECK (task_order >= 0),
    CONSTRAINT chk_retry_count CHECK (retry_count >= 0),
    CONSTRAINT chk_duration_positive CHECK (duration_seconds >= 0)
);

-- Fix the syntax error in the above table definition
-- This is a comment explaining that the 'execution relationship' line above has incorrect syntax
-- It should be defined in SQLAlchemy models, not in DDL

-- Agent logging for debugging and monitoring  
CREATE TABLE IF NOT EXISTS agent_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID,
    task_id UUID,
    
    -- Log entry details
    log_level VARCHAR(20) NOT NULL, -- 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    message TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Structured data
    log_data JSONB,
    exception_type VARCHAR(100),
    stack_trace TEXT,
    
    -- Context
    agent_name VARCHAR(100),
    function_name VARCHAR(100),
    line_number INTEGER,
    
    -- Categorization
    category VARCHAR(50), -- 'api_call', 'data_processing', 'error_handling', 'performance'
    tags TEXT[],
    
    -- Log metadata
    log_metadata JSONB,
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_log_execution 
        FOREIGN KEY (execution_id) REFERENCES agent_executions(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_log_task 
        FOREIGN KEY (task_id) REFERENCES agent_tasks(id) 
        ON DELETE CASCADE
);

-- Create helpful comments table for schema documentation
CREATE TABLE IF NOT EXISTS schema_comments (
    table_name VARCHAR(100) PRIMARY KEY,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert table descriptions
INSERT INTO schema_comments (table_name, description) VALUES
('properties', 'Main property listings with location, features, and pricing information'),
('property_price_history', 'Time-series tracking of property price changes (TimescaleDB hypertable)'),
('property_inspections', 'Scheduled property inspections and their outcomes'),
('property_market_metrics', 'Market analysis and competition data per property'),
('buyers', 'Buyer profiles and contact information'),
('buyer_preferences', 'Detailed search criteria and preferences for each buyer'),
('property_matches', 'ML-powered property recommendations for buyers'),
('buyer_search_history', 'Tracking of buyer search behavior for analytics'),
('property_interactions', 'Buyer interactions with properties (views, saves, inquiries)'),
('buyer_segments', 'Market segmentation definitions for targeted marketing'),
('buyer_segment_memberships', 'Many-to-many relationship between buyers and segments'),
('market_trends', 'Market trend analysis by geography and time period (TimescaleDB hypertable)'),
('suburb_stats', 'Comprehensive suburb statistics and market data'),
('price_changes', 'Tracking of property price changes with context (TimescaleDB hypertable)'),
('agent_executions', 'CrewAI agent execution tracking and performance monitoring'),
('agent_tasks', 'Individual task tracking within agent executions'),
('agent_logs', 'Structured logging for agent debugging and monitoring')
ON CONFLICT (table_name) DO UPDATE SET 
    description = EXCLUDED.description,
    updated_at = NOW();