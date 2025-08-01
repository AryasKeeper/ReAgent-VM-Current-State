"""
CoreLogic (Cotality) API Client

OAuth2-based client for CoreLogic property data API.
"""

import asyncio
import base64
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

import httpx
import structlog
from pydantic import BaseModel, Field
from pybreaker import CircuitBreaker

from pybreaker import CircuitBreaker

from reagent.core.config import get_settings
from reagent.core.exceptions import ExternalAPIError, ConfigurationError

corelogic_api_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)


class CoreLogicTokenResponse(BaseModel):
    """CoreLogic OAuth2 token response."""
    access_token: str
    token_type: str
    expires_in: int
    
    @property
    def expires_at(self) -> datetime:
        """Calculate token expiration time."""
        return datetime.utcnow() + timedelta(seconds=self.expires_in - 60)  # 60s buffer


class CoreLogicPropertySuggestion(BaseModel):
    """CoreLogic property suggestion response."""
    council_area_id: int = Field(alias="councilAreaId")
    country_id: int = Field(alias="countryId")
    is_active_property: bool = Field(alias="isActiveProperty")
    is_body_corporate: bool = Field(alias="isBodyCorporate")
    is_unit: bool = Field(alias="isUnit")
    locality_id: int = Field(alias="localityId")
    postcode_id: int = Field(alias="postcodeId")
    property_id: int = Field(alias="propertyId")
    state_id: int = Field(alias="stateId")
    street_id: int = Field(alias="streetId")
    suggestion: str
    suggestion_type: str = Field(alias="suggestionType")


class CoreLogicClient:
    """
    CoreLogic (Cotality) API client with OAuth2 authentication.
    
    Handles token management, rate limiting, and API requests.
    """
    
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        """
        Initialize CoreLogic API client.
        
        Args:
            client_id: CoreLogic API client ID (from settings if not provided)
            client_secret: CoreLogic API client secret (from settings if not provided)
        """
        self.settings = get_settings()
        self.logger = structlog.get_logger("corelogic.client")
        
        self.client_id = client_id or self.settings.apis.corelogic_api_key
        self.client_secret = client_secret or self.settings.apis.corelogic_secret
        self.base_url = self.settings.apis.corelogic_base_url
        
        if not self.client_id or not self.client_secret:
            raise ConfigurationError("CoreLogic API credentials not configured")
        
        # OAuth2 endpoints
        self.token_url = f"{self.base_url}/access/as/token.oauth2"
        self.legacy_token_url = f"{self.base_url}/access/oauth/token"
        
        # API endpoints
        self.api_base = f"{self.base_url.replace('api.corelogic.asia', 'api-sbox.corelogic.asia')}/property/au/v2"
        
        # Session and token management
        self.http_client: Optional[httpx.AsyncClient] = None
        self._current_token: Optional[CoreLogicTokenResponse] = None
        self._token_lock = asyncio.Lock()
        
        # Rate limiting
        self.rate_limit = self.settings.apis.corelogic_rate_limit
        self.request_count = 0
        self.rate_limit_reset = datetime.utcnow() + timedelta(days=1)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self) -> None:
        """Initialize HTTP client and authenticate."""
        if self.http_client is None:
            timeout = httpx.Timeout(30.0, connect=10.0)
            self.http_client = httpx.AsyncClient(
                timeout=timeout,
                headers={
                    "User-Agent": "ReAgent-Sydney/1.0.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        
        # Get initial access token
        await self._ensure_valid_token()
        
        self.logger.info("CoreLogic API client connected",
                        base_url=self.base_url,
                        api_base=self.api_base)
    
    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        
        self.logger.info("CoreLogic API client disconnected")
    
    async def _get_access_token(self, use_legacy: bool = False) -> CoreLogicTokenResponse:
        """
        Get OAuth2 access token from CoreLogic.
        
        Args:
            use_legacy: Use legacy token endpoint for PSX APIs
            
        Returns:
            Token response with access token and expiration
        """
        # Create Basic Auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        token_url = self.legacy_token_url if use_legacy else self.token_url
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Length": "0"
        }
        
        params = {"grant_type": "client_credentials"}
        
        try:
            response = await self.http_client.post(
                token_url,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            token_data = response.json()
            token_response = CoreLogicTokenResponse(**token_data)
            
            self.logger.info("CoreLogic access token obtained",
                           expires_in=token_response.expires_in,
                           legacy=use_legacy)
            
            return token_response
            
        except httpx.HTTPStatusError as e:
            self.logger.error("Failed to get CoreLogic access token",
                            status_code=e.response.status_code,
                            response=e.response.text)
            raise ExternalAPIError(f"CoreLogic token request failed: {e.response.status_code}")
        except Exception as e:
            self.logger.error("CoreLogic token request error", error=str(e))
            raise ExternalAPIError(f"CoreLogic token request error: {e}")
    
    async def _ensure_valid_token(self) -> str:
        """
        Ensure we have a valid access token, refreshing if necessary.
        
        Returns:
            Valid access token
        """
        async with self._token_lock:
            # Check if current token is still valid
            if (self._current_token and 
                datetime.utcnow() < self._current_token.expires_at):
                return self._current_token.access_token
            
            # Get new token
            self._current_token = await self._get_access_token()
            return self._current_token.access_token
    
        @corelogic_api_breaker
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        use_legacy_token: bool = False
    ) -> Dict[str, Any]:
        """
        Make authenticated request to CoreLogic API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to api_base)
            params: Query parameters
            json_data: JSON request body
            use_legacy_token: Use legacy token for PSX APIs
            
        Returns:
            API response data
        """
        if not self.http_client:
            raise RuntimeError("Client not connected. Call connect() first.")
        
        # Rate limiting check
        if self.request_count >= self.rate_limit:
            if datetime.utcnow() < self.rate_limit_reset:
                raise ExternalAPIError("CoreLogic API rate limit exceeded")
            else:
                # Reset rate limit counter
                self.request_count = 0
                self.rate_limit_reset = datetime.utcnow() + timedelta(days=1)
        
        # Get valid access token
        if use_legacy_token:
            # For PSX APIs, get legacy token
            token_response = await self._get_access_token(use_legacy=True)
            access_token = token_response.access_token
        else:
            access_token = await self._ensure_valid_token()
        
        # Prepare request
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        try:
            response = await self.http_client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            
            # Update rate limiting
            self.request_count += 1
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            self.logger.error("CoreLogic API request failed",
                            method=method,
                            endpoint=endpoint,
                            status_code=e.response.status_code,
                            response=e.response.text)
            
            if e.response.status_code == 401:
                # Token might be expired, clear it
                self._current_token = None
                raise ExternalAPIError("CoreLogic API authentication failed")
            elif e.response.status_code == 429:
                raise ExternalAPIError("CoreLogic API rate limit exceeded")
            else:
                raise ExternalAPIError(f"CoreLogic API error: {e.response.status_code}")
                
        except Exception as e:
            self.logger.error("CoreLogic API request error",
                            method=method,
                            endpoint=endpoint,
                            error=str(e))
            raise ExternalAPIError(f"CoreLogic API request failed: {e}")
    
    async def suggest_properties(self, query: str) -> List[CoreLogicPropertySuggestion]:
        """
        Get property suggestions for a search query.
        
        Args:
            query: Property search query (address, suburb, etc.)
            
        Returns:
            List of property suggestions
        """
        params = {"q": query}
        
        response_data = await self._make_request("GET", "suggest.json", params=params)
        
        suggestions = []
        for suggestion_data in response_data.get("suggestions", []):
            try:
                suggestion = CoreLogicPropertySuggestion(**suggestion_data)
                suggestions.append(suggestion)
            except Exception as e:
                self.logger.warning("Failed to parse property suggestion",
                                  suggestion=suggestion_data,
                                  error=str(e))
        
        self.logger.info("CoreLogic property suggestions retrieved",
                        query=query,
                        count=len(suggestions))
        
        return suggestions
    
    async def get_property_details(self, property_id: int) -> Dict[str, Any]:
        """
        Get detailed property information.
        
        Args:
            property_id: CoreLogic property ID
            
        Returns:
            Property details
        """
        endpoint = f"property/{property_id}.json"
        
        response_data = await self._make_request("GET", endpoint)
        
        self.logger.info("CoreLogic property details retrieved",
                        property_id=property_id)
        
        return response_data
    
    async def health_check(self) -> bool:
        """
        Check if CoreLogic API is accessible.
        
        Returns:
            True if API is healthy
        """
        try:
            # Simple test query
            await self.suggest_properties("Sydney NSW")
            return True
        except Exception as e:
            self.logger.error("CoreLogic API health check failed", error=str(e))
            return False


# Global client instance
_corelogic_client: Optional[CoreLogicClient] = None


async def get_corelogic_client() -> CoreLogicClient:
    """Get or create global CoreLogic client instance."""
    global _corelogic_client
    
    if _corelogic_client is None:
        _corelogic_client = CoreLogicClient()
        await _corelogic_client.connect()
    
    return _corelogic_client


async def close_corelogic_client() -> None:
    """Close global CoreLogic client."""
    global _corelogic_client
    
    if _corelogic_client:
        await _corelogic_client.disconnect()
        _corelogic_client = None
