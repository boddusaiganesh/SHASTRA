from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, scope_district_param
from app.utils.district_resolver import resolve_district_id
from app.services.prediction_service import (
    get_risk_map,
    get_high_risk_areas,
    get_crime_forecast,
    get_emerging_typologies,
    get_socioeconomic_correlation,
)

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/risk-map")
@limiter.limit("30/minute")
async def risk_map(
    request: Request,
    district_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db), 
    current_user=Depends(get_current_user)
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
        
    data = await get_risk_map(db, district_id=district_id, date_from=date_from, date_to=date_to)
    return {"success": True, "data": data}

@router.get("/high-risk-areas")
@limiter.limit("30/minute")
async def high_risk_areas(
    request: Request,
    district_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    days_ahead: int = Query(7, le=30),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_high_risk_areas(db, days_ahead, district_id, date_from=date_from, date_to=date_to)
    return {"success": True, "data": data}

@router.get("/forecast")
@limiter.limit("30/minute")
async def forecast(
    request: Request,
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    days_ahead: int = Query(30, le=90),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_crime_forecast(db, district_id, crime_type, days_ahead, date_from=date_from, date_to=date_to)
    return {"success": True, "data": data}

@router.get("/emerging-typologies")
@limiter.limit("30/minute")
async def emerging_typologies(
    request: Request,
    district_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_emerging_typologies(db, district_id, date_from=date_from, date_to=date_to)
    return {"success": True, "data": data}

@router.get("/socioeconomic-correlation")
@limiter.limit("30/minute")
async def socioeconomic_correlation(
    request: Request,
    district_id: Optional[str] = Query(None),
    factor: str = Query("all"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_socioeconomic_correlation(db, district_id, factor)
    return {"success": True, "data": data}
