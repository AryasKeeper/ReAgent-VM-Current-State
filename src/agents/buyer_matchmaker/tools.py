"""
Buyer Matchmaker AU - CrewAI Tools

Specialized tools for property matching, buyer management, and learning operations.
Provides high-level interfaces for CrewAI agent orchestration.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import asdict

from langchain.tools import Tool
from pydantic import BaseModel, Field

from reagent_sydney.core.database.dependencies import get_db_session
from reagent_sydney.core.cache.redis_client import get_cache_manager
from reagent_sydney.core.vector_db import get_weaviate_client
from reagent_sydney.data.models.buyer_models import Buyer, BuyerPreferences, PropertyMatch
from reagent_sydney.data.models.property_models import Property
from reagent_sydney.agents.buyer_matchmaker.matching_engine import MatchingEngine, MatchExplanation

import structlog
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload


class MatchingToolsError(Exception):
    """Custom exception for matching tools errors."""
    pass


class PropertyMatchTool(BaseModel):
    """Tool for finding property matches for buyers."""
    
    name: str = "find_property_matches"
    description: str = (
        "Find matching properties for a buyer using advanced AI matching algorithms. "
        "Takes buyer_id and optional parameters like force_refresh and max_matches."
    )
    
    async def run(self, buyer_id: str, force_refresh: bool = False, max_matches: int = 10) -> str:
        """Execute property matching for a buyer."""
        try:
            logger = structlog.get_logger("tools.property_match")
            
            # Load buyer and preferences
            async with get_db_session() as session:
                result = await session.execute(
                    select(Buyer)
                    .options(
                        selectinload(Buyer.preferences),
                        selectinload(Buyer.property_interactions),
                        selectinload(Buyer.search_history)
                    )
                    .where(Buyer.id == buyer_id)
                )
                buyer = result.scalar_one_or_none()
                
                if not buyer:
                    return f"Buyer {buyer_id} not found"
                
                if not buyer.preferences:
                    return f"Buyer {buyer_id} has no preferences set. Please update buyer preferences first."
            
            # Initialize matching engine
            weaviate_client = await get_weaviate_client()
            matching_engine = MatchingEngine(weaviate_client)
            
            # Check cache first if not forcing refresh
            cache_manager = get_cache_manager()
            cache_key = f"buyer_matches:{buyer_id}"
            
            if not force_refresh:
                cached_matches = await cache_manager.get(cache_key)
                if cached_matches:
                    return f"Found {len(cached_matches)} cached matches for buyer {buyer.full_name}"
            
            # Generate fresh matches
            from reagent_sydney.agents.buyer_matchmaker.agent import BuyerMatchmakerAgent
            agent = BuyerMatchmakerAgent()
            await agent.initialize()
            
            matches = await agent._find_matches_for_buyer(buyer_id, force_refresh)
            
            if not matches:
                return f"No suitable matches found for buyer {buyer.full_name} with current preferences"
            
            # Store matches in database
            await agent._store_buyer_matches(buyer_id, matches[:max_matches])
            
            # Prepare summary
            top_matches = matches[:3]
            summary = f"Found {len(matches)} matches for {buyer.full_name}. Top matches:\n"
            
            for i, match in enumerate(top_matches, 1):
                summary += f"{i}. Score: {match.match_score:.2f} - {', '.join(match.match_reasons[:2])}\n"
            
            logger.info(f"Generated {len(matches)} matches for buyer {buyer_id}")
            return summary
            
        except Exception as e:
            logger.error(f"Error finding matches: {e}")
            return f"Error finding matches: {str(e)}"


class BuyerPreferencesUpdateTool(BaseModel):
    """Tool for updating buyer preferences and regenerating vector profile."""
    
    name: str = "update_buyer_preferences"
    description: str = (
        "Update buyer preferences and regenerate their vector profile for improved matching. "
        "Takes buyer_id and preferences dictionary with updated values."
    )
    
    async def run(self, buyer_id: str, preferences: Dict[str, Any]) -> str:
        """Update buyer preferences."""
        try:
            logger = structlog.get_logger("tools.preferences_update")
            
            async with get_db_session() as session:
                # Load buyer
                result = await session.execute(
                    select(Buyer)
                    .options(selectinload(Buyer.preferences))
                    .where(Buyer.id == buyer_id)
                )
                buyer = result.scalar_one_or_none()
                
                if not buyer:
                    return f"Buyer {buyer_id} not found"
                
                # Update or create preferences
                if buyer.preferences:
                    prefs = buyer.preferences
                else:
                    prefs = BuyerPreferences(buyer_id=buyer.id)
                    session.add(prefs)
                
                # Update preference fields
                update_fields = []
                
                if "max_price" in preferences:
                    prefs.max_price = preferences["max_price"]
                    update_fields.append("max_price")
                
                if "min_price" in preferences:
                    prefs.min_price = preferences["min_price"]
                    update_fields.append("min_price")
                
                if "property_types" in preferences:
                    prefs.property_types = preferences["property_types"]
                    update_fields.append("property_types")
                
                if "preferred_suburbs" in preferences:
                    prefs.preferred_suburbs = preferences["preferred_suburbs"]
                    update_fields.append("preferred_suburbs")
                
                if "excluded_suburbs" in preferences:
                    prefs.excluded_suburbs = preferences["excluded_suburbs"]
                    update_fields.append("excluded_suburbs")
                
                if "min_bedrooms" in preferences:
                    prefs.min_bedrooms = preferences["min_bedrooms"]
                    update_fields.append("min_bedrooms")
                
                if "max_bedrooms" in preferences:
                    prefs.max_bedrooms = preferences["max_bedrooms"]
                    update_fields.append("max_bedrooms")
                
                if "required_features" in preferences:
                    prefs.required_features = preferences["required_features"]
                    update_fields.append("required_features")
                
                if "preferred_features" in preferences:
                    prefs.preferred_features = preferences["preferred_features"]
                    update_fields.append("preferred_features")
                
                if "budget_flexibility" in preferences:
                    prefs.budget_flexibility = preferences["budget_flexibility"]
                    update_fields.append("budget_flexibility")
                
                # Save changes
                await session.commit()
                await session.refresh(prefs)
                
                # Regenerate vector profile
                from reagent_sydney.core.vector_db.embeddings import BuyerProfileVectorizer
                from reagent_sydney.agents.buyer_matchmaker.matching_engine import MatchingEngine
                
                vectorizer = BuyerProfileVectorizer()
                buyer_features = vectorizer.extract_features(buyer, prefs)
                buyer_vector, metadata = await vectorizer.generate_embedding(buyer_features)
                
                # Update vector database
                weaviate_client = await get_weaviate_client()
                matching_engine = MatchingEngine(weaviate_client)
                
                success = await matching_engine.update_buyer_vector_profile(
                    buyer, buyer_vector, metadata.__dict__
                )
                
                if success:
                    # Clear cached matches to force regeneration
                    cache_manager = get_cache_manager()
                    await cache_manager.delete(f"buyer_matches:{buyer_id}")
                    
                    logger.info(f"Updated preferences for buyer {buyer_id}: {', '.join(update_fields)}")
                    return f"Successfully updated {len(update_fields)} preferences for {buyer.full_name} and regenerated matching profile"
                else:
                    return f"Updated preferences but failed to update vector profile for {buyer.full_name}"
                    
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return f"Error updating preferences: {str(e)}"


class FeedbackRecordingTool(BaseModel):
    """Tool for recording buyer feedback on property matches."""
    
    name: str = "record_buyer_feedback"
    description: str = (
        "Record buyer feedback on property matches for machine learning and improvement. "
        "Takes match_id, feedback type, and optional notes."
    )
    
    async def run(
        self, 
        match_id: str, 
        feedback: str, 
        interest_level: Optional[str] = None,
        notes: Optional[str] = None
    ) -> str:
        """Record buyer feedback."""
        try:
            logger = structlog.get_logger("tools.feedback_recording")
            
            async with get_db_session() as session:
                # Find the match
                result = await session.execute(
                    select(PropertyMatch)
                    .options(selectinload(PropertyMatch.buyer))
                    .where(PropertyMatch.id == match_id)
                )
                match = result.scalar_one_or_none()
                
                if not match:
                    return f"Match {match_id} not found"
                
                # Update match with feedback
                match.buyer_feedback = feedback
                match.last_interaction_date = datetime.utcnow()
                match.interaction_count = (match.interaction_count or 0) + 1
                
                # Update status based on feedback
                feedback_lower = feedback.lower()
                if any(word in feedback_lower for word in ["love", "perfect", "interested", "book inspection"]):
                    match.status = "interested"
                elif any(word in feedback_lower for word in ["not interested", "no", "pass", "skip"]):
                    match.status = "not_interested"
                else:
                    match.status = "viewed"
                
                if notes:
                    match.agent_notes = f"{match.agent_notes or ''}\nBuyer feedback ({datetime.utcnow().isoformat()}): {notes}"
                
                await session.commit()
                
                # Learn from feedback for future improvements
                await self._process_feedback_for_learning(match, feedback, interest_level)
                
                logger.info(f"Recorded feedback for match {match_id}: {feedback}")
                return f"Recorded feedback '{feedback}' for {match.buyer.full_name}'s match. Status updated to '{match.status}'"
                
        except Exception as e:
            logger.error(f"Error recording feedback: {e}")
            return f"Error recording feedback: {str(e)}"
    
    async def _process_feedback_for_learning(
        self, 
        match: PropertyMatch, 
        feedback: str, 
        interest_level: Optional[str]
    ) -> None:
        """Process feedback to improve future matching."""
        try:
            # Store learning data in cache for batch processing
            cache_manager = get_cache_manager()
            
            learning_data = {
                "match_id": str(match.id),
                "buyer_id": str(match.buyer_id),
                "property_id": str(match.property_id),
                "match_score": float(match.match_score),
                "feedback": feedback,
                "interest_level": interest_level,
                "timestamp": datetime.utcnow().isoformat(),
                "match_reasons": match.match_reasons,
                "scoring_details": match.scoring_details if hasattr(match, 'scoring_details') else {}
            }
            
            # Add to learning queue
            learning_key = f"learning_feedback:{datetime.utcnow().strftime('%Y%m%d')}"
            existing_data = await cache_manager.get(learning_key) or []
            existing_data.append(learning_data)
            
            # Store with 7-day TTL for batch processing
            await cache_manager.set(learning_key, existing_data, ttl=7*24*3600)
            
        except Exception as e:
            structlog.get_logger("tools.feedback_learning").error(f"Error processing feedback for learning: {e}")


class MatchExplanationTool(BaseModel):
    """Tool for getting detailed explanations of property matches."""
    
    name: str = "get_match_explanations"
    description: str = (
        "Get detailed explanations for why properties were matched to a buyer. "
        "Provides transparent AI reasoning and scoring breakdown."
    )
    
    async def run(self, match_id: str) -> str:
        """Get match explanation."""
        try:
            logger = structlog.get_logger("tools.match_explanation")
            
            async with get_db_session() as session:
                result = await session.execute(
                    select(PropertyMatch)
                    .options(
                        selectinload(PropertyMatch.buyer).selectinload(Buyer.preferences),
                        selectinload(PropertyMatch.property)
                    )
                    .where(PropertyMatch.id == match_id)
                )
                match = result.scalar_one_or_none()
                
                if not match:
                    return f"Match {match_id} not found"
                
                # Use existing explanation if available
                if match.match_explanation:
                    explanation = f"MATCH EXPLANATION for {match.buyer.full_name}\n\n"
                    explanation += f"Property: {match.property.title}\n"
                    explanation += f"Match Score: {match.match_score:.2f}\n\n"
                    explanation += match.match_explanation
                    
                    if match.match_reasons:
                        explanation += f"\n\nKEY REASONS:\n"
                        for reason in match.match_reasons:
                            explanation += f"• {reason}\n"
                    
                    if match.match_concerns:
                        explanation += f"\nCONSIDERATIONS:\n"
                        for concern in match.match_concerns:
                            explanation += f"• {concern}\n"
                    
                    return explanation
                
                # Generate fresh explanation
                from reagent_sydney.core.vector_db.embeddings import BuyerProfileVectorizer
                from reagent_sydney.agents.buyer_matchmaker.matching_engine import MatchingEngine
                
                weaviate_client = await get_weaviate_client()
                matching_engine = MatchingEngine(weaviate_client)
                
                # Extract features
                vectorizer = BuyerProfileVectorizer()
                buyer_features = vectorizer.extract_features(match.buyer, match.buyer.preferences)
                
                # Generate explanation
                scoring_details = match.scoring_details if hasattr(match, 'scoring_details') else {}
                explanation_obj = await matching_engine.generate_match_reasoning(
                    buyer_features, match.property, scoring_details
                )
                
                # Update match with explanation
                match.match_explanation = explanation_obj.explanation_text
                match.match_reasons = explanation_obj.reasons
                match.match_concerns = explanation_obj.concerns
                
                await session.commit()
                
                return explanation_obj.explanation_text
                
        except Exception as e:
            logger.error(f"Error getting match explanation: {e}")
            return f"Error getting match explanation: {str(e)}"


class BuyerBehaviorAnalysisTool(BaseModel):
    """Tool for analyzing buyer behavior patterns."""
    
    name: str = "analyze_buyer_behavior"
    description: str = (
        "Analyze buyer behavior patterns from search history and property interactions "
        "to improve future matching recommendations."
    )
    
    async def run(self, buyer_id: str, analysis_days: int = 30) -> str:
        """Analyze buyer behavior."""
        try:
            logger = structlog.get_logger("tools.behavior_analysis")
            
            async with get_db_session() as session:
                # Load buyer with interaction data
                result = await session.execute(
                    select(Buyer)
                    .options(
                        selectinload(Buyer.preferences),
                        selectinload(Buyer.property_interactions),
                        selectinload(Buyer.search_history),
                        selectinload(Buyer.property_matches)
                    )
                    .where(Buyer.id == buyer_id)
                )
                buyer = result.scalar_one_or_none()
                
                if not buyer:
                    return f"Buyer {buyer_id} not found"
                
                # Analyze recent activity
                cutoff_date = datetime.utcnow() - timedelta(days=analysis_days)
                
                recent_interactions = [
                    interaction for interaction in buyer.property_interactions
                    if interaction.created_at >= cutoff_date
                ]
                
                recent_searches = [
                    search for search in buyer.search_history
                    if search.created_at >= cutoff_date
                ]
                
                recent_matches = [
                    match for match in buyer.property_matches
                    if match.created_at >= cutoff_date
                ]
                
                # Behavior analysis
                analysis = {
                    "activity_level": self._analyze_activity_level(recent_interactions, recent_searches),
                    "preference_patterns": self._analyze_preference_patterns(recent_searches),
                    "engagement_quality": self._analyze_engagement_quality(recent_interactions),
                    "match_feedback_patterns": self._analyze_match_feedback(recent_matches),
                    "search_evolution": self._analyze_search_evolution(recent_searches)
                }
                
                # Generate insights
                insights = self._generate_behavioral_insights(analysis)
                
                # Store analysis for future use
                cache_manager = get_cache_manager()
                cache_key = f"buyer_behavior:{buyer_id}"
                await cache_manager.set(cache_key, analysis, ttl=24*3600)  # 24-hour cache
                
                summary = f"BEHAVIOR ANALYSIS for {buyer.full_name} (Last {analysis_days} days)\n\n"
                summary += f"Activity Level: {analysis['activity_level']['level']}\n"
                summary += f"• {analysis['activity_level']['total_interactions']} property interactions\n"
                summary += f"• {analysis['activity_level']['total_searches']} searches performed\n\n"
                
                summary += "KEY INSIGHTS:\n"
                for insight in insights[:5]:
                    summary += f"• {insight}\n"
                
                if analysis['preference_patterns']['trending_features']:
                    summary += f"\nTrending Interests: {', '.join(analysis['preference_patterns']['trending_features'])}\n"
                
                logger.info(f"Analyzed behavior for buyer {buyer_id}")
                return summary
                
        except Exception as e:
            logger.error(f"Error analyzing buyer behavior: {e}")
            return f"Error analyzing buyer behavior: {str(e)}"
    
    def _analyze_activity_level(self, interactions: List, searches: List) -> Dict[str, Any]:
        """Analyze buyer activity level."""
        total_interactions = len(interactions)
        total_searches = len(searches)
        
        # Calculate engagement scores
        high_engagement_interactions = len([i for i in interactions if i.interest_level in ["high", "very_high"]])
        
        if total_interactions + total_searches >= 20:
            level = "very_high"
        elif total_interactions + total_searches >= 10:
            level = "high"
        elif total_interactions + total_searches >= 5:
            level = "medium"
        else:
            level = "low"
        
        return {
            "level": level,
            "total_interactions": total_interactions,
            "total_searches": total_searches,
            "high_engagement_count": high_engagement_interactions,
            "engagement_rate": high_engagement_interactions / max(total_interactions, 1)
        }
    
    def _analyze_preference_patterns(self, searches: List) -> Dict[str, Any]:
        """Analyze search preference patterns."""
        trending_features = []
        price_ranges = []
        location_focus = []
        
        for search in searches:
            filters = search.search_filters or {}
            
            # Extract trending features
            if "features" in filters:
                trending_features.extend(filters["features"])
            
            # Extract price patterns
            if "min_price" in filters and "max_price" in filters:
                price_ranges.append((filters["min_price"], filters["max_price"]))
            
            # Extract location patterns
            if "suburbs" in filters:
                location_focus.extend(filters["suburbs"])
        
        # Find most common patterns
        from collections import Counter
        feature_counts = Counter(trending_features)
        location_counts = Counter(location_focus)
        
        return {
            "trending_features": [f for f, c in feature_counts.most_common(5)],
            "price_trend": self._analyze_price_trend(price_ranges),
            "location_focus": [l for l, c in location_counts.most_common(3)]
        }
    
    def _analyze_price_trend(self, price_ranges: List[Tuple]) -> Dict[str, Any]:
        """Analyze price search trends."""
        if not price_ranges:
            return {"trend": "stable", "average_range": 0}
        
        # Calculate average ranges and trends
        recent_ranges = price_ranges[-5:]  # Last 5 searches
        early_ranges = price_ranges[:5] if len(price_ranges) > 5 else price_ranges
        
        recent_avg = sum(max_p - min_p for min_p, max_p in recent_ranges) / len(recent_ranges)
        early_avg = sum(max_p - min_p for min_p, max_p in early_ranges) / len(early_ranges)
        
        if recent_avg > early_avg * 1.1:
            trend = "expanding"
        elif recent_avg < early_avg * 0.9:
            trend = "narrowing"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "average_range": recent_avg,
            "recent_max": max(max_p for _, max_p in recent_ranges),
            "recent_min": min(min_p for min_p, _ in recent_ranges)
        }
    
    def _analyze_engagement_quality(self, interactions: List) -> Dict[str, Any]:
        """Analyze quality of buyer engagement."""
        if not interactions:
            return {"quality": "unknown", "depth_score": 0}
        
        # Calculate engagement depth
        total_duration = sum(i.interaction_duration or 0 for i in interactions)
        avg_duration = total_duration / len(interactions)
        
        # Count high-value interactions
        high_value_interactions = len([
            i for i in interactions 
            if i.interaction_type in ["inspection_booking", "enquiry", "phone_call"]
        ])
        
        depth_score = (avg_duration / 300) + (high_value_interactions / len(interactions))  # Normalize to 0-2 scale
        
        if depth_score >= 1.5:
            quality = "high"
        elif depth_score >= 1.0:
            quality = "medium"
        else:
            quality = "low"
        
        return {
            "quality": quality,
            "depth_score": min(depth_score, 2.0),
            "avg_session_duration": avg_duration,
            "high_value_interactions": high_value_interactions
        }
    
    def _analyze_match_feedback(self, matches: List) -> Dict[str, Any]:
        """Analyze feedback patterns on matches."""
        if not matches:
            return {"feedback_rate": 0, "positive_rate": 0}
        
        matches_with_feedback = [m for m in matches if m.buyer_feedback]
        positive_feedback = [
            m for m in matches_with_feedback
            if any(word in (m.buyer_feedback or "").lower() for word in ["love", "perfect", "interested", "yes"])
        ]
        
        feedback_rate = len(matches_with_feedback) / len(matches)
        positive_rate = len(positive_feedback) / max(len(matches_with_feedback), 1)
        
        return {
            "feedback_rate": feedback_rate,
            "positive_rate": positive_rate,
            "total_matches": len(matches),
            "feedback_count": len(matches_with_feedback),
            "positive_count": len(positive_feedback)
        }
    
    def _analyze_search_evolution(self, searches: List) -> Dict[str, Any]:
        """Analyze how search patterns evolved over time."""
        if len(searches) < 3:
            return {"evolution": "insufficient_data"}
        
        # Compare early vs recent searches
        early_searches = searches[:len(searches)//2]
        recent_searches = searches[len(searches)//2:]
        
        evolution_patterns = {
            "price_change": self._compare_price_filters(early_searches, recent_searches),
            "location_change": self._compare_location_filters(early_searches, recent_searches),
            "feature_change": self._compare_feature_filters(early_searches, recent_searches)
        }
        
        return evolution_patterns
    
    def _compare_price_filters(self, early: List, recent: List) -> str:
        """Compare price filters between periods."""
        # Simplified implementation
        return "stable"  # Would implement full comparison logic
    
    def _compare_location_filters(self, early: List, recent: List) -> str:
        """Compare location filters between periods."""
        # Simplified implementation
        return "stable"  # Would implement full comparison logic
    
    def _compare_feature_filters(self, early: List, recent: List) -> str:
        """Compare feature filters between periods."""
        # Simplified implementation
        return "stable"  # Would implement full comparison logic
    
    def _generate_behavioral_insights(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable insights from behavior analysis."""
        insights = []
        
        activity = analysis["activity_level"]
        if activity["level"] == "very_high":
            insights.append("Highly active buyer - prioritize fresh listings and quick notifications")
        elif activity["level"] == "low":
            insights.append("Lower activity buyer - may benefit from curated, high-quality matches")
        
        engagement = analysis["engagement_quality"]
        if engagement["quality"] == "high":
            insights.append("High engagement quality - buyer is serious and ready to act")
        elif engagement["quality"] == "low":
            insights.append("Lower engagement - may need more compelling matches or different approach")
        
        feedback = analysis["match_feedback_patterns"]
        if feedback["positive_rate"] > 0.7:
            insights.append("High satisfaction with matches - current strategy is working well")
        elif feedback["positive_rate"] < 0.3:
            insights.append("Low match satisfaction - preferences may need refinement")
        
        preferences = analysis["preference_patterns"]
        if preferences["trending_features"]:
            insights.append(f"Showing increased interest in: {', '.join(preferences['trending_features'][:3])}")
        
        return insights


class BuyerAlertGenerationTool(BaseModel):
    """Tool for generating alerts about new matching properties."""
    
    name: str = "generate_buyer_alerts"
    description: str = (
        "Generate alerts for buyers when new properties match their criteria. "
        "Supports immediate alerts for urgent buyers and daily digests for others."
    )
    
    async def run(self, buyer_id: Optional[str] = None, alert_type: str = "new_matches") -> str:
        """Generate buyer alerts."""
        try:
            logger = structlog.get_logger("tools.buyer_alerts")
            
            if buyer_id:
                # Generate alerts for specific buyer
                return await self._generate_alerts_for_buyer(buyer_id, alert_type)
            else:
                # Generate alerts for all active buyers
                return await self._generate_alerts_for_all_buyers(alert_type)
                
        except Exception as e:
            logger.error(f"Error generating buyer alerts: {e}")
            return f"Error generating buyer alerts: {str(e)}"
    
    async def _generate_alerts_for_buyer(self, buyer_id: str, alert_type: str) -> str:
        """Generate alerts for a specific buyer."""
        async with get_db_session() as session:
            result = await session.execute(
                select(Buyer)
                .options(selectinload(Buyer.preferences))
                .where(and_(Buyer.id == buyer_id, Buyer.status == "active"))
            )
            buyer = result.scalar_one_or_none()
            
            if not buyer:
                return f"Active buyer {buyer_id} not found"
            
            # Check for new matches
            recent_matches = await self._get_recent_matches(buyer_id)
            
            if not recent_matches:
                return f"No new matches found for {buyer.full_name}"
            
            # Generate alert content
            alert_content = self._format_alert_content(buyer, recent_matches, alert_type)
            
            # Store alert for delivery
            await self._store_alert(buyer_id, alert_content, alert_type)
            
            return f"Generated {alert_type} alert for {buyer.full_name} with {len(recent_matches)} new matches"
    
    async def _generate_alerts_for_all_buyers(self, alert_type: str) -> str:
        """Generate alerts for all active buyers."""
        async with get_db_session() as session:
            result = await session.execute(
                select(Buyer.id, Buyer.full_name)
                .where(Buyer.status == "active")
            )
            active_buyers = result.fetchall()
        
        alerts_generated = 0
        errors = []
        
        for buyer_id, buyer_name in active_buyers:
            try:
                await self._generate_alerts_for_buyer(str(buyer_id), alert_type)
                alerts_generated += 1
            except Exception as e:
                errors.append(f"{buyer_name}: {str(e)}")
        
        summary = f"Generated {alert_type} alerts for {alerts_generated}/{len(active_buyers)} buyers"
        if errors:
            summary += f". Errors: {len(errors)}"
        
        return summary
    
    async def _get_recent_matches(self, buyer_id: str, hours: int = 24) -> List[PropertyMatch]:
        """Get recent matches for a buyer."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        async with get_db_session() as session:
            result = await session.execute(
                select(PropertyMatch)
                .options(selectinload(PropertyMatch.property))
                .where(
                    and_(
                        PropertyMatch.buyer_id == buyer_id,
                        PropertyMatch.first_presented_date >= cutoff_time,
                        PropertyMatch.status == "new"
                    )
                )
                .order_by(PropertyMatch.match_score.desc())
                .limit(10)
            )
            return result.scalars().all()
    
    def _format_alert_content(
        self, 
        buyer: Buyer, 
        matches: List[PropertyMatch], 
        alert_type: str
    ) -> Dict[str, Any]:
        """Format alert content for delivery."""
        
        content = {
            "alert_type": alert_type,
            "buyer_name": buyer.full_name,
            "buyer_id": str(buyer.id),
            "timestamp": datetime.utcnow().isoformat(),
            "match_count": len(matches),
            "matches": []
        }
        
        for match in matches:
            prop = match.property
            match_data = {
                "match_id": str(match.id),
                "property_id": str(prop.id),
                "title": prop.title,
                "address": f"{prop.address_line_1}, {prop.suburb}",
                "price": f"${prop.price:,.0f}" if prop.price else "Price on application",
                "bedrooms": prop.bedrooms,
                "bathrooms": prop.bathrooms,
                "property_type": prop.property_type,
                "match_score": float(match.match_score),
                "key_reasons": match.match_reasons[:3] if match.match_reasons else [],
                "image_url": prop.image_urls[0] if prop.image_urls else None
            }
            content["matches"].append(match_data)
        
        return content
    
    async def _store_alert(self, buyer_id: str, content: Dict[str, Any], alert_type: str) -> None:
        """Store alert for delivery by notification system."""
        cache_manager = get_cache_manager()
        
        # Store in alert queue
        alert_key = f"buyer_alerts:{buyer_id}:{datetime.utcnow().strftime('%Y%m%d%H')}"
        await cache_manager.set(alert_key, content, ttl=24*3600)
        
        # Add to delivery queue
        delivery_queue_key = f"alert_delivery_queue:{alert_type}"
        queue_items = await cache_manager.get(delivery_queue_key) or []
        queue_items.append({
            "buyer_id": buyer_id,
            "alert_key": alert_key,
            "timestamp": datetime.utcnow().isoformat()
        })
        await cache_manager.set(delivery_queue_key, queue_items, ttl=48*3600)


# Tool registry for easy access
BUYER_MATCHMAKER_TOOLS = {
    "find_property_matches": PropertyMatchTool(),
    "update_buyer_preferences": BuyerPreferencesUpdateTool(),
    "record_buyer_feedback": FeedbackRecordingTool(),
    "get_match_explanations": MatchExplanationTool(),
    "analyze_buyer_behavior": BuyerBehaviorAnalysisTool(),
    "generate_buyer_alerts": BuyerAlertGenerationTool()
}


def get_buyer_matchmaker_tools() -> List[Tool]:
    """Get all buyer matchmaker tools as LangChain Tool objects."""
    tools = []
    
    for tool_name, tool_instance in BUYER_MATCHMAKER_TOOLS.items():
        langchain_tool = Tool(
            name=tool_instance.name,
            description=tool_instance.description,
            func=tool_instance.run
        )
        tools.append(langchain_tool)
    
    return tools