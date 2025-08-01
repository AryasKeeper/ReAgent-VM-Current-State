"""
Unit tests for external API clients, including Domain and RealEstate.com.au.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from reagent.services.external_apis.domain_client import DomainAPIClient
from reagent.services.external_apis.realestate_client import RealEstateAPIClient

@pytest.fixture
def mock_cache_manager():
    """Fixture for a mock cache manager."""
    return AsyncMock()

@pytest.mark.asyncio
class TestDomainAPIClient:
    """Tests for the DomainAPIClient."""

    @pytest.fixture
    def client(self, mock_cache_manager):
        """Fixture for a DomainAPIClient instance with a mock cache manager."""
        with patch('reagent.services.external_apis.domain_client.get_settings') as mock_get_settings:
            mock_get_settings.return_value.apis.domain_api_key = "test_key"
            mock_get_settings.return_value.apis.domain_rate_limit = 1000
            client = DomainAPIClient()
            client.cache_manager = mock_cache_manager
            client.session = MagicMock()
            return client

    async def test_etag_caching_flow(self, client, mock_cache_manager):
        """Test the ETag caching and retrieval flow."""
        endpoint = "listings/residential/_search"
        params = {"postcodes": "2000"}
        cache_key = "domain_search:test"
        
        # 1. First request (cache miss)
        mock_cache_manager.get.side_effect = [
            None,  # for cache_key
            0,     # for rate_key in _check_rate_limit
            0,     # for rate_key in _increment_rate_counter
        ]
        
        mock_response_1 = AsyncMock()
        mock_response_1.status = 200
        mock_response_1.headers = {"ETag": "etag-123"}
        mock_response_1.json.return_value = {"data": "initial_data"}
        
        client.session.request.return_value.__aenter__.return_value = mock_response_1
        
        result_1 = await client._make_request("GET", endpoint, params, cache_key=cache_key)
        assert result_1 == {"data": "initial_data"}
        mock_cache_manager.set.assert_any_call(
            cache_key, {"data": {"data": "initial_data"}, "etag": "etag-123"}, ttl=client.cache_ttl
        )

        # 2. Second request (cache hit, 304 Not Modified)
        mock_cache_manager.reset_mock()
        mock_cache_manager.get.side_effect = [
            {"data": {"data": "initial_data"}, "etag": "etag-123"}, # for cache_key
            1, # for rate_key in _check_rate_limit
            1, # for rate_key in _increment_rate_counter
        ]
        
        mock_response_2 = AsyncMock()
        mock_response_2.status = 304
        client.session.request.return_value.__aenter__.return_value = mock_response_2
        
        result_2 = await client._make_request("GET", endpoint, params, cache_key=cache_key)
        assert result_2 == {"data": "initial_data"}
        # `set` should not be called for cache, only for rate limit
        mock_cache_manager.set.assert_called_once_with(client.rate_key, 2, ttl=client.rate_window)

    async def test_etag_cache_update(self, client, mock_cache_manager):
        """Test that the cache is updated when the ETag changes."""
        endpoint = "listings/residential/_search"
        params = {"localities": ["2000"]}
        cache_key = "realestate_search:test_update"

        # 1. Initial request, cache populated
        mock_cache_manager.get.side_effect = [None, 0, 0]
        mock_response_1 = AsyncMock()
        mock_response_1.status = 200
        mock_response_1.headers = {"ETag": "etag-abc"}
        mock_response_1.json.return_value = {"data": "rea_data"}
        client.session.request.return_value.__aenter__.return_value = mock_response_1
        await client._make_request("GET", endpoint, params, cache_key=cache_key)

        # 2. Second request, ETag mismatch, new data returned
        mock_cache_manager.reset_mock()
        mock_cache_manager.get.side_effect = [
            {"data": {"data": "rea_data"}, "etag": "etag-abc"},
            1,
            1
        ]
        mock_response_2 = AsyncMock()
        mock_response_2.status = 200
        mock_response_2.headers = {"ETag": "etag-def"}
        mock_response_2.json.return_value = {"data": "updated_rea_data"}
        client.session.request.return_value.__aenter__.return_value = mock_response_2

        result = await client._make_request("GET", endpoint, params, cache_key=cache_key)
        assert result == {"data": "updated_rea_data"}
        mock_cache_manager.set.assert_any_call(
            cache_key, {"data": {"data": "updated_rea_data"}, "etag": "etag-def"}, ttl=client.cache_ttl
        )

    async def test_cache_miss_server_error(self, client, mock_cache_manager):
        """Test that a server error on a cache miss is handled correctly."""
        endpoint = "listings/residential/_search"
        params = {"localities": ["2000"]}
        cache_key = "realestate_search:test_error"

        # 1. First request (cache miss, server error)
        mock_cache_manager.get.side_effect = [None, 0, 0]
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Internal Server Error"
        client.session.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="API request failed: 500 - Internal Server Error"):
            await client._make_request("GET", endpoint, params, cache_key=cache_key)
        
        mock_cache_manager.set.assert_called_once_with(client.rate_key, 1, ttl=client.rate_window)


    async def test_etag_cache_update(self, client, mock_cache_manager):
        """Test that the cache is updated when the ETag changes."""
        endpoint = "listings/residential/_search"
        params = {"postcodes": "2000"}
        cache_key = "domain_search:test_update"

        # 1. Initial request, cache populated
        mock_cache_manager.get.side_effect = [None, 0, 0]
        mock_response_1 = AsyncMock()
        mock_response_1.status = 200
        mock_response_1.headers = {"ETag": "etag-123"}
        mock_response_1.json.return_value = {"data": "initial_data"}
        client.session.request.return_value.__aenter__.return_value = mock_response_1
        await client._make_request("GET", endpoint, params, cache_key=cache_key)

        # 2. Second request, ETag mismatch, new data returned
        mock_cache_manager.reset_mock()
        mock_cache_manager.get.side_effect = [
            {"data": {"data": "initial_data"}, "etag": "etag-123"},
            1, 
            1
        ]
        mock_response_2 = AsyncMock()
        mock_response_2.status = 200
        mock_response_2.headers = {"ETag": "etag-456"}
        mock_response_2.json.return_value = {"data": "updated_data"}
        client.session.request.return_value.__aenter__.return_value = mock_response_2

        result = await client._make_request("GET", endpoint, params, cache_key=cache_key)
        assert result == {"data": "updated_data"}
        mock_cache_manager.set.assert_any_call(
            cache_key, {"data": {"data": "updated_data"}, "etag": "etag-456"}, ttl=client.cache_ttl
        )

    async def test_cache_miss_server_error(self, client, mock_cache_manager):
        """Test that a server error on a cache miss is handled correctly."""
        endpoint = "listings/residential/_search"
        params = {"postcodes": "2000"}
        cache_key = "domain_search:test_error"

        # 1. First request (cache miss, server error)
        mock_cache_manager.get.side_effect = [None, 0, 0]
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Internal Server Error"
        client.session.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="API request failed: 500 - Internal Server Error"):
            await client._make_request("GET", endpoint, params, cache_key=cache_key)
        
        mock_cache_manager.set.assert_called_once_with(client.rate_key, 1, ttl=client.rate_window)

@pytest.mark.asyncio
class TestRealEstateAPIClient:
    """Tests for the RealEstateAPIClient."""

    @pytest.fixture
    def client(self, mock_cache_manager):
        """Fixture for a RealEstateAPIClient instance with a mock cache manager."""
        with patch('reagent.services.external_apis.realestate_client.get_settings') as mock_get_settings:
            mock_get_settings.return_value.apis.rea_api_key = "test_key"
            mock_get_settings.return_value.apis.rea_rate_limit = 1000
            client = RealEstateAPIClient()
            client.cache_manager = mock_cache_manager
            client.session = MagicMock()
            return client

    async def test_etag_caching_flow(self, client, mock_cache_manager):
        """Test the ETag caching and retrieval flow."""
        endpoint = "listings/residential/_search"
        params = {"localities": ["2000"]}
        cache_key = "realestate_search:test"
        
        # 1. First request (cache miss)
        mock_cache_manager.get.side_effect = [
            None,  # for cache_key
            0,     # for rate_key in _check_rate_limit
            0,     # for rate_key in _increment_rate_counter
        ]
        
        mock_response_1 = AsyncMock()
        mock_response_1.status = 200
        mock_response_1.headers = {"ETag": "etag-abc"}
        mock_response_1.json.return_value = {"data": "rea_data"}
        
        client.session.request.return_value.__aenter__.return_value = mock_response_1
        
        result_1 = await client._make_request("GET", endpoint, params, cache_key=cache_key)
        assert result_1 == {"data": "rea_data"}
        mock_cache_manager.set.assert_any_call(
            cache_key, {"data": {"data": "rea_data"}, "etag": "etag-abc"}, ttl=client.cache_ttl
        )

        # 2. Second request (cache hit, 304 Not Modified)
        mock_cache_manager.reset_mock()
        mock_cache_manager.get.side_effect = [
            {"data": {"data": "rea_data"}, "etag": "etag-abc"}, # for cache_key
            1, # for rate_key in _check_rate_limit
            1, # for rate_key in _increment_rate_counter
        ]
        
        mock_response_2 = AsyncMock()
        mock_response_2.status = 304
        client.session.request.return_value.__aenter__.return_value = mock_response_2
        
        result_2 = await client._make_request("GET", endpoint, params, cache_key=cache_key)
        assert result_2 == {"data": "rea_data"}
        mock_cache_manager.set.assert_called_once_with(client.rate_key, 2, ttl=client.rate_window)

    async def test_etag_cache_update(self, client, mock_cache_manager):
        """Test that the cache is updated when the ETag changes."""
        endpoint = "listings/residential/_search"
        params = {"localities": ["2000"]}
        cache_key = "realestate_search:test_update"

        # 1. Initial request, cache populated
        mock_cache_manager.get.side_effect = [None, 0, 0]
        mock_response_1 = AsyncMock()
        mock_response_1.status = 200
        mock_response_1.headers = {"ETag": "etag-abc"}
        mock_response_1.json.return_value = {"data": "rea_data"}
        client.session.request.return_value.__aenter__.return_value = mock_response_1
        await client._make_request("GET", endpoint, params, cache_key=cache_key)

        # 2. Second request, ETag mismatch, new data returned
        mock_cache_manager.reset_mock()
        mock_cache_manager.get.side_effect = [
            {"data": {"data": "rea_data"}, "etag": "etag-abc"},
            1,
            1
        ]
        mock_response_2 = AsyncMock()
        mock_response_2.status = 200
        mock_response_2.headers = {"ETag": "etag-def"}
        mock_response_2.json.return_value = {"data": "updated_rea_data"}
        client.session.request.return_value.__aenter__.return_value = mock_response_2

        result = await client._make_request("GET", endpoint, params, cache_key=cache_key)
        assert result == {"data": "updated_rea_data"}
        mock_cache_manager.set.assert_any_call(
            cache_key, {"data": {"data": "updated_rea_data"}, "etag": "etag-def"}, ttl=client.cache_ttl
        )

    async def test_cache_miss_server_error(self, client, mock_cache_manager):
        """Test that a server error on a cache miss is handled correctly."""
        endpoint = "listings/residential/_search"
        params = {"localities": ["2000"]}
        cache_key = "realestate_search:test_error"

        # 1. First request (cache miss, server error)
        mock_cache_manager.get.side_effect = [None, 0, 0]
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Internal Server Error"
        client.session.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="API request failed: 500 - Internal Server Error"):
            await client._make_request("GET", endpoint, params, cache_key=cache_key)
        
        mock_cache_manager.set.assert_called_once_with(client.rate_key, 1, ttl=client.rate_window)
