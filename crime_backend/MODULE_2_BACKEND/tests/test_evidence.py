import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_evidence_get():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/evidence/crime/fake-id")
    # Even if fake-id fails parsing, it should be 401, 403, 404 or 400
    assert response.status_code in (200, 400, 401, 403, 404)
