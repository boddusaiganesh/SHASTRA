from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.investigation_service import (
    create_investigation, list_investigations, get_investigation,
    update_investigation, delete_investigation,
)

router = APIRouter()


class SaveInvestigationRequest(BaseModel):
    title: str
    notes: Optional[str] = None
    filters: Dict[str, Any] = {}
    board_state: Dict[str, Any] = {}
    district_id: Optional[str] = None


@router.post("")
async def save_investigation(
    payload: SaveInvestigationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await create_investigation(db, payload.model_dump(), str(current_user["user_id"]))
    return {"success": True, "data": data}


@router.get("")
async def get_investigations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await list_investigations(db, str(current_user["user_id"]), page, page_size)
    return {"success": True, "data": data}


@router.get("/{investigation_id}")
async def get_investigation_detail(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_investigation(db, investigation_id, str(current_user["user_id"]))
    if not data:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {"success": True, "data": data}


@router.put("/{investigation_id}")
async def update_investigation_endpoint(
    investigation_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await update_investigation(db, investigation_id, payload, str(current_user["user_id"]))
    if not data:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {"success": True, "data": data}


@router.delete("/{investigation_id}")
async def delete_investigation_endpoint(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ok = await delete_investigation(db, investigation_id, str(current_user["user_id"]))
    if not ok:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {"success": True}
