"""
ReAgent Sydney - Buyer Models

SQLAlchemy models for buyer profiles, preferences, and matching data.
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


class Buyer(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """Buyer profile and contact information."""
    
    __tablename__ = "buyers"
    
    # Personal Information
    first_name = Column(String(100), nullable=False, doc="Buyer first name")
    last_name = Column(String(100), nullable=False, doc="Buyer last name")
    display_name = Column(String(200), doc="Preferred display name")
    
    # Contact Information
    email = Column(String(255), unique=True, nullable=False, index=True,
                  doc="Primary email address")
    phone = Column(String(50), doc="Primary phone number")
    mobile = Column(String(50), doc="Mobile number")
    
    # Status and Lifecycle
    status = Column(String(50), nullable=False, default="active", index=True,
                   doc="active, inactive, paused, converted")
    buyer_type = Column(String(50), nullable=False, default="individual",
                       doc="individual, investor, first_home_buyer, upgrader")
    
    # Financial Information
    pre_approval_status = Column(String(50), default="unknown",
                               doc="pre_approved, conditional, not_approved, unknown")
    pre_approval_amount = Column(Numeric(12, 2), doc="Pre-approved loan amount")
    deposit_available = Column(Numeric(12, 2), doc="Available deposit amount")
    
    # Timeline and Urgency
    buying_urgency = Column(String(50), default="medium",
                          doc="low, medium, high, urgent")
    target_settlement_date = Column(DateTime(timezone=True),
                                  doc="Preferred settlement date")
    first_contact_date = Column(DateTime(timezone=True),
                              doc="Date of first contact")
    
    # Additional Information
    current_situation = Column(String(100),
                             doc="renting, living_with_family, owned_property, etc.")
    notes = Column(Text, doc="Additional notes about buyer")
    
    # Source and Attribution
    source = Column(String(100), doc="Lead source")
    referral_agent_id = Column(PostgresUUID(as_uuid=True), 
                              ForeignKey("agents.id"),
                              doc="Referring agent if applicable")
    
    # Marketing Preferences
    marketing_consent = Column(Boolean, default=True,
                             doc="Consent to receive marketing communications")
    preferred_contact_method = Column(String(50), default="email",
                                    doc="email, phone, sms, any")
    communication_frequency = Column(String(50), default="weekly",
                                   doc="daily, weekly, monthly")
    
    # Relationships
    preferences = relationship("BuyerPreferences", back_populates="buyer",
                             uselist=False, cascade="all, delete-orphan")
    property_matches = relationship("PropertyMatch", back_populates="buyer",
                                  cascade="all, delete-orphan")
    search_history = relationship("BuyerSearchHistory", back_populates="buyer",
                                cascade="all, delete-orphan")
    property_interactions = relationship("PropertyInteraction", back_populates="buyer",
                                       cascade="all, delete-orphan")
    
    @property
    def full_name(self) -> str:
        """Get buyer's full name."""
        return f"{self.first_name} {self.last_name}"
    
    __table_args__ = (
        Index("idx_buyers_name", first_name, last_name),
        Index("idx_buyers_status_type", status, buyer_type),
        Index("idx_buyers_urgency", buying_urgency, "created_at"),
        CheckConstraint(
            "status IN ('active', 'inactive', 'paused', 'converted')",
            name="valid_status"
        ),
        CheckConstraint(
            "buyer_type IN ('individual', 'investor', 'first_home_buyer', 'upgrader')",
            name="valid_buyer_type"
        ),
        CheckConstraint(
            "pre_approval_status IN ('pre_approved', 'conditional', 'not_approved', 'unknown')",
            name="valid_pre_approval_status"
        ),
        CheckConstraint(
            "buying_urgency IN ('low', 'medium', 'high', 'urgent')",
            name="valid_buying_urgency"
        ),
        CheckConstraint(
            "preferred_contact_method IN ('email', 'phone', 'sms', 'any')",
            name="valid_contact_method"
        ),
        CheckConstraint("pre_approval_amount >= 0", name="positive_pre_approval_amount"),
        CheckConstraint("deposit_available >= 0", name="positive_deposit_available"),
    )


class BuyerPreferences(Base, TimestampMixin):
    """Buyer property preferences and search criteria."""
    
    __tablename__ = "buyer_preferences"
    
    buyer_id = Column(PostgresUUID(as_uuid=True), ForeignKey("buyers.id"),
                     nullable=False, unique=True, doc="Buyer reference")
    
    # Property Type Preferences
    property_types = Column(ARRAY(String), nullable=False,
                          doc="Preferred property types")
    
    # Location Preferences
    preferred_suburbs = Column(ARRAY(String), doc="Preferred suburbs list")
    excluded_suburbs = Column(ARRAY(String), doc="Suburbs to exclude")
    preferred_postcodes = Column(ARRAY(String), doc="Preferred postcodes")
    max_commute_time = Column(Integer, doc="Maximum commute time in minutes")
    commute_destinations = Column(JSONB, doc="Work/school locations with transport preferences")
    
    # Budget Constraints
    min_price = Column(Numeric(12, 2), doc="Minimum price range")
    max_price = Column(Numeric(12, 2), nullable=False, doc="Maximum price range")
    budget_flexibility = Column(Numeric(5, 2), default=0.1,
                              doc="Budget flexibility as percentage (0.1 = 10%)")
    
    # Property Features
    min_bedrooms = Column(Integer, doc="Minimum number of bedrooms")
    max_bedrooms = Column(Integer, doc="Maximum number of bedrooms")
    min_bathrooms = Column(Integer, doc="Minimum number of bathrooms")
    min_car_spaces = Column(Integer, doc="Minimum parking spaces")
    
    # Size Requirements
    min_land_size = Column(Integer, doc="Minimum land size in sqm")
    min_building_size = Column(Integer, doc="Minimum building size in sqm")
    
    # Must-Have Features
    required_features = Column(ARRAY(String), doc="Required property features")
    preferred_features = Column(ARRAY(String), doc="Nice-to-have features")
    excluded_features = Column(ARRAY(String), doc="Features to avoid")
    
    # Lifestyle Preferences
    lifestyle_preferences = Column(JSONB, doc="Lifestyle and amenity preferences")
    school_preferences = Column(JSONB, doc="School catchment and rating preferences")
    
    # Investment Specific (if applicable)
    rental_yield_target = Column(Numeric(5, 2), doc="Target rental yield percentage")
    capital_growth_expectation = Column(String(50), doc="Expected capital growth rate")
    
    # Search Behavior
    alert_frequency = Column(String(50), default="daily",
                           doc="How often to send property alerts")
    auto_match_enabled = Column(Boolean, default=True,
                              doc="Enable automatic property matching")
    
    # Relationship
    buyer = relationship("Buyer", back_populates="preferences")
    
    __table_args__ = (
        Index("idx_buyer_preferences_price_range", min_price, max_price),
        Index("idx_buyer_preferences_property_types", "property_types"),
        CheckConstraint("max_price > 0", name="positive_max_price"),
        CheckConstraint("min_price IS NULL OR min_price >= 0", name="positive_min_price"),
        CheckConstraint("min_price IS NULL OR min_price <= max_price", name="valid_price_range"),
        CheckConstraint("min_bedrooms IS NULL OR min_bedrooms >= 0", name="positive_min_bedrooms"),
        CheckConstraint("max_bedrooms IS NULL OR max_bedrooms >= 0", name="positive_max_bedrooms"),
        CheckConstraint(
            "min_bedrooms IS NULL OR max_bedrooms IS NULL OR min_bedrooms <= max_bedrooms",
            name="valid_bedroom_range"
        ),
        CheckConstraint("budget_flexibility BETWEEN 0 AND 1", name="valid_budget_flexibility"),
        CheckConstraint(
            "alert_frequency IN ('immediate', 'daily', 'weekly', 'monthly')",
            name="valid_alert_frequency"
        ),
    )


class PropertyMatch(Base, TimestampMixin):
    """AI-generated property matches for buyers."""
    
    __tablename__ = "property_matches"
    
    buyer_id = Column(PostgresUUID(as_uuid=True), ForeignKey("buyers.id"),
                     nullable=False, doc="Buyer reference")
    property_id = Column(PostgresUUID(as_uuid=True), ForeignKey("properties.id"),
                        nullable=False, doc="Property reference")
    
    # Match Quality
    match_score = Column(Numeric(5, 4), nullable=False,
                        doc="AI confidence score (0-1)")
    match_rank = Column(Integer, doc="Ranking among all matches for this buyer")
    
    # Match Reasoning
    match_reasons = Column(ARRAY(String), doc="Key reasons for the match")
    match_concerns = Column(ARRAY(String), doc="Potential concerns or drawbacks")
    match_explanation = Column(Text, doc="Detailed explanation of the match")
    
    # Status and Actions
    status = Column(String(50), nullable=False, default="new",
                   doc="new, viewed, interested, not_interested, contacted")
    buyer_feedback = Column(String(50), doc="Buyer's feedback on the match")
    agent_notes = Column(Text, doc="Agent notes about this match")
    
    # Interaction Tracking
    first_presented_date = Column(DateTime(timezone=True), nullable=False,
                                doc="When match was first presented to buyer")
    last_interaction_date = Column(DateTime(timezone=True),
                                 doc="Last buyer interaction with this match")
    interaction_count = Column(Integer, default=0,
                             doc="Number of buyer interactions")
    
    # Pricing Analysis
    price_assessment = Column(String(50),
                            doc="underpriced, fairly_priced, overpriced, unknown")
    estimated_value = Column(Numeric(12, 2), doc="AI estimated property value")
    
    # Relationships
    buyer = relationship("Buyer", back_populates="property_matches")
    property = relationship("Property")
    
    __table_args__ = (
        Index("idx_property_matches_buyer_score", buyer_id, match_score.desc()),
        Index("idx_property_matches_property", property_id),
        Index("idx_property_matches_status", status, "created_at"),
        UniqueConstraint("buyer_id", "property_id", name="unique_buyer_property_match"),
        CheckConstraint("match_score BETWEEN 0 AND 1", name="valid_match_score"),
        CheckConstraint("match_rank > 0", name="positive_match_rank"),
        CheckConstraint("interaction_count >= 0", name="positive_interaction_count"),
        CheckConstraint(
            "status IN ('new', 'viewed', 'interested', 'not_interested', 'contacted')",
            name="valid_status"
        ),
        CheckConstraint(
            "price_assessment IN ('underpriced', 'fairly_priced', 'overpriced', 'unknown')",
            name="valid_price_assessment"
        ),
    )


class BuyerSearchHistory(Base, TimestampMixin):
    """Buyer search history and behavior tracking."""
    
    __tablename__ = "buyer_search_history"
    
    buyer_id = Column(PostgresUUID(as_uuid=True), ForeignKey("buyers.id"),
                     nullable=False, doc="Buyer reference")
    
    # Search Parameters
    search_query = Column(String(500), doc="Text search query")
    search_filters = Column(JSONB, nullable=False, doc="Applied search filters")
    search_type = Column(String(50), nullable=False, default="browse",
                        doc="browse, targeted, saved_search, alert")
    
    # Results and Engagement
    results_count = Column(Integer, nullable=False, doc="Number of results returned")
    results_viewed = Column(Integer, default=0, doc="Number of results clicked")
    session_duration = Column(Integer, doc="Search session duration in seconds")
    
    # Geographic Focus
    searched_suburbs = Column(ARRAY(String), doc="Suburbs included in search")
    searched_postcodes = Column(ARRAY(String), doc="Postcodes searched")
    
    # Search Metadata
    device_type = Column(String(50), doc="desktop, mobile, tablet")
    user_agent = Column(String(500), doc="Browser user agent")
    ip_address = Column(String(45), doc="IP address (for analytics)")
    
    # Relationship
    buyer = relationship("Buyer", back_populates="search_history")
    
    __table_args__ = (
        Index("idx_search_history_buyer_time", buyer_id, "created_at"),
        Index("idx_search_history_type", search_type, "created_at"),
        CheckConstraint("results_count >= 0", name="positive_results_count"),
        CheckConstraint("results_viewed >= 0", name="positive_results_viewed"),
        CheckConstraint("results_viewed <= results_count", name="viewed_within_results"),
        CheckConstraint("session_duration >= 0", name="positive_session_duration"),
        CheckConstraint(
            "search_type IN ('browse', 'targeted', 'saved_search', 'alert')",
            name="valid_search_type"
        ),
    )


class PropertyInteraction(Base, TimestampMixin):
    """Buyer interactions with specific properties."""
    
    __tablename__ = "property_interactions"
    
    buyer_id = Column(PostgresUUID(as_uuid=True), ForeignKey("buyers.id"),
                     nullable=False, doc="Buyer reference")
    property_id = Column(PostgresUUID(as_uuid=True), ForeignKey("properties.id"),
                        nullable=False, doc="Property reference")
    
    # Interaction Details
    interaction_type = Column(String(50), nullable=False,
                            doc="view, favorite, enquiry, inspection_booking, phone_call")
    interaction_source = Column(String(50), doc="website, email, app, agent")
    interaction_duration = Column(Integer, doc="Duration in seconds")
    
    # Context
    referrer_url = Column(String(500), doc="How buyer arrived at property")
    device_type = Column(String(50), doc="Device used for interaction")
    
    # Engagement Metrics
    page_views = Column(Integer, default=1, doc="Number of property page views")
    image_views = Column(Integer, default=0, doc="Number of images viewed")
    floorplan_views = Column(Integer, default=0, doc="Number of floorplan views")
    video_views = Column(Integer, default=0, doc="Number of videos watched")
    
    # Interest Level
    interest_level = Column(String(50), doc="low, medium, high, very_high")
    interest_notes = Column(Text, doc="Notes about buyer's interest")
    
    # Follow-up
    follow_up_required = Column(Boolean, default=False,
                              doc="Whether follow-up is needed")
    follow_up_notes = Column(Text, doc="Follow-up action notes")
    
    # Relationships
    buyer = relationship("Buyer", back_populates="property_interactions")
    property = relationship("Property")
    
    __table_args__ = (
        Index("idx_property_interactions_buyer_time", buyer_id, "created_at"),
        Index("idx_property_interactions_property", property_id, "created_at"),
        Index("idx_property_interactions_type", interaction_type, "created_at"),
        CheckConstraint("interaction_duration >= 0", name="positive_interaction_duration"),
        CheckConstraint("page_views >= 0", name="positive_page_views"),
        CheckConstraint("image_views >= 0", name="positive_image_views"),
        CheckConstraint("floorplan_views >= 0", name="positive_floorplan_views"),
        CheckConstraint("video_views >= 0", name="positive_video_views"),
        CheckConstraint(
            "interaction_type IN ('view', 'favorite', 'enquiry', 'inspection_booking', 'phone_call')",
            name="valid_interaction_type"
        ),
        CheckConstraint(
            "interest_level IN ('low', 'medium', 'high', 'very_high')",
            name="valid_interest_level"
        ),
    )


class BuyerSegment(Base, TimestampMixin):
    """Buyer segmentation for targeted marketing and analysis."""
    
    __tablename__ = "buyer_segments"
    
    # Segment Definition
    name = Column(String(100), unique=True, nullable=False, doc="Segment name")
    description = Column(Text, doc="Segment description")
    
    # Segment Criteria
    criteria = Column(JSONB, nullable=False, doc="Segmentation criteria")
    sql_filter = Column(Text, doc="SQL filter for dynamic segmentation")
    
    # Segment Metadata
    is_active = Column(Boolean, default=True, doc="Whether segment is active")
    segment_type = Column(String(50), nullable=False, default="behavioral",
                         doc="behavioral, demographic, psychographic, value_based")
    
    # Performance Metrics
    member_count = Column(Integer, default=0, doc="Current number of members")
    conversion_rate = Column(Numeric(5, 4), doc="Segment conversion rate")
    avg_transaction_value = Column(Numeric(12, 2), doc="Average transaction value")
    
    # Relationships
    segment_memberships = relationship("BuyerSegmentMembership", back_populates="segment",
                                     cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_buyer_segments_type", segment_type),
        Index("idx_buyer_segments_active", is_active, "created_at"),
        CheckConstraint("member_count >= 0", name="positive_member_count"),
        CheckConstraint("conversion_rate BETWEEN 0 AND 1", name="valid_conversion_rate"),
        CheckConstraint("avg_transaction_value >= 0", name="positive_avg_transaction_value"),
        CheckConstraint(
            "segment_type IN ('behavioral', 'demographic', 'psychographic', 'value_based')",
            name="valid_segment_type"
        ),
    )


class BuyerSegmentMembership(Base, TimestampMixin):
    """Buyer membership in segments."""
    
    __tablename__ = "buyer_segment_memberships"
    
    buyer_id = Column(PostgresUUID(as_uuid=True), ForeignKey("buyers.id"),
                     nullable=False, doc="Buyer reference")
    segment_id = Column(PostgresUUID(as_uuid=True), ForeignKey("buyer_segments.id"),
                       nullable=False, doc="Segment reference")
    
    # Membership Details
    membership_score = Column(Numeric(5, 4), doc="Membership strength score (0-1)")
    membership_reason = Column(Text, doc="Why buyer belongs to this segment")
    
    # Status
    is_active = Column(Boolean, default=True, doc="Active membership")
    exit_date = Column(DateTime(timezone=True), doc="When buyer left segment")
    exit_reason = Column(String(200), doc="Reason for leaving segment")
    
    # Relationships
    buyer = relationship("Buyer")
    segment = relationship("BuyerSegment", back_populates="segment_memberships")
    
    __table_args__ = (
        Index("idx_segment_memberships_buyer", buyer_id),
        Index("idx_segment_memberships_segment", segment_id, is_active),
        UniqueConstraint("buyer_id", "segment_id", name="unique_buyer_segment"),
        CheckConstraint("membership_score BETWEEN 0 AND 1", name="valid_membership_score"),
    )