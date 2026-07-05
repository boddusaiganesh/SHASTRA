import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_anomalies_list_auth():
    """
    Test that the anomalies list endpoint is protected.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/anomalies/list")
    
    assert resp.status_code in [401, 403]
    assert "detail" in resp.json()
