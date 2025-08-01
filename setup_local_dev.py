#!/usr/bin/env python3
"""
ReAgent Sydney - Local Development Setup Script

This script sets up a local development environment without Docker.
It creates SQLite databases and mock services for development.
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

def setup_sqlite_database():
    """Create SQLite database for local development."""
    print("Setting up SQLite database for local development...")
    
    db_path = Path("data/reagent_dev.db")
    db_path.parent.mkdir(exist_ok=True)
    
    # Create database connection
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Create basic tables for development
    schema_sql = """
    -- Properties table
    CREATE TABLE IF NOT EXISTS properties (
        id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
        source TEXT NOT NULL,
        source_id TEXT,
        source_url TEXT,
        
        -- Property details
        title TEXT,
        description TEXT,
        property_type TEXT,
        
        -- Location
        address_line_1 TEXT,
        address_line_2 TEXT,
        suburb TEXT,
        postcode TEXT,
        state TEXT DEFAULT 'NSW',
        country TEXT DEFAULT 'Australia',
        
        -- Geographic coordinates
        latitude REAL,
        longitude REAL,
        
        -- Property features
        bedrooms INTEGER,
        bathrooms INTEGER,
        car_spaces INTEGER,
        land_size_sqm REAL,
        building_size_sqm REAL,
        
        -- Pricing
        price_guide DECIMAL(12,2),
        price_display TEXT,
        listing_type TEXT CHECK (listing_type IN ('sale', 'rent', 'auction')),
        listing_status TEXT CHECK (listing_status IN ('active', 'sold', 'withdrawn', 'expired')),
        
        -- Dates
        listing_date DATETIME,
        sold_date DATETIME,
        auction_date DATETIME,
        
        -- Metadata
        features TEXT, -- JSON array
        image_urls TEXT, -- JSON array
        agent_info TEXT, -- JSON object
        
        -- Timestamps
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        deleted_at DATETIME
    );
    
    -- Buyers table
    CREATE TABLE IF NOT EXISTS buyers (
        id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
        email TEXT UNIQUE NOT NULL,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        
        -- Preferences
        max_budget DECIMAL(12,2),
        min_budget DECIMAL(12,2),
        preferred_suburbs TEXT, -- JSON array
        property_types TEXT, -- JSON array
        min_bedrooms INTEGER,
        max_bedrooms INTEGER,
        
        -- Search criteria
        search_criteria TEXT, -- JSON object
        notification_preferences TEXT, -- JSON object
        
        -- Status
        is_active BOOLEAN DEFAULT 1,
        
        -- Timestamps
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Property matches table
    CREATE TABLE IF NOT EXISTS property_matches (
        id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
        buyer_id TEXT REFERENCES buyers(id),
        property_id TEXT REFERENCES properties(id),
        
        -- Match details
        match_score REAL CHECK (match_score >= 0.0 AND match_score <= 1.0),
        match_reasons TEXT, -- JSON array
        
        -- Status
        status TEXT CHECK (status IN ('pending', 'viewed', 'interested', 'not_interested')),
        
        -- Timestamps
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Market trends table
    CREATE TABLE IF NOT EXISTS market_trends (
        id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
        suburb TEXT NOT NULL,
        postcode TEXT,
        
        -- Metrics
        avg_price DECIMAL(12,2),
        median_price DECIMAL(12,2),
        price_change_30d REAL,
        price_change_90d REAL,
        
        -- Activity
        listings_count INTEGER,
        sales_count INTEGER,
        days_on_market_avg REAL,
        
        -- Analysis period
        period_start DATETIME,
        period_end DATETIME,
        
        -- Timestamps
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_properties_suburb ON properties(suburb);
    CREATE INDEX IF NOT EXISTS idx_properties_postcode ON properties(postcode);
    CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price_guide);
    CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(listing_status);
    CREATE INDEX IF NOT EXISTS idx_buyers_active ON buyers(is_active);
    CREATE INDEX IF NOT EXISTS idx_matches_buyer ON property_matches(buyer_id);
    CREATE INDEX IF NOT EXISTS idx_matches_property ON property_matches(property_id);
    """
    
    cursor.executescript(schema_sql)
    
    # Insert sample data
    sample_data_sql = """
    -- Sample properties
    INSERT OR IGNORE INTO properties (
        source, source_id, title, property_type, suburb, postcode,
        bedrooms, bathrooms, price_guide, listing_type, listing_status,
        latitude, longitude, listing_date
    ) VALUES 
    ('domain', 'DOM001', '3 Bedroom House in Surry Hills', 'House', 'Surry Hills', '2010', 
     3, 2, 1200000, 'sale', 'active', -33.8889, 151.2093, datetime('now', '-10 days')),
    ('rea', 'REA001', 'Modern Apartment with Harbour Views', 'Unit', 'Milsons Point', '2061',
     2, 2, 950000, 'sale', 'active', -33.8472, 151.2108, datetime('now', '-5 days')),
    ('domain', 'DOM002', 'Family Home with Garden', 'House', 'Leichhardt', '2040',
     4, 3, 1450000, 'sale', 'active', -33.8833, 151.1500, datetime('now', '-15 days'));
    
    -- Sample buyers
    INSERT OR IGNORE INTO buyers (
        email, first_name, last_name, max_budget, preferred_suburbs,
        property_types, min_bedrooms, is_active
    ) VALUES
    ('john.smith@email.com', 'John', 'Smith', 1300000, '["Surry Hills", "Redfern", "Darlinghurst"]',
     '["House", "Townhouse"]', 3, 1),
    ('sarah.jones@email.com', 'Sarah', 'Jones', 1000000, '["Milsons Point", "North Sydney", "Neutral Bay"]',
     '["Unit", "Apartment"]', 2, 1);
    
    -- Sample market trends
    INSERT OR IGNORE INTO market_trends (
        suburb, postcode, avg_price, median_price, price_change_30d,
        listings_count, sales_count, days_on_market_avg,
        period_start, period_end
    ) VALUES
    ('Surry Hills', '2010', 1250000, 1200000, 2.5, 45, 12, 28.5,
     datetime('now', '-30 days'), datetime('now')),
    ('Milsons Point', '2061', 980000, 950000, 1.8, 23, 8, 32.1,
     datetime('now', '-30 days'), datetime('now'));
    """
    
    cursor.executescript(sample_data_sql)
    conn.commit()
    conn.close()
    
    print(f"✅ SQLite database created at: {db_path}")
    return str(db_path.absolute())

def create_mock_services():
    """Create mock service configurations for local development."""
    print("Setting up mock services configuration...")
    
    # Create mock Redis configuration
    mock_config = {
        "services": {
            "redis": {
                "enabled": False,
                "mock": True,
                "data": {}
            },
            "weaviate": {
                "enabled": False,
                "mock": True,
                "url": "http://localhost:8080",
                "collections": []
            }
        },
        "external_apis": {
            "domain": {
                "mock": True,
                "rate_limit": 1000,
                "sample_responses": {
                    "search": "mock_responses/domain_search.json",
                    "listing": "mock_responses/domain_listing.json"
                }
            },
            "realestate": {
                "mock": True,
                "rate_limit": 500,
                "sample_responses": {
                    "search": "mock_responses/rea_search.json",
                    "listing": "mock_responses/rea_listing.json"
                }
            }
        }
    }
    
    # Create mock responses directory
    mock_dir = Path("mock_responses")
    mock_dir.mkdir(exist_ok=True)
    
    # Save mock configuration
    with open("mock_services.json", "w") as f:
        json.dump(mock_config, f, indent=2)
    
    # Create sample API responses
    domain_search_response = {
        "listings": [
            {
                "id": "DOM001",
                "headline": "3 Bedroom House in Surry Hills",
                "propertyType": "House",
                "propertyDetails": {
                    "displayableAddress": "123 Crown Street, Surry Hills NSW 2010",
                    "suburb": "Surry Hills",
                    "postcode": "2010",
                    "state": "NSW",
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "latitude": -33.8889,
                    "longitude": 151.2093
                },
                "priceDetails": {
                    "displayPrice": "$1,200,000",
                    "price": 1200000
                },
                "listing": {
                    "listingType": "Sale"
                }
            }
        ]
    }
    
    with open(mock_dir / "domain_search.json", "w") as f:
        json.dump(domain_search_response, f, indent=2)
    
    print("✅ Mock services configuration created")

def update_env_for_local():
    """Update .env file for local development."""
    print("Updating .env file for local development...")
    
    db_path = Path("data/reagent_dev.db").absolute()
    
    env_updates = f"""
# Local development overrides
DATABASE_URL=sqlite:///{db_path}
REDIS_URL=mock://localhost:6379/0
WEAVIATE_URL=mock://localhost:8080

# Enable mock services
MOCK_EXTERNAL_APIS=true
MOCK_SERVICES_CONFIG=mock_services.json

# Development flags
DEBUG=true
ENABLE_DEBUG_LOGS=true
ENABLE_API_DOCS=true
"""
    
    with open(".env", "a") as f:
        f.write(env_updates)
    
    print("✅ Environment configuration updated for local development")

def create_test_script():
    """Create a test script to verify the setup."""
    test_script = """#!/usr/bin/env python3
'''Test script for local ReAgent Sydney setup'''

import sqlite3
import json
from pathlib import Path

def test_database():
    print("Testing database connection...")
    db_path = Path("data/reagent_dev.db")
    
    if not db_path.exists():
        print("❌ Database not found")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Test basic query
    cursor.execute("SELECT COUNT(*) FROM properties")
    count = cursor.fetchone()[0]
    print(f"✅ Found {count} properties in database")
    
    # Test sample data
    cursor.execute("SELECT title, suburb, price_guide FROM properties LIMIT 3")
    properties = cursor.fetchall()
    
    print("Sample properties:")
    for prop in properties:
        print(f"  - {prop[0]} in {prop[1]} - ${prop[2]:,.0f}")
    
    conn.close()
    return True

def test_mock_config():
    print("\\nTesting mock services configuration...")
    
    if not Path("mock_services.json").exists():
        print("❌ Mock services config not found")
        return False
    
    with open("mock_services.json") as f:
        config = json.load(f)
    
    print("✅ Mock services configuration loaded")
    print(f"  - Redis mock: {config['services']['redis']['mock']}")
    print(f"  - Weaviate mock: {config['services']['weaviate']['mock']}")
    print(f"  - Domain API mock: {config['external_apis']['domain']['mock']}")
    
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("ReAgent Sydney - Local Setup Test")
    print("=" * 50)
    
    db_ok = test_database()
    mock_ok = test_mock_config()
    
    if db_ok and mock_ok:
        print("\\n🎉 Local development setup is ready!")
        print("\\nNext steps:")
        print("1. Install Python dependencies: pip install -r requirements.txt")
        print("2. Run API server: python -m uvicorn src.api.main:app --reload")
        print("3. Test agents: python -m src.agents.listing_watcher.demo")
    else:
        print("\\n❌ Setup has issues. Please check the errors above.")
"""
    
    with open("test_local_setup.py", "w") as f:
        f.write(test_script)
    
    os.chmod("test_local_setup.py", 0o755)
    print("✅ Test script created: test_local_setup.py")

def main():
    """Main setup function."""
    print("=" * 60)
    print("REAGENT SYDNEY - LOCAL DEVELOPMENT SETUP")
    print("=" * 60)
    print()
    print("This script sets up ReAgent Sydney for local development")
    print("without requiring Docker or external services.")
    print()
    
    try:
        # Setup database
        db_path = setup_sqlite_database()
        
        # Create mock services
        create_mock_services()
        
        # Update environment
        update_env_for_local()
        
        # Create test script
        create_test_script()
        
        print("\n" + "=" * 60)
        print("✅ LOCAL DEVELOPMENT SETUP COMPLETE!")
        print("=" * 60)
        print(f"""
Setup Summary:
- ✅ SQLite database: {db_path}
- ✅ Mock services configuration created
- ✅ Environment variables updated
- ✅ Test script created

Next Steps:
1. Run test: python test_local_setup.py
2. Install dependencies: pip install -r requirements.txt
3. Test API connections: python test_api_connections.py
4. Start development server: python -m uvicorn src.api.main:app --reload

The system is now ready for local development! 🚀
""")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()