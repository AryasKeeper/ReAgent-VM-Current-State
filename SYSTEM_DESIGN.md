# ReAgent Sydney - System Design Document

## Problem Statement

Real estate agents in Sydney face information fragmentation across multiple platforms (Domain, REA, CoreLogic) with no unified intelligence layer. Manual monitoring of price changes, buyer matching, and market trends leads to missed opportunities and suboptimal pricing strategies.

## Goals

### Primary Goals
- **Real-time Intelligence**: Monitor 100+ daily listings across Sydney LGAs with <1hr latency
- **Intelligent Matching**: Vector-based buyer-listing matching with 80%+ relevance score
- **Market Insights**: Automated suburb trend detection and pricing recommendations
- **Natural Interface**: Chat-based agent interaction with on-demand reporting

### Success Metrics
- Process 500+ listings/day with 99.5% uptime
- Generate buyer matches within 15 minutes of new listings
- Achieve <2 second response time for agent queries
- Detect price changes within 1 hour of occurrence

## System Constraints

### MVP Constraints
- **Budget**: Single-user prototype, minimal API costs
- **Compliance**: Basic privacy handling, no full GDPR initially
- **Scale**: Sydney metro area only, 10-50 active buyers max
- **Data Sources**: Public APIs only, no premium data feeds initially

### Technical Constraints
- **Rate Limits**: Domain API (1000 calls/day), REA (500 calls/day)
- **Storage**: PostgreSQL + TimescaleDB for time-series data
- **Compute**: Local/VPS deployment with Docker Compose
- **Latency**: Sub-second response for cached queries, <30s for complex analysis

## Architecture Overview

```mermaid
graph TB
    subgraph "External Data Sources"
        DOM[Domain API]
        REA[RealEstate.com.au]
        CL[CoreLogic API]
        LPI[NSW LPI]
    end
    
    subgraph "Data Ingestion Layer"
        LW[Listing Watcher AU]
        OMR[Off-Market Radar AU]
    end
    
    subgraph "Intelligence Layer"
        SSA[Suburb Signal Agent]
        BM[Buyer Matchmaker AU]
        SST[Seller Strategy Agent]
    end
    
    subgraph "Interface Layer"
        AW[Agent Whisperer]
        API[FastAPI Backend]
        WEB[Next.js Frontend]
    end
    
    subgraph "Data Storage"
        PG[(PostgreSQL + TimescaleDB)]
        VDB[(Weaviate Vector DB)]
        CACHE[(Redis Cache)]
    end
    
    subgraph "Orchestration"
        CREW[CrewAI Orchestrator]
        SCHED[Celery Scheduler]
    end
    
    DOM --> LW
    REA --> LW
    CL --> OMR
    LPI --> OMR
    
    LW --> PG
    OMR --> PG
    
    PG --> SSA
    PG --> BM
    PG --> SST
    
    BM --> VDB
    SSA --> CACHE
    
    CREW --> SSA
    CREW --> BM
    CREW --> SST
    
    AW --> CREW
    API --> CREW
    WEB --> API
    
    SCHED --> LW
    SCHED --> OMR
```

## System Sequence Diagram

```mermaid
sequenceDiagram
    participant U as User/Agent
    participant AW as Agent Whisperer
    participant CREW as CrewAI Orchestrator
    participant BM as Buyer Matchmaker
    participant SSA as Suburb Signal Agent
    participant VDB as Vector Database
    participant PG as PostgreSQL
    participant LW as Listing Watcher
    participant DOM as Domain API
    
    Note over LW, DOM: Background Data Ingestion
    loop Every Hour
        LW->>DOM: Fetch new listings
        DOM-->>LW: Listing data
        LW->>PG: Store listings & deltas
        LW->>VDB: Index listing vectors
    end
    
    Note over U, VDB: User Interaction Flow
    U->>AW: "Find matches for buyer John with $2M budget in Northern Beaches"
    AW->>CREW: Parse intent & route task
    CREW->>BM: Execute buyer matching
    BM->>VDB: Vector similarity search
    VDB-->>BM: Ranked matches
    BM->>PG: Fetch listing details
    PG-->>BM: Enhanced listing data
    BM->>SSA: Get suburb trends
    SSA->>PG: Query price trends
    PG-->>SSA: Historical data
    SSA-->>BM: Trend insights
    BM-->>CREW: Compiled results
    CREW-->>AW: Structured response
    AW-->>U: "Found 12 matches in Manly/Dee Why. Market up 8% QoQ."
```

## Component Dependencies

```mermaid
graph LR
    subgraph "Core Dependencies"
        PG[PostgreSQL]
        VDB[Weaviate]
        REDIS[Redis]
    end
    
    subgraph "Agent Dependencies"
        LW[Listing Watcher] --> PG
        LW --> VDB
        
        SSA[Suburb Signal] --> PG
        SSA --> REDIS
        
        BM[Buyer Matchmaker] --> VDB
        BM --> PG
        BM --> SSA
        
        SST[Seller Strategy] --> PG
        SST --> SSA
        
        OMR[Off-Market Radar] --> PG
        
        AW[Agent Whisperer] --> BM
        AW --> SSA
        AW --> SST
        AW --> OMR
    end
```

## Failure Modes & Resilience

### Data Source Failures
- **API Rate Limits**: Exponential backoff, request queuing
- **API Downtime**: Graceful degradation, cached data serving
- **Data Quality**: Validation pipelines, anomaly detection

### System Failures
- **Database Outage**: Connection pooling, retry logic
- **Vector DB Failure**: Fallback to PostgreSQL similarity
- **Agent Crashes**: Automatic restart, health monitoring

### Recovery Strategies
- **Data Consistency**: Write-ahead logging, transaction boundaries
- **State Recovery**: Agent checkpoint persistence
- **Monitoring**: Docker health checks, log aggregation