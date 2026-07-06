"""Evidence Database Model - PostgreSQL Table: evidence"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crime_id = Column(UUID(as_uuid=True), ForeignKey("crimes.crime_id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)     # original filename, per evidence_router.py usage
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "evidence_id": str(self.evidence_id),
            "crime_id": str(self.crime_id),
            "file_path": self.file_path,
            "description": self.description,
            "uploaded_by": str(self.uploaded_by) if self.uploaded_by else None,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }
