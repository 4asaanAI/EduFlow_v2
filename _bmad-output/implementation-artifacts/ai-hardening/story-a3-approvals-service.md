# Story A.3 — Approval-request decision service parity

**Epic:** A · **Status:** DONE (11 new tests + 3 existing REST workflow tests green; parity byte-identical; zero new failures vs pinned baseline)
**FRs:** FR13, FR14, FR16–FR18

## Case-by-case parity resolution (canonical = REST)
| Behavior | Old AI tool | REST route | **Canonical (service)** |
|---|---|---|---|
| routing-dependent authz | ❌ **dropped** (P6 "registry gate" — but the static gate can't see `approval.routing`) | ✅ owner=any; principal=only `owner_and_principal`; else 403 | ✅ enforced in service for BOTH paths |
| audit action | `decide_approval_request` | `approval_decide` | `approval_decide` |
| audit entity_type | `approval_requests` | `approval_request` | `approval_request` |
| audit `changed_by_name` | present | absent | absent |
| scoping | `scoped_query(branch_id)` (narrows) | `scoped_filter` (school-wide) | `scoped_filter` school-wide (intentional — routed to owner/principal) |
| validation order | n/a | 400 → 404 → 403 | 400 → 404 → 403 (preserved) |

**Security note:** the dropped routing check was a real hole within the Phase-1 owner+principal
set — a principal could decide an `owner_only` request via chat, and the registry's `roles=["owner","admin"]`
(no sub_categories) let any admin (e.g. accountant) reach the tool. The service now closes both.

## Architecture note (P2 boundary)
The REST route uses `Depends(get_current_user)` (no static role gate) — its authorization is
*inherently record-level* (depends on the loaded `approval.routing`), and lived in the handler body.
Centralizing it in the service (raising `ApprovalAuthorizationError`) is the correct way to make
both entrypoints enforce identical authz. The *static* role/sub_category gate stays in the adapters
(`require_*` / `_is_tool_authorized`) per P2; this is the dynamic, data-dependent gate.

## Implementation
- `services/approvals_service.py::decide_approval_request(db, actor_ctx, params, *, session=None, idempotency_key=None)`
  with `ApprovalValidationError`(400)/`ApprovalNotFoundError`(404)/`ApprovalAuthorizationError`(403).
- `routes/operations.py::decide_approval_request` route → thin adapter. **Name collision fixed:** the route
  handler and the service fn share the name `decide_approval_request`; the service is imported `as
  decide_approval_request_service` (else the handler shadowed the import and recursed).
- `ai/tool_functions_v2.py::tool_decide_approval_request` → thin adapter (preserves `request_id/decision/reason`).

## Parity / audit
- Parity test (`parity/approvals_parity_test.py`): owner decide via REST vs AI → approval doc + audit + notification byte-identical.
- 3 existing REST workflow tests (`test_operations_workflow.py`) stay green (pins audit `approval_decide` + notif `approval_decision`).
- grep audit: decide handler now has 0 `scoped_filter` (service uses school-wide with intentional comment).
