# SHASTRA Crime Intelligence Platform — Full-Stack Audit Report
**Scope:** `crime_backend/MODULE_2_BACKEND` (FastAPI + PostgreSQL + Neo4j + Redis + Gemini) and `crime_frontend` (React 19 + Vite + Redux Toolkit + Leaflet + Cytoscape)
**Goal:** identify every connectivity gap between frontend ↔ backend ↔ databases ↔ AI ↔ network layer, and everything blocking a real production deployment.

This is organized by severity. Each item has: **what's wrong**, **why it matters**, and **a code fix you can drop in**. Nothing here has been applied to your files — copy what you want into your codebase.

---

## 0. TL;DR — the 5 things to fix before anything else

1. **Authentication bypass backdoor** in `security.py` — any request with `Authorization: Bearer mock-...` gets full admin access, in *production too*, not just dev.
2. **Frontend has zero environment-based configuration.** `API_BASE_URL`, the WebSocket URL, and half a dozen `fetch()` calls are hardcoded to `http://localhost:8000`. The app cannot be deployed anywhere else without editing source.
3. **Login silently falls back to fake mock authentication** whenever the backend is unreachable — meaning a down/misconfigured backend doesn't show an error, it lets *anyone* log in as a fake "System Administrator".
4. **Evidence files (case evidence!) are served publicly, unauthenticated,** with no file-type or size validation on upload.
5. **Neo4j (graph DB) calls are synchronous and block the async event loop** on every network-graph request — this alone will cap your API throughput under load regardless of server size.

---

## 1. CRITICAL — Authentication & Authorization

### 1.1 Hardcoded auth-bypass backdoor (`app/core/security.py`)

```python
payload = decode_access_token(token)
if not payload:
    if token == "mock-jwt-token-12345" or token.startswith("mock-") or settings.ENVIRONMENT == "development":
        return {
            "user_id": "00000000-0000-0000-0000-000000000001",
            "username": "admin",
            "role": "SCRB_OFFICER",
            ...
            "permissions": ["view_all_districts", ..., "manage_users", "modify_settings"],
        }
    raise credentials_exception
```

**Why this is critical:** the `token.startswith("mock-")` branch is **not gated by environment**. In production, any client can send:

```
Authorization: Bearer mock-anything
```

...and receive a fully-privileged `SCRB_OFFICER` identity with `manage_users` and `modify_settings` permissions — no password, no valid JWT, nothing. This is a complete authentication bypass on every protected endpoint in the system (crimes, offenders, victims, network graph, settings, user management, everything behind `get_current_user`).

It exists because the frontend (`authService.ts`) fabricates a `mock-jwt-token-12345` when the backend is unreachable, and someone made the backend "cooperate" with that fake token instead of fixing the real problem (see §2.2).

**Fix — remove the bypass entirely:**

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    if await is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated. Please login again.",
        )

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception          # <-- no mock/dev bypass, ever

    user_id = payload.get("user_id")
    if not user_id:
        raise credentials_exception

    return {
        "user_id": payload.get("user_id"),
        "username": payload.get("username"),
        "role": payload.get("role"),
        "district_id": payload.get("district_id"),
        "police_station_id": payload.get("police_station_id"),
        "permissions": payload.get("permissions", []),
        "token": token,
    }
```

If you want a genuinely useful local-dev experience, gate it behind a **separate, explicit** flag that can never be true in a deployed environment, e.g. require both `settings.ENVIRONMENT == "development"` **and** a `settings.ALLOW_DEV_AUTH_BYPASS` flag that defaults to `False` and is never set in any `.env` used outside a laptop. Don't key anything off a value (`mock-...`) that the client controls.

### 1.2 Frontend fabricates fake logins when the backend is down (`authService.ts`)

```typescript
login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
  try {
    const res = await api.post(ENDPOINTS.AUTH.LOGIN, credentials);
    return res.data;
  } catch (error) {
    console.warn("Backend DB offline, falling back to mock authentication.");
    return {
      ...mockAuthResponse,
      user_name: credentials.username === "admin" ? "System Administrator" : credentials.username || mockAuthResponse.user_name,
    };
  }
},
```

**Why this is critical:** this is presumably a demo convenience, but as shipped it means: type *any* username/password, and if the network call fails for *any* reason (backend down, CORS misconfigured, timeout, wrong URL — see §2), the user is logged in anyway with an admin-equivalent role (`mockAuthResponse.permissions_list` includes `manage_users`). Combined with §1.1, this pairing is a fully-functional, silent bypass of the entire auth system for a police intelligence platform.

**Fix — never fabricate credentials. Fail loudly and let the user retry:**

```typescript
export const authService = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    // Let errors propagate — the Login page should show a real error message.
    const res = await api.post(ENDPOINTS.AUTH.LOGIN, credentials);
    return res.data;
  },

  logout: async (): Promise<void> => {
    try {
      await api.post(ENDPOINTS.AUTH.LOGOUT);
    } finally {
      // Always clear local state even if the server call fails.
    }
  },

  verifyToken: async (): Promise<boolean> => {
    try {
      await api.get(ENDPOINTS.AUTH.VERIFY_TOKEN);
      return true;
    } catch {
      return false;
    }
  },

  isAuthenticated: (): boolean => !!localStorage.getItem("auth_token"),
};
```

Then in `Login.tsx`, surface the thrown error to the user (e.g. "Invalid username or password" / "Server unreachable — contact IT"). Delete `mockAuthResponse` and every other `mock*` export from `mockData.ts` before shipping — see §4.

### 1.3 Unauthenticated internal endpoint (`settings_router.py`)

```python
@router.post("/datasources/{source_id}/sync")
async def sync_datasource(source_id: str):
    from app.services.settings_service import trigger_sync
    result = await trigger_sync(source_id)
    return {"success": True, "data": result}
```

No `Depends(get_current_user)` at all — anyone, unauthenticated, can trigger a data-source sync job.

**Fix:**

```python
@router.post("/datasources/{source_id}/sync")
async def sync_datasource(
    source_id: str,
    current_user=Depends(require_scrb_officer),   # only SCRB officers may trigger syncs
):
    from app.services.settings_service import trigger_sync
    result = await trigger_sync(source_id)
    return {"success": True, "data": result}
```

Audit every router file for the same pattern — search for any `async def` under `/api/*` that doesn't have a `Depends(get_current_user)`/`require_role`/`require_scrb_officer` in its signature. `evidence_router.list_evidence` and a few reporting endpoints should be double-checked the same way.

### 1.4 WebSocket endpoint has no authentication (`alerts_router.py`)

```python
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from app.core.websocket import manager
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

Anyone who can reach the server can open this socket and receive every live crime alert broadcast (`CRIME_SPIKE`, `KNOWN_CRIMINAL`, `NETWORK_DISCOVERED`, etc.) with no login required.

**Fix — validate the JWT on connect, before accepting:**

```python
from fastapi import Query, status
from app.core.security import decode_access_token
from app.core.redis_connection import is_token_blacklisted

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    payload = decode_access_token(token)
    if not payload or await is_token_blacklisted(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    from app.core.websocket import manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()   # heartbeat/ping from client, ignored or used for liveness
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

Frontend side — pass the token as a query param (browsers can't set custom headers on the WebSocket handshake):

```typescript
const token = localStorage.getItem("auth_token");
const wsUrl = `${import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/alerts/ws"}?token=${encodeURIComponent(token || "")}`;
const ws = new WebSocket(wsUrl);
```

### 1.5 Uploaded evidence files are served publicly with no auth (`main.py` + `evidence_router.py`)

```python
app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")
```

Anyone with (or able to guess/enumerate) a file URL like `/uploads/<crime_id>_<8hex>.jpg` can download case evidence — no login, no role check, no audit trail. There is also no file-type whitelist or size cap on upload:

```python
ext = file.filename.split(".")[-1]
filename = f"{crime_id}_{uuid.uuid4().hex[:8]}.{ext}"
...
content = await file.read()          # entire file buffered in memory, no size limit
with open(filepath, "wb") as f:
    f.write(content)
```

A user could upload a `.html`/`.svg` file that gets served back with `Content-Type` inferred from extension — a stored-XSS vector if this URL is ever opened directly by an officer's browser, and an unbounded-size upload is a trivial DoS.

**Fix — replace the static mount with an authenticated download route, and validate uploads:**

```python
# main.py — remove the public static mount entirely:
# app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")   # DELETE THIS LINE
```

```python
# evidence_router.py
import os, uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse

router = APIRouter()
UPLOAD_DIR = "app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf", "mp4", "docx", "mp3", "wav"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024   # 25 MB

@router.post("/{crime_id}")
async def upload_evidence(
    crime_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"])),
):
    try:
        uuid.UUID(crime_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid crime_id")

    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '.{ext}' is not permitted")

    # Stream to disk with a hard size cap instead of buffering the whole file in memory
    filename = f"{crime_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    size = 0
    with open(filepath, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                os.remove(filepath)
                raise HTTPException(status_code=413, detail="File exceeds 25MB limit")
            f.write(chunk)

    from app.models.database_models.evidence_model import Evidence
    new_evidence = Evidence(
        crime_id=crime_id, file_path=filepath,
        description=file.filename, uploaded_by=current_user["user_id"],
    )
    db.add(new_evidence)
    await db.commit()
    await db.refresh(new_evidence)
    return {"success": True, "data": new_evidence.to_dict()}


@router.get("/download/{evidence_id}")
async def download_evidence(
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),   # must be logged in to fetch evidence
):
    from sqlalchemy import select
    from app.models.database_models.evidence_model import Evidence

    result = await db.execute(select(Evidence).where(Evidence.evidence_id == evidence_id))
    item = result.scalar_one_or_none()
    if not item or not os.path.exists(item.file_path):
        raise HTTPException(status_code=404, detail="Evidence not found")

    # TODO: log this access to the audit_log table (who viewed which evidence, when)
    return FileResponse(item.file_path, filename=item.description)
```

And update the frontend to call `GET /api/evidence/download/{evidence_id}` through the authenticated `api` instance (which attaches the Bearer token) instead of building raw `<a href="http://localhost:8000${ev.file_url}">` links — see §2.3.

---

## 2. CRITICAL — Frontend ↔ Backend Connectivity

### 2.1 `API_BASE_URL` is hardcoded, no environment configuration exists at all

```typescript
// crime_frontend/src/constants/apiEndpoints.ts
export const API_BASE_URL = "http://localhost:8000/api";
```

There is **no `.env` / `.env.example` / `import.meta.env` usage anywhere in the frontend.** Building this for any environment other than a developer's own laptop (staging, prod, a colleague's machine) requires editing and recommitting source code. This is the single biggest blocker to "production grade."

**Fix:**

```typescript
// crime_frontend/src/constants/apiEndpoints.ts
export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
```

```bash
# crime_frontend/.env.example   (create this file)
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/api/alerts/ws
```

```
# crime_frontend/.gitignore — add:
.env
.env.local
.env.production
```

At build time, set `VITE_API_URL`/`VITE_WS_URL` per environment (Docker build args, CI secrets, hosting-platform env vars). Never bake a real backend URL into the repo.

### 2.2 Response-unwrapping interceptor silently treats *every* failure as "switch to mock data"

```typescript
// api.ts
api.interceptors.response.use(
  (response) => { ... },
  (error) => {
    ...
    try {
      (window as any).__using_mock_data = true;
      window.dispatchEvent(new CustomEvent("mock-data-detected"));
    } catch (e) {}
    return Promise.reject(error);
  }
);
```

Every single failed API call — a typo'd endpoint, a 500 error, a timeout, a CORS failure, an expired token — dispatches a global "switch everything to mock/demo data" event. In a real deployment this **hides real outages and bugs behind fake numbers** that look plausible (`2,847 crimes this month`, etc.), which is actively dangerous for a system meant to inform policing decisions.

**Fix:** this pattern should not exist in a production build at all. If you want a demo mode, make it an explicit, opt-in build flag — not an automatic fallback triggered by any error:

```typescript
api.interceptors.response.use(
  (response) => {
    if (response.data && response.data.success !== undefined && response.data.data !== undefined) {
      return { ...response, data: response.data.data };
    }
    return response;
  },
  (error) => {
    const token = localStorage.getItem("auth_token");
    if (error.response?.status === 401) {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("user_data");
      window.location.href = "/login";
    }
    // No mock-data fallback. Let the caller show a real error/toast.
    return Promise.reject(error);
  }
);
```

Then in each page (`Dashboard.tsx`, `CrimeMapPage.tsx`, etc.), handle the rejected promise by rendering the existing `<ErrorMessage />` component with a retry button, instead of quietly loading `mockData.ts`.

### 2.3 Several components bypass the shared `api` client and hit `http://localhost:8000` directly

Confirmed in:
- `components/common/Navbar.tsx:56` — global search: `fetch(\`http://localhost:8000/api/search/global?q=...\`)`
- `pages/CrimeMapPage.tsx:76` — CSV/export: `window.open(\`http://localhost:8000/api/crimes/map-data?...\`)`
- `pages/CrimeMapPage.tsx:289` and `pages/CrimeDatabase.tsx:129` — evidence links: `href={\`http://localhost:8000${ev.file_url}\`}`
- `pages/HotspotAnalysis.tsx:51` — export: `window.open(\`http://localhost:8000/api/hotspots/clusters?...\`)`

Two separate bugs here:
1. **They will 404/CORS-fail in any non-local deployment** because the host is hardcoded.
2. **They bypass the `Authorization` header entirely** (raw `fetch`/`window.open` don't go through the `api.ts` interceptor), so on a backend that actually enforces auth (once you apply §1.1's fix), every one of these calls will get a `401`.

**Fix pattern — centralize a "resolve full URL" helper and always attach the token:**

```typescript
// src/utils/buildApiUrl.ts
import { API_BASE_URL } from "../constants/apiEndpoints";

export const buildApiUrl = (path: string, params?: Record<string, string>) => {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  return url.toString();
};

// For downloads that must open in a new tab/window and still be authenticated,
// fetch the blob yourself instead of window.open (window.open can't send headers):
export const downloadAuthenticated = async (path: string, params?: Record<string, string>) => {
  const api = (await import("../services/api")).default;
  const response = await api.get(path, { params, responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = "";
  a.click();
  window.URL.revokeObjectURL(blobUrl);
};
```

```typescript
// Navbar.tsx — before
const res = await fetch(`http://localhost:8000/api/search/global?q=${searchQuery}`, { ... });

// Navbar.tsx — after
import api from "../../services/api";
const res = await api.get("/search/global", { params: { q: searchQuery } });
```

```typescript
// CrimeMapPage.tsx — before
window.open(`http://localhost:8000/api/crimes/map-data?${queryParams.toString()}`, "_blank");

// CrimeMapPage.tsx — after
import { downloadAuthenticated } from "../utils/buildApiUrl";
await downloadAuthenticated("/crimes/map-data", Object.fromEntries(queryParams));
```

```typescript
// evidence links — before
<a href={`http://localhost:8000${ev.file_url}`} target="_blank" rel="noreferrer">...</a>

// evidence links — after (calls the new authenticated download route from §1.5)
<button onClick={() => downloadAuthenticated(`/evidence/download/${ev.evidence_id}`)}>
  {ev.file_name}
</button>
```

### 2.4 CORS: wildcard origin reflected on unhandled errors, alongside `allow_credentials=True`

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "")
    headers = {
        "Access-Control-Allow-Origin": origin if origin else "*",
        "Access-Control-Allow-Credentials": "true",
    }
    ...
```

This reflects **whatever `Origin` header the caller sends** back as an allowed origin (with credentials allowed) on every unhandled 500 error, regardless of the `allowed_origins` allow-list configured on `CORSMiddleware` a few lines below. That defeats the purpose of the allow-list for every path that raises an unhandled exception.

**Fix — only ever allow origins that are actually on the allow-list:**

```python
allowed_origins = (
    [settings.FRONTEND_URL]
    if settings.ENVIRONMENT == "production"
    else [settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"]
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"

    logger.error(f"Unhandled server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},   # don't leak str(exc) to clients — see §5.3
        headers=headers,
    )
```

Move the `allowed_origins` list construction above this handler (it currently appears further down `main.py`) so both places share the same list instead of duplicating it.

### 2.5 WebSocket has no reconnect logic

```typescript
// App.tsx
const ws = new WebSocket(wsUrl);
ws.onmessage = (event) => { ... };
return () => ws.close();
```

If the socket drops (server restart, network blip, load balancer idle-timeout — all normal in production), the app never reconnects; live alert delivery silently stops for the rest of the session.

**Fix — a small reconnecting wrapper:**

```typescript
useEffect(() => {
  if (!isAuthenticated) return;
  let ws: WebSocket;
  let retryDelay = 1000;
  let closedByUs = false;

  const connect = () => {
    const token = localStorage.getItem("auth_token");
    const base = import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/alerts/ws";
    ws = new WebSocket(`${base}?token=${encodeURIComponent(token || "")}`);

    ws.onopen = () => { retryDelay = 1000; };
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "NEW_ALERT") {
          dispatch(addAlert(msg.data));
          addToast(msg.data);
        }
      } catch (e) {
        console.error("WS message parse error", e);
      }
    };
    ws.onclose = () => {
      if (closedByUs) return;
      setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 2, 30000);   // exponential backoff, capped at 30s
    };
  };

  connect();
  return () => { closedByUs = true; ws?.close(); };
}, [isAuthenticated, dispatch]);
```

---

## 3. HIGH — Database & Backend Connectivity

### 3.1 Neo4j driver is synchronous and blocks the async event loop

```python
# neo4j_connection.py
_driver = GraphDatabase.driver(...)   # the official sync driver

def run_neo4j_query(query, parameters=None):
    with _driver.session() as session:
        result = session.run(query, parameters or {})
        return [record.data() for record in result]
```

```python
# network_service.py
async def get_network_graph_data(...):
    graph_data = get_network_graph(...)   # calls the sync driver directly, no await, no executor
```

Every call to `/api/network/graph-data`, `/api/network/ai-summary`, `/api/offenders/{id}/network`, etc. blocks FastAPI's single-threaded event loop for the full duration of the Cypher query. Under any real concurrent load this serializes all requests (not just network ones — everything sharing that worker's event loop stalls behind it).

**Fix — either (A) swap to the official async Neo4j driver, or (B) offload sync calls to a thread pool. (A) is the correct fix; (B) is the minimal patch if you're short on time.**

**Option A (recommended) — `neo4j.AsyncGraphDatabase`:**

```python
# neo4j_connection.py
from neo4j import AsyncGraphDatabase, AsyncDriver

_driver: Optional[AsyncDriver] = None

async def init_neo4j():
    global _driver
    try:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URL,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
        )
        await _driver.verify_connectivity()
        await _create_indexes()
    except Exception as e:
        logger.warning(f"Neo4j connection failed (non-critical): {e}")
        _driver = None

async def _create_indexes():
    if not _driver:
        return
    async with _driver.session() as session:
        for query in [...]:
            try:
                await session.run(query)
            except Exception as e:
                logger.warning(f"Index creation warning: {e}")

async def run_neo4j_query(query: str, parameters: Dict = None) -> List[Dict[str, Any]]:
    if not _driver:
        return []
    try:
        async with _driver.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]
    except Exception as e:
        logger.error(f"Neo4j query error: {e}")
        return []
```

Every caller (`get_network_graph`, `sync_offender_to_neo4j`, etc.) becomes `async def` and gets `await`ed at every call site (`network_service.py`, `offender_service.py`, wherever they're invoked).

**Option B (quick patch if you can't refactor the whole call chain right now):**

```python
import asyncio
from functools import partial

async def get_network_graph_data(...):
    loop = asyncio.get_running_loop()
    graph_data = await loop.run_in_executor(
        None, partial(get_network_graph, search_query, crime_type, resolved_id, depth, node_limit)
    )
```

This at least frees the event loop while the sync driver blocks in a worker thread, without a full driver migration.

### 3.2 Windows-only hardcoded path baked into startup (`main.py`)

```python
def start_local_postgres():
    if os.environ.get("ENVIRONMENT", "local") == "development" and platform.system() == "Windows":
        ...
        pg_ctl_path = r"D:\PostgreSQL_17\bin\pg_ctl.exe"
        data_dir = r"D:\PostgreSQL_17\data"
        if os.path.exists(pg_ctl_path) and os.path.exists(data_dir):
            subprocess.Popen([pg_ctl_path, "start", "-D", data_dir])
```

This is a developer's personal machine path (`D:\PostgreSQL_17`) shipped into `main.py`. It's harmless on Linux/containers (the `platform.system() == "Windows"` guard skips it) but it's dead code that has no business being in a shared codebase, let alone a "production-grade" one — remove it and rely on Docker Compose / systemd / your process manager to guarantee Postgres is up before the app starts.

**Fix — delete `start_local_postgres()` and its call site entirely.** If local Windows setup needs automation, put it in a `dev-scripts/start-local-db.ps1` outside the app source, never invoked by `main.py`.

### 3.3 `docker-compose.yml` ships default/plaintext credentials and exposes every datastore port to the host

```yaml
environment:
  - DATABASE_URL=postgresql+asyncpg://admin:securepassword@postgres:5432/crime_intelligence_db
  ...
postgres:
  ports:
    - "5432:5432"
neo4j:
  ports:
    - "7474:7474"
    - "7687:7687"
redis:
  command: redis-server --requirepass redissecurepassword
  ports:
    - "6379:6379"
```

Issues:
- Real-looking credentials (`securepassword`, `neo4jsecurepassword`, `redissecurepassword`) are committed to source control — anyone with repo access effectively has the default prod-shaped credentials.
- Every datastore's port is published to the host (`ports:`), meaning if this compose file is ever used on a machine with a public IP, Postgres/Neo4j/Redis are directly reachable from the internet.
- `volumes: - .:/app` bind-mounts the entire source tree into the backend container, overriding whatever was `COPY`'d into the image at build time — fine for local hot-reload, wrong for anything called "production."
- There's no `frontend` service in `docker-compose.yml` at all, no `restart:` policies, and no healthchecks — `depends_on` only waits for the container to start, not for Postgres/Neo4j to actually be ready to accept connections (this is why `main.py` has to defensively catch DB errors at startup instead of relying on compose to sequence things).

**Fix:**

```yaml
# docker-compose.yml
services:
  backend:
    build: .
    restart: unless-stopped
    env_file: .env                      # secrets live in a gitignored .env, not in compose
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      neo4j:
        condition: service_healthy
    networks:
      - crime_intelligence_network
    # no "ports:" published directly in prod — put a reverse proxy (nginx/traefik) in front instead

  postgres:
    image: postgis/postgis:15-3.4
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DATABASE_NAME}
      POSTGRES_USER: ${DATABASE_USER}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DATABASE_USER}"]
      interval: 5s
      timeout: 5s
      retries: 10
    # no "ports:" published to host in prod — only backend needs to reach it, over the internal network
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - crime_intelligence_network

  neo4j:
    image: neo4j:5.18-community
    restart: unless-stopped
    environment:
      NEO4J_AUTH: ${NEO4J_USER}/${NEO4J_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:7474 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
    volumes:
      - neo4j_data:/data
    networks:
      - crime_intelligence_network

  redis:
    image: redis:7.2-alpine
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - redis_data:/data
    networks:
      - crime_intelligence_network

  frontend:
    build: ./crime_frontend
    restart: unless-stopped
    environment:
      - VITE_API_URL=${VITE_API_URL}
      - VITE_WS_URL=${VITE_WS_URL}
    ports:
      - "80:80"     # served via nginx from a multi-stage build, see below
    networks:
      - crime_intelligence_network

volumes:
  postgres_data:
  neo4j_data:
  redis_data:

networks:
  crime_intelligence_network:
    driver: bridge
```

```dockerfile
# crime_frontend/Dockerfile (doesn't currently exist — add it)
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ARG VITE_WS_URL
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_WS_URL=${VITE_WS_URL}
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

Move every secret out of `docker-compose.yml` into a gitignored `.env` file read via `env_file:`, and rotate the three passwords currently committed in the repo (`securepassword`, `neo4jsecurepassword`, `redissecurepassword`) since they must be treated as already leaked.

### 3.4 `JWT_SECRET_KEY` has a fallback default that's easy to accidentally ship

```python
JWT_SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION_64_CHARS_MIN"
...
@field_validator("JWT_SECRET_KEY")
def validate_jwt(cls, v):
    if v == "CHANGE_THIS_IN_PRODUCTION_64_CHARS_MIN":
        logging.getLogger(__name__).warning("⚠️ JWT_SECRET_KEY is using default value...")
    return v
```

It only logs a warning — the app happily starts and signs real tokens with a publicly-known secret if the operator misses the log line. Given a chunk of this system authenticates law-enforcement officers, this should hard-fail in production.

**Fix:**

```python
@field_validator("JWT_SECRET_KEY")
@classmethod
def validate_jwt(cls, v, info):
    if v == "CHANGE_THIS_IN_PRODUCTION_64_CHARS_MIN":
        env = os.environ.get("ENVIRONMENT", "development")
        if env == "production":
            raise ValueError(
                "JWT_SECRET_KEY must be set to a unique secret before running in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(64))\""
            )
        logging.getLogger(__name__).warning("⚠️ JWT_SECRET_KEY is using the default dev value.")
    return v
```

---

## 4. HIGH — Mock Data / Demo Artifacts Left in Production Path

`crime_frontend/src/services/mockData.ts` and the mock-fallback logic scattered through `api.ts`, `authService.ts`, and (implicitly) any service that imports `mockData` are demo/prototype scaffolding that never got removed. Beyond the auth bypass in §1.2, this means:

- Dashboards can silently show **fabricated crime statistics** (`mockDashboardSummary`, `mockCrimeTrends`, etc.) instead of an error state, which is the opposite of what an intelligence platform should do when its data pipeline breaks.
- It's easy to accidentally demo the "successful" app to a stakeholder while the real backend is actually broken, because the UI can't tell the difference.

**Fix — behind a single explicit flag, not automatic:**

```typescript
// vite.config.ts / .env
VITE_DEMO_MODE=false
```

```typescript
// api.ts
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

// Each service explicitly checks DEMO_MODE and only then imports/returns mock data;
// any real error propagates to the UI as an error state, never a silent fallback.
```

Grep the repo for every `mock` import outside of `mockData.ts` itself and remove the `catch` blocks that return mock objects (`authService.ts`, and check `crimeService.ts`, `offenderService.ts`, `networkService.ts`, `predictionService.ts`, `victimService.ts` for the same `catch (error) { return mockX }` pattern — they should all follow the auth-service fix in §1.2).

---

## 5. MEDIUM — AI / Gemini Integration

### 5.1 Model auto-discovery filters out exactly the models it's trying to prefer

```python
valid_models = [
    m.name for m in models
    if 'generateContent' in m.supported_generation_methods
    and 'gemini' in m.name.lower()
    and 'pro' not in m.name.lower()          # <-- excludes every "pro" model
]
valid_models.sort(key=_rank_model, reverse=True)
```

```python
def _rank_model(model_name: str) -> tuple:
    ...
    is_pro = 1 if 'pro' in model_name else 0   # <-- ranks "pro" models higher... but they were already filtered out above
```

The filter excludes any model with `"pro"` in its name, then the ranking function tries to prioritize `"pro"` models that can never appear in the list. Net effect: `GEMINI_MODEL` default of `gemini-1.5-pro` is discovered and immediately discarded, and you always end up on flash-tier models regardless of what's configured, silently.

**Fix — decide intent and make the code match it.** If cost/rate-limit reasons are why "pro" was excluded, keep the exclusion and remove the now-meaningless `is_pro` ranking weight. If you actually want "pro" available, drop the exclusion:

```python
valid_models = [
    m.name for m in models
    if 'generateContent' in m.supported_generation_methods
    and 'gemini' in m.name.lower()
    # keep pro models in the pool now that ranking actually prefers them
]
valid_models.sort(key=_rank_model, reverse=True)
```

### 5.2 No rate limiting on the AI assistant / any endpoint other than login

```python
@router.post("/login")
@limiter.limit("10/minute")     # the only rate-limited endpoint in the whole codebase
```

`assistant_router.py`, `network_router.get_network_ai_summary`, and every other Gemini-backed endpoint have no per-user/per-IP throttling. Since each call can hit a metered, paid external API (and — per §5.1 — retries across up to 4 key/model combinations on failure), an authenticated user (or, combined with §1.1's bypass, literally anyone) can drive your Gemini bill and rate limits into the ground with a simple loop.

**Fix:**

```python
# assistant_router.py
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

@router.post("/chat")
@limiter.limit("20/minute")
async def chat(request: Request, ...):
    ...
```

Apply the same `@limiter.limit(...)` pattern to `network_router.fetch_ai_summary`, `reports_router` generation endpoints, and `import_router` bulk-import endpoints — anything that's expensive (LLM calls, large DB writes, file processing) should have an explicit ceiling.

### 5.3 Global exception handler leaks internal error detail to clients

```python
return JSONResponse(
    status_code=500,
    content={"detail": "Internal Server Error", "message": str(exc)},   # raw exception text returned to the client
    headers=headers,
)
```

`str(exc)` can leak stack-trace-adjacent detail — SQL fragments, file paths, internal service names — to any client that manages to trigger a 500. Log the detail server-side; don't return it.

**Fix:**

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.url.path}: {exc}", exc_info=True)
    headers = {}
    origin = request.headers.get("origin", "")
    if origin in allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": "Internal Server Error"},
        headers=headers,
    )
```

### 5.4 MD5 used for the Gemini prompt-cache key

```python
def generate_prompt_hash(prompt: str) -> str:
    return hashlib.md5(prompt.encode()).hexdigest()
```

Not a security issue here (it's only a cache key, not used for auth/integrity), but MD5 is deprecated in most security linters/compliance scanners and will get flagged in an audit. Swap to `hashlib.sha256` — negligible cost, one less finding in your next pen-test report:

```python
def generate_prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()
```

---

## 6. MEDIUM — Maps & Network Graph

### 6.1 Map/network components rely on the same hardcoded/unauthenticated calls described in §2.3
`CrimeMap.tsx`, `HotspotMap.tsx`, `RiskMap.tsx` (Leaflet) and `NetworkGraph.tsx` (Cytoscape) themselves use OpenStreetMap tiles (no API key required, fine as-is), but the **data** feeding them goes through `crimeService`/`hotspotService`/`networkService`, all of which route through the shared `api` instance — good — **except** the export/evidence links noted in §2.3 which don't. Apply the §2.3 fix there.

### 6.2 `get_network_graph` builds Cypher with an f-string for `relationship_type`

```python
def create_criminal_relationship(offender_id_1, offender_id_2, relationship_type, ...):
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"Invalid relationship_type: {relationship_type}")
    query = f"""
    MATCH (c1:Criminal {{offender_id: $id1}})
    MATCH (c2:Criminal {{offender_id: $id2}})
    MERGE (c1)-[r:{relationship_type}]->(c2)
    ...
```

This one specific query is actually safe today because `relationship_type` is validated against the `RELATIONSHIP_TYPES` allow-list *before* being interpolated — Cypher doesn't support parameterized relationship-type names, so the f-string is the correct approach here as long as that validation stays in place. **Flagging it so nobody "simplifies" this function later and removes the allow-list check** — if that check is ever removed or bypassed (e.g. a new caller that skips this function and builds Cypher some other way), this becomes a graph-injection vector. Add a comment to that effect directly above the check:

```python
def create_criminal_relationship(offender_id_1, offender_id_2, relationship_type, ...):
    # SECURITY: relationship_type is interpolated directly into the Cypher query below
    # because Neo4j doesn't support parameterizing relationship type names. This allow-list
    # check is the only thing preventing Cypher injection here — do not remove it, and do not
    # add any other caller that builds a relationship-type Cypher string without this check.
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"Invalid relationship_type: {relationship_type}")
    ...
```

---

## 7. LOW / CLEANUP

| # | Issue | File | Fix |
|---|---|---|---|
| 7.1 | `requirements.txt` lists `asyncpg==0.29.0` twice | `requirements.txt` | Remove the duplicate line; harmless but sloppy |
| 7.2 | `Alerts: // Alerts` duplicate comment | `apiEndpoints.ts` | Cosmetic, delete duplicate comment line |
| 7.3 | `.env.example` `REDIS_PASSWORD` is set, but `config.py`'s `REDIS_PASSWORD: Optional[str] = None` default is `None` — if an operator copies `.env.example` incompletely, Redis silently connects unauthenticated in the code path where `REDIS_PASSWORD` isn't provided | `config.py`, `redis_connection.py` | Make `REDIS_PASSWORD` required (no default) once you're past local dev, so a missing password fails startup instead of connecting without one |
| 7.4 | No `Content-Security-Policy` header, only `X-Content-Type-Options`/`X-Frame-Options`/`X-XSS-Protection`/HSTS | `main.py` `SecurityHeadersMiddleware` | Add a CSP header once you know your final asset/CDN origins, e.g. `default-src 'self'; connect-src 'self' https://your-api-domain` |
| 7.5 | `workers = 1 if ENVIRONMENT == "development" else 4` hardcoded in `main.py`'s `__main__` block | `main.py` | Fine for a quick start, but in real production you'd run under `gunicorn -k uvicorn.workers.UvicornWorker` or a process manager instead of `python main.py`, with worker count driven by CPU count / an env var, not a hardcoded `4` |
| 7.6 | CI (`ci.yml`) has no lint step (`ruff`/`eslint`), no `docker build` verification, and doesn't run against a real Postgres/Neo4j/Redis service — so `pytest` presumably runs against mocks or skips DB-dependent tests silently | `.github/workflows/ci.yml` | Add `services: postgres:`, `redis:`, `neo4j:` blocks to the `backend-test` job (GitHub Actions supports service containers) so integration tests actually exercise the DB layer |

---

## Suggested order of work

1. **Security first** (§1) — remove the auth bypass, fix the mock-login fallback, lock down `/uploads`, add WebSocket auth, and audit every router for missing `Depends(get_current_user)`.
2. **Make the frontend deployable** (§2.1–2.3) — env-based config, kill the hardcoded URLs, route every request through the authenticated `api` client.
3. **Fix the event-loop-blocking Neo4j calls** (§3.1) — this is the difference between the API scaling under load or falling over.
4. **Clean up secrets and Docker** (§3.3–3.4) — rotate the committed passwords, stop publishing DB ports, add a frontend Docker service.
5. **Rate-limit and harden the AI paths** (§5) — cost control and DoS resistance.
6. Everything in §6–7 as time allows — these are real but lower-blast-radius issues.

If you want, I can also produce ready-to-apply unified diffs for any specific file above, or walk through the remaining routers/services (`crimes_router`, `offenders_router`, `predictions_router`, `import_router`, etc.) at the same depth — just say which ones matter most for your launch.