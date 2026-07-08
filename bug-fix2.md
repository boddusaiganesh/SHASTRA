# SHASTRA Platform — Full-Stack Audit Report
**Scope:** All 14 pages (Login → Settings & Administration), frontend↔backend wiring, database connections (PostgreSQL / Neo4j / Redis), the Criminal Network graph + its District/Crime-Type filters, and general production-readiness.

**Method:** Every backend router (`app/routers/*.py`), service (`app/services/*.py`), core module (`app/core/*.py`), every frontend page (`src/pages/*.tsx`), every service (`src/services/*.ts`), state slices, routing, and Docker/Alembic config were read and cross-referenced against each other (not just skimmed).

Legend: 🔴 Critical (breaks a feature or is a security/data-integrity risk) · 🟠 High (works but wrong/fragile in production) · 🟡 Medium · 🔵 Minor/cleanup.

---

## 1. Executive Summary

The codebase is well-structured (clean router/service/model separation, JWT + bcrypt auth, rate limiting, RBAC via `require_role`, Alembic migrations, Dockerized Postgres/Neo4j/Redis). However, three classes of problems will cause real production failures:

1. **The Criminal Network graph's District and Crime-Type filters are structurally non-functional** — the Neo4j sync code never writes the properties those filters query on. This is one of the biggest issues and directly affects the "Criminal Network" page you called out (§2).
2. **The real-time Alerts WebSocket has no access-control scoping at all** — every connected client, regardless of role or district, receives every alert statewide. `DISTRICT_OFFICER` accounts are scoped everywhere else in the app (crimes, hotspots) but not here, and the REST alerts endpoint is scopable but the frontend never scopes it either (§16.1, §16.2). This is a genuine access-control gap, not just a UX bug.
3. **Uploaded evidence files have no persistent storage** — the backend container has no volume for `app/uploads`, so every file is lost on redeploy/restart while the database still references it (§16.3).
4. **Several frontend services silently substitute fake/mock data for real data on the success path**, not just on network failure — and this is *not* gated by `VITE_DEMO_MODE`. In a police intelligence product this is a serious integrity risk (an officer could see fabricated stats and not know it) (§4).
5. A handful of **response-shape / naming mismatches** (district naming, response envelope unwrapping, a typo'd default district code in bulk import, missing endpoints) that are fragile rather than fully broken, but will bite in production.

This report went through two full passes over the entire codebase (every router, service, core module, page, and frontend service file — not a sample). Everything below is organized by severity first (§2–§13 from pass one, §16 from the re-audit), then a page-by-page checklist for all 14 screens (§14), then DB connectivity (§15) and a consolidated priority fix order (§17).

---

## 2. 🔴 CRITICAL — Criminal Network graph: District & Crime-Type filters are dead

**Where:** `crime_backend/MODULE_2_BACKEND/app/core/neo4j_connection.py` (`get_network_graph`) and `scripts/sync_postgres_to_neo4j.py`.

**What's wrong:** The graph query filters nodes/edges like this:

```python
# app/core/neo4j_connection.py — get_network_graph()
if district_id:
    where_clauses.append("n.district_id = $district_id")
    params["district_id"] = district_id

if crime_type:
    where_clauses.append("$crime_type IN n.crime_types")
```

But the sync script that populates Neo4j from Postgres **never writes `district_id` or `crime_types` onto any node**:

```python
# scripts/sync_postgres_to_neo4j.py
await sync_offender_to_neo4j({
    "offender_id": str(off.offender_id),
    "name": f"{off.first_name} {off.last_name}",
    "risk_level": off.risk_level,
    "risk_score": off.risk_score or 0,
    "crime_count": off.total_crimes or 0,
    "status": off.status,
    # <-- no district_id, no crime_types
})
```

```python
# app/core/neo4j_connection.py
async def sync_offender_to_neo4j(offender_data):
    query = """
    MERGE (c:Criminal {offender_id: $offender_id})
    SET c.name = $name, c.risk_level = $risk_level, c.risk_score = $risk_score,
        c.crime_count = $crime_count, c.status = $status
    RETURN c
    """
    # district_id / crime_types are simply never SET
```

Same story for `sync_victim_to_neo4j` and `sync_location_to_neo4j` — no `district_id`. And `create_criminal_relationship` is always called from the sync script with `crime_types=[]`:

```python
await create_criminal_relationship(
    offender_id_1=node_id, offender_id_2=associate_id,
    relationship_type="KNOWS", strength_score=60.0,
    confidence_level="SUSPECTED", crime_ids=[], crime_types=[]   # always empty
)
```

**Effect:** In `CriminalNetwork.tsx`, selecting any district (`districtFilter`) or crime type (`crimeTypeLens`) sends `district_id` / `crime_type` to `/api/network/graph-data`. Cypher's `n.district_id = $district_id` against a node with no `district_id` property evaluates to `NULL` (not a match), so **the WHERE clause excludes every node** the moment a district or crime-type filter is applied. The UI will show the "No Matches for This Filter Combination" empty state for any non-"All" selection — this is not a data problem, it's a hardcoded impossibility.

**Fix (two parts):**

1. Add `district_id` and `crime_types` to the nodes/relationships when syncing:

```python
# app/core/neo4j_connection.py
async def sync_offender_to_neo4j(offender_data: Dict[str, Any]):
    query = """
    MERGE (c:Criminal {offender_id: $offender_id})
    SET c.name = $name, c.risk_level = $risk_level, c.risk_score = $risk_score,
        c.crime_count = $crime_count, c.status = $status,
        c.district_id = $district_id, c.crime_types = $crime_types
    RETURN c
    """
    await run_neo4j_query(query, offender_data)
```

```python
# scripts/sync_postgres_to_neo4j.py
for off in offenders:
    off_crime_types = list({
        crime_map[cid].crime_type
        for cid, oids in crime_to_offenders.items() if str(off.offender_id) in oids
    })
    await sync_offender_to_neo4j({
        "offender_id": str(off.offender_id),
        "name": f"{off.first_name} {off.last_name}",
        "risk_level": off.risk_level,
        "risk_score": off.risk_score or 0,
        "crime_count": off.total_crimes or 0,
        "status": off.status,
        "district_id": off.district_id,          # NEW
        "crime_types": off_crime_types,           # NEW
    })
```

Do the same for `sync_victim_to_neo4j` / `sync_location_to_neo4j` (locations already have a natural `district_id` on the Postgres `Location` model — pull it through), and pass real `crime_types` into `create_criminal_relationship` instead of `[]`.

2. This must also run on the **live** path, not just the offline batch script — currently nothing calls `sync_offender_to_neo4j` when a crime/offender is created via the API (`crime_service.create_crime`), so newly created records never reach Neo4j at all until someone manually re-runs `sync_neo4j.py`. Confirm whether that's intended (batch-only sync) and document it in the README; if not, call the sync functions from `crime_service.py`/`offender_service.py` on create/update.

---

## 3. 🔴 CRITICAL — Network graph produces duplicate edges

**Where:** `app/core/neo4j_connection.py` → `get_network_graph()`

```python
edges.append({
    "edge_id": f"{source_id}_{target_id}",
    "source_node_id": source_id,
    "target_node_id": target_id,
    ...
})
```

The Cypher query expands `OPTIONAL MATCH (n)-[r]-(connected)` **from every root node independently**. If both endpoints of a relationship are within the top `node_limit` nodes (very common — that's most of the graph), the same relationship is emitted twice: once as `(A→B)` while processing A, once as `(B→A)` while processing B. There is no de-duplication before `edges` is returned, so `total_edges`, `network_density`, and the rendered graph all double-count many relationships, and Cytoscape will draw two overlapping lines for the same connection.

**Fix:** de-dupe by an order-independent key before returning:

```python
seen_edges = {}
for e in edges:
    key = tuple(sorted([e["source_node_id"], e["target_node_id"]])) + (e["relationship_type"],)
    if key not in seen_edges:
        seen_edges[key] = e
edges = list(seen_edges.values())
```

---

## 4. 🔴 CRITICAL — Frontend silently returns mock/fake data on the *success* path, not gated by `VITE_DEMO_MODE`

**Where:** This exact pattern repeats across `crimeService.ts`, `alertService.ts`, `predictionService.ts`, `offenderService.ts`, `settingsService`, `reportService`.

```ts
// crime_frontend/src/services/crimeService.ts
getRecentCrimes: async (limit = 10) => {
  try {
    const res = await api.get(ENDPOINTS.DASHBOARD.RECENT_CRIMES, { params: { limit } });
    const data = res.data;
    return Array.isArray(data) ? data : (data?.crimes || data?.data || mockRecentCrimes); // ⚠️
  } catch (error) {
    if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockRecentCrimes; }
    throw error;
  }
},
```

The `|| mockRecentCrimes` fallback is **inside the `try` block**, i.e. it runs on a *successful* HTTP response whose JSON shape doesn't match what the code expects (e.g. an empty object, a renamed key, or any backend refactor) — completely independent of `VITE_DEMO_MODE`. The README explicitly says `VITE_DEMO_MODE` "MUST be set to false" in production, but that flag has no effect on this code path at all.

Same bug exists in:
- `crimeService.getMapData` → `mockMapCrimes`
- `crimeService.getRecentAlerts` → `mockRecentAlerts`
- `alertService.getAlerts` → `mockRecentAlerts`
- `settingsService.getUsers` → `mockUsers`
- `reportService.getSavedList` → `mockSavedReports`

**Why it's dangerous here specifically:** this is a crime-intelligence tool for police. Silently showing fabricated crime counts, fabricated alerts, or fabricated user lists to an officer — with zero indication it happened — is worse than showing an error.

**Fix:** separate "malformed success response" from "network/demo fallback." Never fall back to mock data unless the *request itself* failed and demo mode is explicitly on:

```ts
getRecentCrimes: async (limit = 10) => {
  try {
    const res = await api.get(ENDPOINTS.DASHBOARD.RECENT_CRIMES, { params: { limit } });
    const data = res.data;
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.crimes)) return data.crimes;
    if (Array.isArray(data?.data)) return data.data;
    // Unexpected shape from a *successful* call — this is a bug, not "no data". Surface it.
    console.error("Unexpected /dashboard/recent-crimes response shape:", data);
    throw new Error("Malformed response from server");
  } catch (error) {
    if (import.meta.env.VITE_DEMO_MODE === 'true') { flagMockDataUsed(); return mockRecentCrimes; }
    throw error;
  }
},
```

Apply the same restructuring to every service listed above.

---

## 5. 🟠 HIGH — Inconsistent response-envelope unwrapping (fragile, easy to silently break)

**Where:** `crime_frontend/src/services/api.ts`

```ts
api.interceptors.response.use((response) => {
  if (response.data && response.data.success !== undefined && response.data.data !== undefined) {
    const keys = Object.keys(response.data);
    const hasMetadata = keys.some(k => !['success', 'data', 'message'].includes(k));
    if (!hasMetadata) {
      return { ...response, data: response.data.data };   // unwraps to response.data.data
    }
    return response;                                        // does NOT unwrap
  }
  return response;
});
```

Whether a response gets unwrapped depends entirely on whether the backend happened to add an extra top-level key (e.g. `total_count`, `limit`). Compare:

```python
# dashboard_router -> {"success": True, "data": {...}}          → gets unwrapped
return {"success": True, "data": summary_dict}

# crimes_router /map-data -> {"success": True, "data": [...], "total_count": n, "limit": n}  → NOT unwrapped
return {"success": True, "data": formatted_data, "total_count": total_count, "limit": limit}
```

Every single consumer downstream then has to defensively try `res.data?.data || res.data` to cope with both cases (this is exactly why `crimeService.getDashboardSummary` has `res.data?.data || res.data`, and `getMapData` has `data?.crimes || data?.data || mockMapCrimes` — those aren't stylistic, they're compensating for this inconsistency). Adding one new field to *any* endpoint's response tomorrow will silently flip its unwrapping behavior and can break every caller.

**Fix:** pick one envelope shape and enforce it everywhere. Two options:
- **(a)** Backend always returns `{success, data, message?, meta?}` (put `total_count`/`limit` under `meta`, not top-level), and the interceptor always unwraps to `data`, always exposing `meta` via `response.headers` or a second field so callers don't lose it.
- **(b)** Never auto-unwrap in the interceptor; every service explicitly reads `res.data.data`.

Either is fine — what's not fine is the current "depends on incidental extra keys" behavior.

---

## 6. 🟠 HIGH — District naming mismatch (`Bangalore` vs `Bengaluru`) is patched around, not fixed, and doesn't reach Neo4j at all

**Where:** `app/core/config.py` (`KARNATAKA_DISTRICTS`) vs `app/utils/district_resolver.py`

```python
# config.py
{"district_id": "KA-01", "district_name": "Bangalore Urban", ...}
```

```python
# district_resolver.py
search_name = district_val.replace("Bengaluru", "Bangalore").strip()
```

This resolver is called before every Postgres query (`crimes_router`, `hotspots_router`, etc.), so SQL filtering works. But:
- It is **never called** in the Neo4j path (`get_network_graph` takes `district_id` straight from the query string with no resolution) — so even after fixing §2, a UI passing `"Bengaluru Urban"` instead of the code `"KA-01"` would still silently fail to match.
- The seed districts use the colonial spelling "Bangalore" while literally every other place in the codebase (mock data, UI copy, README) uses "Bengaluru" — this is a paper cut waiting to bite anyone who queries the DB directly or adds a new integration that doesn't go through `district_resolver`.

**Fix:** Standardize on one canonical name (`Bengaluru Urban`) in `KARNATAKA_DISTRICTS`, keep `district_resolver` only as a defensive alias layer (for legacy/free-text input), and route all Neo4j district filtering through the same resolver:

```python
# network_router.py — before calling get_network_graph
resolved_district_id = await resolve_district_id(db, district_id) if district_id else None
data = await get_network_graph(..., district_id=resolved_district_id, ...)
```

---

## 7. 🟠 HIGH — `init_db()` doesn't actually create/migrate tables; misleading log message

**Where:** `app/core/database.py`

```python
async def init_db():
    ...
    try:
        logger.info("Database tables initialized via Alembic migrations")   # ⚠️ nothing happened here
        await seed_initial_data()
        return True
    except Exception as e:
        ...
```

This function logs a success message but never runs `alembic upgrade head` or `Base.metadata.create_all`. It **only works because** the Docker image's `CMD` happens to run migrations first:

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && python main.py"]
```

If anyone runs `python main.py` directly (local dev without Docker, a Kubernetes deployment with a different entrypoint, CI test runner, etc.) — which the README's own "Getting Started" doesn't explicitly forbid — tables will not exist, `seed_initial_data()` will throw, get swallowed by the `except`, and the app will boot in a fully broken "degraded mode" with a misleading "✅ PostgreSQL Database connected" log line.

**Fix:** make `init_db()` honest — either actually invoke Alembic programmatically, or explicitly document/enforce that migrations are a required external step and fail loudly (not silently continue) when the expected tables are missing:

```python
async def init_db():
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1 FROM users LIMIT 1"))
    except Exception:
        logger.critical("Required tables not found. Run `alembic upgrade head` before starting the app.")
        return False
    await seed_initial_data()
    return True
```

---

## 8. 🟠 HIGH — `/settings/districts`, `/network/graph-data`, and the frontend `useDistricts` hook are wired through a mislabeled import

**Where:** `crime_frontend/src/hooks/useDistricts.ts`

```ts
import { settingsService } from "../services/alertService";  // ⚠️ districts service lives in alertService.ts
```

This *works* today because `settingsService` is (confusingly) defined inside `alertService.ts` rather than a `settingsService.ts` file, but it's a maintenance trap: anyone adding a new `settingsService.ts` file (a very natural thing to do) will create a silent duplicate/shadow module, and anyone searching for "where is settingsService defined" will look in the wrong file. It's not a runtime bug today, but it's a landmine.

**Fix:** move `settingsService`, `alertService`, and `reportService` out of `alertService.ts` into their own files (`settingsService.ts`, `reportService.ts`), consistent with every other domain (`offenderService.ts`, `victimService.ts`, etc.).

---

## 9. 🟠 HIGH — Redis connection: password wiring depends entirely on `.env`, no fail-fast

**Where:** `docker-compose.yml` + `app/core/redis_connection.py`

```yaml
redis:
  command: /bin/sh -c 'redis-server --requirepass "$$REDIS_PASSWORD"'
```

```python
_redis_client = aioredis.from_url(
    settings.REDIS_URL,
    password=settings.REDIS_PASSWORD or None,
    ...
)
await _redis_client.ping()
```

If `REDIS_PASSWORD` is unset/empty in `.env` (the `.env.example` for the backend should be checked — it defaults to `""` in `config.py`), Redis starts with `--requirepass ""`, i.e. **no password**, on a container that's also mapped to the host on port 6379 in `docker-compose.yml`:

```yaml
redis:
  ports:
    - "6379:6379"
```

That's an open, unauthenticated Redis instance reachable from the host network (and beyond, if the host isn't firewalled) holding session/token-blacklist data. Also note `postgres` (5432) and `neo4j` (7687/7474) are similarly published to the host in this compose file — fine for local dev, but this compose file is presented in the README as the production deployment path with no separate hardened compose override.

**Fix:**
- Fail startup in `settings.py`/`redis_connection.py` if `REDIS_PASSWORD` is empty and `ENVIRONMENT == "production"` (mirror the existing `JWT_SECRET_KEY` validator).
- Don't publish `5432`/`6379`/`7687`/`7474` to the host in a production compose file; only `backend` and `frontend` need public ports. Provide a `docker-compose.prod.yml` override that removes these `ports:` blocks.

---

## 10. 🟡 MEDIUM — No client-side session validation on app load / silent stale-session UX

**Where:** `crime_frontend/src/store/authSlice.ts`, `App.tsx`

```ts
const initialState: AuthState = {
  isAuthenticated: !!localStorage.getItem("auth_token"),   // token presence only, never validated
  ...
};
```

`authService.verifyToken()` exists and calls `GET /auth/verify-token`, but it is **never invoked** anywhere (no `useEffect` on app mount calls it). So a user with an expired/blacklisted token gets treated as authenticated and shown the full dashboard shell until their *first* API call 401s (via the interceptor), at which point they're bounced to `/login` mid-interaction. This is a UX gap, not a security hole (the backend still rejects the expired token), but it produces confusing flicker/partial-load states.

**Fix:** call `authService.verifyToken()` once in a top-level effect in `App.tsx` before rendering `ProtectedRoute`'s children, and show a loading state / redirect immediately if it fails.

---

## 11. 🟡 MEDIUM — Evidence download endpoint exists on the backend but isn't in `apiEndpoints.ts`

**Where:** `app/routers/evidence_router.py` defines:

```python
@router.get("/download/{evidence_id}")
```

But `crime_frontend/src/constants/apiEndpoints.ts` only defines:

```ts
EVIDENCE: {
  BY_CRIME: (crimeId: string) => `/evidence/${crimeId}`,
},
```

There is no `DOWNLOAD` entry and `evidenceService.ts` never calls it — so evidence files can be uploaded (`POST /evidence/{crime_id}`) and listed (`GET /evidence/{crime_id}`) but a user has no way to actually download/view an uploaded evidence file from the UI. Either this is an intentionally unfinished feature or a missed wire-up.

**Fix:**
```ts
// apiEndpoints.ts
EVIDENCE: {
  BY_CRIME: (crimeId: string) => `/evidence/${crimeId}`,
  DOWNLOAD: (evidenceId: string) => `/evidence/download/${evidenceId}`,
},
```
```ts
// evidenceService.ts
downloadEvidence: async (evidenceId: string) => {
  const res = await api.get(ENDPOINTS.EVIDENCE.DOWNLOAD(evidenceId), { responseType: 'blob' });
  return res.data;
},
```

---

## 12. 🟡 MEDIUM — `anomalies_router` registers two routes to the same handler at conflicting paths

**Where:** `app/routers/anomalies_router.py`

```python
@router.get("/")
@router.get("/list")
async def get_anomalies(...):
```

Frontend only calls `ENDPOINTS.ANOMALIES.LIST = "/anomalies/list"`, so `/anomalies/` (i.e. `/api/anomalies/` with trailing slash) is dead code — harmless, but worth removing for a clean OpenAPI schema (right now `/docs` shows the same operation twice under two paths, which is confusing during QA/pen-testing).

---

## 13. 🔵 MINOR — Misc cleanup items found during the pass

- **`crime_backend/.../app/routers/settings_router.py`** — `GET /settings/profile` exists but has no corresponding entry in `apiEndpoints.ts`/no frontend caller. Confirm intended or remove.
- **`NetworkGraph.tsx`** builds a fallback edge id as `` `e${i}_${source}_${target}` `` — unique per array index, so it won't literally collide, but combined with §3 (duplicate edges from the backend) you'll still visually render two lines for one relationship. Fixing §3 server-side is the real fix; consider also de-duping client-side defensively:
  ```ts
  const uniqueEdges = Array.from(
    new Map(edges.map(e => [[e.source_node_id, e.target_node_id].sort().join('|') + e.relationship_type, e])).values()
  );
  ```
- **`alertService.markRead` / `dismiss`** swallow all errors and return an optimistic `{success:true}` even when the backend call actually failed:
  ```ts
  markRead: async (id: string) => {
    try { const res = await api.put(ENDPOINTS.ALERTS.MARK_READ(id)); return res.data; }
    catch { return { success: true, alert_id: id }; }   // ⚠️ lies about success on failure
  },
  ```
  This means a failed "mark as read" (e.g. token expired) will still update Redux state as if it succeeded, and the alert will appear read in the UI while remaining unread server-side. Re-throw on failure and let the caller handle it, or only optimistically update after a confirmed 2xx.
- **`GEMINI_API_KEY` / Gemini AI features** (Network AI Summary, Edge Insight, Assistant, Anomaly `ai_explanation`, MO analysis) all depend on `settings.GEMINI_API_KEY`/`GEMINI_API_KEYS` being set. If unset, `init_gemini_models()` fails at startup (caught, logged as `❌ Gemini AI init failed`) and every AI-powered panel across Dashboard's assistant widget, Criminal Network's "AI Network Analysis", Anomaly Detection's AI explanation, and Predictive Analytics will silently return empty/None. There is no UI-level "AI unavailable" banner distinct from "no data" — worth adding so QA/officers can tell the difference between "nothing found" and "AI is not configured."
- **CORS in `main.py`**: production `allowed_origins` is built by splitting `settings.FRONTEND_URL` on commas, but the Dockerfile/compose only ever sets a single `FRONTEND_URL`. Double-check your actual production domain list (including `https://` vs bare host) is set via a comma-separated `FRONTEND_URL` env var before deploying — a mismatch here manifests as totally silent, hard-to-diagnose CORS failures in prod only.

---

## 14. Page-by-Page Wiring Checklist

| # | Page | Route | Frontend Service(s) | Backend Router | Status |
|---|------|-------|---------------------|-----------------|--------|
| 1 | Login | `/login` | `authService.ts` | `auth_router.py` | ✅ Wired correctly. Rate-limited (10/min), bcrypt + JWT, Redis blacklist on logout. `verifyToken` unused (§10). |
| 2 | Dashboard | `/` | `crimeService.ts` (summary, recent crimes/alerts, trends) | `dashboard_router.py` | ✅ Routes match. ⚠️ Success-path mock fallback (§4) on recent crimes/alerts. |
| 3 | Crime Map | `/map` | `crimeService.getMapData` | `crimes_router.py /map-data` | ✅ Filters (crime_type/district/date/bbox) all implemented server-side and match query params sent from `CrimeMapPage.tsx`/`MapControls.tsx`. ⚠️ Mock fallback (§4). |
| 4 | Crime Database | `/crimes` | `crimeService.filterCrimes/update/updateStatus/remove` | `crimes_router.py /filter,/detail,/{id}` | ✅ Status enum values match exactly between frontend dropdown and backend `CRIME_STATUS_VALUES`. Role checks correct (`DISTRICT_OFFICER` scoping, `SCRB_OFFICER`-only delete). |
| 5 | Hotspot Analysis | `/hotspots` | `crimeService.getHotspotClusters/getTimePatterns/getTopHotspots/getDeploymentSuggestions` | `hotspots_router.py` | ✅ Endpoints match. Field-name normalization in `normalizeHotspot()` is defensive/reasonable. |
| 6 | Criminal Network | `/network` | `networkService.ts` | `network_router.py`, `neo4j_connection.py` | 🔴 **District & crime-type filters non-functional (§2). Duplicate edges (§3).** 🟠 **Graph layout spacing is static, doesn't scale with node count — clumped/unreadable with "All Crimes Lens" or large datasets (§17).** Search/node-type filters work (client + Cypher `CONTAINS`). Shortest-path, expand, AI summary, edge insight all correctly wired end-to-end otherwise. |
| 7 | Anomaly Detection | `/anomalies` | `predictionService.anomalyService` / `anomalyService` | `anomalies_router.py` | ✅ Wired (note duplicate route registration, §12). Relies on scheduler having run `run_anomaly_detection` at least once — if it hasn't, page will correctly show empty state, not an error. |
| 8 | Predictive Analytics | `/predictions` | `predictionService.ts` | `predictions_router.py` | ✅ All 5 sub-endpoints (risk-map, high-risk-areas, forecast, emerging-typologies, socioeconomic-correlation) match. Relies on Prophet forecasts having been generated by the scheduler; verify `run_hotspots.py`/scheduled tasks have run before first use or the page will look empty. |
| 9 | Offender Database | `/offenders` | `offenderService.ts` | `offenders_router.py` | ✅ Search/profile/MO/risk/network/create/update all match. Good field-normalization layer for legacy shapes. |
| 10 | Victim Database | `/victims` | `victimService.ts` | `victims_router.py` | ✅ Simple, correctly wired, no mock-fallback risk (this service doesn't use mock data at all — good). |
| 11 | Socio-Economic Insights | `/socioeconomic` | `predictionService.getSocioeconomicData` | `predictions_router.py /socioeconomic-correlation` | ✅ Wired. |
| 12 | Alerts Center | `/alerts` | `alertService.ts` + WebSocket (`App.tsx`) | `alerts_router.py` (`/active`, `/{id}/read`, `/{id}`, `/ws`) | ✅ REST/WS URL & reconnect logic correct (exponential backoff). 🔴 **WebSocket broadcast not district-scoped (§16.1) — District Officers receive alerts outside their jurisdiction.** 🟠 REST `getAlerts()` also never sends `district_id` (§16.2). ⚠️ `markRead`/`dismiss` swallow failures optimistically (§13). ⚠️ Mock fallback on `getAlerts` (§4). |
| 13 | Reports | `/reports` | `reportService.ts` | `reports_router.py` | ✅ Generate/history/download match. Download uses `responseType: 'blob'` correctly. ⚠️ Mock fallback on `getSavedList` (§4). |
| 14 | Settings & Administration | `/settings` | `settingsService.ts` (in `alertService.ts`, §8) + `DataImport.tsx` → `ENDPOINTS.IMPORT.BULK` | `settings_router.py`, `import_router.py` | ✅ Users/districts/alert-thresholds/audit-logs/datasource-sync all match and are correctly role-gated (`require_scrb_officer`). ⚠️ Misplaced module (§8), mock fallback on `getUsers`/`getDistricts` (§4). 🟡 Bulk import defaults orphaned `"KAA_01"` district code (§16.4). 🔵 Import gated on a non-existent `SUPER_ADMIN` role (§16.5) and shown to all roles in the UI regardless (§16.6). |

**Overall backend↔frontend endpoint coverage:** every endpoint defined in `apiEndpoints.ts` has a matching backend route with matching HTTP verb (auth, dashboard, crimes, hotspots, network, offenders, predictions, anomalies, alerts, reports, settings, victims, evidence, assistant, import, search). No dangling frontend calls to non-existent routes were found. The only backend route with no frontend consumer is `GET /evidence/download/{evidence_id}` (§11) and `GET /settings/profile` (§13).

---

## 15. Database Connectivity Summary

| Store | Purpose | Connects from | Verified path |
|---|---|---|---|
| PostgreSQL (+PostGIS) | Primary relational store (crimes, offenders, victims, users, alerts, anomalies, reports) | `app/core/database.py`, async SQLAlchemy | ✅ Correct pooling config. ⚠️ §7 — migrations not actually enforced by app code, only by Docker `CMD`. |
| Neo4j | Criminal network graph | `app/core/neo4j_connection.py` | ⚠️ Connects fine, degrades gracefully when offline (`status: "offline"` surfaced correctly to UI) — but **data written to it is incomplete** (§2), and query results contain duplicates (§3). |
| Redis | Cache, JWT blacklist, Gemini response cache | `app/core/redis_connection.py` | ✅ Graceful degradation if unavailable (non-critical warnings, not hard failures). ⚠️ §9 — needs a fail-fast in prod if unauthenticated. |

---

## 16. Second-pass findings (re-audit)

A deeper re-check of the WebSocket layer, evidence upload persistence, and bulk import path turned up several more issues that weren't in the first pass — including one real cross-district data-leak.

### 16.1 🔴 CRITICAL — Real-time alert WebSocket broadcasts to every connected client, with zero district/role scoping

**Where:** `app/core/websocket.py` + `app/services/alert_service.py`

```python
# app/core/websocket.py
class ConnectionManager:
    async def broadcast(self, data: dict):
        for connection in self.active_connections:      # every socket, no filtering
            await connection.send_text(json.dumps(data))
```

```python
# app/services/alert_service.py — create_alert() and detect_and_generate_alerts()
await manager.broadcast({"type": "NEW_ALERT", "data": alert.to_dict()})
```

Every other read path in this codebase enforces district scoping for `DISTRICT_OFFICER` accounts — `scope_district_filter()` / `scope_district_param()` are used consistently in `crimes_router.py`, `hotspots_router.py`, etc., and `get_active_alerts()` (the REST alerts service) even accepts a `district_id` argument for exactly this purpose. But the WebSocket layer has no concept of "which user is this socket" beyond the JWT used at handshake time (`alerts_router.py`'s `websocket_endpoint` decodes the token just to authenticate the connection, then discards the payload) — every alert, for every district, statewide, is pushed to every connected officer regardless of role. A `DISTRICT_OFFICER` in Mysuru will get real-time push alerts for a crime spike in Kalaburagi that they are explicitly barred from querying via REST.

**Fix:** scope the connection manager by district (and/or role) and filter on broadcast:

```python
# app/core/websocket.py
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, dict] = {}   # ws -> {"district_id": ..., "role": ...}

    async def connect(self, websocket: WebSocket, user: dict):
        await websocket.accept()
        self.active_connections[websocket] = user

    async def broadcast(self, data: dict, target_district: str | None = None):
        dead = []
        for ws, user in self.active_connections.items():
            if target_district and target_district != "ALL" and user.get("role") == "DISTRICT_OFFICER" \
               and user.get("district_id") != target_district:
                continue   # not this officer's district
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
```

```python
# app/routers/alerts_router.py
payload = decode_access_token(token)
...
await manager.connect(websocket, payload)   # pass the decoded user, not just accept blindly
```

```python
# app/services/alert_service.py
await manager.broadcast({"type": "NEW_ALERT", "data": alert.to_dict()}, target_district=alert.district_id)
```

### 16.2 🟠 HIGH — `alertService.getAlerts()` never sends `district_id`, so the REST alerts feed is also unscoped for District Officers

**Where:** `crime_frontend/src/services/alertService.ts`

```ts
getAlerts: async () => {
  try {
    const res = await api.get(ENDPOINTS.ALERTS.LIST);   // no params at all
    ...
```

The backend endpoint fully supports scoping (`GET /alerts/active?district_id=...` → `get_active_alerts(db, district_id)`), and `current_user["district_id"]` is available from the JWT — but nothing on the frontend ever passes it, and the backend route doesn't default it from `current_user` either when the caller omits it:

```python
# alerts_router.py
@router.get("/active")
async def active_alerts(
    district_id: Optional[str] = Query(None),
    ...
    current_user=Depends(get_current_user)
):
    data = await get_active_alerts(db, district_id)   # district_id is None unless the caller passes it
```

**Fix:** default-scope on the backend so it can't be forgotten by any future caller (defense in depth beyond just fixing the frontend call):

```python
@router.get("/active")
async def active_alerts(
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    effective_district = scope_district_param(district_id, current_user)  # same helper used elsewhere
    data = await get_active_alerts(db, effective_district)
    return {"success": True, "data": data}
```

### 16.3 🟠 HIGH — Evidence file uploads are not persisted outside the container — lost on every redeploy/restart

**Where:** `crime_backend/MODULE_2_BACKEND/app/routers/evidence_router.py` + `docker-compose.yml`

```python
UPLOAD_DIR = "app/uploads"
...
filepath = os.path.join(UPLOAD_DIR, filename)
with open(filepath, "wb") as f: ...
```

`docker-compose.yml` mounts named/bind volumes for `postgres`, `neo4j`, and `redis` data directories, but the `backend` service has **no volume at all**:

```yaml
backend:
  build: .
  restart: unless-stopped
  env_file: [.env]
  ports: ["8000:8000"]
  # no `volumes:` entry — app/uploads lives on the container's writable layer
```

Any evidence file (photos, scanned FIRs, audio/video) uploaded through the Crime Map/Crime Database "attachments" tab is written inside the container's ephemeral filesystem. The `Evidence.file_path` row survives in Postgres, but the moment the backend container is rebuilt, redeployed, or rescheduled (routine in any real deployment — CI/CD, autoscaling, `docker compose up --build`), the physical file is gone while the database still references it — `download_evidence()` will then 404 with "Evidence not found" despite an intact-looking database record.

**Fix:** mount a persistent volume for uploads, same pattern as the other stateful services:

```yaml
backend:
  ...
  volumes:
    - ./local_data/uploads:/app/app/uploads
```

For a real multi-instance production deployment, prefer object storage (S3/GCS/Azure Blob) over local disk entirely, since local volumes don't work across replicas.

### 16.4 🟡 MEDIUM — Bulk CSV/JSON import defaults `district_id` to a typo'd, non-existent code

**Where:** `app/services/import_service.py` → `_import_crime()`

```python
district_id=data.get("district_id", "KAA_01"),
```

Every real district code in the system is formatted `KA-01` … `KA-31` (see `KARNATAKA_DISTRICTS` in `config.py`). `"KAA_01"` matches nothing — it isn't even the right prefix (`KAA_` vs `KA-`), so `district_resolver.resolve_district_id()`'s fast path (`district_val.startswith("KA-")`) won't catch it either, and the `ILIKE` fallback search won't find a district named `"KAA_01"`. Any row in a bulk-imported CSV/JSON that omits `district_id` silently gets an orphaned, unresolvable district reference — it will show as `"KAA_01"` (raw, unresolved) in the Crime Map/Crime Database district column instead of a real district name, and will never match any district filter.

**Fix:**
```python
district_id=data.get("district_id") or None,   # let it be NULL rather than a fake code
```
and treat `district_id IS NULL` explicitly in the UI ("Unassigned district") rather than inventing a placeholder that looks like a real code.

### 16.5 🔵 MINOR — `import_router.py` role-gates on a role that doesn't exist anywhere in the system

```python
current_user=Depends(require_role(["SUPER_ADMIN", "SCRB_OFFICER"])),
```

`app/core/config.py` defines `USER_ROLES = ["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"]` — there is no `SUPER_ADMIN` role anywhere in the seed data (`data_seeder.py`), the user model, or the registration/creation path (`create_user` in `auth_service.py`/`settings_router.py`). `"SUPER_ADMIN"` is dead reference text that makes the intended access model look broader than it is. Either implement the role properly or drop it from the check (`require_role(["SCRB_OFFICER"])`).

### 16.6 🔵 MINOR — Bulk Import UI is shown to every authenticated user regardless of role

**Where:** `crime_frontend/src/components/settings/DataImport.tsx`

The component renders unconditionally inside the Settings page for any logged-in user, including `DISTRICT_OFFICER`/`INVESTIGATOR`. The backend correctly 403s them, but the UX is "let them fill out the form, pick a file, click upload, then show a red error banner" instead of hiding/disabling the feature for roles that can never use it. Gate rendering on `user_role === "SCRB_OFFICER"` (the role is already in Redux via `authSlice`).

---

## 17. 🟠 HIGH (UX) — Network graph layout uses fixed spacing that doesn't scale with data size ("All Crime Types" looks clumped/unreadable)

**Where:** `crime_frontend/src/components/network/NetworkGraph.tsx`

**What's wrong:** The Cytoscape `fcose` layout is configured once as a **hardcoded constant**, used for every render regardless of how many nodes/edges are in the graph:

```ts
const LAYOUT_OPTIONS = {
  name: "fcose",
  quality: "default",
  animate: true,
  randomize: true,
  nodeSeparation: 160,
  idealEdgeLength: 220,
  nodeRepulsion: 9000,
  edgeElasticity: 0.35,
  gravity: 0.15,
} as const;
```

...and it's reused unchanged in all three places the layout gets run:

```ts
// initial render
const cy = cytoscape({ container, elements, style, layout: LAYOUT_OPTIONS as any, ... });

// full rebuild (graph shrank / crime-type filter changed)
cy.layout(LAYOUT_OPTIONS as any).run();

// incremental expand (double-click to expand a node)
cy.layout({ ...LAYOUT_OPTIONS, randomize: false, fit: false } as any).run();
```

`nodeSeparation: 160` / `idealEdgeLength: 220` / `nodeRepulsion: 9000` are reasonable for maybe 15–25 nodes. With "All Crimes Lens" selected, `crimeTypeLens` doesn't restrict the node set at all — you get up to `node_limit=100` root nodes from Neo4j (see `get_network_graph()` in `neo4j_connection.py`) plus their expanded neighbors, easily 100–300 nodes/edges. `fcose`'s repulsion/separation forces are tuned for the smaller case, so at high node counts they're nowhere near strong enough to keep nodes apart — hence the clumped, unreadable ball of nodes you're seeing. There's also no `nodeDimensionsIncludeLabels` setting, so the physics simulation treats each node as just its circle (20–80px) and ignores the label text width/height entirely, which is why labels overlap each other even where the nodes themselves have a bit of room.

**Fix:** replace the static constant with a function that derives layout parameters from the current node/edge count, and call it fresh every time a layout runs instead of reusing one frozen object. More nodes → proportionally more separation, edge length, and repulsion; fewer nodes → tighter, faster-settling layout instead of the graph looking unnecessarily sparse.

```ts
// crime_frontend/src/components/network/NetworkGraph.tsx

/**
 * Builds fcose layout options scaled to the current graph size, so a
 * 10-node graph stays compact and readable while a 200-node graph
 * (e.g. "All Crimes Lens") gets enough breathing room to stay legible.
 */
const getDynamicLayoutOptions = (nodeCount: number, edgeCount: number) => {
  // sqrt growth: spacing increases with size but doesn't explode for very large graphs
  const scale = 1 + Math.sqrt(Math.max(nodeCount, 1)) / 6;

  // denser graphs (higher avg degree) need extra edge length so crossing
  // edges don't visually merge with their neighbours
  const avgDegree = nodeCount > 0 ? (edgeCount * 2) / nodeCount : 0;
  const densityFactor = 1 + Math.min(avgDegree / 6, 1) * 0.4;

  const isLarge = nodeCount > 150;

  return {
    name: "fcose",
    quality: isLarge ? "draft" : "default",   // "draft" trades a little precision for speed on big graphs
    animate: !isLarge,                         // skip the settle animation above ~150 nodes (perf)
    randomize: true,
    nodeDimensionsIncludeLabels: true,          // labels are treated as part of node size, so they stop overlapping
    packComponents: true,                       // disconnected clusters get packed neatly instead of scattering
    nodeSeparation: Math.min(600, Math.round(160 * scale)),
    idealEdgeLength: Math.min(520, Math.round(220 * scale * densityFactor)),
    nodeRepulsion: Math.min(60000, Math.round(9000 * scale * scale)),
    edgeElasticity: 0.35,
    gravity: Math.max(0.02, 0.15 / scale),      // relax gravity as the graph grows so it can spread out
    numIter: isLarge ? 1500 : 2500,
    tile: true,
  } as any;
};
```

Then swap every usage of the old constant for a call to this function with the *current* node/edge counts:

```ts
// initial render
if (!cyRef.current) {
  const cy = cytoscape({
    container: containerRef.current,
    elements: buildElements(nodes, edges),
    style: styleSheet,
    layout: getDynamicLayoutOptions(nodes.length, edges.length),
    minZoom: 0.2,
    maxZoom: 3,
  });
  ...
}
```

```ts
// full rebuild branch
if (currentIds.size < existingIds.size) {
  cy.elements().remove();
  cy.add(buildElements(nodes, edges));
  cy.layout(getDynamicLayoutOptions(nodes.length, edges.length)).run();
} else {
  // incremental expand — recompute against the *post-expand* totals, not the old constant
  cy.add(buildElements(newNodes, newEdges));
  const totalNodes = cy.nodes().length;
  const totalEdges = cy.edges().length;
  cy.layout({
    ...getDynamicLayoutOptions(totalNodes, totalEdges),
    randomize: false,
    fit: false,
  }).run();
}
```

**Optional companion fix — visual crowding when "All Crimes Lens" is active:** even with better spacing, 200+ nodes on screen at once is inherently harder to scan. Consider softening (not hiding) the non-relevant nodes so the eye is drawn to what matters, similar to what `crimeTypeLens` already does for edges:

```ts
// styleSheet — add alongside the existing ".lens-dimmed" selector
{
  selector: "node.lens-dimmed",
  style: { "font-size": "8px" },   // shrink dimmed labels a bit further to reduce label clutter at high node counts
},
```

and, in `CriminalNetwork.tsx`, consider defaulting `showIsolated` to `false` (it currently defaults to `false` already — good) and surfacing a lightweight node-count indicator near the "Highlight Key Players" button so officers understand *why* the graph looks denser after clearing filters, e.g.:

```tsx
<span className="text-xs text-slate-500 ml-2">{filteredNodes.length} nodes • {edges.length} connections</span>
```

---

## 18. Priority Fix Order (suggested)

1. §16.1 — WebSocket alert broadcast leaks all-district alerts to `DISTRICT_OFFICER` accounts (real access-control gap)
2. §2 — Neo4j sync missing `district_id`/`crime_types` (breaks the feature you specifically flagged)
3. §16.3 — Evidence uploads have no persistent volume (silent data loss on redeploy)
4. §3 — Duplicate edges in network graph
5. §17 — Network graph layout spacing is static and doesn't scale with node count (clumped/unreadable at high data volumes)
6. §16.2 — REST alerts feed also unscoped by district (defense-in-depth fix alongside #1)
7. §4 — Remove unconditional mock-data fallbacks on the success path (data-integrity/trust issue)
8. §5 — Standardize response envelope shape
9. §7 — Make `init_db()` fail loudly instead of silently degrading
10. §9 — Redis/Postgres/Neo4j port exposure + password fail-fast for prod
11. §16.4 — Fix `"KAA_01"` typo default in bulk import
12. §6, §8, §10, §11, §12, §13, §16.5, §16.6 — cleanup, in any order

---

*This report reflects the code as of the uploaded `SHASTRA-main.zip`. No code was modified — all fixes above are suggested snippets for you to apply.*