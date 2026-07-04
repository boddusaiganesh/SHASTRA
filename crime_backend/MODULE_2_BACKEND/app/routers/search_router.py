from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from sqlalchemy import select, or_

from app.models.database_models.crime_model import Crime
from app.models.database_models.offender_model import Offender
from app.models.database_models.victim_model import Victim

router = APIRouter()

@router.get("")
async def global_search(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    like_q = f"%{q}%"
    
    # Search crimes
    crimes_result = await db.execute(
        select(Crime).where(
            or_(
                Crime.crime_reference_no.ilike(like_q),
                Crime.description.ilike(like_q),
                Crime.address.ilike(like_q)
            )
        ).limit(5)
    )
    crimes = crimes_result.scalars().all()
    
    # Search offenders
    offenders_result = await db.execute(
        select(Offender).where(
            or_(
                Offender.first_name.ilike(like_q),
                Offender.last_name.ilike(like_q)
            )
        ).limit(5)
    )
    offenders = offenders_result.scalars().all()
    
    # Search victims
    victims_result = await db.execute(
        select(Victim).where(
            or_(
                Victim.first_name.ilike(like_q),
                Victim.last_name.ilike(like_q),
                Victim.phone_number.ilike(like_q)
            )
        ).limit(5)
    )
    victims = victims_result.scalars().all()
    
    return {
        "success": True,
        "data": {
            "crimes": [c.to_dict() for c in crimes],
            "offenders": [o.to_dict() for o in offenders],
            "victims": [v.to_dict() for v in victims]
        }
    }
