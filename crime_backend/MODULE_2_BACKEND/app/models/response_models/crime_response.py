"""
Crime Response Pydantic Models
"""

from pydantic import BaseModel
from typing import Optional, List


class CrimeMapItem(BaseModel):
    crime_id: str
    crime_type: str
    crime_sub_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    date_time: Optional[str] = None
    district: Optional[str] = None
    police_station: Optional[str] = None
    status: str
    severity: str
    victim_count: int = 0


class CrimeMapResponse(BaseModel):
    crimes: List[CrimeMapItem]
    total_count: int
    date_range: dict
    filters_applied: dict


class CrimeDetailResponse(BaseModel):
    crime_id: str
    crime_reference_no: str
    crime_type: str
    crime_sub_type: Optional[str] = None
    description: Optional[str] = None
    date_of_occurrence: Optional[str] = None
    time_of_occurrence: Optional[str] = None
    day_of_week: Optional[str] = None
    district: Optional[str] = None
    police_station: Optional[str] = None
    address: Optional[str] = None
    landmark: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str
    severity: str
    weapons_used: List[str] = []
    modus_operandi: Optional[str] = None
    property_stolen: Optional[str] = None
    property_value: Optional[float] = None
    fir_number: Optional[str] = None
    victims: List[dict] = []
    offenders: List[dict] = []
    investigating_officer: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CrimeListItem(BaseModel):
    crime_id: str
    crime_type: str
    location: str
    district: str
    datetime: str
    status: str
    severity: str


class CrimeFilterResponse(BaseModel):
    crimes: List[dict]
    total_count: int
    page: int
    total_pages: int


class CreateCrimeRequest(BaseModel):
    crime_type: str
    crime_sub_type: Optional[str] = None
    description: Optional[str] = None
    date_of_occurrence: str
    time_of_occurrence: Optional[str] = None
    district_id: str
    police_station_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    landmark: Optional[str] = None
    status: str = "REPORTED"
    severity: str = "MEDIUM"
    weapons_used: List[str] = []
    modus_operandi: Optional[str] = None
    property_stolen: Optional[str] = None
    property_value: Optional[float] = None
    fir_number: Optional[str] = None
    offender_ids: List[str] = []
    victim_ids: List[str] = []
