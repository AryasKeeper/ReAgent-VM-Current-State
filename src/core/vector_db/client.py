"""
Weaviate Vector Database Client

High-performance client wrapper for Weaviate vector database operations.
Provides property and buyer profile vector storage and similarity search.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

import weaviate
from weaviate.client import Client
from weaviate.auth import AuthApiKey
from weaviate.exceptions import WeaviateException

from reagent_sydney.config.settings import get_settings
import structlog


@dataclass
class VectorSearchResult:
    """Vector search result with metadata."""
    
    object_id: str
    score: float
    data: Dict[str, Any]
    class_name: str
    vector: Optional[List[float]] = None


@dataclass 
class SearchQuery:
    """Vector search query configuration."""
    
    vector: List[float]
    class_name: str
    limit: int = 10
    where_filter: Optional[Dict[str, Any]] = None
    certainty: Optional[float] = None
    distance: Optional[float] = None
    additional_properties: List[str] = None


class WeaviateClient:
    """
    Production-ready Weaviate client for vector operations.
    
    Provides high-level interface for property and buyer profile
    vector storage, retrieval, and similarity search operations.
    """
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self.logger = structlog.get_logger("weaviate.client")
        self._client: Optional[Client] = None
        self._is_connected = False
        
    async def connect(self) -> None:
        """Establish connection to Weaviate instance."""
        try:
            auth_config = None
            if self.settings.weaviate.api_key:
                auth_config = AuthApiKey(api_key=self.settings.weaviate.api_key)
            
            self._client = weaviate.Client(
                url=self.settings.weaviate.url,
                auth_client_secret=auth_config,
                timeout_config=weaviate.Config(
                    query_timeout=self.settings.weaviate.timeout,
                    insert_timeout=self.settings.weaviate.timeout,
                )
            )
            
            # Test connection
            if self._client.is_ready():
                self._is_connected = True
                self.logger.info("Connected to Weaviate successfully",
                               url=self.settings.weaviate.url)
            else:
                raise ConnectionError("Weaviate is not ready")
                
        except Exception as e:
            self.logger.error("Failed to connect to Weaviate", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close Weaviate connection."""
        if self._client:
            # Weaviate client doesn't have explicit disconnect
            self._client = None
            self._is_connected = False
            self.logger.info("Disconnected from Weaviate")
    
    def _ensure_connected(self) -> None:
        """Ensure client is connected."""
        if not self._is_connected or not self._client:
            raise ConnectionError("Weaviate client not connected. Call connect() first.")
    
    async def create_schema(self, schema: Dict[str, Any]) -> bool:
        """Create or update Weaviate schema."""
        self._ensure_connected()
        
        try:
            class_name = schema["class"]
            
            # Check if class already exists
            existing_schema = self._client.schema.get()
            existing_classes = [cls["class"] for cls in existing_schema.get("classes", [])]
            
            if class_name in existing_classes:
                self.logger.info("Schema class already exists", class_name=class_name)
                return True
            
            # Create new class
            self._client.schema.create_class(schema)
            self.logger.info("Created Weaviate schema class", class_name=class_name)
            return True
            
        except WeaviateException as e:
            self.logger.error("Failed to create schema", error=str(e), schema=schema)
            return False
    
    async def delete_schema(self, class_name: str) -> bool:
        """Delete Weaviate schema class."""
        self._ensure_connected()
        
        try:
            self._client.schema.delete_class(class_name)
            self.logger.info("Deleted schema class", class_name=class_name)
            return True
            
        except WeaviateException as e:
            self.logger.error("Failed to delete schema", error=str(e), class_name=class_name)
            return False
    
    async def insert_object(
        self, 
        class_name: str, 
        properties: Dict[str, Any],
        vector: Optional[List[float]] = None,
        object_id: Optional[str] = None
    ) -> Optional[str]:
        """Insert single object into Weaviate."""
        self._ensure_connected()
        
        try:
            result = self._client.data_object.create(
                data_object=properties,
                class_name=class_name,
                uuid=object_id,
                vector=vector
            )
            
            object_uuid = result if isinstance(result, str) else result.get("id")
            self.logger.debug("Inserted object", 
                            class_name=class_name, 
                            object_id=object_uuid)
            return object_uuid
            
        except WeaviateException as e:
            self.logger.error("Failed to insert object", 
                            error=str(e), 
                            class_name=class_name)
            return None
    
    async def batch_insert_objects(
        self, 
        class_name: str, 
        objects: List[Dict[str, Any]],
        vectors: Optional[List[List[float]]] = None,
        batch_size: int = 100
    ) -> List[str]:
        """Batch insert objects into Weaviate."""
        self._ensure_connected()
        
        inserted_ids = []
        
        try:
            with self._client.batch(
                batch_size=batch_size,
                dynamic=True,
                timeout_retries=3,
                callback=None
            ) as batch:
                
                for i, obj in enumerate(objects):
                    vector = vectors[i] if vectors else None
                    object_id = obj.get("id") or obj.get("object_id")
                    
                    batch.add_data_object(
                        data_object=obj,
                        class_name=class_name,
                        uuid=object_id,
                        vector=vector
                    )
                    
                    if object_id:
                        inserted_ids.append(object_id)
            
            self.logger.info("Batch inserted objects", 
                           class_name=class_name, 
                           count=len(objects))
            return inserted_ids
            
        except WeaviateException as e:
            self.logger.error("Failed to batch insert objects", 
                            error=str(e), 
                            class_name=class_name)
            return []
    
    async def update_object(
        self, 
        class_name: str, 
        object_id: str,
        properties: Dict[str, Any],
        vector: Optional[List[float]] = None
    ) -> bool:
        """Update existing object in Weaviate."""
        self._ensure_connected()
        
        try:
            self._client.data_object.update(
                data_object=properties,
                class_name=class_name,
                uuid=object_id,
                vector=vector
            )
            
            self.logger.debug("Updated object", 
                            class_name=class_name, 
                            object_id=object_id)
            return True
            
        except WeaviateException as e:
            self.logger.error("Failed to update object", 
                            error=str(e), 
                            class_name=class_name,
                            object_id=object_id)
            return False
    
    async def delete_object(self, class_name: str, object_id: str) -> bool:
        """Delete object from Weaviate."""
        self._ensure_connected()
        
        try:
            self._client.data_object.delete(uuid=object_id, class_name=class_name)
            self.logger.debug("Deleted object", 
                            class_name=class_name, 
                            object_id=object_id)
            return True
            
        except WeaviateException as e:
            self.logger.error("Failed to delete object", 
                            error=str(e), 
                            class_name=class_name,
                            object_id=object_id)
            return False
    
    async def get_object(
        self, 
        class_name: str, 
        object_id: str,
        additional_properties: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve single object by ID."""
        self._ensure_connected()
        
        try:
            result = self._client.data_object.get(
                uuid=object_id,
                class_name=class_name,
                additional_properties=additional_properties or []
            )
            
            self.logger.debug("Retrieved object", 
                            class_name=class_name, 
                            object_id=object_id)
            return result
            
        except WeaviateException as e:
            self.logger.error("Failed to get object", 
                            error=str(e), 
                            class_name=class_name,
                            object_id=object_id)
            return None
    
    async def vector_search(self, query: SearchQuery) -> List[VectorSearchResult]:
        """Perform vector similarity search."""
        self._ensure_connected()
        
        try:
            # Build GraphQL query
            query_builder = (
                self._client.query
                .get(query.class_name, query.additional_properties or ["*"])
                .with_near_vector({"vector": query.vector})
                .with_limit(query.limit)
            )
            
            # Add where filter if provided
            if query.where_filter:
                query_builder = query_builder.with_where(query.where_filter)
            
            # Add certainty or distance threshold
            if query.certainty is not None:
                query_builder = query_builder.with_additional(["certainty"])
            elif query.distance is not None:
                query_builder = query_builder.with_additional(["distance"])
            
            # Execute query
            result = query_builder.do()
            
            # Process results
            results = []
            get_results = result.get("data", {}).get("Get", {}).get(query.class_name, [])
            
            for item in get_results:
                additional = item.get("_additional", {})
                score = additional.get("certainty", additional.get("distance", 0.0))
                
                # Remove metadata from data
                data = {k: v for k, v in item.items() if not k.startswith("_")}
                
                results.append(VectorSearchResult(
                    object_id=additional.get("id", ""),
                    score=score,
                    data=data,
                    class_name=query.class_name,
                    vector=additional.get("vector")
                ))
            
            self.logger.debug("Vector search completed", 
                            class_name=query.class_name,
                            results_count=len(results))
            return results
            
        except WeaviateException as e:
            self.logger.error("Vector search failed", 
                            error=str(e), 
                            class_name=query.class_name)
            return []
    
    async def hybrid_search(
        self,
        class_name: str,
        query_text: str,
        query_vector: Optional[List[float]] = None,
        alpha: float = 0.5,
        limit: int = 10,
        where_filter: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """Perform hybrid text + vector search."""
        self._ensure_connected()
        
        try:
            query_builder = (
                self._client.query
                .get(class_name, ["*"])
                .with_hybrid(
                    query=query_text,
                    vector=query_vector,
                    alpha=alpha
                )
                .with_limit(limit)
                .with_additional(["score"])
            )
            
            if where_filter:
                query_builder = query_builder.with_where(where_filter)
            
            result = query_builder.do()
            
            # Process results
            results = []
            get_results = result.get("data", {}).get("Get", {}).get(class_name, [])
            
            for item in get_results:
                additional = item.get("_additional", {})
                score = additional.get("score", 0.0)
                
                data = {k: v for k, v in item.items() if not k.startswith("_")}
                
                results.append(VectorSearchResult(
                    object_id=additional.get("id", ""),
                    score=score,
                    data=data,
                    class_name=class_name
                ))
            
            self.logger.debug("Hybrid search completed", 
                            class_name=class_name,
                            results_count=len(results))
            return results
            
        except WeaviateException as e:
            self.logger.error("Hybrid search failed", 
                            error=str(e), 
                            class_name=class_name)
            return []
    
    async def get_object_count(self, class_name: str) -> int:
        """Get total count of objects in class."""
        self._ensure_connected()
        
        try:
            result = (
                self._client.query
                .aggregate(class_name)
                .with_meta_count()
                .do()
            )
            
            count = result["data"]["Aggregate"][class_name][0]["meta"]["count"]
            return count
            
        except WeaviateException as e:
            self.logger.error("Failed to get object count", 
                            error=str(e), 
                            class_name=class_name)
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Weaviate instance health."""
        try:
            if not self._client:
                return {"status": "disconnected", "ready": False}
            
            is_ready = self._client.is_ready()
            is_live = self._client.is_live()
            
            meta = {}
            if is_ready:
                try:
                    meta = self._client.get_meta()
                except:
                    pass
            
            return {
                "status": "connected" if is_ready else "error", 
                "ready": is_ready,
                "live": is_live,
                "url": self.settings.weaviate.url,
                "meta": meta
            }
            
        except Exception as e:
            return {
                "status": "error",
                "ready": False,
                "error": str(e)
            }


# Global client instance
_weaviate_client: Optional[WeaviateClient] = None


async def get_weaviate_client() -> WeaviateClient:
    """Get or create global Weaviate client instance."""
    global _weaviate_client
    
    if _weaviate_client is None:
        _weaviate_client = WeaviateClient()
        await _weaviate_client.connect()
    
    return _weaviate_client


async def close_weaviate_client() -> None:
    """Close global Weaviate client."""
    global _weaviate_client
    
    if _weaviate_client:
        await _weaviate_client.disconnect()
        _weaviate_client = None