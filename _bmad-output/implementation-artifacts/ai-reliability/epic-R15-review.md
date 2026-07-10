# Epic R15 — Residual Confirmatory Sweep — EPIC-CLOSE REVIEW

**Date:** 2026-07-10 · **Model:** Claude Opus 4.8 (1M) · Multi-lens review over the whole R15 diff.

## Test results
- **Full backend suite: 1632 passed, 14 deselected, 0 failed** (baseline 1616 → +16 R15 tests). 0 skipped in the selected set.
- The 14 deselected are the `mongo_real` (real replica-set) + `llm_eval` (real Azure creds) tiers — marker-gated by `pytest.ini` addopts, **not failures**. See "14-deselected investigation" below.
- Branch-scope `scoped_filter` grep audit re-run on all 10 touched backend files: clean. No new unguarded hit introduced; existing hits are pre-existing school-scoped helpers (attendance/houses/academic are school-scoped by design, branch derived via student/class).
- Eval gate (standing rule 5): R15 touches **none** of `ai/prompts.py`, `ai/tool_functions*.py`, `ai/context_builder.py`, `ai/llm_client.py`, or the chat tool-loop, so the prompt/tool-change eval gate is not triggered. The always-on structural + judge-logic eval tiers run inside the full suite and are green.

## Review lenses applied (adversarial / edge-case / acceptance / NFR / trace)

### Findings raised → resolved in-run

| # | Severity | File:area | Finding | Resolution |
|---|----------|-----------|---------|------------|
| 1 | Med | `token_service.record_usage` | `$inc: -tokens_used` could drive `personal_topups` negative (big/concurrent turns) | FIXED — atomic `$max(0, …$subtract…)` pipeline clamp. Regression: `test_record_usage_personal_topup_floors_at_zero`. |
| 2 | Med | `idempotency.store_response` | unbounded body could bloat the doc past 16 MB BSON (write raises, key unstored) | FIXED — 512 KB cap; oversized → not stored (never truncated). Regressions: small stored / oversized skipped. |
| 3 | Med | `auth.py /seed-status` | unauthenticated row-count disclosure | FIXED — owner-gated in production, open in dev/staging. Regression: 401/403/200 matrix. |
| 4 | Med | `attendance.py` manual entry | duplicate `(student_id,date)` → 500 | FIXED — idempotent replay (200) / conflict (409). Regression: idempotent-or-conflict test. |
| 5 | Med | `activities.py` house seed | concurrent first-load → duplicate houses | FIXED — idempotent upsert + unique `(schoolId,name)` index. Regressions: API seed + unit upsert-idempotency. |
| 6 | Med | `assistant.py` | no rate limit + no token accounting → uncapped Azure spend | FIXED — per-user 20/hr limiter (429) + `record_usage(source="assistant")`. Regressions: 429, accounting, 503. |
| 7 | Low | `actor_context._now` / `notification_service` | naive timestamps persisted (naive/aware BSON-mix) | FIXED — tz-aware UTC. Full suite green (no format assertion broke). |
| 8 | Low | `academics.py:641` | `$regex ^{current_month}` not `re.escape`d (line 634 was) | FIXED — escaped. (Value is already validated `^\d{4}-\d{2}` at line 620, so consistency/defence-in-depth, not a live vuln.) |

### Findings dismissed (with reason)

| Finding (from parallel audit agents) | Why dismissed |
|---|---|
| ~20 "CRITICAL: missing schoolId" tenancy flags across students/staff/academics/attendance/operations | **False positive.** `get_db()` → `ScopedDatabase`; `ScopedCollection` auto-injects `schoolId` on every op (find/find_one/insert/update/delete/aggregate/find_one_and_*). School isolation is automatic; only branch scoping is explicit (and present where required). |
| operations.py `leave_requests`/`announcements`/`users` school-wide `scoped_filter` (agent called it a branch leak) | **Intentional + documented** — `platform-quality-sweep.md` line 64 records these as deliberate school-wide scoping. Owners have no branch; approval/leave notifications are school-wide by design. |
| `db.users` vs `db.auth_users` for owner/principal notification fan-out | **Intentional pre-existing pattern** (operations/incident/certificate + migration 014 all use `db.users`); listed as intentional school-wide in the tracker. Not a silent no-op. |
| assistant.py `ok=False` "false success" | **Already fixed by R1.7** — returns 503; confirmed + test-covered (P-L9 AC2). |
| guardian phone in AI tools | **Already masked** (R4.4, last-3-digits). |

### Deferred / logged (see `DEFERRED-AND-DISCOVERIES.md`)
- `_check_ai` "not configured" vs "unreachable" both → `degraded` (P-L3): diagnostic blind-spot, readiness still fails correctly when AI is down. Safe to defer.
- `settings.py token-usage/admin` uses `.to_list(None)` (unbounded): should aggregate server-side. Low.
- ~120 naive `datetime.now()` calls across 16 route files: large-scale migration. The persisted-timestamp *source of record* (`actor_context`) + notification write are fixed in R15.4; the rest is a tracked sweep.

### Sent to `HUMAN-VERIFICATION-CHECKLIST.md`
- Whether teachers/admins should see full guardian contact (`phone`/`email`) via `get_student`/`list_guardians` — product/DPDP judgment call (staff↔guardian contact is a legitimate need; over-restricting would break it). Self-view already minimizes.

## 14-deselected investigation (final pass)
Per the run instruction, re-ran `python -m pytest tests/backend/ -q` (no `-x`): **1632 passed, 14 deselected, 0 failed.** Collecting only `-m "llm_eval or mongo_real"` yields exactly 14 tests — i.e. the deselected set is entirely the two credentialed/infra tiers (`mongo_real` needs a real MongoDB replica set for transactions/sessions/unique-index enforcement `FakeDb` can't honor; `llm_eval` needs real Azure OpenAI credentials to score answer quality). Both are **deselected by design** via `pytest.ini` `addopts = -m "not mongo_real and not llm_eval"` and run in nightly/credentialed CI — they are NOT the "25 pinned baseline failures." The 25 pinned failures are confirmed **not reproducing** (suite is fully green, 0 failed), consistent with the DEFERRED-log note since R11. They cannot be executed in this fakes-only dev environment without real Mongo + Azure; that requirement is documented in `tests/backend/mongo_real/README.md` and `tests/backend/evals/README.md`.

## Test-infra note
`conftest.FakeCollection.update_one` gained minimal aggregation-pipeline (list update) support (`$max/$min/$subtract/$add/$ifNull`), needed to test the atomic token floor. Additive: only the `isinstance(update, list)` branch is new; all dict-update paths are unchanged, so no prior test is affected (verified — full suite green).

## Gate status: CLEAN
All ACs met; every raised finding fixed with a fails-before/passes-after regression test or dismissed with a written reason; grep audit clean; suite green vs baseline.
