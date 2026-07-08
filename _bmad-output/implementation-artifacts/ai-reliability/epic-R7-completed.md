# Epic R7 — Data Correctness & Performance — COMPLETED

**Date:** 2026-07-08
**Branch:** ai-reliability-r1-turn-completion
**Fixes:** M3, M4, M5, M6, M7 + L2 (deferred-from-R4)

Goal: the numbers the assistant reports (attendance rates, fee totals, exam
pass-rates, event lists) are correct, and the read tools are fast.

---

## R7.1 — Wrong-collection & formula unification (M3, M5)

**New module:** `backend/ai/fee_metrics.py` — the single canonical fee-outstanding
math, imported by every caller:
- `compute_fee_totals(db, match)` → collected / outstanding / collection_rate.
- `student_outstanding_from_txns(txns)` → per-student owed (partial rows owe
  `amount - paid_amount`).
- `OUTSTANDING_STATUSES` / `DEFAULTER_STATUSES` constants.

| AC | What was done | Files |
|----|----------------|-------|
| AC1 | Branch comparison now reads `student_attendance` (was empty `attendance`). `student_attendance` has no `branch_id`, so it is scoped via this branch's `class_id`s. | `tool_functions_v2.py` `tool_get_branch_comparison` |
| AC2 | One shared helper used by **fee_summary, context_metrics, smart_alerts, fee_defaulters, context_builder** — all four agree. | `tool_functions.py`, `tool_functions_v2.py`, `context_builder.py`, `ai/fee_metrics.py` |
| AC3 | Defaulter = any student with an outstanding balance (overdue/pending/unpaid/partial), **not** only `status='overdue'`. Documented in `fee_metrics.py` docstring. `tool_get_fee_defaulters` and `context_builder.fee_defaulters` both use it. | `tool_functions_v2.py`, `context_builder.py` |

## R7.2 — N+1 batching (M4)

| AC | What was done | Files |
|----|----------------|-------|
| AC1 | Per-item DB queries inside loops replaced with `$in` batch + dict/aggregate: `class_wise_attendance`, `class_list`, `fee_defaulters`, `staff_list` (attendance), `leave_requests` (staff), `house_standings`, `house_details` (recent points), `student_council`. | `tool_functions_v2.py` |
| AC2 | Chronic-absence in `context_metrics` no longer capped at 50 students (the cap made the result *wrong*). Now batched over all students via a single windowed `student_attendance` read + in-memory scan (same shape smart_alerts already used). | `tool_functions.py` |

## R7.3 — Small correctness batch (M6, M7, misc)

| AC | What was done | Files |
|----|----------------|-------|
| AC1 | AI-created announcements now appear in `get_upcoming_events`. Root cause: created announcements are stored `status="active"` + `sent_at` (never `"published"`) and had no `event_date`. Fixed the events query to match the real visibility rule, added an optional `event_date` on create, and fall back to `sent_at` for the calendar date. | `tool_functions_v2.py` |
| AC2 | Exam pass-rate uses the **actual** `max_marks` (exam's, else per-result), never a silent `/100`; when max is unknown the rate is `"N/A"`. Class attendance rate is derived only from active in-class students and clamped so `>100%` is impossible. | `tool_functions_v2.py` |
| AC3 | `detect_navigate` anchors on the navigation verb — the command must lead the message (after stripping polite lead-ins), not match as a substring anywhere. | `routes/chat.py` |
| AC4 | `_extract_result_count` counts the envelope's own `data` list, never a stray first list field. | `routes/chat.py` |
| AC5 | Keyword-tool keepalive is now actually **started** (the read tool runs as a task and keepalive frames are emitted while it runs; previously the coroutine was defined but never scheduled and yielded nothing). Analytics `distinct_id` uses `user["id"]` (was `user.get("user_id")` → always `None`). | `routes/chat.py` |

## L2 (deferred from R4) — audit timestamp consistency

`_audit_doc` and `audit_service._normalise_doc` now stamp
`datetime.now(timezone.utc)`; the audit log is no longer a mix of naive-local and
UTC times.

---

## Tests added

`tests/backend/unit/test_r7_data_correctness.py` (8 tests):
- canonical fee totals + partial-remainder per-student owed
- defaulter includes pending-only student (AC3)
- branch comparison reads student_attendance (AC1/M3)
- exam pass-rate uses actual max_marks (AC2/M7)
- attendance rate never exceeds 100% (AC2/M7)
- `detect_navigate` anchors on command, ignores mid-sentence mentions (AC3)
- `_extract_result_count` counts the data list (AC4)

Two existing tests updated to the corrected contracts (documented, not silenced):
- `test_context_builder.py` fixture now gives fee txns realistic `student_id`s
  (defaulter is now per-student, matching fee_summary).
- `test_ai_tools_new.py` upcoming-events fixture uses the real stored shape
  (`status="active"` + `sent_at`) instead of the never-produced `"published"`.

## Gate results

- Full backend suite: **1433 passed, 0 failed, 0 skipped** (14 deselected = credentialed `llm_eval` tier).
- Always-on eval corpus (structural + judge-logic): **18 passed**.
- scoped_filter/scoped_query grep audit: the two new `student_attendance` reads
  in branch-comparison carry a `# branch-scope: intentional` comment (branch
  isolation is enforced via `class_id ∈ branch classes`; the collection has no
  `branch_id`). All other new reads use `scoped_query(branch_id=...)`.
