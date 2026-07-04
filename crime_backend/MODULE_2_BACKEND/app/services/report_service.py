"""
Report Generation Service
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, true as sa_true
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, date
import uuid
import logging

from app.models.database_models.report_model import Report
from app.models.database_models.crime_model import Crime, District
from app.models.database_models.offender_model import Offender
from app.models.database_models.location_model import Hotspot

logger = logging.getLogger(__name__)


async def generate_report(
    db: AsyncSession,
    report_type: str,
    report_name: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    district_id: Optional[str] = None,
    crime_types_included: List[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a comprehensive report"""
    from app.services.gemini_service import get_report_narrative
    
    logger.info(f"Generating report: {report_type} - {report_name}")
    
    # Parse dates
    try:
        d_from = date.fromisoformat(date_from) if date_from else None
        d_to = date.fromisoformat(date_to) if date_to else None
    except:
        d_from = None
        d_to = None
    
    # Build base conditions
    conditions = []
    if d_from:
        conditions.append(Crime.date_of_occurrence >= d_from)
    if d_to:
        conditions.append(Crime.date_of_occurrence <= d_to)
    if district_id:
        conditions.append(Crime.district_id == district_id)
    if crime_types_included:
        from sqlalchemy import or_
        conditions.append(or_(*[Crime.crime_type == ct for ct in crime_types_included]))
    
    # Gather report data based on type
    report_data = {}
    
    if report_type in ["DISTRICT_SUMMARY", "CRIME_TREND"]:
        # Crime statistics
        total_result = await db.execute(
            select(func.count(Crime.crime_id)).where(and_(*conditions) if conditions else sa_true())
        )
        report_data["total_crimes"] = total_result.scalar() or 0
        
        # By crime type
        type_result = await db.execute(
            select(Crime.crime_type, func.count(Crime.crime_id).label("count"))
            .where(and_(*conditions) if conditions else sa_true())
            .group_by(Crime.crime_type)
            .order_by(desc("count"))
        )
        report_data["by_crime_type"] = [
            {"crime_type": row[0], "count": row[1]}
            for row in type_result.all()
        ]
        
        # By status
        status_result = await db.execute(
            select(Crime.status, func.count(Crime.crime_id).label("count"))
            .where(and_(*conditions) if conditions else sa_true())
            .group_by(Crime.status)
        )
        report_data["by_status"] = {
            row[0]: row[1] for row in status_result.all()
        }
        
        # By severity
        severity_result = await db.execute(
            select(Crime.severity, func.count(Crime.crime_id).label("count"))
            .where(and_(*conditions) if conditions else sa_true())
            .group_by(Crime.severity)
        )
        report_data["by_severity"] = {
            row[0]: row[1] for row in severity_result.all()
        }
        
        # By district (for state-wide reports)
        if not district_id:
            district_result = await db.execute(
                select(Crime.district_id, func.count(Crime.crime_id).label("count"))
                .where(and_(*conditions) if conditions else sa_true())
                .group_by(Crime.district_id)
                .order_by(desc("count"))
                .limit(10)
            )
            
            all_districts = await db.execute(select(District))
            district_map = {d.district_id: d.district_name for d in all_districts.scalars().all()}
            
            report_data["by_district"] = [
                {"district": district_map.get(row[0], row[0]), "count": row[1]}
                for row in district_result.all()
            ]
    
    if report_type == "OFFENDER":
        # Offender statistics
        offender_query = select(func.count(Offender.offender_id))
        if district_id:
            offender_query = offender_query.where(Offender.district_id == district_id)
        
        total_offenders = await db.execute(offender_query)
        report_data["total_offenders"] = total_offenders.scalar() or 0
        
        high_risk_result = await db.execute(
            select(func.count(Offender.offender_id)).where(Offender.risk_level == "HIGH")
        )
        report_data["high_risk_offenders"] = high_risk_result.scalar() or 0
        
        active_result = await db.execute(
            select(func.count(Offender.offender_id)).where(Offender.status == "ACTIVE")
        )
        report_data["active_offenders"] = active_result.scalar() or 0
        
        repeat_result = await db.execute(
            select(func.count(Offender.offender_id)).where(Offender.total_crimes > 1)
        )
        report_data["repeat_offenders"] = repeat_result.scalar() or 0
    
    if report_type == "HOTSPOT":
        hotspot_query = select(Hotspot).where(Hotspot.is_active == True)
        if district_id:
            hotspot_query = hotspot_query.where(Hotspot.district_id == district_id)
        
        hotspot_result = await db.execute(hotspot_query.order_by(desc(Hotspot.risk_score)).limit(20))
        hotspots = hotspot_result.scalars().all()
        
        report_data["total_hotspots"] = len(hotspots)
        report_data["high_risk_hotspots"] = sum(1 for h in hotspots if h.risk_level == "HIGH")
        report_data["top_hotspots"] = [
            {
                "name": h.hotspot_name,
                "crime_count": h.crime_count,
                "risk_level": h.risk_level,
                "dominant_crime": h.dominant_crime_type,
                "trend": h.trend,
            }
            for h in hotspots[:10]
        ]
    
    # Add report metadata
    report_data["report_type"] = report_type
    report_data["date_from"] = date_from
    report_data["date_to"] = date_to
    report_data["district_id"] = district_id
    report_data["generated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Generate AI narrative
    ai_narrative = await get_report_narrative(report_data, report_type)
    
    # Save report to database
    report = Report(
        report_type=report_type,
        report_name=report_name,
        generated_by=uuid.UUID(user_id) if user_id else None,
        date_from=d_from,
        date_to=d_to,
        district_id=district_id,
        crime_types_included=crime_types_included or [],
        report_data=report_data,
        ai_narrative=ai_narrative,
        status="READY",
    )
    
    db.add(report)
    await db.commit()
    await db.refresh(report)
    
    result = report.to_dict()
    result["ai_narrative"] = ai_narrative
    
    logger.info(f"Report generated successfully: {report.report_id}")
    
    return result


async def get_saved_reports(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Get list of saved reports"""
    
    count_result = await db.execute(select(func.count(Report.report_id)))
    total_count = count_result.scalar() or 0
    
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Report)
        .order_by(desc(Report.created_at))
        .offset(offset)
        .limit(page_size)
    )
    reports = result.scalars().all()
    
    all_districts = await db.execute(select(District))
    district_map = {d.district_id: d.district_name for d in all_districts.scalars().all()}
    
    report_list = []
    for r in reports:
        report_list.append({
            "report_id": str(r.report_id),
            "report_type": r.report_type,
            "report_name": r.report_name,
            "generated_by": str(r.generated_by) if r.generated_by else "System",
            "date_from": r.date_from.isoformat() if r.date_from else None,
            "date_to": r.date_to.isoformat() if r.date_to else None,
            "district": district_map.get(r.district_id, r.district_id) if r.district_id else "All Districts",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    
    return {
        "reports": report_list,
        "total_count": total_count,
    }


async def get_report_by_id(db: AsyncSession, report_id: str) -> Optional[Dict[str, Any]]:
    """Get a report by ID"""
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        return None
    
    result = await db.execute(select(Report).where(Report.report_id == report_uuid))
    report = result.scalar_one_or_none()
    
    if not report:
        return None
    data = report.to_dict()
    # Add file_url if file exists in storage
    data["file_url"] = report.file_path or None
    return data

def export_report_csv(report_data: dict) -> bytes:
    import io
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Report Name", report_data.get("report_name")])
    writer.writerow(["Report Type", report_data.get("report_type")])
    writer.writerow(["Generated At", report_data.get("created_at")])
    writer.writerow([])
    
    data = report_data.get("report_data", {})
    for k, v in data.items():
        if isinstance(v, (int, str, float)):
            writer.writerow([k, v])
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            writer.writerow([k])
            keys = v[0].keys()
            writer.writerow(list(keys))
            for item in v:
                writer.writerow([item.get(key) for key in keys])
            writer.writerow([])
    
    return output.getvalue().encode('utf-8')

def export_report_pdf(report_data: dict) -> bytes:
    import io
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        return b"PDF Generation failed: reportlab not installed"
        
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"Report: {report_data.get('report_name', 'Untitled')}")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 70, f"Type: {report_data.get('report_type', 'N/A')}")
    c.drawString(50, height - 90, f"Date: {report_data.get('created_at', 'N/A')}")
    
    y = height - 130
    data = report_data.get("report_data", {})
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Summary Metrics")
    y -= 25
    c.setFont("Helvetica", 12)
    
    for k, v in data.items():
        if isinstance(v, (int, str, float)):
            c.drawString(50, y, f"{str(k).replace('_', ' ').title()}: {v}")
            y -= 20
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = height - 50
            
    c.save()
    packet.seek(0)
    return packet.read()
