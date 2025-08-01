#!/usr/bin/env python3
"""
Final Buyer-Property Matching Validation

Comprehensive validation of the ReAgent matching system using proper UUID formatting
and realistic test data to validate AI-powered matching capabilities.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.core.vector_db.client import WeaviateClient, get_weaviate_client, SearchQuery
    from src.core.vector_db.schemas import get_all_schemas
    from src.config.settings import get_settings
except ImportError as e:
    print(f"❌ Failed to import core components: {e}")
    sys.exit(1)

import structlog

# Configure basic logging
structlog.configure()
logger = structlog.get_logger("matching_validation")


class MatchingPipelineValidator:
    """Comprehensive validation of buyer-property matching pipeline."""
    
    def __init__(self):
        self.client: WeaviateClient = None
        self.test_results = {
            "schema_validation": {},
            "data_ingestion": {},
            "vector_search": {},
            "semantic_matching": {},
            "performance_testing": {},
            "accuracy_testing": {}
        }
        
    async def initialize(self):
        """Initialize the validation system."""
        try:
            print("🔗 Initializing Weaviate client...")
            self.client = await get_weaviate_client()
            print("✅ Weaviate connection established")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            return False
    
    async def validate_schemas(self):
        """Validate that required schemas are deployed."""
        print("\n📊 Validating schemas...")
        
        try:
            health = await self.client.health_check()
            self.test_results["schema_validation"]["weaviate_health"] = health
            print(f"✅ Weaviate health: {health.get('status', 'unknown')}")
            
            # Check object counts for all schemas
            schema_counts = {}
            for schema_name in ["Property", "BuyerProfile", "PropertyMatch"]:
                try:
                    count = await self.client.get_object_count(schema_name)
                    schema_counts[schema_name] = count
                    print(f"  📊 {schema_name}: {count} objects")
                except Exception as e:
                    schema_counts[schema_name] = f"Error: {e}"
                    print(f"  ❌ {schema_name}: {e}")
            
            self.test_results["schema_validation"]["object_counts"] = schema_counts
            return True
            
        except Exception as e:
            print(f"❌ Schema validation failed: {e}")
            self.test_results["schema_validation"]["error"] = str(e)
            return False
    
    async def test_data_ingestion(self):
        """Test data ingestion with proper formatting."""
        print("\n📥 Testing data ingestion...")
        
        ingestion_results = {
            "properties_inserted": 0,
            "buyers_inserted": 0,
            "errors": []
        }
        
        # Test properties with proper UUID formatting
        test_properties = [
            {
                "listing_id": "PROP001",
                "title": "Modern 2BR Unit in Chatswood",
                "description": "Beautiful modern apartment with city views, parking, and balcony in prime Chatswood location",
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
                "first_listed_date": "2025-07-29T10:00:00Z",
                "days_on_market": 15,
                "latitude": -33.7969,
                "longitude": 151.1816
            },
            {
                "listing_id": "PROP002",
                "title": "Luxury House in Mosman with Harbour Views",
                "description": "Stunning 4-bedroom family home with harbour views, pool, and landscaped garden",
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
                "features": ["harbour views", "pool", "garden", "luxury", "family"],
                "first_listed_date": "2025-07-29T09:00:00Z",
                "days_on_market": 8,
                "latitude": -33.8299,
                "longitude": 151.2411
            },
            {
                "listing_id": "PROP003",
                "title": "Investment Unit in Surry Hills",
                "description": "High-yield 1-bedroom unit perfect for investors, excellent transport links and rental potential",
                "property_type": "Unit",
                "suburb": "Surry Hills",
                "postcode": "2010",
                "state": "NSW",
                "bedrooms": 1,
                "bathrooms": 1,
                "car_spaces": 0,
                "price": 650000,
                "listing_status": "active",
                "listing_type": "sale",
                "features": ["investment", "transport", "rental yield", "modern"],
                "first_listed_date": "2025-07-29T08:00:00Z",
                "days_on_market": 20,
                "latitude": -33.8830,
                "longitude": 151.2093
            },
            {
                "listing_id": "PROP004",
                "title": "Affordable 3BR Townhouse in Parramatta",
                "description": "Family-friendly townhouse with courtyard, perfect for first home buyers",
                "property_type": "Townhouse",
                "suburb": "Parramatta",
                "postcode": "2150",
                "state": "NSW",
                "bedrooms": 3,
                "bathrooms": 2,
                "car_spaces": 1,
                "price": 750000,
                "listing_status": "active",
                "listing_type": "sale",
                "features": ["family", "courtyard", "affordable", "first home"],
                "first_listed_date": "2025-07-29T11:00:00Z",
                "days_on_market": 10,
                "latitude": -33.8175,
                "longitude": 151.0037
            },
            {
                "listing_id": "PROP005",
                "title": "Beachside Unit in Manly",
                "description": "Light-filled 2-bedroom unit with ocean views and beach lifestyle",
                "property_type": "Unit",
                "suburb": "Manly",
                "postcode": "2095",
                "state": "NSW", 
                "bedrooms": 2,
                "bathrooms": 2,
                "car_spaces": 1,
                "price": 1150000,
                "listing_status": "active",
                "listing_type": "sale",
                "features": ["ocean views", "beach", "lifestyle", "parking"],
                "first_listed_date": "2025-07-29T07:00:00Z",
                "days_on_market": 25,
                "latitude": -33.7875,
                "longitude": 151.2873
            }
        ]
        
        # Insert properties with proper UUIDs
        for prop in test_properties:
            try:
                property_uuid = str(uuid.uuid4())
                object_id = await self.client.insert_object(
                    class_name="Property",
                    properties=prop,
                    object_id=property_uuid
                )
                
                if object_id:
                    ingestion_results["properties_inserted"] += 1
                    print(f"✅ Property inserted: {prop['title'][:40]}...")
                
            except Exception as e:
                error_msg = f"Property {prop['listing_id']}: {e}"
                ingestion_results["errors"].append(error_msg)
                print(f"❌ {error_msg}")
        
        # Test buyer profiles
        test_buyers = [
            {
                "buyer_id": "BUYER001",
                "full_name": "Sarah Chen - First Home Buyer",
                "buyer_type": "individual",
                "buying_urgency": "high",
                "max_price": 900000,
                "min_price": 600000,
                "budget_flexibility": 0.1,
                "property_types": ["Unit", "Apartment"],
                "preferred_suburbs": ["Chatswood", "North Sydney", "Parramatta"],
                "min_bedrooms": 2,
                "max_bedrooms": 3,
                "preferred_features": ["parking", "balcony", "modern", "transport"],
                "created_at": "2025-07-29T10:00:00Z",
                "updated_at": "2025-07-29T10:00:00Z"
            },
            {
                "buyer_id": "BUYER002", 
                "full_name": "Michael Thompson - Investor",
                "buyer_type": "investor",
                "buying_urgency": "medium",
                "max_price": 800000,
                "min_price": 500000,
                "budget_flexibility": 0.15,
                "property_types": ["Unit"],
                "preferred_suburbs": ["Surry Hills", "Redfern", "Chippendale"],
                "min_bedrooms": 1,
                "max_bedrooms": 2,
                "preferred_features": ["investment", "rental yield", "transport", "modern"],
                "created_at": "2025-07-29T10:00:00Z",
                "updated_at": "2025-07-29T10:00:00Z"
            },
            {
                "buyer_id": "BUYER003",
                "full_name": "Wilson Family - Luxury Seekers",
                "buyer_type": "family",
                "buying_urgency": "low",
                "max_price": 4000000,
                "min_price": 2500000,
                "budget_flexibility": 0.2,
                "property_types": ["House"],
                "preferred_suburbs": ["Mosman", "Neutral Bay", "Double Bay"],
                "min_bedrooms": 3,
                "max_bedrooms": 5,
                "preferred_features": ["harbour views", "pool", "luxury", "garden"],
                "created_at": "2025-07-29T10:00:00Z",
                "updated_at": "2025-07-29T10:00:00Z"
            },
            {
                "buyer_id": "BUYER004",
                "full_name": "Lisa Rodriguez - Downsizer",
                "buyer_type": "downsizer",
                "buying_urgency": "medium",
                "max_price": 1300000,
                "min_price": 900000,
                "budget_flexibility": 0.1,
                "property_types": ["Unit"],
                "preferred_suburbs": ["Manly", "Dee Why", "Collaroy"],
                "min_bedrooms": 2,
                "max_bedrooms": 3,
                "preferred_features": ["ocean views", "low maintenance", "parking"],
                "created_at": "2025-07-29T10:00:00Z",
                "updated_at": "2025-07-29T10:00:00Z"
            }
        ]
        
        # Insert buyer profiles
        for buyer in test_buyers:
            try:
                buyer_uuid = str(uuid.uuid4())
                object_id = await self.client.insert_object(
                    class_name="BuyerProfile",
                    properties=buyer,
                    object_id=buyer_uuid
                )
                
                if object_id:
                    ingestion_results["buyers_inserted"] += 1
                    print(f"✅ Buyer inserted: {buyer['full_name']}")
                
            except Exception as e:
                error_msg = f"Buyer {buyer['buyer_id']}: {e}"
                ingestion_results["errors"].append(error_msg)
                print(f"❌ {error_msg}")
        
        print(f"\n📊 Data ingestion summary:")
        print(f"  Properties: {ingestion_results['properties_inserted']}")
        print(f"  Buyers: {ingestion_results['buyers_inserted']}")
        print(f"  Errors: {len(ingestion_results['errors'])}")
        
        self.test_results["data_ingestion"] = ingestion_results
        return ingestion_results["properties_inserted"] > 0 and ingestion_results["buyers_inserted"] > 0
    
    async def test_vector_search_performance(self):
        """Test vector search performance."""
        print("\n⚡ Testing vector search performance...")
        
        performance_results = {
            "search_times": [],
            "result_counts": [],
            "average_time": 0.0,
            "queries_performed": 0
        }
        
        # Wait for indexing
        await asyncio.sleep(2)
        
        # Create dummy vectors for testing (in real scenario, these would be embeddings)
        dummy_vector = [0.1] * 1536  # OpenAI embedding dimension
        
        # Perform multiple searches to test performance
        for i in range(10):
            try:
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
                    },
                    additional_properties=["certainty"]
                )
                
                results = await self.client.vector_search(search_query)
                end_time = time.time()
                
                search_time = end_time - start_time
                performance_results["search_times"].append(search_time)
                performance_results["result_counts"].append(len(results))
                performance_results["queries_performed"] += 1
                
                print(f"  Search {i+1}: {search_time:.3f}s ({len(results)} results)")
                
            except Exception as e:
                print(f"❌ Search {i+1} failed: {e}")
        
        if performance_results["search_times"]:
            performance_results["average_time"] = sum(performance_results["search_times"]) / len(performance_results["search_times"])
            performance_results["max_time"] = max(performance_results["search_times"])
            performance_results["min_time"] = min(performance_results["search_times"])
        
        avg_time = performance_results["average_time"]
        performance_grade = "A" if avg_time < 2.0 else "B" if avg_time < 5.0 else "C"
        meets_target = avg_time < 2.0
        
        print(f"\n📊 Performance summary:")
        print(f"  Average time: {avg_time:.3f}s")
        print(f"  Performance grade: {performance_grade}")
        print(f"  Meets <2s target: {'✅ YES' if meets_target else '❌ NO'}")
        
        performance_results["performance_grade"] = performance_grade
        performance_results["meets_target"] = meets_target
        
        self.test_results["performance_testing"] = performance_results
        return meets_target
    
    async def test_semantic_matching_accuracy(self):
        """Test semantic matching accuracy with realistic scenarios."""
        print("\n🎯 Testing semantic matching accuracy...")
        
        accuracy_results = {
            "test_cases": 0,
            "accurate_matches": 0,
            "accuracy_percentage": 0.0,
            "test_details": []
        }
        
        # Wait for data to be indexed
        await asyncio.sleep(3)
        
        # Define test scenarios with expected outcomes
        test_scenarios = [
            {
                "buyer_description": "First home buyer seeking modern unit",
                "query_text": "modern 2 bedroom unit apartment parking balcony transport first home buyer affordable",
                "expected_keywords": ["chatswood", "unit", "modern", "parking"],
                "max_price_filter": 900000
            },
            {
                "buyer_description": "Investor seeking rental yield",
                "query_text": "investment unit rental yield high return transport city access small",
                "expected_keywords": ["surry hills", "investment", "yield"],
                "max_price_filter": 800000
            },
            {
                "buyer_description": "Luxury family seeker",
                "query_text": "luxury house family harbour views pool garden premium location",
                "expected_keywords": ["mosman", "house", "luxury", "harbour"],
                "max_price_filter": 4000000
            },
            {
                "buyer_description": "Beachside lifestyle seeker",
                "query_text": "beach ocean views lifestyle unit balcony parking seaside",
                "expected_keywords": ["manly", "ocean", "beach"],
                "max_price_filter": 1300000
            }
        ]
        
        for scenario in test_scenarios:
            try:
                accuracy_results["test_cases"] += 1
                
                # Perform hybrid search combining text and vector search
                results = await self.client.hybrid_search(
                    class_name="Property",
                    query_text=scenario["query_text"],
                    limit=5,
                    where_filter={
                        "operator": "And",
                        "operands": [
                            {"path": ["listing_status"], "operator": "Equal", "valueString": "active"},
                            {"path": ["price"], "operator": "LessThanEqual", "valueNumber": scenario["max_price_filter"]}
                        ]
                    }
                )
                
                test_detail = {
                    "buyer_description": scenario["buyer_description"],
                    "results_count": len(results),
                    "top_matches": [],
                    "accuracy_assessment": "no_results"
                }
                
                if results and len(results) > 0:
                    # Analyze top 3 results
                    for i, result in enumerate(results[:3]):
                        match_data = {
                            "rank": i + 1,
                            "title": result.data.get("title", "Unknown"),
                            "suburb": result.data.get("suburb", "Unknown"),
                            "price": result.data.get("price", 0),
                            "property_type": result.data.get("property_type", "Unknown"),
                            "score": result.score if hasattr(result, 'score') else 0
                        }
                        test_detail["top_matches"].append(match_data)
                    
                    # Check if top result matches expected criteria
                    top_result = results[0]
                    top_result_text = f"{top_result.data.get('title', '')} {top_result.data.get('suburb', '')} {top_result.data.get('description', '')}".lower()
                    
                    keyword_matches = sum(1 for keyword in scenario["expected_keywords"] if keyword.lower() in top_result_text)
                    
                    if keyword_matches >= len(scenario["expected_keywords"]) * 0.5:  # 50% keyword match threshold
                        accuracy_results["accurate_matches"] += 1
                        test_detail["accuracy_assessment"] = "accurate"
                        print(f"✅ {scenario['buyer_description']}: Accurate match")
                    else:
                        test_detail["accuracy_assessment"] = "inaccurate"
                        print(f"❌ {scenario['buyer_description']}: Poor match")
                    
                    print(f"   Top result: {top_result.data.get('title', 'Unknown')[:50]}...")
                    print(f"   Score: {result.score if hasattr(result, 'score') else 'N/A'}")
                else:
                    print(f"❌ {scenario['buyer_description']}: No results returned")
                
                accuracy_results["test_details"].append(test_detail)
                
            except Exception as e:
                print(f"❌ Test scenario failed: {e}")
                accuracy_results["test_details"].append({
                    "buyer_description": scenario["buyer_description"],
                    "error": str(e)
                })
        
        # Calculate accuracy percentage
        if accuracy_results["test_cases"] > 0:
            accuracy_results["accuracy_percentage"] = (accuracy_results["accurate_matches"] / accuracy_results["test_cases"]) * 100
        
        accuracy_percent = accuracy_results["accuracy_percentage"]
        meets_accuracy_target = accuracy_percent >= 80
        
        print(f"\n📊 Semantic matching accuracy:")
        print(f"  Accurate matches: {accuracy_results['accurate_matches']}/{accuracy_results['test_cases']}")
        print(f"  Accuracy: {accuracy_percent:.1f}%")
        print(f"  Meets 80% target: {'✅ YES' if meets_accuracy_target else '❌ NO'}")
        
        self.test_results["accuracy_testing"] = accuracy_results
        return meets_accuracy_target
    
    async def run_comprehensive_validation(self):
        """Run the complete validation pipeline."""
        print("🏠 ReAgent Sydney - Comprehensive Matching Pipeline Validation")
        print("=" * 70)
        
        if not await self.initialize():
            return False
        
        # Run all validation phases
        schema_valid = await self.validate_schemas()
        data_ingested = await self.test_data_ingestion()
        performance_good = await self.test_vector_search_performance()
        accuracy_good = await self.test_semantic_matching_accuracy()
        
        # Generate final assessment
        print("\n" + "=" * 70)
        print("📋 FINAL VALIDATION RESULTS")
        print("=" * 70)
        
        print(f"📊 Schema Validation: {'✅ PASS' if schema_valid else '❌ FAIL'}")
        print(f"📥 Data Ingestion: {'✅ PASS' if data_ingested else '❌ FAIL'}")
        print(f"⚡ Performance (<2s): {'✅ PASS' if performance_good else '❌ FAIL'}")
        print(f"🎯 Accuracy (80%+): {'✅ PASS' if accuracy_good else '❌ FAIL'}")
        
        overall_pass = schema_valid and data_ingested and performance_good and accuracy_good
        
        print(f"\n🏆 OVERALL ASSESSMENT: {'🎉 PRODUCTION READY' if overall_pass else '⚠️  NEEDS IMPROVEMENT'}")
        
        # Generate recommendations
        if not overall_pass:
            print("\n💡 CRITICAL RECOMMENDATIONS:")
            if not schema_valid:
                print("  • Fix Weaviate schema deployment and connectivity issues")
            if not data_ingested:
                print("  • Resolve data ingestion and UUID formatting problems")
            if not performance_good:
                print("  • Optimize vector search indexing and query performance")
            if not accuracy_good:
                print("  • Improve semantic matching with better embeddings and similarity thresholds")
        
        return overall_pass


async def main():
    """Main validation execution."""
    validator = MatchingPipelineValidator() 
    
    try:
        success = await validator.run_comprehensive_validation()
        
        # Save detailed results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"buyer_matching_validation_report_{timestamp}.json"
        
        # Add metadata
        validator.test_results["metadata"] = {
            "test_run_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "validation_passed": success,
            "target_accuracy": 80,
            "target_response_time": 2.0
        }
        
        with open(report_filename, 'w') as f:
            json.dump(validator.test_results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed report saved to: {report_filename}")
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)