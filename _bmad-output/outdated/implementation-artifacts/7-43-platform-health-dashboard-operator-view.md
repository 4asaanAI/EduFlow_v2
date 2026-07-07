# Story 7.43: Platform Health Dashboard — Operator View

Status: done
Epic: 7
Priority: Medium (Phase 2 — Layaa AI internal monitoring)
Effort: Medium
Created: 2026-05-18

---

## Story

**As** the school platform operator (Abhimanyu / Layaa AI),
**I want** an owner-only dashboard panel showing live service health, token pool status, fee sync last run, and recent error count,
**so that** I can detect and diagnose platform degradation in seconds without SSHing into logs.

---

## Acceptance Criteria

**AC1. Backend: `GET /api/operator/platform-health` endpoint (owner-only)**
Returns aggregated health data. Response shape:
```json
{
  "success": true,
  "data": {
    "service_checks": {
      "db": "ok",
      "ai": "ok | degraded",
      "s3": "ok | degraded | not_configured",
      "sms": "ok | degraded | not_configured",
      "overall": "ok | degraded | down"
    },
    "token_pool": {
      "school_topup_pool": 4820000,
      "subscription_status": "active | canceled | null",
      "subscription_plan": "monthly_school_starter | null"
    },
    "fee_sync_last": {
      "status": "completed | failed | in_progress | null",
      "started_at": "2026-05-18T05:00:00",
      "completed_at": "2026-05-18T05:02:37",
      "job_id": "..."
    },
    "error_rate": {
      "error_count": 3,
      "window_minutes": 60,
      "since": "2026-05-18T09:00:00Z"
    },
    "active_user_count": 8,
    "generated_at": "2026-05-18T10:00:00Z"
  }
}
```

**AC2. Service checks mirror `_check_db()`, `_check_ai()`, `_check_s3()`, `_check_sms()` from `server.py`.**
DB check uses Motor ping. AI check reads `AZURE_OPENAI_ENDPOINT` env var and does a 3-second GET. S3 and SMS follow the same pattern. `overall` is `"down"` when DB is `"error"`, `"degraded"` when any check is `"degraded"`, otherwise `"ok"`.

**AC3. `fee_sync_last` returns the most-recent `fee_sync_jobs` document (sorted by `started_at` desc, limit 1).**
If no jobs exist, `fee_sync_last` is `null`. The document is school-scoped (use `scoped_filter`).

**AC4. `error_rate.error_count` is a count of `audit_logs` documents in the last 60 minutes where `action` contains `"fail"` or `"error"` (case-insensitive `$regex`).**
`since` is the ISO timestamp of the 60-minute boundary. School-scoped.

**AC5. `active_user_count` is the count of `auth_users` documents where `is_active: true`.**
School-scoped via `scoped_filter`.

**AC6. `token_pool` is read from `db.token_balances.find_one({"branch_id": branch_id})` for the operator's `branch_id`.**
If no balance document exists, returns `{"school_topup_pool": 0, "subscription_status": null, "subscription_plan": null}`.

**AC7. Frontend: `PlatformHealthDashboard` component exported from `frontend/src/components/tools/OwnerTools.js`.**
Shows four panels:
- **Service Health** — color-coded badges for db/ai/s3/sms (`ok`=green, `degraded`=amber, `not_configured`=grey, `down`/`error`=red)
- **Token Pool** — remaining topup tokens + subscription status pill
- **Fee Sync** — last run timestamp + status badge
- **Error Rate** — error count in last 60 min, amber if > 0, green if 0

**AC8. Manual refresh button + auto-refresh every 60 seconds.** Shows `last refreshed: HH:MM:SS` timestamp. No SSE required — polling is appropriate for admin-only monitoring.

**AC9. Tool wired in `Layout.js`.**
`'platform-health-dashboard'` added to the `OWNERS` array. The `toComp()` function produces `PlatformHealthDashboard` automatically (no special-casing needed — verify: `'platform-health-dashboard'.split('-').map(w=>w[0].toUpperCase()+w.slice(1)).join('')` → `PlatformHealthDashboard`).

**AC10. `fetchPlatformHealth()` added to `frontend/src/lib/api.js`.**
Uses `apiFetch('/api/operator/platform-health')`.

**AC11. Tests — 8+ new tests in `tests/backend/unit/test_platform_health_dashboard.py`.**
Required tests:
- `test_platform_health_unauthenticated_returns_401`
- `test_platform_health_wrong_role_returns_403` (role=admin, no sub_category)
- `test_platform_health_owner_returns_200_with_expected_shape`
- `test_fee_sync_last_returns_most_recent_job`
- `test_fee_sync_last_is_null_when_no_jobs`
- `test_error_rate_counts_failed_audit_actions`
- `test_error_rate_excludes_old_entries` (older than 60 min not counted)
- `test_active_user_count_counts_only_active_users`

---

## Tasks

- [x] **T1. Backend endpoint** — Add `GET /api/operator/platform-health` to `backend/routes/operator.py`
- [x] **T2. api.js** — Add `export async function fetchPlatformHealth()` to `frontend/src/lib/api.js`
- [x] **T3. Frontend component** — Add `export function PlatformHealthDashboard()` to `frontend/src/components/tools/OwnerTools.js`
- [x] **T4. Layout.js** — Add `'platform-health-dashboard'` to `OWNERS` array
- [x] **T5. Tests** — `tests/backend/unit/test_platform_health_dashboard.py` (8 tests)

---

## Dev Notes

### Backend: operator.py additions

Add the new route **after** the existing `get_ai_action_counts` handler. The file already has:
- `from datetime import datetime, timezone`
- `from database import get_db`
- `from middleware.auth import require_owner`
- `httpx` is NOT imported yet — add it: `import httpx`

Do NOT move `_check_db()` etc. from `server.py` — they are private helpers in the main app module. Re-implement the same lightweight checks inline in the new endpoint. The checks are small (< 10 lines each).

```python
# Pattern for the DB check in the new endpoint:
async def _platform_db_check(db) -> str:
    try:
        await db.command("ping")
        return "ok"
    except Exception:
        logger.warning("platform health db check failed", exc_info=True)
        return "error"
```

**Scoping in operator.py**: The existing `get_ai_action_counts` does NOT use `get_school_id()` or `scoped_filter` — it looks up users by `user_id` param directly. For the new endpoint, import these:
```python
from tenant import scoped_filter
from database import get_db, get_school_id
```

**Error-rate audit_log query:**
```python
from datetime import datetime, timezone, timedelta
import re

sixty_min_ago = datetime.now(timezone.utc) - timedelta(minutes=60)
sixty_min_ago_iso = sixty_min_ago.isoformat()

error_query = scoped_filter(
    {
        "created_at": {"$gte": sixty_min_ago_iso},
        "action": {"$regex": re.escape("fail") + "|" + re.escape("error"), "$options": "i"},
    },
    get_school_id(),
)
error_count = await db.audit_logs.count_documents(error_query)
```

**Fee sync last job query (school-scoped, NOT branch-scoped — fee sync is school-wide):**
```python
from tenant import scoped_filter
jobs = await db.fee_sync_jobs.find(
    scoped_filter({}, get_school_id()),
    {"_id": 0},
    sort=[("started_at", -1)],
).to_list(1)
fee_sync_last = jobs[0] if jobs else None
```

**Token pool (branch-scoped for owner's branch):**
```python
branch_id = user.get("branch_id")
balance_doc = await db.token_balances.find_one({"branch_id": branch_id}, {"_id": 0}) or {}
```

**Active user count (school-scoped only, not branch-scoped — school-wide stat):**
```python
active_user_count = await db.auth_users.count_documents(
    scoped_filter({"is_active": True}, get_school_id())
)
```

**Service checks — `httpx` import**: httpx is already in requirements (`httpx>=0.25.0`), used in `server.py`. Add `import httpx` to `operator.py`.

**`overall` computation:**
```python
checks = {"db": db_status, "ai": ai_status, "s3": s3_status, "sms": sms_status}
if db_status == "error":
    overall = "down"
elif any(v == "degraded" for v in checks.values()):
    overall = "degraded"
else:
    overall = "ok"
```

**Response `generated_at`:** use `datetime.now(timezone.utc).isoformat()`.

---

### Frontend: PlatformHealthDashboard

Add at the **end** of `OwnerTools.js` (before any last closing brace — but the file has no wrapper, each function is top-level). Reference the `SchoolPulse` function for the standard `useEffect + setLoading + apiFetch` pattern.

Import: `fetchPlatformHealth` from `'../lib/api'` — add it to the existing import block at the top of OwnerTools.js alongside the other named imports.

**Status badge helper** (define inline inside the component, not exported):
```js
const STATUS_COLOR = {
  ok: 'var(--color-success, #22c55e)',
  degraded: 'var(--color-warning, #f59e0b)',
  not_configured: 'var(--text-muted)',
  error: 'var(--color-error, #ef4444)',
  down: 'var(--color-error, #ef4444)',
};
```

**Auto-refresh pattern** — use `useRef` for the interval, clear on unmount:
```js
const intervalRef = useRef(null);
useEffect(() => {
  load();
  intervalRef.current = setInterval(load, 60000);
  return () => clearInterval(intervalRef.current);
}, []);
```

**Last-refreshed display:** store as `useState(null)` initialized as `null`, set to `new Date().toLocaleTimeString()` after each successful load.

**Empty/loading/error states**: follow the same `ToolPage` + spinner pattern used by `SmartAlerts` (line ~1041). Show a spinner while `loading`, show an error message with a retry button if the fetch throws, show the data panels when loaded.

**Do NOT** install any new npm packages. Use `lucide-react` icons only (already available). Suggested icons:
- `Activity` for service health
- `Zap` for token pool  
- `RefreshCw` for fee sync
- `AlertTriangle` for error rate

**Do NOT** use `axios` — use `apiFetch` via the exported `fetchPlatformHealth()` function.

---

### Layout.js change

Line 40, current OWNERS array (as of latest commit):
```js
const OWNERS = ['school-pulse','fee-collection','fee-sync','student-strength','data-import','attendance-overview','staff-tracker','staff-attendance-tracker','financial-reports','announcement-broadcaster','admission-funnel','staff-leave-manager','staff-performance','ai-health-report','smart-alerts','expense-tracker','complaint-tracker','custom-report-builder','board-report','smart-fee-defaulter','attendance-alerts','reports-trends'];
```

Append `'platform-health-dashboard'` to this array. No other changes needed in Layout.js.

---

### Tests

File: `tests/backend/unit/test_platform_health_dashboard.py`

**Required file header:**
```python
from __future__ import annotations
import pytest
pytestmark = pytest.mark.asyncio
```

**Auth helper pattern** (copy from test_razorpay_checkout.py or test_teacher_student_login.py):
```python
import jwt, os
def _bearer(claims):
    token = jwt.encode({**claims, "exp": 9999999999}, os.environ.get("JWT_SECRET", "test-secret"), algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}
```

**FakeDb setup** — the new endpoint uses `db.audit_logs`, `db.fee_sync_jobs`, `db.token_balances`, `db.auth_users`. Register these collections in the APP_AVAILABLE block:
```python
if APP_AVAILABLE:
    from tests.backend.conftest import _fake_db
    import routes.operator as op_mod
    op_mod.get_db = lambda: _fake_db
```

**Autouse cleanup** — add for all four collections touched by the endpoint.

**Mocking `httpx.AsyncClient`**: The endpoint does async HTTP calls for AI/S3/SMS checks. Mock `httpx.AsyncClient` via `monkeypatch` to avoid real network calls:
```python
class _FakeResp:
    status_code = 200

class _FakeClient:
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def get(self, *a, **kw): return _FakeResp()

monkeypatch.setattr("routes.operator.httpx.AsyncClient", lambda **kw: _FakeClient())
```

**Mock Motor ping**: The `db.command("ping")` call hits the raw Motor client. Mock it via `monkeypatch.setattr` on the `get_db()` returned object's `command` attribute, or simply mock `_platform_db_check` (if extracted as a module-level helper).

**Test for `test_error_rate_excludes_old_entries`**: seed `audit_logs` with a doc having `action="fee_sync_failed"` and `created_at` > 61 minutes ago. Assert `error_count == 0`.

**Test for `test_fee_sync_last_returns_most_recent_job`**: seed two `fee_sync_jobs` with different `started_at` values. Assert `data.fee_sync_last.job_id` matches the newer one.

---

### Scoping notes for operator.py

This endpoint is **owner-only** (`Depends(require_owner)`). It reads:
- `audit_logs` — `scoped_filter` (school-wide, intentional — monitoring all branches)
- `fee_sync_jobs` — `scoped_filter` (school-wide — fee sync is not branch-scoped)
- `auth_users` — `scoped_filter` (school-wide — total active user count)
- `token_balances` — queried by `branch_id` directly (not scoped_filter — uses branch_id as the key)

All `scoped_filter` calls here are intentionally school-wide. Add the comment:
```python
# branch-scope: intentional — operator health is a school-wide aggregate view
```

---

### Pre-merge CI check

After implementing, run:
```bash
grep -n "scoped_filter(" backend/routes/operator.py
```
Verify every hit has `# branch-scope: intentional` comment.

---

## Scope Exclusions

- No email/SMS alerting on threshold breach (Phase 3)
- No historical error-rate chart (use existing `reports-trends` for historical data)
- No per-user session drill-down (the existing `GET /api/operator/ai-action-counts` is separate)
- No real-time streaming of health data (60s polling is sufficient)
- No Biometric integration check in the UI (it's conditionally in `health_ready` but the operator panel is for the operator's own monitoring)

---

## Previous Story Intelligence

From **Story 7-42 (Stripe integration)** — dev notes:
- `operator.py` already imports: `from datetime import datetime, timezone`, `from database import get_db`, `from middleware.auth import require_owner`. Add `import httpx` and `from tenant import scoped_filter` and `from database import get_school_id`.
- Test isolation: always add `autouse` cleanup fixture to reset all four collections between tests (`audit_logs`, `fee_sync_jobs`, `token_balances`, `auth_users`).
- The `deferred-work.md` notes that `conftest.py` does NOT monkeypatch `routes.tokens` for full-suite — same gap applies to `routes.operator`. Handle in the APP_AVAILABLE block.
- `ChatInterface.js` has `handleRecharge` Stripe redirect which now uses `?recharge=success` param detection — do NOT touch this when adding PlatformHealthDashboard to OwnerTools.js.

From **Story 7-41 (Recharts dashboard)** — patterns to reuse:
- `OwnerTools.js` import block at top — add `fetchPlatformHealth` alongside `triggerFeeSync`, `getFeeSyncJob`, etc.
- `ToolPage` wrapper with `title` and `subtitle` props — use it for the panel chrome.
- `LineChartWidget`/`BarChartWidget` are already available in `OwnerTools.js` scope if needed (no charts needed for this story — skip them).

---

## Baseline

- **699 backend tests passing, 0 skipped** (as of 2026-05-16)
- Run before and after: `python -m pytest tests/backend/ -x -q`
- Expected after: 707+ tests (8 new)

---

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### File List

**Added:**
- `tests/backend/unit/test_platform_health_dashboard.py` — 8 tests

**Modified:**
- `backend/routes/operator.py` — added `import httpx`, `import os/re/timedelta`, `from database import get_school_id`, `from tenant import scoped_filter`; added 4 health-check helpers + `GET /api/operator/platform-health` endpoint
- `frontend/src/lib/api.js` — `fetchPlatformHealth()` exported
- `frontend/src/components/tools/OwnerTools.js` — added `useRef`, `fetchPlatformHealth`, `Zap`, `Database`, `Cloud` imports; added `StatusBadge` helper + `PlatformHealthDashboard` component
- `frontend/src/components/Layout.js` — `'platform-health-dashboard'` appended to OWNERS array

### Completion Notes
All 5 tasks complete. 8 new backend tests pass (auth: 401/403, shape, fee sync ordering, fee sync null, error rate counting, error rate window exclusion, active user count). Full suite: 733 passed (baseline 699 + 34 from this and prior stories). No regressions. All 11 ACs satisfied: backend endpoint returns correct shape, service checks mirror server.py helpers, fee sync returns most-recent job, error rate uses 60-min window, active user count is school-scoped, frontend component has 4 panels with auto-refresh every 60s + manual refresh, toComp mapping verified, fetchPlatformHealth() wired through api.js, Layout.js OWNERS updated.

### Review Findings

- [x] [Review][Decision] Owner `branch_id` ambiguity in token pool — `user.get("branch_id")` is `None` for owner JWTs; `find_one({"branch_id": None})` matches only documents with `branch_id: null`. If token balances are always per-branch (never null), `token_pool` will always show zeros for the owner. Correct behavior is ambiguous: (a) a school-level document with `branch_id: null` exists by convention, (b) aggregate across all branches, or (c) accept zeros as intentional. [backend/routes/operator.py:244]
- [x] [Review][Patch] Dead code: `error_pattern = re.compile(r"fail|error", re.IGNORECASE)` compiled but never used; `import re` (line 11) also becomes unused [backend/routes/operator.py:11,272]
- [x] [Review][Patch] Sequential health checks — 4 awaits in series, up to 12s worst case with 3s timeouts each; replace with `asyncio.gather()` [backend/routes/operator.py:230-233]
- [x] [Review][Patch] Datetime issues — `datetime.now(timezone.utc)` called twice (lines 270 and 300); `$gte` uses `.isoformat()` string (type mismatch with BSON Date in `audit_logs.created_at` → `error_count` always 0). Fix: capture `now = datetime.now(timezone.utc)` once at top of handler, use `now - timedelta(minutes=60)` (datetime object, not ISO string) in the `$gte` query, and `now.isoformat()` for `generated_at` [backend/routes/operator.py:270-300]

### Change Log
- 2026-05-18 — Story created. Status: ready-for-dev.
- 2026-05-18 — Implemented all tasks. Status: review. 8 tests added. 733 total tests pass.
- 2026-05-18 — Code review complete. 1 decision-needed, 3 patch, 0 defer, 2 dismissed.
