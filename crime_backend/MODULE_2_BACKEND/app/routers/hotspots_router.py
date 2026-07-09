from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, scope_district_param
from app.utils.district_resolver import resolve_district_id
from app.services.hotspot_service import (
    get_hotspot_clusters,
    get_time_patterns,
    get_top_hotspots,
    get_deployment_suggestions,
)

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/clusters")
@limiter.limit("30/minute")
async def hotspot_clusters(
    request: Request,
    district_id: Optional[str] = Query(None),
    file_format: str = Query("json", enum=["json", "csv"]),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_hotspot_clusters(db, resolved_id)
    
    if file_format == "csv":
        import csv
        from io import StringIO
        from fastapi.responses import StreamingResponse
        
        output = StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
            writer.writeheader()
            writer.writerows(data)
            
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="hotspots_export.csv"'}
        )
        
    return {"success": True, "data": data}

@router.get("/time-patterns")
@limiter.limit("30/minute")
async def time_patterns(
    request: Request,
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_time_patterns(db, resolved_id, crime_type)
    return {"success": True, "data": data}

@router.get("/top-list")
@limiter.limit("30/minute")
async def top_hotspots(
    request: Request,
    district_id: Optional[str] = Query(None),
    limit: int = Query(10),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_top_hotspots(db, limit, resolved_id)
    return {"success": True, "data": data}

@router.get("/deployment-suggestions")
@limiter.limit("30/minute")
async def deployment_suggestions(
    request: Request,
    district_id: Optional[str] = Query(None, description="Optional — district to generate deployment suggestions for"),
    target_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_deployment_suggestions(db, resolved_id, target_date)
    return {"success": True, "data": data}
