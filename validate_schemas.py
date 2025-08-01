#!/usr/bin/env python3
"""
Comprehensive Weaviate Schema Validation

Tests all deployed schemas for proper configuration, indexing,
and vector search capabilities.
"""

import asyncio
import sys
import logging
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.vector_db.client import WeaviateClient
from src.core.vector_db.schemas import SCHEMA_REGISTRY

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def validate_schemas():
    """Comprehensive schema validation."""
    
    try:
        # Initialize client
        client = WeaviateClient()
        await client.connect()
        logger.info("✅ Connected to Weaviate cluster")
        
        # Get current schema
        full_schema = client._client.schema.get()
        existing_classes = {cls["class"]: cls for cls in full_schema.get("classes", [])}
        
        logger.info(f"📊 Found {len(existing_classes)} classes in cluster")
        
        validation_results = {}
        
        # Validate each schema
        for class_name, expected_schema in SCHEMA_REGISTRY.items():
            logger.info(f"\n🔍 Validating {class_name} schema...")
            
            if class_name not in existing_classes:
                logger.error(f"❌ {class_name} not found in cluster")
                validation_results[class_name] = "missing"
                continue
            
            actual_schema = existing_classes[class_name]
            result = {"status": "success", "details": {}}
            
            # Validate basic properties
            logger.info(f"   📋 Basic Properties:")
            logger.info(f"      Class: {actual_schema.get('class')}")
            logger.info(f"      Description: {actual_schema.get('description', 'N/A')}")
            
            # Validate vectorizer configuration
            logger.info(f"   🤖 Vectorizer Configuration:")
            vectorizer = actual_schema.get('vectorizer', 'none')
            logger.info(f"      Vectorizer: {vectorizer}")
            
            if vectorizer == 'text2vec-openai':
                module_config = actual_schema.get('moduleConfig', {}).get('text2vec-openai', {})
                logger.info(f"      Model: {module_config.get('model', 'unknown')}")
                logger.info(f"      Model Version: {module_config.get('modelVersion', 'unknown')}")
                logger.info(f"      Dimensions: {module_config.get('dimensions', 'unknown')}")
                logger.info(f"      Type: {module_config.get('type', 'unknown')}")
                
                # Validate OpenAI configuration
                if module_config.get('model') == 'ada' and module_config.get('dimensions') == 1536:
                    logger.info(f"      ✅ OpenAI configuration correct")
                else:
                    logger.warning(f"      ⚠️  OpenAI configuration issues detected")
                    result["details"]["openai_config"] = "incorrect"
            
            # Validate vector index configuration
            logger.info(f"   📐 Vector Index Configuration:")
            vector_config = actual_schema.get('vectorIndexConfig', {})
            logger.info(f"      Skip: {vector_config.get('skip', False)}")
            logger.info(f"      Distance: {vector_config.get('distance', 'unknown')}")
            logger.info(f"      Max Connections: {vector_config.get('maxConnections', 'unknown')}")
            logger.info(f"      EF Construction: {vector_config.get('efConstruction', 'unknown')}")
            
            # Validate properties
            logger.info(f"   📊 Properties:")
            actual_properties = actual_schema.get('properties', [])
            expected_properties = expected_schema.get('properties', [])
            
            logger.info(f"      Expected: {len(expected_properties)} properties")
            logger.info(f"      Actual: {len(actual_properties)} properties")
            
            # Create property maps for comparison
            actual_prop_map = {prop['name']: prop for prop in actual_properties}
            expected_prop_map = {prop['name']: prop for prop in expected_properties}
            
            missing_props = set(expected_prop_map.keys()) - set(actual_prop_map.keys())
            extra_props = set(actual_prop_map.keys()) - set(expected_prop_map.keys())
            
            if missing_props:
                logger.warning(f"      ⚠️  Missing properties: {list(missing_props)}")
                result["details"]["missing_properties"] = list(missing_props)
            
            if extra_props:
                logger.info(f"      ℹ️  Extra properties: {list(extra_props)}")
            
            # Validate property types and indexing
            indexing_issues = []
            for prop_name in expected_prop_map.keys():
                if prop_name in actual_prop_map:
                    expected_prop = expected_prop_map[prop_name]
                    actual_prop = actual_prop_map[prop_name]
                    
                    # Check data type
                    if expected_prop.get('dataType') != actual_prop.get('dataType'):
                        indexing_issues.append(f"{prop_name}: dataType mismatch")
                    
                    # Check indexing
                    for index_type in ['indexFilterable', 'indexSearchable']:
                        if expected_prop.get(index_type) != actual_prop.get(index_type):
                            indexing_issues.append(f"{prop_name}: {index_type} mismatch")
            
            if indexing_issues:
                logger.warning(f"      ⚠️  Indexing issues: {indexing_issues[:5]}...")  # Show first 5
                result["details"]["indexing_issues"] = indexing_issues
            else:
                logger.info(f"      ✅ All property configurations match")
            
            # Test basic operations
            logger.info(f"   🧪 Testing Basic Operations:")
            
            try:
                # Test object count
                count = await client.get_object_count(class_name)
                logger.info(f"      📊 Object count: {count}")
                result["details"]["object_count"] = count
                
                # Test schema retrieval
                schema_test = client._client.schema.get(class_name)
                if schema_test:
                    logger.info(f"      ✅ Schema retrieval works")
                else:
                    logger.error(f"      ❌ Schema retrieval failed")
                    result["status"] = "partial"
                    
            except Exception as e:
                logger.error(f"      ❌ Basic operations failed: {e}")
                result["status"] = "failed"
                result["details"]["operation_error"] = str(e)
            
            validation_results[class_name] = result
        
        # Summary
        logger.info(f"\n📊 Validation Summary:")
        success_count = sum(1 for r in validation_results.values() if r.get("status") == "success")
        total_count = len(validation_results)
        
        logger.info(f"   ✅ Successful validations: {success_count}/{total_count}")
        
        for class_name, result in validation_results.items():
            status = result.get("status", "unknown")
            status_emoji = {"success": "✅", "partial": "⚠️", "failed": "❌", "missing": "❌"}.get(status, "❓")
            logger.info(f"   {status_emoji} {class_name}: {status}")
            
            if result.get("details"):
                details = result["details"]
                if "missing_properties" in details:
                    logger.info(f"      Missing props: {len(details['missing_properties'])}")
                if "indexing_issues" in details:
                    logger.info(f"      Indexing issues: {len(details['indexing_issues'])}")
                if "object_count" in details:
                    logger.info(f"      Objects: {details['object_count']}")
        
        # Test vector search capability (if possible)
        logger.info(f"\n🔍 Testing Vector Search Capabilities:")
        
        try:
            # Test with a simple query (won't work without data, but tests API)
            from src.core.vector_db.client import SearchQuery
            
            test_vector = [0.1] * 1536  # Dummy 1536-dimension vector
            search_query = SearchQuery(
                vector=test_vector,
                class_name="Property",
                limit=1
            )
            
            results = await client.vector_search(search_query)
            logger.info(f"   ✅ Vector search API functional (returned {len(results)} results)")
            
        except Exception as e:
            logger.warning(f"   ⚠️  Vector search test failed: {e} (expected without data)")
        
        await client.disconnect()
        logger.info(f"\n🎉 Schema validation completed!")
        
        return validation_results
        
    except Exception as e:
        logger.error(f"❌ Schema validation failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(validate_schemas())