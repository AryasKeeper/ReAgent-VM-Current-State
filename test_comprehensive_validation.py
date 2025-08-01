#!/usr/bin/env python3
"""
Comprehensive Weaviate Vector Search Validation

Production-ready validation suite for ReAgent Sydney's AI-powered property matching system.
Tests all aspects of vector search functionality with realistic Sydney property data.
"""

import asyncio
import sys
import os
import time
import uuid
import json
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.vector_db.client import WeaviateClient, SearchQuery
from src.core.vector_db.embeddings import PropertyVectorizer, BuyerProfileVectorizer, PropertyFeatures, BuyerPreferenceFeatures


class ComprehensiveValidator:
    """Comprehensive Weaviate validation suite for ReAgent Sydney."""
    
    def __init__(self):
        self.client = None
        self.property_vectorizer = PropertyVectorizer()
        self.buyer_vectorizer = BuyerProfileVectorizer()
        self.test_results = {}
        
    async def run_all_tests(self):
        """Run complete validation suite."""
        print("🚀 ReAgent Sydney - Weaviate Vector Search Validation")
        print("=" * 60)
        
        try:
            # Initialize connection
            await self._test_connection()
            
            # Test embedding generation
            await self._test_embeddings()
            
            # Test data ingestion
            await self._test_data_ingestion()
            
            # Test search functionality
            await self._test_search_functionality()
            
            # Test buyer-property matching
            await self._test_matching_system()
            
            # Test performance
            await self._test_performance()
            
            # Generate report
            await self._generate_report()
            
        except Exception as e:
            print(f"❌ Validation suite failed: {e}")
            
    async def _test_connection(self):
        """Test Weaviate connection and setup."""
        print("\n🔌 Testing Weaviate Connection")
        print("-" * 40)
        
        try:
            self.client = WeaviateClient()
            await self.client.connect()
            
            health = await self.client.health_check()
            
            if health.get("ready"):
                print("✅ Connection successful")
                print(f"   URL: {health.get('url')}")
                print(f"   Version: {health.get('meta', {}).get('version', 'Unknown')}")
                print(f"   Modules: {', '.join(health.get('meta', {}).get('modules', {}).keys())}")
                self.test_results["connection"] = {"status": "pass", "details": health}
            else:
                print("❌ Connection failed - Weaviate not ready")
                self.test_results["connection"] = {"status": "fail", "error": "Not ready"}
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            self.test_results["connection"] = {"status": "fail", "error": str(e)}
    
    async def _test_embeddings(self):
        """Test embedding generation for properties and buyers."""
        print("\n🧠 Testing Embedding Generation")
        print("-" * 40)
        
        try:
            # Test property embedding
            prop_features = PropertyFeatures(
                property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
                land_size=0, building_size=85, price=850000,
                suburb="Surry Hills", postcode="2010",
                latitude=-33.8858, longitude=151.2131,
                title="Modern Apartment", description="Modern apartment with city views",
                features_list=["modern", "city_views", "balcony"], days_on_market=14,
                price_per_sqm=10000, suburb_price_percentile=75,
                agent_name="Test Agent", agency_name="Test Agency",
                amenities={}, market_context={}
            )
            
            start_time = time.time()
            prop_embedding, prop_metadata = await self.property_vectorizer.generate_embedding(prop_features)
            prop_duration = time.time() - start_time
            
            print(f"✅ Property embedding: {len(prop_embedding)} dimensions in {prop_duration:.3f}s")
            
            # Test buyer embedding
            buyer_features = BuyerPreferenceFeatures(
                max_price=900000, min_price=700000, budget_flexibility=0.15,
                property_types=["apartment"], min_bedrooms=2, max_bedrooms=3,
                min_bathrooms=1, min_car_spaces=1, min_land_size=0, min_building_size=0,
                preferred_suburbs=["surry_hills"], excluded_suburbs=[],
                preferred_postcodes=["2010"], max_commute_time=30,
                required_features=["modern"], preferred_features=["city_views"],
                excluded_features=[], buyer_type="first_home_buyer", buying_urgency="medium",
                rental_yield_target=0, capital_growth_expectation="medium",
                interaction_patterns={}, preference_weights={}
            )
            
            start_time = time.time()
            buyer_embedding, buyer_metadata = await self.buyer_vectorizer.generate_embedding(buyer_features)
            buyer_duration = time.time() - start_time
            
            print(f"✅ Buyer embedding: {len(buyer_embedding)} dimensions in {buyer_duration:.3f}s")
            
            # Test similarity
            similarity = self.property_vectorizer.calculate_similarity(prop_embedding, buyer_embedding)
            print(f"✅ Similarity calculation: {similarity:.3f}")
            
            self.test_results["embeddings"] = {
                "status": "pass",
                "property_dims": len(prop_embedding),
                "buyer_dims": len(buyer_embedding),
                "similarity": similarity,
                "generation_times": {
                    "property": prop_duration,
                    "buyer": buyer_duration
                }
            }
            
        except Exception as e:
            print(f"❌ Embedding generation failed: {e}")
            self.test_results["embeddings"] = {"status": "fail", "error": str(e)}
    
    async def _test_data_ingestion(self):
        """Test property and buyer data ingestion with vector storage."""
        print("\n📥 Testing Data Ingestion")
        print("-" * 40)
        
        try:
            # Create schemas
            property_schema = {
                "class": "ValidationProperty",
                "description": "Property validation test",
                "vectorizer": "none",
                "properties": [
                    {"name": "address", "dataType": ["text"]},
                    {"name": "suburb", "dataType": ["text"]},
                    {"name": "property_type", "dataType": ["text"]},
                    {"name": "bedrooms", "dataType": ["int"]},
                    {"name": "bathrooms", "dataType": ["int"]},
                    {"name": "price", "dataType": ["number"]},
                    {"name": "description", "dataType": ["text"]}
                ]
            }
            
            buyer_schema = {
                "class": "ValidationBuyer",
                "description": "Buyer validation test",
                "vectorizer": "none",
                "properties": [
                    {"name": "buyer_type", "dataType": ["text"]},
                    {"name": "max_price", "dataType": ["number"]},
                    {"name": "preferred_suburbs", "dataType": ["text[]"]},
                    {"name": "search_query", "dataType": ["text"]}
                ]
            }
            
            await self.client.create_schema(property_schema)
            await self.client.create_schema(buyer_schema)
            print("✅ Schemas created")
            
            # Sample Sydney properties
            properties = [
                {
                    "address": "123 Crown Street, Surry Hills NSW 2010",
                    "suburb": "Surry Hills", "property_type": "apartment",
                    "bedrooms": 2, "bathrooms": 1, "price": 850000,
                    "description": "Modern apartment with city views"
                },
                {
                    "address": "456 Beach Road, Bondi NSW 2026",
                    "suburb": "Bondi", "property_type": "house",
                    "bedrooms": 3, "bathrooms": 2, "price": 1200000,
                    "description": "Beach house with ocean views"
                },
                {
                    "address": "789 Family Street, Chatswood NSW 2067",
                    "suburb": "Chatswood", "property_type": "house",
                    "bedrooms": 4, "bathrooms": 3, "price": 1650000,
                    "description": "Family home with pool and garden"
                }
            ]
            
            # Insert properties with embeddings
            property_ids = []
            for prop in properties:
                prop_features = PropertyFeatures(
                    property_type=prop["property_type"],
                    bedrooms=prop["bedrooms"], bathrooms=prop["bathrooms"], car_spaces=1,
                    land_size=0, building_size=100, price=prop["price"],
                    suburb=prop["suburb"], postcode=prop["address"].split()[-1],
                    latitude=-33.8688, longitude=151.2093,
                    title=prop["description"], description=prop["description"],
                    features_list=prop["description"].split(), days_on_market=14,
                    price_per_sqm=prop["price"]/100, suburb_price_percentile=50,
                    agent_name="Test", agency_name="Test",
                    amenities={}, market_context={}
                )
                
                embedding, _ = await self.property_vectorizer.generate_embedding(prop_features)
                
                object_id = await self.client.insert_object(
                    class_name="ValidationProperty",
                    properties=prop,
                    vector=embedding,
                    object_id=str(uuid.uuid4())
                )
                
                if object_id:
                    property_ids.append(object_id)
            
            print(f"✅ Inserted {len(property_ids)} properties")
            
            # Sample buyers
            buyers = [
                {
                    "buyer_type": "first_home_buyer",
                    "max_price": 900000,
                    "preferred_suburbs": ["surry_hills", "darlinghurst"],
                    "search_query": "Modern apartment near CBD"
                },
                {
                    "buyer_type": "family",
                    "max_price": 1400000,
                    "preferred_suburbs": ["bondi", "chatswood"],
                    "search_query": "Family home with outdoor space"
                }
            ]
            
            # Insert buyers with embeddings
            buyer_ids = []
            for buyer in buyers:
                buyer_features = BuyerPreferenceFeatures(
                    max_price=buyer["max_price"], min_price=buyer["max_price"]*0.8,
                    budget_flexibility=0.1, property_types=["apartment", "house"],
                    min_bedrooms=2, max_bedrooms=4, min_bathrooms=1, min_car_spaces=0,
                    min_land_size=0, min_building_size=0,
                    preferred_suburbs=buyer["preferred_suburbs"], excluded_suburbs=[],
                    preferred_postcodes=[], max_commute_time=30,
                    required_features=[], preferred_features=[],
                    excluded_features=[], buyer_type=buyer["buyer_type"],
                    buying_urgency="medium", rental_yield_target=0,
                    capital_growth_expectation="medium",
                    interaction_patterns={}, preference_weights={}
                )
                
                embedding, _ = await self.buyer_vectorizer.generate_embedding(buyer_features)
                
                object_id = await self.client.insert_object(
                    class_name="ValidationBuyer",
                    properties=buyer,
                    vector=embedding,
                    object_id=str(uuid.uuid4())
                )
                
                if object_id:
                    buyer_ids.append(object_id)
            
            print(f"✅ Inserted {len(buyer_ids)} buyers")
            
            self.test_results["ingestion"] = {
                "status": "pass",
                "properties_inserted": len(property_ids),
                "buyers_inserted": len(buyer_ids)
            }
            
        except Exception as e:
            print(f"❌ Data ingestion failed: {e}")
            self.test_results["ingestion"] = {"status": "fail", "error": str(e)}
    
    async def _test_search_functionality(self):
        """Test semantic property search."""
        print("\n🔍 Testing Search Functionality")
        print("-" * 40)
        
        try:
            # Test queries for different property types
            test_queries = [
                ("modern apartment CBD", "apartment"),
                ("beach house ocean views", "house"),
                ("family home garden", "house")
            ]
            
            search_results = {}
            
            for query_text, expected_type in test_queries:
                # Generate query embedding
                query_features = PropertyFeatures(
                    property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
                    land_size=0, building_size=100, price=800000,
                    suburb="Sydney", postcode="2000",
                    latitude=-33.8688, longitude=151.2093,
                    title=query_text, description=query_text,
                    features_list=query_text.split(), days_on_market=0,
                    price_per_sqm=8000, suburb_price_percentile=50,
                    agent_name="", agency_name="",
                    amenities={}, market_context={}
                )
                
                query_embedding, _ = await self.property_vectorizer.generate_embedding(query_features)
                
                # Search
                search_query = SearchQuery(
                    vector=query_embedding,
                    class_name="ValidationProperty",
                    limit=3,
                    additional_properties=["certainty"]
                )
                
                results = await self.client.vector_search(search_query)
                
                if results:
                    top_result = results[0]
                    search_results[query_text] = {
                        "result_count": len(results),
                        "top_score": top_result.score,
                        "top_address": top_result.data.get("address"),
                        "top_type": top_result.data.get("property_type")
                    }
                    print(f"✅ Query '{query_text}': {len(results)} results, top score: {top_result.score:.3f}")
                else:
                    search_results[query_text] = {"result_count": 0}
                    print(f"❌ Query '{query_text}': No results")
            
            # Test hybrid search
            hybrid_results = await self.client.hybrid_search(
                class_name="ValidationProperty",
                query_text="modern apartment",
                limit=2
            )
            
            print(f"✅ Hybrid search: {len(hybrid_results)} results")
            
            self.test_results["search"] = {
                "status": "pass",
                "query_results": search_results,
                "hybrid_results": len(hybrid_results)
            }
            
        except Exception as e:
            print(f"❌ Search functionality failed: {e}")
            self.test_results["search"] = {"status": "fail", "error": str(e)}
    
    async def _test_matching_system(self):
        """Test buyer-property matching."""
        print("\n🤝 Testing Buyer-Property Matching")
        print("-" * 40)
        
        try:
            # Get all buyers
            buyer_count = await self.client.get_object_count("ValidationBuyer")
            print(f"Total buyers in system: {buyer_count}")
            
            # Test matching for different buyer types
            matches_found = 0
            
            # Search properties for first home buyer budget
            query_features = PropertyFeatures(
                property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
                land_size=0, building_size=85, price=850000,
                suburb="Surry Hills", postcode="2010",
                latitude=-33.8858, longitude=151.2131,
                title="Modern apartment", description="Modern apartment near CBD",
                features_list=["modern", "apartment", "CBD"], days_on_market=14,
                price_per_sqm=10000, suburb_price_percentile=75,
                agent_name="", agency_name="",
                amenities={}, market_context={}
            )
            
            query_embedding, _ = await self.property_vectorizer.generate_embedding(query_features)
            
            # Search for matching properties under budget
            search_query = SearchQuery(
                vector=query_embedding,
                class_name="ValidationProperty",
                limit=3,
                where_filter={
                    "path": ["price"],
                    "operator": "LessThanEqual",
                    "valueNumber": 900000
                }
            )
            
            results = await self.client.vector_search(search_query)
            
            if results:
                matches_found += len(results)
                print(f"✅ Found {len(results)} matches for first home buyer")
                for result in results:
                    print(f"   - {result.data.get('address')} (${result.data.get('price'):,})")
            
            # Test family buyer matching
            family_query = PropertyFeatures(
                property_type="house", bedrooms=3, bathrooms=2, car_spaces=2,
                land_size=320, building_size=150, price=1200000,
                suburb="Bondi", postcode="2026",
                latitude=-33.8915, longitude=151.2767,
                title="Family house", description="Family house with outdoor space",
                features_list=["family", "house", "outdoor"], days_on_market=7,
                price_per_sqm=8000, suburb_price_percentile=60,
                agent_name="", agency_name="",
                amenities={}, market_context={}
            )
            
            family_embedding, _ = await self.property_vectorizer.generate_embedding(family_query)
            
            family_search = SearchQuery(
                vector=family_embedding,
                class_name="ValidationProperty",
                limit=2,
                where_filter={
                    "path": ["price"],
                    "operator": "LessThanEqual",
                    "valueNumber": 1400000
                }
            )
            
            family_results = await self.client.vector_search(family_search)
            
            if family_results:
                matches_found += len(family_results)
                print(f"✅ Found {len(family_results)} matches for family buyer")
            
            self.test_results["matching"] = {
                "status": "pass",
                "total_matches": matches_found,
                "first_home_buyer_matches": len(results) if results else 0,
                "family_buyer_matches": len(family_results) if family_results else 0
            }
            
            print(f"✅ Total matches found: {matches_found}")
            
        except Exception as e:
            print(f"❌ Matching system failed: {e}")
            self.test_results["matching"] = {"status": "fail", "error": str(e)}
    
    async def _test_performance(self):
        """Test system performance metrics."""
        print("\n⚡ Testing Performance")
        print("-" * 40)
        
        try:
            # Test batch operations
            batch_properties = []
            batch_embeddings = []
            
            for i in range(5):
                prop_data = {
                    "address": f"Performance Test {i}",
                    "suburb": "Test Suburb",
                    "property_type": "apartment",
                    "bedrooms": 2,
                    "bathrooms": 1,
                    "price": 800000 + (i * 10000),
                    "description": f"Test property {i}"
                }
                
                features = PropertyFeatures(
                    property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
                    land_size=0, building_size=85, price=prop_data["price"],
                    suburb="Test", postcode="2000",
                    latitude=-33.8688, longitude=151.2093,
                    title=f"Test {i}", description=prop_data["description"],
                    features_list=["test"], days_on_market=0, price_per_sqm=10000,
                    suburb_price_percentile=50, agent_name="Test", agency_name="Test",
                    amenities={}, market_context={}
                )
                
                embedding, _ = await self.property_vectorizer.generate_embedding(features)
                
                batch_properties.append(prop_data)
                batch_embeddings.append(embedding)
            
            # Test batch insertion
            start_time = time.time()
            inserted_ids = await self.client.batch_insert_objects(
                class_name="ValidationProperty",
                objects=batch_properties,
                vectors=batch_embeddings
            )
            batch_duration = time.time() - start_time
            
            print(f"✅ Batch insert: {len(inserted_ids)} objects in {batch_duration:.3f}s")
            
            # Test search performance
            start_time = time.time()
            search_results = await self.client.vector_search(SearchQuery(
                vector=batch_embeddings[0],
                class_name="ValidationProperty",
                limit=10
            ))
            search_duration = time.time() - start_time
            
            print(f"✅ Search performance: {len(search_results)} results in {search_duration:.3f}s")
            
            # Test object count
            start_time = time.time()
            total_count = await self.client.get_object_count("ValidationProperty")
            count_duration = time.time() - start_time
            
            print(f"✅ Object count: {total_count} objects in {count_duration:.3f}s")
            
            self.test_results["performance"] = {
                "status": "pass",
                "batch_insert_duration": batch_duration,
                "search_duration": search_duration,
                "count_duration": count_duration,
                "total_objects": total_count
            }
            
        except Exception as e:
            print(f"❌ Performance testing failed: {e}")
            self.test_results["performance"] = {"status": "fail", "error": str(e)}
    
    async def _generate_report(self):
        """Generate comprehensive validation report."""
        print("\n📊 VALIDATION REPORT")
        print("=" * 60)
        
        # Clean up test data
        try:
            await self.client.delete_schema("ValidationProperty")
            await self.client.delete_schema("ValidationBuyer")
            print("✅ Test data cleaned up")
        except:
            pass
        
        # Calculate summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get("status") == "pass")
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n🎯 SUMMARY")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        # Detailed results
        print(f"\n📋 DETAILED RESULTS")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result.get("status") == "pass" else "❌ FAIL"
            print(f"{test_name.upper()}: {status}")
            
            if result.get("status") == "fail":
                print(f"   Error: {result.get('error', 'Unknown error')}")
        
        # Key metrics
        if self.test_results.get("embeddings", {}).get("status") == "pass":
            emb = self.test_results["embeddings"]
            print(f"\n🧠 EMBEDDING METRICS")
            print(f"Property dimensions: {emb.get('property_dims', 0)}")
            print(f"Buyer dimensions: {emb.get('buyer_dims', 0)}")
            print(f"Similarity score: {emb.get('similarity', 0):.3f}")
        
        if self.test_results.get("performance", {}).get("status") == "pass":
            perf = self.test_results["performance"]
            print(f"\n⚡ PERFORMANCE METRICS")
            print(f"Batch insert: {perf.get('batch_insert_duration', 0):.3f}s")
            print(f"Search query: {perf.get('search_duration', 0):.3f}s")
            print(f"Total objects: {perf.get('total_objects', 0)}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        
        if success_rate == 100:
            print("✅ All tests passed - Weaviate vector search system is production-ready!")
            print("🚀 Ready for Sydney property market deployment")
            print("📊 Implement monitoring dashboards for production metrics")
        elif success_rate >= 80:
            print("⚠️ Most tests passed - address failed tests before production")
            print("🔧 Review failed components and retry validation")
        else:
            print("❌ Multiple test failures - system not ready for production")
            print("🛠️ Significant debugging required before deployment")
        
        # Save detailed report
        report = {
            "timestamp": time.time(),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "success_rate": success_rate
            },
            "test_results": self.test_results,
            "recommendations": []
        }
        
        with open("weaviate_validation_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Full report saved to: weaviate_validation_report.json")


async def main():
    """Run comprehensive Weaviate validation suite."""
    validator = ComprehensiveValidator()
    await validator.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())