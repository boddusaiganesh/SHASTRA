import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from main import app
from app.core.database import get_db

@pytest.mark.asyncio
async def test_auth_login_fail():
    async def override_get_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/auth/login", json={"username": "invalid_user", "password": "wrongpassword"})
        
        # Should fail for invalid credentials
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_login_admin_fail():
    async def override_get_db():
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/auth/login", json={"username": "admin", "password": "securepassword"})
        
        # Should fail because hardcoded bypass is removed
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
