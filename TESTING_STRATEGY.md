# ReAgent Sydney - Comprehensive Testing Strategy

*Version: 1.0*  
*Last Updated: 2025-07-28*

## Overview

This document outlines the comprehensive testing strategy for the ReAgent Sydney multi-agent real estate intelligence system. Our testing approach ensures reliability, performance, and maintainability across all system components including the 6 specialized agents, FastAPI backend, database operations, and external API integrations.

## Testing Philosophy

**Quality Gates First**: Every component must pass rigorous testing before deployment
**Test Pyramid Approach**: Emphasize fast unit tests, strategic integration tests, and focused E2E tests
**Real-World Scenarios**: Test with realistic Sydney real estate data patterns
**Performance Conscious**: Validate time-series operations and agent orchestration performance
**API-First Testing**: Mock external dependencies but validate integration points

## Architecture Overview

### System Components Under Test
- **6 Specialized Agents**: Listing Watcher, Suburb Signal, Buyer Matchmaker, Seller Strategy, Off-Market Radar, Agent Whisperer
- **FastAPI Backend**: REST APIs with async operations
- **Database Layer**: PostgreSQL + TimescaleDB for time-series data
- **Vector Database**: Weaviate for semantic search and matching
- **Cache Layer**: Redis for performance optimization
- **External APIs**: Domain, REA, CoreLogic integrations
- **CrewAI Orchestration**: Multi-agent coordination and task management

## 1. Unit Testing Strategy

### 1.1 Agent Unit Tests

**Test Structure**: `/tests/unit/agents/`
```
tests/unit/agents/
├── __init__.py
├── test_base_agent.py
├── test_listing_watcher/
│   ├── __init__.py
│   ├── test_listing_watcher_core.py
│   ├── test_listing_processor.py
│   └── test_delta_detection.py
├── test_suburb_signal/
│   ├── __init__.py
│   ├── test_trend_analyzer.py
│   ├── test_micro_trend_detection.py
│   └── test_postcode_aggregation.py
├── test_buyer_matchmaker/
│   ├── __init__.py
│   ├── test_preference_matching.py
│   ├── test_vector_search.py
│   └── test_inspection_alerts.py
├── test_seller_strategy/
│   ├── __init__.py
│   ├── test_pricing_models.py
│   ├── test_auction_timing.py
│   └── test_competitor_analysis.py
├── test_off_market_radar/
│   ├── __init__.py
│   ├── test_expired_listings.py
│   ├── test_da_tracker.py
│   └── test_distress_signals.py
└── test_agent_whisperer/
    ├── __init__.py
    ├── test_nlp_processing.py
    ├── test_report_generation.py
    └── test_chat_interface.py
```

**Test Patterns for Agents**:
```python
# tests/unit/agents/test_base_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from reagent_sydney.agents.base import BaseReAgentAgent, AgentConfig, AgentRole
from reagent_sydney.agents.listing_watcher import ListingWatcherAgent

class TestBaseAgent:
    """Test base agent functionality."""
    
    @pytest.fixture
    def agent_config(self):
        return AgentConfig(
            name="Test Agent",
            role=AgentRole.DATA_COLLECTOR,
            description="Test agent for unit tests",
            max_execution_time=60,
            max_retries=2
        )
    
    @pytest.fixture
    def mock_agent(self, agent_config):
        # Create concrete implementation for testing
        class MockAgent(BaseReAgentAgent):
            async def _initialize_agent(self):
                pass
            
            async def _cleanup_agent(self):
                pass
            
            async def _execute_agent_logic(self, input_data):
                return {"status": "success", "processed": len(input_data)}
            
            async def _initialize_tools(self):
                return []
            
            def _get_agent_goal(self):
                return "Test goal"
            
            def _get_agent_backstory(self):
                return "Test backstory"
        
        return MockAgent(agent_config)
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_agent):
        """Test agent initialization process."""
        await mock_agent.initialize()
        
        assert mock_agent._crew_agent is not None
        assert mock_agent.logger is not None
        assert mock_agent.cache_manager is not None
    
    @pytest.mark.asyncio
    async def test_execution_tracking(self, mock_agent):
        """Test execution context and tracking."""
        input_data = {"test": "data"}
        
        result = await mock_agent.execute(input_data)
        
        assert result["success"] is True
        assert "execution_id" in result
        assert "execution_time" in result
        assert result["data"]["processed"] == 1
    
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_agent):
        """Test error handling and metrics update."""
        # Mock agent logic to raise exception
        mock_agent._execute_agent_logic = AsyncMock(side_effect=Exception("Test error"))
        
        result = await mock_agent.execute()
        
        assert result["success"] is False
        assert "error" in result
        assert mock_agent.metrics.failed_executions == 1
    
    def test_metrics_calculation(self, mock_agent):
        """Test metrics calculation accuracy."""
        # Simulate multiple executions
        mock_agent._update_metrics(True, 1.5)
        mock_agent._update_metrics(False, 2.0)
        mock_agent._update_metrics(True, 1.0)
        
        assert mock_agent.metrics.total_executions == 3
        assert mock_agent.metrics.successful_executions == 2
        assert mock_agent.metrics.failed_executions == 1
        assert mock_agent.metrics.success_rate == 66.67
        assert mock_agent.metrics.avg_execution_time == 1.5

# tests/unit/agents/test_listing_watcher/test_listing_watcher_core.py
@pytest.mark.unit
class TestListingWatcherCore:
    """Test core ListingWatcher functionality."""
    
    @pytest.fixture
    def listing_watcher(self):
        config = AgentConfig(
            name="Listing Watcher AU",
            role=AgentRole.DATA_COLLECTOR,
            description="Property listing monitoring agent"
        )
        return ListingWatcherAgent(config)
    
    @pytest.mark.asyncio
    async def test_delta_detection(self, listing_watcher, sample_listing_data):
        """Test listing change detection."""
        # Mock existing listings
        existing_listings = [sample_listing_data]
        new_listings = [
            {**sample_listing_data, "price": 850000}  # Price change
        ]
        
        with patch.object(listing_watcher, '_fetch_existing_listings', 
                         return_value=existing_listings):
            changes = await listing_watcher._detect_changes(new_listings)
        
        assert len(changes) == 1
        assert changes[0]["change_type"] == "price_update"
        assert changes[0]["old_price"] == 800000
        assert changes[0]["new_price"] == 850000
    
    @pytest.mark.asyncio
    async def test_api_rate_limiting(self, listing_watcher):
        """Test API rate limiting behavior."""
        # Mock API calls to simulate rate limiting
        call_count = 0
        
        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            if call_count > 5:
                raise Exception("Rate limit exceeded")
            return {"listings": []}
        
        listing_watcher._api_client.get_listings = mock_api_call
        
        # Should handle rate limiting gracefully
        result = await listing_watcher._fetch_with_rate_limiting()
        assert call_count <= 5
```

### 1.2 Database Model Unit Tests

**Test Structure**: `/tests/unit/models/`
```python
# tests/unit/models/test_property_models.py
import pytest
from datetime import datetime, timedelta

from reagent_sydney.data.models.property_models import PropertyListing, PriceHistory

@pytest.mark.unit
class TestPropertyModels:
    """Test property data models."""
    
    def test_property_listing_creation(self, sample_listing_data):
        """Test PropertyListing model creation."""
        listing = PropertyListing(**sample_listing_data)
        
        assert listing.domain_id == "12345"
        assert listing.address == "123 Test Street, Sydney NSW 2000"
        assert listing.price == 800000
        assert listing.is_active is True
    
    def test_price_change_detection(self):
        """Test price change detection logic."""
        listing = PropertyListing(
            domain_id="test123",
            address="Test Address",
            price=800000,
            suburb="Sydney",
            postcode="2000"
        )
        
        # Simulate price change
        old_price = listing.price
        listing.price = 850000
        
        price_history = PriceHistory(
            listing_id=listing.id,
            old_price=old_price,
            new_price=listing.price,
            change_date=datetime.utcnow(),
            change_percentage=((850000 - 800000) / 800000) * 100
        )
        
        assert price_history.change_percentage == 6.25
    
    def test_listing_status_transitions(self):
        """Test valid listing status transitions."""
        listing = PropertyListing(
            domain_id="test123",
            address="Test Address",
            status="active"
        )
        
        # Valid transitions
        listing.status = "sold"
        assert listing.status == "sold"
        
        listing.status = "withdrawn"
        assert listing.status == "withdrawn"
```

### 1.3 Service Layer Unit Tests

**Test Structure**: `/tests/unit/services/`
```python
# tests/unit/services/test_external_apis/test_domain_client.py
import pytest
from unittest.mock import AsyncMock, patch
import httpx

from reagent_sydney.services.external_apis.domain_client import DomainAPIClient

@pytest.mark.unit
class TestDomainAPIClient:
    """Test Domain API client."""
    
    @pytest.fixture
    def domain_client(self):
        return DomainAPIClient(api_key="test-key")
    
    @pytest.mark.asyncio
    async def test_successful_listing_fetch(self, domain_client, mock_httpx_client):
        """Test successful listing retrieval."""
        mock_response = {
            "listings": [
                {
                    "id": "12345",
                    "address": "123 Test St, Sydney NSW",
                    "price": 800000
                }
            ]
        }
        
        mock_httpx_client.get.return_value.json.return_value = mock_response
        mock_httpx_client.get.return_value.status_code = 200
        
        with patch.object(domain_client, '_client', mock_httpx_client):
            listings = await domain_client.get_listings(suburb="Sydney")
        
        assert len(listings) == 1
        assert listings[0]["id"] == "12345"
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, domain_client, mock_httpx_client):
        """Test API error handling."""
        mock_httpx_client.get.side_effect = httpx.HTTPError("Network error")
        
        with patch.object(domain_client, '_client', mock_httpx_client):
            with pytest.raises(Exception):
                await domain_client.get_listings(suburb="Sydney")
    
    @pytest.mark.asyncio
    async def test_rate_limiting_retry(self, domain_client, mock_httpx_client):
        """Test rate limiting retry logic."""
        # First call returns 429, second succeeds
        mock_responses = [
            AsyncMock(status_code=429, json=AsyncMock(return_value={"error": "Rate limited"})),
            AsyncMock(status_code=200, json=AsyncMock(return_value={"listings": []}))
        ]
        
        mock_httpx_client.get.side_effect = mock_responses
        
        with patch.object(domain_client, '_client', mock_httpx_client):
            result = await domain_client.get_listings(suburb="Sydney")
        
        assert mock_httpx_client.get.call_count == 2
        assert result == {"listings": []}
```

## 2. Integration Testing Strategy

### 2.1 Database Integration Tests

**Test Structure**: `/tests/integration/database/`
```python
# tests/integration/database/test_timescale_operations.py
import pytest
from datetime import datetime, timedelta

from reagent_sydney.data.models.market_models import MarketTrend, SuburbStats

@pytest.mark.integration
@pytest.mark.requires_db
class TestTimescaleOperations:
    """Test TimescaleDB specific operations."""
    
    @pytest.mark.asyncio
    async def test_hypertable_insertion(self, db_session):
        """Test insertion into TimescaleDB hypertables."""
        # Create market trend data
        trend = MarketTrend(
            suburb="Sydney",
            postcode="2000",
            timestamp=datetime.utcnow(),
            median_price=950000,
            listings_count=45,
            days_on_market=28
        )
        
        db_session.add(trend)
        await db_session.commit()
        
        # Verify insertion
        result = await db_session.execute(
            "SELECT COUNT(*) FROM market_trends WHERE suburb = 'Sydney'"
        )
        assert result.scalar() == 1
    
    @pytest.mark.asyncio
    async def test_time_bucket_aggregation(self, db_session):
        """Test TimescaleDB time bucket aggregations."""
        # Insert sample data across multiple time periods
        base_time = datetime.utcnow() - timedelta(days=30)
        
        for i in range(30):
            trend = MarketTrend(
                suburb="Sydney",
                postcode="2000",
                timestamp=base_time + timedelta(days=i),
                median_price=900000 + (i * 1000),
                listings_count=40 + i,
                days_on_market=25 + (i % 10)
            )
            db_session.add(trend)
        
        await db_session.commit()
        
        # Test weekly aggregation
        query = """
        SELECT 
            time_bucket('7 days', timestamp) as week,
            AVG(median_price) as avg_price,
            SUM(listings_count) as total_listings
        FROM market_trends 
        WHERE suburb = 'Sydney'
        GROUP BY week
        ORDER BY week
        """
        
        result = await db_session.execute(query)
        rows = result.fetchall()
        
        assert len(rows) >= 4  # Should have ~4 weeks of data
        assert all(row.avg_price > 0 for row in rows)
    
    @pytest.mark.asyncio
    async def test_continuous_aggregates(self, db_session):
        """Test TimescaleDB continuous aggregates."""
        # This would test pre-computed aggregations
        # Implementation depends on specific continuous aggregate setup
        pass
```

### 2.2 Vector Database Integration Tests

```python
# tests/integration/vector_db/test_weaviate_operations.py
import pytest
import numpy as np

from reagent_sydney.core.vector_db.weaviate_client import WeaviateManager

@pytest.mark.integration
class TestWeaviateOperations:
    """Test Weaviate vector database operations."""
    
    @pytest.fixture
    async def weaviate_manager(self):
        manager = WeaviateManager()
        await manager.initialize()
        yield manager
        await manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_property_vector_storage(self, weaviate_manager, sample_listing_data):
        """Test storing property vectors."""
        # Create property vector
        property_vector = {
            "id": sample_listing_data["domain_id"],
            "description": sample_listing_data["description"],
            "features": {
                "bedrooms": sample_listing_data["bedrooms"],
                "bathrooms": sample_listing_data["bathrooms"],
                "price": sample_listing_data["price"],
                "suburb": sample_listing_data["suburb"]
            }
        }
        
        # Store in Weaviate
        object_id = await weaviate_manager.store_property(property_vector)
        assert object_id is not None
        
        # Retrieve and verify
        retrieved = await weaviate_manager.get_property(object_id)
        assert retrieved["features"]["bedrooms"] == 2
    
    @pytest.mark.asyncio
    async def test_semantic_search(self, weaviate_manager):
        """Test semantic search functionality."""
        # Store test properties
        properties = [
            {
                "id": "prop1",
                "description": "Modern apartment with harbor views",
                "features": {"bedrooms": 2, "price": 800000, "suburb": "Sydney"}
            },
            {
                "id": "prop2", 
                "description": "Family home with garden and pool",
                "features": {"bedrooms": 4, "price": 1200000, "suburb": "Bondi"}
            }
        ]
        
        for prop in properties:
            await weaviate_manager.store_property(prop)
        
        # Search for similar properties
        search_query = "waterfront apartment with views"
        results = await weaviate_manager.semantic_search(search_query, limit=2)
        
        assert len(results) >= 1
        # Harbor views property should rank higher
        assert results[0]["id"] == "prop1"
    
    @pytest.mark.asyncio
    async def test_buyer_preference_matching(self, weaviate_manager, sample_buyer_data):
        """Test buyer preference vector matching."""
        # Create buyer preference vector
        buyer_preferences = {
            "budget_range": [sample_buyer_data["budget_min"], sample_buyer_data["budget_max"]],
            "preferred_suburbs": sample_buyer_data["preferred_suburbs"],
            "property_types": sample_buyer_data["property_types"],
            "min_bedrooms": sample_buyer_data["bedrooms_min"]
        }
        
        # Find matching properties
        matches = await weaviate_manager.find_matching_properties(buyer_preferences)
        
        assert isinstance(matches, list)
        if matches:
            assert all("similarity_score" in match for match in matches)
```

### 2.3 Agent Orchestration Integration Tests

```python
# tests/integration/agents/test_agent_orchestration.py
import pytest
from unittest.mock import AsyncMock, patch

from reagent_sydney.agents.orchestrator import AgentOrchestrator
from reagent_sydney.agents.listing_watcher import ListingWatcherAgent
from reagent_sydney.agents.buyer_matchmaker import BuyerMatchmakerAgent

@pytest.mark.integration
class TestAgentOrchestration:
    """Test agent orchestration and coordination."""
    
    @pytest.fixture
    async def orchestrator(self):
        orchestrator = AgentOrchestrator()
        await orchestrator.initialize()
        yield orchestrator
        await orchestrator.shutdown()
    
    @pytest.mark.asyncio
    async def test_agent_workflow_execution(self, orchestrator):
        """Test complete agent workflow execution."""
        # Mock external APIs
        with patch('reagent_sydney.services.external_apis.domain_client.DomainAPIClient') as mock_domain:
            mock_domain.return_value.get_listings = AsyncMock(return_value=[
                {
                    "id": "12345",
                    "address": "123 Test St, Sydney NSW",
                    "price": 800000,
                    "bedrooms": 2,
                    "suburb": "Sydney"
                }
            ])
            
            # Execute workflow: Listing Watcher -> Buyer Matchmaker
            workflow_result = await orchestrator.execute_workflow(
                "listing_analysis",
                {"suburbs": ["Sydney"], "max_listings": 10}
            )
        
        assert workflow_result["success"] is True
        assert "listings_processed" in workflow_result
        assert "matches_found" in workflow_result
    
    @pytest.mark.asyncio
    async def test_agent_failure_handling(self, orchestrator):
        """Test agent failure and recovery."""
        # Mock agent failure
        with patch.object(orchestrator.agents["listing_watcher"], "execute", 
                         side_effect=Exception("Agent failed")):
            
            result = await orchestrator.execute_workflow("listing_analysis")
        
        assert result["success"] is False
        assert "error" in result
        # Check that other agents didn't execute due to dependency failure
        assert orchestrator.execution_stats["failed_agents"] == 1
    
    @pytest.mark.asyncio
    async def test_parallel_agent_execution(self, orchestrator):
        """Test parallel execution of independent agents."""
        # Execute multiple independent agents
        tasks = [
            orchestrator.execute_agent("suburb_signal", {"postcode": "2000"}),
            orchestrator.execute_agent("suburb_signal", {"postcode": "2001"}),
            orchestrator.execute_agent("suburb_signal", {"postcode": "2002"})
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        assert all(result["success"] for result in results)
```

## 3. End-to-End Testing Strategy

### 3.1 Complete System Workflows

```python
# tests/e2e/test_complete_workflows.py
import pytest
from fastapi.testclient import TestClient

@pytest.mark.e2e
class TestCompleteWorkflows:
    """Test complete system workflows end-to-end."""
    
    @pytest.mark.asyncio
    async def test_new_listing_to_buyer_notification(self, test_client):
        """Test complete flow from new listing detection to buyer notification."""
        
        # Step 1: Create buyer profile
        buyer_data = {
            "name": "Test Buyer",
            "email": "test@example.com",
            "budget_min": 700000,
            "budget_max": 900000,
            "preferred_suburbs": ["Sydney", "Pyrmont"],
            "property_types": ["apartment"]
        }
        
        buyer_response = test_client.post("/api/v1/buyers/", json=buyer_data)
        assert buyer_response.status_code == 201
        buyer_id = buyer_response.json()["id"]
        
        # Step 2: Trigger listing watcher (simulate new listing)
        with patch('external_api_calls'):  # Mock external APIs
            listing_response = test_client.post(
                "/api/v1/agents/listing-watcher/execute",
                json={"suburbs": ["Sydney"]}
            )
        
        assert listing_response.status_code == 200
        
        # Step 3: Check that matching was triggered
        matches_response = test_client.get(f"/api/v1/buyers/{buyer_id}/matches")
        assert matches_response.status_code == 200
        matches = matches_response.json()
        
        # Should have found matches for the buyer
        assert len(matches) > 0
        
        # Step 4: Verify notification was sent
        notifications_response = test_client.get(f"/api/v1/buyers/{buyer_id}/notifications")
        assert notifications_response.status_code == 200
        notifications = notifications_response.json()
        
        assert any(notif["type"] == "new_match" for notif in notifications)
    
    @pytest.mark.asyncio
    async def test_market_analysis_workflow(self, test_client):
        """Test market analysis and reporting workflow."""
        
        # Trigger suburb signal analysis
        analysis_response = test_client.post(
            "/api/v1/agents/suburb-signal/execute",
            json={"postcodes": ["2000", "2001"], "analysis_period": "30d"}
        )
        
        assert analysis_response.status_code == 200
        analysis_result = analysis_response.json()
        
        # Check analysis results
        assert "trend_data" in analysis_result
        assert "price_movements" in analysis_result
        
        # Generate market report
        report_response = test_client.post(
            "/api/v1/reports/market-analysis",
            json={"postcodes": ["2000", "2001"], "format": "pdf"}
        )
        
        assert report_response.status_code == 200
        assert report_response.headers["content-type"] == "application/pdf"
```

### 3.2 Performance Testing

```python
# tests/e2e/test_performance.py
import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

@pytest.mark.e2e
@pytest.mark.slow
class TestPerformance:
    """Test system performance under load."""
    
    @pytest.mark.asyncio
    async def test_concurrent_agent_execution(self):
        """Test system performance with concurrent agent executions."""
        
        async def execute_agent(agent_name, params):
            start_time = time.time()
            # Execute agent via API
            response = await test_client.post(f"/api/v1/agents/{agent_name}/execute", json=params)
            execution_time = time.time() - start_time
            return {
                "agent": agent_name,
                "success": response.status_code == 200,
                "execution_time": execution_time
            }
        
        # Execute 10 concurrent agent tasks
        tasks = []
        for i in range(10):
            tasks.append(execute_agent("listing-watcher", {"suburb": f"test-suburb-{i}"}))
        
        results = await asyncio.gather(*tasks)
        
        # Performance assertions
        success_rate = sum(1 for r in results if r["success"]) / len(results)
        avg_execution_time = sum(r["execution_time"] for r in results) / len(results)
        
        assert success_rate >= 0.9  # 90% success rate minimum
        assert avg_execution_time < 30.0  # Average execution under 30 seconds
    
    @pytest.mark.asyncio
    async def test_database_performance(self, db_session):
        """Test database performance with large datasets."""
        
        # Insert large number of listings
        start_time = time.time()
        
        listings = []
        for i in range(1000):
            listing = PropertyListing(
                domain_id=f"perf-test-{i}",
                address=f"{i} Performance St, Sydney NSW",
                price=800000 + (i * 1000),
                suburb="Sydney",
                postcode="2000"
            )
            listings.append(listing)
        
        db_session.add_all(listings)
        await db_session.commit()
        
        insert_time = time.time() - start_time
        
        # Query performance test
        start_time = time.time()
        
        result = await db_session.execute(
            "SELECT COUNT(*) FROM property_listings WHERE suburb = 'Sydney'"
        )
        count = result.scalar()
        
        query_time = time.time() - start_time
        
        # Performance assertions
        assert insert_time < 5.0  # Bulk insert under 5 seconds
        assert query_time < 1.0   # Query under 1 second
        assert count == 1000
    
    @pytest.mark.asyncio
    async def test_vector_search_performance(self, weaviate_manager):
        """Test vector search performance with large dataset."""
        
        # Store large number of property vectors
        properties = []
        for i in range(500):
            prop = {
                "id": f"perf-prop-{i}",
                "description": f"Property {i} with various features",
                "features": {
                    "bedrooms": (i % 5) + 1,
                    "price": 600000 + (i * 2000),
                    "suburb": f"Suburb-{i % 20}"
                }
            }
            properties.append(prop)
        
        # Measure batch insertion time
        start_time = time.time()
        await weaviate_manager.batch_store_properties(properties)
        insert_time = time.time() - start_time
        
        # Measure search performance
        start_time = time.time()
        results = await weaviate_manager.semantic_search(
            "modern apartment with good features", 
            limit=10
        )
        search_time = time.time() - start_time
        
        # Performance assertions
        assert insert_time < 30.0  # Batch insert under 30 seconds
        assert search_time < 2.0   # Search under 2 seconds
        assert len(results) == 10
```

## 4. Test Data Management and Fixtures

### 4.1 Test Data Factory

```python
# tests/factories.py
import factory
from factory import fuzzy
from datetime import datetime, timedelta
import random

from reagent_sydney.data.models.property_models import PropertyListing
from reagent_sydney.data.models.buyer_models import BuyerProfile

class PropertyListingFactory(factory.Factory):
    """Factory for creating test property listings."""
    
    class Meta:
        model = PropertyListing
    
    domain_id = factory.Sequence(lambda n: f"test-listing-{n}")
    address = factory.Faker('street_address')
    suburb = fuzzy.FuzzyChoice(['Sydney', 'Bondi', 'Manly', 'Pyrmont', 'Darlinghurst'])
    postcode = fuzzy.FuzzyChoice(['2000', '2026', '2095', '2009', '2010'])
    property_type = fuzzy.FuzzyChoice(['apartment', 'house', 'townhouse', 'studio'])
    bedrooms = fuzzy.FuzzyInteger(1, 5)
    bathrooms = fuzzy.FuzzyInteger(1, 3)
    car_spaces = fuzzy.FuzzyInteger(0, 3)
    price = fuzzy.FuzzyInteger(500000, 2000000)
    price_display = factory.LazyAttribute(lambda obj: f"${obj.price:,}")
    listing_date = factory.LazyFunction(
        lambda: datetime.utcnow() - timedelta(days=random.randint(1, 60))
    )
    status = fuzzy.FuzzyChoice(['active', 'under_contract', 'sold', 'withdrawn'])
    source = 'domain'
    description = factory.Faker('text', max_nb_chars=500)

class BuyerProfileFactory(factory.Factory):
    """Factory for creating test buyer profiles."""
    
    class Meta:
        model = BuyerProfile
    
    name = factory.Faker('name')
    email = factory.Faker('email')
    budget_min = fuzzy.FuzzyInteger(400000, 800000)
    budget_max = factory.LazyAttribute(lambda obj: obj.budget_min + random.randint(100000, 500000))
    preferred_suburbs = factory.LazyFunction(
        lambda: random.sample(['Sydney', 'Bondi', 'Manly', 'Pyrmont'], k=random.randint(1, 3))
    )
    property_types = factory.LazyFunction(
        lambda: random.sample(['apartment', 'house', 'townhouse'], k=random.randint(1, 2))
    )
    bedrooms_min = fuzzy.FuzzyInteger(1, 4)
    is_active = True
    urgency_level = fuzzy.FuzzyChoice(['low', 'medium', 'high'])

# Usage in tests
@pytest.fixture
def sample_listings():
    """Create sample listings for testing."""
    return PropertyListingFactory.create_batch(10)

@pytest.fixture
def sample_buyers():
    """Create sample buyer profiles for testing."""
    return BuyerProfileFactory.create_batch(5)
```

### 4.2 Test Database Setup

```python
# tests/database_fixtures.py
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from reagent_sydney.data.models.base import Base

@pytest.fixture(scope="session")
async def test_database():
    """Create and manage test database."""
    
    # Create in-memory SQLite for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()

@pytest.fixture
async def db_session(test_database):
    """Create database session for tests."""
    Session = async_sessionmaker(test_database, expire_on_commit=False)
    
    async with Session() as session:
        yield session
        await session.rollback()

@pytest.fixture(scope="session")
def load_test_data():
    """Load comprehensive test dataset."""
    return {
        "sydney_postcodes": ["2000", "2001", "2006", "2009", "2010"],
        "property_types": ["apartment", "house", "townhouse", "studio"],
        "sample_descriptions": [
            "Modern apartment with harbor views and premium finishes",
            "Family home with garden, pool and entertaining area",
            "Contemporary townhouse in sought-after location",
            "Spacious studio in the heart of the city"
        ],
        "suburbs_data": {
            "Sydney": {"median_price": 950000, "growth_rate": 0.05},
            "Bondi": {"median_price": 1200000, "growth_rate": 0.03},
            "Manly": {"median_price": 1100000, "growth_rate": 0.04}
        }
    }
```

## 5. Mock Strategies for External APIs

### 5.1 API Response Mocking

```python
# tests/mocks/external_api_mocks.py
import json
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, List, Any

class MockDomainAPI:
    """Mock Domain API responses."""
    
    def __init__(self):
        self.call_count = 0
        self.rate_limited = False
    
    async def get_listings(self, suburb: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Mock Domain API listings endpoint."""
        self.call_count += 1
        
        if self.rate_limited and self.call_count % 5 == 0:
            raise Exception("Rate limit exceeded")
        
        # Return mock listings based on suburb
        if suburb == "Sydney":
            return [
                {
                    "id": "domain-12345",
                    "address": "123 Harbour St, Sydney NSW 2000",
                    "price": 850000,
                    "bedrooms": 2,
                    "bathrooms": 1,
                    "property_type": "apartment",
                    "listing_date": "2025-07-28T10:00:00Z"
                },
                {
                    "id": "domain-12346", 
                    "address": "456 City Rd, Sydney NSW 2000",
                    "price": 950000,
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "property_type": "apartment",
                    "listing_date": "2025-07-27T14:30:00Z"
                }
            ]
        else:
            return []
    
    async def get_sold_listings(self, suburb: str = None, **kwargs) -> List[Dict[str, Any]]:
        """Mock Domain API sold listings endpoint."""
        return [
            {
                "id": "domain-sold-001",
                "address": "789 Test Ave, Sydney NSW 2000",
                "sold_price": 825000,
                "sold_date": "2025-07-20T00:00:00Z",
                "bedrooms": 2,
                "bathrooms": 1
            }
        ]

class MockREAAPI:
    """Mock RealEstate.com.au API responses."""
    
    async def search_properties(self, **params) -> Dict[str, Any]:
        """Mock REA property search."""
        return {
            "listings": [
                {
                    "id": "rea-98765",
                    "address": "321 Beach Rd, Bondi NSW 2026",
                    "price": "Guide $1,200,000",
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "property_type": "house"
                }
            ],
            "total_count": 1,
            "page": 1
        }

class MockCoreLogicAPI:
    """Mock CoreLogic API responses."""
    
    async def get_market_data(self, postcode: str) -> Dict[str, Any]:
        """Mock CoreLogic market data."""
        return {
            "postcode": postcode,
            "median_price": 950000,
            "price_change_12m": 0.05,
            "days_on_market": 32,
            "clearance_rate": 0.68,
            "stock_levels": "low"
        }

# Pytest fixtures for mocks
@pytest.fixture
def mock_domain_api():
    """Mock Domain API client."""
    return MockDomainAPI()

@pytest.fixture
def mock_rea_api():
    """Mock REA API client."""
    return MockREAAPI()

@pytest.fixture
def mock_corelogic_api():
    """Mock CoreLogic API client."""
    return MockCoreLogicAPI()

@pytest.fixture
def mock_all_external_apis(monkeypatch, mock_domain_api, mock_rea_api, mock_corelogic_api):
    """Mock all external API clients."""
    monkeypatch.setattr(
        "reagent_sydney.services.external_apis.domain_client.DomainAPIClient",
        lambda: mock_domain_api
    )
    monkeypatch.setattr(
        "reagent_sydney.services.external_apis.rea_client.REAAPIClient", 
        lambda: mock_rea_api
    )
    monkeypatch.setattr(
        "reagent_sydney.services.external_apis.corelogic_client.CoreLogicAPIClient",
        lambda: mock_corelogic_api
    )
    
    return {
        "domain": mock_domain_api,
        "rea": mock_rea_api, 
        "corelogic": mock_corelogic_api
    }
```

### 5.2 Dynamic Response Generation

```python
# tests/mocks/response_generators.py
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any

class ResponseGenerator:
    """Generate realistic mock API responses."""
    
    @staticmethod
    def generate_listing_response(count: int = 10, suburb: str = "Sydney") -> List[Dict[str, Any]]:
        """Generate realistic listing data."""
        listings = []
        
        for i in range(count):
            listing = {
                "id": f"mock-{suburb.lower()}-{i:04d}",
                "address": f"{random.randint(1, 999)} {random.choice(['Harbour', 'Beach', 'City', 'Park'])} {random.choice(['St', 'Rd', 'Ave', 'Dr'])}, {suburb} NSW",
                "price": random.randint(600000, 1500000),
                "bedrooms": random.randint(1, 4),
                "bathrooms": random.randint(1, 3),
                "car_spaces": random.randint(0, 2),
                "property_type": random.choice(["apartment", "house", "townhouse"]),
                "listing_date": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
                "description": f"Beautiful {random.choice(['modern', 'contemporary', 'renovated'])} property in {suburb}",
                "features": random.sample([
                    "air_conditioning", "balcony", "pool", "garden", 
                    "parking", "gym", "security", "storage"
                ], k=random.randint(2, 5))
            }
            listings.append(listing)
        
        return listings
    
    @staticmethod
    def generate_market_data(postcode: str) -> Dict[str, Any]:
        """Generate realistic market data."""
        base_price = 800000 + (int(postcode) * 10000)  # Price varies by postcode
        
        return {
            "postcode": postcode,
            "median_price": base_price + random.randint(-100000, 200000),
            "price_change_12m": random.uniform(-0.1, 0.15),  # -10% to +15%
            "price_change_3m": random.uniform(-0.05, 0.08),   # -5% to +8%
            "days_on_market": random.randint(20, 60),
            "clearance_rate": random.uniform(0.5, 0.8),
            "stock_levels": random.choice(["very_low", "low", "medium", "high"]),
            "listings_count": random.randint(50, 200),
            "sales_count": random.randint(30, 120),
            "growth_trend": random.choice(["increasing", "stable", "decreasing"])
        }
```

## 6. CI/CD Testing Pipeline

### 6.1 GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: ReAgent Sydney Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  PYTHON_VERSION: "3.11"
  POETRY_VERSION: "1.5.1"

jobs:
  lint-and-format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install black isort ruff mypy bandit
      
      - name: Run Black
        run: black --check src tests
      
      - name: Run isort
        run: isort --check-only src tests
      
      - name: Run Ruff
        run: ruff check src tests
      
      - name: Run MyPy
        run: mypy src
      
      - name: Run Bandit Security Check
        run: bandit -r src -f json -o bandit-report.json
      
      - name: Upload Bandit Report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: bandit-report
          path: bandit-report.json

  unit-tests:
    runs-on: ubuntu-latest
    needs: lint-and-format
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      
      - name: Run Unit Tests
        run: |
          pytest tests/unit/ \
            --cov=src \
            --cov-report=xml \
            --cov-report=html \
            --junitxml=junit-unit.xml \
            -v
      
      - name: Upload Coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unit
          name: unit-tests
      
      - name: Upload Test Results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: unit-test-results
          path: |
            junit-unit.xml
            htmlcov/

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    
    services:
      postgres:
        image: timescale/timescaledb:latest-pg15
        env:
          POSTGRES_DB: reagent_test
          POSTGRES_USER: reagent
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
      
      weaviate:
        image: semitechnologies/weaviate:1.21.2
        env:
          AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
          DEFAULT_VECTORIZER_MODULE: 'text2vec-openai'
          ENABLE_MODULES: 'text2vec-openai'
        ports:
          - 8080:8080
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      
      - name: Wait for services
        run: |
          sleep 30  # Give services time to fully start
      
      - name: Run Integration Tests
        env:
          DATABASE_URL: postgresql+asyncpg://reagent:test_password@localhost:5432/reagent_test
          REDIS_URL: redis://localhost:6379/0
          WEAVIATE_URL: http://localhost:8080
          OPENAI_API_KEY: test-key
        run: |
          pytest tests/integration/ \
            --cov=src \
            --cov-report=xml \
            --junitxml=junit-integration.xml \
            -v \
            -m "integration and not slow"
      
      - name: Upload Integration Test Results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: integration-test-results
          path: junit-integration.xml

  e2e-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Start Test Environment
        run: |
          docker-compose -f docker-compose.test.yml up -d
          sleep 60  # Wait for all services to be ready
      
      - name: Run E2E Tests
        run: |
          docker-compose -f docker-compose.test.yml exec -T api-test \
            pytest tests/e2e/ \
            --junitxml=junit-e2e.xml \
            -v \
            -m "not slow"
      
      - name: Collect Logs
        if: always()
        run: |
          mkdir -p logs
          docker-compose -f docker-compose.test.yml logs > logs/docker-compose.logs
      
      - name: Upload E2E Test Results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: e2e-test-results
          path: |
            junit-e2e.xml
            logs/

  performance-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Start Test Environment
        run: |
          docker-compose -f docker-compose.test.yml up -d
          sleep 60
      
      - name: Run Performance Tests
        run: |
          docker-compose -f docker-compose.test.yml exec -T api-test \
            pytest tests/e2e/test_performance.py \
            --junitxml=junit-performance.xml \
            -v \
            -m "slow" \
            --tb=short
      
      - name: Upload Performance Results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: performance-results
          path: junit-performance.xml

  security-tests:
    runs-on: ubuntu-latest
    needs: lint-and-format
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Run Safety Check
        run: |
          pip install safety
          safety check --json --output safety-report.json || true
      
      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: p/python
          generateSarif: "1"
      
      - name: Upload Security Reports
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: security-reports
          path: |
            safety-report.json
            semgrep.sarif
```

### 6.2 Local Testing Scripts

```bash
#!/bin/bash
# scripts/run-tests.sh

set -e

echo "🧪 ReAgent Sydney - Test Runner"
echo "================================"

# Default values
TEST_TYPE="all"
COVERAGE=true
VERBOSE=false
PARALLEL=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        --no-coverage)
            COVERAGE=false
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -t, --type TYPE     Test type (unit|integration|e2e|all)"
            echo "  --no-coverage       Skip coverage reporting"
            echo "  -v, --verbose       Verbose output"
            echo "  -p, --parallel      Run tests in parallel"
            echo "  -h, --help          Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_ARGS=()

if [ "$COVERAGE" = true ]; then
    PYTEST_ARGS+=(--cov=src --cov-report=term-missing --cov-report=html)
fi

if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS+=(-v)
fi

if [ "$PARALLEL" = true ]; then
    PYTEST_ARGS+=(-n auto)
fi

# Function to run specific test types
run_unit_tests() {
    echo "🔬 Running Unit Tests..."
    pytest tests/unit/ "${PYTEST_ARGS[@]}" -m "unit"
}

run_integration_tests() {
    echo "🔗 Running Integration Tests..."
    echo "Starting test services..."
    docker-compose -f docker-compose.test.yml up -d postgres-test redis-test weaviate-test
    
    # Wait for services
    sleep 30
    
    pytest tests/integration/ "${PYTEST_ARGS[@]}" -m "integration"
    
    echo "Stopping test services..."
    docker-compose -f docker-compose.test.yml down
}

run_e2e_tests() {
    echo "🌐 Running E2E Tests..."
    echo "Starting full test environment..."
    docker-compose -f docker-compose.test.yml up -d
    
    # Wait for all services
    sleep 60
    
    docker-compose -f docker-compose.test.yml exec -T api-test \
        pytest tests/e2e/ "${PYTEST_ARGS[@]}" -m "e2e and not slow"
    
    echo "Stopping test environment..."
    docker-compose -f docker-compose.test.yml down
}

run_performance_tests() {
    echo "⚡ Running Performance Tests..."
    docker-compose -f docker-compose.test.yml up -d
    sleep 60
    
    docker-compose -f docker-compose.test.yml exec -T api-test \
        pytest tests/e2e/test_performance.py "${PYTEST_ARGS[@]}" -m "slow"
    
    docker-compose -f docker-compose.test.yml down
}

# Execute based on test type
case $TEST_TYPE in
    unit)
        run_unit_tests
        ;;
    integration)
        run_integration_tests
        ;;
    e2e)
        run_e2e_tests
        ;;
    performance)
        run_performance_tests
        ;;
    all)
        run_unit_tests
        run_integration_tests
        run_e2e_tests
        ;;
    *)
        echo "❌ Invalid test type: $TEST_TYPE"
        exit 1
        ;;
esac

echo "✅ Tests completed successfully!"

# Generate coverage report if enabled
if [ "$COVERAGE" = true ] && [ "$TEST_TYPE" != "performance" ]; then
    echo "📊 Coverage Report:"
    echo "==================="
    coverage report --show-missing
    echo ""
    echo "📄 HTML coverage report generated in htmlcov/"
fi
```

## 7. Coverage Targets and Quality Gates

### 7.1 Coverage Configuration

**Updated pytest.ini**:
```ini
[tool:pytest]
minversion = 6.0
addopts = 
    -ra 
    -q 
    --strict-markers
    --strict-config
    --cov=src
    --cov-report=term-missing:skip-covered
    --cov-report=html:htmlcov
    --cov-report=xml
    --cov-fail-under=85
    --disable-warnings
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    e2e: marks tests as end-to-end tests
    requires_api_keys: marks tests that require real API keys
    requires_db: marks tests that require database connection
    performance: marks tests as performance tests
filterwarnings =
    ignore::UserWarning
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
asyncio_mode = auto
```

### 7.2 Quality Gates

**Coverage Targets by Component**:
- **Agents Core Logic**: 90% minimum
- **Database Models**: 85% minimum  
- **API Endpoints**: 95% minimum
- **External API Clients**: 80% minimum (due to mocking complexity)
- **Utility Functions**: 95% minimum
- **Overall Project**: 85% minimum

**Quality Gates Checklist**:
```python
# scripts/quality_gates.py
import subprocess
import sys
from pathlib import Path

class QualityGate:
    """Quality gate validation for CI/CD."""
    
    def __init__(self):
        self.failures = []
    
    def check_coverage(self, min_coverage: float = 85.0) -> bool:
        """Check test coverage meets minimum threshold."""
        try:
            result = subprocess.run(
                ["coverage", "report", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )
            
            import json
            coverage_data = json.loads(result.stdout)
            total_coverage = coverage_data["totals"]["percent_covered"]
            
            if total_coverage < min_coverage:
                self.failures.append(
                    f"Coverage {total_coverage:.1f}% below minimum {min_coverage}%"
                )
                return False
            
            print(f"✅ Coverage: {total_coverage:.1f}% (target: {min_coverage}%)")
            return True
            
        except subprocess.CalledProcessError as e:
            self.failures.append(f"Coverage check failed: {e}")
            return False
    
    def check_security(self) -> bool:
        """Run security checks."""
        try:
            # Run bandit
            subprocess.run(["bandit", "-r", "src", "-f", "json"], check=True)
            
            # Run safety
            subprocess.run(["safety", "check"], check=True)
            
            print("✅ Security checks passed")
            return True
            
        except subprocess.CalledProcessError:
            self.failures.append("Security checks failed")
            return False
    
    def check_code_quality(self) -> bool:
        """Check code quality standards."""
        checks = [
            (["black", "--check", "src", "tests"], "Black formatting"),
            (["isort", "--check-only", "src", "tests"], "Import sorting"),
            (["ruff", "check", "src", "tests"], "Ruff linting"),
            (["mypy", "src"], "Type checking")
        ]
        
        all_passed = True
        
        for cmd, name in checks:
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                print(f"✅ {name} passed")
            except subprocess.CalledProcessError:
                self.failures.append(f"{name} failed")
                all_passed = False
        
        return all_passed
    
    def check_test_results(self) -> bool:
        """Validate test results."""
        # Check for test result files
        unit_results = Path("junit-unit.xml")
        integration_results = Path("junit-integration.xml")
        
        if not unit_results.exists():
            self.failures.append("Unit test results missing")
            return False
        
        if not integration_results.exists():
            self.failures.append("Integration test results missing")
            return False
        
        # Parse test results (simplified)
        print("✅ Test result files present")
        return True
    
    def run_all_checks(self) -> bool:
        """Run all quality gate checks."""
        print("🚪 Running Quality Gates")
        print("=" * 40)
        
        checks = [
            self.check_code_quality,
            self.check_security, 
            self.check_coverage,
            self.check_test_results
        ]
        
        all_passed = True
        for check in checks:
            if not check():
                all_passed = False
        
        if self.failures:
            print("\n❌ Quality Gate Failures:")
            for failure in self.failures:
                print(f"  - {failure}")
        
        return all_passed

if __name__ == "__main__":
    gate = QualityGate()
    success = gate.run_all_checks()
    
    if success:
        print("\n🎉 All quality gates passed!")
        sys.exit(0)
    else:
        print("\n💥 Quality gates failed!")
        sys.exit(1)
```

## 8. Monitoring and Metrics

### 8.1 Test Metrics Collection

```python
# tests/conftest.py (additional fixtures)
import time
import pytest
from collections import defaultdict

# Global test metrics
test_metrics = defaultdict(list)

@pytest.fixture(autouse=True)
def track_test_performance(request):
    """Automatically track test execution time."""
    start_time = time.time()
    
    yield
    
    execution_time = time.time() - start_time
    test_name = request.node.name
    test_file = request.node.fspath.basename
    
    test_metrics["execution_times"].append({
        "test": test_name,
        "file": test_file,
        "duration": execution_time
    })

@pytest.fixture(scope="session", autouse=True)
def report_test_metrics():
    """Report test metrics at end of session."""
    yield
    
    # Generate test performance report
    if test_metrics["execution_times"]:
        times = [t["duration"] for t in test_metrics["execution_times"]]
        
        print(f"\n📊 Test Performance Summary:")
        print(f"Total tests: {len(times)}")
        print(f"Average execution time: {sum(times)/len(times):.3f}s")
        print(f"Slowest test: {max(times):.3f}s")
        print(f"Fastest test: {min(times):.3f}s")
        
        # Report slowest tests
        slow_tests = sorted(
            test_metrics["execution_times"], 
            key=lambda x: x["duration"], 
            reverse=True
        )[:5]
        
        print(f"\n🐌 Slowest Tests:")
        for test in slow_tests:
            print(f"  {test['test']}: {test['duration']:.3f}s")
```

### 8.2 Continuous Monitoring

```yaml
# monitoring/test-monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - ./grafana/dashboard.yml:/etc/grafana/provisioning/dashboards/dashboard.yml
      - ./grafana/datasource.yml:/etc/grafana/provisioning/datasources/datasource.yml
```

## 9. Implementation Roadmap

### Phase 1: Foundation (Week 1)
- [ ] Set up unit test framework and fixtures
- [ ] Implement base agent testing patterns
- [ ] Create mock strategies for external APIs
- [ ] Configure pytest and coverage reporting

### Phase 2: Core Testing (Week 2-3)
- [ ] Complete unit tests for all 6 agents
- [ ] Implement database integration tests
- [ ] Set up vector database testing
- [ ] Create comprehensive test data factories

### Phase 3: System Testing (Week 4)
- [ ] Implement end-to-end workflow tests
- [ ] Set up performance testing suite
- [ ] Configure CI/CD pipeline
- [ ] Implement quality gates

### Phase 4: Advanced Testing (Week 5)
- [ ] Load testing and stress testing
- [ ] Security testing integration
- [ ] Chaos engineering tests
- [ ] Production monitoring setup

## 10. Best Practices and Guidelines

### Testing Best Practices
1. **Test Naming**: Use descriptive test names that explain the scenario
2. **Arrange-Act-Assert**: Structure tests clearly with setup, execution, and verification
3. **Single Responsibility**: Each test should verify one specific behavior  
4. **Test Independence**: Tests should not depend on each other's state
5. **Fast Feedback**: Prioritize fast unit tests over slow integration tests

### Agent-Specific Guidelines
1. **Mock External Dependencies**: Always mock external API calls in unit tests
2. **Test Error Scenarios**: Verify error handling and retry logic
3. **Validate Metrics**: Ensure agent metrics are updated correctly
4. **Test Concurrency**: Validate thread-safe operations and async behavior
5. **Resource Cleanup**: Ensure proper cleanup of resources in tests

### Performance Testing Guidelines
1. **Baseline Establishment**: Establish performance baselines for all critical operations
2. **Realistic Load**: Use realistic data volumes and user patterns
3. **Resource Monitoring**: Monitor CPU, memory, and I/O during tests
4. **Gradual Load Increase**: Implement gradual load testing to find breaking points
5. **Environment Consistency**: Maintain consistent test environments

This comprehensive testing strategy provides a solid foundation for ensuring the reliability, performance, and maintainability of the ReAgent Sydney system. The strategy covers all critical aspects from unit testing to production monitoring, with specific focus on the multi-agent architecture and real estate domain requirements.