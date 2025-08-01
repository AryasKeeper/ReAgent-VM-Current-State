"""
Data Aggregation Engine for Suburb Signal Agent

Optimized data aggregation using TimescaleDB continuous aggregates and advanced querying
for efficient analysis of 800+ Sydney suburbs with sub-5-minute performance requirements.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from decimal import Decimal

from sqlalchemy import select, func, and_, or_, text, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from reagent.core.database.engine import get_db_session
from reagent.data.models.property_models import Property, PropertyListing, PropertyPriceHistory
from reagent.data.models.market_models import MarketTrend, SuburbStats, PriceChange
from reagent.core.cache.redis_client import get_cache_manager


class AggregationPeriod(str, Enum):
    """Data aggregation period options."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class MetricType(str, Enum):
    """Types of metrics to aggregate."""
    PRICE = "price"
    VOLUME = "volume"
    TREND = "trend"
    COMPARATIVE = "comparative"
    ACTIVITY = "activity"


@dataclass
class AggregationQuery:
    """Configuration for data aggregation queries."""
    
    suburbs: List[str]
    start_date: datetime
    end_date: datetime
    period: AggregationPeriod
    metrics: List[MetricType]
    property_types: Optional[List[str]] = None
    price_range: Optional[Tuple[Decimal, Decimal]] = None
    bedroom_range: Optional[Tuple[int, int]] = None
    include_rentals: bool = False
    group_by_postcode: bool = False
    
    def __post_init__(self):
        """Validate query parameters."""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        
        if not self.suburbs:
            raise ValueError("At least one suburb must be specified")
        
        if not self.metrics:
            raise ValueError("At least one metric type must be specified")


@dataclass
class AggregatedData:
    """Container for aggregated market data."""
    
    suburb: str
    postcode: Optional[str]
    period_start: datetime
    period_end: datetime
    aggregation_period: AggregationPeriod
    
    # Price metrics
    median_price: Optional[Decimal] = None
    mean_price: Optional[Decimal] = None
    price_change: Optional[Decimal] = None
    price_change_percent: Optional[float] = None
    price_std: Optional[Decimal] = None
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    
    # Volume metrics
    sales_count: Optional[int] = None
    listings_count: Optional[int] = None
    withdrawn_count: Optional[int] = None
    active_listings: Optional[int] = None
    absorption_rate: Optional[float] = None
    
    # Market dynamics
    days_on_market_avg: Optional[float] = None
    days_on_market_median: Optional[float] = None
    price_reductions: Optional[int] = None
    price_increases: Optional[int] = None
    
    # Property type breakdown
    property_type_distribution: Dict[str, int] = None
    
    # Data quality
    sample_size: Optional[int] = None
    data_completeness: Optional[float] = None
    
    def __post_init__(self):
        if self.property_type_distribution is None:
            self.property_type_distribution = {}


class DataAggregator:
    """
    High-performance data aggregation engine for suburb market analysis.
    
    Leverages TimescaleDB continuous aggregates and intelligent caching
    for optimal performance across 800+ Sydney suburbs.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.cache_manager = get_cache_manager()
        
        # Performance configuration
        self.batch_size = 50  # Process suburbs in batches
        self.cache_ttl = 3600  # 1 hour cache TTL
        self.max_concurrent_queries = 10
        
        # Continuous aggregate views
        self.aggregate_views = {
            AggregationPeriod.DAILY: "daily_price_changes",
            AggregationPeriod.WEEKLY: "weekly_suburb_trends",
            AggregationPeriod.MONTHLY: "monthly_market_summary"
        }
        
        # Query optimization settings
        self.use_continuous_aggregates = True
        self.enable_query_caching = True
        self.parallel_processing = True
    
    async def aggregate_suburb_data(
        self,
        query: AggregationQuery,
        use_cache: bool = True
    ) -> Dict[str, AggregatedData]:
        """
        Aggregate market data for specified suburbs and time period.
        
        Args:
            query: Aggregation query configuration
            use_cache: Whether to use cached results
            
        Returns:
            Dict mapping suburb names to aggregated data
        """
        try:
            # Check cache first
            if use_cache and self.enable_query_caching:
                cached_results = await self._get_cached_results(query)
                if cached_results:
                    self.logger.info(f"Retrieved cached results for {len(cached_results)} suburbs")
                    return cached_results
            
            # Execute aggregation
            start_time = datetime.utcnow()
            
            if self.parallel_processing and len(query.suburbs) > self.batch_size:
                results = await self._parallel_aggregate(query)
            else:
                results = await self._sequential_aggregate(query)
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Cache results
            if use_cache and self.enable_query_caching:
                await self._cache_results(query, results)
            
            self.logger.info(
                f"Aggregated data for {len(results)} suburbs in {execution_time:.2f}s"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error aggregating suburb data: {e}")
            raise
    
    async def aggregate_comparative_metrics(
        self,
        suburbs: List[str],
        comparison_group: str = "sydney_metro",
        period: AggregationPeriod = AggregationPeriod.MONTHLY
    ) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate comparative metrics for suburb ranking and analysis.
        
        Args:
            suburbs: List of suburbs to analyze
            comparison_group: Comparison group ('lga', 'region', 'sydney_metro')
            period: Aggregation period
            
        Returns:
            Dict mapping suburb names to comparative metrics
        """
        try:
            async with get_db_session() as session:
                # Build comparative query based on period
                if period == AggregationPeriod.MONTHLY and self.use_continuous_aggregates:
                    query = await self._build_comparative_query_from_aggregates(
                        session, suburbs, comparison_group
                    )
                else:
                    query = await self._build_comparative_query_direct(
                        session, suburbs, comparison_group, period
                    )
                
                result = await session.execute(query)
                rows = result.fetchall()
                
                # Process results
                comparative_data = {}
                for row in rows:
                    suburb = row.suburb
                    if suburb not in comparative_data:
                        comparative_data[suburb] = {}
                    
                    comparative_data[suburb].update({
                        'median_price': row.median_price,
                        'price_growth_12m': row.price_growth_12m,
                        'sales_volume_30d': row.sales_volume_30d,
                        'rank_price': row.price_rank,
                        'rank_growth': row.growth_rank,
                        'rank_volume': row.volume_rank,
                        'percentile_price': row.price_percentile,
                        'percentile_growth': row.growth_percentile,
                        'percentile_volume': row.volume_percentile,
                        'total_suburbs': row.total_suburbs
                    })
                
                self.logger.info(f"Generated comparative metrics for {len(comparative_data)} suburbs")
                return comparative_data
                
        except Exception as e:
            self.logger.error(f"Error aggregating comparative metrics: {e}")
            raise
    
    async def aggregate_time_series(
        self,
        suburb: str,
        metric: MetricType,
        start_date: datetime,
        end_date: datetime,
        period: AggregationPeriod = AggregationPeriod.DAILY
    ) -> pd.DataFrame:
        """
        Aggregate time series data for a specific suburb and metric.
        
        Args:
            suburb: Suburb name
            metric: Type of metric to aggregate
            start_date: Start date for time series
            end_date: End date for time series
            period: Aggregation period
            
        Returns:
            DataFrame with time series data
        """
        try:
            async with get_db_session() as session:
                query = await self._build_time_series_query(
                    session, suburb, metric, start_date, end_date, period
                )
                
                result = await session.execute(query)
                rows = result.fetchall()
                
                # Convert to DataFrame
                if rows:
                    df = pd.DataFrame([dict(row._mapping) for row in rows])
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    df.sort_index(inplace=True)
                else:
                    # Return empty DataFrame with expected columns
                    df = pd.DataFrame(columns=['date'])
                    df.set_index('date', inplace=True)
                
                self.logger.info(f"Retrieved {len(df)} time series points for {suburb} ({metric.value})")
                return df
                
        except Exception as e:
            self.logger.error(f"Error aggregating time series for {suburb}: {e}")
            raise
    
    async def aggregate_market_summary(
        self,
        postcodes: Optional[List[str]] = None,
        lgas: Optional[List[str]] = None,
        property_types: Optional[List[str]] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None
    ) -> Dict[str, Any]:
        """
        Generate market summary statistics.
        
        Args:
            postcodes: Filter by postcodes
            lgas: Filter by LGAs
            property_types: Filter by property types
            date_range: Date range for analysis
            
        Returns:
            Dictionary with market summary statistics
        """
        try:
            async with get_db_session() as session:
                query = await self._build_market_summary_query(
                    session, postcodes, lgas, property_types, date_range
                )
                
                result = await session.execute(query)
                row = result.fetchone()
                
                if row:
                    summary = {
                        'total_suburbs': row.total_suburbs,
                        'total_properties': row.total_properties,
                        'total_sales': row.total_sales,
                        'median_price_sydney': row.median_price_sydney,
                        'avg_days_on_market': row.avg_days_on_market,
                        'price_growth_12m': row.price_growth_12m,
                        'most_active_suburb': row.most_active_suburb,
                        'highest_growth_suburb': row.highest_growth_suburb,
                        'analysis_date': datetime.utcnow(),
                        'data_coverage_percent': row.data_coverage_percent
                    }
                else:
                    summary = {
                        'total_suburbs': 0,
                        'total_properties': 0,
                        'analysis_date': datetime.utcnow()
                    }
                
                self.logger.info("Generated market summary statistics")
                return summary
                
        except Exception as e:
            self.logger.error(f"Error generating market summary: {e}")
            raise
    
    async def get_suburb_rankings(
        self,
        metric: str = "composite",
        period: AggregationPeriod = AggregationPeriod.MONTHLY,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get suburb rankings for specified metric.
        
        Args:
            metric: Ranking metric ('price', 'growth', 'volume', 'composite')
            period: Analysis period
            limit: Number of top suburbs to return
            
        Returns:
            List of suburb rankings with scores
        """
        try:
            async with get_db_session() as session:
                query = await self._build_ranking_query(session, metric, period, limit)
                
                result = await session.execute(query)
                rows = result.fetchall()
                
                rankings = []
                for i, row in enumerate(rows, 1):
                    rankings.append({
                        'rank': i,
                        'suburb': row.suburb,
                        'postcode': row.postcode,
                        'score': float(row.score) if row.score else 0.0,
                        'median_price': float(row.median_price) if row.median_price else 0.0,
                        'growth_12m': float(row.growth_12m) if row.growth_12m else 0.0,
                        'sales_volume': row.sales_volume or 0,
                        'percentile': round((len(rows) - i + 1) / len(rows) * 100, 1)
                    })
                
                self.logger.info(f"Generated top {len(rankings)} suburb rankings for {metric}")
                return rankings
                
        except Exception as e:
            self.logger.error(f"Error generating suburb rankings: {e}")
            raise
    
    # Private methods for query building and optimization
    
    async def _parallel_aggregate(self, query: AggregationQuery) -> Dict[str, AggregatedData]:
        """Execute aggregation in parallel batches."""
        results = {}
        
        # Split suburbs into batches
        batches = [
            query.suburbs[i:i + self.batch_size]
            for i in range(0, len(query.suburbs), self.batch_size)
        ]
        
        # Process batches concurrently
        semaphore = asyncio.Semaphore(self.max_concurrent_queries)
        
        async def process_batch(suburb_batch: List[str]) -> Dict[str, AggregatedData]:
            async with semaphore:
                batch_query = AggregationQuery(
                    suburbs=suburb_batch,
                    start_date=query.start_date,
                    end_date=query.end_date,
                    period=query.period,
                    metrics=query.metrics,
                    property_types=query.property_types,
                    price_range=query.price_range,
                    bedroom_range=query.bedroom_range,
                    include_rentals=query.include_rentals,
                    group_by_postcode=query.group_by_postcode
                )
                return await self._sequential_aggregate(batch_query)
        
        # Execute all batches
        batch_tasks = [process_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*batch_tasks)
        
        # Combine results
        for batch_result in batch_results:
            results.update(batch_result)
        
        return results
    
    async def _sequential_aggregate(self, query: AggregationQuery) -> Dict[str, AggregatedData]:
        """Execute aggregation sequentially."""
        results = {}
        
        async with get_db_session() as session:
            for metric in query.metrics:
                metric_data = await self._aggregate_metric(session, query, metric)
                
                # Merge metric data into results
                for suburb, data in metric_data.items():
                    if suburb not in results:
                        results[suburb] = AggregatedData(
                            suburb=suburb,
                            postcode=data.get('postcode'),
                            period_start=query.start_date,
                            period_end=query.end_date,
                            aggregation_period=query.period
                        )
                    
                    # Update result with metric-specific data
                    self._merge_metric_data(results[suburb], metric, data)
        
        return results
    
    async def _aggregate_metric(
        self,
        session: AsyncSession,
        query: AggregationQuery,
        metric: MetricType
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate data for a specific metric type."""
        
        if metric == MetricType.PRICE:
            return await self._aggregate_price_metrics(session, query)
        elif metric == MetricType.VOLUME:
            return await self._aggregate_volume_metrics(session, query)
        elif metric == MetricType.TREND:
            return await self._aggregate_trend_metrics(session, query)
        elif metric == MetricType.ACTIVITY:
            return await self._aggregate_activity_metrics(session, query)
        else:
            self.logger.warning(f"Unknown metric type: {metric}")
            return {}
    
    async def _aggregate_price_metrics(
        self,
        session: AsyncSession,
        query: AggregationQuery
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate price-related metrics."""
        
        # Use continuous aggregates if available and appropriate
        if (query.period in self.aggregate_views and 
            self.use_continuous_aggregates):
            return await self._aggregate_price_from_views(session, query)
        else:
            return await self._aggregate_price_direct(session, query)
    
    async def _aggregate_price_from_views(
        self,
        session: AsyncSession,
        query: AggregationQuery
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate price metrics using continuous aggregates."""
        
        view_name = self.aggregate_views[query.period]
        
        # Build query using continuous aggregate view
        sql_query = text(f"""
            SELECT 
                suburb,
                postcode,
                AVG(avg_price) as median_price,
                STDDEV(avg_price) as price_std,
                MIN(avg_price) as price_min,
                MAX(avg_price) as price_max,
                SUM(change_count) as total_changes,
                AVG(avg_change_pct) as avg_change_percent,
                COUNT(*) as data_points
            FROM {view_name}
            WHERE suburb = ANY(:suburbs)
              AND day BETWEEN :start_date AND :end_date
            GROUP BY suburb, postcode
            ORDER BY suburb
        """)
        
        result = await session.execute(sql_query, {
            'suburbs': query.suburbs,
            'start_date': query.start_date,
            'end_date': query.end_date
        })
        
        rows = result.fetchall()
        
        # Process results
        data = {}
        for row in rows:
            data[row.suburb] = {
                'postcode': row.postcode,
                'median_price': Decimal(str(row.median_price)) if row.median_price else None,
                'price_std': Decimal(str(row.price_std)) if row.price_std else None,
                'price_min': Decimal(str(row.price_min)) if row.price_min else None,
                'price_max': Decimal(str(row.price_max)) if row.price_max else None,
                'total_changes': row.total_changes or 0,
                'avg_change_percent': row.avg_change_percent or 0.0,
                'sample_size': row.data_points or 0
            }
        
        return data
    
    async def _aggregate_price_direct(
        self,
        session: AsyncSession,
        query: AggregationQuery
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate price metrics directly from base tables."""
        
        # Build base query
        base_query = select(
            Property.suburb,
            Property.postcode,
            func.percentile_cont(0.5).within_group(PropertyPriceHistory.amount).label('median_price'),
            func.avg(PropertyPriceHistory.amount).label('mean_price'),
            func.stddev(PropertyPriceHistory.amount).label('price_std'),
            func.min(PropertyPriceHistory.amount).label('price_min'),
            func.max(PropertyPriceHistory.amount).label('price_max'),
            func.count(PropertyPriceHistory.id).label('sample_size')
        ).select_from(
            Property.__table__.join(PropertyPriceHistory.__table__)
        ).where(
            and_(
                Property.suburb.in_(query.suburbs),
                PropertyPriceHistory.recorded_at.between(query.start_date, query.end_date)
            )
        )
        
        # Add optional filters
        if query.property_types:
            base_query = base_query.where(Property.property_type.in_(query.property_types))
        
        if query.price_range:
            base_query = base_query.where(
                PropertyPriceHistory.amount.between(query.price_range[0], query.price_range[1])
            )
        
        if query.bedroom_range:
            base_query = base_query.where(
                Property.bedrooms.between(query.bedroom_range[0], query.bedroom_range[1])
            )
        
        # Group by suburb
        if query.group_by_postcode:
            base_query = base_query.group_by(Property.suburb, Property.postcode)
        else:
            base_query = base_query.group_by(Property.suburb, Property.postcode)
        
        result = await session.execute(base_query)
        rows = result.fetchall()
        
        # Process results
        data = {}
        for row in rows:
            data[row.suburb] = {
                'postcode': row.postcode,
                'median_price': Decimal(str(row.median_price)) if row.median_price else None,
                'mean_price': Decimal(str(row.mean_price)) if row.mean_price else None,
                'price_std': Decimal(str(row.price_std)) if row.price_std else None,
                'price_min': Decimal(str(row.price_min)) if row.price_min else None,
                'price_max': Decimal(str(row.price_max)) if row.price_max else None,
                'sample_size': row.sample_size or 0
            }
        
        return data
    
    async def _aggregate_volume_metrics(
        self,
        session: AsyncSession,
        query: AggregationQuery
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate volume-related metrics."""
        
        # Query for listing and sales volumes
        volume_query = select(
            Property.suburb,
            Property.postcode,
            func.count(
                func.distinct(PropertyListing.id).filter(
                    PropertyListing.status == 'active'
                )
            ).label('active_listings'),
            func.count(
                func.distinct(PropertyListing.id).filter(
                    PropertyListing.status == 'sold'
                )
            ).label('sales_count'),
            func.count(
                func.distinct(PropertyListing.id).filter(
                    PropertyListing.status == 'withdrawn'
                )
            ).label('withdrawn_count'),
            func.count(func.distinct(PropertyListing.id)).label('total_listings'),
            func.avg(PropertyListing.days_on_market).label('avg_days_on_market'),
            func.percentile_cont(0.5).within_group(PropertyListing.days_on_market).label('median_days_on_market')
        ).select_from(
            Property.__table__.join(PropertyListing.__table__)
        ).where(
            and_(
                Property.suburb.in_(query.suburbs),
                PropertyListing.listing_date.between(query.start_date, query.end_date)
            )
        )
        
        # Add optional filters
        if query.property_types:
            volume_query = volume_query.where(Property.property_type.in_(query.property_types))
        
        if query.bedroom_range:
            volume_query = volume_query.where(
                Property.bedrooms.between(query.bedroom_range[0], query.bedroom_range[1])
            )
        
        volume_query = volume_query.group_by(Property.suburb, Property.postcode)
        
        result = await session.execute(volume_query)
        rows = result.fetchall()
        
        # Process results
        data = {}
        for row in rows:
            # Calculate absorption rate
            absorption_rate = None
            if row.total_listings and row.total_listings > 0:
                absorption_rate = row.sales_count / row.total_listings
            
            data[row.suburb] = {
                'postcode': row.postcode,
                'active_listings': row.active_listings or 0,
                'sales_count': row.sales_count or 0,
                'withdrawn_count': row.withdrawn_count or 0,
                'total_listings': row.total_listings or 0,
                'absorption_rate': absorption_rate,
                'avg_days_on_market': float(row.avg_days_on_market) if row.avg_days_on_market else None,
                'median_days_on_market': float(row.median_days_on_market) if row.median_days_on_market else None
            }
        
        return data
    
    async def _aggregate_trend_metrics(
        self,
        session: AsyncSession,
        query: AggregationQuery
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate trend-related metrics."""
        
        # Query for price changes and trends
        trend_query = select(
            PriceChange.suburb,
            func.count(PriceChange.id).label('total_changes'),
            func.count(PriceChange.id).filter(PriceChange.change_type == 'increase').label('price_increases'),
            func.count(PriceChange.id).filter(PriceChange.change_type == 'decrease').label('price_decreases'),
            func.avg(PriceChange.change_percent).label('avg_change_percent'),
            func.stddev(PriceChange.change_percent).label('change_volatility'),
            func.avg(PriceChange.confidence_score).label('avg_confidence')
        ).where(
            and_(
                PriceChange.suburb.in_(query.suburbs),
                PriceChange.created_at.between(query.start_date, query.end_date)
            )
        ).group_by(PriceChange.suburb)
        
        result = await session.execute(trend_query)
        rows = result.fetchall()
        
        # Process results
        data = {}
        for row in rows:
            data[row.suburb] = {
                'total_changes': row.total_changes or 0,
                'price_increases': row.price_increases or 0,
                'price_decreases': row.price_decreases or 0,
                'avg_change_percent': float(row.avg_change_percent) if row.avg_change_percent else 0.0,
                'change_volatility': float(row.change_volatility) if row.change_volatility else 0.0,
                'avg_confidence': float(row.avg_confidence) if row.avg_confidence else 0.0
            }
        
        return data
    
    async def _aggregate_activity_metrics(
        self,
        session: AsyncSession,
        query: AggregationQuery
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate market activity metrics."""
        
        # This would include interaction data, search volumes, etc.
        # For now, return basic activity metrics based on listing activity
        
        activity_query = select(
            Property.suburb,
            Property.postcode,
            func.count(func.distinct(PropertyListing.id)).label('listing_activity'),
            func.count(func.distinct(Property.id)).label('unique_properties'),
            func.avg(
                func.extract('epoch', 
                    func.coalesce(PropertyListing.sold_date, func.now()) - PropertyListing.listing_date
                ) / 86400
            ).label('avg_market_time')
        ).select_from(
            Property.__table__.join(PropertyListing.__table__)
        ).where(
            and_(
                Property.suburb.in_(query.suburbs),
                PropertyListing.listing_date.between(query.start_date, query.end_date)
            )
        ).group_by(Property.suburb, Property.postcode)
        
        result = await session.execute(activity_query)
        rows = result.fetchall()
        
        # Process results
        data = {}
        for row in rows:
            data[row.suburb] = {
                'postcode': row.postcode,
                'listing_activity': row.listing_activity or 0,
                'unique_properties': row.unique_properties or 0,
                'avg_market_time': float(row.avg_market_time) if row.avg_market_time else None
            }
        
        return data
    
    def _merge_metric_data(self, result: AggregatedData, metric: MetricType, data: Dict[str, Any]):
        """Merge metric-specific data into aggregated result."""
        
        if metric == MetricType.PRICE:
            result.median_price = data.get('median_price')
            result.mean_price = data.get('mean_price')
            result.price_std = data.get('price_std')
            result.price_min = data.get('price_min')
            result.price_max = data.get('price_max')
            if not result.sample_size:
                result.sample_size = data.get('sample_size', 0)
        
        elif metric == MetricType.VOLUME:
            result.sales_count = data.get('sales_count')
            result.listings_count = data.get('total_listings')
            result.withdrawn_count = data.get('withdrawn_count')
            result.active_listings = data.get('active_listings')
            result.absorption_rate = data.get('absorption_rate')
            result.days_on_market_avg = data.get('avg_days_on_market')
            result.days_on_market_median = data.get('median_days_on_market')
        
        elif metric == MetricType.TREND:
            result.price_increases = data.get('price_increases')
            result.price_reductions = data.get('price_decreases')
        
        # Set postcode if not already set
        if not result.postcode and 'postcode' in data:
            result.postcode = data['postcode']
    
    async def _get_cached_results(self, query: AggregationQuery) -> Optional[Dict[str, AggregatedData]]:
        """Retrieve cached aggregation results."""
        if not self.cache_manager:
            return None
        
        try:
            cache_key = self._generate_cache_key(query)
            cached_data = await self.cache_manager.get(cache_key)
            
            if cached_data:
                # Deserialize cached data (implementation would depend on cache format)
                self.logger.debug(f"Cache hit for aggregation query: {cache_key}")
                return cached_data
            
        except Exception as e:
            self.logger.warning(f"Error retrieving cached results: {e}")
        
        return None
    
    async def _cache_results(self, query: AggregationQuery, results: Dict[str, AggregatedData]):
        """Cache aggregation results."""
        if not self.cache_manager:
            return
        
        try:
            cache_key = self._generate_cache_key(query)
            await self.cache_manager.set(cache_key, results, ttl=self.cache_ttl)
            self.logger.debug(f"Cached aggregation results: {cache_key}")
            
        except Exception as e:
            self.logger.warning(f"Error caching results: {e}")
    
    def _generate_cache_key(self, query: AggregationQuery) -> str:
        """Generate cache key for aggregation query."""
        key_parts = [
            f"agg",
            f"suburbs:{hash(tuple(sorted(query.suburbs)))}",
            f"period:{query.period.value}",
            f"start:{query.start_date.strftime('%Y%m%d')}",
            f"end:{query.end_date.strftime('%Y%m%d')}",
            f"metrics:{'-'.join(sorted([m.value for m in query.metrics]))}"
        ]
        
        if query.property_types:
            key_parts.append(f"types:{'-'.join(sorted(query.property_types))}")
        
        if query.price_range:
            key_parts.append(f"price:{query.price_range[0]}-{query.price_range[1]}")
        
        return ":".join(key_parts)
    
    # Additional query builders for specialized aggregations
    
    async def _build_time_series_query(
        self,
        session: AsyncSession,
        suburb: str,
        metric: MetricType,
        start_date: datetime,
        end_date: datetime,
        period: AggregationPeriod
    ) -> Select:
        """Build time series query for specific suburb and metric."""
        
        # Time bucket size based on period
        bucket_sizes = {
            AggregationPeriod.HOURLY: "1 hour",
            AggregationPeriod.DAILY: "1 day",
            AggregationPeriod.WEEKLY: "1 week",
            AggregationPeriod.MONTHLY: "1 month"
        }
        
        bucket_size = bucket_sizes.get(period, "1 day")
        
        if metric == MetricType.PRICE:
            # Price time series from PropertyPriceHistory
            query = select(
                func.time_bucket(bucket_size, PropertyPriceHistory.recorded_at).label('date'),
                func.avg(PropertyPriceHistory.amount).label('price'),
                func.count(PropertyPriceHistory.id).label('volume')
            ).select_from(
                Property.__table__.join(PropertyPriceHistory.__table__)
            ).where(
                and_(
                    Property.suburb == suburb,
                    PropertyPriceHistory.recorded_at.between(start_date, end_date)
                )
            ).group_by(
                func.time_bucket(bucket_size, PropertyPriceHistory.recorded_at)
            ).order_by('date')
            
        elif metric == MetricType.VOLUME:
            # Volume time series from PropertyListing
            query = select(
                func.time_bucket(bucket_size, PropertyListing.listing_date).label('date'),
                func.count(PropertyListing.id).label('listings'),
                func.count(PropertyListing.id).filter(PropertyListing.status == 'sold').label('sales')
            ).select_from(
                Property.__table__.join(PropertyListing.__table__)
            ).where(
                and_(
                    Property.suburb == suburb,
                    PropertyListing.listing_date.between(start_date, end_date)
                )
            ).group_by(
                func.time_bucket(bucket_size, PropertyListing.listing_date)
            ).order_by('date')
            
        else:
            raise ValueError(f"Time series not supported for metric: {metric}")
        
        return query
    
    async def _build_comparative_query_from_aggregates(
        self,
        session: AsyncSession,
        suburbs: List[str],
        comparison_group: str
    ) -> Select:
        """Build comparative query using continuous aggregates."""
        
        # Use weekly trends view for comparative analysis
        query = text("""
            WITH suburb_metrics AS (
                SELECT 
                    suburb,
                    postcode,
                    AVG(avg_price_guide) as median_price,
                    (AVG(avg_price_guide) - LAG(AVG(avg_price_guide), 52) OVER (PARTITION BY suburb ORDER BY week)) / 
                     LAG(AVG(avg_price_guide), 52) OVER (PARTITION BY suburb ORDER BY week) * 100 as price_growth_12m,
                    SUM(sales_count) as sales_volume_30d
                FROM weekly_suburb_trends
                WHERE week >= NOW() - INTERVAL '13 months'
                GROUP BY suburb, postcode
            ),
            rankings AS (
                SELECT 
                    *,
                    ROW_NUMBER() OVER (ORDER BY median_price DESC) as price_rank,
                    ROW_NUMBER() OVER (ORDER BY price_growth_12m DESC) as growth_rank,
                    ROW_NUMBER() OVER (ORDER BY sales_volume_30d DESC) as volume_rank,
                    PERCENT_RANK() OVER (ORDER BY median_price) * 100 as price_percentile,
                    PERCENT_RANK() OVER (ORDER BY price_growth_12m) * 100 as growth_percentile,
                    PERCENT_RANK() OVER (ORDER BY sales_volume_30d) * 100 as volume_percentile,
                    COUNT(*) OVER () as total_suburbs
                FROM suburb_metrics
            )
            SELECT * FROM rankings
            WHERE suburb = ANY(:suburbs)
            ORDER BY suburb
        """)
        
        return query
    
    async def _build_comparative_query_direct(
        self,
        session: AsyncSession,
        suburbs: List[str],
        comparison_group: str,
        period: AggregationPeriod
    ) -> Select:
        """Build comparative query directly from base tables."""
        
        # This would build a more complex query for real-time comparative analysis
        # For brevity, returning a simplified version
        
        query = select(
            Property.suburb,
            Property.postcode,
            func.percentile_cont(0.5).within_group(PropertyListing.price_guide).label('median_price'),
            func.count(PropertyListing.id).filter(PropertyListing.status == 'sold').label('sales_volume_30d'),
            func.row_number().over(order_by=desc(func.percentile_cont(0.5).within_group(PropertyListing.price_guide))).label('price_rank')
        ).select_from(
            Property.__table__.join(PropertyListing.__table__)
        ).where(
            Property.suburb.in_(suburbs)
        ).group_by(Property.suburb, Property.postcode)
        
        return query
    
    async def _build_market_summary_query(
        self,
        session: AsyncSession,
        postcodes: Optional[List[str]],
        lgas: Optional[List[str]],
        property_types: Optional[List[str]],
        date_range: Optional[Tuple[datetime, datetime]]
    ) -> Select:
        """Build market summary query."""
        
        base_query = select(
            func.count(func.distinct(Property.suburb)).label('total_suburbs'),
            func.count(func.distinct(Property.id)).label('total_properties'),
            func.count(PropertyListing.id).filter(PropertyListing.status == 'sold').label('total_sales'),
            func.percentile_cont(0.5).within_group(PropertyListing.price_guide).label('median_price_sydney'),
            func.avg(PropertyListing.days_on_market).label('avg_days_on_market'),
            func.avg(
                (PropertyListing.price_guide - PropertyListing.original_price) / PropertyListing.original_price * 100
            ).label('price_growth_12m')
        ).select_from(
            Property.__table__.join(PropertyListing.__table__)
        )
        
        # Apply filters
        conditions = []
        
        if postcodes:
            conditions.append(Property.postcode.in_(postcodes))
        
        if lgas:
            conditions.append(Property.lga.in_(lgas))
        
        if property_types:
            conditions.append(Property.property_type.in_(property_types))
        
        if date_range:
            conditions.append(PropertyListing.listing_date.between(date_range[0], date_range[1]))
        
        if conditions:
            base_query = base_query.where(and_(*conditions))
        
        return base_query
    
    async def _build_ranking_query(
        self,
        session: AsyncSession,
        metric: str,
        period: AggregationPeriod,
        limit: int
    ) -> Select:
        """Build suburb ranking query."""
        
        # Simplified ranking query - would be more sophisticated in practice
        if metric == "composite":
            order_column = func.coalesce(
                PropertyListing.price_guide * 0.4 +
                func.coalesce(PropertyListing.days_on_market, 0) * 0.3 +
                func.count(PropertyListing.id) * 0.3,
                0
            )
        elif metric == "price":
            order_column = func.percentile_cont(0.5).within_group(PropertyListing.price_guide)
        elif metric == "growth":
            order_column = func.avg(
                (PropertyListing.price_guide - PropertyListing.original_price) / PropertyListing.original_price * 100
            )
        else:  # volume
            order_column = func.count(PropertyListing.id)
        
        query = select(
            Property.suburb,
            Property.postcode,
            order_column.label('score'),
            func.percentile_cont(0.5).within_group(PropertyListing.price_guide).label('median_price'),
            func.avg(
                (PropertyListing.price_guide - PropertyListing.original_price) / PropertyListing.original_price * 100
            ).label('growth_12m'),
            func.count(PropertyListing.id).label('sales_volume')
        ).select_from(
            Property.__table__.join(PropertyListing.__table__)
        ).group_by(
            Property.suburb, Property.postcode
        ).order_by(
            desc(order_column)
        ).limit(limit)
        
        return query