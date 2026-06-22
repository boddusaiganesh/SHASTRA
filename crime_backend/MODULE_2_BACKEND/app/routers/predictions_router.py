from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.database_models.prediction_model import Prediction

router = APIRouter()
logger = logging.getLogger(__name__)

def generate_mock_forecast():
    import math
    import random
    forecasts = []
    base = 2847
    today = datetime.now()
    for i in range(30):
        val = base + math.sin(i * 0.3) * 150
        date_str = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        forecasts.append({
            "day": i + 1,
            "date": date_str,
            "predicted_count": int(val + random.uniform(-50, 50)),
            "lower_bound": int(val - 200),
            "upper_bound": int(val + 200),
            "historical": int(val + random.uniform(-40, 40)) if i < 10 else None,
        })
    return forecasts

MOCK_FORECAST = generate_mock_forecast()

@router.get("/forecast")
async def get_crime_forecast(db: AsyncSession = Depends(get_db)):
    """
    Fetch 30-day time-series crime forecasts from the DB.
    """
    try:
        result = await db.execute(
            select(Prediction)
            .where(Prediction.prediction_type == "STATE_WIDE_FORECAST")
            .order_by(Prediction.created_at.desc())
            .limit(1)
        )
        prediction = result.scalar_one_or_none()
        if prediction and prediction.forecast_data:
            return prediction.forecast_data.get("forecast", MOCK_FORECAST)
    except Exception as e:
        logger.error(f"Error fetching forecast from DB: {e}")
        
    return MOCK_FORECAST
