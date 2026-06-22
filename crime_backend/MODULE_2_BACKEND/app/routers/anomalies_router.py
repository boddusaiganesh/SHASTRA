from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.anomaly_service import get_anomaly_list, get_anomaly_detail, update_anomaly_status

router = APIRouter()

@router.get("/")
@router.get("/list")
async def get_anomalies(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_anomaly_list(db, severity, status, district_id, page=page, page_size=page_size)
    return {"success": True, "data": data}

@router.get("/detail/{anomaly_id}")
async def anomaly_detail(anomaly_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_anomaly_detail(db, anomaly_id)
    if not data:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return {"success": True, "data": data}

@router.patch("/update-status/{anomaly_id}")
async def update_status(
    anomaly_id: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await update_anomaly_status(
        db, anomaly_id, body.get("status"), body.get("assigned_officer"), body.get("notes")
    )
    return {"success": True, "data": data}
