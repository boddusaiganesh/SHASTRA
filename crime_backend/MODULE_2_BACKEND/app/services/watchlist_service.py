"""Watchlist Service — follow/unfollow entities, and detect new crimes involving watched entities."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timezone
from typing import Dict, Any
import uuid

from app.models.database_models.watchlist_model import WatchlistEntry


async def add_watch(db: AsyncSession, user_id: str, entity_id: str, entity_type: str, entity_label: str) -> Dict[str, Any]:
    existing = await db.execute(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == uuid.UUID(user_id),
            WatchlistEntry.entity_id == entity_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.is_active = True
        row.entity_label = entity_label
    else:
        row = WatchlistEntry(
            user_id=uuid.UUID(user_id), entity_id=entity_id,
            entity_type=entity_type, entity_label=entity_label,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row.to_dict()


async def remove_watch(db: AsyncSession, user_id: str, entity_id: str) -> bool:
    result = await db.execute(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == uuid.UUID(user_id),
            WatchlistEntry.entity_id == entity_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return False
    row.is_active = False
    await db.commit()
    return True


async def list_watches(db: AsyncSession, user_id: str) -> list[Dict[str, Any]]:
    result = await db.execute(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == uuid.UUID(user_id),
            WatchlistEntry.is_active.is_(True),
        )
    )
    return [r.to_dict() for r in result.scalars().all()]


async def is_watched(db: AsyncSession, user_id: str, entity_id: str) -> bool:
    result = await db.execute(
        select(WatchlistEntry).where(
            WatchlistEntry.user_id == uuid.UUID(user_id),
            WatchlistEntry.entity_id == entity_id,
            WatchlistEntry.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none() is not None


async def check_watchlist_hits_for_crime(db: AsyncSession, crime_id: str, involved_entity_ids: list[str]):
    """Call this whenever a new crime is logged (from create_crime()) or a new
    offender/victim link is added to an existing crime. Checks whether any watched
    entity is involved, and if so, fires an Alert through the existing alert pipeline."""
    from app.services.alert_service import create_alert

    if not involved_entity_ids:
        return

    result = await db.execute(
        select(WatchlistEntry).where(
            WatchlistEntry.entity_id.in_(involved_entity_ids),
            WatchlistEntry.is_active.is_(True),
        )
    )
    hits = result.scalars().all()
    for hit in hits:
        hit.last_triggered_at = datetime.now(timezone.utc)
        await create_alert(
            db,
            alert_type="KNOWN_CRIMINAL",
            severity="HIGH",
            title=f"Watchlist hit: {hit.entity_label or hit.entity_id}",
            description=f"{hit.entity_label or hit.entity_id} ({hit.entity_type}) appears in newly logged crime {crime_id}.",
            related_entity_id=hit.entity_id,
            related_entity_type=hit.entity_type,
            generated_by="WATCHLIST",
        )
    if hits:
        await db.commit()
