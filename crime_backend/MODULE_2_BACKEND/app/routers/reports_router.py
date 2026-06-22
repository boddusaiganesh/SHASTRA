from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.report_service import (
    generate_executive_report,
    get_report_history,
    download_report
)

router = APIRouter()

@router.post("/generate")
async def generate_report(
    report_type: str = Query(..., description="E.g. DISTRICT_SUMMARY, STATE_WIDE"),
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await generate_executive_report(db, report_type, district_id)
    return {"success": True, "data": data}

@router.get("/history")
async def history(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_report_history(db, limit)
    return {"success": True, "data": data}

@router.get("/{report_id}/download")
async def download(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await download_report(db, report_id)
    return {"success": True, "data": data}
