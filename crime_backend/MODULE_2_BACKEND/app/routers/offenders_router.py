from fastapi import APIRouter, Depends, Query, Body, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, require_role, scope_district_param
from app.utils.district_resolver import resolve_district_id
from app.services.offender_service import (
    search_offenders,
    get_offender_profile,
    get_offender_network,
    get_recidivism_risk
)

router = APIRouter()

@router.get("/search")
async def search(
    query: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    
    data = await search_offenders(
        db, 
        name=query if query else None,
        crime_type=crime_type,
        district_id=district_id,
        risk_level=risk_level,
        status=status,
        page=page,
        page_size=page_size
    )
    return {"success": True, "data": data}

@router.get("/{offender_id}/profile")
async def profile(
    offender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_offender_profile(db, offender_id)
    if not data:
        raise HTTPException(status_code=404, detail="Offender not found")
        
    if current_user["role"] == "DISTRICT_OFFICER" and data.get("district_id") != current_user.get("district_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    return {"success": True, "data": data}

@router.get("/{offender_id}/network")
async def network(
    offender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_offender_network(db, offender_id)
    # The network is tied to the offender, we verify via the offender profile
    profile_data = await get_offender_profile(db, offender_id)
    if profile_data and current_user["role"] == "DISTRICT_OFFICER" and profile_data.get("district_id") != current_user.get("district_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return {"success": True, "data": data}

@router.get("/{offender_id}/risk")
async def risk(
    offender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_recidivism_risk(db, offender_id)
    profile_data = await get_offender_profile(db, offender_id)
    if profile_data and current_user["role"] == "DISTRICT_OFFICER" and profile_data.get("district_id") != current_user.get("district_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return {"success": True, "data": data}

@router.get("/{offender_id}/modus-operandi")
async def modus_operandi(
    offender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from app.services.offender_service import get_modus_operandi
    data = await get_modus_operandi(db, offender_id)
    profile_data = await get_offender_profile(db, offender_id)
    if profile_data and current_user["role"] == "DISTRICT_OFFICER" and profile_data.get("district_id") != current_user.get("district_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return {"success": True, "data": data}

@router.post("", status_code=status.HTTP_201_CREATED)
async def add_offender(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"])),
):
    from app.services.offender_service import create_offender
    from app.utils.audit import log_action
    
    if current_user["role"] == "DISTRICT_OFFICER":
        payload["district_id"] = current_user.get("district_id")
    data = await create_offender(db, payload)
    
    await log_action(db, current_user["user_id"], "CREATE", "OFFENDER", data.get("offender_id"), payload)
    return {"success": True, "data": data}

@router.put("/{offender_id}")
async def edit_offender(
    offender_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"])),
):
    from app.services.offender_service import update_offender
    from app.utils.audit import log_action
    
    data = await update_offender(db, offender_id, payload)
    if not data:
        raise HTTPException(status_code=404, detail="Offender not found")
        
    await log_action(db, current_user["user_id"], "UPDATE", "OFFENDER", offender_id, payload)
    return {"success": True, "data": data}
