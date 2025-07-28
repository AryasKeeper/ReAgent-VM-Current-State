"""
Unit tests for the Listing Watcher AU agent and related components.
"""

import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from reagent_sydney.agents.listing_watcher import (
    ListingWatcherAgent, 
    PropertyDeltaDetector,
    PropertyDataEnricher,
    ListingWatcherTools
)
from reagent_sydney.agents.listing_watcher.config import (
    ListingWatcherConfig,
    create_test_config,
    SydneyPostcodes
)
from reagent_sydney.services.external_apis import DomainAPIClient, RealEstateAPIClient
from reagent_sydney.utils.validation import validate_property_data


class TestSydneyPostcodes:
    """Test Sydney postcode configuration."""
    
    def test_get_all_sydney_postcodes(self):
        """Test getting all Sydney postcodes."""
        postcodes = SydneyPostcodes.get_all_sydney_postcodes()
        
        assert isinstance(postcodes, list)
        assert len(postcodes) > 100  # Should have many postcodes
        assert "2000" in postcodes  # Sydney CBD
        assert "2088" in postcodes  # Mosman
        assert all(isinstance(pc, str) for pc in postcodes)
    
    def test_get_premium_postcodes(self):
        """Test getting premium postcodes."""
        premium = SydneyPostcodes.get_premium_postcodes()
        
        assert isinstance(premium, list)
        assert len(premium) > 10
        assert "2023" in premium  # Bellevue Hill
        assert "2061" in premium  # Kirribilli
        assert all(isinstance(pc, str) for pc in premium)


class TestListingWatcherConfig:
    """Test Listing Watcher configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ListingWatcherConfig()
        
        assert config.scraping_interval_seconds == 3600  # 1 hour
        assert config.batch_size == 100
        assert config.enable_delta_detection is True
        assert config.enable_data_enrichment is True
        assert len(config.target_postcodes) > 100
    
    def test_test_config(self):
        """Test test configuration."""
        config = create_test_config()
        
        assert config.batch_size == 10
        assert config.dry_run_mode is True
        assert len(config.target_postcodes) == 3  # Small subset
        assert config.test_mode_max_listings == 10
    
    def test_get_active_postcodes(self):
        """Test getting active postcodes."""
        config = ListingWatcherConfig(focus_premium_areas=True)
        active = config.get_active_postcodes()
        
        assert isinstance(active, list)
        assert len(active) > 0
        assert "2023" in active  # Premium area
    
    def test_rate_limit_for_source(self):
        """Test rate limit calculation."""
        config = ListingWatcherConfig()
        
        domain_limit = config.get_rate_limit_for_source("domain")
        rea_limit = config.get_rate_limit_for_source("realestate")
        
        assert domain_limit < config.domain_max_calls_per_hour  # Has buffer
        assert rea_limit < config.realestate_max_calls_per_hour
        assert domain_limit > 0
        assert rea_limit > 0
    
    def test_should_process_property_type(self):
        """Test property type filtering."""
        config = ListingWatcherConfig()
        
        assert config.should_process_property_type("House") is True
        assert config.should_process_property_type("Unit") is True
        assert config.should_process_property_type("Land") is False
        assert config.should_process_property_type("Commercial") is False
        assert config.should_process_property_type("") is False


class TestPropertyValidation:
    """Test property data validation."""
    
    def test_validate_property_data_valid(self):
        """Test validation with valid data."""
        property_data = {
            "listing_id": "test_123",
            "source": "domain",
            "title": "Beautiful House",
            "suburb": "Mosman",
            "postcode": "2088",
            "property_type": "House",
            "bedrooms": 3,
            "bathrooms": 2,
            "price": Decimal("750000"),
            "latitude": -33.8365,
            "longitude": 151.2395
        }
        
        validated = validate_property_data(property_data)
        
        assert "_validation_errors" not in validated
        assert validated["listing_id"] == "test_123"
        assert validated["bedrooms"] == 3
        assert isinstance(validated["price"], Decimal)
    
    def test_validate_property_data_invalid(self):
        """Test validation with invalid data."""
        property_data = {
            "listing_id": "",  # Missing required field
            "source": "domain",
            "postcode": "invalid",  # Invalid postcode
            "bedrooms": -1,  # Invalid value
            "price": "not_a_number"  # Invalid price
        }
        
        validated = validate_property_data(property_data)
        
        assert "_validation_errors" in validated
        assert len(validated["_validation_errors"]) > 0
    
    def test_validate_coordinates(self):
        """Test coordinate validation."""
        property_data = {
            "listing_id": "test_123",
            "source": "domain",
            "title": "Test Property",
            "suburb": "Sydney",
            "postcode": "2000",
            "latitude": 91.0,  # Invalid latitude
            "longitude": 181.0  # Invalid longitude
        }
        
        validated = validate_property_data(property_data)
        
        assert "_validation_errors" in validated
        errors = validated["_validation_errors"]
        assert any("latitude" in error.lower() for error in errors)
        assert any("longitude" in error.lower() for error in errors)


@pytest.mark.asyncio
class TestPropertyDeltaDetector:
    """Test property delta detection."""
    
    @pytest.fixture
    async def detector(self):
        """Create a delta detector for testing."""
        detector = PropertyDeltaDetector(cache_ttl=300)  # 5 minutes for testing
        
        # Mock the cache manager
        detector.cache_manager = Mock()
        detector.cache_manager.get = AsyncMock()
        detector.cache_manager.set = AsyncMock()
        detector.cache_manager.mget = AsyncMock()
        
        await detector.initialize()
        return detector
    
    async def test_detect_new_listing(self, detector):
        """Test detecting a new listing."""
        # Mock that listing is not known
        detector.cache_manager.get.return_value = set()
        
        property_data = {
            "listing_id": "new_123",
            "title": "New Property",
            "price": Decimal("500000")
        }
        
        result = await detector.detect_changes("new_123", property_data)
        
        assert result["is_new"] is True
        assert result["has_changes"] is False
        assert result["changes"] == {}
    
    async def test_detect_price_change(self, detector):
        """Test detecting a price change."""
        # Mock existing data
        cached_data = {
            "price": "500000",
            "title": "Test Property"
        }
        detector.cache_manager.get.side_effect = [
            {"new_123"},  # Known listings
            cached_data   # Cached property data
        ]
        
        current_data = {
            "listing_id": "new_123",
            "title": "Test Property",
            "price": Decimal("450000")  # Price dropped
        }
        
        result = await detector.detect_changes("new_123", current_data)
        
        assert result["is_new"] is False
        assert result["has_changes"] is True
        assert "price" in result["changes"]
        
        price_change = result["changes"]["price"]
        assert price_change["old_value"] == "500000"
        assert price_change["new_value"] == "450000"
    
    async def test_batch_detect_changes(self, detector):
        """Test batch change detection."""
        # Mock batch cached data
        detector.cache_manager.mget.return_value = {
            "listing_1": {"price": "500000"},
            "listing_2": None  # New listing
        }
        
        listings = [
            {"listing_id": "listing_1", "price": Decimal("500000")},  # No change
            {"listing_id": "listing_2", "price": Decimal("600000")},  # New
            {"listing_id": "listing_3", "price": Decimal("700000")}   # New (no cache)
        ]
        
        results = await detector.batch_detect_changes(listings)
        
        assert len(results) == 3
        assert results[0]["has_changes"] is False  # No change
        assert results[1]["is_new"] is True        # New listing
        assert results[2]["is_new"] is True        # New listing


@pytest.mark.asyncio
class TestPropertyDataEnricher:
    """Test property data enrichment."""
    
    @pytest.fixture
    async def enricher(self):
        """Create a data enricher for testing."""
        enricher = PropertyDataEnricher(cache_ttl=300)
        
        # Mock cache manager
        enricher.cache_manager = Mock()
        enricher.cache_manager.get = AsyncMock()
        enricher.cache_manager.set = AsyncMock()
        
        await enricher.initialize()
        return enricher
    
    async def test_enrich_property_data(self, enricher):
        """Test basic property data enrichment."""
        property_data = {
            "listing_id": "enrich_123",
            "title": "Beautiful House with Pool",
            "description": "This stunning 3 bedroom house features a swimming pool, garage, and harbor views. Air conditioning throughout.",
            "suburb": "Mosman",
            "postcode": "2088",
            "property_type": "House",
            "bedrooms": 3,
            "bathrooms": 2,
            "price": Decimal("2800000"),
            "latitude": -33.8365,
            "longitude": 151.2395
        }
        
        enriched = await enricher.enrich_property_data(property_data)
        
        # Check that features were extracted
        features = enriched.get("features", [])
        assert len(features) > 0
        assert any("pool" in feature.lower() for feature in features)
        assert any("garage" in feature.lower() for feature in features)
        
        # Check search keywords
        keywords = enriched.get("search_keywords", [])
        assert len(keywords) > 0
        assert "mosman" in keywords
        assert "2088" in keywords
        
        # Check suburb quality
        assert enriched.get("suburb_quality") == "premium"  # Mosman is premium
        
        # Check distance to CBD
        assert "distance_to_cbd_km" in enriched
        assert enriched["distance_to_cbd_km"] > 0
    
    async def test_extract_features_from_description(self, enricher):
        """Test feature extraction from text."""
        description = "Beautiful house with swimming pool, 2 car garage, air conditioning, and stunning harbor views."
        title = "Luxury Home with Pool"
        
        features = await enricher._extract_features_from_description(description, title)
        
        assert len(features) > 0
        # Should extract pool, garage, air conditioning, views
        feature_text = " ".join(features).lower()
        assert "pool" in feature_text
        assert "garage" in feature_text or "car" in feature_text
        assert "air" in feature_text
        assert "views" in feature_text
    
    def test_get_suburb_quality(self, enricher):
        """Test suburb quality assessment."""
        assert enricher._get_suburb_quality("Mosman") == "premium"
        assert enricher._get_suburb_quality("Bondi") == "high"
        assert enricher._get_suburb_quality("Parramatta") == "medium"
        assert enricher._get_suburb_quality("Unknown Suburb") == "medium"
    
    def test_calculate_distance_km(self, enricher):
        """Test distance calculation."""
        # Distance from Sydney CBD to Mosman (approximate)
        cbd_lat, cbd_lng = -33.8688, 151.2093
        mosman_lat, mosman_lng = -33.8365, 151.2395
        
        distance = enricher._calculate_distance_km(
            mosman_lat, mosman_lng, cbd_lat, cbd_lng
        )
        
        # Should be roughly 5-10km
        assert 3 < distance < 15


@pytest.mark.asyncio 
class TestDomainAPIClient:
    """Test Domain API client (mocked)."""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock HTTP session."""
        session = Mock()
        session.request = AsyncMock()
        return session
    
    @pytest.fixture
    def client(self, mock_session):
        """Create Domain client with mocked session."""
        with patch('reagent_sydney.services.external_apis.domain_client.get_settings') as mock_settings:
            mock_settings.return_value.apis.domain_api_key = "test_key"
            mock_settings.return_value.apis.domain_rate_limit = 1000
            
            client = DomainAPIClient("test_key")
            client.cache_manager = Mock()
            client.cache_manager.get = AsyncMock(return_value=None)
            client.cache_manager.set = AsyncMock()
            
            return client
    
    async def test_search_listings_success(self, client, mock_session):
        """Test successful listing search."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "listings": [
                {
                    "id": "123",
                    "headline": "Test Property",
                    "propertyDetails": {
                        "suburb": "Sydney",
                        "postcode": "2000"
                    }
                }
            ]
        })
        
        mock_session.request.return_value.__aenter__.return_value = mock_response
        client.session = mock_session
        
        result = await client.search_listings(postcodes=["2000"])
        
        assert "listings" in result
        assert len(result["listings"]) == 1
        assert result["listings"][0]["id"] == "123"
    
    async def test_normalize_property_data(self, client):
        """Test property data normalization."""
        raw_data = {
            "id": "test_123",
            "headline": "Beautiful House",
            "propertyDetails": {
                "suburb": "Mosman",
                "postcode": "2088",
                "displayableAddress": "123 Test Street",
                "bedrooms": 3,
                "bathrooms": 2,
                "latitude": -33.8365,
                "longitude": 151.2395
            },
            "priceDetails": {
                "displayPrice": "$750,000",
                "price": 750000
            }
        }
        
        normalized = client.normalize_property_data(raw_data)
        
        assert normalized["listing_id"] == "test_123"
        assert normalized["source"] == "domain"
        assert normalized["title"] == "Beautiful House"
        assert normalized["suburb"] == "Mosman"
        assert normalized["postcode"] == "2088"
        assert normalized["bedrooms"] == 3
        assert normalized["bathrooms"] == 2
        assert isinstance(normalized["price"], Decimal)
        assert normalized["price"] == Decimal("750000")


# Integration test placeholder
@pytest.mark.integration
@pytest.mark.asyncio
class TestListingWatcherIntegration:
    """Integration tests for the complete agent (requires real services)."""
    
    async def test_agent_initialization(self):
        """Test agent can initialize with test configuration."""
        config = create_test_config()
        agent = ListingWatcherAgent(config)
        
        # This would require actual services to be running
        # For now, just test that the agent can be created
        assert agent is not None
        assert agent.config.name == "Listing Watcher AU"
    
    @pytest.mark.skip(reason="Requires live API keys and services")
    async def test_full_agent_execution(self):
        """Test complete agent execution (requires live services)."""
        config = create_test_config()
        agent = ListingWatcherAgent(config)
        
        try:
            await agent.initialize()
            
            result = await agent.execute({
                "config": {
                    "postcodes": ["2000"],
                    "force_full_scan": True
                }
            })
            
            assert result["success"] is True
            assert "statistics" in result.get("data", {})
            
        finally:
            await agent.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])