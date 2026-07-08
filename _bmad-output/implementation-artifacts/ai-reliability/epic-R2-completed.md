# Epic R2 — Confirmed-Write Integrity · Completed Log

**Goal:** a confirmed action's *reported* outcome is always the *true* outcome.
Fixes audit findings X2, X4, X5, XM1, XM2, XM6, XM9.

**Branch:** `ai-reliability-r1-turn-completion` (R2 committed on the same branch per the
standing instruction that R1/R2 ship to a branch, not `main`, until told otherwise).
**Baseline:** 1290 passed / 0 failed / 0 skipped → **after R2: 1313 passed / 0 failed / 0 skipped** (13 mongo_real deselected).

---

## R2.1 — Plan executor honors tool failure envelopes (X2)
**Files:** `backend/ai/plan_executor.py`, `backend/routes/chat.py`

- Added `StepExecutionError`. In `run()`, a write step whose runner **returns** a
  failure envelope (`result.get("success") is False`) now records the step
  `status: "failed"` and raises — aborting the whole transaction. A confirmed plan
  never commits around a failed step.
- `chat.py` grew an `except StepExecutionError` handler → HTTP **422**
  `{code: "step_failed", failed_tool, failed_step, message}`; the message names the
  failed step and states "No changes were applied." The write-ahead audit row is
  finalized as a failure, so **user reply and audit row always agree** (AC2).
- Step success rule follows architecture §5.1: success = `result.get("success") is not False`
  (a legacy tool returning no `success` key is still treated as success).

**ACs:** AC1 ✅ AC2 ✅ AC3 (failure matrix) ✅
**Tests:** `unit/test_r2_confirmed_write_integrity.py` (envelope-false single & multi-step,
success/legacy commit), `api/test_r2_confirm_dispatch.py` (422 + audit agreement, single-action reply from actual result).

## R2.2 — Correct `already_applied` semantics (X4)
**Files:** `backend/ai/plan_executor.py`

- The idempotency-claim `insert_one` is now wrapped in its own `try/except
  DuplicateKeyError` → raises the internal `_IdempotentReplay` sentinel → returns
  `already_applied`. **Only** the claim collision maps to `already_applied`.
- A `DuplicateKeyError` raised by the step **runner** (a domain unique-index
  collision) is caught separately → `StepExecutionError` naming the collection/index
  (`_dup_detail()` parses the E11000 message). It is a genuine failure, never
  "already applied".

**ACs:** AC1 ✅
**Tests:** `test_domain_duplicate_key_is_a_step_failure_not_already_applied`,
`test_idempotency_claim_duplicate_is_already_applied`.

## R2.3 — No silent no-op transactions (X5)
**Files:** `backend/database.py`, `backend/routes/chat.py`

- Added `TransactionUnavailableError`. `get_txn_session()` now falls back to
  `_NoopSession` on a `start_session()` failure **only** when
  `ENVIRONMENT == "development"`; in staging/production it **raises** (fail loud).
  The `_client is None` case (FakeDb/test tier — no client configured) still returns
  a no-op session; that is the legitimate test path, never a production state.
- `chat.py` grew an `except TransactionUnavailableError` handler → HTTP **503**
  `{code: "txn_unavailable", …}` "we couldn't guarantee transactional safety, so
  nothing was applied."
- Dry-run/shadow already aborts the txn (`_DryRunAbort`); a real-session rollback
  proof was added on the mongo_real tier.

**ACs:** AC1 ✅ AC2 ✅
**Tests:** `test_get_txn_session_raises_outside_development`,
`…_falls_back_to_noop_in_development`, `…_no_client_is_noop`,
`api/…::test_txn_unavailable_returns_503`, `mongo_real/test_dry_run_rollback_r2.py`.

## R2.4 — Confirm-token hardening + expiry UX (XM6)
**Files:** `backend/services/confirm_tokens.py`, `backend/routes/chat.py`

- **AC1:** `compute_plan_hash` is now **HMAC-SHA256 keyed with `JWT_SECRET`**
  (was an unkeyed sha256 anyone able to edit the stored plan could recompute).
  Verification uses `hmac.compare_digest`. Key resolved via `middleware.auth` at
  call time.
- **AC2:** Expiry/validation failures now carry **typed reason codes**
  (`token_expired`, `token_tenant_mismatch`, existing `plan_tampered`). `chat.py`
  maps expiry to the re-planable `plan_expired` **by code**, not by string-matching
  `"expired"` in the detail text.
- **AC3:** Post-consume validation failures (`plan_tampered`, tenant mismatch) and
  the expiry response echo a **PII-free `intent`** (`{kind, tools|action}`) so the
  client can re-issue in one tap.

**ACs:** AC1 ✅ AC2 ✅ AC3 ✅
**Tests:** `test_plan_hash_is_hmac_keyed`, `test_plan_hash_stable_for_same_key`,
`test_expired_token_returns_typed_code_with_intent`,
`test_post_consume_plan_tampered_echoes_intent`; updated
`test_wave2_patches.py::…school_id_mismatch` to the typed detail.

## R2.5 — Post-commit safety + dead saga cleanup (XM1/XM2/XM9)
**Files:** `backend/routes/chat.py`, `backend/ai/planner.py`

- **AC1 (XM9):** All post-commit bookkeeping in `chat.py` (metric writes, destructive
  audit, and the assistant-transcript message persistence) is now wrapped so an
  exception is logged and swallowed — **a committed plan can never become a
  user-facing 500**.
- **AC2 (XM2):** `planner.build_plan` now **drops READ steps** from the resolved plan
  entirely (the executor only runs write steps, so a read on the confirm card was a
  false promise) and re-indexes writes sequentially.
- **AC3 (XM1) — decision documented:** the saga `side_effect`/`compensate` machinery
  is **retained** (it is correct and already runs strictly post-commit, and is
  covered by `test_saga_d5.py`). Rationale, not a cop-out: the only side effect the
  live AI-write path produces is a **notification**, which is a *Mongo* write that
  enlists in the executor's transaction via `session_kwargs()` — so a rolled-back
  plan sends nothing (AD14). "Wiring notifications to fire post-commit" would be the
  *wrong* design (it would notify about writes that then rolled back). There is no
  synchronous non-Mongo (SMS/email) effect in the AI dispatch path today; the saga
  infra stays as tested infrastructure for when one is added. The pre-existing
  "survives rollback" concern only applied to the no-op session tier, which R2.3 now
  confines to development.

**ACs:** AC1 ✅ AC2 ✅ AC3 ✅ (documented)
**Tests:** `api/…::test_post_commit_metric_failure_still_returns_success`,
`unit/test_planner_e2.py` (reads dropped, writes re-indexed),
`test_notification_enlists_ambient_txn_session`.

## R2.6 — Write-tool classification guard (X7)
**Files:** `tests/backend/parity/write_classification_guard_test.py` (new)

- A CI guard walks `TOOL_REGISTRY`: every tool must be classified **exactly once** —
  either flagged as a write (`requires_confirmation` / `dispatch_type == "write"`)
  or present on the explicit `READ_ONLY_ALLOWLIST` (the current 45 read tools). A
  new tool that is neither fails the test, forcing a conscious decision at review
  time — closing the hole where a mutating tool without flags silently bypasses
  confirm/kill-switch/audit.
- Defense in depth: allowlisted tools must use a read-only name prefix
  (`get_/query_/search_/recall_/draft_`) and no write tool may use one, so a
  mutating tool cannot be quietly parked on the allowlist.

**ACs:** AC1 ✅ AC2 ✅
**Tests:** 5 assertions in the new guard module.

---

## Files touched
- `backend/ai/plan_executor.py` — StepExecutionError, `_IdempotentReplay`, `_dup_detail`, failure-aware loop.
- `backend/ai/planner.py` — drop read steps, re-index writes.
- `backend/database.py` — `TransactionUnavailableError`, fail-loud `get_txn_session`.
- `backend/routes/chat.py` — StepExecutionError/TransactionUnavailable handlers, typed expiry code, post-commit try/except (metrics + message persist).
- `backend/services/confirm_tokens.py` — HMAC plan MAC, typed reason codes, `_intent_summary` echo.
- Tests: `unit/test_r2_confirmed_write_integrity.py` (new, 14), `api/test_r2_confirm_dispatch.py` (new, 5), `parity/write_classification_guard_test.py` (new, 5), `mongo_real/test_dry_run_rollback_r2.py` (new, 1), updated `unit/test_planner_e2.py` + `unit/test_wave2_patches.py`.
