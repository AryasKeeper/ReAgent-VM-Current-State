"""
ReAgent Sydney - Natural Language Processor

Advanced NLP engine for understanding real estate agent queries and converting them
into structured intents that can be processed by the ReAgent system.

Core Capabilities:
- Intent classification for common real estate queries
- Entity extraction (suburbs, property types, price ranges, etc.)
- Context-aware query understanding
- Query clarification and refinement suggestions
- Confidence scoring for processing decisions
"""

from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import re
import json
from collections import defaultdict

# For production, you'd use more sophisticated NLP libraries like:
# from transformers import pipeline, AutoTokenizer, AutoModel
# from spacy import load as spacy_load
# For this implementation, we'll use pattern matching and rule-based approaches


class IntentType(str, Enum):
    """Supported intent types for real estate queries."""
    
    # Basic interactions
    GREETING = "greeting"
    HELP = "help"
    GOODBYE = "goodbye"
    
    # Property searches
    LISTING_SEARCH = "listing_search"
    PROPERTY_DETAILS = "property_details"
    PRICE_LOOKUP = "price_lookup"
    
    # Market analysis
    MARKET_UPDATE = "market_update"
    SUBURB_ANALYSIS = "suburb_analysis"
    PRICE_TRENDS = "price_trends"
    COMPARATIVE_ANALYSIS = "comparative_analysis"
    
    # Agent services
    BUYER_MATCHING = "buyer_matching"
    SELLER_STRATEGY = "seller_strategy"
    INVESTMENT_ANALYSIS = "investment_analysis"
    
    # Specialized services
    OFF_MARKET_OPPORTUNITIES = "off_market_opportunities"
    AUCTION_ANALYSIS = "auction_analysis"
    RENTAL_ANALYSIS = "rental_analysis"
    
    # Reporting
    GENERATE_REPORT = "generate_report"
    EXPORT_DATA = "export_data"
    
    # System
    CLARIFICATION_NEEDED = "clarification_needed"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    """Types of entities that can be extracted from queries."""
    
    SUBURB = "suburb"
    POSTCODE = "postcode"
    PROPERTY_TYPE = "property_type"
    BEDROOMS = "bedrooms"
    BATHROOMS = "bathrooms"
    PRICE_MIN = "price_min"
    PRICE_MAX = "price_max"
    PRICE_RANGE = "price_range"
    TIMEFRAME = "timeframe"
    FEATURES = "features"
    BUYER_TYPE = "buyer_type"
    REPORT_TYPE = "report_type"
    ADDRESS = "address"
    AGENT_NAME = "agent_name"


@dataclass
class ExtractedEntity:
    """Represents an extracted entity from user input."""
    
    entity_type: EntityType
    value: str
    confidence: float
    start_pos: int
    end_pos: int
    normalized_value: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.entity_type.value,
            "value": self.value,
            "normalized_value": self.normalized_value or self.value,
            "confidence": self.confidence,
            "position": [self.start_pos, self.end_pos],
            "metadata": self.metadata
        }


@dataclass 
class QueryIntent:
    """Structured representation of a parsed user query."""
    
    intent_type: IntentType
    confidence: float
    original_query: str
    entities: Dict[str, Any] = field(default_factory=dict)
    extracted_entities: List[ExtractedEntity] = field(default_factory=list)
    
    # Context and clarifications
    missing_entities: List[EntityType] = field(default_factory=list)
    ambiguous_entities: List[str] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    
    # Processing metadata
    processing_method: str = "rule_based"
    alternative_intents: List[Tuple[IntentType, float]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "original_query": self.original_query,
            "entities": self.entities,
            "extracted_entities": [entity.to_dict() for entity in self.extracted_entities],
            "missing_entities": [e.value for e in self.missing_entities],
            "ambiguous_entities": self.ambiguous_entities,
            "clarification_questions": self.clarification_questions,
            "processing_method": self.processing_method,
            "alternative_intents": [(intent.value, conf) for intent, conf in self.alternative_intents]
        }
    
    def needs_clarification(self) -> bool:
        """Check if this query needs clarification."""
        return len(self.missing_entities) > 0 or len(self.ambiguous_entities) > 0
    
    def is_high_confidence(self, threshold: float = 0.8) -> bool:
        """Check if the intent classification is high confidence."""
        return self.confidence >= threshold


class IntentClassification:
    """Result of intent classification with confidence scores."""
    
    def __init__(self, intent: IntentType, confidence: float, alternatives: List[Tuple[IntentType, float]] = None):
        self.intent = intent
        self.confidence = confidence
        self.alternatives = alternatives or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "alternatives": [(alt.value, conf) for alt, conf in self.alternatives]
        }


class NaturalLanguageProcessor:
    """
    Advanced NLP processor for understanding real estate agent queries.
    
    Uses a combination of rule-based patterns, entity recognition, and 
    contextual understanding to convert natural language into structured intents.
    """
    
    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
        
        # Pattern libraries
        self.intent_patterns = {}
        self.entity_patterns = {}
        self.suburb_database = set()
        self.property_types = set()
        
        # Context tracking
        self.query_history = []
        self.conversation_context = {}
        
        # Performance metrics
        self.classification_stats = {
            "total_queries": 0,
            "high_confidence_classifications": 0,
            "entities_extracted": 0,
            "clarifications_requested": 0
        }
    
    async def initialize(self) -> None:
        """Initialize the NLP processor with patterns and databases."""
        
        # Load intent patterns
        self._load_intent_patterns()
        
        # Load entity patterns
        self._load_entity_patterns()
        
        # Load Sydney suburbs and localities
        await self._load_suburb_database()
        
        # Load property type vocabulary
        self._load_property_types()
        
        # Initialize any ML models (in production, this would load pre-trained models)
        # self.intent_classifier = pipeline("text-classification", model="your-model")
        # self.entity_extractor = pipeline("ner", model="your-ner-model")
        
    async def cleanup(self) -> None:
        """Cleanup NLP processor resources."""
        
        # In production, cleanup model resources
        pass
    
    async def parse_user_query(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> QueryIntent:
        """
        Parse a user query into structured intent and entities.
        
        Args:
            query: The natural language query from the user
            context: Conversation context from previous interactions
            user_context: Additional user context (preferences, history, etc.)
            
        Returns:
            QueryIntent with classified intent and extracted entities
        """
        
        self.classification_stats["total_queries"] += 1
        
        # Clean and normalize query
        normalized_query = self._normalize_query(query)
        
        # Classify intent
        intent_classification = await self._classify_intent(normalized_query, context)
        
        # Extract entities
        extracted_entities = await self._extract_entities(normalized_query, intent_classification.intent)
        
        # Convert entities to structured format
        entity_dict = self._entities_to_dict(extracted_entities)
        
        # Identify missing or ambiguous entities
        missing_entities, ambiguous_entities = self._analyze_entity_completeness(
            intent_classification.intent, entity_dict, extracted_entities
        )
        
        # Generate clarification questions if needed
        clarification_questions = self._generate_clarification_questions(
            intent_classification.intent, missing_entities, ambiguous_entities
        )
        
        # Create query intent
        query_intent = QueryIntent(
            intent_type=intent_classification.intent,
            confidence=intent_classification.confidence,
            original_query=query,
            entities=entity_dict,
            extracted_entities=extracted_entities,
            missing_entities=missing_entities,
            ambiguous_entities=ambiguous_entities,
            clarification_questions=clarification_questions,
            alternative_intents=intent_classification.alternatives
        )
        
        # Update statistics
        if query_intent.is_high_confidence(self.confidence_threshold):
            self.classification_stats["high_confidence_classifications"] += 1
        
        self.classification_stats["entities_extracted"] += len(extracted_entities)
        
        if query_intent.needs_clarification():
            self.classification_stats["clarifications_requested"] += 1
        
        # Store in query history for context
        self.query_history.append({
            "query": query,
            "intent": query_intent,
            "timestamp": datetime.utcnow()
        })
        
        # Keep only recent history
        if len(self.query_history) > 50:
            self.query_history = self.query_history[-50:]
        
        return query_intent
    
    def _load_intent_patterns(self) -> None:
        """Load rule-based patterns for intent classification."""
        
        self.intent_patterns = {
            IntentType.GREETING: [
                r"hello|hi|hey|good morning|good afternoon|good evening",
                r"start|begin|let's start"
            ],
            
            IntentType.HELP: [
                r"help|assist|support|guide|how to|what can you",
                r"don't know|not sure|confused|explain"
            ],
            
            IntentType.LISTING_SEARCH: [
                r"find|search|look for|show me.*(?:property|properties|house|houses|apartment|apartments)",
                r"(?:property|properties|house|houses|apartment|apartments).*(?:for sale|available)",
                r"I need|looking for.*(?:bedroom|br|bath|ba)",
                r"under \$|between \$|around \$.*(?:property|house|apartment)"
            ],
            
            IntentType.PRICE_LOOKUP: [
                r"(?:price|cost|value|worth).*(?:in|at|for)",
                r"how much.*(?:cost|worth|selling for)",
                r"median price|average price|typical price",
                r"what.*(?:selling for|going for|worth)"
            ],
            
            IntentType.MARKET_UPDATE: [
                r"market.*(?:update|condition|status|how)",
                r"what's happening.*market",
                r"current market|market trends|market analysis"
            ],
            
            IntentType.SUBURB_ANALYSIS: [
                r"tell me about|analysis.*(?:suburb|area|region)",
                r"(?:suburb|area|region).*(?:analysis|report|information)",
                r"what's.*like in|how is.*(?:suburb|area|region)"
            ],
            
            IntentType.BUYER_MATCHING: [
                r"match|find.*buyer|buyer.*(?:for|match)",
                r"client.*(?:looking|wants|needs)",
                r"suitable.*buyer|right buyer"
            ],
            
            IntentType.SELLER_STRATEGY: [
                r"sell|selling.*strategy|how to sell",
                r"best.*(?:sell|selling)|when to sell",
                r"pricing.*strategy|auction.*strategy"
            ],
            
            IntentType.INVESTMENT_ANALYSIS: [
                r"investment|invest|roi|return",
                r"good investment|worth investing",
                r"investment.*(?:potential|opportunity)"
            ],
            
            IntentType.OFF_MARKET: [
                r"off market|off-market|private sale",
                r"unlisted|not listed|before market",
                r"exclusive|private.*opportunity"
            ],
            
            IntentType.GENERATE_REPORT: [
                r"report|generate.*report|create.*report",
                r"analysis.*report|market.*report",
                r"export|download|pdf"
            ]
        }
    
    def _load_entity_patterns(self) -> None:
        """Load patterns for entity extraction."""
        
        self.entity_patterns = {
            EntityType.PRICE_RANGE: [
                r"\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)[km]?\s*(?:to|-)\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)[km]?",
                r"between\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)[km]?\s*(?:and|-)\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)[km]?",
                r"under\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)[km]?",
                r"over\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)[km]?",
                r"around\s*\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)[km]?"
            ],
            
            EntityType.BEDROOMS: [
                r"(\d+)\s*(?:bed|bedroom|br)s?",
                r"(\d+)br",
                r"(\d+)\s*(?:bed|bedroom)s?"
            ],
            
            EntityType.BATHROOMS: [
                r"(\d+)\s*(?:bath|bathroom|ba)s?",
                r"(\d+)ba",
                r"(\d+)\s*(?:bath|bathroom)s?"
            ],
            
            EntityType.PROPERTY_TYPE: [
                r"house|houses|home|homes",
                r"apartment|apartments|unit|units",
                r"townhouse|townhouses|terrace|terraces",
                r"villa|villas|duplex|studio"
            ],
            
            EntityType.TIMEFRAME: [
                r"last\s*(\d+)\s*(?:day|days|week|weeks|month|months|year|years)",
                r"past\s*(\d+)\s*(?:day|days|week|weeks|month|months|year|years)",
                r"recent|recently|latest|current",
                r"this\s*(?:week|month|quarter|year)",
                r"(\d+)\s*(?:day|days|week|weeks|month|months|year|years)\s*ago"
            ],
            
            EntityType.FEATURES: [
                r"pool|swimming pool",
                r"garage|parking|car space",
                r"garden|yard|outdoor space",
                r"balcony|terrace|deck",
                r"air conditioning|aircon|a/c",
                r"dishwasher|ensuite|walk-in wardrobe"
            ]
        }
    
    async def _load_suburb_database(self) -> None:
        """Load database of Sydney suburbs and localities."""
        
        # In production, this would load from a comprehensive database
        # For now, we'll use a representative sample of Sydney suburbs
        sydney_suburbs = [
            # Inner City
            "Sydney", "Surry Hills", "Darlinghurst", "Potts Point", "Kings Cross",
            "Ultimo", "Pyrmont", "Haymarket", "Chippendale", "Redfern",
            
            # Eastern Suburbs
            "Bondi", "Bondi Beach", "Bondi Junction", "Bronte", "Coogee",
            "Double Bay", "Rose Bay", "Vaucluse", "Watsons Bay", "Woollahra",
            "Paddington", "Randwick", "Clovelly", "Maroubra", "Eastgardens",
            
            # Northern Beaches
            "Manly", "Dee Why", "Collaroy", "Avalon", "Palm Beach",
            "Mona Vale", "Newport", "Pittwater", "Narrabeen", "Freshwater",
            
            # North Shore
            "North Sydney", "Neutral Bay", "Cremorne", "Mosman", "Chatswood",
            "Willoughby", "Lane Cove", "Artarmon", "St Leonards", "Crows Nest",
            "Kirribilli", "McMahons Point", "Waverton", "Gore Hill",
            
            # Inner West
            "Newtown", "Glebe", "Balmain", "Rozelle", "Leichhardt",
            "Marrickville", "Petersham", "Stanmore", "Enmore", "Camperdown",
            "Annandale", "Lilyfield", "Haberfield", "Summer Hill", "Ashfield",
            
            # Western Suburbs
            "Parramatta", "Westmead", "Blacktown", "Mount Druitt", "Penrith",
            "Liverpool", "Campbelltown", "Bankstown", "Canterbury", "Fairfield",
            
            # Southern Suburbs
            "Kogarah", "Hurstville", "Rockdale", "Brighton-Le-Sands", "Cronulla",
            "Sutherland", "Caringbah", "Miranda", "Gymea", "Kurnell"
        ]
        
        # Add variations and normalize
        for suburb in sydney_suburbs:
            self.suburb_database.add(suburb.lower())
            # Add variations without common words
            self.suburb_database.add(suburb.lower().replace("-", " "))
            self.suburb_database.add(suburb.lower().replace(" ", ""))
    
    def _load_property_types(self) -> None:
        """Load vocabulary of property types."""
        
        property_types = [
            "house", "houses", "home", "homes",
            "apartment", "apartments", "unit", "units", "flat", "flats",
            "townhouse", "townhouses", "terrace", "terraces",
            "villa", "villas", "duplex", "duplexes",
            "studio", "studios", "penthouse", "penthouses",
            "warehouse", "warehouses", "loft", "lofts"
        ]
        
        for prop_type in property_types:
            self.property_types.add(prop_type.lower())
    
    def _normalize_query(self, query: str) -> str:
        """Normalize and clean the input query."""
        
        # Convert to lowercase
        normalized = query.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Handle common abbreviations
        abbreviations = {
            r'\bbr\b': 'bedroom',
            r'\bba\b': 'bathroom', 
            r'\bk\b': '000',
            r'\bm\b': '000000',
            r'\$(\d+)k\b': r'$\1000',
            r'\$(\d+)m\b': r'$\1000000',
            r'\bu/\b': 'unit',
            r'\bapt\b': 'apartment'
        }
        
        for abbrev, expansion in abbreviations.items():
            normalized = re.sub(abbrev, expansion, normalized)
        
        return normalized
    
    async def _classify_intent(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> IntentClassification:
        """Classify the intent of a normalized query."""
        
        # Score each intent type
        intent_scores = defaultdict(float)
        
        for intent_type, patterns in self.intent_patterns.items():
            score = 0.0
            matches = 0
            
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    matches += 1
                    # Weight by pattern specificity (longer patterns = higher weight)
                    pattern_weight = min(len(pattern) / 20.0, 2.0)
                    score += pattern_weight
            
            if matches > 0:
                # Boost score based on number of matching patterns
                intent_scores[intent_type] = score * (1 + matches * 0.1)
        
        # Apply contextual boosting
        if context:
            intent_scores = self._apply_contextual_boosting(intent_scores, context)
        
        # Handle edge cases
        if not intent_scores:
            return IntentClassification(IntentType.UNKNOWN, 0.1)
        
        # Sort by score
        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Calculate confidence based on score separation
        top_score = sorted_intents[0][1]
        second_score = sorted_intents[1][1] if len(sorted_intents) > 1 else 0
        
        # Confidence is higher when there's clear separation between top scores
        confidence = min(top_score / max(top_score + second_score, 0.1), 1.0)
        
        # Create alternatives list
        alternatives = [(intent, score/top_score) for intent, score in sorted_intents[1:4]]
        
        return IntentClassification(
            intent=sorted_intents[0][0],
            confidence=confidence,
            alternatives=alternatives
        )
    
    def _apply_contextual_boosting(
        self, 
        intent_scores: Dict[IntentType, float], 
        context: Dict[str, Any]
    ) -> Dict[IntentType, float]:
        """Apply contextual boosting to intent scores based on conversation history."""
        
        # Boost related intents based on recent queries
        recent_intents = context.get("recent_intents", [])
        
        # Intent relationships for contextual boosting
        related_intents = {
            IntentType.LISTING_SEARCH: [IntentType.PRICE_LOOKUP, IntentType.SUBURB_ANALYSIS],
            IntentType.SUBURB_ANALYSIS: [IntentType.MARKET_UPDATE, IntentType.INVESTMENT_ANALYSIS],
            IntentType.BUYER_MATCHING: [IntentType.LISTING_SEARCH, IntentType.PROPERTY_DETAILS],
            IntentType.SELLER_STRATEGY: [IntentType.PRICE_LOOKUP, IntentType.MARKET_UPDATE]
        }
        
        for recent_intent in recent_intents[-3:]:  # Look at last 3 intents
            if recent_intent in related_intents:
                for related_intent in related_intents[recent_intent]:
                    if related_intent in intent_scores:
                        intent_scores[related_intent] *= 1.2  # 20% boost
        
        return intent_scores
    
    async def _extract_entities(self, query: str, intent: IntentType) -> List[ExtractedEntity]:
        """Extract entities from the query based on the classified intent."""
        
        entities = []
        
        # Extract different types of entities based on patterns
        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, query, re.IGNORECASE)
                
                for match in matches:
                    # Determine confidence based on pattern match quality
                    confidence = self._calculate_entity_confidence(match, entity_type, query)
                    
                    # Extract and normalize value
                    value = match.group(0)
                    normalized_value = self._normalize_entity_value(value, entity_type)
                    
                    entity = ExtractedEntity(
                        entity_type=entity_type,
                        value=value,
                        confidence=confidence,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        normalized_value=normalized_value
                    )
                    
                    entities.append(entity)
        
        # Extract suburbs using the suburb database
        suburb_entities = self._extract_suburbs(query)
        entities.extend(suburb_entities)
        
        # Extract property types
        property_type_entities = self._extract_property_types(query)
        entities.extend(property_type_entities)
        
        # Remove overlapping entities (keep highest confidence)
        entities = self._resolve_entity_overlaps(entities)
        
        return entities
    
    def _extract_suburbs(self, query: str) -> List[ExtractedEntity]:
        """Extract suburb names from the query."""
        
        entities = []
        query_lower = query.lower()
        
        for suburb in self.suburb_database:
            # Look for exact matches and partial matches
            if suburb in query_lower:
                start_pos = query_lower.find(suburb)
                end_pos = start_pos + len(suburb)
                
                # Check if it's a word boundary match
                if (start_pos == 0 or not query_lower[start_pos-1].isalnum()) and \
                   (end_pos >= len(query_lower) or not query_lower[end_pos].isalnum()):
                    
                    confidence = 0.9 if len(suburb) > 4 else 0.7
                    
                    entity = ExtractedEntity(
                        entity_type=EntityType.SUBURB,
                        value=query[start_pos:end_pos],
                        confidence=confidence,
                        start_pos=start_pos,
                        end_pos=end_pos,
                        normalized_value=suburb.title()
                    )
                    
                    entities.append(entity)
        
        return entities
    
    def _extract_property_types(self, query: str) -> List[ExtractedEntity]:
        """Extract property types from the query."""
        
        entities = []
        query_lower = query.lower()
        
        for prop_type in self.property_types:
            if prop_type in query_lower:
                start_pos = query_lower.find(prop_type)
                end_pos = start_pos + len(prop_type)
                
                # Check for word boundaries
                if (start_pos == 0 or not query_lower[start_pos-1].isalnum()) and \
                   (end_pos >= len(query_lower) or not query_lower[end_pos].isalnum()):
                    
                    entity = ExtractedEntity(
                        entity_type=EntityType.PROPERTY_TYPE,
                        value=query[start_pos:end_pos],
                        confidence=0.8,
                        start_pos=start_pos,
                        end_pos=end_pos,
                        normalized_value=self._normalize_property_type(prop_type)
                    )
                    
                    entities.append(entity)
        
        return entities
    
    def _calculate_entity_confidence(self, match: re.Match, entity_type: EntityType, query: str) -> float:
        """Calculate confidence score for an extracted entity."""
        
        base_confidence = 0.7
        
        # Boost confidence for specific entity types
        if entity_type == EntityType.PRICE_RANGE:
            # Higher confidence for well-formatted price ranges
            if '$' in match.group(0):
                base_confidence += 0.2
        
        elif entity_type == EntityType.BEDROOMS or entity_type == EntityType.BATHROOMS:
            # Higher confidence for explicit bedroom/bathroom mentions
            if 'bed' in match.group(0) or 'bath' in match.group(0):
                base_confidence += 0.1
        
        # Adjust for context within the query
        surrounding_context = query[max(0, match.start()-10):match.end()+10].lower()
        
        # Contextual confidence boosters
        if entity_type == EntityType.PROPERTY_TYPE and 'looking for' in surrounding_context:
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def _normalize_entity_value(self, value: str, entity_type: EntityType) -> str:
        """Normalize an entity value to a standard format."""
        
        if entity_type == EntityType.PRICE_RANGE:
            # Convert price strings to standardized format
            value = re.sub(r'[,$]', '', value.lower())
            if 'k' in value:
                value = value.replace('k', '000')
            elif 'm' in value:
                value = value.replace('m', '000000')
            return value
        
        elif entity_type == EntityType.BEDROOMS or entity_type == EntityType.BATHROOMS:
            # Extract just the number
            numbers = re.findall(r'\d+', value)
            return numbers[0] if numbers else value
        
        elif entity_type == EntityType.SUBURB:
            # Title case for suburbs
            return value.title()
        
        elif entity_type == EntityType.PROPERTY_TYPE:
            return self._normalize_property_type(value)
        
        return value
    
    def _normalize_property_type(self, prop_type: str) -> str:
        """Normalize property type to standard categories."""
        
        prop_type_lower = prop_type.lower()
        
        if prop_type_lower in ['house', 'houses', 'home', 'homes']:
            return 'House'
        elif prop_type_lower in ['apartment', 'apartments', 'unit', 'units', 'flat', 'flats']:
            return 'Unit'
        elif prop_type_lower in ['townhouse', 'townhouses', 'terrace', 'terraces']:
            return 'Townhouse'
        elif prop_type_lower in ['villa', 'villas']:
            return 'Villa'
        elif prop_type_lower in ['duplex', 'duplexes']:
            return 'Duplex'
        elif prop_type_lower in ['studio', 'studios']:
            return 'Studio'
        elif prop_type_lower in ['penthouse', 'penthouses']:
            return 'Penthouse'
        else:
            return prop_type.title()
    
    def _resolve_entity_overlaps(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Remove overlapping entities, keeping the highest confidence ones."""
        
        if not entities:
            return entities
        
        # Sort by start position
        entities.sort(key=lambda e: e.start_pos)
        
        resolved = []
        
        for entity in entities:
            # Check if this entity overlaps with any already resolved entity
            overlaps = False
            
            for resolved_entity in resolved:
                if (entity.start_pos < resolved_entity.end_pos and 
                    entity.end_pos > resolved_entity.start_pos):
                    
                    # There's an overlap
                    if entity.confidence > resolved_entity.confidence:
                        # Replace the resolved entity with this higher confidence one
                        resolved.remove(resolved_entity)
                        resolved.append(entity)
                    
                    overlaps = True
                    break
            
            if not overlaps:
                resolved.append(entity)
        
        return resolved
    
    def _entities_to_dict(self, entities: List[ExtractedEntity]) -> Dict[str, Any]:
        """Convert extracted entities to a structured dictionary."""
        
        entity_dict = {}
        
        for entity in entities:
            key = entity.entity_type.value
            
            if key in entity_dict:
                # Handle multiple entities of the same type
                if not isinstance(entity_dict[key], list):
                    entity_dict[key] = [entity_dict[key]]
                entity_dict[key].append(entity.normalized_value or entity.value)
            else:
                entity_dict[key] = entity.normalized_value or entity.value
        
        return entity_dict
    
    def _analyze_entity_completeness(
        self, 
        intent: IntentType, 
        entities: Dict[str, Any],
        extracted_entities: List[ExtractedEntity]
    ) -> Tuple[List[EntityType], List[str]]:
        """Analyze what entities might be missing or ambiguous for the given intent."""
        
        missing_entities = []
        ambiguous_entities = []
        
        # Define required entities for each intent type
        required_entities = {
            IntentType.LISTING_SEARCH: [EntityType.PROPERTY_TYPE],
            IntentType.PRICE_LOOKUP: [EntityType.SUBURB],
            IntentType.SUBURB_ANALYSIS: [EntityType.SUBURB],
            IntentType.BUYER_MATCHING: [EntityType.PROPERTY_TYPE, EntityType.PRICE_RANGE],
            IntentType.SELLER_STRATEGY: [EntityType.SUBURB],
            IntentType.INVESTMENT_ANALYSIS: [EntityType.SUBURB]
        }
        
        # Check for missing required entities
        if intent in required_entities:
            for required_entity in required_entities[intent]:
                if required_entity.value not in entities:
                    missing_entities.append(required_entity)
        
        # Check for ambiguous entities (low confidence)
        for entity in extracted_entities:
            if entity.confidence < 0.6:
                ambiguous_entities.append(f"{entity.entity_type.value}: {entity.value}")
        
        return missing_entities, ambiguous_entities
    
    def _generate_clarification_questions(
        self, 
        intent: IntentType, 
        missing_entities: List[EntityType],
        ambiguous_entities: List[str]
    ) -> List[str]:
        """Generate clarification questions for missing or ambiguous entities."""
        
        questions = []
        
        # Questions for missing entities
        entity_questions = {
            EntityType.SUBURB: "Which suburb or area are you interested in?",
            EntityType.PROPERTY_TYPE: "What type of property are you looking for? (house, apartment, townhouse, etc.)",
            EntityType.PRICE_RANGE: "What's your budget or price range?",
            EntityType.BEDROOMS: "How many bedrooms do you need?",
            EntityType.TIMEFRAME: "What timeframe are you looking at?"
        }
        
        for missing_entity in missing_entities:
            if missing_entity in entity_questions:
                questions.append(entity_questions[missing_entity])
        
        # Questions for ambiguous entities
        if ambiguous_entities:
            questions.append(f"Could you clarify: {', '.join(ambiguous_entities)}?")
        
        # Intent-specific clarification questions
        if intent == IntentType.LISTING_SEARCH and not missing_entities:
            questions.append("Any specific features or requirements?")
        
        elif intent == IntentType.MARKET_UPDATE and EntityType.SUBURB not in [e for e in missing_entities]:
            questions.append("Are you interested in sales data, rental market, or general trends?")
        
        return questions[:3]  # Limit to 3 questions to avoid overwhelming
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics."""
        
        success_rate = 0.0
        if self.classification_stats["total_queries"] > 0:
            success_rate = (
                self.classification_stats["high_confidence_classifications"] / 
                self.classification_stats["total_queries"]
            ) * 100
        
        return {
            "total_queries_processed": self.classification_stats["total_queries"],
            "high_confidence_rate": success_rate,
            "total_entities_extracted": self.classification_stats["entities_extracted"],
            "clarification_rate": (
                self.classification_stats["clarifications_requested"] /
                max(self.classification_stats["total_queries"], 1)
            ) * 100,
            "suburb_database_size": len(self.suburb_database),
            "property_types_known": len(self.property_types),
            "intent_patterns_loaded": len(self.intent_patterns)
        }
    
    def __repr__(self) -> str:
        return f"<NaturalLanguageProcessor(queries={self.classification_stats['total_queries']}, success_rate={self.classification_stats['high_confidence_classifications']}/{self.classification_stats['total_queries']})>"