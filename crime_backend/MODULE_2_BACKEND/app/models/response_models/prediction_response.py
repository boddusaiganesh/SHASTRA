"""
Prediction Response Models
"""

from pydantic import BaseModel
from typing import Optional, List, Any


class DistrictRiskItem(BaseModel):
    district_id: str
    district_name: str
    risk_score: float
    risk_level: str
    risk_color: str
    primary_risk: str
    confidence: float
    trend: str
    boundary_geojson: Optional[dict] = None


class PredictionItem(BaseModel):
    rank: int
    location: str
    district: str
    predicted_crime_type: str
    risk_percentage: float
    confidence_level: float
    prediction_date_range: dict
    recommended_action: str
    contributing_factors: List[str]
    similar_past_events: List[dict]


class ForecastDataPoint(BaseModel):
    date: str
    predicted_count: float
    lower_bound: float
    upper_bound: float
    confidence: float


class HistoricalDataPoint(BaseModel):
    date: str
    actual: int


class ForecastResponse(BaseModel):
    forecast: List[ForecastDataPoint]
    historical: List[HistoricalDataPoint]
    model_accuracy: float
    trend_direction: str
    seasonal_factors: List[str]


class EmergingTypologyItem(BaseModel):
    crime_type: str
    growth_rate: float
    first_detected: str
    affected_districts: List[str]
    pattern_description: str
    warning_level: str
    ai_explanation: str


class SocioeconomicCorrelationResponse(BaseModel):
    correlations: List[dict]
    overlay_data: List[dict]
    ai_analysis: str
