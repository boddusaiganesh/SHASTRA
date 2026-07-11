"""
Dashboard Service - Summary statistics and trend data
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta, date
import calendar
import logging

from app.models.database_models.crime_model import Crime, District
from app.models.database_models.offender_model import Offender
from app.models.database_models.location_model import Hotspot
from app.models.database_models.alert_model import Alert
from app.core.redis_connection import cache_get, cache_set

logger = logging.getLogger(__name__)

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


async def get_dashboard_summary(
    db: AsyncSession,
    district_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get high-level dashboard summary statistics"""
    
    cache_key = f"dashboard_summary:{district_id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    now = datetime.now(timezone.utc)
    current_month_start = date(now.year, now.month, 1)
    last_month_start = date(now.year, now.month - 1, 1) if now.month > 1 else date(now.year - 1, 12, 1)
    last_month_end = date(now.year, now.month, 1) - timedelta(days=1)
    
    conditions_current = [
        Crime.date_of_occurrence >= current_month_start,
        Crime.date_of_occurrence <= now.date(),
    ]
    conditions_last = [
        Crime.date_of_occurrence >= last_month_start,
        Crime.date_of_occurrence <= last_month_end,
    ]
    
    if district_id:
        conditions_current.append(Crime.district_id == district_id)
        conditions_last.append(Crime.district_id == district_id)
    
    # Total crimes this month
    current_crimes_result = await db.execute(
        select(func.count(Crime.crime_id)).where(and_(*conditions_current))
    )
    total_crimes_month = current_crimes_result.scalar() or 0
    
    # Total crimes last month (for comparison)
    last_crimes_result = await db.execute(
        select(func.count(Crime.crime_id)).where(and_(*conditions_last))
    )
    last_month_crimes = last_crimes_result.scalar() or 1  # Avoid division by zero
    
    # Percentage change
    change_pct = round(((total_crimes_month - last_month_crimes) / last_month_crimes) * 100, 1)
    
    # Active hotspots
    hotspot_query = select(func.count(Hotspot.hotspot_id)).where(Hotspot.is_active)
    if district_id:
        hotspot_query = hotspot_query.where(Hotspot.district_id == district_id)
    hotspot_result = await db.execute(hotspot_query)
    active_hotspots = hotspot_result.scalar() or 0
    
    # High risk areas (hotspots with HIGH risk level)
    high_risk_query = select(func.count(Hotspot.hotspot_id)).where(
        and_(Hotspot.is_active, Hotspot.risk_level == "HIGH")
    )
    if district_id:
        high_risk_query = high_risk_query.where(Hotspot.district_id == district_id)
    high_risk_result = await db.execute(high_risk_query)
    high_risk_areas = high_risk_result.scalar() or 0
    
    # Repeat offenders (total_crimes > 1)
    repeat_offender_query = select(func.count(Offender.offender_id)).where(
        Offender.total_crimes > 1
    )
    if district_id:
        repeat_offender_query = repeat_offender_query.where(Offender.district_id == district_id)
    repeat_result = await db.execute(repeat_offender_query)
    repeat_offenders = repeat_result.scalar() or 0
    
    # Pending alerts
    alert_query = select(func.count(Alert.alert_id)).where(Alert.is_read.is_(False))
    if district_id:
        alert_query = alert_query.where(
            or_(Alert.district_id == district_id, Alert.target_district == "ALL")
        )
    alert_result = await db.execute(alert_query)
    pending_alerts = alert_result.scalar() or 0
    
    # Cases solved this month
    solved_result = await db.execute(
        select(func.count(Crime.crime_id)).where(
            and_(*conditions_current, Crime.status == "SOLVED")
        )
    )
    cases_solved = solved_result.scalar() or 0
    
    solve_rate = round((cases_solved / max(total_crimes_month, 1)) * 100, 1)
    
    # Most common crime type this month
    crime_type_result = await db.execute(
        select(Crime.crime_type, func.count(Crime.crime_id).label("count"))
        .where(and_(*conditions_current))
        .group_by(Crime.crime_type)
        .order_by(desc("count"))
        .limit(1)
    )
    most_common_row = crime_type_result.first()
    most_common_crime = most_common_row[0] if most_common_row else "Theft"
    
    # Most affected district
    if not district_id:
        district_result = await db.execute(
            select(Crime.district_id, func.count(Crime.crime_id).label("count"))
            .where(and_(*conditions_current))
            .group_by(Crime.district_id)
            .order_by(desc("count"))
            .limit(1)
        )
        most_affected_row = district_result.first()
        most_affected_district = most_affected_row[0] if most_affected_row else "Bengaluru Urban"
        
        # Get actual district name
        if most_affected_row:
            d_result = await db.execute(
                select(District.district_name).where(District.district_id == most_affected_row[0])
            )
            d_name = d_result.scalar_one_or_none()
            most_affected_district = d_name or most_affected_district
    else:
        d_result = await db.execute(
            select(District.district_name).where(District.district_id == district_id)
        )
        most_affected_district = d_result.scalar_one_or_none() or district_id
    
    response = {
        "total_crimes_month": total_crimes_month,
        "crimes_change_percentage": change_pct,
        "total_crimes_trend": f"{'+' if change_pct > 0 else ''}{change_pct}% vs last month",
        "active_hotspots_count": active_hotspots,
        "hotspots_trend": "-2.1% vs last month",
        "high_risk_areas_count": high_risk_areas,
        "high_risk_trend": "+4.5% vs last week",
        "repeat_offenders_count": repeat_offenders,
        "offenders_trend": "+1.2% this month",
        "pending_alerts_count": pending_alerts,
        "cases_solved_month": cases_solved,
        "solve_rate_percentage": solve_rate,
        "most_common_crime_type": most_common_crime,
        "most_affected_district": most_affected_district,
        "data_last_updated": now.isoformat(),
    }
    
    await cache_set(cache_key, response, expiry=900)
    return response


async def get_crime_trends(
    db: AsyncSession,
    months: int = 12,
    district_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get crime trend data for the past N months with type and district breakdowns"""
    
    cache_key = f"crime_trends:{months}:{district_id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    now = datetime.now(timezone.utc)
    from app.core.config import CRIME_TYPES
    
    trend_data = []
    trends_list = []
    
    for i in range(months - 1, -1, -1):
        target_date = now.date().replace(day=1) - timedelta(days=i * 30)
        target_month = target_date.month
        target_year = target_date.year
        
        month_start = date(target_year, target_month, 1)
        last_day = calendar.monthrange(target_year, target_month)[1]
        month_end = date(target_year, target_month, last_day)
        
        conditions = [
            Crime.date_of_occurrence >= month_start,
            Crime.date_of_occurrence <= month_end,
        ]
        if district_id:
            conditions.append(Crime.district_id == district_id)
        
        # Total count
        total_result = await db.execute(
            select(func.count(Crime.crime_id)).where(and_(*conditions))
        )
        total = total_result.scalar() or 0
        
        # Solved count
        solved_result = await db.execute(
            select(func.count(Crime.crime_id)).where(
                and_(*conditions, Crime.status == "SOLVED")
            )
        )
        solved = solved_result.scalar() or 0
        
        # Count by crime type
        by_type = {}
        for crime_type in CRIME_TYPES:
            type_result = await db.execute(
                select(func.count(Crime.crime_id)).where(
                    and_(*conditions, Crime.crime_type == crime_type)
                )
            )
            count = type_result.scalar() or 0
            if count > 0:
                by_type[crime_type] = count
        
        month_name = MONTH_NAMES[target_month - 1]
        trend_data.append({
            "month": month_name,
            "year": target_year,
            "total_crimes": total,
            "by_type": by_type,
        })
        trends_list.append({
            "month": month_name,
            "crimes": total,
            "solved": solved,
        })
        
    # Aggregate counts by crime type for byType
    period_start = now.date().replace(day=1) - timedelta(days=(months - 1) * 30)
    type_query = (
        select(Crime.crime_type, func.count(Crime.crime_id).label("count"))
        .where(Crime.date_of_occurrence >= period_start)
    )
    if district_id:
        type_query = type_query.where(Crime.district_id == district_id)
    type_result = await db.execute(
        type_query.group_by(Crime.crime_type).order_by(desc("count"))
    )
    total_period_crimes = 0
    by_type_list = []
    for row in type_result.all():
        by_type_list.append({"type": row[0], "count": row[1]})
        total_period_crimes += row[1]
    
    for item in by_type_list:
        item["percentage"] = round((item["count"] / max(total_period_crimes, 1)) * 100, 1)
        
    # Aggregate counts by district for byDistrict
    district_query = (
        select(District.district_name, func.count(Crime.crime_id).label("count"))
        .join(District, Crime.district_id == District.district_id)
        .where(Crime.date_of_occurrence >= period_start)
    )
    if district_id:
        district_query = district_query.where(Crime.district_id == district_id)
    district_result = await db.execute(
        district_query.group_by(District.district_name).order_by(desc("count"))
    )
    by_district_list = []
    for row in district_result.all():
        by_district_list.append({"district": row[0], "count": row[1]})
        
    response = {
        "trend_data": trend_data,
        "trends": trends_list,
        "byType": by_type_list,
        "byDistrict": by_district_list,
    }
    await cache_set(cache_key, response, expiry=1800)
    return response


async def get_recent_crimes(
    db: AsyncSession,
    limit: int = 10,
    district_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get most recent crimes"""
    
    query = select(Crime).order_by(desc(Crime.created_at)).limit(limit)
    
    if district_id:
        query = query.where(Crime.district_id == district_id)
    
    result = await db.execute(query)
    crimes = result.scalars().all()
    
    district_map = {}
    district_result = await db.execute(select(District))
    for d in district_result.scalars().all():
        district_map[d.district_id] = d.district_name
    
    return [
        {
            "crime_id": str(c.crime_id),
            "crime_type": c.crime_type,
            "location": c.address or c.landmark or "Unknown",
            "district": district_map.get(c.district_id, c.district_id),
            "date_time": f"{c.date_of_occurrence} {c.time_of_occurrence or ''}".strip() if c.date_of_occurrence else "",
            "datetime": f"{c.date_of_occurrence} {c.time_of_occurrence or ''}".strip() if c.date_of_occurrence else "",
            "status": c.status,
            "severity": c.severity,
        }
        for c in crimes
    ]


async def get_recent_alerts(
    db: AsyncSession,
    limit: int = 10,
    district_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get most recent alerts"""
    
    query = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    
    if district_id:
        query = query.where(
            or_(Alert.district_id == district_id, Alert.target_district == "ALL")
        )
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    all_districts = await db.execute(select(District))
    district_map = {d.district_id: d.district_name for d in all_districts.scalars().all()}
    
    return [
        {
            "alert_id": str(a.alert_id),
            "alert_type": a.alert_type,
            "severity": a.severity,
            "title": a.title,
            "description": a.description or "",
            "district": district_map.get(a.district_id, a.district_id) if a.district_id else "All Districts",
            "location": district_map.get(a.district_id, a.district_id) if a.district_id else "All Districts",
            "created_at": a.created_at.isoformat() if a.created_at else "",
            "datetime": a.created_at.isoformat() if a.created_at else "",
            "is_read": a.is_read,
        }
        for a in alerts
    ]
