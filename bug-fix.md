# SHASTRA — Full Platform Audit Report
**Scope:** All 14 pages, frontend↔backend wiring, DB connections (Postgres / Neo4j / Redis), Criminal Network graph + filters, district/crime filters, AI response sanitization, pagination.
**Method:** Static review of `crime_frontend` (React/TS) and `crime_backend/MODULE_2_BACKEND` (FastAPI), endpoint-by-endpoint cross-reference, and per-page trace of every API call.
**Note:** This is an issues list only — no fixes were applied. Every issue below is backed by an exact file/line reference so you can jump straight to it.

---

## 0. How the system is wired (for context)

- Frontend calls `crime_frontend/src/constants/apiEndpoints.ts` → `axios` instance in `services/api.ts` → FastAPI routers under `/api/*`.
- Backend talks to **Postgres** (relational data), **Neo4j** (criminal network graph), **Redis** (cache + token blacklist + rate limiting), and **Gemini** (AI narratives).
- I cross-checked every route in `app/routers/*.py` against every call in `crime_frontend/src/services/*.ts`. **All 68 backend endpoints are reachable and correctly referenced from the frontend** — no orphaned/mismatched URLs, no wrong HTTP verbs, no broken path params. This part of the wiring is solid.
- The real problems are not "broken links" — they are **missing pagination, unbounded queries, inconsistent data contracts, and a few spots where AI markdown isn't sanitized**. Details below.

---

## 1. CRITICAL issues (fix before production)

### 1.1 Unbounded queries — no pagination on several list endpoints
These endpoints return **every matching row, with no `LIMIT`/`OFFSET`, and no `page`/`page_size` params at all**. As data grows, these will slow down and eventually crash the browser tab (full array kept in React state + rendered as one giant `<table>`).

| Endpoint | File | Issue |
|---|---|---|
| `GET /api/alerts/active` | `app/services/alert_service.py:294-314` | No `LIMIT`. Query: `select(Alert).where(...)` — returns ALL active alerts forever. |
| `GET /api/settings/audit-logs` | `app/routers/settings_router.py:32-59` | Hardcoded `.limit(100)` server-side, **no `page`/`offset` param exposed** — you can never see log #101 onward. |
| `GET /api/settings/users` | `app/routers/settings_router.py:61-68` | No limit/pagination at all. |
| `GET /api/hotspots/clusters`, `/time-patterns` | `app/routers/hotspots_router.py:23,56` | No limit param. |
| `GET /api/victims/search` | `app/routers/victims_router.py:12-33` | No `page`/`page_size` params (unlike offenders' identical-purpose endpoint, which has them — inconsistent). |

**Frontend mirrors this** — `AlertsPage.tsx`, `SettingsPage.tsx` (Users tab, Audit Log tab), `HotspotAnalysis.tsx`, `VictimDatabase.tsx`, `OffenderDatabase.tsx`, `AnomalyDetection.tsx` all render the **entire returned array** with no client pagination, no "load more", no virtualization:

```tsx
// AlertsPage.tsx — loads and renders the full unbounded alerts array
const load = async () => {
  setLoading(true);
  const data = await alertService.getAlerts();   // no limit param sent
  dispatch(setAlerts(data));
  setLoading(false);
};
// ...
<AlertsTable alerts={filtered as any} onMarkRead={handleMarkRead} onDismiss={handleDismiss} />
// AlertsTable.tsx maps over the array directly, no slicing, no page controls
```

**Note:** `CrimeDatabase.tsx` is the **one page that does this correctly** (`page`, `pageSize`, `totalCount`, prev/next buttons wired to `GET /api/crimes/filter`). Use it as the reference pattern for the fixes.

Also note `offenders_router.py` (`/search`) and `anomalies_router.py` (`/list`) and `crimes_router.py` (`/filter`) **already have `page`/`page_size` support server-side** — but the corresponding frontend pages (`OffenderDatabase.tsx`, `AnomalyDetection.tsx`) never send those params and never render pagination controls, so the backend capability is wasted:

```ts
// offenderService.ts — page/page_size are typed and accepted...
searchOffenders: async (query = "", filters?: { ...; page?: number; page_size?: number }) => { ... }

// ...but OffenderDatabase.tsx never sets or passes them:
const executeSearch = async (q = search, d = districtFilter, c = crimeTypeFilter, r = riskLevelFilter, s = statusFilter) => {
  const filters: any = {};
  if (d !== "all") filters.district_id = d;
  if (c !== "all") filters.crime_type = c;
  if (r !== "all") filters.risk_level = r;
  if (s !== "all") filters.status = s;
  // <-- no page / page_size ever added here
  const data: any = await offenderService.searchOffenders(q, filters);
};
```

**Pages with NO pagination whatsoever (UI or API):** Alerts Center, Anomaly Detection, Offender Database, Victim Database, Hotspot Analysis, Settings → Users, Settings → Audit Logs, Reports (saved list).
**Pages with pagination done correctly:** Crime Database only.

---

### 1.2 AI-generated text rendered without markdown sanitization (the `**` issue)
`AIMarkdown.tsx` (`components/common/AIMarkdown.tsx`) is a well-built sanitizer (uses `react-markdown` + `rehype-sanitize` + `remark-gfm`) and is correctly used in `AIChatWidget.tsx`, `CriminalNetwork.tsx`, `HotspotAnalysis.tsx`, `PredictiveAnalytics.tsx`, and `SocioEconomicInsights.tsx`.

But it is **not used everywhere Gemini output is displayed** — these spots will show raw `**bold**`, `*italic*`, `- ` bullets, etc. as literal characters:

```tsx
// OffenderDatabase.tsx ~line 248-252
// selected.modus_operandi can be `ai_mo_summary` from Gemini (offender_service.py normalizes
// modus_operandi <- ai_mo_summary) — rendered as raw text, not through AIMarkdown:
{selected.modus_operandi && !modusOperandi && (
   <p className="text-xs text-slate-200 leading-relaxed">
     {typeof selected.modus_operandi === 'string' ? selected.modus_operandi : selected.modus_operandi.typical_target || "N/A"}
   </p>
)}
```

```tsx
// OffenderDatabase.tsx ~line 259-264 — the /modus-operandi endpoint result
// (backend: offender_service.py -> Gemini-generated fields) rendered raw, field by field:
{Object.entries(modusOperandi).map(([k, v]) => (
  <div key={k} className="flex justify-between text-xs">
    <span className="text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
    <span className="text-slate-200 text-right max-w-[60%]">{Array.isArray(v) ? v.join(", ") : String(v)}</span>
  </div>
))}
```

**Fix pattern** (apply everywhere AI text is shown raw):
```tsx
import AIMarkdown from "../components/common/AIMarkdown";
// ...
<AIMarkdown text={typeof selected.modus_operandi === 'string' ? selected.modus_operandi : selected.modus_operandi.typical_target || "N/A"} />
```

**Also check on the backend side** — confirm which Gemini prompts explicitly ask for markdown vs. plain text, so you're not sanitizing text that was never meant to have `**` in the first place. `app/services/gemini_service.py` is the single place all AI text originates from; grep it for every field name (`ai_mo_summary`, `ai_analysis`, `ai_explanation`, `summary_text`, `insight`, `narrative`) and confirm each has a frontend consumer wrapped in `AIMarkdown`.

**Full audit of every AI text field found:**

| Field | Backend source | Frontend consumer | Sanitized? |
|---|---|---|---|
| Assistant chat answer | `assistant_router.py` → `/ask` | `AIChatWidget.tsx` | ✅ Yes |
| Network AI summary (`summary_text`, `key_findings`, etc.) | `network_service.py` | `CriminalNetwork.tsx` | ✅ Yes (summary_text) — but `key_findings[]`, `recommended_actions[]`, `suspicious_pairs[]` are rendered as **raw `<li>{item}</li>` / `<p>{item}</p>`**, not through `AIMarkdown` (see `CriminalNetwork.tsx:746-770`) |
| Node `ai_analysis` | `network_service.py` | `CriminalNetwork.tsx:683` | ✅ Yes |
| Edge insight | `network_router.py` → `/edge-insight` | `CriminalNetwork.tsx` | ✅ Yes |
| Hotspot `ai_summary` (deployment suggestions) | `hotspot_service.py` | `HotspotAnalysis.tsx` | ✅ Yes |
| Emerging typology `ai_explanation` | `prediction_service.py` | `PredictiveAnalytics.tsx` | ✅ Yes |
| Socioeconomic `ai_analysis` narrative | `socioeconomic_service.py` | `SocioEconomicInsights.tsx` | ✅ Yes |
| Offender `ai_mo_summary` / modus operandi fields | `offender_service.py` | `OffenderDatabase.tsx` | ❌ **No — raw text/objects** |
| Offender risk `risk_factors` (explainability) | `offender_service.py` | `ExplainabilityPanel.tsx` | ⚠️ Rendered as plain `<p>` bullets — fine only if backend guarantees plain-text (no markdown) output; verify the Gemini prompt for this field doesn't ask for bold/lists |
| Anomaly `reasoning`/explanation | `anomaly_service.py` | `AnomalyDetection.tsx` | ⚠️ Not found rendered anywhere in the page at all — see §2.4 |

Fix for `key_findings`/`recommended_actions`/`suspicious_pairs` in `CriminalNetwork.tsx`:
```tsx
{(Array.isArray(aiSummary?.key_findings) ? aiSummary.key_findings : []).map((kf, i) => (
  <li key={i}><AIMarkdown text={kf} /></li>   // instead of raw {kf}
))}
```

---

### 1.3 JWT stored in `localStorage` + sent as a WebSocket query-string param
```ts
// services/api.ts
const token = localStorage.getItem("auth_token");
```
```ts
// App.tsx
ws = new WebSocket(`${base}?token=${encodeURIComponent(token || "")}`);
```
- `localStorage` is readable by any injected script — if there is ever an XSS anywhere in the app (e.g., via the AI chat markdown renderer, a compromised dependency, etc.), the token is trivially stolen. Prefer an `httpOnly` secure cookie for the access token, or at minimum add strict CSP (already partially present) and keep this on the radar.
- Putting the JWT in a WebSocket URL query string means it can end up in browser history, proxy logs, and server access logs. Prefer sending the token as the first message after the socket opens (a subprotocol/auth-frame handshake) rather than in the URL.

---

### 1.4 Database ports exposed to the host in `docker-compose.yml`
```yaml
postgres:
  ports:
    - "5432:5432"
```
Postgres (and check Neo4j/Redis further down the file — same pattern) are bound to the host's public interface. For production, remove these `ports:` mappings (keep them reachable only via the internal `crime_intelligence_network`), or bind to `127.0.0.1:5432:5432` if you need local debugging access.

---

## 2. Page-by-page findings

### 2.1 Login
- `Login.tsx` posts to `/api/auth/login`, stores token via `authService`. Wiring is correct.
- No rate-limit/lockout UI feedback beyond a generic error — backend does rate-limit login (`slowapi`), but confirm the frontend surfaces a clear "too many attempts" message rather than a generic failure (check `authService.ts` error handling — currently any failure shows the same generic text).

### 2.2 Dashboard
- `getRecentCrimes`/`getRecentAlerts` correctly pass a `limit` param — this page is fine, no unbounded fetch (it's meant to be a small "recent" widget, not a full list).
- No filters expected/needed here — none present, consistent with the page's purpose.

### 2.3 Crime Map
- `CrimeMapPage.tsx` correctly guards the "All Districts"/"All" sentinel values before sending filters to `/api/crimes/map-data`.
- Backend caps map data at `limit: int = Query(5000, ge=1, le=20000)` (`crimes_router.py:26`) and the frontend has `pinsTruncated` state — **good**, this is properly handled (shows a "results truncated" indicator). This is the pattern the other pages should copy.

### 2.4 Crime Database — ✅ best-implemented page
- Full server-side pagination (`page`, `page_size`, `totalCount`, prev/next). Filters (district/type/status) correctly guarded against the "All" sentinel. Use this file as the template for fixing the other pages.
- Minor: `search` state is explicitly client-side only ("Search page..." placeholder) — i.e., search only filters the *current page* of 20 rows, not the full dataset. Confirm this is the intended UX; if not, the `/crimes/filter` endpoint needs a `search`/`q` param added and wired.

### 2.5 Hotspot Analysis
- No pagination on `clusters`/`time-patterns`/`top-list` (top-list does have a `limit` param, default 10, but it's not surfaced as a user-adjustable control).
- AI summary correctly sanitized via `AIMarkdown`.
- Polls every 60s (`setInterval(() => fetch(true), 60000)`) — confirm this interval doesn't stack with the network `/api/network/ai-summary` rate limit of "20/minute" if a user leaves multiple tabs open; not currently an issue on this specific page, but worth being aware of shared quotas.

### 2.6 Criminal Network — largest, most complex page (785 lines)
- Filters (search, node type, crime type, district) all correctly guard "all" sentinel and are round-tripped into the URL via `useSearchParams` (nice touch — filters are shareable/bookmarkable).
- `GET /api/network/graph-data` hard-caps at `node_limit: int = 100` server-side (`network_service.py:81`) with **no way for the frontend to request more, fewer, or "next page" of nodes**. For a large criminal network this silently truncates the graph. There is a `g.warning` field surfaced to the UI when truncation/fallback happens — good — but there's no way to actually see the rest of the network short of narrowing filters.
- `key_findings`, `recommended_actions`, `suspicious_pairs` rendered without `AIMarkdown` (see §1.2).
- "Mark All Read"-style N+1 pattern also appears here in edge-insight/expand flows — generally fine since these are single-node actions, not loops.
- `getEdgeInsight` and `getNodeAiAnalysis` in `networkService.ts` swallow errors and return `null` instead of surfacing them — the UI shows "No insight available" for both real "nothing found" and actual network failures, making debugging harder in production. Consider distinguishing the two.
- `ConnectivityMatrix.tsx` (Grid view / matrix mode): confirm this is wired to the same node/edge dataset as the graph view (it consumes the same `nodes`/`edges` shape) — good, single source of truth, no separate/duplicate fetch found.

### 2.7 Anomaly Detection
- **No pagination anywhere** — `AnomalyDetection.tsx` calls `getAnomalies()` once on mount with **no filters passed at all** (severity/district filters exist in `predictionService.ts`'s `getAnomalies(filters)` signature but the page calls it with zero args):
```tsx
useEffect(() => { fetch(); }, []);   // fetch() -> predictionService.getAnomalies() with no params
```
  Meanwhile the backend supports `severity`, `status`, `district_id`, `page`, `page_size` (`anomalies_router.py:18-30`) — **none of these are exposed as UI controls** on this page except a client-side `statusFilter` that filters the already-fetched (unpaginated) array.
- No AI reasoning/explanation is rendered anywhere on this page even though the anomaly model clearly carries some kind of explanation field server-side (worth confirming with `anomaly_service.py` what fields exist and whether `ExplainabilityPanel` should be used here too, the way it's used on Offender Database).

### 2.8 Predictive Analytics
- AI text (`ai_explanation`) correctly sanitized.
- No visible filters for district/date-range on this page at all — `risk-map`, `high-risk-areas`, `forecast`, `emerging-typologies` are called with no params even though several of these endpoints accept optional filters server-side. Confirm this is intentional (state-wide-only view) or a missing feature.

### 2.9 Criminal Network — *(covered under 2.6)*

### 2.10 Offender Database
- Filters correctly guard the `"all"` sentinel.
- **No pagination UI**, despite backend `page`/`page_size` support (see §1.1).
- Raw (unsanitized) AI text rendering (see §1.2) — this is the primary place users will see literal `**`.
- `handleRegisterOffender` re-runs `handleSearch(search)` after creating an offender but doesn't reset filters/page — fine for now since there's no pagination, but will need attention once pagination is added (should probably reset to page 1 after a mutation).

### 2.11 Victim Database
- Backend `/api/victims/search` has **no pagination params at all** (unlike the near-identical Offender search) — inconsistent API design. If the victim list grows, there's no way to page through results without adding backend support first.
- Confirm PII handling here specifically — victim registration (`POST /api/victims`) is scoped to `require_role(["SCRB_OFFICER","DISTRICT_OFFICER","INVESTIGATOR"])` server-side (good), but double check the Victim Database *view/search* endpoint (`GET /api/victims/search`) has equivalent role/district scoping — worth explicitly verifying since victim data is the most sensitive PII in the system, and no `scope_district_param`/role check was found being applied here the way it is in `crimes_router.py`, `alerts_router.py`, `network_router.py`. **Verify this explicitly** — if missing, any authenticated user in any district can search victims statewide.

### 2.12 Socio-Economic Insights
- AI narrative correctly sanitized via `AIMarkdown`.
- Correlation/insight data appears state-wide with a district selector — confirm the district selector is actually wired to a refetch (double check filter → `predictionService.getSocioeconomicCorrelation(filters)` call is triggered on district change, not just on mount).

### 2.13 Alerts Center
- **No pagination** — see §1.1. Loads and keeps the *entire* alerts history table in Redux (`store/alertsSlice.ts`) for the life of the session, growing further with every WebSocket-pushed `NEW_ALERT`. Long-running sessions will accumulate an ever-growing array client-side with no cap.
- `handleMarkAllRead` marks alerts read one at a time in a sequential loop:
```tsx
const handleMarkAllRead = async () => {
  const unread = alerts.filter((a) => !a.is_read);
  for (const a of unread) {
    await alertService.markRead(a.alert_id);   // N sequential round-trips
    dispatch(markAlertRead(a.alert_id));
  }
};
```
  With many unread alerts this is slow and easy to accidentally rate-limit against. Prefer a bulk `PUT /api/alerts/mark-all-read` endpoint (needs to be added backend-side) or at minimum `Promise.all(...)`.
- WebSocket (`/api/alerts/ws`) is correctly wired in `App.tsx` with reconnect/backoff logic — good implementation overall, just needs the pagination + bulk-action fixes above.

### 2.14 Reports
- `POST /api/reports/generate` is rate-limited server-side to `5/minute` — confirm the frontend disables the "Generate" button while a request is in flight and shows a clear "rate limited, try again in X" message rather than a generic error (currently just shows `successMsg`/error text, not specifically rate-limit-aware).
- Saved reports list (`GET /api/reports/history`) has a `limit` param (default 20, max 100) but **no page/offset param** and the frontend doesn't pass or expose any — same "first N only, no way to see older reports" issue as elsewhere.

### 2.15 Settings & Administration
- **Users tab**: no pagination on `GET /api/settings/users`.
- **Audit Log tab**: hardcoded backend `.limit(100)` with zero pagination controls in `SettingsPage.tsx` — once you have >100 audit events, everything before them becomes permanently invisible in the UI.
- **Districts tab / data sync**: `POST /api/settings/datasources/{source_id}/sync` — confirm the frontend shows sync status/errors distinctly (didn't find a clear loading/error state specific to sync failures vs. generic error).
- **Alert thresholds**: GET/PUT wired correctly.

---

## 3. Filters audit (district & crime-type specifically, as requested)

**Good news:** the "All" sentinel-guarding pattern (never sending the literal string `"All"`/`"all"`/`"All Districts"` to the backend as a real filter value) is implemented **correctly and consistently** everywhere it's used — `CrimeDatabase.tsx`, `CrimeMapPage.tsx`, `HotspotAnalysis.tsx`, `OffenderDatabase.tsx`, `CriminalNetwork.tsx` all guard this properly. I checked each one individually; no case-sensitivity or sentinel-leak bugs found in the actual filter-building code.

**Real issue found — dead/inconsistent constants that are a landmine for future code:**
```ts
// crime_frontend/src/constants/crimeTypes.ts
export const RISK_LEVELS = ["High", "Medium", "Low"] as const;        // Capitalized
export const SEVERITY_LEVELS = ["Critical","High","Medium","Low"] as const;
export const STATUS_OPTIONS = ["Active","Imprisoned","Absconding","Deceased"] as const;
```
```python
# crime_backend/MODULE_2_BACKEND/app/core/config.py
RISK_LEVELS = ["HIGH", "MEDIUM", "LOW"]                                # UPPERCASE
SEVERITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
OFFENDER_STATUS_VALUES = ["ACTIVE", "IMPRISONED", "ABSCONDING", "DECEASED"]
```
The backend does an **exact-match, case-sensitive** comparison:
```python
# offender_service.py:46
conditions.append(Offender.risk_level == risk_level)
```
Currently the pages that actually filter by risk/severity/status hardcode the correct UPPERCASE values inline (`OffenderDatabase.tsx` uses `"HIGH"/"MEDIUM"/"LOW"` directly, not the constant), so **there is no live bug today** — but `RISK_LEVELS`/`SEVERITY_LEVELS`/`STATUS_OPTIONS` in `crimeTypes.ts` are dead, wrongly-cased exports. The next developer who "cleans up" a dropdown by swapping the inline array for these constants will silently break every risk/severity/status filter (queries will just return zero results, no error). **Fix:** either delete these three exports or fix their casing to match the backend and then actually use them.

**District source of truth:** `useDistricts()` hook correctly fetches from `GET /api/settings/districts` (no hardcoded district lists found in components — good). Note it has no shared cache/context, so every page that uses it fires its own `/settings/districts` request on mount; harmless but wasteful (7+ duplicate identical requests per session). Consider lifting it into a React Context or a simple module-level cache/SWR.

---

## 4. Criminal Network graph — feature checklist

| Feature | Status |
|---|---|
| Search by name/id | ✅ Wired, debounced (400ms) |
| Filter by node type | ✅ Wired, URL-persisted |
| Filter by crime type ("lens") | ⚠️ Wired end-to-end (request → response → render), but returns wrong/empty results for Criminal & Victim nodes in production — root cause found and documented in **§6** |
| Filter by district | ⚠️ Wired end-to-end (request → response → render), but returns wrong/empty results for Criminal & Victim nodes in production — root cause found and documented in **§6** |
| Show isolated nodes toggle | ✅ Confirmed wired — `CriminalNetwork.tsx:288-297` filters into `filteredNodes`, passed to `<NetworkGraph nodes={filteredNodes}>` |
| Visual cluster/component separation | ❌ Not implemented today (nodes/edges render flat); backend already computes `community_id` via Louvain and frontend already colors by it — see §7 for a ready-to-use implementation using Cytoscape compound nodes |
| AI network summary | ✅ Wired, sanitized |
| Node AI analysis (per-node) | ✅ Wired, sanitized, rate-limited 20/min server-side |
| Edge insight (per-relationship) | ✅ Wired, sanitized |
| Shortest path / compare two nodes | ✅ Wired, rate-limited 10/min server-side |
| Node expansion (double-click to load neighbors) | ✅ Wired |
| Ego-network navigation history (back/forward) | ✅ State present (`navHistory`, `navIndex`) |
| Matrix/Grid alternate view | ✅ Wired, same data source as graph view |
| Node/edge count limit visibility | ⚠️ `node_limit=100` hardcoded server-side with no UI control or "showing 100 of N" count surfaced beyond a generic `warning` string |
| Pagination / "load more nodes" | ❌ Not implemented |

---

## 5. Database connectivity review

- **Postgres**: primary store for crimes, offenders, victims, alerts, users, audit logs, districts. `init_db()` in `app/core/database.py` runs at startup; app continues in "degraded mode" if unavailable (logs a warning) rather than crashing — good resilience choice, but confirm every router handles a possibly-down DB gracefully (i.e., returns a clean 503, not an unhandled 500) — didn't find a systematic dependency-level DB-health guard on the routers themselves, only the global exception handler catching whatever falls through.
- **Neo4j**: powers the Criminal Network graph. Also degrades gracefully (`init_neo4j()` failure → "continuing in degraded mode", and `network_service.py` has a Postgres-based fallback path — confirmed via `g.source === "postgres_fallback"` handling in `CriminalNetwork.tsx`). This is a genuinely good design — the graph page has a real, working degraded mode. Confirm `sync_neo4j.py` (found in repo root of backend) — the script that presumably keeps Neo4j in sync with Postgres — is actually scheduled somewhere (checked `app/scheduler/scheduled_tasks.py` — worth confirming Neo4j sync is one of the scheduled jobs, not just a manually-run script, or graph data can silently drift out of date from the relational source of truth).
- **Redis**: used for caching (`cache_key` patterns seen throughout `*_service.py` files), JWT blacklist (logout/revocation), and rate limiting (`slowapi` + `get_remote_address`). Also degrades gracefully. Cache keys are built from filter params (e.g. `f"crimes_map_data:{file_format}:{crime_type}:{resolved_district}:..."`) — reasonable, but confirm a sensible `CACHE_EXPIRY_SECONDS` (`config.py` default 900s/15min) is appropriate for near-real-time pages like Alerts and Dashboard, vs. slower-changing pages like Socio-Economic Insights — a single global TTL for everything is a one-size-fits-all compromise worth revisiting per-endpoint.

---

## 6. ROOT CAUSE FOUND — district & crime-type filters silently fail on the Criminal Network graph

You reported this bug repeatedly and it's real — I traced it end-to-end (frontend → API → Neo4j sync scripts → Cypher query) and found the exact cause. **Short version: it's not the dropdowns, it's the data feeding Neo4j.** The district and crime-type filters on the Criminal Network page rely on every node in Neo4j having `district_id` and `crime_types` properties set correctly — and the script that populates Neo4j on first deploy (and the one documented in the README for manual re-sync) never sets those two properties on Criminal or Victim nodes at all. So the filter code itself is fine; it's filtering against data that was never written.

### 6.1 The query that powers the filter (this part is correct)
`app/core/neo4j_connection.py:266-280` (`get_network_graph()`) builds the Cypher `WHERE` clause like this:
```python
if district_id:
    where_clauses.append("n.district_id = $district_id")
    params["district_id"] = district_id

if crime_type:
    where_clauses.append("$crime_type IN n.crime_types")
```
This is a completely reasonable, standard way to filter — **if** every node actually has `district_id` and `crime_types` properties. That's where it breaks.

### 6.2 Bug A (the main one) — the seed/manual sync script never writes `district_id` or `crime_types` onto Criminal/Victim nodes
`sync_neo4j.py` (repo root of the backend — this is the script the **README tells you to run** at line 83: `docker compose exec backend python sync_neo4j.py`, and the one **automatically run on first-ever startup** via `app/core/database.py:152-155`) does this:
```python
# sync_neo4j.py:30-38 — offenders synced with NO district_id, NO crime_types
await sync_offender_to_neo4j({
    "offender_id": str(o.offender_id),
    "name": f"{o.first_name} {o.last_name}".strip(),
    "risk_level": o.risk_level,
    "risk_score": float(o.risk_score) if o.risk_score else 0.0,
    "crime_count": int(o.total_crimes) if o.total_crimes else 0,
    "status": o.status
    # <-- district_id and crime_types are missing entirely
})
```
```python
# sync_neo4j.py:41-47 — same problem for victims
await sync_victim_to_neo4j({
    "victim_id": str(v.victim_id),
    "name": f"{v.first_name} {v.last_name}".strip(),
    "vulnerability_level": "HIGH" if len(v.vulnerability_factors or []) > 2 else "LOW",
    "victimization_count": v.total_victimizations or 1
    # <-- district_id and crime_types are missing entirely
})
```
But the underlying Cypher these functions run **requires** both params unconditionally:
```python
# app/core/neo4j_connection.py:117-126 — sync_offender_to_neo4j()
query = """
MERGE (c:Criminal {offender_id: $offender_id})
SET c.name = $name,
    c.risk_level = $risk_level,
    c.risk_score = $risk_score,
    c.crime_count = $crime_count,
    c.status = $status,
    c.district_id = $district_id,   # <- no value supplied by sync_neo4j.py
    c.crime_types = $crime_types    # <- no value supplied by sync_neo4j.py
RETURN c
"""
```
Neo4j requires every `$param` referenced in a query to actually be bound at execution time — when it isn't, the driver raises a `ClientError: Expected parameter(s): district_id, crime_types`. That error is then **caught and silently swallowed**:
```python
# app/core/neo4j_connection.py:89-95 — run_neo4j_query()
try:
    async with _driver.session() as session:
        result = await session.run(query, parameters or {})
        return [record.data() async for record in result]
except Exception as e:
    logger.error(f"Neo4j query error: {e}")   # logged only — never raised, never surfaced to the caller
    return []
```
Net effect: `sync_neo4j.py` logs `"Synced 500 offenders to Neo4j."` and looks successful, but **every single offender/victim MERGE actually failed** — the nodes are either never created, or (if they already existed from another source) never get `district_id`/`crime_types` written onto them. Either way: `n.district_id` and `n.crime_types` are `NULL` on Criminal/Victim nodes, so `n.district_id = $district_id` and `$crime_type IN n.crime_types` both evaluate to `NULL` (Cypher's "unknown"/falsy) — **the node is excluded from every district- or crime-type-filtered query, every time.**

**This explains exactly what you're seeing:** pick a district or a crime type on the Criminal Network page → Criminal and Victim nodes vanish (or the graph comes back near-empty), while Location nodes still show up fine — because Locations *are* synced correctly (see §6.4).

### 6.3 There's already a correct version of this script sitting unused
`scripts/sync_postgres_to_neo4j.py` does this properly — it computes each offender's/victim's actual `crime_types` from their linked crimes and includes `district_id`:
```python
# scripts/sync_postgres_to_neo4j.py:62-79 — the CORRECT pattern
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
    "district_id": off.district_id,     # present
    "crime_types": off_crime_types,     # present, computed from real crime links
})
```
**Fix:** point the README instructions and the `app/core/database.py` initial-seed call at `scripts/sync_postgres_to_neo4j.py` instead of the root-level `sync_neo4j.py`, and delete (or fix) the broken script so nobody runs it by accident:
```python
# app/core/database.py:152-155 — change this:
from sync_neo4j import sync as sync_neo4j_graph
await sync_neo4j_graph()
# to this:
from scripts.sync_postgres_to_neo4j import sync as sync_neo4j_graph   # adjust import path/function name to match
await sync_neo4j_graph()
```
```md
<!-- README.md:83 — change this: -->
docker compose exec backend python sync_neo4j.py
<!-- to this: -->
docker compose exec backend python scripts/sync_postgres_to_neo4j.py
```

### 6.4 Bug B — every offender *update* silently wipes `crime_types` back to empty
Even after a correct full re-sync, real-time edits break it again. `update_offender()` (used by `PUT /api/offenders/{offender_id}`, which `OffenderDatabase.tsx` calls whenever you edit an offender) does this:
```python
# app/services/offender_service.py:419-431
await sync_offender_to_neo4j({
    "offender_id": str(offender.offender_id),
    "name": f"{offender.first_name} {offender.last_name}",
    "risk_level": offender.risk_level,
    "risk_score": offender.risk_score or 0,
    "crime_count": offender.total_crimes or 0,
    "status": offender.status,
    "district_id": offender.district_id,
    "crime_types": [],   # <-- always overwrites with an empty list, wiping previously-correct data
})
# comment in the code even acknowledges this:
# "We would ideally fetch existing crime_types here, but for now we just pass empty to avoid losing district info"
```
So: run the correct bulk sync, everything filters fine → an officer edits that offender's status a day later → their `crime_types` in Neo4j silently resets to `[]` → that offender now disappears from every crime-type-filtered graph view until the next full bulk resync. This matches "the bug happens sometimes, not always" — it depends on whether the record was recently edited.

**Fix:** fetch the offender's current crime types from the existing links before syncing, instead of hardcoding `[]`:
```python
# app/services/offender_service.py — inside update_offender(), before the sync call
crime_types_result = await db.execute(
    select(Crime.crime_type)
    .join(CrimeOffenderLink, CrimeOffenderLink.crime_id == Crime.crime_id)
    .where(CrimeOffenderLink.offender_id == offender.offender_id)
    .distinct()
)
current_crime_types = [row[0] for row in crime_types_result.all()]

await sync_offender_to_neo4j({
    "offender_id": str(offender.offender_id),
    "name": f"{offender.first_name} {offender.last_name}",
    "risk_level": offender.risk_level,
    "risk_score": offender.risk_score or 0,
    "crime_count": offender.total_crimes or 0,
    "status": offender.status,
    "district_id": offender.district_id,
    "crime_types": current_crime_types,   # no longer wipes existing data
})
```

### 6.5 Bug C — even with correct data, connected/neighbor nodes are never district-filtered
This one doesn't cause an empty graph, but it does cause a confusing partial-filter result. Only the **root** node set is filtered by `district_id`; the neighbors pulled in via the relationship expansion are not:
```python
# app/core/neo4j_connection.py:289-297
CALL {{
  WITH n
  OPTIONAL MATCH (n)-[r]-(connected)
  WHERE $crime_type IS NULL
     OR $crime_type IN coalesce(r.crime_types, [])
     OR $crime_type IN coalesce(connected.crime_types, [])
  RETURN r, connected
  LIMIT 25
}}
```
Notice there's no `connected.district_id = $district_id` condition here at all — so filtering by "Bengaluru Urban" will correctly restrict which nodes can be the *center* of the graph, but any of their connections from other districts will still be pulled in and rendered. If the intent is a hard district boundary (which is what a user visually expects from a "district filter"), add the same district condition to this inner match:
```python
CALL {{
  WITH n
  OPTIONAL MATCH (n)-[r]-(connected)
  WHERE ($crime_type IS NULL
     OR $crime_type IN coalesce(r.crime_types, [])
     OR $crime_type IN coalesce(connected.crime_types, []))
    AND ($district_id IS NULL OR connected.district_id = $district_id)   # NEW
  RETURN r, connected
  LIMIT 25
}}
```
(and add `params["district_id"] = district_id if district_id else None` alongside the existing `params["crime_type"]` line so `$district_id` is always bound, the same fix pattern as Bug A.)

### 6.6 Why this was easy to miss in testing
The **Postgres fallback path** (`build_network_from_postgres()` in `network_service.py`, used only when Neo4j is unreachable) filters district and crime type correctly — I verified this separately in §4/§7 review and found no bugs there. Since your `docker-compose.yml` marks Neo4j as a required healthy dependency for the backend to start, Neo4j is up in any normal run — so the app is almost always using the **broken** live-Neo4j path, not the working fallback. If anyone tested this bug specifically by temporarily stopping Neo4j, filtering would have looked correct (fallback path), masking the issue.

### 6.7 Fix checklist for this specific bug
1. Fix or delete `sync_neo4j.py` at the backend root; standardize on `scripts/sync_postgres_to_neo4j.py`, which already computes `crime_types`/`district_id` correctly (§6.3).
2. Update the initial-seed call in `app/core/database.py:152-155` and the README instructions to use the correct script.
3. Stop the accidental data loss in `update_offender()` — fetch current crime types instead of hardcoding `[]` (§6.4). Check `update_offender`'s Victim equivalent too if one exists, and any other place `crime_types: []` is hardcoded outside of true "brand-new record" creation.
4. Decide whether cross-district neighbors should appear when a district filter is active; if not, add the missing `connected.district_id` condition (§6.5).
5. After fixing, run a full re-sync (`python scripts/sync_postgres_to_neo4j.py`) against your existing database once, since any nodes created via the broken path may currently have `district_id`/`crime_types` permanently missing until re-synced.
6. Consider making `run_neo4j_query()`'s exception handling less silent for write operations specifically (reads returning `[]` on failure is reasonable/graceful; a failed **write/sync** silently returning `[]` and being logged as success upstream is how this bug went unnoticed — writes should probably re-raise or return a clear failure signal the caller can act on).

---

## 7. Implementation: visually separating clusters in the Criminal Network graph

**Context:** the graph currently renders every node/edge flat in one Cytoscape canvas. When many small, unrelated groups of connected people exist (e.g., a 20-person gang with zero links to anyone else), they visually blend into the rest of the graph instead of reading as a distinct group.

**What's already in place (confirmed in code) — you don't need to build this part:**
- Backend already runs **Louvain community detection** and assigns every node a `community_id`: `app/services/network_service.py:52-71` (`detect_communities()`, using `networkx.algorithms.community.louvain_communities`).
- Frontend already **colors** nodes by `community_id`: `NetworkGraph.tsx:94-98`.
- Layout already uses `fcose` with `packComponents: true` (`NetworkGraph.tsx:48`), which gives disconnected components *some* automatic spacing — but there's no visible boundary, label, or extra spacing tuning around each group, so it's easy to miss at a glance.
- `showIsolated` toggle is **confirmed correctly wired** (I flagged this as "unconfirmed" in §4 — I traced it further and it is: `CriminalNetwork.tsx:288-297` filters `nodes` down to `filteredNodes` based on `showIsolated`, which is what's actually passed into `<NetworkGraph nodes={filteredNodes} .../>` at line 531). Correcting that earlier note.

**What's missing — the actual "make clusters visually obvious" part.** Below are concrete, drop-in code changes using **native Cytoscape.js compound nodes** (no new dependency required — this is the standard, production-proven approach used by Cytoscape Desktop, Gephi, and most graph-analysis tools for exactly this problem).

### 7.1 `NetworkGraph.tsx` — group nodes into compound "cluster" parents

Add a `showClusters` prop and build one invisible **parent node per community** (only for communities with 2+ members — singletons don't need a wrapper). Cytoscape.js natively supports this via the `parent` field on node data; the layout engine then treats each parent as a container and spaces containers apart from each other automatically.

```tsx
// NetworkGraph.tsx — add to Props interface
interface Props {
  nodes: NetworkNode[]; edges: NetworkEdge[];
  onNodeSelect?: (node: NetworkNode) => void;
  onNodeExpand?: (node: NetworkNode) => void;
  onNodeCompare?: (node: NetworkNode) => void;
  onEdgeSelect?: (sourceId: string, targetId: string, edgeData: any) => void;
  selectedNodeId?: string | null;
  highlightPath?: string[];
  crimeTypeLens?: string | null;
  showClusters?: boolean;          // NEW
}
```

```tsx
// NetworkGraph.tsx — replace buildElements() with a cluster-aware version.
// Only nodes/edges change; edges are untouched. Nodes get an optional `parent`
// pointing at a synthetic cluster container node, added only when the
// community has 2+ members (so isolated pairs/singles aren't wrapped).
const buildElements = (nodes: NetworkNode[], edges: NetworkEdge[], showClusters: boolean) => {
  const communityCounts: Record<number, number> = {};
  nodes.forEach((n) => {
    const c = n.community_id ?? 0;
    communityCounts[c] = (communityCounts[c] || 0) + 1;
  });

  // Only cluster communities with >=2 members; singletons render as normal free nodes.
  const clusterableCommunities = new Set(
    Object.entries(communityCounts).filter(([, count]) => count >= 2).map(([id]) => Number(id))
  );

  const clusterParents = showClusters
    ? Array.from(clusterableCommunities).map((cId) => ({
        data: {
          id: `cluster-${cId}`,
          label: `Cluster ${cId + 1} · ${communityCounts[cId]} members`,
          isCluster: true,
        },
      }))
    : [];

  const memberNodes = nodes.map((n) => {
    const cId = n.community_id ?? 0;
    const parent = showClusters && clusterableCommunities.has(cId) ? `cluster-${cId}` : undefined;
    return {
      data: {
        id: n.node_id,
        label: n.label,
        type: n.node_type,
        risk: n.risk_score,
        crimes: n.crime_count,
        betweenness: n.centrality?.betweenness || 0,
        community: cId,
        ...(parent ? { parent } : {}),
      },
    };
  });

  const edgeEls = edges
    .filter((e) => {
      const s = e.source || e.source_node_id || "";
      const t = e.target || e.target_node_id || "";
      return nodes.some((n) => n.node_id === s) && nodes.some((n) => n.node_id === t);
    })
    .map((e, i) => ({
      data: {
        id: e.edge_id || `e${i}_${e.source_node_id}_${e.target_node_id}`,
        source: e.source || e.source_node_id || "",
        target: e.target || e.target_node_id || "",
        label: e.relationship_type,
        strength: e.strength_score,
        crimeTypes: e.crime_types || [],
        confidence: e.confidence_level || "SUSPECTED",
      },
    }));

  return [...clusterParents, ...memberNodes, ...edgeEls];
};
```

Add matching styles for the cluster container (a soft translucent "bubble" with a label, in your existing dark theme):

```tsx
// NetworkGraph.tsx — add to styleSheet array
{
  selector: "node:parent",
  style: {
    "background-color": "#1e293b",
    "background-opacity": 0.35,
    "border-color": "#475569",
    "border-width": 1.5,
    "border-style": "dashed",
    "shape": "round-rectangle",
    "label": "data(label)",
    "color": "#94a3b8",
    "font-size": "11px",
    "font-weight": 600,
    "text-valign": "top",
    "text-halign": "center",
    "text-margin-y": -6,
    "padding": "28px",
  } as any,
},
```

Tune the layout so cluster containers repel each other more than individual nodes repel within a cluster (keeps each gang tight internally, but pushes separate gangs further apart):

```tsx
// NetworkGraph.tsx — inside getDynamicLayoutOptions(), add these fcose-specific options
return {
  name: "fcose",
  quality: isLarge ? "draft" : "default",
  animate: !isLarge,
  randomize: true,
  nodeDimensionsIncludeLabels: true,
  packComponents: true,
  nodeSeparation: Math.min(600, Math.round(160 * scale)),
  idealEdgeLength: Math.min(520, Math.round(220 * scale * densityFactor)),
  nodeRepulsion: Math.min(60000, Math.round(9000 * scale * scale)),
  edgeElasticity: 0.35,
  gravity: Math.max(0.02, 0.15 / scale),
  numIter: isLarge ? 1500 : 2500,
  tile: true,
  // NEW — pulls members of the same cluster tighter together, and (combined
  // with packComponents) leaves visible empty space between different clusters
  nestingFactor: 1.2,
  gravityRangeCompound: 1.5,
  gravityCompound: 1.0,
} as any;
```

Finally, thread `showClusters` through the two `buildElements(...)` call sites and the effect dependency array:

```tsx
// NetworkGraph.tsx — inside the main useEffect, both calls become:
elements: buildElements(nodes, edges, showClusters),
// ...
layout: getDynamicLayoutOptions(nodes.length, edges.length),
```
```tsx
// and the incremental-add branch:
cy.add(buildElements(newNodes, newEdges, showClusters));
```
```tsx
// and add showClusters to the effect's dependency array:
}, [nodes, edges, showClusters]);
```

### 7.2 `CriminalNetwork.tsx` — add the toggle button and pass the prop

Follow the exact same pattern already used for `showIsolated` (line 53, 445-452):

```tsx
// CriminalNetwork.tsx — add near the other view-state declarations (~line 53)
const [showClusters, setShowClusters] = useState(true); // default ON — this is the fix you asked for
```

```tsx
// CriminalNetwork.tsx — add a toggle button next to "Show/Hide Isolated" (~line 445-452)
<button
  onClick={() => setShowClusters(!showClusters)}
  className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
    showClusters ? "bg-purple-900/40 text-purple-400" : "bg-slate-800 text-slate-400 hover:text-white"
  }`}
>
  {showClusters ? "Clusters: On" : "Clusters: Off"}
</button>
```

```tsx
// CriminalNetwork.tsx — pass the new prop into the graph (~line 529-540)
<NetworkGraph
  ref={graphRef}
  nodes={filteredNodes}
  edges={edges}
  onNodeSelect={handleNodeSelect}
  onNodeCompare={handleNodeCompare}
  onNodeExpand={handleNodeExpand}
  onEdgeSelect={handleEdgeSelect}
  selectedNodeId={selectedNode?.node_id}
  highlightPath={highlightPath}
  crimeTypeLens={crimeTypeLens === "all" ? null : crimeTypeLens}
  showClusters={showClusters}   // NEW
/>
```

### 7.3 Optional but recommended — click-to-collapse clusters for very large graphs

For graphs near the 100-node cap (§4), even with clustering turned on there can be too much on screen at once. The standard next step (used by Cytoscape Desktop) is letting the user **collapse a whole cluster into a single summary node**, then expand it back on click. This needs one small, well-maintained extension:

```bash
npm install cytoscape-expand-collapse
```

```tsx
// NetworkGraph.tsx — register alongside fcose
import expandCollapse from "cytoscape-expand-collapse";
cytoscape.use(expandCollapse);

// after the cytoscape() instance is created:
const api = (cy as any).expandCollapse({
  layoutBy: () => cy.layout(getDynamicLayoutOptions(cy.nodes().length, cy.edges().length)).run(),
  fisheye: true,
  animate: true,
  undoable: false,
});

// collapse every cluster parent by default when there are many nodes,
// so the user sees clean cluster bubbles first and expands what they care about:
if (nodes.length > 60) {
  api.collapseAll();
}
```

### 7.4 Optional — better cluster labels from the backend

Right now a cluster would just be labeled "Cluster 3 · 14 members". If you want investigator-friendly labels ("Whitefield Robbery Ring · 14 members"), compute a dominant crime type / dominant district per community server-side and send it down instead of a bare index:

```python
# app/services/network_service.py — after detect_communities(...) is called,
# before returning the graph payload, add a small summary block:

def summarize_clusters(nodes: list, community_map: dict) -> dict:
    from collections import Counter
    groups: dict[int, list] = {}
    for n in nodes:
        cid = community_map.get(n["node_id"], 0)
        groups.setdefault(cid, []).append(n)

    summaries = {}
    for cid, members in groups.items():
        if len(members) < 2:
            continue
        crime_types = Counter(
            ct for m in members for ct in (m.get("preferred_crime_types") or [])
        )
        districts = Counter(m.get("district_id") for m in members if m.get("district_id"))
        summaries[cid] = {
            "size": len(members),
            "dominant_crime_type": crime_types.most_common(1)[0][0] if crime_types else None,
            "dominant_district": districts.most_common(1)[0][0] if districts else None,
        }
    return summaries

# then include it in the response:
# data["cluster_summary"] = summarize_clusters(formatted_nodes, communities)
```

```tsx
// NetworkGraph.tsx — use it instead of the generic label, if present on the node payload
label: `${clusterSummary?.[cId]?.dominant_crime_type || "Cluster"} · ${communityCounts[cId]} members`,
```

This is additive only — nothing above changes existing endpoints' contracts (new fields are optional/additive), so it's safe to ship incrementally: ship 7.1+7.2 first (pure frontend, uses data you already compute), then 7.3/7.4 as follow-ups.

---

## 8. Summary checklist (for your fix tracking)

- [ ] Add pagination (backend `page`/`page_size` + frontend controls) to: Alerts Center, Anomaly Detection, Offender Database, Victim Database, Hotspot Analysis, Settings Users, Settings Audit Logs, Reports history.
- [ ] Add `page`/`page_size`/`offset` support to `GET /api/victims/search` and `GET /api/alerts/active` (currently missing server-side entirely).
- [ ] Wrap all raw AI text in `AIMarkdown`: Offender Database's modus operandi (both the simple string case and the `Object.entries` breakdown), Criminal Network's `key_findings`/`recommended_actions`/`suspicious_pairs` list items.
- [ ] Delete or fix the casing of the dead `RISK_LEVELS`/`SEVERITY_LEVELS`/`STATUS_OPTIONS` exports in `constants/crimeTypes.ts` so they can't silently break filters if adopted later.
- [ ] Verify role/district scoping is applied to `GET /api/victims/search` the same way it is on crimes/alerts/network (currently unconfirmed/likely missing).
- [ ] Replace the sequential "mark all read" loop with a bulk endpoint or `Promise.all`.
- [ ] Move JWT out of `localStorage` (or at minimum keep it top of mind for XSS hardening) and out of the WebSocket URL query string.
- [ ] Remove/restrict public port mappings for Postgres/Neo4j/Redis in `docker-compose.yml` for production.
- [ ] Surface `node_limit`/graph truncation more clearly in Criminal Network (e.g., "Showing 100 of 340 nodes — narrow your filters").
- [ ] **[HIGH PRIORITY — §6]** Fix or delete the broken `sync_neo4j.py`; standardize on `scripts/sync_postgres_to_neo4j.py`, which correctly populates `district_id`/`crime_types` on Criminal & Victim nodes. Update `app/core/database.py:152-155` and `README.md:83` to point at the correct script.
- [ ] **[HIGH PRIORITY — §6]** Stop `update_offender()` from wiping `crime_types` to `[]` on every edit — fetch current crime types from `CrimeOffenderLink` before syncing to Neo4j instead of hardcoding an empty list.
- [ ] **[§6]** Decide whether neighbor/connected nodes should be constrained by the active district filter, and if so add the missing `connected.district_id = $district_id` condition in `get_network_graph()`'s inner `CALL` block.
- [ ] **[§6]** Run a full corrected re-sync (`python scripts/sync_postgres_to_neo4j.py`) against the current database once the sync script is fixed, since existing nodes may have permanently missing `district_id`/`crime_types` until re-synced.
- [ ] **[§6]** Make `run_neo4j_query()` fail loudly (re-raise or return an explicit error) for write/sync operations specifically, so a broken sync script can't silently look successful again in the future.
- [ ] Implement visual cluster separation in the Criminal Network graph (compound cluster nodes + styling + layout tuning) — see §7.1/7.2, pure frontend, no new dependency.
- [ ] (Optional follow-up) Add click-to-collapse for large clusters via `cytoscape-expand-collapse` — see §7.3.
- [ ] (Optional follow-up) Backend cluster summary (`dominant_crime_type`/`dominant_district` per community) for investigator-friendly cluster labels — see §7.4.