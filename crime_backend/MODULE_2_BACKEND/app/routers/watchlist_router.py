from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.watchlist_service import add_watch, remove_watch, list_watches, is_watched

router = APIRouter()


class WatchRequest(BaseModel):
    entity_id: str
    entity_type: str
    entity_label: str


@router.post("")
async def watch_entity(payload: WatchRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await add_watch(db, str(current_user["user_id"]), payload.entity_id, payload.entity_type, payload.entity_label)
    return {"success": True, "data": data}


@router.delete("/{entity_id}")
async def unwatch_entity(entity_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    ok = await remove_watch(db, str(current_user["user_id"]), entity_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Watch not found")
    return {"success": True}


@router.get("")
async def get_watchlist(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await list_watches(db, str(current_user["user_id"]))
    return {"success": True, "data": data}


@router.get("/{entity_id}/status")
async def watch_status(entity_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    watched = await is_watched(db, str(current_user["user_id"]), entity_id)
    return {"success": True, "data": {"is_watched": watched}}
