from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, scope_district_param
from app.utils.district_resolver import resolve_district_id
from app.services.anomaly_service import get_anomaly_list, get_anomaly_detail, update_anomaly_status

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/list")
@limiter.limit("30/minute")
async def get_anomalies(
    request: Request,
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_anomaly_list(db, severity, status, district_id, page=page, page_size=page_size)
    return {"success": True, "data": data}

@router.get("/detail/{anomaly_id}")
@limiter.limit("30/minute")
async def anomaly_detail(request: Request, anomaly_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_anomaly_detail(db, anomaly_id)
    if not data:
        raise HTTPException(status_code=404, detail="Anomaly not found")
        
    if current_user["role"] == "DISTRICT_OFFICER" and data.get("district_id") != current_user.get("district_id"):
        from fastapi import status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    return {"success": True, "data": data}

@router.patch("/update-status/{anomaly_id}")
@limiter.limit("30/minute")
async def update_status(
    request: Request,
    anomaly_id: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Fetch detail first to check authorization
    data_check = await get_anomaly_detail(db, anomaly_id)
    if not data_check:
        raise HTTPException(status_code=404, detail="Anomaly not found")
        
    if current_user["role"] == "DISTRICT_OFFICER" and data_check.get("district_id") != current_user.get("district_id"):
        from fastapi import status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    data = await update_anomaly_status(
        db, anomaly_id, body.get("status"), body.get("assigned_officer"), body.get("notes")
    )
    return {"success": True, "data": data}
