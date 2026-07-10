# Epic R2 — Confirmed-Write Integrity · Epic-Close Quality Gate

Review lenses applied over the whole R2 combined diff (executing agent performed the
bmad-code-review / adversarial / edge-case-hunter / test-review / trace / nfr lenses
manually, per the protocol's "no skills? follow the workflow" clause).

## Test results
- Full backend suite: **1313 passed, 0 failed, 0 skipped, 13 deselected** (mongo_real tier).
  Baseline was 1290 passed. Net new: +23 collected (22 selectable + 1 deselected mongo_real),
  and one pre-existing test updated for the new typed token detail.
- No regression versus the pinned baseline; the 25 pinned pre-existing failures remain
  deferred to the initiative close and were neither touched nor worsened.

## Grep audit (scoped_filter / scoped_query) on touched backend files
- `plan_executor.py`, `planner.py`, `confirm_tokens.py` — no `scoped_filter` hits (no data queries added).
- `database.py` — hits are the ScopedCollection internals (the scoping mechanism itself; unchanged).
- `chat.py` — all `scoped_filter` hits are pre-existing conversation-scoping queries with
  `get_school_id()`; my changes (confirm-dispatch handlers, post-commit try/except) added none.
- Result: **clean** — no new branch/tenant scoping introduced or weakened.

## Findings (found during self-review) & resolution

| # | Severity | File | Issue | Resolution | Regression test |
|---|----------|------|-------|------------|-----------------|
| 1 | Medium | `chat.py` | Post-commit assistant-message persistence (`db.messages.insert_one`) was still outside a guard — a Mongo hiccup there could 500 a *committed* plan (XM9 spirit). | Wrapped in try/except that logs and returns success with `message_id=None`. | `api/…::test_post_commit_metric_failure_still_returns_success` (exercises the post-commit path; message-persist guard covered by inspection + suite green). |
| 2 | Low | `plan_executor.py` | On the **no-op** (dev) tier a mid-plan step failure leaves earlier steps' writes un-rolled-back while their idempotency claims are compensated — a retry could double-write. | Accepted: no-op path is confined to `ENVIRONMENT == development` by R2.3; production uses a real txn that rolls everything back. Documented here; matches pre-existing no-op limitations. | n/a (dev-only, documented) |
| 3 | Low | `confirm_tokens.py` | HMAC key read from `middleware.auth.JWT_SECRET` at call time — a test that swaps the secret between issue and consume would see a mismatch. | Intended (that's the tamper property). Both issue and consume use the same `compute_plan_hash`; tests seed via it. | `test_plan_hash_is_hmac_keyed`, `test_plan_hash_stable_for_same_key` |

## Edge cases walked (edge-case-hunter lens)
- Idempotency-claim `DuplicateKeyError` vs domain `DuplicateKeyError` — now provably distinct paths (`_IdempotentReplay` vs `StepExecutionError`). ✅
- Concurrent confirm landing a `OperationFailure`/WriteConflict on the claim — still handled by the existing `_is_write_conflict` + `_idempotency_key_committed` branch (unchanged). ✅
- `TransactionUnavailableError` raised before `run()`'s try block → no session created, nothing to clean up, propagates to the 503 handler. ✅
- `record_ai_metric` / `audit_ai_dispatch_finalize` both swallow internally, so the `except StepExecutionError` handler always reaches its typed 422. ✅
- Reads-only "plan" → `resolved_steps == []` → `has_writes` False → no confirm card issued (correct; reads execute inline, not via a plan). ✅
- Legacy single-action token (no `plan`) failing → 422 composed from the tool's own message. ✅

## NFR lens
- **Security:** plan MAC is now keyed (forgery requires the server secret); `compare_digest` avoids timing leaks; the write-classification guard prevents a future mutating tool from bypassing confirm/kill-switch/audit. Token intent echo is PII-free (tool/action labels only, never resolved params).
- **Reliability:** confirmed writes are all-or-nothing outside development or refused with a visible 503; committed plans never surface as 500s.
- **Tenancy:** unchanged; grep audit clean.

## AC → test traceability
Every AC in R2.1–R2.6 maps to at least one named test — see the completed log's per-story
"Tests" lines. Failure matrix (R2.1 AC3) covered across envelope-false, runner-raises,
domain-dup, and idempotency-dup cases at both executor and API tiers.
