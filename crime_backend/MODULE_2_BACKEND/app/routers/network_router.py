from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.security import get_current_user, scope_district_param
from app.utils.district_resolver import resolve_district_id
from app.services.network_service import get_network_graph_data, get_node_detail, get_network_ai_summary

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/graph")            
@router.get("/graph-data")
@limiter.limit("30/minute")
async def fetch_network_graph(
    request: Request,
    search_query: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_graph_data(db, search_query, crime_type, resolved_id)
    return {"success": True, "data": data}

@router.get("/node-detail/{node_id}")
@limiter.limit("30/minute")
async def fetch_node_detail(
    request: Request,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_node_detail(db, node_id)
    if not data:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"success": True, "data": data}

@router.get("/ai-summary")
@limiter.limit("5/minute")
async def fetch_ai_summary(
    request: Request,
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_ai_summary(db, resolved_id)
    return {"success": True, "data": data}

@router.get("/shortest-path")
@limiter.limit("10/minute")
async def shortest_path(
    request: Request,
    node_a: str = Query(...),
    node_b: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.core.neo4j_connection import find_shortest_path
    data = await find_shortest_path(node_a, node_b)
    return {"success": True, "data": data}

@router.get("/expand/{node_id}")
@limiter.limit("20/minute")
async def expand_node(
    request: Request,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return only the immediate neighbors of one node — for incremental graph expansion."""
    from app.core.neo4j_connection import run_neo4j_query
    query = """
    MATCH (n)-[r]-(connected)
    WHERE n.offender_id = $id OR n.victim_id = $id OR n.location_id = $id OR n.org_id = $id
    RETURN connected, labels(connected) AS labels, type(r) AS rel_type, r
    LIMIT 25
    """
    results = await run_neo4j_query(query, {"id": node_id})
    return {"success": True, "data": results}

