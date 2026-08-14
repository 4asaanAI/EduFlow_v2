# Admissions funnel: progress

The only record of what is done. Read it first, update it last, every run.
Plan: `_bmad-output/planning-artifacts/admissions-funnel-end-to-end-2026-08-14.md`.

## Where things stand

| Item | State |
|---|---|
| A1 Start an application from an enquiry | SHIPPED 2026-08-14 |
| A2 The enrolled stage comes off the list | SHIPPED 2026-08-14 |
| A3 The stages, said once, **plus mother and father, date of birth, gender and previous school on the enquiry** (Abhimanyu, 2026-08-14) | SHIPPED 2026-08-14 |
| A4 One admissions screen | SHIPPED 2026-08-14 |
| A5 Who to call today | SHIPPED 2026-08-14 |
| A6 Flo can work the second half | SHIPPED 2026-08-14 |
| B1 to B4 (stage two) | not to be started yet |

## Deployed 2026-08-14, on Abhimanyu's instruction

All six went out together as commit `52dc341`.

- **Backend:** `eduflow-admissions-20260814-52dc341`, environment Ready and Green.
- **Frontend:** Amplify job 158, SUCCEED, on the same commit.
- **Rollback target: `eduflow-noshop-20260814-484135d`.**
- **Proven live, not assumed.** The new follow-up route answers 401 while a route that
  does not exist answers 404 from the same server, which is the difference between "the
  new code is there and still guarded" and "the deploy did not land".

No live school database was read or modified. No migration was run.

## The machine's baseline, read before starting

The backend suite on this laptop is **3,733 passed, 1 failed, 14 deselected** as of A6.
(It was 3,675 when A1 began and 3,709 when A5 began; the number grows every item, so read
the FAILURE count and not this one.) The one
failure is `tests/backend/unit/test_document_builder.py::test_the_shipped_configuration_has_both_the_font_and_the_shaper`,
which fails because the `uharfbuzz` package is not installed on this machine. It has
nothing to do with admissions and was failing before any of this work began. **The bar
for this initiative is that failure and no other.** If a second one appears, it is ours.

## A1: start an application from an enquiry (done 2026-08-14)

**What a person can now do.** On the Enquiry Register, every enquiry row has a
"Start application" button. Pressing it creates the application with the child's name,
the parent's name and the phone number already filled in. On the application form there
is also a picker, "Start from an enquiry", which does the same thing the other way round.

**Where the honesty is.** The server already refused a second application for the same
family and handed back the first one. Nothing on screen said so, which would have read
as a fresh application every time. Both entrances now say which of the two happened:
either "Application started" or "already had an application, so nothing new was created".
Once an enquiry has an application, the button is replaced by the words "Application
started", and that family drops out of the picker, so the same record cannot be started
twice by accident.

**The class is not guessed.** An enquiry carries free text such as "Class 3", which is
not a class on the roll. The picker deliberately leaves the class box empty for the
office to choose. The row button passes the enquiry's own wording through to the server,
and refuses with a plain message if the enquiry has no class on it at all.

**Nothing was widened.** No new route, no changed permission. Both entrances use the
`POST /api/admissions/applications` route that already existed with its existing gate.

**Files.** `frontend/src/components/tools/AdmissionsWorkflow.js` (picker, honest notice,
`reloadKey` so the embedded list refreshes when a row starts one),
`frontend/src/components/tools/AdminTools.js` (`EnquiryRegister`: the row button, the
message line), `tests/backend/api/test_admissions_and_student_leave.py` (two new tests).

**Gate.** Backend 3,677 passed / 1 failed (the machine's `uharfbuzz` one, unchanged from
the baseline). Frontend 793 passed across 66 suites. Lint and production build clean.

## A2: the enrolled stage comes off the list (done 2026-08-14)

**The fault.** Moving an enquiry from "fee paid" to "enrolled" was an ordinary stage
move with no check that any child had been created, and the owner could jump an enquiry
to enrolled from any stage at all. So the funnel could report an enrolment that had never
happened, and a person looking at the screen could not tell that apart from a real one.

**The rule now.** Nobody chooses enrolled, on any path, including the owner. An enquiry
becomes enrolled only when its admission application creates the child, which
`enroll_application` does in one transaction and writes to the enquiry itself. Everything
else about moving stages is unchanged.

**Four ways in, one refusal, said the same way.** The enquiry screen, the REST route, the
CRM lead route, and Flo. The wording is one constant, `ENROLLED_IS_NOT_A_CHOICE` in
`services/enquiry_service.py`, and it says what to do instead rather than only saying no.
The check sits **above** the owner branch on purpose.

**Three things fixed alongside, because they were the same fault wearing a different hat:**

- The CRM lead route used to accept "enrolled" as long as an application id and a student
  id were typed in beside it. That checked that two identifiers were present, not that a
  child existed. Gone.
- The "Application ID" and "Student ID" boxes on the CRM opportunity panel were never
  sent with the opportunity. Their only use was that hand-made enrolment. They were two
  boxes a person could type into that did nothing at all, so they are gone too.
- A refused stage change on the Enquiry Register used to do **nothing at all** on screen,
  which looks exactly like a change that worked. It now shows what the server said.

**On screen.** The stage buttons no longer offer Enrolled, and a line under them explains
how a family actually becomes enrolled. The funnel across the top still counts all eight
stages, enrolled included, because hiding the stage a family is in would be a different
lie from the one being fixed. A CRM lead already enrolled still shows that in its
dropdown, greyed out.

**Files.** `backend/services/enquiry_service.py` (the constant, the refusal, `enrolled`
removed as a target from `fee_paid`, `applied` and `admitted`),
`backend/services/commercial_service.py`, `backend/ai/prompts.py` (Flo's stage list and
description), `frontend/src/components/tools/AdminTools.js`,
`frontend/src/components/tools/CommercialOperations.js`, plus
`tests/backend/api/test_enrolled_is_never_chosen_by_hand.py` (new) and one updated
assertion in `tests/backend/parity/ops_crud_parity_test.py`.

**That parity assertion changed on purpose.** It pinned the old message, "Invalid enquiry
transition". The move is still refused; only the reason changed, from "you cannot get
there from `new`" to "nobody gets there by hand".

**Gate.** Backend 3,688 passed / 1 failed (the machine's `uharfbuzz` one, unchanged from
the baseline). Frontend 793 passed across 66 suites. Lint and production build clean.

## A3: the journey said once, and the family the school records (done 2026-08-14)

Two halves, both aimed at the same fault: a reader could not tell one answer from two.

### Half one: one vocabulary

`backend/services/admissions_journey.py` is the source of truth. Nine steps, from
"Enquired" to "On the roll", with "Closed" as an ending rather than a rung. It says which
enquiry stage and which application stage mean which step, and `describe_position` gives
**one** answer for a family plus the record that decided it.

- **The further-along record wins**, and a closed record never outranks a live one. A
  withdrawn application cannot drag a live enquiry to closed, and a lost enquiry cannot
  hide an application still moving.
- `frontend/src/lib/admissionsJourney.generated.js` is a **generated mirror**, same
  pattern as the profile matrix. Regenerate with
  `scripts/generate_admissions_journey.py`. **Never hand-edit it**;
  `tests/backend/unit/test_admissions_journey_drift.py` fails if it goes stale, and a
  third test fails if any stage on either side has no step.
- **This module permits nothing.** It is vocabulary. What moves are allowed is still
  `ALLOWED_TRANSITIONS` and `TRANSITIONS`, both untouched.
- Both lists now answer in it. The enquiry list looks its applications up in **one
  batched query**, never one per row. The screen shows a Position column with a small
  line saying whether it came from the enquiry or the application.

### Half two: the family the school actually records

`mother_name`, `father_name`, `dob`, `gender` and `previous_school` on the enquiry, and
carried onto the application when one is started. **`parent_name` stays**: it is the
contact the office deals with, it is what messaging and every export read, and 102
existing records carry it. Empty fields are stored as empty rather than left off, so a
record nobody asked does not look like a record written before the field existed.
Anything typed on the application beats what the enquiry held.

Still deliberately excluded: Aadhaar, religion, category and income.

### Two things fixed alongside

- **`GET /api/ops/enquiries` stopped at 50 rows with no total beside it.** A school with
  200 enquiries looked like a school with 50, and the funnel counts drawn from that list
  were wrong with nothing saying so. It now uses the one page-size rule, returns the
  total, refuses a nonsense page size with a 400, and the screen says "showing N of M".
- **The stand-in database ignored row limits.** `FakeCursor.to_list` threw its argument
  away and returned every document, while real Motor honours it. Every route that caps
  its answer with `.to_list(N)` was therefore untested, and a page-size fault would have
  passed the suite and truncated in production. It now behaves like Motor. **Nothing
  broke when it was tightened**, which is the good outcome: no route was leaning on it.

**Gate.** Backend 3,709 passed / 1 failed (the machine's `uharfbuzz` one, unchanged from
the baseline). Frontend 793 passed across 66 suites. Lint and production build clean.

## A4: one admissions screen (done 2026-08-14)

**The fault.** Three screens described one funnel. "Admission Funnel" showed the owner a
read-only count. "Enquiry Register" ran the pipeline with the applications bolted onto
the bottom. "Legal Entities & Admissions" held the same enquiries again as CRM leads with
values against them. Somebody looking for one family had three places to look and no way
of knowing which was the real one.

**Now one screen, `admissions`, with tabs:** Enquiries, Applications, and Pipeline value.
The owner's old read-only counts are the header of the Enquiries tab, which is the same
figures with the ability to act on them. Legal Entities keeps the entity records and the
money overview, including the lead count, and is no longer an admissions screen.

**Grouping never grants, and here is the proof.**

- Who reaches the screen is still `profile_matrix.py`. The two old entries were replaced
  by one, so anybody who held either holds this and anybody who held neither still holds
  neither.
- The Pipeline tab keeps **the same gate it has always had**, inside the panel. The
  management head is not on that list and was never on it, so he does not gain the
  pipeline by the tabs existing. There is a test that asserts exactly this.
- **The Flo tool reach counts in `test_all_nine_profiles_sweep_r2_13.py` did not move**,
  which is the check the plan asked for. Nobody's tools changed.

**One pinned number DID move, and it is a different number.** The screen count in
`ProfileMenuSweep.test.js` for the management head went from 47 to 46. That is the merge
itself: he held both old entries and now holds one merged screen. **The receptionist
swapped one entry for one and did not move**, which is the proof the merge hit what it
aimed at, because only a profile holding BOTH could change. Do not confuse this screen
count with the Flo tool counts above; they are different tests measuring different things.

**Nothing is dropped.** Everything the three screens did is on a tab. The CRM lead form,
activities and opportunities all moved intact and have a test proving they still work in
their new home, plus a test proving they are not ALSO still on Legal Entities, because
two doors to one thing is the fault being fixed rather than a convenience.

**There is deliberately no Tests tab.** Entrance tests are stage two and are not built. A
tab opening onto nothing would be a button that looks like a feature. A test asserts its
absence so nobody adds an empty one.

**Two dead things found while reading, left alone on purpose.** The CRM gate names an
`admission` sub-category, and `_can_enroll` in `routes/admissions.py` names it too.
**`admission` is not a sub-category the platform recognises**, so both can never be true.
The plan's decision 5 says "the admissions desk" reaches this screen; **there is no
admissions desk profile**. Nothing was invented to fill the gap. A4 moves a panel; it
does not draw a new profile.

**Files.** New `frontend/src/components/tools/AdmissionsScreen.js`;
`AdminTools.js` (`EnquiryRegister` became the `EnquiriesPanel` tab);
`CommercialOperations.js` (CRM tab out, `AdmissionsPipelinePanel` exported);
`profile_matrix.py` plus its regenerated mirror; `Layout.js`, `Sidebar.js`,
`ToolDashboard.js`, `CommandPalette.js`, `managementHubs.js`, `notifRouting.js`;
`routes/exports.py`, `routes/search.py`, `routes/chat.py`, `ai/prompts.py`. The old words
"admission funnel" and "enquiry register" still work in chat, because the school says
them and being told "no such screen" would read as a feature being lost.

**Gate.** Backend 3,709 passed / 1 failed (the machine's `uharfbuzz` one, unchanged from
the baseline). Frontend 799 passed across 67 suites. Lint and production build clean.

## A5: who to call today (done 2026-08-14)

**The fault.** The follow-up date already existed and nothing ever read it back. Adding a
CRM activity with a date on it has written `next_follow_up` onto the enquiry since the
CRM shipped, and the only place that field was ever looked at again was a single number
on the pipeline summary. So the office could write down "call them on Tuesday" and the
platform would never mention it on Tuesday.

**What a person can now do.** The Enquiries tab of the Admissions screen opens with a
"Who to call" block: families missed, families due today, and families due in the next
seven days, each with the parent's name, the number, how late the call is and the last
thing anybody wrote down about them. "Log call" writes the note and sets the next date
through the CRM activity route the screen already had.

**The honesty is NOT the overdue count. It is the opposite one.** A list built only from
rows that carry a date is empty both when the office is up to date and when the office
has planned nothing at all, and those are opposite facts. So the answer always carries
how many open enquiries there are, how many have **no follow-up date at all**, and how
many are scheduled past the end of the window. The line is shown even when the list is
empty. Nothing lands in a bucket whose size the reader cannot see.

**A date that cannot be read is now refused at the point of writing**, on all three
entrances (new lead, lead update, activity). It was free text before, and nothing read it,
so nobody noticed. Now that it drives a worklist, an unreadable date would put a family in
a list nobody looks at while the record still shows a date beside their name. The 102 real
enquiries predate that rule, so one already carrying rubbish is shown in the missed group
and marked unreadable rather than dropped: a row in no bucket at all is the silent short
answer again.

**Complete, not capped.** The worklist has no row ceiling. It is bounded by the enquiries
the school is actively working, and a partial call list is worse than none.

**Nothing was widened.** `GET /api/commercial/crm/follow-ups` carries the same gate as the
activities that WRITE the date, one line above it in the same file: owner, principal,
receptionist. Those are exactly the profiles holding the Admissions screen. The block
hides itself for anybody the gate refuses rather than showing an error over a list that
works.

**Files.** `backend/services/commercial_service.py` (`follow_up_worklist`,
`_follow_up_date`, `FOLLOW_UP_CLOSED_STATUSES`), `backend/routes/commercial.py` (the new
route), `frontend/src/components/tools/AdminTools.js` (`FollowUpWorklist`, wired into
`EnquiriesPanel`), `tests/backend/api/test_follow_up_worklist.py` (12 new, including the
unauthenticated and wrong-role pair), `frontend/src/components/__tests__/FollowUpWorklist.test.js`
(7 new).

## A6: Flo can work the second half (done 2026-08-14)

**The fault.** Flo had `create_enquiry`, `update_enquiry_status`, `get_admissions_pipeline`
and `delete_enquiry`, and no application tool at all. The chat half of the platform could
take a family as far as "fee paid" and then stop. A person could ask Flo to do the first
half of a job and had no way of knowing the second half was not merely refused to them but
absent.

**Five tools, each a thin adapter over the same service function the screen calls**
(`services/admissions_service.py`): `create_admission_application`,
`update_admission_application_status`, `record_admission_assessment`,
`issue_admission_offer`, `enroll_admission_application`. Not a copy of the rules, the same
rules, so every refusal the screen gets Flo gets for free: no submitting without a
guardian name and phone, no "assessed" without an assessment, no acceptance without an
offer, and A2's rule that nobody sets enrolled by hand.
`tests/backend/parity/admissions_parity_test.py` pins screen and chat to identical writes,
and the five names are registered in `parity/corpus.py`.

**No new read tool, deliberately.** `get_admissions_pipeline` already lists applications
with their statuses. A second door onto the same list is the fault A4 spent its run
removing.

**`add_application_document` is deliberately absent.** It attaches an uploaded file, and
the thing it needs is a file rather than a sentence. Left for when the chat attachment path
is joined to admissions properly rather than half-joined now.

**Enrolment stops for a confirm card, and the other four do not.** The platform's settled
design is that ordinary single-record writes execute immediately. Enrolment is not one:
it is the only write in this platform that **brings a person into existence**, creating a
child's record and their guardians together and minting an admission number, and there is
no un-enrol. It is the mirror image of "destructive", which already stops. The second
reason is A2: enrolment was the exact place the funnel could claim a child existed when
none did, and a confirm card is how a person tells "Flo enrolled the child" from "Flo said
it did". Both confirm-set alarm tests were updated with that reason written into them.

### The four guards, each with a decision rather than a shrug

1. **Classification.** All five are `non_finance`, the same as `create_enquiry` and
   `get_admissions_pipeline`, which are the other half of the same funnel. None reads or
   writes a rupee figure: the admission fee on an offer is a number quoted to a family,
   not a ledger entry.
2. **Verb prefix.** All five are write-flagged and none uses a read prefix.
3. **Permission segment.** The `roles` and `sub_categories` on each MIRROR THE REST ROUTE.
   `_can_enroll` names an `admission` sub_category that the platform does not recognise
   and that can never be true; it is deliberately NOT repeated, because copying a dead
   value forward is how it comes to read as a real permission.
4. **The pinned reach counts moved, on purpose.**

**EXPECTED_REACH: owner and principal 159/98 to 164/103. Management 101/60 to 104/63.**
Read the three together. The management head gains only THREE, because issuing an offer
and enrolling a child are refused to him on the REST route by `_can_enroll`, so they are
named in his `denied_tools` and chat gives the same answer as the screen. The accountant
head and the six dormant desks did not move at all, which is the proof this landed where
it was aimed.

**A trap worth knowing.** `sub_categories: ["principal"]` on a registry entry does NOT
refuse the management head. `profile_authorization_decision` deliberately ignores
`sub_categories` for the domain profiles, and says so in its own comment. The mechanism
that works is `denied_tools` in `profile_matrix.py`, where a denial always wins. Without
that, Flo would have let him enrol a child the server refuses him.

**Files.** `backend/ai/tool_functions_v2.py` (five tool functions, five registry entries,
the classification list, the confirm set), `backend/services/profile_matrix.py` plus its
regenerated mirror, `backend/routes/chat.py` (required-parameter map),
`backend/ai/prompts.py` (two lines telling Flo the second half and the follow-up date
exist), `tests/backend/parity/admissions_parity_test.py` (new, 12 tests),
`tests/backend/parity/corpus.py`, `tests/backend/unit/test_all_nine_profiles_sweep_r2_13.py`,
`tests/backend/unit/test_flo_profile_matrix.py`,
`tests/backend/unit/test_release2_ai_layer_audit.py`.

**Gate for A5 and A6 together.** Backend 3,733 passed / 1 failed (the machine's
`uharfbuzz` one, unchanged from the baseline of 3,709 before this run). Frontend 806
passed across 68 suites. Lint and production build clean. No live school database was read
or touched. Deployed the same day; see the deploy block at the top of this file.

## Noticed while reading, not fixed, not in A1's scope

- ~~`GET /api/ops/enquiries` stops at **50 rows**.~~ **Fixed in A3.**

- **The school's own admission form and 102 real enquiries have now been read**, from
  `aaryans_database/`. Written up in `the-schools-own-admission-form-2026-08-14.md`. The
  headline: our enquiry holds **one** parent name, the school records mother and father
  separately on essentially every record, so "Start application" carries one of two
  parents across and cannot say which. The enquiry also lacks date of birth, gender and
  previous school, all of which the school captures at enquiry time and all of which then
  get retyped onto the application. Not A1's scope. Belongs with A3 or A4, and needs
  Abhimanyu to place it.

## Open question, flagged not built

An applicant sitting a test on screen would need a sign-in for somebody who is neither a
student nor staff. Part 4 of the plan. Not settled, not needed until stage two, and the
paper route ships without it.
