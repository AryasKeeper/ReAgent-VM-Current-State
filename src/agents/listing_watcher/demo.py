"""
ReAgent Sydney - Listing Watcher Demo

Demonstration script showing how to use the Listing Watcher AU agent
for property monitoring and data collection.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from reagent_sydney.agents.listing_watcher import ListingWatcherAgent
from reagent_sydney.agents.listing_watcher.config import (
    ListingWatcherConfig, create_test_config, create_production_config
)
from reagent_sydney.config.settings import get_settings


async def demo_basic_usage():
    """Demonstrate basic Listing Watcher usage."""
    print("🏠 ReAgent Sydney - Listing Watcher Demo")
    print("=" * 50)
    
    # Create test configuration
    config = create_test_config()
    
    # Initialize agent
    agent = ListingWatcherAgent(config.to_dict())
    
    try:
        # Initialize the agent
        await agent.initialize()
        print(f"✅ Agent initialized: {agent.config.name}")
        
        # Execute property scan
        print("\n🔍 Starting property scan...")
        
        execution_input = {
            "config": {
                "postcodes": ["2000", "2001", "2010"],  # CBD areas
                "property_types": ["House", "Unit"],
                "force_full_scan": True
            }
        }
        
        result = await agent.execute(execution_input)
        
        print(f"📊 Scan Results:")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Success: {result.get('success', False)}")
        
        if result.get("success"):
            stats = result.get("data", {}).get("statistics", {})
            print(f"   Total Listings: {stats.get('total_listings', 0)}")
            print(f"   New Listings: {stats.get('new_listings', 0)}")
            print(f"   Updated Listings: {stats.get('updated_listings', 0)}")
            print(f"   Sources: {', '.join(stats.get('sources_processed', []))}")
        
        if result.get("error"):
            print(f"❌ Error: {result['error']}")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
    
    finally:
        # Cleanup
        await agent.shutdown()
        print("\n✅ Agent shutdown complete")


async def demo_api_clients():
    """Demonstrate API client usage."""
    print("\n🌐 API Clients Demo")
    print("-" * 30)
    
    from reagent_sydney.services.external_apis.domain_client import DomainAPIClient
    from reagent_sydney.services.external_apis.realestate_client import RealEstateAPIClient
    
    # Test Domain client
    print("Testing Domain API...")
    try:
        async with DomainAPIClient() as domain_client:
            health = await domain_client.get_health_status()
            print(f"Domain API Status: {health.get('status', 'unknown')}")
            
            # Small search test
            if health.get('api_accessible'):
                search_results = await domain_client.search_listings(
                    postcodes=["2000"],
                    max_results=5
                )
                listings_count = len(search_results.get("listings", []))
                print(f"Domain Sample Listings: {listings_count}")
    
    except Exception as e:
        print(f"Domain API Error: {e}")
    
    # Test RealEstate client
    print("\nTesting RealEstate API...")
    try:
        async with RealEstateAPIClient() as rea_client:
            health = await rea_client.get_health_status()
            print(f"RealEstate API Status: {health.get('status', 'unknown')}")
            
            # Small search test
            if health.get('api_accessible'):
                search_results = await rea_client.search_listings(
                    postcodes=["2000"],
                    max_results=5
                )
                
                # Count listings from tiered results
                listings_count = 0
                for tier in search_results.get("tieredResults", []):
                    listings_count += len(tier.get("results", []))
                
                print(f"RealEstate Sample Listings: {listings_count}")
    
    except Exception as e:
        print(f"RealEstate API Error: {e}")


async def demo_delta_detection():
    """Demonstrate delta detection capabilities."""
    print("\n🔄 Delta Detection Demo")
    print("-" * 30)
    
    from reagent_sydney.agents.listing_watcher.delta_detector import PropertyDeltaDetector
    
    detector = PropertyDeltaDetector()
    
    try:
        await detector.initialize()
        
        # Create sample property data
        sample_property = {
            "listing_id": "demo_12345",
            "title": "Beautiful 2BR Unit with Harbor Views",
            "price": 750000,
            "price_display": "$750,000",
            "suburb": "Neutral Bay",
            "bedrooms": 2,
            "bathrooms": 1,
            "features": ["Harbor Views", "Balcony", "Garage"]
        }
        
        # Test new listing detection
        result1 = await detector.detect_changes("demo_12345", sample_property)
        print(f"First Check - Is New: {result1['is_new']}")
        
        # Test change detection
        updated_property = sample_property.copy()
        updated_property["price"] = 725000  # Price drop
        updated_property["price_display"] = "$725,000"
        
        result2 = await detector.detect_changes("demo_12345", updated_property)
        print(f"Second Check - Has Changes: {result2['has_changes']}")
        
        if result2["has_changes"]:
            changes = result2["changes"]
            print(f"Changes detected: {list(changes.keys())}")
            if "price" in changes:
                old_price = changes["price"]["old_value"]
                new_price = changes["price"]["new_value"]
                print(f"Price change: ${old_price} → ${new_price}")
        
        # Get statistics
        stats = await detector.get_statistics()
        print(f"Known Listings: {stats.get('known_listings_count', 0)}")
        
    except Exception as e:
        print(f"Delta Detection Error: {e}")


async def demo_data_enrichment():
    """Demonstrate data enrichment capabilities."""
    print("\n✨ Data Enrichment Demo")
    print("-" * 30)
    
    from reagent_sydney.agents.listing_watcher.data_enricher import PropertyDataEnricher
    
    enricher = PropertyDataEnricher()
    
    try:
        await enricher.initialize()
        
        # Sample raw property data
        raw_property = {
            "listing_id": "enrich_demo_123",
            "title": "Stunning House with Pool",
            "description": "This beautiful 3 bedroom house features a sparkling pool, garage parking for 2 cars, and beautiful harbor views. Air conditioning throughout.",
            "suburb": "Mosman",
            "postcode": "2088",
            "property_type": "House",
            "bedrooms": 3,
            "bathrooms": 2,
            "price": 2800000,
            "latitude": -33.8365,
            "longitude": 151.2395
        }
        
        # Enrich the data
        enriched = await enricher.enrich_property_data(raw_property)
        
        print("Enrichment Results:")
        print(f"  Original Features: {raw_property.get('features', [])}")
        print(f"  Enriched Features: {enriched.get('features', [])}")
        print(f"  Search Keywords: {len(enriched.get('search_keywords', []))} generated")
        print(f"  Suburb Quality: {enriched.get('suburb_quality', 'unknown')}")
        print(f"  Distance to CBD: {enriched.get('distance_to_cbd_km', 'N/A')} km")
        print(f"  Location Convenience: {enriched.get('location_convenience', 'unknown')}")
        print(f"  Estimated Time to Sell: {enriched.get('estimated_time_to_sell', 'N/A')} days")
        
        # Show some extracted features
        features_count = len(enriched.get('features', []))
        if features_count > 0:
            print(f"  Sample Features: {enriched['features'][:5]}...")
        
    except Exception as e:
        print(f"Data Enrichment Error: {e}")


async def demo_configuration():
    """Demonstrate configuration options."""
    print("\n⚙️  Configuration Demo")
    print("-" * 30)
    
    # Show different configuration options
    test_config = create_test_config()
    prod_config = create_production_config()
    
    print("Test Configuration:")
    test_dict = test_config.to_dict()
    for key, value in test_dict.items():
        print(f"  {key}: {value}")
    
    print(f"\nActive Postcodes (Test): {len(test_config.get_active_postcodes())}")
    print(f"Active Postcodes (Prod): {len(prod_config.get_active_postcodes())}")
    
    # Show scraping schedule
    schedule = prod_config.get_scraping_schedule()
    print(f"\nProduction Schedule: {schedule}")
    
    # Show rate limits
    domain_limit = prod_config.get_rate_limit_for_source("domain")
    rea_limit = prod_config.get_rate_limit_for_source("realestate")
    print(f"Rate Limits - Domain: {domain_limit}/hour, RealEstate: {rea_limit}/hour")


async def main():
    """Run all demonstrations."""
    print("🚀 Starting ReAgent Sydney Listing Watcher Demonstrations")
    print("=" * 60)
    
    # Run demonstrations
    await demo_configuration()
    await demo_api_clients()
    await demo_delta_detection()
    await demo_data_enrichment()
    
    # Only run full agent demo if APIs are configured
    settings = get_settings()
    if settings.apis.domain_api_key or settings.apis.rea_api_key:
        await demo_basic_usage()
    else:
        print("\n⚠️  Skipping agent demo - API keys not configured")
        print("   Set DOMAIN_API_KEY or REA_API_KEY environment variables to test")
    
    print("\n🎉 Demo completed!")
    print("\nNext Steps:")
    print("1. Configure API keys in your .env file")
    print("2. Set up PostgreSQL and Redis connections")
    print("3. Run database migrations")
    print("4. Deploy the agent in production mode")


if __name__ == "__main__":
    asyncio.run(main())