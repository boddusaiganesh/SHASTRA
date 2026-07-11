# SHASTRA Crime Intelligence Platform — Full Codebase Audit

**Scope reviewed:** `crime_frontend/` (React + Vite + TS, 71 files) and `crime_backend/MODULE_2_BACKEND/` (FastAPI, 91 files) — ~20,300 LOC total. Covers all 14 requested pages, frontend↔backend wiring, DB connections (PostgreSQL/Neo4j/Redis), the Criminal Network graph + filters, district/crime-type filters app‑wide, AI (Gemini) integration, Docker/deployment config, and static analysis (`pyflakes`) of the entire backend.

**How to read this:** Every issue below cites the exact file/line and the offending code. Severity: 🔴 Critical (crashes/broken data/security) · 🟠 High (feature silently broken) · 🟡 Medium (UX/consistency) · ⚪ Low (code quality).

---

## 1. Critical Bugs (crashes / silently wrong data)

### 1.1 🔴 `NameError` crash in Network Graph "expand node" — Criminal Network page
**File:** `crime_backend/MODULE_2_BACKEND/app/routers/network_router.py`

`status` is used but never imported. This code path is the *fallback error handler* for when Neo4j is offline — exactly the moment you need a clean error, this throws an unhandled `NameError` instead, turning a controlled 503 into a raw 500.

```python
# top of file — only these are imported:
from fastapi import APIRouter, Depends, HTTPException, Query, Request
...
    try:
        results = await run_neo4j_query(query, {"id": node_id})
        if not results:
            return {"success": True, "data": {"nodes": [], "edges": []}}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,   # <-- `status` undefined here
            detail="Node expansion is currently not available in fallback mode (Neo4j is offline)."
        )
```
Confirmed via static analysis:
```
app/routers/network_router.py:128:25: undefined name 'status'
```
**Impact:** Clicking "Expand node" on the Criminal Network graph while Neo4j is down (or on any Neo4j query error) crashes the request with a 500 and a confusing traceback instead of the intended graceful message.

**✅ Fix:**
```python
# app/routers/network_router.py — top of file
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
#                                                                       ^^^^^^ add this
```
No other change needed — the rest of the `except` block already references `status.HTTP_503_SERVICE_UNAVAILABLE` correctly, it just needs the name in scope.

---

### 1.2 🔴 AI Network Summary is always empty / wrong stats — Criminal Network page
**File:** `crime_backend/MODULE_2_BACKEND/app/services/network_service.py` → `get_network_ai_summary()`

```python
all_offenders = []
for node in graph_data.get("nodes", []):
    if node.get("node_type") == "criminal" or node.get("node_type") == "Offender":
        props = node.get("properties", {})     # <-- BUG: no node ever has a "properties" key
        if props:
            ...
            all_offenders.append(props)
```
Every node object actually built by this codebase (both paths) stores the offender's data under **`profile_data`**, never `properties`:

```python
# Neo4j path — app/core/neo4j_connection.py, normalize_node()
return {
    "node_id": node_id,
    "node_type": node_type,
    ...
    "profile_data": dict(raw_node),   # <-- real key
}

# Postgres-fallback path — network_service.py, build_network_from_postgres()
nodes.append({
    "node_id": node_id,
    "node_type": "criminal",
    ...
    "profile_data": { ... },          # <-- real key
})
```
Because `node.get("properties", {})` never matches, `props` is always `{}`, so `all_offenders` is always empty, `suspicious_pairs` is always `[]`, and `network_stats` (`total_criminals`, `high_risk_count`, `active_count`, `network_density`) is always `0`. The `/network/ai-summary` endpoint (Criminal Network page → "AI Network Analysis" panel) **never reflects the real graph**, regardless of Neo4j being up or the Postgres fallback being used.

**✅ Fix:**
```python
# app/services/network_service.py — get_network_ai_summary()

# Extract offenders from the graph nodes
all_offenders = []
for node in graph_data.get("nodes", []):
    if node.get("node_type") != "criminal":
        continue
    props = dict(node.get("profile_data", {}) or {})   # <-- was node.get("properties", {})
    if not props:
        continue
    props.setdefault("full_name", node.get("label", "Unknown"))
    props.setdefault("risk_score", node.get("risk_score", 0))
    all_offenders.append(props)
```
**Related follow-on bug you should fix at the same time:** even after this correction, `known_associates` will still always be missing from `props`, because neither `normalize_node()` (Neo4j path) nor `build_network_from_postgres()` (Postgres fallback) ever copies `known_associates` into the node's `profile_data` — it's only used internally to build edges, then discarded. That means the "suspicious pairs" logic a few lines down will still always return `[]`:
```python
for o1, o2 in itertools.combinations(all_offenders, 2):
    common = set(o1.get("known_associates", [])) & set(o2.get("known_associates", []))  # always empty set ∩ empty set
```
Fix by embedding `known_associates` into the node's `profile_data` at build time in **both** places:
```python
# app/services/network_service.py — build_network_from_postgres(), inside the "Criminals" block
nodes.append({
    "node_id": node_id,
    "node_type": "criminal",
    "label": f"{offender.first_name} {offender.last_name}",
    "risk_score": offender.risk_score or 0,
    "crime_count": offender.total_crimes or 0,
    "size": 15 + (offender.total_crimes or 0) * 3,
    "color": color,
    "profile_data": {
        "offender_reference": offender.offender_reference,
        "status": offender.status,
        "risk_level": offender.risk_level,
        "district_id": offender.district_id,
        "known_associates": offender.known_associates or [],   # <-- add this line
    },
})
```
And on the Neo4j write side, add `known_associates` so `raw_node` (and therefore `profile_data`) contains it:
```python
# app/core/neo4j_connection.py — sync_offender_to_neo4j()
async def sync_offender_to_neo4j(offender_data: Dict[str, Any]):
    query = """
    MERGE (c:Criminal {offender_id: $offender_id})
    SET c.name = $name,
        c.risk_level = $risk_level,
        c.risk_score = $risk_score,
        c.crime_count = $crime_count,
        c.status = $status,
        c.district_id = $district_id,
        c.crime_types = $crime_types,
        c.known_associates = $known_associates
    RETURN c
    """
    await run_neo4j_query(query, offender_data)
```
```python
# scripts/sync_postgres_to_neo4j.py — inside the "Sync Offenders" loop
await sync_offender_to_neo4j({
    "offender_id": str(off.offender_id),
    "name": f"{off.first_name} {off.last_name}",
    "risk_level": off.risk_level,
    "risk_score": off.risk_score or 0,
    "crime_count": off.total_crimes or 0,
    "status": off.status,
    "district_id": off.district_id,
    "crime_types": off_crime_types,
    "known_associates": off.known_associates or [],   # <-- add this line
})
```

---

### 1.3 🟠 Hotspot Analysis: `crime_type` / date-range filters are silently ignored by the backend
**Frontend — `pages/HotspotAnalysis.tsx`:**
```tsx
const [crimeType, setCrimeType] = useState("All");
...
if (crimeType !== "All") params.crime_type = crimeType;
...
crimeService.getHotspotClusters({ ...params, page, page_size: pageSize })
```
**Backend — `app/routers/hotspots_router.py` `/clusters`:**
```python
@router.get("/clusters")
async def hotspot_clusters(
    district_id: Optional[str] = Query(None),
    file_format: str = Query("json", enum=["json", "csv"]),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # crime_type, date_from, date_to are NOT declared as query params at all
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_hotspot_clusters(db, district_id, None, None, None, page, page_size)
    #                                              ^^^^  ^^^^  ^^^^ hard-coded None
```
FastAPI silently drops unknown query params — no error is raised, the UI just doesn't filter. `get_hotspot_clusters()` in `hotspot_service.py` **does** accept and honor `crime_type`/`date_from`/`date_to`, so the service layer is ready; only the router forgot to wire it through.
**Impact:** the Crime Type dropdown and Date range pickers on the Hotspot Analysis page have zero effect on results.
**Fix direction:** add `crime_type: Optional[str] = Query(None)`, `date_from: Optional[str] = Query(None)`, `date_to: Optional[str] = Query(None)` to the router signature and pass them through instead of `None, None, None`.

---

### 1.4 🟠 Hotspot cluster cache key omits pagination → page 2+ returns page‑1 data
**File:** `app/services/hotspot_service.py`
```python
cache_key = f"hotspot_clusters:{district_id}:{crime_type}:{date_from}:{date_to}"
cached = await cache_get(cache_key)
if cached:
    return cached
...
response = {
    "hotspots": hotspots_data,   # built from hotspots_paginated (page-specific)
    ...
    "page": page,
    "page_size": page_size,
}
await cache_set(cache_key, response, expiry=900)
```
`page`/`page_size` are excluded from the cache key. First call for `page=1` populates the cache under a key with no page info; the next call for `page=2` (same filters) hits that cache and **returns page 1's hotspot list again**, just with `page: 2` printed in the payload.
**Fix direction:** include `page`/`page_size` in `cache_key`.

---

### 1.5 🟠 Predictive Analytics: district & date-range filters are ignored by most endpoints
**Frontend — `pages/PredictiveAnalytics.tsx`:**
```tsx
predictionService.getForecast(districtFilter, dateFrom, dateTo),
predictionService.getHighRiskAreas(districtFilter, dateFrom, dateTo),
predictionService.getEmergingTypologies(districtFilter, dateFrom, dateTo),
predictionService.getRiskMap(districtFilter, dateFrom, dateTo),
```
**Backend `app/routers/predictions_router.py`:**
```python
@router.get("/risk-map")
async def risk_map(request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    district_id = None
    if current_user["role"] == "DISTRICT_OFFICER":
        district_id = current_user.get("district_id")
    data = await get_risk_map(db, district_id=district_id)   # no query params accepted at all
    return {"success": True, "data": data}

@router.get("/forecast")
async def forecast(
    request: Request,
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    days_ahead: int = Query(30, le=90),          # no date_from / date_to
    ...
):
```
| UI control | Sent by frontend to | Actually read by backend |
|---|---|---|
| District dropdown | `risk-map` (`district_id`) | ❌ not declared — ignored |
| Date From / Date To | `risk-map`, `forecast`, `high-risk-areas`, `emerging-typologies` (`date_from`/`date_to`) | ❌ none of these routes declare `date_from`/`date_to` |
| District dropdown | `forecast`, `high-risk-areas`, `emerging-typologies` | ✅ honored |

**Impact:** selecting a district for the Risk Map view, or setting any date range anywhere on the Predictive Analytics page, has **no effect** on the returned data — the page silently shows unfiltered/default results while the UI implies it's filtered.
**Fix direction:** either remove the non-functional date pickers from the UI, or add `district_id`/`date_from`/`date_to` query params to `risk_map`, `forecast`, `high_risk_areas`, `emerging_typologies` and thread them into the corresponding `prediction_service.py` functions.

---

### 1.6 🟡 Alerts Center: severity/type filters only apply to the currently-fetched page, not the full dataset
**File:** `pages/AlertsPage.tsx`
```tsx
const data = await alertService.getAlerts(page, pageSize);   // only page & pageSize sent
...
const filtered = alerts.filter(a => {
  if (severityFilter !== "All" && a.severity !== severityFilter) return false;
  if (typeFilter !== "All" && a.alert_type !== typeFilter) return false;
  ...
});
```
`alertService.getAlerts()` calls `GET /alerts/active` (which does accept `district_id`, `page`, `page_size` server-side) but never sends `severity`/`alert_type`, and the backend `active_alerts()` endpoint doesn't even accept those params. Filtering then happens **client-side against only the current page's 20 rows**, while the pager (`Next`/`Prev`, page count) is driven by the *server's unfiltered total*. Selecting "Critical" severity on page 1 can show 0 rows even though critical alerts exist on page 3, and the page count shown doesn't shrink to match the filtered set.
**Fix direction:** either add `severity`/`alert_type` query params to `GET /api/alerts/active` and pass them from the frontend, or fully paginate client-side by fetching the full alert set once.

---

## 2. Security Issues

### 2.1 🔴 Evidence upload/download endpoints have no district-based access control (IDOR)
**File:** `app/routers/evidence_router.py`
```python
@router.get("/{crime_id}")
async def list_evidence(crime_id: str, db: AsyncSession = Depends(get_db),
                         current_user=Depends(get_current_user)):     # any authenticated user
    ...
@router.get("/download/{evidence_id}")
async def download_evidence(evidence_id: str, db: AsyncSession = Depends(get_db),
                             current_user=Depends(get_current_user)):  # any authenticated user
    result = await db.execute(select(Evidence).where(Evidence.evidence_id == evidence_id))
    item = result.scalar_one_or_none()
    if not item or not os.path.exists(item.file_path):
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(item.file_path, filename=item.description)
```
Every other resource type in this codebase (crimes, offenders, victims, anomalies, reports) enforces `DISTRICT_OFFICER` scoping — e.g. `crimes_router.py` uses `scope_district_filter`, `offenders_router.py` compares `current_user.get("district_id")`. Evidence upload/list/download has **no such check anywhere** — `evidence_id` is a guessable/enumerable identifier and any logged-in user (including a `DISTRICT_OFFICER` from an unrelated district) can list or download any case's evidence files (photos, docs, audio) just by knowing/guessing the ID.
**Fix direction:** join `Evidence → Crime` and apply the same `scope_district_filter`/district comparison used elsewhere before returning/streaming the file.

---

### 2.2 🟡 `verify-token` leaks the JWT into the JSON body, undermining the httpOnly cookie
**File:** `app/routers/auth_router.py`
```python
@router.get("/verify-token")
async def verify_token(current_user=Depends(get_current_user)):
    return {
        "success": True,
        "data": {
            "auth_token": current_user["token"],   # <-- token re-exposed in JS-readable JSON
            ...
        }
    }
```
Login correctly sets the JWT as an `httponly` cookie specifically so client-side JS (and any XSS payload) can't read it:
```python
# auth_router.py — login()
response.set_cookie(key="auth_token", value=token_data["auth_token"], httponly=True, ...)
safe_data = {k: v for k, v in token_data.items() if k != "auth_token"}  # correctly stripped here
```
...but `verify-token` (called on every app mount via `authService.verifyToken()`) puts the same raw token right back into a response body that `axios`/JS can read, defeating the point of `httponly`.
**Fix direction:** drop `auth_token` from the `verify-token` response payload — the frontend never actually uses it (`authService.verifyToken()` only checks the request didn't throw).

---

### 2.3 🟡 CSP header is applied to API/JSON responses, not just HTML — provides no real protection and can be dropped/simplified
**File:** `main.py`
```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        ...
        if request.url.path in ("/docs", "/redoc"):
            response.headers["Content-Security-Policy"] = (...)
        else:
            response.headers["Content-Security-Policy"] = (
                f"default-src 'self'; connect-src 'self' {settings.FRONTEND_URL}"
            )
        return response
```
CSP only matters for documents a browser renders/executes (HTML). Every `/api/*` JSON response gets this header too, which is inert there — it's not wrong, just dead weight, and can create confusion when debugging (looks like it's protecting something it isn't). Real CSP for the app should be set by the frontend's own server (see `crime_frontend/nginx.conf`).

### 2.4 🟡 `Settings → Add User` accepts an unvalidated raw `dict` — missing fields crash with a raw 500, duplicate usernames aren't handled cleanly
**File:** `app/routers/settings_router.py`
```python
@router.post("/users/add")
async def add_user(user_data: dict = Body(...), db: AsyncSession = Depends(get_db),
                    current_user=Depends(require_scrb_officer)):
    new_user = await create_user(db, user_data)
    return {"success": True, "data": new_user}
```
**`auth_service.create_user()`:**
```python
async def create_user(db: AsyncSession, user_data: Dict[str, Any]) -> Dict[str, Any]:
    result = await db.execute(select(User).where(User.username == user_data["username"]))
    if result.scalar_one_or_none():
        raise ValueError(f"Username '{user_data['username']}' already exists")   # never caught → 500
    password_hash = hash_password(user_data["password"])   # KeyError if missing → 500
    ...
    new_user = User(
        username=user_data["username"],
        full_name=user_data["full_name"],   # KeyError if missing → 500
        role=user_data["role"],             # KeyError if missing → 500
        ...
    )
```
No Pydantic request model, no password strength/length check, and the `ValueError` for duplicate usernames is never caught in the router — it bubbles up to the global exception handler and returns a generic `500 Internal Server Error` instead of a proper `409 Conflict`/`400 Bad Request`.
**Fix direction:** define a `CreateUserRequest(BaseModel)` with required fields + password policy, and catch `ValueError` in the router to return `HTTPException(409, ...)`.

---

## 3. Deployment / Infrastructure Issues (Database connections, Docker, env)

### 3.1 🔴 README's setup command points at the wrong directory — `docker compose up` will fail out of the box
**File:** `README.md`
```bash
cd crime_backend/MODULE_2_BACKEND
docker compose up -d --build
```
`docker-compose.yml` lives at the **repo root** (`SHASTRA-main/docker-compose.yml`); `crime_backend/MODULE_2_BACKEND/` only has `docker-compose.prod.yml` (an override file with no `services:` root config beyond `ports: []`). Running the documented command from that subdirectory gives Docker Compose's classic *"no configuration file provided: not found"* error.
**Fix direction:** README should say `cd SHASTRA-main && docker compose up -d --build` (repo root), and separately document `docker compose -f docker-compose.yml -f crime_backend/MODULE_2_BACKEND/docker-compose.prod.yml up -d` for the production override.

### 3.2 🔴 Root `.env.example` is missing the variables `docker-compose.yml` actually needs for interpolation
**File:** `docker-compose.yml` (root) references these at the **compose-file level** (`${VAR}` interpolation, resolved from a `.env` file *at the same directory as docker-compose.yml*, i.e. the repo root):
```yaml
frontend:
  build:
    args:
      VITE_API_URL: ${FRONTEND_VITE_API_URL}
      VITE_WS_URL: ${FRONTEND_VITE_WS_URL}
...
postgres:
  environment:
    POSTGRES_USER: ${DATABASE_USER}
    POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
    POSTGRES_DB: ${DATABASE_NAME}
...
neo4j:
  environment:
    NEO4J_AUTH: ${NEO4J_USER}/${NEO4J_PASSWORD}
```
But the **root** `.env.example` only contains:
```
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/api/alerts/ws
VITE_DEMO_MODE=false
```
`DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_NAME`, `NEO4J_USER`, `NEO4J_PASSWORD`, `FRONTEND_VITE_API_URL`, `FRONTEND_VITE_WS_URL` are **not present** — those only exist in `crime_backend/MODULE_2_BACKEND/.env.example`, which is loaded via `env_file:` **inside the backend/scheduler containers only**, not for root-level compose interpolation. If someone copies the root `.env.example` → `.env` (the natural thing to do) and runs `docker compose up`, Compose substitutes **empty strings**:
- `postgres` container starts with empty `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` → Postgres init fails or creates unusable defaults.
- `neo4j` container gets `NEO4J_AUTH: /` → invalid, container will not start correctly.
- `backend`'s computed `DATABASE_URL: postgresql+asyncpg://${DATABASE_USER}:${DATABASE_PASSWORD}@postgres:5432/${DATABASE_NAME}` becomes `postgresql+asyncpg://:@postgres:5432/` → malformed.
- `frontend` build gets `VITE_API_URL=""` baked into the static build → every API call from the built frontend breaks.

**Fix direction:** merge one authoritative root `.env.example` containing **all** variables the root `docker-compose.yml` interpolates (`DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_NAME`, `NEO4J_USER`, `NEO4J_PASSWORD`, `REDIS_PASSWORD`, `FRONTEND_VITE_API_URL`, `FRONTEND_VITE_WS_URL`, `GEMINI_API_KEY(S)`, `JWT_SECRET_KEY`, etc.), and have both the `backend/.env` and root `.env` reference the same source of truth (or document that only one `.env` — at root — should be maintained, with `env_file:` pointed at it for every service).

### 3.3 🟡 `docker-compose.prod.yml` lives in a different directory than the base file it overrides
`crime_backend/MODULE_2_BACKEND/docker-compose.prod.yml` is a Compose *override* file meant to be combined with the root `docker-compose.yml`, but nothing in the README documents the two-file `-f`/`-f` invocation, and their separation across two directories makes the intended command non-obvious:
```bash
# Not documented anywhere, but required to use the prod override:
docker compose -f docker-compose.yml -f crime_backend/MODULE_2_BACKEND/docker-compose.prod.yml up -d
```

### 3.4 🟡 Health check reports "healthy" services generically but nothing in the UI surfaces individual DB failures beyond Settings
`GET /api/health` (in `main.py`) correctly aggregates Postgres/Redis/Neo4j health, and `settingsService.getDataSources()` on the **Settings & Administration** page consumes it — that part is wired correctly. However, no other page (Dashboard, Crime Map, etc.) checks `/api/health` before rendering, so if e.g. Neo4j is down, the Criminal Network page's only signal is the `{"status": "offline", ...}` payload embedded inside graph data (handled), while Postgres being down produces various unhandled `500`s across almost every other page (each service's `catch` block only special-cases demo-mode fallback or rethrows — see §4).

---

## 4. Frontend Error Handling / Demo-Mode Inconsistency

`crime_frontend/src/services/api.ts` intentionally removed automatic mock-data fallback:
```ts
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("auth_token");   // 🟡 this key is never actually set anywhere
      localStorage.removeItem("user_data");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
```
But most services still hand-roll a **per-call** mock fallback guarded by `VITE_DEMO_MODE`:
```ts
} catch (error) {
  if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockDashboardSummary; }
  throw error;
}
```
This pattern is applied **inconsistently**:
- `crimeService`, `offenderService`, `predictionService`, `settingsService`, `reportService`, `alertService` → have demo-mode fallback.
- `networkService`, `victimService`, `authService`, `evidenceService` → **no** demo-mode fallback at all (they either `throw` or silently `return null`/log to console).

Net effect: with `VITE_DEMO_MODE=true`, Dashboard/Crime Map/Offenders/Reports keep working when the backend is down, but Criminal Network, Victim Database, and Evidence uploads just break — an inconsistent demo experience, and a maintenance trap (every new service call has to remember to add the same boilerplate).

**Fix direction:** centralize the demo-mode fallback logic in the axios response interceptor (single place), or drop per-service mock fallback entirely and rely on one clear "backend unreachable" banner (`AlertBanner.tsx` already exists for this purpose but isn't used this way).

Also note — `api.ts` removes `localStorage["auth_token"]` on 401, but nothing in the codebase ever **sets** `localStorage["auth_token"]` (auth now correctly lives in an httpOnly cookie, and `authSlice.ts` only ever sets `is_logged_in`/`user_data`). Dead/confusing code — harmless but should be removed for clarity.

---

## 5. Page-by-Page Findings

| # | Page | Route | Status | Notes |
|---|---|---|---|---|
| 1 | Login | `/login` | ✅ OK | Cookie-based JWT auth wired correctly end-to-end; rate limited 10/min server-side. |
| 2 | Dashboard | `/` | ✅ OK | `crimeService.getDashboardSummary/getCrimeTrends/getRecentCrimes/getRecentAlerts` map cleanly to `dashboard_router.py`. No district selector by design (server auto-scopes `DISTRICT_OFFICER`). |
| 3 | Crime Map | `/map` | ✅ OK, minor | `map-data` filters (`crime_type`, `district_id`, `date_from/to`, bbox) all correctly declared/consumed both sides. CSV export (`file_format=csv`) works only through the *uncached* code path — verify large exports don't time out (`limit` caps at 20000). |
| 4 | Crime Database | `/crimes` | ✅ OK | `/crimes/filter` fully wired: `q`, `district_id`, `crime_type`, `status`, `page`/`page_size` all match; status dropdown values (`REPORTED`/`UNDER_INVESTIGATION`/…) match `CRIME_STATUS_VALUES` exactly on both ends. |
| 5 | Hotspot Analysis | `/hotspots` | 🟠 Broken filters | See **§1.3** (crime type & date filters ignored) and **§1.4** (pagination cache bug). |
| 6 | Criminal Network | `/network` | 🔴 Broken feature | See **§1.1** (crash on Neo4j-offline expand) and **§1.2** (AI summary always empty). Graph itself (nodes/edges/centrality/communities) is otherwise well built — see deep-dive in §6. |
| 7 | Anomaly Detection | `/anomalies` | ✅ OK | `severity`, `status`, `district_id`, `page`/`page_size` all wired through `anomalyService.getList` → `/anomalies/list`. |
| 8 | Predictive Analytics | `/predictions` | 🟠 Broken filters | See **§1.5** — district/date filters silently ignored on Risk Map, Forecast, High-Risk Areas, Emerging Typologies. |
| 9 | Offender Database | `/offenders` | ✅ OK | `district_id`, `crime_type`, `risk_level`, `status`, free-text search all correctly filtered server-side in `offender_service.search_offenders`. |
| 10 | Victim Database | `/victims` | 🟡 Minor | `victimService`/`victims_router.py` wired correctly, but has **no demo-mode mock fallback** (see §4) — a backend outage here shows a raw error instead of the graceful degradation other pages get. |
| 11 | Socio-Economic Insights | `/socioeconomic` | ✅ OK | Straightforward `district_id` filter, single endpoint. |
| 12 | Alerts Center | `/alerts` | 🟡 Filter bug | See **§1.6** — severity/type filters only apply to the current page of results, not the full list. |
| 13 | Reports | `/reports` | 🟡 Missing UI wiring | Backend `/reports/generate` supports `date_from`/`date_to` scoping, but `ReportsPage.tsx` never exposes date inputs or sends them — reports can only be scoped by type + district, not date range, even though the capability exists server-side. |
| 14 | Settings & Administration | `/settings` | 🟠 Validation gap | See **§2.4** (unvalidated Add User) and **§3.4** (health check only surfaced here). |

---

## 6. Criminal Network Graph — Deep Dive

Beyond the two crashes in §1.1/§1.2, the graph feature itself is well designed:

- **Dual data source** (`network_service.py`): tries Neo4j first (`get_network_graph`), falls back to a hand-built Postgres reconstruction (`build_network_from_postgres`) when Neo4j is offline — this fallback correctly re-derives criminal/victim/location nodes and edges from `CrimeOffenderLink`/`CrimeVictimLink`/`Crime.location_id`, and *does* respect the active `crime_type`/`district_id`/`node_type` filters (this part is solid — only the AI summary layer on top is broken, per §1.2).
- **Centrality & community detection** (`compute_graph_centrality`, `detect_communities`) run in a thread pool via `run_in_executor` so they don't block the event loop — correct pattern.
- **Filters** (`CriminalNetwork.tsx`): `districtFilter`, `crimeTypeLens`, `nodeTypeFilter`, `searchQuery` are all correctly threaded into `networkService.getGraphData(...)` and `getAiSummary(...)`, and reflected into the URL via `useSearchParams` (shareable/bookmarkable filter state) — good practice, no issues found here.
- **One inconsistency to note:** `build_network_from_postgres` explicitly refuses `node_type=organization` (`"warning": "Organization entities are only available when Neo4j is connected."`), but the frontend's node-type filter (`NODE_TYPES` in `crimeTypes.ts`) still offers "organization" as a selectable option with no visual indication it will return empty results whenever Neo4j is down — worth a UI hint (e.g. disable/tag the option when `/api/health` reports `neo4j` unhealthy).
- **`expand_node`** (`/network/expand/{node_id}`) is Neo4j-only with no Postgres fallback at all (raises `HTTPException` — once §1.1 is fixed, that's the correct behavior) — confirm this is acceptable product behavior (i.e., "expand" simply unavailable when Neo4j is down) rather than expected to degrade gracefully like the main graph does.

---

## 6A. ADDENDUM — Criminal Network Filters Re-Audit: District & Crime Type (traced end-to-end, both data paths)

You asked me to re-check specifically whether the **District** and **Crime Type** filters on the Criminal Network page actually work. I traced every hop: `CriminalNetwork.tsx` → `networkService.getGraphData()` → `GET /api/network/graph-data` → `network_router.py` → `network_service.get_network_graph_data()` → **both** `get_network_graph()` (Neo4j) and `build_network_from_postgres()` (fallback). Verdict below.

### 6A.1 ✅ District filter — works correctly on both paths
- Frontend sends `district_id` as the raw `district_id` code (e.g. `KA-01`) from `useDistricts()`.
- `resolve_district_id()` short-circuits and passes it straight through when it already starts with `"KA-"`, so no transformation/mismatch happens.
- **Postgres fallback** (`build_network_from_postgres`) filters every entity type (`Offender.district_id`, `Victim.district_id`, `Location.district_id`) directly against the resolved value — correct.
- **Neo4j path** (`get_network_graph`) filters the root node with `n.district_id = $district_id` and additionally restricts expanded neighbors with `connected.district_id = $district_id` — correct, and every node type (`Criminal`, `Victim`, `Location`) is synced with a matching `district_id` property (`sync_offender_to_neo4j`, `sync_victim_to_neo4j`, `sync_location_to_neo4j` all set it from the same Postgres column). **No bug found here.**

### 6A.2 🔴 Crime Type filter — confirmed broken for Location nodes on the Neo4j path
**Root cause, file `app/core/neo4j_connection.py`, `get_network_graph()`:**
```python
if crime_type:
    where_clauses.append("$crime_type IN n.crime_types")
```
This is applied to **every** root node type (`Criminal`, `Victim`, `Location`, `Organization`) via the shared `where_clauses` list. But `n.crime_types` is only ever set for `Criminal` and `Victim` nodes:
```python
# sync_location_to_neo4j() — no crime_types property is ever written:
async def sync_location_to_neo4j(location_data: Dict[str, Any]):
    query = """
    MERGE (l:Location {location_id: $location_id})
    SET l.name = $name,
        l.location_type = $location_type,
        l.risk_score = $risk_score,
        l.is_hotspot = $is_hotspot,
        l.district_id = $district_id
    RETURN l
    """
```
In Cypher, `$crime_type IN n.crime_types` evaluates to `NULL` (not `false`, but still excluded by `WHERE`) when `n.crime_types` doesn't exist. **Result: whenever a Crime Type filter is active — for `node_type = "All"` or explicitly `"location"` — every Location node is silently dropped from the graph, with no error and no empty-state explanation.** Select Node Type = "Locations" + any Crime Type on the Criminal Network page today and you will always get zero nodes.

**✅ Fix (query-level, no data migration needed):**
```python
# app/core/neo4j_connection.py — get_network_graph()
if crime_type:
    where_clauses.append(
        "("
        "  $crime_type IN coalesce(n.crime_types, [])"                              # Criminal / Victim: own property
        "  OR EXISTS { MATCH (n)-[rel]-() WHERE $crime_type IN coalesce(rel.crime_types, []) }"  # Location / Organization: via any edge
        ")"
    )
```
This keeps the existing behavior for `Criminal`/`Victim` nodes (checked via their own `crime_types` array) and additionally lets `Location`/`Organization` nodes match if **any** relationship touching them carries that crime type (relationships already carry `crime_types` — see `create_criminal_relationship()` / `create_victim_offender_relationship()`). `EXISTS { ... }` subquery syntax is supported by Neo4j 5.x, which matches the `neo4j:5.18-community` image already pinned in `docker-compose.yml`, so no version upgrade is needed.

### 6A.3 🔴 Deeper structural bug found: Location nodes are *permanently isolated* in the real (Neo4j) graph — independent of any filter
While tracing the crime-type bug above I found the actual reason Location nodes rarely show up connected to anything even *without* a crime-type filter: **no code anywhere creates a relationship between a `Location` node and a `Criminal`/`Victim` node in Neo4j.**
```bash
$ grep -rn "FREQUENTED\|create_location" app/core/neo4j_connection.py app/services/*.py scripts/*.py
app/services/network_service.py:387:    "relationship_type": "FREQUENTED",   # <-- only exists in the Postgres FALLBACK path
```
Compare the two paths:
- **Postgres fallback** (`build_network_from_postgres`, used automatically whenever Neo4j is offline) *does* correctly build `FREQUENTED` edges between offenders and the locations where their crimes occurred.
- **Neo4j path** (the "real"/primary graph engine, and the one `scripts/sync_postgres_to_neo4j.py` populates) only ever calls `sync_location_to_neo4j()` to create the bare node — there is no `create_location_relationship()` function in `neo4j_connection.py` at all, and the sync script never calls anything to link a location to the crimes/offenders/victims associated with it.

**Impact:** in a fully-working deployment (Neo4j up, data synced), every Location node on the Criminal Network graph renders as a disconnected island — it can only be seen via `Show Isolated`, it can never be reached by "Expand node" from a Criminal/Victim, and it never appears in `key_players`/community/cluster analysis. This is worse than the crime-type filter bug because Locations are broken *by default*, filter or not — the crime-type bug (§6A.2) simply makes an already-mostly-broken feature return zero instead of a handful of isolated dots.

**✅ Fix — add a location-linking function and wire it into the sync pipeline:**
```python
# app/core/neo4j_connection.py — add this new function near create_victim_offender_relationship()

async def create_location_relationship(
    offender_id: str,
    location_id: str,
    relationship_type: str = "FREQUENTED",
    crime_ids: List[str] = None,
    crime_types: List[str] = None,
):
    """Link a criminal to a location where one of their crimes occurred."""
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"Invalid relationship_type: {relationship_type}")
    query = f"""
    MATCH (c:Criminal {{offender_id: $offender_id}})
    MATCH (l:Location {{location_id: $location_id}})
    MERGE (c)-[r:{relationship_type}]->(l)
    SET r.crime_ids = $crime_ids,
        r.crime_types = $crime_types,
        r.strength_score = 55,
        r.confidence_level = 'SUSPECTED'
    """
    await run_neo4j_query(query, {
        "offender_id": offender_id,
        "location_id": location_id,
        "crime_ids": crime_ids or [],
        "crime_types": crime_types or [],
    })
```
```python
# scripts/sync_postgres_to_neo4j.py — after the existing "Sync Locations" block, add:

print("Creating criminal-location relationships...")
from app.core.neo4j_connection import create_location_relationship

# Map each crime to its location (if any) so we can link offenders -> locations
crime_to_location = {str(c.crime_id): str(c.location_id) for c in crimes if c.location_id}

loc_rel_count = 0
for cid, loc_id in crime_to_location.items():
    crime = crime_map.get(cid)
    if not crime or cid not in crime_to_offenders:
        continue
    for oid in crime_to_offenders[cid]:
        await create_location_relationship(
            offender_id=oid,
            location_id=loc_id,
            crime_ids=[cid],
            crime_types=[crime.crime_type],
        )
        loc_rel_count += 1
print(f"Created {loc_rel_count} criminal-location relationships.")
```
After deploying this, re-run the sync once (`docker compose exec backend python scripts/sync_postgres_to_neo4j.py`) to backfill the missing edges on existing data.

### 6A.4 🟡 "Organizations" node-type filter is a dead option — no Organization nodes are ever created
```bash
$ grep -rn "Organization" scripts/sync_postgres_to_neo4j.py app/utils/data_seeder.py
# (no output — Organization nodes are never created anywhere in the codebase)
```
`Organization` is a full first-class option in the frontend's Node Type filter (`CriminalNetwork.tsx`) and in `NODE_TYPES` (`constants/crimeTypes.ts`), and it has its own uniqueness constraint (`CREATE CONSTRAINT ... FOR (o:Organization) ...`) and color mapping — but there is no `sync_organization_to_neo4j()`, no seeder logic, and no `Organization` model in Postgres at all. Selecting Node Type = "Orgs" will always return an empty graph.
**Fix direction:** either (a) implement an `Organization` entity end-to-end (Postgres model + seeder + Neo4j sync + relationship types — a real feature, not a quick patch), or (b) remove the "Organizations" option from the Node Type filter and the legend until it's implemented, so the UI doesn't advertise a capability that doesn't exist.

### 6A.5 Summary table

| Filter | Neo4j path | Postgres-fallback path |
|---|---|---|
| District | ✅ Correct | ✅ Correct |
| Crime Type — Criminal nodes | ✅ Correct | ✅ Correct |
| Crime Type — Victim nodes | ✅ Correct | ✅ Correct |
| Crime Type — Location nodes | 🔴 Always returns zero (§6A.2) | ✅ Correct |
| Crime Type — Organization nodes | 🔴 N/A — no data exists (§6A.4) | ⚪ Explicitly returns empty w/ warning message (handled gracefully) |
| Location connectivity (any filter) | 🔴 Always isolated, no edges ever created (§6A.3) | ✅ Correct (`FREQUENTED` edges built from crime co-occurrence) |

---

## 7. Database Connections Summary

| Store | Used for | Wiring status |
|---|---|---|
| **PostgreSQL** (`app/core/database.py`, SQLAlchemy async) | All CRUD: crimes, offenders, victims, alerts, reports, users, audit log, settings | ✅ Correctly wired; `init_db()` degrades gracefully (`_db_ready=False`) rather than crashing startup if Postgres is unreachable — good for resilience, but note many routers will 500 on any DB call in that state (no circuit breaker / friendly "DB unavailable" response). |
| **Redis** (`app/core/redis_connection.py`) | Response caching (`cache_get`/`cache_set`), token blacklist (logout) | ✅ Wired; password passed via `settings.REDIS_PASSWORD` (not the connection URL), which correctly matches the `docker-compose.yml` Redis container's `--requirepass`, so no auth mismatch — this is fine. Degrades gracefully if unavailable. See **§1.4** for a caching *key* bug (not a connection bug). |
| **Neo4j** (`app/core/neo4j_connection.py`) | Criminal Network graph | ✅ Connection handling itself is solid with graceful `{"status": "offline"}` fallback; see §1.1/§1.2/§6 for feature-level bugs once connected/disconnected. |
| **Gemini AI** (`app/core/gemini_client.py`, `app/services/gemini_service.py`) | AI summaries (network, offender MO, edge insight, hotspot deployment, assistant chat) | See §8 below. |

---

## 8. AI (Gemini) Integration

- **Round-robin key/model rotation** (`get_next_key_and_model()`) is a reasonable design for handling per-key rate limits across multiple Gemini API keys — no issues found in the rotation logic itself.
- **Model discovery** (`init_gemini_models()`) only ever queries `keys[0]` at startup to list available models; if `keys[0]` is invalid/rate-limited at boot but `keys[1..n]` are fine, `_available_models` stays empty and every subsequent call falls back to the single hardcoded `settings.GEMINI_MODEL` — not wrong, but means the discovery feature effectively only benefits from your *first* configured key's access level. Minor, worth a comment or fallback loop over all configured keys.
- **`/assistant/ask` (AI Chat Widget)**: correctly grounds the LLM in live `dashboard_service.get_dashboard_summary()` data and instructs it to only use supplied data — good prompt hygiene. `is_fallback` flag is returned but confirm `AIChatWidget.tsx` actually surfaces it to the user (worth checking — a "the AI could not reach live data" indicator matters for a police intelligence tool).
- **`get_network_ai_summary` (§1.2)** is the one place the AI layer is fed structurally broken input — everything downstream of that (summary text, key findings, suspicious pairs) is generated from an empty offender list, so the AI's own fallback text ("Identified 0 repeat offenders...") is what officers will actually see on the Criminal Network page today.

---

## 9. Code Quality — Static Analysis Findings (pyflakes, full backend)

Non-blocking but worth a cleanup pass; full output saved for reference. Highlights beyond the confirmed bug in §1.1:

```
app/services/anomaly_service.py:162:28: f-string is missing placeholders
app/services/alert_service.py:250:9: local variable 'daily_average' is assigned to but never used
app/services/network_service.py:364/427/430/534/537: redefinition of unused 'uuid'/'run_neo4j_query' (repeated local re-imports shadow the module-level ones — harmless but sloppy)
app/ml_models/anomaly_detection.py:228,234,239,245,250: f-strings missing placeholders (likely intended to interpolate a variable — check these messages actually contain the values they claim to report)
app/ml_models/modus_operandi_analyzer.py:379:27: f-string is missing placeholders
main.py:205: redefinition of unused 'os' (imported twice)
```
Plus ~30 unused imports across `services/`, `routers/`, `models/` (listed in the raw pyflakes log) — safe to strip in a lint pass; none change behavior, but several (`import_router.py: get_current_user unused`, `reports_router.py: scope_district_param unused`) are worth a second look to confirm the intended authorization check wasn't accidentally dropped when refactored to use `require_role`/other guards (in both cases checked here, the auth is in fact still enforced via a different dependency — see §2 for the ones that genuinely aren't).

---

## 10. Production-Readiness Checklist

- [ ] Fix **§1.1** `status` import in `network_router.py` (blocks a core Criminal Network action).
- [ ] Fix **§1.2** `properties` → `profile_data` key in `network_service.py`, and add `known_associates` to node `profile_data` on both sync paths (Criminal Network's AI summary is non-functional today).
- [ ] Fix **§6A.2** Neo4j crime-type filter excluding all Location/Organization nodes (`EXISTS {}` query patch).
- [ ] Fix **§6A.3** Location nodes never get relationships in Neo4j — add `create_location_relationship()` and wire it into `scripts/sync_postgres_to_neo4j.py`, then re-run the sync to backfill.
- [ ] Decide on **§6A.4** — implement Organization entities end-to-end or remove the dead "Orgs" filter option from the UI.
- [ ] Wire `crime_type`/`date_from`/`date_to` into `/hotspots/clusters` (**§1.3**) and fix its cache key (**§1.4**).
- [ ] Wire `district_id`/date range into Predictive Analytics endpoints or remove the dead filter UI (**§1.5**).
- [ ] Server-side filter `/alerts/active` by severity/type, or fully client-paginate (**§1.6**).
- [ ] Add district-scoping to Evidence list/download endpoints (**§2.1** — treat as a priority given this is case evidence).
- [ ] Strip `auth_token` from `/auth/verify-token` response body (**§2.2**).
- [ ] Add a Pydantic request model + duplicate-username handling to `POST /settings/users/add` (**§2.4**).
- [ ] Fix README's `docker compose up` working directory (**§3.1**) and unify `.env.example` files (**§3.2**).
- [ ] Decide on one consistent demo-mode fallback strategy instead of per-service copy/paste (**§4**).
- [ ] Add date-range inputs to Reports page to use the backend capability that already exists (page 13 note).
- [ ] Run a full `pyflakes`/`ruff` pass to clear ~30 unused imports and 6 malformed f-strings (**§9**).
- [ ] Load-test `/crimes/map-data` at the documented `limit=20000` cap and the CSV export path specifically — both bypass Redis caching under some conditions and run synchronous CSV writing in the request path.

---

*End of report. All line/file references reflect the uploaded `SHASTRA-main.zip` snapshot; re-verify line numbers if the codebase has changed since this audit.*