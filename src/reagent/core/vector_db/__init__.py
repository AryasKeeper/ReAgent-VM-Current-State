"""
Vector Database Infrastructure

Weaviate vector database integration for semantic search of properties.
Provides embedding generation and similarity search capabilities.
"""

from .client import WeaviateClient, get_weaviate_client, close_weaviate_client, SearchQuery, VectorSearchResult
from .schemas import PropertySchema, BuyerProfileSchema
from .embeddings import PropertyVectorizer, BuyerProfileVectorizer

__all__ = [
    "WeaviateClient",
    "get_weaviate_client",
    "close_weaviate_client",
    "SearchQuery",
    "VectorSearchResult",
    "PropertySchema",
    "BuyerProfileSchema", 
    "PropertyVectorizer",
    "BuyerProfileVectorizer"
]