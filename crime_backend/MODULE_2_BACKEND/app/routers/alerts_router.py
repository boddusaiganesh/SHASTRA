from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
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
    data = await get_active_alerts(db, district_id)
    return {"success": True, "data": data}

@router.put("/{alert_id}/read")
async def mark_read(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await mark_alert_read(db, alert_id, current_user["user_id"])
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
async def websocket_endpoint(websocket: WebSocket):
    from app.core.websocket import manager
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
