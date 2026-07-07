# SHASTRA Crime Intelligence Platform — Full Codebase Audit

**Scope:** Complete backend (`crime_backend/MODULE_2_BACKEND`, FastAPI + PostgreSQL + Neo4j + Redis + Gemini) and frontend (`crime_frontend`, React + TS + Vite + Cytoscape) review. Special focus on the **Criminal Network / Link Analysis** feature (graph, matrix, filters).

This document lists every gap found — broken/missing connections, dead endpoints, filter issues, data-shape mismatches — with the exact file/line context and a ready-to-apply code fix. You do not need to apply anything; just copy the snippets into the referenced files.

---

## 0. How the app is wired (for reference)

- Backend: `main.py` registers 16 routers under `/api/*` (auth, dashboard, crimes, hotspots, network, offenders, predictions, anomalies, alerts, reports, settings, victims, import, search, evidence, assistant). All routers ARE registered correctly — no router is missing from `main.py`.
- Frontend: `src/constants/apiEndpoints.ts` centralizes most paths; a few services (`victimService.ts`, `evidenceService.ts`, `AIChatWidget.tsx`, `DataImport.tsx`) call `api.<verb>('/hardcoded/path')` directly instead of using the constants file. Functionally these all resolve correctly today, but it's an inconsistency (see §5).
- Axios response interceptor (`services/api.ts`) auto-unwraps `{success, data}` envelopes into just the `data` payload when there's no extra metadata key. This is important context — several services access `res.data` expecting the *unwrapped* inner object, which works only because of this interceptor. Keep this in mind if you ever add a response key alongside `success`/`data`/`message` — it will silently stop being unwrapped.

---

## 1. CRITICAL — Criminal Network / Link Analysis feature

This was checked in the most depth per your request. Summary table first, details + fixes after.

| # | Item | Status | Severity |
|---|------|--------|----------|
| 1.1 | District filter for network graph | Backend supports it, **frontend never sends it** | High |
| 1.2 | Crime-type filter for network graph | Backend supports it, **frontend never sends it** (only a client-side visual "lens" exists) | High |
| 1.3 | Postgres-fallback graph: **Location nodes have zero edges** | Bug — orphaned nodes whenever Neo4j is offline | High |
| 1.4 | Postgres-fallback graph: **Organization node type unsupported** | Missing — `node_type=organization` silently returns empty | High |
| 1.5 | Postgres-fallback graph: **offender↔offender associate edges can be dropped** depending on row order | Bug | Medium |
| 1.6 | `GET /offenders/{id}/network` endpoint | **Fully implemented on backend, never called from frontend** | Medium |
| 1.7 | Backend node `color` field ignored by frontend | Cosmetic mismatch (backend sends `#a855f7` for orgs, frontend legend uses `#F59E0B`) | Low |
| 1.8 | `crimeTypeLens` never triggers a network refetch | By design, but worth confirming | Info |

### 1.1 / 1.2 — District & crime-type filters not wired from the Network page

**Where:** `crime_frontend/src/pages/CriminalNetwork.tsx`

```tsx
// CURRENT (both effects only ever pass `undefined` for crimeType & districtId):
const [g, ai] = await Promise.all([
  networkService.getGraphData(searchQuery || undefined, undefined, undefined, nodeTypeFilter === "all" ? undefined : nodeTypeFilter),
  networkService.getAiSummary(undefined),
]);
```

The backend (`network_router.py` → `fetch_network_graph`) fully supports `crime_type` and `district_id` query params, and `get_network_ai_summary` supports `district_id` too — but the UI never exposes controls for them, so this backend capability is dead weight and the network view can't be scoped to a district or a specific crime type server-side (only the local visual "lens" dims edges client-side, it doesn't refetch).

**Fix — add the missing UI controls and thread the values through:**

```tsx
// 1. Add state near your other filters
const [districtFilter, setDistrictFilter] = useState<string | undefined>(undefined);
const [crimeTypeFilter, setCrimeTypeFilter] = useState<string | undefined>(undefined);

// 2. Update both fetch effects to pass them through
const [g, ai] = await Promise.all([
  networkService.getGraphData(
    searchQuery || undefined,
    crimeTypeFilter,
    districtFilter,
    nodeTypeFilter === "all" ? undefined : nodeTypeFilter
  ),
  networkService.getAiSummary(districtFilter),
]);

// ...and in the debounced search effect:
const g = await networkService.getGraphData(
  searchQuery || undefined,
  crimeTypeFilter,
  districtFilter,
  nodeTypeFilter === "all" ? undefined : nodeTypeFilter,
  { signal: controller.signal }
);

// 3. Don't forget to add districtFilter/crimeTypeFilter to the effect dependency arrays:
}, [searchQuery, nodeTypeFilter, districtFilter, crimeTypeFilter]);

// 4. Add a district dropdown + crime-type dropdown to the toolbar JSX
// (reuse settingsService.getDistricts() — see §2 below — instead of the
// hardcoded KARNATAKA_DISTRICTS list, since the backend already resolves names -> ids)
<select
  value={districtFilter || ""}
  onChange={(e) => setDistrictFilter(e.target.value || undefined)}
  className="bg-slate-800 border border-slate-700 text-slate-300 text-xs rounded-lg px-2 py-1 outline-none"
>
  <option value="">All Districts</option>
  {districts.map((d) => (
    <option key={d.district_id} value={d.district_id}>{d.district_name}</option>
  ))}
</select>
```

### 1.3 — Postgres fallback: Location nodes are always isolated (no edges)

**Where:** `crime_backend/MODULE_2_BACKEND/app/services/network_service.py` → `build_network_from_postgres()`

When Neo4j is offline (which the app is designed to tolerate — "continuing in degraded mode"), the graph is rebuilt from PostgreSQL. Criminals get `KNOWS` edges from `known_associates`, and Victims get `VICTIMIZED_AT` edges from crime links — but **Locations never get any edge created**, so every location node renders as a disconnected dot, and the "Show Isolated / Hide Isolated" toggle in the UI will always hide them by default.

**Fix — link locations to the crimes/offenders that occurred there.** This assumes `Crime` has a `location_id` FK (check `crime_model.py`; if the field name differs, adjust accordingly):

```python
# --- Locations --- (inside build_network_from_postgres, replace the existing block)
if node_type in (None, "location"):
    lq = select(Location).limit(per_type_limit)
    if district_id:
        lq = lq.where(Location.district_id == district_id)
    if search_query:
        lq = lq.where(Location.address.ilike(f"%{search_query}%"))

    l_result = await db.execute(lq)
    locations = l_result.scalars().all()
    location_ids_in_graph = set()
    for l in locations:
        nodes.append({
            "node_id": str(l.location_id),
            "node_type": "location",
            "label": l.address,
            "risk_score": 0,
            "crime_count": 0,
            "size": 25,
            "color": "#a855f7",
            "profile_data": {"district_id": l.district_id},
        })
        location_ids_in_graph.add(str(l.location_id))

    # NEW: connect locations to offenders via crimes that happened there
    if location_ids_in_graph:
        crime_q = select(Crime).where(Crime.location_id.in_(location_ids_in_graph))
        crimes_at_locations = (await db.execute(crime_q)).scalars().all()
        crime_ids_by_location = {}
        for c in crimes_at_locations:
            crime_ids_by_location.setdefault(str(c.location_id), []).append(c.crime_id)

        existing_offender_ids = {n["node_id"] for n in nodes if n["node_type"] == "criminal"}
        for loc_id, crime_ids in crime_ids_by_location.items():
            link_q = select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id.in_(crime_ids))
            offender_links = (await db.execute(link_q)).scalars().all()
            for ol in offender_links:
                offender_id = str(ol.offender_id)
                if offender_id in existing_offender_ids:
                    edges.append({
                        "edge_id": f"{offender_id}_{loc_id}",
                        "source_node_id": offender_id,
                        "target_node_id": loc_id,
                        "relationship_type": "FREQUENTED",
                        "strength_score": 55,
                        "confidence_level": "SUSPECTED",
                        "crime_types": [],
                    })
```

> If `Crime` doesn't have `location_id` directly (e.g. it stores lat/lng only), you'll need to join through whatever table actually links a `Crime` to a `Location`. Check `app/models/database_models/crime_model.py` and `location_model.py` for the real relationship before applying this patch.

### 1.4 — Postgres fallback: "organization" node type is unsupported

**Where:** same file, `build_network_from_postgres()`

The function only has `if node_type in (None, "criminal")`, `(None, "victim")`, `(None, "location")` blocks. There's no `Organization` model query at all. On the frontend, `CriminalNetwork.tsx` has a fully working "Orgs" filter button (`nodeTypeFilter = "organization"`) and the legend shows an organization color swatch — but selecting it will always return an empty graph whenever Neo4j is down, silently.

**Fix — options, pick based on whether you actually have an `Organization` model:**

**Option A** — if an `Organization` DB model exists (check `app/models/database_models/`) but wasn't wired in here, add a block mirroring the Location one:

```python
if node_type in (None, "organization"):
    from app.models.database_models.organization_model import Organization  # adjust import if named differently
    oq = select(Organization).limit(per_type_limit)
    if district_id:
        oq = oq.where(Organization.district_id == district_id)
    if search_query:
        oq = oq.where(Organization.name.ilike(f"%{search_query}%"))
    o_result = await db.execute(oq)
    orgs = o_result.scalars().all()
    for org in orgs:
        nodes.append({
            "node_id": str(org.org_id),
            "node_type": "organization",
            "label": org.name,
            "risk_score": org.risk_score or 0,
            "crime_count": 0,
            "size": 22,
            "color": "#a855f7",
            "profile_data": {"org_type": org.org_type, "district_id": org.district_id},
        })
    # add edges from offenders -> orgs if you track that relationship, e.g. via a join table
```

**Option B** — if there is genuinely no `Organization` model in Postgres (only in Neo4j), then at minimum make the frontend honest about the limitation instead of showing an empty graph silently:

```python
# at the top of build_network_from_postgres, after building nodes/edges:
if node_type == "organization" and not nodes:
    return {
        "nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0,
        "network_density": 0, "key_players": [],
        "warning": "Organization entities are only available when Neo4j is connected.",
    }
```
```tsx
// CriminalNetwork.tsx — show the warning if present
if (g.warning) setErrorMessage(g.warning); // surface via a small banner near the toolbar
```

### 1.5 — Offender↔offender "KNOWS" edges can be silently dropped

**Where:** `network_service.py` → `build_network_from_postgres()`, criminals block:

```python
if offender.known_associates:
    current_node_ids = {n["node_id"] for n in nodes}   # <-- only nodes processed so far
    for associate_id in offender.known_associates:
        if associate_id in current_node_ids:
            edges.append({...})
```

`current_node_ids` is recomputed **inside the offender loop**, so it only contains nodes added *up to and including the current offender*. If offender A's associate is offender B, but B appears **later** in the query result set, the edge is silently skipped. Whether an edge shows up becomes dependent on arbitrary DB row order — a real bug, not just a stylistic one.

**Fix — do a second pass after all offenders are loaded:**

```python
# --- Criminals --- (build the node list first WITHOUT creating edges inline)
offender_node_ids = set()
offender_associate_map = {}  # node_id -> known_associates list

for offender in offenders:
    node_id = str(offender.offender_id)
    color_map = {"HIGH": "#ef4444", "MEDIUM": "#f97316", "LOW": "#22c55e"}
    color = color_map.get(offender.risk_level, "#6b7280")

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
        },
    })
    offender_node_ids.add(node_id)
    if offender.known_associates:
        offender_associate_map[node_id] = offender.known_associates

# AFTER the loop — now every offender node exists, so no edge is missed regardless of row order
seen_pairs = set()
for node_id, associates in offender_associate_map.items():
    for associate_id in associates:
        if associate_id in offender_node_ids:
            pair_key = tuple(sorted([node_id, associate_id]))
            if pair_key in seen_pairs:
                continue  # avoid duplicate edges when both sides list each other
            seen_pairs.add(pair_key)
            edges.append({
                "edge_id": f"{node_id}_{associate_id}",
                "source_node_id": node_id,
                "target_node_id": associate_id,
                "relationship_type": "KNOWS",
                "strength_score": 60,
                "confidence_level": "SUSPECTED",
                "crime_types": [],
            })
```

### 1.6 — `GET /offenders/{id}/network` is implemented but never called

**Backend:** `offenders_router.py`
```python
@router.get("/{offender_id}/network")
async def network(offender_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    data = await get_offender_network(db, offender_id)
    return {"success": True, "data": data}
```
`get_offender_network` is fully implemented in `offender_service.py`.

**Frontend:** `constants/apiEndpoints.ts` even has the constant defined:
```ts
NETWORK: (id: string) => `/offenders/${id}/network`,
```
…but grep across the entire `crime_frontend/src` shows **zero usages** of `ENDPOINTS.OFFENDERS.NETWORK`. `OffenderDatabase.tsx` has no "View Network" button and no mini-graph panel — this looks like a feature that was built end-to-end on the backend and then never surfaced in the UI.

**Fix — add the missing service call + a button/panel on the offender profile:**

```ts
// services/offenderService.ts — add:
getNetwork: async (id: string) => {
  try {
    const res = await api.get(ENDPOINTS.OFFENDERS.NETWORK(id));
    return res.data; // { nodes, edges, ... } after interceptor unwrap
  } catch {
    return null;
  }
},
```

```tsx
// pages/OffenderDatabase.tsx — inside the offender detail panel, add a button:
<button
  onClick={() => navigate(`/network?focus=${selectedOffender.offender_id}`)}
  className="mt-3 w-full text-xs px-3 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium"
>
  View in Criminal Network →
</button>

// Then in pages/CriminalNetwork.tsx, read the `focus` query param on mount and call
// networkService.getNodeDetail(focusId) + graphRef.current?.focusOnNode(focusId)
// OR call offenderService.getNetwork(id) directly to render a scoped ego-network
// without leaving the offender page — either approach closes this gap.
```

### 1.7 — Backend `color` field on nodes is computed but ignored by the frontend

`network_service.py` / `neo4j_connection.py::normalize_node()` set `color: "#a855f7"` for organizations, but `NetworkGraph.tsx`'s Cytoscape stylesheet computes color purely from `community_id` (falling back to the **frontend's own** `NODE_COLORS` map, which uses `#F59E0B` for organizations — different from the backend's `#a855f7`). Not breaking anything (frontend wins), but it's redundant/inconsistent data. Two options:

```ts
// Option A (recommended) — make frontend and backend agree, in constants/colorCodes.ts:
export const NODE_COLORS: Record<string, string> = {
  criminal: "#EF4444",
  victim: "#3b82f6",
  location: "#22c55e",   // was #22C55E, matches backend
  organization: "#a855f7", // was #F59E0B, now matches backend's normalize_node()
};
```
```python
# Option B — instead, stop computing `color` server-side since it's unused, to reduce payload size:
# (remove the "color": color lines in network_service.py / neo4j_connection.py normalize_node())
```

---

## 2. Settings page — dead / unwired backend endpoints

| Endpoint | Backend file | Called from frontend? |
|---|---|---|
| `POST /api/settings/datasources/{source_id}/sync` | `settings_router.py:23` | **No** — no "Sync" button anywhere |
| `GET /api/settings/profile` | `settings_router.py:13` | **No** — no profile screen consumes it |
| `GET /api/settings/districts` | `settings_router.py:107` | **No** — `settingsService.getDistricts()` exists but is never invoked; every district dropdown in the app uses the hardcoded `constants/districtsList.ts` list instead |

### 2.1 — Wire up "Sync" for data sources

**Where:** `pages/SettingsPage.tsx`, Data Sources tab currently only *displays* status pulled from `/health`, it doesn't hit `/settings/datasources/{id}/sync` at all, so users can never trigger a manual resync even though the backend supports it.

```tsx
// services/alertService.ts — add to settingsService:
syncDataSource: async (sourceId: string) => {
  try {
    const res = await api.post(`/settings/datasources/${sourceId}/sync`);
    return res.data;
  } catch (error) {
    console.error(error);
    return { success: false };
  }
},
```

```tsx
// pages/SettingsPage.tsx — Data Sources tab, add a Sync button per row:
{(Array.isArray(dataSources) ? dataSources : []).map((ds, i) => (
  <div key={i} className="flex items-center justify-between p-3 bg-slate-900/60 rounded-lg border border-slate-700/50">
    <div>
      <p className="text-sm text-white">{ds.name || ds.source_name}</p>
      <p className="text-xs text-slate-400">{ds.type || 'Database'} · Last sync: {ds.last_sync}</p>
    </div>
    <div className="flex items-center gap-2">
      <span className={`text-xs px-2 py-0.5 rounded-full ${ds.status === "Active" || ds.status === "Connected" ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"}`}>
        {ds.status}
      </span>
      {ds.source_id && (
        <button
          onClick={async () => { await settingsService.syncDataSource(ds.source_id); /* refetch list */ }}
          className="text-xs px-2 py-1 bg-blue-600/20 text-blue-400 rounded hover:bg-blue-600/30"
        >
          Sync
        </button>
      )}
    </div>
  </div>
))}
```
> Note: `settingsService.getDataSources()` currently synthesizes its list from `GET /health` (Postgres/Redis/Neo4j/Gemini) — those aren't real "data sources" with a `source_id` that `sync_datasource()` expects. If you want the Sync button to be meaningful, either (a) add a real `GET /settings/datasources` list endpoint backed by an actual data-sources table, or (b) drop the Sync button and keep `/health` purely informational. Right now the two are mismatched: the sync endpoint expects `source_id`s that the current UI list doesn't have.

### 2.2 — Use the real districts endpoint instead of the hardcoded list

Every district dropdown (`MapControls.tsx`, `ReportsPage.tsx`, `CrimeDatabase.tsx`, `HotspotAnalysis.tsx`) imports `KARNATAKA_DISTRICTS` from a static constants file. Meanwhile `GET /api/settings/districts` returns the live list from Postgres (with actual `district_id`s), and `settingsService.getDistricts()` already exists to call it — it's just not used anywhere. This means if districts are ever added/renamed in the DB, the UI won't reflect it, and filters silently send district *names* instead of resolvable `district_id`s (works today only because `resolve_district_id()` does fuzzy name matching as a safety net — see backend `district_resolver.py`).

**Fix — replace the static import with a fetched list in a shared hook:**

```ts
// hooks/useDistricts.ts (new file)
import { useEffect, useState } from "react";
import { settingsService } from "../services/alertService";

export function useDistricts() {
  const [districts, setDistricts] = useState<{ district_id: string; district_name: string }[]>([]);
  useEffect(() => {
    settingsService.getDistricts().then((d) => setDistricts(Array.isArray(d) ? d : []));
  }, []);
  return districts;
}
```

```tsx
// e.g. MapControls.tsx — replace:
import { KARNATAKA_DISTRICTS } from "../../constants/districtsList";
// ...
{KARNATAKA_DISTRICTS.map((d) => <option key={d}>{d}</option>)}

// with:
import { useDistricts } from "../../hooks/useDistricts";
// ...
const districts = useDistricts();
// ...
<option value="">All Districts</option>
{districts.map((d) => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}
```
> Apply the same swap in `ReportsPage.tsx`, `CrimeDatabase.tsx`, `HotspotAnalysis.tsx`, and the network filter you're adding in §1.1.

---

## 3. Alerts — dismiss endpoint is dead

**Backend:** `alerts_router.py`
```python
@router.delete("/{alert_id}")
async def dismiss(alert_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    data = await dismiss_alert(db, alert_id)
    return {"success": True, "data": data}
```
Fully implemented (`dismiss_alert` exists in `alert_service.py`), but `alertService.ts` only exposes `getAlerts` and `markRead` — there's no `dismiss`/`delete` function, and `AlertsPage.tsx` / `AlertsTable.tsx` have no dismiss button.

**Fix:**
```ts
// services/alertService.ts — add:
dismiss: async (id: string) => {
  try {
    const res = await api.delete(ENDPOINTS.ALERTS.MARK_READ(id).replace('/read', '')); // or add a DISMISS constant, see below
    return res.data;
  } catch {
    return { success: false };
  }
},
```
```ts
// constants/apiEndpoints.ts — cleaner: add a proper constant instead of string-mangling above
ALERTS: {
  LIST: "/alerts/active",
  MARK_READ: (id: string) => `/alerts/${id}/read`,
  DISMISS: (id: string) => `/alerts/${id}`,   // NEW
},
```
```tsx
// components/tables/AlertsTable.tsx — add a dismiss button per row, wired to:
// onDismiss={(id) => alertService.dismiss(id).then(() => /* remove from redux state */)}
```

---

## 4. Everything that IS wired correctly (verified — no action needed)

To be clear about what's healthy, these were checked line-by-line and are working:

- All 16 routers registered in `main.py`, CORS/security headers/rate limiting configured correctly.
- `auth` (login/logout/verify-token) ↔ `authService.ts` — correct.
- `dashboard` (summary/recent-crimes/recent-alerts/crime-trends) ↔ `crimeService.ts` — correct, with sensible fallbacks.
- `crimes` (map-data/filter/detail/CRUD/status) ↔ `crimeService.ts` — correct.
- `hotspots` (clusters/time-patterns/top-list/deployment-suggestions) ↔ `crimeService.ts` — correct, including CSV export support server-side (`file_format=csv` on `/clusters` — confirm this is surfaced somewhere in `HotspotAnalysis.tsx`'s export button if you have one).
- `evidence` (list/upload/download) ↔ `evidenceService.ts` — correct.
- `predictions` + `anomalies` ↔ `predictionService.ts` / `anomalyService.ts` — correct.
- `reports` (generate/history/download) ↔ `reportService` in `alertService.ts` — correct.
- `import` (`/import/bulk`) ↔ `DataImport.tsx` — correct, response shape matches (`total`/`successful`/`failed`/`errors`).
- `assistant` (`/assistant/ask`) ↔ `AIChatWidget.tsx` — correct.
- `search` (`/search/global`) ↔ `Navbar.tsx` — correct (relies on the axios auto-unwrap interceptor, confirmed working).
- WebSocket alerts (`/api/alerts/ws`) — backend `ConnectionManager.broadcast()` is actually invoked from `alert_service.py` (twice — once for auto-generated alerts, once elsewhere), and `App.tsx` has a real reconnecting WebSocket client with exponential backoff. This is properly wired end-to-end.
- `victims` (search/profile/register) ↔ `victimService.ts` — correct (uses hardcoded paths but they resolve correctly).

---

## 5. Minor / stylistic issues (not breaking, but worth cleaning up)

1. **Inconsistent endpoint sourcing.** `victimService.ts`, `evidenceService.ts`, `AIChatWidget.tsx`, and `DataImport.tsx` all call `api.get('/hardcoded/path')` instead of going through `constants/apiEndpoints.ts`. Functionally fine today, but if the API base path or a route ever changes, these won't get updated by a global find-in-`ENDPOINTS`. Recommend consolidating:
   ```ts
   // constants/apiEndpoints.ts — add:
   VICTIMS: {
     SEARCH: "/victims/search",
     PROFILE: (id: string) => `/victims/${id}/profile`,
     REGISTER: "/victims",
   },
   EVIDENCE: {
     LIST: (crimeId: string) => `/evidence/${crimeId}`,
     UPLOAD: (crimeId: string) => `/evidence/${crimeId}`,
   },
   ASSISTANT: { ASK: "/assistant/ask" },
   IMPORT: { BULK: "/import/bulk" },
   ```
   Then update the 4 files above to import and use these instead of raw strings.

2. **`crimeService.update` / `updateStatus` / `remove`** in `crimeService.ts` use raw template strings (`` `/crimes/${id}` ``) instead of `ENDPOINTS.CRIMES.DETAIL`-style helpers — same category as #1, add `ENDPOINTS.CRIMES.UPDATE`, `.UPDATE_STATUS`, `.DELETE` for consistency.

3. **`settingsService.getAuditLogs()`** does `ENDPOINTS.SETTINGS.AUDIT_LOGS || '/settings/audit-logs'` — the `||` fallback is dead code since the constant is always defined; harmless but can be simplified to just `ENDPOINTS.SETTINGS.AUDIT_LOGS`.

---

## 6. Suggested priority order to fix

1. §1.3 and §1.4 (Postgres-fallback graph gaps) — these directly affect what you asked about most: the network graph will visibly misbehave (isolated locations, empty org filter) any time Neo4j is down, which per your own `docker-compose.yml`/lifespan logic is an explicitly supported "degraded mode," not a rare edge case.
2. §1.5 (associate-edge ordering bug) — silent data loss, hard to notice without this audit.
3. §1.1/1.2 (network district & crime-type filters) — restores parameters your backend already computed for.
4. §1.6 (offender mini-network) and §3 (alert dismiss) — finish features that are half-built.
5. §2 (settings dead endpoints / hardcoded districts) — mostly a data-integrity/consistency improvement.
6. §5 — cleanup, do whenever convenient.

---

*End of report.*