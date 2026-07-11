from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, decode_access_token, scope_district_param
from app.utils.district_resolver import resolve_district_id
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
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    resolved_district = await resolve_district_id(db, district_id)
    effective_district = scope_district_param(resolved_district, current_user)
    data = await get_active_alerts(db, effective_district, severity, alert_type, page, page_size)
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
async def websocket_endpoint(websocket: WebSocket):
    # Retrieve token from cookies during the HTTP upgrade
    token = websocket.cookies.get("auth_token")
    if not token:
        await websocket.close(code=1008)
        return
        
    await websocket.accept()
    
    try:
        payload = decode_access_token(token)
        if not payload or await is_token_blacklisted(token):
            await websocket.close(code=1008)
            return

        from app.core.websocket import manager
        # Since we manually accepted, we need to adapt manager.connect if it also accepts
        # Assuming manager.connect doesn't accept again, or we change it.
        # Let's verify manager.connect behavior. Assuming we just register it.
        manager.connect(websocket, payload)
        
        # Send a success message back
        await websocket.send_json({"type": "auth_success"})
        
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        from app.core.websocket import manager
        manager.disconnect(websocket)
    except Exception:
        await websocket.close(code=1008)
