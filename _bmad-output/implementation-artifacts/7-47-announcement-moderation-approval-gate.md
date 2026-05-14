# Story 7.47: Announcement Moderation + Approval Gate

Status: done
Epic: 7 (Growth Features / Phase 2)
Priority: High (required when teachers + students are live)
Effort: Small-Medium
Created: 2026-05-15
PRD: Phase 2 Growth — "Announcement moderation / approval gate"

## Story

**As** a Principal,
**I want** to review and approve Receptionist-authored announcements before they reach teachers and students,
**so that** inappropriate or incorrect announcements are not broadcast school-wide.

## Acceptance Criteria

1. **AC1 — Pending status on creation when teacher/student-targeted.** `POST /api/operations/announcements` — when `target_roles` (or `audience_roles`) includes `teacher` or `student`, the new announcement is persisted with `status: "pending_approval"` instead of `"active"`. Announcements targeting only admin roles bypass the gate and persist with `status: "active"` exactly as today.
2. **AC2 — Pending list visible to Principal only.** `GET /api/operations/announcements/pending` — returns all announcements in `pending_approval` status. Caller must have role `owner` or be an `admin` with `sub_category == "principal"`. Other roles get 403.
3. **AC3 — Principal can approve.** `PATCH /api/operations/announcements/{id}/approve` — Principal-only. Status flips to `active`, `approved_by` + `approved_at` fields stamped. Announcement immediately visible to its target roles via existing `GET /api/operations/announcements`.
4. **AC4 — Principal can reject with mandatory reason.** `PATCH /api/operations/announcements/{id}/reject` — Principal-only. Body `{ "reason": "..." }`. Empty/missing reason returns 400. Status flips to `rejected`, `rejected_by` + `rejected_at` + `rejection_reason` stamped. Receptionist (the original author) receives an in-app `notifications` row including the rejection reason.
5. **AC5 — Read filter excludes pending/rejected.** `GET /api/operations/announcements` returns only `status == "active"` rows. Existing announcements lacking the `status` field are treated as `active` for backward compatibility.
6. **AC6 — Audit trail.** Every approve/reject decision writes to `audit_logs` with `action: "announcement_approved"` or `"announcement_rejected"`, including the decision-maker, target announcement id, target_roles, and (for rejections) the reason.

## Tasks / Subtasks

- [x] **T1. Create flow** (AC: #1) — `requires_approval` flag computed from `target_roles`; status defaults applied at insert.
- [x] **T2. Pending list endpoint** (AC: #2) — endpoints registered at `/api/ops/announcements/pending` (project convention is `/api/ops`, not `/api/operations` as written in the AC; frontend already uses `/ops/`).
- [x] **T3. Approve endpoint** (AC: #3, #6) — `PATCH /api/ops/announcements/{id}/approve`, audit row written via `_audit_doc`.
- [x] **T4. Reject endpoint** (AC: #4, #6) — `PATCH /api/ops/announcements/{id}/reject`, mandatory reason validated (`reason.strip()` empty → 400), author notified via `_notify`.
- [x] **T5. Read filter** (AC: #5) — `list_announcements` now restricts to `status==active` OR `status` missing.
- [x] **T6. Tests** — 12 tests in `tests/backend/api/test_announcement_moderation.py` covering all ACs + edge cases (404, 400 on non-pending state, principal vs other roles).

## Dev Notes

### Existing code (READ BEFORE EDITING)

- **`backend/routes/operations.py:772–796`** `create_announcement`: today every announcement is created with no `status` field. Add the field. Don't break existing rows.
- **`backend/routes/operations.py:749–769`** `list_announcements`: filters by `is_draft` and audience. Add a status filter.
- **`backend/routes/operations.py:38–51`** `_notify`: existing notification helper used by other operations endpoints. Reuse it for rejection notifications.
- **`backend/routes/operations.py:_audit`** helper (line ~25) — existing audit-row builder. Use for approve/reject audit entries.

### Role check pattern

Principal is `role == "admin"` with `sub_category == "principal"`. Owner is `role == "owner"`. The convenience predicate used elsewhere:
```python
def _is_principal(user): return user.get("role") == "admin" and user.get("sub_category") == "principal"
```
Define inline or reuse if available.

### Schema additions

Add to `announcements` documents (no migration needed — additive):
- `status`: `"active" | "pending_approval" | "rejected"` (default `"active"` for legacy rows)
- `approved_by`, `approved_at`
- `rejected_by`, `rejected_at`, `rejection_reason`

### References

- [Source: backend/routes/operations.py#L772-L796] — create_announcement
- [Source: backend/routes/operations.py#L749-L769] — list_announcements
- [Source: backend/routes/operations.py#L38-L51] — _notify helper

## Dev Agent Record

### Agent Model Used
claude-opus-4-7 (1M context)

### File List

**Modified:**
- `backend/routes/operations.py` — `create_announcement` sets initial `status`; `list_announcements` filters to active+legacy; three new endpoints (`pending`, `approve`, `reject`).
- `tests/backend/conftest.py` — `FakeDb.announcements` collection registered.

**Added:**
- `tests/backend/api/test_announcement_moderation.py` — 12 tests covering all 6 ACs.

### Completion Notes

- All 6 ACs satisfied; 12 new tests pass; full backend suite **164/164 passes** (no regressions).
- URL prefix divergence from spec: AC says `/api/operations/announcements/...`, code uses `/api/ops/announcements/...` to match existing prefix and avoid breaking the frontend. The spec phrasing was the logical endpoint name; project convention won.
- Backward compatibility: legacy announcement rows lacking the `status` field still appear in the recipient-facing list (treated as active).
- Audit and notification reuse the existing `_audit_doc` and `_notify` helpers — same patterns as the leave-request workflow.

### Change Log

- 2026-05-15 — Implementation complete; story moved to `done` after self-review. 12 tests added, 164/164 backend tests pass.
