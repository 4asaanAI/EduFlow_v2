# Epic R14 — Multi-Worker Correctness — Review

**Date:** 2026-07-10
**Reviewer:** executing agent (post-implementation adversarial review)

---

## What went well

- **Option B (startup guard) is the right call for R14.1.** Adding Redis pub/sub would require a new infrastructure dependency (Redis), a new client library, and a non-trivial migration of the `publish`/`connect`/`disconnect` API. The school runs a single-worker EB deployment today; enforcing that with a clear startup error (mirroring the JWT_SECRET guard pattern) is low-cost, immediately testable, and leaves the migration path open (set `REDIS_URL`, swap `publish` for a broker path).

- **layaastat AC2 was already complete.** R9.3 (M9) had already added `_pending_tasks` and warning-level logging. Confirming it with a structural test (`test_layaastat_pending_tasks_set_exists`) is the right move — cheaper than re-implementing what's already there.

- **The school status cache design mirrors `ai_kill_switch.py` exactly** (module-level dict, `time.monotonic()` clock, 30s TTL, same helper names). This consistency makes the codebase easier to reason about.

## Issues found and fixed during implementation

### test_deactivated_school_returns_402 in test_multi_tenancy_enforcement.py — failed in full suite

Root cause: `test_no_school_doc_passes_middleware` (which runs earlier in the same file) hits the DB for "school-a", finds no doc, caches `"active"`. The subsequent `test_deactivated_school_returns_402` adds a deactivated doc but the cache still has "active" — so the middleware never returns 402.

Fix: added an `autouse=True` function-scoped fixture to `conftest.py` that calls `_clear_school_status_cache()` before every test. This is the correct approach: the cache is a process-level side effect that should not bleed between tests.

## Risk areas and mitigations

| Risk | Mitigation |
|------|-----------|
| School status cached as "active" for up to 30s after an operator deactivates it | Documented in module comment; acceptable for a safety brake (max 30s window, same as kill-switch TTL). Operators deactivating schools are not doing it for real-time lockout — it's a billing action. |
| `validate_multi_worker_config()` reads `WEB_CONCURRENCY` at import time vs. call time | The function reads the env var at call time (inside the function body), so monkeypatching in tests works correctly. |
| Tests that rely on the school status DB path will now always hit a cold cache on each test | Resolved by the autouse fixture. DB path tests in `test_multi_tenancy_enforcement.py` re-seed `_fake_db.schools.docs` per test as before. |

## Architectural notes

- **Cache invalidation not implemented on school update.** When an operator updates a school's status via the operator panel, the in-process cache for that school will remain stale for up to 30 seconds. This is documented as acceptable in the module comment. If immediate invalidation is needed (e.g. emergency deactivation), an operator can restart the process or add an explicit `_clear_school_status_cache(school_id)` call to the update endpoint.

- **`_clear_school_status_cache()` is also available for explicit invalidation** from the operator endpoint or tests. It's a public helper (underscore prefix is conventional, not enforced in Python).

## Recommendation for Abhimanyu/Shubham

Both stories are complete and tested. The EB deployment constraint (WEB_CONCURRENCY=1) is now enforced at startup rather than being an implicit assumption. If you ever want to scale horizontally:
1. Stand up a Redis instance (ElastiCache or similar)
2. Set `REDIS_URL` in the EB environment
3. Swap `publish()` in `sse.py` for a redis pub/sub fan-out (the connect/disconnect remain per-worker)

The startup guard will stop blocking as soon as `REDIS_URL` is present.
