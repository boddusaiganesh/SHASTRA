"""
Alert Database Model - PostgreSQL Table: alerts
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    district_id = Column(String(50), nullable=True, index=True)
    location_id = Column(UUID(as_uuid=True), nullable=True)
    related_entity_id = Column(String(200), nullable=True)
    related_entity_type = Column(String(100), nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    read_by = Column(UUID(as_uuid=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    target_role = Column(String(100), default="ALL")
    target_district = Column(String(50), default="ALL")
    generated_by = Column(String(100), default="SYSTEM")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "alert_id": str(self.alert_id),
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "district_id": self.district_id,
            "district": self.district_id,
            "location_id": str(self.location_id) if self.location_id else None,
            "location": self.district_id,
            "related_entity_id": self.related_entity_id,
            "related_entity_type": self.related_entity_type,
            "is_read": self.is_read,
            "read_by": str(self.read_by) if self.read_by else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "target_role": self.target_role,
            "target_district": self.target_district,
            "generated_by": self.generated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "datetime": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
