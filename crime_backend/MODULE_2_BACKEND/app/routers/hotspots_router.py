from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.hotspot_service import (
    get_hotspot_clusters,
    get_time_patterns,
    get_top_hotspots,
    get_deployment_suggestions,
)

router = APIRouter()

@router.get("/clusters")
async def hotspot_clusters(
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_hotspot_clusters(db, district_id)
    return {"success": True, "data": data}

@router.get("/time-patterns")
async def time_patterns(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_time_patterns(db)
    return {"success": True, "data": data}

@router.get("/top-list")
async def top_hotspots(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_top_hotspots(db)
    return {"success": True, "data": data}

@router.get("/deployment-suggestions")
async def deployment_suggestions(
    district_id: str = Query(..., description="Required — district to generate deployment suggestions for"),
    target_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_deployment_suggestions(db, district_id, target_date)
    return {"success": True, "data": data}
