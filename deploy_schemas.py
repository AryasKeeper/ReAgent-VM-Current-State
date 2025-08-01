#!/usr/bin/env python3
"""
Deploy Weaviate Vector Database Schemas

Initializes the Weaviate vector database with production-ready schemas
for ReAgent Sydney's AI-powered property matching system.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.vector_db.client import WeaviateClient
from src.core.vector_db.schemas import SCHEMA_REGISTRY

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def deploy_schemas():
    """Deploy all Weaviate schemas."""
    
    try:
        # Initialize client
        client = WeaviateClient()
        await client.connect()
        logger.info("✅ Connected to Weaviate cluster")
        
        # Get current schema
        existing_schema = client._client.schema.get()
        existing_classes = [cls["class"] for cls in existing_schema.get("classes", [])]
        logger.info(f"Existing classes: {existing_classes}")
        
        # Deploy each schema
        deployment_results = {}
        
        for class_name, schema in SCHEMA_REGISTRY.items():
            logger.info(f"\n🚀 Deploying {class_name} schema...")
            
            # Check if class already exists
            if class_name in existing_classes:
                logger.warning(f"⚠️  Class {class_name} already exists")
                
                # Ask user if they want to recreate
                response = input(f"Recreate {class_name} schema? (y/N): ").strip().lower()
                if response == 'y':
                    logger.info(f"🗑️  Deleting existing {class_name} class...")
                    await client.delete_schema(class_name)
                else:
                    logger.info(f"⏭️  Skipping {class_name}")
                    deployment_results[class_name] = "skipped"
                    continue
            
            # Create schema
            success = await client.create_schema(schema)
            
            if success:
                logger.info(f"✅ Successfully deployed {class_name} schema")
                deployment_results[class_name] = "success"
                
                # Verify schema was created
                new_schema = client._client.schema.get()
                new_classes = [cls["class"] for cls in new_schema.get("classes", [])]
                
                if class_name in new_classes:
                    logger.info(f"✅ Verified {class_name} exists in cluster")
                    
                    # Get schema details
                    class_schema = next((cls for cls in new_schema["classes"] if cls["class"] == class_name), None)
                    if class_schema:
                        logger.info(f"   📊 Properties: {len(class_schema.get('properties', []))}")
                        logger.info(f"   🔍 Vectorizer: {class_schema.get('vectorizer', 'none')}")
                        logger.info(f"   📐 Vector Index: {class_schema.get('vectorIndexConfig', {}).get('distance', 'unknown')}")
                        
                        # Check OpenAI configuration
                        module_config = class_schema.get('moduleConfig', {})
                        if 'text2vec-openai' in module_config:
                            openai_config = module_config['text2vec-openai']
                            logger.info(f"   🤖 OpenAI Model: {openai_config.get('model', 'unknown')}")
                            logger.info(f"   📏 Dimensions: {openai_config.get('dimensions', 'unknown')}")
                else:
                    logger.error(f"❌ Failed to verify {class_name} in cluster")
                    deployment_results[class_name] = "verification_failed"
            else:
                logger.error(f"❌ Failed to deploy {class_name} schema")
                deployment_results[class_name] = "failed"
        
        # Final validation
        logger.info("\n🔍 Final Schema Validation:")
        final_schema = client._client.schema.get()
        final_classes = [cls["class"] for cls in final_schema.get("classes", [])]
        
        for class_name in SCHEMA_REGISTRY.keys():
            if class_name in final_classes:
                logger.info(f"✅ {class_name}: Deployed and verified")
            else:
                logger.error(f"❌ {class_name}: Missing from cluster")
        
        # Summary
        logger.info(f"\n📊 Deployment Summary:")
        for class_name, status in deployment_results.items():
            status_emoji = {
                "success": "✅",
                "failed": "❌", 
                "skipped": "⏭️",
                "verification_failed": "⚠️"
            }.get(status, "❓")
            logger.info(f"   {status_emoji} {class_name}: {status}")
        
        # Test basic operations
        logger.info(f"\n🧪 Testing Basic Operations:")
        
        for class_name in SCHEMA_REGISTRY.keys():
            if class_name in final_classes:
                try:
                    count = await client.get_object_count(class_name)
                    logger.info(f"   📊 {class_name}: {count} objects")
                except Exception as e:
                    logger.error(f"   ❌ {class_name}: Error getting count - {e}")
        
        await client.disconnect()
        logger.info("\n🎉 Schema deployment completed!")
        
        return deployment_results
        
    except Exception as e:
        logger.error(f"❌ Schema deployment failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(deploy_schemas())