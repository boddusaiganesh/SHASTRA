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
    
    import re
    if re.match(r"^[A-Z]{2}-\d{1,3}$", district_val):
        return district_val
        
    # Standardize names (e.g. Bangalore to Bengaluru)
    search_name = district_val.replace("Bangalore", "Bengaluru").strip()
    
    # 1. Try exact match first (safest for RBAC scoping)
    stmt_exact = select(District.district_id).where(
        or_(
            District.district_name.ilike(district_val.strip()),
            District.district_name.ilike(search_name)
        )
    )
    result = await db.execute(stmt_exact)
    resolved = result.scalars().first()
    if resolved:
        return resolved

    # 2. Fall back to substring match as a last resort, with a warning
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"District exact match failed for '{district_val}', attempting substring match")
    
    stmt_sub = select(District.district_id).where(
        District.district_name.ilike(f"%{district_val.strip()}%")
    )
    result = await db.execute(stmt_sub)
    resolved = result.scalars().first()
    if resolved:
        return resolved
        
    from app.core.config import settings
    if district_val in settings.KARNATAKA_DISTRICTS:
        return district_val
        
    return None
