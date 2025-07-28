"""
Weaviate Schema Definitions

Defines vector database schemas for properties and buyer profiles
with optimized indexing and vectorization configurations.
"""

from typing import Dict, Any, List
from dataclasses import dataclass


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


class PropertySchema:
    """Property vector schema for semantic search."""
    
    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """Get property schema for Weaviate."""
        return {
            "class": "Property",
            "description": "Real estate property listings with semantic embeddings",
            "properties": [
                {
                    "name": "listing_id",
                    "dataType": ["string"],
                    "description": "External listing identifier",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "title",
                    "dataType": ["text"],
                    "description": "Property title",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "description",
                    "dataType": ["text"],
                    "description": "Property description",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "property_type",
                    "dataType": ["string"],
                    "description": "Property type (House, Unit, etc.)",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "suburb",
                    "dataType": ["string"],
                    "description": "Suburb name",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "postcode",
                    "dataType": ["string"],
                    "description": "Postcode",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "state",
                    "dataType": ["string"],
                    "description": "State",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "bedrooms",
                    "dataType": ["int"],
                    "description": "Number of bedrooms",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "bathrooms",
                    "dataType": ["int"],
                    "description": "Number of bathrooms",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "car_spaces",
                    "dataType": ["int"],
                    "description": "Number of car spaces",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "price",
                    "dataType": ["number"],
                    "description": "Property price",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "price_display",
                    "dataType": ["string"],
                    "description": "Price display text",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "land_size",
                    "dataType": ["int"],
                    "description": "Land size in sqm",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "building_size",
                    "dataType": ["int"],
                    "description": "Building size in sqm",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "listing_status",
                    "dataType": ["string"],
                    "description": "Listing status",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "listing_type",
                    "dataType": ["string"],
                    "description": "Listing type (sale, rent, etc.)",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "features",
                    "dataType": ["string[]"],
                    "description": "Property features list",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "latitude",
                    "dataType": ["number"],
                    "description": "Latitude coordinate",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "longitude",
                    "dataType": ["number"],
                    "description": "Longitude coordinate",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "first_listed_date",
                    "dataType": ["date"],
                    "description": "First listing date",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "days_on_market",
                    "dataType": ["int"],
                    "description": "Days on market",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "agent_name",
                    "dataType": ["string"],
                    "description": "Primary agent name",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "agency_name",
                    "dataType": ["string"],
                    "description": "Agency name",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "source",
                    "dataType": ["string"],
                    "description": "Data source",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "amenities",
                    "dataType": ["object"],
                    "description": "Structured amenities data",
                    "indexInverted": False
                },
                {
                    "name": "market_context",
                    "dataType": ["object"],
                    "description": "Market trend and context data",
                    "indexInverted": False
                },
                {
                    "name": "embedding_metadata",
                    "dataType": ["object"],
                    "description": "Embedding generation metadata",
                    "indexInverted": False
                }
            ],
            "vectorIndexConfig": {
                "skip": False,
                "cleanupIntervalSeconds": 300,
                "maxConnections": 64,
                "efConstruction": 128,
                "ef": -1,
                "dynamicEfMin": 100,
                "dynamicEfMax": 500,
                "dynamicEfFactor": 8,
                "vectorCacheMaxObjects": 1000000,
                "flatSearchCutoff": 40000,
                "distance": "cosine"
            },
            "invertedIndexConfig": {
                "bm25": {
                    "b": 0.75,
                    "k1": 1.2
                },
                "cleanupIntervalSeconds": 60,
                "stopwords": {
                    "preset": "en",
                    "additions": ["property", "home", "house"]
                }
            }
        }


class BuyerProfileSchema:
    """Buyer profile vector schema for preference matching."""
    
    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """Get buyer profile schema for Weaviate."""
        return {
            "class": "BuyerProfile",
            "description": "Buyer profiles with preference embeddings for property matching",
            "properties": [
                {
                    "name": "buyer_id",
                    "dataType": ["string"],
                    "description": "Buyer UUID identifier",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "full_name",
                    "dataType": ["string"],
                    "description": "Buyer full name",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "buyer_type",
                    "dataType": ["string"],
                    "description": "Buyer type (individual, investor, etc.)",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "buying_urgency",
                    "dataType": ["string"],
                    "description": "Buying urgency level",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "max_price",
                    "dataType": ["number"],
                    "description": "Maximum budget",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "min_price",
                    "dataType": ["number"],
                    "description": "Minimum budget",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "budget_flexibility",
                    "dataType": ["number"],
                    "description": "Budget flexibility percentage",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "property_types",
                    "dataType": ["string[]"],
                    "description": "Preferred property types",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "preferred_suburbs",
                    "dataType": ["string[]"],
                    "description": "Preferred suburbs",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "excluded_suburbs",
                    "dataType": ["string[]"],
                    "description": "Excluded suburbs",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "preferred_postcodes",
                    "dataType": ["string[]"],
                    "description": "Preferred postcodes",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "min_bedrooms",
                    "dataType": ["int"],
                    "description": "Minimum bedrooms",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "max_bedrooms",
                    "dataType": ["int"],
                    "description": "Maximum bedrooms",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "min_bathrooms",
                    "dataType": ["int"],
                    "description": "Minimum bathrooms",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "min_car_spaces",
                    "dataType": ["int"],
                    "description": "Minimum car spaces",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "min_land_size",
                    "dataType": ["int"],
                    "description": "Minimum land size",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "min_building_size",
                    "dataType": ["int"],
                    "description": "Minimum building size",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "required_features",
                    "dataType": ["string[]"],
                    "description": "Must-have features",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "preferred_features",
                    "dataType": ["string[]"],
                    "description": "Nice-to-have features",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "excluded_features",
                    "dataType": ["string[]"],
                    "description": "Features to avoid",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "lifestyle_preferences",
                    "dataType": ["object"],
                    "description": "Lifestyle and amenity preferences",
                    "indexInverted": False
                },
                {
                    "name": "school_preferences",
                    "dataType": ["object"],
                    "description": "School catchment preferences",
                    "indexInverted": False
                },
                {
                    "name": "commute_destinations",
                    "dataType": ["object"],
                    "description": "Work/school locations",
                    "indexInverted": False
                },
                {
                    "name": "max_commute_time",
                    "dataType": ["int"],
                    "description": "Maximum commute time in minutes",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "rental_yield_target",
                    "dataType": ["number"],
                    "description": "Target rental yield (for investors)",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "capital_growth_expectation",
                    "dataType": ["string"],
                    "description": "Expected capital growth rate",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "created_at",
                    "dataType": ["date"],
                    "description": "Profile creation date",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "updated_at",
                    "dataType": ["date"],
                    "description": "Last profile update",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "behavioral_data",
                    "dataType": ["object"],
                    "description": "Behavioral analysis data",
                    "indexInverted": False
                },
                {
                    "name": "interaction_history",
                    "dataType": ["object"],
                    "description": "Property interaction patterns",
                    "indexInverted": False
                },
                {
                    "name": "preference_weights",
                    "dataType": ["object"],
                    "description": "ML-derived preference weights",
                    "indexInverted": False
                },
                {
                    "name": "embedding_metadata",
                    "dataType": ["object"],
                    "description": "Embedding generation metadata",
                    "indexInverted": False
                }
            ],
            "vectorIndexConfig": {
                "skip": False,
                "cleanupIntervalSeconds": 300,
                "maxConnections": 32,
                "efConstruction": 64,
                "ef": -1,
                "dynamicEfMin": 50,
                "dynamicEfMax": 200,
                "dynamicEfFactor": 4,
                "vectorCacheMaxObjects": 100000,
                "flatSearchCutoff": 10000,
                "distance": "cosine"
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


class PropertyMatchSchema:
    """Property match results schema for storing match history."""
    
    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """Get property match schema for Weaviate."""
        return {
            "class": "PropertyMatch",
            "description": "Property-buyer matches with scoring and feedback",
            "properties": [
                {
                    "name": "match_id",
                    "dataType": ["string"],
                    "description": "Match UUID identifier",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "buyer_id",
                    "dataType": ["string"],
                    "description": "Buyer UUID",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "property_listing_id",
                    "dataType": ["string"],
                    "description": "Property listing ID",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "match_score",
                    "dataType": ["number"],
                    "description": "AI confidence score (0-1)",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "match_rank",
                    "dataType": ["int"],
                    "description": "Ranking among buyer matches",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "match_reasons",
                    "dataType": ["string[]"],
                    "description": "Key match reasons",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "match_concerns",
                    "dataType": ["string[]"],
                    "description": "Potential concerns",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "match_explanation",
                    "dataType": ["text"],
                    "description": "Detailed explanation",
                    "indexInverted": True,
                    "indexSearchable": True
                },
                {
                    "name": "status",
                    "dataType": ["string"],
                    "description": "Match status",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "buyer_feedback",
                    "dataType": ["string"],
                    "description": "Buyer feedback",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "created_at",
                    "dataType": ["date"],
                    "description": "Match creation date",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "first_presented_date",
                    "dataType": ["date"],
                    "description": "First presentation to buyer",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "last_interaction_date",
                    "dataType": ["date"],
                    "description": "Last buyer interaction",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "interaction_count",
                    "dataType": ["int"],
                    "description": "Number of interactions",
                    "indexInverted": True,
                    "indexFilterable": True
                },
                {
                    "name": "scoring_details",
                    "dataType": ["object"],
                    "description": "Detailed scoring breakdown",
                    "indexInverted": False
                },
                {
                    "name": "ml_features",
                    "dataType": ["object"],
                    "description": "ML features used for matching",
                    "indexInverted": False
                }
            ],
            "vectorIndexConfig": {
                "skip": True  # No vector embeddings for match records
            },
            "invertedIndexConfig": {
                "bm25": {
                    "b": 0.75,
                    "k1": 1.2
                },
                "cleanupIntervalSeconds": 60
            }
        }


# Schema registry for easy access
SCHEMA_REGISTRY = {
    "Property": PropertySchema.get_schema(),
    "BuyerProfile": BuyerProfileSchema.get_schema(),
    "PropertyMatch": PropertyMatchSchema.get_schema()
}


def get_schema(class_name: str) -> Dict[str, Any]:
    """Get schema by class name."""
    if class_name not in SCHEMA_REGISTRY:
        raise ValueError(f"Schema {class_name} not found in registry")
    return SCHEMA_REGISTRY[class_name]


def get_all_schemas() -> Dict[str, Dict[str, Any]]:
    """Get all registered schemas."""
    return SCHEMA_REGISTRY.copy()