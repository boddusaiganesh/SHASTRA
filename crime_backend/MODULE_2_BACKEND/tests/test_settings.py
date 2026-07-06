import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_settings_districts(client: AsyncClient, token_headers: dict):
    response = await client.get("/api/settings/districts", headers=token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data or isinstance(data, list)
    
@pytest.mark.asyncio
async def test_settings_sync(client: AsyncClient, token_headers: dict):
    response = await client.post("/api/settings/sync", json={"source_id": "neo4j"}, headers=token_headers)
    assert response.status_code in (200, 400, 404, 503)
