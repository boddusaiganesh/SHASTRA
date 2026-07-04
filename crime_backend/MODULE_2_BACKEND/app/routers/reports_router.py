from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.services.report_service import (
    generate_report,
    get_saved_reports,
    get_report_by_id,
)

router = APIRouter()

@router.post("/generate")
async def generate_report_endpoint(
    report_type: str = Query(...),
    report_name: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "INVESTIGATOR", "DISTRICT_OFFICER"]))
):
    from datetime import datetime
    name = report_name or f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M')}"
    data = await generate_report(
        db, report_type, name,
        date_from=date_from, date_to=date_to,
        district_id=district_id, user_id=current_user["user_id"],
    )
    return {"success": True, "data": data}

@router.get("/history")
async def history(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_saved_reports(db, page_size=limit)
    return {"success": True, "data": data}

@router.get("/{report_id}/download")
async def download(
    report_id: str,
    format: str = Query("pdf"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    data = await get_report_by_id(db, report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Report not found")
        
    from app.services.report_service import export_report_pdf, export_report_csv
    if format.lower() == "csv":
        content = export_report_csv(data)
        media_type = "text/csv"
        ext = "csv"
    else:
        content = export_report_pdf(data)
        media_type = "application/pdf"
        ext = "pdf"
        
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=report_{report_id}.{ext}"}
    )
