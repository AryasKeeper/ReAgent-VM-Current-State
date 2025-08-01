"""
ReAgent Sydney - Domain.com.au API Client

Production-ready client for Domain.com.au API with rate limiting,
caching, and error handling.
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin, urlencode
from pybreaker import CircuitBreaker

from reagent.core.cache.redis_client import get_cache_manager
from reagent.core.config import get_settings
from reagent.utils.logging import get_logger
from reagent.utils.validation import validate_postcode


from pybreaker import CircuitBreaker

logger = get_logger(__name__)

domain_api_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)


from reagent.core.exceptions import (
    ExternalAPIError as DomainAPIError,
    APIRateLimitError as DomainRateLimitError,
    AuthenticationError as DomainAuthenticationError,
    DataIntegrityError as DomainDataError
)


class DomainAPIClient:
    """
    Production-ready Domain.com.au API client with comprehensive
    rate limiting, caching, and error handling.
    """
    
    BASE_URL = "https://api.domain.com.au"
    API_VERSION = "v1"
    
    # Sydney Metro postcodes (2000-2999)
    SYDNEY_POSTCODES = list(range(2000, 3000))
    
    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = 3600):
        """
        Initialize Domain API client.
        
        Args:
            api_key: Domain API key (from settings if not provided)
            cache_ttl: Cache TTL in seconds (default 1 hour)
        """
        self.settings = get_settings()
        self.api_key = api_key or self.settings.apis.domain_api_key
        self.cache_ttl = cache_ttl
        self.cache_manager = get_cache_manager()
        
        if not self.api_key:
            raise DomainAuthenticationError("Domain API key is required")
        
        # Rate limiting
        self.rate_limit = self.settings.apis.domain_rate_limit
        self.rate_window = 24 * 3600  # 24 hours
        self.rate_key = "domain_api_calls"
        
        # HTTP session configuration
        self.session_config = {
            "timeout": aiohttp.ClientTimeout(total=30),
            "headers": {
                "X-Api-Key": self.api_key,
                "User-Agent": f"ReAgent-Sydney/{self.settings.version}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        }
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(**self.session_config)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if hasattr(self, 'session'):
            await self.session.close()
    
    async def _check_rate_limit(self) -> None:
        """Check if we're within rate limits."""
        current_calls = await self.cache_manager.get(self.rate_key) or 0
        
        if current_calls >= self.rate_limit:
            logger.warning(
                "Domain API rate limit exceeded",
                current_calls=current_calls,
                rate_limit=self.rate_limit
            )
            raise DomainRateLimitError(
                f"Rate limit exceeded: {current_calls}/{self.rate_limit} calls per day"
            )
    
    async def _increment_rate_counter(self) -> None:
        """Increment the rate limiting counter."""
        current_calls = await self.cache_manager.get(self.rate_key) or 0
        await self.cache_manager.set(
            self.rate_key, 
            current_calls + 1, 
            ttl=self.rate_window
        )
    
    @track_external_api_call(api_name="domain", endpoint="listings/residential/_search")
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        cache_key: Optional[str] = None,
        cache_ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Domain API with error handling and caching.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            cache_key: Cache key for response caching
            cache_ttl: Cache TTL override

        Returns:
            API response data

        Raises:
            DomainAPIError: Various API-related errors
        """
        headers = self.session_config["headers"].copy()
        cached_data = None
        
        # Check cache first
        if cache_key and method.upper() == "GET":
            cached_item = await self.cache_manager.get(cache_key)
            if cached_item:
                logger.debug("Domain API cache hit", cache_key=cache_key)
                cached_data = cached_item.get("data")
                etag = cached_item.get("etag")
                if etag:
                    headers["If-None-Match"] = etag
                
                # Track cache hit
                track_external_api_call(api_name="domain", endpoint=endpoint, cache_hit=True)

        # If we have cached data and aren't checking for updates, return it
        if cached_data and "If-None-Match" not in headers:
            return cached_data

        # Check rate limit before making a request
        await self._check_rate_limit()

        # Build URL
        url = urljoin(f"{self.BASE_URL}/{self.API_VERSION}/", endpoint.lstrip('/'))

        try:
            logger.debug(
                "Making Domain API request",
                method=method,
                url=url,
                params=params,
                headers=headers
            )

            async with self.session.request(method, url, params=params, headers=headers) as response:
                # Increment rate counter after the request is made
                await self._increment_rate_counter()

                # If content is not modified, return cached data
                if response.status == 304:
                    logger.debug("ETag match, returning cached data", cache_key=cache_key)
                    if cached_data:
                        # Track cache hit
                        track_external_api_call(api_name="domain", endpoint=endpoint, cache_hit=True)
                        return cached_data
                    # If cache expired locally but not on server, we must refetch
                    logger.warning("304 received but no cached data, refetching", cache_key=cache_key)
                    # To refetch, we remove the If-None-Match header and retry
                    del headers["If-None-Match"]
                    async with self.session.request(method, url, params=params, headers=headers) as refetch_response:
                        return await self._handle_response(refetch_response, cache_key, cache_ttl)


                return await self._handle_response(response, cache_key, cache_ttl)

        except aiohttp.ClientError as e:
            raise DomainAPIError(f"HTTP client error: {e}")
        except asyncio.TimeoutError:
            raise DomainAPIError("API request timeout")

    async def _handle_response(
        self, 
        response: aiohttp.ClientResponse, 
        cache_key: Optional[str], 
        cache_ttl: Optional[int]
    ) -> Dict[str, Any]:
        """Helper to process the HTTP response."""
        # Handle HTTP errors
        if response.status == 401:
            raise DomainAuthenticationError("Invalid API key")
        elif response.status == 429:
            raise DomainRateLimitError("Rate limit exceeded")
        elif response.status >= 400:
            error_text = await response.text()
            raise DomainAPIError(
                f"API request failed: {response.status} - {error_text}"
            )

        # Parse response
        try:
            data = await response.json()
        except Exception as e:
            raise DomainDataError(f"Failed to parse API response: {e}")

        # Cache successful response
        if cache_key and response.status == 200:
            ttl = cache_ttl or self.cache_ttl
            etag = response.headers.get("ETag")
            cache_item = {"data": data, "etag": etag}
            await self.cache_manager.set(cache_key, cache_item, ttl=ttl)
            logger.debug("Domain API response cached", cache_key=cache_key, etag=etag)

        return data
    
    async def search_listings(
        self,
        postcodes: Optional[List[str]] = None,
        property_types: Optional[List[str]] = None,
        listing_type: str = "Sale",
        max_results: int = 100,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Search property listings with filters.
        
        Args:
            postcodes: List of postcodes to search (defaults to Sydney)
            property_types: Property types to include
            listing_type: "Sale" or "Rent"
            max_results: Maximum results per page
            page: Page number
            
        Returns:
            Search results with listings and metadata
        """
        # Default to Sydney postcodes
        if not postcodes:
            postcodes = [str(pc) for pc in self.SYDNEY_POSTCODES]
        
        # Validate postcodes
        for postcode in postcodes:
            if not validate_postcode(postcode):
                raise ValueError(f"Invalid postcode: {postcode}")
        
        # Build search parameters
        params = {
            "listingType": listing_type,
            "pageSize": min(max_results, 200),  # API limit
            "page": page,
            "postCodes": ",".join(postcodes)
        }
        
        if property_types:
            params["propertyTypes"] = ",".join(property_types)
        
        # Create cache key
        cache_key = f"domain_search:{hash(str(sorted(params.items())))}"
        
        # Make request
        response = await self._make_request(
            "GET",
            "listings/residential/_search",
            params=params,
            cache_key=cache_key,
            cache_ttl=1800  # 30 minutes for search results
        )
        
        logger.info(
            "Domain search completed",
            postcodes=postcodes,
            listing_type=listing_type,
            results_count=len(response.get("listings", []))
        )
        
        return response
    
    async def get_listing_details(self, listing_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific listing.
        
        Args:
            listing_id: Domain listing ID
            
        Returns:
            Detailed listing information
        """
        cache_key = f"domain_listing:{listing_id}"
        
        response = await self._make_request(
            "GET",
            f"listings/{listing_id}",
            cache_key=cache_key,
            cache_ttl=3600  # 1 hour for listing details
        )
        
        logger.debug("Domain listing details retrieved", listing_id=listing_id)
        return response
    
    async def get_suburb_performance(self, suburb: str, state: str = "NSW") -> Dict[str, Any]:
        """
        Get suburb performance statistics.
        
        Args:
            suburb: Suburb name
            state: State (default NSW)
            
        Returns:
            Suburb performance data
        """
        params = {"suburb": suburb, "state": state}
        cache_key = f"domain_suburb_performance:{suburb}:{state}"
        
        response = await self._make_request(
            "GET",
            "suburbPerformanceStatistics",
            params=params,
            cache_key=cache_key,
            cache_ttl=86400  # 24 hours for suburb stats
        )
        
        logger.debug("Domain suburb performance retrieved", suburb=suburb, state=state)
        return response
    
    async def get_price_estimate(
        self,
        address: str,
        property_type: str,
        bedrooms: int,
        bathrooms: int
    ) -> Dict[str, Any]:
        """
        Get automated price estimate for a property.
        
        Args:
            address: Property address
            property_type: Property type
            bedrooms: Number of bedrooms
            bathrooms: Number of bathrooms
            
        Returns:
            Price estimate data
        """
        params = {
            "address": address,
            "propertyType": property_type,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms
        }
        
        cache_key = f"domain_price_estimate:{hash(str(sorted(params.items())))}"
        
        response = await self._make_request(
            "GET",
            "properties/_priceEstimate",
            params=params,
            cache_key=cache_key,
            cache_ttl=21600  # 6 hours for price estimates
        )
        
        logger.debug("Domain price estimate retrieved", address=address)
        return response
    
    def normalize_property_data(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Domain API response to standard property format.
        
        Args:
            listing_data: Raw Domain API listing data
            
        Returns:
            Normalized property data compatible with our models
        """
        try:
            # Extract basic information
            normalized = {
                "listing_id": str(listing_data.get("id", "")),
                "source": "domain",
                "source_url": listing_data.get("listing", {}).get("listingSlug", ""),
                "source_data": listing_data,
                
                # Property details
                "title": listing_data.get("headline", ""),
                "description": listing_data.get("description", ""),
                "property_type": listing_data.get("propertyType", "").title(),
                
                # Location
                "address_line_1": listing_data.get("propertyDetails", {}).get("displayableAddress", ""),
                "suburb": listing_data.get("propertyDetails", {}).get("suburb", ""),
                "postcode": listing_data.get("propertyDetails", {}).get("postcode", ""),
                "state": listing_data.get("propertyDetails", {}).get("state", "NSW"),
                "country": "Australia",
                
                # Geographic coordinates
                "latitude": listing_data.get("propertyDetails", {}).get("latitude"),
                "longitude": listing_data.get("propertyDetails", {}).get("longitude"),
                
                # Property features
                "bedrooms": listing_data.get("propertyDetails", {}).get("bedrooms"),
                "bathrooms": listing_data.get("propertyDetails", {}).get("bathrooms"),
                "car_spaces": listing_data.get("propertyDetails", {}).get("carspaces"),
                "land_size": listing_data.get("propertyDetails", {}).get("landArea"),
                "building_size": listing_data.get("propertyDetails", {}).get("buildingArea"),
                
                # Pricing
                "listing_type": listing_data.get("listing", {}).get("listingType", "").lower(),
                "listing_status": "active",  # Domain only shows active listings
                
                # Features and media
                "features": listing_data.get("propertyDetails", {}).get("features", []),
                "image_urls": [
                    img.get("fullUrl", "") 
                    for img in listing_data.get("media", []) 
                    if img.get("category") == "Image"
                ],
                
                # Timestamps
                "first_listed_date": self._parse_date(
                    listing_data.get("listing", {}).get("listingSlug")
                ),
                "last_updated_source": datetime.utcnow()
            }
            
            # Handle pricing based on listing type
            price_details = listing_data.get("priceDetails", {})
            if price_details:
                normalized["price_display"] = price_details.get("displayPrice", "")
                
                # Try to extract numeric price
                price = price_details.get("price")
                if price and isinstance(price, (int, float)):
                    normalized["price"] = Decimal(str(price))
            
            # Handle auction date
            auction_date = listing_data.get("listing", {}).get("auctionDate")
            if auction_date:
                normalized["auction_date"] = self._parse_date(auction_date)
            
            # Agent information
            agent_data = listing_data.get("advertiser", {}).get("contacts", [])
            if agent_data:
                agent = agent_data[0]  # Primary agent
                normalized["agent_info"] = {
                    "name": agent.get("name", ""),
                    "phone": agent.get("phoneNumber", ""),
                    "email": agent.get("emailAddress", ""),
                    "image_url": agent.get("imageUrl", "")
                }
            
            return normalized
            
        except Exception as e:
            logger.error(
                "Failed to normalize Domain property data",
                listing_id=listing_data.get("id"),
                error=str(e)
            )
            raise DomainDataError(f"Data normalization failed: {e}")
    
    def _parse_date(self, date_string: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_string:
            return None
        
        try:
            # Handle common Domain date formats
            if "T" in date_string:
                return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            else:
                return datetime.strptime(date_string, "%Y-%m-%d")
        except (ValueError, TypeError):
            logger.warning("Failed to parse date", date_string=date_string)
            return None
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Check Domain API health and connectivity.
        
        Returns:
            Health status information
        """
        try:
            # Simple test request
            response = await self._make_request(
                "GET",
                "listings/residential/_search",
                params={"pageSize": 1, "postCodes": "2000"}
            )
            
            return {
                "status": "healthy",
                "api_accessible": True,
                "rate_limit_remaining": self.rate_limit - (
                    await self.cache_manager.get(self.rate_key) or 0
                ),
                "last_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "api_accessible": False,
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }


def get_settings():
    """Get settings instance."""
    from reagent.core.config import settings
    return settings
