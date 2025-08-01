#!/usr/bin/env python3
"""
Weaviate Data Investigation and Debugging
Property Data Detective Investigation

Debug search functionality and investigate data ingestion issues.
"""

import asyncio
import json
from typing import Dict, Any
import structlog

from src.core.vector_db.client import WeaviateClient
from src.config.settings import Settings

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class WeaviateDataInvestigator:
    """Investigate Weaviate data ingestion and search issues."""
    
    def __init__(self):
        self.settings = Settings()
        self.settings.weaviate.url = "http://localhost:8080"
        self.settings.weaviate.api_key = None
        self.client: WeaviateClient = None
    
    async def investigate_data_issues(self) -> Dict[str, Any]:
        """Comprehensive investigation of data ingestion and search issues."""
        logger.info("🔍 Starting comprehensive Weaviate data investigation")
        
        investigation_results = {
            "connection_status": False,
            "schema_analysis": {},
            "object_counts": {},
            "sample_data_inspection": {},
            "search_diagnostics": {},
            "issues_identified": [],
            "recommendations": []
        }
        
        try:
            # Connect to Weaviate
            self.client = WeaviateClient(self.settings)
            await self.client.connect()
            investigation_results["connection_status"] = True
            logger.info("✅ Connected to Weaviate successfully")
            
            # Investigate schemas
            await self._investigate_schemas(investigation_results)
            
            # Check object counts
            await self._check_object_counts(investigation_results)
            
            # Inspect sample data
            await self._inspect_sample_data(investigation_results)
            
            # Debug search functionality
            await self._debug_search_functionality(investigation_results)
            
            # Analyze findings and provide recommendations
            self._analyze_findings(investigation_results)
            
        except Exception as e:
            error_msg = f"Investigation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            investigation_results["issues_identified"].append(error_msg)
        
        finally:
            if self.client:
                await self.client.disconnect()
        
        return investigation_results
    
    async def _investigate_schemas(self, results: Dict[str, Any]):
        """Investigate Weaviate schema configuration."""
        logger.info("📋 Investigating Weaviate schemas")
        
        try:
            # Get current schema
            schema = self.client._client.schema.get()
            classes = schema.get("classes", [])
            
            schema_analysis = {
                "total_classes": len(classes),
                "class_names": [cls["class"] for cls in classes],
                "class_details": {}
            }
            
            for cls in classes:
                class_name = cls["class"]
                schema_analysis["class_details"][class_name] = {
                    "property_count": len(cls.get("properties", [])),
                    "vectorizer": cls.get("vectorizer", "none"),
                    "vector_index_config": cls.get("vectorIndexConfig", {}),
                    "inverted_index_config": cls.get("invertedIndexConfig", {})
                }
            
            results["schema_analysis"] = schema_analysis
            logger.info(f"✅ Found {len(classes)} schema classes: {schema_analysis['class_names']}")
            
        except Exception as e:
            error_msg = f"Schema investigation failed: {str(e)}"
            logger.error(error_msg)
            results["issues_identified"].append(error_msg)
    
    async def _check_object_counts(self, results: Dict[str, Any]):
        """Check object counts for all classes."""
        logger.info("📊 Checking object counts")
        
        try:
            object_counts = {}
            
            # Check standard classes
            for class_name in ["Property", "BuyerProfile", "PropertyMatch"]:
                try:
                    count = await self.client.get_object_count(class_name)
                    object_counts[class_name] = count
                    logger.info(f"📈 {class_name}: {count} objects")
                except Exception as e:
                    object_counts[class_name] = f"Error: {str(e)}"
                    logger.error(f"Failed to get count for {class_name}: {str(e)}")
            
            results["object_counts"] = object_counts
            
        except Exception as e:
            error_msg = f"Object count check failed: {str(e)}"
            logger.error(error_msg)
            results["issues_identified"].append(error_msg)
    
    async def _inspect_sample_data(self, results: Dict[str, Any]):
        """Inspect sample data from each class."""
        logger.info("🔬 Inspecting sample data")
        
        try:
            sample_data = {}
            
            # Inspect Property data
            try:
                property_query = self.client._client.query.get(
                    "Property", ["listing_id", "title", "suburb", "price", "bedrooms"]
                ).with_limit(3).do()
                
                property_results = property_query.get("data", {}).get("Get", {}).get("Property", [])
                sample_data["Property"] = {
                    "count": len(property_results),
                    "samples": property_results
                }
                logger.info(f"🏠 Property samples: {len(property_results)} found")
                
                # Debug: Print first property for detailed inspection
                if property_results:
                    logger.info(f"First property sample: {json.dumps(property_results[0], indent=2)}")
                
            except Exception as e:
                sample_data["Property"] = {"error": str(e)}
                logger.error(f"Property inspection failed: {str(e)}")
            
            # Inspect BuyerProfile data
            try:
                buyer_query = self.client._client.query.get(
                    "BuyerProfile", ["buyer_id", "full_name", "buyer_type", "max_price"]
                ).with_limit(3).do()
                
                buyer_results = buyer_query.get("data", {}).get("Get", {}).get("BuyerProfile", [])
                sample_data["BuyerProfile"] = {
                    "count": len(buyer_results),
                    "samples": buyer_results
                }
                logger.info(f"👥 BuyerProfile samples: {len(buyer_results)} found")
                
                if buyer_results:
                    logger.info(f"First buyer sample: {json.dumps(buyer_results[0], indent=2)}")
                
            except Exception as e:
                sample_data["BuyerProfile"] = {"error": str(e)}
                logger.error(f"BuyerProfile inspection failed: {str(e)}")
            
            # Inspect PropertyMatch data
            try:
                match_query = self.client._client.query.get(
                    "PropertyMatch", ["match_id", "buyer_id", "property_listing_id", "match_score"]
                ).with_limit(3).do()
                
                match_results = match_query.get("data", {}).get("Get", {}).get("PropertyMatch", [])
                sample_data["PropertyMatch"] = {
                    "count": len(match_results),
                    "samples": match_results
                }
                logger.info(f"🎯 PropertyMatch samples: {len(match_results)} found")
                
                if match_results:
                    logger.info(f"First match sample: {json.dumps(match_results[0], indent=2)}")
                
            except Exception as e:
                sample_data["PropertyMatch"] = {"error": str(e)}
                logger.error(f"PropertyMatch inspection failed: {str(e)}")
            
            results["sample_data_inspection"] = sample_data
            
        except Exception as e:
            error_msg = f"Sample data inspection failed: {str(e)}"
            logger.error(error_msg)
            results["issues_identified"].append(error_msg)
    
    async def _debug_search_functionality(self, results: Dict[str, Any]):
        """Debug search functionality with detailed diagnostics."""
        logger.info("🔍 Debugging search functionality")
        
        try:
            search_diagnostics = {}
            
            # Test 1: Basic property retrieval (no filters)
            try:
                basic_query = self.client._client.query.get(
                    "Property", ["title", "suburb"]
                ).with_limit(5).do()
                
                basic_results = basic_query.get("data", {}).get("Get", {}).get("Property", [])
                search_diagnostics["basic_property_query"] = {
                    "success": True,
                    "count": len(basic_results),
                    "results": basic_results
                }
                logger.info(f"✅ Basic property query returned {len(basic_results)} results")
                
            except Exception as e:
                search_diagnostics["basic_property_query"] = {"success": False, "error": str(e)}
                logger.error(f"Basic property query failed: {str(e)}")
            
            # Test 2: Property filtering by suburb (specific test)
            try:
                # First, let's see what suburbs are actually in the data
                suburb_query = self.client._client.query.get(
                    "Property", ["suburb"]
                ).do()
                
                suburb_results = suburb_query.get("data", {}).get("Get", {}).get("Property", [])
                available_suburbs = [r.get("suburb") for r in suburb_results if r.get("suburb")]
                unique_suburbs = list(set(available_suburbs))
                
                search_diagnostics["available_suburbs"] = unique_suburbs
                logger.info(f"📍 Available suburbs in data: {unique_suburbs}")
                
                # Now test filtering by the first available suburb
                if unique_suburbs:
                    test_suburb = unique_suburbs[0]
                    filtered_query = self.client._client.query.get(
                        "Property", ["title", "suburb", "price"]
                    ).with_where({
                        "path": ["suburb"],
                        "operator": "Equal",
                        "valueString": test_suburb
                    }).do()
                    
                    filtered_results = filtered_query.get("data", {}).get("Get", {}).get("Property", [])
                    search_diagnostics["suburb_filtering"] = {
                        "success": True,
                        "test_suburb": test_suburb,
                        "count": len(filtered_results),
                        "results": filtered_results
                    }
                    logger.info(f"✅ Suburb filtering for '{test_suburb}' returned {len(filtered_results)} results")
                else:
                    search_diagnostics["suburb_filtering"] = {"success": False, "error": "No suburbs found in data"}
                
            except Exception as e:
                search_diagnostics["suburb_filtering"] = {"success": False, "error": str(e)}
                logger.error(f"Suburb filtering test failed: {str(e)}")
            
            # Test 3: Buyer profile filtering
            try:
                buyer_type_query = self.client._client.query.get(
                    "BuyerProfile", ["buyer_type", "full_name"]
                ).do()
                
                buyer_type_results = buyer_type_query.get("data", {}).get("Get", {}).get("BuyerProfile", [])
                available_types = [r.get("buyer_type") for r in buyer_type_results if r.get("buyer_type")]
                unique_types = list(set(available_types))
                
                search_diagnostics["available_buyer_types"] = unique_types
                logger.info(f"👤 Available buyer types: {unique_types}")
                
                if unique_types:
                    test_type = unique_types[0]
                    type_filtered_query = self.client._client.query.get(
                        "BuyerProfile", ["full_name", "buyer_type", "max_price"]
                    ).with_where({
                        "path": ["buyer_type"],
                        "operator": "Equal", 
                        "valueString": test_type
                    }).do()
                    
                    type_filtered_results = type_filtered_query.get("data", {}).get("Get", {}).get("BuyerProfile", [])
                    search_diagnostics["buyer_type_filtering"] = {
                        "success": True,
                        "test_type": test_type,
                        "count": len(type_filtered_results),
                        "results": type_filtered_results
                    }
                    logger.info(f"✅ Buyer type filtering for '{test_type}' returned {len(type_filtered_results)} results")
                
            except Exception as e:
                search_diagnostics["buyer_type_filtering"] = {"success": False, "error": str(e)}
                logger.error(f"Buyer type filtering test failed: {str(e)}")
            
            # Test 4: Numeric filtering (price ranges)
            try:
                price_query = self.client._client.query.get(
                    "Property", ["price", "suburb"]
                ).with_where({
                    "path": ["price"],
                    "operator": "GreaterThan",
                    "valueNumber": 1000000
                }).do()
                
                price_results = price_query.get("data", {}).get("Get", {}).get("Property", [])
                search_diagnostics["price_filtering"] = {
                    "success": True,
                    "count": len(price_results),
                    "results": price_results[:3]  # Only first 3 for brevity
                }
                logger.info(f"✅ Price filtering (>$1M) returned {len(price_results)} results")
                
            except Exception as e:
                search_diagnostics["price_filtering"] = {"success": False, "error": str(e)}
                logger.error(f"Price filtering test failed: {str(e)}")
            
            results["search_diagnostics"] = search_diagnostics
            
        except Exception as e:
            error_msg = f"Search functionality debugging failed: {str(e)}"
            logger.error(error_msg)
            results["issues_identified"].append(error_msg)
    
    def _analyze_findings(self, results: Dict[str, Any]):
        """Analyze investigation findings and provide recommendations."""
        logger.info("🎯 Analyzing findings and generating recommendations")
        
        issues = results["issues_identified"]
        recommendations = []
        
        # Analyze object counts
        object_counts = results.get("object_counts", {})
        total_objects = sum(count for count in object_counts.values() if isinstance(count, int))
        
        if total_objects == 0:
            issues.append("No objects found in any Weaviate class")
            recommendations.append("Verify data ingestion process - objects may not have been persisted")
        elif total_objects < 20:
            issues.append(f"Low object count detected: {total_objects} total objects")
            recommendations.append("Check if all sample data was successfully ingested")
        
        # Analyze search diagnostics
        search_diagnostics = results.get("search_diagnostics", {})
        
        basic_query_success = search_diagnostics.get("basic_property_query", {}).get("success", False)
        if not basic_query_success:
            issues.append("Basic property queries are failing")
            recommendations.append("Check Weaviate schema and object structure")
        
        suburb_filtering_success = search_diagnostics.get("suburb_filtering", {}).get("success", False)
        if not suburb_filtering_success:
            issues.append("Suburb-based filtering is not working")
            recommendations.append("Verify suburb field indexing and data format")
        
        # Analyze data consistency
        sample_data = results.get("sample_data_inspection", {})
        property_samples = sample_data.get("Property", {}).get("samples", [])
        
        if not property_samples:
            issues.append("No property samples could be retrieved")
            recommendations.append("Check if Property objects are being created with correct schema")
        
        # Schema analysis
        schema_analysis = results.get("schema_analysis", {})
        class_names = schema_analysis.get("class_names", [])
        
        expected_classes = ["Property", "BuyerProfile", "PropertyMatch"]
        missing_classes = [cls for cls in expected_classes if cls not in class_names]
        
        if missing_classes:
            issues.append(f"Missing schema classes: {missing_classes}")
            recommendations.append("Ensure all required schemas are deployed before data ingestion")
        
        # Generate final recommendations
        if not issues:
            recommendations.append("✅ Data pipeline appears to be functioning correctly")
            recommendations.append("Consider testing with larger datasets for production readiness")
        else:
            recommendations.append("🔧 Address identified issues before proceeding to production")
            recommendations.append("Re-run validation tests after implementing fixes")
        
        results["recommendations"] = recommendations


async def main():
    """Run comprehensive Weaviate data investigation."""
    print("🔍 === ReAgent Sydney - Weaviate Data Investigation ===")
    print("Investigating data ingestion and search functionality issues...")
    print()
    
    investigator = WeaviateDataInvestigator()
    results = await investigator.investigate_data_issues()
    
    print("\n📊 === INVESTIGATION RESULTS ===")
    print(f"Connection Status: {'✅ CONNECTED' if results['connection_status'] else '❌ FAILED'}")
    
    # Schema Analysis
    schema_analysis = results.get("schema_analysis", {})
    print(f"\n📋 Schema Analysis:")
    print(f"  Total Classes: {schema_analysis.get('total_classes', 0)}")
    print(f"  Class Names: {schema_analysis.get('class_names', [])}")
    
    # Object Counts
    object_counts = results.get("object_counts", {})
    print(f"\n📈 Object Counts:")
    for class_name, count in object_counts.items():
        print(f"  {class_name}: {count}")
    
    # Sample Data Inspection
    sample_data = results.get("sample_data_inspection", {})
    print(f"\n🔬 Sample Data Inspection:")
    for class_name, data in sample_data.items():
        if "error" in data:
            print(f"  {class_name}: ❌ Error - {data['error']}")
        else:
            print(f"  {class_name}: ✅ {data.get('count', 0)} samples retrieved")
    
    # Search Diagnostics
    search_diagnostics = results.get("search_diagnostics", {})
    print(f"\n🔍 Search Diagnostics:")
    
    for test_name, test_result in search_diagnostics.items():
        if isinstance(test_result, dict):
            success = test_result.get("success", False)
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {test_name}: {status}")
            
            if "count" in test_result:
                print(f"    Results: {test_result['count']} found")
            if "error" in test_result:
                print(f"    Error: {test_result['error']}")
        else:
            print(f"  {test_name}: {test_result}")
    
    # Issues and Recommendations
    if results.get("issues_identified"):
        print(f"\n❌ === ISSUES IDENTIFIED ===")
        for issue in results["issues_identified"]:
            print(f"  • {issue}")
    
    if results.get("recommendations"):
        print(f"\n💡 === RECOMMENDATIONS ===")
        for recommendation in results["recommendations"]:
            print(f"  • {recommendation}")
    
    # Overall Assessment
    has_critical_issues = len(results.get("issues_identified", [])) > 0
    print(f"\n🎯 === OVERALL ASSESSMENT ===")
    if has_critical_issues:
        print("❌ CRITICAL ISSUES DETECTED - Requires Investigation")
    else:
        print("✅ DATA PIPELINE FUNCTIONING - Ready for Production")
    
    return not has_critical_issues


if __name__ == "__main__":
    asyncio.run(main())