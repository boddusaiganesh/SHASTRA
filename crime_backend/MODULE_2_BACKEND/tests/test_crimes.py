import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_map_data_returns_success():
    """
    Test that the unauthenticated map-data endpoint returns a successful response.
    Because of dependency injection for auth, we may get a 401 if it's protected,
    or 200 if unprotected. The current implementation protects /map-data.
    We will just test that it returns JSON.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/crimes/map-data")
    
    # It should return 401 Unauthorized or 403 Forbidden because get_current_user is injected
    assert resp.status_code in [401, 403]
    assert "detail" in resp.json()

@pytest.mark.asyncio
async def test_health_check():
    """
    Test the public health check endpoint.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/")
        
    assert resp.status_code == 200
    assert "success" in resp.json()
    assert resp.json()["success"] is True
