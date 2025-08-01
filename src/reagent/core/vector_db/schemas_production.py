"""
Production-Optimized Weaviate Schema Definitions

Combines the best features from both schema versions with production-ready
optimizations for ReAgent Sydney's vector search capabilities.
"""

from typing import Dict, Any, List
from dataclasses import dataclass
import os


@dataclass
class WeaviateSchema:
    """Base Weaviate schema configuration."""
    
    class_name: str
    description: str
    properties: List[Dict[str, Any]]
    vector_index_config: Dict[str, Any]
    inverted_index_config: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schema to Weaviate format."""
        return {
            "class": self.class_name,
            "description": self.description,
            "properties": self.properties,
            "vectorIndexConfig": self.vector_index_config,
            "invertedIndexConfig": self.inverted_index_config
        }


class ProductionPropertySchema:
    """Production-optimized Property vector schema for semantic search."""
    
    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """Get production-optimized property schema for Weaviate."""
        
        # Choose vectorizer based on environment
        use_openai = os.getenv("OPENAI_API_KEY") is not None or True  # Force OpenAI for production cluster
        
        schema = {
            "class": "Property",
            "description": "Real estate property listings with semantic embeddings for Sydney market",
            "properties": [
                {
                    "name": "listing_id",
                    "dataType": ["string"],
                    "description": "External listing identifier",
                    "indexSearchable": True
                },
                {
                    "name": "title",
                    "dataType": ["text"],
                    "description": "Property title",
                    "indexSearchable": True
                },
                {
                    "name": "description",
                    "dataType": ["text"],
                    "description": "Property description",
                    "indexSearchable": True
                },
                {
                    "name": "property_type",
                    "dataType": ["string"],
                    "description": "Property type (House, Unit, Townhouse, etc.)",
                    "indexFilterable": True
                },
                {
                    "name": "suburb",
                    "dataType": ["string"],
                    "description": "Sydney suburb name",
                    "indexFilterable": True
                },
                {
                    "name": "postcode",
                    "dataType": ["string"],
                    "description": "Australian postcode",
                    "indexFilterable": True
                },
                {
                    "name": "state",
                    "dataType": ["string"],
                    "description": "State (NSW for Sydney)",
                    "indexFilterable": True
                },
                {
                    "name": "bedrooms",
                    "dataType": ["int"],
                    "description": "Number of bedrooms",
                    "indexFilterable": True
                },
                {
                    "name": "bathrooms",
                    "dataType": ["int"],
                    "description": "Number of bathrooms",
                    "indexFilterable": True
                },
                {
                    "name": "car_spaces",
                    "dataType": ["int"],
                    "description": "Number of car spaces",
                    "indexFilterable": True
                },
                {
                    "name": "price",
                    "dataType": ["number"],
                    "description": "Property price in AUD",
                    "indexFilterable": True
                },
                {
                    "name": "price_display",
                    "dataType": ["string"],
                    "description": "Price display text",
                    "indexSearchable": True
                },
                {
                    "name": "land_size",
                    "dataType": ["int"],
                    "description": "Land size in square meters",
                    "indexFilterable": True
                },
                {
                    "name": "building_size",
                    "dataType": ["int"],
                    "description": "Building size in square meters",
                    "indexFilterable": True
                },
                {
                    "name": "listing_status",
                    "dataType": ["string"],
                    "description": "Listing status (active, sold, withdrawn)",
                    "indexFilterable": True
                },
                {
                    "name": "listing_type",
                    "dataType": ["string"],
                    "description": "Listing type (sale, rent, auction)",
                    "indexFilterable": True
                },
                {
                    "name": "features",
                    "dataType": ["string[]"],
                    "description": "Property features list",
                    "indexSearchable": True
                },
                {
                    "name": "latitude",
                    "dataType": ["number"],
                    "description": "Latitude coordinate",
                    "indexFilterable": True
                },
                {
                    "name": "longitude",
                    "dataType": ["number"],
                    "description": "Longitude coordinate", 
                    "indexFilterable": True
                },
                {
                    "name": "first_listed_date",
                    "dataType": ["date"],
                    "description": "First listing date",
                    "indexFilterable": True
                },
                {
                    "name": "days_on_market",
                    "dataType": ["int"],
                    "description": "Days on market",
                    "indexFilterable": True
                },
                {
                    "name": "agent_name",
                    "dataType": ["string"],
                    "description": "Primary agent name",
                    "indexSearchable": True
                },
                {
                    "name": "agency_name",
                    "dataType": ["string"],
                    "description": "Real estate agency name",
                    "indexSearchable": True
                },
                {
                    "name": "source",
                    "dataType": ["string"],
                    "description": "Data source (Domain, REA, CoreLogic)",
                    "indexFilterable": True
                },
                {
                    "name": "amenities",
                    "dataType": ["text"],
                    "description": "Structured amenities data (transport, schools, shopping)"
                },
                {
                    "name": "market_context",
                    "dataType": ["text"],
                    "description": "Market trend and context data"
                },
                {
                    "name": "embedding_metadata",
                    "dataType": ["text"],
                    "description": "Embedding generation metadata and quality metrics"
                }
            ]
        }
        
        # Configure vectorizer based on availability
        if use_openai:
            schema.update({
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "ada",
                        "modelVersion": "002", 
                        "type": "text",
                        "dimensions": 1536,
                        "skipPropertiesForVectorization": [
                            "listing_id", "price", "bedrooms", "bathrooms", "car_spaces",
                            "latitude", "longitude", "first_listed_date", "days_on_market",
                            "source", "embedding_metadata"
                        ]
                    }
                }
            })
        else:
            schema.update({
                "vectorizer": "text2vec-transformers",
                "moduleConfig": {
                    "text2vec-transformers": {
                        "poolingStrategy": "masked_mean",
                        "vectorizeClassName": False
                    }
                }
            })
        
        # Production-optimized vector index configuration
        schema["vectorIndexConfig"] = {
            "skip": False,
            "cleanupIntervalSeconds": 300,
            "maxConnections": 64,  # High for property search workloads
            "efConstruction": 128,  # High for better recall
            "ef": -1,  # Dynamic
            "dynamicEfMin": 100,
            "dynamicEfMax": 500,
            "dynamicEfFactor": 8,
            "vectorCacheMaxObjects": 1000000,  # Large cache for Sydney property volume
            "flatSearchCutoff": 40000,
            "distance": "cosine"
        }
        
        # Optimized inverted index for text search
        schema["invertedIndexConfig"] = {
            "bm25": {
                "b": 0.75,
                "k1": 1.2
            },
            "cleanupIntervalSeconds": 60,
            "stopwords": {
                "preset": "en",
                "additions": ["property", "home", "house", "unit", "apartment", "listing"]
            }
        }
        
        return schema


class ProductionBuyerProfileSchema:
    """Production-optimized Buyer profile vector schema for preference matching."""
    
    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """Get production-optimized buyer profile schema for Weaviate."""
        
        # Choose vectorizer based on environment
        use_openai = os.getenv("OPENAI_API_KEY") is not None or True  # Force OpenAI for production cluster
        
        schema = {
            "class": "BuyerProfile",
            "description": "Buyer profiles with preference embeddings for Sydney property matching",
            "properties": [
                {
                    "name": "buyer_id",
                    "dataType": ["string"],
                    "description": "Buyer UUID identifier",
                    "indexFilterable": True
                },
                {
                    "name": "full_name",
                    "dataType": ["string"],
                    "description": "Buyer full name",
                    "indexSearchable": True
                },
                {
                    "name": "buyer_type",
                    "dataType": ["string"],
                    "description": "Buyer type (owner_occupier, investor, first_home_buyer)",
                    "indexFilterable": True
                },
                {
                    "name": "buying_urgency",
                    "dataType": ["string"],
                    "description": "Buying urgency level (high, medium, low)",
                    "indexFilterable": True
                },
                {
                    "name": "max_price",
                    "dataType": ["number"],
                    "description": "Maximum budget in AUD",
                    "indexFilterable": True
                },
                {
                    "name": "min_price",
                    "dataType": ["number"],
                    "description": "Minimum budget in AUD",
                    "indexFilterable": True
                },
                {
                    "name": "budget_flexibility",
                    "dataType": ["number"],
                    "description": "Budget flexibility percentage (0-1)",
                    "indexFilterable": True
                },
                {
                    "name": "property_types",
                    "dataType": ["string[]"],
                    "description": "Preferred property types",
                    "indexFilterable": True
                },
                {
                    "name": "preferred_suburbs",
                    "dataType": ["string[]"],
                    "description": "Preferred Sydney suburbs",
                    "indexFilterable": True
                },
                {
                    "name": "excluded_suburbs",
                    "dataType": ["string[]"],
                    "description": "Excluded suburbs",
                    "indexFilterable": True
                },
                {
                    "name": "preferred_postcodes",
                    "dataType": ["string[]"],
                    "description": "Preferred postcodes",
                    "indexFilterable": True
                },
                {
                    "name": "min_bedrooms",
                    "dataType": ["int"],
                    "description": "Minimum bedrooms required",
                    "indexFilterable": True
                },
                {
                    "name": "max_bedrooms",
                    "dataType": ["int"],
                    "description": "Maximum bedrooms desired",
                    "indexFilterable": True
                },
                {
                    "name": "min_bathrooms",
                    "dataType": ["int"],
                    "description": "Minimum bathrooms required",
                    "indexFilterable": True
                },
                {
                    "name": "min_car_spaces",
                    "dataType": ["int"],
                    "description": "Minimum car spaces required",
                    "indexFilterable": True
                },
                {
                    "name": "min_land_size",
                    "dataType": ["int"],
                    "description": "Minimum land size in sqm",
                    "indexFilterable": True
                },
                {
                    "name": "min_building_size",
                    "dataType": ["int"],
                    "description": "Minimum building size in sqm",
                    "indexFilterable": True
                },
                {
                    "name": "required_features",
                    "dataType": ["string[]"],
                    "description": "Must-have features",
                    "indexFilterable": True
                },
                {
                    "name": "preferred_features",
                    "dataType": ["string[]"],
                    "description": "Nice-to-have features",
                    "indexSearchable": True
                },
                {
                    "name": "excluded_features",
                    "dataType": ["string[]"],
                    "description": "Features to avoid",
                    "indexFilterable": True
                },
                {
                    "name": "lifestyle_preferences",
                    "dataType": ["text"],
                    "description": "Lifestyle and amenity preferences"
                },
                {
                    "name": "school_preferences",
                    "dataType": ["text"],
                    "description": "School catchment preferences"
                },
                {
                    "name": "commute_destinations",
                    "dataType": ["text"],
                    "description": "Work and frequent destinations"
                },
                {
                    "name": "max_commute_time",
                    "dataType": ["int"],
                    "description": "Maximum commute time in minutes",
                    "indexFilterable": True
                },
                {
                    "name": "rental_yield_target",
                    "dataType": ["number"],
                    "description": "Target rental yield for investors",
                    "indexFilterable": True
                },
                {
                    "name": "capital_growth_expectation",
                    "dataType": ["string"],
                    "description": "Expected capital growth rate",
                    "indexFilterable": True
                },
                {
                    "name": "created_at",
                    "dataType": ["date"],
                    "description": "Profile creation date",
                    "indexFilterable": True
                },
                {
                    "name": "updated_at",
                    "dataType": ["date"],
                    "description": "Last profile update",
                    "indexFilterable": True
                },
                {
                    "name": "behavioral_data",
                    "dataType": ["text"],
                    "description": "Behavioral analysis and interaction patterns"
                },
                {
                    "name": "interaction_history",
                    "dataType": ["text"],
                    "description": "Property interaction patterns and feedback"
                },
                {
                    "name": "preference_weights",
                    "dataType": ["text"],
                    "description": "ML-derived preference weights and importance scores"
                },
                {
                    "name": "embedding_metadata",
                    "dataType": ["text"],
                    "description": "Embedding generation metadata and quality metrics"
                }
            ]
        }
        
        # Configure vectorizer based on availability
        if use_openai:
            schema.update({
                "vectorizer": "text2vec-openai",
                "moduleConfig": {
                    "text2vec-openai": {
                        "model": "ada",
                        "modelVersion": "002",
                        "type": "text", 
                        "dimensions": 1536,
                        "skipPropertiesForVectorization": [
                            "buyer_id", "max_price", "min_price", "budget_flexibility",
                            "min_bedrooms", "max_bedrooms", "min_bathrooms", "min_car_spaces",
                            "min_land_size", "min_building_size", "max_commute_time",
                            "rental_yield_target", "created_at", "updated_at", "embedding_metadata"
                        ]
                    }
                }
            })
        else:
            schema.update({
                "vectorizer": "text2vec-transformers",
                "moduleConfig": {
                    "text2vec-transformers": {
                        "poolingStrategy": "masked_mean",
                        "vectorizeClassName": False
                    }
                }
            })
        
        # Buyer profiles need less aggressive indexing than properties
        schema["vectorIndexConfig"] = {
            "skip": False,
            "cleanupIntervalSeconds": 300,
            "maxConnections": 32,  # Moderate for buyer profiles
            "efConstruction": 64,
            "ef": -1,
            "dynamicEfMin": 50,
            "dynamicEfMax": 200,
            "dynamicEfFactor": 4,
            "vectorCacheMaxObjects": 100000,  # Smaller cache for buyer profiles
            "flatSearchCutoff": 10000,
            "distance": "cosine"
        }
        
        schema["invertedIndexConfig"] = {
            "bm25": {
                "b": 0.75,
                "k1": 1.2
            },
            "cleanupIntervalSeconds": 60,
            "stopwords": {
                "preset": "en"
            }
        }
        
        return schema


class ProductionPropertyMatchSchema:
    """Production-optimized Property match results schema."""
    
    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """Get production-optimized property match schema for Weaviate."""
        return {
            "class": "PropertyMatch",
            "description": "Property-buyer matches with AI scoring and feedback for Sydney market",
            "properties": [
                {
                    "name": "match_id",
                    "dataType": ["string"],
                    "description": "Match UUID identifier",
                    "indexFilterable": True
                },
                {
                    "name": "buyer_id",
                    "dataType": ["string"],
                    "description": "Buyer UUID reference",
                    "indexFilterable": True
                },
                {
                    "name": "property_listing_id",
                    "dataType": ["string"],
                    "description": "Property listing ID reference",
                    "indexFilterable": True
                },
                {
                    "name": "match_score",
                    "dataType": ["number"],
                    "description": "AI confidence score (0-1)",
                    "indexFilterable": True
                },
                {
                    "name": "match_rank",
                    "dataType": ["int"],
                    "description": "Ranking among buyer matches",
                    "indexFilterable": True
                },
                {
                    "name": "match_reasons",
                    "dataType": ["string[]"],
                    "description": "Key match reasons and strengths",
                    "indexSearchable": True
                },
                {
                    "name": "match_concerns",
                    "dataType": ["string[]"],
                    "description": "Potential concerns and weaknesses",
                    "indexSearchable": True
                },
                {
                    "name": "match_explanation",
                    "dataType": ["text"],
                    "description": "Detailed AI explanation of the match",
                    "indexSearchable": True
                },
                {
                    "name": "status",
                    "dataType": ["string"],
                    "description": "Match status (active, viewed, interested, rejected)",
                    "indexFilterable": True
                },
                {
                    "name": "buyer_feedback",
                    "dataType": ["string"],
                    "description": "Buyer feedback (positive, negative, neutral)",
                    "indexFilterable": True
                },
                {
                    "name": "created_at",
                    "dataType": ["date"],
                    "description": "Match creation timestamp",
                    "indexFilterable": True
                },
                {
                    "name": "first_presented_date",
                    "dataType": ["date"],
                    "description": "First presentation to buyer",
                    "indexFilterable": True
                },
                {
                    "name": "last_interaction_date",
                    "dataType": ["date"],
                    "description": "Most recent buyer interaction",
                    "indexFilterable": True
                },
                {
                    "name": "interaction_count",
                    "dataType": ["int"],
                    "description": "Total number of interactions",
                    "indexFilterable": True
                },
                {
                    "name": "scoring_details",
                    "dataType": ["text"],
                    "description": "Detailed AI scoring breakdown and feature importance"
                },
                {
                    "name": "ml_features",
                    "dataType": ["text"],
                    "description": "ML features and weights used for matching"
                }
            ],
            "vectorIndexConfig": {
                "skip": True  # Match records don't need vector embeddings
            },
            "invertedIndexConfig": {
                "bm25": {
                    "b": 0.75,
                    "k1": 1.2
                },
                "cleanupIntervalSeconds": 60,
                "stopwords": {
                    "preset": "en"
                }
            }
        }


# Production schema registry
PRODUCTION_SCHEMA_REGISTRY = {
    "Property": ProductionPropertySchema.get_schema(),
    "BuyerProfile": ProductionBuyerProfileSchema.get_schema(),
    "PropertyMatch": ProductionPropertyMatchSchema.get_schema()
}


def get_production_schema(class_name: str) -> Dict[str, Any]:
    """Get production schema by class name."""
    if class_name not in PRODUCTION_SCHEMA_REGISTRY:
        raise ValueError(f"Schema {class_name} not found in production registry")
    return PRODUCTION_SCHEMA_REGISTRY[class_name]


def get_all_production_schemas() -> Dict[str, Dict[str, Any]]:
    """Get all production schemas."""
    return PRODUCTION_SCHEMA_REGISTRY.copy()