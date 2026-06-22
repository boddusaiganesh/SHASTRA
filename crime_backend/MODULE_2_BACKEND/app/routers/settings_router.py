from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.auth_service import get_user_profile

router = APIRouter()

@router.get("/profile")
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_user_profile(db, current_user["user_id"])
    return {"success": True, "data": data}
