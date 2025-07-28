# ReAgent Sydney - Project Coordination Hub

*Last Updated: 2025-07-28*

## Project Scope

**ReAgent Sydney** is a multi-agent real estate intelligence system designed for the Sydney, Australia market. It provides real-time monitoring, intelligent matching, and strategic insights for real estate professionals through a natural language interface.

**Primary Users:** Real estate agents, property investors, market analysts  
**Core Mission:** Eliminate information fragmentation across Domain, REA, CoreLogic by providing unified intelligence layer with sub-hour market updates and AI-powered recommendations.

**Tech Stack:**
- **Backend:** Python 3.11, FastAPI, CrewAI orchestration
- **Data:** PostgreSQL + TimescaleDB, Weaviate vector DB, Redis cache  
- **Frontend:** Next.js with real-time updates
- **Deployment:** Docker Compose (local/VPS), no serverless complexity for MVP
- **APIs:** Domain, RealEstate.com.au, CoreLogic, NSW LPI

**Agent Architecture:**
1. **Listing Watcher AU** - Hourly polling of property listings with delta detection
2. **Suburb Signal Agent** - Micro-trend analysis by postcode/LGA  
3. **Buyer Matchmaker AU** - Vector-based preference matching + inspection alerts
4. **Seller Strategy Agent** - Pricing guidance, auction timing, competitor analysis
5. **Off-Market Radar AU** - Expired listings, council DA tracker, distress signals
6. **Agent Whisperer** - Natural language chat interface + report generation

**MVP Constraints:** Single-user prototype, Sydney metro only, 10-50 active buyers, minimal API costs, basic privacy handling.

---

## Current To-Dos

### System Design & Architecture ✅
- ~~Create comprehensive system design document~~ `[🧠 System-Architect - 2025-07-28]`
- ~~Define component specifications for all 6 agents~~ `[🧠 System-Architect - 2025-07-28]`
- ~~Design production deployment architecture with Docker Compose~~ `[🧠 System-Architect - 2025-07-28]`

### Implementation Structure ✅
- ~~Build complete project directory structure~~ `[🔧 Main Agent - 2025-07-28]`
- ~~Create SQLAlchemy data models for PostgreSQL + TimescaleDB~~ `[🔧 Main Agent - 2025-07-28]`  
- ~~Implement CrewAI agent base classes and skeletons~~ `[🔧 Main Agent - 2025-07-28]`
- ~~Set up FastAPI backend with health checks~~ `[🔧 Main Agent - 2025-07-28]`
- ~~Configure environment management and Docker setup~~ `[🔧 Main Agent - 2025-07-28]`

### Data Models & Database
- Design ERD for all entities (listings, buyers, agents, suburbs)
- Write SQL DDL scripts with TimescaleDB extensions
- Create database migration system
- Set up connection pooling and replica configuration

### Agent Development
- Implement Listing Watcher AU with Domain/REA API integration
- Build Suburb Signal Agent with trend analysis algorithms  
- Create Buyer Matchmaker AU with Weaviate vector search
- Develop Seller Strategy Agent with pricing models
- Build Off-Market Radar AU with council DA tracking
- Implement Agent Whisperer with NLP and report generation

### Infrastructure & Deployment
- Create docker-compose.yml for local development
- Set up monitoring with Prometheus/Grafana
- Configure CI/CD pipeline with GitHub Actions
- Write deployment documentation and runbooks

### Testing & Quality
- Set up pytest framework with coverage targets
- Create integration tests for all agents
- Build API endpoint tests
- Implement load testing scenarios

---

## Current Bottlenecks

*No active bottlenecks reported.*

---

## Current Bugs

*No confirmed bugs reported.*