# Epic R7 — Epic-Close Quality Gate Review

**Date:** 2026-07-08
**Reviewer:** executing agent (self-review across the 5 mandatory lenses)
**Scope:** combined R7 diff — `ai/fee_metrics.py` (new), `ai/tool_functions.py`,
`ai/tool_functions_v2.py`, `ai/context_builder.py`, `services/audit_service.py`,
`routes/chat.py`, plus tests.

## Test results
- `python -m pytest tests/backend/ -q` → **1433 passed, 0 failed, 0 skipped** (14 deselected = credentialed llm_eval tier). Pinned baseline unchanged (no new failures, none of the 25 pinned failures reproduce).
- `pytest tests/backend/evals -q` → **18 passed** (always-on structural + judge-logic). Credentialed tier unchanged (no prompt/tool-schema change in this epic).

## Grep audit (scoped_filter / scoped_query)
- `tool_functions_v2.py`: two new `scoped_filter(...)` on `student_attendance` in branch-comparison — carry `# branch-scope: intentional` (collection has no branch_id; isolation via class_id ∈ branch classes). All other new reads (`fee_defaulters`, `class_list`, `class_wise_attendance`, `staff_list`, `leave_requests`) use `scoped_query(branch_id=...)` or operate on already-branch-filtered id sets.
- `context_builder.py`: new defaulter-count read uses `_tenant_query` (school-wide, intentional per existing ADR-003 note at top of file).

## Findings (found → fixed in-run)

| # | Severity | Lens | Issue | Fix | Regression test |
|---|----------|------|-------|-----|-----------------|
| 1 | High | edge-case | New `db.house_points` aggregation used a compound `_id` dict — unsupported by the test double AND an unhashable key risk. | Rewrote to a single `$in` find + Python grouping. | Covered by existing `test_ai_tools_new` house tests (green). |
| 2 | High | edge-case | `context_builder` defaulter count used `db.fee_transactions.distinct(...)` — not implemented by `FakeCollection`. | Switched to find + set of student_ids. | `test_context_builder` (green, fixture updated). |
| 3 | Med | adversarial | `detect_navigate` prefix-anchor could still fire on "why can't we open library…" if the verb led. | Strip polite lead-ins, require phrase to lead OR equal; a mid-sentence mention returns None. | `test_detect_navigate_anchors_on_command`. |
| 4 | Med | correctness | Exam pass-rate `/100` fallback would report 0% when the real max is e.g. 50. | Use exam/per-result `max_marks`; `"N/A"` when unknown. | `test_exam_pass_rate_uses_actual_max_marks`. |
| 5 | Med | correctness | Class attendance rate could exceed 100% from stray records for non-active students. | Count only active in-class students; clamp ≤100. | `test_attendance_rate_never_exceeds_100`. |
| 6 | Low | nfr | Keyword-tool keepalive coroutine was defined but never scheduled — a slow read could idle-timeout the SSE stream. | Run tool as a task; emit keepalive frames while it runs; cancel on exit. | Exercised by existing chat/stream suite (green). |

## Dismissed / accepted
- **`to_list(...)` caps** on batched reads (e.g. `student_attendance` windowed reads at 50k) are ample for a single-school-per-instance deployment; documented, not a defect.
- **Announcements without `event_date`** fall back to `sent_at` for the calendar date — intentional so news items created "today" still surface in the 7-day window; a genuine future event carries an explicit `event_date`.
- **`detect_navigate` prefix collisions** (e.g. "open attendance" vs "open attendance recorder") both map to the same tool — no user-visible ambiguity.

## NFR / trace
- Every R7 AC traces to a test or an existing green test (see completed doc's test table).
- No regression to the confirm-token → kill-switch → lockdown → audit gating; no change to DPDP redaction; no prompt/registry change (parity gate untouched).
