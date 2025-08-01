"""
ReAgent Sydney - Property Models

SQLAlchemy models for property-related entities with TimescaleDB support.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text,
    Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PostgresUUID
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin, AuditMixin, SoftDeleteMixin


class Property(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """Main property listing model."""
    
    __tablename__ = "properties"
    
    # Basic Property Information
    listing_id = Column(String(100), unique=True, index=True, nullable=False, 
                       doc="External listing identifier")
    title = Column(String(500), nullable=False, doc="Property title")
    description = Column(Text, doc="Property description")
    property_type = Column(String(50), nullable=False, index=True,
                          doc="House, Unit, Townhouse, Villa, Duplex, etc.")
    
    # Location
    address_line_1 = Column(String(200), nullable=False, doc="Street address")
    address_line_2 = Column(String(200), doc="Additional address info")
    suburb = Column(String(100), nullable=False, index=True, doc="Suburb name")
    postcode = Column(String(10), nullable=False, index=True, doc="Postcode")
    state = Column(String(10), nullable=False, default="NSW", doc="State")
    country = Column(String(50), nullable=False, default="Australia", doc="Country")
    
    # Geographic Coordinates
    latitude = Column(Numeric(10, 8), doc="Latitude coordinate")
    longitude = Column(Numeric(11, 8), doc="Longitude coordinate")
    
    # Property Details
    bedrooms = Column(Integer, doc="Number of bedrooms")
    bathrooms = Column(Integer, doc="Number of bathrooms")
    car_spaces = Column(Integer, doc="Number of car spaces")
    land_size = Column(Integer, doc="Land size in square meters")
    building_size = Column(Integer, doc="Building size in square meters")
    
    # Pricing
    price = Column(Numeric(12, 2), doc="Current asking price")
    price_display = Column(String(100), doc="Price display text")
    auction_date = Column(DateTime(timezone=True), doc="Auction date if applicable")
    
    # Listing Status
    listing_status = Column(String(50), nullable=False, default="active", index=True,
                           doc="active, sold, withdrawn, off_market")
    listing_type = Column(String(50), nullable=False, 
                         doc="sale, rent, auction, expressions_of_interest")
    
    # External Source Information
    source = Column(String(50), nullable=False, index=True,
                   doc="domain, realestate, corelogic, manual")
    source_url = Column(String(500), doc="Original listing URL")
    source_data = Column(JSONB, doc="Raw data from source")
    
    # Features and Amenities
    features = Column(ARRAY(String), doc="Property features list")
    amenities = Column(JSONB, doc="Structured amenities data")
    
    # Media
    image_urls = Column(ARRAY(String), doc="Property image URLs")
    floorplan_urls = Column(ARRAY(String), doc="Floorplan image URLs")
    video_urls = Column(ARRAY(String), doc="Property video URLs")
    
    # Agent Information
    agent_id = Column(PostgresUUID(as_uuid=True), ForeignKey("agents.id"), 
                     doc="Primary agent ID")
    agency_id = Column(PostgresUUID(as_uuid=True), ForeignKey("agencies.id"),
                      doc="Agency ID")
    
    # Metadata
    first_listed_date = Column(DateTime(timezone=True), doc="First listing date")
    last_updated_source = Column(DateTime(timezone=True), doc="Last update from source")
    days_on_market = Column(Integer, doc="Days on market")
    
    # Search and Analytics
    search_keywords = Column(ARRAY(String), doc="Search optimization keywords")
    embedding_vector = Column(ARRAY(Numeric), doc="Property description embedding")
    
    # Relationships
    agent = relationship("Agent", back_populates="properties")
    agency = relationship("Agency", back_populates="properties")
    price_history = relationship("PropertyPriceHistory", back_populates="property",
                                cascade="all, delete-orphan")
    inspections = relationship("PropertyInspection", back_populates="property",
                              cascade="all, delete-orphan")
    market_metrics = relationship("PropertyMarketMetrics", back_populates="property",
                                 cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("price >= 0", name="positive_price"),
        CheckConstraint("bedrooms >= 0", name="positive_bedrooms"),
        CheckConstraint("bathrooms >= 0", name="positive_bathrooms"),
        CheckConstraint("car_spaces >= 0", name="positive_car_spaces"),
        CheckConstraint("land_size >= 0", name="positive_land_size"),
        CheckConstraint("building_size >= 0", name="positive_building_size"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="valid_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="valid_longitude"),
        CheckConstraint(
            "listing_status IN ('active', 'sold', 'withdrawn', 'off_market')",
            name="valid_listing_status"
        ),
        CheckConstraint(
            "listing_type IN ('sale', 'rent', 'auction', 'expressions_of_interest')",
            name="valid_listing_type"
        ),
        CheckConstraint(
            "source IN ('domain', 'realestate', 'corelogic', 'manual')",
            name="valid_source"
        ),
        Index("idx_properties_location", suburb, postcode),
        Index("idx_properties_price_range", "price"),
        Index("idx_properties_property_type_status", property_type, listing_status),
        Index("idx_properties_coordinates", latitude, longitude),
        Index("idx_properties_source_updated", source, "last_updated_source"),
    )


class PropertyPriceHistory(Base, TimestampMixin):
    """Property price change history - TimescaleDB hypertable."""
    
    __tablename__ = "property_price_history"
    
    property_id = Column(PostgresUUID(as_uuid=True), ForeignKey("properties.id"),
                        nullable=False, doc="Property reference")
    price = Column(Numeric(12, 2), nullable=False, doc="Price at this point")
    price_display = Column(String(100), doc="Price display text")
    price_type = Column(String(50), nullable=False, 
                       doc="asking, sold, auction_result, price_drop")
    
    # Change Information
    previous_price = Column(Numeric(12, 2), doc="Previous price")
    price_change = Column(Numeric(12, 2), doc="Price change amount")
    price_change_percent = Column(Numeric(5, 2), doc="Price change percentage")
    
    # Source and Context
    source = Column(String(50), nullable=False, doc="Source of price update")
    event_type = Column(String(50), nullable=False, 
                       doc="listing, update, sale, auction, withdrawal")
    notes = Column(Text, doc="Additional notes about price change")
    
    # Relationship
    property = relationship("Property", back_populates="price_history")
    
    __table_args__ = (
        Index("idx_price_history_property_time", property_id, "created_at"),
        Index("idx_price_history_price_type", price_type, "created_at"),
        CheckConstraint("price >= 0", name="positive_price"),
        CheckConstraint(
            "price_type IN ('asking', 'sold', 'auction_result', 'price_drop')",
            name="valid_price_type"
        ),
        CheckConstraint(
            "event_type IN ('listing', 'update', 'sale', 'auction', 'withdrawal')",
            name="valid_event_type"
        ),
    )


class PropertyInspection(Base, TimestampMixin):
    """Property inspection times."""
    
    __tablename__ = "property_inspections"
    
    property_id = Column(PostgresUUID(as_uuid=True), ForeignKey("properties.id"),
                        nullable=False, doc="Property reference")
    
    inspection_start = Column(DateTime(timezone=True), nullable=False,
                             doc="Inspection start time")
    inspection_end = Column(DateTime(timezone=True), nullable=False,
                           doc="Inspection end time")
    
    inspection_type = Column(String(50), nullable=False, default="open_house",
                            doc="open_house, private, auction")
    status = Column(String(50), nullable=False, default="scheduled",
                   doc="scheduled, completed, cancelled")
    
    # Additional Details
    notes = Column(Text, doc="Inspection notes")
    attendance_estimate = Column(Integer, doc="Estimated number of attendees")
    
    # Relationship
    property = relationship("Property", back_populates="inspections")
    
    __table_args__ = (
        Index("idx_inspections_property_date", property_id, inspection_start),
        CheckConstraint("inspection_end > inspection_start", name="valid_inspection_times"),
        CheckConstraint(
            "inspection_type IN ('open_house', 'private', 'auction')",
            name="valid_inspection_type"
        ),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="valid_status"
        ),
    )


class PropertyMarketMetrics(Base, TimestampMixin):
    """Property market performance metrics - TimescaleDB hypertable."""
    
    __tablename__ = "property_market_metrics"
    
    property_id = Column(PostgresUUID(as_uuid=True), ForeignKey("properties.id"),
                        nullable=False, doc="Property reference")
    
    # View and Engagement Metrics
    view_count = Column(Integer, default=0, doc="Total views")
    daily_views = Column(Integer, default=0, doc="Views in last 24 hours")
    weekly_views = Column(Integer, default=0, doc="Views in last 7 days")
    
    # Interest Metrics
    enquiry_count = Column(Integer, default=0, doc="Number of enquiries")
    inspection_requests = Column(Integer, default=0, doc="Inspection requests")
    favorite_count = Column(Integer, default=0, doc="Times favorited/saved")
    
    # Market Position
    days_on_market = Column(Integer, doc="Days since first listed")
    price_per_sqm = Column(Numeric(8, 2), doc="Price per square meter")
    suburb_price_percentile = Column(Numeric(5, 2), doc="Price percentile in suburb")
    
    # Predictive Metrics
    estimated_sale_price = Column(Numeric(12, 2), doc="AI predicted sale price")
    sale_probability = Column(Numeric(5, 4), doc="Probability of sale this month")
    time_to_sell_estimate = Column(Integer, doc="Estimated days to sell")
    
    # Search Performance
    search_ranking_avg = Column(Numeric(5, 2), doc="Average search ranking position")
    keyword_performance = Column(JSONB, doc="Keyword search performance data")
    
    # Relationship
    property = relationship("Property", back_populates="market_metrics")
    
    __table_args__ = (
        Index("idx_market_metrics_property_time", property_id, "created_at"),
        Index("idx_market_metrics_performance", "sale_probability", "created_at"),
        CheckConstraint("view_count >= 0", name="positive_view_count"),
        CheckConstraint("enquiry_count >= 0", name="positive_enquiry_count"),
        CheckConstraint("days_on_market >= 0", name="positive_days_on_market"),
        CheckConstraint("sale_probability BETWEEN 0 AND 1", name="valid_sale_probability"),
    )


class Agent(Base, TimestampMixin, SoftDeleteMixin):
    """Real estate agent information."""
    
    __tablename__ = "agents"
    
    # Basic Information
    first_name = Column(String(100), nullable=False, doc="Agent first name")
    last_name = Column(String(100), nullable=False, doc="Agent last name")
    display_name = Column(String(200), doc="Public display name")
    
    # Contact Information
    phone = Column(String(50), doc="Primary phone number")
    mobile = Column(String(50), doc="Mobile number")
    email = Column(String(255), doc="Email address")
    
    # Professional Details
    license_number = Column(String(100), doc="Real estate license number")
    agency_id = Column(PostgresUUID(as_uuid=True), ForeignKey("agencies.id"),
                      doc="Agency reference")
    position = Column(String(100), doc="Position/title at agency")
    
    # Specializations and Areas
    specializations = Column(ARRAY(String), doc="Property type specializations")
    service_areas = Column(ARRAY(String), doc="Suburbs/areas serviced")
    languages = Column(ARRAY(String), doc="Languages spoken")
    
    # Profile and Marketing
    bio = Column(Text, doc="Agent biography")
    profile_image_url = Column(String(500), doc="Profile image URL")
    social_media = Column(JSONB, doc="Social media profiles")
    
    # Performance Metrics
    total_sales = Column(Integer, default=0, doc="Total properties sold")
    sales_volume = Column(Numeric(15, 2), default=0, doc="Total sales volume")
    average_days_to_sell = Column(Numeric(5, 1), doc="Average days to sell")
    
    # Source Information
    source = Column(String(50), nullable=False, doc="Data source")
    source_agent_id = Column(String(100), doc="External agent ID")
    source_profile_url = Column(String(500), doc="External profile URL")
    
    # Relationships
    agency = relationship("Agency", back_populates="agents")
    properties = relationship("Property", back_populates="agent")
    
    @property
    def full_name(self) -> str:
        """Get agent's full name."""
        return f"{self.first_name} {self.last_name}"
    
    __table_args__ = (
        Index("idx_agents_name", first_name, last_name),
        Index("idx_agents_agency", agency_id),
        Index("idx_agents_source", source, source_agent_id),
        UniqueConstraint("source", "source_agent_id", name="unique_source_agent"),
    )


class Agency(Base, TimestampMixin, SoftDeleteMixin):
    """Real estate agency information."""
    
    __tablename__ = "agencies"
    
    # Basic Information
    name = Column(String(200), nullable=False, doc="Agency name")
    display_name = Column(String(200), doc="Public display name")
    abn = Column(String(20), doc="Australian Business Number")
    license_number = Column(String(100), doc="Agency license number")
    
    # Contact Information
    phone = Column(String(50), doc="Primary phone number")
    email = Column(String(255), doc="Primary email address")
    website = Column(String(500), doc="Agency website")
    
    # Address
    address_line_1 = Column(String(200), doc="Street address")
    address_line_2 = Column(String(200), doc="Additional address info")
    suburb = Column(String(100), doc="Suburb")
    postcode = Column(String(10), doc="Postcode")
    state = Column(String(10), default="NSW", doc="State")
    
    # Profile
    description = Column(Text, doc="Agency description")
    logo_url = Column(String(500), doc="Agency logo URL")
    
    # Service Areas
    service_areas = Column(ARRAY(String), doc="Primary service areas")
    
    # Performance
    total_agents = Column(Integer, default=0, doc="Number of agents")
    total_listings = Column(Integer, default=0, doc="Current active listings")
    
    # Source Information
    source = Column(String(50), nullable=False, doc="Data source")
    source_agency_id = Column(String(100), doc="External agency ID")
    source_profile_url = Column(String(500), doc="External profile URL")
    
    # Relationships
    agents = relationship("Agent", back_populates="agency")
    properties = relationship("Property", back_populates="agency")
    
    __table_args__ = (
        Index("idx_agencies_name", name),
        Index("idx_agencies_location", suburb, postcode),
        Index("idx_agencies_source", source, source_agency_id),
        UniqueConstraint("source", "source_agency_id", name="unique_source_agency"),
    )