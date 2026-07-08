# Epic R5 — Tenancy & Scope Fail-Closed — COMPLETED

**Date:** 2026-07-08 · **Branch:** `ai-reliability-r1-turn-completion` · **Fixes:** H4, X6, L6 (+ DEFERRED row 18)
**Baseline in:** 1396 passed / 0 failed · **Baseline out:** 1411 passed / 0 failed / 14 deselected / 0 skipped
**Goal met:** empty/ambiguous scope never widens access; a branch-bound user sees only their branch; owners/principals without a JWT branch stay school-wide by design.

---

## R5.1 — Branch-scoping sweep of read tools (H4)

**Root cause:** `_apply_branch_filter(query, scope)` consulted ONLY the resolved `scope`, never the JWT. A branch-bound admin whose scope lacked a `branch_id` read every branch's data.

**Fix:** deleted `_apply_branch_filter`; every read tool now uses
`query = scoped_query(query, branch_id=_branch_id(user, scope))` — prefers the JWT branch, falls closed. Owner/principal (no JWT branch → `_branch_id` returns `None`) stay school-wide.

Files: `backend/ai/tool_functions_v2.py` — 11 call sites migrated:
`tool_get_student_database`, `tool_get_fee_structures`, `tool_get_class_wise_attendance`, `tool_get_class_list`, `tool_get_fee_defaulters`, `tool_get_house_standings`, `tool_get_student_council` (×2 incl. fallback), `tool_get_library_status`, `tool_get_transport_status`, `tool_get_inventory_status`.

- **AC1** ✅ Every site uses `scoped_query(..., branch_id=_branch_id(user, scope))`; grep audit: 0 remaining `_apply_branch_filter`, 0 `scoped_filter(` in the file.
- **AC2** ✅ Cross-branch fixture tests: `tool_get_student_database` (branch-A admin sees only branch-A; owner sees all), `tool_get_class_list`, `tool_get_house_standings`.

## R5.2 — Branch-scope the `find_one` lookups (H4)

Files: `backend/ai/tool_functions_v2.py`.
- **AC1** ✅ `tool_get_student_profile` — both the `student_id` and `search_term` `find_one` lookups branch-scoped. Branch-A admin cannot read a branch-B profile (returns empty, not the record).
- **AC2** ✅ `tool_award_house_points` name lookup and `tool_mark_attendance` class-name lookup branch-scoped. **Defense-in-depth (discovery, fixed in-run):** `mark_attendance` also validates a *directly-supplied* `class_id` against a branch-scoped class lookup before writing — `student_attendance` carries no `branch_id`, so the service cannot re-check downstream.

Tests: `test_r5_branch_isolation.py` — cross-branch profile blocked / same-branch succeeds; cross-branch house-points not-found; direct cross-branch `class_id` rejected.

## R5.3 — scope_resolver fail-closed (X6, L6)

Files: `backend/ai/scope_resolver.py`.
- **AC1** ✅ Coordinator range regex anchored: prefixes `re.escape`d and suffixed with `\b`, so `"Class 1"` matches `"Class 1"`/`"Class 1-A"` but never `"Class 10/11/12"`. Applied in the standard-range path and `_parse_custom_range`.
- **AC2** ✅ Zero resolved classes → `_IMPOSSIBLE_FILTER = {"id": {"$in": []}}`, never `{}`. Covers HOD subject scope with no classes and `class_list` with empty `class_ids`. `can_see_personal_info` no longer blanket-returns `True` for `type="subject"` when `class_ids` is empty (was a school-wide personal-info leak).
- **AC3** ✅ `class_list` scope over `fee_transactions`/`exam_results` returns the impossible filter (was `{}` = every fee/exam row school-wide).
- **AC4** ✅ All interpolated `$regex` fragments `re.escape`d — HOD subject `"C++"` no longer crashes the resolver.
- **AC5 / L6** ✅ HOD/coordinator/class-teacher/subject-teacher/KG/legacy class lookups branch-scoped (via `_branch_scoped`, which adds only the branch axis since these run against a `ScopedCollection` that injects `schoolId`). `class_teacher_id`/`teacher_id` matched against BOTH the staff record `id` and the login `user_id`, consistent with `tool_get_class_list`.

**Also (DEFERRED row 18, R3→R5):** `context_builder.py` default-admin fall-through no longer serves the **principal** context to `it_tech`/`maintenance`/`management`/`support_staff`/legacy sub_categories — they get a minimal context, aligned with scope_resolver's deny-by-default (was a silent school-wide over-exposure).

Tests: `test_r5_scope_fail_closed.py` (8 tests) + updated `test_scope_resolver.py::test_scope_filter_class_list_empty_yields_impossible_filter`.

---

## Design notes
- **Why `_branch_scoped` in scope_resolver, not `scoped_query`:** these lookups run against a `ScopedCollection` that already injects `schoolId`; adding only the branch clause mirrors the existing `Scope.filter()` composition and keeps the school-agnostic FakeDb unit tests (which seed docs without `schoolId`) valid. The tool layer uses the canonical `scoped_query` (docs there carry `schoolId`).
- **Fail-closed direction accepted:** HOD subject scope over non-student collections now returns the impossible filter instead of `{}`. This is the safe direction (X6 was fail-*open*); if HODs later need scoped exam access it is a separate, explicit feature.
