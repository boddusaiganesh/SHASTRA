import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_auth_login_fail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/auth/token", data={"username": "invalid_user", "password": "wrongpassword"})
    
    # Should fail for invalid credentials
    assert resp.status_code in [400, 401]
