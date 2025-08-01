#!/usr/bin/env python3
"""
Basic Weaviate Client Test

Test core Weaviate functionality with proper method calls.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Any
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.core.vector_db.client import WeaviateClient, get_weaviate_client
    from src.core.vector_db.schemas import get_all_schemas
    from src.config.settings import get_settings
except ImportError as e:
    print(f"❌ Failed to import core components: {e}")
    sys.exit(1)


async def test_basic_weaviate_functionality():
    """Test basic Weaviate operations."""
    print("🏠 ReAgent Sydney - Basic Weaviate Test")
    print("=" * 50)
    
    try:
        # Connect to Weaviate
        print("🔗 Connecting to Weaviate...")
        client = await get_weaviate_client()
        print("✅ Connection established")
        
        # Health check
        print("\n🏥 Health check...")
        health = await client.health_check()
        print(f"✅ Health status: {health}")
        
        # Check object counts
        print("\n📊 Checking object counts...")
        schemas = ["Property", "BuyerProfile", "PropertyMatch"]
        for schema_name in schemas:
            try:
                count = await client.get_object_count(schema_name)
                print(f"  📈 {schema_name}: {count} objects")
            except Exception as e:
                print(f"  ❌ {schema_name}: Error - {e}")
        
        # Test data insertion with proper datetime format
        print("\n📥 Testing data insertion...")
        
        # Test property insertion
        test_property = {
            "listing_id": "TEST_001",
            "title": "Test Property",
            "description": "A test property for validation",
            "property_type": "Unit",
            "suburb": "Chatswood",
            "postcode": "2067",
            "state": "NSW",
            "bedrooms": 2,
            "bathrooms": 2,
            "price": 850000,
            "listing_status": "active",
            "listing_type": "sale",
            "features": ["parking", "balcony"],
            "first_listed_date": "2025-07-29T10:00:00Z",  # RFC3339 format
            "days_on_market": 15
        }
        
        try:
            property_id = await client.insert_object(
                class_name="Property",
                properties=test_property,
                object_id="test-property-001"
            )
            print(f"✅ Property inserted: {property_id}")
            
            # Verify insertion by retrieving the object
            retrieved_property = await client.get_object(
                class_name="Property",
                object_id="test-property-001"
            )
            if retrieved_property:
                print("✅ Property retrieval successful")
            else:
                print("❌ Property retrieval failed")
                
        except Exception as e:
            print(f"❌ Property insertion failed: {e}")
        
        # Test buyer profile insertion
        test_buyer = {
            "buyer_id": "buyer-001",
            "full_name": "Test Buyer",
            "buyer_type": "individual",
            "buying_urgency": "medium",
            "max_price": 1000000,
            "min_price": 600000,
            "property_types": ["Unit"],
            "preferred_suburbs": ["Chatswood"],
            "min_bedrooms": 2,
            "created_at": "2025-07-29T10:00:00Z",  # RFC3339 format
            "updated_at": "2025-07-29T10:00:00Z"   # RFC3339 format
        }
        
        try:
            buyer_id = await client.insert_object(
                class_name="BuyerProfile",
                properties=test_buyer,
                object_id="test-buyer-001"
            )
            print(f"✅ Buyer profile inserted: {buyer_id}")
            
        except Exception as e:
            print(f"❌ Buyer profile insertion failed: {e}")
        
        # Test vector search if we have data
        print("\n🔍 Testing vector search...")
        try:
            from src.core.vector_db.client import SearchQuery
            
            # Create a simple search query (this will use automatic vectorization)
            # We'll create a dummy vector for testing
            dummy_vector = [0.1] * 1536  # OpenAI embedding dimension
            
            search_query = SearchQuery(
                vector=dummy_vector,
                class_name="Property",
                limit=5,
                where_filter={
                    "operator": "Equal",
                    "operands": [
                        {"path": ["listing_status"], "operator": "Equal", "valueString": "active"}
                    ]
                }
            )
            
            search_results = await client.vector_search(search_query)
            print(f"✅ Vector search completed: {len(search_results)} results")
            
            for i, result in enumerate(search_results[:3]):
                print(f"  Result {i+1}: Score {result.score:.3f}, ID: {result.object_id}")
            
        except Exception as e:
            print(f"❌ Vector search failed: {e}")
        
        # Final object counts
        print("\n📊 Final object counts...")
        for schema_name in schemas:
            try:
                count = await client.get_object_count(schema_name)
                print(f"  📈 {schema_name}: {count} objects")
            except Exception as e:
                print(f"  ❌ {schema_name}: Error - {e}")
        
        print("\n🎉 Basic Weaviate test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


async def test_semantic_matching_accuracy():
    """Test semantic matching accuracy with real data."""
    print("\n🎯 Testing Semantic Matching Accuracy")
    print("=" * 40)
    
    try:
        client = await get_weaviate_client()
        
        # Insert test properties with semantic content
        test_properties = [
            {
                "listing_id": "LUXURY_001",
                "title": "Luxury Harbour View Penthouse",
                "description": "Stunning penthouse with panoramic harbour views, modern kitchen, pool, and premium finishes in exclusive Double Bay location",
                "property_type": "Penthouse",
                "suburb": "Double Bay",
                "postcode": "2028",
                "bedrooms": 3,
                "bathrooms": 3,
                "price": 4500000,
                "features": ["harbour views", "pool", "luxury finishes", "modern kitchen", "parking"],
                "listing_status": "active",
                "listing_type": "sale",
                "first_listed_date": "2025-07-29T10:00:00Z",
                "days_on_market": 5
            },
            {
                "listing_id": "FAMILY_001", 
                "title": "Family Home with Garden",
                "description": "Perfect family home with large garden, quiet street, close to good schools and parks in Mosman",
                "property_type": "House",
                "suburb": "Mosman",
                "postcode": "2088",
                "bedrooms": 4,
                "bathrooms": 2,
                "price": 2200000,
                "features": ["garden", "family friendly", "quiet street", "near schools", "parking"],
                "listing_status": "active",
                "listing_type": "sale",
                "first_listed_date": "2025-07-29T10:00:00Z",
                "days_on_market": 12
            },
            {
                "listing_id": "INVESTMENT_001",
                "title": "High Yield Investment Unit",
                "description": "Modern 1-bedroom unit with high rental yield potential, excellent transport links, perfect for investors",
                "property_type": "Unit",
                "suburb": "Surry Hills",
                "postcode": "2010",
                "bedrooms": 1,
                "bathrooms": 1,
                "price": 650000,
                "features": ["high yield", "transport", "modern", "investment", "city access"],
                "listing_status": "active",
                "listing_type": "sale",
                "first_listed_date": "2025-07-29T10:00:00Z",
                "days_on_market": 8
            }
        ]
        
        # Insert properties
        print("📥 Inserting test properties...")
        for prop in test_properties:
            try:
                await client.insert_object(
                    class_name="Property",
                    properties=prop,
                    object_id=prop["listing_id"]
                )
                print(f"✅ Inserted: {prop['title'][:30]}...")
            except Exception as e:
                print(f"❌ Failed to insert {prop['listing_id']}: {e}")
        
        # Wait a moment for indexing
        await asyncio.sleep(2)
        
        # Test semantic search queries
        print("\n🔍 Testing semantic search queries...")
        
        test_queries = [
            {
                "description": "Luxury seeker",
                "query_text": "luxury premium harbour views high-end expensive penthouse",
                "expected_match": "LUXURY_001"
            },
            {
                "description": "Family buyer", 
                "query_text": "family home garden children schools quiet neighborhood",
                "expected_match": "FAMILY_001"
            },
            {
                "description": "Investor",
                "query_text": "investment rental yield small unit transport city access",
                "expected_match": "INVESTMENT_001"
            }
        ]
        
        matching_accuracy = 0
        total_queries = len(test_queries)
        
        for query in test_queries:
            try:
                # For this test, we'll use hybrid search which combines text and vector search
                results = await client.hybrid_search(
                    class_name="Property",
                    query_text=query["query_text"],
                    limit=3,
                    where_filter={
                        "operator": "Equal",
                        "operands": [
                            {"path": ["listing_status"], "operator": "Equal", "valueString": "active"}
                        ]
                    }
                )
                
                if results and len(results) > 0:
                    top_match = results[0]
                    top_match_id = top_match.data.get("listing_id", "unknown")
                    
                    print(f"  Query: {query['description']}")
                    print(f"    Expected: {query['expected_match']}")
                    print(f"    Got: {top_match_id} (score: {top_match.score:.3f})")
                    
                    if top_match_id == query["expected_match"]:
                        matching_accuracy += 1
                        print(f"    ✅ Correct match!")
                    else:
                        print(f"    ❌ Incorrect match")
                else:
                    print(f"  Query: {query['description']} - No results returned")
                
            except Exception as e:
                print(f"  Query: {query['description']} - Error: {e}")
        
        accuracy_percentage = (matching_accuracy / total_queries) * 100
        print(f"\n📊 Semantic Matching Accuracy: {matching_accuracy}/{total_queries} ({accuracy_percentage:.1f}%)")
        
        if accuracy_percentage >= 80:
            print("🎉 EXCELLENT - Meets 80%+ accuracy target!")
        elif accuracy_percentage >= 60:
            print("⚠️  GOOD - Above 60% but below target")
        else:
            print("❌ POOR - Below acceptable accuracy threshold")
        
        return accuracy_percentage >= 80
        
    except Exception as e:
        print(f"❌ Semantic matching test failed: {e}")
        return False


async def test_performance_benchmarks():
    """Test performance benchmarks."""
    print("\n⚡ Testing Performance Benchmarks")
    print("=" * 35)
    
    try:
        client = await get_weaviate_client()
        
        # Test query response times
        print("🔍 Testing query response times...")
        
        response_times = []
        dummy_vector = [0.1] * 1536
        
        for i in range(10):
            start_time = time.time()
            
            search_query = SearchQuery(
                vector=dummy_vector,
                class_name="Property",
                limit=10,
                where_filter={
                    "operator": "Equal", 
                    "operands": [
                        {"path": ["listing_status"], "operator": "Equal", "valueString": "active"}
                    ]
                }
            )
            
            results = await client.vector_search(search_query)
            end_time = time.time()
            
            response_time = end_time - start_time
            response_times.append(response_time)
            
            print(f"  Query {i+1}: {response_time:.3f}s ({len(results)} results)")
        
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        print(f"\n📊 Performance Summary:")
        print(f"  Average: {avg_response_time:.3f}s")
        print(f"  Min: {min_response_time:.3f}s")
        print(f"  Max: {max_response_time:.3f}s")
        
        # Performance assessment
        if avg_response_time < 2.0:
            print("🎉 EXCELLENT - Sub-2 second average response time!")
            performance_grade = "A"
        elif avg_response_time < 5.0:
            print("✅ GOOD - Acceptable response times")
            performance_grade = "B"
        else:
            print("❌ SLOW - Response times need improvement")
            performance_grade = "C"
        
        meets_target = avg_response_time < 2.0
        
        return {
            "meets_target": meets_target,
            "average_response_time": avg_response_time,
            "performance_grade": performance_grade
        }
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return {"meets_target": False, "error": str(e)}


async def main():
    """Main test execution."""
    print("🏠 ReAgent Sydney - Buyer-Property Matching Validation")
    print("=" * 60)
    
    # Run tests
    basic_test_passed = await test_basic_weaviate_functionality()
    accuracy_test_passed = await test_semantic_matching_accuracy()
    performance_results = await test_performance_benchmarks()
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 VALIDATION SUMMARY")
    print("=" * 60)
    
    print(f"🔧 Basic Functionality: {'✅ PASS' if basic_test_passed else '❌ FAIL'}")
    print(f"🎯 Semantic Accuracy: {'✅ PASS' if accuracy_test_passed else '❌ FAIL'}")
    print(f"⚡ Performance: {'✅ PASS' if performance_results.get('meets_target', False) else '❌ FAIL'}")
    
    overall_pass = basic_test_passed and accuracy_test_passed and performance_results.get('meets_target', False)
    
    print(f"\n🏆 OVERALL RESULT: {'🎉 READY FOR PRODUCTION' if overall_pass else '⚠️  NEEDS IMPROVEMENT'}")
    
    if not overall_pass:
        print("\n💡 RECOMMENDATIONS:")
        if not basic_test_passed:
            print("  • Fix basic Weaviate connectivity and schema issues")
        if not accuracy_test_passed:
            print("  • Improve semantic matching accuracy with better embeddings")
        if not performance_results.get('meets_target', False):
            print("  • Optimize query performance and indexing")
    
    return 0 if overall_pass else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)