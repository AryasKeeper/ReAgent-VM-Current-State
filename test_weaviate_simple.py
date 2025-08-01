#!/usr/bin/env python3
"""
Simple Weaviate Vector Search Test

Quick validation of core Weaviate functionality with ReAgent.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.vector_db.client import WeaviateClient
from src.config.settings import get_settings


async def test_weaviate_connection():
    """Test basic Weaviate connectivity."""
    print("🔍 Testing Weaviate connection...")
    
    try:
        # Initialize client
        settings = get_settings()
        print(f"Connecting to: {settings.weaviate.url}")
        
        client = WeaviateClient()
        await client.connect()
        
        # Health check
        health = await client.health_check()
        print(f"Health status: {health}")
        
        if health.get("ready"):
            print("✅ Weaviate connection successful!")
            return True
        else:
            print("❌ Weaviate not ready")
            return False
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


async def test_schema_operations():
    """Test schema creation and management."""
    print("\n🔧 Testing schema operations...")
    
    try:
        client = WeaviateClient()
        await client.connect()
        
        # Test schema
        test_schema = {
            "class": "TestProperty",
            "description": "Test property schema",
            "vectorizer": "none",
            "properties": [
                {"name": "address", "dataType": ["text"]},
                {"name": "price", "dataType": ["number"]},
                {"name": "bedrooms", "dataType": ["int"]}
            ]
        }
        
        # Create schema
        success = await client.create_schema(test_schema)
        if success:
            print("✅ Schema creation successful!")
            
            # Clean up
            await client.delete_schema("TestProperty")
            print("✅ Schema cleanup successful!")
            return True
        else:
            print("❌ Schema creation failed")
            return False
            
    except Exception as e:
        print(f"❌ Schema operations failed: {e}")
        return False


async def test_basic_operations():
    """Test basic CRUD operations."""
    print("\n📝 Testing basic operations...")
    
    try:
        client = WeaviateClient()
        await client.connect()
        
        # Create test schema
        schema = {
            "class": "TestData",
            "vectorizer": "none",
            "properties": [
                {"name": "name", "dataType": ["text"]},
                {"name": "value", "dataType": ["number"]}
            ]
        }
        
        await client.create_schema(schema)
        
        # Insert test object
        test_data = {"name": "test_property", "value": 100}
        test_vector = [0.1, 0.2, 0.3, 0.4, 0.5]  # Simple test vector
        
        object_id = await client.insert_object(
            class_name="TestData",
            properties=test_data,
            vector=test_vector
        )
        
        if object_id:
            print(f"✅ Object inserted: {object_id}")
            
            # Retrieve object
            retrieved = await client.get_object("TestData", object_id)
            if retrieved:
                print("✅ Object retrieval successful!")
                
                # Count objects
                count = await client.get_object_count("TestData")
                print(f"✅ Object count: {count}")
                
                # Clean up
                await client.delete_schema("TestData")
                return True
            else:
                print("❌ Object retrieval failed")
                return False
        else:
            print("❌ Object insertion failed")
            return False
            
    except Exception as e:
        print(f"❌ Basic operations failed: {e}")
        return False


async def main():
    """Run simple Weaviate tests."""
    print("🚀 Starting Simple Weaviate Validation")
    print("=" * 50)
    
    results = []
    
    # Test connection
    results.append(await test_weaviate_connection())
    
    # Test schema operations
    results.append(await test_schema_operations())
    
    # Test basic operations
    results.append(await test_basic_operations())
    
    # Summary
    print("\n📊 TEST SUMMARY")
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("✅ All tests passed - Weaviate is ready!")
    else:
        print("❌ Some tests failed - check configuration")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)