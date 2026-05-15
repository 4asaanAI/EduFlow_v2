# Part 7 Audit Coverage Matrix

**Date:** 2026-05-15
**Scope:** Quality Sweep Part 7 - Observability + Audit

## Canonical Audit Path

All direct audit writes now go through `services.audit_service.write_audit` or
`services.audit_service.write_audit_doc`.

The helper normalizes:

- `schoolId`
- `branch_id`
- `entity_type`
- `collection`
- `entity_id`
- `record_id`
- `changes`
- `reason`
- `created_at`
- `timestamp`

It is intentionally fail-open. Audit insert failures are logged with structured
metadata and escalate from warning to error after repeated failures.

## Coverage

| Area | Representative actions | Status |
|---|---|---|
| Settings | school settings update, user settings update, academic-year transition, token usage tracking | Covered |
| Custom Forms | form create, response submit, form delete | Covered |
| Activities | house points, student positions, sports team create/update/delete | Covered |
| Core People | student create/update/delete/photo, staff create/update/delete | Covered |
| Attendance | manual attendance, corrections, AI attendance writes | Covered |
| Fees | payment, correction, discount, contact log, AI fee payment | Covered |
| Operations | leave requests, approvals, incidents, announcements approval/rejection | Covered |
| Issues | facility/tech requests, maintenance schedule, vendors | Covered |
| Academics | substitutions | Covered |
| Imports | student bulk import | Covered |
| AI Tools | follow-up assignment, incident status, thread entries, substitutions, attendance corrections, discounts, approvals, resolution confirmation, announcements | Covered |
| Generated Files | persisted generated PDFs | Covered |

## Query and Retention Support

- Audit list supports explicit branch filtering.
- Principal/admin branch context auto-filters when `branch_id` is present and no explicit owner branch filter is supplied.
- Record history is paginated and branch scoped.
- Migration `021_audit_log_indexes.py` adds compound indexes for school/date and school/entity/date.

## Verification

- `Select-String -Path backend\**\*.py -Pattern "audit_logs\.insert_one"` returns only `backend/services/audit_service.py`.
- Focused Part 7 suite: 79 passed.
