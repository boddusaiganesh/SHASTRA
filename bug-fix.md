# SHASTRA — Criminal Network Page: Complete Fix & Feature Document (v2)
### Consolidated: performance fixes + new advanced features
*(Reference only — nothing in your repo was changed. Copy/paste whatever you want into your files.)*

This replaces and extends the first document. It's organized in two parts:

- **Part A — Fixes**: the hang/bug fixes from before (heatmap, matrix, cytoscape rebuild, missing
  victim/location nodes, backend blocking, dead filters).
- **Part B — New features**: everything from this conversation — wider node spacing, crime-type
  "lens" filtering, cross-filter connections that never disappear, confirmed/suspected line styling,
  a Key Players button, and an AI "explain this connection" feature.

A quick note on your schema (checked against your actual model files, not assumed): you have a real
`Location` table (`location_model.py`) and `Victim` table, but **no `Organization` table anywhere in
Postgres** — organizations only exist as a Neo4j label with no backing relational data. That means the
Postgres-fallback graph (used when Neo4j is down) can be fixed to show real Criminals, Victims, and
Locations, but it cannot show Organizations until an `organizations` table/model exists. I've called
this out again inline below rather than inventing one.

---

## PART A — Fixes (hangs, bugs, dead filters)

### A1. Chrome hang on the Heatmap / Crime Analysis page

**Backend** — `crime_backend/MODULE_2_BACKEND/app/routers/crimes_router.py` — `/crimes/map-data` has no
limit at all today; it ships every row in the `crimes` table on every load.

```python
from datetime import datetime, timedelta

@router.get("/map-data")
async def get_map_data(
    file_format: str = Query("json", enum=["json", "csv"]),
    days: int = Query(90, ge=1, le=730, description="Only crimes from the last N days"),
    limit: int = Query(5000, ge=1, le=20000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    stmt = select(Crime, District, PoliceStation).join(
        District, Crime.district_id == District.district_id, isouter=True
    ).join(
        PoliceStation, Crime.police_station_id == PoliceStation.station_id, isouter=True
    )
    cutoff = datetime.utcnow().date() - timedelta(days=days)
    stmt = stmt.where(Crime.date_of_occurrence >= cutoff)
    stmt = scope_district_filter(stmt, current_user, Crime.district_id)
    stmt = stmt.order_by(Crime.date_of_occurrence.desc()).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()
    # ... existing formatted_data loop unchanged
```

**Frontend** — `crime_frontend/src/components/maps/CrimeMap.tsx` — "heatmap" mode currently draws one
`<CircleMarker>` per crime with no clustering. `leaflet.heat` is already in your `package.json` but
never imported/used anywhere. New file:

`crime_frontend/src/components/maps/HeatLayer.tsx`
```tsx
import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";

interface Props { points: [number, number, number?][] }

const HeatLayer: React.FC<Props> = ({ points }) => {
  const map = useMap();
  useEffect(() => {
    // @ts-ignore - leaflet.heat augments L at runtime
    const heat = L.heatLayer(points, {
      radius: 22, blur: 18, maxZoom: 12,
      gradient: { 0.2: "#3b82f6", 0.4: "#22c55e", 0.6: "#f59e0b", 0.8: "#ef4444", 1.0: "#991b1b" },
    }).addTo(map);
    return () => { map.removeLayer(heat); };
  }, [map, points]);
  return null;
};
export default HeatLayer;
```

In `CrimeMap.tsx`, replace the "heatmap" branch:
```tsx
import HeatLayer from "./HeatLayer";

{viewMode === "heatmap" ? (
  <HeatLayer points={crimes.map(c => [c.latitude, c.longitude, 0.6])} />
) : viewMode === "cluster" ? (
  <MarkerClusterGroup>{/* existing markers, unchanged */}</MarkerClusterGroup>
) : (
  crimes.map((crime) => ( /* existing "pins" markers, unchanged */ ))
)}
```

One canvas layer instead of thousands of DOM markers — this is the actual fix for the hang.

---

### A2. Connectivity Matrix freezes with more than ~100 nodes

`crime_frontend/src/components/network/ConnectivityMatrix.tsx` renders `O(n²)` SVG `<rect>` +
`<title>` elements. Cap it (quick fix) or move to canvas (proper fix):

```tsx
// Quick fix — cap the matrix and tell the user why
const MAX_MATRIX_NODES = 120;
const ordered = useMemo(() => {
  const sorted = [...nodes].sort(/* existing comparator, unchanged */);
  return sorted.slice(0, MAX_MATRIX_NODES);
}, [nodes, sortMode]);
// render a small note when nodes.length > MAX_MATRIX_NODES:
// "Matrix capped at 120 nodes for performance — narrow your filters to see more."
```

```tsx
// Proper fix — canvas instead of SVG (handles any size, single DOM element)
const canvasRef = useRef<HTMLCanvasElement>(null);

useEffect(() => {
  const canvas = canvasRef.current;
  const ctx = canvas?.getContext("2d");
  if (!canvas || !ctx) return;

  canvas.width = ordered.length * cellSize + offset + 20;
  canvas.height = ordered.length * cellSize + offset + 20;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ordered.forEach((rowNode, i) => {
    ordered.forEach((colNode, j) => {
      const edge = i !== j ? edgeMap.get(`${rowNode.node_id}_${colNode.node_id}`) : null;
      let fill = i === j ? "#334155" : "#1e293b";
      if (edge) {
        const t = Math.min(1, (edge.strength_score || 50) / 100);
        fill = `rgb(${Math.round(30 + t * 195)}, ${Math.round(41 - t * 20)}, ${Math.round(59 - t * 40)})`;
      }
      ctx.fillStyle = fill;
      ctx.fillRect(offset + j * cellSize, offset + i * cellSize, cellSize - 1, cellSize - 1);
    });
  });
}, [ordered, edgeMap, cellSize]);

const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
  const rect = canvasRef.current!.getBoundingClientRect();
  const j = Math.floor((e.clientX - rect.left - offset) / cellSize);
  const i = Math.floor((e.clientY - rect.top - offset) / cellSize);
  if (i === j || i < 0 || j < 0 || i >= ordered.length || j >= ordered.length) return;
  const rowNode = ordered[i], colNode = ordered[j];
  if (edgeMap.has(`${rowNode.node_id}_${colNode.node_id}`)) onCellClick(rowNode.node_id, colNode.node_id);
};

return <canvas ref={canvasRef} onClick={handleClick} className="cursor-pointer" />;
```

---

### A3. Graph view: destroy/rebuild on every change + tighter spacing (covers your "too packed" ask)

`crime_frontend/src/components/network/NetworkGraph.tsx` destroys and fully re-lays-out the whole
graph — at the slowest `fcose` quality setting — on every single data change, including one node
expanding. This is both the freeze cause *and* why it looks cramped (the layout params are tuned tight).

```tsx
// Move these OUT of the component (module-level constants) so they aren't recreated every render:
const GRAPH_STYLE: cytoscape.StylesheetJson = [ /* your existing `style: [...]` array, unchanged */ ];

function buildElements(nodes: NetworkNode[], edges: NetworkEdge[]) {
  return [
    ...nodes.map((n) => ({ data: { /* same mapping you already have */ } })),
    ...edges
      .filter((e) => {
        const s = e.source || e.source_node_id || "";
        const t = e.target || e.target_node_id || "";
        return nodes.some(n => n.node_id === s) && nodes.some(n => n.node_id === t);
      })
      .map((e, i) => ({ data: { /* same mapping you already have */ } })),
  ];
}

const LAYOUT_OPTIONS = {
  name: "fcose",
  quality: "default",       // was "proof" — that setting is meant for one-shot final layouts, not interaction
  animate: true,
  randomize: true,
  nodeSeparation: 160,      // was 75 — this is the main "too packed" knob, raise until it feels right
  idealEdgeLength: 220,     // was 100 — distance along edges specifically
  nodeRepulsion: 9000,      // NEW — push unconnected nodes further apart from each other
  edgeElasticity: 0.35,     // NEW — lower = straighter, less tangled edges
  gravity: 0.15,            // NEW — lower = graph spreads out more instead of pulling to center
} as const;
```

```tsx
// Replace the single useEffect that builds/destroys cytoscape with this:
const prevIdsRef = useRef<Set<string>>(new Set());

useEffect(() => {
  if (!containerRef.current) return;
  const currentIds = new Set(nodes.map(n => n.node_id));

  if (!cyRef.current) {
    const cy = cytoscape({
      container: containerRef.current,
      elements: buildElements(nodes, edges),
      style: GRAPH_STYLE,
      layout: LAYOUT_OPTIONS,
      wheelSensitivity: 0.3,
    });
    attachHandlers(cy); // pull your existing cy.on("tap"...) / cy.on("dblclick"...) into a helper fn
    cyRef.current = cy;
    prevIdsRef.current = currentIds;
    return;
  }

  const cy = cyRef.current;
  const existingIds = new Set(cy.nodes().map(n => n.id()));
  const newNodes = nodes.filter(n => !existingIds.has(n.node_id));
  const newEdges = edges.filter(e => cy.getElementById(e.edge_id ?? `${e.source_node_id}-${e.target_node_id}`).empty());

  if (newNodes.length === 0 && newEdges.length === 0) return; // nothing changed — skip entirely, no relayout

  if (currentIds.size < existingIds.size) {
    // Graph shrank (filter narrowed) — full rebuild is fine, it's a small graph now
    cy.elements().remove();
    cy.add(buildElements(nodes, edges));
    cy.layout(LAYOUT_OPTIONS).run();
  } else {
    // Incremental expand — add only what's new, keep existing node positions fixed
    cy.add(buildElements(newNodes, newEdges));
    cy.layout({ ...LAYOUT_OPTIONS, randomize: false, fit: false }).run();
  }
  prevIdsRef.current = currentIds;
}, [nodes, edges]);
```

Also cap what you ever hand to Cytoscape in the first place — pass at most ~300 nodes and show a
"showing 300 of 842 — narrow your filters" note, same pattern as the matrix fix above.

---

### A4. Neo4j: victims/locations/organizations can't be found or filtered properly

`crime_backend/MODULE_2_BACKEND/app/core/neo4j_connection.py`, `get_network_graph()` roots the search
on `MATCH (n:Criminal)` only — other types can only ever appear as one-hop neighbors, never as the
thing you searched/filtered for.

```python
async def get_network_graph(
    search_query: str = None, crime_type: str = None, district_id: str = None,
    node_type: str | None = None,   # NEW
    depth: int = 2, node_limit: int = 100,
) -> Dict[str, Any]:
    global _driver
    if not _driver:
        return {"status": "offline", "error": "Graph database (Neo4j) is not connected"}

    label_map = {"criminal": "Criminal", "victim": "Victim", "location": "Location", "organization": "Organization"}
    root_labels = [label_map[node_type]] if node_type in label_map else list(label_map.values())
    label_filter = " OR ".join(f"n:{lbl}" for lbl in root_labels)

    where_clauses = [f"({label_filter})"]
    params = {"node_limit": node_limit, "limit": node_limit * 3}

    if search_query:
        where_clauses.append(
            "(n.name CONTAINS $search OR n.offender_id = $search OR n.victim_id = $search "
            "OR n.location_id = $search OR n.org_id = $search)"
        )
        params["search"] = search_query
    if district_id:
        where_clauses.append("n.district_id = $district_id")
        params["district_id"] = district_id
    if crime_type:
        where_clauses.append("$crime_type IN n.crime_types")
        params["crime_type"] = crime_type

    query = f"""
    MATCH (n)
    WHERE {" AND ".join(where_clauses)}
    OPTIONAL MATCH (n)-[r]-()
    WITH n, count(r) AS degree
    ORDER BY degree DESC, n.risk_score DESC
    LIMIT $node_limit
    CALL {{
      WITH n
      OPTIONAL MATCH (n)-[r]-(connected)
      RETURN r, connected
      LIMIT 25
    }}
    RETURN n, elementId(n) AS n_eid, labels(n) AS labels_n, properties(r) AS r_props, type(r) AS type_r,
           connected, elementId(connected) AS connected_eid, labels(connected) AS labels_connected
    """
    results = await run_neo4j_query(query, params)
    # ... rest of the function body is unchanged
```

Thread `node_type` through `network_router.py` and `network_service.py` exactly like `crime_type` is
already threaded (shown fully in A7 below).

---

### A5. Postgres fallback: only ever builds Criminal nodes — fixed to include real Victims & Locations

`crime_backend/MODULE_2_BACKEND/app/services/network_service.py`,
`build_network_from_postgres()` today only queries `Offender`, and links offenders using the blind
`known_associates` ID list (no idea *why* two people are linked). Rewritten to build real nodes for
Criminals, Victims, and Locations from your actual tables, and to link people through the crimes that
actually connect them (so every edge can carry a real crime type + confirmed/suspected status — this
also directly enables Part B's crime-type lens and confirmed/suspected line styling when Neo4j is down):

```python
from collections import defaultdict
from app.models.database_models.crime_model import CrimeOffenderLink, CrimeVictimLink, Crime
from app.models.database_models.victim_model import Victim
from app.models.database_models.location_model import Location

async def build_network_from_postgres(
    db: AsyncSession,
    search_query: Optional[str] = None,
    district_id: Optional[str] = None,
    node_limit: int = 100,
    crime_type: Optional[str] = None,
    node_type: Optional[str] = None,
) -> Dict[str, Any]:
    nodes: list[dict] = []
    edges: list[dict] = []
    per_type_limit = max(1, node_limit // (1 if node_type else 3))

    # ---- Criminals ----
    offenders_by_id: dict[str, Offender] = {}
    if node_type in (None, "criminal"):
        q = select(Offender).limit(per_type_limit)
        if district_id:
            q = q.where(Offender.district_id == district_id)
        if search_query:
            q = q.where(Offender.first_name.ilike(f"%{search_query}%") | Offender.last_name.ilike(f"%{search_query}%"))
        if crime_type:
            q = q.join(CrimeOffenderLink).join(Crime).where(Crime.crime_type == crime_type).distinct()
        offenders = (await db.execute(q)).scalars().all()
        for o in offenders:
            offenders_by_id[str(o.offender_id)] = o
            color_map = {"HIGH": "#ef4444", "MEDIUM": "#f97316", "LOW": "#22c55e"}
            nodes.append({
                "node_id": str(o.offender_id), "node_type": "criminal",
                "label": f"{o.first_name} {o.last_name}", "risk_score": o.risk_score or 0,
                "crime_count": o.total_crimes or 0, "color": color_map.get(o.risk_level, "#6b7280"),
                "profile_data": {"status": o.status, "risk_level": o.risk_level, "district_id": o.district_id},
            })

    # ---- Victims ----
    victims_by_id: dict[str, Victim] = {}
    if node_type in (None, "victim"):
        vq = select(Victim).limit(per_type_limit)
        if district_id:
            vq = vq.where(Victim.district_id == district_id)
        if search_query:
            vq = vq.where(Victim.first_name.ilike(f"%{search_query}%") | Victim.last_name.ilike(f"%{search_query}%"))
        victims = (await db.execute(vq)).scalars().all()
        for v in victims:
            victims_by_id[str(v.victim_id)] = v
            nodes.append({
                "node_id": str(v.victim_id), "node_type": "victim",
                "label": f"{v.first_name} {v.last_name}",
                "risk_score": min(100, len(v.vulnerability_factors or []) * 25),
                "crime_count": v.total_victimizations or 0,
                "profile_data": {"district_id": v.district_id},
            })

    # ---- Locations ----
    if node_type in (None, "location"):
        lq = select(Location).limit(per_type_limit)
        if district_id:
            lq = lq.where(Location.district_id == district_id)
        locations = (await db.execute(lq)).scalars().all()
        for l in locations:
            nodes.append({
                "node_id": str(l.location_id), "node_type": "location",
                "label": l.location_name, "risk_score": l.risk_score or 0,
                "crime_count": l.total_crimes or 0,
                "profile_data": {"location_type": l.location_type, "is_hotspot": l.is_hotspot},
            })

    # NOTE: there is no Organization table in Postgres (checked location_model.py / crime_model.py) —
    # "organization" nodes can only come from Neo4j today. If you want them in the Postgres fallback
    # too, that requires a new `organizations` table/model first; this function can't fabricate one.

    node_ids_present = {n["node_id"] for n in nodes}

    # ---- Real edges: build them FROM the crimes that connect people, not from a blind ID list ----
    # Group offenders and victims by the crime that ties them together, so every edge can carry the
    # real crime_type + a real confirmed/suspected status instead of a guessed constant.
    crime_query = select(Crime)
    if district_id:
        crime_query = crime_query.where(Crime.district_id == district_id)
    if crime_type:
        crime_query = crime_query.where(Crime.crime_type == crime_type)
    crimes_by_id = {str(c.crime_id): c for c in (await db.execute(crime_query)).scalars().all()}

    off_links = (await db.execute(
        select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id.in_([UUID(cid) for cid in crimes_by_id]))
    )).scalars().all() if crimes_by_id else []
    vic_links = (await db.execute(
        select(CrimeVictimLink).where(CrimeVictimLink.crime_id.in_([UUID(cid) for cid in crimes_by_id]))
    )).scalars().all() if crimes_by_id else []

    crime_to_offenders: dict[str, list] = defaultdict(list)
    for link in off_links:
        crime_to_offenders[str(link.crime_id)].append(link)
    crime_to_victims: dict[str, list] = defaultdict(list)
    for link in vic_links:
        crime_to_victims[str(link.crime_id)].append(link)

    seen_edges = set()
    for crime_id, crime in crimes_by_id.items():
        offender_links = crime_to_offenders.get(crime_id, [])
        victim_links = crime_to_victims.get(crime_id, [])

        # Co-offender edges (two suspects sharing the same crime)
        for i in range(len(offender_links)):
            for j in range(i + 1, len(offender_links)):
                a, b = str(offender_links[i].offender_id), str(offender_links[j].offender_id)
                if a not in offenders_by_id or b not in offenders_by_id:
                    continue
                key = tuple(sorted([a, b])) + (crime.crime_type,)
                if key in seen_edges:
                    continue
                seen_edges.add(key)
                confirmed = offender_links[i].is_confirmed and offender_links[j].is_confirmed
                edges.append({
                    "edge_id": f"{a}_{b}_{crime_id}", "source_node_id": a, "target_node_id": b,
                    "relationship_type": "CO_OFFENDER", "strength_score": 75 if confirmed else 45,
                    "confidence_level": "CONFIRMED" if confirmed else "SUSPECTED",
                    "crime_types": [crime.crime_type],
                })

        # Offender <-> Victim edges
        for ol in offender_links:
            for vl in victim_links:
                a, b = str(ol.offender_id), str(vl.victim_id)
                if a not in offenders_by_id or b not in victims_by_id:
                    continue
                edges.append({
                    "edge_id": f"{a}_{b}_{crime_id}", "source_node_id": a, "target_node_id": b,
                    "relationship_type": "VICTIMIZED_AT",
                    "strength_score": 70, "confidence_level": "CONFIRMED" if ol.is_confirmed else "SUSPECTED",
                    "crime_types": [crime.crime_type],
                })

    # Merge duplicate offender-pairs across multiple shared crimes into one edge with combined crime_types
    merged: dict[str, dict] = {}
    for e in edges:
        base_key = f"{e['source_node_id']}_{e['target_node_id']}_{e['relationship_type']}"
        if base_key in merged:
            merged[base_key]["crime_types"] = list(set(merged[base_key]["crime_types"] + e["crime_types"]))
            merged[base_key]["strength_score"] = min(100, merged[base_key]["strength_score"] + 10)
        else:
            merged[base_key] = e
    edges = list(merged.values())

    centrality = compute_graph_centrality(nodes, edges)
    communities = detect_communities(nodes, edges)
    for n in nodes:
        n["centrality"] = centrality.get(n["node_id"], {"betweenness": 0, "degree": 0, "pagerank": 0})
        n["community_id"] = communities.get(n["node_id"], 0)

    return {
        "nodes": nodes, "edges": edges,
        "total_nodes": len(nodes), "total_edges": len(edges),
        "network_density": round(len(edges) / max(len(nodes), 1), 2),
        "key_players": [n["node_id"] for n in sorted(nodes, key=lambda x: x["centrality"]["betweenness"], reverse=True)[:5]],
    }
```

(`from uuid import UUID` needs to be imported at the top of the file if not already.)

---

### A6. Backend blocks all users while computing network stats

`network_service.py`, `get_network_graph_data()` calls `compute_graph_centrality` /
`detect_communities` synchronously — both are CPU-heavy `networkx` calls that **freeze the entire
FastAPI event loop** while running, stalling every other request (including other officers' tabs and
the live WebSocket alert feed) until done.

```python
import asyncio
from functools import partial

async def get_network_graph_data(
    db: AsyncSession, search_query: Optional[str] = None, crime_type: Optional[str] = None,
    district_id: Optional[str] = None, node_type: Optional[str] = None,
    depth: int = 2, node_limit: int = 100,
) -> Dict[str, Any]:
    cache_key = f"network_graph:{search_query}:{crime_type}:{district_id}:{node_type}:{depth}:{node_limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    graph_data = await get_network_graph(
        search_query=search_query, crime_type=crime_type, district_id=district_id,
        node_type=node_type, depth=depth, node_limit=node_limit,
    )
    if graph_data.get("status") == "offline":
        graph_data = await build_network_from_postgres(
            db, search_query=search_query, district_id=district_id,
            node_limit=node_limit, crime_type=crime_type, node_type=node_type,
        )
        graph_data["source"] = "postgres_fallback"

    if not graph_data.get("nodes"):
        graph_data["status"] = "no_data"
    else:
        loop = asyncio.get_running_loop()
        centrality, communities = await asyncio.gather(
            loop.run_in_executor(None, partial(compute_graph_centrality, graph_data["nodes"], graph_data["edges"])),
            loop.run_in_executor(None, partial(detect_communities, graph_data["nodes"], graph_data["edges"])),
        )
        for n in graph_data["nodes"]:
            n["centrality"] = centrality.get(n["node_id"], {"betweenness": 0, "degree": 0, "pagerank": 0})
            n["community_id"] = communities.get(n["node_id"], 0)
        graph_data["key_players"] = [
            n["node_id"] for n in sorted(graph_data["nodes"], key=lambda x: x.get("centrality", {}).get("betweenness", 0), reverse=True)[:5]
        ]

    await cache_set(cache_key, graph_data, expiry=600)
    return graph_data
```

---

### A7. Wire the crime-type / district / node-type filters end to end

`crime_frontend/src/services/networkService.ts` already has the *parameters* for `crimeType`/
`districtId`, they're just never sent from the page, and there's no `node_type` param at all yet.

```ts
getGraphData: async (
  searchQuery?: string, crimeType?: string, districtId?: string, nodeType?: string,
  opts?: { signal?: AbortSignal }
) => {
  try {
    const response = await api.get(ENDPOINTS.NETWORK.GRAPH_DATA, {
      params: { search_query: searchQuery, crime_type: crimeType, district_id: districtId, node_type: nodeType },
      signal: opts?.signal,
    });
    return response.data || null;
  } catch (error: any) {
    if (error.name === "CanceledError") throw error;
    return { status: "offline", error: error.response?.data?.detail || "Failed to connect to the backend API." };
  }
},
```

`crime_backend/MODULE_2_BACKEND/app/routers/network_router.py`:
```python
@router.get("/graph-data", response_model=None)
@limiter.limit("30/minute")
async def fetch_network_graph(
    request: Request,
    search_query: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),   # NEW
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_graph_data(db, search_query, crime_type, resolved_id, node_type=node_type)
    return {"success": True, "data": data}
```

Page-level wiring is folded into Part B (since the crime-type UI row is new anyway) — see B2.

---

## PART B — New features (from this conversation)

### B1. Tag every edge with its real crime type(s) — the foundation for the crime-type lens

Right now edges only carry a generic `relationship_type` (`KNOWS`, `WORKED_WITH`...) with no crime
type attached, so there's nothing for a "show only Theft connections" filter to check against. Fix
this at the source, in two places:

**Neo4j — store `crime_types` directly on the relationship**

`crime_backend/MODULE_2_BACKEND/app/core/neo4j_connection.py`:
```python
async def create_criminal_relationship(
    offender_id_1: str, offender_id_2: str, relationship_type: str,
    strength_score: float = 50.0, confidence_level: str = "SUSPECTED",
    crime_ids: List[str] = None, crime_types: List[str] = None,   # NEW param
    first_seen_date: str = None, last_seen_date: str = None,
):
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"Invalid relationship_type: {relationship_type}")
    query = f"""
    MATCH (c1:Criminal {{offender_id: $id1}})
    MATCH (c2:Criminal {{offender_id: $id2}})
    MERGE (c1)-[r:{relationship_type}]->(c2)
    SET r.strength_score = $strength_score,
        r.confidence_level = $confidence_level,
        r.crime_ids = $crime_ids,
        r.crime_types = $crime_types,
        r.first_seen_date = $first_seen_date,
        r.last_seen_date = $last_seen_date
    RETURN r
    """
    await run_neo4j_query(query, {
        "id1": offender_id_1, "id2": offender_id_2,
        "strength_score": strength_score, "confidence_level": confidence_level,
        "crime_ids": crime_ids or [], "crime_types": crime_types or [],
        "first_seen_date": first_seen_date, "last_seen_date": last_seen_date,
    })


async def create_victim_offender_relationship(offender_id: str, victim_id: str, crime_id: str, crime_type: str = None):
    query = """
    MATCH (c:Criminal {offender_id: $offender_id})
    MATCH (v:Victim {victim_id: $victim_id})
    MERGE (c)-[r:VICTIMIZED_AT]->(v)
    SET r.crime_id = $crime_id, r.crime_types = $crime_types, r.confidence_level = 'CONFIRMED'
    """
    await run_neo4j_query(query, {
        "offender_id": offender_id, "victim_id": victim_id,
        "crime_id": crime_id, "crime_types": [crime_type] if crime_type else [],
    })
```

`sync_neo4j.py` — pass the real crime type when relationships are created (it already loads `Crime`
rows implicitly via `CrimeOffenderLink`/`CrimeVictimLink`, just needs the type looked up):

```python
from app.models.database_models.crime_model import CrimeOffenderLink, CrimeVictimLink, Crime, District

# after fetching `links` (CrimeOffenderLink rows), also fetch crime types:
crime_result = await session.execute(select(Crime.crime_id, Crime.crime_type))
crime_type_by_id = {str(cid): ctype for cid, ctype in crime_result.all()}

# ... inside the "Group by crime_id" / pairing loop:
for crime_id, offender_ids in crimes.items():
    if len(offender_ids) > 1:
        crime_type = crime_type_by_id.get(crime_id)
        for i in range(len(offender_ids)):
            for j in range(i + 1, len(offender_ids)):
                await create_criminal_relationship(
                    offender_id_1=offender_ids[i], offender_id_2=offender_ids[j],
                    relationship_type="WORKED_WITH", strength_score=80.0,
                    confidence_level="CONFIRMED", crime_ids=[crime_id],
                    crime_types=[crime_type] if crime_type else [],
                )
                links_created += 1

# ... and in the victim-linking loop further down:
for crime_id, offender_ids in crimes.items():
    crime_type = crime_type_by_id.get(crime_id)
    for victim_id in crime_to_victims.get(crime_id, []):
        for offender_id in offender_ids:
            await create_victim_offender_relationship(offender_id, victim_id, crime_id, crime_type)
            victims_linked += 1
```

**Return `crime_types` in every edge the API sends** — `neo4j_connection.py`, inside
`get_network_graph()`'s result-processing loop:
```python
edges.append({
    "edge_id": f"{source_id}_{target_id}",
    "source_node_id": source_id, "target_node_id": target_id,
    "relationship_type": record.get("type_r") or "LINKED_TO",
    "strength_score": rel.get("strength_score", 50) if rel else 50,
    "confidence_level": rel.get("confidence_level", "SUSPECTED") if rel else "SUSPECTED",
    "crime_count": len(rel.get("crime_ids", [])) if rel else 0,
    "crime_types": rel.get("crime_types", []) if rel else [],   # NEW
})
```

Do the same in `network_router.py`'s `expand_node()` edge-building block (add
`"crime_types": rel_props.get("crime_types", [])`). The Postgres fallback already returns
`crime_types` per edge if you applied A5 above — nothing extra needed there.

---

### B2. Crime-type lens filter (click a type → dim everything else; click "All" → show everything)

The key UX rule from how professional link-analysis tools do this (i2, Sentinel Visualizer): **a
filter dims non-matching elements, it never deletes them.** That's what makes B3 (cross-filter
connections) possible — nothing is ever actually removed from the graph, just visually de-emphasized.

`crime_frontend/src/pages/CriminalNetwork.tsx` — add state and a filter row using your existing
`CRIME_TYPES` constant:

```tsx
import { CRIME_TYPES, CRIME_TYPE_COLORS } from "../constants/crimeTypes";

const [crimeTypeLens, setCrimeTypeLens] = useState<string>("All");
```

```tsx
{/* Crime-type lens row — add near your existing node-type filter buttons */}
<div className="flex items-center gap-1.5 flex-wrap ml-3 pl-3 border-l border-slate-700">
  <span className="text-xs text-slate-500 mr-1">Crime type:</span>
  {CRIME_TYPES.map((ct) => (
    <button
      key={ct}
      onClick={() => setCrimeTypeLens(ct)}
      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors border ${
        crimeTypeLens === ct
          ? "text-white border-transparent"
          : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white"
      }`}
      style={crimeTypeLens === ct ? { background: CRIME_TYPE_COLORS[ct] || "#3b82f6" } : {}}
    >
      {ct}
    </button>
  ))}
</div>
```

Pass the lens down to the graph as a prop instead of re-fetching from the backend on every click —
since every edge already carries `crime_types` (B1), switching the lens is instant, client-side, no
network round trip:

```tsx
<NetworkGraph
  ref={graphRef}
  nodes={filteredNodes}
  edges={edges}
  crimeTypeLens={crimeTypeLens === "All" ? null : crimeTypeLens}   // NEW prop
  onNodeSelect={handleNodeSelect}
  onNodeCompare={handleNodeCompare}
  onNodeExpand={handleNodeExpand}
  selectedNodeId={selectedNode?.node_id}
  highlightPath={highlightPath}
/>
```

`NetworkGraph.tsx` — add the prop and a dim (not delete) effect, same pattern as the existing
`highlightPath` dimming effect already in the file:

```tsx
interface Props {
  // ...existing props
  crimeTypeLens?: string | null;   // NEW
}

const NetworkGraph = forwardRef<NetworkGraphHandle, Props>(
  ({ nodes, edges, onNodeSelect, onNodeExpand, onNodeCompare, selectedNodeId, highlightPath, crimeTypeLens }, ref) => {
    // ...

    // include crime_types on the edge data when building elements:
    // data: { ..., crimeTypes: e.crime_types || [] }

    useEffect(() => {
      if (!cyRef.current) return;
      cyRef.current.edges().removeClass("lens-dimmed");
      cyRef.current.nodes().removeClass("lens-dimmed");
      if (!crimeTypeLens) return;

      const matchingEdges = cyRef.current.edges().filter(
        (e) => (e.data("crimeTypes") || []).includes(crimeTypeLens)
      );
      const nonMatching = cyRef.current.edges().not(matchingEdges);
      nonMatching.addClass("lens-dimmed");

      // Dim nodes that have NO matching edge and aren't isolated-by-design
      const connectedNodeIds = new Set(matchingEdges.map((e) => [e.source().id(), e.target().id()]).flat());
      cyRef.current.nodes().forEach((n) => {
        if (!connectedNodeIds.has(n.id())) n.addClass("lens-dimmed");
      });
    }, [crimeTypeLens]);
```

Add the dim style alongside your existing `.dimmed` selector:
```tsx
{
  selector: ".lens-dimmed",
  style: { "opacity": 0.12 },   // more aggressive than the path-highlight ".dimmed" (0.2) so the active lens really stands out
},
```

---

### B3. Cross-filter connections never disappear (the "click still shows everything" fix)

This is the actual fix for your example: filtered to "Theft", node also has a "Robbery" link — that
link should never vanish, it should be visible (dimmed by the lens) and light back up the moment you
click that node.

`NetworkGraph.tsx` — extend the existing `focusOnNode` handle so clicking a node **temporarily lifts
the lens dimming for that node's own connections**, regardless of `crimeTypeLens`:

```tsx
useImperativeHandle(ref, () => ({
  focusOnNode: (nodeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;
    const node = cy.getElementById(nodeId);
    if (node.empty()) return;

    const neighborhood = node.closedNeighborhood();
    cy.elements().addClass("dimmed");
    neighborhood.removeClass("dimmed");
    neighborhood.removeClass("lens-dimmed");   // NEW — a clicked node's own links always show, lens or no lens

    cy.animate({ fit: { eles: neighborhood, padding: 60 }, duration: 500, easing: "ease-in-out-cubic" });
  },
  // ...clearFocus unchanged
}));
```

Because `handleNodeExpand` (already in `CriminalNetwork.tsx`) fetches that node's full neighborhood
from the backend if it isn't loaded yet, and `navigateToNode` already calls `handleNodeExpand`
whenever the clicked node's edges aren't present — clicking a node that has out-of-lens connections
will pull them in and un-dim them automatically, with no extra code needed beyond the two changes
above.

**Sidebar: show every connection, labeled with crime type + confidence, regardless of the active lens**

`CriminalNetwork.tsx` — your existing "Connected Edges" block in the right panel already lists every
edge touching the selected node. Just enrich each row instead of only showing `relationship_type`:

```tsx
<div className="space-y-1">
  {edges.filter(e => e.source_node_id === selectedNode.node_id || e.target_node_id === selectedNode.node_id).map((e, i) => {
    const otherId = e.source_node_id === selectedNode.node_id ? e.target_node_id : e.source_node_id;
    const otherNode = nodes.find(n => n.node_id === otherId);
    const isConfirmed = e.confidence_level === "CONFIRMED";
    return (
      <div key={i} className="flex flex-col gap-1 text-xs p-2 bg-slate-800/50 rounded">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full" style={{ background: NODE_COLORS[otherNode?.node_type || "criminal"] }} />
            <span className="text-slate-300">{otherNode?.label || otherId}</span>
          </div>
          <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${isConfirmed ? "bg-green-900/40 text-green-400" : "bg-yellow-900/40 text-yellow-400"}`}>
            {e.confidence_level || "SUSPECTED"}
          </span>
        </div>
        {(e.crime_types?.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-1 pl-4">
            {e.crime_types!.map((ct) => (
              <span key={ct} className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: (CRIME_TYPE_COLORS[ct] || "#6366F1") + "30", color: CRIME_TYPE_COLORS[ct] || "#6366F1" }}>
                {ct}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  })}
</div>
```

(Add `crime_types?: string[]` and `confidence_level?: string` to the `NetworkEdge` interface at the top
of `CriminalNetwork.tsx` — the fields are already flowing from the backend after B1.)

---

### B4. Confirmed vs. suspected connections shown as solid vs. dashed lines

Your data already has `confidence_level` on every edge (backend has always returned it) — it's just
never used for styling. `NetworkGraph.tsx`:

```tsx
{
  selector: "edge",
  style: {
    "width": (ele: cytoscape.EdgeSingular) => 1 + ele.data("strength") / 30,
    "line-color": "#334155",
    "target-arrow-color": "#334155",
    "target-arrow-shape": "triangle",
    "curve-style": "bezier",
    "label": "data(label)",
    "font-size": "8px",
    "color": "#64748b",
    "text-rotation": "autorotate",
    "line-style": (ele: cytoscape.EdgeSingular) => ele.data("confidence") === "SUSPECTED" ? "dashed" : "solid", // NEW
  },
},
```

Add `confidence: e.confidence_level || "SUSPECTED"` to the edge `data` mapping in `buildElements`, and
add a small legend line near the existing color legend at the bottom of the page:
`"— Confirmed    ┄┄ Suspected"`.

---

### B5. "Highlight Key Players" button

Your backend already computes `key_players` (the 5 most-central node IDs by betweenness) on every
graph response — it's just never read by the page. Add the read + a button + a graph handle method:

`CriminalNetwork.tsx`:
```tsx
const [keyPlayerIds, setKeyPlayerIds] = useState<string[]>([]);

// in the initial fetch effect, alongside setNodes/setEdges:
setKeyPlayerIds(g.key_players || []);
```

```tsx
{/* button near the view-mode toggle */}
<button
  onClick={() => graphRef.current?.highlightKeyPlayers(keyPlayerIds)}
  disabled={keyPlayerIds.length === 0}
  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-amber-600/20 text-amber-400 border border-amber-600/40 hover:bg-amber-600/30"
>
  <Brain className="h-3.5 w-3.5" /> Highlight Key Players
</button>
```

`NetworkGraph.tsx` — extend the imperative handle:
```tsx
export interface NetworkGraphHandle {
  focusOnNode: (nodeId: string) => void;
  clearFocus: () => void;
  highlightKeyPlayers: (nodeIds: string[]) => void;   // NEW
}

// inside useImperativeHandle:
highlightKeyPlayers: (nodeIds: string[]) => {
  const cy = cyRef.current;
  if (!cy) return;
  cy.elements().removeClass("dimmed");
  cy.elements().removeClass("key-player");
  const keyEls = cy.collection();
  nodeIds.forEach((id) => keyEls.merge(cy.getElementById(id)));
  cy.elements().not(keyEls).addClass("dimmed");
  keyEls.addClass("key-player");
  cy.animate({ fit: { eles: keyEls, padding: 80 }, duration: 500, easing: "ease-in-out-cubic" });
},
```

```tsx
// style array addition
{
  selector: ".key-player",
  style: { "border-color": "#f59e0b", "border-width": 6, "border-style": "double" },
},
```

---

### B6. AI "Explain this connection" — click a link, get a one-line reason why it matters

New backend function, following the exact same pattern as your existing
`get_network_analysis_summary` — `crime_backend/MODULE_2_BACKEND/app/services/gemini_service.py`:

```python
async def get_edge_connection_insight(
    node_a: Dict[str, Any], node_b: Dict[str, Any], edge: Dict[str, Any],
) -> str:
    """Generate a short AI explanation for a single connection between two network nodes"""
    prompt = f"""
You are assisting a Karnataka Police intelligence analyst reviewing one specific link in a criminal
network graph.

ENTITY A: {node_a.get('label', 'Unknown')} ({node_a.get('node_type', 'unknown')})
ENTITY B: {node_b.get('label', 'Unknown')} ({node_b.get('node_type', 'unknown')})
RELATIONSHIP TYPE: {edge.get('relationship_type', 'LINKED_TO')}
CONFIDENCE: {edge.get('confidence_level', 'SUSPECTED')}
CRIME TYPES INVOLVED: {', '.join(edge.get('crime_types', [])) or 'Unspecified'}
STRENGTH SCORE: {edge.get('strength_score', 50)}/100

In 2-3 sentences, explain what this specific connection likely means operationally and what an
investigator should check next. Be concise and factual — no filler, no restating the input verbatim.
"""
    result = await call_gemini(prompt)
    return result.get("text", "") or "AI insight unavailable for this connection right now."
```

New router endpoint — `crime_backend/MODULE_2_BACKEND/app/routers/network_router.py`:
```python
from pydantic import BaseModel

class EdgeInsightRequest(BaseModel):
    node_a: dict
    node_b: dict
    edge: dict

@router.post("/edge-insight")
@limiter.limit("15/minute")
async def edge_insight(
    request: Request,
    payload: EdgeInsightRequest,
    current_user=Depends(get_current_user),
):
    from app.services.gemini_service import get_edge_connection_insight
    text = await get_edge_connection_insight(payload.node_a, payload.node_b, payload.edge)
    return {"success": True, "data": {"insight": text}}
```

`networkService.ts` — new call:
```ts
getEdgeInsight: async (nodeA: any, nodeB: any, edge: any) => {
  try {
    const response = await api.post(ENDPOINTS.NETWORK.EDGE_INSIGHT, { node_a: nodeA, node_b: nodeB, edge });
    return response.data?.insight ?? null;
  } catch (error) {
    console.error("Error fetching edge insight:", error);
    return null;
  }
},
```
(add `EDGE_INSIGHT: "/network/edge-insight"` to `constants/apiEndpoints.ts`'s `NETWORK` block.)

Frontend wiring — `NetworkGraph.tsx` needs an edge-tap handler + callback prop:
```tsx
interface Props {
  // ...existing
  onEdgeSelect?: (sourceId: string, targetId: string, edgeData: any) => void;   // NEW
}

// alongside the existing cy.on("tap", "node", ...) handler:
cy.on("tap", "edge", (evt: cytoscape.EventObject) => {
  const edgeData = evt.target.data();
  onEdgeSelect?.(edgeData.source, edgeData.target, edgeData);
});
```

`CriminalNetwork.tsx` — small popover state + handler:
```tsx
const [edgeInsight, setEdgeInsight] = useState<{ text: string; loading: boolean } | null>(null);

const handleEdgeSelect = async (sourceId: string, targetId: string, edgeData: any) => {
  const nodeA = nodes.find(n => n.node_id === sourceId);
  const nodeB = nodes.find(n => n.node_id === targetId);
  if (!nodeA || !nodeB) return;
  setEdgeInsight({ text: "", loading: true });
  const insight = await networkService.getEdgeInsight(nodeA, nodeB, edgeData);
  setEdgeInsight({ text: insight || "No insight available.", loading: false });
};
```
```tsx
<NetworkGraph /* ...existing props */ onEdgeSelect={handleEdgeSelect} />

{edgeInsight && (
  <div className="absolute bottom-16 left-4 right-4 bg-blue-950/90 backdrop-blur border border-blue-500/30 rounded-lg p-3 max-w-md">
    <div className="flex items-center gap-2 mb-1">
      <Brain className="h-3.5 w-3.5 text-blue-400" />
      <span className="text-xs font-semibold text-white">Connection Insight</span>
      <button onClick={() => setEdgeInsight(null)} className="ml-auto text-slate-500 hover:text-white text-xs">✕</button>
    </div>
    <p className="text-xs text-blue-200">{edgeInsight.loading ? "Analyzing connection…" : edgeInsight.text}</p>
  </div>
)}
```

---

## File-by-file index (everything touched in this document)

| File | What changes |
|---|---|
| `crime_backend/.../routers/crimes_router.py` | A1: limit/date-bound `/map-data` |
| `crime_frontend/.../maps/HeatLayer.tsx` | A1: new file, canvas heat layer |
| `crime_frontend/.../maps/CrimeMap.tsx` | A1: use `HeatLayer` for heatmap mode |
| `crime_frontend/.../network/ConnectivityMatrix.tsx` | A2: cap or canvas-render |
| `crime_frontend/.../network/NetworkGraph.tsx` | A3, B2, B3, B4, B5, B6: incremental updates, spacing, lens dimming, line style, key players, edge-click |
| `crime_backend/.../core/neo4j_connection.py` | A4, B1: type-aware root match, `crime_types` on relationships |
| `crime_backend/.../services/network_service.py` | A5, A6: real Postgres fallback nodes/edges, executor offload |
| `crime_backend/.../routers/network_router.py` | A4/A7: `node_type` param, B6: `/edge-insight` endpoint |
| `crime_frontend/.../services/networkService.ts` | A7: pass filters + abort signal, B6: `getEdgeInsight` |
| `crime_backend/sync_neo4j.py` | B1: pass real crime type into relationship creation |
| `crime_backend/.../services/gemini_service.py` | B6: `get_edge_connection_insight` |
| `crime_frontend/.../constants/apiEndpoints.ts` | B6: `EDGE_INSIGHT` endpoint constant |
| `crime_frontend/.../pages/CriminalNetwork.tsx` | A7, B2, B3, B5, B6: filter row, sidebar enrich, buttons, popover |

## Suggested build order

1. A1 + A2 (stop the hangs first — quickest wins, no data model changes)
2. A3 (spacing + incremental graph — also quick, no backend change)
3. A6 (executor offload — quick, backend-only)
4. B1 (crime_types on edges — foundation everything in Part B depends on)
5. A4 + A5 (fix what data actually reaches the graph)
6. B4 + B5 (styling/buttons — cheap once B1 data exists)
7. B2 + B3 (the lens + cross-filter behavior — depends on B1)
8. A7 (wire remaining filters through)
9. B6 (AI edge insight — independent, add whenever)




# SHASTRA — Audit Addendum (v3)
### Deep recheck of the codebase against the two previous documents
*(Reference only — nothing changed in your repo.)*

You asked me to re-verify everything, including backend↔frontend wiring, before you start applying
fixes. I went back through the actual files again (not just my notes) and traced every filter/prop/field
end to end. Here's the honest result: **one real bug I'd missed**, one **response-model inconsistency**
worth fixing while you're in there, and a handful of things I re-verified and can now confirm are
**not** problems (so you don't spend time on them).

---

## 1. NEW FINDING — the map filters and my A1 fix would silently conflict

This is the important one. I re-read `CrimeMapPage.tsx` fully this time (I'd only read the map
component before). Here's what's actually happening:

```tsx
// CrimeMapPage.tsx — current behavior
useEffect(() => {
  const fetch = async () => {
    const data = await crimeService.getMapData();   // called ONCE, no filters, on mount only
    dispatch(setMapCrimes(data));
  };
  fetch();
}, []);   // <- empty deps: never re-runs when filters change

const filteredCrimes = (mapCrimes as Crime[]).filter((c) => {
  if (filters.crimeType !== "All" && c.crime_type !== filters.crimeType) return false;
  if (filters.district !== "All Districts" && c.district !== filters.district) return false;
  if (filters.dateFrom && new Date(c.date_time) < new Date(filters.dateFrom)) return false;
  if (filters.dateTo && new Date(c.date_time) > new Date(filters.dateTo)) return false;
  // ... time-of-day filter too
});
```

So the date range picker, crime-type dropdown, district dropdown, and time-of-day dropdown in
`MapControls` are **all filtering an array that was already fully downloaded once** — this confirms the
hang cause even more precisely than before (it's not just "heatmap mode renders too much," it's "the
page always holds the entire crimes table in memory, and always has, regardless of what filters are
selected").

**Why this matters for the fix I gave you:** my A1 fix in the previous document added a `days=90`
default cutoff on the backend. On its own, that would silently break this page — if someone picks a
`dateFrom` earlier than 90 days ago, the backend would have already discarded those rows before the
client-side filter ever runs, and they'd see an empty map with no explanation. That's a real regression
I need to correct, not just a stylistic nitpick.

**The correct fix** is to make the existing filters actually reach the backend (they already exist in
Redux, `MapControls` already collects them, `crimeService.getMapData(filters?)` already accepts a
filters object per its signature — none of that is new, it's just never wired up), and refetch when
they change instead of filtering a static blob:

`crime_backend/MODULE_2_BACKEND/app/routers/crimes_router.py` — replace the `days` idea with real
filter params that mirror what the UI already collects:

```python
from datetime import date

@router.get("/map-data")
async def get_map_data(
    file_format: str = Query("json", enum=["json", "csv"]),
    crime_type: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(5000, ge=1, le=20000),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_district = await resolve_district_id(db, district_id)  # same helper already used in network_router.py

    stmt = select(Crime, District, PoliceStation).join(
        District, Crime.district_id == District.district_id, isouter=True
    ).join(
        PoliceStation, Crime.police_station_id == PoliceStation.station_id, isouter=True
    )
    if crime_type and crime_type != "All":
        stmt = stmt.where(Crime.crime_type == crime_type)
    if resolved_district and resolved_district != "All Districts":
        stmt = stmt.where(Crime.district_id == resolved_district)
    if date_from:
        stmt = stmt.where(Crime.date_of_occurrence >= date_from)
    if date_to:
        stmt = stmt.where(Crime.date_of_occurrence <= date_to)
    if not date_from and not date_to:
        # No date range picked at all → still bound the query so "show everything ever" can't happen
        from datetime import timedelta
        stmt = stmt.where(Crime.date_of_occurrence >= date.today() - timedelta(days=180))

    stmt = scope_district_filter(stmt, current_user, Crime.district_id)
    stmt = stmt.order_by(Crime.date_of_occurrence.desc()).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()
    # ... existing formatted_data loop unchanged
```

`crime_frontend/src/pages/CrimeMapPage.tsx` — fetch on filter change instead of once, and drop the
client-side re-filtering (the backend now does it):

```tsx
useEffect(() => {
  const controller = new AbortController();
  const fetchData = async () => {
    setLoading(true);
    const data = await crimeService.getMapData({
      crime_type: filters.crimeType !== "All" ? filters.crimeType : undefined,
      district_id: filters.district !== "All Districts" ? filters.district : undefined,
      date_from: filters.dateFrom || undefined,
      date_to: filters.dateTo || undefined,
    }, { signal: controller.signal });
    dispatch(setMapCrimes(data));
    setLoading(false);
  };
  fetchData();
  return () => controller.abort();
}, [filters.crimeType, filters.district, filters.dateFrom, filters.dateTo]);

// The time-of-day filter has no server-side column to match against (it's derived from a timestamp,
// not stored as its own field) — keep only THAT one filter client-side, on the now-much-smaller set:
const filteredCrimes = (mapCrimes as Crime[]).filter((c) => {
  if (filters.timeOfDay && filters.timeOfDay !== "All") {
    const hour = new Date(c.date_time).getHours();
    if (filters.timeOfDay === "Morning (6AM-12PM)" && (hour < 6 || hour >= 12)) return false;
    if (filters.timeOfDay === "Afternoon (12PM-6PM)" && (hour < 12 || hour >= 18)) return false;
    if (filters.timeOfDay === "Evening (6PM-10PM)" && (hour < 18 || hour >= 22)) return false;
    if (filters.timeOfDay === "Night (10PM-6AM)" && (hour < 22 && hour >= 6)) return false;
  }
  return true;
});
```

`crime_frontend/src/services/crimeService.ts` — `getMapData` needs to actually pass params + accept an
abort signal (today it's called with zero arguments everywhere, so the params plumbing needs to exist):

```ts
getMapData: async (
  filters?: { crime_type?: string; district_id?: string; date_from?: string; date_to?: string },
  opts?: { signal?: AbortSignal }
) => {
  try {
    const response = await api.get(ENDPOINTS.CRIMES.MAP_DATA, { params: filters, signal: opts?.signal });
    return response.data || [];
  } catch (error: any) {
    if (error.name === "CanceledError") throw error;
    console.error("Error fetching map data:", error);
    return [];
  }
},
```

This replaces the A1 fix from the previous document — same hang fix, but now it won't quietly break
your existing date filter.

---

## 2. NEW FINDING — Pydantic response model for the network graph doesn't declare `crime_types`

`crime_backend/MODULE_2_BACKEND/app/models/response_models/network_response.py` has a `NetworkEdge`
schema that's out of date with what the service actually returns (it's missing `crime_types`, and it
was already missing a few other fields the service adds like `edge_id`/`crime_count` consistency). This
isn't breaking anything **today** because `network_router.py` declares
`@router.get("/graph-data", response_model=None)` — that `response_model=None` disables FastAPI's
response validation/filtering entirely, so the raw dict passes through untouched. But it means this
schema file is silently out of sync with reality, and if anyone re-enables response validation later
(a very normal thing to do "for API docs/type-safety"), the new `crime_types` field would get silently
stripped out of every response and B2/B3 from the feature document would quietly stop working with no
error anywhere. Worth fixing now while it's fresh:

```python
class NetworkEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    strength_score: float = 50
    confidence_level: str = "SUSPECTED"
    crime_count: int = 0
    crime_types: List[str] = []   # NEW — keep this in sync with whatever network_service.py returns
```

---

## 3. Re-checked and confirmed OK (no action needed — listing these so you know they were checked, not skipped)

- **`RELATIONSHIP_TYPES` allow-list** (`app/core/config.py`) already includes `WORKED_WITH` and
  `VICTIMIZED_AT`, which is all B1 needs on the Neo4j side — no allow-list change required. The new
  `CO_OFFENDER` relationship type I introduced is only used in the **Postgres fallback**, which builds
  plain dicts, not Cypher — the allow-list (a Neo4j-injection guard) doesn't apply there and isn't
  bypassed by this.
- **Gemini AI call caching**: I was going to flag "clicking through edges repeatedly could rack up AI
  calls," but `app/core/gemini_client.py`'s `call_gemini()` already hashes the prompt and checks Redis
  first (`get_cached_gemini_response` / `cache_gemini_response`) — since the edge-insight prompt is
  fully determined by the two node labels + edge data, repeat clicks on the same connection are already
  free cache hits. No extra caching code needed for B6.
- **Schema field names used throughout both documents** (`Offender.offender_id`, `Victim.victim_id`,
  `Location.location_id`, `CrimeOffenderLink.is_confirmed`, `CrimeVictimLink.victim_id`,
  `Crime.crime_type`) — all verified directly against `offender_model.py`, `victim_model.py`,
  `location_model.py`, `crime_model.py`. No typos or wrong-field assumptions found.
- **`apiEndpoints.ts` → `ENDPOINTS.NETWORK`** — verified the exact existing keys
  (`GRAPH_DATA`, `NODE_DETAIL`, `AI_SUMMARY`, `EXPAND`, `SHORTEST_PATH`) match what both documents
  reference; only the new `EDGE_INSIGHT` key needs adding, as already noted.
- **`offenders_router.py`'s `/offenders/{id}/network`** delegates straight to
  `network_service.get_node_detail` — it's not a second, diverging implementation that also needs
  patching. One code path, already covered.
- **Hotspot Analysis page (`HotspotAnalysis.tsx` / `hotspots_router.py`)** queries the pre-aggregated
  `Hotspot` table, not raw crime rows — this table is small by design (clusters, not individual crimes),
  so it does **not** have the same unbounded-query risk as `/crimes/map-data`. No fix needed there; the
  hang you saw is specifically the raw-crime heatmap, not this page.
- **`tests/test_network.py`** hits `/api/network/graph` (note: not `/api/network/graph-data`) — that's a
  pre-existing typo in the test itself, unrelated to anything in either document, and not something my
  changes touch or worsen. Flagging only so you're aware it's a separate, minor loose end if you ever
  wonder why that test doesn't seem to test the real endpoint.

---

## 4. Updated file-by-file index (only files affected by this addendum)

| File | What changes |
|---|---|
| `crime_backend/.../routers/crimes_router.py` | **Replaces** the earlier A1 fix — real filter params + `resolve_district_id`, instead of a blanket day cutoff |
| `crime_frontend/.../pages/CrimeMapPage.tsx` | Fetch on filter change; drop client-side crime-type/district/date filtering (backend does it now); keep only time-of-day client-side |
| `crime_frontend/.../services/crimeService.ts` | `getMapData` now takes real filter params + abort signal |
| `crime_backend/.../models/response_models/network_response.py` | Add `crime_types: List[str] = []` to `NetworkEdge` so the schema matches reality |

Everything else in the first two documents checked out against the actual code and needs no changes.

---

## 5. Recommended order (unchanged from v2, with the correction folded in)

1. **A1 (corrected version above)** + A2 — stop the hangs, using the filter-aware map query instead of
   the flat day-cutoff
2. A3 (spacing + incremental graph)
3. A6 (executor offload)
4. B1 (crime_types on edges) + the `network_response.py` schema fix from this addendum
5. A4 + A5 (real victim/location data)
6. B4 + B5 (line styling / key players button)
7. B2 + B3 (crime-type lens + cross-filter connections)
8. A7 (remaining filter wiring)
9. B6 (AI edge insight)