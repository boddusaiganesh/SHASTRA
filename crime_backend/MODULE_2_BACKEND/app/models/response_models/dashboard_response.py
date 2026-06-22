"""
Dashboard Response Pydantic Models
"""

from pydantic import BaseModel
from typing import Optional, List, Any


class DashboardSummaryResponse(BaseModel):
    total_crimes_month: int
    crimes_change_percentage: float
    active_hotspots_count: int
    high_risk_areas_count: int
    repeat_offenders_count: int
    pending_alerts_count: int
    cases_solved_month: int
    solve_rate_percentage: float
    most_common_crime_type: str
    most_affected_district: str
    data_last_updated: str


class TrendDataItem(BaseModel):
    month: str
    year: int
    total_crimes: int
    by_type: dict


class CrimeTrendResponse(BaseModel):
    trend_data: List[TrendDataItem]


class RecentCrimeItem(BaseModel):
    crime_id: str
    crime_type: str
    location: str
    district: str
    datetime: str
    status: str
    severity: str


class RecentAlertItem(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    title: str
    location: Optional[str] = None
    created_at: str
    is_read: bool


class StandardResponse(BaseModel):
    success: bool
    data: Any
    message: Optional[str] = None
    timestamp: str
