"""
Offender Database Model - PostgreSQL Table: offenders
"""

from sqlalchemy import Column, String, Boolean, DateTime, JSON, Float, Integer, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Offender(Base):
    __tablename__ = "offenders"

    offender_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offender_reference = Column(String(100), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    alias_names = Column(JSON, default=list)
    date_of_birth = Column(Date, nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    nationality = Column(String(100), default="Indian")
    religion = Column(String(100), nullable=True)
    caste = Column(String(100), nullable=True)
    education_level = Column(String(100), nullable=True)
    occupation = Column(String(200), nullable=True)
    address_current = Column(Text, nullable=True)
    address_permanent = Column(Text, nullable=True)
    district_id = Column(String(50), ForeignKey("districts.district_id"), nullable=True, index=True)
    latitude_home = Column(Float, nullable=True)
    longitude_home = Column(Float, nullable=True)
    phone_numbers = Column(JSON, default=list)
    physical_description = Column(Text, nullable=True)
    identifying_marks = Column(Text, nullable=True)
    photo_available = Column(Boolean, default=False)
    fingerprint_available = Column(Boolean, default=False)
    status = Column(String(50), default="ACTIVE", nullable=False, index=True)
    prison_name = Column(String(300), nullable=True)
    release_date = Column(Date, nullable=True)
    total_crimes = Column(Integer, default=0)
    first_offense_date = Column(Date, nullable=True)
    last_offense_date = Column(Date, nullable=True)
    risk_level = Column(String(20), default="MEDIUM", nullable=False, index=True)
    risk_score = Column(Float, default=50.0)
    modus_operandi_summary = Column(Text, nullable=True)
    preferred_crime_types = Column(JSON, default=list)
    preferred_locations = Column(JSON, default=list)
    preferred_time = Column(String(50), nullable=True)
    typical_targets = Column(Text, nullable=True)
    known_associates = Column(JSON, default=list)
    reoffend_probability = Column(Float, default=50.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "offender_id": str(self.offender_id),
            "offender_reference": self.offender_reference,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": f"{self.first_name} {self.last_name}",
            "alias_names": self.alias_names or [],
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age": self.age,
            "gender": self.gender,
            "nationality": self.nationality,
            "occupation": self.occupation,
            "address_current": self.address_current,
            "district_id": self.district_id,
            "latitude_home": self.latitude_home,
            "longitude_home": self.longitude_home,
            "phone_numbers": self.phone_numbers or [],
            "physical_description": self.physical_description,
            "identifying_marks": self.identifying_marks,
            "photo_available": self.photo_available,
            "fingerprint_available": self.fingerprint_available,
            "status": self.status,
            "prison_name": self.prison_name,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "total_crimes": self.total_crimes,
            "first_offense_date": self.first_offense_date.isoformat() if self.first_offense_date else None,
            "last_offense_date": self.last_offense_date.isoformat() if self.last_offense_date else None,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "modus_operandi_summary": self.modus_operandi_summary,
            "preferred_crime_types": self.preferred_crime_types or [],
            "preferred_locations": self.preferred_locations or [],
            "preferred_time": self.preferred_time,
            "typical_targets": self.typical_targets,
            "known_associates": self.known_associates or [],
            "reoffend_probability": self.reoffend_probability,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
