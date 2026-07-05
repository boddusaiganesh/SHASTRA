# Part 2 — Best-in-Class Graph Tech + Ego-Expand Navigation + Full-Database "Grid" (Matrix) View

This is a follow-up to `Criminal_Network_Graph_Diagnosis_and_Fix_Plan.md`, based on further research into (1) what the strongest graph-visualization systems in the world actually are, used specifically for criminal/link-analysis work, and (2) how to design the two features you asked for: **click a node → zoom into its connections with Back/Forward navigation**, and **a grid/matrix view showing every connection (and every non-connection) across the whole database.**

---

## 1. Research: What's actually "best in the world" for this, and who uses it

### 1.1 The category leader for *exactly* your use case: Linkurious / Ogma
This isn't a generic recommendation — it's the specific tool built for criminal-network link analysis, and it shows up repeatedly in real casework:
- The International Consortium of Investigative Journalists (ICIJ) used <cite index="11-1">Linkurious combined with Neo4j to visualize and explore the FinCEN Files and, separately, the Pandora Papers leak, which involved 14 offshore-services firms and 11.9 million records spanning 2.94 terabytes</cite>.
- <cite index="12-1">RS21 built a criminal-justice investigation tool called Quaro on top of a graph data model using a POLE structure — Persons, Objects, Locations, Events — with Linkurious Enterprise as the exploration and visualization layer</cite>, specifically to let district attorneys' offices find connections such as the same weapon appearing in two different crimes, or a victim in one case being a witness in another.
- Linkurious's own JS rendering engine, **Ogma**, is a commercial WebGL library built for exactly this scale: <cite index="9-1">it renders 100,000+ edges smoothly even on old hardware, with a force-directed layout that can process more than a million edges in seconds on modern hardware</cite>, and unlike Sigma.js, <cite index="9-1">it automatically falls back to Canvas if WebGL isn't available</cite>.
- Directly relevant to your "isolated nodes" problem: <cite index="9-1">Ogma ships with built-in aggregation and grouping — node/edge grouping, sub-graph transformations, path shortening, visual clustering, and level-of-detail zooming — specifically because plain force-directed rendering turns into a "visual hairball" without it</cite>.
- It also connects to more than just Neo4j: <cite index="11-1">Linkurious provides visualization and exploration across Neo4j, Azure Cosmos DB, Memgraph, Amazon Neptune, Google Spanner Graph, TitanDB, DataStax, AllegroGraph, and FalkorDB</cite> — so if you ever outgrow Neo4j itself, your visualization layer doesn't have to change.

**Bottom line:** if budget allows, Linkurious Enterprise (or embedding Ogma directly into your React app instead of Cytoscape) is the most proven "best in the world" answer for a criminal-network dashboard specifically — it's not a repurposed general graph library, it's what actual law-enforcement/investigative-journalism teams run in production for this exact problem. It is a paid/commercial product; treat it as the "if this becomes a funded, long-term product" tier rather than the immediate next step.

### 1.2 Open-source rendering engines, ranked by what they're actually good at
Current (2026) guidance converges on the same split across every independent source checked:

| Library | Best for | Scale ceiling | Notes |
|---|---|---|---|
| **Cytoscape.js** (what you have now) | Rich graph algorithms, styling, analysis-heavy UI | <cite index="4-1">Canvas-based rendering degrades noticeably above ~3,000-5,000 nodes; COSE layout runs synchronously on the main thread and blocks the UI during layout on graphs above a few thousand nodes</cite> | ~500K weekly npm downloads; richest built-in algorithm set (shortest path, centrality) |
| **Sigma.js** + `graphology` | Large-graph WebGL rendering when you don't need built-in algorithms | <cite index="4-1">practical ceiling around 100,000-500,000 nodes depending on edge density and hardware</cite>, though <cite index="9-1">it struggles with 5,000 nodes once custom icons are involved, and force-directed layout speed drops beyond 50,000 edges</cite> | <cite index="4-1">Graph algorithms (Dijkstra, A*, betweenness, degree, eigenvector centrality, Louvain, Label Propagation, ForceAtlas2) are available as separate graphology packages, and ForceAtlas2 has a WebWorker mode that runs physics off the main thread</cite> |
| **Ogma** (commercial) | Large graphs *and* rich UX out of the box | <cite index="30-1">smooth well past 10,000 nodes on screen</cite>, <cite index="9-1">100,000+ edges "like a breeze"</cite> | GPU-accelerated, built-in clustering/LOD, enterprise support/SLAs |
| **vis-network** | Quick interactive diagrams, drag/drop editing | Canvas-based, similar ceiling to Cytoscape | Best out-of-the-box physics/interactivity, weaker algorithm library |
| **G6 / Graphin** (Ant Design) | Small-to-moderate graphs, rich styling | Good for moderate scale | Strong in finance/security/bio use cases per its own published dev interviews; some docs are Chinese-first |
| **Cosmos** | Extreme scale, GPU simulation | <cite index="1-1">GPU-accelerated simulation, not just rendering</cite> | Best raw scale; weakest styling flexibility |

Independent practical guidance for 2026 sums it up as: <cite index="2-1">pick Cytoscape.js when the graph is an analysis object — algorithms, layouts, centrality, path finding matter — pick Sigma.js when the graph is large enough that WebGL rendering and a graphology data layer matter more than built-in algorithms</cite>. Given your current 100-1,000-node scale plus the fact that you're actively using Cytoscape's algorithmic side (shortest path, centrality overlays), **staying on Cytoscape.js now and re-evaluating Sigma.js/Ogma once you're consistently pushing 3,000+ nodes on screen is the correct call** — don't rewrite the renderer to solve a data-sparsity problem.

### 1.3 On the database side (you asked "apart from Neo4j")
You don't have a database problem right now — your Postgres+Neo4j split with a fallback path is a sound architecture, and Neo4j Community + APOC is genuinely fine at your current data volume. If you ever do outgrow Neo4j Community specifically, the two moves that matter are (a) Neo4j Enterprise / AuraDB for clustering and Graph Data Science support, or (b) Memgraph as an in-memory, Cypher-compatible alternative built for lower query latency at similar semantics — but this is a "when you have millions of nodes and query latency is the bottleneck" decision, not a "fix my graph" decision. Don't reach for it yet.

---

## 2. Feature Spec: Click node → zoom into its connections, with Back/Forward navigation

This is the standard **"ego-network exploration"** pattern from graph-visualization research and is exactly what tools like Ogma and Neo4j Bloom implement as their primary interaction model. Design below is buildable directly on your current Cytoscape.js stack — no renderer swap required.

### 2.1 What "zoom in on connections" should actually do
1. User clicks Node A.
2. Camera animates (`cy.animate()`) to fit Node A + its direct neighbors in the viewport — not just a static select.
3. Non-neighbor nodes fade out (`.dimmed` class — you already have this pattern in `NetworkGraph.tsx` for `highlightPath`, just needs to be triggered on click too, not only shift-click compare).
4. The right panel shows Node A's detail (you already have this).
5. **New:** a breadcrumb/history stack records this as a navigation step.

### 2.2 Back/Forward — implementation options, ranked
**Option A (recommended, minimal dependency): a simple in-app history stack.** You don't need a generic undo/redo library for this — it's conceptually identical to browser history:

```tsx
// CriminalNetwork.tsx — add alongside existing state
const [navHistory, setNavHistory] = useState<NetworkNode[]>([]);
const [navIndex, setNavIndex] = useState(-1);

const navigateToNode = (node: NetworkNode, fromHistory = false) => {
  setSelectedNode(node);
  if (!fromHistory) {
    const truncated = navHistory.slice(0, navIndex + 1); // drop any "future" if user branched
    setNavHistory([...truncated, node]);
    setNavIndex(truncated.length);
  }
  cyRef.current?.focusOnNode(node.node_id); // see 2.3 below
};

const goBack = () => {
  if (navIndex <= 0) return;
  setNavIndex(navIndex - 1);
  navigateToNode(navHistory[navIndex - 1], true);
};
const goForward = () => {
  if (navIndex >= navHistory.length - 1) return;
  setNavIndex(navIndex + 1);
  navigateToNode(navHistory[navIndex + 1], true);
};
```

```tsx
// Toolbar UI, next to existing search/filter controls
<button onClick={goBack} disabled={navIndex <= 0} className="...">
  <ChevronLeft className="h-4 w-4" /> Back
</button>
<button onClick={goForward} disabled={navIndex >= navHistory.length - 1} className="...">
  Forward <ChevronRight className="h-4 w-4" />
</button>
<div className="flex items-center gap-1 text-xs text-slate-400">
  {navHistory.slice(Math.max(0, navIndex - 3), navIndex + 1).map((n, i) => (
    <React.Fragment key={n.node_id}>
      {i > 0 && <ChevronRight className="h-3 w-3" />}
      <button onClick={() => { setNavIndex(navHistory.indexOf(n)); navigateToNode(n, true); }}
              className="hover:text-white hover:underline">
        {n.label}
      </button>
    </React.Fragment>
  ))}
</div>
```

This gives you a literal breadcrumb trail (`Criminal A → Criminal C → Location X`) plus Back/Forward buttons — the exact browser-history mental model, and it's ~30 lines with zero new dependencies.

**Option B — `cytoscape-undo-redo`.** A dedicated Cytoscape.js extension exists for this: <cite index="46-1">it lets you register named actions with their undo functions, and call `ur.undo()`/`ur.redo()`</cite>, with <cite index="49-1">`ur.getUndoStack()`/`ur.getRedoStack()` to inspect history</cite>. This is the right tool if you also want undo/redo for graph *edits* (e.g. an analyst manually adding a note or merging two nodes) — for pure navigation history, Option A is simpler and gives you more UI control (the breadcrumb labels).

### 2.3 The "zoom to neighborhood" camera behavior
```tsx
// NetworkGraph.tsx — expose a method the parent can call via a ref
useImperativeHandle(ref, () => ({
  focusOnNode: (nodeId: string) => {
    const cy = cyRef.current;
    if (!cy) return;
    const node = cy.getElementById(nodeId);
    const neighborhood = node.closedNeighborhood(); // node + direct neighbors + connecting edges

    cy.elements().addClass('dimmed');
    neighborhood.removeClass('dimmed');

    cy.animate({
      fit: { eles: neighborhood, padding: 60 },
      duration: 500,
      easing: 'ease-in-out-cubic',
    });
  },
}));
```
`closedNeighborhood()` is a built-in Cytoscape.js selector — no extension needed for the core zoom-to-neighbors behavior.

### 2.4 Fetching the neighbors themselves — reuse & fix `expand_node`
Right now `handleNodeExpand` (double-click) calls `/expand/{node_id}` and parses raw Neo4j rows inline. For the *click* interaction (not double-click-to-add), you want a fast, already-normalized response. Apply the `normalize_node()` fix from Part 1 §4.5, then:

```tsx
const handleNodeClick = async (node: NetworkNode) => {
  navigateToNode(node);
  // If the neighbors aren't already loaded in `nodes`/`edges` (e.g. user searched
  // and only has a partial graph), lazily fetch them:
  const alreadyLoaded = edges.some(e => e.source_node_id === node.node_id || e.target_node_id === node.node_id);
  if (!alreadyLoaded) {
    const res = await networkService.expandNode(node.node_id); // now returns {nodes, edges}
    setNodes(prev => mergeById(prev, res.nodes));
    setEdges(prev => mergeById(prev, res.edges));
  }
};
```

### 2.5 If you later move to Ogma/Linkurious instead
This entire pattern is a first-class, built-in feature there rather than something you assemble — Ogma calls it out explicitly as "out-of-the-box" node/edge grouping, sub-graph transformation, and level-of-detail zooming, and Neo4j Bloom (Neo4j's own visualization tool) has the same "click to expand, double-click to search-around" model built in with zero custom code. Worth knowing so you don't over-invest in Option A/B above if a platform migration is already planned.

---

## 3. Feature Spec: A "Grid View" of the whole database's connections

What you're describing — "show all the connections of the complete database, where it is connected and where it is not" — is a well-established visualization technique with a name: the **adjacency matrix view**. This is not a Cytoscape feature; it's a genuinely different visual encoding that you build as a second view, and it is specifically the industry-standard *complement* to a node-link graph for exactly the problem you're describing.

### 3.1 Why this is the right tool for "where it is / isn't connected"
The core academic finding, confirmed across multiple sources: <cite index="26-1">for sparse and small graphs, node-link diagrams are the most efficient approach, whereas for dense graphs with attached data, adjacency matrices are the better choice, and because real graphs are often globally sparse but locally dense, combining both visual metaphors is the most effective approach</cite>. That's precisely your situation — mostly-isolated nodes with a few dense clusters. A dedicated tool for this exact large-graph-connectivity problem, Graffinity, exists specifically because <cite index="27-1">standard node-link diagrams are helpful for judging connectivity but don't scale to large networks, and adjacency matrices don't scale to large networks either and are only suitable for judging connectivity between adjacent nodes</cite> — meaning even the matrix view benefits from the same query-driven "only show a relevant subset" approach recommended in Part 1.

In an adjacency matrix: <cite index="28-1">there is a row and a column for every node, and the cell at the intersection of a row and column holds a mark indicating the presence, absence, or weight of a link between those two nodes — completely eliminating the occlusion problem that node-link views have on large, dense networks, since every possible link gets its own dedicated cell</cite>. That last point is exactly your ask: every pair of criminals gets one cell, so "where is it NOT connected" is as visible as "where it IS connected" — something a force-directed layout structurally can't show you (empty space just means "not currently laid out near each other," not "not connected").

### 3.2 The one thing that makes or breaks a matrix view: row/column ordering
A naive alphabetical or ID-ordered matrix looks like random noise. The standard fix: <cite index="24-1">sorting rows/columns by a meaningful attribute reveals dense blocks along the diagonal — e.g. sorting university students by graduation year showed clear dense boxes along the diagonal because students from the same cohort were far more likely to be connected than students ten years apart</cite>. For you, the equivalent grouping is **community / gang ID** (from Louvain — you already compute this in `network_service.py`'s `detect_communities()`). <cite index="22-1">Common reordering strategies include clustering-based reordering and the reverse Cuthill-McKee algorithm, both aimed at pulling connected nodes into contiguous blocks</cite>.

### 3.3 Concrete build plan
**New page/tab: "Connectivity Grid"** alongside the existing node-link Criminal Network view (not a replacement — the research is unanimous that these two views should coexist and stay linked, not compete).

```tsx
// New component: ConnectivityMatrix.tsx
interface MatrixProps {
  nodes: NetworkNode[];   // full 100 (or N) nodes, unfiltered
  edges: NetworkEdge[];
  onCellClick: (nodeA: string, nodeB: string) => void; // jump into ego-view from §2
}

const ConnectivityMatrix: React.FC<MatrixProps> = ({ nodes, edges, onCellClick }) => {
  // 1. Order nodes by community_id (from Louvain), then by degree within community —
  //    this is the "reorder by cluster" strategy from the research above.
  const ordered = useMemo(() => {
    return [...nodes].sort((a, b) => {
      const ca = a.community_id ?? 0, cb = b.community_id ?? 0;
      if (ca !== cb) return ca - cb;
      return (b.centrality?.degree ?? 0) - (a.centrality?.degree ?? 0);
    });
  }, [nodes]);

  // 2. Build a fast lookup: edgeMap[`${a}_${b}`] = edge
  const edgeMap = useMemo(() => {
    const m = new Map<string, NetworkEdge>();
    edges.forEach(e => {
      m.set(`${e.source_node_id}_${e.target_node_id}`, e);
      m.set(`${e.target_node_id}_${e.source_node_id}`, e); // undirected lookup
    });
    return m;
  }, [edges]);

  const cellSize = Math.max(4, Math.min(18, 800 / ordered.length)); // shrink as N grows

  return (
    <div className="overflow-auto">
      <svg width={ordered.length * cellSize + 150} height={ordered.length * cellSize + 150}>
        {/* Row/column labels, rotated for columns */}
        {ordered.map((n, i) => (
          <text key={`rl-${n.node_id}`} x={148} y={150 + i * cellSize + cellSize / 1.5}
                fontSize={Math.min(9, cellSize)} textAnchor="end" fill="#94a3b8">
            {n.label}
          </text>
        ))}
        {/* Matrix cells */}
        {ordered.map((rowNode, i) =>
          ordered.map((colNode, j) => {
            if (i === j) return null; // no self-loops in this view
            const edge = edgeMap.get(`${rowNode.node_id}_${colNode.node_id}`);
            return (
              <rect
                key={`${rowNode.node_id}-${colNode.node_id}`}
                x={150 + j * cellSize} y={150 + i * cellSize}
                width={cellSize - 0.5} height={cellSize - 0.5}
                fill={edge ? strengthToColor(edge.strength_score) : '#1e293b'} // dark = no connection
                onClick={() => edge && onCellClick(rowNode.node_id, colNode.node_id)}
                style={{ cursor: edge ? 'pointer' : 'default' }}
              >
                <title>{edge ? `${rowNode.label} ↔ ${colNode.label}: ${edge.relationship_type}` : `${rowNode.label} ↔ ${colNode.label}: not connected`}</title>
              </rect>
            );
          })
        )}
        {/* Community boundary lines — draw a line every time community_id changes,
            so the eye immediately sees cluster blocks vs bridge connections */}
      </svg>
    </div>
  );
};

function strengthToColor(strength: number): string {
  // e.g. interpolate slate -> red as strength_score goes 0 -> 100
  const t = Math.min(1, strength / 100);
  const r = Math.round(30 + t * 195);
  return `rgb(${r}, ${Math.round(41 - t * 20)}, ${Math.round(59 - t * 40)})`;
}
```

- **Every cell is always rendered** — so an all-dark row instantly tells you "this criminal has zero connections in the database," which is precisely the "where it is not connected" view you asked for, and it's not something a force-directed layout can show as clearly (a node with no edges just looks like everyone else until you check for edges manually).
- **Click a filled cell → reuse `focusOnNode`/`navigateToNode` from §2** to jump straight into the ego-view for that pair — this is the "linked views" pattern the research explicitly calls out as the best practice, not two disconnected UIs.
- For your current ~100-node scale this renders instantly as plain SVG. If this page is later reused for a much larger slice of the database (thousands of nodes), switch the `<svg>` cell grid to an HTML5 `<canvas>` pixel-blit (draw each cell with `ctx.fillRect`) — <cite index="22-1">this is literally how production matrix-view tools render it: "the adjacency matrix is displayed as a pixel map, where links are shown as filled grid cells, colored by edge weight"</cite> — canvas handles tens of thousands of cells far better than SVG DOM nodes.

### 3.4 Toggle between community-order and degree-order
Give the user a small control to switch the sort key — this mirrors <cite index="22-1">the standard practice of offering multiple reordering strategies (including a "return to original ordering" option and algorithms like reverse Cuthill-McKee) since different orderings reveal different patterns</cite>:

```tsx
const [sortMode, setSortMode] = useState<'community' | 'degree' | 'risk'>('community');
// swap the comparator in the `ordered` useMemo above based on sortMode
```

---

## 4. Where this leaves your three original asks

| Your ask | Answer |
|---|---|
| "Better graphing system than Neo4j" | Neo4j itself is fine at your scale — the fix was the seeding logic (Part 1). For the *rendering* layer, Cytoscape.js remains the right choice while you're under ~3-5k nodes on screen; Sigma.js/graphology or commercial Ogma are the correct next steps only once you're consistently past that. Linkurious is the actual best-in-class *product* for this exact criminal-network use case if/when this becomes a funded long-term platform. |
| "Click node → zoom to its connections, with Back/Forward" | Buildable now on Cytoscape.js: `closedNeighborhood()` + `cy.animate({fit})` for the zoom, a simple React history stack (or `cytoscape-undo-redo`) for Back/Forward — no new library required. |
| "Grid view of the whole database's connections, showing where connected/not" | This is the adjacency-matrix pattern — a second, linked view (not a replacement for the node-link graph), ordered by community/degree, one cell per possible pair, dark cells = "not connected." Concrete component sketched in §3.3. |

Everything in this document is additive to Part 1 — apply Part 1's data/query fixes first, since an ego-view and a matrix view of an artificially-sparse graph will just make the sparsity more visually obvious, not less.