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

| 2026-07-22 | **Epic 4** | **Numbers And Details That Are Actually True — DONE.** The reported defect ("the Board Report shows zeros") was not a Board Report defect: a second result envelope meant **eleven** screens read one level too shallow and printed 0 or N/A. Fixed at the source. A failed section can no longer render as a figure — on screen or in the exported board PDF. Attendance nobody has marked says "not marked yet", never "0%". The school's identity now has one verified source, plus its CBSE affiliation number, and the assistant is briefed from the record rather than a constant — it had **never** known the principal's name. Story 4.5 (owner-approved before build) closed three unguarded behaviours on the tool endpoint. Mid-run the owner reported two more: **34 tables gained column sorting** via the shared component, and Class Strength stopped showing "Other" and "Total" as the same number. 66 new tests. Suite 1784 passed / 2 failed (pinned) / 14 deselected; frontend 184 passed / 2 pre-existing. **Closes D-21 in code.** Adds D-24, D-25. **No production writes.** |

| 2026-07-22 | **Epic 10** | **Something You Can Actually Hand Someone - DONE.** Pulled ahead of Epic 5 by the owner. Flo was underselling the platform: every document library was already installed and the store-and-deliver path already proven by certificates. Shipped: one document builder (docx/xlsx/pptx/pdf/csv/md/txt); `draft_document` so Flo returns a real file with a signed, expiring link; a tappable file card in chat that refuses non-http URLs; `format=xlsx` on all seven exports with csv still default and every role gate untouched; OCR that reads a printed page on this server for nothing; and a paid vision fallback that is asserted NOT to run when OCR succeeded. Two parity gates caught two of my own mistakes. 70 new tests; suite 1915 passed / 2 pinned / 14 deselected, frontend 196 / 2 pre-existing. **OCR and the vision fallback SHIP DARK until a deploy.** Adds D-29, D-30, D-31. No production writes. |

| 2026-07-22 | **Epic 5** | **A Conversation That Feels Alive - DONE.** Two of the four owner items were found ALREADY FIXED by earlier work (the composer by Epic 9, stream resilience by epic R8) and were deliberately not rebuilt. The two real defects: the same tool was announced twice, by a badge AND by the thinking panel that already held its steps (owner item 12); and the three stacked stream elements sat at 42px, 0px and 42px with 4/8/24px gaps. Both fixed, with the gutter asserted as a VALUE rather than eyeballed. Added a stall watchdog: a stream accepted and then silent used to spin the typing dots forever, and nothing enforced NFR-P3. It now says 'still working' at 12s and 'the connection may have dropped' at 45s, reset by any inbound event including a keepalive, cleared on unmount. 9 new tests; frontend 205 passed / 2 pre-existing, backend unchanged at 1915 / 2 pinned. Adds D-32. No production writes. |

| 2026-07-23 | **Epic 6** | **Nothing Gets Lost — DONE.** Three product questions went to the Owner before any code (D-18); two were refusals, now written into the code as comments so the absences survive the next reader. The bell had been counting `n.is_read` — a field that has never existed in this product — so the red dot appeared whenever anyone had any notification at all and never cleared; it now reads the endpoint written for the question and shows the number. Notifications past the newest twenty, and chats past the newest fifty, were unreachable by ANY route in the product; both now have a page. Bulk chat delete is behind a typed count. Two traps were found before they shipped: an untyped request body would have turned "delete these three" into "delete everything you own", and the message-delete filter carries no user_id — safe one id at a time, catastrophic on a list. 78 new tests. Suite 1955 passed / 3 pre-existing / 14 deselected; frontend 244 / 2 pre-existing. Closes the `NotificationsPanel` half of D-22 and the last of D-05. Adds D-35, D-36, D-37. **No production writes.** |

| 2026-07-22/23 | **DEPLOYED** | **The whole sweep went live.** Backend first (EB `eduflow-uisweep-20260722-213022-d235c89`, Green in ~90s), then main merged and Amplify rebuilt. Verified by downloading the SERVED bundle and grepping for strings this release introduced, not by trusting a green build. Two problems were caught BEFORE the deploy: the OCR install was a `packages:` block that would have FAILED THE WHOLE DEPLOY if tesseract was absent from the instance repos, and production had no S3 bucket so every generated document would have 500'd. Both fixed first. A merge conflict with two commits that landed on main mid-flight was resolved by reading both sides — their `table { display: block }` was refused because it is D-01. **File storage configured 2026-07-23**: private bucket in ap-south-1, all public access blocked, encrypted, versioned; health now reads `s3: ok`. That also unblocks certificates, student photos and PDF receipts, broken in prod until now. |
---

## Epic 10 — closed 2026-07-22

All six stories are implemented and the epic-close gate is clean. See
`epic-10-completed.md`, `epic-10-review.md` and `epic-10-retrospective.md`.

**Two things are built but not yet working for the school, and must not be reported
otherwise:**

1. **OCR needs a deploy.** `tesseract` is a system binary and is not installed on the
   server. `.ebextensions/04_tesseract_ocr.config` installs it, along with the
   Hindi/Devanagari language data. Until that deploy, every image upload answers "the
   OCR engine is not installed on this server yet" - which is a distinct, tested
   answer precisely so it never reads as "this form is blank".
2. **The vision fallback may not work at all.** It uses the chat deployment the
   platform already talks through, which may not accept images. Nobody has tried. If
   it refuses, the code reports "this server cannot look at pictures yet" rather than
   inventing a description.

**Known limit, pinned by a test rather than left to be rediscovered:** the PDF builder
uses fpdf2's core fonts, which are Latin-1, so **Devanagari is replaced in PDFs**.
Word, Excel and PowerPoint keep Hindi intact. Fixing PDFs properly means shipping an
embedded Unicode font.

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

### D-21 update — **FIXED IN CODE in Epic 4; the stored values still need the Owner**
Epic 4 created one verified source for the school's identity
(`backend/school_identity.py`), taken from the school's own website on Abhimanyu's
instruction, and added the CBSE affiliation number (2133014) and school code (81936),
which had nowhere to live before. Any field the stored record does **not** carry now
falls back to the verified value with no database write.

**But `address`, `phone`, `email` and `principal` ARE present on the record and are
wrong.** A fallback deliberately does not override a stored value — that is what makes
a field the Owner clears stay cleared. So those four are **not yet visible as
corrected**: the change reaches his screen when he opens School Settings and saves
(audited as his action, which is the D-15b lesson), or approves the direct write.
Verified values are in `epic-4-completed.md` and on the human checklist.

### D-24 — Roughly 22 hand-rolled tables still have no column sorting — **DEFERRED**
Abhimanyu asked on 2026-07-22 for column sorting on *every* table. Enumerated rather
than estimated: **2** screens used the shared server-sorted table; **33** rendered
through the older `ToolPage` `DataTable`; **~22** are hand-rolled `<table>` elements.

Epic 4 added sorting to the shared `ToolPage` `DataTable`, so all 33 gained it at once
(plus Class Strength = 34). The remaining hand-rolled tables are in Attendance
Recorder, Exam Manager, Fee Collection, Timetable Builder, Transport Optimisation,
Principal Daily Ops, and parts of Teacher/Admin tools.

**Reason deferred:** each needs its own data plumbing rather than one shared edit, and
several are order-sensitive by nature (a timetable's rows are periods). **This is not
"sorting is done" — it is 34 of ~57.** Belongs with Epic 3's remit; sized as its own
pass. Recorded here so the coverage map is not read as complete again.

### D-25 — Two dispatch paths into one tool registry — **DEFERRED, architectural**
Raised by the architecture review during Epic 4. The chat tool-loop and
`POST /api/tools/{id}/execute` are two doors into one `TOOL_REGISTRY` that grew their
own gates, their own envelope handling, and their own idea of a turn. That is *how* a
double envelope survived the R4 hardening epic: nobody greps for the second caller,
because it is thought of as "the tools API" rather than as a caller.

Story 4.5 walked it back partway — both doors now import the same gate function
(`ai/tool_access.py`) instead of keeping two copies in sync by discipline.

**The end state** is a single `invoke_tool(name, params, user, scope) -> envelope` that
both paths call, so the gate, the scope resolution and the envelope shape are one code
path rather than two that agree today.

**Reason deferred:** it is an AI-layer refactor, not a UI defect. Doing it inside a run
about screens would put the assistant at risk for no owner-visible gain. Needs its own
run with the AI-reliability eval gate green.

### D-26 — Flo cannot read an attached image — **PLANNED, deferred behind the UI sweep**
Abhimanyu, 2026-07-22: Flo should "at least render and understand and extract data from
an image if attached or provided by any user", and explicitly **must NOT generate**
images or video. Sequencing decided by him: **finish Epics 5, 6 and 7 first.**

**Where the code to copy lives** (investigated 2026-07-22 across both repos):

| Ability | Prior art | Verdict |
|---|---|---|
| Understand an attached image | `Layaa-App/supabase/functions/shared/vision-analysis.ts` (hardened: SSRF guard, 8 MB cap, per-turn call cap, HMAC-signed result cache) and `CockRoach/api/chat.js:705-725` (simpler: inline `image_url` content part, base64 data URL, 20 MB cap) | **Portable.** Copy the CockRoach message shape, keep the Layaa-App guards. |
| Transcribe audio | `CockRoach/api/transcribe.js` — Azure Whisper, `POST /openai/deployments/{d}/audio/transcriptions`, `api-key` header, tier-gated, metered with reserve-then-refund | Portable, but needs a Whisper deployment — see the cost note below. |
| Analyze audio | **Does not exist in either repo.** Both transcribe, then reason over the text. | Build honestly as transcribe-then-read, or not at all. |
| Analyze video | **Neither watches video.** CockRoach transcribes the audio track; Layaa-App fetches YouTube captions. | Do not promise sight. |

**Naming, for whoever picks this up:** the agent with these skills is **Blazer**
(Layaa-App, `backend/src/blazer-identity.ts`). "CockRoach" inside Layaa-App is a
resilience mode (`cockroach-mode-registry.ts`), not an agent; the CockRoach *product*
is the separate `E:\Github\Layaa AI\CockRoach` repo, whose one persona is "Cockroach".

**On cost — correcting a misunderstanding recorded here deliberately.** The instruction
was "I do not want to link EduFlow with Azure ... free of cost". **EduFlow already runs
entirely on Azure OpenAI** — `AZURE_OPENAI_DEPLOYMENT` (default `gpt-5.3-chat`) in
`ai/llm_client.py` is how Flo talks at all today. There is no new linking to do, and
image understanding on a vision-capable chat deployment is **extra tokens on the
existing deployment** — no new service, no new subscription, no standing charge. It is
not literally free (an image costs roughly what a page of text costs) but it adds no new
bill line and draws on the existing sponsorship credits.

**Audio is the opposite** and must not be promised as free: transcribing an uploaded
file needs a speech model. The genuinely free route (`CockRoach/src/lib/voice-input.ts`)
is the browser's on-device speech API, which works for **someone speaking live** and not
for an uploaded recording — CockRoach chose it precisely because "per-audio-minute
billing is an unbounded cost lever". So "transcribe-then-read" for uploaded audio has no
free path; it needs a Whisper deployment at roughly half a US cent per minute.

**Before building, confirm:** whether the current `gpt-5.3-chat` deployment accepts
image input. If not, a vision-capable deployment on the same subscription is the
fallback — still no new service.

### D-28 — Founding year: 2005 vs 2015 — **SETTLED and WRITTEN 2026-07-22**
The stored record said `established: "2005"`; the school's website says it "commenced
its journey on 13 April 2015". The Epic 4 write deliberately left this alone rather than
overwrite one plausible year with another.

**Abhimanyu's answer resolves it, and the reason matters more than the number:** *"the
Joya branch of Aaryans was established in 2015 but the other branches might have been
established in 2005 but we are only focusing over the Joya branch as we are making the
platform for them only."* Both years are true — of different branches. **This platform
serves Joya, so the answer is 2015.**

Written to production with approval: one field, `established` `'2005'` → `'2015'`,
read-before/read-after diff proving nothing else moved, 1,802 students untouched.
`school_identity.py` now carries the reasoning so a future session does not "correct"
it back on finding a 2005 reference elsewhere.

**Confirmed read-only at the same time:** `branches` holds exactly ONE record —
`branch-joya` (`JYA`, Joya, Amroha, active) — and all 1,802 students are assigned to it.
So the "where is the Aliganj Branch?" question on the Epics 9+3 checklist is **closed**:
that stale record was deleted in Epic 9 and has not returned. Anything in this codebase
describing "the school" therefore describes Joya, which is why `school_identity.py` is
scoped to one branch by design rather than by omission.

### D-26 continued — access rule

**Access rule — SETTLED by Abhimanyu 2026-07-22:** **Owner, Principal and teachers** may
send Flo an image. **Students may not** — they are the children whose photographs this
protects, and they were excluded deliberately. Note this is *wider* than the Phase-1
lockdown (Owner+Principal only) that governs AI writes, so it needs its own gate rather
than reusing `is_owner_or_principal`; reads are not covered by that lockdown anyway.
Every use should still be audited, consistent with the F.2 minor-read audit rule.

**Scope confirmed:** Flo must be able to **read and extract data from an attached
image**. Flo must **NOT generate** images or video. (`routes/image_gen.py` already exists
and renders certificate templates — that is document rendering, not AI image generation,
and is unaffected.)

### D-27 — Three third-party skill packs evaluated — **1 adopted, 2 do not apply**
Abhimanyu asked (2026-07-22) whether any of three GitHub skills could give Flo image
analysis, and to add them to Flo regardless so it could use them when needed.

**The blocking fact, recorded so it is not asked again:** *no skill file can grant
vision.* Seeing an image is a model capability — the image bytes must actually be sent
to a model that can see. A markdown instruction file cannot make a model look at
something it was never given. None of the three helps with the image goal, and none
ever could. Image understanding stays the engineering job described in D-26.

| Repo | What it actually is | Verdict |
|---|---|---|
| `hardikpandya/stop-slop` (MIT) | Prose rules for removing AI writing tells | **ADOPTED** — see below |
| `rebelytics/one-skill-to-rule-them-all` (CC BY 4.0) | A meta-skill that watches *coding sessions* and improves a *skill library* | **Not applicable to Flo.** Flo has neither. It is built for a coding agent (Claude Code), where it would be useful — but that is tooling for the developer, not a capability for the school's assistant. |
| `vercel-labs/skills` (MIT) | `npx skills` — a CLI that installs skills into coding agents | **Not a skill at all.** A package manager for the developer's editor. Nothing to hand Flo. |

**stop-slop, adopted as `WRITING_STYLE_RULES` in `ai/prompts.py`** — adapted, not pasted.
Two reasons the adaptation matters:
1. The skill is written for essays and **bans emphasis and em-dashes**. This product
   deliberately bolds key figures and marks status with emoji so an owner can scan a
   reply on a phone. Those product decisions win; a committed test
   (`test_the_style_rules_do_not_cancel_the_product_rules`) fails if adopting the skill
   ever quietly deletes them.
2. It is a long document, and the system prompt is paid for on **every turn by every
   user**. Only the highest-value subset was taken: answer first, name the actor, be
   specific, no self-narration, no hedging, no slogans, bad news as plainly as good.

**On "provide them as skills for Flo to use automatically":** Flo has no skill system —
it has a tool registry, where each entry is a function that reads or writes school data.
A behavioural instruction is not a tool; it belongs in the prompt, which is where
stop-slop now lives. Building a genuine skill/mode system for Flo (as CockRoach has, in
`kb/modes/*.md`) would be a real piece of architecture and is **not** proposed here.

**Where the packs now live.** All three are installed in the *developer's* Claude Code
library at `C:\Users\Desktop\.claude\skills\` (`stop-slop`, `task-observer`,
`find-skills`), verbatim from upstream with their licences, so they are available in
every repository rather than just this one. `vercel-labs/skills` contains exactly one
skill — `find-skills` — so that pack is fully covered. Note the rebelytics repo's skill
is actually named **`task-observer`**; "one-skill-to-rule-them-all" is the repository,
not the skill.

**These are agent tooling, not part of the EduFlow product.** Nothing in
`C:\Users\Desktop\.claude\skills\` ships to the school, runs on the server, or is
reachable by Flo. The only thing this initiative put *into the product* is the adapted
`WRITING_STYLE_RULES` block in `ai/prompts.py`. A project-level copy of `find-skills`
was briefly added under `.claude/skills/` and then removed — it registered the same
skill twice, and the decision it documented is recorded here instead.

**Standing caution for whoever installs the next one.** `npx skills add` pulls
third-party instructions into a repository handling the records of 1,802 children. Read
the `SKILL.md` before adopting it, as was done for all three here — that review is what
established that two of them do not belong anywhere near Flo.

### D-29 — `export_expenses` is school-wide while its neighbours are branch-scoped — **DEFERRED**
Found by the Epic 10 audit. Every other export in `routes/exports.py` uses
`scoped_query(branch_id=...)`; expenses uses `scoped_filter` and so returns every
branch's expenses to a branch-bound accountant.

**Annotated in place rather than changed.** Narrowing it alters what an accountant can
see, which is a permission decision and not a packaging story's to make. No practical
effect today: the school has exactly one branch. Fix it in whichever epic next owns
accountant permissions, and ask before narrowing.

### D-30 — A scanned PDF still cannot be read — **DEFERRED**
`pypdf` correctly reports "no extractable text found (may be scanned)" for a PDF that
is a photograph of a page. Making OCR handle it means rasterising pages first
(`pdf2image` + the poppler system binary), a second system dependency on top of
Tesseract. Worth doing once Tesseract is proven in production, not before.

### D-31 — The vision fallback cannot be invoked on demand — **DEFERRED**
It runs at the upload boundary when OCR finds no text. Better would be a tool Flo calls
when it judges the picture needs understanding, because Flo has the conversation and
knows whether the person asked what a picture *says* or what it *shows*. The image
bytes live at the upload boundary rather than in the tool loop, so wiring that is real
work. The current behaviour satisfies the story honestly.

### D-32 — The stall thresholds are judgements, not measurements — **OPEN**
`STALL_SLOW_MS = 12000` and `STALL_DEAD_MS = 45000` in `ChatInterface.js` were chosen
by reasoning (the server keepalive is 5s, so 12s of total silence means the connection
itself is suspect) and have **never been watched against a real connection at the
school on a real morning**. They look precise in the code and are not.

**Reason open:** only use settles them. If Flo starts saying "taking longer than usual"
on answers that were always going to arrive, raise the first threshold; if people give
up before 12s, lower it. On the human checklist.

### D-33 — Post-deploy checks nobody has run yet — **OPEN**
Three things are live but unproven, and must not be reported as working until someone
looks:

1. **Writing a file as the server.** The health check only LISTS the bucket. `PutObject`
   is a different permission on the same policy and is untested. Ask Flo for a Word
   document: a download link means the whole path works.
2. **OCR.** The deploy attempts to install `tesseract` and carries on either way. Send
   Flo a photo of a printed page — it will either read it or say the engine is not
   installed. Nobody has checked which.
3. **Whether the chat model accepts images at all.** The vision fallback only runs when
   OCR finds no text, and the deployment may refuse images outright. It will say so
   plainly rather than inventing a description.

### D-34 — `claude-hosting` still holds the storage-setup permissions — **OPEN, small**
**Corrected 2026-07-23.** An earlier version of this entry said the user was left
holding the SERVER role policy. That was wrong: Abhimanyu *edited* the existing inline
policy `s3-file-storage-policy` rather than adding a second one, so it now contains the
**setup** permissions:

- `s3:CreateBucket`, `PutBucketPublicAccessBlock`, `PutEncryptionConfiguration`,
  `PutBucketVersioning`, `GetBucketLocation` — on the one bucket
- **`iam:PutRolePolicy` on `aws-elasticbeanstalk-ec2-role`**

The second one is the reason to act. It lets whoever holds those keys rewrite what the
production servers are permitted to do — and those keys sit in `backend/.env` inside a
git repository. The setup is finished, so the grant is now pure standing risk.

**Removing it breaks nothing.** The running application authenticates as the EC2
instance role, not as this user; `EduFlowFileStorage` on the role is what serves files.
The only cost is that redoing the setup (a second school, say) needs the permission
granted again for the duration.

**The assistant cannot remove it** — `iam:DeleteUserPolicy` is denied, correctly: a
principal should not be able to edit its own permissions. Console:
IAM → Users → `claude-hosting` → Permissions → tick `s3-file-storage-policy` → Remove.

### D-35 — The pinned test baseline drifts with the time of day — **EXPLAINED, not fixed**
The Epic 6 handoff pinned "1917 passed, 2 failed". A clean-tree run at ~02:00 local on
2026-07-23 measured **1916 passed, 3 failed**. The third failure is real and has a
cause:

`tests/backend/unit/test_receptionist_p11.py::test_visitor_duplicate_returns_409_with_duplicate_field`
seeds a visitor record using `datetime.now()` — **local time, IST** — while the service
computes "today" from `actor_ctx.now()`, which returns **UTC**
(`backend/services/actor_context.py:21`, deliberately, since R15.4). Between 00:00 and
05:30 IST the two dates differ by one day, the duplicate lookup searches the wrong day,
no duplicate is found, and the endpoint returns 200 instead of 409.

**So the test passes during the working day and fails in the small hours.** Verified
pre-existing by stashing all Epic 6 changes and re-running.

**Not fixed:** it is outside Epic 6's scope, and the standing rule is not to touch the
pinned failures mid-initiative. **The fix is one line in the test** — seed with the same
clock the service uses. Worth noting there is also a mild *product* oddity behind it: a
school in IST checking a visitor in between midnight and 05:30 would have "today"
computed as the previous day. Nobody checks visitors in at 00:30, so this is a test
defect first and a product curiosity second.

**Baseline for Epic 7: 1955 passed, 3 failed, 14 deselected** — and expect the third to
disappear if the suite is run after 05:30 IST.

### D-36 — A duplicate index on `notifications` — **DEFERRED, hygiene**
`db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])`
appears twice in `backend/database.py`, at line 367 and again at line 377, identically.
Mongo treats the second as a no-op, so the cost is confusion rather than storage. Found
while checking whether Epic 6 needed a new index (it did, for `conversations`, not for
`notifications`). **Reason deferred:** pre-existing and unrelated; removing it would put
an unrelated change inside an index diff.

### D-37 — Flo's generated documents fail to download in production — **OPEN, needs the Owner**
Reported by Abhimanyu on 2026-07-23. Asking Flo for a Word document produces a
downloadable link, and opening the link returns an AWS error page:
`SignatureDoesNotMatch — the request signature we calculated does not match the
signature you provided`.

**Two separate problems, and they need separating.**

**1. The signing itself.** The link was signed with a temporary AWS identity
(`ASIATB75HTBWMZQ5SLKF` — an `ASIA` prefix means short-lived credentials, not the
permanent `AKIA` kind). `SignatureDoesNotMatch` on such a link almost always means the
secret used to sign does not belong with the access key presented — i.e. the server is
holding a **mismatched or stale set of temporary credentials**. The most likely source
is concrete and checkable: `backend/.env` is deployed inside the application bundle and,
per D-34, has held credentials for the `claude-hosting` user. If that file (or the
Elastic Beanstalk environment) carries `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` /
`AWS_SESSION_TOKEN` from a temporary session, boto3 will prefer them over the EC2
instance role and sign with them — and a partial or stale set produces exactly this
error. `backend/services/s3_storage.py:43` builds its client with `region_name` only and
lets boto3's credential chain decide, so whatever the environment holds wins.

**The check is read-only and quick:** look at whether the EB environment or the deployed
`.env` sets any `AWS_*` credential variables at all. The intended state after the
2026-07-23 storage setup is that it sets **none** and the instance role
(`EduFlowFileStorage` on `aws-elasticbeanstalk-ec2-role`) is used. **Not done in this
run — it is a production change and needs the Owner's approval.**

**2. He was shown raw AWS XML, and that is its own defect.** Story 10.3's acceptance
criteria say an expired or dead link must tell the person it has expired and offer to
generate it again — *"a dead link that simply fails is the failure-that-looks-like-a-zero
defect of Epic 4 in a new place."* That AC is not being met: the link goes straight to
S3, so any S3 error is rendered by S3, in XML, with the school's bucket name and account
number on screen. **Whatever the cause of problem 1, problem 2 is real on its own** and
should be fixed regardless — the download should pass through the platform, or the card
should verify the link before handing it over.

**Note the timestamp in the error:** the link was signed at `20260722T212050Z` with a
one-hour expiry. If it was opened well after that, expiry is a *second*, independent
reason it would fail — and would produce a different AWS error, still rendered as XML.

**This supersedes the optimistic reading of D-33 item 1.** Writing the file as the server
evidently works (the object exists at the key in the error). **Reading it back does not.**
So "file storage is on" is true of `PutObject` and not yet true of the download path.

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
