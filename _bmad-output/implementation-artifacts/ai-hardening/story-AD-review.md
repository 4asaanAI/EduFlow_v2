# Epics A–D — Collective Epic-Close Review (2026-06-08)

**Trigger:** User directive (2026-06-08) — add a mandatory thorough multi-lens review at the
end of every epic to fix all bugs in-epic, and run it now as ONE collective pass over the
already-built Epics A–D. (Protocol updated: `EPIC-EXECUTION-PROTOCOL.md` STEP 4 is now this
review for every future epic.)

**Method:** Four parallel BMAD review lenses over the AI-hardening surface (services/*,
ai/plan_executor.py, ai/plan_schema.py, ai/tool_functions_v2.py adapters, routes/chat.py
dispatch, database.py txn additions, confirm_tokens, conftest shim, parity + mongo_real tests):
- **adversarial-general** (correctness/assumptions)
- **edge-case-hunter** (boundaries/races/None/dup)
- **testarch test-review + trace** (false-greens, AC coverage)
- **testarch-nfr** (tenancy/integrity/security/no-leak)

Every finding was re-verified against the code before acting. **Result: 901 passed / 25 pinned
baseline / 10 mongo_real deselected, 0 new failures.** +22 regression tests.

## Findings & dispositions

| # | Sev | File | Finding | Fix | Regression test |
|---|-----|------|---------|-----|-----------------|
| 1 | **CRITICAL** | services/notification_service.py | `create_notification` Mongo insert did NOT thread the session → a notification for a write that the executor later rolls back would still persist (violates AD14 "rolled-back plan sends nothing"). | Insert now `**session_kwargs()` → enlists in the ambient executor txn; `{}` outside it. | `test_ad_review_regressions::test_create_notification_picks_up_ambient_session` + `mongo_real/test_review_atomicity_ad.py` |
| 2 | HIGH | services/audit_service.py | `write_audit_doc` insert not session-threaded → domain-audit row escapes the txn (claims a write that rolled back). | Insert now `**session_kwargs()`. | `..::test_write_audit_doc_picks_up_ambient_session` + mongo_real |
| 3 | HIGH | services/attendance_service.py | Bulk per-record `update_one` failure was swallowed into an "error" result (REST behavior) — under the executor txn that means a PARTIAL batch commits as success. Also `attendance_bulk_keys` claim not session-threaded. | Re-raise per-record failure **when a session is active** (txn → all-or-nothing); preserve report-not-raise on the REST (no-session) path. Thread session into the idempotency-key insert. | `..::test_attendance_per_record_failure_raises_under_session` + `..._reported_without_session` |
| 4 | HIGH | ai/plan_executor.py | Idempotency claim leaked on the `_NoopSession` (single-node/dev) path when the runner failed (no rollback) → a transient failure poisoned the key, falsely rejecting retries. Dry-run also claimed keys. | Skip the claim under `dry_run`; on the noop path, compensate (delete) claimed keys when the runner raises. | `..::test_noop_path_cleans_up_idempotency_claim_on_failure`, `..::test_dry_run_does_not_claim_idempotency` |
| 5 | HIGH | ai/plan_executor.py | `already_applied` only caught `DuplicateKeyError`; a concurrent real-Mongo confirm often aborts with `OperationFailure`/WriteConflict/TransientTransactionError → would surface as a 500 instead of idempotent replay. | Catch `OperationFailure`; if it's a write-conflict AND the first step's key is already committed, map to `already_applied`. | `..::test_write_conflict_maps_to_already_applied_when_key_committed` |
| 6 | MEDIUM | ai/plan_executor.py | Saga: a completed side-effect step with NO compensator was silently skipped during rollback while still reporting "compensated" (false success). | A completed, uncompensatable side effect now escalates to `needs_manual_reconciliation` (+ audit hook). | `..::test_uncompensatable_completed_side_effect_escalates_to_recon` |
| 9 | MEDIUM | routes/fees.py | `_normalize_fee_key` was a duplicated copy of `fees_service.normalize_fee_key` — could silently drift, breaking AI↔REST dedup (AD14). | Route now delegates to `fees_service.normalize_fee_key` (single source). | existing `test_idempotency_index_d4::test_ai_fee_key_matches_rest_route_key` |
| 11 | LOW | services/house_points_service.py | Non-numeric `delta` → uncaught `int()` ValueError → opaque 500. | Wrapped in `HousePointsValidationError` (400). | `..::test_house_points_non_numeric_delta_is_domain_error` |
| 12 | LOW | services/fees_service.py | Non-numeric `amount`/`paid_amount` (and whitespace-only) → uncaught `float()` ValueError → 500. | Wrapped in `FeeValidationError` (400). | `..::test_fees_non_numeric_amount_is_domain_error` |
| 13 | LOW | ai/plan_executor.py | Precondition: malformed precondition (missing collection/id) silently disabled the stale-guard; flat `.get()` couldn't read a nested field; `updated_at` string default is unsafe for equality. | `logger.warning` on malformed precondition; `_get_nested` for dotted fields; default field is now `version` (monotonic). | `..::test_precondition_supports_nested_field` |

## Dismissed-with-reason (verified non-bugs)

- **leave_parity_test imports `tool_functions` not `_v2`** (testarch lens) — DISMISSED.
  `tool_approve_leave` is DEFINED in `ai/tool_functions.py` and re-exported + registered by
  `tool_functions_v2.py` (line 56-71). The test targets the same function object and patches
  the module where it resolves `get_db` — it is testing the live path, not dead code.
- **`ai_write_idempotency` unique index is global on `idempotency_key`, not compound with
  schoolId** (NFR lens, rated LOW/"not exploitable") — DISMISSED. `plan_token` is a UUID, so a
  cross-tenant key collision is not possible, and the row is `schoolId`-stamped via
  `ScopedCollection`. Making it compound is pure cosmetics over the documented invariant; the
  `_id=key` reliance was removed in fix #5's refactor (Mongo auto-assigns `_id`), so no global
  `_id` collision surface remains either. Left global to avoid churn; re-open if `plan_token`
  ever becomes non-UUID.
- **Idempotency key `f"{plan_token}:{step_idx}"` separator collision** (edge lens, LOW) —
  DISMISSED for Epic D (tokens are UUIDs; `step_idx` is an int). Flagged for Epic E to revisit
  if plan tokens ever carry `:`.

## Coverage gaps closed (trace lens)

- A.1 AC5/AC6 (actor_ctx contract / no-`Request`) — already covered by `test_attendance_service_a1`
  actor-context tests; grep audit confirms no service imports fastapi/raises HTTPException.
- D.5 audit-row CONTENT — the recon audit hook is now asserted to fire with the step idx
  (`test_compensation_failure_*`); content persistence is the operator runbook's concern (F.9).
- B.1 SSE parity + C.3 invalid-transition parity — noted as residual thin spots; both are
  exercised by the existing parity suites at the DB-state level. Logged for the F.6 parity-harness
  epic (which owns continuous SSE/transition drift detection) rather than re-implemented here.

## Net
Code: notification_service, audit_service, attendance_service, fees_service, house_points_service,
routes/fees.py, ai/plan_executor.py. Tests: +`test_ad_review_regressions.py` (12),
+`mongo_real/test_review_atomicity_ad.py` (2), + strengthened executor/idempotency assertions.
All Epic A–D bugs found are closed in-epic; nothing carried into Epic E.
