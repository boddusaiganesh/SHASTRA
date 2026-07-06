from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Any, Optional
import logging

from app.core.database import get_db
from app.core.security import get_current_user, scope_district_filter, require_role
from app.models.database_models.crime_model import Crime, District, PoliceStation
from app.models.response_models.crime_response import CreateCrimeRequest
from app.services.crime_service import create_crime
from app.utils.district_resolver import resolve_district_id

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/map-data")
async def get_map_data(
    file_format: str = Query("json", enum=["json", "csv"]),
    days: int = Query(90, ge=1, le=730, description="Only crimes from the last N days"),
    limit: int = Query(5000, ge=1, le=20000),
    min_lat: float | None = Query(None),
    max_lat: float | None = Query(None),
    min_lng: float | None = Query(None),
    max_lng: float | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Fetch crime data mapped with district and police station names for the frontend map.
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # Base statements
        stmt = select(Crime, District, PoliceStation).join(
            District, Crime.district_id == District.district_id, isouter=True
        ).join(
            PoliceStation, Crime.police_station_id == PoliceStation.station_id, isouter=True
        )
        count_stmt = select(func.count(Crime.crime_id))
        
        # Apply filters
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        for q in [stmt, count_stmt]:
            q = q.where(Crime.date_of_occurrence >= cutoff)
            if min_lat is not None and max_lat is not None:
                q = q.where(Crime.latitude.between(min_lat, max_lat))
            if min_lng is not None and max_lng is not None:
                q = q.where(Crime.longitude.between(min_lng, max_lng))
            q = scope_district_filter(q, current_user, Crime.district_id)

        # Get total count
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar_one_or_none() or 0

        # Apply limit to data query
        stmt = stmt.order_by(Crime.date_of_occurrence.desc()).limit(limit)
        
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
            
        if file_format == "csv":
            import csv
            from io import StringIO
            from fastapi.responses import StreamingResponse
            
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=["crime_id", "crime_type", "date_time", "location", "district", "police_station", "status", "latitude", "longitude"])
            writer.writeheader()
            for row in formatted_data:
                csv_row = {k: v for k, v in row.items() if k in writer.fieldnames}
                writer.writerow(csv_row)
                
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": 'attachment; filename="crimes_export.csv"'}
            )
            
        return {"success": True, "data": formatted_data, "total_count": total_count, "limit": limit}
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
    query = scope_district_filter(query, current_user, Crime.district_id)
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
        
    stmt = select(Crime).where(Crime.crime_id == cid)
    stmt = scope_district_filter(stmt, current_user, Crime.district_id)
    result = await db.execute(stmt)
    crime = result.scalar_one_or_none()
    if not crime:
        raise HTTPException(status_code=404, detail="Crime not found")
        
    return {"success": True, "data": crime.to_dict()}


@router.post("", status_code=status.HTTP_201_CREATED)
async def log_crime(
    crime_data: CreateCrimeRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"]))
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

@router.put("/{crime_id}")
async def update_crime(
    crime_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"])),
):
    from app.services.crime_service import update_crime_record
    from app.utils.audit import log_action
    
    try:
        updated = await update_crime_record(db, crime_id, payload, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
        
    if not updated:
        raise HTTPException(status_code=404, detail="Crime not found")
        
    await log_action(db, current_user["user_id"], "UPDATE", "CRIME", crime_id, payload)
    return {"success": True, "data": updated}

@router.patch("/{crime_id}/status")
async def update_crime_status(
    crime_id: str,
    status_value: str = Query(..., alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"])),
):
    from app.services.crime_service import update_crime_record
    from app.utils.audit import log_action
    
    from app.core.config import CRIME_STATUS_VALUES
    
    if status_value not in CRIME_STATUS_VALUES:
        raise HTTPException(status_code=400, detail=f"status must be one of {CRIME_STATUS_VALUES}")
        
    try:
        updated = await update_crime_record(db, crime_id, {"status": status_value}, current_user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
        
    if not updated:
        raise HTTPException(status_code=404, detail="Crime not found")
        
    await log_action(db, current_user["user_id"], "UPDATE_STATUS", "CRIME", crime_id, {"status": status_value})
    return {"success": True, "data": updated}

@router.delete("/{crime_id}")
async def delete_crime(
    crime_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER"])),
):
    if current_user["role"] != "SCRB_OFFICER":
        raise HTTPException(status_code=403, detail="Only SCRB officers may delete crime records")
    from app.services.crime_service import delete_crime_record
    from app.utils.audit import log_action
    
    ok = await delete_crime_record(db, crime_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Crime not found")
        
    await log_action(db, current_user["user_id"], "DELETE", "CRIME", crime_id)
    return {"success": True}
