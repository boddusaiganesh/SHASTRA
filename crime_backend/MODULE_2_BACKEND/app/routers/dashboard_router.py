from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.dashboard_service import (
    get_dashboard_summary,
    get_crime_trends,
    get_recent_crimes,
    get_recent_alerts,
)

router = APIRouter()

@router.get("/summary")
async def dashboard_summary(
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user["role"] == "DISTRICT_OFFICER":
        district_id = current_user.get("district_id")
    data = await get_dashboard_summary(db, district_id)
    return {"success": True, "data": data}

@router.get("/crime-trends")
async def crime_trends(
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user["role"] == "DISTRICT_OFFICER":
        district_id = current_user.get("district_id")
    data = await get_crime_trends(db, district_id)
    return {"success": True, "data": data}

@router.get("/recent-crimes")
async def recent_crimes(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    district_id = current_user.get("district_id") if current_user["role"] == "DISTRICT_OFFICER" else None
    data = await get_recent_crimes(db, limit, district_id)
    return {"success": True, "data": data}

@router.get("/recent-alerts")
async def recent_alerts(
    limit: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    district_id = current_user.get("district_id") if current_user["role"] == "DISTRICT_OFFICER" else None
    data = await get_recent_alerts(db, limit, district_id)
    return {"success": True, "data": data}
