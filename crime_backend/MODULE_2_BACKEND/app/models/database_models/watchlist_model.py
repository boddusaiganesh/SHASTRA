"""
Watchlist Model — PostgreSQL Table: watchlist_entries
An officer "follows" a network entity (criminal / victim / location / organization).
When that entity appears in a newly logged crime, an Alert is auto-generated.
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"
    __table_args__ = (UniqueConstraint("user_id", "entity_id", name="uq_watchlist_user_entity"),)

    watch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)

    # entity_id matches the network node_id (offender_id / victim_id / location_id / org_id — all strings)
    entity_id = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # criminal / victim / location / organization
    entity_label = Column(String(300), nullable=True)  # display name snapshot, so lists don't need a join

    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "watch_id": str(self.watch_id),
            "user_id": str(self.user_id),
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "entity_label": self.entity_label,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
        }
