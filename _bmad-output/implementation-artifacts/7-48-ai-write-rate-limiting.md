# Story 7.48: AI Write Rate Limiting

Status: done
Epic: 7 (Growth Features / Phase 2)
Priority: High (Phase 1 known gap — fast-tracked if compromise detected)
Effort: Small-Medium
Created: 2026-05-15
PRD: Phase 2 Growth — "AI write rate limiting"; Phase 1 known risk

## Story

**As** the EduFlow system,
**I want** to enforce per-session, per-role hourly rate limits on AI-executed write mutations,
**so that** a compromised or misconfigured session cannot mass-mutate school data via the AI dispatch path.

## Business Context

EduFlow's AI confirm-and-dispatch path (`POST /api/chat/confirm`) executes server-issued write tokens. Today, a single authenticated session can fire unlimited confirms — a known Phase 1 risk flagged for fast-tracking if a compromise is detected. Rate limiting closes that gap before pilot scale.

## Acceptance Criteria

1. **AC1 — Rate-limit config per role.** A `backend/config/ai_rate_limits.yaml` file defines per-role hourly write-dispatch ceilings. Defaults: `owner: 50`, `principal: 30`, `accountant: 20`, `admin: 20`, `teacher: 10`, `student: 0`. The loader is hot-tolerant — config changes pick up on next request without server restart.

2. **AC2 — Enforcement at the confirm endpoint.** Both `POST /api/chat/confirm` and `POST /api/chat/conversations/{conv_id}/confirm` enforce the limit **before** consuming the confirm token. When the limit is reached, the endpoint returns **HTTP 429** with a `Retry-After` header (seconds until the next hour boundary) and a JSON body `{ "success": false, "error": "rate_limit_exceeded", "retry_after_seconds": <int>, "limit": <int>, "window": "hour" }`.

3. **AC3 — Counter storage with hourly reset.** Rate-limit counters live in MongoDB collection `ai_rate_limit_counters`, keyed by `(user_id, session_id, hour_bucket)` where `hour_bucket` is the UTC hour the request landed in (e.g., `"2026-05-15T14:00:00Z"`). Each document has `expires_at = hour_bucket + 65 minutes` with a TTL index so counters are auto-purged. **Reset is by hour boundary, not rolling window** — exactly as spec'd.

4. **AC4 — Audit log captures rate-limit hits.** Every `ai_dispatch_audit_log` entry includes a `rate_limit_hit: bool` field. Rate-limited (rejected) requests **MUST** still produce an audit log entry with `rate_limit_hit: true`, `success: false`, and no `result`/`executed_at`.

5. **AC5 — Frontend 429 handling.** `ConfirmActionCard.js` parses the 429 response, reads `Retry-After`, shows a user-facing toast/inline message `"Too many AI actions — please wait X minutes"` (rounded up, minimum 1), disables the confirm button until `Retry-After` elapses, and re-enables it automatically. The cancel button remains enabled. The card transitions to `status: 'rate_limited'` (new status) and renders an amber/red border.

6. **AC6 — Operator override endpoint.** `PATCH /api/operator/schools/:school_id/ai-rate-limit` accepts `{ "role": "<role>", "limit": <int>, "reason": "<string>", "expires_at": "<ISO8601 | null>" }`. Owner-only. Writes to `ai_rate_limit_overrides` collection; resolver checks overrides before falling back to YAML defaults. An override with `expires_at` in the past is ignored.

7. **AC7 — Per-session AI action count read API.** `GET /api/operator/ai-action-counts?user_id=&session_id=` returns the current-hour counter and the configured limit for any session the caller can see. Owner-only. (UI panel deferred to Story 7-43; this endpoint just exposes the data.)

8. **AC8 — Backward compatibility.** Existing successful dispatches still write to `ai_dispatch_audit_log` with `rate_limit_hit: false`. Existing tests pass without modification (except the audit-log shape check, which gets updated to require the new field).

## Tasks / Subtasks

- [x] **T1. Config layer** (AC: #1)
  - [x] Create `backend/config/ai_rate_limits.yaml` with default per-role limits
  - [x] Add `backend/services/ai_rate_limiter.py` with mtime-cached YAML loader
  - [x] Add `pyyaml>=6.0.1` to `backend/requirements.txt`
- [x] **T2. Counter service** (AC: #3)
  - [x] `increment_and_check` uses `find_one_and_update` with `$inc` + `$setOnInsert` (falls back to `update_one`+`find_one` if the driver lacks `find_one_and_update`)
  - [x] `hour_bucket` and `seconds_until_next_hour` helpers
  - [x] Migration `015_ai_rate_limit_counters.py` creates the unique compound index + TTL index
- [x] **T3. Override resolver** (AC: #6)
  - [x] `resolve_limit(role, school_id, db)` reads `ai_rate_limit_overrides` (most recent unexpired), falls back to YAML default
  - [x] Migration `015` also indexes the overrides collection (school+role+created_at) and adds sparse TTL on `expires_at`
- [x] **T4. Audit log shape change** (AC: #4, #8)
  - [x] `audit_ai_dispatch` now accepts and persists `rate_limit_hit: bool` (default False)
  - [x] New `audit_ai_rate_limit_hit` helper writes rejection rows (`executed_at=None`, `success=False`, `rate_limit_hit=True`, `rate_limit_value=<limit>`, `rejected_at=<utc>`)
- [x] **T5. Confirm endpoint enforcement** (AC: #2, #4)
  - [x] `_execute_confirmed_dispatch` runs the rate-limit gate **before** `consume_confirm_token` — rejected requests do NOT burn the token
  - [x] 429 responses use `JSONResponse(status_code=429, headers={"Retry-After": str(secs)})` (HTTPException can't set custom headers)
  - [x] Internal `RateLimitExceeded` sentinel exception keeps the dispatch helper's happy-path signature intact
  - [x] `peek_confirm_token` helper added so the rejection audit row gets the real tool_name and params without consuming the token
- [x] **T6. Operator endpoints** (AC: #6, #7)
  - [x] New `backend/routes/operator.py` with `PATCH /api/operator/schools/{school_id}/ai-rate-limit` and `GET /api/operator/ai-action-counts`. Owner-only via `_require_owner` shared helper
  - [x] Router registered in `backend/server.py`
- [x] **T7. Frontend 429 handling** (AC: #5)
  - [x] `ConfirmActionCard.js::handleClick` recognises `res.status === 429`, parses `Retry-After` (with body fallback), transitions to new `'rate_limited'` status
  - [x] Amber inline notice with minute-rounded countdown; auto-flip back to `'pending'` when the cooldown hits zero
  - [x] Confirm button locked during cooldown; cancel button remains live
- [x] **T8. Tests** (AC: #1–#8)
  - [x] `tests/backend/services/test_ai_rate_limiter.py` — 15 unit tests covering bucket math, resolver precedence (default / override / expired / DB error), increment behavior, hour reset, session isolation, payload shape
  - [x] `tests/backend/api/test_chat_confirm_rate_limit.py` — 4 integration tests: 429 + Retry-After contract, token-not-consumed-on-rejection, audit-row written with `rate_limit_hit=True`, next-hour counter reset
  - [x] `tests/backend/api/test_operator_rate_limit_override.py` — 8 tests: 403 for non-owner, role/limit/reason validation, override persists + takes effect, expired override ignored, count endpoint returns current-hour data
  - [x] FakeCollection extended with `find_one_and_update` to support the rate limiter's atomic upsert pattern
- [x] **T9. Documentation** (AC: all)
  - [x] No README change needed — operator endpoints are internal-use only; story file is the contract

## Dev Notes

### Existing AI dispatch path (READ BEFORE EDITING)

- **`backend/routes/chat.py:1560–1629` — `_execute_confirmed_dispatch`** is the single funnel. Both `POST /chat/confirm` (`:1632`) and `POST /chat/conversations/{conv_id}/confirm` (`:1652`) call it. Inject the rate-limit check **here**, not in each route handler, so we have one code path.
- **`backend/services/confirm_tokens.py`** holds `issue_confirm_token`, `consume_confirm_token`, `audit_ai_dispatch`. The audit function (`:120–146`) is where the new `rate_limit_hit` field lands. Existing `audit_ai_dispatch` callers pass `result` keyword-only — preserve that signature, add `rate_limit_hit: bool = False` as a new keyword parameter so existing callers don't break.
- **Token consumption is atomic and one-shot.** Place the rate-limit check **before** `consume_confirm_token`. If we placed it after, a rate-limited request would burn the user's confirm token and force them to re-prompt the AI to issue a new one — bad UX.

### Counter storage decision

Hourly buckets, not rolling window — this matches the AC and is simpler:
- Key: `(user_id, session_id, hour_bucket)`
- Bucket format: `2026-05-15T14:00:00Z` (UTC, minute-and-second zeroed)
- TTL: `expires_at = hour_bucket + 65 minutes`. The 5-minute slack handles MongoDB TTL monitor's ~60s sweep interval and clock skew.

Atomic increment pattern (Motor):
```python
res = await db.ai_rate_limit_counters.find_one_and_update(
    {"user_id": user_id, "session_id": session_id, "hour_bucket": bucket},
    {
        "$inc": {"count": 1},
        "$setOnInsert": {"expires_at": bucket_dt + timedelta(minutes=65), "created_at": now},
    },
    upsert=True,
    return_document=ReturnDocument.AFTER,
)
new_count = res["count"]
```
The single atomic op gives us correctness under concurrent confirms in the same session.

### Override precedence

`resolve_limit(role, school_id, db)`:
1. Query `ai_rate_limit_overrides`: `{ school_id, role, $or: [{expires_at: None}, {expires_at: {$gt: now}}] }`, sort `created_at desc`, limit 1.
2. If found, return `override.limit`.
3. Else, return YAML default for that role.

YAML is the source of truth for defaults — DO NOT seed defaults into MongoDB; the override collection only holds explicit operator overrides.

### YAML file structure (AC #1)

`backend/config/ai_rate_limits.yaml`:
```yaml
# Per-role hourly AI write-dispatch ceiling.
# Operator override via PATCH /api/operator/schools/{school_id}/ai-rate-limit.
roles:
  owner: 50
  principal: 30
  accountant: 20
  admin: 20
  teacher: 10
  student: 0
```

Loader caches by file `st_mtime` — re-reads on change without restart. Acceptable to add `pyyaml` to `requirements.txt` (already used elsewhere? — verify; if not present, install).

### Frontend rate_limited state (AC #5)

`ConfirmActionCard.js` already has `'pending' | 'loading' | 'confirmed' | 'cancelled' | 'error'` states. Add `'rate_limited'`:
- Reuse the amber palette already defined for the warning icon
- Countdown: `useEffect` re-running every second decrementing `secondsLeft`; when 0, flip back to `'pending'` and re-enable confirm
- Message: `"Too many AI actions. Please wait {Math.ceil(secondsLeft / 60)} minute(s)."`
- Keep the cancel button enabled so users can dismiss the action

DO NOT add a global rate-limit error to the toast system — keep the message in-card to preserve the action context.

### Operator endpoint scoping (AC #6, #7)

There's no `routes/operator.py` yet. Create one with the same pattern as `routes/settings.py`:
- `from fastapi import APIRouter, Request, HTTPException`
- `router = APIRouter(prefix="/api/operator", tags=["operator"])`
- Use `get_current_user(request)` and assert `user["role"] == "owner"`. If not, raise `HTTPException(403, "Owner-only endpoint")`.
- Register in `server.py` near the other route imports.

### Migration 015

`backend/migrations/015_ai_rate_limit_counters.py`:
- Create collection `ai_rate_limit_counters` (implicit on first insert; just create indexes)
- Index: `{ user_id: 1, session_id: 1, hour_bucket: 1 }` unique
- TTL index: `{ expires_at: 1 }` with `expireAfterSeconds: 0`
- Create collection `ai_rate_limit_overrides`
- Index: `{ school_id: 1, role: 1, created_at: -1 }`
- TTL index: `{ expires_at: 1 }` with `expireAfterSeconds: 0` (sparse — entries without expiry are not auto-deleted)

Add to `run_all.py` migration list.

### Testing standards

Per `_bmad-output/project-context.md`: tests live in `tests/backend/...`, use pytest + `httpx.AsyncClient` for route tests, mock MongoDB with `mongomock_motor` where it exists in conftest. Hour-bucket tests should mock `datetime.now()` via `freezegun` or by patching `_now()` in the rate limiter module — keep the rate limiter's now-resolver pluggable (e.g., `_now = staticmethod(lambda: datetime.now(timezone.utc))`).

### Out of scope

- The operator UI panel for viewing per-session counts → Story 7-43.
- A frontend dashboard for managing overrides → out of scope; the PATCH endpoint is internal-use via `curl`/Postman for now.
- Cross-session aggregation (per-user, not per-session) → AC explicitly scopes counters to `(user_id, session_id, hour)`. Different sessions for the same user have independent counters.

### References

- [Source: backend/routes/chat.py#L1560-L1629] — `_execute_confirmed_dispatch` (single injection point)
- [Source: backend/services/confirm_tokens.py#L120-L146] — `audit_ai_dispatch` (add `rate_limit_hit` field)
- [Source: frontend/src/components/ConfirmActionCard.js#L117-L155] — `handleClick` (add 429 branch)
- [Source: _bmad-output/planning-artifacts/architecture.md#4-data-models--collections] — collection naming + UUID4 ID strategy
- [Source: _bmad-output/implementation-artifacts/stories.md#L1162-L1180] — original story specification

## Project Structure Notes

All new files align with existing layout:
- `backend/config/ai_rate_limits.yaml` (new — first config-yaml file; introducing a `backend/config/` convention is acceptable, alternative is `backend/ai_rate_limits.yaml` at root — prefer `config/` subdir for clarity)
- `backend/services/ai_rate_limiter.py` (consistent with `confirm_tokens.py`, `idempotency.py`, etc.)
- `backend/routes/operator.py` (new namespace; sibling to `settings.py`)
- `backend/migrations/015_ai_rate_limit_counters.py` (next migration number)
- `tests/backend/services/test_ai_rate_limiter.py` + `tests/backend/api/test_chat_confirm_rate_limit.py` + `tests/backend/api/test_operator_rate_limit_override.py`

No naming variances. No conflicts with existing modules.

## Previous Story Intelligence

Most recent AI-layer story is `4-20-ai-graceful-degradation` (done). Lessons applied here:
- AI confirm path treats infrastructure errors as fail-closed — the rate limiter follows the same discipline: any unexpected DB error in `increment_and_check` returns a 503 with a clear message and an audit row, never silently bypasses the limit.
- Recent commit `ab16cf3 Harden Eduflow AI layer` and `ba31ac7 Harden AI write confirmation requirements` reinforced the principle that **rate-limit enforcement and audit logging are coupled** — every rejection is logged, no silent drops.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — Claude Code CLI

### Debug Log References

- **Default-arg pitfall:** initial pass bound `_now` as a default function argument; pytest `monkeypatch.setattr(module, "_now", ...)` did not propagate because Python evaluates default args at definition time. Switched all `now_fn` defaults to `Optional[Callable] = None` with a `(now_fn or _now)()` resolution at call time, restoring monkeypatchability without changing the public contract.
- **Test isolation:** `_fake_db` is a module-level singleton in `tests/backend/conftest.py`. Added autouse fixtures in both rate-limit test modules to clear `ai_rate_limit_*`, `ai_dispatch_audit_log`, and `confirm_tokens` collections between tests so persisted state from earlier tests doesn't leak.
- **Token preservation on rejection:** rate-limit gate intentionally runs before `consume_confirm_token` — the dedicated `test_rate_limited_request_does_not_burn_confirm_token` verifies the token row still has `used: False` after a 429.

### Completion Notes List

- All 8 ACs satisfied; all 9 task groups complete.
- 27 new tests added (15 unit + 4 chat-confirm integration + 8 operator endpoint). Full backend suite: **148 passed, 0 failed**.
- Rate-limit check is the FIRST operation in `_execute_confirmed_dispatch`, ensuring rejected requests do not consume the confirm token.
- `find_one_and_update` is preferred when available (real Mongo / Motor); falls back to `update_one(upsert=True)` + `find_one` otherwise so the limiter works in test environments and on drivers without `find_one_and_update`.
- The pre-existing audit-log shape (`ai_dispatch_audit_log`) gained a `rate_limit_hit: bool` field; pre-existing successful dispatches now write `rate_limit_hit: False`. No reads of this collection in the codebase depend on the previous schema (verified by grep).
- Operator endpoints (`PATCH /api/operator/schools/:id/ai-rate-limit`, `GET /api/operator/ai-action-counts`) are owner-gated. Story 7-43 will consume the GET endpoint when the operator health dashboard ships.
- Frontend `rate_limited` status reuses the existing amber palette and warning iconography. Confirm button is locked during cooldown; cancel button remains live so users can dismiss the action.

### File List

**New files**
- `backend/config/ai_rate_limits.yaml` — per-role hourly defaults (owner: 50, principal: 30, accountant/admin: 20, teacher: 10, student: 0)
- `backend/services/ai_rate_limiter.py` — limiter service (config loader, time helpers, `resolve_limit`, `increment_and_check`, `get_current_count`)
- `backend/routes/operator.py` — owner-only override + counts endpoints
- `backend/migrations/015_ai_rate_limit_counters.py` — collection indexes + TTL
- `tests/backend/services/__init__.py`
- `tests/backend/services/test_ai_rate_limiter.py` — 15 unit tests
- `tests/backend/api/test_chat_confirm_rate_limit.py` — 4 integration tests
- `tests/backend/api/test_operator_rate_limit_override.py` — 8 endpoint tests

**Modified files**
- `backend/services/confirm_tokens.py` — `audit_ai_dispatch` gains `rate_limit_hit` field; new `audit_ai_rate_limit_hit` and `peek_confirm_token` helpers
- `backend/routes/chat.py` — `_execute_confirmed_dispatch` gains rate-limit gate; both confirm endpoints translate `RateLimitExceeded` into 429 + `Retry-After`
- `backend/server.py` — registers `operator_router`
- `backend/migrations/run_all.py` — registers migration 015
- `backend/requirements.txt` — adds `pyyaml>=6.0.1`
- `frontend/src/components/ConfirmActionCard.js` — adds `rate_limited` status with countdown UI; 429 handling in `handleClick`
- `tests/backend/conftest.py` — registers `operator_routes`, adds `find_one_and_update` to FakeCollection, adds `ai_rate_limit_counters` + `ai_rate_limit_overrides` + `messages` + `conversations` to FakeDb

## Senior Developer Review (AI)

**Reviewers:** Blind Hunter + Edge Case Hunter + Acceptance Auditor (parallel)
**Date:** 2026-05-15
**Outcome:** Approve (after patches)

### Action Items

- [x] **[High]** schoolId source — fall-back to caller-supplied `user.schoolId` allowed override resolution to be spoofed. Now sourced unconditionally from `tenant.get_school_id()`.
- [x] **[High]** Session-id rotation bypass — counter was keyed on `(user_id, session_id, hour_bucket)`. A client rotating session_ids could open a fresh counter per request. Re-keyed to `(user_id, hour_bucket)`; session_id is retained in audit log entries only. Migration unique index updated accordingly.
- [x] **[Medium]** Counter inflation past limit — repeated rejected attempts kept `$inc`-ing the counter, skewing the operator dashboard. Added a pre-check: if `count >= limit`, return rejection without incrementing.
- [x] **[Medium]** Override "upsert" was actually insert — multiple PATCHes left a growing pile of "active" rows with non-deterministic tie-breaking. Now marks prior unexpired rows for the same (school, role) as `superseded=true` before inserting; resolver filters them out.
- [x] **[Medium]** Invalid token still burned rate slot — an attacker firing bogus tokens could DoS a user's hourly quota. Token ownership is now validated (via `peek_confirm_token`) BEFORE the rate counter is touched.
- [x] **[Low]** `peek_confirm_token` excluded used tokens, losing replay forensics — now returns the doc regardless of `used`; caller checks `used` flag separately.
- [x] **[Low]** AC5 message string used a period instead of the spec's em-dash — aligned: "Too many AI actions — please wait X minute(s)".
- [x] **[Low]** Cancel button styling logic compounded checks confusingly — refactored to an explicit `isLocked = isConfirm ? (loading or rate_limited) : (loading)` branch.
- [x] **[Low]** `onMouseEnter`/`onMouseLeave` hover logic was inconsistent with the disabled state — both now gate on the same `buttonLocked` predicate.

### Deferred (not in scope of 7-48)

- **[Defer]** Migration 014 (`014_ensure_maintenance_user`) is absent from `run_all.py`. Pre-existing — `run_all.py` already jumped from 013 → ... before this story. Filed for follow-up but not this story's responsibility.
- **[Defer]** `ALLOWED_ROLES` includes `student` (YAML floor is 0). An owner could in theory raise students' limit via override. Flagged for product decision; current behavior is intentional flexibility.

### Dismissed

- `pyyaml` "no usage in patch" — false positive; it's used in the new `ai_rate_limiter.py` file.
- `RateLimitExceeded.__init__` defensive None check — payload always comes from `RateLimitResult.to_response_payload()` which is a dict.
- Copy-pasted try/except across the two confirm endpoints — only 2 sites, factoring out adds complexity without payoff.
- Audit row nullable `executed_at`/`confirmed_at` for downstream consumers — consumer responsibility.

### Patches applied — added tests

- `test_invalid_token_does_not_burn_rate_slot` — 400 on bogus token, counter unchanged
- `test_session_rotation_cannot_bypass_user_limit` — two sessions for the same user share one counter, both trip 429 at limit
- `test_counter_does_not_inflate_past_limit_on_rejected_retries` — 5 rejected attempts leave count == limit (50), not 55
- `test_override_supersedes_previous_active_rows` — fresh PATCH marks prior row superseded; resolver returns newest active

**Final test count:** 31 rate-limit tests; **152/152 backend tests pass.**

## Change Log

- 2026-05-15 — Implementation complete; story moved to `review`. 27 tests added, 148/148 backend tests pass.
- 2026-05-15 — Code review patches applied (5 functional fixes + 4 cosmetic). Counter re-keyed per-user (no session). 4 new tests. 152/152 backend tests pass.
