# BLOCK 2 — completed (T6–T10), 2026-08-04

Branch `inspection-remediation-2026-08-04`. **Not merged to main.**
Theme: correctness under real data volume, and cost.

| Task | Finding | Status |
|---|---|---|
| T6 | NEW-05 silent truncation at 500 rows | ✅ Done |
| T7 | NEW-04 one-query-per-row loops | ✅ Done |
| T8 | NEW-12 per-message AI cost | ✅ Done (both halves; owner approved half 2) |
| T9 | NEW-13 AI answer-quality baseline | ⏸ Blocked on owner — corpus half done, no Azure credentials here |
| T10 | NEW-06 write-rollback safety tests | ✅ Done — first real run ever; found and fixed a harness defect |

---

## T6 · NEW-05 — a capped read must say it was capped

**Root fix, not a message.** The cap stays at 500 (raising it would spend exactly the
token budget T8 is cutting); what changed is that a cut can no longer be silent.

`ai/tool_functions_v2.py`:
- `_find_capped(collection, query, projection, limit, sort) -> (rows, total)` — fetches
  `limit + 1` rows so it *knows* more existed, and only then pays for `count_documents`.
  A read that fits its cap costs exactly what it cost before.
- `_ok(data, ms, message, total=None)` — when the cap actually bit, meta gains `total`,
  `showing_first`, `truncated`, and the message gains a plain sentence Flo can relay
  ("Showing the first 500 of 1,802 matching records…"). Backwards compatible: callers
  that pass no `total` are byte-identical to before.

Applied to the two named reads plus three more the audit surfaced that can genuinely
pass 500 in a 1,802-student school:

| Read | Why it needed it |
|---|---|
| `tool_get_student_database` (:372) | reachable with no class filter — 500 of 1,802 |
| `tool_get_house_details` members (:1073) | 4 houses × 1,802 sits right on the edge |
| `tool_get_my_class_students` (:901) | a teacher with many sections passes 500 |
| library overdue, teacher branch (:1303) | the roster feeds an `$in` — a cut drops books |
| `tool_query_fee_status` (:2113) | school-wide fee transactions pass 500 inside a term |

Two correctness bugs fell out of the same work:
- **`member_count` was the page size, not the roll.** A 720-member house reported 500.
  It now reports 720, with `members_listed` alongside.
- **Captains were sliced out of the capped page** (found in this block's own review, see
  `block-2-review.md` F-1). A captain at row 600 vanished while `member_count` said 720.
  Captains are now asked for by role, independent of the page.
- A fixed `.to_list(20)` on a teacher's class-name lookup became "the number of ids
  actually asked for" — a teacher with 21 sections was losing class labels.

**Audit of the other caps:** reads that cannot reach 1,802 in this school (staff ≈ 90,
one class ≈ 60, one exam, one day's staff attendance) are left at their cap with a
`NEW-05/T6 audit:` comment saying why, so the next audit does not re-derive them.

Tests: `tests/backend/unit/test_inspection_block2_scale.py` (4 for T6).

## T7 · NEW-04 — no database call inside a loop body

The register said 53. A repeatable detector (walk each file, track `for`/`while` bodies,
flag any `await db.*.find*` inside one) found **27** live sites — the register's number
double-counted across the two AI tool files. All 27 were worked, AI layer first.

Worst cases removed:

| Was | Now |
|---|---|
| student search: `find_one` per student — up to **501 round trips** | 1 batched `$in` |
| staff late-arrivals: 5 queries × every staff member (~450) | 1 query over 5 dates |
| substitution planner: 3 queries per timetable slot | 3 batched reads total |
| class fee summary: 2 queries per class (100 for 50 classes) | 2 reads, grouped in memory |
| SMS send: 2 lookups per recipient (up to 1,000 per send) | 2 batched reads |
| context builder: 2 counts per class on **every message** (16) | 2 batched reads |
| exam summary: 1 query per exam, each capped at 200 | 1 read, uncapped by exam |
| student import: 1 duplicate query per row (1,800 for a full import) | 1 read per class |

Shared helpers rather than 27 hand-rolled dicts: `_map_by_id` in `ai/tool_functions.py`
(tenancy via `_tenant_query`), `ai/tool_functions_v2.py`, and `routes/academics.py`
(tenancy via `_academic_query`). Each composes tenancy exactly the way the per-row
lookup it replaced did — this task moved no tenancy boundary.

**Two sites deliberately NOT batched**, now carrying a comment saying why:
`routes/academics.py` timetable import and `services/fee_sync_service.py` — both are the
read-before-write of an upsert loop and must see rows written earlier in the same run.
A pre-fetched snapshot would be wrong, not just different.

Regression guard: a call-counting fake collection asserts the student search issues
exactly **one** class read for 300 students, and **none at all** when no student has a
class. It fails loudly if anyone reintroduces a per-row lookup.

## T8 · NEW-12 — the cost of an owner's message

**Half 1 — trim what is offered.** `ai/tool_chat_exclusions.py` holds `EXCLUDE_FOR_ROLE`
and is consulted in exactly one place: where the chat tool list is built, and only when
no tool was named explicitly.

The safety argument, asserted by test rather than claimed: this changes what is
**offered**, never what is **allowed**. `ai/tool_access.is_tool_authorized` is untouched
and is still the only thing consulted at dispatch, so an excluded tool remains permitted,
remains reachable from the tool panel and from a suggested action, and is still
advertised when named via `only={...}`.

26 structural configuration tools are trimmed for owner and principal only — branches,
classes, houses, fee structures, discount types, asset and transport registers, school
settings, year-end transition, and list-screen deletes. These are done deliberately, on a
screen, with a form in front of you. Everyday work (record a payment, mark attendance,
apply a discount, create a student, draft a document) is explicitly asserted to stay.

Measured: **owner 107 → 81 tools**, tools block ~11,700 → ~8,750 tokens. Accountant,
teacher and student lists are asserted to be untouched.

**Half 2 — stop re-saying the answer.** Asked Abhimanyu in plain English; he chose to
turn the typing-out effect off. A normal turn made **two** model calls: one to work the
answer out, a second to re-synthesise the same answer purely so it could stream word by
word. `AI_STREAM_SECOND_CALL` now gates it, defaulting **off**; set it to `true` in the
environment to bring the effect back with no code change and no new behaviour to deploy.

The existing R11.3 streaming contract test was **not weakened** — it now switches the
flag on explicitly, so the streaming path stays guarded for the day it is switched back.
A new test asserts that at the default no second call is made and the answer still
arrives and is still saved.

Combined: an owner turn drops from ~43,000 input tokens to roughly ~17,000.

Tests: `tests/backend/unit/test_inspection_block2_chat_cost.py` (6),
`tests/backend/api/test_r11_native_function_calling.py` (+1).

## T9 · NEW-13 — ⏸ Blocked on owner

**Done:** the coverage gap from D-37 is closed. Three `draft_document` conversations were
added to the corpus (owner letter, principal circular, Hinglish teacher note), each with a
rubric that explicitly requires the **download link** to be present — a document with no
way to fetch it is the exact D-37 failure. Corpus is now **55** conversations; structural
and judge-logic evals are green with them in.

**Not done, and not faked:** this machine has no Azure OpenAI endpoint or key (checked
`.env` and `backend/.env`), so `pytest -m llm_eval` has nothing to call. Per the register's
own instruction, **no substitute-model baseline was committed** — a baseline recorded
against the wrong model is worse than no baseline, because it looks authoritative.

## T10 · NEW-06 — the write-rollback tests, run for the first time

They had never passed and never failed. Now they pass — but only after fixing a defect
that had made the whole tier impossible to run.

**The finding (recorded as F-2 in the review log):** `mongo_real/conftest.py` created the
Motor client in a **module-scoped** async fixture and handed it to function-scoped tests.
Motor binds to the asyncio loop it was created on, so every single test errored with
"attached to a different loop" *before one assertion ran*. Fixed by splitting the fixture:
the URL and container lifecycle (not loop-bound) stay module-scoped; the client is created
per test, on that test's loop.

**Result: 13 passed** — transaction commit and rollback, executor rollback, idempotency
under concurrency, precondition revalidation, atomic multi-step plans, dry-run persisting
nothing, and cross-tenant transaction scoping. (The register said 14; the tier collects 13.)

**Environment note worth keeping:** MongoDB **8.3** from `winget` will not start on this
Windows 10 build — it exits with `STATUS_ENTRYPOINT_NOT_FOUND` before printing anything,
and the installed service cannot start either. MongoDB **7.0.16** from the fastdl zip works.
The exact one-line command to repeat this run is now at the top of
`tests/backend/mongo_real/README.md`.

---

## Gate at close

- Backend: **2005 passed / 0 failed / 14 deselected**.
- Real-Mongo tier: **13 passed** (`-m mongo_real`).
- Evals: **18 passed** structural + judge-logic (the AI layer was touched).
- Frontend: **282 passed / 2 failed** — both `LayoutRouting.test.js`, pre-existing and
  owned by T12. Unchanged by this block.
- Production build compiles; **48** warnings, the same 48 as before (T11 owns them).
- scoped_filter/scoped_query audit on every touched backend file: this block introduced
  exactly one new `scoped_filter(` hit (`routes/search.py:129`), and it carries the same
  tenancy as the per-row lookup it replaced. Every other hit is pre-existing (D-17).
