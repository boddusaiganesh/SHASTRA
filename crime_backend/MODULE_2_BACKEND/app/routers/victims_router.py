from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.services.victim_service import search_victims, create_victim, get_victim_profile

router = APIRouter()


@router.get("/search")
async def search(
    q: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Apply district scoping if DISTRICT_OFFICER
    if current_user["role"] == "DISTRICT_OFFICER":
        user_district = current_user.get("district_id")
        if district_id and district_id != user_district:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. District officers can only access their own district data."
            )
        district_id = user_district

    data = await search_victims(db, q, district_id)
    return {"success": True, "data": data}


@router.get("/{victim_id}/profile")
async def profile(victim_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_victim_profile(db, victim_id)
    if not data:
        raise HTTPException(status_code=404, detail="Victim not found")
        
    # Check district authorization for DISTRICT_OFFICER
    if current_user["role"] == "DISTRICT_OFFICER" and data.get("district_id") != current_user.get("district_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    return {"success": True, "data": data}


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_victim(payload: dict, db: AsyncSession = Depends(get_db), current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"]))):
    from app.utils.audit import log_action

    if current_user["role"] == "DISTRICT_OFFICER":
        payload["district_id"] = current_user.get("district_id")
    
    data = await create_victim(db, payload)
    await log_action(db, current_user["user_id"], "CREATE", "VICTIM", data.get("victim_id"), payload)
    return {"success": True, "data": data}
