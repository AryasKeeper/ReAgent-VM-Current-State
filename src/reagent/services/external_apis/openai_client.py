"""
ReAgent Sydney - OpenAI API Client

Production-ready client for OpenAI API with rate limiting,
caching, and error handling for market analysis generation.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import json
import structlog

import openai
from openai import AsyncOpenAI
from pybreaker import CircuitBreaker

from reagent.core.cache.redis_client import get_cache_manager
from reagent.core.config import get_settings


from pybreaker import CircuitBreaker

logger = structlog.get_logger(__name__)

openai_api_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)


from reagent.core.exceptions import (
    ExternalAPIError as OpenAIAPIError,
    APIRateLimitError as OpenAIRateLimitError,
    AuthenticationError as OpenAIAuthenticationError,
    ValidationError as OpenAITokenLimitError
)


class ReportGenerationError(Exception):
    """Raised when report generation fails."""
    pass


class OpenAIClient:
    """
    Production-ready OpenAI API client for ReAgent Sydney market analysis.
    
    Handles authentication, rate limiting, caching, and specialized
    real estate market analysis prompts.
    """
    
    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = 3600):
        """
        Initialize OpenAI API client.
        
        Args:
            api_key: OpenAI API key (from settings if not provided)
            cache_ttl: Cache TTL in seconds (default 1 hour)
        """
        self.settings = get_settings()
        self.api_key = api_key or self.settings.apis.openai_api_key
        self.cache_ttl = cache_ttl
        self.cache_manager = get_cache_manager()
        
        if not self.api_key:
            raise OpenAIAuthenticationError("OpenAI API key is required")
        
        # Initialize AsyncOpenAI client
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        # Rate limiting (OpenAI has different limits per model)
        self.rate_limits = {
            "gpt-4": {"rpm": 500, "tpm": 30000},  # requests/tokens per minute
            "gpt-3.5-turbo": {"rpm": 3500, "tpm": 90000}
        }
        
        # Request tracking for rate limiting
        self.request_history = []
        self.token_usage = {}
        
        @openai_api_breaker
    async def generate_market_analysis(
        self,
        market_data: Dict[str, Any],
        analysis_context: str,
        suburb: str,
        model: str = "gpt-4",
        max_tokens: int = 1500,
        temperature: float = 0.3
    ) -> str:
        """
        Generate comprehensive market analysis using OpenAI.
        
        Args:
            market_data: Real market data from CoreLogic/Domain
            analysis_context: Context for the analysis request
            suburb: Suburb name for analysis
            model: OpenAI model to use
            max_tokens: Maximum tokens in response
            temperature: Response creativity (0.0-1.0)
            
        Returns:
            Generated market analysis text
        """
        # Create cache key
        cache_key = f"openai_market_analysis:{suburb}:{hash(str(market_data))}"
        
        # Check cache first
        cached_analysis = await self.cache_manager.get(cache_key)
        if cached_analysis:
            logger.debug("OpenAI market analysis cache hit", suburb=suburb)
            return cached_analysis
        
        # Check rate limits
        await self._check_rate_limits(model)
        
        # Prepare specialized market analysis prompt
        prompt = self._create_market_analysis_prompt(market_data, analysis_context, suburb)
        
        try:
            logger.info(
                "Generating OpenAI market analysis",
                suburb=suburb,
                model=model,
                data_sources=list(market_data.keys())
            )
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Sydney real estate market analyst with 15+ years experience. Provide professional, data-driven insights based exclusively on the provided real market data."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9
            )
            
            # Extract analysis text
            analysis = response.choices[0].message.content.strip()
            
            # Track usage for rate limiting
            await self._track_request(model, response.usage)
            
            # Cache the result
            await self.cache_manager.set(cache_key, analysis, ttl=self.cache_ttl)
            
            logger.info(
                "OpenAI market analysis generated",
                suburb=suburb,
                tokens_used=response.usage.total_tokens,
                analysis_length=len(analysis)
            )
            
            return analysis
            
        except openai.RateLimitError as e:
            logger.error("OpenAI rate limit exceeded", error=str(e))
            raise OpenAIRateLimitError(f"Rate limit exceeded: {e}")
        except openai.AuthenticationError as e:
            logger.error("OpenAI authentication failed", error=str(e))
            raise OpenAIAuthenticationError(f"Authentication failed: {e}")
        except Exception as e:
            logger.error("OpenAI analysis generation failed", error=str(e), suburb=suburb)
            raise OpenAIAPIError(f"Analysis generation failed: {e}")
    
    async def generate_investment_analysis(
        self,
        property_data: Dict[str, Any],
        financial_data: Dict[str, Any],
        market_context: str,
        model: str = "gpt-4",
        max_tokens: int = 1200
    ) -> str:
        """
        Generate investment analysis using OpenAI.
        
        Args:
            property_data: Property details and features
            financial_data: Financial metrics and calculations
            market_context: Market context for investment analysis
            model: OpenAI model to use
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated investment analysis text
        """
        cache_key = f"openai_investment_analysis:{hash(str(property_data))}:{hash(str(financial_data))}"
        
        cached_analysis = await self.cache_manager.get(cache_key)
        if cached_analysis:
            logger.debug("OpenAI investment analysis cache hit")
            return cached_analysis
        
        await self._check_rate_limits(model)
        
        prompt = self._create_investment_analysis_prompt(property_data, financial_data, market_context)
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a property investment advisor specializing in Sydney real estate. Provide comprehensive investment analysis based on real market data and financial metrics."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.2  # Lower temperature for financial analysis
            )
            
            analysis = response.choices[0].message.content.strip()
            await self._track_request(model, response.usage)
            await self.cache_manager.set(cache_key, analysis, ttl=self.cache_ttl)
            
            logger.info("OpenAI investment analysis generated", tokens_used=response.usage.total_tokens)
            return analysis
            
        except Exception as e:
            logger.error("OpenAI investment analysis failed", error=str(e))
            raise OpenAIAPIError(f"Investment analysis failed: {e}")
    
        @openai_api_breaker
    async def generate_buyer_matching_insights(
        self,
        buyer_criteria: Dict[str, Any],
        matching_properties: List[Dict[str, Any]],
        market_conditions: Dict[str, Any],
        model: str = "gpt-3.5-turbo",
        max_tokens: int = 800
    ) -> str:
        """
        Generate buyer matching insights using OpenAI.
        
        Args:
            buyer_criteria: Buyer preferences and requirements
            matching_properties: List of matched properties
            market_conditions: Current market conditions
            model: OpenAI model to use
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated buyer matching insights
        """
        cache_key = f"openai_buyer_insights:{hash(str(buyer_criteria))}:{len(matching_properties)}"
        
        cached_insights = await self.cache_manager.get(cache_key)
        if cached_insights:
            return cached_insights
        
        await self._check_rate_limits(model)
        
        prompt = self._create_buyer_matching_prompt(buyer_criteria, matching_properties, market_conditions)
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a buyer's agent specialist helping match properties to buyer preferences. Provide actionable insights based on real property data and market conditions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.4
            )
            
            insights = response.choices[0].message.content.strip()
            await self._track_request(model, response.usage)
            await self.cache_manager.set(cache_key, insights, ttl=self.cache_ttl)
            
            logger.info("OpenAI buyer insights generated", property_count=len(matching_properties))
            return insights
            
        except Exception as e:
            logger.error("OpenAI buyer insights failed", error=str(e))
            raise OpenAIAPIError(f"Buyer insights failed: {e}")
    
    def _create_market_analysis_prompt(
        self,
        market_data: Dict[str, Any],
        analysis_context: str,
        suburb: str
    ) -> str:
        """Create specialized market analysis prompt."""
        return f"""
        Analyze the following REAL market data for {suburb}, Sydney and provide comprehensive insights:
        
        MARKET DATA:
        {json.dumps(market_data, indent=2)}
        
        ANALYSIS CONTEXT:
        {analysis_context}
        
        Please provide a professional market analysis covering:
        
        1. **Current Market Conditions**: Overall market health and activity levels
        2. **Price Trends**: Analysis of price movements and growth patterns
        3. **Sales Activity**: Transaction volumes, days on market, buyer demand
        4. **Market Dynamics**: Supply and demand factors affecting the area
        5. **Investment Outlook**: Future prospects and key factors to watch
        6. **Buyer/Seller Recommendations**: Strategic advice for market participants
        
        Base your analysis EXCLUSIVELY on the provided real data. Be specific with numbers, dates, and trends. 
        Highlight any significant patterns or anomalies in the data.
        
        Format as professional market commentary suitable for real estate professionals and their clients.
        """
    
    def _create_investment_analysis_prompt(
        self,
        property_data: Dict[str, Any],
        financial_data: Dict[str, Any],
        market_context: str
    ) -> str:
        """Create enhanced investment analysis prompt for Sydney market."""
        return f"""
        As a Sydney real estate investment analyst with 15+ years experience, provide comprehensive investment analysis based on this REAL property and financial data:
        
        PROPERTY DETAILS:
        {json.dumps(property_data, indent=2)}
        
        CALCULATED FINANCIAL METRICS:
        {json.dumps(financial_data, indent=2)}
        
        SYDNEY MARKET CONTEXT:
        {market_context}
        
        Provide detailed analysis covering:
        
        1. **Financial Performance Assessment**:
           - Interpret rental yield vs Sydney averages (current metro average: 3.8%)
           - Analyze capital growth patterns and sustainability
           - Evaluate total ROI in context of current interest rates and market conditions
           - Assess cash flow implications for different investor profiles
        
        2. **Sydney-Specific Market Factors**:
           - Transport infrastructure impact (distance to CBD, train lines, future projects)
           - School zone premiums and demographic trends
           - Local development approvals and planning changes
           - Gentrification patterns and suburb lifecycle stage
        
        3. **Investment Strategy Recommendations**:
           - Optimal holding period based on growth projections
           - Tax optimization strategies (negative gearing, depreciation)
           - Property improvement opportunities for enhanced returns
           - Exit strategy considerations and market timing
        
        4. **Risk Analysis**:
           - Market volatility assessment vs historical patterns
           - Rental vacancy risks and tenant demand stability
           - Interest rate sensitivity analysis
           - Liquidity considerations and market depth
        
        Base analysis EXCLUSIVELY on provided real data. Include specific numbers, percentages, and comparisons.
        Highlight any exceptional performance metrics or concerning trends.
        
        Format as professional investment advisory suitable for sophisticated property investors.
        """
    
    def _create_buyer_matching_prompt(
        self,
        buyer_criteria: Dict[str, Any],
        matching_properties: List[Dict[str, Any]],
        market_conditions: Dict[str, Any]
    ) -> str:
        """Create buyer matching insights prompt."""
        return f"""
        Analyze the property matches for this buyer and provide strategic insights:
        
        BUYER CRITERIA:
        {json.dumps(buyer_criteria, indent=2)}
        
        MATCHED PROPERTIES:
        {json.dumps(matching_properties[:5], indent=2)}  # Top 5 matches
        
        MARKET CONDITIONS:
        {json.dumps(market_conditions, indent=2)}
        
        Provide buyer-focused insights covering:
        
        1. **Match Quality**: Analysis of how well properties align with criteria
        2. **Market Positioning**: Competitive landscape for these property types
        3. **Negotiation Strategy**: Market conditions impact on offers and negotiations
        4. **Timing Considerations**: Urgency factors and market timing
        5. **Alternative Options**: Suggestions for expanding search criteria if beneficial
        6. **Action Plan**: Prioritized next steps for the buyer
        
        Focus on actionable advice that helps the buyer make informed decisions.
        """
    
    async def _check_rate_limits(self, model: str) -> None:
        """Check if we're within rate limits for the specified model."""
        if model not in self.rate_limits:
            return  # No specific limits configured
        
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Clean old requests
        self.request_history = [
            req for req in self.request_history 
            if req["timestamp"] > minute_ago
        ]
        
        # Count recent requests for this model
        recent_requests = len([
            req for req in self.request_history 
            if req["model"] == model
        ])
        
        if recent_requests >= self.rate_limits[model]["rpm"]:
            logger.warning(
                "OpenAI rate limit approaching",
                model=model,
                recent_requests=recent_requests,
                limit=self.rate_limits[model]["rpm"]
            )
            # Wait a bit to avoid hitting the limit
            await asyncio.sleep(2)
    
    async def _track_request(self, model: str, usage: Any) -> None:
        """Track request for rate limiting."""
        self.request_history.append({
            "model": model,
            "timestamp": time.time(),
            "tokens": usage.total_tokens if usage else 0
        })
        
        # Update token usage tracking
        if model not in self.token_usage:
            self.token_usage[model] = {"total": 0, "requests": 0}
        
        self.token_usage[model]["total"] += usage.total_tokens if usage else 0
        self.token_usage[model]["requests"] += 1
    
    async def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        return {
            "request_history_size": len(self.request_history),
            "token_usage_by_model": self.token_usage,
            "rate_limits": self.rate_limits
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check OpenAI API health and connectivity."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=10
            )
            
            return {
                "status": "healthy",
                "api_accessible": True,
                "test_tokens_used": response.usage.total_tokens,
                "last_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy", 
                "api_accessible": False,
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }


# Global client instance
_openai_client: Optional[OpenAIClient] = None


async def get_openai_client() -> OpenAIClient:
    """Get or create global OpenAI client instance."""
    global _openai_client
    
    if _openai_client is None:
        _openai_client = OpenAIClient()
    
    return _openai_client


async def close_openai_client() -> None:
    """Close global OpenAI client."""
    global _openai_client
    _openai_client = None