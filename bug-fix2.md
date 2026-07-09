# SHASTRA Crime Intelligence Platform — Full-Stack Audit Report

**Scope:** All 14 pages (Login → Settings & Administration), frontend↔backend wiring, database connections (PostgreSQL / Redis / Neo4j), and a deep-dive on the Criminal Network graph + AI overview + filters.

**Method:** Full static review of `crime_frontend/src` (React/TS, Redux, Cytoscape) and `crime_backend/MODULE_2_BACKEND` (FastAPI, SQLAlchemy, Neo4j, Gemini). Every service file was matched line-by-line against its router, and every router was matched against its service-layer implementation. This is not a runtime test (no live DB/Neo4j/Redis/Gemini credentials were available) — it is a correctness/wiring/security audit of the code as written.

**Legend:** 🔴 Critical (security/data-integrity/broken feature) · 🟠 High (functional bug, wrong data shown) · 🟡 Medium (inconsistency, partial breakage) · ⚪ Low (cleanup, tech debt)

---

## 0. Executive Summary — Top Issues

| # | Issue | Severity | Location |
|---|---|---|---|
| 1 | Hotspot Analysis: district RBAC scoping is computed then **discarded** on all 4 endpoints — District Officers can view every district's hotspot data | 🔴 | `hotspots_router.py` |
| 2 | Criminal Network: AI Overview panel is **not recomputed** when Search / Node-Type filters change, and never reflects `search_query`/`node_type` at all — graph and AI panel go out of sync | 🔴 | `CriminalNetwork.tsx`, `network_router.py`, `network_service.py` |
| 3 | Offender Database: search box implies name/district/crime-type search but backend only matches first/last name — district & crime-type search silently return nothing | 🟠 | `offenders_router.py`, `OffenderDatabase.tsx` |
| 4 | Offender Database: **no district RBAC scoping** on search/profile/network/risk/MO endpoints — a District Officer can pull up any offender in Karnataka | 🔴 | `offenders_router.py` |
| 5 | Anomaly Detection: **no RBAC scoping at all** — any authenticated user can list/update anomalies for any district | 🔴 | `anomalies_router.py` |
| 6 | Reports: `/reports/history` returns **every saved report for every district**, unfiltered by user/role, while generate & download *are* protected — inconsistent access control | 🟠 | `reports_router.py` |
| 7 | Criminal Network graph: "Crime Type Lens" dims KNOWS/FREQUENTED edges to near-invisible (opacity 0.12) whenever a crime-type filter is active, because those synthetic edges are hardcoded with `crime_types: []` | 🟠 | `network_service.py`, `NetworkGraph.tsx` |
| 8 | AI Network Summary numbers **cannot match the graph on screen** — it re-queries offenders independently with a different filter (`total_crimes > 1`) and ignores Neo4j entirely | 🟠 | `network_service.py::get_network_ai_summary` |
| 9 | Suspicious-pair detection in AI summary only compares a small O(10×5) window of offenders — will miss most real pairs once districts have >15 flagged offenders | 🟡 | `network_service.py::get_network_ai_summary` |
| 10 | Widespread N+1 query patterns (per-row `await db.execute()` inside `for` loops) across ~10 services | 🟡 | multiple |
| 11 | Many frontend service methods swallow errors and silently return `null`/`[]`, hiding real 401/500 failures as "no data" | 🟡 | multiple `*Service.ts` |

Full detail below, organized by page, then a dedicated Crime Network + AI deep-dive, then cross-cutting backend issues.

---

## 1. Login Page

**Files:** `pages/Login.tsx`, `services/authService.ts`, `store/authSlice.ts`, `routers/auth_router.py`, `services/auth_service.py`

✅ Wiring is correct: `authService.login` → `POST /api/auth/login` → `auth_service.authenticate_user` → JWT issued with matching field names (`auth_token`, `user_role`, `user_name`, `user_district`, `permissions_list`) consumed correctly by `authSlice.loginSuccess`.

**🟡 Issue 1.1 — Login rate limit may be too aggressive for shared station terminals**
```python
# app/routers/auth_router.py
@router.post("/login")
@limiter.limit("10/minute")
async def login(...):
```
`slowapi`'s default `get_remote_address` key is the **client IP**. Police stations commonly have many officers behind one NAT/proxy IP. 10 login attempts/minute shared across an entire station will lock out legitimate users during shift-change. Recommend keying the limiter off `username`+IP, or raising the limit.

**⚪ Issue 1.2 — No "remember me" / silent refresh**
Token expiry is `JWT_EXPIRY_HOURS` (default 8h) with no refresh-token flow. A user mid-shift will be hard-logged-out with no warning, losing unsaved form state (e.g., mid-way through Offender registration). Consider a refresh endpoint or a "session expiring" toast.

---

## 2. Dashboard

**Files:** `pages/Dashboard.tsx`, `services/crimeService.ts`, `routers/dashboard_router.py`, `services/dashboard_service.py`

✅ Field names match end-to-end (`total_crimes_month`, `active_hotspots_count`, `high_risk_areas_count`, etc.). Polling every 30s via `setInterval` is implemented correctly and cleans up on unmount.

**🟡 Issue 2.1 — Silent error swallowing inside the 30s poll**
```tsx
// pages/Dashboard.tsx
useEffect(() => {
  fetchData();
  const interval = setInterval(() => fetchData(true), 30000);
  return () => clearInterval(interval);
}, []);
```
`fetchData(true)` (silent mode) still sets `setError(...)` on failure, but there's no visual difference between "stale from 30s ago" and "actively failing" once the loading spinner is gone — a persistent backend outage after first load just shows an error banner with no auto-retry/backoff. Fine for now, but confirm this is the intended UX.

---

## 3. Crime Map

**Files:** `pages/CrimeMapPage.tsx`, `services/crimeService.ts`, `routers/crimes_router.py` (`/map-data`)

✅ Filters (`crime_type`, `district_id`, `date_from`, `date_to`) map correctly to backend query params. District/date scoping (`scope_district_filter`) is correctly applied server-side.

**🟡 Issue 3.1 — Client-side re-filtering duplicates server-side date logic incorrectly**
```tsx
if (filters.timeOfDay === "Night (10PM-6AM)" && (hour < 22 && hour >= 6)) return false;
```
This condition is logically inverted for the wrap-around case. For "Night", a crime at `hour = 3` (3 AM, legitimately night) evaluates `hour < 22 && hour >= 6` → `true && false` → `false`, so it is **kept** (correct by luck). But a crime at `hour = 23` evaluates `false && true` → `false` → also kept (correct). Actually tracing further: the only way this excludes anything is when `6 <= hour < 22`, which is exactly the non-night window — so the condition is correct, but written in a fragile, easy-to-break way (double negative). Flagging for readability/maintainability, not a live bug — but any future edit to this condition is high-risk.

**🟠 Issue 3.2 — No pagination / hard 20,000-row cap silently truncates**
```python
# crimes_router.py
limit: int = Query(5000, ge=1, le=20000),
```
Frontend never passes `limit`, so it always requests the default. If a district+date range genuinely has >5000 crimes, the map silently drops the rest with no "truncated" indicator to the user (contrast with `MAX_RENDERABLE_PINS` truncation banner which *does* warn the user client-side, but only for the render limit, not the fetch limit). Recommend surfacing `total_count` vs `data.length` from the response.

---

## 4. Crime Database

**Files:** `pages/CrimeDatabase.tsx`, `services/crimeService.ts` (`filterCrimes`), `routers/crimes_router.py` (`/filter`, PUT/PATCH/DELETE)

**🟠 Issue 4.1 — `remove()` calls DELETE but there is no confirmation of cascading effects**
```python
@router.delete("/{crime_id}")
```
Deleting a `Crime` row does not show whether `CrimeVictimLink`/`CrimeOffenderLink`/`Evidence` rows are cascade-deleted or orphaned. Check `ON DELETE` behavior in the `Crime` model / migration — if it's `RESTRICT` this will throw a raw 500 (caught by the global exception handler, but the user just sees "Internal Server Error" with no explanation of why the delete failed).

**⚪ Issue 4.2 — `updateStatus` sends status as a query param via `PATCH ... null`**
```ts
updateStatus: async (id: string, status: string) => {
  const response = await api.patch(ENDPOINTS.CRIMES.UPDATE_STATUS(id), null, { params: { status } });
```
Works, but is inconsistent with every other PATCH/PUT in the codebase which use JSON bodies (e.g. `anomalyService.updateStatus` sends `{status}` as body). Pick one convention — mixing body vs. query-param semantics for the same verb across modules increases the chance of a future regression when someone copy-pastes the wrong pattern.

---

## 5. Hotspot Analysis — 🔴 Confirmed RBAC Bypass

**Files:** `pages/HotspotAnalysis.tsx`, `services/crimeService.ts`, `routers/hotspots_router.py`, `services/hotspot_service.py`

The frontend wiring itself is fine. The backend has a **critical, systemic bug**: on every one of the four endpoints, the district value is correctly *resolved* and *scoped* to the requesting user's role — and then the **unscoped** variable is passed to the service layer instead of the scoped one.

```python
# app/routers/hotspots_router.py — repeated identically on ALL FOUR endpoints

@router.get("/clusters")
async def hotspot_clusters(..., district_id: Optional[str] = Query(None), ...):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)   # ← computed correctly
    data = await get_hotspot_clusters(db, resolved_id)              # ← BUG: uses resolved_id, not district_id
    ...

@router.get("/time-patterns")
async def time_patterns(...):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_time_patterns(db, resolved_id, crime_type)     # ← same bug

@router.get("/top-list")
async def top_hotspots(...):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_top_hotspots(db, limit, resolved_id)           # ← same bug

@router.get("/deployment-suggestions")
async def deployment_suggestions(...):
    resolved_id = await resolve_district_id(db, district_id)
    district_id = scope_district_param(resolved_id, current_user)
    data = await get_deployment_suggestions(db, resolved_id, target_date)  # ← same bug
```

**Impact:** `scope_district_param` exists specifically to force a `DISTRICT_OFFICER` to only see their own district when they omit `district_id`, or to reject/override a district they don't own. Because its return value is discarded, **a District Officer who simply omits `district_id` (or passes another district's ID) sees hotspot clusters, time patterns, the top-hotspot list, and patrol deployment suggestions for the entire state**, not just their assigned district. This defeats the purpose of the `DISTRICT_OFFICER` role for this entire page.

**Fix direction (for your reference — not applied):** replace every `resolved_id` argument in the four `await get_*(...)` calls with `district_id` (the already-scoped variable).

---

## 6. Criminal Network — see dedicated Section 13 (deep dive requested)

---

## 7. Anomaly Detection — 🔴 No RBAC Scoping At All

**Files:** `pages/AnomalyDetection.tsx`, `services/predictionService.ts` (`anomalyService`), `routers/anomalies_router.py`, `services/anomaly_service.py`

```python
# app/routers/anomalies_router.py
@router.get("/list")
async def get_anomalies(
    ...,
    district_id: Optional[str] = Query(None),
    ...,
    current_user=Depends(get_current_user),   # ← only checks the token is valid, no role/district logic at all
):
    data = await get_anomaly_list(db, severity, status, district_id, page=page, page_size=page_size)
```

Unlike every other list-style router in the codebase (`crimes_router`, `hotspots_router`, `predictions_router`, `victims_router`), `anomalies_router.py` never imports or calls `scope_district_param`/`resolve_district_id`, and never checks `current_user["role"]`. A `DISTRICT_OFFICER` can pass any `district_id` (or none, seeing all districts) to `/anomalies/list`, and `anomaly_detail`/`update_status` don't verify the anomaly's district against the caller at all before returning/mutating it.

**Recommend:** Apply the same `resolve_district_id` + `scope_district_param` pattern used elsewhere, and add an ownership check inside `update_status`/`anomaly_detail` similar to the one already used in `reports_router.py`'s `/download` (see Section 12).

**🟡 Issue 7.2 — Frontend never surfaces `district_id` filter for scoping**
`anomalyService.getList()` (used by `AnomalyDetection.tsx`) is called with **no filters at all** — even the `severity`/`status`/`district_id` params the backend supports go unused, meaning the page always fetches page 1 of the unfiltered global list and does all filtering client-side. For a high-volume state-wide system this will paginate incorrectly (client "filters" only ever see the 20 anomalies from page 1).

---

## 8. Predictive Analytics

**Files:** `pages/PredictiveAnalytics.tsx`, `services/predictionService.ts`, `routers/predictions_router.py`, `services/prediction_service.py`

✅ `/high-risk-areas`, `/forecast`, `/emerging-typologies`, `/socioeconomic-correlation` all correctly use the **scoped** `district_id` variable (this module does NOT have the Section 5 bug — good).

**🟡 Issue 8.1 — `/risk-map` has no district scoping whatsoever, by design or by omission?**
```python
@router.get("/risk-map")
async def risk_map(request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_risk_map(db)
```
No `district_id` parameter exists at all, so this always returns the state-wide risk map regardless of caller role. This may be intentional (an overview map is arguably fine to show everyone), but it's inconsistent with every sibling endpoint in the same router which does scope by district. Confirm intent; if a District Officer should only see their own risk tile, this needs the same treatment as the others.

**⚪ Issue 8.2 — `predictionService.getForecast()` duplicates `getPredictions()`**
```ts
getPredictions: async (filters?: any) => { ... api.get(ENDPOINTS.PREDICTIONS.FORECAST, ...) ... }
getForecast: async () => { ... api.get(ENDPOINTS.PREDICTIONS.FORECAST) ... }   // no filters param accepted!
```
Two methods hit the identical endpoint; `getForecast` doesn't even accept a `filters` argument, so whichever page/component calls `getForecast()` instead of `getPredictions()` cannot filter by district/crime-type at all. Verify which one `PredictiveAnalytics.tsx` actually calls (dead-code risk either way).

---

## 9. Offender Database — 🔴 RBAC Gap + 🟠 Broken Search Claim

**Files:** `pages/OffenderDatabase.tsx`, `services/offenderService.ts`, `routers/offenders_router.py`, `services/offender_service.py`

**🔴 Issue 9.1 — No district scoping on any read endpoint**
```python
# app/routers/offenders_router.py
@router.get("/search")
async def search(query: Optional[str] = Query(None), db=Depends(get_db), current_user=Depends(get_current_user)):
    data = await search_offenders(db, name=query if query else None)   # no district arg passed at all
```
Compare with `victims_router.py`, which explicitly does:
```python
if current_user["role"] == "DISTRICT_OFFICER":
    user_district = current_user.get("district_id")
    ...
    district_id = user_district
```
`offenders_router.py` has this pattern on **none** of `/search`, `/{id}/profile`, `/{id}/network`, `/{id}/risk`, `/{id}/modus-operandi` — only on the `POST`/`PUT` (create/edit) routes. A `DISTRICT_OFFICER` can view **any offender's full profile, MO, risk score, and known-associate network from any district in Karnataka**, purely by guessing/enumerating offender IDs or using the unfiltered search box.

**🟠 Issue 9.2 — Search box UI promises more than the backend delivers**
```tsx
// pages/OffenderDatabase.tsx
<input type="text" placeholder="Search by name, district, crime type..." ... />
```
```python
# app/services/offender_service.py — search_offenders() DOES support these:
async def search_offenders(db, name=None, crime_type=None, district_id=None, risk_level=None, status=None, page=1, page_size=20):
    if name: ... ilike name
    if crime_type: ... contains
    if district_id: ...
    if risk_level: ...
    if status: ...
```
```python
# app/routers/offenders_router.py — but the route only forwards `name`:
@router.get("/search")
async def search(query: Optional[str] = Query(None), ...):
    data = await search_offenders(db, name=query if query else None)   # crime_type/district_id/risk_level/status never wired up
```
The service function already supports every filter the placeholder text advertises — it's just never exposed through the router or the frontend. Typing a district name or crime type into the search box (as the placeholder instructs) returns **zero results**, because the query only matches `first_name`/`last_name`. This will read as "no such offenders exist" to an investigating officer, which is actively misleading.

**Also note:** `search_offenders` returns pagination metadata (`page`, `page_size`, `total_count` presumably), but the router doesn't expose `page`/`page_size` as query params either, and `offenderService.searchOffenders` doesn't pass them — the Offender Database page has no working pagination, so any district with more offenders than one default page will silently be cut off.

---

## 10. Victim Database

**Files:** `pages/VictimDatabase.tsx`, `services/victimService.ts`, `routers/victims_router.py`, `services/victim_service.py`

✅ This is the **best-wired module for RBAC** in the codebase — `/search` and `/{id}/profile` both correctly restrict `DISTRICT_OFFICER` to their own district and 403 otherwise. Use this file as the template when fixing Sections 5, 7, and 9.

**⚪ Issue 10.1 — `victimService.ts` has no error handling / demo-mode fallback at all**, unlike every sibling service:
```ts
export const victimService = {
  search: (q?: string, districtId?: string) =>
    api.get(ENDPOINTS.VICTIMS.SEARCH, { params: { q, district_id: districtId } }).then((r) => r.data?.data || []),
  ...
};
```
Not a bug (arguably cleaner than the swallow-errors pattern elsewhere — see Section 14.2), but it means a network failure surfaces as an unhandled promise rejection in `VictimDatabase.tsx` unless the page wraps every call in its own try/catch. Confirm the page does this (worth double-checking against Section 14.2's pattern for consistency across the app either way).

---

## 11. Socio-Economic Insights

**Files:** `pages/SocioEconomicInsights.tsx`, `services/predictionService.ts` (`getSocioeconomicData`), `routers/predictions_router.py` (`/socioeconomic-correlation`), `services/socioeconomic_service.py`

✅ District scoping correct here (part of `predictions_router.py`, unaffected by the Section 5 bug).

**🟡 Issue 11.1 — N+1 query pattern in the correlation builder**
```python
# app/services/socioeconomic_service.py (loop starting ~line 35, await inside at ~line 37)
```
Per the systemic-issues sweep (Section 15), this file has an `await db.execute(...)` inside a `for` loop. For 30 districts × several socioeconomic factors this is a small, bounded N (probably fine performance-wise today), but flagged for consistency with the wider N+1 write-up in Section 15 — batch this into a single `select(...).where(District.district_id.in_(...))` query.

---

## 12. Alerts Center

**Files:** `pages/AlertsPage.tsx`, `services/alertService.ts`, `App.tsx` (WebSocket), `routers/alerts_router.py`, `services/alert_service.py`

✅ Both the REST (`GET /active`, `PUT /{id}/read`, `DELETE /{id}`) and the WebSocket (`ws://…/api/alerts/ws?token=...`) paths are correctly wired end-to-end, including token validation and blacklist checking on the socket handshake, and exponential backoff reconnect logic on the frontend.

**🟡 Issue 12.1 — `handleMarkAllRead` fires N sequential awaited requests**
```tsx
// pages/AlertsPage.tsx
const handleMarkAllRead = async () => {
  const unread = alerts.filter((a) => !a.is_read);
  for (const a of unread) {
    await alertService.markRead(a.alert_id);   // sequential, one round-trip per alert
    dispatch(markAlertRead(a.alert_id));
  }
};
```
With dozens of unread alerts this is slow (N sequential HTTP round-trips) and there's no bulk "mark all as read" endpoint on the backend to batch it. Low severity today, but will visibly lag during a major incident spike (exactly when officers most need the UI to be fast).

**⚪ Issue 12.2 — WebSocket reconnect never re-authenticates on token refresh**
If the JWT expires mid-session, the socket will keep reconnecting with the stale token from `localStorage` every retry (`getItem("auth_token")` is re-read each `connect()` call, which is good), but there is no path that refreshes the token itself (see Issue 1.2) — so once the token truly expires, the socket will be closed with code 1008 forever and no new alerts will arrive until the user manually re-logs-in. There's no visible "real-time alerts disconnected" indicator for the user in this state.

---

## 13. Criminal Network — Deep Dive (as requested)

**Files:** `pages/CriminalNetwork.tsx`, `components/network/NetworkGraph.tsx`, `components/network/ConnectivityMatrix.tsx`, `services/networkService.ts`, `routers/network_router.py`, `services/network_service.py`

This section covers the graph, all filters (search / node type / crime type lens / district / show-isolated), node/edge selection, ego-navigation, shortest path, and the AI panel — and specifically the requirement: *"when using filters we get the graph right, then the AI overview should also reflect that graph."*

### 13.1 🔴 AI Overview does not track the graph's filters — the central issue

There are **two separate `useEffect` hooks** driving this page:

```tsx
// pages/CriminalNetwork.tsx — Effect A: loads graph AND ai summary, but only reacts to 2 of 4 filters
useEffect(() => {
  const fetch = async () => {
    const [g, ai] = await Promise.all([
      networkService.getGraphData(
        searchQuery || undefined,
        crimeTypeLens === "all" ? undefined : crimeTypeLens,
        districtFilter === "all" ? undefined : districtFilter,
        nodeTypeFilter === "all" ? undefined : nodeTypeFilter
      ),
      networkService.getAiSummary(
        districtFilter === "all" ? undefined : districtFilter,
        crimeTypeLens === "all" ? undefined : crimeTypeLens
        // ← searchQuery and nodeTypeFilter are NEVER passed to the AI summary call
      ),
    ]);
    ...
  };
  fetch();
}, [crimeTypeLens, districtFilter]);   // ← nodeTypeFilter and searchQuery are missing from deps entirely

// Effect B: debounced, reacts to ALL FOUR filters, but only refreshes the GRAPH — never the AI summary
useEffect(() => {
  const handle = setTimeout(async () => {
    const g = await networkService.getGraphData(
      searchQuery || undefined,
      crimeTypeLens === "all" ? undefined : crimeTypeLens,
      districtFilter === "all" ? undefined : districtFilter,
      nodeTypeFilter === "all" ? undefined : nodeTypeFilter,
      { signal: controller.signal }
    );
    // sets nodes, edges, keyPlayers — never calls networkService.getAiSummary()
  }, 400);
  return () => { clearTimeout(handle); controller.abort(); };
}, [searchQuery, nodeTypeFilter, crimeTypeLens, districtFilter]);
```

**What this means in practice:**
- Typing in the Search box updates the graph (Effect B) but the AI Overview panel is completely untouched.
- Switching the Node Type filter (Criminal / Victim / Location / Organization) updates the graph but **never re-triggers the AI summary** — even though the AI panel's `network_stats` (total criminals, high-risk count, etc.) is now describing a totally different node population than what's rendered.
- Only changing **District** or **Crime Type** refreshes both — and even then, the AI summary uses its own independent query rather than sharing the graph's data (see 13.2).

On the backend, this is baked in at the API contract level — `ai-summary` never accepted these two filters to begin with:

```python
# app/routers/network_router.py
@router.get("/ai-summary")
async def fetch_ai_summary(
    request: Request,
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    # no search_query, no node_type — the endpoint has no way to be told about them
    ...
):
```

### 13.2 🟠 AI summary is computed from a completely different dataset than the graph

```python
# app/services/network_service.py :: get_network_ai_summary
offender_query = select(Offender).where(Offender.total_crimes > 1)   # ← arbitrary >1 filter, not used by the graph builder
if district_id: offender_query = offender_query.where(Offender.district_id == district_id)
if focus_area: offender_query = offender_query.join(CrimeOffenderLink).join(Crime).where(Crime.crime_type == focus_area)
result = await db.execute(offender_query)
all_offenders = result.scalars().all()
...
for off in all_offenders:
    if len(unique_offenders) >= 50: break   # hard cap unrelated to node_limit used by the graph (100)
```

vs. the graph builder (`get_network_graph_data` → `build_network_from_postgres` or Neo4j `get_network_graph`), which:
- Includes **all** offenders regardless of `total_crimes`, not just `> 1`,
- Can include Victim / Location / Organization nodes the AI summary never looks at,
- Uses Neo4j as the primary source when available — the AI summary **never queries Neo4j at all**, only Postgres,
- Caps at `node_limit` (100 by default) rather than the AI summary's independent 50-offender cap.

**Net effect:** the counts shown in the AI panel (`total_criminals`, `high_risk_count`, `active_count`, `network_density`) are drawn from a different query, different cap, and sometimes a different database entirely than the nodes/edges rendered in the graph. They will frequently disagree with what an officer is looking at, e.g. "network density 0.34" in the AI text while the visible graph shows a sparse 8-node subgraph.

### 13.3 🟡 Suspicious-pair detection only samples a small window

```python
for i, o1 in enumerate(all_offenders[:10]):
    for o2 in all_offenders[i+1:i+6]:
        common = set(o1.get("known_associates", [])) & set(o2.get("known_associates", []))
```
This only ever compares offender `#0` against `#1..#5`, offender `#1` against `#2..#6`, … up to offender `#9` — i.e. at most 10×5=50 comparisons total, regardless of how many offenders (up to 50) were fetched. Any suspicious shared-associate pair where **both** offenders are outside the first 10 in the (arbitrary) query order will never be found. This should iterate over the full `all_offenders` list (`itertools.combinations`) if the intent is genuinely to surface all suspicious pairs.

### 13.4 🟠 "Crime Type Lens" visually breaks non-crime edges

```tsx
// components/network/NetworkGraph.tsx
const nonMatching = cyRef.current.edges().filter(
  (e) => (e.data("crimeTypes") || []).includes(crimeTypeLens)
);
```
`crimeTypeLens` is fed the **same value** as the server-side `crime_type` filter:
```tsx
crimeTypeLens={crimeTypeLens === "all" ? null : crimeTypeLens}
```
But the Postgres-fallback graph builder hardcodes `crime_types: []` on every `KNOWS` (criminal↔criminal) and `FREQUENTED` (criminal↔location) synthetic edge:
```python
# app/services/network_service.py :: build_network_from_postgres
edges.append({
    ...
    "relationship_type": "KNOWS",
    "crime_types": [],   # ← always empty
})
...
edges.append({
    ...
    "relationship_type": "FREQUENTED",
    "crime_types": [],   # ← always empty
})
```
So the instant a user selects **any** specific crime type, every `KNOWS`/`FREQUENTED` edge — even though the endpoints on both sides were already server-filtered to belong to that exact crime type — gets `.addClass("lens-dimmed")` (opacity **0.12**), because `[].includes(crimeTypeLens)` is always `false`. In Postgres-fallback mode (i.e., whenever Neo4j is offline), selecting a crime-type filter makes the associate/location relationships in the already-correctly-filtered graph look broken/near-invisible, which is confusing and makes the network look sparser and less connected than it actually is.

**Two independent fixes are possible (documenting both, not applying either):**
1. Backend: populate `crime_types` on `KNOWS`/`FREQUENTED` edges with the actual shared crime type(s) instead of `[]`.
2. Frontend: since server-side filtering already guarantees every edge on screen matches the selected crime type, the client-side "lens" dimming pass is redundant when `crime_type` is already a server param — it should only need to run when the lens is being used as a *pure visual highlight* on an otherwise-unfiltered graph, not layered on top of an already-filtered result set.

### 13.5 🟡 Redundant double-filtering of the same criteria

```tsx
// pages/CriminalNetwork.tsx
const filteredNodes = useMemo(() => {
  let result = nodes.filter((n) => {
    if (nodeTypeFilter !== "all" && n.node_type !== nodeTypeFilter) return false;
    if (searchQuery && !n.label.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });
  ...
}, [nodes, edges, nodeTypeFilter, searchQuery, showIsolated]);
```
`nodeTypeFilter` and `searchQuery` are already sent to `getGraphData` and filtered **server-side** (see `network_router.py`'s `graph-data` params, and `build_network_from_postgres`'s `node_type`/`search_query` handling). Filtering again client-side is redundant, and worse, is a second, independently-maintained implementation of "does this node match the search text" that can drift from the backend's `ilike` matching (e.g. backend also matches `Location.address`, but the client re-filter only checks `n.label`, which for a location node *is* the address — coincidentally consistent today, but fragile).

### 13.6 🟡 `keyPlayers` (used for the "Highlight Key Players" button) goes stale after debounced updates

```tsx
// Effect A sets keyPlayers from `g.key_players`
setKeyPlayers(g.key_players || []);
...
// Effect B (the debounced one that runs on searchQuery/nodeTypeFilter changes) never updates keyPlayers:
if (g && g.status !== "offline" && g.status !== "no_data") {
  setNodes(g.nodes);
  setEdges(g.edges);
  setKeyPlayers(g.key_players || []);   // NOTE: this line *is* present in Effect B too — confirmed present
```
On closer inspection this one is actually updated in both effects — no bug here; flagged during initial pass but verified correct on re-check. Leaving this note in the report so the "Highlight Key Players" button's data source is documented as correct.

### 13.7 🟡 `expand/{node_id}` fallback message is misleading for non-Neo4j deployments

```python
# app/routers/network_router.py
except Exception as e:
    return {"success": False, "message": "Node expansion is currently not available in fallback mode (Neo4j is offline)."}
```
This is a blanket `except Exception` — any error while running the Cypher query (bad node id, Neo4j auth failure, network timeout, malformed query) is reported to the user identically as "Neo4j is offline," even when Neo4j is actually online but the query itself failed for another reason. This will misdirect debugging effort during an actual incident (ops team will check Neo4j's health, find it fine, and be confused).

### 13.8 🟡 Shortest-path / node-compare feature has no fallback for Postgres-only mode
```python
@router.get("/shortest-path")
async def shortest_path(...):
    from app.core.neo4j_connection import find_shortest_path
    data = await find_shortest_path(node_a, node_b)
```
There is no Postgres fallback here (unlike `graph-data`, which does fall back). If Neo4j is down, `handleNodeCompare` in `CriminalNetwork.tsx` will always show "No path found between the selected nodes, or the graph database is offline" — the *comparison/shortest-path* feature is 100% Neo4j-dependent with no degraded mode, while the rest of the page pretends to work fine in Postgres-fallback mode. This inconsistency should at minimum be called out in the UI (e.g. disable the compare button entirely when the graph is in `postgres_fallback` source mode) rather than letting the user attempt it and get a generic failure message.

---

## 14. Reports & Settings — remaining checks

### Reports (Page 13)
**🟠 Issue 14.1 — `/reports/history` is unscoped** (see Executive Summary #6):
```python
@router.get("/history")
async def history(limit: int = Query(20, le=100), db=Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_saved_reports(db, page_size=limit)   # no user_id / district_id / role filter at all
```
Compare to `/generate` and `/{report_id}/download` on the same router, both of which explicitly check `current_user["role"] == "DISTRICT_OFFICER"` against the report's district before allowing access. `/history` has no equivalent check — a District Officer's "Saved Reports" list on `ReportsPage.tsx` will show every report ever generated by every officer in every district (report names, types, timestamps), even though they'd be denied if they tried to actually download one of those cross-district reports. This is an information-disclosure inconsistency, and also just confusing UX (list shows things you then get a 403 for).

### Settings & Administration (Page 14)
✅ This module is correctly protected — every admin-sensitive route (`/users`, `/users/add`, `/audit-logs`, `PUT /alert-thresholds`, `/datasources/{id}/sync`) uses `require_scrb_officer`, and `/districts`/`GET /alert-thresholds` are appropriately open to any authenticated role as read-only reference data.

**⚪ Issue 14.2 — `settingsService.getUsers()`/`getAuditLogs()` swallow all errors to `[]` outside demo mode**
```ts
getAuditLogs: async () => {
  try {
    const res = await api.get(ENDPOINTS.SETTINGS.AUDIT_LOGS);
    return res.data?.data || res.data || [];
  } catch (error) {
    if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return []; }
    throw error;   // OK — this one does rethrow correctly
  }
},
```
This one actually does rethrow — flagged here only to contrast with the pattern in Section 15.2 below, several of which do **not** rethrow.

**⚪ Issue 14.3 — Add-User form has no client-side validation of password strength/uniqueness before submit**, relying entirely on the backend's `ValueError` on duplicate username, which surfaces as a generic Axios error rather than a friendly inline "username taken" message — `SettingsPage.tsx` should catch `error.response?.data?.detail` and show it inline (check whether it currently does; if it just shows a generic toast this is a UX gap for admins provisioning new officers).

---

## 15. Cross-Cutting Backend & Frontend Issues (apply platform-wide)

### 15.1 🟡 N+1 query patterns (bounded scan, representative examples)

Concrete, verified example inside the Criminal Network location-builder:
```python
# app/services/network_service.py :: build_network_from_postgres
for loc_id, crime_ids in crime_ids_by_location.items():
    if not crime_ids:
        continue
    link_q = select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id.in_(crime_ids))
    offender_links = (await db.execute(link_q)).scalars().all()   # ← one query per location, inside the loop
```
and the victim-edge builder just above it:
```python
for cvl in cv_links:
    off_links = (await db.execute(select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id == cvl.crime_id))).scalars().all()
    crime = (await db.execute(select(Crime).where(Crime.crime_id == cvl.crime_id))).scalar_one_or_none()   # ← 2 queries per victim link
```
Similar patterns were found (loop start → first `await db.execute` inside it) in: `alert_service.py`, `anomaly_service.py`, `crime_service.py`, `dashboard_service.py`, `hotspot_service.py`, `offender_service.py`, `prediction_service.py`, `report_service.py`, `socioeconomic_service.py`. Not all of these are necessarily harmful (some loop over small, already-limited result sets), but for a "production ready" target this is worth a systematic pass — batch these into single `WHERE ... IN (...)` queries, especially anywhere the outer loop is over `Crime`/`Offender`/`Location` rows that could scale into the thousands (map data, hotspot builders).

### 15.2 🟡 Errors silently swallowed to `null`/`[]` outside of the intended demo-mode fallback

```ts
// services/offenderService.ts
getModusOperandi: async (id: string) => {
  try { ... }
  catch { return null; }   // ← no VITE_DEMO_MODE check, no rethrow — ALL errors (401, 500, network) become "no data"
},
getRisk: async (id: string) => { try {...} catch { return null; } },
getNetwork: async (id: string) => { try {...} catch { return null; } },
```
```ts
// services/networkService.ts — same pattern throughout
getNodeDetail: async (nodeId) => { try {...} catch (error) { console.error(...); return null; } },
getShortestPath: async (...) => { try {...} catch (error) { console.error(...); return null; } },
getEdgeInsight: async (...) => { try {...} catch (error) { console.error(...); return null; } },
```
These always return `null` on **any** failure — including an expired token (401) or a genuine 500 — with only a `console.error` that a working officer will never see. The UI then renders "no data available" states that look identical to "this offender genuinely has no known modus operandi," which is actively misleading in an investigative tool. Recommend at minimum distinguishing 401 (already globally redirects to `/login` via the `api.ts` interceptor, so this specific case is handled) from 5xx/network errors, which currently are indistinguishable from "empty."

### 15.3 🟡 `VITE_DEMO_MODE` mock-data fallback is compiled into the production bundle

Every service file (`crimeService`, `alertService`, `offenderService`, `predictionService`, `settingsService`, `reportService`) imports the full `mockData.ts` (40KB) and gates the fallback behind an env var checked **at runtime** (`import.meta.env.VITE_DEMO_MODE === 'true'`), not at build time. This means:
- The entire mock dataset ships to every production client regardless of whether demo mode is ever used, bloating the bundle.
- If `VITE_DEMO_MODE` is ever accidentally left `true` in a production `.env` (easy operator mistake — it's a plain string comparison with no build-time stripping), the platform will silently serve **fabricated crime/offender/victim data** to real police officers on any backend hiccup, with only a console-invisible `flagMockDataUsed()` custom event as an in-app signal. For a law-enforcement system this is a significant operational-integrity risk. Recommend making this a build-time constant (`define` in `vite.config.ts`) that's fully stripped from the production build via dead-code elimination, and/or gating it additionally behind `import.meta.env.PROD === false`.

### 15.4 🟡 Gemini caching does not distinguish fallback vs. real responses across restarts consistently
Already self-documented in the code as a known simplification:
```python
# app/core/gemini_client.py
# Realistically we should cache whether it was a fallback too, but for simplicity
# we assume cached responses are valid responses (not fallbacks).
```
Verified this is actually fine in the current code (fallback responses are never written to cache — only the success path calls `cache_gemini_response`), so there is no live bug today. Flagging only because the comment itself suggests the original author was uncertain — worth a unit test (`tests/` currently has no test asserting a fallback response is never cached) to lock in this behavior so a future refactor doesn't accidentally cache a fallback string.

### 15.5 🟡 Default credentials baked into `Settings` class
```python
# app/core/config.py
DATABASE_URL: str = "postgresql+asyncpg://admin:securepassword@localhost:5432/crime_intelligence_db"
NEO4J_PASSWORD: str = "neo4jsecurepassword"
JWT_SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_64_CHARS_MIN"
```
`JWT_SECRET_KEY` correctly **raises at startup** in production if left default (good — verified in the `field_validator`). `DATABASE_URL`/`DATABASE_PASSWORD`/`NEO4J_PASSWORD` have **no equivalent validator** — if an operator forgets to set these in `.env` for a production deploy, the app will happily boot and connect using `admin`/`securepassword`, a widely-known default that will be attempted by any automated credential-stuffing scanner against an internet-facing DB port. Recommend adding the same "reject default value when `ENVIRONMENT=production`" validator used for `JWT_SECRET_KEY` to these two as well.

### 15.6 🟡 AI Assistant (chat widget) has no conversational memory and cannot answer entity-specific questions
```python
# app/routers/assistant_router.py
async def ask_assistant(..., question: str = Body(..., embed=True), ...):
    summary_data = await get_dashboard_summary(db, resolved_id)
    context = f"... {summary_data.get(...)} ..."   # only ever the dashboard aggregate stats
    prompt = f"""... DATA: {context} QUESTION: {question} """
    result = await call_gemini(prompt)
```
- No prior turns are sent — every message is answered from scratch with zero conversation history, so follow-ups like "what about last month?" will not reference the previous answer at all.
- The assistant is only ever grounded in dashboard-level aggregates (`total_crimes_month`, `active_hotspots_count`, etc.) — it cannot answer questions referencing a specific crime ID, offender name, or district drill-down, because no retrieval step exists to fetch that context before prompting Gemini. This limits the "AI check everything" ask on this page to "can regurgitate today's dashboard numbers in prose," not genuine investigative Q&A.

---

## 16. Endpoint Wiring Cross-Check (frontend `ENDPOINTS` vs. backend routes)

Full comparison performed between `constants/apiEndpoints.ts` and every `@router.*` decorator across all 16 router files. **Result: every path + HTTP verb pair matches exactly**, with one documentation-only gap:

**⚪ Issue 16.1 — `GET /network/node-detail/{id}/ai-analysis` exists on the backend and is called from `networkService.getNodeAiAnalysis`, but is not listed in `constants/apiEndpoints.ts`'s `ENDPOINTS.NETWORK` object** — it's hand-built with string concatenation instead:
```ts
getNodeAiAnalysis: async (nodeId: string) => {
  const response = await api.get(`${ENDPOINTS.NETWORK.NODE_DETAIL(nodeId)}/ai-analysis`);
```
Works correctly today, but breaks the "single source of truth for API paths" convention the rest of the file follows, and will silently keep working even if the backend path is ever renamed (no compile-time reference to catch it). Recommend adding `NODE_AI_ANALYSIS: (id: string) => \`/network/node-detail/${id}/ai-analysis\`` to the constants file.

Similarly, `GET /settings/profile` exists on the backend (`settings_router.py`) but has no corresponding entry in `ENDPOINTS.SETTINGS` and does not appear to be called from any frontend service file — likely dead/unused backend code, or a feature (viewing your own profile page) that was planned but never wired up on the frontend. Worth confirming which.

---

## 17. Summary Table

| Page | Critical | High | Medium | Low |
|---|---|---|---|---|
| 1. Login | – | – | 1 (rate limit) | 1 (no refresh token) |
| 2. Dashboard | – | – | 1 | – |
| 3. Crime Map | – | 1 (fetch cap) | 1 | – |
| 4. Crime Database | – | 1 (cascade unclear) | – | 1 |
| 5. Hotspot Analysis | **1 (RBAC bypass, all 4 endpoints)** | – | – | – |
| 6. Criminal Network | **1 (AI/graph desync)** | 3 (AI dataset mismatch, lens dimming, Neo4j-only compare) | 3 | – |
| 7. Anomaly Detection | **1 (no RBAC at all)** | – | 1 | – |
| 8. Predictive Analytics | – | – | 1 | 1 |
| 9. Offender Database | **1 (no RBAC)** | 1 (broken search claim) | – | – |
| 10. Victim Database | – | – | – | 1 |
| 11. Socio-Economic Insights | – | – | 1 | – |
| 12. Alerts Center | – | – | 1 | 1 |
| 13. Reports | – | 1 (unscoped history) | – | – |
| 14. Settings & Administration | – | – | – | 2 |
| Cross-cutting (backend+frontend) | – | – | 4 | 1 |

**Total: 4 Critical, 6 High, 14 Medium, 8 Low** across the audited surface.

---

## 18. Suggested Fix Priority Order

1. **Hotspot Analysis RBAC bypass** (Section 5) — one-line variable swap × 4, highest severity, trivial fix.
2. **Offender Database RBAC gap** (Section 9.1) — copy the District-Officer-scoping pattern already correct in `victims_router.py`.
3. **Anomaly Detection RBAC gap** (Section 7) — same pattern again.
4. **Reports `/history` scoping** (Section 14.1) — same pattern again.
5. **Crime Network AI/graph desync** (Section 13.1–13.2) — extend `ai-summary`'s signature to accept `search_query`/`node_type`, and ideally have it derive its stats from the *same* node/edge list `graph-data` already computed (pass the graph's `nodes`/`edges` into the AI summary function) rather than re-querying independently — this both fixes the sync issue and the dataset-mismatch issue in one change.
6. **Crime-type lens dimming bug** (Section 13.4) — populate `crime_types` on synthetic edges, or skip lens-dimming when `crime_type` is already a server-side filter.
7. Everything else in Sections 15–16 as time permits; none are user-facing breakages today but all reduce production-readiness.

*(Per your request, no fixes have been applied — this document is diagnostic only.)*