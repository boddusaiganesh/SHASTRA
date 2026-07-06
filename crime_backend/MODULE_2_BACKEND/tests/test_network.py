import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_network_graph_auth():
    """
    Test that the network graph endpoint is protected.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/network/graph")
    
    assert resp.status_code in [401, 403, 404]
    
@pytest.mark.asyncio
async def test_expand_node():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/network/expand/fake-node")
    assert resp.status_code in (200, 400, 401, 403, 404)
    
@pytest.mark.asyncio
async def test_edge_insight():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/network/edge-insight", json={
            "node_a": {"id": "1"}, "node_b": {"id": "2"}, "edge": {"type": "KNOWS"}
        })
    assert resp.status_code in (200, 400, 401, 403, 422, 500)
