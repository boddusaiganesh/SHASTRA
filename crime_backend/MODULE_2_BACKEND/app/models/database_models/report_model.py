"""
Report Database Model - PostgreSQL Table: reports
"""

from sqlalchemy import Column, String, Boolean, DateTime, JSON, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_type = Column(String(100), nullable=False)
    report_name = Column(String(500), nullable=False)
    generated_by = Column(UUID(as_uuid=True), nullable=True)
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    district_id = Column(String(50), nullable=True)
    crime_types_included = Column(JSON, default=list)
    report_data = Column(JSON, default=dict)
    ai_narrative = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    status = Column(String(50), default="GENERATING")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "report_id": str(self.report_id),
            "report_type": self.report_type,
            "report_name": self.report_name,
            "generated_by": str(self.generated_by) if self.generated_by else None,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "district_id": self.district_id,
            "crime_types_included": self.crime_types_included or [],
            "report_data": self.report_data or {},
            "ai_narrative": self.ai_narrative,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "generated_at": self.created_at.isoformat() if self.created_at else None,
        }
