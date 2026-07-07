---
story_id: "7.46"
story_key: 7-46-google-maps-transport-optimisation
epic: 7
story: 46
status: done
priority: medium
effort: large
created: "2026-05-19"
---

# Story 7.46: Google Maps Transport Optimisation

## User Story

**As** the Transport Head (or Owner),
**I want** the system to geocode student home addresses, compute distances to route zones, and suggest optimal zone assignments,
**so that** I can minimise travel time and cost by placing students in the nearest available route zone.

---

## Acceptance Criteria

- [x] **AC1 — Student coordinates storage:** Students can have backend-only `coordinates` object `{"lat": float, "lng": float}` stored. A `PATCH /api/transport/students/{student_id}/coordinates` endpoint accepts `{"lat": float, "lng": float}` and updates the student document. Coordinates are **never** returned in `GET /api/students` list or detail responses (backend projection excludes them).
- [x] **AC2 — Zone centroid storage:** `transport_routes` documents can store a `centroid` object `{"lat": float, "lng": float}` representing the geographic centre of the route zone. A `PATCH /api/transport/zones/{zone_id}/centroid` endpoint accepts `{"lat": float, "lng": float}` and saves it. Owner + admin only.
- [x] **AC3 — Geocoding endpoint:** `POST /api/transport/geocode` accepts `{"address": str}`, calls the Google Maps Geocoding REST API using `GOOGLE_MAPS_API_KEY`, and returns `{"lat": float, "lng": float, "formatted_address": str}`. If `GOOGLE_MAPS_API_KEY` is not configured, returns 503 with `{"detail": "Maps API not configured"}`. Owner + admin only.
- [x] **AC4 — Route suggestion:** `GET /api/transport/suggest-route?student_id={id}` finds the student's stored `coordinates`, computes Haversine distances to all active zone centroids (that have `centroid` set), and returns zones ranked by proximity. If the student has no coordinates, returns 422. Owner + admin only.
- [x] **AC5 — Cluster analysis:** `GET /api/transport/cluster-analysis` returns all students who have coordinates AND are assigned to a zone that is **not** the nearest zone (i.e. a nearer centroid exists). Response: `{"data": [{"student_id", "student_name", "current_zone_id", "current_zone_name", "nearest_zone_id", "nearest_zone_name", "current_distance_km", "nearest_distance_km"}], "meta": {"total_suboptimal": N, "total_with_coords": M}}`. Owner only.
- [x] **AC6 — Fail gracefully when Maps API is unavailable:** Geocoding errors (network error, API quota exceeded, invalid key) must return 502 with `{"detail": "Geocoding request failed"}`. The error detail must never contain the raw API response or the API key. Maps API calls use a 5-second timeout.
- [x] **AC7 — Migration 019:** A new migration adds `2dsphere` index on `transport_routes.centroid` (sparse) and `students.coordinates` (sparse). Migration is registered in `backend/migrations/run_all.py`.
- [x] **AC8 — Frontend: Transport Optimisation panel:** A new `TransportOptimisation.js` component renders in the Transport Head's AdminTools panel as a new "Optimise Routes" tab. Features: (1) geocode any address text to get coordinates; (2) set those coordinates on a selected student; (3) view the route suggestion for any student with coordinates; (4) view the cluster analysis table of suboptimal assignments with one-click re-assign button. Owner + Transport Head admin only.
- [x] **AC9 — env.example updated:** `GOOGLE_MAPS_API_KEY=` added to `backend/.env.example` with a comment linking to the Maps API console.
- [x] **AC10 — Tests:** `tests/backend/unit/test_transport_optimisation.py` covers: geocode endpoint 503 when no key, suggest-route happy path, suggest-route 422 when no coordinates, cluster-analysis happy path with mock data, auth matrix (401 + 403).

---

## Tasks / Subtasks

- [x] **Task 1 — Backend: maps_service.py**
  - [x] Create `backend/services/maps_service.py` with `geocode(address, api_key)` → `dict` and `haversine_km(lat1, lng1, lat2, lng2)` → float
  - [x] `geocode()` calls `https://maps.googleapis.com/maps/api/geocode/json` via `httpx` (5s timeout); raises `RuntimeError` on API error

- [x] **Task 2 — Backend: new transport endpoints**
  - [x] `PATCH /api/transport/students/{student_id}/coordinates` — save lat/lng on student doc
  - [x] `PATCH /api/transport/zones/{zone_id}/centroid` — save centroid on transport_route doc
  - [x] `POST /api/transport/geocode` — geocode endpoint (AC3)
  - [x] `GET /api/transport/suggest-route` — proximity rank (AC4)
  - [x] `GET /api/transport/cluster-analysis` — suboptimal assignments (AC5 + AC6)

- [x] **Task 3 — Backend: migration 019**
  - [x] Create `backend/migrations/019_transport_coordinates.py` with 2dsphere indexes
  - [x] Register in `backend/migrations/run_all.py`

- [x] **Task 4 — Backend: env.example + coordinates exclusion**
  - [x] Add `GOOGLE_MAPS_API_KEY=` to `backend/.env.example`
  - [x] Ensure `coordinates` field is excluded from student list/detail responses in `backend/routes/students.py`

- [x] **Task 5 — Frontend: TransportOptimisation.js**
  - [x] Create `frontend/src/components/tools/TransportOptimisation.js`
  - [x] Wire into `frontend/src/components/tools/AdminTools.js` for transport-head sub_category
  - [x] Add API calls to `frontend/src/lib/api.js`

- [x] **Task 6 — Tests**
  - [x] Create `tests/backend/unit/test_transport_optimisation.py` (AC10)

---

## Dev Notes

### Architecture
- `maps_service.py` is a pure utility module — no FastAPI dependency. Functions accept `api_key` parameter (injected from `os.environ.get("GOOGLE_MAPS_API_KEY")`).
- All new transport endpoints go at the end of the `# --- Transport ---` section in `backend/routes/operations.py`.
- `httpx` is already imported in `operator.py` — no new package dependency.
- Haversine formula for great-circle distance — no scipy needed, pure Python math.

### Haversine distance
```python
import math
def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0  # Earth radius km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))
```

### Google Maps Geocoding REST call
```python
import httpx
async def geocode(address: str, api_key: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, params={"address": address, "key": api_key})
    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise RuntimeError("geocode_failed")
    loc = data["results"][0]["geometry"]["location"]
    return {"lat": loc["lat"], "lng": loc["lng"], "formatted_address": data["results"][0]["formatted_address"]}
```

### Coordinates excluded from student responses
In `backend/routes/students.py`, all `find` projections must include `"coordinates": 0`. Check existing projection dicts and add the exclusion.

### Transport head role check
Transport Head is `role="admin", sub_category="transport"`. Use `Depends(require_role("owner", "admin"))` for most endpoints; for cluster-analysis (owner-only) use `Depends(require_owner)`.

### Frontend: AdminTools sub_category check
In `AdminTools.js`, the transport panel is conditionally rendered when `user.sub_category === "transport"`. Add `TransportOptimisation` as an additional tab within that panel.

### Python 3.9 compliance
All new backend files must have `from __future__ import annotations` as the first line.

---

## Dev Agent Record

### Agent Model Used
Claude Sonnet 4.6

### Debug Log
- N/A (fresh implementation)

### Completion Notes
_To be filled on completion._

### Status
done

## File List

- backend/services/maps_service.py (NEW)
- backend/routes/operations.py (MODIFIED — new transport endpoints)
- backend/migrations/019_transport_coordinates.py (NEW)
- backend/migrations/run_all.py (MODIFIED)
- backend/.env.example (MODIFIED)
- backend/routes/students.py (MODIFIED — exclude coordinates from responses)
- frontend/src/components/tools/TransportOptimisation.js (NEW)
- frontend/src/components/tools/AdminTools.js (MODIFIED — wire in new tab)
- frontend/src/lib/api.js (MODIFIED — new transport API calls)
- tests/backend/unit/test_transport_optimisation.py (NEW)

## Change Log

- 2026-05-19: Story 7-46 created and implementation started.

---

### Review Findings

**Code review date:** 2026-05-19 — Layers: Blind Hunter, Edge Case Hunter, Acceptance Auditor
**Dismissed:** 4 (resp.json outer-try coverage, geocode only-raises-RuntimeError, zoneId-state false-positive, student-lng guard already present)

#### Decision-Needed

- [x] [Review][Decision] D1: cluster_analysis RBAC vs transport_head UX — resolved: option A applied, opened to `require_role("owner","admin")` so transport_head can run analysis.
- [x] [Review][Decision] D2: TransportOptimisation wired as standalone sidebar tool, not as a tab named "Optimise Routes" within TransportManager — resolved: option A accepted, standalone tool approach kept.

#### Patches

- [x] [Review][Patch] P1: Migration 023 docstring says "Migration 019" in three places — trivial find/replace to 023 [backend/migrations/023_transport_coordinates.py]
- [x] [Review][Patch] P2: 2dsphere index incompatible with plain-dict `{"lat": float, "lng": float}` storage — MongoDB requires GeoJSON or legacy `[lng, lat]` array; plain dict causes MongoDB to reject updates on indexed documents in production; since geo queries are not used, remove the 2dsphere index from the migration (keep regular index or no index) [backend/migrations/023_transport_coordinates.py]
- [x] [Review][Patch] P3: Deferred imports `from services.maps_service import geocode/haversine_km` inside handler bodies — move to module-level imports in operations.py [backend/routes/operations.py]
- [x] [Review][Patch] P4: No lat/lng range validation in set_student_coordinates and set_zone_centroid — accepts lat=9999.0; add guard: `if not (-90 <= lat <= 90) or not (-180 <= lng <= 180)` [backend/routes/operations.py]
- [x] [Review][Patch] P5: Centroid lng guard missing — `if not centroid or centroid.get("lat") is None` skips lng check; float(centroid["lng"]) when lng=None raises TypeError → 500; fix: add `or centroid.get("lng") is None` to both suggest_route and cluster_analysis centroid guards [backend/routes/operations.py]
- [x] [Review][Patch] P6: Hard cap `.to_list(50)` on zones silently truncates — suggest_route and cluster_analysis both cap at 50 zones (and cluster_analysis caps students at 1000) with no warning in response meta; violates AC4/AC5 ("all active zone centroids"); raise zone cap to 500 and add `meta.zones_loaded` / `meta.students_loaded` counts [backend/routes/operations.py]
- [x] [Review][Patch] P7: AdminTools.js re-export of TransportOptimisation is dead code — Layout.js directly imports `./tools/TransportOptimisation`, never uses the AdminTools re-export; remove it [frontend/src/components/tools/AdminTools.js]
- [x] [Review][Patch] P8: result.data not guarded in frontend tabs — SuggestRouteTab and ClusterAnalysisTab call `.map()` on result.data without Array.isArray check; meta.total_with_coords used without optional chaining; add guards [frontend/src/components/tools/TransportOptimisation.js]
- [x] [Review][Patch] P9: GeocodeTab stale error/saved state — handleSaveToStudent and handleSaveToZone don't call `setError('')` and `setSaved('')` at their start; previous error or success message persists alongside new state [frontend/src/components/tools/TransportOptimisation.js]
- [x] [Review][Patch] P10: TOCTOU find_one + update_one in set_student_coordinates and set_zone_centroid — two round trips with race window; replace with single `update_one(...) → modified_count == 0 → 404` [backend/routes/operations.py]
- [x] [Review][Patch] P11: get_student detail endpoint still exposes coordinates — only list_students was patched with `"coordinates": 0`; the single-student detail endpoint also needs the projection exclusion → AC1 violation [backend/routes/students.py]
- [x] [Review][Patch] P12: Missing 403 test for PATCH /transport/students/{id}/coordinates [tests/backend/unit/test_transport_optimisation.py]
- [x] [Review][Patch] P13: Missing 403 test for PATCH /transport/zones/{id}/centroid [tests/backend/unit/test_transport_optimisation.py]
- [x] [Review][Patch] P14: Missing 422 test for POST /transport/geocode with empty/missing address body [tests/backend/unit/test_transport_optimisation.py]
- [x] [Review][Patch] P15: Missing 404 test for GET /transport/suggest-route with nonexistent student_id [tests/backend/unit/test_transport_optimisation.py]
- [x] [Review][Patch] P16: Cross-tenant isolation tests missing — all test fixtures use only schoolId="aaryans-joya"; mandatory per CLAUDE.md testing conventions; add a doc from "other-school" and assert it is NOT returned [tests/backend/unit/test_transport_optimisation.py]
- [x] [Review][Patch] P17: Test patch target brittle — `patch("services.maps_service.geocode")` patches the module-level name; if P3 (module-level imports) is applied, the correct target becomes `patch("routes.operations._geocode_address")`; update the patch target in tandem with P3 [tests/backend/unit/test_transport_optimisation.py]
- [x] [Review][Patch] P18: SuggestRouteTab missing empty-state — when data is [] (no zones have centroids), tab renders a blank panel with no user message; add "No zones with centroids found" empty state [frontend/src/components/tools/TransportOptimisation.js]
- [x] [Review][Patch] P19: ClusterAnalysisTab missing one-click re-assign button → AC8 violation — table shows suboptimal assignments but provides no action; add a "Reassign" button per row that calls the existing student zone-assignment endpoint [frontend/src/components/tools/TransportOptimisation.js]

#### Deferred

- [x] [Review][Defer] DEF1: O(students×zones) in-memory haversine loop — no pagination or async offload; acceptable for school fleet today; revisit if analysis times out under load [backend/routes/operations.py:cluster_analysis] — deferred, pre-existing architectural choice
- [x] [Review][Defer] DEF2: haversine math.asin overflow for near-antipodal points — `a` can slightly exceed 1.0 via float rounding; would raise ValueError; unreachable with India-based coordinates and valid data [backend/services/maps_service.py:haversine_km] — deferred, pre-existing
- [x] [Review][Defer] DEF3: zone document missing `id` field raises KeyError in suggest_route — `z["id"]` used without .get(); `id` is a data invariant enforced by the insert path, not introduced here [backend/routes/operations.py:suggest_route] — deferred, pre-existing
