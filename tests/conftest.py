"""Pytest configuration and fixtures for ReAgent Sydney tests."""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.settings import Settings
from src.core.database import get_db_session
from src.core.cache import CacheManager
from src.models.base import Base


# Test settings
@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        environment="test",
        debug=True,
        database__url="sqlite+aiosqlite:///:memory:",
        redis__url="redis://localhost:6379/15",  # Use different Redis DB for tests
        apis__openai_api_key="test-key",
        apis__domain_api_key="test-key",
        apis__rea_api_key="test-key",
    )


# Database fixtures
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture
def mock_db_session(monkeypatch):
    """Mock database session for unit tests."""
    mock_session = AsyncMock(spec=AsyncSession)
    
    async def mock_get_session():
        yield mock_session
    
    monkeypatch.setattr("src.core.database.get_db_session", mock_get_session)
    return mock_session


# Cache fixtures
@pytest_asyncio.fixture
async def cache_manager():
    """Create test cache manager."""
    cache = CacheManager()
    # Mock Redis client for tests
    cache.client = AsyncMock()
    return cache


@pytest.fixture
def mock_cache(monkeypatch):
    """Mock cache manager for unit tests."""
    mock_cache = AsyncMock(spec=CacheManager)
    monkeypatch.setattr("src.core.cache.cache", mock_cache)
    return mock_cache


# HTTP client fixtures
@pytest.fixture
def mock_httpx_client():
    """Mock HTTPX client for API calls."""
    return AsyncMock()


# Agent fixtures
@pytest.fixture
def mock_domain_client():
    """Mock Domain API client."""
    client = MagicMock()
    client.get_listings = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_rea_client():
    """Mock REA API client."""
    client = MagicMock()
    client.get_listings = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_weaviate_client():
    """Mock Weaviate client."""
    client = MagicMock()
    client.query = MagicMock()
    client.data_object = MagicMock()
    return client


# Sample data fixtures
@pytest.fixture
def sample_listing_data():
    """Sample listing data for tests."""
    return {
        "domain_id": "12345",
        "address": "123 Test Street, Sydney NSW 2000",
        "suburb": "Sydney",
        "postcode": "2000",
        "property_type": "apartment",
        "bedrooms": 2,
        "bathrooms": 1,
        "car_spaces": 1,
        "price": 800000,
        "price_display": "$800,000",
        "listing_date": "2025-07-28T10:00:00Z",
        "status": "active",
        "source": "domain",
        "description": "Modern apartment in the heart of Sydney",
        "raw_data": {"test": "data"}
    }


@pytest.fixture
def sample_buyer_data():
    """Sample buyer profile data for tests."""
    return {
        "name": "Test Buyer",
        "email": "test@example.com",
        "budget_min": 700000,
        "budget_max": 900000,
        "preferred_suburbs": ["Sydney", "Pyrmont"],
        "property_types": ["apartment", "townhouse"],
        "bedrooms_min": 2,
        "is_active": True,
        "urgency_level": "medium"
    }


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# FastAPI test client fixture
@pytest.fixture
def test_client(test_settings, mock_db_session, mock_cache):
    """Create FastAPI test client."""
    from fastapi.testclient import TestClient
    from src.api.main import app
    
    # Override dependencies
    app.dependency_overrides = {}
    
    return TestClient(app)


# Pytest markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", 
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "external_api: mark test as requiring external API access"
    )