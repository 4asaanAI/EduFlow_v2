# UI Sweep — Deferred Work & Discoveries

Running log for the EduFlow UI Sweep initiative (owner-reported defects, 2026-07-22).
Rule 6: anything discovered mid-run is either fixed in that run or logged here with a
reason and a pointer. Never silently skipped.

Branch: `ui-sweep-2026-07-22`

---

## Timeline — what has actually happened

| Date | Run | Outcome |
|---|---|---|
| 2026-07-22 | Pre-epic | Responsive audit; found the earlier "fully screen-responsive" commit (807fd8f) was a CSS-only layer that missed ~25 dialogs, everything outside `.app-main-content`, and mobile viewport height. Fixed. |
| 2026-07-22 | Pre-epic | **Two regressions introduced and then fixed the same day** — see D-01. |
| 2026-07-22 | Pre-epic | Local dev unblocked: production CORS + AWS WAF were rejecting `localhost`. Solved with a dev-server proxy and a cookie allow-list (`frontend/src/setupProxy.js`). Root cause: PostHog's cookie is URL-encoded JSON, which WAF reads as an injection attempt; in production the analytics cookies never reach the API because page and API are different origins. |
| 2026-07-22 | Pre-epic | Read-only reconciliation of the school's source documents vs the live database → `_bmad-output/planning-artifacts/aaryans-source-of-truth-2026-07-22.md`. |
| 2026-07-22 | Pre-epic | Shipped: staff role/sub-category lockdown (frontend), staff `designation` display, mobile header + sidebar behaviour, class ordering, notification dot. Commits `401a4ac`, `ab206cb`, and the mobile-shell commit. |
| 2026-07-22 | Planning | `bmad-check-implementation-readiness` run → paused at step 1: **no epic document existed** for this work. `bmad-create-epics-and-stories` run → requirements inventory, 7 epics, coverage map, Epic 1 stories written. |
| 2026-07-22 | **Epic 8** | **Ask, Don't Just Change — DONE (same run).** Abhimanyu reversed Story 1.3 mid-run — nobody edits their own record — and asked for the approval flow. Staff and admin can request a correction to their own name/phone/email; Owner and Principal approve or reject it beside their leave approvals. A Principal cannot approve their own. 34 tests. Suite 1720 passed / 2 failed (pinned) / 14 deselected. |
| 2026-07-22 | **Epics 9 + 3** | **Looks Like The Brochure + Finding One Record Among Two Thousand — DONE.** Epic 9 was created mid-run at Abhimanyu's request (make the product look like `eduflow.layaa.ai`) and sequenced first so Epic 3's table was built once in the new language. Shipped: a token system with a committed WCAG contrast test, playful primitives, the mobile type scale (closes Epic 2's UX-DR7), "Flo" copied from the landing-page repo, the school crest behind the chat, a shared server-sorted table with rows-per-page, and school-order class sorting. 139 hard-coded theme colours removed from the shell. 127 new tests. Suite 1745 passed / 2 failed (pinned) / 14 deselected. **Closes D-05.** Adds D-15b, D-20, D-21, D-22, D-23. 8 live-data fields corrected and 1 stale branch deleted, each separately approved. **11 of 15 findings came from Abhimanyu testing live, not from the review passes — see the retrospective.** |
| 2026-07-22 | **Epic 1** | **Access That Cannot Be Talked Around — DONE.** Elicitation + party-mode passes rewrote the ACs before any code (E-1…E-9); 3 stories implemented; epic-close gate found 10 further findings, all fixed with regression tests. Owner role is now refused by the server for every caller including the Owner, in both directions; unrecognised job categories are refused; staff can maintain their own contact details. Suite 1682 passed / 2 failed (the pinned pair) / 14 deselected. **Closes D-02, D-11, D-12, D-13, D-14.** No production writes. |

---

## Open items

### D-01 — Regressions introduced 2026-07-22 (FIXED same day)
Two defects were shipped by this initiative and corrected within hours:
1. Setting `display:block` on tables with `display:table` on thead/tbody split each table
   into two independently-sized tables, so headings stopped aligning with their cells.
   Fixed with a `:has()` rule that scrolls the table's wrapper instead.
2. Forcing all form controls to 16px under `pointer: coarse` also fired in Chrome's
   device simulator, so dropdowns rendered at 16px beside 12px labels.
   Reverted; the correct fix is a mobile type scale (UX-DR7, Epic 2).
**Status:** closed. Recorded because the owner reported both, and because they are the
reason the epic-close adversarial review gate exists.

### D-02 (was RISK-1) — Owner-role restriction is frontend-only — **CLOSED 2026-07-22 (Epic 1, Story 1.1)**
"Owner" was removed from the staff role dropdown and reported to the owner as closing
the privilege-escalation hole. It did not: FR4 and NFR-S1 require server-side denial,
and the API still accepted `role: "owner"`. **This was mis-reported as complete.**

**Fixed:** the server now refuses any request that would grant owner authority through
the staff API, for **every** caller including the Owner, on both create and update, and
before any staff record or login account is written. Removal of owner authority is
refused too, so the school cannot be left with no owner and no in-app way to appoint
one. Every refusal is audited with the caller's id, and a failure of the audit write
does not turn the refusal into a server error. Proven by 44 tests written against the
API, deliberately bypassing the UI. The dropdown change remains as a second layer.
**Owner assignment is now out-of-band only** — see the human-verification checklist for
what that means in practice.

### D-03 (was RISK-2) — Two order-dependent backend test failures — **DEFERRED**
`tests/backend/api/test_r13_tenancy_rbac.py::test_scoped_collection_find_one_and_update_injects_school_id`
and `::test_scoped_collection_distinct_scopes_to_school` fail in a full-suite run but
pass in isolation (38 passed alone). Verified pre-existing by running the full suite
against a clean `main` worktree — identical two failures.
**Baseline for this initiative: 1636 passed, 2 failed, 14 deselected.**
**Reason deferred:** pre-existing, unrelated to this initiative, caused by shared state
left behind by an earlier test. Do not attribute to your own changes; do confirm the
count is still exactly 2 at each epic close.

### D-04 (was RISK-3) — Test runs could reach the production database — **CLOSED 2026-07-22**
`backend/.env` holds the live `MONGO_URL`, pulled from Elastic Beanstalk. `conftest.py`
used `os.environ.setdefault`, which does not override an already-present value, so an
exported variable or the `.env` file silently won and the suite would have run against
live data (1,802 students, 88 staff, 1,892 users).

**Fixed:** a fail-closed guard at the top of `tests/backend/conftest.py`, placed before
the `setdefault` calls and before any app import. It refuses to run when the effective
`MONGO_URL` looks like a hosted cluster (`mongodb+srv://` or `.mongodb.net`), checking
the environment first and falling back to `backend/.env` only when the environment does
not pin a value. The error message tells the developer exactly what to export.

Escape hatch for a deliberate remote run:
`EDUFLOW_ALLOW_PROD_DB_IN_TESTS=i-understand-this-can-write-to-production`.

**Verified both directions:** with no override the suite aborts at collection naming the
offending source; with `MONGO_URL` pinned to a local test database the full suite runs at
the pinned baseline — 1636 passed, 2 failed, 14 deselected. Approved by Abhimanyu.

### D-05 (was RISK-4) — `project-context.md` carries a stale fact — **DEFERRED**
It states "Sidebar width is 120px fixed". Actual: 260px, and 280px as a mobile drawer.
It is loaded as authoritative context by every BMAD workflow, so it misinforms agents.
**Reason deferred:** documentation-only; fix alongside Epic 2 (the sidebar epic).

### D-06 — Two students in the school's export are absent from the platform — **DEFERRED to Track 2**
Admission numbers `19968` and `211309` appear in `Students-22-06-2026.xlsx` (1,804 rows)
but not in the database (1,802). Possibly withdrawals, possibly a missed import.
**Action:** the school should confirm. Not a UI defect.

### D-07 — Six login accounts have no matching user record — **DEFERRED to Track 2**
`users` = 1,892 vs `auth_users` = 1,898. Cause unknown.

### D-08 — Leave types do not match the school's register — **DEFERRED, product decision**
The school's staff attendance register tracks Casual, Medical, **Special** and
**Without Pay**. The platform tracks Casual, Medical and **Earned**. So two of the
school's leave types cannot be recorded, and one platform type is unused.

### D-09 — The school's real staff vocabulary is unused — **DEFERRED, feeds Epic 7**
The register uses **PRIN / NTT / PRT / TGT / PGT / Other** (Principal, Nursery Teacher
Training, Primary, Trained Graduate, Post Graduate, Other). The platform uses
`class_teacher` / `subject_teacher`. Relevant to the roles redesign the owner asked to
see mocked both ways before building.

### D-10 — Nine admission-form fields have nowhere to be stored — **DEFERRED to Track 2**
From the printed enquiry form: student/father/mother Aadhar numbers, PEN (UDISE) number,
APAAR ID and consent, previous school attended, registration number, declaration/T.C.
undertaking. See §2 of the source-of-truth document.

### D-11 — Profile dialog shows the wrong city — **FIXED in Epic 1 (Story 1.3)**
`ProfileModal.js` printed a hard-coded "The Aaryans, Lucknow, CBSE". The school is in
Joya, Amroha (U.P.). Found by the Epic 1 party-mode pass. Fixed in-run because Story 1.3
rewrites that dialog anyway; the line now comes from the signed-in user's school rather
than a literal. The stored school record itself is still placeholder data — correcting it
is a WRITE and stays with Epic 4 / Track 2.

### D-12 — A staff record could be linked to someone else's login — **FIXED in Epic 1 (Story 1.1)**
`create_staff` accepted a caller-supplied `user_id`, and silently re-used any existing
login whose username matched the new staff member's email/phone/name. Either path let an
admin attach a new staff record to the **owner's** login. Deactivating that staff record
(`DELETE /api/staff/{id}`) deactivates the linked login and revokes its sessions — so any
admin could have locked the owner out of the school. Found by the Epic 1 red-team pass.
Fixed in-run: the link is refused when the target login holds owner authority or is
already claimed by another staff record. Out of Epic 1's literal scope, logged per rule 6.

### D-13 — The AI's staff tool advertised powers the server does not grant — **FIXED in Epic 1**
`ai/prompts.py` told the model that `create_staff` accepts `role: "owner"` and a
sub-category of `"accounts"` — a spelling `VALID_SUB_CATEGORIES` does not contain (the
canonical value is `"accountant"`). The same class of prompt↔registry drift the shipped
R3 epic was built to prevent. Corrected alongside Stories 1.1 and 1.2.

### D-14 — Three existing tests encoded the weaker contract — **RESOLVED in Epic 1**
`test_staff_routes.py::test_principal_cannot_change_staff_role`,
`::test_principal_self_update_cannot_escalate` and
`test_epic_j_crud_guardrails.py::test_principal_owner_only_fields_silently_stripped_on_update`
asserted that an attempt to grant owner authority returns 200 with the field silently
stripped. Story 1.1 makes that a hard 403. The tests were **rewritten, not deleted** —
each now asserts the stronger contract, and the silent-strip behaviour they were really
guarding (salary) is still covered by its own test.

### D-15 — The school's city was wrong in five places — **FIXED IN CODE 2026-07-22**
Instructed by Abhimanyu: *"change Lucknow to Joya, Amroha everywhere it appears."*

It turned out **not** to be stored data in most cases but a set of code defaults:
- `ai/prompts.py` — `SCHOOL_CITY` default, **and the assistant's own organisation
  briefing**, which told the model the school is in Lucknow. This one mattered most: the
  AI was answering from a false premise about where the school is.
- `routes/settings.py` — the `city` fallback returned when no school record is stored.
- `AdminTools.js` — a hard-coded "Affiliated to CBSE · Lucknow, Uttar Pradesh".
- `SchoolSettings.js` — city and address placeholders.
- `ProfileModal.js` — covered separately as D-11.

All corrected to **Joya, Amroha**. **No database write.** Because the settings endpoint
falls back to the code default when no `school_settings` record exists, this may correct
production on deploy with no data change at all. **If the sidebar still says Lucknow
after deploying**, a `school_settings` record does exist and holds the wrong city — a
one-line data correction needing separate approval. Flagged on the human checklist.
The school's address, phone and principal remain placeholder data (Epic 4 / Track 2).

### D-16 — `CI=true` fails the frontend build repo-wide — **DEFERRED, hygiene**
Roughly 30 pre-existing `react-hooks/exhaustive-deps` warnings across
`StudentTools.js`, `TeacherTools.js`, `QuerySection.js`, `ToolPage.js` and others mean
a warnings-as-errors build fails, both before and after Epic 1. So the build cannot
currently be used as a gate on new warnings. **Reason deferred:** unrelated to this
epic and touching a dozen files; it would bury a security diff. Worth a dedicated pass.

### D-17 — Pre-existing `scoped_filter(` hits carry no intent comment — **DEFERRED, hygiene**
Seven hits in `backend/routes/staff.py` predate this initiative and lack the
`# branch-scope: intentional — <reason>` annotation the standing audit expects. They
appear to be correct (school-scoped leave and staff lookups) but are unannotated, so
each future audit has to re-derive the reasoning. **Reason deferred:** unrelated churn
in a security diff; annotate during whichever epic next touches that file.

### D-18 — Story 1.3 shipped the wrong product decision — **RESOLVED SAME RUN**
The first version let staff edit their own name, phone and email directly. The owner
reversed it on sight: a person changing their own name or phone is itself a way to
misuse an account. The write path was **removed** (endpoint, client function and the
session-merge helper all deleted, not hidden), and the ask-and-approve flow he asked for
was built as Epic 8.

**Worth recording as a process point, not just a change:** the acceptance criteria were
argued through two review passes and 44 tests, and every one of them was satisfied. None
of that could catch "the feature should not exist". Reviews test whether the thing was
built right, not whether it should have been built — that question only had one place to
be answered, and it was the owner. For anything that changes what a *person* is allowed
to do, ask him before building, not at the demo.

### D-19 — Nobody can appoint a second owner from inside the app — **ACCEPTED 2026-07-22**
A consequence of Story 1.1, raised for a decision. Abhimanyu's answer: keep it exactly as
it is, with Aman Litt as sole owner. Recorded so a future session does not "helpfully"
reopen the path. Changing it requires a direct database change by us.

### D-15b — The city was ALSO stored in the database — **FIXED 2026-07-22 (approved write)**
D-15 corrected the city in ten places in the **code** and predicted this: *"If the
sidebar still says Lucknow after deploying, a `school_settings` record does exist and
holds the wrong city."* That prediction was right, and the record did exist.

**The reporting was the failure, not the work.** It was summarised as "changed
everywhere", which was true of the code and false of what the owner could see. He
raised it twice before it was acted on, and the second response was another
explanation rather than a fix. **Lesson: a UI defect is not fixed until the screen
changes. If a change only reaches the screen after a deploy or a data edit, say
"not yet visible to you" — never "done".**

**Fixed:** with Abhimanyu's explicit in-chat approval, exactly one field on one record
was changed: `school_settings.city` `'Lucknow'` → `'Joya, Amroha'`. Read-before,
write, read-after, with a diff proving `['city']` was the only field touched.
Script: `scratchpad/fix_city.py` (dry-run by default, refuses unless exactly one
record matches, refuses if already correct).

**Note — done outside the app, so NOT audited.** The proper path is the owner's own
School Settings screen, which writes through `updateSchoolSettings()` and is audited.
That path was offered first; the owner chose to have it done directly. Any future
correction of this kind should prefer the in-app route.

### D-21 — The rest of the school's own details are still placeholder data — **OPEN**
Still stored on the same record, and all wrong for a real school:

| Field | Stored now | The school's actual value (source-of-truth §1) |
|---|---|---|
| address | `Sector 12, Jankipuram, Lucknow, UP 226021` | Prem Nagar, Joya, Delhi–Moradabad Highway, Distt. Amroha 244222 |
| phone | `0522-4567890` | +91-8126965555 / 8126968888 |
| email | `info@theararyans.edu.in` (also misspelt) | theaaryansjoya@gmail.com |
| website | — | www.theaaryans.in |
| principal | `Adesh` | unconfirmed — needs the owner |

The address still contains "Lucknow", so the wrong city survives there. Only the
`city` field was approved, so nothing else was touched. **Needs one approval to
correct the lot**; the values above come from the school's own printed material.

### D-20 — The `ui-ux-pro-max` skill is installed without its data — **LOGGED**
Only `SKILL.md` is present; the search script and the CSV datasets it documents are
missing, so `--design-system` cannot be run. Its rule checklists were applied
directly instead, and the palette was measured off the live marketing site, which is
a better source anyway. No impact on this epic; worth reinstalling before a future
design pass leans on it.

### D-22 — The shell computed its own colours in JavaScript — **FIXED in Epic 9**
139 hard-coded `isDark ? '#hex' : '#hex'` pairs across `Layout`, `Sidebar`, `Header`,
`Login` and eleven modals. This is **why the retheme initially did not reach the app
shell**: switching theme recoloured the text (CSS variables) and left the surfaces
behind (JS literals), so dark mode rendered light text on a white page. All replaced
with tokens. `project-context.md` now forbids the pattern.

### D-23 — Every tool screen printed its title twice — **FIXED in Epic 9**
The header bar and the page both rendered the tool's name, one line apart, on every
single tab. Reported by the owner. The header now shows the title only when the page
does not — on the chat view, and on phones where the page heading scrolls away and
the sticky header is the only remaining indication of where you are.

---

## Track 2 (data load) — explicitly OUT OF SCOPE for these epics

Requires separate owner approval; involves writes to live data.
1. Student date of birth, gender, house, admission date — from the **FY2025-26**
   detainees workbook, joined on admission number only, ~1,551 of 1,802 matchable (88%).
   **The class column in that file must never be used** — it is last year's class and
   would demote every continuing student.
2. Transport routes and rates (~250 pick-up points).
3. Fee structure 2026-27.
4. Class-teacher assignments for all 48 sections.
5. Correcting the school's own details (address, phone, email, principal, affiliation) —
   currently placeholder data for a real school.
