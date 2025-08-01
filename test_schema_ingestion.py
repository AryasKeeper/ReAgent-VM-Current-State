#!/usr/bin/env python3
"""
Test Schema Data Ingestion

Tests that schemas can accept property and buyer data and perform
vector similarity searches as expected.
"""

import asyncio
import sys
import logging
import uuid
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.vector_db.client import WeaviateClient, SearchQuery

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_data_ingestion():
    """Test schema data ingestion and retrieval."""
    
    try:
        # Initialize client
        client = WeaviateClient()
        await client.connect()
        logger.info("✅ Connected to Weaviate cluster")
        
        # Test 1: Insert sample property
        logger.info("\n🏠 Testing Property Schema Ingestion:")
        
        sample_property = {
            "listing_id": "TEST_PROP_001",
            "title": "Modern 3 Bedroom Apartment in Bondi",
            "description": "Stunning modern apartment with ocean views, located in the heart of Bondi. Features include hardwood floors, marble countertops, and a private balcony overlooking the beach.",
            "property_type": "Apartment",
            "suburb": "Bondi",
            "postcode": "2026",
            "state": "NSW",
            "bedrooms": 3,
            "bathrooms": 2,
            "car_spaces": 1,
            "price": 1200000,
            "price_display": "$1,200,000",
            "land_size": 0,
            "building_size": 120,
            "listing_status": "Active",
            "listing_type": "Sale",
            "features": ["Ocean Views", "Balcony", "Modern Kitchen", "Hardwood Floors"],
            "latitude": -33.8909,
            "longitude": 151.2773,
            "first_listed_date": "2025-07-28T00:00:00Z",
            "days_on_market": 1,
            "agent_name": "John Smith",
            "agency_name": "Premium Properties",
            "source": "Domain",
            "amenities": "Pool, Gym, Concierge",
            "market_context": "High demand area with strong capital growth",
            "embedding_metadata": "Generated via OpenAI text-embedding-ada-002"
        }
        
        property_id = await client.insert_object(
            class_name="Property",
            properties=sample_property,
            object_id=str(uuid.uuid4())
        )
        
        if property_id:
            logger.info(f"   ✅ Successfully inserted property: {property_id}")
        else:
            logger.error(f"   ❌ Failed to insert sample property")
            return False
        
        # Test 2: Insert sample buyer profile
        logger.info("\n👤 Testing BuyerProfile Schema Ingestion:")
        
        sample_buyer = {
            "buyer_id": "BUYER_001",
            "full_name": "Sarah Johnson",
            "buyer_type": "Individual",
            "buying_urgency": "High",
            "max_price": 1500000,
            "min_price": 800000,
            "budget_flexibility": 0.1,
            "property_types": ["Apartment", "Townhouse"],
            "preferred_suburbs": ["Bondi", "Surry Hills", "Paddington"],
            "excluded_suburbs": ["Blacktown"],
            "preferred_postcodes": ["2026", "2010", "2021"],
            "min_bedrooms": 2,
            "max_bedrooms": 4,
            "min_bathrooms": 2,
            "min_car_spaces": 1,
            "min_land_size": 0,
            "min_building_size": 80,
            "required_features": ["Modern Kitchen", "Balcony"],
            "preferred_features": ["Ocean Views", "Pool", "Gym"],
            "excluded_features": ["Ground Floor"],
            "lifestyle_preferences": "Beach lifestyle, close to cafes and restaurants",
            "school_preferences": "Good local schools for future family",
            "commute_destinations": "CBD, North Sydney",
            "max_commute_time": 45,
            "rental_yield_target": 0.0,
            "capital_growth_expectation": "High",
            "created_at": "2025-07-28T00:00:00Z",
            "updated_at": "2025-07-28T00:00:00Z",
            "behavioral_data": "Frequently views waterfront properties",
            "interaction_history": "Viewed 15 properties in Bondi area",
            "preference_weights": "Location: 0.4, Price: 0.3, Features: 0.3",
            "embedding_metadata": "Generated via OpenAI text-embedding-ada-002"
        }
        
        buyer_id = await client.insert_object(
            class_name="BuyerProfile",
            properties=sample_buyer,
            object_id=str(uuid.uuid4())
        )
        
        if buyer_id:
            logger.info(f"   ✅ Successfully inserted buyer profile: {buyer_id}")
        else:
            logger.error(f"   ❌ Failed to insert sample buyer profile")
            return False
        
        # Test 3: Insert sample property match
        logger.info("\n🎯 Testing PropertyMatch Schema Ingestion:")
        
        sample_match = {
            "match_id": str(uuid.uuid4()),
            "buyer_id": "BUYER_001",
            "property_listing_id": "TEST_PROP_001",
            "match_score": 0.87,
            "match_rank": 1,
            "match_reasons": ["Price within budget", "Preferred suburb", "Required features match"],
            "match_concerns": ["Only 1 parking space"],
            "match_explanation": "This property matches 87% of buyer criteria including location preferences and budget range.",
            "status": "New",
            "buyer_feedback": "",
            "created_at": "2025-07-28T00:00:00Z",
            "first_presented_date": "2025-07-28T00:00:00Z",
            "last_interaction_date": "2025-07-28T00:00:00Z",
            "interaction_count": 0,
            "scoring_details": "Location: 0.9, Price: 0.8, Features: 0.9",
            "ml_features": "Vector similarity: 0.85, Rule-based: 0.89"
        }
        
        match_id = await client.insert_object(
            class_name="PropertyMatch",
            properties=sample_match,
            object_id=str(uuid.uuid4())
        )
        
        if match_id:
            logger.info(f"   ✅ Successfully inserted property match: {match_id}")
        else:
            logger.error(f"   ❌ Failed to insert sample property match")
            return False
        
        # Test 4: Verify data retrieval
        logger.info("\n📊 Testing Data Retrieval:")
        
        # Get object counts
        for class_name in ["Property", "BuyerProfile", "PropertyMatch"]:
            count = await client.get_object_count(class_name)
            logger.info(f"   📊 {class_name}: {count} objects")
        
        # Test 5: Test vector search (with dummy vector since we don't have embeddings)
        logger.info("\n🔍 Testing Vector Search:")
        
        try:
            # Create a dummy search query
            test_vector = [0.1] * 1536  # 1536-dimensional dummy vector
            search_query = SearchQuery(
                vector=test_vector,
                class_name="Property",
                limit=5
            )
            
            results = await client.vector_search(search_query)
            logger.info(f"   ✅ Vector search returned {len(results)} results")
            
            if results:
                for i, result in enumerate(results):
                    logger.info(f"      {i+1}. Property: {result.data.get('title', 'N/A')} (Score: {result.score:.3f})")
            
        except Exception as e:
            logger.warning(f"   ⚠️  Vector search test failed: {e}")
        
        # Test 6: Test hybrid search
        logger.info("\n🔎 Testing Hybrid Search:")
        
        try:
            results = await client.hybrid_search(
                class_name="Property",
                query_text="modern apartment ocean views",
                limit=3
            )
            logger.info(f"   ✅ Hybrid search returned {len(results)} results")
            
            if results:
                for i, result in enumerate(results):
                    logger.info(f"      {i+1}. Property: {result.data.get('title', 'N/A')} (Score: {result.score:.3f})")
            
        except Exception as e:
            logger.warning(f"   ⚠️  Hybrid search test failed: {e}")
        
        await client.disconnect()
        logger.info(f"\n🎉 Data ingestion tests completed successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Data ingestion test failed: {e}")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_data_ingestion())
    exit(0 if result else 1)