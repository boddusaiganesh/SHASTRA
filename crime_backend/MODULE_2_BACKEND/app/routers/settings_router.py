from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, require_scrb_officer
from app.services.auth_service import get_user_by_id, get_all_users, create_user
from app.models.database_models.system_settings_model import SystemSettings
from app.models.database_models.crime_model import District

router = APIRouter()

@router.get("/profile")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_user_by_id(db, current_user["user_id"])
    if not data:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "data": data}

@router.post("/datasources/{source_id}/sync")
async def sync_datasource(source_id: str):
    from app.services.settings_service import trigger_sync
    result = await trigger_sync(source_id)
    return {"success": True, "data": result}

@router.get("/audit-logs")
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_scrb_officer)
):
    from sqlalchemy import select, desc
    from app.models.database_models.audit_log_model import AuditLog
    
    result = await db.execute(
        select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(100)
    )
    logs = result.scalars().all()
    
    return {
        "success": True,
        "data": [
            {
                "log_id": str(log.log_id),
                "user_id": str(log.user_id) if log.user_id else None,
                "action": log.action,
                "resource_id": log.resource_id,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None
            }
            for log in logs
        ]
    }

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_scrb_officer)
):
    data = await get_all_users(db)
    return {"success": True, "data": data}

@router.post("/users/add")
async def add_user(
    user_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_scrb_officer)
):
    new_user = await create_user(db, user_data)
    return {"success": True, "data": new_user}

@router.get("/alert-thresholds")
async def get_alert_thresholds(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    row = result.scalar_one_or_none()
    if not row:
        row = SystemSettings(id=1)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return {"success": True, "data": row.to_dict()}

@router.put("/alert-thresholds")
async def update_alert_thresholds(
    thresholds: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_scrb_officer)
):
    result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    row = result.scalar_one_or_none() or SystemSettings(id=1)
    for key in ("crime_spike_percent", "anomaly_confidence", "high_risk_score"):
        if key in thresholds:
            setattr(row, key, thresholds[key])
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"success": True, "data": row.to_dict()}

@router.get("/districts")
async def list_districts(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = await db.execute(select(District).order_by(District.district_name))
    districts = result.scalars().all()
    return {"success": True, "data": [d.to_dict() for d in districts]}
