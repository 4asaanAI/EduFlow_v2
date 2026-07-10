# Epic R5 — Epic-Close Quality Gate

**Date:** 2026-07-08 · **Reviewed diff:** `tool_functions_v2.py`, `scope_resolver.py`, `context_builder.py` + 2 new test files + 1 updated test.

## STEP 4a — Tests
`python -m pytest tests/backend/ -q` → **1411 passed, 14 deselected, 0 skipped** (baseline 1396 → +15 new R5 tests). 0 regressions.
Eval structural + judge-logic tier (`tests/backend/evals/test_eval_corpus_structure.py`, `test_eval_judge_logic.py`) → **18 passed**. Credentialed LLM-judge tier stays deferred (no Azure creds in dev — DEFERRED row 21); STEP 4e structural comparison green.

## STEP 4b — Review lenses (applied manually per protocol)

| Lens | Findings | Resolution |
|------|----------|------------|
| code-review (correctness) | After `query = scoped_query(...)`, later `query["k"]=v` / `{**query}` produce a top-level `$and` sibling — valid Mongo implicit-AND. Verified each of 11 sites. | No change needed. |
| adversarial-general | Could a branch-bound user still cross branches via a directly-supplied `class_id` to `mark_attendance`? YES (name lookup was scoped, direct id was not). | **Fixed in-run:** direct `class_id` validated against a branch-scoped class lookup before write. |
| edge-case-hunter | `re.escape` + `\b` anchoring: does "Class 1-A" still match range 1-5? Boundary is between `1` and `-` → matches. "Class 10" → no boundary between `1` and `0` → excluded. | Verified by `test_coordinator_range_matches_suffixed_class_names`. |
| edge-case-hunter | `_IMPOSSIBLE_FILTER` mutation safety — returned via `dict(...)` copy so a caller mutating it cannot poison the module constant. | No change needed. |
| edge-case-hunter | Owner/principal without JWT branch: `_branch_id` → `None` → `scoped_query`/`_branch_scoped` no-op → school-wide preserved. | Covered by `test_student_database_owner_sees_all_branches`. |
| testarch-trace | Every AC traced to a test (R5.1 AC1/AC2, R5.2 AC1/AC2, R5.3 AC1–AC5). | See mapping in epic-R5-completed.md. |
| testarch-nfr | Perf: branch clause adds one `$and` term; no new round-trips except one branch-scoped class existence check on the `mark_attendance` write path (write path, not hot read). Security: fail-closed everywhere; no regression to confirm-token/kill-switch/lockdown/audit. | Acceptable. |

## STEP 4c — Findings fixed in-run
1. `mark_attendance` direct-`class_id` cross-branch write gap → branch existence check added + regression test.

## STEP 4d — Scoped grep audit (touched backend files)
- `tool_functions_v2.py`: `_apply_branch_filter` → **0**; `scoped_filter(` → **0** (all branch reads via `scoped_query`).
- `scope_resolver.py`: lookups use `_branch_scoped` (branch axis; `schoolId` via `ScopedCollection`); no bare `{}` school-wide student/fee/exam filters remain (impossible filter on empty scope).
- `context_builder.py`: only pre-existing `scoped_filter` hits, one already carrying `# branch-scope: intentional`; my change added no new query.

## STEP 4e — Eval
Structural/judge-logic green (18). Credentialed judge deferred (no creds); no prompt files changed in R5, so no prose-quality regression risk.

## Verdict
Gate clean. No findings carried into R6.
