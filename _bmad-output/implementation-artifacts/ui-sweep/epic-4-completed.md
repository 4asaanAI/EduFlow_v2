# Epic 4 — Numbers And Details That Are Actually True — COMPLETED

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`
**Owner items closed:** 7 (Board Report zeroes), 8 (placeholder school data)
**Deferred items closed:** D-21 (in code; the stored values still need the Owner's save)
**Added mid-run at the owner's request:** column sorting on every tool table; the
Class Strength "Other == Total" defect.

---

## The root cause, established before any story was written

The owner reported item 7 as "the Board Report shows zeros". It was never a Board
Report defect.

Commit `8789fea` (epic R4 of the shipped AI-reliability initiative) made `_env()` in
`ai/tool_functions.py` the one tool-result envelope — `{success, data, meta, message,
denied}`. `routes/tools.py`, the non-chat tool-panel path, had not been touched since
Part 1.5 and still did `return {"success": True, "data": result}`, wrapping the
envelope in a second envelope.

Every screen that reads a tool therefore read one level too shallow, and every
`|| 0` / `|| 'N/A'` fallback fired. **Eleven surfaces, not one:** Board Report, School
Pulse, Fee Collection, Attendance Overview, Staff Tracker, Admission Funnel, Smart
Alerts, Financial Reports, AI Health Report, the health score in the chat greeting,
and a student's own My Attendance and My Results.

**Why nothing caught it for a whole initiative:** `tests/support/e2e_backend.py`
answered this endpoint with a *single* envelope — the correct contract — so every
browser test passed against a fake server that did not behave like the real one. And
`routes/tools.py` had **no tests of any kind**.

---

## Story 4.1 — One envelope, so every tool screen shows the real number

| | |
|---|---|
| Files | `backend/routes/tools.py`, `frontend/src/components/tools/OwnerTools.js`, `tests/support/e2e_backend.py`, `tests/backend/conftest.py` |
| Tests | `tests/backend/api/test_ui_sweep_epic4_tool_endpoint.py` (12) |

- The endpoint returns the tool's own envelope unchanged. There is one.
- The registry-wide regression asserts no tool's `data` is itself an envelope, so a
  third envelope in 2027 fails a test instead of showing zeros on a screen nobody
  opened.
- The one call site that had been "defensively fixed" (`r.data?.data ?? r.data` in the
  WhatsApp reminder modal) now reads `r.data`. All 22 `executeTool` call sites were
  examined individually; the rest were written against the pre-R4 contract, which is
  exactly what the endpoint now returns, so they are restored rather than changed.
- `routes/tools.py` was registered in the test harness for the first time.
- The browser-test double now mirrors production and carries a comment saying that is
  its job.

**Proven fails-before / passes-after:** with the pre-fix endpoint restored,
**9 of the 12 tests fail**; with the fix, all 12 pass.

## Story 4.2 — A zero means zero, and a failure says so

| | |
|---|---|
| Files | `backend/ai/tool_functions.py`, `frontend/src/components/tools/OwnerTools.js`, `frontend/src/components/tools/ToolPage.js`, `frontend/src/components/ChatInterface.js` |
| Tests | `tests/backend/api/test_ui_sweep_epic4_honest_numbers.py` (10), `StatCardHonesty.test.js` (5), `BoardReport.test.js` (10), `HealthScoreAttendance.test.js` (2) |

- **The number itself is honest, not just the card.** With nothing marked,
  `attendance_rate` said `0%` — which reads as "the school is empty" to a principal
  on a Monday morning. It now says **"not marked yet"**, and the 30-day average says
  **"not recorded"** rather than averaging nought. Both the screens and the assistant
  read these fields, so fixing the number once fixed both.
- `get_fee_summary` now reports `transactions_on_file`, so a **true** ₹0 can say why
  it is zero. The school has one fee record for 1,802 students.
- `StatCard` gained three states — `ok`, `unavailable`, `not-recorded` — distinguished
  by **text and a dashed border, not colour alone**, because the owner reads this on a
  phone in a meeting and will never hover anything.
- The Board Report's six sources now succeed or fail **independently**. A failed
  section shows one clear message and its own retry; it is never drawn as a figure.
  The banner names what is missing instead of promising a "partial report" and then
  showing nothing.
- A **second** failure reads differently from the first, so a retry that fails is
  distinguishable from a tap that did nothing.
- **The PDF still exports with sections missing**, printing "not available" rather
  than a fabricated `0` — a board document outlives the screen.
- `.catch(() => ({ data: [] }))` was removed from the staff and expenses calls: a 403
  used to render as "0 teachers".

## Story 4.3 — The school's own identity, stored once and complete

| | |
|---|---|
| Files | `backend/school_identity.py` (new), `backend/routes/settings.py`, `backend/services/org_config_service.py`, `frontend/src/components/tools/SchoolSettings.js`, `frontend/src/components/tools/AdminTools.js` |
| Tests | `tests/backend/api/test_ui_sweep_epic4_school_identity.py` (17) |

- One verified source for the school's identity, taken from **theaaryans.in** on
  Abhimanyu's instruction and reconciled against the printed prospectus.
- `affiliation_no` (2133014) and `school_code` (81936) now exist, are Owner-editable,
  and are in the server-side whitelist. A test asserts **every field the form posts is
  accepted**, so an edit can never be discarded behind a success message.
- The certificate generator reads the school record instead of a hard-coded
  `'Affiliated to CBSE · Joya, Amroha, Uttar Pradesh'` string, and now prints the
  affiliation number as a CBSE certificate should.
- A committed test greps the whole frontend and fails if any screen hard-codes the
  school's own identity again (D-15 was five files each writing it in separately).
- A field the Owner **deliberately clears** stays cleared; only absent fields fall back.

> **NOT YET VISIBLE TO THE OWNER.** The stored `address`, `phone`, `email` and
> `principal` are still the old placeholder values. Correcting them is a write to live
> data. Story 4.3 ships the audited in-app path and the verified values — the change
> reaches his screen when he saves them in School Settings, or approves the write.

## Story 4.4 — The assistant is briefed from the record, not a constant

| | |
|---|---|
| Files | `backend/ai/prompts.py`, `backend/ai/context_builder.py` |
| Tests | in `test_ui_sweep_epic4_school_identity.py` |

- **The assistant has never known the principal's name.** `build_system_prompt()` read
  `school_settings["principal_name"]`; the record stores `principal`. The lookup never
  once matched. The same prompt-vs-data drift class that epic R3 exists to prevent.
- The opening line and the organisation briefing are built from the stored record, so
  correcting the record corrects the assistant. A constant is why it kept saying
  "Lucknow" after the database had been fixed.
- A detail the school has not recorded is stated as **"not recorded"** — the assistant
  repeating a plausible phone number it invented is worse than admitting it has none.
- The fee-structure summary field reaches the briefing when recorded (entering it is a
  write and follows the same approval rule).
- The existing per-turn projection was **widened, not joined** — no second query.

## Story 4.5 — The screen tools play by the same rules as the assistant

**Asked and approved before any code was written**, per the D-18 rule.

| | |
|---|---|
| Files | `backend/ai/tool_access.py` (new), `backend/routes/tools.py`, `backend/routes/chat.py` |
| Tests | in `test_ui_sweep_epic4_tool_endpoint.py` |

The gate now lives in one module that both doors import, rather than two kept in sync
by discipline.

1. **Job category is honoured.** The endpoint gated on role alone, ignoring the 49
   registry entries carrying `sub_categories` and the Phase-1 lockdown.
2. **Reads only.** Write tools were invocable with no confirm token, kill-switch,
   lockdown or audit. Verified first that no screen depends on this: all 22
   `executeTool` call sites are `get_*` reads. A **frozen inventory test** fails if a
   new tool omits `dispatch_type`, so the door cannot silently widen.
3. **Branch scoping.** The endpoint called `fn(params, user)` with no scope, so
   `_tenant_query` emitted no `branch_id` clause and a branch-bound admin read every
   branch. `resolve_scope` is now called, exactly as the chat path does. The Owner
   still reads across branches, which is asserted.
4. An unknown tool and a forbidden tool are now indistinguishable from outside.

---

## Added mid-run at the owner's request (2026-07-22, while the gate was running)

### Column sorting on every tool table

> *"make sure that the sorting per column is available in every table that is present
> over the platform"*

Enumerated first rather than guessed: **2** screens used the shared server-sorted
table (Epic 3), **33** tables rendered through the older `ToolPage` `DataTable`, and
**~22** were hand-rolled `<table>` elements.

Sorting was added to the **shared `ToolPage` DataTable**, which gives all 33 at once —
the shared-component lever from the Epic 3/9 retrospective.

- Client-side, and that is correct **here**: these screens hand over their complete
  result set, so ordering the array *is* ordering the whole set. (`ui/DataTable` stays
  server-sorted because it is paginated, where a client sort would lie about the rest.)
- **Money and percentages sort by value.** As text, `₹1,20,000` sorts *below* `₹9,000`
  — which would put the largest debt at the bottom of a defaulters list.
- Sorting **sees through styled cells**; most screens wrap values in a coloured
  `<span>`, which would otherwise sort by `[object Object]` and appear to do nothing.
- Blanks and "not recorded" sort **last**, so the 1,802 students with no recorded date
  of birth do not fill page one.
- Real `<button>` headings with `aria-sort`; keyboard and screen-reader operable.
- The caller's array is never mutated, and **default order is unchanged until someone
  clicks** — so no screen's behaviour changes on its own.
- `sortable={false}` opts out a table whose order is itself the information.

Tests: `ToolTableSorting.test.js` (10).

**Still not sortable, honestly stated:** the ~22 hand-rolled `<table>` elements
(Attendance Recorder, Exam Manager, Fee Collection, Timetable Builder, Transport
Optimisation, Principal Daily Ops, parts of Teacher/Admin tools). Logged as **D-24**.

### Class Strength showed "Other" and "Total" as the same number

> *"not sure why there are 2 columns i.e. other and total giving the same number"*

Correct observation, and squarely this epic. "Other" meant *everything that is not
male or female*, which lumped a student **recorded** as another gender together with a
student whose gender was **never captured**. Gender is empty for all 1,802 students,
so Other equalled Total on every row, and the Boys/Girls tiles read `0`.

- The aggregation now counts `not_recorded` separately from `other`, and the rule
  lives in a plain `classify_gender()` function so it can be tested exhaustively.
- The Boys and Girls tiles say **"Not recorded — gender was never collected for these
  students"** rather than `0`.
- The table moved to the shared sortable component, with class order NUR → LKG → UKG →
  1st … 12th rather than alphabetical.

> **Honest note on the test:** the in-memory test double cannot evaluate
> `$cond`/`$toLower`/`$trim`, so it returns the same count for every bucket. Asserting
> the aggregation's arithmetic through it would have been measuring the fake, not the
> code — the same trap as the browser-test double. The **rule** is therefore tested
> exhaustively as a pure function, and the pipeline is asserted to mirror it. The
> arithmetic end-to-end is on the human checklist.

---

## Test counts

| | Before | After | New |
|---|---|---|---|
| Backend | 1745 passed / 2 pinned | **1784 passed / 2 pinned** | **39** |
| Frontend | 157 passed / 2 pre-existing | **184 passed / 2 pre-existing** | **27** |

**66 new tests.**

Backend suite run with `MONGO_URL` pinned to a local test database (D-04). The 2
backend failures are the pinned order-dependent pair (D-03); the 2 frontend failures
are the pre-existing `LayoutRouting` pair. Neither count moved.

Production build: **passes** (`npx craco build`), one pre-existing source-map warning
from `html2pdf.js`, unrelated.
