# SHASTRA — Full-Stack Code Audit Report
**Scope:** All 14 frontend pages, backend routers/services, PostgreSQL/Neo4j/Redis wiring, Criminal Network graph + filters, AI (Gemini) integration.
**Method:** Static review of every router, every frontend service, and every page component, with request/response shapes cross-checked between frontend and backend, and endpoint‑by‑endpoint mapping against `ENDPOINTS` in `apiEndpoints.ts`.
**How to use this doc:** Each issue has a **Location**, **What's wrong**, **Why it matters**, and a **Snippet** of the actual offending code (not a made-up example) so you can jump straight to the fix. Severity tags: 🔴 Critical (security/data), 🟠 High (broken feature/wrong data), 🟡 Medium (inconsistent behavior/UX), ⚪ Low (code quality/cleanup).

---

## Table of Contents
1. [Critical Security & Authorization Issues](#1-critical-security--authorization-issues)
2. [Broken / Dead Features](#2-broken--dead-features)
3. [Frontend ↔ Backend Wiring Mismatches](#3-frontend--backend-wiring-mismatches)
4. [Criminal Network Graph — Deep Dive](#4-criminal-network-graph--deep-dive)
5. [District & Crime-Type Filters — Deep Dive](#5-district--crime-type-filters--deep-dive)
6. [Database Layer (Postgres / Neo4j / Redis) Issues](#6-database-layer-postgres--neo4j--redis-issues)
7. [AI (Gemini) Integration Issues](#7-ai-gemini-integration-issues)
8. [Page-by-Page Findings (all 14 pages)](#8-page-by-page-findings-all-14-pages)
9. [Error-Handling / UX Consistency](#9-error-handling--ux-consistency)
10. [Code Quality / Production Hygiene](#10-code-quality--production-hygiene)
11. [Summary Table](#11-summary-table)

---

## 1. Critical Security & Authorization Issues

### 1.1 🔴 Redis cache key leaks cross-district / cross-role data on `/crimes/map-data`
**Location:** `crime_backend/MODULE_2_BACKEND/app/routers/crimes_router.py` (`get_map_data`, ~line 19-50)

Every other district-aware endpoint (`hotspots_router.py`, `network_router.py`, `dashboard_router.py`) resolves the caller's permitted district **before** building the cache key, using `scope_district_param()`. `crimes_router.py`'s `/map-data` does not — it caches using the raw *requested* filter, then applies the row-level restriction (`scope_district_filter`) only to the SQL query, **after** the cache key was already built:

```python
resolved_district = await resolve_district_id(db, district_id)

cache_key = f"crimes_map_data:{file_format}:{crime_type}:{resolved_district}:{date_from}:{date_to}:{limit}:{min_lat}:{max_lat}:{min_lng}:{max_lng}"
cached_data = await cache_get(cache_key)
if cached_data:
    ...
    return cached_data          # <-- served to ANY user who hits this exact key

...
q = scope_district_filter(q, current_user, Crime.district_id)   # scoping applied AFTER the cache key is fixed
```

**Why it matters:** If a `DISTRICT_OFFICER` for Mysuru requests `/api/crimes/map-data` with no `district_id` filter, the response (already restricted to Mysuru by `scope_district_filter`) gets cached under `crimes_map_data:json:None:None:None:None:5000:None:None:None:None`. The **next** user who hits that same unfiltered endpoint — including an `SCRB_OFFICER` who should see all 31 districts, or a `DISTRICT_OFFICER` from a *different* district — gets served the Mysuru-only cached payload (or vice-versa: an SCRB officer's full statewide result could be cached and then served to a district officer who should never see other districts' crime data). This is a real authorization bypass via cache poisoning, not just a data-freshness bug.

**Fix direction:** Include `current_user["role"]` and `current_user.get("district_id")` in the cache key, exactly like the pattern already used correctly elsewhere — or better, call `scope_district_param()` up front (as `hotspots_router.py` / `network_router.py` do) so the *resolved, permission-checked* district is what feeds the cache key.

---

### 1.2 🔴 Same class of bug should be verified in `/crimes/filter`
**Location:** `crimes_router.py`, `filter_crimes()` (~line 169)

This endpoint doesn't cache (no `cache_get`/`cache_set` calls), so it isn't currently exploitable the same way — but it's inconsistent with `/map-data` and worth double-checking if caching is ever added here later. Flagging for awareness since it's the same router.

---

### 1.3 🟠 `PUT /api/offenders/{offender_id}` has no district-ownership check
**Location:** `crime_backend/MODULE_2_BACKEND/app/routers/offenders_router.py` (~line 108-118)

Every read endpoint in this router (`profile`, `network`, `risk`, `modus-operandi`) explicitly checks:
```python
if current_user["role"] == "DISTRICT_OFFICER" and data.get("district_id") != current_user.get("district_id"):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
```
`POST /offenders` also forces `payload["district_id"] = current_user.get("district_id")` for district officers. But `edit_offender` (PUT) has **no such check at all**:
```python
@router.put("/{offender_id}")
async def edit_offender(
    offender_id: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"])),
):
    from app.services.offender_service import update_offender
    from app.utils.audit import log_action

    data = await update_offender(db, offender_id, payload)   # no ownership/district check
    if not data:
        raise HTTPException(status_code=404, detail="Offender not found")

    await log_action(db, current_user["user_id"], "UPDATE", "OFFENDER", offender_id, payload)
    return {"success": True, "data": data}
```
**Why it matters:** A `DISTRICT_OFFICER` can edit (including reassigning `district_id`, risk fields, status, etc. — `payload` is an untyped `dict`) any offender record in the system, from any district, contradicting the access model enforced everywhere else in the same file. Also note `payload: dict = Body(...)` is unvalidated — there's no Pydantic schema restricting which fields can be changed, so a caller could overwrite fields like `district_id`, `risk_score`, or internal bookkeeping fields directly.

---

### 1.4 🟡 AI Assistant / Edge-Insight prompt injection surface
**Location:** `assistant_router.py` (`/ask`), `network_router.py` (`/edge-insight`), `gemini_service.py`

`question` (from the user) and full node/edge JSON payloads (from `edge-insight`) are interpolated directly into the LLM prompt with no delimiting/sanitization beyond an f-string:
```python
prompt = f"""You are a crime-intelligence assistant for Karnataka State Police.
Use ONLY the following current statistics to answer. If the answer isn't in the data, say so.

DATA: {context}

QUESTION: {question}
"""
```
This is a standard prompt-injection surface (a user could try to get the model to ignore the "use only this data" instruction and fabricate authoritative-sounding "KSP statistics"). Low exploitability given the model only has read access and outputs go through `AIMarkdown` (react-markdown, not `dangerouslySetInnerHTML`, so XSS via markdown is **not** currently possible — confirmed safe), but worth hardening the system-prompt/user-content separation before this ships to real officers who may treat AI output as authoritative.

---

## 2. Broken / Dead Features

### 2.1 🟠 "Offline Mode" banner in Navbar can never appear — dead event listener
**Location:** `crime_frontend/src/components/common/Navbar.tsx` (~line 21-30, 202-206)

```tsx
const [usingMockData, setUsingMockData] = useState((window as any).__using_mock_data || false);
useEffect(() => {
  const handleMockData = () => setUsingMockData(true);
  window.addEventListener("mock-data-detected", handleMockData);
  return () => window.removeEventListener("mock-data-detected", handleMockData);
}, []);
...
{usingMockData && (
  <span>Offline Mode: Backend connection unavailable. Displaying simulated mock intelligence data.</span>
)}
```
**Search performed:** `grep -rn "mock-data-detected\|__using_mock_data" crime_frontend/src` — **zero** results outside `Navbar.tsx` itself. Nothing anywhere in the app ever dispatches `mock-data-detected` or sets `window.__using_mock_data`. Combined with the comment in `api.ts` ("No mock-data fallback. Let the caller show a real error/toast.") this looks like a leftover from an older build where a mock-data fallback existed — the UI still ships the banner and listener, but it's permanently unreachable dead code. Either wire it up to real offline detection or remove it.

### 2.2 🟠 `crimeTypeLens` client-side dimming in `NetworkGraph.tsx` is permanently disabled
**Location:** `CriminalNetwork.tsx` line 568, `NetworkGraph.tsx` lines 413-436, 477-482

`NetworkGraph` has a fully implemented feature: dim nodes/edges that don't match a selected crime type ("lens"). But `CriminalNetwork.tsx` always passes `null`:
```tsx
crimeTypeLens={null /* server already filters by crime type — lens overlay not needed */}
```
The comment explains the *intent* (server-side filtering replaced it), but the entire `useEffect` block in `NetworkGraph.tsx` that listens to `crimeTypeLens` changes, plus the `crimeTypeLensRef` re-application logic inside `clearFocus()`, is now unreachable dead code (~30 lines). Either remove it, or — better — repurpose it for something useful like a "preview" highlight while the user is choosing a crime type before the debounced server request fires.

### 2.3 🟠 Matrix view (`ConnectivityMatrix`) never shows the AI "Connection Insight" panel
**Location:** `CriminalNetwork.tsx` lines 574-582

In Graph view, tapping an edge calls `handleEdgeSelect()`, which populates `selectedEdge` and fetches an AI insight (`edgeInsight`). In Matrix view, clicking a connected cell does this instead:
```tsx
<ConnectivityMatrix
  nodes={filteredNodes}
  edges={edges}
  onCellClick={(nodeA, nodeB) => {
    const targetNode = filteredNodes.find(n => n.node_id === nodeB) || filteredNodes.find(n => n.node_id === nodeA);
    if (targetNode) navigateToNode(targetNode);
  }}
/>
```
It ignores the actual edge between `nodeA`/`nodeB` and just navigates to one of the two nodes — the entire point of a connectivity matrix (inspecting the *relationship*) is unavailable in Matrix view. `ConnectivityMatrix.tsx`'s `onCellClick` prop only passes back `(nodeA, nodeB)`, not the edge object, so this needs a prop-shape change too.

### 2.4 🟠 `GET /api/settings/profile` backend endpoint has no frontend caller
**Location:** `settings_router.py` (~line 13-20) vs. `crime_frontend/src/constants/apiEndpoints.ts` / `settingsService.ts`

The backend implements a working `/settings/profile` endpoint returning the logged-in user's own record, but there is no `ENDPOINTS.SETTINGS.PROFILE` entry and nothing in `settingsService.ts` or `SettingsPage.tsx` calls it. The Settings page ("Settings & Administration") has no "My Profile" tab at all — the officer viewing the page can't see or edit their own name/email/username, only manage other users (if SCRB) or thresholds. Either the page is missing a Profile tab, or this endpoint is dead.

### 2.5 ⚪ `get_crimes_for_map()` in `crime_service.py` is dead code
**Location:** `crime_backend/MODULE_2_BACKEND/app/services/crime_service.py` (~line 20-45)

A full, separate implementation of map-data fetching (with its own cache key `crime_map:...`) exists here but is **never called** (`grep -rn "get_crimes_for_map" app/` only matches its own definition). The actual `/crimes/map-data` route in `crimes_router.py` reimplements the same logic inline instead. This is duplicated, drifted logic — the two implementations already disagree (this one doesn't do district scoping via `scope_district_filter`, doesn't join `CrimeVictimLink`/`CrimeOffenderLink`, etc.). Safe to delete, or intentionally wire it in and delete the inline duplicate in the router — but don't leave both.

---

## 3. Frontend ↔ Backend Wiring Mismatches

### 3.1 🟠 `Promise.all` in Criminal Network couples graph load to AI summary load
**Location:** `CriminalNetwork.tsx` lines 93-146, `networkService.ts` (`getGraphData` vs `getAiSummary`)

`networkService.getGraphData()` catches its own errors and resolves to `{ status: "offline", error }` (never throws, except for aborts). `networkService.getAiSummary()` does the opposite — it **re-throws** on failure:
```ts
// getGraphData — swallows errors:
} catch (error: any) {
  if (error.name === "CanceledError") throw error;
  console.error("Error fetching network graph:", error);
  return { status: "offline", error: error.response?.data?.detail || "Failed to connect to the backend API." };
}

// getAiSummary — re-throws:
} catch (error: any) {
  if (error.name === "CanceledError") throw error;
  console.error("Error fetching AI summary:", error);
  throw error;
}
```
Both are awaited together:
```tsx
const [g, ai] = await Promise.all([
  networkService.getGraphData(...),
  networkService.getAiSummary(...),
]);
```
**Why it matters:** If Gemini is rate-limited, the `GEMINI_API_KEY` is missing, or `/network/ai-summary` 500s for any reason — while Neo4j and Postgres are perfectly healthy — `Promise.all` rejects because of the AI summary alone, and the `catch` block sets `status: "offline"` with a generic "Failed to connect to backend" message, discarding the graph data that *did* load successfully. The user sees "graph database is disconnected" when actually only the AI narrative failed. Use `Promise.allSettled` here (the pattern already used correctly in `SettingsPage.tsx`) and degrade the AI panel independently.

### 3.2 🟡 Silent-fail pattern on `CrimeMapPage.tsx`
**Location:** `CrimeMapPage.tsx` lines 34-56

```tsx
} catch (e: any) {
  if (e.name !== "CanceledError" && e.name !== "AbortError") {
    console.error("Failed to load map data:", e);
  }
} finally {
  setLoading(false);
}
```
There is no `error` state on this page at all — compare to `CriminalNetwork.tsx`, which has `status`/`errorMessage`/`warningMessage` and renders a real banner. If `/crimes/map-data` fails (backend down, 401, 500), `CrimeMapPage` just stops the spinner and silently shows an empty map with no explanation. Same silent-failure pattern recurs in `VictimDatabase.tsx`'s `handleRegisterVictim` (`catch (err) { console.error(err); }` — modal just stays open with no error text) and `SettingsPage.tsx`'s `handleAddUser`/`handleSaveThresholds` (no `try/catch` at all — see §9).

### 3.3 🟡 `NetworkGraph.tsx` ships ~15 `console.log` debug statements in the render/update path
**Location:** `NetworkGraph.tsx` lines 362-427 (verbatim, not paraphrased list — see file)

Example:
```tsx
console.log('[NetworkGraph] cy already exists — isReplace:', isReplace, 'cy nodes:', cy.nodes().length, 'cy edges:', cy.edges().length);
console.log('[NetworkGraph] classes on cy nodes sample:', cy.nodes().slice(0, 3).map(n => n.id() + ':' + n.classes().join(',')));
...
console.log('[NetworkGraph] lens matchingEdges:', matchingEdges.length, '/ total edges:', cyRef.current.edges().length);
```
These run on every graph rebuild/filter change and will spam the console for real users in production, plus have a (small) perf cost from repeated `.map()`/`.classes()` calls purely for logging. Strip before shipping, or gate behind `import.meta.env.DEV`.

---

## 4. Criminal Network Graph — Deep Dive

Since this was called out specifically, here's the consolidated picture (issues also listed individually above, gathered here for convenience):

| # | Feature | Status | Issue |
|---|---|---|---|
| 1 | Node click → detail panel | ✅ Works | `handleNodeSelect` → `navigateToNode` → parallel `getNodeDetail` + `getNodeAiAnalysis` (criminal nodes only). Fine. |
| 2 | Double-click → expand node | ✅ Works | Calls `/network/expand/{node_id}`, de-dupes new nodes/edges by id. Fine. |
| 3 | Edge click → AI insight (Graph view) | ✅ Works | `handleEdgeSelect` → `/network/edge-insight`. |
| 4 | Edge click → AI insight (Matrix view) | 🟠 Broken | See §2.3 — matrix cells don't surface edge details at all. |
| 5 | Shift-click → compare / shortest path | ✅ Works, but | Silently no-ops with only a `setWarningMessage` if `isFallbackMode` (Neo4j offline) — acceptable, but the message duplicates ("No path found... **or** the graph database is offline") rather than distinguishing the two cases, which will confuse investigators trying to diagnose why a path search failed. |
| 6 | Crime-type "lens" dimming | 🟠 Dead code | See §2.2 — always passed `null`. |
| 7 | Search / node-type / district / crime-type filters | ✅ Wired, server-side | Debounced (400 ms) `useEffect` correctly re-fetches on any of the 4 filter states; params round-trip through the URL via `useSearchParams` for shareable/bookmarkable links — nice. |
| 8 | AI Summary panel | 🟠 Coupled failure | See §3.1. |
| 9 | Cluster view toggle (`showClusters`) | ✅ Works | Cytoscape compound-node parenting keyed off `community_id`. |
| 10 | `colorBy` (type vs cluster) | ✅ Works | |
| 11 | Debug logging | 🟡 Needs cleanup | See §3.3. |
| 12 | `filteredNodes` "isolated node" toggle | ⚪ Minor gotcha | `showIsolated` filters client-side by recomputing connected-node-ids from the **currently loaded edge set**, which is correct — but the comment on line 308 ("nodeTypeFilter and searchQuery filtering happens server-side") is a trap for future maintainers: if someone adds a client-side node-type filter later without checking this comment, they'll get double-filtering bugs. Consider asserting this invariant with a code comment closer to where `nodeTypeFilter` is actually sent (line 103), not just here. |
| 13 | `selectedEdge` field names | ⚪ Fragile coupling | `CriminalNetwork.tsx`'s edge detail panel reads `selectedEdge.strength`, `selectedEdge.crimeTypes`, `selectedEdge.confidence`, `selectedEdge.label` — these are **cytoscape's internal camelCase field names** (set in `NetworkGraph.tsx`'s `buildElements()`), not the API's snake_case `NetworkEdge` shape (`strength_score`, `crime_types`, `confidence_level`, `relationship_type`). It works today only because Graph view is the *only* thing that ever calls `handleEdgeSelect`, and it happens to pass cytoscape's shape. This is exactly why #4 (Matrix view) can't be trivially fixed by just calling `handleEdgeSelect` from `ConnectivityMatrix` — the edge object shapes are different, and there's no shared type checking this. Recommend a single canonical `EdgeInsightData` type used everywhere. |

---

## 5. District & Crime-Type Filters — Deep Dive

- **District name → ID resolution** (`district_resolver.py`) is applied inconsistently in terms of *when* row-level scoping happens relative to caching (root cause of §1.1). The resolver itself (fuzzy `ILIKE` match with a `Bangalore`→`Bengaluru` alias) is fine functionally, but note it does an **unbounded `ILIKE '%value%'`** as a final fallback:
  ```python
  stmt = select(District.district_id).where(
      or_(
          District.district_name.ilike(district_val.strip()),
          District.district_name.ilike(search_name),
          District.district_name.ilike(f"%{district_val.strip()}%"),
      )
  )
  ```
  Any arbitrary query-string value for `district_id` gets passed through this on every filtered request (map, hotspots, network, offenders, victims, predictions, reports) — it's parameterized so not SQL-injectable, but it does mean a malformed/garbage `district_id` silently falls through to "no matching district → return the original raw string," which then gets compared against `Crime.district_id == resolved_district` and will just match zero rows rather than erroring. Acceptable, but no validation/allow-listing against `KARNATAKA_DISTRICTS` (already defined in `config.py`) is ever done — worth adding for defense-in-depth.

- **Crime-type filters**: `CRIME_TYPES` is defined once in `config.py` (12 types) and mirrored in the frontend as `constants/crimeTypes.ts`. These two lists were **not diffed against each other** in this review — recommend running a quick equality check (`config.py` vs `crimeTypes.ts`) since a drift here would silently break the crime-type filter/lens features (a frontend crime type that doesn't exist in the backend enum will just never match).

- **`useDistricts()` hook fails silently** (`hooks/useDistricts.ts`):
  ```ts
  .catch(() => {
    setDistricts([]);
  });
  ```
  If `/api/settings/districts` fails (network blip, backend restart), every district dropdown across the app (Network page, Settings, Victim/Offender search, Reports) just silently renders empty with **no error indicator and no retry** — the user has no way to know districts failed to load vs. "there are no districts."

---

## 6. Database Layer (Postgres / Neo4j / Redis) Issues

### 6.1 🟡 Neo4j fallback mode is well-designed, but confirm it stays consistent
`network_service.py` clearly implements a Postgres fallback when Neo4j is unreachable (`source: "postgres_fallback"` flag read by the frontend at `isFallbackMode`). This is good design. However, confirm that **all** graph-touching features correctly disable themselves in fallback mode — `handleNodeCompare` (shortest path) already checks `isFallbackMode` client-side, but `handleNodeExpand` does not; it will hit `/network/expand/{node_id}` regardless, which itself throws a 503 from Neo4j-dependent code:
```python
except Exception:
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, ...)
```
This is *handled* (caught in `handleNodeExpand`'s try/catch, shown as a warning message), so it's not broken, but it means every double-click during a Neo4j outage produces a failed network request + a visible warning rather than the button being disabled/hinted the way shortest-path compare is. Minor UX inconsistency, not a hard bug.

### 6.2 🟡 Health check doesn't reflect true readiness
**Location:** `main.py`, `/api/health`
```python
"scheduler": "running" if _db_ready else "stopped",
```
`_db_ready` is a startup-time global flag, only reflecting whether Postgres connected during the **lifespan startup event**. If Postgres later drops the connection at runtime (network partition, DB restart), `/api/health` will keep reporting `"scheduler": "running"` and `"database"` health is only accurate because `get_db_health()` does a live check — but the `scheduler` field is stale/misleading and doesn't actually reflect the scheduler container (which is a **separate process** per `docker-compose.yml`, not something this API process controls at all). This key is actively misleading for anyone using `/api/health` for uptime monitoring.

### 6.3 ⚪ Duplicate `EVIDENCE_UPLOAD_DIR` creation
`os.makedirs(UPLOAD_DIR, exist_ok=True)` is called both in `main.py` (top level) and again in `evidence_router.py`. Harmless (idempotent), but redundant — one source of truth would be cleaner, and currently two different `os.environ.get("EVIDENCE_UPLOAD_DIR", "/app/uploads")` calls exist instead of referencing `settings.EVIDENCE_UPLOAD_DIR` which is already defined in `config.py` for exactly this purpose.

---

## 7. AI (Gemini) Integration Issues

- Assistant (`/assistant/ask`) and Edge Insight (`/network/edge-insight`) both call `call_gemini(...)` and check `is_fallback` — good, this means the platform has a documented degraded-mode path (multi-key rotation implied by `GEMINI_API_KEYS`/`get_gemini_api_keys()` in `config.py`). Confirm `gemini_client.py`'s key-rotation logic actually rotates on 429/quota errors and not just on hard connection failures — not fully traced in this pass given time constraints; recommend a focused review of `app/core/gemini_client.py` and `app/services/gemini_service.py` specifically for retry/backoff behavior under Gemini rate limits, since **every** page that shows an "AI Analysis" panel (Network, Anomalies presumably, Predictive Analytics) depends on this being resilient.
- Prompt injection hardening — see §1.4.
- `AIMarkdown.tsx`'s aggressive string pre-processing (stripping `\"` wrapping quotes, un-escaping `\n`, collapsing `** text **` → `**text**`) is a strong signal that the raw Gemini output is inconsistently formatted/double-encoded coming out of the backend. This is a symptom worth fixing at the source (in `gemini_service.py`'s response parsing) rather than papering over client-side with five separate regex passes on every render.

---

## 8. Page-by-Page Findings (all 14 pages)

| # | Page | File | Status |
|---|---|---|---|
| 1 | Login | `Login.tsx` | ✅ Solid — proper try/catch, 429 handling, no localStorage token leakage (JWT is httpOnly cookie). |
| 2 | Dashboard | `Dashboard.tsx` | ✅ Wired to `/dashboard/summary`, `/dashboard/recent-crimes`, `/dashboard/recent-alerts`, `/dashboard/crime-trends`. No `console.log`/dead code found. |
| 3 | Crime Map | `CrimeMapPage.tsx` | 🟡 Works, but silent-fail on load error (§3.2); relies on backend's default 180-day window when no date filter set — confirm this matches user expectations on first load. |
| 4 | Crime Database | `CrimeDatabase.tsx` | ✅ Wired to `/crimes/filter`, status update, delete, evidence upload/list. |
| 5 | Hotspot Analysis | `HotspotAnalysis.tsx` | ✅ Wired to `/hotspots/clusters`, `/time-patterns`, `/top-list`, `/deployment-suggestions`; correctly uses `scope_district_param` server-side (not vulnerable to §1.1's caching bug). |
| 6 | Criminal Network | `CriminalNetwork.tsx` | 🟠 See §4 — multiple issues (dead lens feature, matrix/graph edge-insight asymmetry, coupled AI-summary failure). |
| 7 | Anomaly Detection | `AnomalyDetection.tsx` | ✅ Wired to `/anomalies/list`, `/update-status`, `/scan`. |
| 8 | Predictive Analytics | `PredictiveAnalytics.tsx` | ✅ Wired to `/predictions/risk-map`, `/high-risk-areas`, `/forecast`, `/emerging-typologies`. |
| 9 | Offender Database | `OffenderDatabase.tsx` | 🟠 Backend PUT has no district check (§1.3); frontend itself is fine. |
| 10 | Victim Database | `VictimDatabase.tsx` | 🟡 Silent-fail on register error (§3.2). |
| 11 | Socio-Economic Insights | `SocioEconomicInsights.tsx` | ✅ Wired to `/predictions/socioeconomic-correlation`. |
| 12 | Alerts Center | `AlertsPage.tsx` | ✅ Wired to `/alerts/active`, `mark-read`, `dismiss`; WebSocket live-push confirmed correctly routed to `/api/alerts/ws` (§ see App.tsx review). |
| 13 | Reports | `ReportsPage.tsx` | ✅ Wired to `/reports/generate`, `/history`, `/download`, `delete`; backend has correct per-report district ownership checks. |
| 14 | Settings & Administration | `SettingsPage.tsx` | 🟠 No error handling on Add User / Save Thresholds (§9); no user edit/deactivate; `/settings/profile` endpoint unused (§2.4); pagination count goes stale after adding a user (§9). |

---

## 9. Error-Handling / UX Consistency

A recurring pattern across the app: **some pages show real errors, most swallow them silently.**

Good example (`CriminalNetwork.tsx`) — has `status`, `errorMessage`, `warningMessage` state and renders a banner.

Bad examples:
- `SettingsPage.tsx` — `handleSaveThresholds` and `handleAddUser` have **no try/catch at all**:
  ```tsx
  const handleSaveThresholds = async () => {
    if (!thresholds) return;
    await settingsService.updateAlertThresholds(thresholds as any);   // unhandled if this throws
    setSaveMsg("Thresholds saved!");
    setTimeout(() => setSaveMsg(""), 2500);
  };

  const handleAddUser = async () => {
    if (!newUser.username || !newUser.full_name) return;
    const payload = { ...newUser, district_id: newUser.district || undefined };
    const result = await settingsService.addUser(payload as any);   // unhandled if this throws (e.g. 409 duplicate username)
    setUsers((prev) => [...prev, ((result as any).data || (result as any).user) as User]);
    setNewUser({ username: "", full_name: "", role: "INVESTIGATOR", password: "", district: "" });
  };
  ```
  If `addUser` 409s on a duplicate username (the backend explicitly returns this — `raise HTTPException(status_code=409, detail=str(e))`), this becomes an unhandled promise rejection: the form doesn't clear, no message is shown, and the user has no idea the add failed. Also note `usersTotalCount` isn't incremented after a successful add, so pagination ("Showing X of Y") becomes stale until the next full reload.
- `VictimDatabase.tsx` — `handleRegisterVictim` catches but only `console.error`s; the registration modal doesn't show the user why it failed.
- `CrimeMapPage.tsx` — see §3.2.

**Recommendation:** Standardize on one pattern (a shared `useAsyncAction` hook or a toast utility) instead of each page inventing its own ad-hoc error state.

---

## 10. Code Quality / Production Hygiene

- Debug `console.log` statements shipped in `NetworkGraph.tsx` (§3.3) — grep for `console.log` across `src/` before shipping; a few more scattered instances exist beyond this file and should be swept in one pass:
  ```bash
  grep -rn "console.log" crime_frontend/src --include="*.tsx" --include="*.ts"
  ```
- Duplicate/dead backend function `get_crimes_for_map` (§2.5).
- Unreachable frontend feature code: mock-data banner (§2.1), crime-type lens (§2.2).
- `PUT /crimes/{crime_id}` and `PATCH /crimes/{crime_id}/status` both accept `payload: dict = Body(...)` with no Pydantic schema — same untyped-payload concern as offenders' PUT (§1.3), just with less severe consequence since `update_crime_record` presumably whitelists fields server-side (verify this in `crime_service.py` — not fully traced here).
- `docker-compose.yml` is otherwise clean: healthchecks present for all three databases, `depends_on: condition: service_healthy` used correctly, Postgres/Neo4j/Redis all bound to `127.0.0.1` only (not exposed publicly) — good production hygiene there.
- `config.py` correctly refuses to boot in production with default JWT secret / default DB passwords via `field_validator` — good.

---

## 11. Summary Table

| Severity | Count | Examples |
|---|---|---|
| 🔴 Critical | 1 | Cache-key authorization bypass on `/crimes/map-data` (§1.1) |
| 🟠 High | 8 | Offender PUT missing district check; dead mock-data banner; dead crime-type lens; Matrix view missing edge insight; AI-summary failure blocks graph load; dead `/settings/profile`; `get_crimes_for_map` dead code; no Settings error handling |
| 🟡 Medium | 7 | Silent-fail patterns (map, victim register); debug console.logs; stale health-check field; districts hook silent failure; shortest-path/Neo4j-offline messaging; Neo4j fallback UX inconsistency; untyped PUT payloads |
| ⚪ Low | 4 | Duplicate upload-dir creation; unbounded ILIKE fallback; edge-field-name fragility; comment/code-location mismatch in filter logic |

**Priority order for fixing:**
1. §1.1 (cache authorization bypass) — fix before any multi-role production deployment.
2. §1.3 (offender PUT district check) — same class of bug, quick fix.
3. §3.1 (Promise.all coupling) — affects daily usability of the Network page whenever Gemini has any hiccup.
4. §2.3 (Matrix view edge insight) — feature completeness for the page you called out specifically.
5. Everything else, roughly in the order listed above.

---
*Audit scope note: this review covered `main.py`, `config.py`, `security.py`, `redis_connection.py`, `district_resolver.py`, and the routers for auth, crimes, hotspots, network, offenders, evidence, reports, settings, dashboard, assistant — plus all 14 frontend pages, `App.tsx`, all `services/*.ts`, `NetworkGraph.tsx`, `ConnectivityMatrix.tsx`, `AIMarkdown.tsx`, `useDistricts.ts`, and `docker-compose.yml`. Services not fully traced line-by-line in this pass (flagged for a follow-up focused review if you want it): `gemini_client.py`/`gemini_service.py` retry logic, `ml_models/*` (hotspot clustering, forecasting, anomaly detection, risk scoring internals), `import_router.py`/`import_service.py` bulk CSV ingestion, and the `scheduler/` background jobs.*