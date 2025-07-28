"""
ReAgent Sydney - Off-Market Radar Data Models

Data structures for representing off-market opportunities and related entities.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
from uuid import uuid4

from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, Numeric, DateTime, Integer, Boolean, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID as PostgresUUID
from sqlalchemy.orm import relationship

from ...data.models.base import Base, TimestampMixin, AuditMixin


class OpportunityType(str, Enum):
    """Types of off-market opportunities."""
    EXPIRED_LISTING = "expired_listing"
    COUNCIL_DA = "council_da"
    DISTRESS_SIGNAL = "distress_signal"
    MARKET_ANOMALY = "market_anomaly"
    OWNER_MOTIVATION = "owner_motivation"
    DEVELOPMENT_OPPORTUNITY = "development_opportunity"
    PRICE_REDUCTION = "price_reduction"
    TIME_ON_MARKET = "time_on_market"


class OpportunityStatus(str, Enum):
    """Status of off-market opportunities."""
    ACTIVE = "active"
    UNDER_INVESTIGATION = "under_investigation"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    EXPIRED = "expired"
    COMPLETED = "completed"
    INVALID = "invalid"


class DistressSignalType(str, Enum):
    """Types of distress signals."""
    FINANCIAL_PRESSURE = "financial_pressure"
    LEGAL_ISSUE = "legal_issue"
    OWNERSHIP_CHANGE = "ownership_change"
    PRICE_DROP_PATTERN = "price_drop_pattern"
    EXTENDED_MARKET_TIME = "extended_market_time"
    AUCTION_FAILURE = "auction_failure"
    REPEATED_LISTING = "repeated_listing"


class CouncilDAStatus(str, Enum):
    """Council Development Application status."""
    LODGED = "lodged"
    UNDER_ASSESSMENT = "under_assessment"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    APPEALED = "appealed"


@dataclass
class OpportunityScore:
    """Scoring system for opportunities."""
    
    overall_score: float = field(default=0.0)
    roi_potential: float = field(default=0.0)
    acquisition_difficulty: float = field(default=0.0)
    time_sensitivity: float = field(default=0.0)
    market_conditions: float = field(default=0.0)
    
    # Component scores
    price_attractiveness: float = field(default=0.0)
    location_desirability: float = field(default=0.0)
    property_condition: float = field(default=0.0)
    seller_motivation: float = field(default=0.0)
    
    # Risk factors
    legal_risk: float = field(default=0.0)
    market_risk: float = field(default=0.0)
    execution_risk: float = field(default=0.0)
    
    @property
    def priority_score(self) -> float:
        """Calculate priority score (0-1) combining all factors."""
        return min(1.0, max(0.0, (
            self.overall_score * 0.4 +
            self.roi_potential * 0.3 +
            self.time_sensitivity * 0.2 +
            (1 - self.acquisition_difficulty) * 0.1
        )))


@dataclass
class OffMarketOpportunity:
    """Represents an off-market real estate opportunity."""
    
    # Identity
    id: str = field(default_factory=lambda: str(uuid4()))
    opportunity_type: OpportunityType = field(default=OpportunityType.EXPIRED_LISTING)
    status: OpportunityStatus = field(default=OpportunityStatus.ACTIVE)
    
    # Property Information
    property_id: Optional[str] = None
    listing_id: Optional[str] = None
    address: str = ""
    suburb: str = ""
    postcode: str = ""
    property_type: str = ""
    
    # Property Details
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    car_spaces: Optional[int] = None
    land_size: Optional[int] = None
    
    # Financial Information
    current_price: Optional[Decimal] = None
    estimated_market_value: Optional[Decimal] = None
    potential_purchase_price: Optional[Decimal] = None
    estimated_roi_percent: Optional[float] = None
    
    # Opportunity Details
    title: str = ""
    description: str = ""
    opportunity_details: Dict[str, Any] = field(default_factory=dict)
    
    # Scoring
    scoring: OpportunityScore = field(default_factory=OpportunityScore)
    priority_score: float = field(default=0.0)
    
    # Timeline
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    estimated_timeline_days: Optional[int] = None
    
    # Source and Evidence
    data_sources: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence_level: float = field(default=0.0)
    
    # Contact Information
    agent_contact: Optional[Dict[str, str]] = None
    owner_contact: Optional[Dict[str, str]] = None
    
    # Compliance and Ethics
    compliance_checked: bool = False
    ethical_approval: bool = False
    data_privacy_compliant: bool = False
    
    # Internal Tracking
    investigation_notes: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.priority_score == 0.0:
            self.priority_score = self.scoring.priority_score
    
    def add_investigation_note(self, note: str, author: str = "system") -> None:
        """Add an investigation note."""
        timestamp = datetime.utcnow().isoformat()
        self.investigation_notes.append(f"[{timestamp}] [{author}] {note}")
    
    def add_action_item(self, action: str) -> None:
        """Add an action item."""
        if action not in self.action_items:
            self.action_items.append(action)
    
    def update_status(self, new_status: OpportunityStatus, note: str = "") -> None:
        """Update opportunity status with optional note."""
        old_status = self.status
        self.status = new_status
        
        status_note = f"Status changed from {old_status.value} to {new_status.value}"
        if note:
            status_note += f": {note}"
        
        self.add_investigation_note(status_note)
    
    def is_high_priority(self) -> bool:
        """Check if this is a high-priority opportunity."""
        return self.priority_score > 0.8
    
    def is_time_sensitive(self) -> bool:
        """Check if this opportunity is time-sensitive."""
        if self.expires_at:
            return (self.expires_at - datetime.utcnow()).days <= 7
        return self.scoring.time_sensitivity > 0.7
    
    def get_estimated_profit(self) -> Optional[Decimal]:
        """Calculate estimated profit if purchase and market prices are available."""
        if self.potential_purchase_price and self.estimated_market_value:
            return self.estimated_market_value - self.potential_purchase_price
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "opportunity_type": self.opportunity_type.value,
            "status": self.status.value,
            "property_id": self.property_id,
            "address": self.address,
            "suburb": self.suburb,
            "postcode": self.postcode,
            "title": self.title,
            "description": self.description,
            "priority_score": self.priority_score,
            "current_price": float(self.current_price) if self.current_price else None,
            "estimated_market_value": float(self.estimated_market_value) if self.estimated_market_value else None,
            "potential_purchase_price": float(self.potential_purchase_price) if self.potential_purchase_price else None,
            "estimated_roi_percent": self.estimated_roi_percent,
            "discovered_at": self.discovered_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "confidence_level": self.confidence_level,
            "data_sources": self.data_sources,
            "tags": self.tags,
            "scoring": {
                "overall_score": self.scoring.overall_score,
                "roi_potential": self.scoring.roi_potential,
                "time_sensitivity": self.scoring.time_sensitivity,
                "priority_score": self.scoring.priority_score
            }
        }


class OffMarketOpportunityDB(Base, TimestampMixin, AuditMixin):
    """Database model for off-market opportunities."""
    
    __tablename__ = "off_market_opportunities"
    
    # Basic Information
    opportunity_id = Column(String(100), unique=True, index=True, nullable=False)
    opportunity_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="active", index=True)
    
    # Property Reference
    property_id = Column(PostgresUUID(as_uuid=True), ForeignKey("properties.id"))
    listing_id = Column(String(100))
    
    # Location
    address = Column(String(500))
    suburb = Column(String(100), nullable=False, index=True)
    postcode = Column(String(10), nullable=False, index=True)
    property_type = Column(String(50))
    
    # Financial Data
    current_price = Column(Numeric(12, 2))
    estimated_market_value = Column(Numeric(12, 2))
    potential_purchase_price = Column(Numeric(12, 2))
    estimated_roi_percent = Column(Numeric(5, 2))
    
    # Opportunity Details
    title = Column(String(500))
    description = Column(Text)
    opportunity_details = Column(JSONB)
    
    # Scoring
    priority_score = Column(Numeric(3, 2), nullable=False, default=0.0)
    overall_score = Column(Numeric(3, 2), default=0.0)
    roi_potential = Column(Numeric(3, 2), default=0.0)
    time_sensitivity = Column(Numeric(3, 2), default=0.0)
    confidence_level = Column(Numeric(3, 2), default=0.0)
    
    # Timeline
    discovered_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))
    estimated_timeline_days = Column(Integer)
    
    # Source and Evidence
    data_sources = Column(ARRAY(String))
    evidence = Column(JSONB)
    
    # Contact Information
    agent_contact = Column(JSONB)
    owner_contact = Column(JSONB)
    
    # Compliance
    compliance_checked = Column(Boolean, default=False)
    ethical_approval = Column(Boolean, default=False)
    data_privacy_compliant = Column(Boolean, default=False)
    
    # Tracking
    investigation_notes = Column(ARRAY(String))
    action_items = Column(ARRAY(String))
    tags = Column(ARRAY(String))
    
    # Relationships
    property = relationship("Property", back_populates="off_market_opportunities")
    
    __table_args__ = (
        Index("idx_opportunities_type_status", opportunity_type, status),
        Index("idx_opportunities_priority", priority_score, "created_at"),
        Index("idx_opportunities_location", suburb, postcode),
        Index("idx_opportunities_timeline", expires_at, "created_at"),
        Index("idx_opportunities_discovered", "discovered_at"),
    )


class CouncilDARecord(Base, TimestampMixin):
    """Council Development Application records."""
    
    __tablename__ = "council_da_records"
    
    # DA Information
    da_number = Column(String(100), unique=True, nullable=False, index=True)
    council_name = Column(String(200), nullable=False)
    status = Column(String(50), nullable=False, index=True)
    
    # Property Information
    address = Column(String(500), nullable=False)
    suburb = Column(String(100), nullable=False, index=True)
    postcode = Column(String(10), nullable=False, index=True)
    lot_number = Column(String(50))
    plan_number = Column(String(50))
    
    # Application Details
    application_type = Column(String(100))
    development_type = Column(String(100))
    description = Column(Text)
    estimated_cost = Column(Numeric(12, 2))
    
    # Timeline
    lodged_date = Column(DateTime(timezone=True))
    decision_date = Column(DateTime(timezone=True))
    determination_date = Column(DateTime(timezone=True))
    
    # Applicant Information
    applicant_name = Column(String(200))
    applicant_type = Column(String(50))  # owner, developer, agent
    
    # Assessment Details
    officer_assessment = Column(Text)
    public_submissions = Column(Integer, default=0)
    conditions = Column(JSONB)
    
    # Source Information
    source_url = Column(String(500))
    raw_data = Column(JSONB)
    last_updated_source = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index("idx_da_records_council_status", council_name, status),
        Index("idx_da_records_location", suburb, postcode),
        Index("idx_da_records_timeline", lodged_date, decision_date),
        Index("idx_da_records_applicant", applicant_name, applicant_type),
    )


class DistressSignalRecord(Base, TimestampMixin):
    """Records of distress signals detected."""
    
    __tablename__ = "distress_signal_records"
    
    # Basic Information
    property_id = Column(PostgresUUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    signal_type = Column(String(50), nullable=False, index=True)
    severity = Column(Numeric(3, 2), nullable=False)  # 0.0 to 1.0
    
    # Signal Details
    description = Column(Text)
    evidence = Column(JSONB)
    detection_method = Column(String(100))
    
    # Timeline
    signal_date = Column(DateTime(timezone=True), nullable=False)
    first_detected = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Source Information
    data_source = Column(String(100), nullable=False)
    source_url = Column(String(500))
    raw_data = Column(JSONB)
    
    # Validation
    validated = Column(Boolean, default=False)
    validation_notes = Column(Text)
    false_positive = Column(Boolean, default=False)
    
    # Relationships
    property = relationship("Property", back_populates="distress_signals")
    
    __table_args__ = (
        Index("idx_distress_signals_property", property_id, signal_type),
        Index("idx_distress_signals_severity", severity, "created_at"),
        Index("idx_distress_signals_timeline", signal_date, "created_at"),
        Index("idx_distress_signals_source", data_source, "created_at"),
    )


# Pydantic models for API serialization

class OpportunityCreateRequest(BaseModel):
    """Request model for creating opportunities."""
    opportunity_type: OpportunityType
    property_id: Optional[str] = None
    address: str
    suburb: str
    postcode: str
    title: str
    description: str
    current_price: Optional[Decimal] = None
    data_sources: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)


class OpportunityResponse(BaseModel):
    """Response model for opportunities."""
    id: str
    opportunity_type: OpportunityType
    status: OpportunityStatus
    address: str
    suburb: str
    postcode: str
    title: str
    description: str
    priority_score: float
    current_price: Optional[Decimal] = None
    estimated_market_value: Optional[Decimal] = None
    discovered_at: datetime
    expires_at: Optional[datetime] = None
    confidence_level: float
    data_sources: List[str]
    tags: List[str]
    
    class Config:
        from_attributes = True


class OpportunitySearchFilters(BaseModel):
    """Filters for searching opportunities."""
    opportunity_types: Optional[List[OpportunityType]] = None
    suburbs: Optional[List[str]] = None
    postcodes: Optional[List[str]] = None
    min_priority_score: Optional[float] = None
    max_price: Optional[Decimal] = None
    min_roi: Optional[float] = None
    time_sensitive_only: bool = False
    high_priority_only: bool = False
    tags: Optional[List[str]] = None
    
    @validator('min_priority_score')
    def validate_priority_score(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError('Priority score must be between 0 and 1')
        return v


class ScanRequest(BaseModel):
    """Request model for initiating scans."""
    scan_type: str = Field(default="full", regex="^(full|expired|council|distress|anomalies)$")
    target_suburbs: Optional[List[str]] = None
    target_postcodes: Optional[List[str]] = None
    force_refresh: bool = False
    filters: Optional[OpportunitySearchFilters] = None


class ScanResponse(BaseModel):
    """Response model for scan results."""
    scan_type: str
    scan_started: datetime
    opportunities_discovered: List[OpportunityResponse]
    scan_statistics: Dict[str, Any]
    compliance_report: Dict[str, Any]
    errors: List[str] = Field(default_factory=list)