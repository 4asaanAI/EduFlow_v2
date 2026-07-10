# Epic R14 — Multi-Worker Correctness — Completed

**Date:** 2026-07-10
**Baseline before:** 1606 passed, 14 deselected, 0 failed
**Baseline after:** 1616 passed, 14 deselected, 0 failed
**New tests added:** 10 (test_r14_multi_worker.py)

---

## Stories shipped

### R14.1 — Shared or guarded SSE / notification fan-out (P-M3)

**Chosen posture: OPTION B — startup guard (single-worker enforcement)**

**Files changed:** `backend/services/sse.py`, `backend/server.py`

**What changed:**
- Added `validate_multi_worker_config()` to `sse.py` that raises `ValueError` if `WEB_CONCURRENCY > 1` and `REDIS_URL` is not set. This prevents the silent-drop scenario where a notification published on worker A never reaches a client connected to worker B.
- Added a call to `_validate_sse_worker_config()` in `server.py`'s `startup()` handler, alongside the existing `validate_school_id()` and `validate_ai_config()` guards.
- Updated the module-level comment in `sse.py` to formally document the single-worker constraint, the reasoning, and the migration path (set `REDIS_URL` to enable a shared broker in future).

**layaastat AC2 — already complete (R9.3 M9):**
`_pending_tasks` set already exists in `layaastat.py` (added in R9.3) to hold strong refs to fire-and-forget tasks and prevent GC. Failure logging is already at `warning` level. No changes needed; test `test_layaastat_pending_tasks_set_exists` confirms it.

**AC3 test:** `test_sse_startup_refuses_multi_worker_without_redis` — verifies the guard fires for `WEB_CONCURRENCY=4` without Redis. Companion tests verify single-worker-without-Redis and multi-worker-with-Redis are both allowed.

### R14.2 — Deactivated-school gate: cached + deliberate failure posture (P-M5)

**File changed:** `backend/middleware/school_context.py`

**What changed:**
- Added a simple TTL cache (`_school_status_cache: dict[str, Tuple[Optional[str], float]]`) bounded to `SCHOOL_STATUS_CACHE_TTL_SECONDS = 30` (matching the kill-switch TTL in `ai_kill_switch.py`). The lookup now hits the cache on the hot path; only a cache miss or TTL expiry triggers a Mongo round-trip.
- Added `_get_cached_school_status()`, `_set_cached_school_status()`, `_clear_school_status_cache()` helpers.
- Fail-open behavior on DB exception is now explicitly documented as a **deliberate architectural choice** in the module comment, with a clear explanation of the rationale (a stuck-closed brake caused by transient DB errors would be its own availability incident).

**Test isolation fix:** Added an `autouse=True` function-scoped fixture to `tests/backend/conftest.py` that clears the school status cache before each test, preventing the new per-process cache from leaking between test cases.

**AC2 test:** `test_school_status_fail_open_on_db_exception` — verifies that when the DB throws, the middleware logs a warning and proceeds (fail-open). `test_deactivated_school_returns_402` and `test_active_school_passes_through` verify the correct 402 and non-402 paths with a primed cache.

---

## grep audit (no new scoped_filter hits)

R14 only modified `sse.py`, `server.py`, and `school_context.py` — none of which use `scoped_filter` in operational data paths. No audit needed.

---

## Deferred / Discoveries

- The `ai_kill_switch.py` cache is also per-process (same 30s TTL, same fail-open posture). The write path already uses `force_fresh=True` to bypass the cache for the critical confirm path (R9.3 M8, already shipped). No further action needed.
- The `sse.py` channel registry eviction loop has no `schoolId` filter (noted in DEFERRED-AND-DISCOVERIES.md from R11.6). Still accepted — the SSE channels carry only keepalive pings; data is in the event payload delivered per-conversation.
