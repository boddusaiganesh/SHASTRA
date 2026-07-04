"""
Offender Service - Profile management and MO analysis
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from typing import Optional, Dict, Any, List
import uuid
import logging

from app.models.database_models.offender_model import Offender
from app.models.database_models.crime_model import Crime, CrimeOffenderLink, District
from app.core.redis_connection import cache_get, cache_set

logger = logging.getLogger(__name__)


async def search_offenders(
    db: AsyncSession,
    name: Optional[str] = None,
    crime_type: Optional[str] = None,
    district_id: Optional[str] = None,
    risk_level: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Search and filter offenders"""
    
    query = select(Offender)
    count_query = select(func.count(Offender.offender_id))
    conditions = []
    
    if name:
        conditions.append(
            or_(
                Offender.first_name.ilike(f"%{name}%"),
                Offender.last_name.ilike(f"%{name}%"),
            )
        )
    if crime_type:
        conditions.append(Offender.preferred_crime_types.contains([crime_type]))
    if district_id:
        conditions.append(Offender.district_id == district_id)
    if risk_level:
        conditions.append(Offender.risk_level == risk_level)
    if status:
        conditions.append(Offender.status == status)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    total_result = await db.execute(count_query)
    total_count = total_result.scalar() or 0
    
    offset = (page - 1) * page_size
    query = query.order_by(desc(Offender.risk_score)).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    offenders = result.scalars().all()
    
    district_map = await _get_district_map(db)
    
    offender_list = []
    for o in offenders:
        offender_list.append({
            "offender_id": str(o.offender_id),
            "full_name": f"{o.first_name} {o.last_name}",
            "age": o.age,
            "status": o.status,
            "risk_level": o.risk_level,
            "risk_score": o.risk_score,
            "total_crimes": o.total_crimes,
            "last_offense": o.last_offense_date.isoformat() if o.last_offense_date else None,
            "district": district_map.get(o.district_id, o.district_id),
        })
    
    return {
        "offenders": offender_list,
        "total_count": total_count,
        "total_pages": (total_count + page_size - 1) // page_size,
    }


async def get_offender_profile(
    db: AsyncSession,
    offender_id: str,
) -> Optional[Dict[str, Any]]:
    """Get full offender profile with crime history"""
    from app.services.gemini_service import get_offender_ai_analysis
    
    try:
        offender_uuid = uuid.UUID(offender_id)
    except ValueError:
        return None
    
    result = await db.execute(
        select(Offender).where(Offender.offender_id == offender_uuid)
    )
    offender = result.scalar_one_or_none()
    
    if not offender:
        return None
    
    profile = offender.to_dict()
    
    # Get district name
    district_map = await _get_district_map(db)
    profile["district"] = district_map.get(offender.district_id, offender.district_id)
    
    # Get crime history
    link_result = await db.execute(
        select(CrimeOffenderLink).where(CrimeOffenderLink.offender_id == offender_uuid)
    )
    links = link_result.scalars().all()
    
    crime_history = []
    for link in links:
        cr = await db.execute(select(Crime).where(Crime.crime_id == link.crime_id))
        crime = cr.scalar_one_or_none()
        if crime:
            crime_history.append({
                "crime_id": str(crime.crime_id),
                "crime_reference_no": crime.crime_reference_no,
                "crime_type": crime.crime_type,
                "date": str(crime.date_of_occurrence),
                "district": district_map.get(crime.district_id, crime.district_id),
                "status": crime.status,
                "severity": crime.severity,
                "role_in_crime": link.role_in_crime,
                "is_confirmed": link.is_confirmed,
            })
    
    profile["crime_history"] = crime_history
    
    # Get linked locations from crime history
    linked_locations = []
    for crime_item in crime_history[:10]:
        cr = await db.execute(
            select(Crime).where(Crime.crime_reference_no == crime_item.get("crime_reference_no"))
        )
        crime = cr.scalar_one_or_none()
        if crime and crime.latitude and crime.longitude:
            linked_locations.append({
                "latitude": crime.latitude,
                "longitude": crime.longitude,
                "crime_type": crime.crime_type,
                "address": crime.address,
            })
    
    profile["linked_locations"] = linked_locations
    
    # Get AI assessment
    ai_assessment = await get_offender_ai_analysis(profile, crime_history)
    profile["ai_assessment"] = {
        "risk_narrative": ai_assessment,
        "reoffend_probability": offender.reoffend_probability,
        "recommended_monitoring": "Standard" if offender.risk_level == "LOW" else "Enhanced",
    }
    
    return profile


async def get_modus_operandi(
    db: AsyncSession,
    offender_id: str,
) -> Optional[Dict[str, Any]]:
    """Analyze and return offender's modus operandi"""
    from app.services.gemini_service import get_mo_analysis
    from collections import Counter
    
    try:
        offender_uuid = uuid.UUID(offender_id)
    except ValueError:
        return None
    
    # Get offender
    result = await db.execute(
        select(Offender).where(Offender.offender_id == offender_uuid)
    )
    offender = result.scalar_one_or_none()
    if not offender:
        return None
    
    # Get all crimes
    link_result = await db.execute(
        select(CrimeOffenderLink).where(CrimeOffenderLink.offender_id == offender_uuid)
    )
    links = link_result.scalars().all()
    
    crimes = []
    for link in links:
        cr = await db.execute(select(Crime).where(Crime.crime_id == link.crime_id))
        crime = cr.scalar_one_or_none()
        if crime:
            crimes.append(crime)
    
    if not crimes:
        return None
    
    # Analyze patterns
    crime_types = Counter([c.crime_type for c in crimes])
    time_patterns = Counter([c.time_of_occurrence[:2] if c.time_of_occurrence else "unknown" for c in crimes])
    day_patterns = Counter([c.day_of_week for c in crimes if c.day_of_week])
    weapons_used = Counter()
    for c in crimes:
        if c.weapons_used:
            for w in c.weapons_used:
                weapons_used[w] += 1
    
    # Determine preferred time of day
    from app.core.config import TIME_OF_DAY
    time_category_counts = {"MORNING": 0, "AFTERNOON": 0, "EVENING": 0, "NIGHT": 0}
    for hour_str, count in time_patterns.items():
        try:
            hour = int(hour_str)
            if 6 <= hour < 12:
                time_category_counts["MORNING"] += count
            elif 12 <= hour < 18:
                time_category_counts["AFTERNOON"] += count
            elif 18 <= hour < 22:
                time_category_counts["EVENING"] += count
            else:
                time_category_counts["NIGHT"] += count
        except:
            pass
    
    preferred_time = max(time_category_counts, key=time_category_counts.get)
    
    # Calculate average interval between crimes
    dates = sorted([c.date_of_occurrence for c in crimes if c.date_of_occurrence])
    intervals = []
    for i in range(1, len(dates)):
        intervals.append((dates[i] - dates[i-1]).days)
    avg_interval = int(sum(intervals) / len(intervals)) if intervals else 0
    
    # Calculate geographic range
    lats = [c.latitude for c in crimes if c.latitude]
    lons = [c.longitude for c in crimes if c.longitude]
    geographic_range = "Local (< 10 km)"
    if lats and lons:
        lat_range = max(lats) - min(lats)
        lon_range = max(lons) - min(lons)
        km_range = ((lat_range ** 2 + lon_range ** 2) ** 0.5) * 111
        if km_range > 50:
            geographic_range = "Wide (> 50 km)"
        elif km_range > 20:
            geographic_range = "Regional (20-50 km)"
        elif km_range > 10:
            geographic_range = "District-wide (10-20 km)"
    
    # Determine escalation trend
    if len(crimes) >= 3:
        recent_avg_severity = sum(
            1 if c.severity == "HIGH" else (0.5 if c.severity == "MEDIUM" else 0)
            for c in crimes[-3:]
        )
        early_avg_severity = sum(
            1 if c.severity == "HIGH" else (0.5 if c.severity == "MEDIUM" else 0)
            for c in crimes[:3]
        )
        if recent_avg_severity > early_avg_severity:
            escalation = "ESCALATING"
        elif recent_avg_severity < early_avg_severity:
            escalation = "DE_ESCALATING"
        else:
            escalation = "STABLE"
    else:
        escalation = "STABLE"
    
    mo_data = {
        "offender_id": offender_id,
        "preferred_crime_types": [
            {"crime_type": ct, "frequency": cnt, "percentage": round(cnt / len(crimes) * 100, 1)}
            for ct, cnt in crime_types.most_common(5)
        ],
        "preferred_locations": offender.preferred_locations or [],
        "preferred_time": preferred_time,
        "preferred_days": [
            {"day": d, "count": c}
            for d, c in day_patterns.most_common(3)
        ],
        "typical_targets": offender.typical_targets or "Mixed target profile",
        "weapons_pattern": [w for w, _ in weapons_used.most_common(5)],
        "escape_methods": "Unknown - under investigation",
        "accomplice_pattern": "SOLO" if not offender.known_associates else "WITH_PARTNER",
        "average_crime_interval": avg_interval,
        "geographic_range": geographic_range,
        "escalation_trend": escalation,
        "total_crimes_analyzed": len(crimes),
    }
    
    # Get AI MO summary
    mo_summary = await get_mo_analysis(mo_data, offender.to_dict())
    mo_data["ai_mo_summary"] = mo_summary
    
    return mo_data


async def _get_district_map(db: AsyncSession) -> Dict[str, str]:
    result = await db.execute(select(District))
    districts = result.scalars().all()
    return {d.district_id: d.district_name for d in districts}


async def get_offender_network(db: AsyncSession, offender_id: str) -> Optional[Dict[str, Any]]:
    """Get this offender's network (delegates to the network service)."""
    from app.services.network_service import get_node_detail
    return await get_node_detail(db, offender_id)


async def get_recidivism_risk(db: AsyncSession, offender_id: str) -> Optional[Dict[str, Any]]:
    """Get ML-based reoffend-risk scoring for an offender."""
    from app.ml_models.risk_scoring import calculate_offender_recidivism_risk
    try:
        offender_uuid = uuid.UUID(offender_id)
    except ValueError:
        return None

    result = await db.execute(select(Offender).where(Offender.offender_id == offender_uuid))
    offender = result.scalar_one_or_none()
    if not offender:
        return None

    risk = calculate_offender_recidivism_risk(offender.to_dict())
    return {
        "offender_id": offender_id,
        "reoffend_probability": risk.get("probability", offender.reoffend_probability or 0),
        "risk_level": risk.get("risk_level", offender.risk_level),
        "risk_factors": risk.get("factors", []),
        "model_used": "Risk Scoring Engine",
    }


async def create_offender(db: AsyncSession, payload: dict):
    valid_keys = [c.name for c in Offender.__table__.columns if c.name != "offender_id"]
    data = {k: v for k, v in payload.items() if k in valid_keys}
    if "date_of_birth" in data and isinstance(data["date_of_birth"], str):
        from datetime import datetime
        try:
            data["date_of_birth"] = datetime.strptime(data["date_of_birth"].split("T")[0], "%Y-%m-%d").date()
        except ValueError:
            pass
    if "last_offense_date" in data and isinstance(data["last_offense_date"], str):
        from datetime import datetime
        try:
            data["last_offense_date"] = datetime.strptime(data["last_offense_date"].split("T")[0], "%Y-%m-%d").date()
        except ValueError:
            pass
            
    offender = Offender(offender_id=uuid.uuid4(), **data)
    db.add(offender)
    await db.commit()
    await db.refresh(offender)
    return offender.to_dict()

async def update_offender(db: AsyncSession, offender_id: str, payload: dict):
    try:
        oid = uuid.UUID(offender_id)
    except ValueError:
        return None
    result = await db.execute(select(Offender).where(Offender.offender_id == oid))
    offender = result.scalar_one_or_none()
    if not offender:
        return None
        
    for k, v in payload.items():
        if hasattr(offender, k) and k != "offender_id":
            if (k == "date_of_birth" or k == "last_offense_date") and isinstance(v, str):
                from datetime import datetime
                try:
                    v = datetime.strptime(v.split("T")[0], "%Y-%m-%d").date()
                except ValueError:
                    pass
            setattr(offender, k, v)
    await db.commit()
    await db.refresh(offender)
    return offender.to_dict()
