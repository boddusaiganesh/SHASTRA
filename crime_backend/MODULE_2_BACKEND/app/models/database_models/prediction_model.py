"""
Prediction Database Model - PostgreSQL Table: predictions
"""

from sqlalchemy import Column, String, Boolean, DateTime, JSON, Float, Integer, Date, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_type = Column(String(100), nullable=False, index=True)
    district_id = Column(String(50), nullable=True, index=True)
    location_id = Column(UUID(as_uuid=True), nullable=True)
    predicted_crime_type = Column(String(100), nullable=True)
    risk_percentage = Column(Float, default=0.0)
    confidence_level = Column(Float, default=0.0)
    prediction_date = Column(Date, nullable=True)
    prediction_made_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    model_used = Column(String(100), nullable=True)
    features_used = Column(JSON, default=list)
    actual_outcome = Column(String(200), nullable=True)
    accuracy_score = Column(Float, nullable=True)
    recommended_action = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    contributing_factors = Column(JSON, default=list)
    forecast_data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "prediction_id": str(self.prediction_id),
            "prediction_type": self.prediction_type,
            "district_id": self.district_id,
            "location_id": str(self.location_id) if self.location_id else None,
            "predicted_crime_type": self.predicted_crime_type,
            "risk_percentage": self.risk_percentage,
            "confidence_level": self.confidence_level,
            "prediction_date": self.prediction_date.isoformat() if self.prediction_date else None,
            "prediction_made_at": self.prediction_made_at.isoformat() if self.prediction_made_at else None,
            "model_used": self.model_used,
            "features_used": self.features_used or [],
            "recommended_action": self.recommended_action,
            "is_active": self.is_active,
            "contributing_factors": self.contributing_factors or [],
            "forecast_data": self.forecast_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
