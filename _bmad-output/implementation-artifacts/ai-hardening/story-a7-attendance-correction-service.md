# Story A.7 — Attendance-correction service parity (mandatory reason)

**Epic:** A · **Status:** DONE (6 new tests + existing correction tests green; parity byte-identical; zero new failures)
**FRs:** FR13, FR14, FR16–FR18

## Case-by-case parity resolution (canonical = REST)
| Behavior | Old AI tool | REST route | **Canonical (service)** |
|---|---|---|---|
| mandatory `correction_type`+`reason` | ✅ required | ✅ required (400) | required → `AttendanceCorrectionValidationError` |
| `original_record` snapshot + `previous_status`/`new_status` | ✅ | ✅ | identical |
| two writes (snapshot + status update) | in tool | in route | encapsulated in one service call (true txn atomicity = Epic D; `session=` threaded) |
| audit action | `correct_attendance` | `correct` | `correct` |
| scoping | `scoped_query(branch_id=...)` | `scoped_filter` (school-wide) | `scoped_filter` school-wide |

**Latent AI bug fixed:** attendance docs carry no `branch_id`, so the AI tool's
`scoped_query(branch_id=...)` could never match the record for a branch-scoped principal —
corrections silently returned "not found". School-wide scoping (matching REST) fixes it.

(The A.7 AC's "original_snapshot/correction_count" wording is fee-correction terminology;
attendance correction uses `original_record` with no count — preserved as-is.)

## Implementation
- `services/attendance_correction_service.py::correct_attendance(db, actor_ctx, params, *, session=None, idempotency_key=None)`
  with `AttendanceCorrectionValidationError`(400)/`AttendanceCorrectionNotFoundError`(404).
- `routes/attendance.py::correct_attendance` route → thin adapter. **Name collision fixed:** service
  imported `as correct_attendance_service` (route handler shares the name `correct_attendance`).
- `ai/tool_functions_v2.py::tool_correct_attendance` → thin adapter (maps `record_id`→`attendance_id`).

## Parity / audit
- Parity test (`parity/attendance_correction_parity_test.py`): REST vs AI → attendance_corrections doc +
  student_attendance update + `correct` audit byte-identical (mask ids/timestamps/corrected_at).
- Existing `test_attendance_corrections.py` (4 tests) stay green (REST characterization).
- grep audit: correct handler now has 0 `scoped_filter` (delegates to service; service uses school-wide
  `scoped_filter` with intentional comments — attendance has no branch_id).
