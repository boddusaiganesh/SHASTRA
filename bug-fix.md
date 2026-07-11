# SHASTRA Crime Intelligence Platform — Full Audit Report (v2, deep re-check)

**Scope:** All 14 pages, frontend↔backend wiring, database connections (PostgreSQL / Neo4j / Redis), Criminal Network graph + filters, Report generation/download, responsive/resizing behavior.

**Method:** Full static code review of `crime_frontend` (React + TS + Redux + Cytoscape + Leaflet) and `crime_backend` (FastAPI + SQLAlchemy + Neo4j + Redis). No live servers/databases were available in this environment, so this is a **static audit**, not a runtime test — every API call in the frontend was traced against every route in the backend router files, and the actual state/render logic for each page, service, slice, and shared component was read end‑to‑end (not just grepped).

**What changed in this pass:** This is a second, deeper pass. Beyond the 13 issues from the first pass (still included below, now with full fix code instead of just direction), this pass reviewed every remaining service (`authService`, `offenderService`, `victimService`, `alertService`, `evidenceService`, `predictionService`, `settingsService`), every remaining page in full (`Login`, `Dashboard`, `HotspotAnalysis`, `AnomalyDetection`, `PredictiveAnalytics`, `OffenderDatabase`, `VictimDatabase`, `SocioEconomicInsights`, `SettingsPage`, `AlertsPage`), the Redux slices, `Navbar.tsx`/`Sidebar.tsx`/`App.tsx` shell, and cross-checked every response shape against its consuming component. **Four new critical, verified bugs surfaced** that were not visible from the first pass, including one that makes the entire Settings page unusable for 2 of the 3 user roles, and one that means Logout does not actually invalidate the session on the server.

Fix priority: 🔴 Critical → 🟠 High → 🟡 Medium → 🟢 Low. Every item below has copy-pasteable fix code.

---

## 🔴 CRITICAL ISSUES

### 1. [NEW] Logout never calls the backend — the session cookie is never invalidated server-side
**File:** `crime_frontend/src/components/common/Navbar.tsx`

```tsx
import { logout } from "../../store/authSlice";
// ...
const handleLogout = () => {
  dispatch(logout());
  navigate("/login");
};
```
`authService` is never imported in this file. Clicking "Logout" only clears Redux state and two `localStorage` flags — it never calls `POST /api/auth/logout`, which is the only thing that (a) blacklists the JWT in Redis and (b) tells the browser to delete the `httpOnly` cookie (`response.delete_cookie(...)` in `auth_router.py`). Client-side JS **cannot** delete an `httpOnly` cookie itself — only the server response can.

**Real-world impact:** on a shared workstation (very common in a police department), clicking Logout gives the appearance of logging out (redirect to `/login`, blank state) while the actual session cookie is still valid on that machine. Anyone with browser/devtools access, or anyone replaying that cookie against the API directly, is still authenticated as that officer until the token's natural expiry.

**Fix — make `handleLogout` actually call the backend, and only clear local state after:**
```tsx
// Navbar.tsx
import { authService } from "../../services/authService";
import { logout } from "../../store/authSlice";
// ...
const handleLogout = async () => {
  try {
    await authService.logout();   // POST /api/auth/logout — blacklists token + deletes the cookie server-side
  } catch (e) {
    // Backend might already be unreachable/token expired — still proceed to clear client state
    console.error("Logout request failed, clearing local session anyway", e);
  } finally {
    dispatch(logout());
    navigate("/login");
  }
};
```

---

### 2. [NEW] Settings page is permanently stuck on "Loading..." for District Officers and Investigators
**File:** `crime_frontend/src/pages/SettingsPage.tsx`

```tsx
useEffect(() => {
  Promise.all([
    settingsService.getUsers(usersPage, pageSize),          // backend requires SCRB_OFFICER
    settingsService.getAlertThresholds(),                    // any authenticated user
    settingsService.getDataSources(),                        // any authenticated user
    settingsService.getAuditLogs(logsPage, pageSize),        // backend requires SCRB_OFFICER
  ]).then(([u, t, d, logs]: any[]) => {
    ...
    setLoading(false);
  });
  // NOTE: no .catch() anywhere
}, [usersPage, logsPage]);
```
Cross-referencing `settings_router.py`:
```python
@router.get("/users")
async def list_users(..., current_user=Depends(require_scrb_officer)):  # 403 for anyone else

@router.get("/audit-logs")
async def get_audit_logs(..., current_user=Depends(require_scrb_officer)):  # 403 for anyone else
```
Both `/users` and `/audit-logs` return **HTTP 403** for `DISTRICT_OFFICER` and `INVESTIGATOR` roles (2 of the 3 roles in the system — see `USER_ROLES` in `crimeTypes.ts`). `Promise.all` rejects the instant **any** of its promises rejects. Since there is no `.catch()` on this chain, `.then()` never runs, `setLoading(false)` is **never called**, and the entire Settings & Administration page shows the loading spinner forever for those two roles — not an error message, not a partial view, just an infinite spinner. This is the entire 14th page being non-functional for the majority of realistic users.

There's a second half of the same problem: even for the one role (`SCRB_OFFICER`) that *can* see it, the "User Management" and "Activity Log" tabs are shown to *everyone* in the UI regardless of role — there's no role gate like the one `OffenderDatabase.tsx`/`VictimDatabase.tsx` correctly use (`isScrbOrInvestigator`) — so a non-SCRB user sees tabs that are guaranteed to fail.

**Fix — fetch role-restricted data separately from role-open data, tolerate individual failures, and gate the tabs in the UI:**
```tsx
// SettingsPage.tsx
import { useSelector } from "react-redux";
import { RootState } from "../store/store";
// ...
const { user_role } = useSelector((state: RootState) => state.auth);
const isScrbOfficer = user_role === "SCRB_OFFICER";

useEffect(() => {
  let cancelled = false;

  const loadAll = async () => {
    setLoading(true);

    // Always-available data
    const [thresholdsResult, dataSourcesResult] = await Promise.allSettled([
      settingsService.getAlertThresholds(),
      settingsService.getDataSources(),
    ]);
    if (!cancelled) {
      if (thresholdsResult.status === "fulfilled") setThresholds(thresholdsResult.value as AlertThresholds);
      if (dataSourcesResult.status === "fulfilled") {
        const d = dataSourcesResult.value as any;
        setDataSources(Array.isArray(d) ? d : (d?.sources || d?.data || []));
      }
    }

    // SCRB-only data — skip the request entirely for other roles instead of letting it 403
    if (isScrbOfficer) {
      const [usersResult, logsResult] = await Promise.allSettled([
        settingsService.getUsers(usersPage, pageSize),
        settingsService.getAuditLogs(logsPage, pageSize),
      ]);
      if (!cancelled) {
        if (usersResult.status === "fulfilled") {
          const u = usersResult.value as any;
          setUsers(Array.isArray(u) ? u : (u?.users || u?.data || []));
          setUsersTotalCount(u?.total_count || 0);
        }
        if (logsResult.status === "fulfilled") {
          const logs = logsResult.value as any;
          setAuditLogs(Array.isArray(logs) ? logs : (logs?.data || []));
          setLogsTotalCount(logs?.total_count || 0);
        }
      }
    }

    if (!cancelled) setLoading(false);
  };

  loadAll();
  return () => { cancelled = true; };
}, [usersPage, logsPage, isScrbOfficer]);
```
And gate the tabs themselves:
```tsx
{[
  ...(isScrbOfficer ? [{ id: "users", label: "User Management", icon: Users }] : []),
  { id: "thresholds", label: "Alert Thresholds", icon: Bell },
  { id: "datasources", label: "Data Sources", icon: Database },
  ...(isScrbOfficer ? [{ id: "auditlogs", label: "Activity Log", icon: ActivitySquare }] : []),
  { id: "import", label: "Import Data", icon: UploadCloud },
].map(({ id, label, icon: Icon }) => ( /* unchanged */ ))}
```
and default `activeTab` to `"thresholds"` instead of `"users"` for non-SCRB roles so they don't land on a tab they can't use:
```tsx
const [activeTab, setActiveTab] = useState(isScrbOfficer ? "users" : "thresholds");
```

---

### 3. [NEW] Global search in the top Navbar crashes the moment anyone types 2+ characters
**File:** `crime_frontend/src/components/common/Navbar.tsx`

```tsx
const res = await api.get(ENDPOINTS.SEARCH.GLOBAL, { params: { q: searchQuery } });
setSearchResults(res.data);
```
Every other service in this codebase unwraps the backend's `{success, data}` envelope (`res.data?.data || res.data`). This one doesn't. The backend's actual response (`search_router.py`):
```python
return {
    "success": True,
    "data": { "crimes": [...], "offenders": [...], "victims": [...] }
}
```
So `res.data` is `{success: true, data: {...}}`, **not** `{crimes, offenders, victims}`. Two lines later:
```tsx
{!isSearching && searchResults.crimes.length === 0 && searchResults.offenders.length === 0 && (
```
`searchResults.crimes` is `undefined` → `undefined.length` → **`TypeError: Cannot read properties of undefined (reading 'length')`**, thrown during render. Because `Navbar` wraps every one of the 14 pages (it's part of the shared app shell in `App.tsx`), this crashes the entire authenticated app the instant a user searches for anything, not just the search box.

**Fix:**
```tsx
// Navbar.tsx
const res = await api.get(ENDPOINTS.SEARCH.GLOBAL, { params: { q: searchQuery } });
const unwrapped = res.data?.data || res.data;
setSearchResults({
  crimes: Array.isArray(unwrapped?.crimes) ? unwrapped.crimes : [],
  offenders: Array.isArray(unwrapped?.offenders) ? unwrapped.offenders : [],
  victims: Array.isArray(unwrapped?.victims) ? unwrapped.victims : [],
});
```

---

### 4. [NEW] Hotspot CSV export always 500s — dict indexed like a list
**File:** `crime_backend/MODULE_2_BACKEND/app/routers/hotspots_router.py`

```python
data = await get_hotspot_clusters(db, district_id, crime_type, date_from, date_to, page, page_size)

if file_format == "csv":
    ...
    if data:
        writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
```
`get_hotspot_clusters()` (in `hotspot_service.py`) returns a **dict**:
```python
response = {
    "hotspots": hotspots_data,
    "total_hotspots": total_count,
    "high_risk_count": high_risk,
    "emerging_count": emerging,
    "page": page,
    "page_size": page_size
}
return response
```
`data[0]` on a dict raises `KeyError: 0` (Python dicts aren't indexable by position). **Every single call** to `GET /hotspots/clusters?file_format=csv` — i.e., every click of the "Export CSV" button on the Hotspot Analysis page — throws an unhandled exception and returns a 500. This isn't a filter-correctness issue like the other export bugs below; this export **does not work at all, under any conditions**.

**Fix:**
```python
# hotspots_router.py
data = await get_hotspot_clusters(db, district_id, crime_type, date_from, date_to, page, page_size)

if file_format == "csv":
    import csv
    from io import StringIO
    from fastapi.responses import StreamingResponse

    rows = data.get("hotspots", []) if isinstance(data, dict) else data

    output = StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="hotspots_export.csv"'}
    )

return {"success": True, "data": data}
```
Note this also means CSV export was silently capped at `page_size` (default 20) records even before this crash — see item #12 below for that follow-on fix.

---

### 5. Auth cookie is hardcoded `secure=False` — breaks/weakens auth in production
**File:** `crime_backend/MODULE_2_BACKEND/app/routers/auth_router.py`

```python
response.set_cookie(
    key="auth_token",
    value=token_data["auth_token"],
    httponly=True,
    samesite="lax",
    secure=False, # True if using HTTPS
    max_age=token_data["expires_in"]
)
...
response.delete_cookie(key="auth_token", httponly=True, samesite="lax", secure=False)
```
Every deployment (including production over HTTPS) currently sends the session cookie with `Secure=false`. The comment even says what to do; it was never done.

**Fix:**
```python
# auth_router.py
from app.core.config import settings

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, response: Response, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token_data = await create_user_token(user)

    response.set_cookie(
        key="auth_token",
        value=token_data["auth_token"],
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT == "production",
        max_age=token_data["expires_in"]
    )
    safe_data = {k: v for k, v in token_data.items() if k != "auth_token"}
    return {"success": True, "data": safe_data}

@router.post("/logout")
async def logout(response: Response, current_user=Depends(get_current_user)):
    await blacklist_token(current_user["token"])
    response.delete_cookie(
        key="auth_token",
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT == "production",
    )
    return {"success": True, "message": "Logged out successfully"}
```

---

### 6. Report PDF generation will crash on normal AI-generated text (unescaped XML)
**File:** `crime_backend/MODULE_2_BACKEND/app/services/report_service.py`, `export_report_pdf()`

ReportLab's `Paragraph` parses its input as pseudo-XML/HTML. `ai_narrative` comes straight from Gemini and is never escaped. Any narrative containing `&`, `<`, or `>` (e.g. `"Crime rates < 10% in Bangalore & Mysore"`) throws `xml.parsers.expat.ExpatError` and the "Download Report" request 500s. Same risk for any DB text field rendered via `str(val)` in the data tables.

**Fix:**
```python
# report_service.py
from xml.sax.saxutils import escape

def export_report_pdf(report_data: dict) -> bytes:
    import io
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        return b"PDF Generation failed: reportlab not installed"

    packet = io.BytesIO()
    doc = SimpleDocTemplate(packet, pagesize=letter, rightMargin=40, leftMargin=40,
                             topMargin=60, bottomMargin=40,
                             title=escape(report_data.get("report_name", "SHASTRA Report")))

    styles = getSampleStyleSheet()
    title_style, h1_style, h2_style, normal_style = styles["Title"], styles["Heading1"], styles["Heading2"], styles["Normal"]
    narrative_style = ParagraphStyle('Narrative', parent=styles['Normal'], fontName='Helvetica',
                                     fontSize=11, leading=14, textColor=colors.darkslategray, spaceAfter=12)

    story = []
    story.append(Paragraph("KARNATAKA STATE POLICE", title_style))
    story.append(Paragraph("CRIME INTELLIGENCE & ANALYTICAL PLATFORM (SHASTRA)", h2_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Report: {escape(str(report_data.get('report_name', 'Untitled')))}", h1_style))
    story.append(Paragraph(f"Type: {escape(str(report_data.get('report_type', 'N/A')))}", normal_style))
    story.append(Paragraph(f"Date: {escape(str(report_data.get('created_at', 'N/A')))}", normal_style))
    story.append(Spacer(1, 20))

    ai_narrative = report_data.get("ai_narrative")
    if ai_narrative:
        story.append(Paragraph("Executive Summary (AI Generated)", h2_style))
        for p in ai_narrative.split("\n"):
            if p.strip():
                story.append(Paragraph(escape(p.strip()), narrative_style))
        story.append(Spacer(1, 20))

    data = report_data.get("report_data", {})
    if data:
        story.append(Paragraph("Detailed Metrics", h2_style))
        simple_data, complex_data = [], {}
        for k, v in data.items():
            if isinstance(v, (int, float, str)):
                simple_data.append([escape(k.replace('_', ' ').title()), escape(str(v))])
            elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                complex_data[k] = v

        if simple_data:
            t = Table(simple_data, colWidths=[200, 300])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            story.append(t)
            story.append(Spacer(1, 20))

        for k, items in complex_data.items():
            story.append(Paragraph(escape(k.replace('_', ' ').title()), h2_style))
            headers = [escape(key.replace('_', ' ').title()) for key in items[0].keys()]
            table_data = [headers]
            for item in items:
                table_data.append([escape(str(val)) for val in item.values()])
            t2 = Table(table_data)
            t2.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.aliceblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(t2)
            story.append(Spacer(1, 20))

    doc.build(story)
    packet.seek(0)
    return packet.read()
```

---

### 7. Report date range filter is silently dropped
**File:** `crime_frontend/src/services/reportService.ts`

```ts
generateReport: async (params: Record<string, string>) => {
  const queryParams = {
    report_type: params.report_type,
    report_name: params.report_name || `${params.report_type}_${Date.now()}`,
    ...(params.district_id ? { district_id: params.district_id } : {}),
  };
  const res = await api.post(`${ENDPOINTS.REPORTS.GENERATE}?${new URLSearchParams(queryParams).toString()}`);
```
`ReportsPage.tsx` collects `date_from`/`date_to` from the user, but this function drops them before the request goes out. The backend fully supports both. Every generated report silently covers all‑time data regardless of the date range picked.

**Fix:**
```ts
// reportService.ts
generateReport: async (params: Record<string, string>) => {
  try {
    const queryParams: Record<string, string> = {
      report_type: params.report_type,
      report_name: params.report_name || `${params.report_type}_${Date.now()}`,
    };
    if (params.district_id) queryParams.district_id = params.district_id;
    if (params.date_from) queryParams.date_from = params.date_from;
    if (params.date_to) queryParams.date_to = params.date_to;

    const res = await api.post(`${ENDPOINTS.REPORTS.GENERATE}?${new URLSearchParams(queryParams).toString()}`);
    return res.data?.data || res.data;
  } catch (error) {
    throw error;
  }
},
```

---

### 8. `docker-compose.yml` references two different `.env` files — Redis container will not start on a clean checkout
**File:** `docker-compose.yml`

```yaml
backend:
  env_file: [ .env ]
scheduler:
  env_file: [ .env ]
redis:
  env_file: [ ./crime_backend/MODULE_2_BACKEND/.env ]   # different path
```
The repo ships two separate, byte-for-byte identical example files (`/.env.example` and `/crime_backend/MODULE_2_BACKEND/.env.example`), and the README has no env-setup section documenting that both are needed. A clean checkout following the obvious path (create root `.env` only) will fail the `redis` service specifically.

**Fix:**
```yaml
# docker-compose.yml
redis:
  image: redis:7.2-alpine
  restart: unless-stopped
  command: /bin/sh -c 'redis-server --requirepass "$$REDIS_PASSWORD"'
  env_file:
    - .env        # <- was ./crime_backend/MODULE_2_BACKEND/.env
  healthcheck:
    test: ["CMD", "redis-cli", "-a", "$$REDIS_PASSWORD", "ping"]
    interval: 5s
    timeout: 5s
    retries: 10
  ports:
    - "127.0.0.1:6379:6379"
  networks:
    - crime_intelligence_network
```
and delete the now-redundant `crime_backend/MODULE_2_BACKEND/.env.example` to remove the ambiguity entirely.

---

## 🟠 HIGH PRIORITY (feature-breaking / data-correctness)

### 9. [NEW] Wrong password triggers a jarring full-page reload instead of an inline error
**File:** `crime_frontend/src/services/api.ts`

```ts
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("user_data");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
```
This interceptor applies to **every** request made through the shared `api` instance — including the login call itself. `authService.login()` posts to `/auth/login` through this same instance. When an officer types the wrong password, the backend correctly returns **401 Invalid username or password** — but this interceptor intercepts it first, wipes `user_data`, and forces `window.location.href = "/login"` (a hard browser navigation), reloading the entire SPA before `Login.tsx`'s own `catch` block can render the inline error message the UI was designed to show. The net effect: entering a wrong password looks like the app crashed/reset, not like "please check your credentials."

**Fix — don't hijack 401s that come from the login endpoint itself:**
```ts
// api.ts
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginRequest = error.config?.url?.includes("/auth/login");
    if (error.response?.status === 401 && !isLoginRequest) {
      localStorage.removeItem("user_data");
      localStorage.removeItem("is_logged_in");   // see item #10 — clear both flags
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
```

### 10. [NEW] 401 interceptor clears `user_data` but not the `is_logged_in` flag
**File:** `crime_frontend/src/services/api.ts` (same block as #9)

`authSlice.ts` seeds `isAuthenticated` straight from `localStorage.getItem("is_logged_in")` on every fresh page load. The 401 handler removes `user_data` but leaves `is_logged_in` set to `"true"`. After an expired-token redirect, the next full load of the app will briefly re-hydrate Redux with `isAuthenticated: true` and empty user fields, before `ProtectedRoute`'s own `verifyToken()` effect self-corrects it. It's self-healing, but avoidable — fix it at the source instead of relying on a second round-trip to notice.

**Fix:** included directly above in item #9's snippet (`localStorage.removeItem("is_logged_in")` added alongside `user_data`).

### 11. Leaflet crime map doesn't call `invalidateSize()` on layout changes
**File:** `crime_frontend/src/components/maps/CrimeMap.tsx`

`react-leaflet`'s `MapContainer` reacts to the **window** `resize` event automatically, but not to CSS/flex layout changes that don't fire one (opening the right-hand "Map Statistics" panel, collapsing the sidebar). Result: grey/missing tiles and mis-registered markers until the user manually pans/zooms.

**Fix:**
```tsx
// CrimeMap.tsx
import React, { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
// ...

const FitBounds = () => {
  const map = useMap();
  useEffect(() => { map.setView(karnatakaCenter, 7); }, [map]);
  return null;
};

// NEW: keep Leaflet's internal size cache in sync with the actual container
const InvalidateOnResize = () => {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    const ro = new ResizeObserver(() => {
      map.invalidateSize();
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, [map]);
  return null;
};

const CrimeMap: React.FC<Props> = ({ crimes, viewMode, onCrimeSelect }) => {
  // ...
  return (
    <MapContainer center={karnatakaCenter} zoom={7} className="h-full w-full" style={{ background: "#0f172a" }} preferCanvas={true}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap contributors' className="map-tiles" />
      <FitBounds />
      <InvalidateOnResize />
      {/* ...rest unchanged... */}
    </MapContainer>
  );
};
```

### 12. Criminal Network graph never calls `cy.resize()` — goes blank/misaligned on resize, and is never destroyed (memory leak)
**File:** `crime_frontend/src/components/network/NetworkGraph.tsx`

A repo-wide search confirms zero resize handling anywhere in the frontend (`grep -rn "ResizeObserver\|cy.resize" src/` → no matches). Cytoscape.js caches canvas dimensions at construction time and never repaints on container resize on its own. There is also no `cy.destroy()` cleanup, so remounting this component (route change, hot reload, React StrictMode double-invoke) leaks a Cytoscape instance + its canvas/event listeners every time.

**Fix — add both a resize observer and a destroy-on-unmount cleanup:**
```tsx
// NetworkGraph.tsx — inside the NetworkGraph component, alongside the existing effects

// Keep the graph correctly sized as its container changes (sidebar toggle, window resize, etc.)
useEffect(() => {
  if (!containerRef.current) return;
  const el = containerRef.current;
  const ro = new ResizeObserver(() => {
    if (cyRef.current) {
      cyRef.current.resize();
    }
  });
  ro.observe(el);
  return () => ro.disconnect();
}, []);

// Tear down the Cytoscape instance when this component unmounts
useEffect(() => {
  return () => {
    cyRef.current?.destroy();
    cyRef.current = null;
  };
}, []);
```

### 13. CSV export on Crime Map ignores active Crime-Type and Date filters
**File:** `crime_frontend/src/pages/CrimeMapPage.tsx`

```ts
const handleExport = async () => {
  const queryParams = new URLSearchParams({ file_format: "csv" });
  if (filters.district !== "All Districts") queryParams.append("district_id", filters.district);
  // crime_type, date_from, date_to are silently dropped
  const { downloadAuthenticated } = await import("../utils/buildApiUrl");
  await downloadAuthenticated("/crimes/map-data", Object.fromEntries(queryParams.entries()));
};
```
`crimes_router.py`'s `/crimes/map-data` fully supports `crime_type`, `date_from`, `date_to`. An officer who filters the map to "Theft, Bengaluru Urban, last 7 days" and clicks Export gets a CSV of **all crime types in that district over the default 180-day window** instead.

**Fix:**
```ts
// CrimeMapPage.tsx
const handleExport = async () => {
  const queryParams = new URLSearchParams({ file_format: "csv" });
  if (filters.district !== "All Districts") queryParams.append("district_id", filters.district);
  if (filters.crimeType !== "All") queryParams.append("crime_type", filters.crimeType);
  if (filters.dateFrom) queryParams.append("date_from", filters.dateFrom);
  if (filters.dateTo) queryParams.append("date_to", filters.dateTo);
  const { downloadAuthenticated } = await import("../utils/buildApiUrl");
  await downloadAuthenticated("/crimes/map-data", Object.fromEntries(queryParams.entries()));
};
```

### 14. [NEW] Hotspot Analysis CSV export has the exact same filter-dropping bug, in a different file
**File:** `crime_frontend/src/pages/HotspotAnalysis.tsx`

```ts
const handleExport = async () => {
  const queryParams = new URLSearchParams({ file_format: "csv" });
  if (district !== "All Districts") queryParams.append("district_id", district);
  // crime_type, date_from, date_to dropped here too
  const { downloadAuthenticated } = await import("../utils/buildApiUrl");
  await downloadAuthenticated("/hotspots/clusters", Object.fromEntries(queryParams.entries()));
};
```
Same class of bug as #13, independent occurrence — `hotspots_router.py`'s `/clusters` endpoint accepts `crime_type`/`date_from`/`date_to` and this page collects all three in local state (`crimeType`, `dateFrom`, `dateTo`) but never forwards them to the export call.

**Fix:**
```ts
// HotspotAnalysis.tsx
const handleExport = async () => {
  const queryParams = new URLSearchParams({ file_format: "csv" });
  if (district !== "All Districts") queryParams.append("district_id", district);
  if (crimeType !== "All") queryParams.append("crime_type", crimeType);
  if (dateFrom) queryParams.append("date_from", dateFrom);
  if (dateTo) queryParams.append("date_to", dateTo);
  const { downloadAuthenticated } = await import("../utils/buildApiUrl");
  await downloadAuthenticated("/hotspots/clusters", Object.fromEntries(queryParams.entries()));
};
```

### 15. [NEW] Downloaded files (evidence attachments, CSV exports) always save with no filename or extension
**File:** `crime_frontend/src/utils/buildApiUrl.ts`

```ts
export const downloadAuthenticated = async (path: string, params?: Record<string, string>) => {
  const api = (await import("../services/api")).default;
  const response = await api.get(path, { params, responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = "";   // <- always empty
  a.click();
  window.URL.revokeObjectURL(blobUrl);
};
```
This helper is used for evidence downloads (`CrimeDatabase.tsx`, `CrimeMapPage.tsx`) and CSV exports (Crime Map, Hotspot Analysis). The backend correctly sends a `Content-Disposition: attachment; filename="..."` header everywhere (`crimes_router.py` → `crimes_export.csv`, `hotspots_router.py` → `hotspots_export.csv`, and `evidence_router.py`'s `FileResponse(item.file_path, filename=item.description)` for the original uploaded filename) — but this helper discards the header entirely and hands the browser an empty filename, so the browser falls back to a generic name with no extension. Every download from these three flows lands in Downloads as an unlabeled file the OS doesn't know how to open until it's renamed.

**Fix — read the real filename off the response header, with a sensible fallback:**
```ts
// buildApiUrl.ts
export const downloadAuthenticated = async (path: string, params?: Record<string, string>) => {
  const api = (await import("../services/api")).default;
  const response = await api.get(path, { params, responseType: "blob" });

  // Content-Disposition: attachment; filename="crimes_export.csv"
  const disposition: string = response.headers["content-disposition"] || "";
  const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  const filename = match ? decodeURIComponent(match[1]) : path.split("/").pop() || "download";

  const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(blobUrl);
};
```

---

## 🟡 MEDIUM (responsive/UX + minor correctness)

### 16. Sidebar has zero mobile/small-window handling — no breakpoint, no drawer/overlay pattern
**File:** `crime_frontend/src/components/common/Sidebar.tsx` / `App.tsx`

```tsx
<aside className={`${collapsed ? "w-16" : "w-64"} transition-all duration-300 ...`}>
```
No `md:` breakpoint anywhere, no off-canvas drawer pattern. It only manually toggles between a 256px and 64px fixed rail — it never becomes an overlay on narrow viewports. This affects all 14 pages since they share this shell.

**Fix — add a real mobile breakpoint with an off-canvas drawer:**
```tsx
// Sidebar.tsx
interface Props { collapsed: boolean; onToggle: () => void; alertCount?: number; mobileOpen?: boolean; onMobileClose?: () => void; }

const Sidebar: React.FC<Props> = ({ collapsed, onToggle, alertCount = 0, mobileOpen = false, onMobileClose }) => {
  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 md:hidden"
          onClick={onMobileClose}
        />
      )}
      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-40
          ${collapsed ? "md:w-16" : "md:w-64"} w-64
          ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
          transition-all duration-300 bg-slate-900 border-r border-slate-700/50 flex flex-col h-full
        `}
      >
        {/* ...unchanged content... */}
      </aside>
    </>
  );
};
```
```tsx
// App.tsx — add mobile state and a hamburger trigger in the Navbar/shell
const [mobileNavOpen, setMobileNavOpen] = useState(false);
// ...
<Sidebar
  collapsed={sidebarCollapsed}
  onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
  mobileOpen={mobileNavOpen}
  onMobileClose={() => setMobileNavOpen(false)}
  alertCount={alerts?.unreadCount || 0}
/>
```
(Pass a hamburger button into `Navbar` that calls `setMobileNavOpen(true)`, visible only below `md:`.)

### 17. Header/filter rows without `flex-wrap` squish on narrow screens (four separate locations)
Confirmed in four places — the same fix pattern applies to all:

**a) `ReportsPage.tsx`** — the "Generate New Report" form:
```tsx
// Before
<div className="flex gap-4 items-end">
// After
<div className="flex flex-wrap gap-4 items-end">
  <div className="flex-1 min-w-[160px]">{/* Report Type */}</div>
  <div className="flex-1 min-w-[160px]">{/* District Focus */}</div>
  <div className="flex-1 min-w-[140px]">{/* From Date */}</div>
  <div className="flex-1 min-w-[140px]">{/* To Date */}</div>
```

**b) `AlertsPage.tsx`** — the 4 severity stat cards:
```tsx
// Before
<div className="grid grid-cols-4 gap-3">
// After
<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
```

**c) `PredictiveAnalytics.tsx`** — the page header (title + district/date filter bar):
```tsx
// Before
<div className="flex items-center justify-between">
// After
<div className="flex flex-wrap items-center justify-between gap-3">
```
and its inner filter cluster:
```tsx
// Before
<div className="flex items-center gap-4 bg-slate-800/50 p-2 rounded-xl border border-slate-700/50">
// After
<div className="flex flex-wrap items-center gap-3 bg-slate-800/50 p-2 rounded-xl border border-slate-700/50">
```

**d) `SocioEconomicInsights.tsx`** — same header pattern:
```tsx
// Before
<div className="mb-6 flex items-center justify-between">
// After
<div className="mb-6 flex flex-wrap items-center justify-between gap-3">
```

### 18. [NEW] Victim Database page doesn't follow the app's standard scroll/resize container pattern
**File:** `crime_frontend/src/pages/VictimDatabase.tsx`

```tsx
<div className="flex h-full space-x-6">
```
Every other page uses `flex-1 min-h-0 ... overflow-hidden` as the outermost element so that the page correctly confines its own scrolling inside the fixed-height app shell (`App.tsx`'s `<main className="... flex flex-col min-h-0">`). This page uses `h-full` with no `flex-1`/`min-h-0`/`overflow-hidden`, which is the one page in the app whose height computation doesn't match the shared shell contract — at some window heights this can make the whole app shell scroll instead of just this page's internal table, and it behaves inconsistently with the other 13 pages when the window is resized vertically.

**Fix:**
```tsx
// VictimDatabase.tsx
// Before
<div className="flex h-full space-x-6">
// After
<div className="flex-1 min-h-0 w-full overflow-hidden flex space-x-6 p-0">
```
(and keep the existing inner `overflow-auto` table wrapper as-is — it will now correctly scroll within a properly bounded parent).

### 19. [NEW] Redundant double-fetch when changing filters (two separate pages)
**Files:** `crime_frontend/src/pages/AnomalyDetection.tsx` and `crime_frontend/src/pages/OffenderDatabase.tsx`

In `AnomalyDetection.tsx`:
```tsx
useEffect(() => { fetch(); }, [page, severityFilter, statusFilter, districtFilter]);

useEffect(() => { setPage(1); }, [severityFilter, statusFilter, districtFilter]);
```
Changing any filter fires the first effect (fetching with the *old* page), and the second effect resets `page`, which re-triggers the first effect a second time on the next render. Every filter change performs two network calls instead of one against a rate-limited endpoint.

**Fix — merge into a single source of truth so a filter change only ever fetches once:**
```tsx
// AnomalyDetection.tsx
const handleFilterChange = (setter: (v: string) => void, value: string) => {
  setter(value);
  setPage(1);
};

useEffect(() => { fetch(); }, [page, severityFilter, statusFilter, districtFilter]);
// (delete the second `useEffect(() => { setPage(1); }, [...])` entirely)

// then in the JSX, replace direct setStatusFilter/setSeverityFilter/setDistrictFilter calls:
onClick={() => handleFilterChange(setStatusFilter, s)}
// ...
onChange={(e) => handleFilterChange(setSeverityFilter, e.target.value)}
// ...
onChange={(e) => handleFilterChange(setDistrictFilter, e.target.value)}
```
`OffenderDatabase.tsx` has the same shape (each `<select onChange>` calls `setPage(1)` **and** `executeSearch(...)` directly, while a separate `useEffect` also watches `page`) — apply the same consolidation there: let the `onChange` handlers only update state, and let the single `useEffect` (which should watch all filters, not just `[searchParams, page]`) be the only place that calls `executeSearch`:
```tsx
// OffenderDatabase.tsx
useEffect(() => {
  executeSearch(search, districtFilter, crimeTypeFilter, riskLevelFilter, statusFilter, page);
}, [districtFilter, crimeTypeFilter, riskLevelFilter, statusFilter, page]); // was: [searchParams, page]

// and each select's onChange becomes just:
onChange={(e) => { setDistrictFilter(e.target.value); setPage(1); }}
```

### 20. [NEW] Alerts page has no error handling — a failed request leaves it spinning forever
**File:** `crime_frontend/src/pages/AlertsPage.tsx`

```tsx
const load = async () => {
  setLoading(true);
  const data = await alertService.getAlerts(page, pageSize, severityFilter, typeFilter);
  dispatch(setAlerts(data));
  setLoading(false);
};
```
No `try/catch`. If the request throws (network blip, 401, 500), `setLoading(false)` is skipped and the page is stuck on the loading spinner with no error message and no retry — inconsistent with every other page in the app (`Dashboard`, `HotspotAnalysis`, `OffenderDatabase`, etc. all wrap this in `try/catch` + show an error state with a Retry button).

**Fix:**
```tsx
// AlertsPage.tsx
const [error, setError] = useState<string | null>(null);

const load = async () => {
  setLoading(true);
  try {
    const data = await alertService.getAlerts(page, pageSize, severityFilter, typeFilter);
    dispatch(setAlerts(data));
    setError(null);
  } catch (e: any) {
    setError(e.response?.data?.detail || "Failed to load alerts");
  } finally {
    setLoading(false);
  }
};
// ...
if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Loading alerts..." /></div>;
if (error) return (
  <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-4">
    <AlertTriangle className="h-12 w-12 text-red-500" />
    <p>{error}</p>
    <button onClick={load} className="px-4 py-2 bg-slate-800 rounded-lg text-white hover:bg-slate-700">Retry</button>
  </div>
);
```
(remember to `import { AlertTriangle } from "lucide-react";` alongside the existing icon imports).

### 21. [NEW] Alerts "Type" filter dropdown only ever shows types present on the current page
**File:** `crime_frontend/src/pages/AlertsPage.tsx`

```tsx
const alertTypes = Array.from(new Set((alerts as { alert_type: string }[]).map((a) => a.alert_type)));
```
`alerts` here is only the current page's 20 records (server-side paginated), so the "All Types" dropdown can never offer a type that doesn't happen to appear on whatever page you're currently viewing — you can't filter *to* a type unless you already happened to see one from it.

**Fix — use a fixed, complete list instead of deriving it from paginated data** (mirroring the pattern already used for crime types/status elsewhere in the app):
```tsx
// AlertsPage.tsx
const ALERT_TYPES = ["CRIME_SPIKE", "HOTSPOT_EMERGING", "ANOMALY_DETECTED", "HIGH_RISK_PREDICTION", "SYSTEM"]; // match backend's actual alert_type values
// ...
<select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="...">
  <option value="All">All Types</option>
  {ALERT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
</select>
```
(Confirm the exact enum values against `alert_service.py`/the `Alert` model before hardcoding — if there's no fixed enum backend-side, expose a small `/alerts/types` endpoint instead of guessing.)

---

## 🟢 LOW (polish / defensive coding)

### 22. `NaN` can appear in a couple of computed display values when a data set is empty
**Files:** `SocioEconomicInsights.tsx`, `AnomalyDetection.tsx`

```tsx
// SocioEconomicInsights.tsx — divides by zero if chartData is empty (e.g. a district with no overlay data)
{ title: "Avg Crime Rate", value: (chartData.reduce((acc: number, val: any) => acc + val.crimeRate, 0) / chartData.length).toFixed(1), ... }

// AnomalyDetection.tsx — displays "NaN%" if confidence_score is ever null/undefined from the API
<span>Confidence: <span className="text-blue-400 font-bold">{(a.confidence_score * 100).toFixed(0)}%</span></span>
```
Neither throws, but both can render the literal string `NaN` / `NaN%` to an officer's screen.

**Fix:**
```tsx
// SocioEconomicInsights.tsx
{
  title: "Avg Crime Rate",
  value: chartData.length > 0
    ? (chartData.reduce((acc: number, val: any) => acc + val.crimeRate, 0) / chartData.length).toFixed(1)
    : "N/A",
  ...
}
```
```tsx
// AnomalyDetection.tsx
<span>Confidence: <span className="text-blue-400 font-bold">
  {typeof a.confidence_score === "number" ? `${(a.confidence_score * 100).toFixed(0)}%` : "N/A"}
</span></span>
```

### 23. `window.confirm()` used for destructive delete on Crime Database
**File:** `CrimeDatabase.tsx` — native `confirm()` dialogs are inconsistent across browsers/mobile and can't match the dark theme. Not a functional bug; consider a themed confirm modal in a polish pass.

### 24. Report list "Download CSV" is unreachable from the UI
The backend fully supports `GET /reports/{id}/download?format=csv` and `export_report_csv()` is implemented, but `ReportsPage.tsx`'s download button always requests the PDF. Minor missed feature — worth wiring up a "Download ⌄ PDF / CSV" split button since the backend work already exists.

### 25. Dead code: a "using mock data" banner exists but nothing ever triggers it
**Files:** `crime_frontend/src/utils/mockDataFlag.ts`, `crime_frontend/src/services/mockData.ts`, `components/common/Navbar.tsx`

`Navbar.tsx` listens for a `"mock-data-detected"` window event and would show a banner (`usingMockData`), and `flagMockDataUsed()` exists to dispatch that event — but nothing in the entire codebase ever calls `flagMockDataUsed()`, and the 683-line `mockData.ts` is never imported anywhere. Not a bug, just incomplete/dead code worth either wiring up (call `flagMockDataUsed()` from `api.ts`'s error interceptor when the backend is fully unreachable) or deleting to reduce bundle size and confusion.

---

## Page-by-page wiring confirmation (all 14 pages)

Every path in `crime_frontend/src/constants/apiEndpoints.ts` was cross-checked against every `@router.*` decorator across all 16 backend router files — they match 1:1, so routing/wiring itself is sound everywhere. Status below reflects **functional correctness of what's wired**, not just "does a request get sent."

| # | Page | Route | Backend wiring | Notes |
|---|------|-------|-----------------|-------|
| 1 | Login | `/login` | ✅ `auth_router.py` | Cookie hardcoded insecure (#5); wrong-password UX broken by global interceptor (#9) |
| 2 | Dashboard | `/` | ✅ `dashboard_router.py` | Clean — no issues found |
| 3 | Crime Map | `/map` | ✅ `crimes_router.py` | Leaflet resize (#11), export filters dropped (#13), download filenames (#15) |
| 4 | Crime Database | `/crimes` | ✅ `crimes_router.py` | Clean aside from download filenames (#15) and minor #23 |
| 5 | Hotspot Analysis | `/hotspots` | ✅ `hotspots_router.py` | CSV export 500s always (#4), export filters dropped (#14) |
| 6 | Criminal Network | `/network` | ✅ `network_router.py` | Cytoscape resize + leak (#12) |
| 7 | Anomaly Detection | `/anomalies` | ✅ `anomalies_router.py` | Double-fetch on filter change (#19), NaN display (#22) |
| 8 | Predictive Analytics | `/predictions` | ✅ `predictions_router.py` | Header wrap (#17c) |
| 9 | Offender Database | `/offenders` | ✅ `offenders_router.py` | Double-fetch on filter change (#19) |
| 10 | Victim Database | `/victims` | ✅ `victims_router.py` | Non-standard page container (#18) |
| 11 | Socio-Economic Insights | `/socioeconomic` | ✅ `predictions_router.py` | Header wrap (#17d), NaN display (#22) |
| 12 | Alerts Center | `/alerts` | ✅ `alerts_router.py` | Grid wrap (#17b), no error handling (#20), type filter limited to current page (#21) |
| 13 | Reports | `/reports` | ✅ `reports_router.py` | Date filter dropped (#7), PDF XML crash (#6), form wrap (#17a), CSV unreachable (#24) |
| 14 | Settings & Administration | `/settings` | ✅ `settings_router.py` | **Infinite loading spinner for 2 of 3 roles** (#2) |

Additionally, the shared app shell (`Navbar.tsx`, `Sidebar.tsx`, `App.tsx`), which every one of the 14 pages renders inside, has three of its own issues (#1 logout, #3 global search crash, #16 no mobile drawer) that affect the whole app regardless of which page you're on.

---

## Database connectivity summary
- **PostgreSQL**: primary store for crimes/offenders/victims/hotspots/reports/users — all routers query it via async SQLAlchemy; consistent everywhere.
- **Neo4j**: powers `/network/*` graph traversal (`expand`, `shortest-path`). The backend has a genuinely good fallback: if Neo4j is down, `network_service.py` falls back to building the graph from Postgres relationship tables and flags `source: "postgres_fallback"`, which the frontend correctly detects and displays a warning banner for (`isFallbackMode` in `CriminalNetwork.tsx`). This remains one of the better-engineered parts of the app.
- **Redis**: used for response caching (`cache_get`/`cache_set`) and JWT blacklisting on logout — except logout is never actually called from the UI (see #1), so the blacklist mechanism, while correctly implemented server-side, currently never fires in practice. Password handling itself is correct (passed as a separate parameter, not embedded in the URL). See #8 for the `.env` path mismatch in Compose.

---

## Full fix checklist
- [ ] #1 — Navbar `handleLogout` must call `authService.logout()` before clearing local state
- [ ] #2 — Settings page: split role-gated vs. open requests, use `Promise.allSettled`, gate tabs by role
- [ ] #3 — Navbar global search: unwrap `{success, data}` envelope + default to empty arrays
- [ ] #4 — `hotspots_router.py` CSV export: read `data["hotspots"]`, not `data[0]`
- [ ] #5 — `auth_router.py`: `secure=settings.ENVIRONMENT == "production"` on both set/delete cookie
- [ ] #6 — `report_service.py`: escape all text going into ReportLab `Paragraph`/`Table` calls
- [ ] #7 — `reportService.ts`: forward `date_from`/`date_to` in `generateReport`
- [ ] #8 — `docker-compose.yml`: point `redis` service at root `.env`
- [ ] #9 — `api.ts`: exclude `/auth/login` from the global 401 redirect handler
- [ ] #10 — `api.ts`: clear `is_logged_in` alongside `user_data` on 401
- [ ] #11 — `CrimeMap.tsx`: add `InvalidateOnResize` helper inside `MapContainer`
- [ ] #12 — `NetworkGraph.tsx`: add `ResizeObserver` → `cy.resize()`, and `cy.destroy()` on unmount
- [ ] #13 — `CrimeMapPage.handleExport`: forward `crime_type`/`date_from`/`date_to`
- [ ] #14 — `HotspotAnalysis.handleExport`: forward `crime_type`/`date_from`/`date_to`
- [ ] #15 — `buildApiUrl.ts`: parse `Content-Disposition` for the real filename
- [ ] #16 — `Sidebar.tsx`/`App.tsx`: real mobile drawer breakpoint
- [ ] #17 — `flex-wrap` on Reports form, Alerts grid, Predictive Analytics header, Socio-Economic header
- [ ] #18 — `VictimDatabase.tsx`: match the standard `flex-1 min-h-0 overflow-hidden` page container pattern
- [ ] #19 — `AnomalyDetection.tsx` / `OffenderDatabase.tsx`: remove duplicate fetch-on-filter-change
- [ ] #20 — `AlertsPage.tsx`: wrap `load()` in `try/catch/finally` with an error+retry state
- [ ] #21 — `AlertsPage.tsx`: use a fixed alert-type list instead of deriving from the current page
- [ ] #22 — Guard divide-by-zero / null `confidence_score` before `.toFixed()`
- [ ] #23 — (optional polish) themed confirm modal for delete
- [ ] #24 — (optional feature) wire up CSV download option in Reports UI
- [ ] #25 — (optional cleanup) wire up or delete the unused mock-data banner/file