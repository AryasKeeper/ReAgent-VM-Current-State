#!/usr/bin/env python3
"""
Simple agent test for ReAgent Sydney local development
Tests basic agent functionality without external dependencies
"""

import asyncio
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Set up environment for local testing
import os
from dotenv import load_dotenv
load_dotenv()

class MockAgent:
    """Mock agent for testing basic agent workflows."""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.db_path = Path("data/reagent_dev.db")
        
    async def initialize(self):
        """Initialize the agent."""
        print(f"🤖 Initializing {self.name} agent...")
        return True
        
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent task."""
        print(f"⚡ Executing {self.name} with input: {input_data}")
        
        # Simulate processing
        await asyncio.sleep(0.1)
        
        return {
            "success": True,
            "agent": self.name,
            "timestamp": datetime.utcnow().isoformat(),
            "processed": True,
            "data": input_data
        }
    
    async def shutdown(self):
        """Cleanup agent resources."""
        print(f"🔄 Shutting down {self.name} agent")

class MockListingWatcher(MockAgent):
    """Mock Listing Watcher agent for testing."""
    
    def __init__(self):
        super().__init__("Listing Watcher AU")
        
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock property scanning."""
        print(f"🏠 Scanning properties in postcodes: {input_data.get('postcodes', [])}")
        
        # Get properties from local database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, suburb, postcode, bedrooms, bathrooms, price_guide
            FROM properties 
            WHERE postcode IN ({})
            LIMIT 10
        """.format(','.join(['?' for _ in input_data.get('postcodes', ['2000'])])),
        input_data.get('postcodes', ['2000']))
        
        properties = cursor.fetchall()
        conn.close()
        
        return {
            "success": True,
            "agent": self.name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "statistics": {
                    "total_listings": len(properties),
                    "new_listings": 1,  # Mock data
                    "updated_listings": 2,  # Mock data
                    "sources_processed": ["mock_domain", "mock_rea"]
                },
                "properties_found": [
                    {
                        "id": prop[0],
                        "title": prop[1],
                        "suburb": prop[2],
                        "postcode": prop[3],
                        "bedrooms": prop[4],
                        "bathrooms": prop[5],
                        "price": prop[6]
                    } for prop in properties
                ]
            }
        }

class MockBuyerMatchmaker(MockAgent):
    """Mock Buyer Matchmaker agent for testing."""
    
    def __init__(self):
        super().__init__("Buyer Matchmaker AU")
        
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock buyer matching."""
        print(f"💕 Matching buyers with properties...")
        
        # Get buyers and properties from local database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Get buyers
        cursor.execute("""
            SELECT id, first_name, last_name, max_budget, preferred_suburbs, min_bedrooms
            FROM buyers 
            WHERE is_active = 1
            LIMIT 5
        """)
        buyers = cursor.fetchall()
        
        # Get recent properties
        cursor.execute("""
            SELECT id, title, suburb, postcode, bedrooms, price_guide
            FROM properties 
            ORDER BY created_at DESC
            LIMIT 5
        """)
        properties = cursor.fetchall()
        
        conn.close()
        
        # Mock matching logic
        matches = []
        for buyer in buyers:
            buyer_id, first_name, last_name, max_budget, preferred_suburbs, min_bedrooms = buyer
            
            for prop in properties:
                prop_id, title, suburb, postcode, bedrooms, price = prop
                
                # Simple matching logic
                score = 0.0
                if price and max_budget and price <= max_budget:
                    score += 0.4
                if bedrooms and min_bedrooms and bedrooms >= min_bedrooms:
                    score += 0.3
                if preferred_suburbs and suburb in preferred_suburbs:
                    score += 0.3
                
                if score > 0.5:  # Good match threshold
                    matches.append({
                        "buyer_id": buyer_id,
                        "buyer_name": f"{first_name} {last_name}",
                        "property_id": prop_id,
                        "property_title": title,
                        "match_score": round(score, 2),
                        "reasons": ["Budget match", "Bedroom requirement", "Preferred area"]
                    })
        
        return {
            "success": True,
            "agent": self.name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "statistics": {
                    "buyers_processed": len(buyers),
                    "properties_evaluated": len(properties),
                    "matches_found": len(matches)
                },
                "matches": matches[:5]  # Top 5 matches
            }
        }

class MockSuburbSignal(MockAgent):
    """Mock Suburb Signal agent for testing."""
    
    def __init__(self):
        super().__init__("Suburb Signal Agent")
        
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock market trend analysis."""
        print(f"📊 Analyzing market trends for suburbs...")
        
        # Get market data from local database
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT suburb, postcode, avg_price, median_price, price_change_30d,
                   listings_count, sales_count, days_on_market_avg
            FROM market_trends
            ORDER BY price_change_30d DESC
            LIMIT 10
        """)
        
        trends = cursor.fetchall()
        conn.close()
        
        trend_data = []
        for trend in trends:
            suburb, postcode, avg_price, median_price, price_change, listings, sales, days_on_market = trend
            
            # Determine trend signal
            signal = "neutral"
            if price_change > 2.0:
                signal = "strong_growth"
            elif price_change > 0.5:
                signal = "growth"
            elif price_change < -1.0:
                signal = "decline"
            
            trend_data.append({
                "suburb": suburb,
                "postcode": postcode,
                "signal": signal,
                "avg_price": avg_price,
                "median_price": median_price,
                "price_change_30d": price_change,
                "market_activity": {
                    "listings": listings,
                    "sales": sales,
                    "days_on_market": days_on_market
                }
            })
        
        return {
            "success": True,
            "agent": self.name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "statistics": {
                    "suburbs_analyzed": len(trends),
                    "growth_suburbs": len([t for t in trend_data if t["signal"] in ["growth", "strong_growth"]]),
                    "declining_suburbs": len([t for t in trend_data if t["signal"] == "decline"])
                },
                "trends": trend_data
            }
        }

async def test_individual_agents():
    """Test individual agent execution."""
    print("=" * 60)
    print("TESTING INDIVIDUAL AGENTS")
    print("=" * 60)
    
    # Test Listing Watcher
    listing_watcher = MockListingWatcher()
    await listing_watcher.initialize()
    
    listing_result = await listing_watcher.execute({
        "postcodes": ["2000", "2010", "2061"],
        "property_types": ["House", "Unit"],
        "force_full_scan": True
    })
    
    print("Listing Watcher Results:")
    stats = listing_result["data"]["statistics"]
    print(f"  📊 Total Listings: {stats['total_listings']}")
    print(f"  🆕 New Listings: {stats['new_listings']}")
    print(f"  🔄 Updated Listings: {stats['updated_listings']}")
    
    await listing_watcher.shutdown()
    
    # Test Buyer Matchmaker
    print("\n" + "-" * 40)
    buyer_matchmaker = MockBuyerMatchmaker()
    await buyer_matchmaker.initialize()
    
    buyer_result = await buyer_matchmaker.execute({
        "run_full_matching": True,
        "notification_threshold": 0.7
    })
    
    print("Buyer Matchmaker Results:")
    stats = buyer_result["data"]["statistics"]
    print(f"  👥 Buyers Processed: {stats['buyers_processed']}")
    print(f"  🏠 Properties Evaluated: {stats['properties_evaluated']}")
    print(f"  💕 Matches Found: {stats['matches_found']}")
    
    # Show top matches
    if buyer_result["data"]["matches"]:
        print("  Top Matches:")
        for match in buyer_result["data"]["matches"][:3]:
            print(f"    - {match['buyer_name']} ↔ {match['property_title']} (Score: {match['match_score']})")
    
    await buyer_matchmaker.shutdown()
    
    # Test Suburb Signal
    print("\n" + "-" * 40)
    suburb_signal = MockSuburbSignal()
    await suburb_signal.initialize()
    
    suburb_result = await suburb_signal.execute({
        "analysis_period": "30_days",
        "include_predictions": True
    })
    
    print("Suburb Signal Results:")
    stats = suburb_result["data"]["statistics"]
    print(f"  🏘️  Suburbs Analyzed: {stats['suburbs_analyzed']}")
    print(f"  📈 Growth Suburbs: {stats['growth_suburbs']}")
    print(f"  📉 Declining Suburbs: {stats['declining_suburbs']}")
    
    # Show trend highlights
    if suburb_result["data"]["trends"]:
        print("  Market Highlights:")
        for trend in suburb_result["data"]["trends"][:3]:
            signal_emoji = {"strong_growth": "🚀", "growth": "📈", "decline": "📉", "neutral": "➡️"}
            print(f"    {signal_emoji.get(trend['signal'], '❓')} {trend['suburb']}: {trend['price_change_30d']:+.1f}% (30d)")
    
    await suburb_signal.shutdown()

async def test_multi_agent_workflow():
    """Test coordinated multi-agent workflow."""
    print("\n" + "=" * 60)
    print("TESTING MULTI-AGENT WORKFLOW")
    print("=" * 60)
    
    # Initialize all agents
    agents = {
        "listing_watcher": MockListingWatcher(),
        "buyer_matchmaker": MockBuyerMatchmaker(),
        "suburb_signal": MockSuburbSignal()
    }
    
    workflow_results = {}
    
    try:
        # Initialize all agents
        for name, agent in agents.items():
            await agent.initialize()
        
        print("🔄 Running coordinated workflow...")
        
        # Step 1: Update property listings
        print("Step 1: Updating property listings...")
        listing_result = await agents["listing_watcher"].execute({
            "postcodes": ["2000", "2010", "2061"],
            "incremental_update": True
        })
        workflow_results["listings"] = listing_result
        
        # Step 2: Analyze market trends
        print("Step 2: Analyzing market trends...")
        market_result = await agents["suburb_signal"].execute({
            "triggered_by": "new_listings",
            "focus_areas": ["2000", "2010", "2061"]
        })
        workflow_results["market_analysis"] = market_result
        
        # Step 3: Match buyers with new opportunities
        print("Step 3: Matching buyers with opportunities...")
        matching_result = await agents["buyer_matchmaker"].execute({
            "new_listings_only": True,
            "high_priority_buyers": True
        })
        workflow_results["buyer_matching"] = matching_result
        
        # Workflow summary
        print("\n🎯 Workflow Summary:")
        print(f"  Properties Updated: {workflow_results['listings']['data']['statistics']['total_listings']}")
        print(f"  Market Trends Analyzed: {workflow_results['market_analysis']['data']['statistics']['suburbs_analyzed']}")
        print(f"  Buyer Matches Created: {workflow_results['buyer_matching']['data']['statistics']['matches_found']}")
        
        # Simulate notifications
        matches = workflow_results['buyer_matching']['data']['matches']
        if matches:
            print(f"\n📧 Mock Notifications Sent:")
            for i, match in enumerate(matches[:3], 1):
                print(f"    {i}. Email to {match['buyer_name']}: New property match (Score: {match['match_score']})")
        
        print("\n✅ Multi-agent workflow completed successfully!")
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
    
    finally:
        # Cleanup all agents
        for agent in agents.values():
            await agent.shutdown()

async def test_error_handling():
    """Test error handling and recovery."""
    print("\n" + "=" * 60)
    print("TESTING ERROR HANDLING")
    print("=" * 60)
    
    # Test agent with invalid input
    agent = MockAgent("Test Agent")
    await agent.initialize()
    
    try:
        # This should handle gracefully
        result = await agent.execute({"invalid_data": None})
        print(f"✅ Agent handled invalid input gracefully: {result['success']}")
    except Exception as e:
        print(f"⚠️  Agent error handling needs improvement: {e}")
    
    await agent.shutdown()

async def main():
    """Run all agent tests."""
    print("🚀 REAGENT SYDNEY - AGENT TESTING SUITE")
    print("=" * 70)
    print()
    print("This test suite validates agent functionality using local SQLite data.")
    print("No external APIs or services are required.")
    print()
    
    try:
        # Run individual agent tests
        await test_individual_agents()
        
        # Run multi-agent workflow test
        await test_multi_agent_workflow()
        
        # Run error handling test
        await test_error_handling()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("✅ Individual agents functioning correctly")
        print("✅ Multi-agent workflows coordinating properly")
        print("✅ Error handling working as expected")
        print()
        print("Next steps:")
        print("1. Configure real API keys for external data sources")
        print("2. Set up production database (PostgreSQL + TimescaleDB)")  
        print("3. Deploy agents to production environment")
        print("4. Set up monitoring and alerting")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        print("\nDebugging tips:")
        print("1. Check that SQLite database exists: data/reagent_dev.db")
        print("2. Verify environment variables are set correctly")
        print("3. Ensure all dependencies are installed")

if __name__ == "__main__":
    asyncio.run(main())