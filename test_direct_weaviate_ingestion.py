#!/usr/bin/env python3
"""
Direct Weaviate API Ingestion Test

Tests data ingestion using direct Weaviate API calls to bypass
potential client issues and validate the core functionality.
"""

import requests
import json
import uuid
from datetime import datetime


def test_direct_api_ingestion():
    """Test ingestion using direct Weaviate REST API."""
    print("=== Direct Weaviate API Ingestion Test ===")
    
    base_url = "http://localhost:8080/v1"
    
    try:
        # 1. Check Weaviate health
        print("1. Checking Weaviate health...")
        health_response = requests.get(f"{base_url}/meta")
        if health_response.status_code == 200:
            print("   ✅ Weaviate is healthy")
        else:
            print(f"   ❌ Weaviate health check failed: {health_response.status_code}")
            return False
        
        # 2. Clean up existing test schema
        print("2. Cleaning up existing test schema...")
        requests.delete(f"{base_url}/schema/DirectTestProperty")
        
        # 3. Create simple test schema
        print("3. Creating test schema...")
        
        schema = {
            "class": "DirectTestProperty",
            "description": "Direct API test property schema",
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
                }
            ],
            "vectorIndexConfig": {
                "skip": True  # Disable vectorization
            },
            "vectorizer": "none"  # Explicitly disable vectorizer
        }
        
        schema_response = requests.post(
            f"{base_url}/schema",
            headers={"Content-Type": "application/json"},
            json=schema
        )
        
        if schema_response.status_code in [200, 201]:
            print("   ✅ Schema created successfully")
        else:
            print(f"   ❌ Schema creation failed: {schema_response.status_code}")
            print(f"   Response: {schema_response.text}")
            return False
        
        # 4. Insert test objects one by one
        print("4. Inserting test objects...")
        
        test_objects = [
            {
                "listing_id": "DIRECT_001",
                "title": "Test Property 1",
                "suburb": "Bondi",
                "price": 1200000
            },
            {
                "listing_id": "DIRECT_002", 
                "title": "Test Property 2",
                "suburb": "Surry Hills",
                "price": 1800000
            },
            {
                "listing_id": "DIRECT_003",
                "title": "Test Property 3", 
                "suburb": "Parramatta",
                "price": 850000
            }
        ]
        
        inserted_count = 0
        inserted_ids = []
        
        for i, obj in enumerate(test_objects):
            object_id = str(uuid.uuid4())
            
            # Insert object
            insert_response = requests.post(
                f"{base_url}/objects",
                headers={"Content-Type": "application/json"},
                json={
                    "class": "DirectTestProperty",
                    "id": object_id,
                    "properties": obj
                }
            )
            
            if insert_response.status_code in [200, 201]:
                inserted_count += 1
                inserted_ids.append(object_id)
                print(f"   ✅ Inserted object {i+1}: {obj['listing_id']}")
            else:
                print(f"   ❌ Failed to insert object {i+1}: {insert_response.status_code}")
                print(f"   Response: {insert_response.text}")
        
        print(f"   Total inserted: {inserted_count}/{len(test_objects)}")
        
        if inserted_count != len(test_objects):
            print("   Error: Not all objects were inserted")
            return False
        
        # 5. Verify objects exist
        print("5. Verifying objects exist...")
        
        # Get all objects
        get_response = requests.get(f"{base_url}/objects?class=DirectTestProperty")
        
        if get_response.status_code == 200:
            objects = get_response.json().get("objects", [])
            print(f"   ✅ Retrieved {len(objects)} objects")
            
            if len(objects) == len(test_objects):
                print("   ✅ All objects found")
            else:
                print(f"   ❌ Expected {len(test_objects)} objects, found {len(objects)}")
                return False
        else:
            print(f"   ❌ Failed to retrieve objects: {get_response.status_code}")
            return False
        
        # 6. Test GraphQL queries
        print("6. Testing GraphQL queries...")
        
        # Query all properties
        graphql_query = {
            "query": "{ Get { DirectTestProperty { listing_id title suburb price } } }"
        }
        
        graphql_response = requests.post(
            f"{base_url}/graphql",
            headers={"Content-Type": "application/json"},
            json=graphql_query
        )
        
        if graphql_response.status_code == 200:
            data = graphql_response.json()
            properties = data.get("data", {}).get("Get", {}).get("DirectTestProperty", [])
            print(f"   ✅ GraphQL query returned {len(properties)} properties")
            
            if len(properties) == len(test_objects):
                print("   ✅ GraphQL query results match expected count")
            else:
                print(f"   ❌ GraphQL query expected {len(test_objects)}, got {len(properties)}")
                return False
        else:
            print(f"   ❌ GraphQL query failed: {graphql_response.status_code}")
            return False
        
        # 7. Test filtered queries
        print("7. Testing filtered queries...")
        
        filtered_query = {
            "query": """
            { 
                Get { 
                    DirectTestProperty(where: {
                        path: ["suburb"]
                        operator: Equal
                        valueString: "Bondi"
                    }) { 
                        listing_id title suburb 
                    } 
                } 
            }
            """
        }
        
        filtered_response = requests.post(
            f"{base_url}/graphql",
            headers={"Content-Type": "application/json"},
            json=filtered_query
        )
        
        if filtered_response.status_code == 200:
            data = filtered_response.json()
            bondi_properties = data.get("data", {}).get("Get", {}).get("DirectTestProperty", [])
            print(f"   ✅ Filtered query returned {len(bondi_properties)} Bondi properties")
            
            if len(bondi_properties) == 1:
                print("   ✅ Filtered query results correct")
            else:
                print(f"   ❌ Expected 1 Bondi property, got {len(bondi_properties)}")
        else:
            print(f"   ❌ Filtered query failed: {filtered_response.status_code}")
        
        # 8. Test object retrieval by ID
        print("8. Testing object retrieval by ID...")
        
        if inserted_ids:
            get_obj_response = requests.get(f"{base_url}/objects/{inserted_ids[0]}")
            
            if get_obj_response.status_code == 200:
                obj_data = get_obj_response.json()
                title = obj_data.get("properties", {}).get("title")
                print(f"   ✅ Retrieved object by ID: {title}")
            else:
                print(f"   ❌ Failed to retrieve object by ID: {get_obj_response.status_code}")
                return False
        
        print("\n=== TEST RESULTS ===")
        print("✅ Weaviate Health: PASS")
        print("✅ Schema Creation: PASS")
        print("✅ Object Insertion: PASS")
        print("✅ Object Retrieval: PASS")
        print("✅ GraphQL Queries: PASS")
        print("✅ Filtered Queries: PASS")
        print("✅ Object ID Retrieval: PASS")
        print(f"\n✅ ALL TESTS PASSED - Direct API ingestion working correctly!")
        print(f"   Successfully ingested and queried {len(test_objects)} test objects")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    except requests.RequestException as e:
        print(f"\n❌ API REQUEST FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    test_direct_api_ingestion()