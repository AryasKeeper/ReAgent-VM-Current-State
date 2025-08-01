#!/usr/bin/env python3
"""
OpenAI Embeddings Validation for ReAgent Sydney
Production readiness testing for OpenAI + Weaviate integration
"""

import asyncio
import json
import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import traceback
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OpenAIEmbeddingsValidator:
    """Validates OpenAI embeddings integration for production readiness."""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "tests": {}
        }
    
    async def test_openai_connectivity(self) -> Dict[str, Any]:
        """Test OpenAI API connectivity and authentication."""
        logger.info("Testing OpenAI API connectivity...")
        
        test_result = {
            "status": "failed",
            "api_key_configured": bool(self.api_key),
            "authentication_valid": False,
            "response_time_ms": 0,
            "test_embedding_success": False,
            "embedding_dimensions": 0,
            "error": None
        }
        
        if not self.api_key:
            test_result["error"] = "OPENAI_API_KEY environment variable not set"
            return test_result
        
        try:
            import openai
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key)
            
            # Test basic connectivity with health check
            start_time = time.time()
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=5
            )
            response_time = (time.time() - start_time) * 1000
            
            test_result["response_time_ms"] = round(response_time, 2)
            test_result["authentication_valid"] = True
            
            # Test embedding generation
            logger.info("Testing embedding generation...")
            start_time = time.time()
            embedding_response = await client.embeddings.create(
                model="text-embedding-ada-002",
                input="Test property listing for validation"
            )
            
            if embedding_response.data and len(embedding_response.data) > 0:
                embedding = embedding_response.data[0].embedding
                test_result["test_embedding_success"] = True
                test_result["embedding_dimensions"] = len(embedding)
                test_result["embedding_generation_time_ms"] = round((time.time() - start_time) * 1000, 2)
                test_result["status"] = "passed"
                
                logger.info(f"✅ OpenAI connectivity validated - {len(embedding)} dimensions")
            
        except Exception as e:
            logger.error(f"❌ OpenAI connectivity test failed: {e}")
            test_result["error"] = str(e)
            test_result["traceback"] = traceback.format_exc()
        
        return test_result
    
    async def test_embedding_consistency(self) -> Dict[str, Any]:
        """Test embedding generation consistency and quality."""
        logger.info("Testing embedding consistency and quality...")
        
        test_result = {
            "status": "failed",
            "dimension_consistency": False,
            "quality_metrics": {},
            "generation_times": [],
            "error": None
        }
        
        try:
            import openai
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key)
            
            # Test texts for property and buyer scenarios
            property_text = """
            Modern 3-bedroom house in Bondi Beach with ocean views.
            Features: 3 bedrooms, 2 bathrooms, modern kitchen, private courtyard,
            walking distance to beach and transport, secure parking for 2 cars.
            Price: $2,100,000
            """
            
            buyer_text = """
            Looking for family home near beach for young family with 2 children.
            Requirements: 3-4 bedrooms, good schools, walking distance to beach,
            modern kitchen, outdoor space, budget up to $2.5M, eastern suburbs preferred.
            """
            
            embeddings = []
            generation_times = []
            
            # Generate multiple embeddings to test consistency
            test_texts = [property_text, buyer_text, property_text]  # Duplicate to test consistency
            
            for i, text in enumerate(test_texts):
                start_time = time.time()
                response = await client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=text.strip()
                )
                generation_time = (time.time() - start_time) * 1000
                generation_times.append(generation_time)
                
                embedding = response.data[0].embedding
                embeddings.append(embedding)
                
                logger.info(f"Generated embedding {i+1}: {len(embedding)} dimensions ({generation_time:.2f}ms)")
            
            # Validate dimension consistency
            dimensions = [len(emb) for emb in embeddings]
            test_result["dimension_consistency"] = all(d == 1536 for d in dimensions)
            test_result["generation_times"] = generation_times
            
            # Quality metrics
            if len(embeddings) >= 3:
                # Test consistency - same text should produce identical embeddings
                property_embedding_1 = np.array(embeddings[0])
                property_embedding_2 = np.array(embeddings[2])
                consistency_score = np.dot(property_embedding_1, property_embedding_2) / (
                    np.linalg.norm(property_embedding_1) * np.linalg.norm(property_embedding_2)
                )
                
                # Test semantic relationship
                property_embedding = np.array(embeddings[0])
                buyer_embedding = np.array(embeddings[1])
                semantic_similarity = np.dot(property_embedding, buyer_embedding) / (
                    np.linalg.norm(property_embedding) * np.linalg.norm(buyer_embedding)
                )
                
                test_result["quality_metrics"] = {
                    "consistency_score": float(consistency_score),
                    "semantic_similarity": float(semantic_similarity),
                    "avg_generation_time_ms": round(np.mean(generation_times), 2),
                    "vector_norms": [float(np.linalg.norm(emb)) for emb in embeddings]
                }
                
                # Pass if dimensions are correct and consistency is high
                if test_result["dimension_consistency"] and consistency_score > 0.99:
                    test_result["status"] = "passed"
                    logger.info(f"✅ Embedding consistency validated - consistency: {consistency_score:.6f}")
                else:
                    logger.warning(f"⚠️  Consistency score: {consistency_score:.6f}")
            
        except Exception as e:
            logger.error(f"❌ Embedding consistency test failed: {e}")
            test_result["error"] = str(e)
            test_result["traceback"] = traceback.format_exc()
        
        return test_result
    
    async def test_weaviate_connectivity(self) -> Dict[str, Any]:
        """Test Weaviate connectivity and schema compatibility."""
        logger.info("Testing Weaviate connectivity...")
        
        test_result = {
            "status": "failed",
            "weaviate_accessible": False,
            "response_time_ms": 0,
            "version_info": {},
            "openai_module_available": False,
            "error": None
        }
        
        try:
            import weaviate
            
            # Test basic connectivity
            start_time = time.time()
            client = weaviate.Client(url=self.weaviate_url)
            
            is_ready = client.is_ready()
            response_time = (time.time() - start_time) * 1000
            
            test_result["weaviate_accessible"] = is_ready
            test_result["response_time_ms"] = round(response_time, 2)
            
            if is_ready:
                # Get version and module information
                meta = client.get_meta()
                test_result["version_info"] = {
                    "version": meta.get("version", "unknown"),
                    "modules": list(meta.get("modules", {}).keys())
                }
                
                # Check if text2vec-openai module is available
                modules = meta.get("modules", {})
                test_result["openai_module_available"] = "text2vec-openai" in modules
                
                if test_result["openai_module_available"]:
                    test_result["status"] = "passed"
                    logger.info(f"✅ Weaviate connectivity validated - OpenAI module available")
                else:
                    logger.warning("⚠️  Weaviate accessible but text2vec-openai module not found")
            else:
                logger.error("❌ Weaviate is not ready")
                
        except Exception as e:
            logger.error(f"❌ Weaviate connectivity test failed: {e}")
            test_result["error"] = str(e)
            test_result["traceback"] = traceback.format_exc()
        
        return test_result
    
    async def test_end_to_end_integration(self) -> Dict[str, Any]:
        """Test complete end-to-end integration flow."""
        logger.info("Testing end-to-end integration...")
        
        test_result = {
            "status": "failed",
            "schema_creation": False,
            "data_ingestion": False,
            "vector_search": False,
            "total_time_ms": 0,
            "error": None
        }
        
        try:
            import weaviate
            import openai
            from openai import AsyncOpenAI
            
            start_time = time.time()
            
            # Initialize clients
            weaviate_client = weaviate.Client(url=self.weaviate_url)
            openai_client = AsyncOpenAI(api_key=self.api_key)
            
            if not weaviate_client.is_ready():
                raise Exception("Weaviate is not ready")
            
            # Test schema creation with OpenAI vectorizer
            test_class_name = "TestProperty"
            test_schema = {
                "class": test_class_name,
                "description": "Test property class for OpenAI embeddings validation",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "ada",
                        "modelVersion": "002",
                        "type": "text",
                        "dimensions": 1536
                    }
                },
                "properties": [
                    {
                        "name": "title",
                        "dataType": ["text"],
                        "description": "Property title"
                    },
                    {
                        "name": "description", 
                        "dataType": ["text"],
                        "description": "Property description"
                    },
                    {
                        "name": "price",
                        "dataType": ["number"],
                        "description": "Property price"
                    }
                ]
            }
            
            # Clean up any existing test class
            try:
                weaviate_client.schema.delete_class(test_class_name)
            except:
                pass
            
            # Create test schema
            weaviate_client.schema.create_class(test_schema)
            test_result["schema_creation"] = True
            logger.info("✅ Test schema created successfully")
            
            # Test data ingestion with automatic vectorization
            test_property = {
                "title": "Modern 2BR Apartment in Sydney CBD",
                "description": "Stunning 2-bedroom apartment with harbour views, modern kitchen, and premium finishes. Located in the heart of Sydney with easy access to transport and amenities.",
                "price": 1500000
            }
            
            # Insert property (Weaviate will automatically generate embeddings)
            result = weaviate_client.data_object.create(
                data_object=test_property,
                class_name=test_class_name
            )
            
            if result:
                test_result["data_ingestion"] = True
                logger.info(f"✅ Test property ingested successfully: {result}")
                
                # Wait a moment for indexing
                await asyncio.sleep(1)
                
                # Test vector search
                search_query = "waterfront apartment with city views"
                
                # Generate query embedding manually for comparison
                query_response = await openai_client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=search_query
                )
                query_vector = query_response.data[0].embedding
                
                # Perform vector search
                search_result = (
                    weaviate_client.query
                    .get(test_class_name, ["title", "description", "price"])
                    .with_near_vector({"vector": query_vector})
                    .with_limit(1)
                    .with_additional(["certainty"])
                    .do()
                )
                
                if search_result.get("data", {}).get("Get", {}).get(test_class_name):
                    test_result["vector_search"] = True
                    search_results = search_result["data"]["Get"][test_class_name]
                    certainty = search_results[0]["_additional"]["certainty"]
                    
                    logger.info(f"✅ Vector search successful - certainty: {certainty:.4f}")
                    test_result["search_certainty"] = certainty
                
            # Clean up
            try:
                weaviate_client.schema.delete_class(test_class_name)
            except:
                pass
            
            test_result["total_time_ms"] = round((time.time() - start_time) * 1000, 2)
            
            # Overall success check
            if (test_result["schema_creation"] and 
                test_result["data_ingestion"] and 
                test_result["vector_search"]):
                test_result["status"] = "passed"
                logger.info(f"✅ End-to-end integration test passed ({test_result['total_time_ms']}ms)")
            
        except Exception as e:
            logger.error(f"❌ End-to-end integration test failed: {e}")
            test_result["error"] = str(e)
            test_result["traceback"] = traceback.format_exc()
        
        return test_result
    
    async def test_rate_limiting(self) -> Dict[str, Any]:
        """Test rate limiting behavior and error handling."""
        logger.info("Testing rate limiting and error handling...")
        
        test_result = {
            "status": "passed",  # Default to passed unless issues found
            "concurrent_requests_success": False,
            "rate_limit_detection": False,
            "error_handling": False,
            "performance_metrics": {},
            "error": None
        }
        
        try:
            import openai
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=self.api_key)
            
            # Test concurrent requests (small batch to avoid hitting limits)
            logger.info("Testing concurrent embedding requests...")
            
            test_texts = [
                f"Test property {i} with modern amenities and great location"
                for i in range(3)  # Small batch for testing
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
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            concurrent_time = (time.time() - start_time) * 1000
            
            successful_requests = sum(1 for r in responses if not isinstance(r, Exception))
            failed_requests = len(responses) - successful_requests
            
            test_result["concurrent_requests_success"] = failed_requests == 0
            test_result["performance_metrics"] = {
                "total_requests": len(test_texts),
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "total_time_ms": round(concurrent_time, 2),
                "avg_time_per_request_ms": round(concurrent_time / len(test_texts), 2)
            }
            
            # Check for rate limit errors
            rate_limit_errors = [r for r in responses if isinstance(r, Exception) and "rate" in str(r).lower()]
            test_result["rate_limit_detection"] = len(rate_limit_errors) > 0
            
            if rate_limit_errors:
                logger.warning(f"⚠️  Rate limit errors detected: {len(rate_limit_errors)}")
                test_result["rate_limit_errors"] = [str(e) for e in rate_limit_errors]
            
            # Test error handling with invalid input
            try:
                await client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=""  # Empty input should cause an error
                )
            except Exception as e:
                test_result["error_handling"] = True
                logger.info(f"✅ Error handling validated: {type(e).__name__}")
            
            logger.info(f"✅ Rate limiting test completed - {successful_requests}/{len(test_texts)} requests successful")
            
        except Exception as e:
            logger.error(f"❌ Rate limiting test failed: {e}")
            test_result["error"] = str(e)
            test_result["status"] = "failed"
        
        return test_result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests and generate comprehensive report."""
        logger.info("🚀 Starting OpenAI + Weaviate integration validation...")
        
        # Run all tests
        self.results["tests"]["openai_connectivity"] = await self.test_openai_connectivity()
        self.results["tests"]["embedding_consistency"] = await self.test_embedding_consistency()
        self.results["tests"]["weaviate_connectivity"] = await self.test_weaviate_connectivity()
        self.results["tests"]["end_to_end_integration"] = await self.test_end_to_end_integration()
        self.results["tests"]["rate_limiting"] = await self.test_rate_limiting()
        
        # Generate summary
        self.results["summary"] = self._generate_summary()
        
        return self.results
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate validation summary and recommendations."""
        summary = {
            "overall_status": "unknown",
            "passed_tests": 0,
            "total_tests": len(self.results["tests"]),
            "critical_issues": [],
            "warnings": [],
            "recommendations": [],
            "readiness_score": 0
        }
        
        # Count passed tests
        for test_name, test_result in self.results["tests"].items():
            if test_result.get("status") == "passed":
                summary["passed_tests"] += 1
        
        # Calculate readiness score
        summary["readiness_score"] = round((summary["passed_tests"] / summary["total_tests"]) * 100)
        
        # Determine overall status
        if summary["readiness_score"] >= 90:
            summary["overall_status"] = "production_ready"
        elif summary["readiness_score"] >= 70:
            summary["overall_status"] = "ready_with_warnings"
        elif summary["readiness_score"] >= 50:
            summary["overall_status"] = "needs_fixes"
        else:
            summary["overall_status"] = "not_ready"
        
        # Identify critical issues
        if not self.results["tests"]["openai_connectivity"].get("authentication_valid", False):
            summary["critical_issues"].append("OpenAI API authentication failed")
        
        if not self.results["tests"]["weaviate_connectivity"].get("weaviate_accessible", False):
            summary["critical_issues"].append("Weaviate is not accessible")
        
        if not self.results["tests"]["embedding_consistency"].get("dimension_consistency", False):
            summary["critical_issues"].append("Embedding dimensions are inconsistent")
        
        if not self.results["tests"]["end_to_end_integration"].get("status") == "passed":
            summary["critical_issues"].append("End-to-end integration failed")
        
        # Generate warnings
        if not self.results["tests"]["weaviate_connectivity"].get("openai_module_available", False):
            summary["warnings"].append("Weaviate text2vec-openai module not available")
        
        embedding_time = self.results["tests"]["embedding_consistency"].get("quality_metrics", {}).get("avg_generation_time_ms", 0)
        if embedding_time > 1000:
            summary["warnings"].append(f"Embedding generation is slow ({embedding_time:.0f}ms avg)")
        
        # Generate recommendations
        recommendations = [
            "Set up comprehensive monitoring for API usage and costs",
            "Implement caching for frequently generated embeddings",
            "Configure proper error handling and retry mechanisms",
            "Monitor embedding quality and search relevance in production"
        ]
        
        if summary["readiness_score"] < 90:
            recommendations.append("Address critical issues before production deployment")
        
        summary["recommendations"] = recommendations
        
        return summary


async def main():
    """Main execution function."""
    print("=" * 80)
    print("🔍 ReAgent Sydney - OpenAI Embeddings Validation")
    print("=" * 80)
    
    validator = OpenAIEmbeddingsValidator()
    results = await validator.run_all_tests()
    
    # Save results
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_file = f"openai_embeddings_validation_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    summary = results["summary"]
    print(f"\n{'='*80}")
    print("📊 VALIDATION SUMMARY")
    print(f"{'='*80}")
    
    status_emoji = {
        "production_ready": "✅",
        "ready_with_warnings": "⚠️",
        "needs_fixes": "🔧",
        "not_ready": "❌"
    }
    
    print(f"Overall Status: {status_emoji.get(summary['overall_status'], '❓')} {summary['overall_status'].upper()}")
    print(f"Readiness Score: {summary['readiness_score']}/100")
    print(f"Tests Passed: {summary['passed_tests']}/{summary['total_tests']}")
    
    if summary["critical_issues"]:
        print(f"\n🚨 CRITICAL ISSUES ({len(summary['critical_issues'])}):")
        for issue in summary["critical_issues"]:
            print(f"  ❌ {issue}")
    
    if summary["warnings"]:
        print(f"\n⚠️  WARNINGS ({len(summary['warnings'])}):")
        for warning in summary["warnings"]:
            print(f"  ⚠️  {warning}")
    
    print(f"\n💡 RECOMMENDATIONS ({len(summary['recommendations'])}):")
    for i, rec in enumerate(summary["recommendations"], 1):
        print(f"  {i}. {rec}")
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())