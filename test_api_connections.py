#!/usr/bin/env python3
"""
Simple API connection test for ReAgent Sydney
Tests basic connectivity to external APIs
"""

import asyncio
import aiohttp
import os
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

async def test_domain_api():
    """Test Domain API connection."""
    api_key = os.getenv('DOMAIN_API_KEY', '')
    
    if not api_key or api_key == 'REPLACE_WITH_ACTUAL_API_KEY':
        print("❌ Domain API: Not configured (API key missing)")
        return False
    
    try:
        headers = {
            'X-Api-Key': api_key,
            'Accept': 'application/json',
            'User-Agent': 'ReAgent-Sydney/0.1.0'
        }
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Simple test endpoint
            url = "https://api.domain.com.au/v1/listings/residential/_search"
            params = {"pageSize": 1, "postCodes": "2000"}
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    print("✅ Domain API: Connected successfully")
                    return True
                elif response.status == 401:
                    print("❌ Domain API: Authentication failed (check API key)")
                    return False
                else:
                    print(f"⚠️  Domain API: Unexpected response ({response.status})")
                    return False
                    
    except Exception as e:
        print(f"❌ Domain API: Connection failed - {e}")
        return False

async def test_realestate_api():
    """Test RealEstate.com.au API connection."""
    api_key = os.getenv('REA_API_KEY', '')
    
    if not api_key or api_key == 'REPLACE_WITH_ACTUAL_API_KEY':
        print("❌ RealEstate API: Not configured (API key missing)")
        return False
    
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'User-Agent': 'ReAgent-Sydney/0.1.0'
        }
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Simple test endpoint
            url = "https://services.realestate.com.au/v1/listings/residential/_search"
            params = {"pageSize": 1, "localities": ["2000"]}
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    print("✅ RealEstate API: Connected successfully")
                    return True
                elif response.status == 401:
                    print("❌ RealEstate API: Authentication failed (check API key)")
                    return False
                else:
                    print(f"⚠️  RealEstate API: Unexpected response ({response.status})")
                    return False
                    
    except Exception as e:
        print(f"❌ RealEstate API: Connection failed - {e}")
        return False

async def test_openai_api():
    """Test OpenAI API connection."""
    api_key = os.getenv('OPENAI_API_KEY', '')
    
    if not api_key or api_key == 'REPLACE_WITH_ACTUAL_API_KEY':
        print("❌ OpenAI API: Not configured (API key missing)")
        return False
    
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Simple test endpoint
            url = "https://api.openai.com/v1/models"
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    print("✅ OpenAI API: Connected successfully")
                    return True
                elif response.status == 401:
                    print("❌ OpenAI API: Authentication failed (check API key)")
                    return False
                else:
                    print(f"⚠️  OpenAI API: Unexpected response ({response.status})")
                    return False
                    
    except Exception as e:
        print(f"❌ OpenAI API: Connection failed - {e}")
        return False

async def test_corelogic_api():
    """Test CoreLogic (Cotality) API connectivity."""
    client_id = os.getenv('CORELOGIC_API_KEY', '')
    client_secret = os.getenv('CORELOGIC_SECRET', '')
    
    if not client_id or client_id == 'REPLACE_WITH_ACTUAL_API_KEY':
        print("❌ CoreLogic API: API key not configured")
        return False
    
    if not client_secret:
        print("❌ CoreLogic API: Client secret not configured")
        return False
    
    try:
        # Import the CoreLogic client
        from src.services.external_apis.corelogic_client import CoreLogicClient
        
        async with CoreLogicClient(client_id, client_secret) as client:
            # Test with a simple property search
            suggestions = await client.suggest_properties("Sydney NSW")
            
            print(f"✅ CoreLogic API: Connected successfully ({len(suggestions)} suggestions found)")
            
            # Show first suggestion as example
            if suggestions:
                first = suggestions[0]
                print(f"   Example: {first.suggestion} (ID: {first.property_id})")
            
            return True
            
    except ImportError as e:
        print(f"❌ CoreLogic API: Import error - {e}")
        return False
    except Exception as e:
        print(f"❌ CoreLogic API: Connection failed - {e}")
        return False

async def test_database_connection():
    """Test database connectivity."""
    database_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://reagent:password@localhost:5432/reagent')
    
    # Handle SQLite for local development
    if database_url.startswith('sqlite://'):
        try:
            import sqlite3
            db_path = database_url.replace('sqlite://', '')
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM properties')
            count = cursor.fetchone()[0]
            conn.close()
            
            print(f"✅ SQLite Database: Connected successfully ({count} properties)")
            return True
            
        except Exception as e:
            print(f"❌ SQLite Database: Connection failed - {e}")
            return False
    
    # Handle PostgreSQL
    try:
        import asyncpg
        
        # Convert to asyncpg format
        db_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
        
        conn = await asyncpg.connect(db_url)
        await conn.execute('SELECT 1')
        await conn.close()
        
        print("✅ PostgreSQL: Connected successfully")
        return True
        
    except ImportError:
        print("⚠️  PostgreSQL: asyncpg not installed (pip install asyncpg)")
        return False
    except Exception as e:
        print(f"❌ PostgreSQL: Connection failed - {e}")
        return False

async def test_redis_connection():
    """Test Redis connectivity."""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Handle mock Redis for local development
    if redis_url.startswith('mock://'):
        print("✅ Redis (Mock): Mock service configured for local development")
        return True
    
    try:
        import redis.asyncio as redis
        
        client = redis.from_url(redis_url)
        await client.ping()
        await client.close()
        
        print("✅ Redis: Connected successfully")
        return True
        
    except ImportError:
        print("⚠️  Redis: redis package not installed (pip install redis)")
        return False
    except Exception as e:
        print(f"❌ Redis: Connection failed - {e}")
        return False

async def test_weaviate_connection():
    """Test Weaviate connectivity."""
    weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
    
    # Handle mock Weaviate for local development
    if weaviate_url.startswith('mock://'):
        print("✅ Weaviate (Mock): Mock service configured for local development")
        return True
    
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{weaviate_url}/v1/meta") as response:
                if response.status == 200:
                    print("✅ Weaviate: Connected successfully")
                    return True
                else:
                    print(f"⚠️  Weaviate: Unexpected response ({response.status})")
                    return False
                    
    except Exception as e:
        print(f"❌ Weaviate: Connection failed - {e}")
        return False

async def main():
    """Run all connection tests."""
    print("=" * 60)
    print("REAGENT SYDNEY - API CONNECTION TEST")
    print("=" * 60)
    print()
    
    # Test infrastructure
    print("Infrastructure Services:")
    db_ok = await test_database_connection()
    redis_ok = await test_redis_connection()
    weaviate_ok = await test_weaviate_connection()
    
    print("\nExternal APIs:")
    domain_ok = await test_domain_api()
    rea_ok = await test_realestate_api()
    openai_ok = await test_openai_api()
    
    # Test CoreLogic API
    corelogic_ok = await test_corelogic_api()
    
    # Check remaining APIs
    print("\nOther APIs (not implemented yet):")
    nsw_lpi_key = os.getenv('NSW_LPI_API_KEY', '')
    
    if nsw_lpi_key and nsw_lpi_key != 'REPLACE_WITH_ACTUAL_API_KEY':
        print("🚧 NSW LPI API: Key configured (client not implemented)")
    else:
        print("❌ NSW LPI API: Not configured")
    
    print("\n" + "=" * 60)
    
    # Summary
    infrastructure_ready = db_ok and redis_ok and weaviate_ok
    apis_ready = domain_ok and rea_ok and openai_ok
    
    if infrastructure_ready and apis_ready:
        print("🎉 SYSTEM READY: All core services are connected!")
        print("Next step: Run database migrations and start agents")
        return 0
    elif infrastructure_ready and (domain_ok or rea_ok):
        print("⚠️  PARTIAL READY: Core services up, some APIs need configuration")
        print("You can proceed with limited functionality")
        return 0
    else:
        print("❌ NOT READY: Critical services need configuration")
        print("Fix the issues above before proceeding")
        return 1

if __name__ == "__main__":
    import sys
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)