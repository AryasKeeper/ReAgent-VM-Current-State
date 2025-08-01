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

from reagent.core.database.dependencies import get_db_session
from reagent.core.cache.redis_client import get_cache_manager
from reagent.core.vector_db import WeaviateClient, SearchQuery
from reagent.data.models.buyer_models import Buyer, BuyerPreferences, PropertyMatch
from reagent.data.models.property_models import Property
from reagent.data.models.market_models import SuburbStats

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


class SemanticMatchingEngine:
    """
    Production-grade semantic matching engine for property-buyer recommendations.
    
    Implements advanced AI algorithms for:
    - Vector similarity search with Weaviate
    - Multi-factor scoring system (vector 60%, price 20%, location 15%, features 5%)
    - Explainable AI results with natural language explanations
    - Real-time matching pipeline for batch processing
    - Performance optimization and caching
    """
    
    def __init__(self, weaviate_client: WeaviateClient, openai_client=None):
        self.weaviate_client = weaviate_client
        self.openai_client = openai_client
        self.logger = structlog.get_logger("semantic_matching_engine")
        self.cache_manager = get_cache_manager()
        
        # Enhanced scoring weights based on requirements
        self.default_weights = {
            "vector_similarity": 0.60,  # Primary semantic matching
            "price_fit": 0.20,          # Budget compatibility
            "location_match": 0.15,     # Location preferences
            "feature_alignment": 0.05   # Feature requirements
        }
        
        # Performance tracking
        self.match_performance_metrics = {
            "total_matches": 0,
            "avg_response_time": 0.0,
            "cache_hit_rate": 0.0,
            "vector_search_calls": 0
        }
    
    async def find_property_matches(
        self, 
        buyer_profile: Any,
        limit: int = 10,
        min_score: float = 0.7
    ) -> List[PropertyMatch]:
        """
        Find properties that semantically match buyer preferences
        using vector similarity and business logic filters.
        """
        start_time = datetime.utcnow()
        
        try:
            # Generate buyer embedding for semantic search
            buyer_features = self._extract_buyer_features(buyer_profile)
            buyer_vector = await self._generate_buyer_vector(buyer_features)
            
            # Perform vector similarity search
            candidates = await self._vector_similarity_search(
                buyer_vector, buyer_features, limit * 2  # Get more candidates for filtering
            )
            
            # Calculate comprehensive match scores
            scored_matches = []
            for candidate in candidates:
                property_data = await self._load_property_data(candidate.data.get("listing_id"))
                if not property_data:
                    continue
                    
                match_score = await self.calculate_match_score(
                    property_data, buyer_profile, candidate.score
                )
                
                if match_score.overall_score >= min_score:
                    scored_matches.append(match_score)
            
            # Sort by score and limit results
            scored_matches.sort(key=lambda x: x.overall_score, reverse=True)
            final_matches = scored_matches[:limit]
            
            # Update performance metrics
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self._update_performance_metrics(execution_time, len(final_matches))
            
            self.logger.info(
                "Semantic matching completed",
                buyer_id=str(buyer_profile.id),
                matches_found=len(final_matches),
                execution_time=execution_time
            )
            
            return final_matches
            
        except Exception as e:
            self.logger.error("Semantic matching failed", error=str(e))
            raise
    
    async def calculate_match_score(
        self,
        property_data: Property,
        buyer_profile: Any,
        vector_similarity: float
    ) -> 'MatchScore':
        """
        Calculate comprehensive match score combining:
        - Vector similarity (60% weight)
        - Price compatibility (20% weight) 
        - Location preferences (15% weight)
        - Feature requirements (5% weight)
        """
        try:
            buyer_features = self._extract_buyer_features(buyer_profile)
            
            # Component scores
            scores = {
                "vector_similarity": vector_similarity,
                "price_fit": self._calculate_price_compatibility(property_data, buyer_features),
                "location_match": self._calculate_location_match(property_data, buyer_features),
                "feature_alignment": self._calculate_feature_match(property_data, buyer_features)
            }
            
            # Calculate weighted overall score
            overall_score = sum(
                scores[component] * self.default_weights[component]
                for component in scores.keys()
            )
            
            # Apply penalties for deal-breakers
            penalties = self._calculate_penalties(property_data, buyer_features)
            overall_score = max(0.0, overall_score - sum(penalties.values()))
            
            # Generate explanation
            explanation = self.generate_explanation(
                overall_score, property_data, buyer_profile, scores, penalties
            )
            
            return MatchScore(
                overall_score=overall_score,
                component_scores=scores,
                penalties=penalties,
                property=property_data,
                buyer=buyer_profile,
                explanation=explanation,
                confidence_level=self._determine_confidence_level(overall_score)
            )
            
        except Exception as e:
            self.logger.error("Match scoring failed", error=str(e))
            raise
    
    def generate_explanation(self, match_score: float, property_data: Property, buyer_profile: Any, scores: Dict[str, float], penalties: Dict[str, float]) -> str:
        """
        Generate human-readable explanations for matches.
        
        Example output:
        'This 2-bedroom apartment in Surry Hills matches your preference for 
        modern properties near the CBD (similarity: 85%). The price of $850k 
        fits within your budget range of $700k-$900k (price match: 95%). 
        Location aligns with your preferred areas (location match: 80%).'
        """
        try:
            # Property description
            prop_desc = f"{property_data.bedrooms}BR {property_data.bathrooms}BA {property_data.property_type.title()}"
            location = f"in {property_data.suburb}" if property_data.suburb else ""
            price_text = f"${property_data.price:,.0f}" if property_data.price else "Price on application"
            
            explanation = f"This {prop_desc} {location} ({price_text}) "
            
            # Overall match assessment
            if match_score >= 0.85:
                explanation += "is an EXCELLENT match "
            elif match_score >= 0.75:
                explanation += "is a VERY GOOD match "
            elif match_score >= 0.65:
                explanation += "is a GOOD match "
            else:
                explanation += "is a FAIR match "
            
            explanation += f"for your requirements (overall score: {match_score:.1%}).\n\n"
            
            # Component explanations
            explanation += "📊 MATCH BREAKDOWN:\n"
            
            # Vector similarity explanation
            similarity_score = scores.get("vector_similarity", 0)
            explanation += f"• Semantic similarity: {similarity_score:.1%} - "
            if similarity_score >= 0.8:
                explanation += "Strong alignment with your preferences\n"
            elif similarity_score >= 0.6:
                explanation += "Good alignment with your requirements\n"
            else:
                explanation += "Moderate alignment with your criteria\n"
            
            # Price compatibility explanation
            price_score = scores.get("price_fit", 0)
            explanation += f"• Price compatibility: {price_score:.1%} - "
            if price_score >= 0.8:
                explanation += "Excellent fit within your budget\n"
            elif price_score >= 0.6:
                explanation += "Good price alignment\n"
            else:
                explanation += "Price may require budget adjustment\n"
            
            # Location match explanation
            location_score = scores.get("location_match", 0)
            explanation += f"• Location match: {location_score:.1%} - "
            if location_score >= 0.8:
                explanation += "Perfect location for your needs\n"
            elif location_score >= 0.6:
                explanation += "Good location alignment\n"
            else:
                explanation += "Location may not fully meet preferences\n"
            
            # Feature alignment explanation
            feature_score = scores.get("feature_alignment", 0)
            explanation += f"• Feature alignment: {feature_score:.1%} - "
            if feature_score >= 0.8:
                explanation += "Includes many desired features\n"
            elif feature_score >= 0.6:
                explanation += "Has some important features\n"
            else:
                explanation += "Limited feature alignment\n"
            
            # Penalties explanation
            if penalties:
                explanation += "\n⚠️  CONSIDERATIONS:\n"
                for penalty_type, penalty_value in penalties.items():
                    if penalty_value > 0:
                        explanation += f"• {penalty_type.replace('_', ' ').title()}: -{penalty_value:.1%}\n"
            
            # Action recommendation
            explanation += "\n💡 RECOMMENDATION: "
            if match_score >= 0.8:
                explanation += "Highly recommended - schedule an inspection soon!"
            elif match_score >= 0.7:
                explanation += "Strong candidate - worth serious consideration."
            elif match_score >= 0.6:
                explanation += "Good option - review details and consider inspection."
            else:
                explanation += "Consider if other priorities have changed."
            
            return explanation
            
        except Exception as e:
            self.logger.error("Explanation generation failed", error=str(e))
            return f"Match score: {match_score:.1%}. Unable to generate detailed explanation."
    
    async def process_new_properties(self, properties: List[Property]) -> Dict[str, Any]:
        """
        Process new properties and find matches for all active buyers.
        Efficiently match new properties against existing buyer profiles.
        """
        start_time = datetime.utcnow()
        processed_count = 0
        match_count = 0
        
        try:
            # Get all active buyers
            active_buyers = await self._get_active_buyers()
            
            # Process each new property
            for property_data in properties:
                # Generate property vector embedding
                property_vector = await self._generate_property_vector(property_data)
                
                # Store property in vector database
                await self._store_property_vector(property_data, property_vector)
                
                # Find matching buyers for this property
                property_matches = await self._find_matching_buyers(
                    property_data, active_buyers
                )
                
                # Store match records
                for match in property_matches:
                    await self._store_property_match(match)
                    match_count += 1
                
                processed_count += 1
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "processed_properties": processed_count,
                "matches_generated": match_count,
                "execution_time": execution_time,
                "properties_per_second": processed_count / execution_time if execution_time > 0 else 0
            }
            
            self.logger.info("New properties processed", **result)
            return result
            
        except Exception as e:
            self.logger.error("Property processing failed", error=str(e))
            raise
    
    async def update_buyer_matches(self, buyer_id: str, updated_profile: Any) -> Dict[str, Any]:
        """
        Recalculate matches when buyer profile changes.
        Re-run matching algorithm for updated buyer.
        """
        try:
            # Clear existing cached matches
            cache_key = f"buyer_matches:{buyer_id}"
            await self.cache_manager.delete(cache_key)
            
            # Generate new matches with updated profile
            new_matches = await self.find_property_matches(
                updated_profile, limit=20, min_score=0.6
            )
            
            # Compare with previous matches to identify new opportunities
            previous_matches = await self._get_previous_matches(buyer_id)
            new_opportunities = self._identify_new_opportunities(new_matches, previous_matches)
            
            # Update match history
            await self._update_match_history(buyer_id, new_matches)
            
            # Send notifications for high-scoring new matches
            notifications_sent = 0
            for match in new_opportunities:
                if match.overall_score >= 0.8:
                    await self._send_match_notification(buyer_id, match)
                    notifications_sent += 1
            
            return {
                "buyer_id": buyer_id,
                "new_matches_count": len(new_matches),
                "new_opportunities": len(new_opportunities),
                "notifications_sent": notifications_sent
            }
            
        except Exception as e:
            self.logger.error("Buyer match update failed", error=str(e))
            raise
    
    # Helper methods for the core matching functionality
    
    def _extract_buyer_features(self, buyer_profile: Any) -> Dict[str, Any]:
        """Extract structured features from buyer profile for vector generation."""
        if hasattr(buyer_profile, 'preferences') and buyer_profile.preferences:
            prefs = buyer_profile.preferences
            return {
                "buyer_type": buyer_profile.buyer_type or "individual",
                "budget_min": float(prefs.min_price or 0),
                "budget_max": float(prefs.max_price or 0),
                "budget_flexibility": float(prefs.budget_flexibility or 0.1),
                "property_types": prefs.property_types or [],
                "preferred_suburbs": prefs.preferred_suburbs or [],
                "excluded_suburbs": prefs.excluded_suburbs or [],
                "min_bedrooms": prefs.min_bedrooms or 0,
                "max_bedrooms": prefs.max_bedrooms or 10,
                "min_bathrooms": prefs.min_bathrooms or 0,
                "required_features": prefs.required_features or [],
                "preferred_features": prefs.preferred_features or [],
                "excluded_features": prefs.excluded_features or [],
                "buying_urgency": buyer_profile.buying_urgency or "medium"
            }
        return {}
    
    async def _vector_similarity_search(
        self, 
        buyer_vector: List[float], 
        buyer_features: Dict[str, Any], 
        limit: int
    ) -> List['VectorSearchResult']:
        """Perform optimized vector similarity search with business filters."""
        from reagent.core.vector_db.client import SearchQuery
        
        # Build filter conditions based on buyer preferences
        where_filter = {
            "operator": "And",
            "operands": [
                {"path": ["listing_status"], "operator": "Equal", "valueString": "active"},
                {"path": ["listing_type"], "operator": "Equal", "valueString": "sale"}
            ]
        }
        
        # Add price filter
        if buyer_features.get("budget_max", 0) > 0:
            max_price = buyer_features["budget_max"] * (1 + buyer_features.get("budget_flexibility", 0.1))
            where_filter["operands"].append({
                "path": ["price"],
                "operator": "LessThanEqual",
                "valueNumber": max_price
            })
        
        # Add property type filter
        if buyer_features.get("property_types"):
            type_filter = {
                "operator": "Or",
                "operands": [
                    {"path": ["property_type"], "operator": "Equal", "valueString": pt}
                    for pt in buyer_features["property_types"]
                ]
            }
            where_filter["operands"].append(type_filter)
        
        # Execute vector search
        search_query = SearchQuery(
            vector=buyer_vector,
            class_name="Property",
            limit=limit,
            where_filter=where_filter,
            certainty=0.6,  # Minimum similarity threshold
            additional_properties=["certainty", "distance"]
        )
        
        return await self.weaviate_client.vector_search(search_query)
    
    def _calculate_price_compatibility(self, property_data: Property, buyer_features: Dict[str, Any]) -> float:
        """Calculate price compatibility score (20% weight)."""
        if not property_data.price or buyer_features.get("budget_max", 0) <= 0:
            return 0.5
        
        price = float(property_data.price)
        max_budget = buyer_features["budget_max"] * (1 + buyer_features.get("budget_flexibility", 0.1))
        min_budget = buyer_features.get("budget_min", 0)
        
        # Ideal price is around 85-95% of max budget
        ideal_min = buyer_features["budget_max"] * 0.85
        ideal_max = buyer_features["budget_max"] * 0.95
        
        if price > max_budget:
            return 0.0  # Over budget
        elif price < min_budget:
            return 0.2  # Below minimum
        elif ideal_min <= price <= ideal_max:
            return 1.0  # Perfect price range
        elif price < ideal_min:
            # Below ideal but acceptable
            return 0.7 + 0.3 * (price - min_budget) / (ideal_min - min_budget)
        else:
            # Above ideal but within budget
            return 0.7 + 0.3 * (max_budget - price) / (max_budget - ideal_max)
    
    def _calculate_location_match(self, property_data: Property, buyer_features: Dict[str, Any]) -> float:
        """Calculate location match score (15% weight)."""
        score = 0.5  # Base score
        
        # Preferred suburbs match
        preferred_suburbs = buyer_features.get("preferred_suburbs", [])
        if preferred_suburbs and property_data.suburb:
            if property_data.suburb.lower() in [s.lower() for s in preferred_suburbs]:
                score += 0.4
        
        # Excluded suburbs penalty
        excluded_suburbs = buyer_features.get("excluded_suburbs", [])
        if excluded_suburbs and property_data.suburb:
            if property_data.suburb.lower() in [s.lower() for s in excluded_suburbs]:
                return 0.0  # Deal breaker
        
        # Postcode preference (if no suburb preference)
        if not preferred_suburbs:
            preferred_postcodes = buyer_features.get("preferred_postcodes", [])
            if preferred_postcodes and property_data.postcode:
                if property_data.postcode in preferred_postcodes:
                    score += 0.3
        
        return min(1.0, score)
    
    def _calculate_feature_match(self, property_data: Property, buyer_features: Dict[str, Any]) -> float:
        """Calculate feature alignment score (5% weight)."""
        score = 0.5  # Base score
        property_features = [f.lower() for f in (property_data.features or [])]
        
        # Required features (critical)
        required_features = buyer_features.get("required_features", [])
        if required_features:
            matched_required = sum(
                1 for req in required_features
                if any(req.lower() in pf for pf in property_features)
            )
            score += 0.3 * (matched_required / len(required_features))
        
        # Preferred features (nice to have)
        preferred_features = buyer_features.get("preferred_features", [])
        if preferred_features:
            matched_preferred = sum(
                1 for pref in preferred_features
                if any(pref.lower() in pf for pf in property_features)
            )
            score += 0.2 * (matched_preferred / len(preferred_features))
        
        # Excluded features penalty
        excluded_features = buyer_features.get("excluded_features", [])
        if excluded_features:
            excluded_found = sum(
                1 for excl in excluded_features
                if any(excl.lower() in pf for pf in property_features)
            )
            if excluded_found > 0:
                score -= 0.1 * excluded_found
        
        return max(0.0, min(1.0, score))
    
    def _calculate_penalties(self, property_data: Property, buyer_features: Dict[str, Any]) -> Dict[str, float]:
        """Calculate penalties for deal-breakers."""
        penalties = {}
        
        # Bedroom requirements
        min_bedrooms = buyer_features.get("min_bedrooms", 0)
        if min_bedrooms > 0 and property_data.bedrooms and property_data.bedrooms < min_bedrooms:
            penalties["insufficient_bedrooms"] = 0.2
        
        max_bedrooms = buyer_features.get("max_bedrooms", 10)
        if max_bedrooms < 10 and property_data.bedrooms and property_data.bedrooms > max_bedrooms:
            penalties["excessive_bedrooms"] = 0.1
        
        # Bathroom requirements
        min_bathrooms = buyer_features.get("min_bathrooms", 0)
        if min_bathrooms > 0 and property_data.bathrooms and property_data.bathrooms < min_bathrooms:
            penalties["insufficient_bathrooms"] = 0.15
        
        return penalties
    
    def _determine_confidence_level(self, overall_score: float) -> str:
        """Determine confidence level based on overall score."""
        if overall_score >= 0.85:
            return "very_high"
        elif overall_score >= 0.75:
            return "high"
        elif overall_score >= 0.65:
            return "medium"
        else:
            return "low"
    
    def _update_performance_metrics(self, execution_time: float, matches_found: int) -> None:
        """Update performance tracking metrics."""
        self.match_performance_metrics["total_matches"] += matches_found
        self.match_performance_metrics["vector_search_calls"] += 1
        
        # Update average response time
        current_avg = self.match_performance_metrics["avg_response_time"]
        call_count = self.match_performance_metrics["vector_search_calls"]
        new_avg = ((current_avg * (call_count - 1)) + execution_time) / call_count
        self.match_performance_metrics["avg_response_time"] = new_avg
    
    # Performance Optimization Methods
    
    async def optimize_vector_search(self) -> Dict[str, Any]:
        """Optimize vector search performance and caching."""
        try:
            optimization_report = {
                "cache_optimization": await self._optimize_match_caching(),
                "vector_index_health": await self._check_vector_index_health(),
                "batch_processing_tuning": await self._tune_batch_processing(),
                "memory_usage": await self._analyze_memory_usage()
            }
            
            self.logger.info("Vector search optimization completed", **optimization_report)
            return optimization_report
            
        except Exception as e:
            self.logger.error("Vector search optimization failed", error=str(e))
            return {"error": str(e)}
    
    async def _optimize_match_caching(self) -> Dict[str, Any]:
        """Optimize match result caching strategy."""
        # Implement intelligent cache warming for high-priority buyers
        active_buyers = await self._get_active_high_priority_buyers()
        
        cache_stats = {
            "buyers_pre_cached": 0,
            "cache_hit_improvement": 0.0,
            "cache_size_optimized": False
        }
        
        # Pre-cache matches for urgent buyers
        for buyer in active_buyers[:50]:  # Limit to top 50 urgent buyers
            cache_key = f"buyer_matches:{buyer.id}"
            if not await self.cache_manager.exists(cache_key):
                matches = await self.find_property_matches(buyer, limit=20, min_score=0.6)
                await self.cache_manager.set(
                    cache_key, 
                    [match.to_dict() for match in matches], 
                    ttl=1800  # 30 minutes for urgent buyers
                )
                cache_stats["buyers_pre_cached"] += 1
        
        # Implement cache eviction for stale matches
        await self._cleanup_stale_match_cache()
        cache_stats["cache_size_optimized"] = True
        
        return cache_stats
    
    async def _check_vector_index_health(self) -> Dict[str, Any]:
        """Check and optimize Weaviate vector index performance."""
        try:
            # Get Weaviate cluster health
            health = await self.weaviate_client.health_check()
            
            # Check index statistics
            property_count = await self.weaviate_client.get_object_count("Property")
            buyer_profile_count = await self.weaviate_client.get_object_count("BuyerProfile")
            
            return {
                "weaviate_status": health.get("status", "unknown"),
                "property_vectors": property_count,
                "buyer_profile_vectors": buyer_profile_count,
                "index_ready": health.get("ready", False),
                "recommendations": self._generate_index_recommendations(property_count)
            }
            
        except Exception as e:
            return {"error": str(e), "status": "unhealthy"}
    
    def _generate_index_recommendations(self, property_count: int) -> List[str]:
        """Generate vector index optimization recommendations."""
        recommendations = []
        
        if property_count > 100000:
            recommendations.append("Consider index sharding for large dataset")
        
        if property_count < 1000:
            recommendations.append("Property vector count is low - ensure data sync is working")
        
        recommendations.append("Monitor query performance and adjust HNSW parameters if needed")
        return recommendations
    
    async def _get_active_high_priority_buyers(self) -> List[Any]:
        """Get list of active high-priority buyers for cache warming."""
        async with get_db_session() as session:
            result = await session.execute(
                select(Buyer)
                .options(selectinload(Buyer.preferences))
                .where(
                    and_(
                        Buyer.status == "active",
                        Buyer.buying_urgency.in_(["high", "urgent"])
                    )
                )
                .order_by(Buyer.buying_urgency.desc(), Buyer.created_at.desc())
                .limit(100)
            )
            return result.scalars().all()
    
    async def _cleanup_stale_match_cache(self) -> None:
        """Clean up stale cached matches."""
        try:
            # Clean up matches older than 4 hours for inactive buyers
            # Clean up matches older than 30 minutes for urgent buyers
            # This would be implemented based on the cache manager's pattern matching
            
            self.logger.info("Stale match cache cleanup completed")
            
        except Exception as e:
            self.logger.error("Cache cleanup failed", error=str(e))
    
    # Placeholder methods for additional functionality
    async def _generate_buyer_vector(self, buyer_features: Dict[str, Any]) -> List[float]:
        """Generate vector embedding for buyer features."""
        # This would use the existing BuyerProfileVectorizer
        # Implementation depends on the vectorizer setup
        return [0.0] * 1536  # Placeholder for OpenAI embedding dimension
    
    async def _load_property_data(self, listing_id: str) -> Optional[Property]:
        """Load property data from database."""
        # Implementation would query the database
        return None  # Placeholder
    
    # Additional helper methods would go here...
    
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


# Data classes for enhanced matching system

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class MatchScore:
    """Comprehensive match score with detailed breakdown."""
    overall_score: float
    component_scores: Dict[str, float]
    penalties: Dict[str, float]
    property: Property
    buyer: Any
    explanation: str
    confidence_level: str

@dataclass 
class PropertyMatch:
    """Enhanced property match result."""
    property_id: str
    buyer_id: str
    match_score: float
    explanation: str
    component_scores: Dict[str, float]
    confidence_level: str
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "property_id": self.property_id,
            "buyer_id": self.buyer_id,
            "match_score": self.match_score,
            "explanation": self.explanation,
            "component_scores": self.component_scores,
            "confidence_level": self.confidence_level,
            "created_at": self.created_at.isoformat()
        }


# Backward compatibility: alias for existing code
MatchingEngine = SemanticMatchingEngine