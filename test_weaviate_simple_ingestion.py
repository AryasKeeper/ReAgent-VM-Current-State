#!/usr/bin/env python3
"""
Simple Weaviate Data Ingestion Test

Tests basic data ingestion into Weaviate without vectorization
to validate the core data pipeline functionality.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any

from src.core.vector_db.client import WeaviateClient
from src.config.settings import Settings
import structlog

logger = structlog.get_logger(__name__)


async def test_simple_ingestion():
    """Test simple data ingestion into Weaviate."""
    print("=== Simple Weaviate Data Ingestion Test ===")
    
    # Configure test settings
    settings = Settings()
    settings.weaviate.url = "http://localhost:8080"
    settings.weaviate.api_key = None
    
    client = WeaviateClient(settings)
    
    try:
        # Connect to Weaviate
        print("1. Connecting to Weaviate...")
        await client.connect()
        health = await client.health_check()
        print(f"   Connection: {'✅ OK' if health['ready'] else '❌ FAILED'}")
        
        if not health['ready']:
            print("   Error: Weaviate is not ready")
            return False
        
        # Clean up existing test classes
        print("2. Cleaning up existing test schemas...")
        await client.delete_schema("TestProperty")
        await client.delete_schema("TestBuyer")
        
        # Create simplified schemas without vectorization
        print("3. Creating test schemas...")
        
        property_schema = {
            "class": "TestProperty",
            "description": "Test property schema without vectors",
            "properties": [
                {
                    "name": "listing_id",
                    "dataType": ["string"],
                    "description": "Listing identifier"
                },
                {
                    "name": "title",
                    "dataType": ["text"],
                    "description": "Property title"
                },
                {
                    "name": "suburb",
                    "dataType": ["string"],
                    "description": "Suburb name"
                },
                {
                    "name": "price",
                    "dataType": ["number"],
                    "description": "Property price"
                },
                {
                    "name": "bedrooms",
                    "dataType": ["int"],
                    "description": "Number of bedrooms"
                }
            ],
            "vectorIndexConfig": {
                "skip": True  # Disable vectorization
            }
        }
        
        buyer_schema = {
            "class": "TestBuyer",
            "description": "Test buyer schema without vectors",
            "properties": [
                {
                    "name": "buyer_id",
                    "dataType": ["string"],
                    "description": "Buyer identifier"
                },
                {
                    "name": "full_name",
                    "dataType": ["string"],
                    "description": "Buyer name"
                },
                {
                    "name": "max_price",
                    "dataType": ["number"],
                    "description": "Maximum budget"
                },
                {
                    "name": "buyer_type",
                    "dataType": ["string"],
                    "description": "Buyer type"
                }
            ],
            "vectorIndexConfig": {
                "skip": True  # Disable vectorization
            }
        }
        
        prop_created = await client.create_schema(property_schema)
        buyer_created = await client.create_schema(buyer_schema)
        print(f"   Property schema: {'✅ CREATED' if prop_created else '❌ FAILED'}")
        print(f"   Buyer schema: {'✅ CREATED' if buyer_created else '❌ FAILED'}")
        
        if not (prop_created and buyer_created):
            print("   Error: Failed to create schemas")
            return False
        
        # Create test data
        print("4. Creating test data...")
        
        test_properties = [
            {
                "id": str(uuid.uuid4()),
                "listing_id": "TEST_PROP_001",
                "title": "Beautiful Bondi Apartment",
                "suburb": "Bondi",
                "price": 1200000,
                "bedrooms": 2
            },
            {
                "id": str(uuid.uuid4()),
                "listing_id": "TEST_PROP_002", 
                "title": "Spacious Surry Hills House",
                "suburb": "Surry Hills",
                "price": 1800000,
                "bedrooms": 3
            },
            {
                "id": str(uuid.uuid4()),
                "listing_id": "TEST_PROP_003",
                "title": "Modern Parramatta Unit",
                "suburb": "Parramatta", 
                "price": 850000,
                "bedrooms": 2
            }
        ]
        
        test_buyers = [
            {
                "id": str(uuid.uuid4()),
                "buyer_id": str(uuid.uuid4()),
                "full_name": "John Smith",
                "max_price": 1000000,
                "buyer_type": "first_home_buyer"
            },
            {
                "id": str(uuid.uuid4()),
                "buyer_id": str(uuid.uuid4()),
                "full_name": "Mary Johnson",
                "max_price": 2000000,
                "buyer_type": "upgrader"
            }
        ]
        
        print(f"   Created {len(test_properties)} properties and {len(test_buyers)} buyers")
        
        # Test batch insertion
        print("5. Testing batch insertion...")
        
        start_time = datetime.now()
        prop_ids = await client.batch_insert_objects("TestProperty", test_properties, batch_size=10)
        buyer_ids = await client.batch_insert_objects("TestBuyer", test_buyers, batch_size=10)
        end_time = datetime.now()
        
        insertion_time = (end_time - start_time).total_seconds()
        
        print(f"   Properties inserted: {len(prop_ids)}/{len(test_properties)}")
        print(f"   Buyers inserted: {len(buyer_ids)}/{len(test_buyers)}")
        print(f"   Insertion time: {insertion_time:.3f}s")
        
        if len(prop_ids) != len(test_properties) or len(buyer_ids) != len(test_buyers):
            print("   Error: Not all objects were inserted")
            return False
        
        # Test object counts
        print("6. Verifying object counts...")
        
        prop_count = await client.get_object_count("TestProperty")
        buyer_count = await client.get_object_count("TestBuyer")
        
        print(f"   Property count: {prop_count}")
        print(f"   Buyer count: {buyer_count}")
        
        if prop_count != len(test_properties) or buyer_count != len(test_buyers):
            print("   Error: Object counts don't match")
            return False
        
        # Test simple queries
        print("7. Testing simple queries...")
        
        # Query all properties
        all_props_query = client._client.query.get("TestProperty", ["listing_id", "title", "suburb", "price"]).do()
        all_props = all_props_query.get("data", {}).get("Get", {}).get("TestProperty", [])
        
        # Query properties by suburb
        bondi_query = client._client.query.get("TestProperty", ["listing_id", "title", "suburb"]).with_where({
            "path": ["suburb"],
            "operator": "Equal",
            "valueString": "Bondi"
        }).do()
        bondi_props = bondi_query.get("data", {}).get("Get", {}).get("TestProperty", [])
        
        # Query all buyers
        all_buyers_query = client._client.query.get("TestBuyer", ["buyer_id", "full_name", "buyer_type"]).do()
        all_buyers = all_buyers_query.get("data", {}).get("Get", {}).get("TestBuyer", [])
        
        # Query buyers by type
        first_home_query = client._client.query.get("TestBuyer", ["buyer_id", "full_name"]).with_where({
            "path": ["buyer_type"],
            "operator": "Equal",
            "valueString": "first_home_buyer"
        }).do()
        first_home_buyers = first_home_query.get("data", {}).get("Get", {}).get("TestBuyer", [])
        
        print(f"   All properties query: {len(all_props)} results")
        print(f"   Bondi properties query: {len(bondi_props)} results")
        print(f"   All buyers query: {len(all_buyers)} results")
        print(f"   First home buyers query: {len(first_home_buyers)} results")
        
        # Verify query results
        if len(all_props) == 3 and len(bondi_props) == 1 and len(all_buyers) == 2 and len(first_home_buyers) == 1:
            print("   ✅ All queries returned expected results")
        else:
            print("   ❌ Query results don't match expectations")
            return False
        
        # Test individual object retrieval
        print("8. Testing object retrieval...")
        
        if prop_ids:
            retrieved_prop = await client.get_object("TestProperty", prop_ids[0])
            if retrieved_prop:
                print(f"   ✅ Retrieved property: {retrieved_prop['properties']['title']}")
            else:
                print("   ❌ Failed to retrieve property")
                return False
        
        # Test object updates
        print("9. Testing object updates...")
        
        if prop_ids:
            update_success = await client.update_object(
                "TestProperty",
                prop_ids[0],
                {"price": 1250000, "title": "Updated Beautiful Bondi Apartment"}
            )
            
            if update_success:
                updated_prop = await client.get_object("TestProperty", prop_ids[0])
                if updated_prop and updated_prop['properties']['price'] == 1250000:
                    print("   ✅ Object update successful")
                else:
                    print("   ❌ Object update verification failed")
                    return False
            else:
                print("   ❌ Object update failed")
                return False
        
        print("\n=== TEST RESULTS ===")
        print("✅ Connection: PASS")
        print("✅ Schema Creation: PASS")
        print("✅ Batch Insertion: PASS")
        print("✅ Object Counting: PASS")
        print("✅ Query Operations: PASS")
        print("✅ Object Retrieval: PASS")
        print("✅ Object Updates: PASS")
        print(f"\n✅ ALL TESTS PASSED - Data pipeline is working correctly!")
        print(f"   Performance: {insertion_time:.3f}s for {len(test_properties) + len(test_buyers)} objects")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        logger.error("Simple ingestion test failed", error=str(e), exc_info=True)
        return False
    
    finally:
        if client:
            await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_simple_ingestion())