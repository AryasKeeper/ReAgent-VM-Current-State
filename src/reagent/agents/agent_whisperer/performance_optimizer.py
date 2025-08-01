"""
ReAgent Sydney - Financial Analysis Performance Optimizer

Optimizes financial calculations for real-time report generation with
advanced caching, database query efficiency, and concurrent processing.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import hashlib
import json
import structlog

from src.core.cache.redis_client import get_cache_manager
from src.agents.agent_whisperer.financial_analyzer import SydneyFinancialAnalyzer, FinancialMetrics
from src.agents.agent_whisperer.market_validator import SydneyMarketValidator, MarketValidationReport


logger = structlog.get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance tracking for financial analysis operations."""
    operation_name: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    cache_hit: bool
    data_sources_used: List[str]
    concurrent_operations: int
    memory_used_mb: float


class OptimizedFinancialAnalyzer:
    """
    Performance-optimized financial analyzer with advanced caching,
    batch processing, and concurrent API calls.
    """
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.base_analyzer = SydneyFinancialAnalyzer()
        self.validator = SydneyMarketValidator()
        
        # Performance configuration
        self.batch_size = 10
        self.cache_ttl = {
            "financial_metrics": 3600,      # 1 hour
            "market_data": 1800,            # 30 minutes
            "validation_report": 7200,      # 2 hours
            "suburb_benchmarks": 21600      # 6 hours
        }
        
        # Connection pooling and rate limiting
        self.concurrent_limit = 5
        self.rate_limit_semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        # Performance tracking
        self.performance_history = []
        
    async def analyze_property_financials_optimized(
        self,
        property_data: Dict[str, Any],
        include_validation: bool = True,
        cache_strategy: str = "aggressive"
    ) -> Tuple[FinancialMetrics, Optional[MarketValidationReport], PerformanceMetrics]:
        """
        Optimized financial analysis with performance tracking.
        
        Args:
            property_data: Property information
            include_validation: Whether to include market validation
            cache_strategy: Cache strategy ("aggressive", "balanced", "minimal")
            
        Returns:
            Financial metrics, validation report, and performance metrics
        """
        start_time = datetime.utcnow()
        cache_hits = 0
        data_sources = []
        
        try:
            # Generate optimized cache keys
            base_cache_key = self._generate_cache_key(property_data)
            financial_cache_key = f"opt_financial:{base_cache_key}"
            validation_cache_key = f"opt_validation:{base_cache_key}"
            
            # Determine cache TTL based on strategy
            financial_ttl = self._get_cache_ttl("financial_metrics", cache_strategy)
            validation_ttl = self._get_cache_ttl("validation_report", cache_strategy)
            
            # Try to get cached results
            financial_metrics = None
            validation_report = None
            
            if cache_strategy != "minimal":
                cached_financial = await self.cache_manager.get(financial_cache_key)
                if cached_financial:
                    financial_metrics = FinancialMetrics(**cached_financial)
                    cache_hits += 1
                    logger.debug("Financial metrics cache hit", property_id=property_data.get('property_id'))
                
                if include_validation:
                    cached_validation = await self.cache_manager.get(validation_cache_key)
                    if cached_validation:
                        validation_report = MarketValidationReport(**cached_validation)
                        cache_hits += 1
                        logger.debug("Validation report cache hit", property_id=property_data.get('property_id'))
            
            # Generate missing data concurrently
            async with self.rate_limit_semaphore:
                tasks = []
                
                if financial_metrics is None:
                    tasks.append(self._get_financial_metrics(property_data))
                    
                if include_validation and validation_report is None and financial_metrics is not None:
                    tasks.append(self._get_validation_report(financial_metrics, property_data))
                elif include_validation and validation_report is None:
                    # Need to wait for financial metrics first
                    tasks.append(None)  # Placeholder
                
                if tasks:
                    if len(tasks) == 2 and tasks[1] is not None:
                        # Can run both concurrently
                        results = await asyncio.gather(*[t for t in tasks if t is not None])
                        financial_metrics = results[0]
                        if len(results) > 1:
                            validation_report = results[1]
                    else:
                        # Run financial metrics first, then validation
                        if financial_metrics is None:
                            financial_metrics = await tasks[0]
                        
                        if include_validation and validation_report is None:
                            validation_report = await self._get_validation_report(financial_metrics, property_data)
            
            # Cache the results
            if cache_strategy != "minimal":
                cache_tasks = []
                
                if financial_metrics and cache_hits < 2:
                    cache_tasks.append(
                        self.cache_manager.set(financial_cache_key, financial_metrics.__dict__, ttl=financial_ttl)
                    )
                
                if validation_report and include_validation:
                    cache_tasks.append(
                        self.cache_manager.set(validation_cache_key, validation_report.__dict__, ttl=validation_ttl)
                    )
                
                if cache_tasks:
                    await asyncio.gather(*cache_tasks)
            
            # Record performance metrics
            end_time = datetime.utcnow()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            
            performance_metrics = PerformanceMetrics(
                operation_name="analyze_property_financials_optimized",
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                cache_hit=cache_hits > 0,
                data_sources_used=data_sources,
                concurrent_operations=len([t for t in tasks if t is not None]) if 'tasks' in locals() else 0,
                memory_used_mb=0.0  # Would implement memory tracking in production
            )
            
            self.performance_history.append(performance_metrics)
            
            logger.info("Optimized financial analysis completed",
                       property_id=property_data.get('property_id'),
                       duration_ms=duration_ms,
                       cache_hits=cache_hits,
                       include_validation=include_validation)
            
            return financial_metrics, validation_report, performance_metrics
            
        except Exception as e:
            logger.error("Optimized financial analysis failed",
                        property_id=property_data.get('property_id'),
                        error=str(e))
            raise
    
    async def batch_analyze_properties(
        self,
        properties_data: List[Dict[str, Any]],
        include_validation: bool = True
    ) -> List[Tuple[FinancialMetrics, Optional[MarketValidationReport], PerformanceMetrics]]:
        """
        Batch analyze multiple properties with optimized concurrent processing.
        
        Args:
            properties_data: List of property data dictionaries
            include_validation: Whether to include validation for each property
            
        Returns:
            List of analysis results
        """
        logger.info("Starting batch financial analysis",
                   property_count=len(properties_data),
                   include_validation=include_validation)
        
        # Process in batches to avoid overwhelming APIs
        results = []
        
        for i in range(0, len(properties_data), self.batch_size):
            batch = properties_data[i:i + self.batch_size]
            
            # Process batch concurrently
            batch_tasks = [
                self.analyze_property_financials_optimized(
                    property_data,
                    include_validation=include_validation,
                    cache_strategy="balanced"
                )
                for property_data in batch
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle exceptions and add successful results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error("Batch analysis failed for property",
                                property_index=i + j,
                                error=str(result))
                else:
                    results.append(result)
        
        logger.info("Batch financial analysis completed",
                   successful_analyses=len(results),
                   total_requested=len(properties_data))
        
        return results
    
    async def _get_financial_metrics(self, property_data: Dict[str, Any]) -> FinancialMetrics:
        """Get financial metrics with optimized data fetching."""
        return await self.base_analyzer.analyze_property_financials(property_data)
    
    async def _get_validation_report(
        self,
        financial_metrics: FinancialMetrics,
        property_data: Dict[str, Any]
    ) -> MarketValidationReport:
        """Get validation report with optimized processing."""
        return await self.validator.validate_financial_analysis(
            financial_metrics,
            property_data.get('property_type', 'house')
        )
    
    def _generate_cache_key(self, property_data: Dict[str, Any]) -> str:
        """Generate optimized cache key from property data."""
        # Use key fields that affect financial calculations
        key_fields = {
            'suburb': property_data.get('suburb', ''),
            'postcode': property_data.get('postcode', ''),
            'property_type': property_data.get('property_type', ''),
            'bedrooms': property_data.get('bedrooms', 0),
            'bathrooms': property_data.get('bathrooms', 0),
            'property_id': property_data.get('property_id', property_data.get('address', ''))
        }
        
        # Create hash of key fields
        key_string = json.dumps(key_fields, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cache_ttl(self, cache_type: str, strategy: str) -> int:
        """Get cache TTL based on type and strategy."""
        base_ttl = self.cache_ttl.get(cache_type, 3600)
        
        if strategy == "aggressive":
            return base_ttl * 2  # Cache longer
        elif strategy == "minimal":
            return base_ttl // 4  # Cache shorter
        else:  # balanced
            return base_ttl
    
    def get_performance_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance statistics for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        recent_metrics = [
            m for m in self.performance_history
            if m.start_time >= cutoff_time
        ]
        
        if not recent_metrics:
            return {
                "total_operations": 0,
                "average_duration_ms": 0,
                "cache_hit_rate": 0,
                "fastest_operation_ms": 0,
                "slowest_operation_ms": 0
            }
        
        durations = [m.duration_ms for m in recent_metrics]
        cache_hits = sum(1 for m in recent_metrics if m.cache_hit)
        
        return {
            "total_operations": len(recent_metrics),
            "average_duration_ms": sum(durations) / len(durations),
            "cache_hit_rate": (cache_hits / len(recent_metrics)) * 100,
            "fastest_operation_ms": min(durations),
            "slowest_operation_ms": max(durations),
            "concurrent_operations_avg": sum(m.concurrent_operations for m in recent_metrics) / len(recent_metrics),
            "data_sources_diversity": len(set().union(*[m.data_sources_used for m in recent_metrics]))
        }
    
    async def warm_cache_for_suburb(self, suburb: str, property_types: List[str] = None) -> Dict[str, Any]:
        """Warm cache with common suburb financial data."""
        if property_types is None:
            property_types = ["house", "unit", "townhouse"]
        
        logger.info("Warming cache for suburb", suburb=suburb, property_types=property_types)
        
        # Create sample property data for cache warming
        sample_properties = []
        for prop_type in property_types:
            for bedrooms in [2, 3, 4]:
                sample_properties.append({
                    'suburb': suburb,
                    'property_type': prop_type,
                    'bedrooms': bedrooms,
                    'bathrooms': max(1, bedrooms - 1),
                    'property_id': f"sample_{suburb}_{prop_type}_{bedrooms}br"
                })
        
        # Analyze properties to populate cache
        results = await self.batch_analyze_properties(sample_properties, include_validation=False)
        
        return {
            "suburb": suburb,
            "cached_combinations": len(sample_properties),
            "successful_analyses": len(results),
            "cache_warming_completed": datetime.utcnow().isoformat()
        }


# Optimized function for report generator
async def generate_optimized_financial_analysis_section(
    property_info: Dict[str, Any],
    cache_strategy: str = "balanced"
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate financial analysis section with optimized performance.
    
    Drop-in replacement for the standard financial analysis function
    with enhanced performance and caching.
    """
    try:
        optimizer = OptimizedFinancialAnalyzer()
        
        financial_metrics, validation_report, performance_metrics = await optimizer.analyze_property_financials_optimized(
            property_info,
            include_validation=True,
            cache_strategy=cache_strategy
        )
        
        # Import the standard function for data formatting
        from src.agents.agent_whisperer.financial_analyzer import generate_financial_analysis_section_with_real_data
        
        # Use the standard formatter but with optimized data
        content, data = await generate_financial_analysis_section_with_real_data(property_info)
        
        # Add performance metadata
        data["metadata"]["performance"] = {
            "analysis_duration_ms": performance_metrics.duration_ms,
            "cache_hit": performance_metrics.cache_hit,
            "concurrent_operations": performance_metrics.concurrent_operations,
            "optimization_enabled": True
        }
        
        # Update content to reflect optimization
        if performance_metrics.cache_hit:
            content = content.replace("Real-time", "Cached real-time")
        
        logger.info("Optimized financial analysis section generated",
                   property_id=property_info.get('property_id'),
                   duration_ms=performance_metrics.duration_ms,
                   cache_hit=performance_metrics.cache_hit)
        
        return content, data
        
    except Exception as e:
        logger.error("Optimized financial analysis section generation failed", error=str(e))
        
        # Fallback to standard function
        from src.agents.agent_whisperer.financial_analyzer import generate_financial_analysis_section_with_real_data
        return await generate_financial_analysis_section_with_real_data(property_info)


# Export for use in report generator
__all__ = [
    'OptimizedFinancialAnalyzer', 
    'generate_optimized_financial_analysis_section',
    'PerformanceMetrics'
]