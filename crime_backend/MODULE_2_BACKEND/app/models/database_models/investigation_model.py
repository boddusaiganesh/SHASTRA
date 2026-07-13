"""
Saved Investigation Model — PostgreSQL Table: saved_investigations
Persists a Criminal Network "case board" (which nodes/edges were on screen,
notes, filters) so an officer can reopen or share it later.
"""

from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class SavedInvestigation(Base):
    __tablename__ = "saved_investigations"

    investigation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(300), nullable=False)
    notes = Column(Text, nullable=True)

    # The filters that were active (district, crime_type, node_type, search) —
    # lets us re-run the same server-side query to refresh the graph on reopen.
    filters = Column(JSON, default=dict)

    # The exact node/edge ids that were on screen, plus per-node officer notes
    # and cytoscape's last layout positions, so the board looks the same on reopen.
    # Shape: {"node_ids": [...], "edge_ids": [...], "node_notes": {node_id: "text"}, "positions": {node_id: {x,y}}}
    board_state = Column(JSON, default=dict)

    district_id = Column(String(50), ForeignKey("districts.district_id"), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "investigation_id": str(self.investigation_id),
            "title": self.title,
            "notes": self.notes,
            "filters": self.filters or {},
            "board_state": self.board_state or {},
            "district_id": self.district_id,
            "created_by": str(self.created_by),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
