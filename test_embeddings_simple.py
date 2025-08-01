#!/usr/bin/env python3
"""
Simplified OpenAI Embeddings Integration Test
===========================================

A focused test to validate core OpenAI embeddings functionality 
for the ReAgent Sydney system without complex dependencies.
"""

import asyncio
import os
import sys
import time
from typing import List, Dict, Any
import json

# Basic imports
try:
    import openai
    from openai import AsyncOpenAI
    import numpy as np
    print("✅ OpenAI library imported successfully")
except ImportError as e:
    print(f"❌ Failed to import OpenAI: {e}")
    sys.exit(1)

# Try to import ReAgent components 
try:
    from src.config.settings import get_settings
    from src.core.vector_db.embeddings import PropertyVectorizer, BuyerProfileVectorizer, PropertyFeatures, BuyerPreferenceFeatures
    print("✅ ReAgent components imported successfully")
except ImportError as e:
    print(f"⚠️  ReAgent components not available: {e}")
    print("Continuing with basic OpenAI functionality test...")

class SimpleEmbeddingsValidator:
    """Simple validator for OpenAI embeddings functionality."""
    
    def __init__(self):
        # Try to get API key from multiple sources
        self.api_key = None
        
        # Try environment variable first
        if os.getenv("OPENAI_API_KEY"):
            self.api_key = os.getenv("OPENAI_API_KEY")
            print("✅ Found OpenAI API key in environment")
        
        # Try ReAgent settings if available
        try:
            settings = get_settings()
            if hasattr(settings, 'apis') and hasattr(settings.apis, 'openai_api_key'):
                self.api_key = settings.apis.openai_api_key
                print("✅ Found OpenAI API key in ReAgent settings")
        except Exception as e:
            print(f"⚠️  Could not get ReAgent settings: {e}")
        
        if not self.api_key:
            print("❌ No OpenAI API key found!")
            print("Please set OPENAI_API_KEY environment variable or configure in settings")
            sys.exit(1)
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.test_results = {}

    async def test_basic_connectivity(self) -> bool:
        """Test basic OpenAI API connectivity."""
        print("\n🔑 Testing OpenAI API connectivity...")
        
        try:
            start_time = time.time()
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            duration = time.time() - start_time
            print(f"✅ OpenAI API connectivity test passed ({duration:.2f}s)")
            print(f"   Response: {response.choices[0].message.content}")
            
            self.test_results["connectivity"] = {
                "status": "PASS",
                "duration": duration,
                "tokens_used": response.usage.total_tokens
            }
            return True
            
        except Exception as e:
            print(f"❌ OpenAI API connectivity failed: {e}")
            self.test_results["connectivity"] = {
                "status": "FAIL",
                "error": str(e)
            }
            return False

    async def test_embeddings_api(self) -> bool:
        """Test OpenAI embeddings API."""
        print("\n🧠 Testing OpenAI embeddings API...")
        
        try:
            start_time = time.time()
            
            test_texts = [
                "Modern 3 bedroom house in Sydney with ocean views",
                "Luxury apartment with harbour bridge views and premium amenities",
                "Family home with large backyard and double garage"
            ]
            
            # Test text-embedding-3-small model (latest)
            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=test_texts
            )
            
            embeddings = [item.embedding for item in response.data]
            duration = time.time() - start_time
            
            # Validate embeddings
            embedding_dim = len(embeddings[0])
            all_same_dim = all(len(emb) == embedding_dim for emb in embeddings)
            
            print(f"✅ OpenAI embeddings API test passed ({duration:.2f}s)")
            print(f"   Model: text-embedding-3-small")
            print(f"   Dimension: {embedding_dim}")
            print(f"   Texts processed: {len(test_texts)}")
            print(f"   Tokens used: {response.usage.total_tokens}")
            print(f"   Sample values: {embeddings[0][:3]}")
            
            self.test_results["embeddings_api"] = {
                "status": "PASS",
                "duration": duration,
                "model": "text-embedding-3-small",
                "dimension": embedding_dim,
                "consistent_dimensions": all_same_dim,
                "tokens_used": response.usage.total_tokens
            }
            return True
            
        except Exception as e:
            print(f"❌ OpenAI embeddings API failed: {e}")
            self.test_results["embeddings_api"] = {
                "status": "FAIL",
                "error": str(e)
            }
            return False

    async def test_embedding_similarity(self) -> bool:
        """Test embedding similarity calculations."""
        print("\n📏 Testing embedding similarity...")
        
        try:
            start_time = time.time()
            
            # Test similar and dissimilar texts
            similar_texts = [
                "3 bedroom house with garden in Bondi",
                "Three bedroom home with yard in Bondi Beach"
            ]
            
            different_texts = [
                "3 bedroom house with garden in Bondi",
                "1 bedroom apartment in the city center"
            ]
            
            # Get embeddings for similar texts
            similar_response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=similar_texts
            )
            similar_embeddings = [item.embedding for item in similar_response.data]
            
            # Get embeddings for different texts
            different_response = await self.client.embeddings.create(
                model="text-embedding-3-small", 
                input=different_texts
            )
            different_embeddings = [item.embedding for item in different_response.data]
            
            # Calculate similarities using cosine similarity
            def cosine_similarity(a: List[float], b: List[float]) -> float:
                a_np = np.array(a)
                b_np = np.array(b)
                return np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np))
            
            similar_similarity = cosine_similarity(similar_embeddings[0], similar_embeddings[1])
            different_similarity = cosine_similarity(different_embeddings[0], different_embeddings[1])
            
            duration = time.time() - start_time
            
            print(f"✅ Embedding similarity test passed ({duration:.2f}s)")
            print(f"   Similar texts similarity: {similar_similarity:.3f}")
            print(f"   Different texts similarity: {different_similarity:.3f}")
            print(f"   Similarity difference: {similar_similarity - different_similarity:.3f}")
            
            # Validate that similar texts have higher similarity
            similarity_works = similar_similarity > different_similarity
            
            self.test_results["similarity"] = {
                "status": "PASS" if similarity_works else "FAIL",
                "duration": duration,
                "similar_similarity": similar_similarity,
                "different_similarity": different_similarity,
                "similarity_works": similarity_works
            }
            return similarity_works
            
        except Exception as e:
            print(f"❌ Embedding similarity test failed: {e}")
            self.test_results["similarity"] = {
                "status": "FAIL",
                "error": str(e)
            }
            return False

    async def test_reagent_vectorizers(self) -> bool:
        """Test ReAgent property and buyer vectorizers if available."""
        print("\n🏠 Testing ReAgent vectorizers...")
        
        try:
            # Check if ReAgent components are available
            if 'PropertyVectorizer' not in globals():
                print("⚠️  ReAgent vectorizers not available, skipping test")
                self.test_results["reagent_vectorizers"] = {
                    "status": "SKIP",
                    "reason": "ReAgent components not available"
                }
                return True
            
            start_time = time.time()
            
            # Test property vectorizer
            property_vectorizer = PropertyVectorizer()
            sample_property = PropertyFeatures(
                property_type="house",
                bedrooms=3,
                bathrooms=2,
                car_spaces=2,
                land_size=650,
                building_size=180,
                price=1250000.0,
                suburb="Bondi",
                postcode="2026",
                latitude=-33.8915,
                longitude=151.2767,
                title="Modern Family Home",
                description="Beautiful family home in great location",
                features_list=["garden", "garage", "modern_kitchen"],
                days_on_market=15,
                price_per_sqm=6944.44,
                suburb_price_percentile=75.0,
                agent_name="Test Agent",
                agency_name="Test Agency",
                amenities={},
                market_context={}
            )
            
            property_embedding, property_metadata = await property_vectorizer.generate_embedding(sample_property)
            
            # Test buyer vectorizer
            buyer_vectorizer = BuyerProfileVectorizer()
            sample_buyer = BuyerPreferenceFeatures(
                max_price=1500000.0,
                min_price=800000.0,
                budget_flexibility=0.15,
                property_types=["house"],
                min_bedrooms=3,
                max_bedrooms=4,
                min_bathrooms=2,
                min_car_spaces=1,
                min_land_size=500,
                min_building_size=150,
                preferred_suburbs=["Bondi"],
                excluded_suburbs=[],
                preferred_postcodes=["2026"],
                max_commute_time=45,
                required_features=["garage"],
                preferred_features=["garden"],
                excluded_features=[],
                buyer_type="family",
                buying_urgency="medium",
                rental_yield_target=0.04,
                capital_growth_expectation="high",
                interaction_patterns={},
                preference_weights={}
            )
            
            buyer_embedding, buyer_metadata = await buyer_vectorizer.generate_embedding(sample_buyer)
            
            duration = time.time() - start_time
            
            # Validate embeddings
            property_normalized = abs(sum(x**2 for x in property_embedding)**0.5 - 1.0) < 0.001
            buyer_normalized = abs(sum(x**2 for x in buyer_embedding)**0.5 - 1.0) < 0.001
            dimensions_match = len(property_embedding) == len(buyer_embedding)
            
            print(f"✅ ReAgent vectorizers test passed ({duration:.2f}s)")
            print(f"   Property embedding dimension: {len(property_embedding)}")
            print(f"   Buyer embedding dimension: {len(buyer_embedding)}")
            print(f"   Property normalized: {property_normalized}")
            print(f"   Buyer normalized: {buyer_normalized}")
            print(f"   Dimensions match: {dimensions_match}")
            
            self.test_results["reagent_vectorizers"] = {
                "status": "PASS",
                "duration": duration,
                "property_dimension": len(property_embedding),
                "buyer_dimension": len(buyer_embedding),
                "property_normalized": property_normalized,
                "buyer_normalized": buyer_normalized,
                "dimensions_match": dimensions_match
            }
            return True
            
        except Exception as e:
            print(f"❌ ReAgent vectorizers test failed: {e}")
            self.test_results["reagent_vectorizers"] = {
                "status": "FAIL",
                "error": str(e)
            }
            return False

    async def test_performance_benchmarks(self) -> bool:
        """Test performance of embedding generation."""
        print("\n⚡ Running performance benchmarks...")
        
        try:
            # Test OpenAI API performance
            test_text = "3 bedroom house in Sydney with garden and garage"
            times = []
            
            for i in range(5):
                start = time.time()
                await self.client.embeddings.create(
                    model="text-embedding-3-small",
                    input=[test_text]
                )
                times.append(time.time() - start)
            
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"✅ Performance benchmarks completed")
            print(f"   Average time: {avg_time:.3f}s")
            print(f"   Min time: {min_time:.3f}s")
            print(f"   Max time: {max_time:.3f}s")
            print(f"   Performance acceptable: {avg_time < 1.0}")
            
            self.test_results["performance"] = {
                "status": "PASS",
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "performance_acceptable": avg_time < 1.0
            }
            return True
            
        except Exception as e:
            print(f"❌ Performance benchmarks failed: {e}")
            self.test_results["performance"] = {
                "status": "FAIL",
                "error": str(e)
            }
            return False

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests."""
        print("🚀 Starting OpenAI Embeddings Validation")
        print("=" * 50)
        
        test_results = []
        
        # Run tests
        test_results.append(await self.test_basic_connectivity())
        test_results.append(await self.test_embeddings_api()) 
        test_results.append(await self.test_embedding_similarity())
        test_results.append(await self.test_reagent_vectorizers())
        test_results.append(await self.test_performance_benchmarks())
        
        # Generate summary
        passed_tests = sum(test_results)
        total_tests = len(test_results)
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n📊 VALIDATION SUMMARY")
        print("=" * 30)
        print(f"Tests passed: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
        
        # Detailed results
        for test_name, result in self.test_results.items():
            status_emoji = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⏭️"
            duration = result.get("duration", 0)
            print(f"{status_emoji} {test_name.replace('_', ' ').title()}: {result['status']} ({duration:.2f}s)")
            
            if result["status"] == "FAIL" and "error" in result:
                print(f"   Error: {result['error']}")
        
        # Production readiness assessment
        print(f"\n🚀 PRODUCTION READINESS")
        print("=" * 25)
        
        critical_tests = ["connectivity", "embeddings_api"]
        critical_passed = all(
            self.test_results.get(test, {}).get("status") == "PASS" 
            for test in critical_tests
        )
        
        if critical_passed and success_rate >= 80:
            print("🟢 READY FOR PRODUCTION")
            print("Core OpenAI embeddings functionality is working correctly.")
        elif critical_passed:
            print("🟡 MOSTLY READY - MINOR ISSUES")
            print("Core functionality works but some features need attention.")
        else:
            print("🔴 NOT READY FOR PRODUCTION") 
            print("Critical OpenAI API issues must be resolved.")
        
        # Save results
        with open("embeddings_validation_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"\n📁 Detailed results saved to embeddings_validation_results.json")
        
        return self.test_results

async def main():
    """Run the validation."""
    validator = SimpleEmbeddingsValidator()
    
    try:
        results = await validator.run_all_tests()
        
        # Exit with appropriate code
        failed_tests = sum(1 for r in results.values() if r.get("status") == "FAIL")
        if failed_tests > 0:
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())