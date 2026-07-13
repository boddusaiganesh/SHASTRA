"""Saved Investigation Service — create/list/load/update/delete case boards."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional, Dict, Any
import uuid

from app.models.database_models.investigation_model import SavedInvestigation


async def create_investigation(db: AsyncSession, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    inv = SavedInvestigation(
        title=data["title"],
        notes=data.get("notes"),
        filters=data.get("filters", {}),
        board_state=data.get("board_state", {}),
        district_id=data.get("district_id"),
        created_by=uuid.UUID(user_id),
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv.to_dict()


async def list_investigations(db: AsyncSession, user_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    base = select(SavedInvestigation).where(SavedInvestigation.created_by == uuid.UUID(user_id))
    count_result = await db.execute(select(func.count(SavedInvestigation.investigation_id)).where(SavedInvestigation.created_by == uuid.UUID(user_id)))
    total = count_result.scalar() or 0

    stmt = base.order_by(desc(SavedInvestigation.updated_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "investigations": [r.to_dict() for r in rows],
        "total_count": total,
        "page": page,
        "page_size": page_size,
    }


async def get_investigation(db: AsyncSession, investigation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    try:
        inv_uuid = uuid.UUID(investigation_id)
    except ValueError:
        return None
    result = await db.execute(
        select(SavedInvestigation).where(
            SavedInvestigation.investigation_id == inv_uuid,
            SavedInvestigation.created_by == uuid.UUID(user_id),
        )
    )
    inv = result.scalar_one_or_none()
    return inv.to_dict() if inv else None


async def update_investigation(db: AsyncSession, investigation_id: str, data: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
    try:
        inv_uuid = uuid.UUID(investigation_id)
    except ValueError:
        return None
    result = await db.execute(
        select(SavedInvestigation).where(
            SavedInvestigation.investigation_id == inv_uuid,
            SavedInvestigation.created_by == uuid.UUID(user_id),
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        return None
    for field in ("title", "notes", "filters", "board_state"):
        if field in data:
            setattr(inv, field, data[field])
    await db.commit()
    await db.refresh(inv)
    return inv.to_dict()


async def delete_investigation(db: AsyncSession, investigation_id: str, user_id: str) -> bool:
    try:
        inv_uuid = uuid.UUID(investigation_id)
    except ValueError:
        return False
    result = await db.execute(
        select(SavedInvestigation).where(
            SavedInvestigation.investigation_id == inv_uuid,
            SavedInvestigation.created_by == uuid.UUID(user_id),
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        return False
    await db.delete(inv)
    await db.commit()
    return True
