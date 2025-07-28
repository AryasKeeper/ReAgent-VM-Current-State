"""
ReAgent Sydney - RealEstate.com.au API Client

Production-ready client for RealEstate.com.au API with rate limiting,
caching, and error handling.
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin, urlencode
import structlog

from reagent_sydney.core.cache.redis_client import get_cache_manager
from reagent_sydney.config.settings import get_settings
from reagent_sydney.utils.validation import validate_postcode


logger = structlog.get_logger(__name__)


class RealEstateAPIError(Exception):
    """Base exception for RealEstate API errors."""
    pass


class RealEstateRateLimitError(RealEstateAPIError):
    """Raised when API rate limit is exceeded."""
    pass


class RealEstateAuthenticationError(RealEstateAPIError):
    """Raised when API authentication fails."""
    pass


class RealEstateDataError(RealEstateAPIError):
    """Raised when API returns malformed data."""
    pass


class RealEstateAPIClient:
    """
    Production-ready RealEstate.com.au API client with comprehensive
    rate limiting, caching, and error handling.
    """
    
    BASE_URL = "https://services.realestate.com.au"
    API_VERSION = "v1"
    
    # Sydney Metro postcodes (2000-2999)
    SYDNEY_POSTCODES = list(range(2000, 3000))
    
    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = 3600):
        """
        Initialize RealEstate API client.
        
        Args:
            api_key: RealEstate API key (from settings if not provided)
            cache_ttl: Cache TTL in seconds (default 1 hour)
        """
        self.settings = get_settings()
        self.api_key = api_key or self.settings.apis.rea_api_key
        self.cache_ttl = cache_ttl
        self.cache_manager = get_cache_manager()
        
        if not self.api_key:
            raise RealEstateAuthenticationError("RealEstate API key is required")
        
        # Rate limiting
        self.rate_limit = self.settings.apis.rea_rate_limit
        self.rate_window = 24 * 3600  # 24 hours
        self.rate_key = "realestate_api_calls"
        
        # HTTP session configuration
        self.session_config = {
            "timeout": aiohttp.ClientTimeout(total=30),
            "headers": {
                "Authorization": f"Bearer {self.api_key}",
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
                "RealEstate API rate limit exceeded",
                current_calls=current_calls,
                rate_limit=self.rate_limit
            )
            raise RealEstateRateLimitError(
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
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        cache_key: Optional[str] = None,
        cache_ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to RealEstate API with error handling and caching.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            cache_key: Cache key for response caching
            cache_ttl: Cache TTL override
            
        Returns:
            API response data
            
        Raises:
            RealEstateAPIError: Various API-related errors
        """
        # Check cache first
        if cache_key and method.upper() == "GET":
            cached_response = await self.cache_manager.get(cache_key)
            if cached_response:
                logger.debug("RealEstate API cache hit", cache_key=cache_key)
                return cached_response
        
        # Check rate limit
        await self._check_rate_limit()
        
        # Build URL
        url = urljoin(f"{self.BASE_URL}/{self.API_VERSION}/", endpoint.lstrip('/'))
        
        try:
            logger.debug(
                "Making RealEstate API request",
                method=method,
                url=url,
                params=params
            )
            
            async with self.session.request(method, url, params=params) as response:
                # Increment rate counter
                await self._increment_rate_counter()
                
                # Handle HTTP errors
                if response.status == 401:
                    raise RealEstateAuthenticationError("Invalid API key")
                elif response.status == 429:
                    raise RealEstateRateLimitError("Rate limit exceeded")
                elif response.status >= 400:
                    error_text = await response.text()
                    raise RealEstateAPIError(
                        f"API request failed: {response.status} - {error_text}"
                    )
                
                # Parse response
                try:
                    data = await response.json()
                except Exception as e:
                    raise RealEstateDataError(f"Failed to parse API response: {e}")
                
                # Cache successful response
                if cache_key and response.status == 200:
                    ttl = cache_ttl or self.cache_ttl
                    await self.cache_manager.set(cache_key, data, ttl=ttl)
                    logger.debug("RealEstate API response cached", cache_key=cache_key)
                
                return data
                
        except aiohttp.ClientError as e:
            raise RealEstateAPIError(f"HTTP client error: {e}")
        except asyncio.TimeoutError:
            raise RealEstateAPIError("API request timeout")
    
    async def search_listings(
        self,
        postcodes: Optional[List[str]] = None,
        property_types: Optional[List[str]] = None,
        listing_type: str = "buy",
        max_results: int = 100,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Search property listings with filters.
        
        Args:
            postcodes: List of postcodes to search (defaults to Sydney)
            property_types: Property types to include
            listing_type: "buy" or "rent"
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
            "channel": listing_type,
            "pageSize": min(max_results, 200),  # API limit
            "page": page,
            "localities": postcodes
        }
        
        if property_types:
            # Map property types to RealEstate format
            rea_types = []
            for prop_type in property_types:
                if prop_type.lower() in ["house", "home"]:
                    rea_types.append("house")
                elif prop_type.lower() in ["unit", "apartment"]:
                    rea_types.append("unit")
                elif prop_type.lower() in ["townhouse", "terrace"]:
                    rea_types.append("townhouse")
                else:
                    rea_types.append(prop_type.lower())
            
            params["propertyTypes"] = rea_types
        
        # Create cache key
        cache_key = f"realestate_search:{hash(str(sorted(params.items())))}"
        
        # Make request
        response = await self._make_request(
            "GET",
            "listings/residential/_search",
            params=params,
            cache_key=cache_key,
            cache_ttl=1800  # 30 minutes for search results
        )
        
        logger.info(
            "RealEstate search completed",
            postcodes=postcodes,
            listing_type=listing_type,
            results_count=len(response.get("tieredResults", [{}])[0].get("results", []))
        )
        
        return response
    
    async def get_listing_details(self, listing_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific listing.
        
        Args:
            listing_id: RealEstate listing ID
            
        Returns:
            Detailed listing information
        """
        cache_key = f"realestate_listing:{listing_id}"
        
        response = await self._make_request(
            "GET",
            f"listings/{listing_id}",
            cache_key=cache_key,
            cache_ttl=3600  # 1 hour for listing details
        )
        
        logger.debug("RealEstate listing details retrieved", listing_id=listing_id)
        return response
    
    async def get_suburb_profile(self, suburb: str, state: str = "nsw") -> Dict[str, Any]:
        """
        Get suburb profile and statistics.
        
        Args:
            suburb: Suburb name
            state: State (default nsw)
            
        Returns:
            Suburb profile data
        """
        params = {"suburb": suburb, "state": state}
        cache_key = f"realestate_suburb_profile:{suburb}:{state}"
        
        response = await self._make_request(
            "GET",
            f"neighbourhoods/{state}/{suburb}",
            params=params,
            cache_key=cache_key,
            cache_ttl=86400  # 24 hours for suburb stats
        )
        
        logger.debug("RealEstate suburb profile retrieved", suburb=suburb, state=state)
        return response
    
    def normalize_property_data(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize RealEstate API response to standard property format.
        
        Args:
            listing_data: Raw RealEstate API listing data
            
        Returns:
            Normalized property data compatible with our models
        """
        try:
            # Extract basic information
            normalized = {
                "listing_id": str(listing_data.get("id", "")),
                "source": "realestate",
                "source_url": listing_data.get("_links", {}).get("canonical", {}).get("href", ""),
                "source_data": listing_data,
                
                # Property details
                "title": listing_data.get("headline", ""),
                "description": listing_data.get("description", ""),
                "property_type": listing_data.get("propertyType", "").title(),
                
                # Location
                "address_line_1": listing_data.get("address", {}).get("streetAddress", ""),
                "suburb": listing_data.get("address", {}).get("suburb", ""),
                "postcode": listing_data.get("address", {}).get("postcode", ""),
                "state": listing_data.get("address", {}).get("state", "NSW"),
                "country": "Australia",
                
                # Geographic coordinates
                "latitude": listing_data.get("address", {}).get("geo", {}).get("lat"),
                "longitude": listing_data.get("address", {}).get("geo", {}).get("lng"),
                
                # Property features
                "bedrooms": listing_data.get("generalFeatures", {}).get("bedrooms"),
                "bathrooms": listing_data.get("generalFeatures", {}).get("bathrooms"),
                "car_spaces": listing_data.get("generalFeatures", {}).get("parkingSpaces"),
                "land_size": listing_data.get("landDetails", {}).get("area"),
                "building_size": listing_data.get("buildingDetails", {}).get("area"),
                
                # Pricing
                "listing_type": self._map_listing_type(listing_data.get("channel", "")),
                "listing_status": "active",  # RealEstate only shows active listings
                
                # Features and media
                "features": self._extract_features(listing_data),
                "image_urls": [
                    media.get("uri", "") 
                    for media in listing_data.get("media", []) 
                    if media.get("type") == "photo"
                ],
                
                # Timestamps
                "first_listed_date": self._parse_date(
                    listing_data.get("listingDetails", {}).get("listedDate")
                ),
                "last_updated_source": datetime.utcnow()
            }
            
            # Handle pricing
            price_details = listing_data.get("priceDetails", {})
            if price_details:
                normalized["price_display"] = price_details.get("displayPrice", "")
                
                # Try to extract numeric price
                price = price_details.get("price")
                if price and isinstance(price, (int, float)):
                    normalized["price"] = Decimal(str(price))
                elif price_details.get("priceFrom"):
                    normalized["price"] = Decimal(str(price_details["priceFrom"]))
            
            # Handle inspection times
            inspection_times = listing_data.get("inspectionDetails", {}).get("inspections", [])
            if inspection_times:
                normalized["next_inspection"] = self._parse_date(
                    inspection_times[0].get("openingTime")
                )
            
            # Agent information
            agent_data = listing_data.get("advertiser", {})
            if agent_data:
                normalized["agent_info"] = {
                    "name": agent_data.get("name", ""),
                    "phone": agent_data.get("phoneNumber", ""),
                    "email": agent_data.get("email", ""),
                    "agency": agent_data.get("agencyName", "")
                }
            
            return normalized
            
        except Exception as e:
            logger.error(
                "Failed to normalize RealEstate property data",
                listing_id=listing_data.get("id"),
                error=str(e)
            )
            raise RealEstateDataError(f"Data normalization failed: {e}")
    
    def _map_listing_type(self, channel: str) -> str:
        """Map RealEstate channel to our listing type."""
        mapping = {
            "buy": "sale",
            "rent": "rent",
            "sold": "sale",
            "leased": "rent"
        }
        return mapping.get(channel.lower(), channel.lower())
    
    def _extract_features(self, listing_data: Dict[str, Any]) -> List[str]:
        """Extract property features from various sections."""
        features = []
        
        # General features
        general = listing_data.get("generalFeatures", {})
        for key, value in general.items():
            if value and key not in ["bedrooms", "bathrooms", "parkingSpaces"]:
                if isinstance(value, bool) and value:
                    features.append(key.replace("_", " ").title())
                elif isinstance(value, str):
                    features.append(value)
        
        # Property features
        prop_features = listing_data.get("propertyFeatures", [])
        if isinstance(prop_features, list):
            features.extend(prop_features)
        
        return list(set(features))  # Remove duplicates
    
    def _parse_date(self, date_string: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object."""
        if not date_string:
            return None
        
        try:
            # Handle common RealEstate date formats
            if "T" in date_string:
                return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            else:
                return datetime.strptime(date_string, "%Y-%m-%d")
        except (ValueError, TypeError):
            logger.warning("Failed to parse date", date_string=date_string)
            return None
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Check RealEstate API health and connectivity.
        
        Returns:
            Health status information
        """
        try:
            # Simple test request
            response = await self._make_request(
                "GET",
                "listings/residential/_search",
                params={"pageSize": 1, "localities": ["2000"]}
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
    from reagent_sydney.config.settings import settings
    return settings