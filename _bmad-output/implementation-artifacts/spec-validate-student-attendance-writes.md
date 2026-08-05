---
title: 'Validate student attendance writes'
type: 'bugfix'
created: '2026-08-05'
status: 'done'
baseline_commit: 'f82f685c244504d053baa383b77586d1410ea111'
context:
  - '{project-root}/_bmad-output/project-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Bulk and manual attendance writes accept arbitrary status strings, malformed dates, unknown classes, duplicate student rows, and students outside the selected class. These invalid records become operational history and can corrupt reports.

**Approach:** Add one shared domain validator used by REST and AI write paths before any attendance mutation. Preserve the existing write/audit/idempotency behavior for valid payloads.

## Boundaries & Constraints

**Always:** Accept the four currently offered statuses (`present`, `absent`, `late`, `holiday`); require `YYYY-MM-DD`; validate class existence and student membership within the school; reject duplicate student IDs; keep empty bulk behavior for backward compatibility; map invalid REST payloads to HTTP 400 and AI payloads to a normal failed tool result.

**Ask First:** Enforcing a school holiday calendar or forbidding future dates, because current UI explicitly supports a holiday status and schools may pre-mark calendar days.

**Never:** Hard-delete attendance, change correction/history behavior, mutate live data, add branch functionality, or create hostel behavior.

</frozen-after-approval>

## Code Map

- `backend/services/attendance_service.py` -- shared validation and write path.
- `backend/routes/attendance.py` -- REST error mapping and manual-write reuse.
- `backend/ai/tool_functions_v2.py` -- AI error-envelope mapping.
- `tests/backend/unit/test_attendance_validation.py` -- invalid/valid domain cases.

## Tasks & Acceptance

**Execution:**
- [x] `backend/services/attendance_service.py` -- validate class, date, statuses, duplicates and membership before writes.
- [x] `backend/routes/attendance.py` and `backend/ai/tool_functions_v2.py` -- expose failures without internal errors.
- [x] `tests/backend/unit/test_attendance_validation.py` -- cover each rejected case and no-write guarantee.
- [x] Existing attendance characterization/parity fixtures -- seed valid class membership without weakening assertions.

**Acceptance Criteria:**
- Given an invalid attendance payload, when either panel or Flo invokes it, then zero attendance/audit records are written and a clear validation failure is returned.
- Given a valid payload, when either entry point invokes it, then existing parity, audit and idempotency behavior remains unchanged.

## Spec Change Log

## Verification

**Commands:**
- `python -m pytest tests/backend/unit/test_attendance_validation.py tests/backend/unit/test_attendance_service_a1.py tests/backend/parity/attendance_parity_test.py -q` -- expected: all pass.

**Results:**
- Validation, characterization, parity and transactional regression slices: 29 passed.

## Suggested Review Order

**Domain invariants**

- Shared validation rejects malformed or cross-class records before writes.
  [`attendance_service.py:34`](../../backend/services/attendance_service.py#L34)

- Panel/manual adapters map domain failures to stable HTTP 400 responses.
  [`attendance.py:122`](../../backend/routes/attendance.py#L122)

- Flo returns a normal failed tool envelope instead of an internal error.
  [`tool_functions_v2.py:2114`](../../backend/ai/tool_functions_v2.py#L2114)

**Regression proof**

- Parameterized tests prove every invalid batch leaves attendance and audit empty.
  [`test_attendance_validation.py:62`](../../tests/backend/unit/test_attendance_validation.py#L62)
