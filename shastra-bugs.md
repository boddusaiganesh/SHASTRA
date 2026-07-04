SHASTRA — Feature Gap Analysis & Implementation Guide
Project: AI-Driven Crime Analytics & Visualization Platform (Karnataka State Police) Reviewed: Full repo (crime_backend/MODULE_2_BACKEND — FastAPI + PostgreSQL + Neo4j + Redis, and crime_frontend — React + Vite + TS + Tailwind) Purpose: Map what's already built against the problem statement, list every feature/requirement that is missing or incomplete, tell you exactly where to add it, and give ready-to-paste code snippets. No changes have been made to your codebase — this document is analysis only.
________________________________________
1. What's Already Built (Baseline)
You've actually built a lot of the platform already. Before the gap list, here's the honest current state so we're on the same page:
Area	Status	Evidence
Interactive crime map (district drill-down)	✅ Built	CrimeMapPage.tsx, CrimeMap.tsx, crimes_router.py /map-data
Spatiotemporal hotspot clustering	✅ Built	HotspotAnalysis.tsx, HotspotMap.tsx, ml_models/hotspot_clustering.py, hotspots_router.py
Emerging trend alerts (visual pulse)	✅ Built	AlertBanner.tsx, alerts_router.py, alertsSlice.ts
Criminal network / link analysis (Cytoscape)	✅ Built	NetworkGraph.tsx, network_router.py, Neo4j integration
Repeat offender + MO tracking	✅ Built	OffenderDatabase.tsx, ml_models/modus_operandi_analyzer.py, /offenders/{id}/modus-operandi
Predictive risk scoring (Prophet forecasting)	✅ Built	PredictiveAnalytics.tsx, ml_models/crime_forecasting.py, ml_models/risk_scoring.py
Anomaly detection (Isolation Forest)	✅ Built	AnomalyDetection.tsx, ml_models/anomaly_detection.py
Socio-economic correlation (backend)	✅ Built	services/socioeconomic_service.py, /predictions/socioeconomic-correlation
AI narrative summaries (Gemini)	✅ Built	core/gemini_client.py, services/gemini_service.py, /network/ai-summary
Background ETL / scheduled ML scans	✅ Built	scheduler/scheduled_tasks.py (APScheduler)
Auth (JWT + bcrypt)	✅ Built	core/security.py, auth_router.py
Basic user management	✅ Built	settings_router.py /users, /users/add
Rate limiting, security headers, CORS	✅ Built	main.py (slowapi, custom middleware)
This is a strong foundation — most of the visualization and ML "wow factor" from the problem statement is done. The gaps below are mostly around data lifecycle (CRUD), enforcement of what you've already designed, exports, real-time delivery, and a few missing modules the problem statement implies but the code doesn't yet cover.
________________________________________
2. Gap Summary Table
#	Gap	Severity	Effort	Problem-statement link
1	No Victim CRUD / Victim Management module	High	Medium	"victims" explicitly named in relationship mapping
2	No Crime record edit / status update / delete	High	Small	"Data Silos & Manual Processes" — can log but not maintain
3	No Offender create/edit endpoints	High	Small	Repeat offender tracking needs data entry
4	RBAC helpers defined but never used in routers	Critical (security)	Small	Multi-role SCRB/District/Investigator access model
5	No bulk Excel/CSV import pipeline	High	Medium	Core ask: "moving beyond Excel-based reporting" — nobody can migrate legacy data in
6	Report download returns JSON, not actual PDF/Excel file	High	Medium	"Intelligence Report" deliverable expected by SCRB
7	No real-time push (WebSocket) — alerts are poll-only	Medium	Medium	"Emerging Trend Alerts" should feel live
8	No global search across crimes/offenders/victims	Medium	Small	Usability for investigators
9	No evidence/file attachment upload on crime records	Medium	Medium	Real crime records include FIR scans, photos
10	No audit trail / activity log	Medium	Small	Government system — accountability requirement
11	No dedicated Socio-Economic Dashboard page (backend exists, no UI)	Medium	Small	Explicitly called out capability #3
12	No AI query/chat assistant (Gemini only wired to one endpoint)	Medium	Medium	"AI-driven approaches" beyond canned charts
13	No GeoJSON/CSV export from map & hotspot views	Low	Small	Analysts need to take data offline
14	No notification channels beyond in-app (SMS/Email)	Low	Medium	Proactive policing needs to reach officers off-app
15	No Kannada/multi-language support	Low	Medium	State police, regional language expectation
16	No automated tests / CI pipeline	Medium (engineering hygiene)	Medium	Not in problem statement directly, but required for a "state-of-the-art" production platform
17	main.py hardcodes a Windows-only local Postgres path	Low (bug)	Trivial	Breaks on Linux/Mac/deploy
________________________________________
3. Detailed Gaps, Where to Add Them, and Code
3.1 Victim Management Module (Missing entirely)
Why it matters: Your DB already has a full Victim model (models/database_models/victim_model.py) and CrimeVictimLink, but there is no victims_router.py, no victim_service.py, and no VictimDatabase.tsx page. Victims are only referenced as network graph nodes — you can't search, view, or register them.
Where to add (backend):
•	New file: app/services/victim_service.py
•	New file: app/routers/victims_router.py
•	Register in main.py next to offenders_router
# app/services/victim_service.py
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
    victim = Victim(victim_id=uuid.uuid4(), **payload)
    db.add(victim)
    await db.commit()
    await db.refresh(victim)
    return victim.to_dict()


async def get_victim_profile(db: AsyncSession, victim_id: str) -> Optional[Dict[str, Any]]:
    result = await db.execute(select(Victim).where(Victim.victim_id == victim_id))
    victim = result.scalar_one_or_none()
    if not victim:
        return None
    links = await db.execute(select(CrimeVictimLink).where(CrimeVictimLink.victim_id == victim_id))
    crime_ids = [l.crime_id for l in links.scalars().all()]
    crimes = []
    if crime_ids:
        crimes_result = await db.execute(select(Crime).where(Crime.crime_id.in_(crime_ids)))
        crimes = [c.to_dict() for c in crimes_result.scalars().all()]
    data = victim.to_dict()
    data["linked_crimes"] = crimes
    return data
# app/routers/victims_router.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.victim_service import search_victims, create_victim, get_victim_profile

router = APIRouter()


@router.get("/search")
async def search(
    q: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await search_victims(db, q, district_id)
    return {"success": True, "data": data}


@router.get("/{victim_id}/profile")
async def profile(victim_id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_victim_profile(db, victim_id)
    if not data:
        raise HTTPException(status_code=404, detail="Victim not found")
    return {"success": True, "data": data}


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_victim(payload: dict, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await create_victim(db, payload)
    return {"success": True, "data": data}
In main.py, add:
from app.routers import victims_router
...
app.include_router(victims_router.router, prefix="/api/victims", tags=["Victims"])
Where to add (frontend):
•	crime_frontend/src/services/victimService.ts
•	crime_frontend/src/pages/VictimDatabase.tsx
•	Route in App.tsx: <Route path="/victims" element={<ProtectedRoute><VictimDatabase /></ProtectedRoute>} />
•	Add a nav item in Sidebar.tsx next to "Offenders"
// src/services/victimService.ts
import api from "./api";

export const victimService = {
  search: (q?: string, districtId?: string) =>
    api.get("/victims/search", { params: { q, district_id: districtId } }).then((r) => r.data.data),
  getProfile: (victimId: string) =>
    api.get(`/victims/${victimId}/profile`).then((r) => r.data.data),
  register: (payload: any) =>
    api.post("/victims", payload).then((r) => r.data.data),
};
Model VictimDatabase.tsx on your existing OffenderDatabase.tsx (same table/search/detail-panel pattern) — you already have the UI primitives (CrimesTable.tsx, search inputs), so this is mostly copy-adapt work.
________________________________________
3.2 Crime Record Lifecycle — Edit / Status Update / Delete
Why it matters: crimes_router.py only has GET /map-data, GET /filter, GET /detail/{id}, and POST "". There is no way to update case status (e.g., REPORTED → UNDER_INVESTIGATION → CLOSED), correct a mis-entered record, or soft-delete a duplicate. This directly blocks "moving beyond manual records" — you still can't fully retire the Excel sheet.
Where to add: app/routers/crimes_router.py + app/services/crime_service.py
# app/routers/crimes_router.py  (add below the existing POST route)
from fastapi import Body

@router.put("/{crime_id}")
async def update_crime(
    crime_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.crime_service import update_crime_record
    updated = await update_crime_record(db, crime_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Crime not found")
    return {"success": True, "data": updated}


@router.patch("/{crime_id}/status")
async def update_crime_status(
    crime_id: str,
    status_value: str = Query(..., alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.crime_service import update_crime_record
    valid = {"REPORTED", "UNDER_INVESTIGATION", "CLOSED", "SOLVED", "ARCHIVED"}
    if status_value not in valid:
        raise HTTPException(status_code=400, detail=f"status must be one of {valid}")
    updated = await update_crime_record(db, crime_id, {"status": status_value})
    if not updated:
        raise HTTPException(status_code=404, detail="Crime not found")
    return {"success": True, "data": updated}


@router.delete("/{crime_id}")
async def delete_crime(
    crime_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.core.security import require_role
    if current_user["role"] != "SCRB_OFFICER":
        raise HTTPException(status_code=403, detail="Only SCRB officers may delete crime records")
    from app.services.crime_service import delete_crime_record
    ok = await delete_crime_record(db, crime_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Crime not found")
    return {"success": True}
# app/services/crime_service.py  (add these functions)
async def update_crime_record(db, crime_id: str, payload: dict):
    from app.models.database_models.crime_model import Crime
    from sqlalchemy import select
    result = await db.execute(select(Crime).where(Crime.crime_id == crime_id))
    crime = result.scalar_one_or_none()
    if not crime:
        return None
    for k, v in payload.items():
        if hasattr(crime, k):
            setattr(crime, k, v)
    await db.commit()
    await db.refresh(crime)
    return crime.to_dict()


async def delete_crime_record(db, crime_id: str) -> bool:
    from app.models.database_models.crime_model import Crime
    from sqlalchemy import select
    result = await db.execute(select(Crime).where(Crime.crime_id == crime_id))
    crime = result.scalar_one_or_none()
    if not crime:
        return False
    await db.delete(crime)
    await db.commit()
    return True
Frontend: in CrimesTable.tsx, add an actions column (Edit / Change Status / Delete) wired to crimeService.ts, which needs matching update, updateStatus, remove methods calling the above endpoints.
________________________________________
3.3 Offender Create/Edit Endpoints
Why it matters: offenders_router.py only reads (search, profile, network, risk, modus-operandi). Investigators can't register a new suspect or update parole/incarceration status from the UI — they'd still need direct DB/Excel access, defeating the point.
Where to add: app/routers/offenders_router.py
@router.post("", status_code=status.HTTP_201_CREATED)
async def add_offender(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.offender_service import create_offender
    data = await create_offender(db, payload)
    return {"success": True, "data": data}


@router.put("/{offender_id}")
async def edit_offender(
    offender_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.offender_service import update_offender
    data = await update_offender(db, offender_id, payload)
    if not data:
        raise HTTPException(status_code=404, detail="Offender not found")
    return {"success": True, "data": data}
Add matching create_offender / update_offender in offender_service.py, following the same pattern as update_crime_record above (select → set attrs → commit → return .to_dict()).
________________________________________
3.4 RBAC Is Designed But Not Enforced — Fix This First (Security)
Finding: app/core/security.py defines require_role(...), require_scrb_officer, and scope_district_filter, and User.role distinguishes SCRB_OFFICER / DISTRICT_OFFICER / INVESTIGATOR. None of these are actually used anywhere in the 11 routers — every route only depends on get_current_user, meaning any authenticated user (even a low-privilege DISTRICT_OFFICER) can currently call state-wide endpoints, manage other users, and see every district's data. This is the single highest-priority fix in the whole codebase because it's a real access-control gap in a law-enforcement system.
Where to fix:
1.	In settings_router.py, protect user management:
from app.core.security import require_role

@router.post("/users/add")
async def add_user(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER"])),   # was: get_current_user
):
    ...
2.	In crimes_router.py / hotspots_router.py / predictions_router.py, apply district scoping for DISTRICT_OFFICER role using the helper that already exists but is unused:
from app.core.security import scope_district_filter
from app.models.database_models.crime_model import Crime

@router.get("/filter")
async def filter_crimes(
    ...,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    stmt = select(Crime)
    stmt = scope_district_filter(stmt, current_user, Crime.district_id)  # add this line
    ...
3.	In reports_router.py and the future victims_router.py delete/create endpoints, gate with require_role(["SCRB_OFFICER", "INVESTIGATOR"]) as appropriate.
Rule of thumb to apply across the codebase: any route that writes data (POST/PUT/PATCH/DELETE) or exposes state-wide data should use require_role([...]) instead of the bare get_current_user; any route that returns district-scoped data should call scope_district_filter.
________________________________________
3.5 Bulk Excel/CSV Import Pipeline (Directly Solves the Stated Problem)
Why it matters: The problem statement's #1 complaint is "heavily reliant on Excel-based reporting." Right now there is no way for SCRB/district staff to bulk-upload their existing Excel crime registers into SHASTRA — utils/data_seeder.py only seeds synthetic demo data, not real imports. Without this, adoption stalls because someone has to manually re-key years of records.
Where to add:
•	app/services/import_service.py
•	app/routers/import_router.py
•	Add pandas and openpyxl to requirements.txt if not present (check first — pandas is likely already a dependency of prophet/scikit-learn, but openpyxl for .xlsx reading may not be)
# app/services/import_service.py
import pandas as pd
from io import BytesIO
from typing import Dict, Any, List
import uuid
from datetime import datetime

from app.models.database_models.crime_model import Crime

REQUIRED_COLUMNS = ["crime_type", "date_of_occurrence", "district_id"]


async def preview_import(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Parse the file and return a preview + validation errors without writing to DB."""
    df = _read_any(file_bytes, filename)
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    errors: List[str] = []
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
    return {
        "row_count": len(df),
        "columns": list(df.columns),
        "preview_rows": df.head(10).fillna("").to_dict(orient="records"),
        "errors": errors,
    }


async def commit_import(db, file_bytes: bytes, filename: str, user_id: str) -> Dict[str, Any]:
    df = _read_any(file_bytes, filename)
    inserted, failed = 0, []
    for idx, row in df.iterrows():
        try:
            crime = Crime(
                crime_id=uuid.uuid4(),
                crime_reference_no=str(row.get("crime_reference_no") or f"IMPORT-{uuid.uuid4().hex[:8]}"),
                crime_type=str(row["crime_type"]),
                date_of_occurrence=pd.to_datetime(row["date_of_occurrence"]).date(),
                district_id=str(row["district_id"]),
                description=str(row.get("description") or ""),
                status="REPORTED",
                severity=str(row.get("severity") or "MEDIUM"),
            )
            db.add(crime)
            inserted += 1
        except Exception as e:
            failed.append({"row": int(idx), "error": str(e)})
    await db.commit()
    return {"inserted": inserted, "failed": failed, "imported_by": user_id, "imported_at": datetime.utcnow().isoformat()}


def _read_any(file_bytes: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(BytesIO(file_bytes))
    return pd.read_excel(BytesIO(file_bytes))
# app/routers/import_router.py
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.services.import_service import preview_import, commit_import

router = APIRouter()


@router.post("/preview")
async def preview(file: UploadFile = File(...), current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER"]))):
    content = await file.read()
    data = await preview_import(content, file.filename)
    return {"success": True, "data": data}


@router.post("/commit")
async def commit(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER"])),
):
    content = await file.read()
    data = await commit_import(db, content, file.filename, current_user["user_id"])
    return {"success": True, "data": data}
Register in main.py: app.include_router(import_router.router, prefix="/api/import", tags=["Data Import"])
Frontend: new page pages/DataImport.tsx with a drag-and-drop file input (you can reuse Tailwind styles from SettingsPage.tsx), calling /api/import/preview first to show a validation table, then a "Confirm Import" button hitting /api/import/commit.
________________________________________
3.6 Real File Export (PDF/Excel) for Reports
Why it matters: reports_router.py's /download endpoint currently just returns the same JSON as /generate — there is no actual downloadable file. For a "State-wide Intelligence Report" deliverable to SCRB leadership, officers need a PDF or Excel they can print/forward/archive, not raw JSON.
Where to add: extend app/services/report_service.py, add reportlab (or weasyprint) and openpyxl to requirements.txt.
# app/services/report_service.py  (add)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO


def render_report_pdf(report_data: dict) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 50, "SHASTRA — Crime Intelligence Report")
    c.setFont("Helvetica", 10)
    c.drawString(40, height - 70, f"Report: {report_data.get('report_name', '')}")
    c.drawString(40, height - 85, f"Generated: {report_data.get('generated_at', '')}")

    y = height - 120
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Summary")
    c.setFont("Helvetica", 10)
    y -= 20
    for key, value in report_data.get("summary", {}).items():
        c.drawString(50, y, f"{key}: {value}")
        y -= 15
        if y < 60:
            c.showPage()
            y = height - 50

    c.save()
    buffer.seek(0)
    return buffer.read()
# app/routers/reports_router.py  (replace the /download route)
from fastapi.responses import StreamingResponse
from io import BytesIO

@router.get("/{report_id}/download")
async def download(
    report_id: str,
    file_format: str = Query("pdf", enum=["pdf", "json"]),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_report_by_id(db, report_id)
    if not data:
        raise HTTPException(status_code=404, detail="Report not found")

    if file_format == "json":
        return {"success": True, "data": data}

    from app.services.report_service import render_report_pdf
    pdf_bytes = render_report_pdf(data)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{report_id}.pdf"'},
    )
Frontend: in ReportsPage.tsx, change the download button to open ${API_BASE}/reports/${id}/download?file_format=pdf directly (browser will handle the file download), rather than fetching JSON.
________________________________________
3.7 Real-Time Alerts via WebSocket
Why it matters: There's no websocket usage anywhere in the codebase (verified by full-repo search). "Emerging Trend Alerts" currently rely on the frontend polling alertService.getAlerts() — likely only on page load / interval, not pushed the instant the scheduler detects a spike. For a "red-zone pulsing" proactive-policing feature, alerts should arrive live.
Where to add: app/core/websocket_manager.py, hook into scheduler/scheduled_tasks.py where alerts are created, and add a /ws/alerts route in main.py.
# app/core/websocket_manager.py
from fastapi import WebSocket
from typing import List
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)

manager = ConnectionManager()
# main.py (add)
from fastapi import WebSocket, WebSocketDisconnect
from app.core.websocket_manager import manager

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping from client
    except WebSocketDisconnect:
        manager.disconnect(websocket)
In scheduler/scheduled_tasks.py, wherever a new Alert row is currently created, add right after the commit:
from app.core.websocket_manager import manager
await manager.broadcast({"type": "NEW_ALERT", "data": new_alert.to_dict()})
Frontend: in App.tsx (inside ProtectedRoute, alongside the existing useEffect that fetches alerts), open a socket and dispatch into alertsSlice:
useEffect(() => {
  if (!isAuthenticated) return;
  const ws = new WebSocket(`${import.meta.env.VITE_WS_URL || "ws://localhost:8000"}/ws/alerts`);
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "NEW_ALERT") {
      dispatch(addAlert(msg.data)); // add this action to alertsSlice.ts
    }
  };
  return () => ws.close();
}, [isAuthenticated, dispatch]);
You'll need to add an addAlert reducer to store/alertsSlice.ts that prepends to the alerts list and increments unreadCount.
________________________________________
3.8 Global Search
Why it matters: Investigators currently have to know whether they're looking for a crime, offender, or (once built) a victim, and go to the right page. A single search bar dramatically speeds up investigation workflows and is a standard expectation in any intelligence platform.
Where to add: app/routers/search_router.py (fan-out to existing services), and a search box in Navbar.tsx.
# app/routers/search_router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.crime_service import filter_crimes  # reuse existing
from app.services.offender_service import search_offenders  # reuse existing

router = APIRouter()


@router.get("/global")
async def global_search(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    crimes = await filter_crimes(db, crime_reference_no=q, limit=5)  # adjust to actual signature
    offenders = await search_offenders(db, q, limit=5)
    return {
        "success": True,
        "data": {"crimes": crimes, "offenders": offenders},
    }
Frontend: add a search <input> to Navbar.tsx with a debounced call to /api/search/global, rendering a dropdown of grouped results (Crimes / Offenders / Victims) that navigate to the relevant detail page on click.
________________________________________
3.9 Evidence / File Attachments on Crime Records
Why it matters: Real crime records include FIR scans, photos of the scene, and CCTV stills. Right now Crime has no attachment relationship, and there's no upload endpoint anywhere in routers/.
Where to add:
•	New model: app/models/database_models/evidence_model.py
•	New router: app/routers/evidence_router.py
•	Local/S3-style storage under app/uploads/ (or wire to S3/MinIO later)
# app/models/database_models/evidence_model.py
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class Evidence(Base):
    __tablename__ = "evidence"

    evidence_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crime_id = Column(UUID(as_uuid=True), ForeignKey("crimes.crime_id"), nullable=False, index=True)
    file_name = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=True)
    uploaded_by = Column(UUID(as_uuid=True), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "evidence_id": str(self.evidence_id),
            "crime_id": str(self.crime_id),
            "file_name": self.file_name,
            "file_type": self.file_type,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }
# app/routers/evidence_router.py
import os, uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.database_models.evidence_model import Evidence

router = APIRouter()
UPLOAD_DIR = "app/uploads/evidence"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/{crime_id}/upload")
async def upload_evidence(
    crime_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ext = os.path.splitext(file.filename)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, stored_name)
    with open(path, "wb") as f:
        f.write(await file.read())

    record = Evidence(
        evidence_id=uuid.uuid4(),
        crime_id=crime_id,
        file_name=file.filename,
        file_path=path,
        file_type=file.content_type,
        uploaded_by=current_user["user_id"],
    )
    db.add(record)
    await db.commit()
    return {"success": True, "data": record.to_dict()}
Add Base.metadata will pick this up automatically via init_db() since it inherits Base. Register router in main.py. On the frontend, add an "Attachments" tab to the crime detail modal/page with a file input calling this endpoint, and a thumbnail/list of previously uploaded files.
________________________________________
3.10 Audit Trail
Why it matters: Government crime-record systems need an immutable log of who viewed/edited/deleted what and when — none of your services currently write an audit record anywhere.
Where to add: app/models/database_models/audit_log_model.py + a lightweight helper called from your write-endpoints.
# app/models/database_models/audit_log_model.py
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(50), nullable=False)       # CREATE / UPDATE / DELETE / VIEW
    resource_type = Column(String(50), nullable=False) # CRIME / OFFENDER / VICTIM / USER
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
# app/utils/audit.py
async def log_action(db, user_id, action, resource_type, resource_id, details=None):
    from app.models.database_models.audit_log_model import AuditLog
    import uuid
    entry = AuditLog(
        log_id=uuid.uuid4(), user_id=user_id, action=action,
        resource_type=resource_type, resource_id=str(resource_id), details=details or {},
    )
    db.add(entry)
    await db.commit()
Call await log_action(db, current_user["user_id"], "DELETE", "CRIME", crime_id) at the end of the delete_crime route from §3.2 (and similarly for other write routes). Expose a read-only GET /api/settings/audit-logs (SCRB-only, via require_role) for an "Activity Log" tab on SettingsPage.tsx.
________________________________________
3.11 Dedicated Socio-Economic Dashboard Page
Why it matters: /predictions/socioeconomic-correlation and services/socioeconomic_service.py exist on the backend, but there's no frontend page presenting this — it's currently only referenced inline inside PredictiveAnalytics.tsx. The problem statement calls this out as its own capability ("understand the why behind the where"), so it deserves its own visual page (overlay charts: urbanization vs. crime rate, population density vs. crime type, etc.) rather than being a buried section.
Where to add:
•	pages/SocioEconomicInsights.tsx
•	Route /socioeconomic in App.tsx, nav item in Sidebar.tsx
// src/pages/SocioEconomicInsights.tsx (skeleton)
import { useEffect, useState } from "react";
import { predictionService } from "../services/predictionService";
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function SocioEconomicInsights() {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    predictionService.getSocioeconomicCorrelation().then(setData);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold text-slate-100 mb-4">Socio-Economic Correlation</h1>
      <div className="bg-slate-800 rounded-xl p-4 h-96">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="urbanization_index" name="Urbanization Index" stroke="#94a3b8" />
            <YAxis dataKey="crime_rate" name="Crime Rate" stroke="#94a3b8" />
            <Tooltip />
            <Scatter data={data} fill="#f97316" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
(Add getSocioeconomicCorrelation to predictionService.ts if it isn't already exposed there — check first, since the backend route exists.)
________________________________________
3.12 AI Query Assistant (Expand Gemini Beyond One Endpoint)
Why it matters: gemini_client.py/gemini_service.py are currently only wired to /network/ai-summary and report narratives. The problem statement's "AI-driven approaches" implies investigators should be able to ask questions ("Which district had the highest chain-snatching increase this month?") and get an answer grounded in your data — not just canned summaries.
Where to add: app/routers/assistant_router.py, reusing gemini_client.py.
# app/routers/assistant_router.py
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.gemini_client import generate_content  # reuse existing wrapper
from app.services.dashboard_service import get_summary  # reuse existing aggregation

router = APIRouter()


@router.post("/ask")
async def ask_assistant(
    question: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    context = await get_summary(db)  # ground the model in real current stats
    prompt = f"""You are a crime-intelligence assistant for Karnataka State Police.
Use ONLY the following current statistics to answer. If the answer isn't in the data, say so.

DATA: {context}

QUESTION: {question}
"""
    answer = await generate_content(prompt)
    return {"success": True, "data": {"answer": answer}}
Frontend: a small chat-style widget (floating button + panel) mounted once in App.tsx's ProtectedRoute, calling /api/assistant/ask — reuse framer-motion (already a dependency) for the open/close animation.
________________________________________
3.13 GeoJSON/CSV Export From Map & Hotspot Views
Where to add: add file_format query param to existing crimes_router.py /map-data and hotspots_router.py /clusters, returning either JSON (current) or a StreamingResponse CSV using Python's built-in csv module — same StreamingResponse pattern as §3.6. On the frontend, add a "Export" button to MapControls.tsx that just links to the endpoint with ?file_format=csv.
________________________________________
3.14 Notification Channels Beyond In-App (SMS/Email)
Where to add: app/services/notification_service.py, called from the same place in scheduler/scheduled_tasks.py where you'd add the WebSocket broadcast (§3.7). Use an email provider SDK (e.g., smtplib for basic SMTP, or a provider like SendGrid) — this is optional/lower priority; stub it so it's easy to wire a real provider later:
# app/services/notification_service.py
import logging
logger = logging.getLogger(__name__)

async def notify_high_priority_alert(alert: dict, recipients: list[str]):
    """Stub — wire to SMTP/SendGrid/Twilio when credentials are available."""
    logger.info(f"[NOTIFY] Would send alert '{alert.get('title')}' to {recipients}")
    # Example SMTP implementation:
    # import smtplib
    # from email.message import EmailMessage
    # msg = EmailMessage()
    # msg["Subject"] = f"SHASTRA Alert: {alert['title']}"
    # msg["From"] = settings.SMTP_FROM
    # msg["To"] = recipients
    # msg.set_content(alert["description"])
    # with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as s:
    #     s.starttls(); s.login(settings.SMTP_USER, settings.SMTP_PASS); s.send_message(msg)
________________________________________
3.15 Kannada / Multi-Language Support
Where to add: frontend only — i18next + react-i18next (new deps), a locales/en.json and locales/kn.json, and a language toggle in Navbar.tsx. Given the size of your UI text surface, this is a larger, lower-priority effort — flagged here so it's on your radar rather than fully scoped with code, since it touches nearly every component.
________________________________________
3.16 Automated Tests & CI
Why it matters: No tests/ directory exists in either crime_backend or crime_frontend, and there's no CI config (no .github/workflows/). For a platform handling law-enforcement data, at minimum smoke tests on auth, crime CRUD, and ML endpoints protect you from silent regressions.
Where to add:
crime_backend/MODULE_2_BACKEND/tests/
  test_auth.py
  test_crimes.py
  test_offenders.py
.github/workflows/ci.yml
# tests/test_crimes.py (using pytest + httpx, add pytest/httpx/pytest-asyncio to requirements.txt)
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_map_data_requires_no_auth_but_returns_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/crimes/map-data")
    assert resp.status_code == 200
    assert "data" in resp.json()
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  backend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r crime_backend/MODULE_2_BACKEND/requirements.txt
      - run: cd crime_backend/MODULE_2_BACKEND && pytest
  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd crime_frontend && npm ci && npm run build
________________________________________
3.17 Bug: Hardcoded Windows-Only Postgres Path
Where: main.py, function start_local_postgres():
pg_ctl = r"D:\PostgreSQL_17\bin\pg_ctl.exe"
pg_data = r"D:\PostgreSQL_17\data"
This silently no-ops on Linux/Mac (fine for now since it's wrapped in os.path.exists checks), but it's dead weight in any deployed environment and confusing for teammates. When you containerize (you already have a Dockerfile/docker-compose.yml), this whole function should be removed or gated behind if settings.ENVIRONMENT == "development" and platform.system() == "Windows":.
________________________________________
4. Suggested Build Order
If you're doing this yourself, tackle in this order — each phase is independently shippable:
1.	Security fix (3.4) — RBAC enforcement. Do this before anything else; it's a correctness bug, not a feature.
2.	CRUD completion (3.2, 3.3, 3.1) — Crime edit/delete, Offender create/edit, Victim module. This is what actually retires the Excel sheets.
3.	Bulk import (3.5) — lets you migrate real historical data and demo the platform with it.
4.	Exports (3.6, 3.13) — PDF/CSV so SCRB leadership can actually consume "Intelligence Reports."
5.	Real-time (3.7) and global search (3.8) — polish that makes the platform feel "state-of-the-art" in a demo.
6.	Evidence upload (3.9), audit log (3.10), socio-economic page (3.11), AI assistant (3.12) — depth features.
7.	Notifications (3.14), i18n (3.15), tests/CI (3.16) — production-readiness, do before go-live rather than before demo.
________________________________________
5. Dependencies You'll Need to Add
Backend (requirements.txt):
openpyxl        # Excel read/write for import (3.5) and export (3.6/3.13)
reportlab       # PDF generation (3.6)
pytest
pytest-asyncio
httpx           # for tests (3.16)
Frontend (package.json):
i18next
react-i18next   # only if doing 3.15
(WebSocket in 3.7 uses the browser-native WebSocket API — no new dependency needed.)
________________________________________
6. Quick Reference — Files You'll Touch
Gap	New files	Modified files
Victim module	victim_service.py, victims_router.py, victimService.ts, VictimDatabase.tsx	main.py, App.tsx, Sidebar.tsx
Crime lifecycle	—	crimes_router.py, crime_service.py, CrimesTable.tsx, crimeService.ts
Offender CRUD	—	offenders_router.py, offender_service.py, OffenderDatabase.tsx
RBAC enforcement	—	every write-route in routers/*.py
Bulk import	import_service.py, import_router.py, DataImport.tsx	main.py, App.tsx, Sidebar.tsx, requirements.txt
PDF/CSV export	—	report_service.py, reports_router.py, ReportsPage.tsx, requirements.txt
WebSocket alerts	websocket_manager.py	main.py, scheduled_tasks.py, App.tsx, alertsSlice.ts
Global search	search_router.py	main.py, Navbar.tsx
Evidence upload	evidence_model.py, evidence_router.py	main.py, crime detail component
Audit log	audit_log_model.py, utils/audit.py	write-routes, SettingsPage.tsx
Socio-economic page	SocioEconomicInsights.tsx	App.tsx, Sidebar.tsx, predictionService.ts
AI assistant	assistant_router.py, chat widget component	main.py, App.tsx
Notifications	notification_service.py	scheduled_tasks.py, config.py (SMTP settings)
i18n	locales/en.json, locales/kn.json	most components, Navbar.tsx
Tests/CI	tests/*.py, .github/workflows/ci.yml	requirements.txt
Windows bug	—	main.py
________________________________________
This document only analyzes and proposes — no files in your project were modified. Implement in the order in §4, and re-run through this checklist once done to confirm each gap is closed.

