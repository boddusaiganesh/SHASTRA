import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_evidence_get(client: AsyncClient, token_headers: dict):
    response = await client.get("/api/evidence/crime/fake-id", headers=token_headers)
    # Even if fake-id fails parsing, it should be 400 or 200 with empty list, not 500
    assert response.status_code in (200, 400)
