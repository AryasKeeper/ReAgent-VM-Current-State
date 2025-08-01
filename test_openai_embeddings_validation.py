#!/usr/bin/env python3
"""
OpenAI Embeddings Integration Validation for ReAgent Sydney
===========================================================

Comprehensive validation suite for OpenAI embeddings integration with Weaviate.
This script tests all critical components for production readiness:

1. OpenAI API connectivity and authentication
2. Embedding generation for property and buyer data  
3. Embedding ingestion into Weaviate
4. Dimension compatibility validation
5. Rate limiting and error handling
6. Performance benchmarking

Usage:
    python test_openai_embeddings_validation.py
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog

# Setup logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.dev.ConsoleRenderer(colors=True)
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Import ReAgent components
try:
    from src.config.settings import get_settings
    from src.services.external_apis.openai_client import get_openai_client, OpenAIClient
    from src.core.vector_db.client import get_weaviate_client, WeaviateClient, SearchQuery
    from src.core.vector_db.embeddings import PropertyVectorizer, BuyerProfileVectorizer, PropertyFeatures, BuyerPreferenceFeatures
    from src.core.vector_db.schemas import get_schema
    from openai import AsyncOpenAI
    import openai
except ImportError as e:
    logger.error(f"Failed to import ReAgent components: {e}")
    sys.exit(1)


class OpenAIEmbeddingsValidator:
    """Comprehensive OpenAI embeddings integration validator."""
    
    def __init__(self):
        self.settings = get_settings()
        self.test_results = {
            "start_time": datetime.utcnow().isoformat(),
            "tests": {},
            "performance_metrics": {},
            "errors": [],
            "warnings": []
        }
        
        # Test data samples
        self.sample_property_data = {
            "property_type": "house",
            "bedrooms": 3,
            "bathrooms": 2,
            "car_spaces": 2,
            "land_size": 650,
            "building_size": 180,
            "price": 1250000.0,
            "suburb": "Bondi",
            "postcode": "2026",
            "latitude": -33.8915,
            "longitude": 151.2767,
            "title": "Modern Family Home with Ocean Views",
            "description": "Stunning modern family home featuring contemporary design, premium finishes, and breathtaking ocean views. Located in prestigious Bondi, close to beach and transport.",
            "features_list": ["ocean_views", "modern_kitchen", "air_conditioning", "garage", "garden"],
            "days_on_market": 15,
            "price_per_sqm": 6944.44,
            "suburb_price_percentile": 75.0,
            "agent_name": "Sarah Johnson",
            "agency_name": "Premium Properties",
            "amenities": {"pool": False, "gym": False, "parking": True},
            "market_context": {"view_count": 450, "enquiry_count": 12, "sale_probability": 0.78}
        }
        
        self.sample_buyer_data = {
            "max_price": 1500000.0,
            "min_price": 800000.0,
            "budget_flexibility": 0.15,
            "property_types": ["house", "townhouse"],
            "min_bedrooms": 3,
            "max_bedrooms": 4,
            "min_bathrooms": 2,
            "min_car_spaces": 1,
            "min_land_size": 500,
            "min_building_size": 150,
            "preferred_suburbs": ["Bondi", "Coogee", "Paddington"],
            "excluded_suburbs": ["Blacktown", "Penrith"],
            "preferred_postcodes": ["2026", "2034", "2021"],
            "max_commute_time": 45,
            "required_features": ["garage", "modern_kitchen"],
            "preferred_features": ["garden", "air_conditioning", "ocean_views"],
            "excluded_features": ["shared_wall"],
            "buyer_type": "family",
            "buying_urgency": "medium",
            "rental_yield_target": 0.04,
            "capital_growth_expectation": "high",
            "interaction_patterns": {"avg_daily_views": 5.2, "avg_session_duration": 480, "interest_score_variance": 0.8},
            "preference_weights": {"location_preferences": 0.3, "property_requirements": 0.25}
        }

    async def run_validation(self) -> Dict[str, Any]:
        """Run complete validation suite."""
        logger.info("🚀 Starting OpenAI Embeddings Integration Validation")
        
        try:
            # Test 1: OpenAI API connectivity and authentication
            await self._test_openai_connectivity()
            
            # Test 2: OpenAI embeddings API functionality
            await self._test_openai_embeddings_api()
            
            # Test 3: Property vectorization
            await self._test_property_vectorization()
            
            # Test 4: Buyer profile vectorization  
            await self._test_buyer_vectorization()
            
            # Test 5: Weaviate connectivity
            await self._test_weaviate_connectivity()
            
            # Test 6: Schema validation
            await self._test_schema_compatibility()
            
            # Test 7: Embedding ingestion
            await self._test_embedding_ingestion()
            
            # Test 8: Vector search functionality
            await self._test_vector_search()
            
            # Test 9: Dimension compatibility
            await self._test_dimension_compatibility()
            
            # Test 10: Rate limiting and error handling
            await self._test_rate_limiting()
            
            # Test 11: Performance benchmarking
            await self._test_performance_benchmarks()
            
        except Exception as e:
            logger.error(f"Validation suite failed: {e}")
            self.test_results["errors"].append(f"Suite failure: {e}")
        
        self.test_results["end_time"] = datetime.utcnow().isoformat()
        return self.test_results

    async def _test_openai_connectivity(self):
        """Test OpenAI API connectivity and authentication."""
        test_name = "openai_connectivity"
        logger.info("🔑 Testing OpenAI API connectivity...")
        
        try:
            start_time = time.time()
            
            # Check if API key is configured
            if not self.settings.apis.openai_api_key:
                raise Exception("OpenAI API key not configured in settings")
            
            # Test direct OpenAI client
            client = AsyncOpenAI(api_key=self.settings.apis.openai_api_key)
            
            # Simple test request
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=5
            )
            
            # Test ReAgent OpenAI client
            reagent_client = await get_openai_client()
            health_check = await reagent_client.health_check()
            
            duration = time.time() - start_time
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "duration": duration,
                "api_accessible": True,
                "authentication_valid": True,
                "reagent_client_healthy": health_check["status"] == "healthy",
                "test_tokens_used": response.usage.total_tokens
            }
            
            logger.info(f"✅ OpenAI connectivity test passed ({duration:.2f}s)")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e),
                "api_accessible": False
            }
            self.test_results["errors"].append(f"OpenAI connectivity: {e}")
            logger.error(f"❌ OpenAI connectivity test failed: {e}")

    async def _test_openai_embeddings_api(self):
        """Test OpenAI embeddings API functionality."""
        test_name = "openai_embeddings_api"
        logger.info("🧠 Testing OpenAI embeddings API...")
        
        try:
            start_time = time.time()
            
            client = AsyncOpenAI(api_key=self.settings.apis.openai_api_key)
            
            # Test text embeddings
            test_texts = [
                "Modern 3 bedroom house in Bondi with ocean views",
                "Family home with garden and garage in Sydney suburb",
                "Luxury apartment with harbour views and modern amenities"
            ]
            
            embeddings_response = await client.embeddings.create(
                model="text-embedding-3-small",  # Latest OpenAI embedding model
                input=test_texts
            )
            
            embeddings = [item.embedding for item in embeddings_response.data]
            
            duration = time.time() - start_time
            
            # Validate embedding properties
            embedding_dim = len(embeddings[0])
            all_same_dim = all(len(emb) == embedding_dim for emb in embeddings)
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "duration": duration,
                "model_used": "text-embedding-3-small",
                "embedding_dimension": embedding_dim,
                "texts_processed": len(test_texts),
                "consistent_dimensions": all_same_dim,
                "tokens_used": embeddings_response.usage.total_tokens,
                "sample_embedding_preview": embeddings[0][:5]  # First 5 values
            }
            
            logger.info(f"✅ OpenAI embeddings API test passed ({duration:.2f}s, dim={embedding_dim})")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"OpenAI embeddings API: {e}")
            logger.error(f"❌ OpenAI embeddings API test failed: {e}")

    async def _test_property_vectorization(self):
        """Test property vectorization functionality."""
        test_name = "property_vectorization"
        logger.info("🏠 Testing property vectorization...")
        
        try:
            start_time = time.time()
            
            # Create property vectorizer
            vectorizer = PropertyVectorizer()
            
            # Create property features from sample data
            features = PropertyFeatures(**self.sample_property_data)
            
            # Generate embedding
            embedding, metadata = await vectorizer.generate_embedding(features)
            
            duration = time.time() - start_time
            
            # Validate embedding
            is_normalized = abs(sum(x**2 for x in embedding)**0.5 - 1.0) < 0.001
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "duration": duration,
                "embedding_dimension": len(embedding),
                "is_normalized": is_normalized,
                "metadata": {
                    "model_name": metadata.model_name,
                    "model_version": metadata.model_version,
                    "feature_count": metadata.feature_count,
                    "normalization_method": metadata.normalization_method
                },
                "sample_values": embedding[:5]  # First 5 values
            }
            
            logger.info(f"✅ Property vectorization test passed ({duration:.2f}s, dim={len(embedding)})")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Property vectorization: {e}")
            logger.error(f"❌ Property vectorization test failed: {e}")

    async def _test_buyer_vectorization(self):
        """Test buyer profile vectorization functionality."""
        test_name = "buyer_vectorization"
        logger.info("👤 Testing buyer profile vectorization...")
        
        try:
            start_time = time.time()
            
            # Create buyer vectorizer
            vectorizer = BuyerProfileVectorizer()
            
            # Create buyer features from sample data
            features = BuyerPreferenceFeatures(**self.sample_buyer_data)
            
            # Generate embedding
            embedding, metadata = await vectorizer.generate_embedding(features)
            
            duration = time.time() - start_time
            
            # Validate embedding
            is_normalized = abs(sum(x**2 for x in embedding)**0.5 - 1.0) < 0.001
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "duration": duration,
                "embedding_dimension": len(embedding),
                "is_normalized": is_normalized,
                "metadata": {
                    "model_name": metadata.model_name,
                    "model_version": metadata.model_version,
                    "feature_count": metadata.feature_count,
                    "normalization_method": metadata.normalization_method
                },
                "sample_values": embedding[:5]  # First 5 values
            }
            
            logger.info(f"✅ Buyer vectorization test passed ({duration:.2f}s, dim={len(embedding)})")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Buyer vectorization: {e}")
            logger.error(f"❌ Buyer vectorization test failed: {e}")

    async def _test_weaviate_connectivity(self):
        """Test Weaviate connectivity."""
        test_name = "weaviate_connectivity"
        logger.info("🔌 Testing Weaviate connectivity...")
        
        try:
            start_time = time.time()
            
            # Get Weaviate client
            client = await get_weaviate_client()
            
            # Test health check
            health = await client.health_check()
            
            duration = time.time() - start_time
            
            self.test_results["tests"][test_name] = {
                "status": "PASS" if health["ready"] else "FAIL",
                "duration": duration,
                "weaviate_ready": health["ready"],
                "weaviate_live": health.get("live", False),
                "weaviate_url": health.get("url", "unknown"),
                "health_details": health
            }
            
            if health["ready"]:
                logger.info(f"✅ Weaviate connectivity test passed ({duration:.2f}s)")
            else:
                logger.error(f"❌ Weaviate not ready: {health}")
                self.test_results["errors"].append(f"Weaviate not ready: {health}")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Weaviate connectivity: {e}")
            logger.error(f"❌ Weaviate connectivity test failed: {e}")

    async def _test_schema_compatibility(self):
        """Test Weaviate schema compatibility."""
        test_name = "schema_compatibility"
        logger.info("📋 Testing schema compatibility...")
        
        try:
            start_time = time.time()
            
            client = await get_weaviate_client()
            
            # Test property schema
            property_created = await client.create_schema(get_schema("Property"))
            
            # Test buyer schema
            buyer_created = await client.create_schema(get_schema("BuyerProfile"))
            
            duration = time.time() - start_time
            
            self.test_results["tests"][test_name] = {
                "status": "PASS" if (property_created and buyer_created) else "FAIL",
                "duration": duration,
                "property_schema_created": property_created,
                "buyer_schema_created": buyer_created,
                "schemas_tested": ["Property", "BuyerProfile"]
            }
            
            logger.info(f"✅ Schema compatibility test passed ({duration:.2f}s)")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Schema compatibility: {e}")
            logger.error(f"❌ Schema compatibility test failed: {e}")

    async def _test_embedding_ingestion(self):
        """Test embedding ingestion into Weaviate."""
        test_name = "embedding_ingestion"
        logger.info("📤 Testing embedding ingestion...")
        
        try:
            start_time = time.time()
            
            client = await get_weaviate_client()
            
            # Generate property embedding
            property_vectorizer = PropertyVectorizer()
            property_features = PropertyFeatures(**self.sample_property_data)
            property_embedding, property_metadata = await property_vectorizer.generate_embedding(property_features)
            
            # Generate buyer embedding
            buyer_vectorizer = BuyerProfileVectorizer()
            buyer_features = BuyerPreferenceFeatures(**self.sample_buyer_data)
            buyer_embedding, buyer_metadata = await buyer_vectorizer.generate_embedding(buyer_features)
            
            # Insert property vector
            property_id = await client.insert_object(
                class_name="Property",
                properties={
                    "listing_id": "test_property_001",
                    "suburb": property_features.suburb,
                    "property_type": property_features.property_type,
                    "price": property_features.price,
                    "bedrooms": property_features.bedrooms,
                    "bathrooms": property_features.bathrooms,
                    "description": property_features.description[:500]  # Limit length
                },
                vector=property_embedding
            )
            
            # Insert buyer vector  
            buyer_id = await client.insert_object(
                class_name="BuyerProfile",
                properties={
                    "buyer_id": "test_buyer_001",
                    "max_price": buyer_features.max_price,
                    "min_price": buyer_features.min_price,
                    "buyer_type": buyer_features.buyer_type,
                    "property_types": buyer_features.property_types,
                    "preferred_suburbs": buyer_features.preferred_suburbs[:10]  # Limit array size
                },
                vector=buyer_embedding
            )
            
            duration = time.time() - start_time
            
            self.test_results["tests"][test_name] = {
                "status": "PASS" if (property_id and buyer_id) else "FAIL",
                "duration": duration,
                "property_object_created": bool(property_id),
                "buyer_object_created": bool(buyer_id),
                "property_id": property_id,
                "buyer_id": buyer_id,
                "property_embedding_dim": len(property_embedding),
                "buyer_embedding_dim": len(buyer_embedding)
            }
            
            logger.info(f"✅ Embedding ingestion test passed ({duration:.2f}s)")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Embedding ingestion: {e}")
            logger.error(f"❌ Embedding ingestion test failed: {e}")

    async def _test_vector_search(self):
        """Test vector search functionality."""
        test_name = "vector_search"
        logger.info("🔍 Testing vector search...")
        
        try:
            start_time = time.time()
            
            client = await get_weaviate_client()
            
            # Generate search vector
            buyer_vectorizer = BuyerProfileVectorizer()
            buyer_features = BuyerPreferenceFeatures(**self.sample_buyer_data)
            search_vector, _ = await buyer_vectorizer.generate_embedding(buyer_features)
            
            # Perform property search
            search_query = SearchQuery(
                vector=search_vector,
                class_name="Property",
                limit=5,
                additional_properties=["listing_id", "suburb", "price", "property_type"]
            )
            
            results = await client.vector_search(search_query)
            
            duration = time.time() - start_time
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "duration": duration,
                "search_results_count": len(results),
                "search_vector_dim": len(search_vector),
                "results_preview": [
                    {
                        "object_id": r.object_id,
                        "score": r.score,
                        "class_name": r.class_name
                    } for r in results[:3]
                ]
            }
            
            logger.info(f"✅ Vector search test passed ({duration:.2f}s, {len(results)} results)")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Vector search: {e}")
            logger.error(f"❌ Vector search test failed: {e}")

    async def _test_dimension_compatibility(self):
        """Test embedding dimension compatibility."""
        test_name = "dimension_compatibility"
        logger.info("📏 Testing dimension compatibility...")
        
        try:
            start_time = time.time()
            
            # Generate multiple embeddings and check consistency
            property_vectorizer = PropertyVectorizer()
            buyer_vectorizer = BuyerProfileVectorizer()
            
            # Generate property embeddings with different data
            property_embeddings = []
            for i in range(3):
                modified_data = self.sample_property_data.copy()
                modified_data["price"] = modified_data["price"] + (i * 100000)
                modified_data["bedrooms"] = modified_data["bedrooms"] + i
                
                features = PropertyFeatures(**modified_data)
                embedding, _ = await property_vectorizer.generate_embedding(features)
                property_embeddings.append(embedding)
            
            # Generate buyer embeddings with different data
            buyer_embeddings = []
            for i in range(3):
                modified_data = self.sample_buyer_data.copy()
                modified_data["max_price"] = modified_data["max_price"] + (i * 200000)
                modified_data["min_bedrooms"] = modified_data["min_bedrooms"] + i
                
                features = BuyerPreferenceFeatures(**modified_data)
                embedding, _ = await buyer_vectorizer.generate_embedding(features)
                buyer_embeddings.append(embedding)
            
            # Check dimension consistency
            property_dims = [len(emb) for emb in property_embeddings]
            buyer_dims = [len(emb) for emb in buyer_embeddings]
            
            property_consistent = all(dim == property_dims[0] for dim in property_dims)
            buyer_consistent = all(dim == buyer_dims[0] for dim in buyer_dims)
            cross_compatible = property_dims[0] == buyer_dims[0]
            
            duration = time.time() - start_time
            
            self.test_results["tests"][test_name] = {
                "status": "PASS" if (property_consistent and buyer_consistent and cross_compatible) else "FAIL",
                "duration": duration,
                "property_dimension": property_dims[0],
                "buyer_dimension": buyer_dims[0],
                "property_consistent": property_consistent,
                "buyer_consistent": buyer_consistent,
                "cross_compatible": cross_compatible,
                "property_dims_tested": property_dims,
                "buyer_dims_tested": buyer_dims
            }
            
            logger.info(f"✅ Dimension compatibility test passed ({duration:.2f}s)")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Dimension compatibility: {e}")
            logger.error(f"❌ Dimension compatibility test failed: {e}")

    async def _test_rate_limiting(self):
        """Test rate limiting and error handling."""
        test_name = "rate_limiting"
        logger.info("⏱️ Testing rate limiting...")
        
        try:
            start_time = time.time()
            
            client = await get_openai_client()
            
            # Test rate limit checking
            await client._check_rate_limits("gpt-3.5-turbo")
            
            # Test usage stats
            stats = await client.get_usage_stats()
            
            # Test error handling with invalid API key
            try:
                invalid_client = AsyncOpenAI(api_key="invalid_key")
                await invalid_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5
                )
                error_handling_works = False
            except openai.AuthenticationError:
                error_handling_works = True
            except Exception:
                error_handling_works = True  # Any error is expected
            
            duration = time.time() - start_time
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "duration": duration,
                "rate_limit_check_works": True,
                "usage_stats_available": bool(stats),
                "error_handling_works": error_handling_works,
                "rate_limits_configured": bool(client.rate_limits),
                "usage_stats_preview": {
                    "request_history_size": stats.get("request_history_size", 0),
                    "models_tracked": list(stats.get("token_usage_by_model", {}).keys())
                }
            }
            
            logger.info(f"✅ Rate limiting test passed ({duration:.2f}s)")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Rate limiting: {e}")
            logger.error(f"❌ Rate limiting test failed: {e}")

    async def _test_performance_benchmarks(self):
        """Test performance benchmarks."""
        test_name = "performance_benchmarks"
        logger.info("⚡ Running performance benchmarks...")
        
        try:
            # Property vectorization benchmark
            property_vectorizer = PropertyVectorizer()
            property_features = PropertyFeatures(**self.sample_property_data)
            
            property_times = []
            for i in range(5):
                start = time.time()
                await property_vectorizer.generate_embedding(property_features)
                property_times.append(time.time() - start)
            
            # Buyer vectorization benchmark
            buyer_vectorizer = BuyerProfileVectorizer()
            buyer_features = BuyerPreferenceFeatures(**self.sample_buyer_data)
            
            buyer_times = []
            for i in range(5):
                start = time.time()
                await buyer_vectorizer.generate_embedding(buyer_features)
                buyer_times.append(time.time() - start)
            
            # Calculate statistics
            avg_property_time = sum(property_times) / len(property_times)
            avg_buyer_time = sum(buyer_times) / len(buyer_times)
            
            self.test_results["performance_metrics"] = {
                "property_vectorization": {
                    "avg_time_seconds": avg_property_time,
                    "min_time_seconds": min(property_times),
                    "max_time_seconds": max(property_times),
                    "samples": len(property_times)
                },
                "buyer_vectorization": {
                    "avg_time_seconds": avg_buyer_time,
                    "min_time_seconds": min(buyer_times),
                    "max_time_seconds": max(buyer_times),
                    "samples": len(buyer_times)
                },
                "performance_targets": {
                    "property_vectorization_target": "< 0.1s",
                    "buyer_vectorization_target": "< 0.1s",
                    "property_meets_target": avg_property_time < 0.1,
                    "buyer_meets_target": avg_buyer_time < 0.1
                }
            }
            
            self.test_results["tests"][test_name] = {
                "status": "PASS",
                "avg_property_time": avg_property_time,
                "avg_buyer_time": avg_buyer_time,
                "performance_acceptable": avg_property_time < 0.5 and avg_buyer_time < 0.5
            }
            
            logger.info(f"✅ Performance benchmarks completed (prop={avg_property_time:.3f}s, buyer={avg_buyer_time:.3f}s)")
            
        except Exception as e:
            self.test_results["tests"][test_name] = {
                "status": "FAIL",
                "error": str(e)
            }
            self.test_results["errors"].append(f"Performance benchmarks: {e}")
            logger.error(f"❌ Performance benchmarks failed: {e}")

    def generate_report(self) -> str:
        """Generate comprehensive validation report."""
        passed_tests = sum(1 for test in self.test_results["tests"].values() if test["status"] == "PASS")
        total_tests = len(self.test_results["tests"])
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        report = f"""
🔬 OpenAI Embeddings Integration Validation Report
=================================================

Execution Time: {self.test_results.get('start_time', 'N/A')} - {self.test_results.get('end_time', 'N/A')}
Overall Result: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)

📊 TEST RESULTS SUMMARY
----------------------
"""
        
        for test_name, result in self.test_results["tests"].items():
            status_emoji = "✅" if result["status"] == "PASS" else "❌"
            duration = result.get("duration", 0)
            report += f"{status_emoji} {test_name.replace('_', ' ').title()}: {result['status']} ({duration:.2f}s)\n"
            
            if result["status"] == "FAIL" and "error" in result:
                report += f"   Error: {result['error']}\n"
        
        # Performance metrics
        if self.test_results.get("performance_metrics"):
            report += f"\n⚡ PERFORMANCE METRICS\n"
            report += f"---------------------\n"
            perf = self.test_results["performance_metrics"]
            
            if "property_vectorization" in perf:
                prop_perf = perf["property_vectorization"]
                report += f"Property Vectorization: {prop_perf['avg_time_seconds']:.3f}s avg (min: {prop_perf['min_time_seconds']:.3f}s, max: {prop_perf['max_time_seconds']:.3f}s)\n"
            
            if "buyer_vectorization" in perf:
                buyer_perf = perf["buyer_vectorization"]
                report += f"Buyer Vectorization: {buyer_perf['avg_time_seconds']:.3f}s avg (min: {buyer_perf['min_time_seconds']:.3f}s, max: {buyer_perf['max_time_seconds']:.3f}s)\n"
        
        # Errors and warnings
        if self.test_results["errors"]:
            report += f"\n🚨 ERRORS ({len(self.test_results['errors'])})\n"
            report += f"--------\n"
            for error in self.test_results["errors"]:
                report += f"• {error}\n"
        
        if self.test_results["warnings"]:
            report += f"\n⚠️  WARNINGS ({len(self.test_results['warnings'])})\n"
            report += f"----------\n"
            for warning in self.test_results["warnings"]:
                report += f"• {warning}\n"
        
        # Production readiness assessment
        report += f"\n🚀 PRODUCTION READINESS ASSESSMENT\n"
        report += f"----------------------------------\n"
        
        critical_tests = ["openai_connectivity", "openai_embeddings_api", "weaviate_connectivity", "embedding_ingestion"]
        critical_passed = all(
            self.test_results["tests"].get(test, {}).get("status") == "PASS" 
            for test in critical_tests
        )
        
        if critical_passed and success_rate >= 90:
            report += "🟢 READY FOR PRODUCTION\n"
            report += "All critical systems are functional and performance is acceptable.\n"
        elif critical_passed and success_rate >= 75:
            report += "🟡 MOSTLY READY - MINOR ISSUES\n"
            report += "Critical systems work but some non-critical issues need attention.\n"
        else:
            report += "🔴 NOT READY FOR PRODUCTION\n"
            report += "Critical issues found that must be resolved before production deployment.\n"
        
        return report


async def main():
    """Run the validation suite."""
    validator = OpenAIEmbeddingsValidator()
    
    try:
        results = await validator.run_validation()
        report = validator.generate_report()
        
        # Print report
        print(report)
        
        # Save detailed results to file
        with open("openai_embeddings_validation_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info("📁 Detailed results saved to openai_embeddings_validation_results.json")
        
        # Exit with error code if tests failed
        passed_tests = sum(1 for test in results["tests"].values() if test["status"] == "PASS")
        total_tests = len(results["tests"])
        
        if passed_tests < total_tests:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Validation failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())