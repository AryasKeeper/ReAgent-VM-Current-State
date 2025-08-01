import pytest
from httpx import AsyncClient
from src.api.main import app

@pytest.mark.asyncio
async def test_get_listings():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/listings")
    assert response.status_code == 200
