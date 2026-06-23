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
    
    alert_list = [a.to_dict() for a in alerts]
    
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
        
        # Check for spike
        if daily_average > 0 and recent_count > 0:
            spike_percentage = ((recent_count - daily_average) / daily_average) * 100
            
            if spike_percentage >= crime_spike_threshold:
                severity = "CRITICAL" if spike_percentage >= 100 else "HIGH"
                
                await create_alert(
                    db=db,
                    alert_type="CRIME_SPIKE",
                    severity=severity,
                    title=f"Crime Spike Alert - {district.district_name}",
                    description=(
                        f"Crime rate in {district.district_name} has spiked by "
                        f"{spike_percentage:.1f}% in the last 24 hours "
                        f"({recent_count} incidents vs daily average of {daily_average:.1f}). "
                        f"Immediate attention required."
                    ),
                    district_id=district.district_id,
                    related_entity_id=district.district_id,
                    related_entity_type="DISTRICT",
                    generated_by="SYSTEM",
                )
    
    logger.info("Crime spike detection complete")


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
    return {
        "alerts": [a.to_dict() for a in alerts],
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

