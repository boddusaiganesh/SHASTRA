"""
Crime Service - Business logic for crime data operations
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, delete
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging

from app.models.database_models.crime_model import Crime, District, PoliceStation, CrimeOffenderLink, CrimeVictimLink
from app.models.database_models.offender_model import Offender
from app.models.database_models.victim_model import Victim
from app.core.redis_connection import cache_get, cache_set

logger = logging.getLogger(__name__)



async def get_crime_detail(db: AsyncSession, crime_id: str) -> Optional[Dict[str, Any]]:
    """Get full detail of a single crime"""
    
    try:
        crime_uuid = uuid.UUID(crime_id)
    except ValueError:
        return None
    
    result = await db.execute(select(Crime).where(Crime.crime_id == crime_uuid))
    crime = result.scalar_one_or_none()
    
    if not crime:
        return None
    
    crime_dict = crime.to_dict()
    
    # Get district name
    district_result = await db.execute(
        select(District).where(District.district_id == crime.district_id)
    )
    district = district_result.scalar_one_or_none()
    crime_dict["district"] = district.district_name if district else crime.district_id
    
    # Get station name
    if crime.police_station_id:
        station_result = await db.execute(
            select(PoliceStation).where(PoliceStation.station_id == crime.police_station_id)
        )
        station = station_result.scalar_one_or_none()
        crime_dict["police_station"] = station.station_name if station else ""
    else:
        crime_dict["police_station"] = ""
    
    # Get linked victims
    victim_links = await db.execute(
        select(CrimeVictimLink).where(CrimeVictimLink.crime_id == crime_uuid)
    )
    victim_link_list = victim_links.scalars().all()
    victims = []
    for link in victim_link_list:
        victim_result = await db.execute(
            select(Victim).where(Victim.victim_id == link.victim_id)
        )
        victim = victim_result.scalar_one_or_none()
        if victim:
            v = victim.to_dict()
            v["injury_level"] = link.injury_level
            victims.append(v)
    crime_dict["victims"] = victims
    
    # Get linked offenders
    offender_links = await db.execute(
        select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id == crime_uuid)
    )
    offender_link_list = offender_links.scalars().all()
    offenders = []
    for link in offender_link_list:
        offender_result = await db.execute(
            select(Offender).where(Offender.offender_id == link.offender_id)
        )
        offender = offender_result.scalar_one_or_none()
        if offender:
            o = {
                "offender_id": str(offender.offender_id),
                "full_name": f"{offender.first_name} {offender.last_name}",
                "role_in_crime": link.role_in_crime,
                "is_confirmed": link.is_confirmed,
                "risk_level": offender.risk_level,
            }
            offenders.append(o)
    crime_dict["offenders"] = offenders
    
    return crime_dict


async def get_crimes_filtered(
    db: AsyncSession,
    district_id: Optional[str] = None,
    crime_type: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Get paginated and filtered list of crimes"""
    
    query = select(Crime)
    count_query = select(func.count(Crime.crime_id))
    conditions = []
    
    if district_id:
        conditions.append(Crime.district_id == district_id)
    if crime_type:
        conditions.append(Crime.crime_type == crime_type)
    if status:
        conditions.append(Crime.status == status)
    if date_from:
        conditions.append(Crime.date_of_occurrence >= date_from)
    if date_to:
        conditions.append(Crime.date_of_occurrence <= date_to)
    if severity:
        conditions.append(Crime.severity == severity)
    
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # Get total count
    total_result = await db.execute(count_query)
    total_count = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(desc(Crime.date_of_occurrence)).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    crimes = result.scalars().all()
    
    district_map = await _get_district_map(db)
    
    crime_list = []
    for crime in crimes:
        c = crime.to_dict()
        c["district"] = district_map.get(crime.district_id, crime.district_id)
        crime_list.append(c)
    
    total_pages = (total_count + page_size - 1) // page_size
    
    return {
        "crimes": crime_list,
        "total_count": total_count,
        "page": page,
        "total_pages": total_pages,
    }


async def create_crime(db: AsyncSession, crime_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Create a new crime record"""
    from datetime import date as date_type
    from app.models.database_models.crime_model import CrimeOffenderLink, CrimeVictimLink
    from app.core.neo4j_connection import create_criminal_relationship
    
    # Generate reference number
    ref_no = f"KSP/{datetime.now(timezone.utc).year}/{str(uuid.uuid4())[:8].upper()}"
    
    crime_date = date_type.fromisoformat(crime_data["date_of_occurrence"])
    
    crime = Crime(
        crime_reference_no=ref_no,
        crime_type=crime_data["crime_type"],
        crime_sub_type=crime_data.get("crime_sub_type"),
        description=crime_data.get("description"),
        date_of_occurrence=crime_date,
        time_of_occurrence=crime_data.get("time_of_occurrence"),
        day_of_week=crime_date.strftime("%A"),
        month=crime_date.month,
        year=crime_date.year,
        district_id=crime_data["district_id"],
        police_station_id=crime_data.get("police_station_id"),
        latitude=crime_data.get("latitude"),
        longitude=crime_data.get("longitude"),
        address=crime_data.get("address"),
        landmark=crime_data.get("landmark"),
        status=crime_data.get("status", "REPORTED"),
        severity=crime_data.get("severity", "MEDIUM"),
        weapons_used=crime_data.get("weapons_used", []),
        modus_operandi=crime_data.get("modus_operandi"),
        property_stolen=crime_data.get("property_stolen"),
        property_value=crime_data.get("property_value"),
        fir_number=crime_data.get("fir_number"),
        reporting_officer_id=uuid.UUID(user_id) if user_id else None,
    )
    
    db.add(crime)
    await db.flush()  # get crime.crime_id before commit

    for offender_id in crime_data.get("offender_ids", []):
        db.add(CrimeOffenderLink(link_id=uuid.uuid4(), crime_id=crime.crime_id, offender_id=uuid.UUID(offender_id)))
    for victim_id in crime_data.get("victim_ids", []):
        db.add(CrimeVictimLink(link_id=uuid.uuid4(), crime_id=crime.crime_id, victim_id=uuid.UUID(victim_id)))

    await db.commit()
    await db.refresh(crime)
    
    # Best-effort graph sync
    for offender_id in crime_data.get("offender_ids", []):
        try:
            await create_criminal_relationship(
                offender_id=offender_id,
                crime_id=str(crime.crime_id),
                crime_type=crime.crime_type,
            )
        except Exception as e:
            logger.warning(f"Neo4j sync skipped for crime {crime.crime_id}: {e}")
            
    return crime.to_dict()


async def _get_district_map(db: AsyncSession) -> Dict[str, str]:
    """Get a mapping of district_id to district_name"""
    result = await db.execute(select(District))
    districts = result.scalars().all()
    return {d.district_id: d.district_name for d in districts}


async def _get_station_map(db: AsyncSession) -> Dict[str, str]:
    """Get a mapping of station_id to station_name"""
    result = await db.execute(select(PoliceStation))
    stations = result.scalars().all()
    return {s.station_id: s.station_name for s in stations}


ALLOWED_UPDATE_FIELDS = {
    "crime_type", "status", "severity", "description", "address", "landmark",
    "latitude", "longitude", "date_of_occurrence", "modus_operandi", "evidence_notes",
    "crime_sub_type", "time_of_occurrence", "weapons_used", "property_stolen",
    "property_value", "fir_number"
}

async def update_crime_record(db: AsyncSession, crime_id: str, payload: dict, current_user: dict):
    try:
        cid = uuid.UUID(crime_id)
    except ValueError:
        return None
    
    result = await db.execute(select(Crime).where(Crime.crime_id == cid))
    crime = result.scalar_one_or_none()
    if not crime:
        return None
        
    if current_user["role"] == "DISTRICT_OFFICER" and crime.district_id != current_user.get("district_id"):
        raise PermissionError("District officers can only update crimes in their own district.")
        
    for k, v in payload.items():
        if k in ALLOWED_UPDATE_FIELDS and hasattr(crime, k):
            setattr(crime, k, v)
            
    from app.models.database_models.crime_model import CrimeOffenderLink, CrimeVictimLink
    from app.core.neo4j_connection import create_criminal_relationship
    
    # Handle offender updates if provided
    if "offender_ids" in payload:
        new_offenders = set(payload["offender_ids"])
        existing_links = await db.execute(select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id == cid))
        existing_offenders = {str(link.offender_id) for link in existing_links.scalars().all()}
        
        # Remove old
        to_remove = existing_offenders - new_offenders
        if to_remove:
            await db.execute(delete(CrimeOffenderLink).where(
                and_(CrimeOffenderLink.crime_id == cid, CrimeOffenderLink.offender_id.in_([uuid.UUID(o) for o in to_remove]))
            ))
            
        # Add new
        to_add = new_offenders - existing_offenders
        for offender_id in to_add:
            db.add(CrimeOffenderLink(link_id=uuid.uuid4(), crime_id=cid, offender_id=uuid.UUID(offender_id)))
            try:
                await create_criminal_relationship(offender_id, str(cid), crime.crime_type)
            except Exception as e:
                logger.warning(f"Neo4j sync skipped for crime {cid}: {e}")

    # Handle victim updates if provided
    if "victim_ids" in payload:
        new_victims = set(payload["victim_ids"])
        existing_links = await db.execute(select(CrimeVictimLink).where(CrimeVictimLink.crime_id == cid))
        existing_victims = {str(link.victim_id) for link in existing_links.scalars().all()}
        
        to_remove = existing_victims - new_victims
        if to_remove:
            await db.execute(delete(CrimeVictimLink).where(
                and_(CrimeVictimLink.crime_id == cid, CrimeVictimLink.victim_id.in_([uuid.UUID(v) for v in to_remove]))
            ))
            
        to_add = new_victims - existing_victims
        for victim_id in to_add:
            db.add(CrimeVictimLink(link_id=uuid.uuid4(), crime_id=cid, victim_id=uuid.UUID(victim_id)))
            
    await db.commit()
    await db.refresh(crime)
    return crime.to_dict()


async def delete_crime_record(db: AsyncSession, crime_id: str) -> bool:
    try:
        cid = uuid.UUID(crime_id)
    except ValueError:
        return False
    result = await db.execute(select(Crime).where(Crime.crime_id == cid))
    crime = result.scalar_one_or_none()
    if not crime:
        return False
        
    from app.models.database_models.crime_model import CrimeOffenderLink, CrimeVictimLink
    
    # Delete links first
    await db.execute(delete(CrimeOffenderLink).where(CrimeOffenderLink.crime_id == cid))
    await db.execute(delete(CrimeVictimLink).where(CrimeVictimLink.crime_id == cid))
    
    # Optionally: remove from Neo4j, though graph cleanup is usually handled async or by orphan sweeps
    try:
        from app.core.neo4j_connection import run_neo4j_query
        await run_neo4j_query("MATCH (c:Crime {crime_id: $cid}) DETACH DELETE c", {"cid": str(cid)})
    except Exception as e:
        logger.warning(f"Failed to delete crime {cid} from Neo4j: {e}")
        
    await db.delete(crime)
    await db.commit()
    return True
