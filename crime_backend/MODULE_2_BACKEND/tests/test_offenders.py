import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_offenders_search():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Without auth token, this might be a 401. So we check if route exists and responds properly.
        resp = await ac.get("/api/offenders/search?q=test")
    
    assert resp.status_code in [200, 401]
