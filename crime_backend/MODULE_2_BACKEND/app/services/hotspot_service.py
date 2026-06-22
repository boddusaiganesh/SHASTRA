"""
Hotspot Service - Crime hotspot detection and analysis
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import Optional, List, Dict, Any
import logging

from app.models.database_models.location_model import Hotspot
from app.models.database_models.crime_model import Crime, District
from app.core.redis_connection import cache_get, cache_set
from app.ml_models.hotspot_clustering import run_hotspot_clustering

logger = logging.getLogger(__name__)


async def get_hotspot_clusters(
    db: AsyncSession,
    district_id: Optional[str] = None,
    crime_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Get crime hotspot clusters"""
    
    cache_key = f"hotspot_clusters:{district_id}:{crime_type}:{date_from}:{date_to}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Try to get from DB first
    query = select(Hotspot).where(Hotspot.is_active == True)
    if district_id:
        query = query.where(Hotspot.district_id == district_id)
    
    result = await db.execute(query.order_by(desc(Hotspot.risk_score)))
    hotspots = result.scalars().all()
    
    district_map = await _get_district_map(db)
    
    if not hotspots:
        # Generate hotspots dynamically using ML clustering
        hotspots_data = await generate_hotspots_from_crimes(
            db, district_id, crime_type, date_from, date_to
        )
    else:
        hotspots_data = []
        for h in hotspots:
            hd = h.to_dict()
            hd["district"] = district_map.get(h.district_id, h.district_id)
            hotspots_data.append(hd)
    
    high_risk = sum(1 for h in hotspots_data if h.get("risk_level") == "HIGH")
    emerging = sum(1 for h in hotspots_data if h.get("trend") == "INCREASING")
    
    response = {
        "hotspots": hotspots_data,
        "total_hotspots": len(hotspots_data),
        "high_risk_count": high_risk,
        "emerging_count": emerging,
    }
    
    await cache_set(cache_key, response, expiry=900)
    return response


async def generate_hotspots_from_crimes(
    db: AsyncSession,
    district_id: Optional[str] = None,
    crime_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate hotspots by running ML clustering on crime data"""
    
    # Get crimes with coordinates
    query = select(Crime).where(
        and_(Crime.latitude.isnot(None), Crime.longitude.isnot(None))
    )
    
    if district_id:
        query = query.where(Crime.district_id == district_id)
    if crime_type and crime_type != "ALL":
        query = query.where(Crime.crime_type == crime_type)
    if date_from:
        query = query.where(Crime.date_of_occurrence >= date_from)
    if date_to:
        query = query.where(Crime.date_of_occurrence <= date_to)
    
    result = await db.execute(query)
    crimes = result.scalars().all()
    
    if len(crimes) < 5:
        return []
    
    # Convert to format for clustering
    crime_data = [
        {
            "crime_id": str(c.crime_id),
            "latitude": c.latitude,
            "longitude": c.longitude,
            "crime_type": c.crime_type,
            "district_id": c.district_id,
            "date": str(c.date_of_occurrence),
            "time": c.time_of_occurrence or "12:00",
            "severity": c.severity,
        }
        for c in crimes
    ]
    
    # Run DBSCAN clustering
    hotspots = run_hotspot_clustering(crime_data)
    
    return hotspots


async def get_time_patterns(
    db: AsyncSession,
    district_id: Optional[str] = None,
    crime_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Get hourly, daily, and monthly crime patterns"""
    
    cache_key = f"time_patterns:{district_id}:{crime_type}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    base_conditions = []
    if district_id:
        base_conditions.append(Crime.district_id == district_id)
    if crime_type and crime_type != "ALL":
        base_conditions.append(Crime.crime_type == crime_type)
    
    # Hourly pattern (0-23)
    hourly_pattern = []
    hourly_result = await db.execute(
        select(Crime.time_of_occurrence)
        .where(and_(*base_conditions, Crime.time_of_occurrence.isnot(None)))
    )
    
    hour_counts: Dict[int, int] = {}
    for (time_str,) in hourly_result.all():
        try:
            hour = int(time_str.split(":")[0])
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        except (ValueError, AttributeError, IndexError):
            continue
    max_hourly = max(hour_counts.values()) if hour_counts else 1
    
    for hour in range(24):
        count = hour_counts.get(hour, 0)
        hourly_pattern.append({
            "hour": hour,
            "crime_count": count,
            "peak_flag": count > (max_hourly * 0.7),
        })
    
    # Daily pattern (Monday to Sunday)
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_result = await db.execute(
        select(Crime.day_of_week, func.count(Crime.crime_id).label("count"))
        .where(and_(*base_conditions, Crime.day_of_week.isnot(None)))
        .group_by(Crime.day_of_week)
    )
    day_counts = {row[0]: row[1] for row in daily_result}
    max_daily = max(day_counts.values()) if day_counts else 1
    
    daily_pattern = [
        {
            "day": day,
            "crime_count": day_counts.get(day, 0),
            "peak_flag": day_counts.get(day, 0) > (max_daily * 0.7),
        }
        for day in days_of_week
    ]
    
    # Monthly pattern
    monthly_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_result = await db.execute(
        select(Crime.month, func.count(Crime.crime_id).label("count"))
        .where(and_(*base_conditions, Crime.month.isnot(None)))
        .group_by(Crime.month)
        .order_by(Crime.month)
    )
    month_counts = {row[0]: row[1] for row in monthly_result}
    max_monthly = max(month_counts.values()) if month_counts else 1
    
    monthly_pattern = [
        {
            "month": monthly_names[m - 1],
            "crime_count": month_counts.get(m, 0),
            "peak_flag": month_counts.get(m, 0) > (max_monthly * 0.7),
        }
        for m in range(1, 13)
    ]
    
    response = {
        "hourly_pattern": hourly_pattern,
        "daily_pattern": daily_pattern,
        "monthly_pattern": monthly_pattern,
    }
    
    await cache_set(cache_key, response, expiry=3600)
    return response


async def get_top_hotspots(
    db: AsyncSession,
    limit: int = 10,
    district_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get top N hotspots ranked by risk score"""
    
    query = select(Hotspot).where(Hotspot.is_active == True)
    if district_id:
        query = query.where(Hotspot.district_id == district_id)
    
    query = query.order_by(desc(Hotspot.risk_score)).limit(limit)
    result = await db.execute(query)
    hotspots = result.scalars().all()
    
    district_map = await _get_district_map(db)
    
    top_list = []
    for rank, h in enumerate(hotspots, start=1):
        top_list.append({
            "rank": rank,
            "hotspot_name": h.hotspot_name,
            "district": district_map.get(h.district_id, h.district_id),
            "crime_count": h.crime_count,
            "dominant_crime_type": h.dominant_crime_type,
            "risk_level": h.risk_level,
            "trend": h.trend,
            "deployment_suggestion": h.deployment_suggestion or "Increase patrol frequency during peak hours",
        })
    
    return top_list


async def get_deployment_suggestions(
    db: AsyncSession,
    district_id: str,
    target_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Get AI-powered deployment suggestions for a district"""
    from app.services.gemini_service import get_deployment_suggestions_ai
    
    # Get active hotspots for district
    result = await db.execute(
        select(Hotspot)
        .where(and_(Hotspot.district_id == district_id, Hotspot.is_active == True))
        .order_by(desc(Hotspot.risk_score))
        .limit(10)
    )
    hotspots = result.scalars().all()
    
    if not hotspots:
        return {
            "suggestions": [],
            "ai_overall_strategy": "No active hotspots found for the specified district. Maintain standard patrol schedules.",
        }
    
    # Build suggestions from hotspot data
    suggestions = []
    for h in hotspots:
        suggestions.append({
            "area_name": h.hotspot_name,
            "suggested_patrol_times": [
                f"{h.peak_time_start} - {h.peak_time_end}" if h.peak_time_start else "20:00 - 02:00"
            ],
            "recommended_officers": max(2, int(h.risk_score / 20)),
            "priority_level": h.risk_level,
            "crime_types_to_watch": [h.dominant_crime_type] if h.dominant_crime_type else [],
            "specific_instructions": h.deployment_suggestion or "Maintain visible patrol presence",
        })
    
    # Get AI strategy
    ai_strategy = await get_deployment_suggestions_ai(hotspots, district_id)
    
    return {
        "suggestions": suggestions,
        "ai_overall_strategy": ai_strategy,
    }


async def _get_district_map(db: AsyncSession) -> Dict[str, str]:
    result = await db.execute(select(District))
    districts = result.scalars().all()
    return {d.district_id: d.district_name for d in districts}
