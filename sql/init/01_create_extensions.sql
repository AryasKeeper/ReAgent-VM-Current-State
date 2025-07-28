-- ReAgent Sydney - Database Initialization
-- Create necessary PostgreSQL and TimescaleDB extensions

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable PostGIS for geographic operations (optional but useful for location features)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable full text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable case-insensitive text matching
CREATE EXTENSION IF NOT EXISTS citext;

-- Create custom types
DO $$ 
BEGIN
    -- Property types enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'property_type_enum') THEN
        CREATE TYPE property_type_enum AS ENUM (
            'house', 'apartment', 'townhouse', 'villa', 'duplex', 
            'terrace', 'studio', 'penthouse', 'land', 'other'
        );
    END IF;
    
    -- Listing status enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'listing_status_enum') THEN
        CREATE TYPE listing_status_enum AS ENUM (
            'active', 'sold', 'withdrawn', 'expired', 'off_market', 'under_contract'
        );
    END IF;
    
    -- Price change type enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'price_change_enum') THEN
        CREATE TYPE price_change_enum AS ENUM (
            'increase', 'decrease', 'method_change', 'initial'
        );
    END IF;
    
    -- Urgency level enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'urgency_level_enum') THEN
        CREATE TYPE urgency_level_enum AS ENUM (
            'low', 'medium', 'high', 'urgent'
        );
    END IF;
END $$;