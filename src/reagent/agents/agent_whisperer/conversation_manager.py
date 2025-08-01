"""
ReAgent Sydney - Conversation Manager

Advanced conversation context management system for maintaining natural, 
contextual multi-turn conversations with real estate agents.

Core Capabilities:
- Multi-turn conversation context tracking
- Intent continuity and topic threading
- User preference learning and adaptation
- Conversation quality monitoring
- Context-aware response generation
- Session management and persistence
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import uuid
from collections import defaultdict, deque
import structlog

from .nlp_processor import QueryIntent, IntentType
from src.core.exceptions import CacheError, AgentExecutionError


class ConversationState(str, Enum):
    """States of a conversation."""
    
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    ERROR = "error"


class InteractionType(str, Enum):
    """Types of interactions within a conversation."""
    
    QUERY = "query"
    CLARIFICATION = "clarification"
    FOLLOW_UP = "follow_up"
    SYSTEM_MESSAGE = "system_message"
    REPORT_REQUEST = "report_request"
    FEEDBACK = "feedback"


@dataclass
class ConversationInteraction:
    """Individual interaction within a conversation."""
    
    interaction_id: str
    timestamp: datetime
    interaction_type: InteractionType
    user_message: str
    agent_response: str
    intent: Optional[QueryIntent] = None
    response_metadata: Dict[str, Any] = field(default_factory=dict)
    user_feedback: Optional[str] = None
    confidence_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "timestamp": self.timestamp.isoformat(),
            "interaction_type": self.interaction_type.value,
            "user_message": self.user_message,
            "agent_response": self.agent_response,
            "intent": self.intent.to_dict() if self.intent else None,
            "response_metadata": self.response_metadata,
            "user_feedback": self.user_feedback,
            "confidence_score": self.confidence_score
        }
    
    def get_summary(self) -> str:
        """Get a brief summary of the interaction."""
        intent_summary = f" ({self.intent.intent_type.value})" if self.intent else ""
        return f"{self.interaction_type.value}{intent_summary}: {self.user_message[:50]}..."


@dataclass
class UserPreferences:
    """User preferences and patterns learned from conversations."""
    
    user_id: str
    preferred_areas: List[str] = field(default_factory=list)
    preferred_property_types: List[str] = field(default_factory=list)
    typical_budget_ranges: List[str] = field(default_factory=list)
    communication_style: str = "professional"  # casual, professional, detailed
    preferred_report_formats: List[str] = field(default_factory=list)
    
    # Interaction patterns
    common_intents: Dict[str, int] = field(default_factory=dict)
    avg_conversation_length: float = 0.0
    peak_activity_hours: List[int] = field(default_factory=list)
    
    # Context preferences
    prefers_detailed_responses: bool = True
    wants_market_context: bool = True
    needs_clarification_help: bool = False
    
    # Learning metadata
    last_updated: datetime = field(default_factory=datetime.utcnow)
    confidence_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "preferred_areas": self.preferred_areas,
            "preferred_property_types": self.preferred_property_types,
            "typical_budget_ranges": self.typical_budget_ranges,
            "communication_style": self.communication_style,
            "preferred_report_formats": self.preferred_report_formats,
            "common_intents": self.common_intents,
            "avg_conversation_length": self.avg_conversation_length,
            "peak_activity_hours": self.peak_activity_hours,
            "prefers_detailed_responses": self.prefers_detailed_responses,
            "wants_market_context": self.wants_market_context,
            "needs_clarification_help": self.needs_clarification_help,
            "last_updated": self.last_updated.isoformat(),
            "confidence_score": self.confidence_score
        }


@dataclass
class TopicContext:
    """Context about ongoing conversation topics."""
    
    topic_id: str
    main_topic: str  # suburb, property_search, market_analysis, etc.
    subtopics: List[str] = field(default_factory=list)
    entities_mentioned: Dict[str, List[str]] = field(default_factory=dict)
    
    # Conversation flow
    current_intent: Optional[IntentType] = None
    previous_intents: List[IntentType] = field(default_factory=list)
    pending_clarifications: List[str] = field(default_factory=list)
    
    # Topic status
    is_resolved: bool = False
    needs_follow_up: bool = False
    resolution_confidence: float = 0.0
    
    def add_entity(self, entity_type: str, entity_value: str) -> None:
        """Add an entity to the topic context."""
        if entity_type not in self.entities_mentioned:
            self.entities_mentioned[entity_type] = []
        if entity_value not in self.entities_mentioned[entity_type]:
            self.entities_mentioned[entity_type].append(entity_value)
    
    def get_entity_values(self, entity_type: str) -> List[str]:
        """Get all values for a specific entity type."""
        return self.entities_mentioned.get(entity_type, [])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "main_topic": self.main_topic,
            "subtopics": self.subtopics,
            "entities_mentioned": self.entities_mentioned,
            "current_intent": self.current_intent.value if self.current_intent else None,
            "previous_intents": [intent.value for intent in self.previous_intents],
            "pending_clarifications": self.pending_clarifications,
            "is_resolved": self.is_resolved,
            "needs_follow_up": self.needs_follow_up,
            "resolution_confidence": self.resolution_confidence
        }


class ConversationContext:
    """Complete context for an ongoing conversation."""
    
    def __init__(self, conversation_id: str, user_id: str, max_history: int = 50):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.max_history = max_history
        
        # Conversation metadata
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.state = ConversationState.ACTIVE
        self.interaction_count = 0
        
        # Conversation history
        self.interactions: deque = deque(maxlen=max_history)
        
        # Topic management
        self.current_topics: Dict[str, TopicContext] = {}
        self.resolved_topics: List[str] = []
        
        # User context
        self.user_preferences: Optional[UserPreferences] = None
        self.session_context: Dict[str, Any] = {}
        
        # Quality metrics
        self.average_confidence: float = 0.0
        self.clarification_requests: int = 0
        self.successful_resolutions: int = 0
    
    def add_interaction(
        self,
        user_message: str,
        agent_response: str,
        interaction_type: InteractionType = InteractionType.QUERY,
        intent: Optional[QueryIntent] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationInteraction:
        """Add a new interaction to the conversation."""
        
        interaction = ConversationInteraction(
            interaction_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            interaction_type=interaction_type,
            user_message=user_message,
            agent_response=agent_response,
            intent=intent,
            response_metadata=metadata or {},
            confidence_score=intent.confidence if intent else 0.0
        )
        
        self.interactions.append(interaction)
        self.interaction_count += 1
        self.last_activity = datetime.utcnow()
        
        # Update topic context if intent is provided
        if intent:
            self._update_topic_context(intent, interaction)
        
        # Update conversation quality metrics
        self._update_quality_metrics(interaction)
        
        return interaction
    
    def get_recent_interactions(self, count: int = 5) -> List[ConversationInteraction]:
        """Get the most recent interactions."""
        return list(self.interactions)[-count:]
    
    def get_context_for_intent(self, intent_type: IntentType) -> Dict[str, Any]:
        """Get relevant context for a specific intent type."""
        
        context = {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "interaction_count": self.interaction_count,
            "recent_intents": self._get_recent_intents(5),
            "current_topics": {k: v.to_dict() for k, v in self.current_topics.items()},
            "user_preferences": self.user_preferences.to_dict() if self.user_preferences else None
        }
        
        # Add intent-specific context
        if intent_type in [IntentType.LISTING_SEARCH, IntentType.BUYER_MATCHING]:
            context["property_search_context"] = self._get_property_search_context()
        
        elif intent_type in [IntentType.MARKET_UPDATE, IntentType.SUBURB_ANALYSIS]:
            context["market_analysis_context"] = self._get_market_analysis_context()
        
        elif intent_type in [IntentType.SELLER_STRATEGY, IntentType.INVESTMENT_ANALYSIS]:
            context["strategic_context"] = self._get_strategic_context()
        
        return context
    
    def get_context_dict(self) -> Dict[str, Any]:
        """Get the full conversation context as a dictionary."""
        
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "state": self.state.value,
            "interaction_count": self.interaction_count,
            "recent_interactions": [
                interaction.to_dict() for interaction in self.get_recent_interactions(10)
            ],
            "current_topics": {k: v.to_dict() for k, v in self.current_topics.items()},
            "resolved_topics": self.resolved_topics,
            "user_preferences": self.user_preferences.to_dict() if self.user_preferences else None,
            "session_context": self.session_context,
            "quality_metrics": {
                "average_confidence": self.average_confidence,
                "clarification_requests": self.clarification_requests,
                "successful_resolutions": self.successful_resolutions
            }
        }
    
    def _update_topic_context(self, intent: QueryIntent, interaction: ConversationInteraction) -> None:
        """Update topic context based on new intent."""
        
        # Determine main topic from intent
        main_topic = self._get_main_topic_from_intent(intent.intent_type)
        
        # Get or create topic context
        if main_topic not in self.current_topics:
            self.current_topics[main_topic] = TopicContext(
                topic_id=str(uuid.uuid4()),
                main_topic=main_topic
            )
        
        topic_context = self.current_topics[main_topic]
        
        # Update topic with new information
        topic_context.current_intent = intent.intent_type
        if intent.intent_type not in topic_context.previous_intents:
            topic_context.previous_intents.append(intent.intent_type)
        
        # Add entities from the intent
        for entity_type, entity_value in intent.entities.items():
            if isinstance(entity_value, list):
                for value in entity_value:
                    topic_context.add_entity(entity_type, str(value))
            else:
                topic_context.add_entity(entity_type, str(entity_value))
        
        # Add any clarification questions as pending
        if intent.clarification_questions:
            topic_context.pending_clarifications.extend(intent.clarification_questions)
        
        # Update resolution status
        if intent.confidence > 0.8 and not intent.needs_clarification():
            topic_context.is_resolved = True
            topic_context.resolution_confidence = intent.confidence
        else:
            topic_context.needs_follow_up = True
    
    def _get_main_topic_from_intent(self, intent_type: IntentType) -> str:
        """Map intent types to main conversation topics."""
        
        topic_mapping = {
            IntentType.LISTING_SEARCH: "property_search",
            IntentType.BUYER_MATCHING: "property_search",
            IntentType.PROPERTY_DETAILS: "property_search",
            
            IntentType.MARKET_UPDATE: "market_analysis",
            IntentType.SUBURB_ANALYSIS: "market_analysis",
            IntentType.PRICE_TRENDS: "market_analysis",
            IntentType.COMPARATIVE_ANALYSIS: "market_analysis",
            
            IntentType.SELLER_STRATEGY: "selling_strategy",
            IntentType.INVESTMENT_ANALYSIS: "investment",
            IntentType.OFF_MARKET_OPPORTUNITIES: "off_market",
            
            IntentType.GENERATE_REPORT: "reporting",
            IntentType.EXPORT_DATA: "reporting"
        }
        
        return topic_mapping.get(intent_type, "general")
    
    def _get_recent_intents(self, count: int) -> List[str]:
        """Get recent intent types as strings."""
        
        recent_intents = []
        for interaction in list(self.interactions)[-count:]:
            if interaction.intent and interaction.intent.intent_type:
                recent_intents.append(interaction.intent.intent_type.value)
        
        return recent_intents
    
    def _get_property_search_context(self) -> Dict[str, Any]:
        """Get context specific to property search conversations."""
        
        search_context = {
            "mentioned_suburbs": [],
            "property_types": [],
            "budget_ranges": [],
            "feature_requirements": [],
            "search_refinements": 0
        }
        
        # Extract from current topics
        if "property_search" in self.current_topics:
            topic = self.current_topics["property_search"]
            search_context["mentioned_suburbs"] = topic.get_entity_values("suburb")
            search_context["property_types"] = topic.get_entity_values("property_type")
            search_context["budget_ranges"] = topic.get_entity_values("price_range")
            search_context["feature_requirements"] = topic.get_entity_values("features")
        
        # Count search refinements
        for interaction in self.interactions:
            if (interaction.intent and 
                interaction.intent.intent_type in [IntentType.LISTING_SEARCH, IntentType.BUYER_MATCHING]):
                search_context["search_refinements"] += 1
        
        return search_context
    
    def _get_market_analysis_context(self) -> Dict[str, Any]:
        """Get context specific to market analysis conversations."""
        
        market_context = {
            "analyzed_suburbs": [],
            "timeframes_mentioned": [],
            "analysis_depth": "basic",
            "comparison_requests": 0
        }
        
        if "market_analysis" in self.current_topics:
            topic = self.current_topics["market_analysis"]
            market_context["analyzed_suburbs"] = topic.get_entity_values("suburb")
            market_context["timeframes_mentioned"] = topic.get_entity_values("timeframe")
            
            # Determine analysis depth based on intents
            if IntentType.COMPARATIVE_ANALYSIS in topic.previous_intents:
                market_context["analysis_depth"] = "detailed"
            elif len(topic.previous_intents) > 2:
                market_context["analysis_depth"] = "comprehensive"
        
        return market_context
    
    def _get_strategic_context(self) -> Dict[str, Any]:
        """Get context specific to strategic conversations (selling, investing)."""
        
        strategic_context = {
            "strategy_type": "unknown",
            "properties_discussed": [],
            "investment_criteria": [],
            "timeline_mentioned": False
        }
        
        # Check selling strategy context
        if "selling_strategy" in self.current_topics:
            strategic_context["strategy_type"] = "selling"
            topic = self.current_topics["selling_strategy"]
            strategic_context["properties_discussed"] = topic.get_entity_values("address")
        
        # Check investment context
        elif "investment" in self.current_topics:
            strategic_context["strategy_type"] = "investment"
            topic = self.current_topics["investment"]
            strategic_context["investment_criteria"] = topic.get_entity_values("property_type")
        
        return strategic_context
    
    def _update_quality_metrics(self, interaction: ConversationInteraction) -> None:
        """Update conversation quality metrics."""
        
        # Update average confidence
        if interaction.confidence_score > 0:
            total_interactions = self.interaction_count
            current_avg = self.average_confidence
            self.average_confidence = (
                (current_avg * (total_interactions - 1) + interaction.confidence_score) / 
                total_interactions
            )
        
        # Count clarification requests
        if interaction.interaction_type == InteractionType.CLARIFICATION:
            self.clarification_requests += 1
        
        # Count successful resolutions (high confidence, no follow-up needed)
        if (interaction.confidence_score > 0.8 and 
            interaction.interaction_type == InteractionType.QUERY):
            self.successful_resolutions += 1


class ConversationManager:
    """
    Advanced conversation context management system.
    
    Manages multi-turn conversations, learns user preferences, and maintains
    contextual understanding across extended interactions with real estate agents.
    """
    
    def __init__(self, max_history: int = 50, cache_manager=None):
        self.max_history = max_history
        self.cache_manager = cache_manager
        
        # Active conversations
        self.active_conversations: Dict[str, ConversationContext] = {}
        
        # User preferences storage
        self.user_preferences: Dict[str, UserPreferences] = {}
        
        # Conversation statistics
        self.conversation_stats = {
            "total_conversations": 0,
            "active_conversations": 0,
            "completed_conversations": 0,
            "avg_conversation_length": 0.0,
            "avg_resolution_time": 0.0,
            "user_satisfaction_score": 0.0
        }
        
        # Configuration
        self.conversation_timeout = timedelta(hours=4)  # Auto-timeout after 4 hours
        self.preference_learning_threshold = 5  # Learn preferences after 5 interactions
    
    async def initialize(self) -> None:
        """Initialize the conversation manager."""
        
        # Load any cached conversations and preferences
        if self.cache_manager:
            await self._load_cached_data()
    
    async def cleanup(self) -> None:
        """Cleanup conversation manager resources."""
        
        # Save active conversations and preferences to cache
        if self.cache_manager:
            await self._save_cached_data()
    
    async def start_conversation(self, user_id: str) -> ConversationContext:
        """Start a new conversation for a user."""
        
        conversation_id = f"conv_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        conversation = ConversationContext(
            conversation_id=conversation_id,
            user_id=user_id,
            max_history=self.max_history
        )
        
        # Load user preferences if available
        if user_id in self.user_preferences:
            conversation.user_preferences = self.user_preferences[user_id]
        
        # Store active conversation
        self.active_conversations[conversation_id] = conversation
        
        # Update statistics
        self.conversation_stats["total_conversations"] += 1
        self.conversation_stats["active_conversations"] += 1
        
        return conversation
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> ConversationContext:
        """Get an existing conversation or create a new one."""
        
        if conversation_id in self.active_conversations:
            conversation = self.active_conversations[conversation_id]
            
            # Check for timeout
            if datetime.utcnow() - conversation.last_activity > self.conversation_timeout:
                conversation.state = ConversationState.TIMEOUT
                await self._complete_conversation(conversation_id)
                # Start a new conversation
                return await self.start_conversation(user_id)
            
            return conversation
        
        else:
            # Try to load from cache or start new
            cached_conversation = await self._load_conversation_from_cache(conversation_id)
            if cached_conversation and cached_conversation.user_id == user_id:
                self.active_conversations[conversation_id] = cached_conversation
                return cached_conversation
            else:
                # Start new conversation
                return await self.start_conversation(user_id)
    
    async def add_interaction(
        self,
        conversation_id: str,
        user_message: str,
        agent_response: str,
        intent: Optional[QueryIntent] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationInteraction:
        """Add an interaction to a conversation."""
        
        if conversation_id not in self.active_conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        conversation = self.active_conversations[conversation_id]
        
        # Determine interaction type
        interaction_type = InteractionType.QUERY
        if intent and intent.needs_clarification():
            interaction_type = InteractionType.CLARIFICATION
        elif metadata and metadata.get("is_follow_up"):
            interaction_type = InteractionType.FOLLOW_UP
        elif metadata and metadata.get("is_report_request"):
            interaction_type = InteractionType.REPORT_REQUEST
        
        # Add interaction to conversation
        interaction = conversation.add_interaction(
            user_message=user_message,
            agent_response=agent_response,
            interaction_type=interaction_type,
            intent=intent,
            metadata=metadata
        )
        
        # Learn from user preferences
        await self._learn_user_preferences(conversation, intent)
        
        # Update conversation in cache
        if self.cache_manager:
            await self._cache_conversation(conversation)
        
        return interaction
    
    async def complete_conversation(self, conversation_id: str, completion_reason: str = "user_ended") -> None:
        """Mark a conversation as completed."""
        
        if conversation_id in self.active_conversations:
            await self._complete_conversation(conversation_id, completion_reason)
    
    async def get_conversation_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get a summary of a conversation."""
        
        if conversation_id not in self.active_conversations:
            return {"error": "Conversation not found"}
        
        conversation = self.active_conversations[conversation_id]
        
        # Generate summary
        summary = {
            "conversation_id": conversation_id,
            "user_id": conversation.user_id,
            "duration": (conversation.last_activity - conversation.created_at).total_seconds(),
            "interaction_count": conversation.interaction_count,
            "topics_discussed": list(conversation.current_topics.keys()),
            "resolved_topics": conversation.resolved_topics,
            "average_confidence": conversation.average_confidence,
            "clarification_requests": conversation.clarification_requests,
            "successful_resolutions": conversation.successful_resolutions,
            "state": conversation.state.value
        }
        
        # Add recent interactions summary
        recent_interactions = conversation.get_recent_interactions(5)
        summary["recent_interactions"] = [
            interaction.get_summary() for interaction in recent_interactions
        ]
        
        # Add dominant intents
        intent_counts = defaultdict(int)
        for interaction in conversation.interactions:
            if interaction.intent:
                intent_counts[interaction.intent.intent_type.value] += 1
        
        summary["dominant_intents"] = dict(sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)[:3])
        
        return summary
    
    async def get_user_preferences(self, user_id: str) -> Optional[UserPreferences]:
        """Get learned preferences for a user."""
        return self.user_preferences.get(user_id)
    
    async def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """Update user preferences manually."""
        
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreferences(user_id=user_id)
        
        user_prefs = self.user_preferences[user_id]
        
        # Update preference fields
        for key, value in preferences.items():
            if hasattr(user_prefs, key):
                setattr(user_prefs, key, value)
        
        user_prefs.last_updated = datetime.utcnow()
        
        # Save to cache
        if self.cache_manager:
            await self._cache_user_preferences(user_id, user_prefs)
    
    async def _learn_user_preferences(self, conversation: ConversationContext, intent: Optional[QueryIntent]) -> None:
        """Learn user preferences from conversation patterns."""
        
        if not intent or conversation.interaction_count < self.preference_learning_threshold:
            return
        
        user_id = conversation.user_id
        
        # Initialize user preferences if not exists
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreferences(user_id=user_id)
        
        user_prefs = self.user_preferences[user_id]
        
        # Learn from entities in the intent
        if "suburb" in intent.entities:
            suburbs = intent.entities["suburb"]
            if isinstance(suburbs, list):
                for suburb in suburbs:
                    if suburb not in user_prefs.preferred_areas:
                        user_prefs.preferred_areas.append(suburb)
            else:
                if suburbs not in user_prefs.preferred_areas:
                    user_prefs.preferred_areas.append(suburbs)
        
        if "property_type" in intent.entities:
            prop_types = intent.entities["property_type"]
            if isinstance(prop_types, list):
                user_prefs.preferred_property_types.extend([pt for pt in prop_types if pt not in user_prefs.preferred_property_types])
            else:
                if prop_types not in user_prefs.preferred_property_types:
                    user_prefs.preferred_property_types.append(prop_types)
        
        if "price_range" in intent.entities:
            price_range = intent.entities["price_range"]
            if price_range not in user_prefs.typical_budget_ranges:
                user_prefs.typical_budget_ranges.append(price_range)
        
        # Learn communication patterns
        if intent.confidence > 0.8:
            # User prefers less detailed responses if they consistently provide high-confidence queries
            if conversation.interaction_count > 10:
                high_confidence_ratio = sum(
                    1 for i in conversation.interactions 
                    if i.intent and i.intent.confidence > 0.8
                ) / conversation.interaction_count
                
                if high_confidence_ratio > 0.7:
                    user_prefs.prefers_detailed_responses = False
        
        # Track common intents
        intent_type = intent.intent_type.value
        if intent_type not in user_prefs.common_intents:
            user_prefs.common_intents[intent_type] = 0
        user_prefs.common_intents[intent_type] += 1
        
        # Update conversation length average
        current_length = conversation.interaction_count
        if user_prefs.avg_conversation_length == 0:
            user_prefs.avg_conversation_length = current_length
        else:
            # Simple moving average
            user_prefs.avg_conversation_length = (
                user_prefs.avg_conversation_length * 0.8 + current_length * 0.2
            )
        
        # Update preferences metadata
        user_prefs.last_updated = datetime.utcnow()
        user_prefs.confidence_score = min(user_prefs.confidence_score + 0.1, 1.0)
        
        # Cache updated preferences
        if self.cache_manager:
            await self._cache_user_preferences(user_id, user_prefs)
    
    async def _complete_conversation(self, conversation_id: str, reason: str = "completed") -> None:
        """Complete a conversation and update statistics."""
        
        if conversation_id not in self.active_conversations:
            return
        
        conversation = self.active_conversations[conversation_id]
        
        # Update conversation state
        if reason == "timeout":
            conversation.state = ConversationState.TIMEOUT
        elif reason == "error":
            conversation.state = ConversationState.ERROR
        else:
            conversation.state = ConversationState.COMPLETED
        
        # Update statistics
        self.conversation_stats["active_conversations"] -= 1
        self.conversation_stats["completed_conversations"] += 1
        
        # Update average conversation length
        total_completed = self.conversation_stats["completed_conversations"]
        current_avg = self.conversation_stats["avg_conversation_length"]
        conversation_length = conversation.interaction_count
        
        self.conversation_stats["avg_conversation_length"] = (
            (current_avg * (total_completed - 1) + conversation_length) / total_completed
        )
        
        # Archive conversation (move to completed storage)
        if self.cache_manager:
            await self._archive_conversation(conversation)
        
        # Remove from active conversations
        del self.active_conversations[conversation_id]
    
    async def save_conversation(self, conversation_id: str, conversation: ConversationContext) -> None:
        """Save a conversation context (used by agent for cleanup)."""
        
        if self.cache_manager:
            await self._cache_conversation(conversation)
    
    async def _load_cached_data(self) -> None:
        """Load conversations and preferences from cache."""
        
        try:
            # Load user preferences
            preferences_key = "conversation_manager:user_preferences"
            cached_prefs = await self.cache_manager.get(preferences_key)
            
            if cached_prefs:
                for user_id, prefs_data in cached_prefs.items():
                    self.user_preferences[user_id] = UserPreferences(**prefs_data)
            
            # Load active conversations (limited number)
            active_convs_key = "conversation_manager:active_conversations"
            cached_convs = await self.cache_manager.get(active_convs_key)
            
            if cached_convs:
                for conv_id, conv_data in cached_convs.items():
                    # Reconstruct conversation context
                    # This would involve deserializing the conversation data
                    pass  # Simplified for this implementation
            
        except Exception as e:
            # Log error but continue - cache loading is not critical
            pass
    
    async def _save_cached_data(self) -> None:
        """Save conversations and preferences to cache."""
        
        if not self.cache_manager:
            return
        
        try:
            # Save user preferences
            preferences_data = {
                user_id: prefs.to_dict() 
                for user_id, prefs in self.user_preferences.items()
            }
            
            preferences_key = "conversation_manager:user_preferences"
            await self.cache_manager.set(preferences_key, preferences_data, ttl=86400 * 7)  # 7 days
            
            # Save active conversations (only essential data)
            active_conversations_data = {
                conv_id: conv.get_context_dict() 
                for conv_id, conv in self.active_conversations.items()
            }
            
            active_convs_key = "conversation_manager:active_conversations"
            await self.cache_manager.set(active_convs_key, active_conversations_data, ttl=14400)  # 4 hours
            
        except Exception as e:
            # Log error but continue - cache saving is not critical
            pass
    
    async def _cache_conversation(self, conversation: ConversationContext) -> None:
        """Cache a single conversation."""
        
        if not self.cache_manager:
            return
        
        try:
            cache_key = f"conversation:{conversation.conversation_id}"
            await self.cache_manager.set(
                cache_key, 
                conversation.get_context_dict(), 
                ttl=14400  # 4 hours
            )
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"Failed to cache conversation: {e}", 
                        conversation_id=conversation.conversation_id, exc_info=True)
            # Non-critical operation, continue without caching
    
    async def _cache_user_preferences(self, user_id: str, preferences: UserPreferences) -> None:
        """Cache user preferences."""
        
        if not self.cache_manager:
            return
        
        try:
            cache_key = f"user_preferences:{user_id}"
            await self.cache_manager.set(cache_key, preferences.to_dict(), ttl=86400 * 7)  # 7 days
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"Failed to cache user preferences: {e}", 
                        user_id=user_id, exc_info=True)
            # Non-critical operation, continue without caching
    
    async def _load_conversation_from_cache(self, conversation_id: str) -> Optional[ConversationContext]:
        """Load a conversation from cache."""
        
        if not self.cache_manager:
            return None
        
        try:
            cache_key = f"conversation:{conversation_id}"
            cached_data = await self.cache_manager.get(cache_key)
            
            if cached_data:
                # Reconstruct conversation context from cached data
                # This would involve deserializing all the conversation components
                # Simplified for this implementation
                return None
            
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"Failed to load conversation from cache: {e}", 
                        conversation_id=conversation_id, exc_info=True)
            # Non-critical operation, return None to indicate cache miss
        
        return None
    
    async def _archive_conversation(self, conversation: ConversationContext) -> None:
        """Archive a completed conversation."""
        
        if not self.cache_manager:
            return
        
        try:
            archive_key = f"conversation_archive:{conversation.conversation_id}"
            await self.cache_manager.set(
                archive_key, 
                conversation.get_context_dict(), 
                ttl=86400 * 30  # 30 days
            )
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"Failed to archive conversation: {e}", 
                        conversation_id=conversation.conversation_id, exc_info=True)
            # Non-critical operation, continue without archiving
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """Get conversation manager statistics."""
        
        return {
            **self.conversation_stats,
            "users_with_preferences": len(self.user_preferences),
            "current_active_conversations": len(self.active_conversations),
            "avg_interactions_per_conversation": (
                sum(conv.interaction_count for conv in self.active_conversations.values()) / 
                max(len(self.active_conversations), 1)
            )
        }
    
    def __repr__(self) -> str:
        return f"<ConversationManager(active={len(self.active_conversations)}, users={len(self.user_preferences)})>"