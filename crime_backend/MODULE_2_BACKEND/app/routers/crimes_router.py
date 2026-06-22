from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Any
import logging

from app.core.database import get_db
from app.models.database_models.crime_model import Crime, District, PoliceStation

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/map-data")
async def get_map_data(db: AsyncSession = Depends(get_db)):
    """
    Fetch all crime data mapped with district and police station names for the frontend map.
    """
    try:
        # Join Crime with District and PoliceStation
        stmt = select(Crime, District, PoliceStation).join(
            District, Crime.district_id == District.district_id, isouter=True
        ).join(
            PoliceStation, Crime.police_station_id == PoliceStation.station_id, isouter=True
        )
        
        result = await db.execute(stmt)
        rows = result.all()
        
        formatted_data = []
        for crime, district, station in rows:
            formatted_data.append({
                "crime_id": str(crime.crime_id),
                "crime_type": crime.crime_type,
                "date_time": crime.date_of_occurrence.isoformat() if crime.date_of_occurrence else "",
                "location": crime.address or crime.landmark or "Unknown Location",
                "district": district.district_name if district else crime.district_id,
                "police_station": station.station_name if station else "Unknown PS",
                "status": crime.status,
                "latitude": crime.latitude,
                "longitude": crime.longitude,
                "victim_id": None, # Future: Fetch from CrimeVictimLink
                "suspect_id": None, # Future: Fetch from CrimeOffenderLink
            })
            
        return formatted_data
    except Exception as e:
        logger.error(f"Error fetching map data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
