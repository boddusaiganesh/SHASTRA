# SHASTRA Platform — Full Code Audit, Connectivity Diagnosis & Fix Guide

**Scope of this review:** Complete codebase (`crime_backend/MODULE_2_BACKEND` FastAPI backend + `crime_frontend` React/Vite frontend), with a deep-dive into the **Criminal Network / Link Analysis** feature. No files in your uploaded project were modified — everything below is diagnostic only. Apply the fixes yourself using the snippets provided.

---

## 1. Architecture Summary (what the app actually does)

| Layer | Tech | Purpose |
|---|---|---|
| Frontend | React 18 + Vite + TS + Redux Toolkit + TailwindCSS | SPA served via Nginx in prod, Vite dev server locally |
| Maps | `react-leaflet` | Crime map, hotspot map, risk map |
| Network Graph | `cytoscape.js` + `cytoscape-fcose` | Criminal network visualization |
| Charts | `recharts` | Trends, forecasts, time patterns |
| Backend | FastAPI (async) | REST API, JWT auth, rate limiting (`slowapi`) |
| Relational DB | PostgreSQL (+PostGIS) via SQLAlchemy async ORM | Crimes, offenders, victims, alerts, users, audit logs |
| Graph DB | Neo4j (`neo4j` async driver) | Criminal network relationships (nodes/edges) |
| Cache | Redis | Response caching, Gemini response caching, token blacklist |
| AI | Google Gemini (`google.generativeai`) | Network AI summary, offender profile analysis, MO summaries, assistant chat |
| Background jobs | APScheduler (separate `scheduler` container) | Hotspot clustering, forecasting, anomaly scans, alert generation |

**Feature inventory (frontend pages ↔ backend routers):**

| Page | Router(s) | Status |
|---|---|---|
| Dashboard | `dashboard_router` | OK |
| Crime Map | `crimes_router` | OK |
| Hotspot Analysis | `hotspots_router` | OK |
| **Criminal Network** | `network_router` | **Partially broken — see §3** |
| Offender Database | `offenders_router` | OK (minor issues, §4.4) |
| Victim Database | `victims_router` | OK |
| Predictive Analytics | `predictions_router` | OK |
| Anomaly Detection | `anomalies_router` | OK |
| Alerts (+WebSocket) | `alerts_router` | **Connectivity risk in Docker, §2.3** |
| Reports | `reports_router` | OK |
| Settings (users, audit logs, data sources) | `settings_router` | **Audit log bug, §4.2** |
| Evidence upload/view | `evidence_router` | **Broken, §4.1** |
| AI Assistant widget | `assistant_router` | OK |

---

## 2. Frontend ⇄ Backend Connectivity Issues

### 2.1 CRITICAL — Dockerized production build has no path from Nginx to the backend

This is the single biggest "why doesn't anything load in production" bug.

**How the app is meant to run (per your own README):**
```bash
cd crime_backend/MODULE_2_BACKEND
docker compose up -d --build
# Frontend at http://localhost, API at http://localhost:8000
```

**What actually happens:**

`crime_backend/MODULE_2_BACKEND/docker-compose.yml`:
```yaml
frontend:
  build:
    context: ../../crime_frontend
    dockerfile: Dockerfile
    args:
      VITE_API_URL: ${FRONTEND_VITE_API_URL}
      VITE_WS_URL: ${FRONTEND_VITE_WS_URL}
  restart: unless-stopped
  ports:
    - "80:80"
```

These build args (`FRONTEND_VITE_API_URL`, `FRONTEND_VITE_WS_URL`) are **never defined** in `crime_backend/MODULE_2_BACKEND/.env.example`. When a user copies `.env.example` → `.env` (as your README instructs) and runs `docker compose up -d --build`, Compose substitutes **empty strings** for both. This gets baked into the static build at build time:

`crime_frontend/Dockerfile`:
```dockerfile
ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_WS_URL=${VITE_WS_URL}
RUN npm run build
```

Since Vite bakes `import.meta.env.VITE_API_URL` in at build time, `API_BASE_URL` (`crime_frontend/src/constants/apiEndpoints.ts`) falls back to:
```ts
export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
```
Because the empty string `""` is falsy, this actually still falls back to `http://localhost:8000/api`, **but that only works if the browser and the backend happen to share `localhost`** — i.e. only in local dev, not in any real deployment (different host/VM/domain) where `localhost:8000` doesn't exist from the browser's point of view.

Worse — even in `http://localhost` deployment, Nginx has **no reverse proxy to the backend at all**:

`crime_frontend/nginx.conf`:
```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }

    # Optional: proxy API requests if backend isn't publicly exposed
    # location /api/ {
    #     proxy_pass http://backend:8000/;
    # }
}
```

The `/api/` proxy block is **commented out**. So:
- If you ever set `VITE_API_URL=/api` (a common "same-origin" pattern for prod), every API call 404s because Nginx has nothing to route `/api/*` to.
- The only reason the app "works" today is that it currently defaults to hard-coding `http://localhost:8000/api`, which is fragile and breaks the moment you deploy to a real server/domain, or the moment someone actually sets the (currently unused) env vars correctly for a non-localhost host.

**Fix — define the build-arg env vars AND enable the Nginx proxy (recommended: proxy through Nginx so you don't need CORS or public backend exposure):**

`crime_backend/MODULE_2_BACKEND/.env` (add):
```env
FRONTEND_VITE_API_URL=/api
FRONTEND_VITE_WS_URL=/api/alerts/ws
```

`crime_frontend/nginx.conf` (uncomment/fix and also proxy websockets):
```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
With `location /api/` proxying to `backend:8000` (the Docker network name — see `docker-compose.yml` service name `backend`), same-origin `VITE_API_URL=/api` works for both plain HTTP calls and the WebSocket upgrade (`/api/alerts/ws`), and you avoid CORS entirely in production since frontend and backend appear to the browser as the same origin.

If you'd rather keep the backend directly exposed on `:8000` (current default), at minimum set the two missing env vars explicitly to the deployed backend's public URL, e.g.:
```env
FRONTEND_VITE_API_URL=http://your-server-ip:8000/api
FRONTEND_VITE_WS_URL=ws://your-server-ip:8000/api/alerts/ws
```

### 2.2 CORS `FRONTEND_URL` mismatch in production mode

`crime_backend/MODULE_2_BACKEND/main.py`:
```python
allowed_origins = []
if settings.ENVIRONMENT == "production":
    allowed_origins = [settings.FRONTEND_URL]
else:
    allowed_origins = [
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost",
        "http://127.0.0.1",
    ]
```
In production mode, **only** `settings.FRONTEND_URL` is allowed — no fallback list. But:
- `.env.example` default is `FRONTEND_URL=http://localhost:5173` (the Vite dev port).
- The Dockerized frontend actually serves on port **80** (`http://localhost` or your real domain).

If you go into production without explicitly overriding `FRONTEND_URL` to match your actual deployed frontend origin, **every cross-origin API call from the browser will be rejected by CORS**, even though the backend itself is reachable and healthy. This is easy to miss because `/docs`, Postman, and server-to-server calls all still work fine — only real browser requests fail.

**Fix:** If you adopt the Nginx-proxy approach in §2.1, this whole class of bug disappears (same-origin ⇒ no CORS needed). Otherwise, make sure `.env`'s `FRONTEND_URL` is set to the *exact* scheme+host+port the browser will use to reach the SPA, e.g.:
```env
# if serving frontend on http://your-domain (port 80, no path)
FRONTEND_URL=http://your-domain
```
Consider supporting a comma-separated list for multiple valid origins (e.g. staging + prod):
```python
allowed_origins = [o.strip() for o in settings.FRONTEND_URL.split(",") if o.strip()] \
    if settings.ENVIRONMENT == "production" else [...]
```

### 2.3 WebSocket alerts channel has the same proxy gap

`crime_frontend/src/App.tsx`:
```ts
const base = import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/alerts/ws";
ws = new WebSocket(`${base}?token=${encodeURIComponent(token || "")}`);
```
Backend endpoint (`alerts_router.py`):
```python
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
```
This will suffer from the exact same problem as §2.1 — in the dockerized deployment there is no path from `ws://<frontend-host>/api/alerts/ws` to the backend container unless you add the Nginx `proxy_pass` + `Upgrade`/`Connection` headers shown above. Real-time alert toasts (`AlertBanner`, the bell icon badge in `Navbar`/`Sidebar`) will silently fail to connect and just retry with exponential backoff forever — no user-facing error is shown, so this is easy to miss in manual QA.

### 2.4 Minor — login error messages lose backend detail

`crime_frontend/src/pages/Login.tsx`:
```ts
} catch (err: unknown) {
  dispatch(loginFailure((err as Error).message || 'Login failed'));
}
```
Axios errors are not plain `Error` objects with a useful `.message` — the useful text is in `err.response.data.detail` (e.g. `"Invalid username or password"` from `auth_router.py`). Today the user just sees Axios's generic `"Request failed with status code 401"`.

**Fix:**
```ts
} catch (err: any) {
  dispatch(loginFailure(err?.response?.data?.detail || 'Login failed'));
}
```

---

## 3. Deep-Dive: Criminal Network / Link Analysis Feature

### 3.1 How it's *supposed* to work (backend architecture is actually solid)

`network_service.get_network_graph_data()`:
1. Checks Redis cache (`network_graph:<query>:<crime_type>:<district>:<depth>:<limit>`).
2. Tries Neo4j (`get_network_graph()` in `neo4j_connection.py`) — builds a dynamic Cypher query scoped by search/crime-type/district, expands each Criminal node's immediate relationships (up to 25 per node), normalizes nodes/edges.
3. **Graceful degradation:** if Neo4j is offline, falls back to `build_network_from_postgres()`, reconstructing a network purely from `Offender.known_associates` JSON arrays in PostgreSQL — nice touch, most systems just error out here.
4. Runs `networkx`-based analytics on whichever graph it got: `betweenness_centrality`, `degree`, `pagerank`, and Louvain community detection — this is genuinely good graph science, not decorative.
5. Computes `key_players` (top-5 by betweenness) and caches the whole payload for 10 minutes.

This part is well-built and production-quality **in isolation**. The problems are entirely in how the frontend consumes two of the five network endpoints.

### 3.2 CRITICAL BUG — "Expand Node" (double-click) is completely broken

**Frontend flow:** `NetworkGraph.tsx` wires a `dblclick` handler on graph nodes:
```tsx
cy.on("dblclick", "node", (evt: cytoscape.EventObject) => {
  const nodeId = evt.target.id();
  const node = nodes.find((n) => n.node_id === nodeId);
  if (node) onNodeExpand?.(node);
});
```
which calls `handleNodeExpand` in `CriminalNetwork.tsx`, which calls:

`networkService.ts`:
```ts
expandNode: async (nodeId: string) => {
  try {
    const response = await api.get(ENDPOINTS.NETWORK.EXPAND(nodeId));
    return response.data?.data || null;   // <-- BUG
  } catch (error) {
    console.error("Error expanding node:", error);
    return null;
  }
},
```

**Root cause — double unwrapping.** The shared Axios instance already unwraps the backend envelope once:

`api.ts`:
```ts
api.interceptors.response.use(
  (response) => {
    // Unwrap the response if it matches our standard payload
    if (response.data && response.data.success !== undefined && response.data.data !== undefined) {
      return { ...response, data: response.data.data };
    }
    return response;
  },
  ...
);
```
So by the time code in `networkService.ts` sees `response.data`, it is **already** the inner payload (e.g. `{ nodes: [...], edges: [...] }` for the expand endpoint). `response.data?.data` then looks for a `.data` property *inside that object*, which doesn't exist — so this **always evaluates to `undefined`**, and the function always returns `null`, even on a perfectly successful 200 response. Double-click-to-expand silently does nothing, with no error shown to the user (the UI hint text even says *"Double-click to expand"*, promising a feature that never fires).

**Fix:**
```ts
expandNode: async (nodeId: string) => {
  try {
    const response = await api.get(ENDPOINTS.NETWORK.EXPAND(nodeId));
    return response.data || null;
  } catch (error) {
    console.error("Error expanding node:", error);
    return null;
  }
},
```

### 3.3 CRITICAL BUG — "Compare / Shortest Path" (shift-click) is completely broken

Same root cause, same fix, different endpoint. `NetworkGraph.tsx`:
```tsx
cy.on("tap", "node", (evt: cytoscape.EventObject) => {
  ...
  if ((evt.originalEvent as MouseEvent).shiftKey) {
    onNodeCompare?.(node);
  } ...
});
```
`CriminalNetwork.tsx`:
```ts
const res = await networkService.getShortestPath(compareNode1.node_id, node.node_id);
if (res && res.found) {
  const pathIds = res.path_nodes.map((n: any) => n.id);
  setHighlightPath(pathIds);
}
```
`networkService.ts`:
```ts
getShortestPath: async (nodeA: string, nodeB: string) => {
  try {
    const response = await api.get(ENDPOINTS.NETWORK.SHORTEST_PATH, {
      params: { node_a: nodeA, node_b: nodeB },
    });
    return response.data?.data || null;   // <-- BUG (same as §3.2)
  } catch (error) {
    console.error("Error fetching shortest path:", error);
    return null;
  }
},
```
Backend `network_router.py` returns `{"success": True, "data": {"found": bool, "path_nodes": [...], "path_rels": [...]}}`. After the interceptor's single unwrap, `response.data` is already `{found, path_nodes, path_rels}`. `response.data?.data` is `undefined` → function always returns `null` → `res.found` throws/short-circuits → `handleNodeCompare` never sets `highlightPath` → the "shift-click two nodes to find the connecting path" feature (a headline capability described in your README as *"Association Detection"*) never highlights anything, and the two selected-node banner at the top just sits there with no visual result and no error message.

**Fix:**
```ts
getShortestPath: async (nodeA: string, nodeB: string) => {
  try {
    const response = await api.get(ENDPOINTS.NETWORK.SHORTEST_PATH, {
      params: { node_a: nodeA, node_b: nodeB },
    });
    return response.data || null;
  } catch (error) {
    console.error("Error fetching shortest path:", error);
    return null;
  }
},
```

### 3.4 Confirm the fix pattern for the two working network calls (for reference — do not change these)

These two already unwrap correctly and should be **left as-is**:
```ts
getNodeDetail: async (nodeId: string) => {
  const response = await api.get(ENDPOINTS.NETWORK.NODE_DETAIL(nodeId));
  return response.data || null;              // correct
},
getAiSummary: async (districtId?: string) => {
  const response = await api.get(ENDPOINTS.NETWORK.AI_SUMMARY, { params: { district_id: districtId } });
  return response.data || null;              // correct
},
```
`getGraphData` is written defensively enough (`response.data?.data || response.data || null`) that it happens to work despite the same confusing pattern — but it's worth cleaning up for consistency/readability once you're touching this file:
```ts
getGraphData: async (searchQuery?: string, crimeType?: string, districtId?: string) => {
  try {
    const response = await api.get(ENDPOINTS.NETWORK.GRAPH_DATA, {
      params: { search_query: searchQuery, crime_type: crimeType, district_id: districtId },
    });
    return response.data || null;   // simplify — the fallback chain was masking the same bug
  } catch (error: any) {
    console.error("Error fetching network graph:", error);
    return { status: "offline", error: error.response?.data?.detail || "Failed to connect to the backend API." };
  }
},
```

### 3.5 The underlying design smell — recommend a single unwrap policy

The root cause of §3.2/§3.3 (and the identical bug class in §4.1/§4.2 below) is that the codebase has **two competing conventions** for unwrapping `{success, data}` envelopes: a global Axios interceptor that already does it, plus scattered manual `res.data.data` / `res.data?.data` calls in individual service files that assume the interceptor *isn't* there. Every time a new endpoint is wired up, whoever writes it has a 50/50 chance of guessing wrong, and it fails silently (no thrown error, just `null`/`undefined`) so it isn't caught by casual testing.

**Recommended structural fix (pick one, apply everywhere):**

**Option A — keep the interceptor, delete all manual `.data.data` in services.** Grep for the pattern and fix every occurrence:
```bash
grep -rn "res\.data\.data\|response\.data\.data\|res\.data?\.data\|response\.data?\.data" crime_frontend/src/services
```
Known offenders to fix (see §4 for two more instances beyond the network ones already covered):
- `crime_frontend/src/services/networkService.ts` (`expandNode`, `getShortestPath` — shown above)
- `crime_frontend/src/services/crimeService.ts` → `getEvidence` (§4.1)
- `crime_frontend/src/services/evidenceService.ts` → `getEvidenceList` (§4.1)
- `crime_frontend/src/services/alertService.ts` → `settingsService.getAuditLogs` (§4.2)

**Option B — remove the interceptor's auto-unwrap, and instead export a small typed helper** so every call site is explicit and greppable:
```ts
// api.ts — remove the auto-unwrap block, keep interceptor for 401 handling only
export async function unwrap<T>(promise: Promise<{ data: { success: boolean; data: T } }>): Promise<T> {
  const res = await promise;
  return res.data.data;
}
```
```ts
// networkService.ts
expandNode: (nodeId: string) => unwrap(api.get(ENDPOINTS.NETWORK.EXPAND(nodeId))).catch(() => null),
```
Either option is fine; Option A is a smaller diff given how much code already assumes the interceptor's behavior.

---

## 4. Other Connectivity/Data Bugs Found Elsewhere (same root cause as §3.2/§3.3)

### 4.1 Evidence viewer always shows empty / undefined (two duplicate, both-broken implementations)

`crime_backend/MODULE_2_BACKEND/app/routers/evidence_router.py`:
```python
@router.get("/{crime_id}")
async def list_evidence(...):
    ...
    return {"success": True, "data": [ ... ]}
```
`crime_frontend/src/services/crimeService.ts`:
```ts
getEvidence: async (id: string) => {
  try {
    const response = await api.get(`/evidence/${id}`);
    return response.data.data;      // <-- BUG: response.data is already the array
  } catch {
    return [];
  }
},
```
`crime_frontend/src/services/evidenceService.ts` (a second, apparently-unused duplicate service with the identical bug):
```ts
export const evidenceService = {
  getEvidenceList: async (crimeId: string) => {
    const res = await api.get(`/evidence/${crimeId}`);
    return res.data.data;           // <-- same BUG
  },
  ...
};
```
Since `response.data` is an array after the interceptor unwraps it, `response.data.data` is simply `undefined` (JS allows the property access, it just isn't there) — **no exception is thrown**, so the `catch` block in `crimeService.getEvidence` never fires, and the function silently returns `undefined` instead of `[]`. Any component rendering `evidence.map(...)` on this will crash or render nothing depending on how it's guarded.

**Fix (`crimeService.ts`):**
```ts
getEvidence: async (id: string) => {
  try {
    const response = await api.get(`/evidence/${id}`);
    return response.data || [];
  } catch {
    return [];
  }
},
```
**Fix (`evidenceService.ts`):**
```ts
getEvidenceList: async (crimeId: string) => {
  const res = await api.get(`/evidence/${crimeId}`);
  return res.data;
},
```
Recommend also deciding which of the two duplicate services is canonical and deleting the other — maintaining two parallel implementations of the same call is itself a latent-bug generator.

### 4.2 Settings → Audit Logs page will always be empty

`crime_backend/MODULE_2_BACKEND/app/routers/settings_router.py`:
```python
@router.get("/audit-logs")
async def get_audit_logs(...):
    ...
    return {"success": True, "data": [ ... ]}
```
`crime_frontend/src/services/alertService.ts`:
```ts
getAuditLogs: async () => {
  try {
    const res = await api.get(ENDPOINTS.SETTINGS.AUDIT_LOGS || '/settings/audit-logs');
    return res.data.data;          // <-- BUG, identical pattern
  } catch (error) {
    if (import.meta.env.VITE_DEMO_MODE === 'true') return [];
    throw error;
  }
},
```
**Fix:**
```ts
getAuditLogs: async () => {
  try {
    const res = await api.get(ENDPOINTS.SETTINGS.AUDIT_LOGS || '/settings/audit-logs');
    return res.data;
  } catch (error) {
    if (import.meta.env.VITE_DEMO_MODE === 'true') return [];
    throw error;
  }
},
```

### 4.3 Duplicate route registration on the network graph endpoint (works, but worth cleaning up)

`network_router.py`:
```python
@router.get("/graph")            
@router.get("/graph-data")
@limiter.limit("30/minute")
async def fetch_network_graph(...):
```
Two route decorators stacked on one function is valid FastAPI, but only `/graph-data` is actually referenced anywhere in the frontend (`ENDPOINTS.NETWORK.GRAPH_DATA = "/network/graph-data"`). `/graph` is dead, undocumented, unused surface area — harmless today, but it's an easy thing to forget about and accidentally leave exposed/rate-limited differently later. Recommend deleting the unused `@router.get("/graph")` line unless you have an external consumer relying on it.

### 4.4 `NetworkGraphResponse` / `NetworkAISummaryResponse` Pydantic models exist but are never used

`crime_backend/MODULE_2_BACKEND/app/models/response_models/network_response.py` defines full response schemas (`NetworkGraphResponse`, `NetworkNode`, `NetworkEdge`, `NetworkAISummaryResponse`), but **no route in `network_router.py` passes `response_model=...`**, so:
- FastAPI does not validate outgoing data against them (a backend bug could ship malformed JSON straight to the frontend with no server-side safety net).
- `/docs` (OpenAPI/Swagger) does not show accurate response shapes for the network endpoints, which will slow down whoever maintains this next.

**Fix (example for the graph endpoint):**
```python
from app.models.response_models.network_response import NetworkGraphResponse

@router.get("/graph-data", response_model=None)  # keep None if payload includes extra dynamic fields (centrality, community_id, key_players not in the schema)
```
Better: extend the Pydantic models to match what the service actually returns (`centrality`, `community_id`, `key_players`, `source`, `status`) and then wire up `response_model=` for real validation — this is the more correct production-readiness fix, but requires reconciling the schema with `network_service.py`'s actual output first (they've drifted apart).

---

## 5. Security / Production-Readiness Checklist

These aren't "broken" per se, but they will bite you specifically when you flip `ENVIRONMENT=production`.

1. **JWT secret validation is good but easy to trip.** `config.py`:
   ```python
   @field_validator("JWT_SECRET_KEY")
   @classmethod
   def validate_jwt(cls, v):
       if v == "CHANGE_THIS_IN_PRODUCTION_64_CHARS_MIN":
           env = os.environ.get("ENVIRONMENT", "development")
           if env == "production":
               raise ValueError(...)
   ```
   This correctly hard-fails startup in production if you forgot to set a real secret — good. Just make sure your deploy scripts actually set `ENVIRONMENT=production` **and** `JWT_SECRET_KEY` together, or the app won't boot (which is the point, but confirm your ops runbook expects this).

2. **`/docs`, `/redoc`, `/openapi.json` are correctly disabled in production** (`main.py`):
   ```python
   docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
   ```
   Good — no action needed, just confirming this is intentional and correct.

3. **Rate limits on network endpoints** — `30/minute` for graph/node-detail, `10/minute` for shortest-path, `20/minute` for expand, `5/minute` for AI summary. Once §3.2/§3.3 are fixed and users start actually double-clicking to expand nodes, `20/minute` per IP could be reached quickly during active investigation sessions with many analysts behind one office NAT/proxy (shared IP). Consider keying the limiter by authenticated `user_id` instead of `get_remote_address` for multi-analyst deployments behind a shared gateway IP.

4. **CSP header hard-codes `connect-src 'self' {FRONTEND_URL}`** (`main.py`, `SecurityHeadersMiddleware`) — this is applied to *backend* responses, so it doesn't affect the browser's ability to call the backend from the frontend's origin (CSP `connect-src` restricts what a *page from this origin* can call, and the browser enforces CSP from the page that served the HTML, not from the API response). This line is effectively inert for cross-origin API calls; it only matters if the backend ever serves HTML directly (e.g., `/docs`). Not a functional bug, just flagging that it doesn't do what its name implies for the API/SPA split architecture you have.

---

## 6. Summary Table — Everything to Fix

| # | File | Bug | Severity | Fix location |
|---|---|---|---|---|
| 1 | `docker-compose.yml` + `.env.example` | Missing `FRONTEND_VITE_API_URL`/`FRONTEND_VITE_WS_URL` build args | Critical (prod) | §2.1 |
| 2 | `crime_frontend/nginx.conf` | `/api/` reverse proxy commented out; no WS upgrade headers | Critical (prod) | §2.1 |
| 3 | `main.py` / `.env` | `FRONTEND_URL` default doesn't match Docker's port-80 frontend in production CORS mode | High (prod) | §2.2 |
| 4 | `App.tsx` / Nginx | WebSocket alerts channel has same missing-proxy issue | High (prod) | §2.3 |
| 5 | `networkService.ts` → `expandNode` | Double `.data.data` unwrap → always returns `null` | **Critical (feature dead)** | §3.2 |
| 6 | `networkService.ts` → `getShortestPath` | Double `.data.data` unwrap → always returns `null` | **Critical (feature dead)** | §3.3 |
| 7 | `crimeService.ts` → `getEvidence` | `response.data.data` on already-unwrapped array | High | §4.1 |
| 8 | `evidenceService.ts` → `getEvidenceList` | Same as #7, duplicate service | High | §4.1 |
| 9 | `alertService.ts` → `settingsService.getAuditLogs` | Same double-unwrap bug | Medium | §4.2 |
| 10 | `Login.tsx` | Swallows backend's actual error `detail` message | Low (UX) | §2.4 |
| 11 | `network_router.py` | Dead duplicate route `/graph` | Low (cleanup) | §4.3 |
| 12 | `network_response.py` | Response models defined but unused / drifted from actual service output | Low (maintainability) | §4.4 |

**Recommended fix order:** #1–#4 first (nothing works reliably in a real deployment until these are fixed), then #5–#6 (the network-graph features you specifically asked about), then #7–#9 (same bug class, quick wins), then the cleanup items.