# ReAgent Sydney - Database Entity Relationship Diagram

*Generated: 2025-07-28*

## Core Entities Overview

The ReAgent Sydney database consists of 4 main domains with TimescaleDB time-series optimization:

### 1. Property Domain
- **Property** - Main property listings with location and features
- **PropertyPriceHistory** - Time-series price changes (TimescaleDB hypertable)
- **PropertyInspection** - Scheduled inspections and outcomes
- **PropertyMarketMetrics** - Market analysis per property

### 2. Buyer Domain  
- **Buyer** - Buyer profiles and contact information
- **BuyerPreferences** - Search criteria and preferences
- **PropertyMatch** - ML-powered property recommendations
- **BuyerSearchHistory** - Search behavior history
- **PropertyInteraction** - View/favorite/inquiry tracking
- **BuyerSegment** - Market segmentation for targeting
- **BuyerSegmentMembership** - Many-to-many buyer segments

### 3. Market Domain
- **MarketTrend** - Time-series market analysis (TimescaleDB hypertable)  
- **SuburbStats** - Geographic market statistics
- **PriceChange** - Price movement tracking

### 4. Agent Domain
- **AgentExecution** - CrewAI agent run tracking
- **AgentTask** - Individual task execution within runs
- **AgentLog** - Structured logging for debugging

---

## Detailed Entity Relationships

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    PROPERTY     │    │     BUYER       │    │  MARKET_TREND   │
│                 │    │                 │    │                 │
│ PK: id (UUID)   │    │ PK: id (UUID)   │    │ PK: id (UUID)   │
│    listing_id   │    │    email (UK)   │    │    postcode     │
│    title        │    │    first_name   │    │    period_start │
│    suburb       │◄──┐│    last_name    │    │    trend_direction│
│    postcode     │   ││    status       │    │    avg_price    │
│    property_type│   ││    buyer_type   │    │                 │
│    bedrooms     │   ││                 │    │ TimescaleDB:    │
│    price_guide  │   ││                 │    │   time(period_start)│
│    status       │   ││                 │    │   space(postcode)│
│                 │   ││                 │    └─────────────────┘
│ Indexes:        │   ││                 │
│  - suburb       │   ││                 │
│  - postcode     │   ││                 │
│  - property_type│   ││                 │
│  - status       │   ││                 │
└─────────────────┘   ││                 │
                      ││                 │
┌─────────────────┐   ││                 │    ┌─────────────────┐
│PROPERTY_PRICE_  │   ││                 │    │ BUYER_SEGMENT   │
│    HISTORY      │   ││                 │    │                 │
│                 │   ││                 │    │ PK: id (UUID)   │
│ PK: id (UUID)   │   ││                 │    │    name (UK)    │
│ FK: property_id ├───┼┘                 │    │    description  │
│    recorded_at  │   │                  │    │    criteria     │
│    price_type   │   │                  │    │    created_by   │
│    amount       │   │ ┌─────────────────┐   └─────────────────┘
│    source       │   │ │BUYER_PREFERENCES│            │
│                 │   │ │                 │            │
│ TimescaleDB:    │   │ │ PK: id (UUID)   │            │
│  time(recorded_at)│  │ │ FK: buyer_id    ├────────────┼───┐
│  space(property_id)│ │ │    location     │            │   │
└─────────────────┘   │ │    min_price    │            │   │
                      │ │    max_price    │            │   │
┌─────────────────┐   │ │    bedrooms     │            │   │
│PROPERTY_MATCH   │   │ │    property_types│           │   │
│                 │   │ │    suburbs      │            │   │
│ PK: id (UUID)   │   │ │                 │            │   │
│ FK: buyer_id    ├───┼─┤                 │   ┌─────────────────┐
│ FK: property_id ├───┘ └─────────────────┘   │BUYER_SEGMENT_   │
│    match_score  │                           │   MEMBERSHIP    │
│    match_reasons│     ┌─────────────────┐   │                 │
│    status       │     │PROPERTY_        │   │ PK: id (UUID)   │
│    created_at   │     │  INTERACTION    │   │ FK: buyer_id    ├───┘
│                 │     │                 │   │ FK: segment_id  ├───────┘
│ Indexes:        │     │ PK: id (UUID)   │   │    joined_at    │
│  - buyer_id     │     │ FK: buyer_id    ├───┤    left_at      │
│  - property_id  │     │ FK: property_id ├─┐ │    is_active    │
│  - status       │     │    interaction  │ │ └─────────────────┘
│  - created_at   │     │    occurred_at  │ │
└─────────────────┘     │    session_id   │ │
                        │    user_agent   │ │
                        │    ip_address   │ │
                        └─────────────────┘ │
                                           │
        ┌─────────────────┐                │
        │ AGENT_EXECUTION │                │
        │                 │                │
        │ PK: id (UUID)   │                │
        │    agent_name   │                │
        │    execution_id │                │
        │    status       │                │
        │    started_at   │                │
        │    completed_at │                │
        │    input_data   │                │
        │    output_data  │                │
        │    error_details│                │
        │                 │                │
        │ Indexes:        │                │
        │  - agent_name   │                │
        │  - status       │                │
        │  - started_at   │                │
        └─────────────────┘                │
                 │                         │
                 │ 1:N                     │
                 ▼                         │
        ┌─────────────────┐                │
        │   AGENT_TASK    │                │
        │                 │                │
        │ PK: id (UUID)   │                │
        │ FK: execution_id│                │
        │    task_name    │                │
        │    status       │                │
        │    started_at   │                │
        │    completed_at │                │
        │    input_params │                │
        │    output_result│                │
        │    error_message│                │
        │    retry_count  │                │
        │                 │                │
        │ ***ISSUE***     │                │
        │ ERROR: 'metadata'│               │
        │ conflicts with  │                │
        │ SQLAlchemy      │                │
        │ reserved word   │                │
        └─────────────────┘                │
                                          │
                                          │
        ┌─────────────────┐                │
        │   SUBURB_STATS  │                │
        │                 │                │
        │ PK: id (UUID)   │                │
        │    suburb       │                │
        │    postcode     │                │
        │    state        │                │
        │    period_start │                │
        │    period_end   │                │
        │    avg_price    │                │
        │    median_price │                │
        │    price_growth │                │
        │    sales_volume │                │
        │    days_on_market│               │
        │    clearance_rate│               │
        │                 │                │
        │ Composite UK:   │                │
        │  (suburb,postcode,│              │
        │   period_start) │                │
        └─────────────────┘                │
                                          │
                                          └──────┐
                                                 │
        ┌─────────────────┐                      │
        │  PRICE_CHANGE   │                      │
        │                 │                      │
        │ PK: id (UUID)   │                      │
        │ FK: property_id ├──────────────────────┘
        │    change_date  │
        │    old_price    │
        │    new_price    │
        │    change_type  │
        │    change_reason│
        │    detected_by  │
        │                 │
        │ TimescaleDB:    │
        │  time(change_date)│
        │  space(property_id)│
        └─────────────────┘
```

---

## Key Design Decisions

### TimescaleDB Integration
Three hypertables optimized for time-series queries:
1. **property_price_history** - partitioned by `recorded_at` + `property_id`
2. **market_trends** - partitioned by `period_start` + `postcode`  
3. **price_changes** - partitioned by `change_date` + `property_id`

### Geographic Indexing
- Multi-column indexes on `(suburb, postcode)` combinations
- Spatial support ready for latitude/longitude queries
- Hierarchy: Property → Suburb → Postcode → State

### Buyer Intelligence
- Vector-ready `match_reasons` JSONB field for ML explanations
- Session tracking for behavioral analysis
- Segmentation system for targeted recommendations

### Audit & Compliance
- All core entities inherit `TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`
- Agent execution logging for transparency
- GDPR-ready with soft deletes

---

## Critical Issues Identified

### 1. SQLAlchemy Reserved Word Conflict
**File:** `src/data/models/agent_models.py:157`
**Issue:** `metadata` field conflicts with SQLAlchemy's reserved `metadata` attribute
**Impact:** Prevents model compilation and database migrations
**Priority:** URGENT - blocks all database operations

### 2. Import Mismatches  
**File:** `src/data/models/__init__.py`
**Issue:** Imports reference classes that don't exist (PropertyListing, BuyerMatch, etc.)
**Status:** PARTIALLY FIXED during consolidation
**Remaining:** Need to verify all imports match actual class names

---

## Next Actions Required

1. **🚨 URGENT:** Fix `metadata` field conflict in AgentTask model
2. **📊 HIGH:** Complete SQL DDL scripts with proper constraints  
3. **🔄 HIGH:** Create Alembic migration system
4. **🔗 MEDIUM:** Set up connection pooling configuration