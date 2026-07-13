from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.models.database_models.crime_model import District

async def resolve_district_id(db: AsyncSession, district_val: Optional[str]) -> Optional[str]:
    """
    Resolves human-readable district name (like 'Bengaluru Urban' or 'Mysuru')
    to district ID code (like 'KA-01' or 'KA-03').
    """
    if not district_val:
        return None
    if district_val.startswith("KA-"):
        return district_val
        
    # Standardize names (e.g. Bangalore to Bengaluru)
    search_name = district_val.replace("Bangalore", "Bengaluru").strip()
    
    stmt = select(District.district_id).where(
        or_(
            District.district_name.ilike(district_val.strip()),
            District.district_name.ilike(search_name),
            District.district_name.ilike(f"%{district_val.strip()}%")
        )
    )
    result = await db.execute(stmt)
    resolved = result.scalars().first()
    if resolved:
        return resolved
        
    from app.core.config import settings
    if district_val in settings.KARNATAKA_DISTRICTS:
        return district_val
        
    return None
