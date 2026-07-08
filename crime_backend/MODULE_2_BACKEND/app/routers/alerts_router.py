from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, decode_access_token, scope_district_param
from app.core.redis_connection import is_token_blacklisted
from app.services.alert_service import (
    get_active_alerts,
    mark_alert_read,
    dismiss_alert
)

router = APIRouter()

@router.get("/active")
async def active_alerts(
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    effective_district = scope_district_param(district_id, current_user)
    data = await get_active_alerts(db, effective_district)
    return {"success": True, "data": data}

@router.put("/{alert_id}/read")
async def mark_read(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await mark_alert_read(db, alert_id, current_user.get("user_id"))
    return {"success": True, "data": data}

@router.delete("/{alert_id}")
async def dismiss(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await dismiss_alert(db, alert_id)
    return {"success": True, "data": data}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    payload = decode_access_token(token)
    if not payload or await is_token_blacklisted(token):
        await websocket.close(code=1008)
        return

    from app.core.websocket import manager
    await manager.connect(websocket, payload)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
