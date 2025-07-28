"""
Vector Database Infrastructure

Weaviate vector database integration for semantic search of properties.
Provides embedding generation and similarity search capabilities.
"""

from .client import WeaviateClient
from .schemas import PropertySchema, BuyerProfileSchema
from .embeddings import PropertyVectorizer, BuyerProfileVectorizer

__all__ = [
    "WeaviateClient",
    "PropertySchema",
    "BuyerProfileSchema", 
    "PropertyVectorizer",
    "BuyerProfileVectorizer"
]