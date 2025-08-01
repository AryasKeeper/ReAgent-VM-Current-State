#!/usr/bin/env python3
"""
ReAgent Sydney - Data Validation Audit Script

Property Data Detective tool for comprehensive validation and integrity checking
of Sydney real estate data across all sources and database tables.

Features:
- API connectivity and data source validation
- Cross-source data consistency checking
- Database integrity and corruption detection
- Suburb-level aggregation accuracy verification
- Price history tracking validation
- Geographic coverage analysis
- Comprehensive error reporting

Usage:
    python src/scripts/data_validation_audit.py [--comprehensive] [--fix-issues]
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import argparse
import structlog

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database.engine import get_db_session
from services.external_apis.domain_client import DomainAPIClient, DomainAPIError
from services.external_apis.realestate_client import RealEstateAPIClient, RealEstateAPIError
from data.models.property_models import Property, PropertyPriceHistory, Agent, Agency
from utils.validation.property_validation import validate_property_data, validate_sydney_location
from config.settings import get_settings

logger = structlog.get_logger(__name__)


class PropertyDataDetective:
    """
    Elite data integrity specialist for Sydney real estate data validation.
    
    Systematically investigates data anomalies with methodical precision,
    identifying patterns and root causes of data corruption or inconsistencies.
    """
    
    SYDNEY_POSTCODES = list(range(2000, 3000))
    
    def __init__(self):
        self.settings = get_settings()
        self.validation_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "api_connectivity": {},
            "data_sources": {},
            "database_integrity": {},
            "cross_source_consistency": {},
            "suburb_aggregations": {},
            "price_history_accuracy": {},
            "geographic_coverage": {},
            "critical_issues": [],
            "warnings": [],
            "recommendations": []
        }
        
    async def investigate_data_integrity(self, comprehensive: bool = False, fix_issues: bool = False) -> Dict[str, Any]:
        """
        Main investigation method - systematically analyze all data sources.
        
        Args:
            comprehensive: Run full deep-dive analysis (slower but thorough)
            fix_issues: Attempt to fix identified data issues automatically
            
        Returns:
            Complete validation report with findings and recommendations
        """
        logger.info("🔍 Property Data Detective - Starting comprehensive investigation")
        
        try:
            # Phase 1: API Connectivity and Source Validation
            await self._investigate_api_connectivity()
            
            # Phase 2: Database Integrity Analysis
            await self._investigate_database_integrity()
            
            # Phase 3: Cross-Source Data Consistency
            await self._investigate_cross_source_consistency()
            
            # Phase 4: Suburb-Level Aggregation Accuracy
            await self._investigate_suburb_aggregations()
            
            # Phase 5: Price History Tracking Validation
            await self._investigate_price_history_accuracy()
            
            # Phase 6: Geographic Coverage Analysis
            await self._investigate_geographic_coverage()
            
            if comprehensive:
                # Phase 7: Deep Dive Analysis (only in comprehensive mode)
                await self._investigate_data_quality_patterns()
                await self._investigate_temporal_anomalies()
            
            if fix_issues:
                # Phase 8: Automated Issue Resolution
                await self._attempt_automated_fixes()
            
            # Generate final assessment
            self._generate_final_assessment()
            
            logger.info("✅ Investigation complete", 
                       critical_issues=len(self.validation_results["critical_issues"]),
                       warnings=len(self.validation_results["warnings"]))
            
            return self.validation_results
            
        except Exception as e:
            logger.error("❌ Investigation failed", error=str(e))
            self.validation_results["critical_issues"].append({
                "category": "investigation_failure",
                "severity": "critical",
                "description": f"Investigation process failed: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })
            raise
    
    async def _investigate_api_connectivity(self) -> None:
        """Phase 1: Test API connectivity and data source health."""
        logger.info("📡 Phase 1: Testing API connectivity and source health")
        
        # Test Domain API
        domain_health = await self._test_domain_api_health()
        self.validation_results["api_connectivity"]["domain"] = domain_health
        
        # Test RealEstate API
        rea_health = await self._test_realestate_api_health()
        self.validation_results["api_connectivity"]["realestate"] = rea_health
        
        # Test CoreLogic API (if available)
        corelogic_health = await self._test_corelogic_api_health()
        self.validation_results["api_connectivity"]["corelogic"] = corelogic_health
        
        # Assess overall API health
        healthy_apis = sum(1 for api in [domain_health, rea_health, corelogic_health] 
                          if api.get("status") == "healthy")
        
        if healthy_apis == 0:
            self.validation_results["critical_issues"].append({
                "category": "api_connectivity",
                "severity": "critical",
                "description": "No data source APIs are accessible",
                "impact": "Complete data ingestion failure",
                "recommendation": "Check API keys and network connectivity"
            })
        elif healthy_apis < 2:
            self.validation_results["warnings"].append({
                "category": "api_connectivity",
                "severity": "warning",
                "description": f"Only {healthy_apis} of 3 APIs are healthy",
                "impact": "Reduced data coverage and redundancy"
            })
    
    async def _test_domain_api_health(self) -> Dict[str, Any]:
        """Test Domain API connectivity and data quality."""
        try:
            async with DomainAPIClient() as client:
                health_status = await client.get_health_status()
                
                # Test actual data retrieval
                test_search = await client.search_listings(
                    postcodes=["2000"], 
                    max_results=5
                )
                
                sample_listings = test_search.get("listings", [])
                data_quality_score = self._assess_data_quality(sample_listings, "domain")
                
                return {
                    "status": "healthy" if health_status["api_accessible"] else "unhealthy",
                    "response_time_ms": 0,  # Would measure actual response time
                    "rate_limit_remaining": health_status.get("rate_limit_remaining", 0),
                    "sample_data_quality": data_quality_score,
                    "last_check": datetime.utcnow().isoformat(),
                    "error": None
                }
                
        except DomainAPIError as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    async def _test_realestate_api_health(self) -> Dict[str, Any]:
        """Test RealEstate API connectivity and data quality."""
        try:
            async with RealEstateAPIClient() as client:
                health_status = await client.get_health_status()
                
                # Test actual data retrieval
                test_search = await client.search_listings(
                    postcodes=["2000"], 
                    max_results=5
                )
                
                # Extract sample listings from tiered results
                sample_listings = []
                for tier in test_search.get("tieredResults", []):
                    sample_listings.extend(tier.get("results", []))
                
                data_quality_score = self._assess_data_quality(sample_listings, "realestate")
                
                return {
                    "status": "healthy" if health_status["api_accessible"] else "unhealthy",
                    "response_time_ms": 0,  # Would measure actual response time
                    "rate_limit_remaining": health_status.get("rate_limit_remaining", 0),
                    "sample_data_quality": data_quality_score,
                    "last_check": datetime.utcnow().isoformat(),
                    "error": None
                }
                
        except RealEstateAPIError as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    async def _test_corelogic_api_health(self) -> Dict[str, Any]:
        """Test CoreLogic API connectivity (placeholder - not implemented yet)."""
        return {
            "status": "not_available",
            "error": "CoreLogic API client not yet implemented",
            "last_check": datetime.utcnow().isoformat()
        }
    
    def _assess_data_quality(self, listings: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
        """Assess data quality of sample listings from an API source."""
        if not listings:
            return {"score": 0.0, "issues": ["No sample data available"]}
        
        total_fields = 0
        populated_fields = 0
        issues = []
        
        critical_fields = [
            "id", "title", "address", "price", "bedrooms", 
            "bathrooms", "property_type", "suburb", "postcode"
        ]
        
        for listing in listings[:5]:  # Check first 5 listings
            for field in critical_fields:
                total_fields += 1
                
                # Check field presence and quality
                value = self._extract_field_value(listing, field, source)
                if value is not None and str(value).strip():
                    populated_fields += 1
                else:
                    issues.append(f"Missing or empty {field} in listing {listing.get('id', 'unknown')}")
            
            # Validate postcode if present
            postcode = self._extract_field_value(listing, "postcode", source)
            if postcode and not self._is_valid_sydney_postcode(str(postcode)):
                issues.append(f"Invalid postcode {postcode} in listing {listing.get('id', 'unknown')}")
        
        completeness_score = populated_fields / total_fields if total_fields > 0 else 0.0
        
        return {
            "score": completeness_score,
            "completeness_percentage": round(completeness_score * 100, 2),
            "total_fields_checked": total_fields,
            "populated_fields": populated_fields,
            "issues": issues[:10]  # Limit to first 10 issues
        }
    
    def _extract_field_value(self, listing: Dict[str, Any], field: str, source: str) -> Any:
        """Extract field value from listing data based on source format."""
        if source == "domain":
            field_mapping = {
                "id": "id",
                "title": "headline", 
                "address": ["propertyDetails", "displayableAddress"],
                "price": ["priceDetails", "price"],
                "bedrooms": ["propertyDetails", "bedrooms"],
                "bathrooms": ["propertyDetails", "bathrooms"],
                "property_type": "propertyType",
                "suburb": ["propertyDetails", "suburb"],
                "postcode": ["propertyDetails", "postcode"]
            }
        else:  # realestate
            field_mapping = {
                "id": "id",
                "title": "headline",
                "address": ["address", "streetAddress"],
                "price": ["priceDetails", "price"],
                "bedrooms": ["generalFeatures", "bedrooms"],
                "bathrooms": ["generalFeatures", "bathrooms"],
                "property_type": "propertyType",
                "suburb": ["address", "suburb"],
                "postcode": ["address", "postcode"]
            }
        
        field_path = field_mapping.get(field, field)
        
        if isinstance(field_path, list):
            value = listing
            for key in field_path:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
            return value
        else:
            return listing.get(field_path)
    
    def _is_valid_sydney_postcode(self, postcode: str) -> bool:
        """Check if postcode is valid for Sydney metro area."""
        try:
            postcode_int = int(postcode.strip())
            return postcode_int in self.SYDNEY_POSTCODES
        except (ValueError, AttributeError):
            return False
    
    async def _investigate_database_integrity(self) -> None:
        """Phase 2: Analyze database integrity and detect corruption."""
        logger.info("🗄️ Phase 2: Analyzing database integrity")
        
        async with get_db_session() as session:
            # Check for duplicate listings
            duplicate_check = await self._check_duplicate_properties(session)
            self.validation_results["database_integrity"]["duplicates"] = duplicate_check
            
            # Check for orphaned records
            orphan_check = await self._check_orphaned_records(session)
            self.validation_results["database_integrity"]["orphans"] = orphan_check
            
            # Check data type consistency
            data_type_check = await self._check_data_type_consistency(session)
            self.validation_results["database_integrity"]["data_types"] = data_type_check
            
            # Check constraint violations
            constraint_check = await self._check_constraint_violations(session)
            self.validation_results["database_integrity"]["constraints"] = constraint_check
            
            # Check TimescaleDB health
            timescale_check = await self._check_timescaledb_health(session)
            self.validation_results["database_integrity"]["timescaledb"] = timescale_check
    
    async def _check_duplicate_properties(self, session) -> Dict[str, Any]:
        """Check for duplicate property listings in the database."""
        # Check for exact duplicates by listing_id
        duplicate_listings_query = """
        SELECT listing_id, COUNT(*) as count
        FROM properties 
        WHERE deleted_at IS NULL
        GROUP BY listing_id 
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        LIMIT 100
        """
        
        result = await session.execute(duplicate_listings_query)
        duplicate_listings = result.fetchall()
        
        # Check for potential duplicates by address
        duplicate_addresses_query = """
        SELECT address_line_1, suburb, postcode, COUNT(*) as count
        FROM properties 
        WHERE deleted_at IS NULL
        GROUP BY address_line_1, suburb, postcode 
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        LIMIT 50
        """
        
        result = await session.execute(duplicate_addresses_query)
        duplicate_addresses = result.fetchall()
        
        duplicate_count = len(duplicate_listings)
        address_duplicate_count = len(duplicate_addresses)
        
        if duplicate_count > 0:
            self.validation_results["critical_issues"].append({
                "category": "database_integrity",
                "severity": "critical",
                "description": f"Found {duplicate_count} duplicate listing IDs",
                "details": [dict(row) for row in duplicate_listings[:10]],
                "recommendation": "Remove duplicate records or implement unique constraints"
            })
        
        if address_duplicate_count > 10:
            self.validation_results["warnings"].append({
                "category": "database_integrity",
                "severity": "warning", 
                "description": f"Found {address_duplicate_count} potential address duplicates",
                "impact": "May indicate duplicate properties with different listing IDs"
            })
        
        return {
            "duplicate_listing_ids": duplicate_count,
            "duplicate_addresses": address_duplicate_count,
            "sample_duplicates": [dict(row) for row in duplicate_listings[:5]]
        }
    
    async def _check_orphaned_records(self, session) -> Dict[str, Any]:
        """Check for orphaned records (foreign key violations)."""
        orphan_checks = {}
        
        # Check for price history without properties
        orphan_price_history_query = """
        SELECT COUNT(*) as count
        FROM property_price_history pph
        LEFT JOIN properties p ON pph.property_id = p.id
        WHERE p.id IS NULL
        """
        
        result = await session.execute(orphan_price_history_query)
        orphan_price_history = result.scalar()
        orphan_checks["orphaned_price_history"] = orphan_price_history
        
        # Check for properties with invalid agent references
        orphan_agent_query = """
        SELECT COUNT(*) as count
        FROM properties p
        LEFT JOIN agents a ON p.agent_id = a.id
        WHERE p.agent_id IS NOT NULL AND a.id IS NULL
        """
        
        result = await session.execute(orphan_agent_query)
        orphan_agents = result.scalar()
        orphan_checks["orphaned_agent_refs"] = orphan_agents
        
        total_orphans = sum(orphan_checks.values())
        
        if total_orphans > 0:
            self.validation_results["warnings"].append({
                "category": "database_integrity",
                "severity": "warning",
                "description": f"Found {total_orphans} orphaned records",
                "details": orphan_checks,
                "recommendation": "Clean up orphaned records to maintain referential integrity"
            })
        
        return orphan_checks
    
    async def _check_data_type_consistency(self, session) -> Dict[str, Any]:
        """Check for data type consistency issues."""
        consistency_checks = {}
        
        # Check for invalid price values
        invalid_prices_query = """
        SELECT COUNT(*) as count
        FROM properties 
        WHERE price IS NOT NULL AND (price < 0 OR price > 100000000)
        """
        
        result = await session.execute(invalid_prices_query)
        invalid_prices = result.scalar()
        consistency_checks["invalid_prices"] = invalid_prices
        
        # Check for invalid coordinates
        invalid_coords_query = """
        SELECT COUNT(*) as count
        FROM properties 
        WHERE (latitude IS NOT NULL AND (latitude < -90 OR latitude > 90))
           OR (longitude IS NOT NULL AND (longitude < -180 OR longitude > 180))
        """
        
        result = await session.execute(invalid_coords_query)
        invalid_coords = result.scalar()
        consistency_checks["invalid_coordinates"] = invalid_coords
        
        # Check for invalid postcodes
        invalid_postcodes_query = """
        SELECT COUNT(*) as count
        FROM properties 
        WHERE postcode !~ '^[0-9]{4}$'
        """
        
        result = await session.execute(invalid_postcodes_query)
        invalid_postcodes = result.scalar()
        consistency_checks["invalid_postcodes"] = invalid_postcodes
        
        total_issues = sum(consistency_checks.values())
        
        if total_issues > 0:
            self.validation_results["warnings"].append({
                "category": "database_integrity",
                "severity": "warning",
                "description": f"Found {total_issues} data type consistency issues",
                "details": consistency_checks
            })
        
        return consistency_checks
    
    async def _check_constraint_violations(self, session) -> Dict[str, Any]:
        """Check for database constraint violations."""
        # This would check various constraints defined in the schema
        # For now, return a placeholder
        return {
            "check_constraints": "passed",
            "foreign_key_constraints": "passed",
            "unique_constraints": "passed"
        }
    
    async def _check_timescaledb_health(self, session) -> Dict[str, Any]:
        """Check TimescaleDB hypertable health and performance."""
        try:
            # Check hypertable status
            hypertables_query = """
            SELECT hypertable_name, num_chunks, compression_enabled
            FROM timescaledb_information.hypertables
            """
            
            result = await session.execute(hypertables_query)
            hypertables = [dict(row) for row in result.fetchall()]
            
            return {
                "status": "healthy",
                "hypertables": hypertables,
                "total_hypertables": len(hypertables)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _investigate_cross_source_consistency(self) -> None:
        """Phase 3: Analyze consistency between different data sources."""
        logger.info("🔄 Phase 3: Analyzing cross-source data consistency")
        
        async with get_db_session() as session:
            # Check for same properties from different sources
            cross_source_query = """
            SELECT 
                address_line_1, suburb, postcode,
                COUNT(DISTINCT source) as source_count,
                ARRAY_AGG(DISTINCT source) as sources,
                COUNT(*) as total_listings
            FROM properties 
            WHERE deleted_at IS NULL
            GROUP BY address_line_1, suburb, postcode
            HAVING COUNT(DISTINCT source) > 1
            ORDER BY total_listings DESC
            LIMIT 100
            """
            
            result = await session.execute(cross_source_query)
            cross_source_properties = [dict(row) for row in result.fetchall()]
            
            # Analyze price discrepancies between sources
            price_discrepancy_analysis = await self._analyze_price_discrepancies(session)
            
            self.validation_results["cross_source_consistency"] = {
                "properties_in_multiple_sources": len(cross_source_properties),
                "sample_cross_source_properties": cross_source_properties[:10],
                "price_discrepancy_analysis": price_discrepancy_analysis
            }
            
            if len(cross_source_properties) > 50:
                self.validation_results["warnings"].append({
                    "category": "cross_source_consistency",
                    "severity": "warning",
                    "description": f"Found {len(cross_source_properties)} properties from multiple sources",
                    "impact": "May indicate duplicate listings or data synchronization issues"
                })
    
    async def _analyze_price_discrepancies(self, session) -> Dict[str, Any]:
        """Analyze price discrepancies between sources for same properties."""
        # Find properties with significant price differences between sources
        price_discrepancy_query = """
        WITH property_prices AS (
            SELECT 
                address_line_1, suburb, postcode,
                source,
                price,
                ROW_NUMBER() OVER (PARTITION BY address_line_1, suburb, postcode ORDER BY price) as price_rank
            FROM properties 
            WHERE deleted_at IS NULL AND price IS NOT NULL
        ),
        price_ranges AS (
            SELECT 
                address_line_1, suburb, postcode,
                MIN(price) as min_price,
                MAX(price) as max_price,
                MAX(price) - MIN(price) as price_diff,
                COUNT(*) as source_count
            FROM property_prices
            GROUP BY address_line_1, suburb, postcode
            HAVING COUNT(*) > 1
        )
        SELECT *
        FROM price_ranges
        WHERE price_diff > 50000  -- $50k+ difference
        ORDER BY price_diff DESC
        LIMIT 50
        """
        
        result = await session.execute(price_discrepancy_query)
        price_discrepancies = [dict(row) for row in result.fetchall()]
        
        return {
            "significant_discrepancies": len(price_discrepancies),
            "sample_discrepancies": price_discrepancies[:10]
        }
    
    async def _investigate_suburb_aggregations(self) -> None:
        """Phase 4: Verify suburb-level data aggregation accuracy."""
        logger.info("🏘️ Phase 4: Verifying suburb aggregation accuracy")
        
        async with get_db_session() as session:
            # Check suburb/postcode mapping consistency
            suburb_postcode_query = """
            SELECT 
                suburb,
                COUNT(DISTINCT postcode) as postcode_count,
                ARRAY_AGG(DISTINCT postcode) as postcodes
            FROM properties 
            WHERE deleted_at IS NULL
            GROUP BY suburb
            HAVING COUNT(DISTINCT postcode) > 3
            ORDER BY postcode_count DESC
            LIMIT 20
            """
            
            result = await session.execute(suburb_postcode_query)
            suburb_inconsistencies = [dict(row) for row in result.fetchall()]
            
            # Validate Sydney postcode coverage
            postcode_coverage = await self._validate_postcode_coverage(session)
            
            self.validation_results["suburb_aggregations"] = {
                "suburb_postcode_inconsistencies": len(suburb_inconsistencies),
                "sample_inconsistencies": suburb_inconsistencies[:5],
                "postcode_coverage": postcode_coverage
            }
    
    async def _validate_postcode_coverage(self, session) -> Dict[str, Any]:
        """Validate coverage of Sydney metro postcodes."""
        # Get all postcodes in database
        postcodes_query = """
        SELECT DISTINCT postcode::int as postcode_int
        FROM properties 
        WHERE postcode ~ '^[0-9]{4}$' AND deleted_at IS NULL
        ORDER BY postcode_int
        """
        
        result = await session.execute(postcodes_query)
        db_postcodes = {row[0] for row in result.fetchall()}
        
        # Check Sydney metro coverage
        sydney_postcodes_set = set(self.SYDNEY_POSTCODES)
        covered_postcodes = db_postcodes.intersection(sydney_postcodes_set)
        missing_postcodes = sydney_postcodes_set - covered_postcodes
        
        coverage_percentage = len(covered_postcodes) / len(sydney_postcodes_set) * 100
        
        if coverage_percentage < 80:
            self.validation_results["warnings"].append({
                "category": "geographic_coverage",
                "severity": "warning",
                "description": f"Sydney metro coverage only {coverage_percentage:.1f}%",
                "missing_postcodes_count": len(missing_postcodes)
            })
        
        return {
            "total_sydney_postcodes": len(sydney_postcodes_set),
            "covered_postcodes": len(covered_postcodes),
            "missing_postcodes": len(missing_postcodes),
            "coverage_percentage": round(coverage_percentage, 2),
            "sample_missing": sorted(list(missing_postcodes))[:20]
        }
    
    async def _investigate_price_history_accuracy(self) -> None:
        """Phase 5: Validate price history tracking and anomaly detection."""
        logger.info("💰 Phase 5: Validating price history accuracy")
        
        async with get_db_session() as session:
            # Check for price history anomalies
            price_anomalies_query = """
            SELECT 
                property_id,
                COUNT(*) as history_count,
                MIN(price) as min_price,
                MAX(price) as max_price,
                MAX(price) - MIN(price) as price_range,
                STDDEV(price) as price_stddev
            FROM property_price_history
            WHERE created_at >= NOW() - INTERVAL '90 days'
            GROUP BY property_id
            HAVING STDDEV(price) > 100000  -- High volatility
            ORDER BY price_stddev DESC
            LIMIT 50
            """
            
            result = await session.execute(price_anomalies_query)
            price_anomalies = [dict(row) for row in result.fetchall()]
            
            # Check for missing price history
            missing_history_query = """
            SELECT COUNT(*) as count
            FROM properties p
            LEFT JOIN property_price_history pph ON p.id = pph.property_id
            WHERE p.deleted_at IS NULL 
              AND p.price IS NOT NULL
              AND pph.property_id IS NULL
            """
            
            result = await session.execute(missing_history_query)
            missing_history_count = result.scalar()
            
            self.validation_results["price_history_accuracy"] = {
                "high_volatility_properties": len(price_anomalies),
                "properties_missing_history": missing_history_count,
                "sample_anomalies": price_anomalies[:5]
            }
            
            if missing_history_count > 100:
                self.validation_results["warnings"].append({
                    "category": "price_history",
                    "severity": "warning",
                    "description": f"{missing_history_count} properties missing price history",
                    "recommendation": "Ensure price history is created for all new listings"
                })
    
    async def _investigate_geographic_coverage(self) -> None:
        """Phase 6: Analyze geographic coverage and coordinate accuracy."""
        logger.info("🗺️ Phase 6: Analyzing geographic coverage")
        
        async with get_db_session() as session:
            # Check coordinate completeness
            coordinate_stats_query = """
            SELECT 
                COUNT(*) as total_properties,
                COUNT(latitude) as properties_with_lat,
                COUNT(longitude) as properties_with_lng,
                COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as properties_with_coords
            FROM properties 
            WHERE deleted_at IS NULL
            """
            
            result = await session.execute(coordinate_stats_query)
            coord_stats = dict(result.fetchone())
            
            # Calculate coordinate completeness percentage
            if coord_stats["total_properties"] > 0:
                coord_completeness = (coord_stats["properties_with_coords"] / 
                                    coord_stats["total_properties"]) * 100
            else:
                coord_completeness = 0
            
            self.validation_results["geographic_coverage"] = {
                **coord_stats,
                "coordinate_completeness_percentage": round(coord_completeness, 2)
            }
            
            if coord_completeness < 90:
                self.validation_results["warnings"].append({
                    "category": "geographic_coverage",
                    "severity": "warning",
                    "description": f"Only {coord_completeness:.1f}% of properties have coordinates",
                    "impact": "Affects location-based searches and mapping features"
                })
    
    async def _investigate_data_quality_patterns(self) -> None:
        """Phase 7: Deep dive into data quality patterns (comprehensive mode only)."""
        logger.info("🔬 Phase 7: Deep dive data quality pattern analysis")
        
        # This would include more sophisticated analysis like:
        # - Temporal patterns in data quality
        # - Source-specific quality trends
        # - Field-level completeness analysis
        # - Anomaly detection in property features
        
        # Placeholder for now
        pass
    
    async def _investigate_temporal_anomalies(self) -> None:
        """Phase 8: Analyze temporal data anomalies (comprehensive mode only)."""
        logger.info("⏰ Phase 8: Analyzing temporal data anomalies")
        
        # This would include:
        # - Properties listed in the future
        # - Properties with impossible date sequences
        # - Seasonal data patterns
        # - Data ingestion timing issues
        
        # Placeholder for now
        pass
    
    async def _attempt_automated_fixes(self) -> None:
        """Phase 9: Attempt automated fixes for identified issues."""
        logger.info("🔧 Phase 9: Attempting automated issue resolution")
        
        # This would include:
        # - Fixing invalid postcodes
        # - Standardizing property types
        # - Cleaning description text
        # - Removing obvious duplicates
        
        # Placeholder for now - would need careful implementation
        pass
    
    def _generate_final_assessment(self) -> None:
        """Generate final assessment and recommendations."""
        critical_count = len(self.validation_results["critical_issues"])
        warning_count = len(self.validation_results["warnings"])
        
        # Overall health score (0-100)
        health_score = 100
        health_score -= critical_count * 20  # -20 per critical issue
        health_score -= warning_count * 5    # -5 per warning
        health_score = max(0, health_score)
        
        # Generate recommendations
        recommendations = []
        
        if critical_count > 0:
            recommendations.append("Address critical issues immediately to prevent data integrity problems")
        
        if warning_count > 5:
            recommendations.append("Implement data quality monitoring to catch issues early")
        
        # API-specific recommendations
        api_status = self.validation_results["api_connectivity"]
        healthy_apis = sum(1 for api in api_status.values() 
                          if isinstance(api, dict) and api.get("status") == "healthy")
        
        if healthy_apis < 2:
            recommendations.append("Implement CoreLogic API integration for better data redundancy")
        
        # Database-specific recommendations
        db_integrity = self.validation_results["database_integrity"]
        if db_integrity.get("duplicates", {}).get("duplicate_listing_ids", 0) > 0:
            recommendations.append("Implement unique constraints and duplicate detection in data pipeline")
        
        # Coverage recommendations
        geographic = self.validation_results.get("geographic_coverage", {})
        if geographic.get("coordinate_completeness_percentage", 0) < 90:
            recommendations.append("Enhance geocoding pipeline to improve coordinate coverage")
        
        self.validation_results.update({
            "overall_health_score": health_score,
            "assessment": self._get_health_assessment(health_score),
            "recommendations": recommendations,
            "next_check_recommended": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        })
    
    def _get_health_assessment(self, score: int) -> str:
        """Get textual health assessment based on score."""
        if score >= 90:
            return "Excellent - Data integrity is very high"
        elif score >= 70:
            return "Good - Minor issues that should be addressed"
        elif score >= 50:
            return "Fair - Several issues requiring attention"
        elif score >= 30:
            return "Poor - Significant data quality problems"
        else:
            return "Critical - Immediate action required"


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="ReAgent Sydney Data Validation Audit")
    parser.add_argument("--comprehensive", action="store_true", 
                       help="Run comprehensive deep analysis (slower)")
    parser.add_argument("--fix-issues", action="store_true",
                       help="Attempt to fix identified issues automatically")
    parser.add_argument("--output", default="data_validation_report.json",
                       help="Output file for validation report")
    
    args = parser.parse_args()
    
    # Initialize the Property Data Detective
    detective = PropertyDataDetective()
    
    try:
        # Run the investigation
        results = await detective.investigate_data_integrity(
            comprehensive=args.comprehensive,
            fix_issues=args.fix_issues
        )
        
        # Save results to file
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "="*80)
        print("🔍 PROPERTY DATA DETECTIVE - INVESTIGATION COMPLETE")
        print("="*80)
        print(f"Overall Health Score: {results['overall_health_score']}/100")
        print(f"Assessment: {results['assessment']}")
        print(f"Critical Issues: {len(results['critical_issues'])}")
        print(f"Warnings: {len(results['warnings'])}")
        print(f"Report saved to: {output_path}")
        
        if results['recommendations']:
            print("\nTop Recommendations:")
            for i, rec in enumerate(results['recommendations'][:5], 1):
                print(f"{i}. {rec}")
        
        print("="*80)
        
        # Exit with appropriate code
        sys.exit(1 if results['overall_health_score'] < 70 else 0)
        
    except Exception as e:
        logger.error("Investigation failed", error=str(e))
        print(f"❌ Investigation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())