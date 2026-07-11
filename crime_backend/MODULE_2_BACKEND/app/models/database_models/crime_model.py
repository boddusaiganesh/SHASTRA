"""
Crime Database Model - PostgreSQL Table: crimes
"""

from sqlalchemy import (
    Column, String, Boolean, DateTime, JSON, Float, Integer, Date, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class District(Base):
    __tablename__ = "districts"

    district_id = Column(String(50), primary_key=True)
    district_name = Column(String(200), nullable=False)
    district_code = Column(String(20), nullable=False)
    headquarters = Column(String(200), nullable=False)
    total_area_sqkm = Column(Float, nullable=True)
    population = Column(Integer, nullable=True)
    boundary_geojson = Column(JSON, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "district_id": self.district_id,
            "district_name": self.district_name,
            "district_code": self.district_code,
            "headquarters": self.headquarters,
            "total_area_sqkm": self.total_area_sqkm,
            "population": self.population,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


class PoliceStation(Base):
    __tablename__ = "police_stations"

    station_id = Column(String(50), primary_key=True)
    station_name = Column(String(200), nullable=False)
    district_id = Column(String(50), ForeignKey("districts.district_id"), nullable=False)
    station_code = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    jurisdiction_area = Column(JSON, nullable=True)
    officer_in_charge = Column(String(200), nullable=True)
    total_officers = Column(Integer, nullable=True)
    contact_number = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "station_id": self.station_id,
            "station_name": self.station_name,
            "district_id": self.district_id,
            "station_code": self.station_code,
            "address": self.address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "officer_in_charge": self.officer_in_charge,
            "total_officers": self.total_officers,
            "contact_number": self.contact_number,
        }


class Crime(Base):
    __tablename__ = "crimes"

    crime_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crime_reference_no = Column(String(100), unique=True, nullable=False, index=True)
    crime_type = Column(String(100), nullable=False, index=True)
    crime_sub_type = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    date_of_occurrence = Column(Date, nullable=False, index=True)
    time_of_occurrence = Column(String(20), nullable=True)
    day_of_week = Column(String(20), nullable=True)
    month = Column(Integer, nullable=True)
    year = Column(Integer, nullable=True, index=True)
    district_id = Column(String(50), ForeignKey("districts.district_id"), nullable=False, index=True)
    police_station_id = Column(String(50), ForeignKey("police_stations.station_id"), nullable=True)
    location_id = Column(UUID(as_uuid=True), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(Text, nullable=True)
    landmark = Column(String(300), nullable=True)
    status = Column(String(50), default="REPORTED", nullable=False)
    severity = Column(String(20), default="MEDIUM", nullable=False)
    weapons_used = Column(JSON, default=list)
    modus_operandi = Column(Text, nullable=True)
    property_stolen = Column(String(500), nullable=True)
    property_value = Column(Float, nullable=True)
    reporting_officer_id = Column(UUID(as_uuid=True), nullable=True)
    investigating_officer_id = Column(UUID(as_uuid=True), nullable=True)
    fir_number = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "crime_id": str(self.crime_id),
            "crime_reference_no": self.crime_reference_no,
            "crime_type": self.crime_type,
            "crime_sub_type": self.crime_sub_type,
            "description": self.description,
            "date_of_occurrence": self.date_of_occurrence.isoformat() if self.date_of_occurrence else None,
            "time_of_occurrence": self.time_of_occurrence,
            "day_of_week": self.day_of_week,
            "month": self.month,
            "year": self.year,
            "district_id": self.district_id,
            "police_station_id": self.police_station_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address": self.address,
            "landmark": self.landmark,
            "status": self.status,
            "severity": self.severity,
            "weapons_used": self.weapons_used or [],
            "modus_operandi": self.modus_operandi,
            "property_stolen": self.property_stolen,
            "property_value": self.property_value,
            "fir_number": self.fir_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CrimeOffenderLink(Base):
    __tablename__ = "crime_offender_links"

    link_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crime_id = Column(UUID(as_uuid=True), ForeignKey("crimes.crime_id"), nullable=False, index=True)
    offender_id = Column(UUID(as_uuid=True), ForeignKey("offenders.offender_id"), nullable=False, index=True)
    role_in_crime = Column(String(50), default="SUSPECT")
    is_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CrimeVictimLink(Base):
    __tablename__ = "crime_victim_links"

    link_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crime_id = Column(UUID(as_uuid=True), ForeignKey("crimes.crime_id"), nullable=False, index=True)
    victim_id = Column(UUID(as_uuid=True), ForeignKey("victims.victim_id"), nullable=False, index=True)
    injury_level = Column(String(50), default="NONE")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
