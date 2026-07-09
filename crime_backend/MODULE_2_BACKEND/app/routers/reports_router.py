from fastapi import APIRouter, Depends, Query, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.security import get_current_user, require_role, scope_district_param
from app.services.report_service import (
    generate_report,
    get_saved_reports,
    get_report_by_id,
)
from app.utils.district_resolver import resolve_district_id

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.post("/generate")
@limiter.limit("5/minute")
async def generate_report_endpoint(
    request: Request,
    report_type: str = Query(...),
    report_name: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "INVESTIGATOR", "DISTRICT_OFFICER"]))
):
    from datetime import datetime
    resolved_district_id = await resolve_district_id(db, district_id)
    if current_user["role"] == "DISTRICT_OFFICER" and resolved_district_id != current_user.get("district_id"):
        raise HTTPException(status_code=403, detail="Access denied. District officers can only access their own district data.")
    name = report_name or f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M')}"
    data = await generate_report(
        db, report_type, name,
        date_from=date_from, date_to=date_to,
        district_id=resolved_district_id, user_id=current_user["user_id"],
    )
    return {"success": True, "data": data}

@router.get("/history")
async def history(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    district_id = None
    if current_user["role"] == "DISTRICT_OFFICER":
        district_id = current_user.get("district_id")
        
    data = await get_saved_reports(db, district_id=district_id, page_size=limit)
    return {"success": True, "data": data}

@router.get("/{report_id}/download")
async def download(
    report_id: str,
    format: str = Query("pdf"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "INVESTIGATOR", "DISTRICT_OFFICER"]))
):
    data = await get_report_by_id(db, report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Report not found")
        
    if current_user["role"] == "DISTRICT_OFFICER":
        report_district = data.get("parameters", {}).get("district_id")
        if report_district and report_district != current_user.get("district_id"):
            raise HTTPException(status_code=403, detail="Access denied. District officers can only download reports for their own district.")
        
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
