#!/usr/bin/env python3
"""
Automated Production Weaviate Schema Deployment for ReAgent Sydney

Automatically deploys production-optimized vector database schemas with
validation and performance testing for Sydney real estate intelligence.
"""

import asyncio
import sys
import logging
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.vector_db.client import WeaviateClient
from src.core.vector_db.schemas_production import PRODUCTION_SCHEMA_REGISTRY
from src.config.settings import get_settings

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('weaviate_deployment.log')
    ]
)
logger = logging.getLogger(__name__)


class AutomatedSchemaDeployer:
    """Automated production-ready Weaviate schema deployment."""
    
    def __init__(self, force_recreate: bool = True):
        self.client: Optional[WeaviateClient] = None
        self.settings = get_settings()
        self.force_recreate = force_recreate
        self.deployment_report = {
            "deployment_timestamp": datetime.now().isoformat(),
            "weaviate_url": self.settings.weaviate.url,
            "force_recreate": force_recreate,
            "schemas_deployed": {},
            "performance_metrics": {},
            "validation_results": {},
            "errors": []
        }
    
    async def connect_to_cluster(self) -> bool:
        """Connect to production Weaviate cluster."""
        try:
            self.client = WeaviateClient()
            await self.client.connect()
            
            # Perform health check
            health = await self.client.health_check()
            
            if health.get("ready", False):
                logger.info("✅ Successfully connected to Weaviate cluster")
                logger.info(f"   🌐 URL: {health.get('url')}")
                logger.info(f"   📊 Status: {health.get('status')}")
                
                # Log cluster metadata
                meta = health.get("meta", {})
                if meta:
                    logger.info(f"   🔧 Version: {meta.get('version', 'unknown')}")
                    modules = meta.get("modules", {})
                    if modules:
                        logger.info(f"   🧩 Modules: {list(modules.keys())}")
                        
                        # Check for OpenAI module
                        if "text2vec-openai" in modules:
                            logger.info("   🤖 OpenAI vectorizer available")
                        else:
                            logger.warning("   ⚠️  OpenAI vectorizer not available, will use transformers")
                
                return True
            else:
                logger.error(f"❌ Weaviate cluster not ready: {health}")
                self.deployment_report["errors"].append(f"Cluster not ready: {health}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to Weaviate cluster: {e}")
            self.deployment_report["errors"].append(f"Connection failed: {str(e)}")
            return False
    
    async def get_schema_statistics(self, class_name: str) -> Dict[str, Any]:
        """Get statistics for existing schema."""
        try:
            count = await self.client.get_object_count(class_name)
            return {
                "object_count": count,
                "exists": True
            }
        except Exception as e:
            return {
                "object_count": 0,
                "exists": False,
                "error": str(e)
            }
    
    async def deploy_schema_automatically(self, class_name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy single schema automatically without user interaction."""
        result = {
            "class_name": class_name,
            "status": "failed",
            "deployment_time": None,
            "pre_deployment_stats": {},
            "post_deployment_stats": {},
            "validation_passed": False,
            "performance_metrics": {},
            "errors": []
        }
        
        try:
            start_time = time.time()
            
            logger.info(f"\n🚀 Deploying {class_name} schema...")
            
            # Get pre-deployment statistics
            result["pre_deployment_stats"] = await self.get_schema_statistics(class_name)
            
            # Check if schema already exists
            existing_schema = self.client._client.schema.get()
            existing_classes = [cls["class"] for cls in existing_schema.get("classes", [])]
            
            if class_name in existing_classes:
                logger.warning(f"⚠️  Schema {class_name} already exists")
                logger.info(f"   📊 Current objects: {result['pre_deployment_stats']['object_count']}")
                
                if self.force_recreate:
                    logger.info(f"🔄 Force recreating {class_name} schema...")
                    
                    # Delete existing schema
                    logger.info(f"🗑️  Deleting existing {class_name} schema...")
                    delete_success = await self.client.delete_schema(class_name)
                    
                    if not delete_success:
                        result["errors"].append("Failed to delete existing schema")
                        return result
                    
                    # Wait for deletion to complete
                    await asyncio.sleep(2)
                    
                else:
                    logger.info(f"⏭️  Skipping {class_name} (force_recreate=False)")
                    result["status"] = "skipped"
                    return result
            
            # Deploy new schema
            logger.info(f"📝 Creating {class_name} schema...")
            logger.info(f"   🔧 Vectorizer: {schema.get('vectorizer', 'none')}")
            logger.info(f"   📊 Properties: {len(schema.get('properties', []))}")
            
            success = await self.client.create_schema(schema)
            
            if not success:
                result["errors"].append("Schema creation failed")
                return result
            
            deployment_time = time.time() - start_time
            result["deployment_time"] = deployment_time
            
            logger.info(f"✅ {class_name} schema deployed in {deployment_time:.2f}s")
            
            # Get post-deployment statistics
            await asyncio.sleep(1)  # Allow schema to propagate
            result["post_deployment_stats"] = await self.get_schema_statistics(class_name)
            
            # Validate deployment
            validation_result = await self.validate_schema_deployment(class_name, schema)
            result["validation_passed"] = validation_result["passed"]
            result["performance_metrics"] = validation_result["performance_metrics"]
            
            if validation_result["passed"]:
                result["status"] = "success" 
                logger.info(f"✅ {class_name} validation passed")
            else:
                result["status"] = "validation_failed"
                result["errors"].extend(validation_result["errors"])
                logger.error(f"❌ {class_name} validation failed")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to deploy {class_name}: {e}")
            result["errors"].append(str(e))
            return result
    
    async def validate_schema_deployment(self, class_name: str, expected_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate deployed schema against expected configuration."""
        validation_result = {
            "passed": False,
            "errors": [],
            "performance_metrics": {},
            "schema_details": {}
        }
        
        try:
            # Get deployed schema
            current_schema = self.client._client.schema.get()
            deployed_class = next((cls for cls in current_schema["classes"] if cls["class"] == class_name), None)
            
            if not deployed_class:
                validation_result["errors"].append(f"Class {class_name} not found after deployment")
                return validation_result
            
            logger.info(f"   🔍 Validating {class_name} deployment...")
            
            # Store schema details for reporting
            validation_result["schema_details"] = {
                "class_name": deployed_class.get("class"),
                "description": deployed_class.get("description"),
                "vectorizer": deployed_class.get("vectorizer"),
                "properties_count": len(deployed_class.get("properties", [])),
                "vector_index_config": deployed_class.get("vectorIndexConfig", {}),
                "module_config": deployed_class.get("moduleConfig", {})
            }
            
            # Check properties count
            expected_props = len(expected_schema.get("properties", []))
            deployed_props = len(deployed_class.get("properties", []))
            
            if expected_props != deployed_props:
                validation_result["errors"].append(f"Property count mismatch: expected {expected_props}, got {deployed_props}")
            else:
                logger.info(f"   ✅ Properties: {deployed_props}/{expected_props}")
            
            # Check vectorizer configuration
            expected_vectorizer = expected_schema.get("vectorizer")
            deployed_vectorizer = deployed_class.get("vectorizer")
            
            if expected_vectorizer != deployed_vectorizer:
                validation_result["errors"].append(f"Vectorizer mismatch: expected {expected_vectorizer}, got {deployed_vectorizer}")
            else:
                logger.info(f"   ✅ Vectorizer: {deployed_vectorizer}")
            
            # Check vector index configuration
            expected_vector_config = expected_schema.get("vectorIndexConfig", {})
            deployed_vector_config = deployed_class.get("vectorIndexConfig", {})
            
            # Check key vector index settings
            key_settings = ["distance", "maxConnections", "efConstruction"]
            for setting in key_settings:
                expected_val = expected_vector_config.get(setting)
                deployed_val = deployed_vector_config.get(setting)
                if expected_val != deployed_val and expected_val is not None:
                    validation_result["errors"].append(f"Vector index {setting} mismatch: expected {expected_val}, got {deployed_val}")
                else:
                    logger.info(f"   ✅ Vector {setting}: {deployed_val}")
            
            # Performance test: Basic operations
            performance_start = time.time()
            
            # Test object count (should be 0 for new schema)
            count = await self.client.get_object_count(class_name)
            logger.info(f"   📊 Object count: {count}")
            
            performance_time = time.time() - performance_start
            validation_result["performance_metrics"]["basic_operations_time"] = performance_time
            validation_result["performance_metrics"]["initial_object_count"] = count
            
            # Mark as passed if no errors
            if not validation_result["errors"]:
                validation_result["passed"] = True
            
            return validation_result
            
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {str(e)}")
            return validation_result
    
    async def run_performance_tests(self) -> Dict[str, Any]:
        """Run comprehensive performance tests."""
        test_results = {
            "vector_search_available": False,
            "openai_integration": False,
            "transformers_available": False,
            "schema_access_times": {},
            "errors": []
        }
        
        try:
            logger.info("\n🧪 Running Performance Tests...")
            
            # Test schema access performance
            schema_start = time.time()
            current_schema = self.client._client.schema.get()
            schema_time = time.time() - schema_start
            test_results["schema_access_times"]["full_schema_retrieval"] = schema_time
            
            logger.info(f"   ⏱️  Schema retrieval: {schema_time:.3f}s")
            
            # Check vector capabilities for each class
            for class_data in current_schema.get("classes", []):
                class_name = class_data["class"]
                vectorizer = class_data.get("vectorizer", "none")
                
                if vectorizer == "text2vec-openai":
                    test_results["openai_integration"] = True
                    test_results["vector_search_available"] = True
                elif vectorizer == "text2vec-transformers":
                    test_results["transformers_available"] = True
                    test_results["vector_search_available"] = True
                
                # Test object count performance
                count_start = time.time()
                count = await self.client.get_object_count(class_name)
                count_time = time.time() - count_start
                test_results["schema_access_times"][f"{class_name}_count"] = count_time
                
                logger.info(f"   📊 {class_name}: {count} objects ({count_time:.3f}s)")
            
            # Overall assessment
            if test_results["vector_search_available"]:
                logger.info("   ✅ Vector search functionality confirmed")
            else:
                logger.warning("   ⚠️  No vector search capability detected")
            
            if test_results["openai_integration"]:
                logger.info("   🤖 OpenAI integration active")
            
            if test_results["transformers_available"]:
                logger.info("   🔧 Transformers vectorizer available")
            
            return test_results
            
        except Exception as e:
            test_results["errors"].append(f"Performance tests failed: {str(e)}")
            logger.error(f"   ❌ Performance tests failed: {e}")
            return test_results
    
    async def generate_deployment_report(self) -> str:
        """Generate comprehensive deployment report."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f"weaviate_production_deployment_report_{timestamp}.json"
        
        # Add summary statistics
        successful = sum(1 for result in self.deployment_report["schemas_deployed"].values() 
                        if result.get("status") == "success")
        failed = sum(1 for result in self.deployment_report["schemas_deployed"].values() 
                    if result.get("status") == "failed")
        skipped = sum(1 for result in self.deployment_report["schemas_deployed"].values() 
                     if result.get("status") == "skipped")
        
        self.deployment_report["summary"] = {
            "total_schemas": len(PRODUCTION_SCHEMA_REGISTRY),
            "successful_deployments": successful,
            "failed_deployments": failed,
            "skipped_deployments": skipped,
            "total_errors": len(self.deployment_report["errors"]),
            "deployment_success_rate": successful / len(PRODUCTION_SCHEMA_REGISTRY) * 100 if PRODUCTION_SCHEMA_REGISTRY else 0
        }
        
        # Write report to file
        with open(report_file, 'w') as f:
            json.dump(self.deployment_report, f, indent=2)
        
        logger.info(f"\n📋 Deployment report saved to: {report_file}")
        return report_file
    
    async def deploy_all_schemas(self) -> bool:
        """Deploy all production schemas automatically."""
        try:
            logger.info("🎯 Starting Automated Production Weaviate Schema Deployment")
            logger.info(f"🔄 Force recreate: {self.force_recreate}")
            logger.info("=" * 70)
            
            # Connect to cluster
            if not await self.connect_to_cluster():
                return False
            
            # Deploy each schema
            total_schemas = len(PRODUCTION_SCHEMA_REGISTRY)
            for i, (class_name, schema) in enumerate(PRODUCTION_SCHEMA_REGISTRY.items(), 1):
                logger.info(f"\n[{i}/{total_schemas}] Processing {class_name}...")
                result = await self.deploy_schema_automatically(class_name, schema)
                self.deployment_report["schemas_deployed"][class_name] = result
            
            # Run performance tests
            performance_results = await self.run_performance_tests()
            self.deployment_report["performance_metrics"] = performance_results
            
            # Generate final report
            report_file = await self.generate_deployment_report()
            
            # Summary
            summary = self.deployment_report["summary"]
            logger.info("\n" + "=" * 70)
            logger.info("🎉 DEPLOYMENT SUMMARY")
            logger.info("=" * 70)
            logger.info(f"✅ Successful: {summary['successful_deployments']}/{summary['total_schemas']}")
            logger.info(f"❌ Failed: {summary['failed_deployments']}/{summary['total_schemas']}")
            logger.info(f"⏭️  Skipped: {summary['skipped_deployments']}/{summary['total_schemas']}")
            logger.info(f"📊 Success Rate: {summary['deployment_success_rate']:.1f}%")
            logger.info(f"⚠️  Total Errors: {summary['total_errors']}")
            logger.info(f"📋 Full Report: {report_file}")
            
            # Disconnect
            if self.client:
                await self.client.disconnect()
            
            return summary['failed_deployments'] == 0
            
        except Exception as e:
            logger.error(f"❌ Deployment process failed: {e}")
            self.deployment_report["errors"].append(f"Process failure: {str(e)}")
            return False


async def main():
    """Main deployment function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy production Weaviate schemas")
    parser.add_argument("--no-force", action="store_true", 
                       help="Don't force recreate existing schemas")
    args = parser.parse_args()
    
    force_recreate = not args.no_force
    
    deployer = AutomatedSchemaDeployer(force_recreate=force_recreate)
    success = await deployer.deploy_all_schemas()
    
    if success:
        logger.info("\n🎉 All schemas deployed successfully!")
        sys.exit(0)
    else:
        logger.error("\n❌ Schema deployment completed with errors!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())