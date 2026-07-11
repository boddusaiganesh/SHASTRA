"""
Victim Database Model - PostgreSQL Table: victims
"""

from sqlalchemy import Column, String, DateTime, JSON, Integer, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Victim(Base):
    __tablename__ = "victims"

    victim_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    occupation = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)
    district_id = Column(String(50), ForeignKey("districts.district_id"), nullable=True, index=True)
    phone_number = Column(String(20), nullable=True)
    vulnerability_factors = Column(JSON, default=list)
    total_victimizations = Column(Integer, default=1)
    first_victimization = Column(Date, nullable=True)
    last_victimization = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "victim_id": str(self.victim_id),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": f"{self.first_name} {self.last_name}",
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age": self.age,
            "gender": self.gender,
            "occupation": self.occupation,
            "address": self.address,
            "district_id": self.district_id,
            "vulnerability_factors": self.vulnerability_factors or [],
            "total_victimizations": self.total_victimizations,
            "first_victimization": self.first_victimization.isoformat() if self.first_victimization else None,
            "last_victimization": self.last_victimization.isoformat() if self.last_victimization else None,
        }
