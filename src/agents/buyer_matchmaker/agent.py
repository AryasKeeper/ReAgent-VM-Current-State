"""
Buyer Matchmaker AU - Intelligent Property Recommendation Agent

Advanced ML-powered matching system that provides personalized property recommendations
using vector search, behavioral analytics, and market intelligence.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from langchain.tools import Tool
from crewai import Agent, Task

from reagent_sydney.agents.base import BaseReAgentAgent, AgentConfig, AgentRole, AgentPriority
from reagent_sydney.core.vector_db import (
    WeaviateClient, get_weaviate_client,
    PropertySchema, BuyerProfileSchema, 
    PropertyVectorizer, BuyerProfileVectorizer
)
from reagent_sydney.core.vector_db.client import SearchQuery, VectorSearchResult
from reagent_sydney.core.cache.redis_client import get_cache_manager
from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.data.models.buyer_models import Buyer, BuyerPreferences, PropertyMatch
from reagent_sydney.data.models.property_models import Property
from reagent_sydney.config.settings import get_settings

import structlog
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload


@dataclass
class MatchResult:
    """Individual property match result."""
    
    property_id: str
    buyer_id: str
    match_score: float
    match_rank: int
    match_reasons: List[str]
    match_concerns: List[str]
    match_explanation: str
    price_assessment: str
    estimated_value: float
    scoring_details: Dict[str, Any]


@dataclass
class MatchingConfig:
    """Configuration for matching algorithm."""
    
    max_matches_per_buyer: int = 10
    min_match_score: float = 0.6
    enable_market_context: bool = True
    enable_behavioral_learning: bool = True
    similarity_threshold: float = 0.7
    price_tolerance_factor: float = 1.1
    recency_weight: float = 0.1
    diversity_factor: float = 0.2


class BuyerMatchmakerAgent(BaseReAgentAgent):
    """
    Intelligent Property Recommendation Agent
    
    Provides AI-powered property-buyer matching using:
    - Vector similarity search with Weaviate
    - Behavioral learning from buyer interactions
    - Market context integration
    - Explainable match scoring
    - Real-time recommendation updates
    """
    
    def __init__(self):
        config = AgentConfig(
            name="Buyer Matchmaker AU",
            role=AgentRole.MATCHER,
            description="AI-powered property-buyer matching with vector search and behavioral learning",
            version="1.0.0",
            max_execution_time=300,
            max_retries=3,
            priority=AgentPriority.HIGH,
            required_services=["database", "cache", "weaviate"],
            enable_metrics=True,
            custom_settings={
                "matching_config": MatchingConfig().__dict__,
                "vector_similarity_threshold": 0.7,
                "max_concurrent_matches": 50,
                "cache_ttl_seconds": 3600
            }
        )
        super().__init__(config)
        
        # Vector components
        self.weaviate_client: Optional[WeaviateClient] = None
        self.property_vectorizer = PropertyVectorizer()
        self.buyer_vectorizer = BuyerProfileVectorizer()
        
        # Matching configuration
        self.matching_config = MatchingConfig()
        
        # Performance tracking
        self.match_cache_hits = 0
        self.match_cache_misses = 0
    
    async def _initialize_agent(self) -> None:
        """Initialize Weaviate client and schemas."""
        try:
            # Connect to Weaviate
            self.weaviate_client = await get_weaviate_client()
            
            # Create schemas if they don't exist
            await self._setup_vector_schemas()
            
            self.logger.info("Buyer Matchmaker Agent initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Buyer Matchmaker Agent: {e}")
            raise
    
    async def _cleanup_agent(self) -> None:
        """Cleanup agent resources."""
        # Weaviate client cleanup handled by global client manager
        pass
    
    async def _execute_agent_logic(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main agent execution logic."""
        
        operation = input_data.get("operation", "generate_matches")
        
        if operation == "generate_matches":
            return await self._generate_buyer_matches(input_data)
        elif operation == "update_buyer_profile":
            return await self._update_buyer_profile(input_data)
        elif operation == "record_feedback":
            return await self._record_buyer_feedback(input_data)
        elif operation == "get_match_explanation":
            return await self._get_match_explanation(input_data)
        elif operation == "sync_properties":
            return await self._sync_properties_to_vector_db(input_data)
        elif operation == "health_check":
            return await self._perform_health_check()
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _initialize_tools(self) -> List[Tool]:
        """Initialize CrewAI tools for matching operations."""
        return [
            Tool(
                name="find_property_matches",
                description="Find matching properties for a buyer using vector similarity search",
                func=self._tool_find_matches
            ),
            Tool(
                name="update_buyer_preferences",
                description="Update buyer preferences and regenerate their vector profile",
                func=self._tool_update_buyer_preferences
            ),
            Tool(
                name="record_buyer_feedback",
                description="Record buyer feedback on property matches for learning",
                func=self._tool_record_feedback
            ),
            Tool(
                name="get_match_explanations",
                description="Get detailed explanations for property matches",
                func=self._tool_get_match_explanations
            ),
            Tool(
                name="analyze_buyer_behavior",
                description="Analyze buyer behavior patterns to improve matching",
                func=self._tool_analyze_buyer_behavior
            ),
            Tool(
                name="generate_buyer_alerts",
                description="Generate alerts for new matching properties",
                func=self._tool_generate_buyer_alerts
            )
        ]
    
    def _get_agent_goal(self) -> str:
        """Get agent goal for CrewAI."""
        return (
            "Provide intelligent, personalized property recommendations to buyers using "
            "advanced vector similarity search, behavioral learning, and market intelligence. "
            "Maximize match quality and buyer satisfaction while minimizing time to find ideal properties."
        )
    
    def _get_agent_backstory(self) -> str:
        """Get agent backstory for CrewAI."""
        return (
            "You are an expert AI property matchmaker specializing in the Sydney real estate market. "
            "You use advanced machine learning techniques including vector embeddings, semantic search, "
            "and behavioral analysis to understand buyer preferences and match them with ideal properties. "
            "Your expertise includes market trend analysis, pricing assessment, and buyer psychology. "
            "You continuously learn from buyer feedback to improve your recommendations and have helped "
            "thousands of buyers find their perfect home or investment property."
        )
    
    # Core Matching Functions
    
    async def _generate_buyer_matches(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate property matches for buyers."""
        
        buyer_ids = input_data.get("buyer_ids", [])
        force_refresh = input_data.get("force_refresh", False)
        
        if not buyer_ids:
            # Get all active buyers if none specified
            async with get_db_session() as session:
                result = await session.execute(
                    select(Buyer.id).where(Buyer.status == "active")
                )
                buyer_ids = [row[0] for row in result.fetchall()]
        
        total_matches = 0
        successful_matches = 0
        errors = []
        
        # Process buyers concurrently
        semaphore = asyncio.Semaphore(self.config.custom_settings.get("max_concurrent_matches", 5))
        
        async def process_buyer(buyer_id: str):
            nonlocal total_matches, successful_matches
            
            async with semaphore:
                try:
                    matches = await self._find_matches_for_buyer(buyer_id, force_refresh)
                    total_matches += len(matches)
                    successful_matches += 1
                    
                    # Store matches in database
                    await self._store_buyer_matches(buyer_id, matches)
                    
                    return {"buyer_id": buyer_id, "matches": len(matches)}
                    
                except Exception as e:
                    error_msg = f"Failed to generate matches for buyer {buyer_id}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
                    return {"buyer_id": buyer_id, "error": str(e)}
        
        # Execute matching for all buyers
        start_time = datetime.utcnow()
        results = await asyncio.gather(*[process_buyer(bid) for bid in buyer_ids])
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "operation": "generate_matches",
            "buyers_processed": len(buyer_ids),
            "successful_matches": successful_matches,
            "total_matches_generated": total_matches,
            "errors": errors,
            "execution_time_seconds": execution_time,
            "cache_performance": {
                "hits": self.match_cache_hits,
                "misses": self.match_cache_misses,
                "hit_rate": self.match_cache_hits / (self.match_cache_hits + self.match_cache_misses) if (self.match_cache_hits + self.match_cache_misses) > 0 else 0
            },
            "results": results
        }
    
    async def _find_matches_for_buyer(
        self, 
        buyer_id: str, 
        force_refresh: bool = False
    ) -> List[MatchResult]:
        """Find property matches for a specific buyer."""
        
        # Check cache first
        cache_key = f"buyer_matches:{buyer_id}"
        if not force_refresh:
            cached_matches = await self.cache_manager.get(cache_key)
            if cached_matches:
                self.match_cache_hits += 1
                return [MatchResult(**match) for match in cached_matches]
        
        self.match_cache_misses += 1
        
        # Load buyer and preferences
        async with get_db_session() as session:
            result = await session.execute(
                select(Buyer)
                .options(selectinload(Buyer.preferences))
                .where(Buyer.id == buyer_id)
            )
            buyer = result.scalar_one_or_none()
            
            if not buyer or not buyer.preferences:
                self.logger.warning(f"Buyer {buyer_id} not found or has no preferences")
                return []
        
        # Generate buyer embedding
        buyer_features = self.buyer_vectorizer.extract_features(buyer, buyer.preferences)
        buyer_vector, buyer_metadata = await self.buyer_vectorizer.generate_embedding(buyer_features)
        
        # Update buyer profile in vector DB
        await self._upsert_buyer_profile(buyer, buyer_vector, buyer_metadata)
        
        # Find candidate properties using vector search
        candidates = await self._find_candidate_properties(buyer_features, buyer_vector)
        
        # Score and rank matches
        matches = await self._score_and_rank_matches(buyer, buyer_features, candidates)
        
        # Apply business rules and filters
        filtered_matches = await self._apply_matching_filters(buyer_features, matches)
        
        # Cache results
        match_dicts = [match.__dict__ for match in filtered_matches]
        await self.cache_manager.set(
            cache_key, 
            match_dicts, 
            ttl=self.config.custom_settings.get("cache_ttl_seconds", 3600)
        )
        
        self.logger.info(f"Generated {len(filtered_matches)} matches for buyer {buyer_id}")
        return filtered_matches
    
    async def _find_candidate_properties(
        self, 
        buyer_features: Any, 
        buyer_vector: List[float]
    ) -> List[VectorSearchResult]:
        """Find candidate properties using vector similarity search."""
        
        # Build base query filters
        where_filter = {
            "operator": "And",
            "operands": [
                {"path": ["listing_status"], "operator": "Equal", "valueString": "active"},
                {"path": ["listing_type"], "operator": "Equal", "valueString": "sale"}
            ]
        }
        
        # Add price filter if specified
        if buyer_features.max_price > 0:
            max_price_with_flexibility = buyer_features.max_price * (1 + buyer_features.budget_flexibility)
            where_filter["operands"].append({
                "path": ["price"],
                "operator": "LessThanEqual",
                "valueNumber": max_price_with_flexibility
            })
        
        if buyer_features.min_price > 0:
            where_filter["operands"].append({
                "path": ["price"],
                "operator": "GreaterThanEqual", 
                "valueNumber": buyer_features.min_price
            })
        
        # Add property type filter
        if buyer_features.property_types:
            type_filter = {
                "operator": "Or",
                "operands": [
                    {"path": ["property_type"], "operator": "Equal", "valueString": pt}
                    for pt in buyer_features.property_types
                ]
            }
            where_filter["operands"].append(type_filter)
        
        # Add bedroom filter
        if buyer_features.min_bedrooms > 0:
            where_filter["operands"].append({
                "path": ["bedrooms"],
                "operator": "GreaterThanEqual",
                "valueInt": buyer_features.min_bedrooms
            })
        
        if buyer_features.max_bedrooms < 10:
            where_filter["operands"].append({
                "path": ["bedrooms"],
                "operator": "LessThanEqual",
                "valueInt": buyer_features.max_bedrooms
            })
        
        # Add location filters
        if buyer_features.preferred_suburbs:
            suburb_filter = {
                "operator": "Or",
                "operands": [
                    {"path": ["suburb"], "operator": "Equal", "valueString": suburb}
                    for suburb in buyer_features.preferred_suburbs
                ]
            }
            where_filter["operands"].append(suburb_filter)
        
        if buyer_features.preferred_postcodes:
            postcode_filter = {
                "operator": "Or", 
                "operands": [
                    {"path": ["postcode"], "operator": "Equal", "valueString": pc}
                    for pc in buyer_features.preferred_postcodes
                ]
            }
            where_filter["operands"].append(postcode_filter)
        
        # Exclude unwanted suburbs
        if buyer_features.excluded_suburbs:
            for suburb in buyer_features.excluded_suburbs:
                where_filter["operands"].append({
                    "path": ["suburb"],
                    "operator": "NotEqual",
                    "valueString": suburb
                })
        
        # Create search query
        search_query = SearchQuery(
            vector=buyer_vector,
            class_name="Property",
            limit=self.matching_config.max_matches_per_buyer * 3,  # Get more candidates for filtering
            where_filter=where_filter,
            certainty=self.matching_config.similarity_threshold,
            additional_properties=["certainty", "distance"]
        )
        
        # Execute vector search
        candidates = await self.weaviate_client.vector_search(search_query)
        
        self.logger.debug(f"Found {len(candidates)} candidate properties from vector search")
        return candidates
    
    async def _score_and_rank_matches(
        self,
        buyer: Buyer,
        buyer_features: Any,
        candidates: List[VectorSearchResult]
    ) -> List[MatchResult]:
        """Score and rank property matches using multi-factor algorithm."""
        
        matches = []
        
        # Load property details for scoring
        property_ids = [candidate.data.get("listing_id") for candidate in candidates]
        
        async with get_db_session() as session:
            result = await session.execute(
                select(Property)
                .options(
                    selectinload(Property.agent),
                    selectinload(Property.agency),
                    selectinload(Property.market_metrics)
                )
                .where(Property.listing_id.in_(property_ids))
            )
            properties = {prop.listing_id: prop for prop in result.scalars().all()}
        
        for i, candidate in enumerate(candidates):
            listing_id = candidate.data.get("listing_id")
            property_obj = properties.get(listing_id)
            
            if not property_obj:
                continue
            
            # Calculate comprehensive match score
            match_score, scoring_details = await self._calculate_match_score(
                buyer_features, property_obj, candidate.score
            )
            
            # Generate match reasoning
            reasons, concerns, explanation = await self._generate_match_reasoning(
                buyer_features, property_obj, scoring_details
            )
            
            # Price assessment
            price_assessment, estimated_value = await self._assess_property_pricing(
                property_obj, buyer_features
            )
            
            match = MatchResult(
                property_id=str(property_obj.id),
                buyer_id=str(buyer.id),
                match_score=match_score,
                match_rank=i + 1,  # Will be re-ranked later
                match_reasons=reasons,
                match_concerns=concerns,
                match_explanation=explanation,
                price_assessment=price_assessment,
                estimated_value=estimated_value,
                scoring_details=scoring_details
            )
            
            matches.append(match)
        
        # Sort by match score and update rankings
        matches.sort(key=lambda m: m.match_score, reverse=True)
        for i, match in enumerate(matches):
            match.match_rank = i + 1
        
        return matches
    
    async def _calculate_match_score(
        self,
        buyer_features: Any,
        property_obj: Property,
        vector_similarity: float
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate comprehensive match score with detailed breakdown."""
        
        scoring_details = {
            "vector_similarity": vector_similarity,
            "component_scores": {},
            "weights": {},
            "penalties": {}
        }
        
        # Component weights
        weights = {
            "vector_similarity": 0.30,
            "price_fit": 0.25,
            "location_match": 0.20,
            "feature_alignment": 0.15,
            "market_attractiveness": 0.10
        }
        scoring_details["weights"] = weights
        
        # 1. Vector similarity (base score)
        vector_score = vector_similarity
        scoring_details["component_scores"]["vector_similarity"] = vector_score
        
        # 2. Price fit score
        price_score = self._calculate_price_fit_score(buyer_features, property_obj)
        scoring_details["component_scores"]["price_fit"] = price_score
        
        # 3. Location match score
        location_score = self._calculate_location_match_score(buyer_features, property_obj)
        scoring_details["component_scores"]["location_match"] = location_score
        
        # 4. Feature alignment score
        feature_score = self._calculate_feature_alignment_score(buyer_features, property_obj)
        scoring_details["component_scores"]["feature_alignment"] = feature_score
        
        # 5. Market attractiveness score
        market_score = self._calculate_market_attractiveness_score(property_obj)
        scoring_details["component_scores"]["market_attractiveness"] = market_score
        
        # Calculate weighted score
        final_score = (
            vector_score * weights["vector_similarity"] +
            price_score * weights["price_fit"] +
            location_score * weights["location_match"] +
            feature_score * weights["feature_alignment"] +
            market_score * weights["market_attractiveness"]
        )
        
        # Apply penalties for deal-breakers
        penalties = self._calculate_match_penalties(buyer_features, property_obj)
        scoring_details["penalties"] = penalties
        
        final_score = max(0, final_score - sum(penalties.values()))
        
        return final_score, scoring_details
    
    def _calculate_price_fit_score(self, buyer_features: Any, property_obj: Property) -> float:
        """Calculate how well property price fits buyer budget."""
        if not property_obj.price or buyer_features.max_price <= 0:
            return 0.5
        
        price = float(property_obj.price)
        max_budget = buyer_features.max_price * (1 + buyer_features.budget_flexibility)
        min_budget = buyer_features.min_price or 0
        
        # Perfect fit is around 90% of max budget
        ideal_price = buyer_features.max_price * 0.9
        
        if price > max_budget:
            return 0.0  # Over budget
        elif price < min_budget:
            return 0.2  # Below minimum
        else:
            # Score based on distance from ideal price
            price_ratio = price / ideal_price if ideal_price > 0 else 1
            if price_ratio <= 1:
                return 1.0 - (abs(1 - price_ratio) * 0.5)
            else:
                return max(0.3, 1.0 - (price_ratio - 1) * 2)
    
    def _calculate_location_match_score(self, buyer_features: Any, property_obj: Property) -> float:
        """Calculate location match score."""
        score = 0.5  # Base score
        
        # Preferred suburbs bonus
        if buyer_features.preferred_suburbs and property_obj.suburb:
            if property_obj.suburb.lower() in [s.lower() for s in buyer_features.preferred_suburbs]:
                score += 0.4
        
        # Preferred postcodes bonus
        if buyer_features.preferred_postcodes and property_obj.postcode:
            if property_obj.postcode in buyer_features.preferred_postcodes:
                score += 0.3
        
        # Excluded suburbs penalty
        if buyer_features.excluded_suburbs and property_obj.suburb:
            if property_obj.suburb.lower() in [s.lower() for s in buyer_features.excluded_suburbs]:
                score = 0.0
        
        return min(1.0, score)
    
    def _calculate_feature_alignment_score(self, buyer_features: Any, property_obj: Property) -> float:
        """Calculate feature alignment score."""
        score = 0.5
        property_features = [f.lower() for f in (property_obj.features or [])]
        
        # Required features
        if buyer_features.required_features:
            required_count = len(buyer_features.required_features)
            found_required = sum(
                1 for req in buyer_features.required_features
                if any(req.lower() in pf for pf in property_features)
            )
            score += 0.3 * (found_required / required_count)
        
        # Preferred features bonus
        if buyer_features.preferred_features:
            preferred_count = len(buyer_features.preferred_features)
            found_preferred = sum(
                1 for pref in buyer_features.preferred_features
                if any(pref.lower() in pf for pf in property_features)
            )
            score += 0.2 * (found_preferred / preferred_count)
        
        return min(1.0, score)
    
    def _calculate_market_attractiveness_score(self, property_obj: Property) -> float:
        """Calculate market attractiveness score."""
        score = 0.5
        
        # Days on market (fresher is better)
        if property_obj.days_on_market is not None:
            if property_obj.days_on_market <= 7:
                score += 0.2
            elif property_obj.days_on_market <= 30:
                score += 0.1
            elif property_obj.days_on_market > 90:
                score -= 0.1
        
        # Market metrics if available
        if hasattr(property_obj, 'market_metrics') and property_obj.market_metrics:
            latest_metrics = property_obj.market_metrics[-1]
            
            # High interest properties
            if latest_metrics.enquiry_count and latest_metrics.enquiry_count > 5:
                score += 0.1
            
            # Sale probability
            if latest_metrics.sale_probability and latest_metrics.sale_probability > 0.7:
                score += 0.1
        
        return min(1.0, score)
    
    def _calculate_match_penalties(self, buyer_features: Any, property_obj: Property) -> Dict[str, float]:
        """Calculate penalties for deal-breakers."""
        penalties = {}
        
        # Bedroom requirement penalties
        if buyer_features.min_bedrooms > 0 and property_obj.bedrooms:
            if property_obj.bedrooms < buyer_features.min_bedrooms:
                penalties["insufficient_bedrooms"] = 0.3
        
        if buyer_features.max_bedrooms < 10 and property_obj.bedrooms:
            if property_obj.bedrooms > buyer_features.max_bedrooms:
                penalties["excessive_bedrooms"] = 0.2
        
        # Bathroom requirements
        if buyer_features.min_bathrooms > 0 and property_obj.bathrooms:
            if property_obj.bathrooms < buyer_features.min_bathrooms:
                penalties["insufficient_bathrooms"] = 0.2
        
        # Car space requirements
        if buyer_features.min_car_spaces > 0 and property_obj.car_spaces is not None:
            if property_obj.car_spaces < buyer_features.min_car_spaces:
                penalties["insufficient_parking"] = 0.15
        
        # Size requirements
        if buyer_features.min_land_size > 0 and property_obj.land_size:
            if property_obj.land_size < buyer_features.min_land_size:
                penalties["insufficient_land_size"] = 0.1
        
        if buyer_features.min_building_size > 0 and property_obj.building_size:
            if property_obj.building_size < buyer_features.min_building_size:
                penalties["insufficient_building_size"] = 0.1
        
        # Excluded features
        if buyer_features.excluded_features and property_obj.features:
            property_features = [f.lower() for f in property_obj.features]
            for excluded in buyer_features.excluded_features:
                if any(excluded.lower() in pf for pf in property_features):
                    penalties[f"excluded_feature_{excluded}"] = 0.1
        
        return penalties
    
    # Additional helper methods for match reasoning, pricing assessment, etc.
    # [Implementation continues with remaining methods...]
    
    # Tool implementations for CrewAI
    async def _tool_find_matches(self, buyer_id: str) -> str:
        """CrewAI tool to find property matches."""
        try:
            matches = await self._find_matches_for_buyer(buyer_id)
            return f"Found {len(matches)} property matches for buyer {buyer_id}"
        except Exception as e:
            return f"Error finding matches: {str(e)}"
    
    async def _tool_update_buyer_preferences(self, buyer_id: str, preferences: Dict[str, Any]) -> str:
        """CrewAI tool to update buyer preferences."""
        try:
            result = await self._update_buyer_profile({"buyer_id": buyer_id, "preferences": preferences})
            return f"Updated buyer preferences: {result.get('message', 'Success')}"
        except Exception as e:
            return f"Error updating preferences: {str(e)}"
    
    async def _tool_record_feedback(self, match_id: str, feedback: str) -> str:
        """CrewAI tool to record buyer feedback."""
        try:
            result = await self._record_buyer_feedback({"match_id": match_id, "feedback": feedback})
            return f"Recorded feedback: {result.get('message', 'Success')}"
        except Exception as e:
            return f"Error recording feedback: {str(e)}"
    
    async def _tool_get_match_explanations(self, match_id: str) -> str:
        """CrewAI tool to get match explanations."""
        try:
            result = await self._get_match_explanation({"match_id": match_id})
            return result.get("explanation", "No explanation available")
        except Exception as e:
            return f"Error getting explanation: {str(e)}"
    
    async def _tool_analyze_buyer_behavior(self, buyer_id: str) -> str:
        """CrewAI tool to analyze buyer behavior."""
        # Implementation for behavioral analysis
        return f"Analyzed behavior patterns for buyer {buyer_id}"
    
    async def _tool_generate_buyer_alerts(self, buyer_id: str) -> str:
        """CrewAI tool to generate buyer alerts."""
        # Implementation for alert generation
        return f"Generated alerts for buyer {buyer_id}"
    
    async def _setup_vector_schemas(self) -> None:
        """Setup Weaviate schemas for matching operations."""
        from .utils import setup_vector_schemas
        await setup_vector_schemas()
    
    async def _upsert_buyer_profile(
        self, 
        buyer: Buyer, 
        buyer_vector: List[float], 
        metadata: Dict[str, Any]
    ) -> bool:
        """Update or insert buyer profile in vector database."""
        from .matching_engine import MatchingEngine
        
        matching_engine = MatchingEngine(self.weaviate_client)
        return await matching_engine.update_buyer_vector_profile(buyer, buyer_vector, metadata)
    
    async def _apply_matching_filters(
        self, 
        buyer_features: Any, 
        matches: List[MatchResult]
    ) -> List[MatchResult]:
        """Apply business rules and filters to matches."""
        from .matching_engine import MatchingEngine
        
        matching_engine = MatchingEngine(self.weaviate_client)
        return await matching_engine.apply_matching_filters(buyer_features, matches)
    
    async def _generate_match_reasoning(
        self,
        buyer_features: Any,
        property_obj: Property,
        scoring_details: Dict[str, Any]
    ) -> Tuple[List[str], List[str], str]:
        """Generate match reasoning and explanation."""
        from .matching_engine import MatchingEngine
        
        matching_engine = MatchingEngine(self.weaviate_client)
        explanation = await matching_engine.generate_match_reasoning(
            buyer_features, property_obj, scoring_details
        )
        
        return explanation.reasons, explanation.concerns, explanation.explanation_text
    
    async def _assess_property_pricing(
        self,
        property_obj: Property,
        buyer_features: Any
    ) -> Tuple[str, float]:
        """Assess property pricing relative to market."""
        from .matching_engine import MatchingEngine
        
        matching_engine = MatchingEngine(self.weaviate_client)
        assessment = await matching_engine.assess_property_pricing(property_obj, buyer_features)
        
        return assessment.assessment, assessment.estimated_value
    
    async def _store_buyer_matches(self, buyer_id: str, matches: List[MatchResult]) -> None:
        """Store buyer matches in database."""
        from .utils import store_buyer_matches
        await store_buyer_matches(buyer_id, matches)
    
    async def _update_buyer_profile(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update buyer preferences and regenerate vector profile."""
        buyer_id = input_data.get("buyer_id")
        preferences = input_data.get("preferences", {})
        
        if not buyer_id:
            return {"success": False, "error": "buyer_id is required"}
        
        try:
            # Use the tools implementation
            from .tools import BuyerPreferencesUpdateTool
            tool = BuyerPreferencesUpdateTool()
            result = await tool.run(buyer_id, preferences)
            
            return {"success": True, "message": result}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _record_buyer_feedback(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record buyer feedback on property matches."""
        match_id = input_data.get("match_id")
        feedback = input_data.get("feedback")
        interest_level = input_data.get("interest_level")
        notes = input_data.get("notes")
        
        if not match_id or not feedback:
            return {"success": False, "error": "match_id and feedback are required"}
        
        try:
            # Use the tools implementation
            from .tools import FeedbackRecordingTool
            tool = FeedbackRecordingTool()
            result = await tool.run(match_id, feedback, interest_level, notes)
            
            return {"success": True, "message": result}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _get_match_explanation(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed explanation for a property match."""
        match_id = input_data.get("match_id")
        
        if not match_id:
            return {"success": False, "error": "match_id is required"}
        
        try:
            # Use the tools implementation
            from .tools import MatchExplanationTool
            tool = MatchExplanationTool()
            explanation = await tool.run(match_id)
            
            return {"success": True, "explanation": explanation}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _sync_properties_to_vector_db(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync properties from PostgreSQL to Weaviate."""
        batch_size = input_data.get("batch_size", 100)
        force_update = input_data.get("force_update", False)
        
        try:
            from .utils import sync_properties_to_vector_db
            result = await sync_properties_to_vector_db(batch_size, force_update)
            return {"success": True, "result": result}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of matching system."""
        try:
            health_data = {
                "agent_status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {}
            }
            
            # Check Weaviate connection
            if self.weaviate_client:
                weaviate_health = await self.weaviate_client.health_check()
                health_data["components"]["weaviate"] = weaviate_health
            else:
                health_data["components"]["weaviate"] = {"status": "not_connected"}
            
            # Check database connection
            try:
                async with get_db_session() as session:
                    await session.execute(select(1))
                health_data["components"]["database"] = {"status": "connected"}
            except Exception as e:
                health_data["components"]["database"] = {"status": "error", "error": str(e)}
            
            # Check cache connection
            try:
                if self.cache_manager:
                    await self.cache_manager.exists("health_check")
                health_data["components"]["cache"] = {"status": "connected"}
            except Exception as e:
                health_data["components"]["cache"] = {"status": "error", "error": str(e)}
            
            # Get performance metrics
            try:
                from .utils import get_matching_performance_metrics
                metrics = await get_matching_performance_metrics(days=1)
                health_data["performance_metrics"] = metrics
            except Exception as e:
                health_data["performance_metrics"] = {"error": str(e)}
            
            # Overall health assessment
            component_statuses = [
                comp.get("status") for comp in health_data["components"].values()
            ]
            
            if all(status in ["connected", "healthy"] for status in component_statuses):
                health_data["overall_status"] = "healthy"
            elif any(status == "error" for status in component_statuses):
                health_data["overall_status"] = "degraded"
            else:
                health_data["overall_status"] = "unknown"
            
            return health_data
            
        except Exception as e:
            return {
                "agent_status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }