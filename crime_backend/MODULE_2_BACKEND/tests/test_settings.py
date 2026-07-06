import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_settings_districts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/settings/districts")
    assert response.status_code in (200, 401, 403)
    if response.status_code == 200:
        data = response.json()
        assert "data" in data or isinstance(data, list)
    
@pytest.mark.asyncio
async def test_settings_sync():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/settings/sync", json={"source_id": "neo4j"})
    assert response.status_code in (200, 400, 401, 403, 404, 503)
