from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional, List, Dict, Any
import uuid

from app.models.database_models.victim_model import Victim
from app.models.database_models.crime_model import CrimeVictimLink, Crime


async def search_victims(db: AsyncSession, query: Optional[str], district_id: Optional[str], limit: int = 25) -> List[Dict[str, Any]]:
    stmt = select(Victim)
    if district_id:
        stmt = stmt.where(Victim.district_id == district_id)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Victim.first_name.ilike(like), Victim.last_name.ilike(like), Victim.phone_number.ilike(like)))
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return [v.to_dict() for v in result.scalars().all()]


async def create_victim(db: AsyncSession, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Extract only the fields that belong to Victim model to prevent errors
    valid_keys = ["first_name", "last_name", "date_of_birth", "age", "gender", "occupation", 
                  "address", "district_id", "phone_number", "vulnerability_factors"]
    victim_data = {k: v for k, v in payload.items() if k in valid_keys}
    
    if "date_of_birth" in victim_data and isinstance(victim_data["date_of_birth"], str):
        from datetime import datetime
        try:
            victim_data["date_of_birth"] = datetime.strptime(victim_data["date_of_birth"], "%Y-%m-%d").date()
        except ValueError:
            pass

    victim = Victim(victim_id=uuid.uuid4(), **victim_data)
    db.add(victim)
    await db.commit()
    await db.refresh(victim)
    return victim.to_dict()


async def get_victim_profile(db: AsyncSession, victim_id: str) -> Optional[Dict[str, Any]]:
    try:
        vid = uuid.UUID(victim_id)
    except ValueError:
        return None
        
    result = await db.execute(select(Victim).where(Victim.victim_id == vid))
    victim = result.scalar_one_or_none()
    if not victim:
        return None
        
    links = await db.execute(select(CrimeVictimLink).where(CrimeVictimLink.victim_id == vid))
    crime_ids = [l.crime_id for l in links.scalars().all()]
    crimes = []
    if crime_ids:
        crimes_result = await db.execute(select(Crime).where(Crime.crime_id.in_(crime_ids)))
        crimes = [c.to_dict() for c in crimes_result.scalars().all()]
        
    data = victim.to_dict()
    data["linked_crimes"] = crimes
    return data
