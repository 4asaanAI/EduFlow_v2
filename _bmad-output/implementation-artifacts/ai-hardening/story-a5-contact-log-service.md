# Story A.5 — Contact-log service parity

**Epic:** A · **Status:** DONE (5 new tests + existing fees-CRUD test green; parity byte-identical; zero new failures)
**FRs:** FR13, FR14

## Case-by-case parity resolution (canonical = REST)
| Behavior | Old AI tool | REST route | **Canonical (service)** |
|---|---|---|---|
| audit action | `log_contact_event` | `contact_log` | `contact_log` |
| audit entity_type | `fee_transactions` | `fee_transaction` | `fee_transaction` |
| record fields | same | same | same (`fee_contact_logs` doc) |
| field name | `note` | `notes` | `notes` (AI adapter maps `note`→`notes`) |
| txn resolution | by id, else student's latest | requires explicit `fee_transaction_id` | stays in AI adapter (convenience); service takes a resolved id |

## Implementation
- `services/contact_log_service.py::log_contact_event(db, actor_ctx, params, *, session=None, idempotency_key=None)`
  with `ContactLogValidationError`(400). Writes the `fee_contact_logs` record + canonical `contact_log`
  audit (entity_type `fee_transaction`).
- `routes/fees.py::create_fee_contact_log` → thin adapter (validation error → 400).
- `ai/tool_functions_v2.py::tool_log_contact_event` → thin adapter; keeps its txn-resolution convenience
  (by id or student's latest), maps `note`→`notes`, then calls the service.

## Parity / audit
- Parity test (`parity/contact_log_parity_test.py`): REST vs AI → `fee_contact_logs` record + `contact_log`
  audit byte-identical (mask `id/_id/created_at/timestamp`).
- Existing `test_fees_crud.py::test_overdue_query_summary_status_and_contact_log` stays green (REST characterization).
- grep audit: contact-log handler now has 0 `scoped_filter` (delegates to service; insert via ScopedCollection).
