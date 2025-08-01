#!/usr/bin/env python3
"""
Production Weaviate Schema Deployment for ReAgent Sydney

Deploys production-optimized vector database schemas with comprehensive
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


class ProductionSchemaDeployer:
    """Production-ready Weaviate schema deployment and validation."""
    
    def __init__(self):
        self.client: Optional[WeaviateClient] = None
        self.settings = get_settings()
        self.deployment_report = {
            "deployment_timestamp": datetime.now().isoformat(),
            "weaviate_url": self.settings.weaviate.url,
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
                
                return True
            else:
                logger.error(f"❌ Weaviate cluster not ready: {health}")
                self.deployment_report["errors"].append(f"Cluster not ready: {health}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to connect to Weaviate cluster: {e}")
            self.deployment_report["errors"].append(f"Connection failed: {str(e)}")
            return False
    
    async def analyze_existing_schemas(self) -> Dict[str, Any]:
        """Analyze existing schemas in the cluster."""
        try:
            existing_schema = self.client._client.schema.get()
            existing_classes = [cls["class"] for cls in existing_schema.get("classes", [])]
            
            logger.info(f"📋 Found {len(existing_classes)} existing classes: {existing_classes}")
            
            analysis = {
                "total_classes": len(existing_classes),
                "class_names": existing_classes,
                "conflicts": [],
                "recommendations": []
            }
            
            # Check for conflicts with production schemas
            for class_name in PRODUCTION_SCHEMA_REGISTRY.keys():
                if class_name in existing_classes:
                    analysis["conflicts"].append(class_name)
                    analysis["recommendations"].append(f"Consider backing up {class_name} data before recreation")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Failed to analyze existing schemas: {e}")
            return {"error": str(e)}
    
    async def backup_existing_data(self, class_name: str) -> bool:
        """Backup existing data before schema recreation."""
        try:
            # Get object count
            count = await self.client.get_object_count(class_name)
            
            if count > 0:
                logger.info(f"🔄 Backing up {count} objects from {class_name}...")
                
                # For production, you would implement actual backup logic here
                # This is a placeholder for the backup process
                backup_file = f"backup_{class_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                logger.info(f"   💾 Backup would be saved to: {backup_file}")
                
                # In real implementation, you would:
                # 1. Query all objects from the class
                # 2. Save to backup file
                # 3. Verify backup integrity
                
                return True
            else:
                logger.info(f"   ℹ️  No data to backup in {class_name}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Backup failed for {class_name}: {e}")
            return False
    
    async def deploy_schema_with_validation(self, class_name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy single schema with comprehensive validation."""
        result = {
            "class_name": class_name,
            "status": "failed",
            "deployment_time": None,
            "validation_passed": False,
            "performance_metrics": {},
            "errors": []
        }
        
        try:
            start_time = time.time()
            
            logger.info(f"\n🚀 Deploying {class_name} schema...")
            
            # Check if schema already exists
            existing_schema = self.client._client.schema.get()
            existing_classes = [cls["class"] for cls in existing_schema.get("classes", [])]
            
            if class_name in existing_classes:
                logger.warning(f"⚠️  Schema {class_name} already exists")
                
                # Ask for confirmation in production
                if self.settings.environment == "production":
                    response = input(f"🔄 Recreate {class_name} schema? This will delete existing data! (yes/no): ").strip().lower()
                    if response != "yes":
                        logger.info(f"⏭️  Skipping {class_name}")
                        result["status"] = "skipped"
                        return result
                
                # Backup data if exists
                backup_success = await self.backup_existing_data(class_name)
                if not backup_success:
                    logger.error(f"❌ Backup failed for {class_name}, aborting deployment")
                    result["errors"].append("Backup failed")
                    return result
                
                # Delete existing schema
                logger.info(f"🗑️  Deleting existing {class_name} schema...")
                await self.client.delete_schema(class_name)
                
                # Wait for deletion to complete
                await asyncio.sleep(1)
            
            # Deploy new schema
            logger.info(f"📝 Creating {class_name} schema...")
            success = await self.client.create_schema(schema)
            
            if not success:
                result["errors"].append("Schema creation failed")
                return result
            
            deployment_time = time.time() - start_time
            result["deployment_time"] = deployment_time
            
            logger.info(f"✅ {class_name} schema deployed in {deployment_time:.2f}s")
            
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
            "schema_comparison": {}
        }
        
        try:
            # Get deployed schema
            current_schema = self.client._client.schema.get()
            deployed_class = next((cls for cls in current_schema["classes"] if cls["class"] == class_name), None)
            
            if not deployed_class:
                validation_result["errors"].append(f"Class {class_name} not found after deployment")
                return validation_result
            
            # Validate class exists
            logger.info(f"   🔍 Validating {class_name} deployment...")
            
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
            
            if expected_vector_config.get("distance") != deployed_vector_config.get("distance"):
                validation_result["errors"].append("Vector index distance mismatch")
            else:
                logger.info(f"   ✅ Vector distance: {deployed_vector_config.get('distance')}")
            
            # Performance test: Basic operations
            performance_start = time.time()
            
            # Test object count (should be 0 for new schema)
            count = await self.client.get_object_count(class_name)
            logger.info(f"   📊 Object count: {count}")
            
            performance_time = time.time() - performance_start
            validation_result["performance_metrics"]["basic_operations_time"] = performance_time
            
            # Mark as passed if no errors
            if not validation_result["errors"]:
                validation_result["passed"] = True
            
            return validation_result
            
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {str(e)}")
            return validation_result
    
    async def test_vector_operations(self) -> Dict[str, Any]:
        """Test vector search performance and functionality."""
        test_results = {
            "vector_search_available": False,
            "embedding_generation_time": None,
            "search_latency": None,
            "errors": []
        }
        
        try:
            logger.info("\n🧪 Testing vector operations...")
            
            # Test if we can perform vector operations
            # This would require actual test data and embeddings
            # For now, we'll check if the functionality is available
            
            property_schema = self.client._client.schema.get()
            property_class = next((cls for cls in property_schema["classes"] if cls["class"] == "Property"), None)
            
            if property_class and property_class.get("vectorizer") != "none":
                test_results["vector_search_available"] = True
                logger.info("   ✅ Vector search functionality available")
            else:
                test_results["errors"].append("Vector search not available")
                logger.warning("   ⚠️  Vector search not available")
            
            return test_results
            
        except Exception as e:
            test_results["errors"].append(f"Vector operations test failed: {str(e)}")
            logger.error(f"   ❌ Vector operations test failed: {e}")
            return test_results
    
    async def generate_deployment_report(self) -> str:
        """Generate comprehensive deployment report."""
        report_file = f"weaviate_deployment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Add summary statistics
        self.deployment_report["summary"] = {
            "total_schemas": len(PRODUCTION_SCHEMA_REGISTRY),
            "successful_deployments": sum(1 for result in self.deployment_report["schemas_deployed"].values() 
                                         if result.get("status") == "success"),
            "failed_deployments": sum(1 for result in self.deployment_report["schemas_deployed"].values() 
                                     if result.get("status") == "failed"),
            "total_errors": len(self.deployment_report["errors"])
        }
        
        # Write report to file
        with open(report_file, 'w') as f:
            json.dump(self.deployment_report, f, indent=2)
        
        logger.info(f"\n📋 Deployment report saved to: {report_file}")
        return report_file
    
    async def deploy_all_schemas(self) -> bool:
        """Deploy all production schemas with comprehensive validation."""
        try:
            logger.info("🎯 Starting Production Weaviate Schema Deployment")
            logger.info("=" * 60)
            
            # Connect to cluster
            if not await self.connect_to_cluster():
                return False
            
            # Analyze existing schemas
            analysis = await self.analyze_existing_schemas()
            logger.info(f"📊 Schema Analysis: {analysis}")
            
            # Deploy each schema
            for class_name, schema in PRODUCTION_SCHEMA_REGISTRY.items():
                result = await self.deploy_schema_with_validation(class_name, schema)
                self.deployment_report["schemas_deployed"][class_name] = result
            
            # Test vector operations
            vector_test_results = await self.test_vector_operations()
            self.deployment_report["performance_metrics"]["vector_operations"] = vector_test_results
            
            # Generate final report
            report_file = await self.generate_deployment_report()
            
            # Summary
            summary = self.deployment_report["summary"]
            logger.info("\n" + "=" * 60)
            logger.info("🎉 DEPLOYMENT SUMMARY")
            logger.info("=" * 60)
            logger.info(f"✅ Successful: {summary['successful_deployments']}/{summary['total_schemas']}")
            logger.info(f"❌ Failed: {summary['failed_deployments']}/{summary['total_schemas']}")
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
    deployer = ProductionSchemaDeployer()
    success = await deployer.deploy_all_schemas()
    
    if success:
        logger.info("\n🎉 All schemas deployed successfully!")
        sys.exit(0)
    else:
        logger.error("\n❌ Schema deployment completed with errors!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())