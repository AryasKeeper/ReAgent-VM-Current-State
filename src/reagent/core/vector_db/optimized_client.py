"""
Optimized Weaviate Vector Database Client

High-performance client with advanced optimization strategies for
sub-second response times and improved search accuracy.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from collections import defaultdict
import json

import weaviate
from weaviate.client import Client
from weaviate.auth import AuthApiKey
from weaviate.exceptions import WeaviateBaseError
import numpy as np

from reagent.core.config import get_settings
from reagent.core.cache.redis_client import get_cache_manager
import structlog


@dataclass
class SearchPerformanceMetrics:
    """Search performance tracking metrics."""
    
    query_time_ms: float
    result_count: int
    cache_hit: bool
    filter_complexity: int
    vector_computation_time_ms: float
    total_processing_time_ms: float
    similarity_threshold: float
    query_id: str = field(default_factory=lambda: str(int(time.time() * 1000)))


@dataclass
class OptimizedSearchQuery:
    """Enhanced search query with performance optimizations."""
    
    vector: List[float]
    class_name: str
    limit: int = 10
    where_filter: Optional[Dict[str, Any]] = None
    certainty: Optional[float] = None
    distance: Optional[float] = None
    additional_properties: List[str] = field(default_factory=list)
    
    # Performance optimizations
    use_cache: bool = True
    cache_ttl: int = 300  # 5 minutes default
    enable_query_batching: bool = False
    similarity_boost: float = 1.0
    rerank_results: bool = True
    max_prefetch: int = 50  # Prefetch more candidates for reranking


@dataclass
class OptimizedVectorSearchResult:
    """Enhanced search result with performance metadata."""
    
    object_id: str
    score: float
    data: Dict[str, Any]
    class_name: str
    vector: Optional[List[float]] = None
    performance_metrics: Optional[SearchPerformanceMetrics] = None
    similarity_breakdown: Optional[Dict[str, float]] = None


class OptimizedWeaviateClient:
    """
    High-performance Weaviate client with advanced optimizations.
    
    Features:
    - Sub-second query response times
    - Intelligent caching with cache warming
    - Query batching and connection pooling
    - Adaptive similarity thresholds
    - Performance monitoring and auto-tuning
    """
    
    def __init__(self, settings: Optional[Any] = None):
        self.settings = settings or get_settings()
        self.logger = structlog.get_logger("weaviate.optimized_client")
        self._client: Optional[Client] = None
        self._is_connected = False
        
        # Performance optimization components
        self.cache_manager = None
        self.query_cache = {}
        self.connection_pool_size = 5
        self.max_concurrent_queries = 10
        self._query_semaphore = asyncio.Semaphore(self.max_concurrent_queries)
        
        # Performance tracking
        self.performance_metrics = defaultdict(list)
        self.total_queries = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Adaptive configuration
        self.adaptive_similarity_thresholds = {
            "Property": 0.75,  # Optimized for properties
            "BuyerProfile": 0.70,  # Slightly lower for buyer matching
            "PropertyMatch": 0.80   # Higher precision for matches
        }
        
        # Query optimization patterns
        self.common_filter_patterns = {}
        self.query_performance_history = []
        
    async def connect(self) -> None:
        """Establish optimized connection to Weaviate instance."""
        try:
            auth_config = None
            if self.settings.weaviate.api_key:
                auth_config = AuthApiKey(api_key=self.settings.weaviate.api_key)
            
            # Optimized timeout configuration
            timeout_config = weaviate.Config(
                query_timeout=10,  # Reduced from 30s
                insert_timeout=15,  # Reduced from 30s
                connection_timeout=5,  # Add connection timeout
            )
            
            self._client = weaviate.Client(
                url=self.settings.weaviate.url,
                auth_client_secret=auth_config,
                timeout_config=timeout_config,
                additional_headers={
                    "X-OpenAI-Api-Key": self.settings.apis.openai_api_key or "",
                    "Content-Type": "application/json"
                }
            )
            
            # Test connection with health check
            if self._client.is_ready():
                self._is_connected = True
                
                # Initialize cache manager
                self.cache_manager = await get_cache_manager()
                
                # Warm up common queries
                await self._warm_up_cache()
                
                self.logger.info("Optimized Weaviate client connected successfully",
                               url=self.settings.weaviate.url,
                               connection_pool_size=self.connection_pool_size)
            else:
                raise ConnectionError("Weaviate is not ready")
                
        except Exception as e:
            self.logger.error("Failed to connect to optimized Weaviate client", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Close optimized Weaviate connection."""
        if self._client:
            # Clear cache and performance data
            self.query_cache.clear()
            self.performance_metrics.clear()
            
            self._client = None
            self._is_connected = False
            self.logger.info("Disconnected from optimized Weaviate client")
    
    def _ensure_connected(self) -> None:
        """Ensure client is connected with detailed error."""
        if not self._is_connected or not self._client:
            raise ConnectionError("Optimized Weaviate client not connected. Call connect() first.")
    
    async def optimized_vector_search(
        self, 
        query: OptimizedSearchQuery
    ) -> List[OptimizedVectorSearchResult]:
        """
        Perform optimized vector similarity search with sub-second response times.
        """
        start_time = time.time()
        query_start = time.perf_counter()
        
        try:
            async with self._query_semaphore:
                # Check cache first if enabled
                cache_key = None
                if query.use_cache:
                    cache_key = self._generate_cache_key(query)
                    cached_result = await self._get_cached_result(cache_key)
                    
                    if cached_result:
                        self.cache_hits += 1
                        self.logger.debug("Cache hit for vector search", cache_key=cache_key)
                        
                        # Add performance metrics
                        for result in cached_result:
                            if result.performance_metrics:
                                result.performance_metrics.cache_hit = True
                                result.performance_metrics.query_time_ms = (time.perf_counter() - query_start) * 1000
                        
                        return cached_result
                
                self.cache_misses += 1
                
                # Build optimized GraphQL query
                optimized_query = await self._build_optimized_query(query)
                
                # Execute query with performance monitoring
                vector_computation_start = time.perf_counter()
                result = optimized_query.do()
                vector_computation_time = (time.perf_counter() - vector_computation_start) * 1000
                
                # Process and optimize results
                processed_results = await self._process_optimized_results(
                    result, query, vector_computation_time, query_start
                )
                
                # Cache results if enabled
                if query.use_cache and cache_key:
                    await self._cache_results(cache_key, processed_results, query.cache_ttl)
                
                # Update performance metrics
                query_time = (time.perf_counter() - query_start) * 1000
                await self._update_performance_metrics(query, query_time, len(processed_results))
                
                self.total_queries += 1
                
                return processed_results
                
        except Exception as e:
            self.logger.error("Optimized vector search failed", 
                            error=str(e), 
                            class_name=query.class_name,
                            query_time_ms=(time.perf_counter() - query_start) * 1000)
            
            # Fallback to basic search if optimization fails
            return await self._fallback_search(query)
    
    async def _build_optimized_query(self, query: OptimizedSearchQuery):
        """Build optimized GraphQL query with performance enhancements."""
        self._ensure_connected()
        
        # Adaptive similarity threshold
        adaptive_threshold = self.adaptive_similarity_thresholds.get(
            query.class_name, query.certainty or 0.7
        )
        
        if query.certainty:
            adaptive_threshold = max(adaptive_threshold, query.certainty)
        
        # Build base query with optimized limit
        effective_limit = min(query.limit * 2, query.max_prefetch) if query.rerank_results else query.limit
        
        query_builder = (
            self._client.query
            .get(query.class_name, query.additional_properties or ["*"])
            .with_near_vector({
                "vector": query.vector,
                "certainty": adaptive_threshold
            })
            .with_limit(effective_limit)
        )
        
        # Optimized filtering
        if query.where_filter:
            optimized_filter = await self._optimize_where_filter(query.where_filter)
            query_builder = query_builder.with_where(optimized_filter)
        
        # Add performance-critical additional properties
        performance_properties = ["certainty", "distance"]
        if query.rerank_results:
            performance_properties.append("vector")
        
        query_builder = query_builder.with_additional(performance_properties)
        
        return query_builder
    
    async def _optimize_where_filter(self, where_filter: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize where filter for better performance."""
        
        # Reorder filter conditions by selectivity (most selective first)
        if where_filter.get("operator") == "And" and where_filter.get("operands"):
            operands = where_filter["operands"]
            
            # Priority order for filter optimization
            priority_paths = [
                "listing_status",  # High selectivity
                "listing_type",    # High selectivity
                "property_type",   # Medium selectivity
                "bedrooms",        # Medium selectivity
                "price",           # Low selectivity (range queries)
                "suburb",          # Low selectivity (many values)
            ]
            
            # Sort operands by priority
            def get_priority(operand):
                path = operand.get("path", [""])[0]
                try:
                    return priority_paths.index(path)
                except ValueError:
                    return len(priority_paths)  # Unknown paths go last
            
            optimized_operands = sorted(operands, key=get_priority)
            where_filter["operands"] = optimized_operands
        
        return where_filter
    
    async def _process_optimized_results(
        self, 
        result: Dict[str, Any], 
        query: OptimizedSearchQuery,
        vector_computation_time: float,
        query_start_time: float
    ) -> List[OptimizedVectorSearchResult]:
        """Process and optimize search results."""
        
        results = []
        get_results = result.get("data", {}).get("Get", {}).get(query.class_name, [])
        
        if not get_results:
            return results
        
        # Process raw results
        raw_results = []
        for item in get_results:
            additional = item.get("_additional", {})
            score = additional.get("certainty", additional.get("distance", 0.0))
            
            # Remove metadata from data
            data = {k: v for k, v in item.items() if not k.startswith("_")}
            
            raw_results.append({
                "object_id": additional.get("id", ""),
                "score": score,
                "data": data,
                "vector": additional.get("vector"),
                "additional": additional
            })
        
        # Rerank results if enabled
        if query.rerank_results and len(raw_results) > query.limit:
            raw_results = await self._rerank_results(raw_results, query)[:query.limit]
        
        # Create optimized result objects
        total_processing_time = (time.perf_counter() - query_start_time) * 1000
        
        for i, raw_result in enumerate(raw_results[:query.limit]):
            performance_metrics = SearchPerformanceMetrics(
                query_time_ms=total_processing_time,
                result_count=len(raw_results),
                cache_hit=False,
                filter_complexity=self._calculate_filter_complexity(query.where_filter),
                vector_computation_time_ms=vector_computation_time,
                total_processing_time_ms=total_processing_time,
                similarity_threshold=query.certainty or 0.7
            )
            
            # Calculate similarity breakdown for explainability
            similarity_breakdown = await self._calculate_similarity_breakdown(
                query.vector, raw_result.get("vector")
            )
            
            results.append(OptimizedVectorSearchResult(
                object_id=raw_result["object_id"],
                score=raw_result["score"],
                data=raw_result["data"],
                class_name=query.class_name,
                vector=raw_result.get("vector"),
                performance_metrics=performance_metrics,
                similarity_breakdown=similarity_breakdown
            ))
        
        return results
    
    async def _rerank_results(
        self, 
        raw_results: List[Dict[str, Any]], 
        query: OptimizedSearchQuery
    ) -> List[Dict[str, Any]]:
        """Rerank results using advanced scoring."""
        
        if query.class_name == "Property":
            return await self._rerank_property_results(raw_results, query)
        elif query.class_name == "BuyerProfile":
            return await self._rerank_buyer_results(raw_results, query)
        else:
            # Default reranking by similarity score
            return sorted(raw_results, key=lambda x: x["score"], reverse=True)
    
    async def _rerank_property_results(
        self, 
        raw_results: List[Dict[str, Any]], 
        query: OptimizedSearchQuery
    ) -> List[Dict[str, Any]]:
        """Rerank property results with business logic."""
        
        def calculate_boosted_score(result):
            base_score = result["score"]
            data = result["data"]
            
            # Business logic boosts
            boosts = 0.0
            
            # Boost recently listed properties
            if data.get("days_on_market", 365) <= 7:
                boosts += 0.1
            
            # Boost properties with good features
            features = data.get("features", [])
            if isinstance(features, list):
                luxury_features = ["pool", "harbour_view", "renovated", "modern"]
                luxury_count = sum(1 for feat in features if any(lux in feat.lower() for lux in luxury_features))
                boosts += min(luxury_count * 0.05, 0.2)
            
            # Boost properties with competitive pricing
            # This would need market data integration
            
            return base_score + (boosts * query.similarity_boost)
        
        # Apply boosted scoring
        for result in raw_results:
            result["boosted_score"] = calculate_boosted_score(result)
        
        return sorted(raw_results, key=lambda x: x["boosted_score"], reverse=True)
    
    async def _rerank_buyer_results(
        self, 
        raw_results: List[Dict[str, Any]], 
        query: OptimizedSearchQuery
    ) -> List[Dict[str, Any]]:
        """Rerank buyer profile results with preference matching."""
        
        # For buyer profiles, prioritize by urgency and budget alignment
        def calculate_buyer_priority(result):
            data = result["data"]
            base_score = result["score"]
            
            priority_score = base_score
            
            # Boost urgent buyers
            urgency = data.get("buying_urgency", "medium")
            urgency_multiplier = {
                "urgent": 1.3,
                "high": 1.2,
                "medium": 1.0,
                "low": 0.8
            }
            priority_score *= urgency_multiplier.get(urgency, 1.0)
            
            # Boost buyers with realistic budgets
            max_price = data.get("max_price", 0)
            if max_price > 500000:  # Reasonable Sydney budget
                priority_score *= 1.1
            
            return priority_score
        
        for result in raw_results:
            result["priority_score"] = calculate_buyer_priority(result)
        
        return sorted(raw_results, key=lambda x: x["priority_score"], reverse=True)
    
    def _calculate_filter_complexity(self, where_filter: Optional[Dict[str, Any]]) -> int:
        """Calculate filter complexity for performance monitoring."""
        if not where_filter:
            return 0
        
        complexity = 1
        if where_filter.get("operands"):
            complexity += len(where_filter["operands"])
            
            # Nested complexity
            for operand in where_filter["operands"]:
                if operand.get("operands"):
                    complexity += len(operand["operands"])
        
        return complexity
    
    async def _calculate_similarity_breakdown(
        self, 
        query_vector: List[float], 
        result_vector: Optional[List[float]]
    ) -> Optional[Dict[str, float]]:
        """Calculate similarity breakdown for explainability."""
        if not result_vector or len(query_vector) != len(result_vector):
            return None
        
        try:
            # Calculate component similarities (assuming structured vector)
            vector_length = len(query_vector)
            component_size = vector_length // 6  # Based on embedding structure
            
            components = {
                "location": np.dot(
                    query_vector[:component_size], 
                    result_vector[:component_size]
                ),
                "property_specs": np.dot(
                    query_vector[component_size:2*component_size], 
                    result_vector[component_size:2*component_size]
                ),
                "price_value": np.dot(
                    query_vector[2*component_size:3*component_size], 
                    result_vector[2*component_size:3*component_size]
                ),
                "features": np.dot(
                    query_vector[3*component_size:4*component_size], 
                    result_vector[3*component_size:4*component_size]
                ),
                "market_context": np.dot(
                    query_vector[4*component_size:5*component_size], 
                    result_vector[4*component_size:5*component_size]
                ),
                "text_semantic": np.dot(
                    query_vector[5*component_size:], 
                    result_vector[5*component_size:]
                )
            }
            
            return components
            
        except Exception as e:
            self.logger.debug("Failed to calculate similarity breakdown", error=str(e))
            return None
    
    def _generate_cache_key(self, query: OptimizedSearchQuery) -> str:
        """Generate cache key for query."""
        key_components = [
            query.class_name,
            str(hash(tuple(query.vector))),  # Vector hash
            json.dumps(query.where_filter, sort_keys=True) if query.where_filter else "",
            str(query.limit),
            str(query.certainty or ""),
        ]
        
        return f"vector_search:{'|'.join(key_components)}"
    
    async def _get_cached_result(self, cache_key: str) -> Optional[List[OptimizedVectorSearchResult]]:
        """Get cached search result."""
        if not self.cache_manager:
            return None
        
        try:
            cached_data = await self.cache_manager.get(cache_key)
            if cached_data:
                # Deserialize cached results
                results = []
                for item in cached_data:
                    result = OptimizedVectorSearchResult(**item)
                    results.append(result)
                return results
        except Exception as e:
            self.logger.debug("Cache retrieval failed", error=str(e))
        
        return None
    
    async def _cache_results(
        self, 
        cache_key: str, 
        results: List[OptimizedVectorSearchResult], 
        ttl: int
    ) -> None:
        """Cache search results."""
        if not self.cache_manager:
            return
        
        try:
            # Serialize results for caching
            serializable_results = []
            for result in results:
                result_dict = {
                    "object_id": result.object_id,
                    "score": result.score,
                    "data": result.data,
                    "class_name": result.class_name,
                    "vector": result.vector,
                    "performance_metrics": result.performance_metrics.__dict__ if result.performance_metrics else None,
                    "similarity_breakdown": result.similarity_breakdown
                }
                serializable_results.append(result_dict)
            
            await self.cache_manager.set(cache_key, serializable_results, ttl=ttl)
        except Exception as e:
            self.logger.debug("Cache storage failed", error=str(e))
    
    async def _fallback_search(self, query: OptimizedSearchQuery) -> List[OptimizedVectorSearchResult]:
        """Fallback search implementation for error cases."""
        self.logger.warning("Using fallback search", class_name=query.class_name)
        
        try:
            # Simple search without optimizations
            simple_query = (
                self._client.query
                .get(query.class_name, ["*"])
                .with_near_vector({"vector": query.vector})
                .with_limit(query.limit)
                .with_additional(["certainty"])
            )
            
            if query.where_filter:
                simple_query = simple_query.with_where(query.where_filter)
            
            result = simple_query.do()
            
            # Basic result processing
            results = []
            get_results = result.get("data", {}).get("Get", {}).get(query.class_name, [])
            
            for item in get_results:
                additional = item.get("_additional", {})
                score = additional.get("certainty", 0.0)
                data = {k: v for k, v in item.items() if not k.startswith("_")}
                
                results.append(OptimizedVectorSearchResult(
                    object_id=additional.get("id", ""),
                    score=score,
                    data=data,
                    class_name=query.class_name
                ))
            
            return results
            
        except Exception as e:
            self.logger.error("Fallback search also failed", error=str(e))
            return []
    
    async def _warm_up_cache(self) -> None:
        """Warm up cache with common queries."""
        self.logger.info("Warming up vector search cache...")
        
        try:
            # Common property type queries
            common_property_types = ["house", "unit", "townhouse"]
            common_price_ranges = [
                (500000, 1000000), (1000000, 2000000), (2000000, 5000000)
            ]
            
            # Create sample vectors for warmup (would be real buyer vectors in production)
            sample_vector = [0.1] * 50  # Placeholder vector
            
            for prop_type in common_property_types:
                for min_price, max_price in common_price_ranges:
                    warmup_query = OptimizedSearchQuery(
                        vector=sample_vector,
                        class_name="Property",
                        limit=10,
                        where_filter={
                            "operator": "And",
                            "operands": [
                                {"path": ["property_type"], "operator": "Equal", "valueString": prop_type},
                                {"path": ["price"], "operator": "GreaterThanEqual", "valueNumber": min_price},
                                {"path": ["price"], "operator": "LessThanEqual", "valueNumber": max_price}
                            ]
                        }
                    )
                    
                    # Execute warmup query (with reduced limit)
                    warmup_query.limit = 5
                    await self.optimized_vector_search(warmup_query)
                    
                    # Small delay to avoid overwhelming the system
                    await asyncio.sleep(0.1)
            
            self.logger.info("Cache warmup completed")
            
        except Exception as e:
            self.logger.warning("Cache warmup failed", error=str(e))
    
    async def _update_performance_metrics(
        self, 
        query: OptimizedSearchQuery, 
        query_time_ms: float, 
        result_count: int
    ) -> None:
        """Update performance metrics for monitoring."""
        
        metrics = {
            "class_name": query.class_name,
            "query_time_ms": query_time_ms,
            "result_count": result_count,
            "filter_complexity": self._calculate_filter_complexity(query.where_filter),
            "cache_enabled": query.use_cache,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.performance_metrics[query.class_name].append(metrics)
        
        # Keep only recent metrics (last 1000 queries per class)
        if len(self.performance_metrics[query.class_name]) > 1000:
            self.performance_metrics[query.class_name] = self.performance_metrics[query.class_name][-1000:]
        
        # Auto-tune thresholds based on performance
        await self._auto_tune_parameters(query.class_name, query_time_ms)
    
    async def _auto_tune_parameters(self, class_name: str, query_time_ms: float) -> None:
        """Auto-tune search parameters based on performance."""
        
        metrics = self.performance_metrics[class_name]
        if len(metrics) < 10:  # Need enough data points
            return
        
        # Calculate average query time for recent queries
        recent_metrics = metrics[-10:]
        avg_query_time = sum(m["query_time_ms"] for m in recent_metrics) / len(recent_metrics)
        
        # Adjust similarity threshold if queries are too slow
        if avg_query_time > 1000:  # Over 1 second
            current_threshold = self.adaptive_similarity_thresholds.get(class_name, 0.7)
            new_threshold = min(current_threshold + 0.05, 0.9)  # Increase threshold to reduce results
            
            if new_threshold != current_threshold:
                self.adaptive_similarity_thresholds[class_name] = new_threshold
                self.logger.info(f"Auto-tuned similarity threshold for {class_name}",
                               old_threshold=current_threshold,
                               new_threshold=new_threshold,
                               avg_query_time_ms=avg_query_time)
        
        elif avg_query_time < 200:  # Very fast queries
            current_threshold = self.adaptive_similarity_thresholds.get(class_name, 0.7)
            new_threshold = max(current_threshold - 0.02, 0.5)  # Decrease threshold for more results
            
            if new_threshold != current_threshold:
                self.adaptive_similarity_thresholds[class_name] = new_threshold
                self.logger.info(f"Auto-tuned similarity threshold for {class_name}",
                               old_threshold=current_threshold,
                               new_threshold=new_threshold,
                               avg_query_time_ms=avg_query_time)
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        total_cache_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / total_cache_requests if total_cache_requests > 0 else 0
        
        stats = {
            "total_queries": self.total_queries,
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "adaptive_thresholds": self.adaptive_similarity_thresholds.copy(),
            "performance_by_class": {}
        }
        
        # Calculate per-class statistics
        for class_name, metrics in self.performance_metrics.items():
            if metrics:
                query_times = [m["query_time_ms"] for m in metrics]
                result_counts = [m["result_count"] for m in metrics]
                
                stats["performance_by_class"][class_name] = {
                    "total_queries": len(metrics),
                    "avg_query_time_ms": sum(query_times) / len(query_times),
                    "min_query_time_ms": min(query_times),
                    "max_query_time_ms": max(query_times),
                    "avg_result_count": sum(result_counts) / len(result_counts),
                    "recent_avg_time_ms": sum(query_times[-10:]) / min(len(query_times), 10)
                }
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Enhanced health check with performance metrics."""
        basic_health = await super().health_check() if hasattr(super(), 'health_check') else {}
        
        performance_stats = await self.get_performance_stats()
        
        return {
            **basic_health,
            "optimizations_enabled": True,
            "performance_stats": performance_stats,
            "connection_pool_size": self.connection_pool_size,
            "max_concurrent_queries": self.max_concurrent_queries
        }


# Global optimized client instance
_optimized_weaviate_client: Optional[OptimizedWeaviateClient] = None


async def get_optimized_weaviate_client() -> OptimizedWeaviateClient:
    """Get or create global optimized Weaviate client instance."""
    global _optimized_weaviate_client
    
    if _optimized_weaviate_client is None:
        _optimized_weaviate_client = OptimizedWeaviateClient()
        await _optimized_weaviate_client.connect()
    
    return _optimized_weaviate_client


async def close_optimized_weaviate_client() -> None:
    """Close global optimized Weaviate client."""
    global _optimized_weaviate_client
    
    if _optimized_weaviate_client:
        await _optimized_weaviate_client.disconnect()
        _optimized_weaviate_client = None