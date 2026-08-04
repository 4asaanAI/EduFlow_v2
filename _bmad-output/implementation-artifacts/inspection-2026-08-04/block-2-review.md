# BLOCK 2 — quality gate output (T6–T10), 2026-08-04

Lenses applied over the whole block's combined diff: code review, adversarial-general,
edge-case hunter, test review, and requirements trace. The BMAD skills were not invoked
as skills in this harness; the equivalent passes were run manually against the same
criteria, which the protocol permits.

## Findings

| # | Sev | File | Issue | Fix | Regression test |
|---|---|---|---|---|---|
| F-1 | **high** | `ai/tool_functions_v2.py` (house details) | Captains were filtered out of the **capped** member page. Once T6 made `member_count` report the true roll (720), a captain sitting at row 600 vanished while the count confidently said 720 — a defect this block *created* by half-fixing the read. | Captains are now queried by role (`house_role in [captain, vice_captain]`), independent of the member page. | `test_house_captain_past_the_page_is_still_found` — a captain seeded at row 600 must appear. Fails before, passes after. |
| F-2 | **high** | `tests/backend/mongo_real/conftest.py` | The 13 write-rollback tests could never run. A module-scoped async fixture created the Motor client on the module loop and handed it to function-scoped tests; Motor binds to its creating loop, so every test errored "attached to a different loop" before any assertion. This is why the tier had never passed *or* failed. | Split the fixture: URL + container lifecycle (not loop-bound) stay module-scoped; the client is created per test on that test's loop. | The tier itself is the test — it now runs green, 13 passed. Command recorded in `mongo_real/README.md`. |
| F-3 | medium | `ai/tool_functions_v2.py` (`tool_get_my_class_students`) | Class names were fetched with a hard `.to_list(20)`. A teacher assigned 21+ sections silently lost class labels on the extras. | Cap is now the number of ids actually asked for. | Covered by the existing class-label assertions; the pattern is asserted generally in `test_student_search_does_one_class_read_not_one_per_student`. |
| F-4 | medium | `ai/tool_functions_v2.py` (exam summary) | Per-exam results were capped at 200 each. A whole-school exam was cut in silence — invisible because it was also an N+1. | Batched into one read across all exams, uncapped per exam. | Full suite regression; no per-exam slicing remains. |
| F-5 | low | `routes/fees.py` (class summary) | Per-class student list was capped at 200, so `total_students` under-reported a large class. | Removed by the batching — the roster is now read once, in full. | Full suite regression. |

## Dismissed, with reasons

| Concern | Why dismissed |
|---|---|
| "T8's trim is a permission change in disguise." | It is consulted in exactly one place — building the chat tool list, and only when no tool is named explicitly. `is_tool_authorized` is untouched and is still the only gate at dispatch. `test_excluded_tools_are_still_authorized` and `test_an_excluded_tool_is_still_advertised_when_named_explicitly` assert both halves directly. |
| "Trimming could hide a read tool Flo needs to answer." | `test_exclusion_list_contains_no_read_tools` asserts every excluded name is a write/action tool, using the same `is_action_tool` predicate the write registry is derived from. |
| "The exclusion list will rot as tools are renamed." | `test_excluded_tools_are_still_authorized` looks each name up in `TOOL_REGISTRY` and fails if it is not a real tool. |
| "Turning off the second call regresses the R11.3 streaming contract." | The contract test was kept and now switches the flag on explicitly, so the streaming path stays guarded for the day it is switched back. It was not deleted or weakened. |
| `_find_capped` races: rows deleted between the fetch and the count could make `total < len(rows)`. | Then no truncation is reported — the code errs toward not stating a number it cannot stand behind, which is the safe direction. It never over-claims. |
| "Batching changed tenancy somewhere." | Each `_map_by_id` composes tenancy the same way the per-row lookup it replaced did (`_tenant_query`, `_academic_query`, or `scoped_query(branch_id=…)`). The audit below confirms exactly one new `scoped_filter(` hit in the whole block, and it mirrors its predecessor. |
| Two remaining in-loop `find_one` calls (timetable import, fee sync). | Both are the read-before-write of an upsert loop and must observe rows written earlier in the same run. Batching them would be a correctness regression, not an optimisation. Both now carry a comment saying so, so the next audit does not "fix" them. |
| The 2 frontend `LayoutRouting.test.js` failures. | Pre-existing, unchanged by this block, owned by T12 in BLOCK 3. |
| The 48 build warnings. | Pre-existing, unchanged count, owned by T11 in BLOCK 3. |

## Test review

- Every new test file carries `from __future__ import annotations` and, where async,
  `pytestmark = pytest.mark.asyncio`.
- The T7 guard asserts an **absence** (no per-row query) rather than a timing, so it
  cannot flake on a slow machine.
- The T8 guard asserts the absence of the second model call, not merely that it is
  cheaper — the saving is the deliverable, so the absence is what is checked.
- No new endpoint was added, so the 401/403 convention has nothing new to cover.
- Parametrisation used only for the two untouched roles (accountant, teacher), never
  across a security boundary.

## Trace (requirement → proof)

| Requirement | Proof |
|---|---|
| NEW-05 truncation never silent | `test_student_search_over_the_cap_reports_the_true_total` |
| NEW-05 no false alarm under the cap | `test_student_search_under_the_cap_claims_no_truncation` |
| NEW-05 counts are the real roll | `test_house_details_member_count_is_the_true_total`, `…captain_past_the_page…` |
| NEW-04 no per-row lookups | `test_student_search_does_one_class_read_not_one_per_student` |
| NEW-04 empty input costs nothing | `test_class_lookup_is_skipped_entirely_when_no_student_has_a_class` |
| NEW-12 list is smaller | `test_owner_tool_list_is_smaller_than_the_authorized_set` |
| NEW-12 permissions unchanged | `test_excluded_tools_are_still_authorized`, `…named_explicitly`, `test_smaller_roles_are_untouched` |
| NEW-12 second call gone by default | `test_second_call_is_off_by_default_and_answer_still_arrives` |
| NEW-12 streaming still works when on | `test_owner_turn_streams_final_answer` |
| NEW-13 draft_document covered | 3 new corpus conversations; structural + judge-logic evals green |
| NEW-06 rollback guarantees hold | 13 passed on a real replica set |

## Final counts

- Backend suite: **2005 passed / 0 failed / 14 deselected**
- Real-Mongo tier: **13 passed**
- Evals (structural + judge-logic): **18 passed / 1 deselected**
- Frontend: **282 passed / 2 failed** (pre-existing, T12)
- Production build: compiles, **48** warnings (pre-existing, T11)

## scoped_filter / scoped_query audit

Re-run on every touched backend file. This block introduced exactly one new
`scoped_filter(` hit — `routes/search.py:129`, the batched class lookup — and it carries
the same school scoping as the per-row `scoped_filter({"id": …})` it replaced. All other
hits predate this block and belong to D-17.

## AI-layer eval gate

`ai/tool_functions.py`, `ai/tool_functions_v2.py`, `ai/context_builder.py` and the chat
tool-loop were all touched, so the gate applies. Structural + judge-logic evals: green.
The credentialed LLM-judge tier could not run (T9, no credentials on this machine) and is
recorded as blocked rather than skipped quietly.
