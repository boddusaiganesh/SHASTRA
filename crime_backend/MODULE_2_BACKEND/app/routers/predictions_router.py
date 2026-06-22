from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.prediction_service import (
    get_risk_map,
    get_high_risk_areas,
    get_crime_forecast,
    get_emerging_typologies,
    get_socioeconomic_correlation,
)

router = APIRouter()

@router.get("/risk-map")
async def risk_map(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_risk_map(db)
    return {"success": True, "data": data}

@router.get("/high-risk-areas")
async def high_risk_areas(
    district_id: Optional[str] = Query(None),
    days_ahead: int = Query(7, le=30),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_high_risk_areas(db, days_ahead, district_id)
    return {"success": True, "data": data}

@router.get("/forecast")
async def forecast(
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    days_ahead: int = Query(30, le=90),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_crime_forecast(db, district_id, crime_type, days_ahead)
    return {"success": True, "data": data}

@router.get("/emerging-typologies")
async def emerging_typologies(
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_emerging_typologies(db, district_id)
    return {"success": True, "data": data}

@router.get("/socioeconomic-correlation")
async def socioeconomic_correlation(
    district_id: Optional[str] = Query(None),
    factor: str = Query("all"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_socioeconomic_correlation(db, district_id, factor)
    return {"success": True, "data": data}
