# SHASTRA — Full-Stack Audit Report
**Scope:** `crime_backend/MODULE_2_BACKEND` (FastAPI + PostgreSQL + Neo4j + Redis + Gemini) and `crime_frontend` (React + Vite + Redux + Cytoscape + Leaflet)
**Method:** Full read-through of every router, service, model, core module, and frontend page/service/store, cross-referenced against each other (frontend↔backend contract, backend↔DB schema, backend↔Neo4j, backend↔Redis, backend↔Gemini). Each issue below was traced to the exact file/line and confirmed by reading both sides of the connection — these are not guesses.

Severity key: 🔴 Critical (breaks a feature or a security boundary in production) · 🟠 High (silent data corruption / wrong results) · 🟡 Medium (works today, will break under normal variation) · ⚪ Low (code quality / consistency / cost)

---

## 1. 🔴 The `evidence` table is never created — the entire Evidence feature is dead in production

`init_db()` builds the schema by importing every model class and running `Base.metadata.create_all()`. The `Evidence` model is **not in that import list**, so `create_all()` never sees it and never creates the table.

```python
# app/core/database.py — init_db()
from app.models.database_models.user_model import User
from app.models.database_models.crime_model import District, PoliceStation, Crime, CrimeOffenderLink, CrimeVictimLink
from app.models.database_models.offender_model import Offender
from app.models.database_models.victim_model import Victim
from app.models.database_models.location_model import Hotspot, Location, SocioeconomicData
from app.models.database_models.prediction_model import Prediction
from app.models.database_models.alert_model import Alert
from app.models.database_models.anomaly_model import Anomaly
from app.models.database_models.report_model import Report
from app.models.database_models.system_settings_model import SystemSettings
# ❌ app.models.database_models.evidence_model.Evidence is never imported here
```

There **is** an Alembic migration for it (`migrations/versions/da5e74d0c8d1_add_evidence_model.py`), but nothing ever runs `alembic upgrade head`:

```dockerfile
# crime_backend/MODULE_2_BACKEND/Dockerfile
CMD ["python", "main.py"]   # ❌ no alembic upgrade step, no entrypoint script
```

```yaml
# docker-compose.yml — backend service
command: (none specified — uses Dockerfile CMD)
```

**Impact:** In a fresh production deployment (which is exactly how this app bootstraps — `create_all` + seed on first boot), the `evidence` table literally does not exist. Every call to `/api/evidence/*` (upload, list, download) will throw `asyncpg.exceptions.UndefinedTableError: relation "evidence" does not exist` → 500s. This affects the Evidence tab on the Crime Map case modal (`CrimeMapPage.tsx`) and `CrimeDatabase.tsx`.

**Where to fix:**
```python
# app/core/database.py
from app.models.database_models.evidence_model import Evidence   # add this import
```
And separately, decide on one schema strategy (see Issue #8) and add a migration-runner step to the Docker entrypoint, e.g.:
```dockerfile
CMD ["sh", "-c", "alembic upgrade head && python main.py"]
```

---

## 2. 🔴 District ID codes are hard-coded twice, and the two lists disagree from `KA-06` onward

The backend's canonical district list (used to seed the `districts` table and to store every `district_id` foreign key) is:

```python
# app/core/config.py
KARNATAKA_DISTRICTS = [
    {"district_id": "KA-01", "district_name": "Bangalore Urban", ...},
    {"district_id": "KA-02", "district_name": "Bangalore Rural", ...},
    {"district_id": "KA-03", "district_name": "Mysuru", ...},
    {"district_id": "KA-04", "district_name": "Tumakuru", ...},
    {"district_id": "KA-05", "district_name": "Kolar", ...},
    {"district_id": "KA-06", "district_name": "Mandya", ...},          # KA-06 = Mandya
    {"district_id": "KA-07", "district_name": "Hassan", ...},          # KA-07 = Hassan
    {"district_id": "KA-08", "district_name": "Dakshina Kannada", ...},
    ...
    {"district_id": "KA-26", "district_name": "Vijayanagara", ...},
    ... # 31 districts total
]
```

But the frontend has its **own, independently hand-typed** copy, used directly (not fetched from the API):

```typescript
// crime_frontend/src/constants/districtsList.ts
export const KARNATAKA_DISTRICTS_WITH_CODES = [
  { district_id: "KA-01", district_name: "Bangalore Urban" },   // ✅ matches
  { district_id: "KA-02", district_name: "Bangalore Rural" },   // ✅ matches
  { district_id: "KA-03", district_name: "Mysuru" },            // ✅ matches
  { district_id: "KA-04", district_name: "Tumakuru" },          // ✅ matches
  { district_id: "KA-05", district_name: "Kolar" },             // ✅ matches
  { district_id: "KA-06", district_name: "Chikkaballapur" },    // ❌ backend says KA-06 = Mandya
  { district_id: "KA-07", district_name: "Ramanagara" },        // ❌ backend says KA-07 = Hassan
  { district_id: "KA-08", district_name: "Mandya" },            // ❌ backend says KA-08 = Dakshina Kannada
  ...
  // only 30 entries total — "Vijayanagara" (backend's KA-26) is missing entirely
];
```

Every code from `KA-06` to `KA-30` points at a **different district** than the backend believes, and `Vijayanagara` doesn't exist in this list at all.

**Where this list is actually used** (both are real, live code paths, not dead code):

```tsx
// crime_frontend/src/pages/SettingsPage.tsx — "Add New User" form
<select value={newUser.district} onChange={(e) => setNewUser({ ...newUser, district: e.target.value })}>
  <option value="">State-Wide</option>
  {KARNATAKA_DISTRICTS_WITH_CODES.map((d) => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}
</select>
```

```typescript
// crime_frontend/src/utils/districtMap.ts — used by VictimDatabase.tsx to render a human-readable district name
const codeToNameMap: Record<string, string> = {};
KARNATAKA_DISTRICTS_WITH_CODES.forEach((d) => { codeToNameMap[d.district_id] = d.district_name; ... });
export function getDistrictName(districtIdOrName) { return codeToNameMap[districtIdOrName] || districtIdOrName; }
```

**Impact (real, not theoretical):**
- An admin creating a `DISTRICT_OFFICER` and picking "Chikkaballapur" in the dropdown actually assigns them `district_id = "KA-06"`. The backend's `resolve_district_id()` short-circuits on anything starting with `"KA-"` and stores it as-is (see next issue), so that officer is silently scoped to **Mandya's** data everywhere (`scope_district_param`, `scope_district_filter`), not Chikkaballapur's. This is a genuine access-control/data-integrity defect, not cosmetic.
- `VictimDatabase.tsx` mislabels the district for every victim whose district code is `KA-06`–`KA-31` (26 of the 31 districts), and shows nothing sensible for the missing `Vijayanagara`.

**Fix direction:** delete `KARNATAKA_DISTRICTS_WITH_CODES` and `districtMap.ts`'s static table entirely; both call sites should source districts from the already-existing `useDistricts()` hook (which correctly calls `GET /api/settings/districts` and gets the DB's real mapping).

---

## 3. 🔴 The Crime Database page's district filter is completely broken — it always returns zero rows when a district is selected

Two different endpoints back two different pages, and only one of them normalizes the district value.

`GET /api/crimes/map-data` (used by the Map page) resolves names → codes:
```python
# app/routers/crimes_router.py — get_map_data()
resolved_district = await resolve_district_id(db, district_id)
...
if resolved_district and resolved_district != "All Districts":
    q = q.where(Crime.district_id == resolved_district)
```

`GET /api/crimes/filter` (used by the Crime Database page) does **not**:
```python
# app/routers/crimes_router.py — filter_crimes()
def apply_filter_conditions(q):
    q = scope_district_filter(q, current_user, Crime.district_id)
    if district_id:
        q = q.where(Crime.district_id == district_id)   # ❌ raw equality, no resolve_district_id() call
    ...
```

And the Crime Database page's dropdown sends a **district name**, not a code:
```tsx
// crime_frontend/src/pages/CrimeDatabase.tsx
if (district !== "All") params.district_id = district;
...
{districts.map(d => <option key={d.district_id} value={d.district_name}>{d.district_name}</option>)}
                                        // ^^^^^^^^^^^^^^^^ value is the NAME, e.g. "Mysuru"
```

`crimes.district_id` in Postgres stores codes (`"KA-03"`), never names. So `WHERE district_id = 'Mysuru'` matches nothing, ever.

**Reproduction:** Open Crime Database → pick any specific district (anything other than "All") → the table silently goes empty, with no error shown to the user.

**Fix direction:** add the same `resolve_district_id(db, district_id)` call to `filter_crimes()` that `get_map_data()` already has, for consistency — or standardize every filter dropdown app-wide to send `district_id` (the code) instead of mixing name/code across pages (see Issue #10).

---

## 4. 🟠 `resolve_district_id()` will throw a 500 on any ambiguous partial match

```python
# app/utils/district_resolver.py
stmt = select(District.district_id).where(
    or_(
        District.district_name.ilike(district_val.strip()),
        District.district_name.ilike(search_name),
        District.district_name.ilike(f"%{district_val.strip()}%"),   # ⚠️ substring match
    )
)
result = await db.execute(stmt)
resolved = result.scalar_one_or_none()   # ❌ raises MultipleResultsFound if >1 row matches
```

`scalar_one_or_none()` raises `sqlalchemy.exc.MultipleResultsFound` (not a graceful `None`) if more than one row satisfies the `WHERE`. The third clause is a raw substring (`%value%`) against `district_name`, so any caller that passes a partial token — e.g. `"Bangalore"` (would match both *Bangalore Urban* and *Bangalore Rural*), or `"Kannada"` (matches *Dakshina Kannada* and *Uttara Kannada*) — will hit this and produce an unhandled exception that turns into a raw 500 for the whole request (dashboard, map data, network graph, or crime creation, since this helper is called from all of them).

This isn't purely theoretical: the global search box, any future free-text district field, or a client passing a partial string from `search_query`-style UI, will trigger it.

**Fix direction:** use `.first()` instead of `.scalar_one_or_none()`, or make the substring clause require an exact word-boundary match, or drop the substring clause and rely only on the two exact-match clauses.

---

## 5. 🟠 Real-time alert payload contract mismatch — two different broadcast shapes, only one of which the frontend understands

The frontend WebSocket handler only reads `msg.data`:
```tsx
// crime_frontend/src/App.tsx
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "NEW_ALERT") {
    dispatch(addAlert(msg.data));     // only reads `data`
    addToast(msg.data);
  }
};
```

But the backend has two call sites that build the broadcast payload differently:
```python
# app/services/alert_service.py — create_alert()
await manager.broadcast({
    "type": "NEW_ALERT",
    "alert": alert.to_dict()          # ❌ key is "alert", not "data"
})
```
```python
# app/services/alert_service.py — detect_and_generate_alerts()
await manager.broadcast({"type": "NEW_ALERT", "data": alert.to_dict()})   # ✅ this one matches the frontend
```

**Impact:** Whenever `create_alert()` is the code path that fires (e.g. any manual/one-off alert creation, as opposed to the scheduled crime-spike scan), the frontend receives `msg.data === undefined` and does:
```ts
addAlert: (state, action) => {
  state.alerts = [action.payload, ...state.alerts];   // pushes `undefined` into the array
  state.unreadCount += 1;                              // count goes up with no real alert
}
```
Any component that renders `alerts[0].title`, `.severity`, `.is_read`, etc. (Sidebar badge, `AlertsTable.tsx`, the toast itself) will throw `Cannot read properties of undefined` on the very next render, and the toast shown to the officer will have a blank title/description.

**Fix direction:** standardize both broadcast call sites on one key (`"data"`, to match what the frontend already expects), e.g.:
```python
await manager.broadcast({"type": "NEW_ALERT", "data": alert.to_dict()})
```

---

## 6. 🟠 The AI Assistant leaks state-wide data to District Officers, bypassing the district-scoping used everywhere else

Every other dashboard endpoint explicitly re-scopes `district_id` for a `DISTRICT_OFFICER`:
```python
# app/routers/dashboard_router.py
if current_user["role"] == "DISTRICT_OFFICER":
    district_id = current_user.get("district_id")
resolved_id = await resolve_district_id(db, district_id)
data = await get_dashboard_summary(db, resolved_id)
```

But the AI chat endpoint calls the same underlying service **with no district argument at all**:
```python
# app/routers/assistant_router.py
@router.post("/ask")
async def ask_assistant(request, question: str = Body(..., embed=True), db=Depends(get_db), current_user=Depends(get_current_user)):
    summary_data = await get_dashboard_summary(db)   # ❌ no district_id passed — always state-wide
    context = (
        f"Karnataka state crime records: "
        f"Total crimes this month: {summary_data.get('total_crimes_month')} ..."
    )
    ...
```

**Impact:** A `DISTRICT_OFFICER` who is restricted to their own district everywhere else in the app can simply open the AI chat widget and ask "what are the current crime stats?" to get **state-wide** numbers (total crimes, most-affected district, high-risk area counts) they aren't supposed to see through any other path in the product. This is a genuine access-control gap, not just an inconsistency.

**Fix direction:**
```python
resolved_id = current_user.get("district_id") if current_user["role"] == "DISTRICT_OFFICER" else None
summary_data = await get_dashboard_summary(db, resolved_id)
```

---

## 7. 🟡 Mixed schema-management strategy — `create_all()` + a single orphan Alembic migration

```python
# app/core/database.py — init_db()
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)   # creates tables straight from ORM models
```
```
migrations/versions/da5e74d0c8d1_add_evidence_model.py   # the only migration; down_revision = None
```

This project effectively has two competing sources of truth for the schema: (1) whatever the current `models/database_models/*.py` files say, auto-applied via `create_all()` at every boot, and (2) a single Alembic revision that is never actually invoked by anything in the deployment (Issue #1). `create_all()` cannot alter existing tables (add/drop/rename columns) — it only creates tables that don't exist yet — so **any future schema change to an existing model will silently do nothing in a running production database**, and there is no migration history to fall back on to apply it manually.

**Fix direction:** pick one strategy. Given Alembic is already wired up (`alembic.ini`, `migrations/env.py`), the production-grade path is: stop calling `create_all()` in `init_db()`, generate a full baseline Alembic revision from the current models, and run `alembic upgrade head` as a startup/entrypoint step (Kubernetes init container, Docker `CMD`, or CI/CD release step) instead of relying on app-boot side effects.

---

## 8. 🟡 `passlib` is an unused, undocumented dependency; `bcrypt` itself is not directly version-pinned

```txt
# requirements.txt
passlib[bcrypt]==1.7.4
```
```python
# app/core/security.py
import bcrypt   # imports the bare `bcrypt` package directly, NOT passlib
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
```

`passlib` is never imported anywhere in `app/`. It's dead weight in the image, and — more importantly — the actual `bcrypt` version your password hashing depends on is only pinned *transitively* (whatever `passlib[bcrypt]==1.7.4` happens to resolve to on a given `pip install`), not with its own `bcrypt==x.y.z` line. `passlib` 1.7.4 is also known to emit a noisy/incorrect "error reading bcrypt version" warning against `bcrypt>=4.1`, which is a signal the two were never actually wired together here.

**Fix direction:** remove `passlib[bcrypt]` from `requirements.txt`, add an explicit `bcrypt==<pinned version>` line instead.

---

## 9. 🟡 The Criminal Network AI panel's "key findings" and "recommended actions" are static templates, not model output — but the UI badges them as "Gemini"

Only `summary_text` in the Network AI Summary actually comes from Gemini:
```python
# app/services/network_service.py — get_network_ai_summary()
summary_text = await get_network_analysis_summary(all_offenders[:20], suspicious_pairs, network_stats, focus_area)

key_findings = [
    f"Identified {network_stats['total_criminals']} repeat offenders in the network",
    f"{network_stats['high_risk_count']} individuals classified as HIGH risk",
    f"{network_stats['active_count']} offenders currently active",
    f"Detected {len(suspicious_pairs)} suspicious associations",
    "Network analysis reveals organized crime patterns requiring investigation",   # ← always the same sentence, regardless of data
]

recommended_actions = [
    "Prioritize surveillance of HIGH risk individuals",
    "Investigate identified suspicious pairs for coordinated activity",
    "Coordinate inter-district intelligence sharing",
    "Deploy undercover assets in identified criminal network areas",
    "Issue lookout notices for absconding network members",
]   # ← identical hard-coded list returned for every district/crime-type combination
```

But the frontend renders this right under an explicit "Gemini" badge:
```tsx
// crime_frontend/src/pages/CriminalNetwork.tsx
<h3 className="text-sm font-semibold text-white">AI Network Analysis</h3>
<span className="text-xs bg-blue-900/40 text-blue-400 px-1.5 py-0.5 rounded-full">Gemini</span>
```

This isn't a functional bug, but it is a correctness/trust issue for a law-enforcement analytics product: the "Recommended Actions" list is identical no matter what district, crime type, or actual offenders are being viewed — officers may reasonably assume every bullet under a "Gemini" badge is generated from their current data, when 2 of the 3 sections are fixed boilerplate.

**Fix direction:** either fold `key_findings`/`recommended_actions` into the actual Gemini prompt/response (so they vary with the data), or relabel the static sections so they aren't presented as AI output.

---

## 10. ⚪ Inconsistent filter contract: some pages send a district *code*, others send a district *name*

- `CriminalNetwork.tsx` → sends `d.district_id` (code, e.g. `KA-03`)
- `CrimeMapPage.tsx` / `MapControls.tsx` → sends `d.district_name` (name, e.g. `Mysuru`)
- `CrimeDatabase.tsx` → sends `d.district_name` (name) — but hits an endpoint that requires the code (Issue #3)

```tsx
// components/network/... (CriminalNetwork.tsx) — sends the CODE
{districts.map((d) => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}

// components/maps/MapControls.tsx — sends the NAME
{districts.map((d) => <option key={d.district_id} value={d.district_name}>{d.district_name}</option>)}
```

Both happen to "work" only because `resolve_district_id()` is defensively called on the *some* of the receiving endpoints (and happens to not crash for full, unambiguous names — see Issue #4 for when it doesn't). This is fragile: any new page copy-pasted from the wrong sibling will silently pick the wrong convention. Standardize on always sending `district_id` (the code) from every dropdown, since that's what's actually stored in the database and requires no server-side name resolution at all.

---

## 11. ⚪ `get_network_graph()` `source_id` closure risk (Neo4j path)

```python
# app/core/neo4j_connection.py — get_network_graph()
for record in results:
    if record.get("n"):
        node = record["n"]
        ...
        node_id = normalized["node_id"]
        if node_id not in nodes_map:
            nodes_map[node_id] = normalized

    if record.get("type_r") and record.get("connected"):
        rel = record.get("r_props") or {}
        connected = record["connected"]
        source_id = node_id   # ⚠️ reads whatever `node_id` was set to in a PREVIOUS iteration if this row has no "n"
        ...
```

Every row returned by the Cypher query does carry `n` alongside `connected` in this particular query shape, so this doesn't currently misfire — but the code silently depends on that invariant holding for every future edit to the query. If the query is ever changed to `UNWIND` or `OPTIONAL MATCH` in a way that produces a row with `connected`/`type_r` but no `n`, this will attach edges to the *previous* row's node instead of raising an error. Recommend making `source_id` explicit per-row (derive it from the row's own `n`, or skip the row if `n` is absent) rather than relying on a stale closure variable.

---

## 12. ⚪ `OffenderDatabase.tsx` lets officers type a raw district ID by hand, unvalidated

```tsx
// crime_frontend/src/pages/OffenderDatabase.tsx — "Add Offender" form
<input
  type="text"
  placeholder="District ID (e.g. KA-01)"
  value={newOffender.district_id}
  onChange={(e) => setNewOffender({ ...newOffender, district_id: e.target.value })}
/>
```
Every other entity-creation form in the app (Add User in Settings, filters everywhere) uses a `<select>` sourced from `useDistricts()`. This is the one free-text field, so a typo (`KA-1` instead of `KA-01`, trailing space, wrong case) creates an offender whose `district_id` foreign key doesn't match any row in `districts`, silently breaking that offender's district-scoped visibility for `DISTRICT_OFFICER` accounts. Swap this for the same `<select>` pattern used elsewhere.

---

## Summary Table

| # | Area | Severity | File(s) | Symptom |
|---|------|----------|---------|---------|
| 1 | DB schema | 🔴 Critical | `core/database.py`, `Dockerfile` | Evidence upload/list/download always 500s in prod |
| 2 | District codes | 🔴 Critical | `districtsList.ts`, `SettingsPage.tsx`, `districtMap.ts` | Officers assigned to wrong district; wrong labels shown |
| 3 | Crime filter | 🔴 Critical | `crimes_router.py`, `CrimeDatabase.tsx` | District filter on Crime Database always returns 0 rows |
| 4 | District resolver | 🟠 High | `district_resolver.py` | 500 error (`MultipleResultsFound`) on ambiguous district text |
| 5 | WebSocket alerts | 🟠 High | `alert_service.py`, `App.tsx` | Real-time alert toast/badge crashes or shows blank alert |
| 6 | AI Assistant scoping | 🟠 High | `assistant_router.py` | District Officers see state-wide stats via chat |
| 7 | Schema strategy | 🟡 Medium | `core/database.py`, `migrations/` | Future column changes silently don't apply in prod |
| 8 | Dependencies | 🟡 Medium | `requirements.txt`, `security.py` | Unpinned bcrypt version; dead `passlib` dependency |
| 9 | AI labeling | 🟡 Medium | `network_service.py`, `CriminalNetwork.tsx` | Static text presented as live "Gemini" output |
| 10 | Filter contract | ⚪ Low | `CriminalNetwork.tsx`, `MapControls.tsx`, `CrimeDatabase.tsx` | Some pages send code, others send name |
| 11 | Neo4j query mapping | ⚪ Low | `neo4j_connection.py` | Latent stale-closure risk in graph builder |
| 12 | Data entry | ⚪ Low | `OffenderDatabase.tsx` | Free-text district field, no validation |

---

## What was checked and found wired correctly (for context)
- `/api/network/*` REST contract between `networkService.ts` ↔ `network_router.py` ↔ `network_service.py`: paths, params, and response shapes match.
- `NetworkGraph.tsx` (Cytoscape) edge/node data keys (`label`, `strength`, `crimeTypes`, `confidence`) are correctly consumed by `CriminalNetwork.tsx`'s edge-detail panel — no mismatch there.
- WebSocket transport itself: `alerts_router.py`'s `/api/alerts/ws` ↔ `App.tsx`'s reconnect-with-backoff client is correctly implemented end-to-end (auth via token query param, blacklist check, reconnect logic) — only the *payload shape* has the bug in #5, not the connection.
- `nginx.conf` correctly proxies both HTTP and the WebSocket upgrade under `/api/`.
- `docker-compose.yml` healthchecks and `depends_on: condition: service_healthy` are correctly set for Postgres/Redis/Neo4j before the backend starts.
- CORS + security headers middleware in `main.py` correctly reflects the request origin for credentialed requests rather than using a wildcard.
- `GET /api/settings/districts` correctly returns the canonical 31-district list from the database (the bug is only in the frontend's separately hard-coded copy, Issue #2).

## Note on scope
This audit covers the wiring, data contracts, and cross-system connections you asked about in depth (network graph, district filters, crime features, AI integration, DB/Neo4j/Redis connections). It is not a line-by-line security penetration test or a full type-check/lint run of all ~160 files — for a production sign-off, I'd also recommend running `mypy`/`tsc --noEmit` across both codebases and a dependency vulnerability scan (`pip-audit`, `npm audit`) as a mechanical follow-up alongside fixing the issues above.