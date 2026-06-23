from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Any, Optional
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database_models.crime_model import Crime, District, PoliceStation
from app.models.response_models.crime_response import CreateCrimeRequest
from app.services.crime_service import create_crime
from app.utils.district_resolver import resolve_district_id

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
            
        return {"success": True, "data": formatted_data}
    except Exception as e:
        logger.error(f"Error fetching map data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/filter")
async def filter_crimes(
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(20),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = select(Crime)
    if district_id:
        query = query.where(Crime.district_id == district_id)
    if crime_type:
        query = query.where(Crime.crime_type == crime_type)
    if status:
        query = query.where(Crime.status == status)
        
    query = query.order_by(Crime.date_of_occurrence.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    crimes = result.scalars().all()
    
    return {"success": True, "data": [c.to_dict() for c in crimes]}

@router.get("/detail/{crime_id}")
async def crime_detail(
    crime_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    import uuid
    try:
        cid = uuid.UUID(crime_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid crime_id format")
        
    result = await db.execute(select(Crime).where(Crime.crime_id == cid))
    crime = result.scalar_one_or_none()
    if not crime:
        raise HTTPException(status_code=404, detail="Crime not found")
        
    return {"success": True, "data": crime.to_dict()}


@router.post("", status_code=status.HTTP_201_CREATED)
async def log_crime(
    crime_data: CreateCrimeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Log a new crime record.
    Role check: DISTRICT_OFFICER can only log crimes within their own district.
    """
    resolved_district = await resolve_district_id(db, crime_data.district_id)
    
    if current_user["role"] == "DISTRICT_OFFICER":
        user_district = current_user.get("district_id")
        if resolved_district != user_district:
            raise HTTPException(
                status_code=403,
                detail="District officers can only log crimes within their own district."
            )
            
    crime_dict = crime_data.model_dump()
    crime_dict["district_id"] = resolved_district
    
    try:
        new_crime = await create_crime(db, crime_dict, str(current_user["user_id"]))
        return {"success": True, "data": new_crime}
    except Exception as e:
        logger.error(f"Error creating crime: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
