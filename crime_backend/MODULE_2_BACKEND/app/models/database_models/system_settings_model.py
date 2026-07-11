from sqlalchemy import Column, Integer
from app.core.database import Base

class SystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, default=1)
    crime_spike_percent = Column(Integer, default=200)
    anomaly_confidence = Column(Integer, default=75)
    high_risk_score = Column(Integer, default=80)

    def to_dict(self):
        return {
            "crime_spike_percent": self.crime_spike_percent,
            "anomaly_confidence": self.anomaly_confidence,
            "high_risk_score": self.high_risk_score,
        }
