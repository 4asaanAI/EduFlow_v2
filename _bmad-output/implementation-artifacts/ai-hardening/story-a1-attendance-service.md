# Story A.1 — Attendance service as the reference shared-write-path

**Epic:** A — Trustworthy single-writer foundation (aligned domains)
**Status:** DONE (10/10 new tests green; dual-entrypoint parity byte-identical; zero new failures vs pinned 25-failure baseline; grep audit clean)
**FRs:** FR13, FR14, FR16, FR17, FR18 (parity foundation) · pins `actor_ctx` contract (AD14)

## Story
As an Owner/Principal, I want my AI-marked attendance to write exactly what the
panel writes, so that the chat and the UI are interchangeable and trustworthy.

## Acceptance Criteria (from epics doc)
1. The existing `POST /api/attendance/student/bulk` behavior is pinned by a
   characterization test (red baseline).
2. `services/attendance_service.py` is extracted with signature
   `mark_attendance(db, actor_ctx, params, *, session=None, idempotency_key=None)`
   and **both** the REST route and `tool_functions_v2.tool_mark_attendance` call it.
3. The REST characterization test still passes unchanged.
4. A dual-entrypoint state-diff test shows the AI tool and REST route produce
   byte-identical DB blast radius (records + audit + scoping) except a
   timestamp/request-id allowlist (`id`, `_id`, `created_at`, `timestamp`).
5. `actor_ctx` dataclass `{user_id, role, sub_category, school_id, branch_id, actor_name}`
   (+ injectable `now_fn`) is defined in `services/actor_context.py` and synthesized
   identically by both adapters (pinned contract; services extend the dataclass, never read `Request`).
6. No service reads `Request`/`Depends` or raises `HTTPException`.
7. `scoped_query(branch_id=...)`/`scoped_filter` grep audit on `attendance.py` is clean.

## Design decisions (case-by-case parity resolution)
Canonical behavior = the **REST bulk route** (AC3 requires its characterization test to pass unchanged).
The AI path is corrected to match. Resolved divergences (AI path → canonical):

| Field/behavior | Old AI tool | Old REST route | **Canonical (service)** |
|---|---|---|---|
| upsert match key | `{student_id, class_id, date}` | `{student_id, date}` | `{student_id, date}` |
| `source` field | `"ai_dispatch"` | `"bulk"` | `"bulk"` |
| `created_at` on record | present | absent | absent (model has none) |
| audit `action` | `"mark_attendance"` | `"attendance_bulk"` | `"attendance_bulk"` |
| audit `changes` | `{date, records}` | `{count_marked, date, class_id}` | `{count_marked, date, class_id}` |
| audit `changed_by_name` | present | absent | absent |
| idempotency | none | `Idempotency-Key` header + `attendance_bulk_keys` | service param `idempotency_key` (REST passes header; AI passes None) |
| record write doc | hand-built | `StudentAttendance` model + `_id`+`source` | `StudentAttendance` model + `_id`+`source` |

**Scoping note (grep audit):** the bulk match uses `scoped_filter` (school-wide), NOT
`scoped_query(branch_id=...)`, **intentionally** — `student_attendance` carries no
`branch_id` field and its unique index is `(student_id, date)` school-wide. Migrating
to `scoped_query(branch_id=...)` would make branch-scoped actors' upserts miss the
existing (branch-less) row → DuplicateKey on the unique index. The intentional comment
satisfies the CLAUDE.md grep-audit rule. `actor_ctx.branch_id` is still carried for the
audit row and future per-step re-scoping (Epic F).

**Provenance:** AI vs UI is distinguished by the write-ahead AI-dispatch audit
(`_execute_confirmed_dispatch`, unchanged) — NOT by the `source` field. FR13 requires
the record itself to be byte-identical, so `source="bulk"` for both is correct.

**Session:** `session=` is forwarded to Mongo ops ONLY when non-None (always None until
Epic D); avoids passing `session=` to `FakeCollection.update_one`, which has no such param.

## Tasks
- [x] `services/actor_context.py` — `ActorContext` dataclass + `actor_ctx_from_user` helper (honors `(now_fn or _now)()`).
- [x] `services/attendance_service.py` — `mark_attendance(...)`.
- [x] Refactor `routes/attendance.py::mark_student_attendance` → thin adapter.
- [x] Refactor `ai/tool_functions_v2.py::tool_mark_attendance` → thin adapter.
- [x] `tests/backend/unit/test_attendance_service_a1.py` — characterization + actor_ctx contract.
- [x] `tests/backend/parity/attendance_parity_test.py` — dual-entrypoint state-diff.
- [x] Grep audit on `attendance.py`; full suite vs pinned baseline (zero new failures).
