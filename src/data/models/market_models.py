"""
ReAgent Sydney - Market Data Models

SQLAlchemy models for market trends, suburb statistics, and price analysis.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Numeric, Text, DateTime, Boolean, 
    ForeignKey, Index, CheckConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import Base, TimestampMixin


class TrendDirection(str, Enum):
    """Market trend direction enumeration."""
    UP = "Up"
    DOWN = "Down"
    STABLE = "Stable"
    VOLATILE = "Volatile"


class MarketSegment(str, Enum):
    """Market segment enumeration."""
    BUDGET = "Budget"      # <$1M
    MID_RANGE = "Mid-Range"  # $1M-$2M  
    PREMIUM = "Premium"    # $2M-$5M
    LUXURY = "Luxury"      # >$5M


class MarketTrend(Base, TimestampMixin):
    """Market trend analysis data."""
    
    __tablename__ = "market_trends"
    
    # Geographic Scope
    geography_type = Column(String(20), nullable=False, doc="Geography type (suburb, lga, region)")
    geography_name = Column(String(100), nullable=False, doc="Geographic area name")
    postcode = Column(String(10), nullable=True, index=True, doc="Postcode if applicable")
    
    # Time Period
    period_start = Column(DateTime(timezone=True), nullable=False, doc="Analysis period start")
    period_end = Column(DateTime(timezone=True), nullable=False, doc="Analysis period end")
    period_type = Column(String(20), nullable=False, doc="Period type (weekly, monthly, quarterly)")
    
    # Market Segment
    property_type = Column(String(50), nullable=True, doc="Property type filter")
    market_segment = Column(String(20), nullable=True, doc="Market segment")
    bedroom_range = Column(String(20), nullable=True, doc="Bedroom range (e.g., '2-3')")
    
    # Price Metrics
    median_price = Column(Numeric(12, 2), nullable=True, doc="Median sale price")
    mean_price = Column(Numeric(12, 2), nullable=True, doc="Average sale price")
    price_change = Column(Numeric(12, 2), nullable=True, doc="Price change from previous period")
    price_change_percent = Column(Numeric(5, 2), nullable=True, doc="Price change percentage")
    
    # Volume Metrics
    sales_volume = Column(Integer, nullable=True, doc="Number of sales")
    listings_volume = Column(Integer, nullable=True, doc="Number of new listings")
    volume_change = Column(Integer, nullable=True, doc="Volume change from previous period")
    volume_change_percent = Column(Numeric(5, 2), nullable=True, doc="Volume change percentage")
    
    # Market Dynamics
    days_on_market = Column(Numeric(5, 1), nullable=True, doc="Average days on market")
    absorption_rate = Column(Numeric(5, 2), nullable=True, doc="Absorption rate (sales/listings)")
    inventory_level = Column(Integer, nullable=True, doc="Current inventory level")
    
    # Trend Analysis
    trend_direction = Column(String(20), nullable=True, doc="Overall trend direction")
    trend_strength = Column(Numeric(3, 2), nullable=True, doc="Trend strength (0-1)")
    volatility_index = Column(Numeric(5, 2), nullable=True, doc="Price volatility index")
    
    # Price Ranges
    price_min = Column(Numeric(12, 2), nullable=True, doc="Minimum price in period")
    price_max = Column(Numeric(12, 2), nullable=True, doc="Maximum price in period")
    price_25th = Column(Numeric(12, 2), nullable=True, doc="25th percentile price")
    price_75th = Column(Numeric(12, 2), nullable=True, doc="75th percentile price")
    
    # Comparative Metrics
    vs_previous_period = Column(JSONB, nullable=True, doc="Comparison with previous period")
    vs_same_period_last_year = Column(JSONB, nullable=True, doc="Year-over-year comparison")
    market_rank = Column(Integer, nullable=True, doc="Rank among similar areas")
    
    # Data Quality
    sample_size = Column(Integer, nullable=True, doc="Number of data points")
    confidence_level = Column(Numeric(3, 2), nullable=True, doc="Statistical confidence")
    data_completeness = Column(Numeric(3, 2), nullable=True, doc="Data completeness ratio")
    
    # Metadata
    analysis_method = Column(String(50), nullable=False, doc="Analysis methodology")
    data_sources = Column(ARRAY(String), nullable=False, doc="Data sources used")
    raw_data = Column(JSONB, nullable=True, doc="Raw analysis data")
    
    # Indexes optimized for TimescaleDB
    __table_args__ = (
        Index("idx_trend_geography_time", "geography_name", "period_end"),
        Index("idx_trend_type_time", "property_type", "period_end"),
        Index("idx_trend_period_type", "period_type", "period_end"),
        Index("idx_trend_postcode_time", "postcode", "period_end"),
        Index("idx_trend_time_segment", "period_end", "market_segment"),
        CheckConstraint("period_start < period_end", name="chk_period_valid"),
        CheckConstraint("confidence_level >= 0 AND confidence_level <= 1", name="chk_confidence_valid"),
    )
    
    @validates("trend_direction")
    def validate_trend_direction(self, key: str, value: str) -> str:
        """Validate trend direction."""
        if value and value not in [td.value for td in TrendDirection]:
            raise ValueError(f"Invalid trend direction: {value}")
        return value
    
    @validates("market_segment")
    def validate_market_segment(self, key: str, value: str) -> str:
        """Validate market segment."""
        if value and value not in [ms.value for ms in MarketSegment]:
            raise ValueError(f"Invalid market segment: {value}")
        return value
    
    @hybrid_property
    def is_positive_trend(self) -> bool:
        """Check if trend is positive."""
        return self.trend_direction == TrendDirection.UP.value
    
    def __repr__(self) -> str:
        return f"<MarketTrend(id={self.id}, area='{self.geography_name}', period='{self.period_type}')>"


class SuburbStats(Base, TimestampMixin):
    """Comprehensive suburb statistics and analytics."""
    
    __tablename__ = "suburb_stats"
    
    # Geographic Information
    suburb_name = Column(String(100), nullable=False, index=True, doc="Suburb name")
    postcode = Column(String(10), nullable=False, index=True, doc="Postcode")
    lga = Column(String(100), nullable=True, doc="Local Government Area")
    
    # Time Period
    stats_date = Column(DateTime(timezone=True), nullable=False, doc="Statistics date")
    period_days = Column(Integer, default=30, doc="Analysis period in days")
    
    # Population & Demographics
    population = Column(Integer, nullable=True, doc="Suburb population")
    median_age = Column(Numeric(4, 1), nullable=True, doc="Median age")
    median_household_income = Column(Numeric(10, 2), nullable=True, doc="Median household income")
    
    # Property Market Overview
    total_properties = Column(Integer, nullable=True, doc="Total properties in suburb")
    active_listings = Column(Integer, nullable=True, doc="Current active listings")
    avg_time_on_market = Column(Numeric(5, 1), nullable=True, doc="Average time on market")
    
    # Price Statistics by Property Type
    house_median_price = Column(Numeric(12, 2), nullable=True, doc="House median price")
    house_price_growth_12m = Column(Numeric(5, 2), nullable=True, doc="House 12m price growth %")
    unit_median_price = Column(Numeric(12, 2), nullable=True, doc="Unit median price")
    unit_price_growth_12m = Column(Numeric(5, 2), nullable=True, doc="Unit 12m price growth %")
    
    # Market Activity
    sales_last_30d = Column(Integer, nullable=True, doc="Sales in last 30 days")
    sales_last_90d = Column(Integer, nullable=True, doc="Sales in last 90 days")
    listings_last_30d = Column(Integer, nullable=True, doc="New listings in last 30 days")
    turnover_rate = Column(Numeric(5, 2), nullable=True, doc="Annual property turnover rate")
    
    # Rental Market
    median_rent_weekly = Column(Numeric(8, 2), nullable=True, doc="Median weekly rent")
    rental_yield = Column(Numeric(4, 2), nullable=True, doc="Gross rental yield %")
    vacancy_rate = Column(Numeric(4, 2), nullable=True, doc="Rental vacancy rate %")
    
    # Price Ranges
    entry_price_house = Column(Numeric(12, 2), nullable=True, doc="Entry level house price")
    premium_price_house = Column(Numeric(12, 2), nullable=True, doc="Premium house price")
    entry_price_unit = Column(Numeric(12, 2), nullable=True, doc="Entry level unit price")
    premium_price_unit = Column(Numeric(12, 2), nullable=True, doc="Premium unit price")
    
    # Comparative Rankings
    price_rank_regional = Column(Integer, nullable=True, doc="Price rank in region")
    growth_rank_regional = Column(Integer, nullable=True, doc="Growth rank in region")
    demand_index = Column(Numeric(5, 2), nullable=True, doc="Demand index (0-100)")
    
    # Infrastructure & Amenities
    school_rating_avg = Column(Numeric(3, 1), nullable=True, doc="Average school rating")
    transport_score = Column(Integer, nullable=True, doc="Transport accessibility score")
    walkability_score = Column(Integer, nullable=True, doc="Walk score")
    cafe_restaurant_count = Column(Integer, nullable=True, doc="Cafes and restaurants")
    
    # Development Activity
    development_approvals_12m = Column(Integer, nullable=True, doc="Development approvals (12m)")
    construction_activity = Column(String(20), nullable=True, doc="Construction activity level")
    future_supply_risk = Column(String(20), nullable=True, doc="Future supply risk level")
    
    # Market Sentiment
    buyer_demand = Column(String(20), nullable=True, doc="Buyer demand level")
    seller_motivation = Column(String(20), nullable=True, doc="Seller motivation level")
    market_hotness = Column(Numeric(3, 1), nullable=True, doc="Market hotness score (1-10)")
    
    # Additional Metrics
    price_volatility = Column(Numeric(5, 2), nullable=True, doc="Price volatility index")
    seasonal_variation = Column(Numeric(5, 2), nullable=True, doc="Seasonal price variation")
    foreign_buyer_activity = Column(Numeric(4, 2), nullable=True, doc="Foreign buyer % of sales")
    
    # Metadata
    data_quality_score = Column(Numeric(3, 2), nullable=True, doc="Data quality score (0-1)")
    calculation_method = Column(String(100), nullable=False, doc="Calculation methodology")
    raw_metrics = Column(JSONB, nullable=True, doc="Raw metric data")
    
    # Indexes
    __table_args__ = (
        Index("idx_suburb_stats_name_date", "suburb_name", "stats_date"),
        Index("idx_suburb_stats_postcode_date", "postcode", "stats_date"),
        Index("idx_suburb_stats_date", "stats_date"),
        Index("idx_suburb_stats_price_growth", "house_price_growth_12m", "unit_price_growth_12m"),
    )
    
    @validates("buyer_demand", "seller_motivation", "construction_activity", "future_supply_risk")
    def validate_level_fields(self, key: str, value: str) -> str:
        """Validate level fields."""
        if value and value not in ["Low", "Medium", "High", "Very High"]:
            raise ValueError(f"Invalid {key}: {value}")
        return value
    
    def __repr__(self) -> str:
        return f"<SuburbStats(id={self.id}, suburb='{self.suburb_name}', date='{self.stats_date.date()}')>"


class PriceChange(Base, TimestampMixin):
    """Property price change tracking for TimescaleDB."""
    
    __tablename__ = "price_changes"
    
    # Foreign Keys
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False, index=True)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("property_listings.id"), nullable=True, index=True)
    
    # Price Change Details
    old_price = Column(Numeric(12, 2), nullable=False, doc="Previous price")
    new_price = Column(Numeric(12, 2), nullable=False, doc="New price")
    change_amount = Column(Numeric(12, 2), nullable=False, doc="Price change amount")
    change_percent = Column(Numeric(5, 2), nullable=False, doc="Price change percentage")
    
    # Change Context
    change_type = Column(String(20), nullable=False, doc="Change type (increase, decrease, initial)")
    change_reason = Column(String(100), nullable=True, doc="Reason for change")
    days_since_listing = Column(Integer, nullable=True, doc="Days since initial listing")
    days_since_last_change = Column(Integer, nullable=True, doc="Days since last price change")
    
    # Market Context
    suburb = Column(String(100), nullable=False, index=True, doc="Property suburb")
    property_type = Column(String(50), nullable=False, doc="Property type")
    bedrooms = Column(Integer, nullable=True, doc="Number of bedrooms")
    
    # Source Information
    source = Column(String(50), nullable=False, doc="Data source")
    detection_method = Column(String(50), nullable=False, doc="How change was detected")
    confidence_score = Column(Numeric(3, 2), nullable=True, doc="Detection confidence")
    
    # Additional Context
    market_activity = Column(String(20), nullable=True, doc="Market activity level")
    comparable_sales = Column(Integer, nullable=True, doc="Recent comparable sales")
    agent_feedback = Column(Text, nullable=True, doc="Agent feedback on change")
    
    # Metadata
    raw_data = Column(JSONB, nullable=True, doc="Raw change data")
    
    # Indexes optimized for TimescaleDB
    __table_args__ = (
        Index("idx_price_change_property_time", "property_id", "created_at"),
        Index("idx_price_change_suburb_time", "suburb", "created_at"),
        Index("idx_price_change_type_time", "change_type", "created_at"),
        Index("idx_price_change_amount", "change_amount", "created_at"),
        CheckConstraint("old_price > 0", name="chk_old_price_positive"),
        CheckConstraint("new_price > 0", name="chk_new_price_positive"),
    )
    
    @validates("change_type")
    def validate_change_type(self, key: str, value: str) -> str:
        """Validate change type."""
        valid_types = ["increase", "decrease", "initial", "withdrawn", "back_on_market"]
        if value not in valid_types:
            raise ValueError(f"Invalid change type: {value}")
        return value
    
    @hybrid_property
    def is_price_increase(self) -> bool:
        """Check if this is a price increase."""
        return self.new_price > self.old_price
    
    @hybrid_property
    def is_significant_change(self) -> bool:
        """Check if this is a significant price change (>5%)."""
        return abs(self.change_percent) >= 5.0
    
    def __repr__(self) -> str:
        return f"<PriceChange(id={self.id}, property_id={self.property_id}, change={self.change_percent}%)>"