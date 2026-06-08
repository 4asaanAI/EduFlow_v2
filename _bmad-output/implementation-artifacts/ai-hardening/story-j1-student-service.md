# Story J.1 — Student create & update (hardened AI tools)

**Epic:** J · **Status:** DONE · **FRs:** FR37, AD15
**Phase-1 role gate:** Owner + Principal ONLY (`roles=["owner","admin"], sub_categories=["principal"]`).

## Scope
Expose existing student CRUD (create/update/guardians/soft-status) to the assistant as
hardened tools that wrap a single shared `services/student_service.py`. **No** AI
`delete_student`/`erase_student` tool — hard-delete (`DELETE /students/{id}`) and
DPDP-erase (`/students/{id}/erase`) stay UI-only (AD15). Photo upload is binary-only
and stays a REST route (the assistant can set `photo_url` via `update_student`).

## Shared service (`services/student_service.py`, P1 signature)
- `create_student(db, actor_ctx, params, *, session=None, idempotency_key=None)` →
  validates class (current-year), enforces unique admission number (409),
  inserts the `students` doc + derived `guardians`, writes the `student/create` audit.
- `update_student(db, actor_ctx, params, *, ...)` → field-whitelist (`UPDATABLE_FIELDS`),
  transport-head field restriction, class re-validation, admission-number dup check,
  no-op short-circuit, `student/update` audit with per-field change diff.
- `upsert_guardians(db, actor_ctx, params, *, ...)` → replace-by-relation, `guardians_update` audit.
- `set_student_status(db, actor_ctx, params, *, ...)` → thin wrapper over `update_student`
  with a single `status` field (UPDATABLE). Soft status change only; never the DELETE route.
- Domain exceptions: `StudentValidationError`(400), `StudentNotFoundError`(404),
  `StudentConflictError`(409), `ClassNotFoundError`(404), `ClassValidationError`(400).
  Services NEVER raise `HTTPException`.

## Adapters
- `routes/students.py`: create/update/guardians become thin adapters (parse → service →
  domain-error→HTTP). Tenant scoping unchanged (school-scoped via `scoped_filter`, no branch).
- `ai/tool_functions_v2.py`: `tool_create_student`, `tool_update_student`,
  `tool_manage_student_guardians`, `tool_set_student_status` build `actor_ctx` then call the service.

## Parity / DPDP / audit
- Dual-entrypoint parity tests (REST vs AI) → `students` + `guardians` + `audit_logs`
  byte-identical (volatile-masked). Corpus entries added for all 4 write tools.
- Student tool results re-enter the LLM via `_safe_tool_result_for_chat` → `redact_for_llm`
  (medical_notes/dob etc. masked) — DPDP hard control, inherited, unchanged.
- Refusal of delete/erase is enforced by tool absence; regression test asserts no such tool.
