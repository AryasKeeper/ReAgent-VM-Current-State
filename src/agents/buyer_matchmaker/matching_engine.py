"""
Matching Engine for Buyer Matchmaker AU

Core matching algorithms, scoring logic, and business rules for 
intelligent property-buyer recommendations.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import numpy as np
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.core.cache.redis_client import get_cache_manager
from reagent_sydney.core.vector_db import WeaviateClient, SearchQuery
from reagent_sydney.data.models.buyer_models import Buyer, BuyerPreferences, PropertyMatch
from reagent_sydney.data.models.property_models import Property
from reagent_sydney.data.models.market_models import SuburbMetrics

import structlog


class MatchQuality(str, Enum):
    """Match quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


@dataclass
class MatchExplanation:
    """Detailed match explanation."""
    
    reasons: List[str]
    concerns: List[str]
    explanation_text: str
    quality_level: MatchQuality
    key_highlights: List[str]
    potential_issues: List[str]


@dataclass
class PriceAssessment:
    """Property price assessment."""
    
    assessment: str  # "underpriced", "fairly_priced", "overpriced"
    estimated_value: float
    confidence: float
    market_comparison: Dict[str, Any]
    value_drivers: List[str]
    pricing_concerns: List[str]


class MatchingEngine:
    """
    Advanced matching engine for property-buyer recommendations.
    
    Implements sophisticated algorithms for:
    - Multi-dimensional scoring
    - Market context integration
    - Behavioral learning
    - Explainable recommendations
    """
    
    def __init__(self, weaviate_client: WeaviateClient):
        self.weaviate_client = weaviate_client
        self.logger = structlog.get_logger("matching_engine")
        self.cache_manager = get_cache_manager()
        
        # Scoring weights (can be adjusted per buyer)
        self.default_weights = {
            "vector_similarity": 0.30,
            "price_fit": 0.25,
            "location_match": 0.20,
            "feature_alignment": 0.15,
            "market_attractiveness": 0.10
        }
    
    async def generate_match_reasoning(
        self,
        buyer_features: Any,
        property_obj: Property,
        scoring_details: Dict[str, Any]
    ) -> MatchExplanation:
        """Generate detailed match reasoning and explanation."""
        
        reasons = []
        concerns = []
        key_highlights = []
        potential_issues = []
        
        # Analyze scoring components
        component_scores = scoring_details.get("component_scores", {})
        
        # Price fit analysis
        price_score = component_scores.get("price_fit", 0)
        if price_score > 0.8:
            reasons.append(f"Excellent price fit within budget of ${buyer_features.max_price:,}")
            key_highlights.append("Price within ideal range")
        elif price_score > 0.6:
            reasons.append("Good price alignment with budget")
        elif price_score < 0.4:
            concerns.append("Price may be challenging given budget constraints")
            potential_issues.append("Budget stretch required")
        
        # Location analysis
        location_score = component_scores.get("location_match", 0)
        if location_score > 0.7:
            if property_obj.suburb and property_obj.suburb.lower() in [s.lower() for s in buyer_features.preferred_suburbs]:
                reasons.append(f"Located in preferred suburb: {property_obj.suburb}")
                key_highlights.append("Prime location match")
            reasons.append("Excellent location alignment with preferences")
        elif location_score < 0.3:
            concerns.append("Location may not fully meet preferences")
        
        # Feature alignment
        feature_score = component_scores.get("feature_alignment", 0)
        if feature_score > 0.7:
            reasons.append("Strong feature alignment with requirements")
            # Check specific required features
            if buyer_features.required_features:
                property_features = [f.lower() for f in (property_obj.features or [])]
                matched_features = [
                    req for req in buyer_features.required_features
                    if any(req.lower() in pf for pf in property_features)
                ]
                if matched_features:
                    key_highlights.append(f"Includes required: {', '.join(matched_features[:3])}")
        
        # Property specifications
        spec_issues = []
        if buyer_features.min_bedrooms > 0 and property_obj.bedrooms:
            if property_obj.bedrooms < buyer_features.min_bedrooms:
                spec_issues.append(f"Only {property_obj.bedrooms} bedrooms (need {buyer_features.min_bedrooms})")
            elif property_obj.bedrooms >= buyer_features.min_bedrooms:
                reasons.append(f"Meets bedroom requirement ({property_obj.bedrooms} bedrooms)")
        
        if buyer_features.min_bathrooms > 0 and property_obj.bathrooms:
            if property_obj.bathrooms < buyer_features.min_bathrooms:
                spec_issues.append(f"Only {property_obj.bathrooms} bathrooms (need {buyer_features.min_bathrooms})")
        
        if spec_issues:
            concerns.extend(spec_issues)
            potential_issues.extend(spec_issues)
        
        # Market context
        market_score = component_scores.get("market_attractiveness", 0)
        if market_score > 0.7:
            reasons.append("Strong market appeal and activity")
            if property_obj.days_on_market and property_obj.days_on_market <= 14:
                key_highlights.append("Fresh to market")
        elif market_score < 0.3:
            if property_obj.days_on_market and property_obj.days_on_market > 60:
                concerns.append(f"Extended market time ({property_obj.days_on_market} days)")
                potential_issues.append("May indicate pricing or property issues")
        
        # Overall quality assessment
        final_score = sum(
            component_scores.get(component, 0) * weight
            for component, weight in self.default_weights.items()
        )
        
        penalties = scoring_details.get("penalties", {})
        final_score = max(0, final_score - sum(penalties.values()))
        
        if final_score >= 0.8:
            quality_level = MatchQuality.EXCELLENT
        elif final_score >= 0.65:
            quality_level = MatchQuality.GOOD
        elif final_score >= 0.5:
            quality_level = MatchQuality.FAIR
        else:
            quality_level = MatchQuality.POOR
        
        # Generate explanation text
        explanation_text = self._generate_explanation_text(
            property_obj, buyer_features, final_score, quality_level, reasons, concerns
        )
        
        return MatchExplanation(
            reasons=reasons,
            concerns=concerns,
            explanation_text=explanation_text,
            quality_level=quality_level,
            key_highlights=key_highlights,
            potential_issues=potential_issues
        )
    
    def _generate_explanation_text(
        self,
        property_obj: Property,
        buyer_features: Any,
        match_score: float,
        quality_level: MatchQuality,
        reasons: List[str],
        concerns: List[str]
    ) -> str:
        """Generate natural language explanation for the match."""
        
        # Property overview
        prop_desc = f"{property_obj.bedrooms}BR {property_obj.bathrooms}BA {property_obj.property_type.title()} in {property_obj.suburb}"
        price_text = f"${property_obj.price:,.0f}" if property_obj.price else "Price on application"
        
        explanation = f"This {prop_desc} ({price_text}) is a {quality_level.value.upper()} match (Score: {match_score:.2f}) for your requirements.\n\n"
        
        # Key strengths
        if reasons:
            explanation += "✅ KEY STRENGTHS:\n"
            for reason in reasons[:4]:  # Top 4 reasons
                explanation += f"• {reason}\n"
            explanation += "\n"
        
        # Potential concerns
        if concerns:
            explanation += "⚠️  CONSIDERATIONS:\n"
            for concern in concerns[:3]:  # Top 3 concerns
                explanation += f"• {concern}\n"
            explanation += "\n"
        
        # Investment/lifestyle perspective
        if buyer_features.buyer_type == "investor":
            explanation += "🏦 INVESTMENT PERSPECTIVE:\n"
            if property_obj.suburb:
                explanation += f"• {property_obj.suburb} market dynamics and rental demand\n"
            if buyer_features.rental_yield_target > 0:
                explanation += f"• Target yield: {buyer_features.rental_yield_target}%\n"
        else:
            explanation += "🏠 LIFESTYLE PERSPECTIVE:\n"
            explanation += "• Consider long-term suitability for your needs\n"
            if buyer_features.preferred_features:
                explanation += f"• Your preferences: {', '.join(buyer_features.preferred_features[:3])}\n"
        
        # Action recommendation
        if quality_level in [MatchQuality.EXCELLENT, MatchQuality.GOOD]:
            explanation += "\n💡 RECOMMENDATION: Schedule an inspection soon - this property aligns well with your criteria."
        elif quality_level == MatchQuality.FAIR:
            explanation += "\n💡 RECOMMENDATION: Worth considering but review the highlighted concerns first."
        else:
            explanation += "\n💡 RECOMMENDATION: May not be the best fit - consider only if other priorities have changed."
        
        return explanation
    
    async def assess_property_pricing(
        self,
        property_obj: Property,
        buyer_features: Any
    ) -> PriceAssessment:
        """Assess property pricing relative to market and buyer budget."""
        
        if not property_obj.price:
            return PriceAssessment(
                assessment="unknown",
                estimated_value=0,
                confidence=0,
                market_comparison={},
                value_drivers=[],
                pricing_concerns=["Price not disclosed"]
            )
        
        price = float(property_obj.price)
        
        # Get suburb market data
        market_data = await self._get_suburb_market_data(property_obj.suburb, property_obj.property_type)
        
        # Calculate price per sqm if possible
        price_per_sqm = None
        if property_obj.building_size and property_obj.building_size > 0:
            price_per_sqm = price / property_obj.building_size
        
        # Market comparison
        market_comparison = {
            "suburb_median": market_data.get("median_price", 0),
            "price_percentile": market_data.get("price_percentile", 50),
            "recent_sales_avg": market_data.get("recent_sales_avg", 0),
            "price_per_sqm_comparison": market_data.get("price_per_sqm_avg", 0)
        }
        
        # Value drivers analysis
        value_drivers = []
        pricing_concerns = []
        
        # Location value drivers
        if property_obj.suburb in ["Bondi", "Mosman", "Paddington", "Surry Hills"]:
            value_drivers.append("Premium location")
        
        # Property features value drivers
        if property_obj.features:
            luxury_features = ["pool", "harbour views", "renovated", "designer kitchen"]
            found_luxury = [f for f in luxury_features if any(f in feat.lower() for feat in property_obj.features)]
            if found_luxury:
                value_drivers.extend(found_luxury)
        
        # Market timing factors
        if property_obj.days_on_market and property_obj.days_on_market <= 7:
            value_drivers.append("Fresh to market")
        elif property_obj.days_on_market and property_obj.days_on_market > 90:
            pricing_concerns.append("Extended market time may indicate overpricing")
        
        # Size analysis
        if property_obj.land_size and property_obj.land_size > 600:
            value_drivers.append(f"Large land holding ({property_obj.land_size}sqm)")
        elif property_obj.land_size and property_obj.land_size < 200:
            pricing_concerns.append("Limited land size")
        
        # Assessment logic
        median_price = market_comparison["suburb_median"]
        assessment = "fairly_priced"
        confidence = 0.7
        estimated_value = price
        
        if median_price > 0:
            price_ratio = price / median_price
            
            if price_ratio < 0.85:
                assessment = "underpriced"
                confidence = 0.8
                estimated_value = median_price * 0.95
            elif price_ratio > 1.15:
                assessment = "overpriced"
                confidence = 0.8
                estimated_value = median_price * 1.05
                pricing_concerns.append("Above suburb median")
            else:
                assessment = "fairly_priced"
                confidence = 0.9
        
        # Budget fit analysis
        if buyer_features.max_price > 0:
            budget_ratio = price / buyer_features.max_price
            if budget_ratio > 1.05:
                pricing_concerns.append("Above maximum budget")
            elif budget_ratio < 0.8:
                value_drivers.append("Well within budget")
        
        return PriceAssessment(
            assessment=assessment,
            estimated_value=estimated_value,
            confidence=confidence,
            market_comparison=market_comparison,
            value_drivers=value_drivers,
            pricing_concerns=pricing_concerns
        )
    
    async def _get_suburb_market_data(self, suburb: str, property_type: str) -> Dict[str, Any]:
        """Get suburb market data for pricing analysis."""
        
        cache_key = f"suburb_market:{suburb}:{property_type}"
        cached_data = await self.cache_manager.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Query recent sales and market metrics
        async with get_db_session() as session:
            # Get recent sales data
            recent_sales = await session.execute(
                select(Property)
                .where(
                    and_(
                        Property.suburb.ilike(f"%{suburb}%"),
                        Property.property_type == property_type,
                        Property.listing_status == "sold",
                        Property.updated_at >= datetime.utcnow() - timedelta(days=90)
                    )
                )
                .limit(20)
            )
            
            sales_data = recent_sales.scalars().all()
            
            # Calculate market metrics
            if sales_data:
                prices = [float(prop.price) for prop in sales_data if prop.price]
                
                market_data = {
                    "median_price": np.median(prices) if prices else 0,
                    "mean_price": np.mean(prices) if prices else 0,
                    "recent_sales_count": len(sales_data),
                    "price_range": {
                        "min": min(prices) if prices else 0,
                        "max": max(prices) if prices else 0
                    }
                }
                
                # Calculate price per sqm if building sizes available
                sqm_prices = [
                    float(prop.price) / prop.building_size
                    for prop in sales_data
                    if prop.price and prop.building_size and prop.building_size > 0
                ]
                
                if sqm_prices:
                    market_data["price_per_sqm_avg"] = np.mean(sqm_prices)
                    market_data["price_per_sqm_median"] = np.median(sqm_prices)
            else:
                market_data = {
                    "median_price": 0,
                    "mean_price": 0,
                    "recent_sales_count": 0,
                    "price_range": {"min": 0, "max": 0},
                    "price_per_sqm_avg": 0
                }
            
            # Cache for 1 hour
            await self.cache_manager.set(cache_key, market_data, ttl=3600)
            return market_data
    
    async def apply_matching_filters(
        self,
        buyer_features: Any,
        matches: List[Any]
    ) -> List[Any]:
        """Apply business rules and filters to matches."""
        
        filtered_matches = []
        
        for match in matches:
            # Skip if score is too low
            if match.match_score < 0.4:
                continue
            
            # Skip if over absolute budget limit
            if buyer_features.max_price > 0:
                property_price = await self._get_property_price(match.property_id)
                max_allowable = buyer_features.max_price * (1 + buyer_features.budget_flexibility)
                
                if property_price and property_price > max_allowable:
                    continue
            
            # Skip if in excluded suburbs
            if buyer_features.excluded_suburbs:
                property_suburb = await self._get_property_suburb(match.property_id)
                if property_suburb and property_suburb.lower() in [s.lower() for s in buyer_features.excluded_suburbs]:
                    continue
            
            # Apply urgency-based filtering
            if buyer_features.buying_urgency == "urgent":
                # For urgent buyers, only show excellent and good matches
                if match.match_score < 0.65:
                    continue
            elif buyer_features.buying_urgency == "low":
                # For low urgency, show more variety
                pass
            
            filtered_matches.append(match)
        
        # Limit to max matches per buyer
        max_matches = 10  # Could be configurable
        return filtered_matches[:max_matches]
    
    async def _get_property_price(self, property_id: str) -> Optional[float]:
        """Get property price by ID."""
        async with get_db_session() as session:
            result = await session.execute(
                select(Property.price).where(Property.id == property_id)
            )
            price = result.scalar_one_or_none()
            return float(price) if price else None
    
    async def _get_property_suburb(self, property_id: str) -> Optional[str]:
        """Get property suburb by ID."""
        async with get_db_session() as session:
            result = await session.execute(
                select(Property.suburb).where(Property.id == property_id)
            )
            return result.scalar_one_or_none()
    
    async def update_buyer_vector_profile(
        self,
        buyer: Buyer,
        buyer_vector: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """Update or create buyer profile in vector database."""
        
        try:
            # Prepare buyer profile data
            profile_data = {
                "buyer_id": str(buyer.id),
                "full_name": buyer.full_name,
                "buyer_type": buyer.buyer_type or "individual",
                "buying_urgency": buyer.buying_urgency or "medium",
                "created_at": buyer.created_at.isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "embedding_metadata": metadata
            }
            
            # Add preferences if available
            if buyer.preferences:
                prefs = buyer.preferences
                profile_data.update({
                    "max_price": float(prefs.max_price or 0),
                    "min_price": float(prefs.min_price or 0),
                    "budget_flexibility": float(prefs.budget_flexibility or 0.1),
                    "property_types": prefs.property_types or [],
                    "preferred_suburbs": prefs.preferred_suburbs or [],
                    "excluded_suburbs": prefs.excluded_suburbs or [],
                    "preferred_postcodes": prefs.preferred_postcodes or [],
                    "min_bedrooms": prefs.min_bedrooms or 0,
                    "max_bedrooms": prefs.max_bedrooms or 10,
                    "min_bathrooms": prefs.min_bathrooms or 0,
                    "min_car_spaces": prefs.min_car_spaces or 0,
                    "min_land_size": prefs.min_land_size or 0,
                    "min_building_size": prefs.min_building_size or 0,
                    "required_features": prefs.required_features or [],
                    "preferred_features": prefs.preferred_features or [],
                    "excluded_features": prefs.excluded_features or [],
                    "max_commute_time": prefs.max_commute_time or 60,
                    "rental_yield_target": float(prefs.rental_yield_target or 0),
                    "capital_growth_expectation": prefs.capital_growth_expectation or "medium"
                })
            
            # Check if profile already exists
            existing_profile = await self.weaviate_client.get_object(
                class_name="BuyerProfile",
                object_id=str(buyer.id)
            )
            
            if existing_profile:
                # Update existing profile
                success = await self.weaviate_client.update_object(
                    class_name="BuyerProfile",
                    object_id=str(buyer.id),
                    properties=profile_data,
                    vector=buyer_vector
                )
            else:
                # Create new profile
                object_id = await self.weaviate_client.insert_object(
                    class_name="BuyerProfile",
                    properties=profile_data,
                    vector=buyer_vector,
                    object_id=str(buyer.id)
                )
                success = object_id is not None
            
            if success:
                self.logger.info(f"Updated buyer vector profile for {buyer.id}")
            else:
                self.logger.error(f"Failed to update buyer vector profile for {buyer.id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error updating buyer vector profile: {e}")
            return False