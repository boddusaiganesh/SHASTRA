"""
Alert Service - Alert management and generation
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, or_, update
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import uuid
import logging

from app.models.database_models.alert_model import Alert
from app.models.database_models.crime_model import District

logger = logging.getLogger(__name__)


async def get_alert_list(
    db: AsyncSession,
    filter_type: str = "ALL",
    district_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Get paginated list of alerts"""
    
    query = select(Alert)
    count_query = select(func.count(Alert.alert_id))
    conditions = []
    
    if filter_type == "UNREAD":
        conditions.append(Alert.is_read == False)
    elif filter_type == "CRITICAL":
        conditions.append(Alert.severity == "CRITICAL")
    
    if district_id:
        conditions.append(
            or_(Alert.district_id == district_id, Alert.target_district == "ALL")
        )
    if alert_type:
        conditions.append(Alert.alert_type == alert_type)
    if date_from:
        conditions.append(Alert.created_at >= date_from)
    if date_to:
        conditions.append(Alert.created_at <= date_to)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    total_result = await db.execute(count_query)
    total_count = total_result.scalar() or 0
    
    unread_result = await db.execute(
        select(func.count(Alert.alert_id)).where(Alert.is_read == False)
    )
    unread_count = unread_result.scalar() or 0
    
    critical_result = await db.execute(
        select(func.count(Alert.alert_id)).where(Alert.severity == "CRITICAL")
    )
    critical_count = critical_result.scalar() or 0
    
    offset = (page - 1) * page_size
    query = query.order_by(desc(Alert.created_at)).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    all_districts = await db.execute(select(District))
    district_map = {d.district_id: d.district_name for d in all_districts.scalars().all()}
    
    alert_list = []
    for a in alerts:
        d = a.to_dict()
        d["district"] = district_map.get(a.district_id, a.district_id) if a.district_id else "All Districts"
        d["location"] = d["district"]
        d["datetime"] = d.get("created_at") or datetime.now(timezone.utc).isoformat()
        alert_list.append(d)
    
    return {
        "alerts": alert_list,
        "total_count": total_count,
        "unread_count": unread_count,
        "critical_count": critical_count,
    }


async def mark_alert_read(
    db: AsyncSession,
    alert_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """Mark an alert as read"""
    
    try:
        alert_uuid = uuid.UUID(alert_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise ValueError("Invalid alert_id or user_id")
    
    now = datetime.now(timezone.utc)
    
    await db.execute(
        update(Alert)
        .where(Alert.alert_id == alert_uuid)
        .values(
            is_read=True,
            read_by=user_uuid,
            read_at=now,
        )
    )
    await db.commit()
    
    return {
        "success": True,
        "alert_id": alert_id,
        "read_at": now.isoformat(),
    }


async def create_alert(
    db: AsyncSession,
    alert_type: str,
    severity: str,
    title: str,
    description: str,
    district_id: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    target_role: str = "ALL",
    generated_by: str = "SYSTEM",
    expiry_hours: int = 72,
) -> Alert:
    """Create a new alert"""
    
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    
    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        title=title,
        description=description,
        district_id=district_id,
        related_entity_id=related_entity_id,
        related_entity_type=related_entity_type,
        target_role=target_role,
        target_district=district_id or "ALL",
        generated_by=generated_by,
        is_read=False,
        expires_at=expires_at,
    )
    
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    
    logger.info(f"Alert created: {alert_type} - {severity} - {title}")
    
    try:
        from app.core.websocket import manager
        await manager.broadcast({
            "type": "NEW_ALERT",
            "data": alert.to_dict()
        })
    except Exception as e:
        logger.error(f"Failed to broadcast alert: {e}")
    
    return alert


async def cleanup_expired_alerts(db: AsyncSession) -> int:
    """Remove expired alerts"""
    from sqlalchemy import delete
    
    now = datetime.now(timezone.utc)
    
    result = await db.execute(
        delete(Alert).where(Alert.expires_at < now)
    )
    await db.commit()
    
    count = result.rowcount
    logger.info(f"Cleaned up {count} expired alerts")
    return count


async def detect_and_generate_alerts(db: AsyncSession):
    """
    Main alert generation function - runs regularly to detect crime spikes
    and generate appropriate alerts
    """
    from app.core.config import settings
    from app.models.database_models.crime_model import Crime
    from datetime import date, timedelta
    
    logger.info("Running crime spike detection for alert generation...")
    
    today = date.today()
    last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    
    # Get districts
    from app.models.database_models.crime_model import District
    district_result = await db.execute(select(District))
    districts = district_result.scalars().all()
    
    # Load threshold from SystemSettings
    from app.models.database_models.system_settings_model import SystemSettings
    try:
        settings_result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
        system_settings = settings_result.scalar_one_or_none()
        crime_spike_threshold = (
            system_settings.crime_spike_percent 
            if system_settings and system_settings.crime_spike_percent is not None
            else settings.CRIME_SPIKE_THRESHOLD
        )
    except Exception as e:
        logger.warning(f"Failed to load SystemSettings, using default: {e}")
        crime_spike_threshold = settings.CRIME_SPIKE_THRESHOLD

    generated = []
    
    for district in districts:
        # Count crimes in last 24 hours
        recent_result = await db.execute(
            select(func.count(Crime.crime_id)).where(
                and_(
                    Crime.district_id == district.district_id,
                    Crime.created_at >= last_24h,
                )
            )
        )
        recent_count = recent_result.scalar() or 0
        
        # Count crimes in previous 30 days (daily average)
        thirty_days_ago = today - timedelta(days=30)
        baseline_result = await db.execute(
            select(func.count(Crime.crime_id)).where(
                and_(
                    Crime.district_id == district.district_id,
                    Crime.date_of_occurrence >= thirty_days_ago,
                    Crime.date_of_occurrence < today,
                )
            )
        )
        baseline_total = baseline_result.scalar() or 0
        daily_average = baseline_total / 30
        previous_count = baseline_total / 30
        
        # Check for spike
        if recent_count > previous_count * (1 + crime_spike_threshold/100) and recent_count >= 3:
            severity = "CRITICAL" if recent_count > previous_count * 2 else "HIGH"
            
            # Check for existing recent alert
            recent = await db.execute(
                select(Alert)
                .where(Alert.district_id == district.district_id)
                .where(Alert.title.ilike("%CRIME_SPIKE%"))
                .where(Alert.created_at >= datetime.now(timezone.utc) - timedelta(hours=24))
            )
            if recent.scalars().first():
                continue
                
            new_alert = Alert(
                alert_type="CRIME_SPIKE",
                title=f"Crime Spike - {district.district_name}",
                severity=severity,
                district_id=district.district_id,
                description=f"Crime cases have increased by {int((recent_count - previous_count) / max(1, previous_count) * 100)}%. "
                            f"Current count: {recent_count} vs Daily Average: {previous_count:.1f}.",
                is_read=False,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            db.add(new_alert)
            generated.append(new_alert)
            
    await db.commit()
    
    # Broadcast alerts
    from app.core.websocket import manager
    from app.services.notification_service import notify_high_priority_alert
    
    for alert in generated:
        await manager.broadcast({"type": "NEW_ALERT", "data": alert.to_dict()})
        if alert.severity in ["HIGH", "CRITICAL"]:
            await notify_high_priority_alert(alert.to_dict(), ["district_officer@ksp.gov.in"])
            
    logger.info(f"Generated {len(generated)} automated alerts.")


async def get_active_alerts(
    db: AsyncSession,
    district_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get all currently active (non-expired) alerts — used by the Alerts page."""
    now = datetime.now(timezone.utc)
    conditions = [or_(Alert.expires_at.is_(None), Alert.expires_at >= now)]
    if district_id:
        conditions.append(or_(Alert.district_id == district_id, Alert.target_district == "ALL"))

    query = select(Alert).where(and_(*conditions)).order_by(desc(Alert.created_at))
    result = await db.execute(query)
    alerts = result.scalars().all()

    unread_result = await db.execute(
        select(func.count(Alert.alert_id)).where(and_(*conditions, Alert.is_read == False))
    )
    
    all_districts = await db.execute(select(District))
    district_map = {d.district_id: d.district_name for d in all_districts.scalars().all()}
    
    alert_list = []
    for a in alerts:
        d = a.to_dict()
        d["district"] = district_map.get(a.district_id, a.district_id) if a.district_id else "All Districts"
        d["location"] = d["district"]
        d["datetime"] = d.get("created_at") or datetime.now(timezone.utc).isoformat()
        alert_list.append(d)
        
    return {
        "alerts": alert_list,
        "total_count": len(alerts),
        "unread_count": unread_result.scalar() or 0,
    }


async def dismiss_alert(db: AsyncSession, alert_id: str) -> Dict[str, Any]:
    """Permanently dismiss/delete an alert."""
    from sqlalchemy import delete
    try:
        alert_uuid = uuid.UUID(alert_id)
    except ValueError:
        raise ValueError("Invalid alert_id")

    await db.execute(delete(Alert).where(Alert.alert_id == alert_uuid))
    await db.commit()
    return {"success": True, "alert_id": alert_id, "dismissed": True}

