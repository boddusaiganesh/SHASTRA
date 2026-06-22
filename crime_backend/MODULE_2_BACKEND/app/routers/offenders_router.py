from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.offender_service import (
    search_offenders,
    get_offender_profile,
    get_offender_network,
    get_recidivism_risk
)

router = APIRouter()

@router.get("/search")
async def search(
    query: str = Query(..., min_length=3),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await search_offenders(db, query)
    return {"success": True, "data": data}

@router.get("/{offender_id}/profile")
async def profile(
    offender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_offender_profile(db, offender_id)
    return {"success": True, "data": data}

@router.get("/{offender_id}/network")
async def network(
    offender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_offender_network(db, offender_id)
    return {"success": True, "data": data}

@router.get("/{offender_id}/risk")
async def risk(
    offender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_recidivism_risk(db, offender_id)
    return {"success": True, "data": data}

@router.get("/{offender_id}/modus-operandi")
async def modus_operandi(
    offender_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from app.services.offender_service import get_modus_operandi
    data = await get_modus_operandi(db, offender_id)
    return {"success": True, "data": data}
