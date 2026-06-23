from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.utils.district_resolver import resolve_district_id
from app.services.network_service import get_network_graph_data, get_node_detail, get_network_ai_summary

router = APIRouter()

@router.get("/graph")            
@router.get("/graph-data")
async def fetch_network_graph(
    search_query: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    data = await get_network_graph_data(db, search_query, crime_type, resolved_id)
    return {"success": True, "data": data}

@router.get("/node-detail/{node_id}")
async def fetch_node_detail(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_node_detail(db, node_id)
    if not data:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"success": True, "data": data}

@router.get("/ai-summary")
async def fetch_ai_summary(
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    data = await get_network_ai_summary(db, resolved_id)
    return {"success": True, "data": data}

