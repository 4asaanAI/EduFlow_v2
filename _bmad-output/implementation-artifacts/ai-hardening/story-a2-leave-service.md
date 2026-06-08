# Story A.2 — Leave-approval service parity

**Epic:** A · **Status:** DONE (9 new tests + 5 existing REST tests green; parity byte-identical; zero new failures vs pinned baseline)
**FRs:** FR13, FR14, FR16–FR18

## Story
As an Owner/Principal, I want AI leave approvals to behave identically to the panel,
so an AI-approved leave is indistinguishable from a manual one.

## Case-by-case parity resolution (canonical = REST)
The old AI `tool_approve_leave` (v1, `ai/tool_functions.py`) **silently diverged** from
`PATCH /api/staff/leaves/{id}`. Divergences and resolution (AI corrected to match REST):

| Behavior | Old AI tool | REST route | **Canonical (service)** |
|---|---|---|---|
| staff notification | ❌ none | ✅ `create_notification(leave_decision)` | ✅ notify |
| audit row | ❌ none | ✅ `write_audit(leave_{status})` | ✅ audit |
| pending-only idempotency guard | ❌ re-decides | ✅ guard + 409 | ✅ guard → `LeaveConflictError` |
| rejection reason required | ❌ optional | ✅ 400 if missing | ✅ `LeaveValidationError` |
| `approved_at` | local naive | UTC-aware | UTC (`actor_ctx.now_utc_iso()`) |
| tenancy | `_tenant_query(scope)` | `scoped_query(branch_id=user.branch_id)` | `scoped_query(branch_id=actor_ctx.branch_id)` |

These were real correctness gaps in the AI path; closing them is intended hardening
(noted as found-while-extracting; distinct from the 3 Epic-B defects).

## Implementation
- `services/leave_service.py::decide_leave(db, actor_ctx, params, *, session=None, idempotency_key=None)`
  with domain exceptions `LeaveValidationError`(400)/`LeaveNotFoundError`(404)/`LeaveConflictError`(409).
- `actor_context.py` extended with `now_utc()`/`now_utc_iso()` (UTC clock, honors `now_fn`).
- `routes/staff.py::update_leave` → thin adapter (domain errors → HTTPException).
- `ai/tool_functions.py::tool_approve_leave` → thin adapter (domain errors → `{success: False, error}`),
  preserving its `(leave_id, action, reason)` param interface so chat.py is unchanged.

## Parity / audit
- Dual-entrypoint parity test (`parity/leave_parity_test.py`): same seed + same actor → leave doc +
  notification + audit row byte-identical (mask `id/_id/created_at/updated_at/timestamp/approved_at`).
- 5 existing REST tests (`test_leave_approval.py`) stay green (REST characterization unchanged).
- AI closed-gap regression guards (`test_leave_service_a2.py`): AI now notifies+audits; AI double-decide guarded.
- grep audit: `update_leave` now has 0 `scoped_filter` (uses service `scoped_query`). Remaining `scoped_filter`
  hits in staff.py are untouched READ handlers under the established "leave_requests is school-wide" pattern
  (project-context.md §Branch Isolation).
