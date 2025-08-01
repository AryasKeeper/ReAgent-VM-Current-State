"""
Property and Buyer Profile Vectorization

Advanced embedding generation for semantic property matching.
Converts property features and buyer preferences into high-dimensional vectors.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
from scipy.spatial.distance import cosine

import structlog

# Import models for type hints
from reagent.data.models.property_models import Property
from reagent.data.models.buyer_models import Buyer, BuyerPreferences
from reagent.core.config import get_settings
from reagent.core.exceptions import VectorSearchError


@dataclass
class EmbeddingMetadata:
    """Metadata about embedding generation."""
    
    model_name: str
    model_version: str
    embedding_dim: int
    generation_time: datetime
    feature_count: int
    normalization_method: str
    custom_weights: Dict[str, float] = field(default_factory=dict)


@dataclass 
class PropertyFeatures:
    """Structured property features for vectorization."""
    
    # Basic features
    property_type: str
    bedrooms: int
    bathrooms: int 
    car_spaces: int
    land_size: int
    building_size: int
    price: float
    
    # Location features
    suburb: str
    postcode: str
    latitude: float
    longitude: float
    
    # Text features
    title: str
    description: str
    features_list: List[str]
    
    # Market features
    days_on_market: int
    price_per_sqm: float
    suburb_price_percentile: float
    
    # Agent features
    agent_name: str
    agency_name: str
    
    # Additional metadata
    amenities: Dict[str, Any] = field(default_factory=dict)
    market_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BuyerPreferenceFeatures:
    """Structured buyer preferences for vectorization."""
    
    # Budget features
    max_price: float
    min_price: float
    budget_flexibility: float
    
    # Property requirements
    property_types: List[str]
    min_bedrooms: int
    max_bedrooms: int
    min_bathrooms: int
    min_car_spaces: int
    min_land_size: int
    min_building_size: int
    
    # Location preferences
    preferred_suburbs: List[str]
    excluded_suburbs: List[str]
    preferred_postcodes: List[str]
    max_commute_time: int
    
    # Feature preferences
    required_features: List[str]
    preferred_features: List[str]
    excluded_features: List[str]
    
    # Buyer characteristics
    buyer_type: str
    buying_urgency: str
    
    # Investment specific
    rental_yield_target: float
    capital_growth_expectation: str
    
    # Behavioral data
    search_history: List[Dict[str, Any]] = field(default_factory=list)
    interaction_patterns: Dict[str, Any] = field(default_factory=dict)
    preference_weights: Dict[str, float] = field(default_factory=dict)


class BaseVectorizer(ABC):
    """Abstract base class for vectorization components."""
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self.logger = structlog.get_logger(f"vectorizer.{self.__class__.__name__.lower()}")
    
    @abstractmethod
    async def generate_embedding(self, features: Any) -> Tuple[List[float], EmbeddingMetadata]:
        """Generate embedding vector from features."""
        pass
    
    @abstractmethod
    def extract_features(self, source_object: Any) -> Any:
        """Extract structured features from source object."""
        pass
    
    def normalize_vector(self, vector: List[float], method: str = "l2") -> List[float]:
        """Normalize vector using specified method."""
        np_vector = np.array(vector)
        
        if method == "l2":
            norm = np.linalg.norm(np_vector)
            if norm == 0:
                return vector
            return (np_vector / norm).tolist()
        elif method == "min_max":
            min_val, max_val = np_vector.min(), np_vector.max()
            if max_val == min_val:
                return vector
            return ((np_vector - min_val) / (max_val - min_val)).tolist()
        else:
            return vector
    
    def calculate_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """Calculate cosine similarity between vectors."""
        try:
            return 1 - cosine(vector1, vector2)
        except (ValueError, IndexError) as e:
            logger = structlog.get_logger(__name__)
            logger.warning(f"Failed to calculate vector similarity: {e}", exc_info=True)
            return 0.0
        except Exception as e:
            logger = structlog.get_logger(__name__)
            logger.error(f"Unexpected error calculating similarity: {e}", exc_info=True)
            raise VectorSearchError("similarity_calculation", f"Similarity calculation failed: {e}") from e


class PropertyVectorizer(BaseVectorizer):
    """
    Advanced property vectorization for semantic search.
    
    Converts property listings into high-dimensional vectors that capture
    spatial, textual, and market characteristics for similarity matching.
    """
    
    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        
        # Feature weights for different property aspects
        self.feature_weights = {
            "location": 0.25,
            "property_specs": 0.25,
            "price_value": 0.20,
            "features_amenities": 0.15,
            "market_context": 0.10,
            "text_semantic": 0.05
        }
        
        # Categorical encodings
        self.property_type_encoding = {
            "house": [1, 0, 0, 0, 0],
            "unit": [0, 1, 0, 0, 0],
            "townhouse": [0, 0, 1, 0, 0],
            "villa": [0, 0, 0, 1, 0],
            "duplex": [0, 0, 0, 0, 1],
            "other": [0, 0, 0, 0, 0]
        }
    
    def extract_features(self, property_obj: Property) -> PropertyFeatures:
        """Extract structured features from Property model."""
        
        # Calculate derived features
        price_per_sqm = 0
        if property_obj.building_size and property_obj.price:
            price_per_sqm = float(property_obj.price) / property_obj.building_size
        
        # Extract features list
        features_list = property_obj.features or []
        
        # Market context from related data
        market_context = {}
        if hasattr(property_obj, 'market_metrics') and property_obj.market_metrics:
            latest_metrics = property_obj.market_metrics[-1]
            market_context = {
                "view_count": latest_metrics.view_count,
                "enquiry_count": latest_metrics.enquiry_count,
                "suburb_price_percentile": latest_metrics.suburb_price_percentile or 0,
                "sale_probability": latest_metrics.sale_probability or 0
            }
        
        return PropertyFeatures(
            property_type=property_obj.property_type or "house",
            bedrooms=property_obj.bedrooms or 0,
            bathrooms=property_obj.bathrooms or 0,
            car_spaces=property_obj.car_spaces or 0,
            land_size=property_obj.land_size or 0,
            building_size=property_obj.building_size or 0,
            price=float(property_obj.price or 0),
            suburb=property_obj.suburb or "",
            postcode=property_obj.postcode or "",
            latitude=float(property_obj.latitude or 0),
            longitude=float(property_obj.longitude or 0),
            title=property_obj.title or "",
            description=property_obj.description or "",
            features_list=features_list,
            days_on_market=property_obj.days_on_market or 0,
            price_per_sqm=price_per_sqm,
            suburb_price_percentile=market_context.get("suburb_price_percentile", 0),
            agent_name=property_obj.agent.full_name if property_obj.agent else "",
            agency_name=property_obj.agency.name if property_obj.agency else "",
            amenities=property_obj.amenities or {},
            market_context=market_context
        )
    
    async def generate_embedding(
        self, 
        features: PropertyFeatures
    ) -> Tuple[List[float], EmbeddingMetadata]:
        """Generate property embedding vector."""
        
        start_time = datetime.utcnow()
        embedding_components = []
        
        # 1. Location vector (lat/lon normalized + suburb hash)
        location_vector = self._encode_location(features)
        embedding_components.extend(location_vector)
        
        # 2. Property specifications vector
        specs_vector = self._encode_property_specs(features)
        embedding_components.extend(specs_vector)
        
        # 3. Price and value vector
        price_vector = self._encode_price_value(features)
        embedding_components.extend(price_vector)
        
        # 4. Features and amenities vector
        features_vector = self._encode_features_amenities(features)
        embedding_components.extend(features_vector)
        
        # 5. Market context vector
        market_vector = self._encode_market_context(features)
        embedding_components.extend(market_vector)
        
        # 6. Text semantic vector (simplified - would use real embeddings in production)
        text_vector = self._encode_text_semantic(features)
        embedding_components.extend(text_vector)
        
        # Normalize the final embedding
        final_embedding = self.normalize_vector(embedding_components, "l2")
        
        metadata = EmbeddingMetadata(
            model_name="PropertyVectorizer",
            model_version="1.0.0",
            embedding_dim=len(final_embedding),
            generation_time=start_time,
            feature_count=6,
            normalization_method="l2",
            custom_weights=self.feature_weights
        )
        
        self.logger.debug("Generated property embedding",
                         property_type=features.property_type,
                         suburb=features.suburb,
                         embedding_dim=len(final_embedding))
        
        return final_embedding, metadata
    
    def _encode_location(self, features: PropertyFeatures) -> List[float]:
        """Encode location features."""
        # Normalize coordinates to Sydney bounds (-34.2, 150.5) to (-33.3, 151.5)
        lat_norm = (features.latitude + 34.2) / 0.9 if features.latitude else 0.5
        lon_norm = (features.longitude - 150.5) / 1.0 if features.longitude else 0.5
        
        # Postcode numerical encoding
        postcode_num = int(features.postcode) if features.postcode.isdigit() else 2000
        postcode_norm = (postcode_num - 2000) / 999  # Sydney postcodes 2000-2999
        
        # Suburb hash (simplified)
        suburb_hash = hash(features.suburb.lower()) % 1000 / 1000
        
        return [lat_norm, lon_norm, postcode_norm, suburb_hash]
    
    def _encode_property_specs(self, features: PropertyFeatures) -> List[float]:
        """Encode property specifications."""
        # Property type one-hot encoding
        prop_type_vector = self.property_type_encoding.get(
            features.property_type.lower(), [0, 0, 0, 0, 0]
        )
        
        # Normalized room counts
        bedrooms_norm = min(features.bedrooms / 6, 1.0)  # Max 6 bedrooms
        bathrooms_norm = min(features.bathrooms / 4, 1.0)  # Max 4 bathrooms
        car_spaces_norm = min(features.car_spaces / 4, 1.0)  # Max 4 car spaces
        
        # Normalized sizes (log scale)
        land_norm = min(np.log1p(features.land_size) / 10, 1.0) if features.land_size else 0
        building_norm = min(np.log1p(features.building_size) / 8, 1.0) if features.building_size else 0
        
        return (prop_type_vector + 
                [bedrooms_norm, bathrooms_norm, car_spaces_norm, land_norm, building_norm])
    
    def _encode_price_value(self, features: PropertyFeatures) -> List[float]:
        """Encode price and value features."""
        # Log-normalized price (Sydney range $300K - $5M)
        price_norm = min(np.log1p(features.price) / 15.4, 1.0) if features.price else 0
        
        # Price per sqm normalized
        price_per_sqm_norm = min(features.price_per_sqm / 20000, 1.0) if features.price_per_sqm else 0
        
        # Suburb price percentile
        percentile_norm = features.suburb_price_percentile / 100 if features.suburb_price_percentile else 0.5
        
        # Days on market (inverse, fresher is better)
        dom_norm = max(0, 1 - features.days_on_market / 365) if features.days_on_market else 1
        
        return [price_norm, price_per_sqm_norm, percentile_norm, dom_norm]
    
    def _encode_features_amenities(self, features: PropertyFeatures) -> List[float]:
        """Encode property features and amenities."""
        # Common feature categories
        feature_categories = {
            "outdoor": ["pool", "garden", "balcony", "courtyard", "deck", "terrace"],
            "parking": ["garage", "carport", "off_street_parking"],
            "luxury": ["ensuite", "walk_in_robe", "study", "home_office"],
            "kitchen": ["modern_kitchen", "gas_cooking", "dishwasher"],
            "comfort": ["air_conditioning", "heating", "fireplace"]
        }
        
        feature_scores = []
        for category, keywords in feature_categories.items():
            score = sum(1 for keyword in keywords 
                       if any(keyword in feature.lower() for feature in features.features_list))
            feature_scores.append(min(score / len(keywords), 1.0))
        
        return feature_scores
    
    def _encode_market_context(self, features: PropertyFeatures) -> List[float]:
        """Encode market context features."""
        context = features.market_context
        
        # Interest metrics (normalized)
        view_score = min(context.get("view_count", 0) / 1000, 1.0)
        enquiry_score = min(context.get("enquiry_count", 0) / 50, 1.0)
        sale_prob = context.get("sale_probability", 0.5)
        
        return [view_score, enquiry_score, sale_prob]
    
    def _encode_text_semantic(self, features: PropertyFeatures) -> List[float]:
        """Encode text semantic features (simplified)."""
        # In production, would use sentence transformers or similar
        # For now, simple keyword-based encoding
        
        text_content = (features.title + " " + features.description).lower()
        
        semantic_keywords = {
            "luxury": ["luxury", "premium", "high-end", "exclusive", "prestigious"],
            "family": ["family", "children", "kids", "school", "playground"],
            "modern": ["modern", "contemporary", "renovated", "updated", "new"],
            "location": ["convenient", "central", "close", "walk", "transport"],
            "investment": ["investment", "rental", "yield", "return", "portfolio"]
        }
        
        semantic_scores = []
        for category, keywords in semantic_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_content)
            semantic_scores.append(min(score / len(keywords), 1.0))
        
        return semantic_scores


class BuyerProfileVectorizer(BaseVectorizer):
    """
    Advanced buyer preference vectorization for matching.
    
    Converts buyer preferences and behavioral data into vectors that can be
    matched against property vectors for personalized recommendations.
    """
    
    def __init__(self, settings: Optional[Any] = None):
        super().__init__(settings)
        
        # Preference weights
        self.preference_weights = {
            "budget_constraints": 0.30,
            "location_preferences": 0.25,
            "property_requirements": 0.20,
            "feature_preferences": 0.15,
            "behavioral_patterns": 0.10
        }
    
    def extract_features(
        self, 
        buyer: Buyer, 
        preferences: Optional[BuyerPreferences] = None
    ) -> BuyerPreferenceFeatures:
        """Extract structured features from Buyer and BuyerPreferences models."""
        
        if not preferences:
            preferences = buyer.preferences
        
        # Extract behavioral data from interactions
        behavioral_data = {}
        preference_weights = {}
        
        if hasattr(buyer, 'property_interactions'):
            interactions = buyer.property_interactions[-50:]  # Last 50 interactions
            behavioral_data = self._analyze_interaction_patterns(interactions)
        
        if hasattr(buyer, 'search_history'):
            searches = buyer.search_history[-20:]  # Last 20 searches
            preference_weights = self._derive_preference_weights(searches)
        
        return BuyerPreferenceFeatures(
            max_price=float(preferences.max_price or 0),
            min_price=float(preferences.min_price or 0),
            budget_flexibility=float(preferences.budget_flexibility or 0.1),
            property_types=preferences.property_types or [],
            min_bedrooms=preferences.min_bedrooms or 0,
            max_bedrooms=preferences.max_bedrooms or 10,
            min_bathrooms=preferences.min_bathrooms or 0,
            min_car_spaces=preferences.min_car_spaces or 0,
            min_land_size=preferences.min_land_size or 0,
            min_building_size=preferences.min_building_size or 0,
            preferred_suburbs=preferences.preferred_suburbs or [],
            excluded_suburbs=preferences.excluded_suburbs or [],
            preferred_postcodes=preferences.preferred_postcodes or [],
            max_commute_time=preferences.max_commute_time or 60,
            required_features=preferences.required_features or [],
            preferred_features=preferences.preferred_features or [],
            excluded_features=preferences.excluded_features or [],
            buyer_type=buyer.buyer_type or "individual",
            buying_urgency=buyer.buying_urgency or "medium",
            rental_yield_target=float(preferences.rental_yield_target or 0),
            capital_growth_expectation=preferences.capital_growth_expectation or "medium",
            interaction_patterns=behavioral_data,
            preference_weights=preference_weights
        )
    
    async def generate_embedding(
        self, 
        features: BuyerPreferenceFeatures
    ) -> Tuple[List[float], EmbeddingMetadata]:
        """Generate buyer preference embedding vector."""
        
        start_time = datetime.utcnow()
        embedding_components = []
        
        # 1. Budget constraints vector
        budget_vector = self._encode_budget_constraints(features)
        embedding_components.extend(budget_vector)
        
        # 2. Location preferences vector
        location_vector = self._encode_location_preferences(features)
        embedding_components.extend(location_vector)
        
        # 3. Property requirements vector
        requirements_vector = self._encode_property_requirements(features)
        embedding_components.extend(requirements_vector)
        
        # 4. Feature preferences vector
        features_vector = self._encode_feature_preferences(features)
        embedding_components.extend(features_vector)
        
        # 5. Behavioral patterns vector
        behavioral_vector = self._encode_behavioral_patterns(features)
        embedding_components.extend(behavioral_vector)
        
        # Normalize the final embedding
        final_embedding = self.normalize_vector(embedding_components, "l2")
        
        metadata = EmbeddingMetadata(
            model_name="BuyerProfileVectorizer",
            model_version="1.0.0",
            embedding_dim=len(final_embedding),
            generation_time=start_time,
            feature_count=5,
            normalization_method="l2",
            custom_weights=self.preference_weights
        )
        
        self.logger.debug("Generated buyer embedding",
                         buyer_type=features.buyer_type,
                         max_price=features.max_price,
                         embedding_dim=len(final_embedding))
        
        return final_embedding, metadata
    
    def _encode_budget_constraints(self, features: BuyerPreferenceFeatures) -> List[float]:
        """Encode budget constraint features."""
        # Log-normalized price range
        max_price_norm = min(np.log1p(features.max_price) / 15.4, 1.0) if features.max_price else 0
        min_price_norm = min(np.log1p(features.min_price) / 15.4, 1.0) if features.min_price else 0
        
        # Budget range and flexibility
        budget_range = features.max_price - features.min_price if features.max_price and features.min_price else 0
        range_norm = min(np.log1p(budget_range) / 15.4, 1.0)
        flexibility_norm = features.budget_flexibility
        
        return [max_price_norm, min_price_norm, range_norm, flexibility_norm]
    
    def _encode_location_preferences(self, features: BuyerPreferenceFeatures) -> List[float]:
        """Encode location preference features."""
        # Suburb preference vectors (simplified hash-based)
        preferred_hash = sum(hash(suburb.lower()) % 1000 for suburb in features.preferred_suburbs) / len(features.preferred_suburbs) / 1000 if features.preferred_suburbs else 0.5
        excluded_hash = sum(hash(suburb.lower()) % 1000 for suburb in features.excluded_suburbs) / len(features.excluded_suburbs) / 1000 if features.excluded_suburbs else 0.5
        
        # Postcode preference vector
        postcode_hash = sum(int(pc) if pc.isdigit() else 2000 for pc in features.preferred_postcodes) / len(features.preferred_postcodes) if features.preferred_postcodes else 2500
        postcode_norm = (postcode_hash - 2000) / 999
        
        # Commute time preference
        commute_norm = min(features.max_commute_time / 120, 1.0)  # Max 2 hours
        
        return [preferred_hash, excluded_hash, postcode_norm, commute_norm]
    
    def _encode_property_requirements(self, features: BuyerPreferenceFeatures) -> List[float]:
        """Encode property requirement features."""
        # Property type preferences (multi-hot encoding)
        property_types = set(pt.lower() for pt in features.property_types)
        type_vector = [
            1 if "house" in property_types else 0,
            1 if "unit" in property_types else 0,
            1 if "townhouse" in property_types else 0,
            1 if "villa" in property_types else 0,
            1 if "duplex" in property_types else 0
        ]
        
        # Room requirements
        min_bed_norm = min(features.min_bedrooms / 6, 1.0)
        max_bed_norm = min(features.max_bedrooms / 6, 1.0)
        min_bath_norm = min(features.min_bathrooms / 4, 1.0)
        min_car_norm = min(features.min_car_spaces / 4, 1.0)
        
        # Size requirements
        min_land_norm = min(np.log1p(features.min_land_size) / 10, 1.0) if features.min_land_size else 0
        min_building_norm = min(np.log1p(features.min_building_size) / 8, 1.0) if features.min_building_size else 0
        
        return type_vector + [min_bed_norm, max_bed_norm, min_bath_norm, min_car_norm, min_land_norm, min_building_norm]
    
    def _encode_feature_preferences(self, features: BuyerPreferenceFeatures) -> List[float]:
        """Encode feature preference features."""
        # Feature categories
        all_features = features.required_features + features.preferred_features + features.excluded_features
        
        feature_categories = {
            "outdoor": ["pool", "garden", "balcony", "courtyard", "deck", "terrace"],
            "parking": ["garage", "carport", "off_street_parking"],
            "luxury": ["ensuite", "walk_in_robe", "study", "home_office"],
            "kitchen": ["modern_kitchen", "gas_cooking", "dishwasher"],
            "comfort": ["air_conditioning", "heating", "fireplace"]
        }
        
        category_scores = []
        for category, keywords in feature_categories.items():
            # Score based on required (1.0), preferred (0.5), excluded (-0.5)
            score = 0
            for keyword in keywords:
                if any(keyword in feat.lower() for feat in features.required_features):
                    score += 1.0
                elif any(keyword in feat.lower() for feat in features.preferred_features):
                    score += 0.5
                elif any(keyword in feat.lower() for feat in features.excluded_features):
                    score -= 0.5
            
            category_scores.append(max(-1, min(1, score / len(keywords))))
        
        return category_scores
    
    def _encode_behavioral_patterns(self, features: BuyerPreferenceFeatures) -> List[float]:
        """Encode behavioral pattern features."""
        patterns = features.interaction_patterns
        
        # Behavioral metrics
        view_frequency = patterns.get("avg_daily_views", 0) / 10  # Normalize to 10 views/day
        engagement_depth = patterns.get("avg_session_duration", 0) / 600  # Normalize to 10 minutes
        interest_consistency = patterns.get("interest_score_variance", 1.0)  # Lower variance = more consistent
        feature_focus = patterns.get("feature_focus_score", 0.5)
        
        # Urgency and buyer type encoding
        urgency_map = {"low": 0.25, "medium": 0.5, "high": 0.75, "urgent": 1.0}
        urgency_score = urgency_map.get(features.buying_urgency, 0.5)
        
        buyer_type_map = {"individual": 0.2, "first_home_buyer": 0.4, "upgrader": 0.6, "investor": 0.8}
        buyer_type_score = buyer_type_map.get(features.buyer_type, 0.2)
        
        return [
            min(view_frequency, 1.0),
            min(engagement_depth, 1.0),
            max(0, min(1, 2 - interest_consistency)),  # Invert variance
            feature_focus,
            urgency_score,
            buyer_type_score
        ]
    
    def _analyze_interaction_patterns(self, interactions: List[Any]) -> Dict[str, float]:
        """Analyze buyer interaction patterns."""
        if not interactions:
            return {}
        
        # Calculate interaction metrics
        total_duration = sum(i.interaction_duration or 0 for i in interactions)
        avg_duration = total_duration / len(interactions)
        
        # Interest level distribution
        interest_levels = [i.interest_level for i in interactions if i.interest_level]
        interest_map = {"low": 1, "medium": 2, "high": 3, "very_high": 4}
        interest_scores = [interest_map.get(level, 2) for level in interest_levels]
        
        avg_interest = sum(interest_scores) / len(interest_scores) if interest_scores else 2
        interest_variance = np.var(interest_scores) if len(interest_scores) > 1 else 1.0
        
        return {
            "avg_session_duration": avg_duration,
            "avg_daily_views": len(interactions) / 30,  # Assuming 30-day window
            "interest_score_variance": interest_variance,
            "feature_focus_score": 0.5  # Would calculate from actual feature interactions
        }
    
    def _derive_preference_weights(self, searches: List[Any]) -> Dict[str, float]:
        """Derive preference weights from search history."""
        if not searches:
            return {}
        
        # Analyze search filter patterns
        weight_adjustments = {}
        
        for search in searches:
            filters = search.search_filters or {}
            
            # Adjust weights based on filter usage frequency
            if "price" in filters:
                weight_adjustments["budget_constraints"] = weight_adjustments.get("budget_constraints", 0) + 0.1
            if "suburb" in filters or "postcode" in filters:
                weight_adjustments["location_preferences"] = weight_adjustments.get("location_preferences", 0) + 0.1
            if "bedrooms" in filters or "property_type" in filters:
                weight_adjustments["property_requirements"] = weight_adjustments.get("property_requirements", 0) + 0.1
        
        # Normalize weights
        total_adjustment = sum(weight_adjustments.values())
        if total_adjustment > 0:
            return {k: v / total_adjustment for k, v in weight_adjustments.items()}
        
        return {}