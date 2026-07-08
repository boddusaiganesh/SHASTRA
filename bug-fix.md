# SHASTRA Platform — Deep Audit Report
**Scope:** Full backend (`crime_backend/MODULE_2_BACKEND`) + frontend (`crime_frontend`), with special focus on the **Criminal Network / Link Analysis** module.
**Method:** Static trace of every router ↔ service ↔ frontend-service ↔ page/component pairing, plus response-shape verification against the global Axios interceptor.

---

## 0. How the app's response envelope works (read this first)

Every backend endpoint returns:
```json
{ "success": true, "data": { ... } }
```
and `crime_frontend/src/services/api.ts` has a response interceptor that **auto‑unwraps** `response.data` → `response.data.data`, but **only if the top-level keys are a subset of `['success','data','message']`**:

```ts
// crime_frontend/src/services/api.ts (lines 21-33)
api.interceptors.response.use((response) => {
  if (response.data && response.data.success !== undefined && response.data.data !== undefined) {
    const keys = Object.keys(response.data);
    const hasMetadata = keys.some(k => !['success', 'data', 'message'].includes(k));
    if (!hasMetadata) {
      return { ...response, data: response.data.data };   // unwrapped
    }
    return response;                                       // NOT unwrapped
  }
  return response;
});
```

This single rule is the root cause of **two** of the bugs below. Any endpoint that returns extra top-level keys (`total_count`, `limit`, etc.) is **not** unwrapped, and any service function that assumes it always is (or always isn't) will silently break. Keep this in mind — it's the #1 thing to check whenever a page shows blank/stale data.

---

## 1. CRITICAL — Network Graph: "Connection Insight" (AI edge insight) is permanently broken

**Where:** `crime_frontend/src/services/networkService.ts`, `getEdgeInsight()`

**What happens:** Clicking an edge in the graph triggers a Gemini-generated relationship insight. It always shows **"No insight available."**

**Root cause:** Backend `POST /api/network/edge-insight` returns exactly `{"success": true, "data": {"insight": "..."}}` — only `success` + `data` keys, so the Axios interceptor **already unwraps it**. `response.data` is therefore `{"insight": "..."}`. But the service code unwraps it **a second time**:

```ts
// crime_frontend/src/services/networkService.ts (line ~67-75) — BUGGY
getEdgeInsight: async (nodeA: any, nodeB: any, edge: any) => {
  try {
    const response = await api.post(ENDPOINTS.NETWORK.EDGE_INSIGHT, { node_a: nodeA, node_b: nodeB, edge });
    return response.data?.data?.insight ?? null;   // ❌ response.data is already {insight}, so .data is undefined
  } catch (error) {
    console.error("Error fetching edge insight:", error);
    return null;
  }
},
```

**Fix:**
```ts
getEdgeInsight: async (nodeA: any, nodeB: any, edge: any) => {
  try {
    const response = await api.post(ENDPOINTS.NETWORK.EDGE_INSIGHT, { node_a: nodeA, node_b: nodeB, edge });
    return response.data?.insight ?? null;   // ✅ single unwrap, matches interceptor behavior
  } catch (error) {
    console.error("Error fetching edge insight:", error);
    return null;
  }
},
```

**Backend file involved (no change needed, included for reference):** `app/routers/network_router.py` lines 147-156 (`edge-insight` endpoint) — confirmed it returns the standard 2-key envelope, so this is purely a frontend fix.

---

## 2. Network Graph: "AI Network Analysis" panel ignores the Crime-Type Lens filter

**Where:** `crime_backend/MODULE_2_BACKEND/app/routers/network_router.py` (`/ai-summary`) and `app/services/network_service.py` (`get_network_ai_summary`)

**What happens:** The UI's "Crimes Lens" dropdown is sent to the backend as `crime_type`, but the AI summary text, key findings, and suspicious-pairs list **never change** when you switch the lens — only the graph itself filters.

**Root cause:** The frontend sends `crime_type`, but the router doesn't declare or forward that parameter, even though the service function underneath was clearly built to accept it (`focus_area`) and just never gets it:

```ts
// crime_frontend/src/pages/CriminalNetwork.tsx (lines 83-86) — sends crime_type
networkService.getAiSummary(
  districtFilter === "all" ? undefined : districtFilter,
  crimeTypeLens === "all" ? undefined : crimeTypeLens
),
```
```ts
// crime_frontend/src/services/networkService.ts (line 57-65)
getAiSummary: async (districtId?: string, crimeType?: string) => {
  const response = await api.get(ENDPOINTS.NETWORK.AI_SUMMARY, {
    params: { district_id: districtId, crime_type: crimeType }   // crime_type sent...
  });
  ...
}
```
```python
# app/routers/network_router.py (lines 44-55) — crime_type never declared, so FastAPI drops it silently
@router.get("/ai-summary")
async def fetch_ai_summary(
    request: Request,
    district_id: Optional[str] = Query(None),   # ❌ no crime_type param
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_ai_summary(db, resolved_id)   # ❌ focus_area never passed
    return {"success": True, "data": data}
```
```python
# app/services/network_service.py (line 411) — focus_area exists but is always None from the router
async def get_network_ai_summary(
    db: AsyncSession,
    district_id: Optional[str] = None,
    focus_area: Optional[str] = None,   # <-- dead parameter, nothing ever supplies it
) -> Dict[str, Any]:
```

**Fix (router):**
```python
@router.get("/ai-summary")
@limiter.limit("5/minute")
async def fetch_ai_summary(
    request: Request,
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),          # ✅ add this
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_ai_summary(db, resolved_id, focus_area=crime_type)   # ✅ forward it
    return {"success": True, "data": data}
```

**Also update the cache key and the offender filter** in `get_network_ai_summary` (`app/services/network_service.py`) so results actually differ per crime type — currently `focus_area` isn't used anywhere in the query even if passed in:
```python
async def get_network_ai_summary(
    db: AsyncSession,
    district_id: Optional[str] = None,
    focus_area: Optional[str] = None,
) -> Dict[str, Any]:
    from app.services.gemini_service import get_network_analysis_summary

    cache_key = f"network_ai_summary:{district_id}:{focus_area}"   # already keyed correctly once focus_area is real
    cached = await cache_get(cache_key)
    if cached:
        return cached

    offender_query = select(Offender).where(Offender.total_crimes > 1)
    if district_id:
        offender_query = offender_query.where(Offender.district_id == district_id)
    if focus_area:                                                  # ✅ add this filter
        offender_query = (
            offender_query.join(CrimeOffenderLink).join(Crime)
            .where(Crime.crime_type == focus_area).distinct()
        )
    ...
```
(Add the necessary imports for `CrimeOffenderLink`/`Crime` at the top of the function, mirroring the pattern already used in `build_network_from_postgres`.)

---

## 3. Network Graph: Node-detail lookup only works for Criminal nodes

**Where:** `app/services/network_service.py` → `get_node_detail()`

**What happens:** Clicking a **Victim**, **Location**, or **Organization** node in the graph shows only the bare data already present in the graph payload (label, risk score, raw `profile_data`). It never gets the enriched detail (AI profile analysis, crime timeline, "Open Full Record" behavior) that Criminal nodes get — and the backend call for it silently 404s every time for non-criminal node types.

**Root cause:**
```python
# app/services/network_service.py (lines 350-364)
async def get_node_detail(db: AsyncSession, node_id: str) -> Optional[Dict[str, Any]]:
    from app.services.gemini_service import get_offender_ai_analysis
    try:
        import uuid
        offender_uuid = uuid.UUID(node_id)
        result = await db.execute(
            select(Offender).where(Offender.offender_id == offender_uuid)   # ❌ only ever queries Offender
        )
        offender = result.scalar_one_or_none()
        if not offender:
            return None   # <-- every Victim/Location/Org node ends up here
        ...
```
And the router just 404s when this returns `None`:
```python
# app/routers/network_router.py (lines 31-42)
@router.get("/node-detail/{node_id}")
async def fetch_node_detail(...):
    data = await get_node_detail(db, node_id)
    if not data:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"success": True, "data": data}
```
The frontend calls this unconditionally for every node type (`navigateToNode()` in `CriminalNetwork.tsx`, line 158), so it just swallows the 404 (`networkService.getNodeDetail` catches the error and returns `null`) — nothing crashes, but victim/location/organization detail panels are permanently incomplete.

**Fix:** branch on node type inside `get_node_detail`, e.g.:
```python
async def get_node_detail(db: AsyncSession, node_id: str) -> Optional[Dict[str, Any]]:
    import uuid
    try:
        parsed_id = uuid.UUID(node_id)
    except ValueError:
        return None

    # Try Offender first (existing behavior)
    result = await db.execute(select(Offender).where(Offender.offender_id == parsed_id))
    offender = result.scalar_one_or_none()
    if offender:
        # ...existing offender logic unchanged...
        return { ... }

    # NEW: Victim branch
    from app.models.database_models.victim_model import Victim
    result = await db.execute(select(Victim).where(Victim.victim_id == parsed_id))
    victim = result.scalar_one_or_none()
    if victim:
        return {
            "node_id": node_id,
            "node_type": "victim",
            "label": f"{victim.first_name} {victim.last_name}",
            "risk_score": victim.vulnerability_level or 0,
            "crime_count": 1,
            "profile_data": victim.to_dict(),
            "timeline": [],
            "ai_analysis": None,
        }

    # NEW: Location branch
    from app.models.database_models.location_model import Location
    result = await db.execute(select(Location).where(Location.location_id == parsed_id))
    location = result.scalar_one_or_none()
    if location:
        return {
            "node_id": node_id,
            "node_type": "location",
            "label": location.address or location.location_name or "Unknown Address",
            "risk_score": location.risk_score or 0,
            "crime_count": location.total_crimes or 0,
            "profile_data": location.to_dict(),
            "timeline": [],
            "ai_analysis": None,
        }

    return None
```

---

## 4. Network Graph: "Expand", "Shortest Path", and "Compare" fail *silently* whenever Neo4j is offline

**Where:** `app/routers/network_router.py` (`/expand/{node_id}`, `/shortest-path`) + `crime_frontend/src/pages/CriminalNetwork.tsx` (`handleNodeExpand`, `handleNodeCompare`)

**What happens:** The main graph view has a documented Postgres fallback (`build_network_from_postgres`) that kicks in automatically when Neo4j is down — the graph itself still loads fine, with a "Graph running in fallback mode" style behavior. **But** three interactive features are hard Neo4j-only and have no fallback:
- Double-click to expand a node (`/network/expand/{node_id}`)
- Shift-click to compare two nodes / shortest-path highlighting (`/network/shortest-path`)

When Neo4j is unreachable, both endpoints return a "soft failure" payload (`{"success": false, "message": "..."}` or `{"found": false}`), and the frontend just does nothing — no toast, no message, no visual indication that the feature didn't work:

```tsx
// crime_frontend/src/pages/CriminalNetwork.tsx (lines 240-266)
const handleNodeExpand = async (node: NetworkNode) => {
  const res = await networkService.expandNode(node.node_id);
  if (res && res.nodes && res.edges) {     // ❌ if res = {success:false, message:...}, this silently no-ops
    ...
  }
  // ❌ no else branch — user gets zero feedback
};
```
```tsx
// crime_frontend/src/pages/CriminalNetwork.tsx (lines 223-238)
const handleNodeCompare = async (node: NetworkNode) => {
  if (!compareNode1) { setCompareNode1(node); }
  else if (!compareNode2) {
    setCompareNode2(node);
    const res = await networkService.getShortestPath(compareNode1.node_id, node.node_id);
    if (res && res.found) {                // ❌ silently does nothing if Neo4j is down
      ...
    }
  }
  ...
};
```

**Fix — surface the failure to the user** (minimal example using the existing `warningMessage` state that's already rendered in the UI):
```tsx
const handleNodeExpand = async (node: NetworkNode) => {
  const res = await networkService.expandNode(node.node_id);
  if (res && res.nodes && res.edges) {
    // ...existing merge logic...
  } else {
    setWarningMessage(res?.message || "Node expansion requires the Neo4j graph database, which is currently offline.");
  }
};

const handleNodeCompare = async (node: NetworkNode) => {
  if (!compareNode1) {
    setCompareNode1(node);
  } else if (!compareNode2) {
    setCompareNode2(node);
    const res = await networkService.getShortestPath(compareNode1.node_id, node.node_id);
    if (res && res.found) {
      setHighlightPath(res.path_nodes.map((n: any) => n.id));
    } else {
      setWarningMessage("No path found between the selected nodes, or the graph database is offline.");
    }
  } else {
    setCompareNode1(node);
    setCompareNode2(null);
    setHighlightPath([]);
  }
};
```
**Longer-term fix:** add a Postgres-based fallback for `expand` (BFS one hop out from the node using `CrimeOffenderLink`/`CrimeVictimLink`, similar to `build_network_from_postgres`) and for `shortest-path` (networkx `shortest_path` over the same graph you already build for `get_network_graph_data`), so these features keep working in fallback mode instead of just failing gracefully.

---

## 5. Neo4j fallback graph: subtle relationship-type drift

**Where:** `app/services/network_service.py`, line ~316 (`build_network_from_postgres`, location↔offender linking)

```python
edges.append({
    "edge_id": f"{offender_id}_{loc_id}",
    "source_node_id": offender_id,
    "target_node_id": loc_id,
    "relationship_type": "FREQUENTED",   # ⚠️ not in RELATIONSHIP_TYPES allow-list
    ...
})
```
`RELATIONSHIP_TYPES` in `app/core/config.py` (lines 144-152) is:
```python
RELATIONSHIP_TYPES = ["KNOWS", "WORKED_WITH", "TARGETS", "OPERATES_IN", "MEMBER_OF", "VICTIMIZED_AT", "LINKED_TO"]
```
This isn't breaking anything **today** because the Postgres fallback path never calls `create_criminal_relationship()` (the function that validates against this allow-list). But if anyone later wires `sync_neo4j.py` or any future sync job to push this Postgres-fallback edge into Neo4j via `create_criminal_relationship`, it will raise `ValueError: Invalid relationship_type: FREQUENTED` and silently break that sync.

**Fix:** add `"FREQUENTED"` to `RELATIONSHIP_TYPES` in `app/core/config.py` now, while it's cheap, so the two code paths stay compatible:
```python
RELATIONSHIP_TYPES = [
    "KNOWS", "WORKED_WITH", "TARGETS", "OPERATES_IN",
    "MEMBER_OF", "VICTIMIZED_AT", "LINKED_TO", "FREQUENTED",
]
```

---

## 6. Offender Database: Add/Edit Offender exists on the backend but has ZERO frontend wiring

**Where:** `app/routers/offenders_router.py` vs `crime_frontend/src/pages/OffenderDatabase.tsx` + `crime_frontend/src/services/offenderService.ts`

**What happens:** The backend has fully-built, role-protected endpoints to create and update offender records:
```python
# app/routers/offenders_router.py
@router.post("", status_code=status.HTTP_201_CREATED)     # line 62 — create offender
async def add_offender(...): ...

@router.put("/{offender_id}")                              # line 78 — edit offender
async def edit_offender(...): ...
```
But:
- `ENDPOINTS.OFFENDERS` in `apiEndpoints.ts` only defines `SEARCH`, `PROFILE`, `MODUS_OPERANDI`, `NETWORK`, `RISK` — no `CREATE`/`UPDATE`.
- `offenderService.ts` has no `create`/`update` function at all.
- `OffenderDatabase.tsx` has no "Add Offender" button, no edit form — nothing calls these endpoints.

Compare this to `VictimDatabase.tsx`, which **does** correctly wire up its equivalent `POST /victims` endpoint with a "Register Victim" modal — so this is a clear, isolated gap rather than a deliberate design choice.

**Fix — add the missing plumbing:**
```ts
// crime_frontend/src/constants/apiEndpoints.ts
OFFENDERS: {
  SEARCH: "/offenders/search",
  PROFILE: (id: string) => `/offenders/${id}/profile`,
  MODUS_OPERANDI: (id: string) => `/offenders/${id}/modus-operandi`,
  NETWORK: (id: string) => `/offenders/${id}/network`,
  RISK: (id: string) => `/offenders/${id}/risk`,
  CREATE: "/offenders",                                    // ✅ add
  UPDATE: (id: string) => `/offenders/${id}`,               // ✅ add
},
```
```ts
// crime_frontend/src/services/offenderService.ts
create: async (payload: Record<string, unknown>) => {
  const res = await api.post(ENDPOINTS.OFFENDERS.CREATE, payload);
  return res.data;
},
update: async (id: string, payload: Record<string, unknown>) => {
  const res = await api.put(ENDPOINTS.OFFENDERS.UPDATE(id), payload);
  return res.data;
},
```
Then add an "Add Offender" button + modal to `OffenderDatabase.tsx`, following the same pattern already used for `VictimDatabase.tsx`'s "Register Victim" modal.

---

## 7. General pattern to watch for (not a single bug, a checklist)

While tracing every service file, this pattern recurred and is worth a one-time pass across the codebase:

| Symptom | Cause | Where to check |
|---|---|---|
| A `service.ts` function does `response.data?.data?.x` | Assumes double-wrapping; breaks if backend only returns `{success, data}` (2 keys) since interceptor already unwraps | `networkService.ts` (fixed above); grep `\.data\?\.data` across `src/services/` for any other instance introduced later |
| A `service.ts` function does `response.data` directly and the endpoint has *extra* top-level keys (`total_count`, `limit`, etc.) | Interceptor does **not** unwrap when extra keys are present — code must defensively check both shapes (`data?.data || data`) | Any new paginated endpoint — pattern already handled correctly in `crimeService.ts` (`getMapData`, `filterCrimes`), copy that style for new endpoints |
| Frontend sends a query param the backend route doesn't declare | FastAPI silently drops unknown query params — no 422, no error, just ignored | Whenever adding a new filter/lens control in the UI, always confirm the corresponding `Query(...)` parameter was added on the router, not just consumed deeper in the service layer |

**Quick regression check you can run any time:**
```bash
grep -rn "response.data?.data\|response\.data\.data" crime_frontend/src/services/
```
Cross-reference each hit against the actual FastAPI return statement for that route (`grep -n 'return {"success"' crime_backend/.../app/routers/*.py`) to see whether it has 2 keys (already unwrapped) or more (not unwrapped).

---

## 8. Making the "District" + "All Crimes Lens" filters actually work together (production-grade fix)

You asked specifically about this: select a district **and** a crime type in the two dropdowns above the graph, and the graph should show the network **for that district + that crime type combined**. Both dropdowns *do* trigger a real server request (not just cosmetic), but the combination is **incompletely implemented on the backend** -- it silently produces a wrong/incomplete graph rather than an error, which is why it "looks like it's not really filtering."

### 8.1 What's actually happening today

`CriminalNetwork.tsx` correctly re-fetches on every change to either dropdown:
```tsx
// crime_frontend/src/pages/CriminalNetwork.tsx (line 114)
useEffect(() => { fetch(); }, [crimeTypeLens, districtFilter]);
```
and sends both as real query params:
```tsx
networkService.getGraphData(
  searchQuery || undefined,
  crimeTypeLens === "all" ? undefined : crimeTypeLens,     // crime_type
  districtFilter === "all" ? undefined : districtFilter,   // district_id
  nodeTypeFilter === "all" ? undefined : nodeTypeFilter
)
```
So the frontend side of this is fine -- this is a backend query-completeness bug, not a wiring bug like the others above.

**On the Postgres fallback path** (`app/services/network_service.py -> build_network_from_postgres`, the code path that runs whenever Neo4j isn't connected, which is the common case in most deployments of this project):

- Correct: `district_id` is applied consistently to Criminals, Victims, and Locations.
- Gap: `crime_type` is applied to Criminals only (via a join to `CrimeOffenderLink` -> `Crime`).
- Gap: Victims and Locations are fetched with no `crime_type` filter at all -- so when you pick e.g. "Chain Snatching", you still get every victim and every location in that district, not just the ones connected to a chain-snatching case.
- Gap: Edges (offender-victim, offender-location) are built from unfiltered link tables, so they aren't restricted to the selected crime type either.

The net effect: selecting a crime type narrows the *criminal* nodes correctly, but victims/locations/edges "leak through" unfiltered, producing a graph that's only half-filtered.

**On the Neo4j path** (`app/core/neo4j_connection.py -> get_network_graph`), the same class of gap exists: `crime_type` is only checked against the *candidate root node's* `n.crime_types` array, but the expansion step that pulls in `connected` neighbors and edges has no crime-type constraint at all -- so once a node passes the filter, all of its neighbors (regardless of crime type) get pulled in too.

### 8.2 How production link-analysis tools do this (i2 Analyst's Notebook, Palantir Gotham, Maltego, Neo4j Bloom)

The pattern used across mature link-analysis products is faceted, server-side, combinable filtering, not client-side dimming:
- Filters combine with AND semantics across facets (district AND crime-type), applied to every entity type and every relationship in the same query -- not just the "primary" entity -- otherwise the graph looks inconsistent to the analyst.
- The query itself is scoped (WHERE-clause / Cypher pattern predicate), not applied as a client-side visual overlay. Visual "lens" dimming (which this app already does client-side for extra emphasis) is a good *secondary* affordance, but should never be the *only* filtering mechanism, since it still ships irrelevant data over the network and lets it leak into isolated-node counts, exports, and the AI summary.
- Active filters are shown as removable chips so the analyst always knows exactly what subgraph they're looking at ("you are viewing: Bengaluru Urban x Chain Snatching").
- Filtered views are deep-linkable (state goes into the URL) so an investigator can share a link to "this exact filtered graph" with a colleague.
- Empty results after filtering get an explicit empty state with a "Clear filters" action, not a blank canvas.

The fixes below bring this codebase in line with that pattern.

### 8.3 Backend fix -- `build_network_from_postgres` (Postgres fallback path)

`crime_backend/MODULE_2_BACKEND/app/services/network_service.py`

```python
async def build_network_from_postgres(
    db: AsyncSession,
    search_query: Optional[str] = None,
    district_id: Optional[str] = None,
    node_limit: int = 100,
    crime_type: Optional[str] = None,
    node_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build network graph from PostgreSQL data when Neo4j is unavailable"""
    from app.models.database_models.crime_model import CrimeOffenderLink, Crime, CrimeVictimLink
    from app.models.database_models.victim_model import Victim
    from app.models.database_models.location_model import Location

    nodes: list[dict] = []
    edges: list[dict] = []
    per_type_limit = max(1, node_limit // (1 if node_type else 3))

    if node_type == "organization":
        return {
            "nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0,
            "network_density": 0, "key_players": [],
            "warning": "Organization entities are only available when Neo4j is connected.",
        }

    # --- Pre-resolve the set of crime_ids that match crime_type (+ district_id) ONCE ---
    # This becomes the single source of truth every entity type and edge filters against,
    # so Criminals / Victims / Locations / edges all agree on the same crime-type scope.
    matching_crime_ids = None
    if crime_type:
        crime_filter_q = select(Crime.crime_id).where(Crime.crime_type == crime_type)
        if district_id:
            crime_filter_q = crime_filter_q.where(Crime.district_id == district_id)
        matching_crime_ids = set((await db.execute(crime_filter_q)).scalars().all())
        if not matching_crime_ids:
            # No crimes at all match this district+type combo -- return an explicit empty
            # result instead of silently falling back to an unfiltered graph.
            return {
                "nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0,
                "network_density": 0, "key_players": [],
                "warning": f"No records found for crime type '{crime_type}'"
                           + (" in the selected district." if district_id else "."),
            }

    # --- Criminals ---
    if node_type in (None, "criminal"):
        q = select(Offender).limit(per_type_limit)
        if district_id:
            q = q.where(Offender.district_id == district_id)
        if search_query:
            q = q.where(
                (Offender.first_name.ilike(f"%{search_query}%")) |
                (Offender.last_name.ilike(f"%{search_query}%"))
            )
        if matching_crime_ids is not None:
            q = q.join(CrimeOffenderLink, CrimeOffenderLink.offender_id == Offender.offender_id) \
                 .where(CrimeOffenderLink.crime_id.in_(matching_crime_ids)).distinct()

        result = await db.execute(q)
        offenders = result.scalars().all()

        offender_node_ids = set()
        offender_associate_map = {}

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

        seen_pairs = set()
        for node_id, associates in offender_associate_map.items():
            for associate_id in associates:
                if associate_id in offender_node_ids:
                    pair_key = tuple(sorted([node_id, associate_id]))
                    if pair_key in seen_pairs:
                        continue
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

    # --- Victims ---
    if node_type in (None, "victim"):
        # When a crime_type is selected, only pull victims linked to a matching crime
        victim_ids_for_crime_type = None
        if matching_crime_ids is not None:
            vlink_q = select(CrimeVictimLink.victim_id).where(CrimeVictimLink.crime_id.in_(matching_crime_ids))
            victim_ids_for_crime_type = set((await db.execute(vlink_q)).scalars().all())

        vq = select(Victim).limit(per_type_limit)
        if district_id:
            vq = vq.where(Victim.district_id == district_id)
        if search_query:
            vq = vq.where(
                (Victim.first_name.ilike(f"%{search_query}%")) |
                (Victim.last_name.ilike(f"%{search_query}%"))
            )
        if victim_ids_for_crime_type is not None:
            vq = vq.where(Victim.victim_id.in_(victim_ids_for_crime_type))

        v_result = await db.execute(vq)
        victims = v_result.scalars().all()
        for v in victims:
            nodes.append({
                "node_id": str(v.victim_id),
                "node_type": "victim",
                "label": f"{v.first_name} {v.last_name}",
                "risk_score": v.vulnerability_level or 0,
                "crime_count": 1,
                "size": 20,
                "color": "#3b82f6",
                "profile_data": {"district_id": v.district_id},
            })

        link_q = select(CrimeVictimLink)
        if district_id:
            link_q = link_q.join(Crime).where(Crime.district_id == district_id)
        if matching_crime_ids is not None:
            link_q = link_q.where(CrimeVictimLink.crime_id.in_(matching_crime_ids))   # NEW
        cv_links = (await db.execute(link_q)).scalars().all()
        for cvl in cv_links:
            off_links = (await db.execute(
                select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id == cvl.crime_id)
            )).scalars().all()
            crime = (await db.execute(select(Crime).where(Crime.crime_id == cvl.crime_id))).scalar_one_or_none()
            for ol in off_links:
                if any(n["node_id"] == str(ol.offender_id) for n in nodes) and \
                   any(n["node_id"] == str(cvl.victim_id) for n in nodes):
                    edges.append({
                        "edge_id": f"{ol.offender_id}_{cvl.victim_id}",
                        "source_node_id": str(ol.offender_id),
                        "target_node_id": str(cvl.victim_id),
                        "relationship_type": "VICTIMIZED_AT",
                        "strength_score": 70,
                        "confidence_level": "CONFIRMED",
                        "crime_types": [crime.crime_type] if crime else [],
                    })

    # --- Locations ---
    if node_type in (None, "location"):
        location_ids_for_crime_type = None
        if matching_crime_ids is not None:
            lloc_q = select(Crime.location_id).where(
                Crime.crime_id.in_(matching_crime_ids), Crime.location_id.isnot(None)
            )
            location_ids_for_crime_type = set((await db.execute(lloc_q)).scalars().all())

        lq = select(Location).limit(per_type_limit)
        if district_id:
            lq = lq.where(Location.district_id == district_id)
        if search_query:
            lq = lq.where(Location.address.ilike(f"%{search_query}%"))
        if location_ids_for_crime_type is not None:
            lq = lq.where(Location.location_id.in_(location_ids_for_crime_type))   # NEW

        l_result = await db.execute(lq)
        locations = l_result.scalars().all()
        location_ids_in_graph = set()
        for l in locations:
            nodes.append({
                "node_id": str(l.location_id),
                "node_type": "location",
                "label": l.address or l.location_name or "Unknown Address",
                "risk_score": l.risk_score or 0,
                "crime_count": l.total_crimes or 0,
                "size": 25,
                "color": "#a855f7",
                "profile_data": {"district_id": l.district_id},
            })
            location_ids_in_graph.add(str(l.location_id))

        if location_ids_in_graph:
            try:
                crime_q = select(Crime).where(Crime.location_id.in_([uuid.UUID(lid) for lid in location_ids_in_graph]))
                if matching_crime_ids is not None:
                    crime_q = crime_q.where(Crime.crime_id.in_(matching_crime_ids))   # NEW
                crimes_at_locations = (await db.execute(crime_q)).scalars().all()
                crime_ids_by_location = {}
                for c in crimes_at_locations:
                    if c.location_id:
                        crime_ids_by_location.setdefault(str(c.location_id), []).append(c.crime_id)

                existing_offender_ids = {n["node_id"] for n in nodes if n["node_type"] == "criminal"}
                for loc_id, crime_ids in crime_ids_by_location.items():
                    if not crime_ids:
                        continue
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
            except Exception as e:
                logger.warning(f"Failed to link locations to crimes/offenders in fallback: {e}")

    # ...centrality/community/return block unchanged...
```

Why the `matching_crime_ids` pre-resolution step matters: it makes `crime_type` behave as a single, consistent scope shared by every entity/edge query in the function, instead of independent, drifting interpretations of "matches the filter." This is exactly the pattern production link-analysis backends use -- resolve the facet to a concrete ID set once, then intersect every sub-query against it.

### 8.4 Backend fix -- Neo4j path (`get_network_graph`)

`crime_backend/MODULE_2_BACKEND/app/core/neo4j_connection.py`

Add a crime-type constraint to the expansion `CALL` block, not just the root-node `WHERE`:

```cypher
CALL {
  WITH n
  OPTIONAL MATCH (n)-[r]-(connected)
  WHERE $crime_type IS NULL
     OR $crime_type IN coalesce(r.crime_types, [])
     OR $crime_type IN coalesce(connected.crime_types, [])
  RETURN r, connected
  LIMIT 25
}
```
```python
params["crime_type"] = crime_type if crime_type else None
# ensure the bound param always exists for the Cypher IS NULL check
```
This keeps both a node and its neighbors scoped to the selected crime type, matching the Postgres-fallback behavior above so the two data sources produce consistent results.

### 8.5 Frontend enhancements -- bring the UX up to "best in class"

Additive, non-breaking improvements to `CriminalNetwork.tsx`, inspired by how i2 Analyst's Notebook / Neo4j Bloom / Maltego handle combinable facet filters, and standard dashboard-filter UX guidance (filter chips, deep-linkable state, explicit empty states):

**a) Active filter chips + "Clear all"** (so the analyst always knows what subgraph they're viewing):
```tsx
{(districtFilter !== "all" || crimeTypeLens !== "all" || nodeTypeFilter !== "all") && (
  <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/60 border-b border-slate-700/50">
    <span className="text-xs text-slate-400">Active filters:</span>
    {districtFilter !== "all" && (
      <span className="flex items-center gap-1 text-xs bg-blue-900/40 text-blue-300 px-2 py-1 rounded-full">
        District: {districts.find(d => d.district_id === districtFilter)?.district_name || districtFilter}
        <button onClick={() => setDistrictFilter("all")} className="hover:text-white">x</button>
      </span>
    )}
    {crimeTypeLens !== "all" && (
      <span className="flex items-center gap-1 text-xs bg-purple-900/40 text-purple-300 px-2 py-1 rounded-full">
        Crime Type: {crimeTypeLens}
        <button onClick={() => setCrimeTypeLens("all")} className="hover:text-white">x</button>
      </span>
    )}
    {nodeTypeFilter !== "all" && (
      <span className="flex items-center gap-1 text-xs bg-emerald-900/40 text-emerald-300 px-2 py-1 rounded-full">
        Type: {nodeTypeFilter}
        <button onClick={() => setNodeTypeFilter("all")} className="hover:text-white">x</button>
      </span>
    )}
    <button
      onClick={() => { setDistrictFilter("all"); setCrimeTypeLens("all"); setNodeTypeFilter("all"); setSearchQuery(""); }}
      className="ml-auto text-xs text-slate-400 hover:text-red-400 underline"
    >
      Clear all filters
    </button>
  </div>
)}
```

**b) Deep-linkable filter state** (so investigators can share/bookmark "Bengaluru Urban x Chain Snatching"):
```tsx
// On mount: hydrate filters from the URL (reuse the existing `searchParams` already imported for `focus`)
useEffect(() => {
  const d = searchParams.get("district"); if (d) setDistrictFilter(d);
  const c = searchParams.get("crime_type"); if (c) setCrimeTypeLens(c);
  const n = searchParams.get("node_type"); if (n) setNodeTypeFilter(n);
}, []); // run once on mount

// On filter change: push to the URL (need `setSearchParams` from useSearchParams -- currently
// only the getter is destructured on line 63, so update that import to also grab the setter)
useEffect(() => {
  const params: Record<string, string> = {};
  if (districtFilter !== "all") params.district = districtFilter;
  if (crimeTypeLens !== "all") params.crime_type = crimeTypeLens;
  if (nodeTypeFilter !== "all") params.node_type = nodeTypeFilter;
  setSearchParams(params, { replace: true });
}, [districtFilter, crimeTypeLens, nodeTypeFilter]);
```

**c) Explicit empty state when the combination legitimately has zero results** -- pair this with the `warning` field the backend fix in 8.3 now returns for a no-match district+crime_type combo:
```tsx
) : status === "no_data" ? (
  <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
    <Network className="h-12 w-12 text-slate-600 mb-3 opacity-50" />
    <h2 className="text-xl font-bold text-white mb-2">No Matches for This Filter Combination</h2>
    <p className="text-sm max-w-md text-center mb-4">
      {warningMessage || "There are no records matching the selected district and crime type."}
    </p>
    <button
      onClick={() => { setDistrictFilter("all"); setCrimeTypeLens("all"); }}
      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm"
    >
      Clear Filters
    </button>
  </div>
```

**d) Cache-key correctness check** -- since 8.3 makes `crime_type` behave differently, double check the Redis cache key in `get_network_graph_data` already includes both filters (it does, no change needed):
```python
cache_key = f"network_graph:{search_query}:{crime_type}:{district_id}:{node_type}:{depth}:{node_limit}"
```

### 8.6 Summary of what changes after this fix

| Filter combination | Before | After |
|---|---|---|
| District only | Worked | Unchanged |
| Crime type only, node_type = "criminal" | Worked | Unchanged |
| Crime type only, node_type = "all" | Criminals filtered, Victims/Locations leaked through unfiltered | All three entity types + edges scoped to the crime type |
| District + Crime type together | Partially filtered, inconsistent between node types | Fully consistent, single-source-of-truth filtering via `matching_crime_ids` |
| District + Crime type with zero matches | Silently showed unrelated leftover nodes | Explicit "No Matches" empty state with Clear Filters action |
| Sharing a filtered view with a colleague | Not possible (state lived only in React) | Filters reflected in the URL, shareable/bookmarkable |

---

## Summary Table

| # | Area | Severity | File(s) | Status after fix |
|---|---|---|---|---|
| 1 | Network Graph — Edge AI Insight | High (feature totally dead) | `networkService.ts` | 1-line fix |
| 2 | Network Graph — AI Summary crime-type lens | Medium (silently ignored filter) | `network_router.py`, `network_service.py` | ~10 lines |
| 3 | Network Graph — Node detail for Victim/Location/Org | Medium (feature incomplete for 3 of 4 node types) | `network_service.py` | ~25 lines |
| 4 | Network Graph — Expand/Compare/Shortest-path silent failure | Medium (bad UX, no data loss) | `CriminalNetwork.tsx` | ~15 lines |
| 5 | Network Graph — `FREQUENTED` relationship type not in allow-list | Low (latent, not yet triggered) | `config.py` | 1 line |
| 6 | Offender Database — Create/Edit not wired to frontend | High (missing feature, not a bug) | `apiEndpoints.ts`, `offenderService.ts`, `OffenderDatabase.tsx` | New UI needed |
| 7 | Systemic — response envelope handling | Preventative | `src/services/*.ts` | Ongoing discipline |
| 8 | Network Graph — District + Crime-Type combined filter incomplete on backend (victims/locations/edges leak through unfiltered) | High (core requested feature) | `network_service.py`, `neo4j_connection.py`, `CriminalNetwork.tsx` | Full rewrite provided in §8 |

All other cross-checked modules — Dashboard, Crime Map/Database, Hotspots, Predictions, Anomalies, Alerts, Settings, Reports, Victims, Evidence upload/download, Global Search, AI Assistant, Auth — had their frontend endpoints, HTTP verbs, and response-shape handling verified against the matching backend router and found **correctly wired**.