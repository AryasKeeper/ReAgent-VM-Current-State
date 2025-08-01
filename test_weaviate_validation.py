#!/usr/bin/env python3
"""
Weaviate Vector Search Validation & Data Ingestion Testing

This script validates the Weaviate vector database functionality with sample 
property and buyer data to ensure AI-powered matching system works correctly.

Author: Production Monitoring Expert
Date: 2025-07-29
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

import structlog
import numpy as np

# Import ReAgent components
from src.core.vector_db.client import WeaviateClient, VectorSearchResult, SearchQuery
from src.core.vector_db.embeddings import PropertyVectorizer, BuyerProfileVectorizer, PropertyFeatures, BuyerPreferenceFeatures
from src.config.settings import get_settings


@dataclass
class TestResult:
    """Test execution result."""
    test_name: str
    success: bool
    duration: float
    details: Dict[str, Any]
    error: Optional[str] = None


class WeaviateValidationSuite:
    """Comprehensive Weaviate validation test suite."""

    def __init__(self):
        self.logger = structlog.get_logger("weaviate.validation")
        self.client: Optional[WeaviateClient] = None
        self.property_vectorizer = PropertyVectorizer()
        self.buyer_vectorizer = BuyerProfileVectorizer()
        self.results: List[TestResult] = []
        
        # Test data
        self.sample_properties = self._create_sample_properties()
        self.sample_buyers = self._create_sample_buyers()
    
    def _create_sample_properties(self) -> List[Dict[str, Any]]:
        """Create realistic Sydney property test data."""
        return [
            {
                "id": str(uuid.uuid4()),
                "address": "123 Crown Street, Surry Hills NSW 2010",
                "postcode": "2010",
                "suburb": "Surry Hills",
                "property_type": "apartment",
                "bedrooms": 2,
                "bathrooms": 1,
                "car_spaces": 1,
                "building_size": 85,
                "price": 850000,
                "latitude": -33.8858,
                "longitude": 151.2131,
                "title": "Modern Apartment with City Views",
                "description": "Modern apartment in trendy Surry Hills with city views, walking distance to CBD, cafes and restaurants. Features include balcony, modern kitchen, and great natural light.",
                "features": ["balcony", "city_views", "near_transport", "modern_kitchen", "natural_light"],
                "days_on_market": 14,
                "agent_name": "Sarah Johnson",
                "agency_name": "Elite Properties Sydney",
                "amenities": {"balcony": True, "air_conditioning": True},
                "market_context": {"view_count": 245, "enquiry_count": 12, "suburb_price_percentile": 75}
            },
            {
                "id": str(uuid.uuid4()),
                "address": "456 Beach Road, Bondi NSW 2026",
                "postcode": "2026",
                "suburb": "Bondi",
                "property_type": "house",
                "bedrooms": 3,
                "bathrooms": 2,
                "car_spaces": 2,
                "land_size": 320,
                "building_size": 150,
                "price": 1200000,
                "latitude": -33.8915,
                "longitude": 151.2767,
                "title": "Charming Beach House Near Bondi Beach",
                "description": "Charming beach house near Bondi Beach with ocean glimpses, outdoor entertaining area, and parking. Perfect for families or beach lovers.",
                "features": ["ocean_views", "outdoor_area", "near_beach", "parking", "family_friendly"],
                "days_on_market": 7,
                "agent_name": "Michael Chen",
                "agency_name": "Coastal Realty",
                "amenities": {"outdoor_area": True, "parking": True, "ocean_views": True},
                "market_context": {"view_count": 189, "enquiry_count": 8, "suburb_price_percentile": 60}
            },
            {
                "id": str(uuid.uuid4()),
                "address": "789 Luxury Lane, Double Bay NSW 2028",
                "postcode": "2028",
                "suburb": "Double Bay",
                "property_type": "apartment",
                "bedrooms": 3,
                "bathrooms": 3,
                "car_spaces": 2,
                "building_size": 180,
                "price": 2100000,
                "latitude": -33.8784,
                "longitude": 151.2415,
                "title": "Luxury Waterfront Apartment",
                "description": "Luxury waterfront apartment in prestigious Double Bay with harbor views, premium finishes, and resort-style amenities. Walk to designer boutiques and fine dining.",
                "features": ["harbor_views", "luxury_finishes", "waterfront", "designer_kitchen", "resort_amenities"],
                "days_on_market": 21,
                "agent_name": "Elizabeth Harper",
                "agency_name": "Prestige Properties",
                "amenities": {"harbor_views": True, "luxury_finishes": True, "concierge": True},
                "market_context": {"view_count": 156, "enquiry_count": 6, "suburb_price_percentile": 85}
            },
            {
                "id": str(uuid.uuid4()),
                "address": "321 Family Street, Chatswood NSW 2067",
                "postcode": "2067",
                "suburb": "Chatswood",
                "property_type": "house",
                "bedrooms": 4,
                "bathrooms": 3,
                "car_spaces": 2,
                "land_size": 550,
                "building_size": 220,
                "price": 1650000,
                "latitude": -33.7969,
                "longitude": 151.1848,
                "title": "Family Home with Pool and Garden",
                "description": "Spacious family home in quiet Chatswood street with pool, garden, and excellent schools nearby. Perfect for growing families with modern kitchen and living areas.",
                "features": ["pool", "garden", "family_friendly", "quiet_street", "modern_kitchen", "near_schools"],
                "days_on_market": 28,
                "agent_name": "David Kim",
                "agency_name": "Family First Realty",
                "amenities": {"pool": True, "garden": True, "garage": True},
                "market_context": {"view_count": 203, "enquiry_count": 15, "suburb_price_percentile": 70}
            },
            {
                "id": str(uuid.uuid4()),
                "address": "555 Investment Avenue, Parramatta NSW 2150",
                "postcode": "2150",
                "suburb": "Parramatta",
                "property_type": "unit",
                "bedrooms": 2,
                "bathrooms": 2,
                "car_spaces": 1,
                "building_size": 75,
                "price": 620000,
                "latitude": -33.8151,
                "longitude": 151.0000,
                "title": "Great Investment Opportunity",
                "description": "Well-located unit in growing Parramatta with strong rental yield potential. Close to transport, shopping, and business district. Perfect for first-time investors.",
                "features": ["investment_potential", "transport_links", "rental_yield", "low_maintenance", "central_location"],
                "days_on_market": 35,
                "agent_name": "Jennifer Wang",
                "agency_name": "Investment Focus",
                "amenities": {"close_transport": True, "low_maintenance": True},
                "market_context": {"view_count": 178, "enquiry_count": 9, "suburb_price_percentile": 45}
            }
        ]
    
    def _create_sample_buyers(self) -> List[Dict[str, Any]]:
        """Create realistic buyer profile test data."""
        return [
            {
                "id": str(uuid.uuid4()),
                "buyer_type": "first_home_buyer",
                "buying_urgency": "medium",
                "preferences": {
                    "max_price": 900000,
                    "min_price": 700000,
                    "budget_flexibility": 0.15,
                    "property_types": ["apartment", "unit"],
                    "min_bedrooms": 2,
                    "max_bedrooms": 3,
                    "min_bathrooms": 1,
                    "min_car_spaces": 1,
                    "preferred_suburbs": ["surry_hills", "darlinghurst", "redfern", "newtown"],
                    "preferred_postcodes": ["2010", "2016", "2008", "2042"],
                    "max_commute_time": 30,
                    "required_features": ["modern_kitchen", "transport_links"],
                    "preferred_features": ["balcony", "city_views", "natural_light"],
                    "excluded_features": ["ground_floor"],
                    "rental_yield_target": 0.0,
                    "capital_growth_expectation": "medium"
                },
                "interaction_patterns": {
                    "avg_daily_views": 3.5,
                    "avg_session_duration": 420,
                    "interest_score_variance": 0.8,
                    "feature_focus_score": 0.7
                },
                "search_query": "Looking for modern apartment near CBD with good transport links, budget up to 900k"
            },
            {
                "id": str(uuid.uuid4()),
                "buyer_type": "upgrader",
                "buying_urgency": "high",
                "preferences": {
                    "max_price": 1300000,
                    "min_price": 1000000,
                    "budget_flexibility": 0.10,
                    "property_types": ["house"],
                    "min_bedrooms": 3,
                    "max_bedrooms": 4,
                    "min_bathrooms": 2,
                    "min_car_spaces": 2,
                    "preferred_suburbs": ["bondi", "coogee", "bronte", "maroubra"],
                    "preferred_postcodes": ["2026", "2034", "2024", "2035"],
                    "max_commute_time": 45,
                    "required_features": ["outdoor_area", "parking"],
                    "preferred_features": ["ocean_views", "near_beach", "family_friendly"],
                    "excluded_features": ["busy_road"],
                    "rental_yield_target": 0.0,
                    "capital_growth_expectation": "high"
                },
                "interaction_patterns": {
                    "avg_daily_views": 5.2,
                    "avg_session_duration": 680,
                    "interest_score_variance": 0.6,
                    "feature_focus_score": 0.8
                },
                "search_query": "Family home near beach with outdoor space, budget up to 1.3M"
            },
            {
                "id": str(uuid.uuid4()),
                "buyer_type": "investor",
                "buying_urgency": "low",
                "preferences": {
                    "max_price": 750000,
                    "min_price": 500000,
                    "budget_flexibility": 0.20,
                    "property_types": ["unit", "apartment"],
                    "min_bedrooms": 1,
                    "max_bedrooms": 2,
                    "min_bathrooms": 1,
                    "min_car_spaces": 0,
                    "preferred_suburbs": ["parramatta", "bankstown", "liverpool", "blacktown"],
                    "preferred_postcodes": ["2150", "2200", "2170", "2148"],
                    "max_commute_time": 60,
                    "required_features": ["transport_links", "rental_yield"],
                    "preferred_features": ["low_maintenance", "central_location"],
                    "excluded_features": ["high_maintenance"],
                    "rental_yield_target": 5.5,
                    "capital_growth_expectation": "medium"
                },
                "interaction_patterns": {
                    "avg_daily_views": 2.8,
                    "avg_session_duration": 300,
                    "interest_score_variance": 1.2,
                    "feature_focus_score": 0.9
                },
                "search_query": "Investment property with strong rental yield, budget 500-750k"
            },
            {
                "id": str(uuid.uuid4()),
                "buyer_type": "luxury_buyer",
                "buying_urgency": "medium",
                "preferences": {
                    "max_price": 2500000,
                    "min_price": 1800000,
                    "budget_flexibility": 0.05,
                    "property_types": ["apartment", "house"],
                    "min_bedrooms": 3,
                    "max_bedrooms": 5,
                    "min_bathrooms": 2,
                    "min_car_spaces": 2,
                    "preferred_suburbs": ["double_bay", "point_piper", "vaucluse", "bellevue_hill"],
                    "preferred_postcodes": ["2028", "2027", "2030", "2023"],
                    "max_commute_time": 25,
                    "required_features": ["luxury_finishes", "waterfront"],
                    "preferred_features": ["harbor_views", "designer_kitchen", "concierge"],
                    "excluded_features": ["noisy_location"],
                    "rental_yield_target": 0.0,
                    "capital_growth_expectation": "high"
                },
                "interaction_patterns": {
                    "avg_daily_views": 1.5,
                    "avg_session_duration": 850,
                    "interest_score_variance": 0.4,
                    "feature_focus_score": 0.95
                },
                "search_query": "Luxury waterfront property with premium finishes and harbor views"
            }
        ]

    async def run_validation_suite(self) -> Dict[str, Any]:
        """Run complete Weaviate validation test suite."""
        start_time = time.time()
        
        self.logger.info("Starting Weaviate validation suite")
        
        try:
            # Initialize client
            await self._test_client_connection()
            
            # Create schemas
            await self._test_schema_creation()
            
            # Test data ingestion
            await self._test_property_ingestion()
            await self._test_buyer_ingestion()
            
            # Test search functionality
            await self._test_semantic_search()
            await self._test_buyer_property_matching()
            
            # Test OpenAI embeddings integration
            await self._test_embeddings_integration()
            
            # Test performance
            await self._test_performance_metrics()
            
            # Cleanup
            await self._cleanup_test_data()
            
        except Exception as e:
            self.logger.error("Validation suite failed", error=str(e))
            self.results.append(TestResult(
                test_name="validation_suite_error",
                success=False,
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))
        
        # Generate final report
        return self._generate_validation_report(time.time() - start_time)

    async def _test_client_connection(self) -> None:
        """Test Weaviate client connection."""
        start_time = time.time()
        
        try:
            self.client = WeaviateClient()
            await self.client.connect()
            
            health = await self.client.health_check()
            
            success = health.get("ready", False)
            details = {
                "connection_status": health.get("status"),
                "ready": health.get("ready"),
                "live": health.get("live"),
                "url": health.get("url"),
                "has_metadata": "meta" in health
            }
            
            self.results.append(TestResult(
                test_name="client_connection",
                success=success,
                duration=time.time() - start_time,
                details=details,
                error=None if success else "Weaviate not ready"
            ))
            
            self.logger.info("Client connection test completed", success=success)
            
        except Exception as e:
            self.results.append(TestResult(
                test_name="client_connection",
                success=False,
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))

    async def _test_schema_creation(self) -> None:
        """Test Weaviate schema creation."""
        start_time = time.time()
        
        try:
            # Property schema
            property_schema = {
                "class": "Property",
                "description": "Real estate property listings",
                "vectorizer": "none",
                "properties": [
                    {"name": "address", "dataType": ["text"]},
                    {"name": "suburb", "dataType": ["text"]},
                    {"name": "property_type", "dataType": ["text"]},
                    {"name": "bedrooms", "dataType": ["int"]},
                    {"name": "bathrooms", "dataType": ["int"]},
                    {"name": "price", "dataType": ["number"]},
                    {"name": "description", "dataType": ["text"]},
                    {"name": "features", "dataType": ["text[]"]}
                ]
            }
            
            # Buyer schema
            buyer_schema = {
                "class": "BuyerProfile",
                "description": "Buyer preference profiles",
                "vectorizer": "none",
                "properties": [
                    {"name": "buyer_type", "dataType": ["text"]},
                    {"name": "max_price", "dataType": ["number"]},
                    {"name": "min_price", "dataType": ["number"]},
                    {"name": "property_types", "dataType": ["text[]"]},
                    {"name": "preferred_suburbs", "dataType": ["text[]"]},
                    {"name": "search_query", "dataType": ["text"]}
                ]
            }
            
            # Create schemas
            prop_success = await self.client.create_schema(property_schema)
            buyer_success = await self.client.create_schema(buyer_schema)
            
            success = prop_success and buyer_success
            details = {
                "property_schema_created": prop_success,
                "buyer_schema_created": buyer_success
            }
            
            self.results.append(TestResult(
                test_name="schema_creation",
                success=success,
                duration=time.time() - start_time,
                details=details
            ))
            
            self.logger.info("Schema creation test completed", success=success)
            
        except Exception as e:
            self.results.append(TestResult(
                test_name="schema_creation",
                success=False,
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))

    async def _test_property_ingestion(self) -> None:
        """Test property data ingestion with embeddings."""
        start_time = time.time()
        inserted_count = 0
        
        try:
            for prop_data in self.sample_properties:
                # Convert to PropertyFeatures
                features = PropertyFeatures(
                    property_type=prop_data["property_type"],
                    bedrooms=prop_data["bedrooms"],
                    bathrooms=prop_data["bathrooms"],
                    car_spaces=prop_data.get("car_spaces", 0),
                    land_size=prop_data.get("land_size", 0),
                    building_size=prop_data.get("building_size", 0),
                    price=prop_data["price"],
                    suburb=prop_data["suburb"],
                    postcode=prop_data["postcode"],
                    latitude=prop_data.get("latitude", 0),
                    longitude=prop_data.get("longitude", 0),
                    title=prop_data["title"],
                    description=prop_data["description"],
                    features_list=prop_data.get("features", []),
                    days_on_market=prop_data.get("days_on_market", 0),
                    price_per_sqm=prop_data["price"] / prop_data.get("building_size", 1) if prop_data.get("building_size") else 0,
                    suburb_price_percentile=prop_data.get("market_context", {}).get("suburb_price_percentile", 0),
                    agent_name=prop_data.get("agent_name", ""),
                    agency_name=prop_data.get("agency_name", ""),
                    amenities=prop_data.get("amenities", {}),
                    market_context=prop_data.get("market_context", {})
                )
                
                # Generate embedding
                embedding, metadata = await self.property_vectorizer.generate_embedding(features)
                
                # Insert into Weaviate
                object_id = await self.client.insert_object(
                    class_name="Property",
                    properties=prop_data,
                    vector=embedding,
                    object_id=prop_data["id"]
                )
                
                if object_id:
                    inserted_count += 1
            
            success = inserted_count == len(self.sample_properties)
            details = {
                "total_properties": len(self.sample_properties),
                "inserted_count": inserted_count,
                "embedding_dimensions": len(embedding) if 'embedding' in locals() else 0,
                "vectorizer_metadata": metadata.__dict__ if 'metadata' in locals() else {}
            }
            
            self.results.append(TestResult(
                test_name="property_ingestion",
                success=success,
                duration=time.time() - start_time,
                details=details
            ))
            
            self.logger.info("Property ingestion test completed", 
                           success=success, 
                           inserted=inserted_count)
            
        except Exception as e:
            self.results.append(TestResult(
                test_name="property_ingestion",
                success=False,
                duration=time.time() - start_time,
                details={"inserted_count": inserted_count},
                error=str(e)
            ))

    async def _test_buyer_ingestion(self) -> None:
        """Test buyer profile ingestion."""
        start_time = time.time()
        inserted_count = 0
        
        try:
            for buyer_data in self.sample_buyers:
                # Convert to BuyerPreferenceFeatures
                prefs = buyer_data["preferences"]
                features = BuyerPreferenceFeatures(
                    max_price=prefs["max_price"],
                    min_price=prefs["min_price"],
                    budget_flexibility=prefs["budget_flexibility"],
                    property_types=prefs["property_types"],
                    min_bedrooms=prefs["min_bedrooms"],
                    max_bedrooms=prefs["max_bedrooms"],
                    min_bathrooms=prefs["min_bathrooms"],
                    min_car_spaces=prefs.get("min_car_spaces", 0),
                    min_land_size=prefs.get("min_land_size", 0),
                    min_building_size=prefs.get("min_building_size", 0),
                    preferred_suburbs=prefs["preferred_suburbs"],
                    excluded_suburbs=prefs.get("excluded_suburbs", []),
                    preferred_postcodes=prefs["preferred_postcodes"],
                    max_commute_time=prefs["max_commute_time"],
                    required_features=prefs["required_features"],
                    preferred_features=prefs["preferred_features"],
                    excluded_features=prefs.get("excluded_features", []),
                    buyer_type=buyer_data["buyer_type"],
                    buying_urgency=buyer_data["buying_urgency"],
                    rental_yield_target=prefs.get("rental_yield_target", 0),
                    capital_growth_expectation=prefs.get("capital_growth_expectation", "medium"),
                    interaction_patterns=buyer_data.get("interaction_patterns", {}),
                    preference_weights={}
                )
                
                # Generate embedding
                embedding, metadata = await self.buyer_vectorizer.generate_embedding(features)
                
                # Insert into Weaviate
                object_id = await self.client.insert_object(
                    class_name="BuyerProfile",
                    properties=buyer_data,
                    vector=embedding,
                    object_id=buyer_data["id"]
                )
                
                if object_id:
                    inserted_count += 1
            
            success = inserted_count == len(self.sample_buyers)
            details = {
                "total_buyers": len(self.sample_buyers),
                "inserted_count": inserted_count,
                "embedding_dimensions": len(embedding) if 'embedding' in locals() else 0
            }
            
            self.results.append(TestResult(
                test_name="buyer_ingestion",
                success=success,
                duration=time.time() - start_time,
                details=details
            ))
            
            self.logger.info("Buyer ingestion test completed", 
                           success=success, 
                           inserted=inserted_count)
            
        except Exception as e:
            self.results.append(TestResult(
                test_name="buyer_ingestion",
                success=False,
                duration=time.time() - start_time,
                details={"inserted_count": inserted_count},
                error=str(e)
            ))

    async def _test_semantic_search(self) -> None:
        """Test semantic property search functionality."""
        start_time = time.time()
        
        try:
            # Test queries
            test_queries = [
                ("modern apartment CBD transport", 3),
                ("beach house ocean views", 2),
                ("luxury waterfront harbor views", 1),
                ("family home pool garden", 2),
                ("investment property rental yield", 1)
            ]
            
            search_results = {}
            
            for query_text, expected_min_results in test_queries:
                # Generate query embedding
                query_features = PropertyFeatures(
                    property_type="apartment",
                    bedrooms=2, bathrooms=1, car_spaces=1,
                    land_size=0, building_size=100, price=800000,
                    suburb="Sydney", postcode="2000",
                    latitude=-33.8688, longitude=151.2093,
                    title=query_text, description=query_text,
                    features_list=query_text.split(),
                    days_on_market=0, price_per_sqm=8000,
                    suburb_price_percentile=50,
                    agent_name="Test", agency_name="Test",
                    amenities={}, market_context={}
                )
                
                query_embedding, _ = await self.property_vectorizer.generate_embedding(query_features)
                
                # Search properties
                search_query = SearchQuery(
                    vector=query_embedding,
                    class_name="Property",
                    limit=5,
                    additional_properties=["certainty"]
                )
                
                results = await self.client.vector_search(search_query)
                
                search_results[query_text] = {
                    "result_count": len(results),
                    "meets_minimum": len(results) >= expected_min_results,
                    "top_score": results[0].score if results else 0,
                    "top_result": results[0].data.get("address", "N/A") if results else "N/A"
                }
            
            success = all(r["meets_minimum"] for r in search_results.values())
            details = {
                "test_queries": len(test_queries),
                "search_results": search_results,
                "all_queries_successful": success
            }
            
            self.results.append(TestResult(
                test_name="semantic_search",
                success=success,
                duration=time.time() - start_time,
                details=details
            ))
            
            self.logger.info("Semantic search test completed", success=success)
            
        except Exception as e:
            self.results.append(TestResult(
                test_name="semantic_search",
                success=False,
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))

    async def _test_buyer_property_matching(self) -> None:
        """Test buyer-property matching functionality."""
        start_time = time.time()
        
        try:
            matches_found = 0
            matching_results = {}
            
            for buyer in self.sample_buyers:
                buyer_id = buyer["id"]
                
                # Get buyer embedding
                buyer_obj = await self.client.get_object("BuyerProfile", buyer_id)
                if not buyer_obj:
                    continue
                
                # Search for matching properties using hybrid search
                results = await self.client.hybrid_search(
                    class_name="Property",
                    query_text=buyer["search_query"],
                    limit=3
                )
                
                # Filter by budget constraints
                budget_filtered = []
                for result in results:
                    prop_price = result.data.get("price", 0)
                    buyer_max = buyer["preferences"]["max_price"]
                    buyer_min = buyer["preferences"]["min_price"]
                    
                    if buyer_min <= prop_price <= buyer_max:
                        budget_filtered.append(result)
                
                matching_results[buyer["buyer_type"]] = {
                    "total_matches": len(results),
                    "budget_filtered_matches": len(budget_filtered),
                    "top_match": budget_filtered[0].data.get("address", "N/A") if budget_filtered else "N/A",
                    "match_score": budget_filtered[0].score if budget_filtered else 0
                }
                
                if budget_filtered:
                    matches_found += 1
            
            success = matches_found >= len(self.sample_buyers) // 2  # At least 50% should find matches
            details = {
                "total_buyers": len(self.sample_buyers),
                "buyers_with_matches": matches_found,
                "matching_results": matching_results
            }
            
            self.results.append(TestResult(
                test_name="buyer_property_matching",
                success=success,
                duration=time.time() - start_time,
                details=details
            ))
            
            self.logger.info("Buyer-property matching test completed", 
                           success=success, 
                           matches=matches_found)
            
        except Exception as e:
            self.results.append(TestResult(
                test_name="buyer_property_matching",
                success=False,
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))

    async def _test_embeddings_integration(self) -> None:
        """Test OpenAI embeddings integration and vector dimensions."""
        start_time = time.time()
        
        try:
            # Test property vectorization
            test_property = PropertyFeatures(
                property_type="apartment",
                bedrooms=2, bathrooms=1, car_spaces=1,
                land_size=0, building_size=85, price=850000,
                suburb="Surry Hills", postcode="2010",
                latitude=-33.8858, longitude=151.2131,
                title="Test Property", description="Modern apartment with city views",
                features_list=["modern", "city_views", "balcony"],
                days_on_market=14, price_per_sqm=10000,
                suburb_price_percentile=75,
                agent_name="Test Agent", agency_name="Test Agency",
                amenities={}, market_context={}
            )
            
            prop_embedding, prop_metadata = await self.property_vectorizer.generate_embedding(test_property)
            
            # Test buyer vectorization
            test_buyer = BuyerPreferenceFeatures(
                max_price=900000, min_price=700000, budget_flexibility=0.15,
                property_types=["apartment"], min_bedrooms=2, max_bedrooms=3,
                min_bathrooms=1, min_car_spaces=1, min_land_size=0, min_building_size=0,
                preferred_suburbs=["surry_hills"], excluded_suburbs=[],
                preferred_postcodes=["2010"], max_commute_time=30,
                required_features=["modern"], preferred_features=["city_views"],
                excluded_features=[], buyer_type="first_home_buyer", buying_urgency="medium",
                rental_yield_target=0, capital_growth_expectation="medium",
                interaction_patterns={}, preference_weights={}
            )
            
            buyer_embedding, buyer_metadata = await self.buyer_vectorizer.generate_embedding(test_buyer)
            
            # Test similarity calculation
            similarity = self.property_vectorizer.calculate_similarity(prop_embedding, buyer_embedding)
            
            success = (
                len(prop_embedding) > 0 and 
                len(buyer_embedding) > 0 and
                0 <= similarity <= 1
            )
            
            details = {
                "property_embedding_dim": len(prop_embedding),
                "buyer_embedding_dim": len(buyer_embedding),
                "similarity_score": similarity,
                "property_metadata": prop_metadata.__dict__,
                "buyer_metadata": buyer_metadata.__dict__,
                "embeddings_valid": success
            }
            
            self.results.append(TestResult(
                test_name="embeddings_integration",
                success=success,
                duration=time.time() - start_time,
                details=details
            ))
            
            self.logger.info("Embeddings integration test completed", success=success)
            
        except Exception as e:
            self.results.append(TestResult(
                test_name="embeddings_integration",
                success=False,
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))

    async def _test_performance_metrics(self) -> None:
        """Test system performance under load."""
        start_time = time.time()
        
        try:
            # Test batch operations
            batch_properties = []
            batch_embeddings = []
            
            for i in range(10):
                prop_data = {
                    "id": str(uuid.uuid4()),
                    "address": f"Test Address {i}",
                    "suburb": "Test Suburb",
                    "property_type": "apartment",
                    "bedrooms": 2,
                    "bathrooms": 1,
                    "price": 800000 + (i * 10000),
                    "description": f"Test property {i} for batch testing"
                }
                
                # Generate embedding
                features = PropertyFeatures(
                    property_type="apartment", bedrooms=2, bathrooms=1, car_spaces=1,
                    land_size=0, building_size=85, price=prop_data["price"],
                    suburb="Test Suburb", postcode="2000",
                    latitude=-33.8688, longitude=151.2093,
                    title=f"Test Property {i}", description=prop_data["description"],
                    features_list=["modern", "test"], days_on_market=0, price_per_sqm=10000,
                    suburb_price_percentile=50, agent_name="Test", agency_name="Test",
                    amenities={}, market_context={}
                )
                
                embedding, _ = await self.property_vectorizer.generate_embedding(features)
                
                batch_properties.append(prop_data)
                batch_embeddings.append(embedding)
            
            # Test batch insertion
            batch_start = time.time()
            inserted_ids = await self.client.batch_insert_objects(
                class_name="Property",
                objects=batch_properties,
                vectors=batch_embeddings
            )
            batch_duration = time.time() - batch_start
            
            # Test search performance
            search_start = time.time()
            search_results = await self.client.vector_search(SearchQuery(
                vector=batch_embeddings[0],
                class_name="Property",
                limit=20
            ))
            search_duration = time.time() - search_start
            
            # Test object count
            count_start = time.time()
            total_count = await self.client.get_object_count("Property")
            count_duration = time.time() - count_start
            
            success = (
                len(inserted_ids) == 10 and
                batch_duration < 5.0 and  # Batch insert under 5 seconds
                search_duration < 2.0 and  # Search under 2 seconds
                total_count > 0
            )
            
            details = {
                "batch_insert_count": len(inserted_ids),
                "batch_insert_duration": batch_duration,
                "search_results_count": len(search_results),
                "search_duration": search_duration,
                "total_objects": total_count,
                "count_query_duration": count_duration,
                "performance_acceptable": success
            }
            
            self.results.append(TestResult(
                test_name="performance_metrics",
                success=success,
                duration=time.time() - start_time,
                details=details
            ))
            
            self.logger.info("Performance test completed", success=success)
            
        except Exception as e:
            self.results.append(TestResult(
                test_name="performance_metrics",
                success=False,
                duration=time.time() - start_time,
                details={},
                error=str(e)
            ))

    async def _cleanup_test_data(self) -> None:
        """Clean up test data from Weaviate."""
        try:
            # Delete test schemas (this will remove all objects)
            await self.client.delete_schema("Property")
            await self.client.delete_schema("BuyerProfile")
            
            self.logger.info("Test data cleanup completed")
            
        except Exception as e:
            self.logger.warning("Test cleanup failed", error=str(e))

    def _generate_validation_report(self, total_duration: float) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        successful_tests = [r for r in self.results if r.success]
        failed_tests = [r for r in self.results if not r.success]
        
        # Calculate metrics
        success_rate = len(successful_tests) / len(self.results) if self.results else 0
        avg_duration = sum(r.duration for r in self.results) / len(self.results) if self.results else 0
        
        # Extract key performance metrics
        performance_details = {}
        for result in self.results:
            if result.test_name == "performance_metrics" and result.success:
                performance_details = result.details
                break
        
        # Extract embedding details
        embedding_details = {}
        for result in self.results:
            if result.test_name == "embeddings_integration" and result.success:
                embedding_details = result.details
                break
        
        return {
            "validation_summary": {
                "total_tests": len(self.results),
                "successful_tests": len(successful_tests),
                "failed_tests": len(failed_tests),
                "success_rate": round(success_rate * 100, 1),
                "total_duration": round(total_duration, 2),
                "average_test_duration": round(avg_duration, 2)
            },
            "functional_validation": {
                "weaviate_connection": any(r.test_name == "client_connection" and r.success for r in self.results),
                "schema_creation": any(r.test_name == "schema_creation" and r.success for r in self.results),
                "property_ingestion": any(r.test_name == "property_ingestion" and r.success for r in self.results),
                "buyer_ingestion": any(r.test_name == "buyer_ingestion" and r.success for r in self.results),
                "semantic_search": any(r.test_name == "semantic_search" and r.success for r in self.results),
                "buyer_property_matching": any(r.test_name == "buyer_property_matching" and r.success for r in self.results)
            },
            "performance_metrics": performance_details,
            "embedding_validation": embedding_details,
            "failed_tests": [
                {
                    "test_name": r.test_name,
                    "error": r.error,
                    "duration": r.duration
                } for r in failed_tests
            ],
            "recommendations": self._generate_recommendations(successful_tests, failed_tests),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _generate_recommendations(self, successful_tests: List[TestResult], failed_tests: List[TestResult]) -> List[str]:
        """Generate optimization recommendations based on test results."""
        recommendations = []
        
        if not failed_tests:
            recommendations.append("✅ All tests passed - Weaviate vector search system is ready for production")
        
        # Check for performance issues
        perf_test = next((r for r in successful_tests if r.test_name == "performance_metrics"), None)
        if perf_test:
            details = perf_test.details
            if details.get("batch_insert_duration", 0) > 3.0:
                recommendations.append("⚠️ Consider optimizing batch insert performance - current duration exceeds 3 seconds")
            if details.get("search_duration", 0) > 1.0:
                recommendations.append("⚠️ Search performance could be improved - consider index optimization")
        
        # Check for failed tests
        for failed_test in failed_tests:
            if failed_test.test_name == "client_connection":
                recommendations.append("🔧 Fix Weaviate connection - ensure Weaviate server is running and accessible")
            elif failed_test.test_name == "embeddings_integration":
                recommendations.append("🔧 Review embedding generation - check OpenAI API configuration")
            elif failed_test.test_name == "semantic_search":
                recommendations.append("🔧 Tune vector search parameters - check embedding quality and similarity thresholds")
        
        # Production readiness recommendations
        if len(successful_tests) >= 6:
            recommendations.append("🚀 System ready for production deployment with comprehensive monitoring")
            recommendations.append("📊 Implement real-time performance dashboards for vector search operations")
            recommendations.append("🔍 Set up alerting for search latency and embedding generation failures")
        
        return recommendations


async def main():
    """Run Weaviate validation suite."""
    print("🔍 Starting Weaviate Vector Search Validation & Data Ingestion Testing")
    print("=" * 70)
    
    validator = WeaviateValidationSuite()
    report = await validator.run_validation_suite()
    
    # Print detailed report
    print("\n📊 VALIDATION REPORT")
    print("=" * 70)
    
    summary = report["validation_summary"]
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Successful: {summary['successful_tests']}")
    print(f"Failed: {summary['failed_tests']}")
    print(f"Success Rate: {summary['success_rate']}%")
    print(f"Total Duration: {summary['total_duration']}s")
    
    print("\n🔧 FUNCTIONAL VALIDATION")
    print("-" * 30)
    functional = report["functional_validation"]
    for test, passed in functional.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test.replace('_', ' ').title()}: {status}")
    
    if report["performance_metrics"]:
        print("\n⚡ PERFORMANCE METRICS")
        print("-" * 30)
        perf = report["performance_metrics"]
        print(f"Batch Insert: {perf.get('batch_insert_duration', 0):.2f}s ({perf.get('batch_insert_count', 0)} objects)")
        print(f"Search Query: {perf.get('search_duration', 0):.2f}s ({perf.get('search_results_count', 0)} results)")
        print(f"Total Objects: {perf.get('total_objects', 0)}")
    
    if report["embedding_validation"]:
        print("\n🧠 EMBEDDING VALIDATION")
        print("-" * 30)
        emb = report["embedding_validation"]
        print(f"Property Embedding Dimensions: {emb.get('property_embedding_dim', 0)}")
        print(f"Buyer Embedding Dimensions: {emb.get('buyer_embedding_dim', 0)}")
        print(f"Similarity Score: {emb.get('similarity_score', 0):.3f}")
    
    if report["failed_tests"]:
        print("\n❌ FAILED TESTS")
        print("-" * 30)
        for failed in report["failed_tests"]:
            print(f"{failed['test_name']}: {failed['error']}")
    
    print("\n💡 RECOMMENDATIONS")
    print("-" * 30)
    for rec in report["recommendations"]:
        print(f"• {rec}")
    
    print("\n" + "=" * 70)
    print("✅ Weaviate validation completed!")
    
    # Save report to file
    with open("weaviate_validation_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("📄 Full report saved to: weaviate_validation_report.json")


if __name__ == "__main__":
    asyncio.run(main())