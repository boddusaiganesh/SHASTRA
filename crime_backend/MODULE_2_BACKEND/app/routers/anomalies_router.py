from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.database import get_db
from app.models.database_models.anomaly_model import Anomaly

router = APIRouter()
logger = logging.getLogger(__name__)

MOCK_ANOMALIES = [
    {
        "anomaly_id": "ANO001",
        "detection_datetime": "2026-06-15T09:30:00",
        "anomaly_type": "Crime Spike",
        "severity_level": "Critical",
        "location": "Whitefield, Bengaluru",
        "description": "Vehicle theft rate increased by 340% in a 48-hour window",
        "ai_explanation": "Gemini AI Analysis: The sudden spike in vehicle thefts in Whitefield appears to be coordinated. Network analysis links 4 of the 12 vehicles stolen to the same parking facility.",
        "related_cases": ["CRM001", "CRM007", "CRM011"],
        "evidence_points": ["12 vehicles stolen in 48 hours", "Same parking facility targeted multiple times"],
        "recommended_action": "Deploy plainclothes officers at targeted parking facilities.",
        "status": "Under Review",
        "assigned_officer": "Inspector Ramesh Kumar",
    },
    {
        "anomaly_id": "ANO002",
        "detection_datetime": "2026-06-14T18:45:00",
        "anomaly_type": "Cross-District Pattern",
        "severity_level": "Critical",
        "location": "Belagavi Border Areas",
        "description": "Unusual pattern of incidents at border checkpoints suggesting smuggling operation",
        "ai_explanation": "Gemini AI Analysis: Analysis reveals a systematic pattern of decoy items being seized at main checkpoints while high-value contraband passes through secondary routes.",
        "related_cases": ["CRM003", "CRM013"],
        "evidence_points": ["Systematic decoy pattern", "Precise timing intervals"],
        "recommended_action": "Secret checkpoints at secondary routes. Intelligence sharing with Maharashtra.",
        "status": "New",
        "assigned_officer": None,
    }
]

@router.get("/")
async def get_anomalies(db: AsyncSession = Depends(get_db)):
    """
    Fetch detected anomalies from the DB.
    """
    try:
        result = await db.execute(select(Anomaly).order_by(Anomaly.detected_at.desc()).limit(20))
        anomalies = result.scalars().all()
        if anomalies:
            return [a.to_dict() for a in anomalies]
    except Exception as e:
        logger.error(f"Error fetching anomalies from DB: {e}")
    
    # Fallback if DB is empty or fails
    return MOCK_ANOMALIES
