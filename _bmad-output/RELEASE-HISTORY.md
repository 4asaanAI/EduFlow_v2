# EduFlow Release History

Full deploy record. Moved out of CLAUDE.md on 2026-09-03 to keep context lean.
For active rules and constraints see CLAUDE.md.

---

## ✅ SHIPPED - Class targeting on announcements (deployed 2026-08-15)

**LIVE.** Backend `eduflow-classnotice-20260815-96499c9`, frontend Amplify job 169,
commit `96499c9`. **Rollback target: `eduflow-approvals-20260815-69a2705`.** Bundle
diffed before upload: 247 entries to 249, the two added being this release's new backend
files, nothing removed. Environment Ready and Green on the new label.

**"By Class" saved the chosen classes and nothing ever read them back.** Delivery was by
role alone, so a notice meant for one class went to every student in the school while
the sender was told it worked. Fixed at every surface through one rule,
`backend/services/announcement_audience.py`. **Targeting is by class ID, never by a
printed label**: the two screens wrote `10th A` and `10th-A` for the same class, so any
label comparison has to pick a winner and mis-targets the other.

**Three more faults found in the same place.** The parent portal filtered on `audience`
and `class_id`, two fields an announcement has never carried, so it matched everything
and showed parents staff notices, other classes' notices and unapproved drafts. It
also pinned a branch announcements do not have. And search asked only "is it a draft".

**"Everyone" now includes the owner** (Abhimanyu, 2026-08-15): a school-wide announcement
never reached Aman, because the owner was in no audience list at all. The guard stopping a
principal singling the owner out is untouched and still 422s.

**The stand-in DB was lying about arrays.** `$in` against a list field did not match the
way Mongo does. Same class of fault as the 2026-08-12 `insert_one` one. Fixed in
`conftest.py`.

Gate: backend 4,016 / 0 failed; frontend 884 across 74; build clean including lint. The
fix was switched off and three tests failed, so the tests prove the fix rather than
passing either way. Record:
`implementation-artifacts/announcements/class-targeting-fixed-2026-08-15.md`.

⛔ **Two announcement questions are PARKED with Abhimanyu pending a discussion with Aman
and Adesh. Do not decide them in code:** whether circulars should reach parents and
students at all given the messaging system already exists, and whether
`announcement-broadcaster` and `circular-sender` become one screen. They remain two.

---

## ✅ SHIPPED - Approvals, the transport head, and searchable lists (deployed 2026-08-15)

**LIVE.** Backend `eduflow-approvals-20260815-69a2705`, frontend Amplify job 166, commit
`69a2705`. **Rollback target: `eduflow-photoleak-20260815-36b04c7`.** Proven live: the
new `/api/approvals/*` routes answer 401 while a made-up path under the same prefix
answers 404. Bundle diffed before upload: 242 entries to 247, the five added being this
release's new backend files, nothing removed.

**This one deploy carried everything that had been held back**: the approvals workflow,
R3-2 and R3-3 (Chaman's profile and the tenth profile for drivers and conductors), and
three leftovers closed on the day. They were held because the transport head would
otherwise have had buttons whose requests nobody could answer. That reason is gone.

**The three leftovers, all closed.** A person can now RAISE a request and not only
answer one, offered only where the server says they may. "Bring somebody in" lists
colleagues BY NAME and narrows as you type, instead of asking for an account id nobody
knows; it is scoped to the record, never a staff directory, because these routes are
signed-in-only by design. An attachment shows its name and opens, instead of being a
count you cannot read.

**The two staff leave decision paths are ONE.** `decide_leave` is deleted; everything
goes through `decide_leave_request`, which also marks the colleague away. Without that
row a colleague given leave still read as available everywhere else. Four things were
carried across from the deleted path so the merge lost nothing: the guard against
deciding twice, **branch scoping** (what stops one branch's principal deciding another
branch's leave), the older field names existing screens still read, and an audit action
name that tells an approval from a refusal. The operations screen keeps its stricter
"a reason either way" rule as its own rather than it being loosened by accident.

**Every drop-down fed by school data is now type-to-search.** One shared control,
`frontend/src/components/ui/SearchableSelect.js`, in 50 drop-downs across 16 files.
**A short list is left exactly as it was** and the LIST decides that, not the author, so
any screen can adopt it without checking first. The match count is always visible, and
the chosen option is never filtered out from under the person. The fixed short lists it
deliberately skips (gender, house, blood group, payment mode, sort order) are recorded
in `implementation-artifacts/picklists-survey-2026-08-15.md` so nobody redoes them
thinking they were missed.

Gate: backend 4,000 passed / 0 failed / 14 deselected; frontend 884 across 74 suites;
production build clean including lint.

**Still open:** R3-4, handing Chaman his credentials, is a deliberate act nobody has
taken. Cover for absence when Aman or Adesh is away is still a later item. Nothing here
is proven by signing in as a real profile.

### Approvals: one workflow for every approval - the architecture

**Record of what was done: `_bmad-output/implementation-artifacts/release-3-access/PROGRESS.md`,
the entry dated 2026-08-15 (later). Read it before touching any of this.**

All six approval systems are on one workflow and a seventh joins by adding one entry to
`backend/services/approval_registry.py`. **It is NOT a new store the six were migrated
into**: each kind is decided by the SAME service its own screen calls, and its
`may_decide` mirrors the gate its own route already carries, so the registry can only
ever hide a row from somebody entitled to it and can never hand anybody a decision they
do not hold. Do not relax that.

**Three corrections this work produced.** The plan said announcements are Adesh's alone;
the code has always allowed Aman OR Adesh and it stays that way (Abhimanyu, 2026-08-15).
The history a late joiner may read is a message NUMBER, not a timestamp, because two
timestamps can tie and when they did the whole history leaked. And deciding through Flo
was not showing the confirm card decision 30 requires; the name has to be in
`EXPLICIT_CONFIRMATION_TOOL_NAMES`, never a literal in the registry entry.

**The bell and the notifications window now carry the SAME two sub-tabs**, "Waiting on
you" and "Already happened", from `KIND_TABS` in `notifKinds.js`.

Gate: backend 3,941 passed / 0 failed / 14 deselected; frontend 868 across 73 suites;
production build clean including lint.

### The plan behind it (decisions 21 to 31, all settled)

**Read `_bmad-output/planning-artifacts/approvals-one-workflow-2026-08-15.md` first.**
Eleven decisions (21 to 31) from Abhimanyu, all settled, all dated 2026-08-15.

**Three things that will catch you out:**

1. **Flo is NEVER in the shared approval thread.** Each person gets Flo privately, on
   their own screen, in their own profile, and nothing Flo says enters the transcript.
   Aman's Flo sees far more than Chaman's, so a shared Flo would print an answer built on
   Aman's access in front of somebody who does not hold it.
2. **Every kind keeps the approvers it has today.** Announcements are Adesh's alone;
   student leave is teacher-then-principal. A screen must never widen access.
3. **Adesh sees Aman's approval decisions.** That does NOT reverse the Release 4 rule that
   Adesh cannot see Aman's changes in the ACTION LOG. Different surface. Keep them apart.

### R3-2 and R3-3 — transport head and driver/conductor profiles

**The reversal you need to know:** the plan said the transport head sees no money at all.
Abhimanyu changed that on 2026-08-15. **He holds full financial visibility of school
TRANSPORT**, fares and who owes what included. Everything else — tuition, concessions,
salaries — stays refused, enforced by giving him ONE purpose-built money tool rather than
the finance domain.

Gate at the time of writing: backend 3,851 passed / 0 failed; frontend 855 passed across
72 suites; production build clean including lint.

---

## ✅ SHIPPED - Enterprise Commercial Operations (2026-08-05)

Commit `3d989e1` is merged to `origin/main`. EduFlow now has lightweight legal-entity
ownership/reporting, admissions CRM activities and opportunities, campus POS/retail with
shifts, split payments and returns, entity-aware accounting-period controls, confirmed Flo
write tools backed by the same domain services as REST, a permanent built-in `/stop-slop`
communication habit, hardened prompt/KB context, and nine responsive owner/principal
management hubs. Branding, theme, legacy records, the single active Joya branch, and current
deep links were preserved. Hostel and full ERPNext/Frappe framework complexity remain out of
scope. Source of truth: `_bmad-output/implementation-artifacts/spec-enterprise-commercial-operations.md`.
Release gate: backend 2,163 passed / 0 failed / 15 credentialed deselected; frontend 439
passed; responsive Chromium 3 passed; production build passed.

---

## ✅ SHIPPED - AI Layer Reliability (Zero Silent Failures) - completed 2026-07-10

All 11 epics (R1–R11) shipped, plus the companion non-AI reliability set (R12–R15). See
`_bmad-output/platform-quality-sweep.md` rows 18–19 and
`_bmad-output/implementation-artifacts/ai-reliability/epic-R*-completed.md`. The execution
protocol (`EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md`) and its 7 standing rules still govern
any follow-on AI-layer work.

---

## ✅ SHIPPED - UI Sweep (owner-reported defects, 2026-07-22)

Plan: `_bmad-output/planning-artifacts/epics-ui-sweep-2026-07-22.md`; live logs in
`_bmad-output/implementation-artifacts/ui-sweep/`. Epics 1–6, 8, 9, 10 are shipped and
Epic 7 (School Directory) built and gate-green. **D-44 is CLOSED.** One merge was made
(Fee Receipts into Fee Collection) and six tools were examined and deliberately left
separate, each with its reason pinned in `ToolMerge.test.js`.

---

## ✅ SHIPPED - Inspection Remediation (2026-08-04)

14 findings worked in 3 blocks of 5/5/4. Process and fixed handoff prompt:
`_bmad-output/INSPECTION-REMEDIATION-PROTOCOL-2026-08-04.md`. Register:
`_bmad-output/planning-artifacts/inspection-findings-2026-08-04.md`. Logs in
`_bmad-output/implementation-artifacts/inspection-2026-08-04/`.

---

## ✅ SHIPPED - Two photo leaks closed, and staff logins narrowed (deployed 2026-08-15)

**LIVE.** Backend `eduflow-photoleak-20260815-36b04c7`, frontend Amplify job 164, commit
`36b04c7`. **Rollback target: `eduflow-tests-20260815-f7a1be2`.** Proven live: the parent
portal, staff and student routes all answer 401 while a made-up path under the same
prefix answers 404. Bundle checked before upload, 242 entries either way, nothing added
or dropped.

**The parent portal was handing parents' browsers the previous vendor's public web
address for their own child and both parents.** `GET /api/guardian/wards` and the ward
detail returned the child's whole record without going through `photo_url_service`, and
the guardian `PATCH` response did the same. Both now go through it, pinned by
`test_no_vendor_photo_link_escapes_2026_08_15.py`, which also fails if a NEW route module
returns a person without so much as importing the service.

**The photo move off Vedmarg is finished and, for the first time, PROVEN.** All 1,692
images are in the school's own bucket (202.8 MB), nothing stranded across students,
parents, guardians and staff, and a 21-image sample was signed and read back as real
JPEGs. **Two traps that manufacture a false alarm** are recorded in
`implementation-artifacts/vedmarg-photos-verified-2026-08-15.md`: `S3_BUCKET` is unset
locally, and a link signed for GET returns 403 to a HEAD request, which is
indistinguishable from the file being gone. The originals are still on Vedmarg's servers
and still public; nothing in this code can change that.

**Creating a staff record MINTS A LOGIN, and that is now owner and principal only.** The
old gate fired only for a privileged account, so every office desk could create a plain
teacher and hand out a way in. Refused server-side and hidden in the UI.

**The Add Staff form used to throw the password away.** The username now travels with it
(derived from email, phone, employee ID or name, so it cannot be guessed) and both are
shown once. **The password is NOT forced to change** (Abhimanyu, 2026-08-15); every
profile can change its own from Settings.

Gate: backend 3,784 passed / 0 failed; frontend 813 passed; production build clean.

---

## ✅ SHIPPED - B1: an entrance test is a record, not a word (deployed 2026-08-15)

**LIVE.** Backend `eduflow-tests-20260815-f7a1be2`, frontend Amplify job 161, commit
`f7a1be2`. **Rollback target: `eduflow-admissions-20260814-52dc341`.** Proven live: the
new `/api/admissions/tests` routes answer 401 while a made-up path under the same prefix
answers 404.

`assessment_scheduled` used to be a status and nothing else, so the school could not
pull a list for Sunday. There is now a Tests tab: a test with a date, a time, a place
and a total, the list of who is sitting it, who turned up, and the marks.

**Two rules, and neither may be relaxed.** "Nobody has marked this yet" is its own state
and is never drawn as absent, because a register nobody filled in and a test nobody came
to are opposite facts. And a mark reaches the application through
`admissions_service.record_assessment` **in the same call**; if that refuses, nothing is
stored, including the attendance, so the list and the application can never disagree.

**The paper's total lives on the TEST and freezes at the first mark.** Before this the
maximum was typed per child, so two children sitting one paper could be recorded out of
different totals with their percentages silently disagreeing.

**The Tests tab was asserted ABSENT by a test until B1 built it.** That assertion was
flipped, not deleted. Keep it that way: it now fails if the tab exists without its panel.

Not built: no Flo tools for tests yet.

---

## ✅ SHIPPED - Admissions stage one: the two halves of the funnel are joined (deployed 2026-08-14)

**LIVE.** A1 to A6 went out together on 2026-08-14 as `52dc341`. Backend
`eduflow-admissions-20260814-52dc341`, frontend Amplify job 158. **Rollback target:
`eduflow-noshop-20260814-484135d`.** Proven live: the new
`/api/commercial/crm/follow-ups` answers 401 while a route that does not exist answers
404 from the same server.

**Start here:** `_bmad-output/implementation-artifacts/admissions-funnel/PROGRESS.md`
is the ONLY record of what is done. The plan is
`_bmad-output/planning-artifacts/admissions-funnel-end-to-end-2026-08-14.md`.

**The one idea.** The platform had two carefully built halves of the admissions journey
and nothing joining them, so the funnel could report a child as enrolled when no child
existed. The test for every item: can a person tell "this child joined the school" from
"somebody moved a row to the last column"?

---

## ✅ SHIPPED - Release 4: the platform can account for itself (deployed 2026-08-13)

**LIVE.** All six parts went out together on 2026-08-13. Backend
`eduflow-release4-20260813-fec72a7`, frontend Amplify job 147, merged as `6daf32f`.
Gate: 3,608 backend and 777 frontend tests passing, build and lint clean. Rollback
target: `eduflow-msgfix-20260812-6520aed`.

**The new routes live under `/api/audit-log`, not `/api/audit`.** Probing the shorter
path returns a 404 and reads exactly like a failed deploy; it caused a false alarm on
14 August. Verified live: `/api/audit-log/{retention/plan,my-changes-today,school-summary}`,
`/api/issues/platform` and `/api/operator/platform-health` all answer 401.

**The ticket route now works end to end.** Email goes through ZOHO MAIL. The school
raises a ticket, it is stored in LayaaStat under The Aaryans, and n8n emails Abhimanyu
and Shubham from `support@layaa.ai`. Detail in
`implementation-artifacts/release-4/ticket-email-via-zoho-2026-08-14.md`.

**All four Release 4 leftovers are closed.** Rotating `CRON_SECRET` is DROPPED by
Abhimanyu's decision of 2026-08-14; do not raise it again.

**LayaaStat runs on AWS Amplify, app `ddsqdblq9ge74`, NOT Vercel.** The repository carries
a leftover `vercel.json` that reads as authoritative and is not. The Vercel account holds
one unrelated project.

**Start here:** `_bmad-output/implementation-artifacts/release-4/PROGRESS.md` is the ONLY
record of what is done. The work itself is
`_bmad-output/planning-artifacts/release-4-audit-undo-and-honest-menus-2026-08-12.md`.

**Two decisions that catch people out:** Adesh must NOT see Aman's changes in the audit
trail. And undo covers only what hurts the platform while Flo talks people through the
rest by hand.

**Grouping never grants, and nothing is ever dropped.** Both rules carry over from the
post-Release-3 work and neither may be relaxed for a layout change.

---

## ✅ SHIPPED - Release 3: the whole list, on any device (2026-08-12)

**LIVE.** All thirteen items shipped together on 2026-08-12.
Backend `eduflow-release3-20260812-810fe43`, frontend Amplify job 143.

**Start here:** `_bmad-output/implementation-artifacts/release-3/PROGRESS.md` is the ONLY
record of what is done. Read it first, update it last, every run.

**The one idea behind the whole release.** Every serious fault found was the same shape:
a query that quietly returned less than it should. So wherever this release added a
filter, an "all" view, a download or a scroll, the count is visible and a partial answer
is impossible to mistake for a complete one.

**A truncated file is worse than a truncated screen**, because it leaves the building and
gets filed as a record. That is why every export is now COMPLETE OR REFUSED, never short.

Settled decisions, do not reopen: "All" on every table; exports need no confirm window;
exports MUST respect the Release 2 permission table; the whole-school workbook is Aman and
Adesh only; **a spreadsheet is NEVER trimmed** (Word and PDF still trim and still say so);
audit and undo work is Release 4 and separate.

### What Release 3 changed that you will trip over

| Thing | Where | Why it matters |
|---|---|---|
| One page-size ceiling, 500 | `backend/pagination.py`, 16 clamp sites | A page size below 1 is **refused with a 400**, never turned into 1. `max(1, -1)` used to make "All" show ONE ROW. |
| Every export complete or refused | `routes/exports.py` `_read_all`, ceiling 100,000 | Nothing is ever silently dropped. Past the ceiling the request fails and says no file was made. |
| Nine export builders, one dictionary | `EXPORT_BUILDERS` | The screen download, Flo, and the whole-school workbook all read through these. **Add a data set here, never beside a route.** |
| Export permission | `require_export` / `may_export`, derived from `profile_matrix` | One rule asked two ways. Never write a second list of role names. |
| Download on every table | `lib/exportTable.js`, `ui/ExportButton.js`, `POST /api/export/table` | The control refuses to save a file holding fewer rows than the table says it has. |
| Filters on every tool table | `ToolPage.DataTable` | Written once for ~70 tables. **The download follows the filter.** |
| Rows drawn as you scroll | `ui/DataTable` | "All" fetches everything; painting is spread out. The count says drawn AND loaded. |
| Touch floor: 40px, 16px fields | `index.css` §7 (≤768px) and §7c (`pointer: coarse` + ≥769px) | §7c is NEW. A tablet is 810px wide, so it used to fall off the end of every touch rule and inherit desktop sizes. |
| Real device tests | `playwright.config.js` projects `phone-pixel`, `tablet-ipad` | The old "responsive" project was Desktop Chrome made narrow: no touch, no pixel ratio. That is why the owner's iPhone report was missed. |

---

## ✅ SHIPPED - After Release 3: four owner reports from the live platform (2026-08-12)

Found by Abhimanyu once Release 3 was live, fixed and deployed the same day. These are
NOT Release 3 scope. Backend `eduflow-msgfix-20260812-6520aed`; frontend Amplify job 145.

**1. Every staff message send was returning a 500, and the message was saved anyway.**
`insert_one` writes Mongo's `_id` into the caller's dict IN PLACE, and `send_message`
echoed that same dict back. An ObjectId is not JSON, so FastAPI raised AFTER the write
committed: the sender was told the opposite of what happened and sent again. **The
stand-in DB is what hid it** — `FakeCollection.insert_one` appended without stamping
`_id`, so the dict was clean in tests and dirty in production. It now stamps an ObjectId
in place, exactly like Mongo, which closes the class rather than the instance. With the
route fix reverted, three tests fail; before the conftest change, zero did.
**Never return the dict you just inserted.** Read it back with `{"_id": 0}` or strip the key.

**2. There was no inactivity sign-out anywhere, for any profile.** The Settings
"Session timeout" dropdown offering 30 min / 1 hour / 2 hours **saved nothing and nothing
read it**. Now `frontend/src/lib/idleLogout.js`: **one hour, every profile, the owner
included** (Abhimanyu, 2026-08-12). It stores a **deadline, not a countdown** — a sleeping
laptop stops timers, so a countdown would wake with time still on it and leave school
records open on an unattended machine. One shared deadline in localStorage across tabs.

**3. Same tab names on every profile.** `groupToolsIntoHubs` in `lib/managementHubs.js`
+ `getGroupConfig` in `Sidebar.js`. Two rules, neither may be relaxed: grouping NEVER
grants, and **nothing is dropped** — orphans are still listed.

**4. The duplicate group icon in Messages is gone.**

**Still open from this release:**
- Aman showed "online" in messaging with nobody signed in. UNEXPLAINED — do not guess.
  The light is driven by `sse_is_connected`, not a stale timestamp. Two candidates: a
  genuinely open session, or a stream whose `finally` never ran. If still lit: it's the
  second one. Ask before fixing.
- The idle sign-out has no "you are about to be signed out" warning. Flagged to
  Abhimanyu; build it if it becomes a nuisance.

---

## ✅ SHIPPED - Release 2: person profiles for Sonu and Lalit (2026-08-10)

Merged and live as `eduflow-release2-20260812-accfc64`. **Permissions are now granted by
a written-down table, not by subtraction** — `backend/services/profile_matrix.py` is the
source of truth and `frontend/src/lib/toolPermissions.js` is a GENERATED mirror of it.
Never hand-edit the mirror. The pinned per-profile reach counts in
`tests/backend/unit/test_all_nine_profiles_sweep_r2_13.py` are the alarm: a count moving
without a written reason means somebody's access changed and nobody decided to.

**Reference, in this order:**
1. `_bmad-output/implementation-artifacts/release-2/PROGRESS.md` ← the ONLY record of what is done.
2. `_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md`

Eight decisions from Abhimanyu are recorded in the plan and are settled; do not re-open
them.

---

## ✅ SHIPPED - Parent messaging + deferred tool loading (2026-08-08)

**Flo can now send WhatsApp/SMS to families for real**, always behind a confirm card.
One shared path: `services/messaging_service.py`, reached by `/api/parent-messaging/*`
(panels) and `send_parent_message` (Flo), pinned by
`tests/backend/parity/messaging_parity_test.py`. Templates live in `message_templates`
and Flo can create/edit/delete them.

**SMS wording is free; WhatsApp wording is not.** Meta requires pre-approved templates,
so `update_message_template` on a WhatsApp template changes only the local PREVIEW. Real
new wording goes through `submit_whatsapp_template` (Twilio Content API → Meta approval,
minutes to a day, can be refused). Do not let any doc or prompt imply otherwise.

**WhatsApp cannot send in production.** See current constraints in CLAUDE.md.

**Deferred tool loading** (`ai/tool_search.py`) cut an owner/principal turn from ~36,400
to ~9,700 tokens (73%). A small CORE set is described in full; everything else is listed
BY NAME and its schema fetched via `search_tools` on demand. **Nothing is ever hidden** —
`test_tool_search.py` proves every authorized tool stays reachable for all 10 role
profiles. Kill switch: `EDUFLOW_TOOL_SEARCH=0`.

Adding a tool? Put it in CORE only if it is genuinely everyday.

---

## ✅ SHIPPED - Spreadsheet import is segment-scoped across four profiles (2026-08-08)

Live as `eduflow-main-20260808-9f5e224`. Import is no longer owner/principal-only:

| Profile | May import |
|---|---|
| owner, principal (`leadership`) | the whole student record |
| accountant (`finance`) | bank fields + contact numbers (fee reminders go to those) |
| management (`non_finance`) | everything except the bank fields |

**One place decides:** `data_import_service.IMPORT_FIELD_SCOPES`, keyed by
`ai_action_policy.privileged_profile()`. Do not add a second copy of that mapping anywhere.

**Out-of-segment columns are REPORTED, never silently dropped.**

**The sidebar "Data Import" panel has TWO tabs, and they are not the same feature.**
"Update existing records" is the scoped import, open to all four profiles.
"Add new students" is the OLD `/api/import/{validate,commit}` route (`routes/import_data.py`),
which **creates** students and is **owner/principal only**.

Import can never set fees, class, or enrolment status (`PROTECTED_FIELDS`), matches on
admission number and never on name, and fills blanks only unless `overwrite=true`.

---

## ✅ Access ladder — office logins removed (2026-08-15)

There is a **seven step access ladder**: 1 Aman and Adesh, 2 + Sonu and Lalit,
**3 + department heads**, **4 + whole admin staff**, 5 + teachers, 6 + students,
7 + parents. **The access ladder stopped after step 2.**

The seven office logins created by migration 041 on 2026-08-12 have been REMOVED. They
were still on their one-time password with zero sessions ever. The seven staff records
are untouched. Each of those people gets a proper profile in their own release.

The four shared desk logins (`transport`, `reception`, `ittech`, `maintenance`) are also
REMOVED. Zero sessions ever. **Every login on the platform now belongs to one named
person.** Do not create a department account. Record:
`implementation-artifacts/release-3-access/shared-desk-logins-removed-2026-08-15.md`.
The four `sub_category` values stay in the code; this deleted accounts, not profiles.

⛔ **Never close this with `041_office_staff_logins.py --rollback`.** That file also clears
the staff link for Adesh Singh and Lalit Thomas, who both sign in for real.

**`profile_matrix.py` does NOT gate the REST API.** It decides menus, Flo tools and
exports, and nothing else. Every route carries a hand-written gate.

**The messaging question is ANSWERED (2026-08-14, decision 17): messaging stops at
teachers, students never get it.** There is no way to create a staff or teacher login
through the platform. Only students have a login-creation route; every staff login so far
came from a hand-run migration.

**R3-0 is RETIRED by Abhimanyu's decision of 2026-08-14 and will NOT be built.**
The twenty questions R3-0 raised are in
`implementation-artifacts/release-3-access/R3-0-retired-and-the-twenty-questions-2026-08-14.md`.

**Read `_bmad-output/planning-artifacts/release-numbering-collision-2026-08-14.md` before
using a release number in any sentence.**
