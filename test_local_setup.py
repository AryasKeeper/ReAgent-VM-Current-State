#!/usr/bin/env python3
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
    print("\nTesting mock services configuration...")
    
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
        print("\n🎉 Local development setup is ready!")
        print("\nNext steps:")
        print("1. Install Python dependencies: pip install -r requirements.txt")
        print("2. Run API server: python -m uvicorn src.api.main:app --reload")
        print("3. Test agents: python -m src.agents.listing_watcher.demo")
    else:
        print("\n❌ Setup has issues. Please check the errors above.")
