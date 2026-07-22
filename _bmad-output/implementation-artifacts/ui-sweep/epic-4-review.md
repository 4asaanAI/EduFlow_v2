# Epic 4 — Quality Gate Output

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

Review lenses applied over the epic's combined diff: code review, adversarial
general, edge-case hunter, test review, AC trace, NFR, plus the scoped-query audit.

> **Honesty note on the gate.** Epic 3/9's retrospective required a **frozen diff**.
> This gate was *mostly* frozen: lenses 1–7 ran over the complete Stories 4.1–4.5 diff.
> The owner then sent two live findings mid-gate (column sorting; the Class Strength
> "Other == Total" column). Those were implemented and then re-reviewed with the same
> lenses, and the full suite, build and audit were re-run afterwards over everything.
> So the gate was applied twice rather than continuously — but it was not applied to a
> single frozen artefact end to end, and that is stated rather than implied.

---

## Findings — all fixed in-run

| # | Sev | Where | Finding | Fix | Regression test |
|---|---|---|---|---|---|
| F-1 | 🔴 | `_bmad-output/planning-artifacts/epics-ui-sweep-2026-07-22.md` | The epic set recorded owner item 7 as an FR5 **scoping** fault. It is not — it is a double result envelope. Implementing from the map would have hunted a scoping bug and "fixed" the display with fallbacks, the exact anti-pattern the PRIME DIRECTIVE forbids. | Root cause established before story creation; coverage map corrected in place, stating the earlier hypothesis was disproved. A scoping fault does exist on the same endpoint and is a *different* defect (F-2). | `test_response_is_the_tools_own_envelope` |
| F-2 | 🔴 | `backend/routes/tools.py` | Three unguarded behaviours vs the chat door: gated on role alone (ignoring 49 `sub_categories` entries + the Phase-1 lockdown); could invoke **write** tools with no confirm token / kill-switch / audit; passed no `scope`, so branch-bound users read every branch. | Story 4.5. **Put to the owner and approved before any code**, per D-18. Verified no screen depended on the gap first. | 5 tests incl. `test_branch_bound_caller_does_not_read_another_branch` |
| F-3 | 🔴 | `frontend/.../ChatInterface.js`, `OwnerTools.js` | **Introduced by this epic.** Making `attendance_rate` honest broke two health scores doing `parseFloat(rate) \|\| 0` — they would have scored a healthy school as failing every morning before the register was taken. The epic's own defect, in a new place. | Unmarked attendance excluded from the score and its weight redistributed; the report says so in words. Found by applying the shared-field rule from the last retrospective. | `HealthScoreAttendance.test.js` (2) |
| F-4 | 🟠 | `tests/support/e2e_backend.py` | The browser-test double returned the **correct** single envelope while production returned a double-wrapped one, so every browser test passed against a server that did not exist. This is why the defect survived a whole initiative. | Double confirmed to mirror production, with a comment stating that is its job. | — (the double itself) |
| F-5 | 🟠 | `backend/routes/tools.py` | **No tests of any kind** existed for the endpoint behind every tool screen; it was never registered in the test harness. | Registered in `conftest.py`; 12 tests added. | whole file |
| F-6 | 🟠 | `frontend/.../OwnerTools.js` | **Introduced by this epic.** `BoardSection`/`BoardSectionFailure` were declared *inside* the render function, giving them a new identity every render. | Hoisted to module level. | `pressing Retry does not throw keyboard focus off the button` |
| F-7 | 🟠 | `frontend/.../OwnerTools.js` | **Introduced by this epic.** Retrying flipped a failed section back to stale content for the duration of the request — reads as "it worked", and unmounts the Retry button. | A retrying section stays in its failure state; `message` cleared on success so a stale failure cannot be resurrected. | same |
| F-8 | 🟠 | `frontend/.../OwnerTools.js` | **Introduced by this epic.** Disabling the Retry button on press removes it from the tab order; the browser drops focus to the top of the document, so a keyboard user loses their place on every retry. | `aria-busy` + a re-entry guard instead of `disabled`. | same |
| F-9 | 🟠 | `frontend/.../OwnerTools.js` | **Introduced by this epic.** Two sections depend on the fee source, so both rendered `data-testid="board-section-error-fee"` — a duplicate id in the document. | `testId` decoupled from `sourceKey`. | `one failed section does not cost the other five` |
| F-10 | 🟠 | `tests/backend/api/test_ui_sweep_epic4_*.py` | **Introduced by this epic.** Blanket `docs[:] = []` cleanup wiped collections other test files seed — broke 6 parity tests. The FakeDb is a session-wide singleton. | Snapshot-and-restore in all three new files. | full-suite green |
| F-11 | 🟠 | `frontend/.../ToolPage.js` | `ActionBtn` swallowed `data-testid`, so ~25 tool screens were untestable except by text matching (UX-DR4). | Forwarded. | `ToolTableSorting.test.js` |
| F-12 | 🟠 | `backend/routes/students.py` | **Owner-reported mid-gate.** "Other" meant *not male and not female*, folding "recorded as other" together with "never captured". Gender is empty for all 1,802 students, so Other == Total on every row. | `not_recorded` counted separately; rule extracted to a testable `classify_gender()`. Boys/Girls tiles say "Not recorded". | 3 tests |
| F-13 | 🟠 | `frontend/.../ToolPage.js` | **Owner-reported mid-gate.** 33 tool tables had no column sorting (FR82). | Sorting added to the **shared** component — all 33 at once. Money/percent sort by value; styled cells see through to their text; blanks sort last. | `ToolTableSorting.test.js` (10) |
| F-14 | 🟡 | `tests/backend/api/test_ui_sweep_epic4_school_identity.py` | My hard-coded-identity grep produced two false positives — one was my own comment, one a truncated exemption. | Exemption matched on the full line before truncation; comment reworded. | itself |
| F-15 | 🟡 | `backend/routes/settings.py`, `services/org_config_service.py` | Pre-existing `scoped_filter(` hits without the `# branch-scope: intentional` annotation the standing audit expects (same class as D-17). | Annotated in the two files this epic changed semantically. | grep audit |

## Findings dismissed, with reasons

| Finding | Why dismissed |
|---|---|
| "Two dispatch paths into one tool registry is the real architectural defect; Epic 4 entrenches it." (architecture review) | **Correct, and deliberately deferred.** Story 4.5 walks it back partway by making both doors share one gate function. Extracting a single `invoke_tool()` that both chat and REST call is the right end state but is an AI-layer refactor, not a UI-sweep defect fix, and would put the assistant at risk inside a run about screens. Logged as **D-25**. |
| "Refusing write tools at REST will break an unknown caller in six months." | Checked before shipping rather than assumed: all 22 `executeTool` call sites are `get_*` reads, and no other caller exists in the repository. Recorded in the completion log, with the limit stated — callers outside this repository cannot be seen from here. |
| Asserting the Class Strength aggregation's arithmetic end-to-end | The in-memory double cannot evaluate `$cond`/`$toLower`/`$trim` and returns the same count for every bucket. A passing assertion would have been measuring the fake — the identical trap as F-4. The **rule** is tested exhaustively as a pure function; the arithmetic is on the human checklist. |
| The ~22 hand-rolled `<table>` elements | Genuinely out of a defect-repair epic's scope, and each needs its own data plumbing. Named explicitly rather than left implied — **D-24**. |
| `CI=true` frontend build (D-16) as a gate on new warnings | Still blocked by ~30 pre-existing `exhaustive-deps` warnings. Unchanged by this epic. |

## Scoped-filter / scoped-query audit — every touched backend file

| File | Hits | Verdict |
|---|---|---|
| `routes/tools.py` | 0 | now resolves scope explicitly (Story 4.5) |
| `routes/settings.py` | 1 | **annotated** — school-level config is shared by every branch |
| `routes/students.py` | 1 | pre-existing, school-wide aggregate; correct |
| `ai/tool_functions.py` | 0 | uses `_tenant_query` (both axes) throughout |
| `ai/context_builder.py` | 2 | 1 already annotated; 1 pre-existing school-wide |
| `ai/prompts.py`, `ai/tool_access.py`, `school_identity.py` | 0 | no DB access |
| `services/org_config_service.py` | 5 | 1 **annotated**; 4 are branch CRUD where `branch_id` is the subject |
| `routes/chat.py` | 6 | pre-existing, per-user conversations; branch filtering is meaningless. Only `_is_tool_authorized` was touched — annotating 6 unrelated lines would be churn in the diff. Extends **D-17**. |

## NFR check

| NFR | Result |
|---|---|
| NFR-A1 contrast | No new colour pairs; the committed contrast test still passes. |
| NFR-A2 focus | Retry keeps focus (F-8). Sort headings are real `<button>`s. |
| WCAG colour-not-only | The three `StatCard` states differ by **text and border style**, never colour alone. |
| Screen reader | `aria-sort` on `<th>`; `role="alert"` on failure states; `aria-busy` while retrying. |
| NFR-P1 | No new per-request query — the assistant's projection was widened, not joined. |
| NFR-S1 / FR4 | Story 4.5 strengthens server-side enforcement; nothing weakened. |
| Error opacity (P3) | The endpoint no longer returns `str(e)` to the caller. |

## AC trace

Every AC on Stories 4.1–4.5 maps to at least one test, except three that cannot be
asserted in jsdom or against the fake and are on the human checklist, named there and
**explicitly marked not verified by this run**:

1. The PDF's rendered content with a section missing (jsPDF is mocked out).
2. The Class Strength aggregation's arithmetic against real Mongo.
3. Anything requiring a save against live data — Story 4.3's stored values.

## Final counts

| | Result |
|---|---|
| Backend | **1784 passed, 2 failed (pinned D-03), 14 deselected** |
| Frontend | **184 passed, 2 failed (pre-existing LayoutRouting)** |
| New tests this epic | **66** (39 backend, 27 frontend) |
| Production build | **passes** (one pre-existing `html2pdf.js` source-map warning) |
| Live-data writes | **0** |
