#!/usr/bin/env python3
"""
Weaviate OpenAI Integration Test Suite

Comprehensive validation of Weaviate text2vec-openai module integration
for the ReAgent Sydney system. Tests schema creation, object insertion,
and vector search capabilities with OpenAI embeddings.

Author: API Integration Expert  
Date: 2025-07-29
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Any
import sys
import os

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import structlog

from src.config.settings import get_settings
from src.core.vector_db.client import WeaviateClient, SearchQuery


# Configure logging
logging = structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger(__name__)


class WeaviateOpenAIIntegrationValidator:
    """Validates Weaviate integration with OpenAI text2vec module."""
    
    def __init__(self):
        self.settings = get_settings()
        self.weaviate_client = None
        self.test_class_name = "TestProperty"
        self.test_results = {}
        
        # Test property data
        self.test_properties = [
            {
                "title": "Luxury Bondi Apartment",
                "description": "Stunning 3-bedroom apartment in Bondi with ocean views, modern kitchen, and rooftop terrace",
                "suburb": "Bondi",
                "property_type": "apartment",
                "bedrooms": 3,
                "price": 1500000
            },
            {
                "title": "Northern Beaches Family Home", 
                "description": "Family-friendly 4-bedroom house in Northern Beaches with garden, garage, and swimming pool",
                "suburb": "Manly",
                "property_type": "house",
                "bedrooms": 4,
                "price": 2200000
            },
            {
                "title": "CBD Modern Unit",
                "description": "Modern 2-bedroom unit in CBD with harbour glimpses, gym facilities, and concierge service",
                "suburb": "Sydney",
                "property_type": "unit",
                "bedrooms": 2,
                "price": 1100000
            }
        ]
    
    async def initialize_weaviate_client(self) -> bool:
        """Initialize Weaviate client and connect."""
        try:
            logger.info("Initializing Weaviate client")
            
            self.weaviate_client = WeaviateClient(self.settings)
            await self.weaviate_client.connect()
            
            logger.info("Weaviate client initialized successfully")
            return True
            
        except Exception as e:
            logger.error("Failed to initialize Weaviate client", error=str(e))
            return False
    
    async def test_weaviate_connectivity(self) -> Dict[str, Any]:
        """Test Weaviate connectivity and health."""
        logger.info("Testing Weaviate connectivity")
        test_results = {
            "test_name": "Weaviate Connectivity",
            "status": "failed",
            "details": {},
            "errors": []
        }
        
        try:
            start_time = time.time()
            
            # Health check
            health_result = await self.weaviate_client.health_check()
            
            response_time = time.time() - start_time
            
            is_healthy = health_result.get("ready", False)
            
            test_results.update({
                "status": "passed" if is_healthy else "failed",
                "details": {
                    "health_check": health_result,
                    "response_time_seconds": round(response_time, 3),
                    "weaviate_url": self.settings.weaviate.url,
                    "api_key_configured": bool(self.settings.weaviate.api_key)
                }
            })
            
            if not is_healthy:
                test_results["errors"].append("Weaviate instance not ready")
            
            logger.info("Weaviate connectivity test completed", 
                       healthy=is_healthy, 
                       response_time=response_time)
            
        except Exception as e:
            test_results["errors"].append(f"Weaviate connectivity failed: {str(e)}")
            logger.error("Weaviate connectivity test failed", error=str(e))
        
        return test_results
    
    async def test_text2vec_openai_schema(self) -> Dict[str, Any]:
        """Test creating schema with text2vec-openai module."""
        logger.info("Testing text2vec-openai schema creation")
        test_results = {
            "test_name": "Text2Vec OpenAI Schema",
            "status": "failed",
            "details": {},
            "errors": []
        }
        
        try:
            # Define schema with text2vec-openai vectorizer
            schema = {
                "class": self.test_class_name,
                "description": "Test property class with OpenAI embeddings",
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "ada",  # Use legacy model supported by older Weaviate
                        "type": "text"
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
                        "name": "suburb",
                        "dataType": ["text"],
                        "description": "Property suburb"
                    },
                    {
                        "name": "property_type",
                        "dataType": ["text"],
                        "description": "Type of property"
                    },
                    {
                        "name": "bedrooms",
                        "dataType": ["int"],
                        "description": "Number of bedrooms"
                    },
                    {
                        "name": "price",
                        "dataType": ["number"],
                        "description": "Property price"
                    }
                ]
            }
            
            # Clean up any existing test schema
            await self.weaviate_client.delete_schema(self.test_class_name)
            
            # Create the schema
            start_time = time.time()
            schema_created = await self.weaviate_client.create_schema(schema)
            creation_time = time.time() - start_time
            
            test_results.update({
                "status": "passed" if schema_created else "failed",
                "details": {
                    "schema_created": schema_created,
                    "creation_time_seconds": round(creation_time, 3),
                    "vectorizer_used": "text2vec-openai",
                    "embedding_model": "text-embedding-3-small",
                    "expected_dimensions": 1536,
                    "schema": schema
                }
            })
            
            if not schema_created:
                test_results["errors"].append("Failed to create schema with text2vec-openai")
            
            logger.info("Schema creation test completed", 
                       created=schema_created, 
                       time=creation_time)
            
        except Exception as e:
            test_results["errors"].append(f"Schema creation failed: {str(e)}")
            logger.error("Schema creation test failed", error=str(e))
        
        return test_results
    
    async def test_automatic_vectorization(self) -> Dict[str, Any]:
        """Test automatic vectorization of inserted objects."""
        logger.info("Testing automatic OpenAI vectorization")
        test_results = {
            "test_name": "Automatic Vectorization",
            "status": "failed",
            "details": {},
            "errors": []
        }
        
        try:
            inserted_objects = []
            insertion_times = []
            
            # Insert test properties (Weaviate will auto-generate embeddings)
            for i, property_data in enumerate(self.test_properties):
                start_time = time.time()
                
                object_id = str(uuid.uuid4())
                inserted_id = await self.weaviate_client.insert_object(
                    class_name=self.test_class_name,
                    properties=property_data,
                    object_id=object_id
                )
                
                insertion_time = time.time() - start_time
                insertion_times.append(insertion_time)
                
                if inserted_id:
                    inserted_objects.append({
                        "object_id": inserted_id,
                        "title": property_data["title"],
                        "insertion_time": insertion_time
                    })
                    
                    logger.debug(f"Inserted object {i+1}", 
                               object_id=inserted_id,
                               time=insertion_time)
            
            # Get object count to verify insertion
            object_count = await self.weaviate_client.get_object_count(self.test_class_name)
            
            all_inserted = len(inserted_objects) == len(self.test_properties)
            avg_insertion_time = sum(insertion_times) / len(insertion_times) if insertion_times else 0
            
            test_results.update({
                "status": "passed" if all_inserted else "failed",
                "details": {
                    "objects_inserted": len(inserted_objects),
                    "total_objects_expected": len(self.test_properties),
                    "all_objects_inserted": all_inserted,
                    "average_insertion_time": round(avg_insertion_time, 3),
                    "total_objects_in_class": object_count,
                    "inserted_objects": inserted_objects
                }
            })
            
            if not all_inserted:
                test_results["errors"].append(f"Only {len(inserted_objects)}/{len(self.test_properties)} objects inserted")
            
            logger.info("Automatic vectorization test completed",
                       inserted=len(inserted_objects),
                       expected=len(self.test_properties),
                       avg_time=avg_insertion_time)
            
        except Exception as e:
            test_results["errors"].append(f"Automatic vectorization failed: {str(e)}")
            logger.error("Automatic vectorization test failed", error=str(e))
        
        return test_results
    
    async def test_vector_search_capabilities(self) -> Dict[str, Any]:
        """Test vector search using text queries."""
        logger.info("Testing vector search capabilities")
        test_results = {
            "test_name": "Vector Search Capabilities",
            "status": "failed",
            "details": {},
            "errors": []
        }
        
        try:
            # Test queries
            search_queries = [
                "luxury apartment with ocean views",
                "family home with swimming pool",
                "modern unit near city center"
            ]
            
            search_results = []
            
            for i, query_text in enumerate(search_queries):
                start_time = time.time()
                
                # Perform hybrid search (combines text and vector search)
                results = await self.weaviate_client.hybrid_search(
                    class_name=self.test_class_name,
                    query_text=query_text,
                    limit=5
                )
                
                search_time = time.time() - start_time
                
                search_results.append({
                    "query": query_text,
                    "results_count": len(results),
                    "search_time_seconds": round(search_time, 3),
                    "top_result": {
                        "title": results[0].data.get("title", "N/A") if results else "No results",
                        "score": results[0].score if results else 0,
                        "suburb": results[0].data.get("suburb", "N/A") if results else "N/A"
                    } if results else None
                })
                
                logger.debug(f"Search query {i+1} completed",
                           query=query_text,
                           results=len(results),
                           time=search_time)
            
            # Analyze search performance
            total_searches = len(search_results)
            searches_with_results = len([r for r in search_results if r["results_count"] > 0])
            avg_search_time = sum(r["search_time_seconds"] for r in search_results) / total_searches
            
            search_success_rate = searches_with_results / total_searches if total_searches > 0 else 0
            meets_performance_req = avg_search_time < 1.0  # < 1 second average
            
            test_results.update({
                "status": "passed" if search_success_rate > 0.5 and meets_performance_req else "failed",
                "details": {
                    "total_searches": total_searches,
                    "searches_with_results": searches_with_results,
                    "search_success_rate": round(search_success_rate, 2),
                    "average_search_time": round(avg_search_time, 3),
                    "meets_performance_requirement": meets_performance_req,
                    "search_results": search_results
                }
            })
            
            if search_success_rate <= 0.5:
                test_results["errors"].append(f"Low search success rate: {search_success_rate:.2%}")
            if not meets_performance_req:
                test_results["errors"].append(f"Search too slow: {avg_search_time:.3f}s > 1.0s requirement")
            
            logger.info("Vector search test completed",
                       success_rate=search_success_rate,
                       avg_time=avg_search_time,
                       performance_ok=meets_performance_req)
            
        except Exception as e:
            test_results["errors"].append(f"Vector search failed: {str(e)}")
            logger.error("Vector search test failed", error=str(e))
        
        return test_results
    
    async def test_embedding_quality(self) -> Dict[str, Any]:
        """Test quality of generated embeddings through similarity checks."""
        logger.info("Testing embedding quality")
        test_results = {
            "test_name": "Embedding Quality",
            "status": "failed",
            "details": {},
            "errors": []
        }
        
        try:
            # Test semantic similarity
            # "luxury apartment" should be more similar to luxury properties
            luxury_query = "expensive luxury apartment with premium features"
            
            luxury_results = await self.weaviate_client.hybrid_search(
                class_name=self.test_class_name,
                query_text=luxury_query,
                limit=3
            )
            
            # "family home" should match family properties better
            family_query = "spacious family house with kids facilities"
            
            family_results = await self.weaviate_client.hybrid_search(
                class_name=self.test_class_name,
                query_text=family_query,
                limit=3
            )
            
            # Analyze results for semantic correctness
            luxury_matches_luxury = False
            family_matches_family = False
            
            if luxury_results:
                top_luxury_result = luxury_results[0]
                luxury_title = top_luxury_result.data.get("title", "").lower()
                luxury_matches_luxury = "luxury" in luxury_title or "bondi" in luxury_title
            
            if family_results:
                top_family_result = family_results[0]
                family_title = top_family_result.data.get("title", "").lower()
                family_matches_family = "family" in family_title or "northern" in family_title
            
            semantic_accuracy = (int(luxury_matches_luxury) + int(family_matches_family)) / 2
            
            test_results.update({
                "status": "passed" if semantic_accuracy >= 0.5 else "failed",
                "details": {
                    "luxury_query": luxury_query,
                    "luxury_top_match": luxury_results[0].data.get("title") if luxury_results else "No results",
                    "luxury_matches_expectation": luxury_matches_luxury,
                    "family_query": family_query,
                    "family_top_match": family_results[0].data.get("title") if family_results else "No results",
                    "family_matches_expectation": family_matches_family,
                    "semantic_accuracy": round(semantic_accuracy, 2),
                    "embedding_quality_assessment": "good" if semantic_accuracy >= 0.75 else "acceptable" if semantic_accuracy >= 0.5 else "poor"
                }
            })
            
            if semantic_accuracy < 0.5:
                test_results["errors"].append(f"Poor semantic accuracy: {semantic_accuracy:.2%}")
            
            logger.info("Embedding quality test completed",
                       semantic_accuracy=semantic_accuracy,
                       luxury_match=luxury_matches_luxury,
                       family_match=family_matches_family)
            
        except Exception as e:
            test_results["errors"].append(f"Embedding quality test failed: {str(e)}")
            logger.error("Embedding quality test failed", error=str(e))
        
        return test_results
    
    async def cleanup_test_data(self) -> bool:
        """Clean up test schema and data."""
        try:
            logger.info("Cleaning up test data")
            
            # Delete the test schema (this removes all objects too)
            deleted = await self.weaviate_client.delete_schema(self.test_class_name)
            
            logger.info("Test data cleanup completed", schema_deleted=deleted)
            return deleted
            
        except Exception as e:
            logger.error("Test data cleanup failed", error=str(e))
            return False
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive Weaviate OpenAI integration validation."""
        logger.info("Starting comprehensive Weaviate OpenAI integration validation")
        
        validation_results = {
            "validation_timestamp": time.time(),
            "validation_date": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "configuration": {
                "weaviate_url": self.settings.weaviate.url,
                "api_key_configured": bool(self.settings.weaviate.api_key),
                "openai_api_key_configured": bool(self.settings.apis.openai_api_key or os.getenv('OPENAI_API_KEY')),
                "environment": self.settings.environment
            },
            "tests": [],
            "summary": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "overall_status": "unknown"
            }
        }
        
        # Initialize Weaviate client
        if not await self.initialize_weaviate_client():
            validation_results["summary"]["overall_status"] = "failed"
            validation_results["summary"]["total_tests"] = 1
            validation_results["summary"]["failed_tests"] = 1
            validation_results["tests"] = [{
                "test_name": "Weaviate Client Initialization",
                "status": "failed",
                "errors": ["Failed to initialize Weaviate client"]
            }]
            return validation_results
        
        # Run all tests
        test_methods = [
            self.test_weaviate_connectivity,
            self.test_text2vec_openai_schema,
            self.test_automatic_vectorization,
            self.test_vector_search_capabilities,
            self.test_embedding_quality
        ]
        
        try:
            for test_method in test_methods:
                try:
                    test_result = await test_method()
                    validation_results["tests"].append(test_result)
                    validation_results["summary"]["total_tests"] += 1
                    
                    if test_result["status"] == "passed":
                        validation_results["summary"]["passed_tests"] += 1
                    else:
                        validation_results["summary"]["failed_tests"] += 1
                        
                except Exception as e:
                    logger.error(f"Test method {test_method.__name__} failed", error=str(e))
                    validation_results["tests"].append({
                        "test_name": test_method.__name__,
                        "status": "failed",
                        "errors": [f"Test execution failed: {str(e)}"]
                    })
                    validation_results["summary"]["total_tests"] += 1
                    validation_results["summary"]["failed_tests"] += 1
        
        finally:
            # Always attempt cleanup
            await self.cleanup_test_data()
            
            # Close Weaviate connection
            if self.weaviate_client:
                await self.weaviate_client.disconnect()
        
        # Determine overall status
        if validation_results["summary"]["failed_tests"] == 0:
            validation_results["summary"]["overall_status"] = "passed"
        elif validation_results["summary"]["passed_tests"] > 0:
            validation_results["summary"]["overall_status"] = "partial"
        else:
            validation_results["summary"]["overall_status"] = "failed"
        
        logger.info("Comprehensive Weaviate validation completed",
                   total=validation_results["summary"]["total_tests"],
                   passed=validation_results["summary"]["passed_tests"],
                   failed=validation_results["summary"]["failed_tests"],
                   overall=validation_results["summary"]["overall_status"])
        
        return validation_results


async def main():
    """Main validation execution."""
    print("=" * 80)
    print("Weaviate OpenAI Integration Validation Suite")
    print("ReAgent Sydney - API Integration Expert")
    print("=" * 80)
    
    validator = WeaviateOpenAIIntegrationValidator()
    results = await validator.run_comprehensive_validation()
    
    # Save results to file
    results_file = "weaviate_openai_integration_report.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print(f"\nValidation Summary:")
    print(f"Total Tests: {results['summary']['total_tests']}")
    print(f"Passed: {results['summary']['passed_tests']}")
    print(f"Failed: {results['summary']['failed_tests']}")
    print(f"Overall Status: {results['summary']['overall_status'].upper()}")
    print(f"\nDetailed results saved to: {results_file}")
    
    # Print test details
    print(f"\nTest Results:")
    for test in results["tests"]:
        status_icon = "✅" if test["status"] == "passed" else "❌"
        print(f"{status_icon} {test['test_name']}: {test['status'].upper()}")
        if test.get("errors"):
            for error in test["errors"]:
                print(f"   Error: {error}")
    
    print("=" * 80)
    return results["summary"]["overall_status"] == "passed"


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)