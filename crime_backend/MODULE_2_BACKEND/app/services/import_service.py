import csv
import io
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database_models.crime_model import Crime
from app.models.database_models.offender_model import Offender
from app.models.database_models.victim_model import Victim

logger = logging.getLogger(__name__)

async def parse_and_import_csv(db: AsyncSession, file_content: bytes, model_type: str, user_id: str) -> Dict[str, Any]:
    if len(file_content) > 5 * 1024 * 1024:
        raise ValueError("File exceeds 5MB limit.")
    content = file_content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(content))
    records = list(reader)
    if len(records) > 5000:
        raise ValueError("File exceeds 5000 rows limit.")
    return await bulk_import_records(db, records, model_type, user_id)

async def parse_and_import_json(db: AsyncSession, file_content: bytes, model_type: str, user_id: str) -> Dict[str, Any]:
    if len(file_content) > 5 * 1024 * 1024:
        raise ValueError("File exceeds 5MB limit.")
    records = json.loads(file_content.decode('utf-8'))
    if not isinstance(records, list):
        records = [records]
    if len(records) > 5000:
        raise ValueError("File exceeds 5000 rows limit.")
    return await bulk_import_records(db, records, model_type, user_id)

async def bulk_import_records(db: AsyncSession, records: List[Dict[str, Any]], model_type: str, user_id: str) -> Dict[str, Any]:
    success_count = 0
    errors = []
    
    for i, record in enumerate(records):
        try:
            if model_type == "crimes":
                await _import_crime(db, record, user_id)
            elif model_type == "offenders":
                await _import_offender(db, record)
            elif model_type == "victims":
                await _import_victim(db, record)
            else:
                raise ValueError(f"Unknown model_type: {model_type}")
            success_count += 1
        except Exception as e:
            errors.append({"row": i + 1, "error": str(e)})
            
    await db.commit()
    
    return {
        "total": len(records),
        "successful": success_count,
        "failed": len(errors),
        "errors": errors[:50]  # Return max 50 errors
    }

async def _import_crime(db: AsyncSession, data: dict, user_id: str):
    from datetime import date
    try:
        dt = data.get("date_of_occurrence", "")
        crime_date = datetime.strptime(dt.split("T")[0], "%Y-%m-%d").date() if dt else date.today()
    except Exception:
        crime_date = date.today()
        
    ref_no = data.get("crime_reference_no") or f"IMP/{datetime.now().year}/{str(uuid.uuid4())[:8].upper()}"
    
    crime = Crime(
        crime_id=uuid.uuid4(),
        crime_reference_no=ref_no,
        crime_type=data.get("crime_type", "OTHER"),
        crime_sub_type=data.get("crime_sub_type"),
        description=data.get("description"),
        date_of_occurrence=crime_date,
        time_of_occurrence=data.get("time_of_occurrence"),
        day_of_week=crime_date.strftime("%A"),
        month=crime_date.month,
        year=crime_date.year,
        district_id=data.get("district_id") or None,
        police_station_id=data.get("police_station_id"),
        latitude=float(data["latitude"]) if data.get("latitude") else None,
        longitude=float(data["longitude"]) if data.get("longitude") else None,
        address=data.get("address"),
        status=data.get("status", "REPORTED"),
        severity=data.get("severity", "MEDIUM"),
        reporting_officer_id=uuid.UUID(user_id) if user_id else None,
    )
    db.add(crime)
    await db.flush()
    
    from app.models.database_models.crime_model import CrimeOffenderLink, CrimeVictimLink
    
    offender_ids_str = data.get("offender_ids") or data.get("offender_id")
    if offender_ids_str:
        for oid in str(offender_ids_str).split(','):
            oid = oid.strip()
            if oid:
                try:
                    db.add(CrimeOffenderLink(link_id=uuid.uuid4(), crime_id=crime.crime_id, offender_id=uuid.UUID(oid)))
                except:
                    pass

    victim_ids_str = data.get("victim_ids") or data.get("victim_id")
    if victim_ids_str:
        for vid in str(victim_ids_str).split(','):
            vid = vid.strip()
            if vid:
                try:
                    db.add(CrimeVictimLink(link_id=uuid.uuid4(), crime_id=crime.crime_id, victim_id=uuid.UUID(vid)))
                except:
                    pass

async def _import_offender(db: AsyncSession, data: dict):
    try:
        dob_str = data.get("date_of_birth", "")
        dob = datetime.strptime(dob_str.split("T")[0], "%Y-%m-%d").date() if dob_str else None
    except Exception:
        dob = None
        
    try:
        lod_str = data.get("last_offense_date", "")
        lod = datetime.strptime(lod_str.split("T")[0], "%Y-%m-%d").date() if lod_str else None
    except Exception:
        lod = None

    offender = Offender(
        offender_id=uuid.uuid4(),
        first_name=data.get("first_name", "Unknown"),
        last_name=data.get("last_name", ""),
        date_of_birth=dob,
        age=int(data["age"]) if data.get("age") else None,
        gender=data.get("gender"),
        district_id=data.get("district_id"),
        risk_level=data.get("risk_level", "LOW"),
        status=data.get("status", "ACTIVE"),
        last_offense_date=lod,
    )
    db.add(offender)
    await db.flush()
    
    from app.core.neo4j_connection import sync_offender_to_neo4j
    try:
        await sync_offender_to_neo4j({
            "offender_id": str(offender.offender_id),
            "name": f"{offender.first_name} {offender.last_name}",
            "risk_level": offender.risk_level,
            "risk_score": 0,
            "crime_count": 0,
            "status": offender.status,
            "district_id": offender.district_id,
            "crime_types": [],
        })
    except Exception as e:
        logger.error(f"Neo4j sync error: {e}")

async def _import_victim(db: AsyncSession, data: dict):
    try:
        dob_str = data.get("date_of_birth", "")
        dob = datetime.strptime(dob_str.split("T")[0], "%Y-%m-%d").date() if dob_str else None
    except Exception:
        dob = None

    victim = Victim(
        victim_id=uuid.uuid4(),
        first_name=data.get("first_name", "Unknown"),
        last_name=data.get("last_name", ""),
        date_of_birth=dob,
        age=int(data["age"]) if data.get("age") else None,
        gender=data.get("gender"),
        district_id=data.get("district_id"),
        phone_number=data.get("phone_number"),
    )
    db.add(victim)
    await db.flush()
    
    from app.core.neo4j_connection import sync_victim_to_neo4j
    try:
        await sync_victim_to_neo4j({
            "victim_id": str(victim.victim_id),
            "name": f"{victim.first_name} {victim.last_name}",
            "district_id": victim.district_id,
            "vulnerability_level": "UNKNOWN",
        })
    except Exception as e:
        logger.error(f"Neo4j sync error: {e}")
