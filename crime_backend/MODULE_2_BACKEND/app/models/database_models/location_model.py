"""
Location and Hotspot Database Models
"""

from sqlalchemy import Column, String, Boolean, DateTime, JSON, Float, Integer, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Location(Base):
    __tablename__ = "locations"

    location_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_name = Column(String(300), nullable=False)
    location_type = Column(String(100), nullable=True)  # RESIDENTIAL/COMMERCIAL/PUBLIC/HIGHWAY
    address = Column(Text, nullable=True)
    district_id = Column(String(50), ForeignKey("districts.district_id"), nullable=True, index=True)
    police_station_id = Column(String(50), ForeignKey("police_stations.station_id"), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    total_crimes = Column(Integer, default=0)
    last_crime_date = Column(Date, nullable=True)
    risk_score = Column(Float, default=0.0)
    is_hotspot = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "location_id": str(self.location_id),
            "location_name": self.location_name,
            "location_type": self.location_type,
            "address": self.address,
            "district_id": self.district_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "total_crimes": self.total_crimes,
            "last_crime_date": self.last_crime_date.isoformat() if self.last_crime_date else None,
            "risk_score": self.risk_score,
            "is_hotspot": self.is_hotspot,
        }


class Hotspot(Base):
    __tablename__ = "hotspots"

    hotspot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotspot_name = Column(String(300), nullable=False)
    district_id = Column(String(50), ForeignKey("districts.district_id"), nullable=False, index=True)
    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    radius_meters = Column(Float, default=500.0)
    boundary_geojson = Column(JSON, nullable=True)
    crime_count = Column(Integer, default=0)
    dominant_crime_type = Column(String(100), nullable=True)
    risk_level = Column(String(20), default="MEDIUM", nullable=False)
    risk_score = Column(Float, default=50.0)
    peak_time_start = Column(String(10), nullable=True)
    peak_time_end = Column(String(10), nullable=True)
    peak_days = Column(JSON, default=list)
    trend = Column(String(20), default="STABLE")  # INCREASING/STABLE/DECREASING
    trend_percentage = Column(Float, default=0.0)
    deployment_suggestion = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "hotspot_id": str(self.hotspot_id),
            "hotspot_name": self.hotspot_name,
            "district_id": self.district_id,
            "center_latitude": self.center_latitude,
            "center_longitude": self.center_longitude,
            "radius_meters": self.radius_meters,
            "boundary_geojson": self.boundary_geojson,
            "crime_count": self.crime_count,
            "dominant_crime_type": self.dominant_crime_type,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "peak_time_start": self.peak_time_start,
            "peak_time_end": self.peak_time_end,
            "peak_days": self.peak_days or [],
            "trend": self.trend,
            "trend_percentage": self.trend_percentage,
            "deployment_suggestion": self.deployment_suggestion,
            "is_active": self.is_active,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class SocioeconomicData(Base):
    __tablename__ = "socioeconomic_data"

    data_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district_id = Column(String(50), ForeignKey("districts.district_id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    population = Column(Integer, nullable=True)
    population_density = Column(Float, nullable=True)
    unemployment_rate = Column(Float, nullable=True)
    poverty_index = Column(Float, nullable=True)
    literacy_rate = Column(Float, nullable=True)
    urbanization_rate = Column(Float, nullable=True)
    per_capita_income = Column(Float, nullable=True)
    young_male_population = Column(Float, nullable=True)
    drug_cases_count = Column(Integer, nullable=True)
    alcohol_shops_count = Column(Integer, nullable=True)
    street_lighting_coverage = Column(Float, nullable=True)
    cctv_coverage = Column(Float, nullable=True)
    data_source = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "data_id": str(self.data_id),
            "district_id": self.district_id,
            "year": self.year,
            "population": self.population,
            "population_density": self.population_density,
            "unemployment_rate": self.unemployment_rate,
            "poverty_index": self.poverty_index,
            "literacy_rate": self.literacy_rate,
            "urbanization_rate": self.urbanization_rate,
            "per_capita_income": self.per_capita_income,
            "young_male_population": self.young_male_population,
            "drug_cases_count": self.drug_cases_count,
            "alcohol_shops_count": self.alcohol_shops_count,
            "street_lighting_coverage": self.street_lighting_coverage,
            "cctv_coverage": self.cctv_coverage,
        }
