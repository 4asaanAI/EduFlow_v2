# Part 1 (Auth + RBAC) — Review Findings + Fix Plan

**Created:** 2026-05-15
**Status:** ⏸️ paused for fresh-context fix session
**User decision:** Fix everything before moving on (including the 126-route helper migration)

## How to resume in a new session

1. Read this file first (you're doing it now)
2. Read `_bmad-output/parts/auth-rbac/scope.md` for the original Part 1 scope
3. Read `_bmad-output/platform-quality-sweep.md` for the master sweep tracker
4. Read `_bmad-output/project-context.md` (Auth+RBAC section especially)
5. Confirm git state: `git log -1` should show `f92d77d Part 1 (Auth + RBAC) hardening: close 12 quality concerns` on main
6. Confirm tests: `python -m pytest tests/backend/ --tb=short` should show **224 passed** (baseline)
7. Begin patches in the order below (A → P). After each cluster, run the test suite to catch regressions.

## Current state

- **Branch:** `main`
- **Last commit:** `f92d77d` (pushed to origin)
- **Tests baseline:** 224/224 backend tests passing
- **Tracker entry:** `platform-quality-sweep.md` Part 1 currently marked ✅ done — **this is wrong, downgrade to 🟡 partially-done before pushing fixes**
- **Working tree:** clean

## Context: what's already done

Part 1 closed these (verified):
- `scope_resolver` no longer falls through to `type="all"` for admin with no sub_category
- `_resolve_admin_scope` denies-by-default on missing sub_category
- `can_see_financial_data` legacy-admin path removed
- Migration 016 backfills `support_staff` for legacy admin rows (auth_users + staff)
- `require_role`, `require_owner`, `require_owner_or_principal` dependencies added in `backend/middleware/auth.py`
- Sanitized error: 403s now say `"Forbidden"` (no role-list leak) **— only in new helpers**
- `secrets.token_urlsafe(48)` per-process dev JWT secret
- Refresh cookie path widened from `/api/auth` to `/`
- `scoped_query(query, branch_id=..., school_id=...)` helper in `backend/tenant.py`
- 48 new `scope_resolver` tests in `tests/backend/services/test_scope_resolver.py`
- 3 new refresh-race tests in `tests/backend/unit/test_auth_tokens.py`
- Docs updated in `project-context.md` (JWT staleness, access-token revocation, dead `otps` collection)

What's NOT done (why we're here):
- See the patch list below

## Three reviewers ran in parallel

1. **Adversarial-general** — found H1–H5 (5 high), M1–M7 (7 medium), L1–L3 (3 low)
2. **Edge case hunter** — found 17 issues across method-driven boundary analysis
3. **Party mode** (5 personas: Security Architect, Engineer, QA, PO, Maintainer) — consensus blocker: helper adoption is 3%, tracker overstates completion

## Patches required (in order)

### Patch A — Wire `Depends(require_owner)` into `operator.py` endpoints

**Severity:** High
**Files:** `backend/routes/operator.py`
**Problem:** `Depends(require_owner)` was imported but never used. Every endpoint still calls `_require_owner(request)` inline. The "audit by single grep" promise fails.

**Fix:**
- Change each operator endpoint signature to receive `user: dict = Depends(require_owner)` parameter
- Delete the inline `user = _require_owner(request)` calls in endpoint bodies
- Delete the local `_require_owner` function (unused after migration) OR keep it `@deprecated` if any internal caller still uses it (verify with grep)
- Endpoints to migrate:
  - `PATCH /schools/{school_id}/ai-rate-limit` → `upsert_ai_rate_limit_override`
  - `GET /ai-action-counts` → `get_ai_action_counts`

**Acceptance:**
- `grep -n "_require_owner\|get_current_user.*operator" backend/routes/operator.py` shows only the `Depends(require_owner)` form
- All existing operator tests still pass
- New assertion: at least one test verifies the dependency is what enforces, not a body check

---

### Patch B — Sanitize remaining "Owner only" / "Owner-only" strings

**Severity:** High
**Files:** `backend/routes/exports.py`, `backend/routes/settings.py`, `backend/routes/students.py`
**Problem:** 3 routes still respond with `"Owner only"` — attacker enumerating endpoints distinguishes owner-gated from generic 403.

**Fix:**
- Grep: `grep -rn '"Owner only"\|"Owner-only"' backend/routes/`
- Replace each with `"Forbidden"` (or migrate the route to `Depends(require_owner)` if straightforward)
- Add a test that asserts no `"Owner only"` substring exists in source — e.g., a meta-test in `tests/backend/test_error_message_hygiene.py`

**Acceptance:**
- `grep -rn '"Owner only"\|"Owner-only"' backend/routes/` returns zero
- All affected routes still return 403 for unauthorized users
- Meta-test passes

---

### Patch C — Make the concurrent refresh test actually concurrent

**Severity:** High
**Files:** `tests/backend/unit/test_auth_tokens.py` (test_concurrent_refresh_only_one_succeeds) AND its local `FakeCollection`
**Problem:** The local `FakeCollection.update_one` is `async def` with no `await` points, so `asyncio.gather` runs the two consume_refresh_token coroutines sequentially. The test passes for the wrong reason.

**Fix options (pick one):**
- (a) Inject `await asyncio.sleep(0)` between `find_one` and `update_one` in `consume_refresh_token` itself (this is the real-Motor behavior — Motor yields to the loop at every I/O point). Then update the local FakeCollection's `update_one` to also `await asyncio.sleep(0)` at the start, so the second coroutine actually preempts.
- (b) Build a stub `RaceyCollection` whose `find_one` and `update_one` await an `asyncio.Event` controlled by the test, deterministically interleaving the two consumers.
- (c) Demote the test claim — rename to `test_sequential_refresh_reuse_rejected` and add a real-Motor integration test elsewhere (gated on `RUN_INTEGRATION_TESTS=1`).

**Recommended:** (b) — gives deterministic interleaving without changing production code timing.

**Acceptance:**
- The test fails if you change `consume_refresh_token`'s atomic guard from `update_one({"_id": ..., "revoked_at": None})` to plain `update_one({"_id": ...})` (i.e., the test actually catches the race regression it claims to catch)
- Test name accurately describes what's tested

---

### Patch D — Migration 016 audit-row idempotency

**Severity:** High
**Files:** `backend/migrations/016_admin_sub_category_default.py`
**Problem:** Audit insert uses fixed `id="migration-016-admin-sub-category-default"`. Re-running raises `DuplicateKeyError` (if unique index) or duplicates the audit row (if not).

**Fix:**
```python
# Replace:
await db.audit_logs.insert_one({"id": "migration-016-...", ...})
# With:
await db.audit_logs.update_one(
    {"id": "migration-016-admin-sub-category-default"},
    {"$set": {<the fields>}, "$setOnInsert": {"first_run_at": datetime.now(timezone.utc).isoformat()}},
    upsert=True,
)
```

Also fix Patch P (hard-coded timestamp) in the same edit — use `datetime.now(timezone.utc).isoformat()` everywhere the migration stamps a date, not the literal `"2026-05-15T00:00:00Z"`.

**Acceptance:**
- Migration runs twice in a row without error
- audit_logs has exactly one row with `id="migration-016-..."`
- Timestamps reflect real run time

---

### Patch E — Empty-string `user_id` permissiveness in `can_see_personal_info`

**Severity:** High
**Files:** `backend/ai/scope_resolver.py`
**Problem:** `Scope.user_id` defaults to `""` (line ~130). `can_see_personal_info` checks `target_id == self.user_id` — empty string matches empty string, so any Scope built without explicit `user_id` becomes an oracle.

**Fix:**
- In `can_see_personal_info`: change `if target_id == self.user_id:` to `if target_id and target_id == self.user_id:`
- Also: in `Scope.__post_init__` (add one if not present), raise `ValueError` if `user_id == ""`
- In `Scope.filter()` self-only branch: similarly guard `{"user_id": self.user_id}` against empty string

**Acceptance:**
- New unit test in `test_scope_resolver.py` that constructs `Scope(user_id="")` and asserts ValueError (or filter returns a fail-closed sentinel)
- Existing tests still pass after adding the guard

---

### Patch F — Phantom legacy `/api/auth` refresh cookie cleanup

**Severity:** Medium (operationally High — affects every existing user)
**Files:** `backend/services/auth_tokens.py`
**Problem:** Pre-deploy users have cookies at `path=/api/auth`. After the path change to `/`, browsers store BOTH cookies. `clear_refresh_cookie` only clears the new path. Old cookies leak for 7 days; logout/login loops possible.

**Fix:**
- In `clear_refresh_cookie`, issue TWO `response.delete_cookie` calls — one with `path="/"` and one with `path="/api/auth"`
- Same dual-clear at the start of `/api/auth/refresh` to evict any phantom cookie before reading
- Add a code comment with a "remove after 2026-08-15" deadline (7 days after deploy day + buffer)

**Acceptance:**
- Test that calls logout, then verifies both delete-cookie headers in the response
- Live test (manual or playwright) confirms a user with both cookies can still logout cleanly

---

### Patch G — Downgrade tracker honestly + adopt `require_role` across all routes

**Severity:** Blocker (consensus across all 3 reviewers)
**Files:** `_bmad-output/platform-quality-sweep.md`, then every route file in `backend/routes/`
**Problem:** Tracker says Part 1 is ✅ done. Scope doc's flagship deliverable ("single canonical role-check path, auditable by grep") is unmet — 126 inline `if user["role"] not in [...]` checks remain. Helper adoption is 4/130 routes (3%).

**Two-step fix:**

**Step G1 — honest tracker:** Update `platform-quality-sweep.md` Part 1 entry to:
- Status: 🟡 partially done
- Note: "Concerns 2–12 closed. Concern 1 (helper adoption) deferred to in-progress Part 1.5. Until then DO NOT mark Part 1 ✅ done."

**Step G2 — route migration:** Migrate every inline role check to `Depends(require_role/require_owner/require_owner_or_principal)`. Approach:

1. Get the full inventory:
   ```bash
   grep -rn 'if user\["role"\] not in\|if user.get("role") not in' backend/routes/
   ```
2. For each match, classify by pattern:
   - Single role check (`role == "owner"`) → `Depends(require_owner)` or `require_role("owner")`
   - 2-role check (`role in ["owner", "admin"]`) → `Depends(require_role("owner", "admin"))`
   - sub_category check (`role == "admin" and sub_category == "principal"`) → `Depends(require_owner_or_principal)`
   - More complex (multi-sub_category, conditional logic) → leave a helper-with-tests, then `Depends`-wrap it
3. Migrate file-by-file (operator.py, reports.py already done):
   - `exports.py` (7 inline checks)
   - `staff.py` (8 checks + `_can_manage`/`_is_owner_or_principal` helpers)
   - `fees.py` (~18 checks)
   - `attendance.py` (~10 checks)
   - `operations.py` (multiple — keep `_can_decide` as alias to `require_owner_or_principal`)
   - `issues.py` (~6 checks)
   - `activities.py` (uses `_require_manage` + `READ_ROLES` — wrap)
   - `students.py`, `settings.py`, `tools.py`, `notifications.py`, `audit.py`, `chat_upload.py`, `import_data.py`, `assistant.py`, `image_gen.py`, `tokens.py`, `search.py`, `queries.py`, `academics.py`, `sms.py`
4. For each migrated file: run that file's tests after the change. Stop on first regression — root-cause, fix, continue.

**Acceptance:**
- `grep -rn 'if user\["role"\] not in\|if user.get("role") not in' backend/routes/` returns zero (or a single explicit allowlist file with comments)
- All 224 backend tests still pass
- New meta-test: assert that every route handler has either a `Depends(require_*)` parameter OR an explicit comment `# auth: <reason>` (catches regressions)

---

### Patch H — Add behavior tests for `scope_resolver`, not just shape tests

**Severity:** Medium
**Files:** `tests/backend/api/test_scope_resolver_behavior.py` (new)
**Problem:** Existing 48 scope_resolver tests verify `scope.filter()` returns the right dict shape but never verify a route actually applies that filter. Routes ignoring the scope would pass every test.

**Fix:**
- Add 6–10 integration tests that:
  1. Seed `students`, `fee_transactions`, `student_attendance` for two different classes
  2. Log in as `class_teacher` of class A
  3. Hit `/api/students` or equivalent
  4. Assert response contains only class-A students (not class-B)
  5. Repeat for `accountant` on fees (should see all), `subject_teacher` on attendance, etc.

**Acceptance:**
- At least 3 routes have direct RBAC-enforcement tests (not just 403/200 gates)
- Tests fail if a future refactor accidentally drops `scope.filter()` from a query

---

### Patch I — Add unit tests for `scoped_query`

**Severity:** Medium
**Files:** `tests/backend/unit/test_tenant.py` (probably exists — extend) or `test_scoped_query.py` (new)
**Problem:** `scoped_query` is a new tenancy primitive with no direct tests. Only `students.py` calls it; if buggy, only students.py is the canary.

**Fix — at minimum these test cases:**
- `scoped_query(None, branch_id="b1")` — works, returns queryable dict
- `scoped_query({}, branch_id="b1")` — same
- `scoped_query({"name": "x"}, branch_id="b1")` — composes correctly
- `scoped_query({"branch_id": "b2"}, branch_id="b1")` — **should raise** (cross-branch attempt) per Patch M below
- `scoped_query({"$or": [...]}, branch_id="b1")` — composes correctly with $or
- `scoped_query({"$and": [{"branch_id": "b2"}]}, branch_id="b1")` — must detect nested branch_id (Patch M)
- Empty-string `branch_id=""` — explicitly defined behavior (recommend: raise)
- `scoped_query({}, school_id="school-x", branch_id="b1")` — both axes applied

**Acceptance:**
- 8+ test cases; coverage report for `tenant.py` near 100%

---

### Patch J — Fix `designation: "Principal"` elevation path

**Severity:** High
**Files:** `backend/ai/scope_resolver.py`, `backend/migrations/016_admin_sub_category_default.py`
**Problem:** `_resolve_admin_scope` reads `(sub_category or designation or "").strip().lower()`. An admin with `sub_category=None` but `designation="Principal"` still gets `type="all"`. Migration 016 only inspects `sub_category`, not `designation`.

**Fix (two options):**

**(a) Strict mode** (preferred for enterprise): drop the `designation` fallback entirely. The resolver only honors `sub_category`. Migration 016 first inspects `designation` for legacy rows and promotes it to `sub_category` (normalized lowercase), then runs the existing backfill.

**(b) Defensive mode:** keep `designation` fallback but require it to match an allow-list (`{"principal", "accountant", "transport_head", "receptionist"}`), and log a warning each time it's used. Migration 016 surfaces a count of rows using the fallback so they can be migrated manually.

**Recommended:** (a). Cleaner future story.

**Acceptance:**
- New test in `test_scope_resolver.py`: admin with `designation="Principal"` and no sub_category → type="self_only" (under strict mode) — the regression the diff currently codifies
- Existing test `test_resolve_admin_designation_principal_fallback` updated or deleted accordingly
- Migration 016 emits a report of legacy `designation` values it normalized

---

### Patch K — `require_role` robustness

**Severity:** Low
**Files:** `backend/middleware/auth.py`
**Problem:**
- `require_role()` (empty tuple) denies every request silently
- `require_role` uses `user["role"]` (KeyError → 500) where peers use `.get()` (clean 403)

**Fix:**
- At the factory: `if not roles: raise ValueError("require_role() needs at least one role")`
- In the dependency: `user.get("role")` instead of `user["role"]`; if None → 403 "Forbidden"
- Mirror the same `.get` in `require_owner`

**Acceptance:**
- Unit tests for both error paths

---

### Patch L — `revoke_refresh_token` returns its outcome

**Severity:** Low
**Files:** `backend/services/auth_tokens.py`, any caller
**Problem:** No `modified_count` check; absorbs garbage. Password-reset misroutes silently.

**Fix:**
- Have `revoke_refresh_token` return `modified_count` (0 or 1)
- Callers can decide whether to log "token not found" — at minimum, logout endpoint should log a debug line on count==0
- `revoke_user_refresh_tokens` already returns count; verify callers actually log/use it

**Acceptance:**
- New test: revoke an unknown token → returns 0, logs at debug level

---

### Patch M — `scoped_query` defensive collision check

**Severity:** Low → Medium (security hardening)
**Files:** `backend/tenant.py`
**Problem:** Helper trusts caller-supplied `branch_id` if already in query (silent cross-branch read footgun). Doesn't recurse into `$and`/`$or`.

**Fix:**
- If the caller's query contains a `branch_id` that does NOT equal the parameter → raise `ValueError("scoped_query branch_id conflict: query has %r, parameter has %r")`
- If the caller's query has matching `branch_id` → return base unchanged with a debug log
- Walk `$and`/`$or` recursively to detect nested `branch_id`
- Treat empty-string `branch_id` the same as `None` (don't apply)

**Acceptance:**
- Tests in Patch I cover the conflict cases

---

### Patch N — JWT secret + multi-worker guidance

**Severity:** Low
**Files:** `backend/middleware/auth.py`, plus a README/.env.example note
**Problem:** Per-process random JWT secret breaks `uvicorn --reload` (every save invalidates sessions) and `gunicorn -w 4` (each worker has a different secret → unreproducible 401s in dev).

**Fix:**
- At startup, if `JWT_SECRET` env is unset AND any of (`WEB_CONCURRENCY > 1`, `os.environ.get("ENVIRONMENT") in ("staging", "preview")`) → raise startup error pointing to `.env.example`
- For `--reload` workflow: optionally cache the dev secret to `~/.cache/eduflow/dev_jwt_secret` (gitignored, file-mode 0600) and read it back on next process boot, so token survives across reloads
- Add `JWT_SECRET=...` to `.env.example` with instructions

**Acceptance:**
- Manual: `uvicorn --reload` doesn't invalidate active sessions on save
- Startup error if multi-worker + no env var

---

### Patch O — `operator.py` ALLOWED_ROLES sanity

**Severity:** Low
**Files:** `backend/routes/operator.py`
**Problem:** `ALLOWED_ROLES` constant mixes top-level roles (`owner`, `admin`) with sub_categories (`principal`, `accountant`, `student`). An override targeting `role="principal"` would never match because no user has role=principal — principals are admin+sub_category=principal.

**Fix:**
- Decide whether the override is keyed by `role` only or `(role, sub_category)`
- If role only: prune `ALLOWED_ROLES` to `{"owner", "admin", "teacher", "student"}`
- If keyed by role+sub_category: change the override schema (add `sub_category` field; resolver matches on both)

**Acceptance:**
- Tests: an override created targeting an invalid combination is rejected at PATCH time

---

### Patch P — Migration 016 real timestamp

**Severity:** Low
**Files:** `backend/migrations/016_admin_sub_category_default.py`
**Problem:** All "backfilled_at" timestamps are hard-coded `"2026-05-15T00:00:00Z"` regardless of when the migration runs.

**Fix:** Replace with `datetime.now(timezone.utc).isoformat()` — already covered by Patch D, repeated here for completeness.

**Acceptance:**
- Re-running the migration on a fresh DB produces realistic timestamps; same applies in CI

---

## Suggested ordering for the fix session

Run patches in this order so test failures are easy to isolate:

1. **P + D** together (migration cleanup; easy, isolated)
2. **K** (require_role robustness; small, surfaces other bugs)
3. **A** (operator.py wiring; canary for Patch G's pattern)
4. **B** (string sanitization; mechanical)
5. **E** (empty-string user_id; touches resolver — run tests after)
6. **J** (designation bypass; coordinated with migration 016 update)
7. **L + M** (token + scoped_query hardening)
8. **F** (cookie phantom cleanup)
9. **N + O** (dev secret + ALLOWED_ROLES)
10. **C** (concurrent refresh test rewrite)
11. **I** (scoped_query tests)
12. **H** (scope_resolver behavior tests)
13. **G2** (route migration — biggest, save for end with patches above proving the pattern)
14. **G1** (tracker update, after the actual work is done)

## Expected outcome

After all patches:
- All 16 findings closed
- 224 backend tests grows to ~280+ (new tests for behavior coverage, scoped_query, race patch, robustness)
- Master tracker: Part 1 honestly ✅ done
- Memory + project-context.md updated with whatever new patterns emerged
- Clean commit + push
- Ready to start Part 2 (AI Layer)

## Reviewer reports (full text, for reference)

The three reviewers' raw reports are not saved here — they were inline in the chat. Key consensus points:

**Consensus across all 3 reviewers:**
1. Helper adoption is 3% — Part 1's flagship goal unmet
2. Tracker overstates completion
3. Concurrent refresh test is false-positive

**Unique findings per reviewer:**
- Adversarial: H1 (operator wiring), H2 (3 stale strings), H4 (migration idempotency), H5 (designation bypass), M4 (cookie phantom), M5 (shape tests), M7 (silent revoke)
- Edge Case Hunter: #1/#16 (empty user_id), #4 (migration audit), #10 (cookie phantom), #11 (race test), #13/14 (require_role robustness)
- Party Mode: PO/Yara consensus on tracker honesty; QA on shape-vs-behavior tests; Dev on cookie zombie window
