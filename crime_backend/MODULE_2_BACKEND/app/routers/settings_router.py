from fastapi import APIRouter, Depends, Query, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.auth_service import get_user_by_id, get_all_users, create_user

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

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_all_users(db)
    return {"success": True, "data": data}

@router.post("/users/add")
async def add_user(
    user_data: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    new_user = await create_user(db, user_data)
    return {"success": True, "data": new_user}

@router.get("/alert-thresholds")
async def get_alert_thresholds(current_user=Depends(get_current_user)):
    # Return defaults; store in DB or config in production
    return {"success": True, "data": {
        "crime_spike_percent": 200,
        "anomaly_confidence": 75,
        "high_risk_score": 80
    }}

@router.put("/alert-thresholds")
async def update_alert_thresholds(
    thresholds: dict = Body(...),
    current_user=Depends(get_current_user)
):
    return {"success": True, "data": thresholds}
