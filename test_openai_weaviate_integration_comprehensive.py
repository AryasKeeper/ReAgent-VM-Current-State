#!/usr/bin/env python3
"""
Comprehensive OpenAI + Weaviate Integration Validation
ReAgent Sydney - Production Readiness Testing

This script validates the complete OpenAI embeddings integration with Weaviate
for production deployment, focusing on reliability and performance.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import traceback
import numpy as np

# Production imports
from src.config.settings import get_settings
from src.core.vector_db.client import WeaviateClient, get_weaviate_client
from src.core.vector_db.schemas_production import get_all_production_schemas
from src.services.external_apis.openai_client import OpenAIClient, get_openai_client

# Set up structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OpenAIWeaviateIntegrationValidator:
    """
    Comprehensive validator for OpenAI + Weaviate integration.
    
    Tests all aspects of the embeddings pipeline for production readiness.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.openai_client: Optional[OpenAIClient] = None
        self.weaviate_client: Optional[WeaviateClient] = None
        self.validation_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "openai_connectivity": {},
            "embedding_generation": {},
            "weaviate_integration": {},
            "dimension_validation": {},
            "rate_limiting": {},
            "performance_metrics": {},
            "error_handling": {},
            "production_readiness": {}
        }
        
    async def initialize_clients(self) -> bool:
        """Initialize OpenAI and Weaviate clients."""
        try:
            logger.info("Initializing OpenAI and Weaviate clients...")
            
            # Initialize OpenAI client
            self.openai_client = await get_openai_client()
            logger.info("OpenAI client initialized successfully")
            
            # Initialize Weaviate client
            self.weaviate_client = await get_weaviate_client()
            logger.info("Weaviate client initialized successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            self.validation_results["initialization_error"] = str(e)
            return False
    
    async def test_openai_connectivity(self) -> Dict[str, Any]:
        """Test OpenAI API connectivity and authentication."""
        logger.info("Testing OpenAI API connectivity...")
        
        connectivity_results = {
            "api_accessible": False,
            "authentication_valid": False,
            "api_key_configured": False,
            "response_time_ms": 0,
            "test_embedding_success": False,
            "error_details": None
        }
        
        try:
            # Check API key configuration
            if self.settings.apis.openai_api_key:
                connectivity_results["api_key_configured"] = True
                logger.info("OpenAI API key is configured")
            else:
                logger.error("OpenAI API key not configured")
                connectivity_results["error_details"] = "API key not configured"
                return connectivity_results
            
            # Test basic connectivity with health check
            start_time = time.time()
            health_check = await self.openai_client.health_check()
            response_time = (time.time() - start_time) * 1000
            
            connectivity_results["response_time_ms"] = response_time
            connectivity_results["api_accessible"] = health_check.get("api_accessible", False)
            
            if health_check.get("status") == "healthy":
                connectivity_results["authentication_valid"] = True
                logger.info(f"OpenAI API connectivity validated (response time: {response_time:.2f}ms)")
                
                # Test embedding generation with a simple text
                try:
                    import openai
                    from openai import AsyncOpenAI
                    
                    client = AsyncOpenAI(api_key=self.settings.apis.openai_api_key)
                    response = await client.embeddings.create(
                        model="text-embedding-ada-002",
                        input="Test property listing for Sydney apartment with 2 bedrooms"
                    )
                    
                    if response.data and len(response.data) > 0:
                        embedding = response.data[0].embedding
                        connectivity_results["test_embedding_success"] = True
                        connectivity_results["test_embedding_dimensions"] = len(embedding)
                        logger.info(f"Test embedding generated successfully: {len(embedding)} dimensions")
                    
                except Exception as embed_error:
                    logger.error(f"Test embedding generation failed: {embed_error}")
                    connectivity_results["embedding_error"] = str(embed_error)
            else:
                connectivity_results["error_details"] = health_check.get("error", "Unknown health check failure")
                logger.error(f"OpenAI health check failed: {connectivity_results['error_details']}")
            
        except Exception as e:
            logger.error(f"OpenAI connectivity test failed: {e}")
            connectivity_results["error_details"] = str(e)
            connectivity_results["traceback"] = traceback.format_exc()
        
        self.validation_results["openai_connectivity"] = connectivity_results
        return connectivity_results
    
    async def test_embedding_generation(self) -> Dict[str, Any]:
        """Test embedding generation for property and buyer data."""
        logger.info("Testing embedding generation for property and buyer data...")
        
        generation_results = {
            "property_embedding_test": {},
            "buyer_embedding_test": {},
            "dimension_consistency": False,
            "generation_time_ms": 0,
            "quality_metrics": {}
        }
        
        try:
            import openai
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.settings.apis.openai_api_key)
            
            # Sample property data for testing
            property_text = """
            Stunning 3-bedroom house in Bondi Beach with ocean views. This modern family home features:
            - 3 spacious bedrooms with built-in wardrobes
            - 2 bathrooms including ensuite
            - Modern kitchen with stone benchtops
            - Open plan living and dining
            - Private courtyard with outdoor entertaining
            - Walking distance to Bondi Beach and transport
            - Secure parking for 2 cars
            Price: $2,100,000
            """
            
            # Sample buyer preferences
            buyer_text = """
            Looking for family home near the beach for young family with 2 children.
            Preferences:
            - 3-4 bedrooms minimum
            - Good school catchment area
            - Walking distance to beach or parks
            - Modern kitchen essential
            - Outdoor space for children to play
            - Budget up to $2.5 million
            - Prefer eastern suburbs, especially Bondi, Coogee, or Bronte areas
            """
            
            start_time = time.time()
            
            # Test property embedding generation
            logger.info("Generating property embedding...")
            property_response = await client.embeddings.create(
                model="text-embedding-ada-002",
                input=property_text
            )
            
            property_embedding = property_response.data[0].embedding
            generation_results["property_embedding_test"] = {
                "success": True,
                "dimensions": len(property_embedding),
                "vector_norm": float(np.linalg.norm(property_embedding)),
                "sample_values": property_embedding[:5]  # First 5 dimensions for inspection
            }
            logger.info(f"Property embedding generated: {len(property_embedding)} dimensions")
            
            # Test buyer embedding generation
            logger.info("Generating buyer embedding...")
            buyer_response = await client.embeddings.create(
                model="text-embedding-ada-002",
                input=buyer_text
            )
            
            buyer_embedding = buyer_response.data[0].embedding
            generation_results["buyer_embedding_test"] = {
                "success": True,
                "dimensions": len(buyer_embedding),
                "vector_norm": float(np.linalg.norm(buyer_embedding)),
                "sample_values": buyer_embedding[:5]
            }
            logger.info(f"Buyer embedding generated: {len(buyer_embedding)} dimensions")
            
            generation_time = (time.time() - start_time) * 1000
            generation_results["generation_time_ms"] = generation_time
            
            # Validate dimension consistency
            if len(property_embedding) == len(buyer_embedding) == 1536:
                generation_results["dimension_consistency"] = True
                logger.info("Embedding dimensions are consistent (1536)")
            else:
                logger.error(f"Dimension mismatch: property={len(property_embedding)}, buyer={len(buyer_embedding)}")
            
            # Calculate similarity score for quality assessment
            similarity = np.dot(property_embedding, buyer_embedding) / (
                np.linalg.norm(property_embedding) * np.linalg.norm(buyer_embedding)
            )
            
            generation_results["quality_metrics"] = {
                "cosine_similarity": float(similarity),
                "property_vector_norm": float(np.linalg.norm(property_embedding)),
                "buyer_vector_norm": float(np.linalg.norm(buyer_embedding)),
                "generation_time_per_embedding_ms": generation_time / 2
            }
            
            logger.info(f"Embedding similarity score: {similarity:.4f}")
            logger.info(f"Total generation time: {generation_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"Embedding generation test failed: {e}")
            generation_results["error"] = str(e)
            generation_results["traceback"] = traceback.format_exc()
        
        self.validation_results["embedding_generation"] = generation_results
        return generation_results
    
    async def test_weaviate_integration(self) -> Dict[str, Any]:
        """Test embedding ingestion into Weaviate cluster."""
        logger.info("Testing Weaviate integration with OpenAI embeddings...")
        
        integration_results = {
            "weaviate_connectivity": {},
            "schema_deployment": {},
            "embedding_ingestion": {},
            "vector_search": {},
            "hybrid_search": {}
        }
        
        try:
            # Test Weaviate connectivity
            health_check = await self.weaviate_client.health_check()
            integration_results["weaviate_connectivity"] = health_check
            
            if not health_check.get("ready", False):
                logger.error("Weaviate is not ready")
                return integration_results
            
            logger.info("Weaviate cluster is ready")
            
            # Test schema deployment
            schemas = get_all_production_schemas()
            schema_results = {}
            
            for class_name, schema in schemas.items():
                try:
                    success = await self.weaviate_client.create_schema(schema)
                    schema_results[class_name] = {
                        "deployed": success,
                        "vectorizer": schema.get("vectorizer", "none"),
                        "dimensions": schema.get("moduleConfig", {}).get("text2vec-openai", {}).get("dimensions", 0)
                    }
                    
                    if success:
                        logger.info(f"Schema {class_name} deployed successfully")
                    else:
                        logger.warning(f"Schema {class_name} deployment failed or already exists")
                        
                except Exception as schema_error:
                    logger.error(f"Schema {class_name} deployment failed: {schema_error}")
                    schema_results[class_name] = {"error": str(schema_error)}
            
            integration_results["schema_deployment"] = schema_results
            
            # Test embedding ingestion
            await self._test_embedding_ingestion(integration_results)
            
            # Test vector search
            await self._test_vector_search(integration_results)
            
        except Exception as e:
            logger.error(f"Weaviate integration test failed: {e}")
            integration_results["error"] = str(e)
            integration_results["traceback"] = traceback.format_exc()
        
        self.validation_results["weaviate_integration"] = integration_results
        return integration_results
    
    async def _test_embedding_ingestion(self, integration_results: Dict[str, Any]) -> None:
        """Test ingesting embeddings into Weaviate."""
        logger.info("Testing embedding ingestion...")
        
        ingestion_results = {
            "property_ingestion": {},
            "buyer_ingestion": {},
            "batch_ingestion": {}
        }
        
        try:
            import openai
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.settings.apis.openai_api_key)
            
            # Test property ingestion
            property_data = {
                "listing_id": "test-property-001",
                "title": "Modern 3BR House in Bondi Beach",
                "description": "Stunning oceanfront property with modern amenities",
                "property_type": "House",
                "suburb": "Bondi Beach",
                "postcode": "2026",
                "state": "NSW",
                "bedrooms": 3,
                "bathrooms": 2,
                "car_spaces": 2,
                "price": 2100000,
                "price_display": "$2,100,000",
                "latitude": -33.8915,
                "longitude": 151.2767,
                "agent_name": "Test Agent",
                "agency_name": "Test Agency",
                "source": "validation_test"
            }
            
            # Generate embedding for property
            property_text = f"{property_data['title']} {property_data['description']}"
            embedding_response = await client.embeddings.create(
                model="text-embedding-ada-002",
                input=property_text
            )
            property_vector = embedding_response.data[0].embedding
            
            # Insert property with embedding
            start_time = time.time()
            property_id = await self.weaviate_client.insert_object(
                class_name="Property",
                properties=property_data,
                vector=property_vector
            )
            ingestion_time = (time.time() - start_time) * 1000
            
            ingestion_results["property_ingestion"] = {
                "success": property_id is not None,
                "object_id": property_id,
                "ingestion_time_ms": ingestion_time,
                "vector_dimensions": len(property_vector)
            }
            
            if property_id:
                logger.info(f"Property ingested successfully: {property_id} ({ingestion_time:.2f}ms)")
            else:
                logger.error("Property ingestion failed")
            
            # Test buyer profile ingestion
            buyer_data = {
                "buyer_id": "test-buyer-001",
                "full_name": "Test Buyer",
                "buyer_type": "owner_occupier",
                "buying_urgency": "high",
                "max_price": 2500000,
                "min_price": 1800000,
                "budget_flexibility": 0.1,
                "property_types": ["House", "Townhouse"],
                "preferred_suburbs": ["Bondi Beach", "Coogee", "Bronte"],
                "min_bedrooms": 3,
                "max_bedrooms": 4,
                "min_bathrooms": 2,
                "min_car_spaces": 1,
                "lifestyle_preferences": "Beach lifestyle, family-friendly area, good schools",
                "max_commute_time": 45
            }
            
            # Generate embedding for buyer
            buyer_text = f"Buyer preferences: {buyer_data['lifestyle_preferences']} Looking for {buyer_data['property_types']} in {', '.join(buyer_data['preferred_suburbs'])}"
            buyer_embedding_response = await client.embeddings.create(
                model="text-embedding-ada-002",
                input=buyer_text
            )
            buyer_vector = buyer_embedding_response.data[0].embedding
            
            # Insert buyer with embedding
            start_time = time.time()
            buyer_id = await self.weaviate_client.insert_object(
                class_name="BuyerProfile",
                properties=buyer_data,
                vector=buyer_vector
            )
            buyer_ingestion_time = (time.time() - start_time) * 1000
            
            ingestion_results["buyer_ingestion"] = {
                "success": buyer_id is not None,
                "object_id": buyer_id,
                "ingestion_time_ms": buyer_ingestion_time,
                "vector_dimensions": len(buyer_vector)
            }
            
            if buyer_id:
                logger.info(f"Buyer profile ingested successfully: {buyer_id} ({buyer_ingestion_time:.2f}ms)")
            else:
                logger.error("Buyer profile ingestion failed")
            
        except Exception as e:
            logger.error(f"Embedding ingestion test failed: {e}")
            ingestion_results["error"] = str(e)
        
        integration_results["embedding_ingestion"] = ingestion_results
    
    async def _test_vector_search(self, integration_results: Dict[str, Any]) -> None:
        """Test vector search capabilities."""
        logger.info("Testing vector search...")
        
        search_results = {
            "property_search": {},
            "buyer_matching": {},
            "performance_metrics": {}
        }
        
        try:
            import openai
            from openai import AsyncOpenAI
            from src.core.vector_db.client import SearchQuery
            
            client = AsyncOpenAI(api_key=self.settings.apis.openai_api_key)
            
            # Test property search with buyer query
            search_query = "Looking for modern family home near beach with 3 bedrooms and outdoor space"
            query_embedding_response = await client.embeddings.create(
                model="text-embedding-ada-002",
                input=search_query
            )
            query_vector = query_embedding_response.data[0].embedding
            
            # Perform vector search
            start_time = time.time()
            search_query_obj = SearchQuery(
                vector=query_vector,
                class_name="Property",
                limit=5,
                additional_properties=["*"]
            )
            
            search_results_data = await self.weaviate_client.vector_search(search_query_obj)
            search_time = (time.time() - start_time) * 1000
            
            search_results["property_search"] = {
                "success": len(search_results_data) > 0,
                "results_count": len(search_results_data),
                "search_time_ms": search_time,
                "top_scores": [result.score for result in search_results_data[:3]]
            }
            
            if search_results_data:
                logger.info(f"Vector search returned {len(search_results_data)} results ({search_time:.2f}ms)")
                for i, result in enumerate(search_results_data[:3]):
                    logger.info(f"  Result {i+1}: Score {result.score:.4f}, ID {result.object_id}")
            else:
                logger.warning("Vector search returned no results")
            
            # Test hybrid search
            start_time = time.time()
            hybrid_results = await self.weaviate_client.hybrid_search(
                class_name="Property",
                query_text="beach house modern family",
                query_vector=query_vector,
                alpha=0.7,
                limit=3
            )
            hybrid_time = (time.time() - start_time) * 1000
            
            search_results["hybrid_search"] = {
                "success": len(hybrid_results) > 0,
                "results_count": len(hybrid_results),
                "search_time_ms": hybrid_time,
                "top_scores": [result.score for result in hybrid_results]
            }
            
            if hybrid_results:
                logger.info(f"Hybrid search returned {len(hybrid_results)} results ({hybrid_time:.2f}ms)")
            
            search_results["performance_metrics"] = {
                "vector_search_latency_ms": search_time,
                "hybrid_search_latency_ms": hybrid_time,
                "total_test_time_ms": search_time + hybrid_time
            }
            
        except Exception as e:
            logger.error(f"Vector search test failed: {e}")
            search_results["error"] = str(e)
        
        integration_results["vector_search"] = search_results
    
    async def test_rate_limiting(self) -> Dict[str, Any]:
        """Test rate limiting and error handling."""
        logger.info("Testing rate limiting and error handling...")
        
        rate_limit_results = {
            "concurrent_requests": {},
            "rate_limit_handling": {},
            "error_recovery": {}
        }
        
        try:
            import openai
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.settings.apis.openai_api_key)
            
            # Test concurrent embedding requests
            logger.info("Testing concurrent embedding requests...")
            
            test_texts = [
                f"Test property listing {i} with various features and amenities"
                for i in range(5)
            ]
            
            start_time = time.time()
            tasks = []
            for text in test_texts:
                task = client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=text
                )
                tasks.append(task)
            
            # Execute concurrent requests
            try:
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                concurrent_time = (time.time() - start_time) * 1000
                
                successful_requests = sum(1 for r in responses if not isinstance(r, Exception))
                failed_requests = len(responses) - successful_requests
                
                rate_limit_results["concurrent_requests"] = {
                    "total_requests": len(test_texts),
                    "successful_requests": successful_requests,
                    "failed_requests": failed_requests,
                    "total_time_ms": concurrent_time,
                    "avg_time_per_request_ms": concurrent_time / len(test_texts),
                    "errors": [str(r) for r in responses if isinstance(r, Exception)]
                }
                
                logger.info(f"Concurrent requests: {successful_requests}/{len(test_texts)} successful ({concurrent_time:.2f}ms)")
                
            except Exception as concurrent_error:
                logger.error(f"Concurrent request test failed: {concurrent_error}")
                rate_limit_results["concurrent_requests"]["error"] = str(concurrent_error)
            
            # Test rate limit detection and handling
            rate_limit_results["rate_limit_handling"] = {
                "openai_client_limits": self.openai_client.rate_limits,
                "current_usage": await self.openai_client.get_usage_stats()
            }
            
        except Exception as e:
            logger.error(f"Rate limiting test failed: {e}")
            rate_limit_results["error"] = str(e)
        
        self.validation_results["rate_limiting"] = rate_limit_results
        return rate_limit_results
    
    async def test_dimension_compatibility(self) -> Dict[str, Any]:
        """Verify embedding dimension compatibility with Weaviate schemas."""
        logger.info("Testing dimension compatibility...")
        
        dimension_results = {
            "expected_dimensions": 1536,
            "schema_compatibility": {},
            "vector_validation": {}
        }
        
        try:
            # Check schema configurations
            schemas = get_all_production_schemas()
            
            for class_name, schema in schemas.items():
                if "vectorizer" in schema and schema["vectorizer"] == "text2vec-openai":
                    module_config = schema.get("moduleConfig", {}).get("text2vec-openai", {})
                    schema_dimensions = module_config.get("dimensions", 0)
                    
                    dimension_results["schema_compatibility"][class_name] = {
                        "configured_dimensions": schema_dimensions,
                        "matches_openai": schema_dimensions == 1536,
                        "vectorizer": schema["vectorizer"]
                    }
                    
                    logger.info(f"Schema {class_name}: {schema_dimensions} dimensions configured")
            
            # Test actual embedding dimensions
            import openai
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.settings.apis.openai_api_key)
            response = await client.embeddings.create(
                model="text-embedding-ada-002",
                input="Dimension validation test"
            )
            
            actual_dimensions = len(response.data[0].embedding)
            dimension_results["vector_validation"] = {
                "actual_dimensions": actual_dimensions,
                "matches_expected": actual_dimensions == 1536,
                "model_used": "text-embedding-ada-002"
            }
            
            logger.info(f"Actual embedding dimensions: {actual_dimensions}")
            
        except Exception as e:
            logger.error(f"Dimension compatibility test failed: {e}")
            dimension_results["error"] = str(e)
        
        self.validation_results["dimension_compatibility"] = dimension_results
        return dimension_results
    
    async def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance and readiness report."""
        logger.info("Generating performance and production readiness report...")
        
        # Analyze all test results
        performance_summary = {
            "overall_status": "unknown",
            "readiness_score": 0,
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
            "performance_metrics": {},
            "deployment_readiness": {}
        }
        
        # Calculate readiness score based on test results
        score_components = {
            "openai_connectivity": 0,
            "embedding_generation": 0,
            "weaviate_integration": 0,
            "dimension_compatibility": 0,
            "rate_limiting": 0
        }
        
        # Evaluate OpenAI connectivity
        if self.validation_results["openai_connectivity"].get("authentication_valid", False):
            score_components["openai_connectivity"] = 25
        elif self.validation_results["openai_connectivity"].get("api_accessible", False):
            score_components["openai_connectivity"] = 15
            performance_summary["warnings"].append("OpenAI API accessible but authentication issues detected")
        else:
            performance_summary["critical_issues"].append("OpenAI API not accessible")
        
        # Evaluate embedding generation
        if (self.validation_results["embedding_generation"].get("property_embedding_test", {}).get("success", False) and
            self.validation_results["embedding_generation"].get("buyer_embedding_test", {}).get("success", False)):
            score_components["embedding_generation"] = 25
        else:
            performance_summary["critical_issues"].append("Embedding generation failed")
        
        # Evaluate Weaviate integration
        weaviate_ready = self.validation_results["weaviate_integration"].get("weaviate_connectivity", {}).get("ready", False)
        ingestion_success = self.validation_results["weaviate_integration"].get("embedding_ingestion", {})
        
        if weaviate_ready and ingestion_success.get("property_ingestion", {}).get("success", False):
            score_components["weaviate_integration"] = 25
        elif weaviate_ready:
            score_components["weaviate_integration"] = 15
            performance_summary["warnings"].append("Weaviate ready but ingestion issues detected")
        else:
            performance_summary["critical_issues"].append("Weaviate integration failed")
        
        # Evaluate dimension compatibility
        if self.validation_results["dimension_compatibility"].get("vector_validation", {}).get("matches_expected", False):
            score_components["dimension_compatibility"] = 15
        else:
            performance_summary["critical_issues"].append("Embedding dimension mismatch")
        
        # Evaluate rate limiting
        if self.validation_results["rate_limiting"]:
            score_components["rate_limiting"] = 10
        
        # Calculate total score
        performance_summary["readiness_score"] = sum(score_components.values())
        
        # Determine overall status
        if performance_summary["readiness_score"] >= 90:
            performance_summary["overall_status"] = "production_ready"
        elif performance_summary["readiness_score"] >= 70:
            performance_summary["overall_status"] = "ready_with_warnings"
        elif performance_summary["readiness_score"] >= 50:
            performance_summary["overall_status"] = "needs_fixes"
        else:
            performance_summary["overall_status"] = "not_ready"
        
        # Collect performance metrics
        performance_summary["performance_metrics"] = {
            "openai_response_time_ms": self.validation_results["openai_connectivity"].get("response_time_ms", 0),
            "embedding_generation_time_ms": self.validation_results["embedding_generation"].get("generation_time_ms", 0),
            "weaviate_ingestion_time_ms": self._get_avg_ingestion_time(),
            "vector_search_time_ms": self._get_search_time()
        }
        
        # Generate recommendations
        self._generate_recommendations(performance_summary)
        
        self.validation_results["performance_metrics"] = performance_summary
        return performance_summary
    
    def _get_avg_ingestion_time(self) -> float:
        """Calculate average ingestion time."""
        ingestion_data = self.validation_results.get("weaviate_integration", {}).get("embedding_ingestion", {})
        
        property_time = ingestion_data.get("property_ingestion", {}).get("ingestion_time_ms", 0)
        buyer_time = ingestion_data.get("buyer_ingestion", {}).get("ingestion_time_ms", 0)
        
        return (property_time + buyer_time) / 2 if property_time and buyer_time else 0
    
    def _get_search_time(self) -> float:
        """Get vector search time."""
        search_data = self.validation_results.get("weaviate_integration", {}).get("vector_search", {})
        return search_data.get("property_search", {}).get("search_time_ms", 0)
    
    def _generate_recommendations(self, performance_summary: Dict[str, Any]) -> None:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Performance-based recommendations
        openai_time = performance_summary["performance_metrics"].get("openai_response_time_ms", 0)
        if openai_time > 2000:
            recommendations.append("OpenAI response time is high (>2s). Consider implementing connection pooling and request batching.")
        
        embedding_time = performance_summary["performance_metrics"].get("embedding_generation_time_ms", 0)
        if embedding_time > 1000:
            recommendations.append("Embedding generation is slow. Implement asynchronous batch processing for production.")
        
        search_time = performance_summary["performance_metrics"].get("vector_search_time_ms", 0)
        if search_time > 500:
            recommendations.append("Vector search latency is high. Optimize Weaviate index configuration and cache frequently accessed vectors.")
        
        # Configuration-based recommendations
        if performance_summary["readiness_score"] < 90:
            recommendations.append("Implement comprehensive monitoring and alerting for production deployment.")
            recommendations.append("Set up automated error recovery and circuit breaker patterns.")
            recommendations.append("Configure proper rate limiting and retry mechanisms.")
        
        recommendations.append("Implement embedding caching to reduce OpenAI API costs and improve performance.")
        recommendations.append("Set up production monitoring for embedding quality and search relevance.")
        
        performance_summary["recommendations"] = recommendations
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run all validation tests and generate final report."""
        logger.info("Starting comprehensive OpenAI + Weaviate integration validation...")
        
        try:
            # Initialize clients
            if not await self.initialize_clients():
                return self.validation_results
            
            # Run all validation tests
            await self.test_openai_connectivity()
            await self.test_embedding_generation()
            await self.test_weaviate_integration()
            await self.test_dimension_compatibility()
            await self.test_rate_limiting()
            
            # Generate final performance report
            await self.generate_performance_report()
            
            logger.info("Comprehensive validation completed successfully")
            
        except Exception as e:
            logger.error(f"Comprehensive validation failed: {e}")
            self.validation_results["validation_error"] = str(e)
            self.validation_results["traceback"] = traceback.format_exc()
        
        return self.validation_results


async def main():
    """Main validation execution."""
    print("=" * 80)
    print("ReAgent Sydney - OpenAI + Weaviate Integration Validation")
    print("=" * 80)
    
    validator = OpenAIWeaviateIntegrationValidator()
    results = await validator.run_comprehensive_validation()
    
    # Save results to file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_file = f"openai_weaviate_validation_report_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    performance = results.get("performance_metrics", {})
    print(f"Overall Status: {performance.get('overall_status', 'unknown').upper()}")
    print(f"Readiness Score: {performance.get('readiness_score', 0)}/100")
    
    if performance.get("critical_issues"):
        print(f"\nCRITICAL ISSUES ({len(performance['critical_issues'])}):")
        for issue in performance["critical_issues"]:
            print(f"  ❌ {issue}")
    
    if performance.get("warnings"):
        print(f"\nWARNINGS ({len(performance['warnings'])}):")
        for warning in performance["warnings"]:
            print(f"  ⚠️  {warning}")
    
    if performance.get("recommendations"):
        print(f"\nRECOMMENDATIONS ({len(performance['recommendations'])}):")
        for rec in performance["recommendations"]:
            print(f"  💡 {rec}")
    
    print(f"\nDetailed results saved to: {results_file}")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())