"""
Integration tests for external API clients.

These tests are marked as 'external_api' and will only run if the
--run-external-api flag is provided. They require valid API keys
to be present in the environment.
"""

import pytest
import os
from reagent.services.external_apis.domain_client import DomainAPIClient
from reagent.services.external_apis.realestate_client import RealEstateAPIClient

pytestmark = pytest.mark.skip(reason="External API tests are disabled because valid API keys are not available.")

@pytest.mark.asyncio
class TestDomainAPIClientIntegration:
    """Integration tests for the DomainAPIClient."""

    @pytest.fixture
    def client(self):
        """Fixture for a DomainAPIClient instance."""
        return DomainAPIClient()

    async def test_search_listings(self, client):
        """Test that we can successfully search for listings."""
        async with client:
            results = await client.search_listings(postcodes=["2000"], max_results=1)
            assert "listings" in results
            assert len(results["listings"]) > 0

@pytest.mark.asyncio
class TestRealEstateAPIClientIntegration:
    """Integration tests for the RealEstateAPIClient."""

    @pytest.fixture
    def client(self):
        """Fixture for a RealEstateAPIClient instance."""
        return RealEstateAPIClient()

    async def test_search_listings(self, client):
        """Test that we can successfully search for listings."""
        async with client:
            results = await client.search_listings(postcodes=["2000"], max_results=1)
            assert "tieredResults" in results
            assert len(results["tieredResults"]) > 0
