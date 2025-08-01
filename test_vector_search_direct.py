#!/usr/bin/env python3
"""
Direct Vector Search Validation

Tests vector similarity search functionality without complex agent imports.
Focus on core Weaviate and embedding functionality.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.core.vector_db.client import WeaviateClient, get_weaviate_client, SearchQuery
    from src.core.vector_db.schemas import get_all_schemas, PropertySchema, BuyerProfileSchema
    from src.config.settings import get_settings
except ImportError as e:
    print(f"❌ Failed to import core components: {e}")
    sys.exit(1)

import structlog

# Configure basic logging
structlog.configure()
logger = structlog.get_logger("vector_search_validation")


class VectorSearchValidator:
    """Direct validation of vector search functionality."""
    
    def __init__(self):
        self.weaviate_client: WeaviateClient = None
        
    async def initialize(self):
        """Initialize Weaviate client."""
        try:
            print("🔗 Connecting to Weaviate...")
            self.weaviate_client = await get_weaviate_client()
            print("✅ Weaviate connection established")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to Weaviate: {e}")
            return False
    
    async def validate_schemas(self) -> Dict[str, Any]:
        """Validate deployed schemas."""
        print("\n📊 Validating Weaviate schemas...")
        
        results = {
            "schemas_checked": 0,
            "schemas_exist": 0,
            "schema_details": {}
        }
        
        schemas = get_all_schemas()
        
        for schema_name, schema_config in schemas.items():
            results["schemas_checked"] += 1
            
            try:
                # Check if schema exists
                class_info = await self.weaviate_client.get_schema_class(schema_name)
                
                if class_info:
                    results["schemas_exist"] += 1
                    results["schema_details"][schema_name] = {
                        "exists": True,
                        "properties_count": len(class_info.get("properties", [])),
                        "vectorizer": class_info.get("vectorizer", "none")
                    }
                    print(f"  ✅ {schema_name}: {len(class_info.get('properties', []))} properties")
                else:
                    results["schema_details"][schema_name] = {
                        "exists": False,
                        "error": "Schema not found"
                    }
                    print(f"  ❌ {schema_name}: Not found")
                    
            except Exception as e:
                results["schema_details"][schema_name] = {
                    "exists": False,
                    "error": str(e)
                }
                print(f"  ❌ {schema_name}: Error - {e}")
        
        success_rate = results["schemas_exist"] / results["schemas_checked"] if results["schemas_checked"] > 0 else 0
        print(f"\n📈 Schema validation: {results['schemas_exist']}/{results['schemas_checked']} ({success_rate:.1%}) schemas exist")
        
        return results
    
    async def test_data_ingestion(self) -> Dict[str, Any]:
        """Test basic data ingestion."""
        print("\n📥 Testing data ingestion...")
        
        results = {
            "test_objects_created": 0,
            "ingestion_errors": [],
            "average_ingestion_time": 0.0
        }
        
        # Test property ingestion
        test_properties = [
            {
                "listing_id": f"TEST_PROP_{uuid.uuid4().hex[:8]}",
                "title": "Modern 2BR Apartment in Chatswood",
                "description": "Beautiful modern apartment with city views, parking, and balcony",
                "property_type": "Unit",
                "suburb": "Chatswood",
                "postcode": "2067",
                "state": "NSW",
                "bedrooms": 2,
                "bathrooms": 2,
                "car_spaces": 1,
                "price": 850000,
                "listing_status": "active",
                "listing_type": "sale",
                "features": ["parking", "balcony", "modern", "city views"],
                "days_on_market": 15,
                "latitude": -33.7969,
                "longitude": 151.1816
            },
            {
                "listing_id": f"TEST_PROP_{uuid.uuid4().hex[:8]}", 
                "title": "Luxury House in Mosman with Harbour Views",
                "description": "Stunning 4-bedroom house with harbour views, pool, and garden",
                "property_type": "House",
                "suburb": "Mosman",
                "postcode": "2088",
                "state": "NSW",
                "bedrooms": 4,
                "bathrooms": 3,
                "car_spaces": 2,
                "price": 3200000,
                "listing_status": "active",
                "listing_type": "sale",
                "features": ["harbour views", "pool", "garden", "parking", "luxury"],
                "days_on_market": 8,
                "latitude": -33.8299,
                "longitude": 151.2411
            }
        ]
        
        start_time = time.time()
        
        for prop_data in test_properties:
            try:
                # Add required timestamp fields
                prop_data["first_listed_date"] = datetime.utcnow().isoformat()
                
                # Insert into Weaviate (let Weaviate generate the vector)
                object_id = await self.weaviate_client.insert_object(
                    class_name="Property",
                    properties=prop_data,
                    object_id=prop_data["listing_id"]
                )
                
                if object_id:
                    results["test_objects_created"] += 1
                    print(f"  ✅ Created property: {prop_data['title'][:50]}...")
                
            except Exception as e:
                error_msg = f"Property ingestion failed: {e}"
                results["ingestion_errors"].append(error_msg)
                print(f"  ❌ {error_msg}")
        
        # Test buyer profile ingestion
        test_buyers = [
            {
                "buyer_id": str(uuid.uuid4()),
                "full_name": "Test Buyer 1",
                "buyer_type": "individual",
                "buying_urgency": "medium",
                "max_price": 1000000,
                "min_price": 600000,
                "budget_flexibility": 0.1,
                "property_types": ["Unit", "Apartment"],
                "preferred_suburbs": ["Chatswood", "North Sydney"],
                "min_bedrooms": 2,
                "preferred_features": ["parking", "balcony", "modern"],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
        ]
        
        for buyer_data in test_buyers:
            try:
                object_id = await self.weaviate_client.insert_object(
                    class_name="BuyerProfile",
                    properties=buyer_data,
                    object_id=buyer_data["buyer_id"]
                )
                
                if object_id:
                    results["test_objects_created"] += 1
                    print(f"  ✅ Created buyer profile: {buyer_data['full_name']}")
                
            except Exception as e:
                error_msg = f"Buyer ingestion failed: {e}"
                results["ingestion_errors"].append(error_msg)
                print(f"  ❌ {error_msg}")
        
        total_time = time.time() - start_time
        if results["test_objects_created"] > 0:
            results["average_ingestion_time"] = total_time / results["test_objects_created"]
        
        print(f"\n📈 Data ingestion: {results['test_objects_created']} objects created in {total_time:.2f}s")
        
        return results
    
    async def test_vector_search(self) -> Dict[str, Any]:
        """Test vector similarity search."""
        print("\n🔍 Testing vector similarity search...")
        
        results = {
            "searches_performed": 0,
            "search_times": [],
            "results_returned": [],
            "average_search_time": 0.0,
            "search_details": []
        }
        
        # Test queries
        test_queries = [
            {
                "description": "Looking for modern 2BR unit with parking",
                "near_text": "modern 2 bedroom unit apartment parking balcony city views",
                "filters": {
                    "operator": "And",
                    "operands": [
                        {"path": ["listing_status"], "operator": "Equal", "valueString": "active"},
                        {"path": ["bedrooms"], "operator": "GreaterThanEqual", "valueInt": 2}
                    ]
                }
            },
            {
                "description": "Luxury house with harbour views",
                "near_text": "luxury house harbour views pool garden premium location",
                "filters": {
                    "operator": "And",
                    "operands": [
                        {"path": ["listing_status"], "operator": "Equal", "valueString": "active"},
                        {"path": ["property_type"], "operator": "Equal", "valueString": "House"}
                    ]
                }
            }
        ]
        
        for query in test_queries:
            try:
                start_time = time.time()
                
                # Perform near text search
                search_response = await self.weaviate_client.near_text_search(
                    class_name="Property",
                    concepts=[query["near_text"]],
                    limit=10,
                    where_filter=query["filters"],
                    additional_properties=["certainty", "distance"]
                )
                
                search_time = time.time() - start_time
                results["searches_performed"] += 1
                results["search_times"].append(search_time)
                results["results_returned"].append(len(search_response))
                
                search_detail = {
                    "query": query["description"],
                    "search_time": search_time,
                    "results_count": len(search_response),
                    "top_results": []
                }
                
                # Extract top results
                for i, result in enumerate(search_response[:3]):
                    if hasattr(result, 'data') and result.data:
                        search_detail["top_results"].append({
                            "rank": i + 1,
                            "title": result.data.get("title", "Unknown"),
                            "suburb": result.data.get("suburb", "Unknown"),
                            "price": result.data.get("price", 0),
                            "certainty": getattr(result, 'score', 0) if hasattr(result, 'score') else 0
                        })
                
                results["search_details"].append(search_detail)
                
                print(f"  ✅ {query['description']}: {len(search_response)} results in {search_time:.3f}s")
                
            except Exception as e:
                print(f"  ❌ Search failed for '{query['description']}': {e}")
        
        # Calculate averages
        if results["search_times"]:
            results["average_search_time"] = sum(results["search_times"]) / len(results["search_times"])
            results["max_search_time"] = max(results["search_times"])
            results["min_search_time"] = min(results["search_times"])
        
        performance_rating = "excellent" if results.get("average_search_time", 10) < 2.0 else "good" if results.get("average_search_time", 10) < 5.0 else "needs_improvement"
        
        print(f"\n📈 Search performance: {results['average_search_time']:.3f}s average ({performance_rating})")
        
        return results
    
    async def test_object_counts(self) -> Dict[str, Any]:
        """Test object counts in each collection."""
        print("\n🔢 Checking object counts...")
        
        results = {}
        schemas = ["Property", "BuyerProfile", "PropertyMatch"]
        
        for schema_name in schemas:
            try:
                count = await self.weaviate_client.get_object_count(schema_name)
                results[schema_name] = count
                print(f"  📊 {schema_name}: {count} objects")
            except Exception as e:
                results[schema_name] = f"Error: {e}"
                print(f"  ❌ {schema_name}: Error getting count - {e}")
        
        return results
    
    async def run_validation(self) -> Dict[str, Any]:
        """Run complete validation."""
        print("🏠 ReAgent Sydney - Vector Search Direct Validation")
        print("=" * 60)
        
        if not await self.initialize():
            return {"error": "Failed to initialize"}
        
        validation_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "test_run_id": str(uuid.uuid4()),
            "schemas": await self.validate_schemas(),
            "object_counts": await self.test_object_counts(),
            "data_ingestion": await self.test_data_ingestion(),
            "vector_search": await self.test_vector_search(),
        }
        
        # Overall assessment
        schema_success = validation_results["schemas"]["schemas_exist"] / validation_results["schemas"]["schemas_checked"] if validation_results["schemas"]["schemas_checked"] > 0 else 0
        ingestion_success = validation_results["data_ingestion"]["test_objects_created"] > 0
        search_success = validation_results["vector_search"]["searches_performed"] > 0
        
        overall_status = "✅ PASS" if schema_success >= 0.8 and ingestion_success and search_success else "❌ FAIL"
        
        print(f"\n🏆 OVERALL VALIDATION STATUS: {overall_status}")
        print(f"📊 Schemas: {validation_results['schemas']['schemas_exist']}/{validation_results['schemas']['schemas_checked']}")
        print(f"📥 Data Ingestion: {validation_results['data_ingestion']['test_objects_created']} objects created")
        print(f"🔍 Vector Search: {validation_results['vector_search']['searches_performed']} searches performed")
        
        return validation_results


async def main():
    """Main execution function."""
    validator = VectorSearchValidator()
    
    try:
        results = await validator.run_validation()
        
        # Save results
        report_filename = f"vector_search_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Full results saved to: {report_filename}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)