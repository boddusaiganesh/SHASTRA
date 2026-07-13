from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from app.core.database import get_db
from app.core.security import get_current_user, scope_district_filter, require_role, scope_district_param
from app.core.redis_connection import cache_get, cache_set
from app.models.database_models.crime_model import Crime, District, PoliceStation, CrimeVictimLink, CrimeOffenderLink
from app.models.response_models.crime_response import CreateCrimeRequest
from app.services.crime_service import create_crime
from app.utils.district_resolver import resolve_district_id

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/map-data")
async def get_map_data(
    file_format: str = Query("json", enum=["json", "csv"]),
    crime_type: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
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
        from datetime import datetime, timedelta, date
        from sqlalchemy import func
        
        resolved_district = await resolve_district_id(db, district_id)
        effective_district = scope_district_param(resolved_district, current_user)
        
        cache_key = f"crimes_map_data:{file_format}:{crime_type}:{effective_district}:{date_from}:{date_to}:{limit}:{min_lat}:{max_lat}:{min_lng}:{max_lng}"
        cached_data = await cache_get(cache_key)
        if cached_data:
            if file_format == "csv":
                import csv
                from io import StringIO
                from fastapi.responses import StreamingResponse
                output = StringIO()
                if cached_data.get("data"):
                    writer = csv.DictWriter(output, fieldnames=list(cached_data["data"][0].keys()))
                    writer.writeheader()
                    writer.writerows(cached_data["data"])
                output.seek(0)
                return StreamingResponse(
                    iter([output.getvalue()]),
                    media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="crimes_export.csv"'}
                )
            return cached_data

        # Base statements
        stmt = select(Crime, District, PoliceStation).join(
            District, Crime.district_id == District.district_id, isouter=True
        ).join(
            PoliceStation, Crime.police_station_id == PoliceStation.station_id, isouter=True
        )
        count_stmt = select(func.count(Crime.crime_id))
        
        # Apply filters
        def apply_filters(q):
            if crime_type and crime_type != "All":
                q = q.where(Crime.crime_type == crime_type)
            if resolved_district and resolved_district != "All Districts":
                q = q.where(Crime.district_id == resolved_district)
            
            has_date_filter = False
            if date_from:
                try:
                    df = datetime.strptime(date_from, "%Y-%m-%d").date()
                    q = q.where(Crime.date_of_occurrence >= df)
                    has_date_filter = True
                except ValueError:
                    pass
            if date_to:
                try:
                    dt = datetime.strptime(date_to, "%Y-%m-%d").date()
                    q = q.where(Crime.date_of_occurrence <= dt)
                    has_date_filter = True
                except ValueError:
                    pass
                    
            if not has_date_filter:
                q = q.where(Crime.date_of_occurrence >= date.today() - timedelta(days=180))

            if min_lat is not None and max_lat is not None:
                q = q.where(Crime.latitude.between(min_lat, max_lat))
            if min_lng is not None and max_lng is not None:
                q = q.where(Crime.longitude.between(min_lng, max_lng))
            q = scope_district_filter(q, current_user, Crime.district_id)
            return q

        stmt = apply_filters(stmt)
        count_stmt = apply_filters(count_stmt)

        # Get total count
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar_one_or_none() or 0

        # Apply limit to data query
        stmt = stmt.order_by(Crime.date_of_occurrence.desc()).limit(limit)
        
        result = await db.execute(stmt)
        rows = result.all()
        crime_ids = [crime.crime_id for crime, _, _ in rows]
        
        victim_links = (await db.execute(select(CrimeVictimLink).where(CrimeVictimLink.crime_id.in_(crime_ids)))).scalars().all() if crime_ids else []
        offender_links = (await db.execute(select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id.in_(crime_ids)))).scalars().all() if crime_ids else []
        
        v_map = {vl.crime_id: str(vl.victim_id) for vl in victim_links}
        o_map = {ol.crime_id: str(ol.offender_id) for ol in offender_links}
        
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
                "victim_id": v_map.get(crime.crime_id),
                "suspect_id": o_map.get(crime.crime_id),
            })
            
        if file_format == "csv":
            import csv
            from io import StringIO
            from fastapi.responses import StreamingResponse
            
            await cache_set(cache_key, {"data": formatted_data}, expiry=300)
            
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
            
        response_data = {"success": True, "data": formatted_data, "total_count": total_count, "limit": limit}
        await cache_set(cache_key, response_data, expiry=300)
        return response_data
        
    except Exception as e:
        logger.error(f"Error fetching map data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/filter")
async def filter_crimes(
    q: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(20),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from sqlalchemy import func, or_, cast, String

    base = select(Crime, District, PoliceStation).join(
        District, Crime.district_id == District.district_id, isouter=True
    ).join(
        PoliceStation, Crime.police_station_id == PoliceStation.station_id, isouter=True
    )
    count_base = select(func.count(Crime.crime_id))

    resolved_district_id = await resolve_district_id(db, district_id) if district_id else None
    effective_district_id = scope_district_param(resolved_district_id, current_user)

    def apply_filter_conditions(query):
        query = scope_district_filter(query, current_user, Crime.district_id)
        if effective_district_id:
            query = query.where(Crime.district_id == effective_district_id)
        if crime_type:
            query = query.where(Crime.crime_type == crime_type)
        if status:
            query = query.where(Crime.status == status)
        if q:
            search_term = f"%{q.lower()}%"
            query = query.where(
                or_(
                    cast(Crime.crime_id, String).ilike(search_term),
                    Crime.crime_type.ilike(search_term),
                    Crime.district_id.ilike(search_term),
                    Crime.address.ilike(search_term),
                    Crime.landmark.ilike(search_term)
                )
            )
        return query

    base = apply_filter_conditions(base)
    count_base = apply_filter_conditions(count_base)

    total_count = (await db.execute(count_base)).scalar_one_or_none() or 0

    base = base.order_by(Crime.date_of_occurrence.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(base)).all()

    data = [
        {
            "crime_id": str(crime.crime_id),
            "crime_type": crime.crime_type,
            "date_time": crime.date_of_occurrence.isoformat() if crime.date_of_occurrence else "",
            "location": crime.address or crime.landmark or "Unknown Location",
            "district": district.district_name if district else crime.district_id,
            "police_station": station.station_name if station else "Unknown PS",
            "status": crime.status,
            "severity": crime.severity,
        }
        for crime, district, station in rows
    ]

    return {"success": True, "data": data, "total_count": total_count}

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
        
        # NEW: check if any watched person/location is involved in this new crime
        from app.services.watchlist_service import check_watchlist_hits_for_crime
        involved_ids = [v for v in [crime_dict.get("offender_id"), crime_dict.get("victim_id"), crime_dict.get("location_id")] if v]
        if involved_ids:
            await check_watchlist_hits_for_crime(db, str(new_crime["crime_id"]), involved_ids)
            
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

class StatusUpdateReq(BaseModel):
    status: str

@router.patch("/{crime_id}/status")
async def update_crime_status(
    crime_id: str,
    req: StatusUpdateReq,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"])),
):
    from app.services.crime_service import update_crime_record
    from app.utils.audit import log_action
    
    from app.core.config import CRIME_STATUS_VALUES
    
    status_value = req.status
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
