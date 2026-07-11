"""
Anomaly Database Model - PostgreSQL Table: anomalies
"""

from sqlalchemy import Column, String, DateTime, JSON, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    anomaly_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anomaly_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    district_id = Column(String(50), nullable=True, index=True)
    location_id = Column(UUID(as_uuid=True), nullable=True)
    crime_id = Column(UUID(as_uuid=True), nullable=True)
    offender_id = Column(UUID(as_uuid=True), nullable=True)
    description = Column(Text, nullable=False)
    evidence_points = Column(JSON, default=list)
    ai_explanation = Column(Text, nullable=True)
    related_case_ids = Column(JSON, default=list)
    similar_historical = Column(JSON, default=list)
    recommended_action = Column(Text, nullable=True)
    status = Column(String(50), default="NEW", nullable=False, index=True)
    assigned_officer_id = Column(UUID(as_uuid=True), nullable=True)
    anomaly_score = Column(Float, nullable=True)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "anomaly_id": str(self.anomaly_id),
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "district_id": self.district_id,
            "district": self.district_id,
            "location_id": str(self.location_id) if self.location_id else None,
            "location": self.district_id,
            "crime_id": str(self.crime_id) if self.crime_id else None,
            "offender_id": str(self.offender_id) if self.offender_id else None,
            "description": self.description,
            "evidence_points": self.evidence_points or [],
            "ai_explanation": self.ai_explanation,
            "related_case_ids": self.related_case_ids or [],
            "similar_historical": self.similar_historical or [],
            "recommended_action": self.recommended_action,
            "status": self.status,
            "assigned_officer_id": str(self.assigned_officer_id) if self.assigned_officer_id else None,
            "anomaly_score": self.anomaly_score,
            "confidence_score": (self.anomaly_score or 0) / 100,
            "affected_crimes_count": len(self.related_case_ids or []),
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
