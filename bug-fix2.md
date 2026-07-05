# SHASTRA Platform — Audit Part 2: Deeper Pass, Dummy/Unwired Features & Cross-File Consistency Bugs

This is a follow-up to `SHASTRA_Audit_and_Fixes.md`. That document covered Docker/Nginx/CORS connectivity and the two broken Criminal Network interactions (expand-node, shortest-path). This pass goes wider: every page was re-read end-to-end, cross-referenced against its exact backend route/service, specifically hunting for (a) features that are visually present but not actually wired to anything, and (b) places where two files that must agree on a value (a field name, a status string, a query-param name) have quietly drifted apart. Nothing in your project was modified.

**New severity ranking used below:**
- 🔴 **Critical** — feature silently does nothing, or corrupts/hides data, with no error shown
- 🟠 **High** — feature returns wrong/empty results, or a whole page can crash
- 🟡 **Medium** — cosmetic-only or narrow-impact
- ⚪ **Info** — dead code / orphaned backend capability, no user-facing symptom yet

---

## 1. 🔴 No root-level Error Boundary — several of the bugs below crash the *entire app*, not just one widget

`crime_frontend/src/main.tsx`:
```tsx
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <App />
    </Provider>
  </StrictMode>
);
```
There is no `ErrorBoundary` anywhere in the codebase (confirmed by grep — zero matches for `ErrorBoundary`, `componentDidCatch`, or `getDerivedStateFromError`). In React, an uncaught render-time exception in *any* component unmounts the **entire** tree back to the nearest boundary — since there is none, it unmounts back to `main.tsx`, producing a **blank white screen** for the whole app, not just the page the user was on. This turns several "data is silently empty" bugs below (marked 💥) into full white-screen crashes instead.

**Fix — wrap the app in a boundary (5-minute fix, prevents dozens of possible future white-screens):**
```tsx
// crime_frontend/src/components/common/ErrorBoundary.tsx
import React from "react";

interface State { hasError: boolean; error?: Error }

export default class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Unhandled UI error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-900 text-slate-300 gap-4">
          <p className="text-lg font-semibold text-white">Something went wrong loading this view.</p>
          <p className="text-sm text-slate-500 max-w-md text-center">{this.state.error?.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```
```tsx
// main.tsx
import ErrorBoundary from "./components/common/ErrorBoundary";
...
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <Provider store={store}>
        <App />
      </Provider>
    </ErrorBoundary>
  </StrictMode>
);
```

---

## 2. 🔴 AI Assistant chat widget (floating button, every page) never shows Gemini's actual answer 💥-adjacent

`crime_frontend/src/components/common/AIChatWidget.tsx`:
```ts
const res = await api.post('/assistant/ask', { question: userMsg.text });
const answer = res.data?.data?.answer || 'Sorry, no response available.';
const isFallback = res.data?.data?.is_fallback || false;
```
Backend (`assistant_router.py`):
```python
return {"success": True, "data": {"answer": answer, "is_fallback": is_fallback}}
```
Same double-unwrap bug family identified in Part 1 (§3.2/§3.3 there) — `api` already unwraps `{success, data}` once via the shared Axios interceptor, so `res.data` here is already `{answer, is_fallback}`. `res.data?.data?.answer` is `undefined` on every single request. **The AI Assistant, present as a floating button on every screen in the app, always displays "Sorry, no response available." regardless of what Gemini actually returned** — it has never worked, in any environment, even with a perfectly configured Gemini API key.

**Fix:**
```ts
const res = await api.post('/assistant/ask', { question: userMsg.text });
const answer = res.data?.answer || 'Sorry, no response available.';
const isFallback = res.data?.is_fallback || false;
```

---

## 3. 🔴 Settings → Import Data never shows success/failure results, even when the import worked 💥

`crime_frontend/src/components/settings/DataImport.tsx`:
```ts
const response = await api.post('/import/bulk', formData, { headers: {...} });
setResult(response.data.data);   // BUG
```
Backend `import_router.py`: `return {"success": True, "data": result}`. Same bug — `response.data` is already `result` (`{total, successful, failed, errors}`), so `response.data.data` is `undefined`. `setResult(undefined)` → the `{result && (...)}` block never renders → **the user gets zero feedback after a bulk import**, success or failure. They just see the button return to its idle state with no indication of whether 500 records imported or 0 did. (No crash here specifically, since the block is gated on truthiness, but it is a totally broken UX for a data-entry-critical operation.)

**Fix:**
```ts
setResult(response.data);
```

---

## 4. 🔴 Socio-Economic Insights page is permanently empty (NaN metrics) 💥-risk

`crime_frontend/src/pages/SocioEconomicInsights.tsx`:
```ts
api.get("/predictions/socioeconomic-correlation")
  .then((res) => {
    setData(res.data.data);   // BUG — same pattern again
    ...
```
Backend: `return {"success": True, "data": data}` where `data = {correlations, overlay_data, ai_analysis}`. Post-interceptor, `res.data` is already that object; `res.data.data` is `undefined`. Effects:
- `correlations = []`, `overlayData = []`, `narrative = "No narrative available."` — always, regardless of what the ML/AI service actually computed.
- `chartData` ends up `[]`, and `"Avg Crime Rate"` is computed as `chartData.reduce(...) / chartData.length` → **`0 / 0 = NaN`**, so the dashboard literally displays **"NaN"** as a headline metric.
- The two scatter charts (Urbanization vs Crime Rate, Unemployment vs Property Crimes) render with **empty datasets** — visually just empty axes with no points, easily mistaken for "no data collected yet" rather than "this page has a bug."

**Fix:**
```ts
api.get("/predictions/socioeconomic-correlation")
  .then((res) => {
    setData(res.data);
    setLoading(false);
  })
```

---

## 5. 🔴 New "District Officer" user accounts are silently locked out of all their own data (RBAC/multi-tenancy is broken by a dropdown)

This is the most severe *data-correctness* bug found in this pass, because it fails silently and only shows up after the fact, for a specific role.

`crime_frontend/src/pages/SettingsPage.tsx` — the "Add New User" form:
```tsx
<select value={newUser.district} onChange={(e) => setNewUser({ ...newUser, district: e.target.value })} className={inputCls}>
  <option value="">State-Wide</option>
  {KARNATAKA_DISTRICTS.map((d) => <option key={d} value={d}>{d}</option>)}
</select>
```
`crime_frontend/src/constants/districtsList.ts`:
```ts
export const KARNATAKA_DISTRICTS = [
  "All Districts",
  "Bagalkot",
  "Ballari",
  ...  // plain human-readable names, e.g. "Mysuru"
];
```
`handleAddUser`:
```ts
const payload = {
  ...newUser,
  district_id: newUser.district || undefined   // e.g. district_id: "Mysuru"
};
const result = await settingsService.addUser(payload as any);
```
This hits `POST /settings/users/add` → `create_user(...)` in `auth_service.py`:
```python
"district_id": user_data.get("district_id"),   # stored verbatim, no lookup/resolution
```
So a brand-new `DISTRICT_OFFICER` account gets `district_id = "Mysuru"` (a **name**) persisted directly into the `users` table. But every place in the backend that *scopes* a district officer's access compares against the **real district code** format (`"KA-03"`, etc.) — e.g.:

`app/core/security.py`:
```python
def scope_district_param(requested_district, user):
    if user["role"] == "DISTRICT_OFFICER":
        user_district = user.get("district_id")           # "Mysuru"
        if requested_district and requested_district != user_district:
            raise HTTPException(403, "...")
        return user_district                                # returned as the filter value
    return requested_district
```
When this mismatched `"Mysuru"` string is later used as `district_id == "Mysuru"` in a SQLAlchemy `WHERE` clause against real `Crime.district_id`/`Offender.district_id` values (which are always `"KA-XX"` codes — see `crimes_router.py`, `network_router.py`, `hotspots_router.py`, `dashboard_router.py`), **it will never match a single row**. The net effect: **every District Officer account created through the Settings UI sees zero crimes, zero offenders, zero hotspots, and gets 403s on cross-district requests forever**, with no error message explaining why — it just looks like "the system has no data for my district."

This has been silently broken since day one for this role, because the seed data (created directly in the DB by `data_seeder.py`, not through this UI) presumably uses correct codes — so it's easy to test the app end-to-end with seed users and never notice this bug, since it only manifests for accounts created via this specific form.

**Fix — resolve the district name to its code before sending, exactly like `district_resolver.py` already does server-side for other flows.** Two options:

**Option A (frontend fix — quick):** Change the dropdown to submit `district_id` codes directly instead of names, by switching to a `{code, name}` pairing:
```tsx
// districtsList.ts — add alongside the existing name-only list
export const KARNATAKA_DISTRICTS_WITH_CODES = [
  { district_id: "KA-01", district_name: "Bangalore Urban" },
  { district_id: "KA-02", district_name: "Bangalore Rural" },
  { district_id: "KA-03", district_name: "Mysuru" },
  // ... (full list is already defined server-side in config.py — mirror it here)
];
```
```tsx
// SettingsPage.tsx
<select value={newUser.district} onChange={(e) => setNewUser({ ...newUser, district: e.target.value })} className={inputCls}>
  <option value="">State-Wide</option>
  {KARNATAKA_DISTRICTS_WITH_CODES.map((d) => (
    <option key={d.district_id} value={d.district_id}>{d.district_name}</option>
  ))}
</select>
```

**Option B (backend fix — more robust, fixes it for *every* caller, not just this form):** Resolve district in `create_user` itself, the same way `crimes_router.py`'s `log_crime` already does:
```python
# auth_service.py — inside create_user (or settings_router.py add_user handler, before calling create_user)
from app.utils.district_resolver import resolve_district_id

async def create_user(db, user_data: dict):
    if user_data.get("district_id"):
        user_data["district_id"] = await resolve_district_id(db, user_data["district_id"])
    ...
```
Recommend doing **both**: Option B closes the hole for any future caller (API clients, scripts), Option A keeps the dropdown UX consistent with the rest of the app. Also recommend adding a quick regression test: create a `DISTRICT_OFFICER` via the real HTTP endpoint (not seeded directly), then assert they can see at least the district's own seeded data.

---

## 6. 🟠 Hotspot Analysis page — district filter is a no-op (wrong query-param name)

`crime_frontend/src/pages/HotspotAnalysis.tsx`:
```ts
const params: any = {};
if (district !== "All Districts") params.district = district;   // <-- wrong key
if (crimeType !== "All") params.crime_type = crimeType;
...
const [h, p, d] = await Promise.all([
  crimeService.getHotspotClusters(params),
  crimeService.getTimePatterns(params),
  crimeService.getDeploymentSuggestions(params),
]);
```
Every one of the four hotspot endpoints on the backend declares the parameter as `district_id`, not `district`:

`hotspots_router.py`:
```python
@router.get("/clusters")
async def hotspot_clusters(request, district_id: Optional[str] = Query(None), ...): ...

@router.get("/time-patterns")
async def time_patterns(request, ..., district_id: Optional[str] = Query(None), ...): ...

@router.get("/top-list")
async def top_list(request, ..., district_id: Optional[str] = Query(None), ...): ...

@router.get("/deployment-suggestions")
async def deployment_suggestions(request, district_id: Optional[str] = Query(None), ...): ...
```
FastAPI silently ignores query parameters it doesn't declare — so `?district=Mysuru&crime_type=Theft` is received, `crime_type` is honored, and `district` is dropped on the floor. **Picking any district in the Hotspot Analysis filter bar has zero effect** — the hotspot map, time-pattern charts, and deployment suggestions always reflect the *entire state*, no matter what district is selected. Contrast this with `handleExport` a few lines below in the same file, which correctly uses `district_id`:
```ts
const handleExport = async () => {
  const queryParams = new URLSearchParams({ file_format: "csv" });
  if (district !== "All Districts") queryParams.append("district_id", district);   // correct key here
  ...
```
— confirming this is an inconsistency/typo rather than an intentional design choice.

**Fix:**
```ts
const fetch = async (silent = false) => {
  if (!silent) setLoading(true);
  const params: any = {};
  if (district !== "All Districts") params.district_id = district;   // fixed key
  if (crimeType !== "All") params.crime_type = crimeType;
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;
  ...
```
Note: this still passes a **district name** (`"Mysuru"`), not a code — but unlike the report/user bugs above, `hotspots_router.py` correctly calls `resolve_district_id(db, district_id)` right after receiving it, so names *are* resolved here. Only the param **name** is wrong; once it's renamed to `district_id`, the existing name-resolution logic on the backend will handle it correctly.

---

## 7. 🟠 District-scoped Report generation silently produces empty/wrong reports

`crime_frontend/src/pages/ReportsPage.tsx`:
```ts
const params: Record<string, string> = { report_type: reportType };
if (district !== "All Districts") params.district_id = district;   // e.g. "Mysuru" (a name)
const result = await reportService.generateReport(params);
```
This time the **param name** is correct (`district_id`), but `reports_router.py`'s `generate_report_endpoint` passes it straight into `report_service.generate_report(...)` **without** calling `resolve_district_id` first (confirmed — `reports_router.py` does not import `district_resolver` at all, unlike `crimes_router.py`, `dashboard_router.py`, `hotspots_router.py`, and `network_router.py`, which all do). Inside `report_service.py`:
```python
if district_id:
    conditions.append(Crime.district_id == district_id)   # "Mysuru" == "KA-03" → never true
```
So **every district-scoped report (anything other than "All Districts (State Wide)")** silently generates a report with zero matching crimes/offenders/hotspots — it "succeeds" (HTTP 200, a report record is created and downloadable), but its contents are empty for that district, which could easily be mistaken for "this district genuinely has no incidents" by an officer relying on it.

**Fix (backend, `reports_router.py`):**
```python
from app.utils.district_resolver import resolve_district_id

@router.post("/generate")
@limiter.limit("5/minute")
async def generate_report_endpoint(
    request: Request,
    report_type: str = Query(...),
    report_name: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "INVESTIGATOR", "DISTRICT_OFFICER"]))
):
    from datetime import datetime
    resolved_district_id = await resolve_district_id(db, district_id)
    name = report_name or f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M')}"
    data = await generate_report(
        db, report_type, name,
        date_from=date_from, date_to=date_to,
        district_id=resolved_district_id, user_id=current_user["user_id"],
    )
    return {"success": True, "data": data}
```

---

## 8. 🟠 Anomaly Detection — status & severity vocabularies don't match between frontend and backend

Backend canonical values (`config.py`):
```python
SEVERITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
ANOMALY_STATUS_VALUES = ["NEW", "UNDER_REVIEW", "RESOLVED", "FALSE_POSITIVE"]
```
Frontend (`AnomalyDetection.tsx`) uses a completely different, human-friendly vocabulary for both:
```tsx
const severityColors: Record<string, string> = {
  Critical: "...", High: "...", Medium: "...", Low: "...",   // Title Case, not UPPER_CASE
};
...
{["All", "Active", "Investigating", "Resolved"].map((s) => (   // doesn't match NEW/UNDER_REVIEW/RESOLVED/FALSE_POSITIVE at all
  <button key={s} onClick={() => setStatusFilter(s)}>{s}</button>
))}
...
const filtered = statusFilter === "All" ? safeAnomalies : safeAnomalies.filter((a) => a.status === statusFilter);
```
Consequences:
1. **Severity summary cards always read 0/0/0/0.** `a.severity === sev` compares the real value (`"CRITICAL"`) against the UI's Title-Case key (`"Critical"`) — never equal.
2. **Severity badge coloring is always the default gray**, because `severityColors[a.severity]` looks up `severityColors["CRITICAL"]`, which doesn't exist in a dict keyed `Critical/High/Medium/Low` — falls through silently to `undefined` in the className.
3. **The status filter buttons ("Active", "Investigating", "Resolved") always return an empty list** — no anomaly's real `status` (`"NEW"`, `"UNDER_REVIEW"`, `"RESOLVED"`, `"FALSE_POSITIVE"`) will ever equal any of those three strings. Only "All" ever shows anything.
4. **Clicking "Investigate"/"Resolve" writes an invalid status back to the database.** `handleUpdateStatus` sends the UI label directly:
   ```tsx
   onClick={() => handleUpdateStatus(a.anomaly_id, a.status === "Active" ? "Investigating" : "Resolved")}
   ```
   → `PATCH /anomalies/update-status/{id}` → `anomaly_service.update_anomaly_status(...)`:
   ```python
   update_values = {"status": new_status}          # stores "Investigating" / "Resolved" verbatim — not in ANOMALY_STATUS_VALUES
   if new_status == "RESOLVED" or new_status == "FALSE_POSITIVE":
       ...                                          # this branch (e.g. setting a resolved_at timestamp) never fires,
                                                     # because it receives "Resolved" (Title Case), not "RESOLVED"
   ```
   This **permanently corrupts** that anomaly's `status` field with a non-canonical value that no other part of the system (filters, dashboards, the `ANOMALY_STATUS_VALUES` constant itself) recognizes going forward, and skips whatever bookkeeping was meant to happen on resolution.

**Fix — normalize on the frontend to the real backend vocabulary (recommended, since the backend enum is the canonical source of truth used elsewhere in the system):**
```tsx
const severityColors: Record<string, string> = {
  CRITICAL: "bg-red-900/30 border-red-500/40 text-red-400",
  HIGH: "bg-orange-900/30 border-orange-500/40 text-orange-400",
  MEDIUM: "bg-yellow-900/30 border-yellow-500/40 text-yellow-400",
  LOW: "bg-blue-900/30 border-blue-500/40 text-blue-400",
};

const STATUS_FILTERS = ["All", "NEW", "UNDER_REVIEW", "RESOLVED", "FALSE_POSITIVE"];
const STATUS_LABELS: Record<string, string> = {
  NEW: "New", UNDER_REVIEW: "Investigating", RESOLVED: "Resolved", FALSE_POSITIVE: "False Positive",
};

// in the filter bar:
{STATUS_FILTERS.map((s) => (
  <button key={s} onClick={() => setStatusFilter(s)}>{s === "All" ? "All" : STATUS_LABELS[s]}</button>
))}

// summary cards:
{["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((sev) => {
  const count = safeAnomalies.filter((a) => a.severity === sev).length;
  return (/* ...same markup, use STATUS_LABELS-style title-casing only for display text, not for comparisons... */);
})}

// update handler — send real enum values:
onClick={() => handleUpdateStatus(a.anomaly_id, a.status === "NEW" ? "UNDER_REVIEW" : "RESOLVED")}
```
And display `STATUS_LABELS[a.status] || a.status` wherever you currently render `a.status` directly, so the UI stays human-readable while all comparisons/writes use the canonical values.

---

## 9. 🟡 Crime status badges are always gray (cosmetic vocabulary mismatch, no data corruption this time)

`crime_frontend/src/components/tables/CrimesTable.tsx`:
```ts
const statusColor: Record<string, string> = {
  "Under Investigation": "bg-yellow-900/40 text-yellow-400",
  "FIR Filed": "bg-blue-900/40 text-blue-400",
  "Arrested": "bg-green-900/40 text-green-400",
  "Solved": "bg-green-900/60 text-green-300",
  "Active Search": "bg-red-900/40 text-red-400",
};
...
<span className={`... ${statusColor[c.status] || "bg-slate-700 text-slate-400"}`}>{c.status}</span>
```
Backend's real crime status values (`config.py`): `["REPORTED", "UNDER_INVESTIGATION", "SOLVED", "CLOSED", "ARCHIVED"]`. None of these match the keys above (different casing, different words entirely — e.g. there's no backend concept of `"FIR Filed"` or `"Arrested"` or `"Active Search"` as a *crime* status at all). Result: **every crime status badge, everywhere `CrimesTable` is used** (Dashboard's Recent Crimes Feed, Crime Database, Crime Map's case list) **always falls back to the default gray badge**, regardless of actual status. Good news: this is display-only — the status **edit** dropdown in the same file correctly uses the real backend values (`REPORTED`, `UNDER_INVESTIGATION`, etc.), so updating a status works correctly; only the colored-badge *display* is broken.

**Fix:**
```ts
const statusColor: Record<string, string> = {
  REPORTED: "bg-slate-600/40 text-slate-300",
  UNDER_INVESTIGATION: "bg-yellow-900/40 text-yellow-400",
  SOLVED: "bg-green-900/60 text-green-300",
  CLOSED: "bg-blue-900/40 text-blue-400",
  ARCHIVED: "bg-slate-700/40 text-slate-500",
};
const statusLabel: Record<string, string> = {
  REPORTED: "Reported", UNDER_INVESTIGATION: "Under Investigation", SOLVED: "Solved",
  CLOSED: "Closed", ARCHIVED: "Archived",
};
...
<span className={`... ${statusColor[c.status] || "bg-slate-700 text-slate-400"}`}>{statusLabel[c.status] || c.status}</span>
```

---

## 10. 🟠 "Register Victim" button is purely decorative — no form, no handler, dead feature

`crime_frontend/src/pages/VictimDatabase.tsx`:
```tsx
{isScrbOrInvestigator && (
  <button className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors">
    <UserPlus className="h-4 w-4" />
    Register Victim
  </button>
)}
```
No `onClick` at all. The backend endpoint this is presumably meant to call already exists and is already wrapped on the frontend:
```python
# victims_router.py
@router.post("", status_code=status.HTTP_201_CREATED)
async def register_victim(...): ...
```
```ts
// victimService.ts
register: (payload: any) => api.post("/victims", payload).then((r) => r.data),
```
So the backend capability and the service-layer call are both fully built — only the UI (a modal/form to collect victim details and call `victimService.register`) was never wired up. This is the same "half-built feature" pattern as the Register button — worth flagging explicitly since it's the kind of thing that looks 100% functional in a screenshot/demo but does nothing when clicked.

**Fix (minimal viable version — expand fields as needed):**
```tsx
const [showRegisterModal, setShowRegisterModal] = useState(false);
const [newVictim, setNewVictim] = useState({ first_name: "", last_name: "", age: "", gender: "", phone_number: "", district_id: "" });

const handleRegisterVictim = async () => {
  try {
    await victimService.register(newVictim);
    setShowRegisterModal(false);
    setNewVictim({ first_name: "", last_name: "", age: "", gender: "", phone_number: "", district_id: "" });
    handleSearch(); // refresh the list
  } catch (err) {
    console.error(err);
  }
};
```
```tsx
<button onClick={() => setShowRegisterModal(true)} className="...">
  <UserPlus className="h-4 w-4" /> Register Victim
</button>
{showRegisterModal && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
    {/* form inputs bound to newVictim, a Save button calling handleRegisterVictim, a Cancel button */}
  </div>
)}
```

---

## 11. ⚪ Orphaned backend endpoints — built server-side, never called from the frontend

These aren't bugs (nothing is broken for the user), but they're evidence of drift between the two codebases and worth a decision (wire them up or delete them):

| Endpoint | Backend location | Frontend reference |
|---|---|---|
| `GET /crimes/filter` (paginated, server-side crime search with `district_id`/`crime_type`/`status`/`page`) | `crimes_router.py` | `ENDPOINTS.CRIMES.FILTER` is defined in `apiEndpoints.ts` but **never called anywhere**. Both `CrimeDatabase.tsx` and `CrimeMapPage.tsx` instead call the unpaginated `getMapData()` and filter/search the *entire* crimes table client-side in JS. |
| `GET /offenders/{id}/network` (per-offender network subgraph) | `offenders_router.py` | `ENDPOINTS.OFFENDERS.NETWORK` is defined but **never called**. `OffenderDatabase.tsx`'s detail panel has no "view this offender's network" affordance despite the backend already supporting it. |
| `GET /network/graph` (duplicate of `/graph-data`) | `network_router.py` (stacked `@router.get` decorator) | Frontend only ever calls `/network/graph-data`. |

**Why this matters for "production ready":** the `/crimes/filter` gap in particular is a real scalability risk, not just dead code — loading the *entire* crimes table into the browser on every page load (Crime Map, Crime Database) will get slower and heavier every day the system is in production use, whereas the paginated, server-side-filtered endpoint that would solve this already exists and works — it's just not being called. Recommend migrating `CrimeDatabase.tsx` and `CrimeMapPage.tsx` to use `ENDPOINTS.CRIMES.FILTER` with real pagination once the district/crime-type filters are applied, rather than shipping the whole table to the client every time.

---

## 12. ⚪ Dead "Offline Mode" banner — the code path that would show it doesn't exist

`crime_frontend/src/components/common/Navbar.tsx`:
```ts
const [usingMockData, setUsingMockData] = useState((window as any).__using_mock_data || false);
useEffect(() => {
  const handleMockData = () => setUsingMockData(true);
  window.addEventListener("mock-data-detected", handleMockData);
  return () => window.removeEventListener("mock-data-detected", handleMockData);
}, []);
...
{usingMockData && (
  <div className="...">
    <span>Offline Mode: Backend connection unavailable. Displaying simulated mock intelligence data.</span>
  </div>
)}
```
Nothing in the entire codebase ever sets `window.__using_mock_data = true` or dispatches a `"mock-data-detected"` `CustomEvent` (confirmed by grep across the whole `src` tree). This banner is permanently dead — it was clearly designed to warn officers when the app has silently fallen back to demo/mock data (a legitimately important thing to surface, given how many services have a `VITE_DEMO_MODE` mock-data fallback), but the wiring was never finished.

**Fix — dispatch the event from the one place that decides to serve mock data.** Since the mock-fallback logic lives in each service's `catch` block (e.g. `crimeService.ts`), the cleanest fix is a small shared helper:
```ts
// utils/mockDataFlag.ts
export function flagMockDataUsed() {
  (window as any).__using_mock_data = true;
  window.dispatchEvent(new CustomEvent("mock-data-detected"));
}
```
```ts
// crimeService.ts (repeat at each `if (import.meta.env.VITE_DEMO_MODE === 'true') return mockX;` site)
import { flagMockDataUsed } from "../utils/mockDataFlag";
...
if (import.meta.env.VITE_DEMO_MODE === 'true') {
  flagMockDataUsed();
  return mockDashboardSummary;
}
```

---

## 13. 🟡 Predictive Analytics page's "Socioeconomic Correlations" grid is always empty

`crime_frontend/src/pages/PredictiveAnalytics.tsx`:
```ts
const [f, r, t, rm, s] = await Promise.all([
  ...,
  predictionService.getSocioeconomicData(),
]);
...
setSocioData(Array.isArray(s) ? s : ((s as any)?.indicators || []));
```
The real backend payload for this endpoint (confirmed in Part 1 and again here) is `{correlations, overlay_data, ai_analysis}` — there is no `indicators` field anywhere in `get_socioeconomic_correlation`'s return shape. So `s?.indicators` is always `undefined` → `socioData` is always `[]` → the entire "Socioeconomic Correlations" card at the bottom of Predictive Analytics silently renders zero district cards, with no "no data" placeholder message either (the grid is just blank). This is a second, independent symptom of the same backend/frontend data-shape drift already covered in §4 above (`SocioEconomicInsights.tsx`), just manifesting differently because this page reads a field name (`indicators`) that was never part of the real response to begin with (unlike `SocioEconomicInsights.tsx`, which had the right field names but the wrong unwrap depth).

**Fix:**
```ts
setSocioData(Array.isArray((s as any)?.overlay_data) ? (s as any).overlay_data : []);
```
And update the render code below it to match the real field names (`district_name`/`unemployment_rate`/`population_density` etc. — cross-check against whatever `get_socioeconomic_correlation` actually returns per-district in `socioeconomic_service.py`).

---

## 14. Duplicate/competing service implementations (maintenance risk, not a bug per se)

Confirmed two independent, parallel implementations of "get evidence for a crime," both suffering the identical unwrap bug (§4.1 in Part 1), and both actually used from different pages:
- `crimeService.getEvidence(id)` — used by `CrimeDatabase.tsx`
- `evidenceService.getEvidenceList(crimeId)` — used by `CrimeMapPage.tsx`

Recommend consolidating to one canonical implementation (in `evidenceService.ts`, since it's the more focused/single-purpose module) and having `crimeService.ts` re-export or call into it, so a fix only ever needs to happen once:
```ts
// crimeService.ts
import { evidenceService } from "./evidenceService";
export const crimeService = {
  ...
  getEvidence: evidenceService.getEvidenceList,
  uploadEvidence: evidenceService.uploadEvidence,
};
```

---

## 15. Summary Table — Part 2 Findings

| # | Area | Issue | Severity | User-visible symptom |
|---|---|---|---|---|
| 1 | App-wide | No React ErrorBoundary | 🔴 Critical | Any one unguarded bug white-screens the *entire app*, not just one page |
| 2 | AI Assistant widget | Double-unwrap bug | 🔴 Critical | Chat assistant never shows real answers, on every page, always |
| 3 | Settings → Import Data | Double-unwrap bug | 🔴 Critical | No success/failure feedback after bulk import, ever |
| 4 | Socio-Economic Insights page | Double-unwrap bug | 🔴 Critical | Page permanently empty, "Avg Crime Rate" shows `NaN` |
| 5 | User creation (Settings) | District **name** stored instead of **code** | 🔴 Critical | New District Officer accounts see zero data for their own district, forever |
| 6 | Hotspot Analysis | Wrong query-param name (`district` vs `district_id`) | 🟠 High | District filter dropdown has zero effect on any hotspot data |
| 7 | Report generation | District name never resolved to code | 🟠 High | District-scoped reports silently generate with 0 matching records |
| 8 | Anomaly Detection | Status/severity vocabulary mismatch | 🟠 High | Severity counts always 0, status filters always empty, resolving an anomaly corrupts its status field |
| 9 | Crime status badges (3 pages) | Vocabulary mismatch | 🟡 Medium | Status badges never show intended color, always gray |
| 10 | Victim Database | "Register Victim" button has no handler | 🟠 High | Button does nothing when clicked |
| 11 | Crimes filter / offender network endpoints | Built but never called | ⚪ Info | No user symptom yet; scalability risk (whole crimes table shipped to browser every load) |
| 12 | Navbar | "Offline/Mock data" banner never triggers | ⚪ Info | Officers get no warning when viewing simulated demo data instead of real data |
| 13 | Predictive Analytics | Wrong field name (`indicators`) | 🟡 Medium | "Socioeconomic Correlations" grid always empty |
| 14 | Evidence services | Duplicate implementations, same bug in both | 🟡 Medium (maintainability) | Fixing one call site doesn't fix the other |

**Suggested fix order for this batch:** #1 (ErrorBoundary) first since it's a 10-line safety net for everything else; then #5 (RBAC/district bug — silent data-access failure for a whole user role) and #2/#3/#4 (the three additional double-unwrap "always empty/broken" features) since those are all one-line fixes with outsized impact; then #6/#7/#8 (filter/vocabulary mismatches); then #9/#10/#13 as polish; #11/#12/#14 whenever you're next touching those files.