#!/usr/bin/env python3
"""
Embeddings Validation Test

Test the property and buyer vectorization functionality.
"""

import asyncio
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.vector_db.client import WeaviateClient, SearchQuery
from src.core.vector_db.embeddings import PropertyVectorizer, BuyerProfileVectorizer, PropertyFeatures, BuyerPreferenceFeatures


async def test_property_vectorization():
    """Test property embedding generation."""
    print("🏠 Testing property vectorization...")
    
    try:
        vectorizer = PropertyVectorizer()
        
        # Create test property features
        test_property = PropertyFeatures(
            property_type="apartment",
            bedrooms=2,
            bathrooms=1,
            car_spaces=1,
            land_size=0,
            building_size=85,
            price=850000,
            suburb="Surry Hills",
            postcode="2010",
            latitude=-33.8858,
            longitude=151.2131,
            title="Modern Apartment with City Views",
            description="Modern apartment in trendy Surry Hills with city views, walking distance to CBD",
            features_list=["balcony", "city_views", "near_transport", "modern_kitchen"],
            days_on_market=14,
            price_per_sqm=10000,
            suburb_price_percentile=75,
            agent_name="Test Agent",
            agency_name="Test Agency",
            amenities={"balcony": True, "air_conditioning": True},
            market_context={"view_count": 245, "enquiry_count": 12}
        )
        
        # Generate embedding
        start_time = time.time()
        embedding, metadata = await vectorizer.generate_embedding(test_property)
        duration = time.time() - start_time
        
        print(f"✅ Property embedding generated:")
        print(f"   Dimensions: {len(embedding)}")
        print(f"   Generation time: {duration:.3f}s")
        print(f"   Model: {metadata.model_name} v{metadata.model_version}")
        print(f"   Feature count: {metadata.feature_count}")
        
        # Validate embedding
        if len(embedding) > 0 and all(isinstance(x, float) for x in embedding):
            print("✅ Embedding validation passed")
            return True, embedding, metadata
        else:
            print("❌ Embedding validation failed")
            return False, None, None
            
    except Exception as e:
        print(f"❌ Property vectorization failed: {e}")
        return False, None, None


async def test_buyer_vectorization():
    """Test buyer preference embedding generation."""
    print("\n👤 Testing buyer vectorization...")
    
    try:
        vectorizer = BuyerProfileVectorizer()
        
        # Create test buyer features
        test_buyer = BuyerPreferenceFeatures(
            max_price=900000,
            min_price=700000,
            budget_flexibility=0.15,
            property_types=["apartment", "unit"],
            min_bedrooms=2,
            max_bedrooms=3,
            min_bathrooms=1,
            min_car_spaces=1,
            min_land_size=0,
            min_building_size=0,
            preferred_suburbs=["surry_hills", "darlinghurst", "redfern"],
            excluded_suburbs=[],
            preferred_postcodes=["2010", "2016", "2008"],
            max_commute_time=30,
            required_features=["modern_kitchen", "transport_links"],
            preferred_features=["balcony", "city_views"],
            excluded_features=["ground_floor"],
            buyer_type="first_home_buyer",
            buying_urgency="medium",
            rental_yield_target=0.0,
            capital_growth_expectation="medium",
            interaction_patterns={
                "avg_daily_views": 3.5,
                "avg_session_duration": 420,
                "interest_score_variance": 0.8,
                "feature_focus_score": 0.7
            },
            preference_weights={}
        )
        
        # Generate embedding
        start_time = time.time()
        embedding, metadata = await vectorizer.generate_embedding(test_buyer)
        duration = time.time() - start_time
        
        print(f"✅ Buyer embedding generated:")
        print(f"   Dimensions: {len(embedding)}")
        print(f"   Generation time: {duration:.3f}s")
        print(f"   Model: {metadata.model_name} v{metadata.model_version}")
        print(f"   Feature count: {metadata.feature_count}")
        
        # Validate embedding
        if len(embedding) > 0 and all(isinstance(x, float) for x in embedding):
            print("✅ Embedding validation passed")
            return True, embedding, metadata
        else:
            print("❌ Embedding validation failed")
            return False, None, None
            
    except Exception as e:
        print(f"❌ Buyer vectorization failed: {e}")
        return False, None, None


async def test_similarity_calculation():
    """Test vector similarity calculation."""
    print("\n🔗 Testing similarity calculation...")
    
    try:
        vectorizer = PropertyVectorizer()
        
        # Generate embeddings for similar properties
        property1 = PropertyFeatures(
            property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
            land_size=0, building_size=85, price=850000,
            suburb="Surry Hills", postcode="2010",
            latitude=-33.8858, longitude=151.2131,
            title="Modern Apartment", description="Modern apartment with city views",
            features_list=["modern", "city_views", "balcony"], days_on_market=14,
            price_per_sqm=10000, suburb_price_percentile=75,
            agent_name="Agent 1", agency_name="Agency 1",
            amenities={}, market_context={}
        )
        
        property2 = PropertyFeatures(
            property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
            land_size=0, building_size=90, price=870000,
            suburb="Surry Hills", postcode="2010",
            latitude=-33.8860, longitude=151.2130,
            title="Contemporary Apartment", description="Contemporary apartment with harbor glimpses",
            features_list=["contemporary", "harbor_views", "balcony"], days_on_market=10,
            price_per_sqm=9666, suburb_price_percentile=78,
            agent_name="Agent 2", agency_name="Agency 2",
            amenities={}, market_context={}
        )
        
        # Different property
        property3 = PropertyFeatures(
            property_type="house", bedrooms=4, bathrooms=3, car_spaces=2,
            land_size=600, building_size=200, price=1800000,
            suburb="Mosman", postcode="2088",
            latitude=-33.8296, longitude=151.2441,
            title="Family House", description="Large family house with pool and garden",
            features_list=["pool", "garden", "family"], days_on_market=21,
            price_per_sqm=9000, suburb_price_percentile=85,
            agent_name="Agent 3", agency_name="Agency 3",
            amenities={}, market_context={}
        )
        
        # Generate embeddings
        emb1, _ = await vectorizer.generate_embedding(property1)
        emb2, _ = await vectorizer.generate_embedding(property2)
        emb3, _ = await vectorizer.generate_embedding(property3)
        
        # Calculate similarities
        similarity_similar = vectorizer.calculate_similarity(emb1, emb2)
        similarity_different = vectorizer.calculate_similarity(emb1, emb3)
        
        print(f"✅ Similarity between similar properties: {similarity_similar:.3f}")
        print(f"✅ Similarity between different properties: {similarity_different:.3f}")
        
        # Validate that similar properties have higher similarity
        if similarity_similar > similarity_different:
            print("✅ Similarity calculation working correctly")
            return True
        else:
            print("❌ Similarity calculation may not be working as expected")
            return False
            
    except Exception as e:
        print(f"❌ Similarity calculation failed: {e}")
        return False


async def test_vector_search():
    """Test vector search functionality."""
    print("\n🔍 Testing vector search...")
    
    try:
        client = WeaviateClient()
        await client.connect()
        
        # Create schema
        schema = {
            "class": "TestProperty",
            "description": "Test property for vector search",
            "vectorizer": "none",
            "properties": [
                {"name": "address", "dataType": ["text"]},
                {"name": "suburb", "dataType": ["text"]},
                {"name": "property_type", "dataType": ["text"]},
                {"name": "price", "dataType": ["number"]},
                {"name": "description", "dataType": ["text"]}
            ]
        }
        
        await client.create_schema(schema)
        
        # Create test properties with embeddings
        vectorizer = PropertyVectorizer()
        test_properties = [
            {
                "id": "prop1",
                "address": "123 Test Street, Surry Hills",
                "suburb": "Surry Hills",
                "property_type": "apartment",
                "price": 850000,
                "description": "Modern apartment with city views",
                "features": PropertyFeatures(
                    property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
                    land_size=0, building_size=85, price=850000,
                    suburb="Surry Hills", postcode="2010",
                    latitude=-33.8858, longitude=151.2131,
                    title="Modern Apartment", description="Modern apartment with city views",
                    features_list=["modern", "city_views"], days_on_market=14,
                    price_per_sqm=10000, suburb_price_percentile=75,
                    agent_name="Agent", agency_name="Agency",
                    amenities={}, market_context={}
                )
            },
            {
                "id": "prop2",
                "address": "456 Beach Road, Bondi",
                "suburb": "Bondi",
                "property_type": "house",
                "price": 1200000,
                "description": "Beach house with ocean views",
                "features": PropertyFeatures(
                    property_type="house", bedrooms=3, bathrooms=2, car_spaces=2,
                    land_size=320, building_size=150, price=1200000,
                    suburb="Bondi", postcode="2026",
                    latitude=-33.8915, longitude=151.2767,
                    title="Beach House", description="Beach house with ocean views",
                    features_list=["ocean_views", "beach"], days_on_market=7,
                    price_per_sqm=8000, suburb_price_percentile=60,
                    agent_name="Agent", agency_name="Agency",
                    amenities={}, market_context={}
                )
            }
        ]
        
        # Insert properties with embeddings
        for prop in test_properties:
            embedding, _ = await vectorizer.generate_embedding(prop["features"])
            await client.insert_object(
                class_name="TestProperty",
                properties={k: v for k, v in prop.items() if k != "features"},
                vector=embedding,
                object_id=prop["id"]
            )
        
        print("✅ Test properties inserted")
        
        # Test vector search
        query_features = PropertyFeatures(
            property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
            land_size=0, building_size=80, price=800000,
            suburb="Sydney", postcode="2000",
            latitude=-33.8688, longitude=151.2093,
            title="Search Query", description="Looking for modern apartment",
            features_list=["modern", "apartment"], days_on_market=0,
            price_per_sqm=10000, suburb_price_percentile=50,
            agent_name="", agency_name="",
            amenities={}, market_context={}
        )
        
        query_embedding, _ = await vectorizer.generate_embedding(query_features)
        
        search_query = SearchQuery(
            vector=query_embedding,
            class_name="TestProperty",
            limit=2,
            additional_properties=["certainty"]
        )
        
        results = await client.vector_search(search_query)
        
        print(f"✅ Vector search returned {len(results)} results")
        for i, result in enumerate(results):
            print(f"   Result {i+1}: {result.data.get('address')} (score: {result.score:.3f})")
        
        # Clean up
        await client.delete_schema("TestProperty")
        
        return len(results) > 0
        
    except Exception as e:
        print(f"❌ Vector search failed: {e}")
        return False


async def main():
    """Run embeddings validation tests."""
    print("🧠 Starting Embeddings Validation Tests")
    print("=" * 50)
    
    results = []
    
    # Test property vectorization
    prop_success, prop_embedding, prop_metadata = await test_property_vectorization()
    results.append(prop_success)
    
    # Test buyer vectorization
    buyer_success, buyer_embedding, buyer_metadata = await test_buyer_vectorization()
    results.append(buyer_success)
    
    # Test similarity calculation
    results.append(await test_similarity_calculation())
    
    # Test vector search
    results.append(await test_vector_search())
    
    # Summary
    print("\n📊 EMBEDDINGS TEST SUMMARY")
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    print(f"Success rate: {(passed/total)*100:.1f}%")
    
    if prop_success and prop_embedding:
        print(f"Property embedding dimensions: {len(prop_embedding)}")
    if buyer_success and buyer_embedding:
        print(f"Buyer embedding dimensions: {len(buyer_embedding)}")
    
    if passed == total:
        print("✅ All embeddings tests passed - Vector system is ready!")
    else:
        print("❌ Some embeddings tests failed - check implementation")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)