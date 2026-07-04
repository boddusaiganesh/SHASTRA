from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
import uuid

async def log_action(
    db: AsyncSession, 
    user_id: str, 
    action: str, 
    resource_type: str, 
    resource_id: str, 
    details: Optional[Dict[str, Any]] = None
):
    from app.models.database_models.audit_log_model import AuditLog
    
    try:
        user_uuid = uuid.UUID(user_id) if user_id else None
    except ValueError:
        user_uuid = None
        
    entry = AuditLog(
        log_id=uuid.uuid4(), 
        user_id=user_uuid, 
        action=action,
        resource_type=resource_type, 
        resource_id=str(resource_id), 
        details=details or {},
    )
    db.add(entry)
    await db.commit()
