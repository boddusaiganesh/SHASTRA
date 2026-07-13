"""
Anomaly Detection Service
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid
import logging

from app.models.database_models.anomaly_model import Anomaly
from app.models.database_models.crime_model import Crime, District

logger = logging.getLogger(__name__)


async def get_anomaly_list(
    db: AsyncSession,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    district_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Get paginated list of anomalies"""
    
    query = select(Anomaly)
    count_query = select(func.count(Anomaly.anomaly_id))
    conditions = []
    
    if severity:
        conditions.append(Anomaly.severity == severity)
    if status:
        conditions.append(Anomaly.status == status)
    if district_id:
        conditions.append(Anomaly.district_id == district_id)
    if date_from:
        conditions.append(Anomaly.detected_at >= date_from)
    if date_to:
        conditions.append(Anomaly.detected_at <= date_to)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    total_result = await db.execute(count_query)
    total_count = total_result.scalar() or 0
    
    critical_result = await db.execute(
        select(func.count(Anomaly.anomaly_id)).where(Anomaly.severity == "CRITICAL")
    )
    critical_count = critical_result.scalar() or 0
    
    new_result = await db.execute(
        select(func.count(Anomaly.anomaly_id)).where(Anomaly.status == "NEW")
    )
    new_count = new_result.scalar() or 0
    
    offset = (page - 1) * page_size
    query = query.order_by(
        desc(Anomaly.detected_at)
    ).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    anomalies = result.scalars().all()
    
    district_result = await db.execute(select(District))
    district_map = {d.district_id: d.district_name for d in district_result.scalars().all()}
    
    anomaly_list = []
    for a in anomalies:
        d = a.to_dict()
        d["district"] = district_map.get(a.district_id, a.district_id)
        d["location"] = d["district"]
        d["confidence_score"] = (a.anomaly_score or 0) / 100
        d["affected_crimes_count"] = len(a.related_case_ids or [])
        anomaly_list.append(d)
    
    return {
        "anomalies": anomaly_list,
        "total_count": total_count,
        "critical_count": critical_count,
        "new_count": new_count,
    }


async def get_anomaly_detail(
    db: AsyncSession,
    anomaly_id: str,
) -> Optional[Dict[str, Any]]:
    """Get full detail of an anomaly"""
    from app.services.gemini_service import get_anomaly_explanation
    
    try:
        anomaly_uuid = uuid.UUID(anomaly_id)
    except ValueError:
        return None
    
    result = await db.execute(
        select(Anomaly).where(Anomaly.anomaly_id == anomaly_uuid)
    )
    anomaly = result.scalar_one_or_none()
    
    if not anomaly:
        return None
    
    detail = anomaly.to_dict()
    
    d_result = await db.execute(select(District).where(District.district_id == anomaly.district_id))
    d_row = d_result.scalar_one_or_none()
    detail["district"] = d_row.district_name if d_row else anomaly.district_id
    detail["location"] = detail["district"]
    detail["confidence_score"] = (anomaly.anomaly_score or 0) / 100
    detail["affected_crimes_count"] = len(anomaly.related_case_ids or [])
    
    # Get related crimes
    related_cases = []
    if anomaly.related_case_ids:
        for case_id in anomaly.related_case_ids[:5]:
            try:
                cr = await db.execute(
                    select(Crime).where(Crime.crime_id == uuid.UUID(case_id))
                )
                crime = cr.scalar_one_or_none()
                if crime:
                    related_cases.append({
                        "crime_id": str(crime.crime_id),
                        "crime_type": crime.crime_type,
                        "date": str(crime.date_of_occurrence),
                        "status": crime.status,
                        "severity": crime.severity,
                    })
            except:
                pass
    
    detail["related_cases"] = related_cases
    
    # Get AI explanation if not already present
    if not anomaly.ai_explanation:
        ai_response = await get_anomaly_explanation(detail)
        ai_explanation = ai_response.get("text", "")
        detail["is_fallback"] = ai_response.get("is_fallback", False)
        
        # Update the DB record
        from sqlalchemy import update
        await db.execute(
            update(Anomaly)
            .where(Anomaly.anomaly_id == anomaly_uuid)
            .values(ai_explanation=ai_explanation)
        )
        await db.commit()
        detail["ai_explanation"] = ai_explanation
    
    # Build timeline
    timeline = []
    if anomaly.detected_at:
        timeline.append({
            "event": "Anomaly Detected",
            "timestamp": anomaly.detected_at.isoformat(),
            "description": "Anomaly automatically detected by ML model",
        })
    if anomaly.status == "UNDER_REVIEW":
        timeline.append({
            "event": "Under Review",
            "timestamp": anomaly.created_at.isoformat() if anomaly.created_at else "",
            "description": "Assigned for investigation",
        })
    if anomaly.resolved_at:
        timeline.append({
            "event": "Resolved",
            "timestamp": anomaly.resolved_at.isoformat(),
            "description": f"Status changed to {anomaly.status}",
        })
    
    detail["timeline"] = timeline
    
    return detail


async def update_anomaly_status(
    db: AsyncSession,
    anomaly_id: str,
    new_status: str,
    assigned_officer: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Update the status of an anomaly"""
    from sqlalchemy import update
    
    try:
        anomaly_uuid = uuid.UUID(anomaly_id)
    except ValueError:
        raise ValueError(f"Invalid anomaly_id: {anomaly_id}")
    
    update_values = {"status": new_status}
    
    if new_status == "RESOLVED" or new_status == "FALSE_POSITIVE":
        update_values["resolved_at"] = datetime.now(timezone.utc)
    
    if assigned_officer:
        try:
            update_values["assigned_officer_id"] = uuid.UUID(assigned_officer)
        except:
            pass
    
    await db.execute(
        update(Anomaly)
        .where(Anomaly.anomaly_id == anomaly_uuid)
        .values(**update_values)
    )
    await db.commit()
    
    return {
        "success": True,
        "anomaly_id": anomaly_id,
        "updated_status": new_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def save_anomaly(
    db: AsyncSession,
    anomaly_type: str,
    severity: str,
    description: str,
    evidence_points: List[str],
    district_id: Optional[str] = None,
    crime_id: Optional[str] = None,
    anomaly_score: float = 0.0,
) -> Anomaly:
    """Save a new anomaly to the database"""
    
    anomaly = Anomaly(
        anomaly_type=anomaly_type,
        severity=severity.upper() if severity else severity,
        description=description,
        evidence_points=evidence_points,
        district_id=district_id,
        crime_id=uuid.UUID(crime_id) if crime_id else None,
        anomaly_score=anomaly_score,
        status="NEW",
    )
    
    db.add(anomaly)
    await db.commit()
    await db.refresh(anomaly)
    
    return anomaly
