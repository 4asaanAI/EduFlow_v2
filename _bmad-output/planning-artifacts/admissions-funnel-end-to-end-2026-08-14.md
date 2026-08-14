# Admissions: one funnel, first enquiry to enrolled child

**Written 2026-08-14. Decisions in Part 1 are Abhimanyu's and are settled.**

## The one idea

The platform has two carefully built halves of the admissions journey and nothing joining
them. The consequence is the same shape as Release 4's: **the funnel can say a child is
enrolled when no child exists**, and nobody looking at the screen can tell that apart from
a real enrolment. Everything below is in service of one test: can a person tell "this child
joined the school" from "somebody moved a row to the last column"?

## Part 1: settled decisions, do not reopen

1. **The enrolled stage comes off the enquiry stage list.** Nobody picks it by hand. An
   enquiry becomes enrolled only when its application creates the child, which the code
   already does. The owner keeps the freedom to move stages, minus that one.
2. **Enquiry families become a messaging audience of their own**, built now, refusing to
   send and saying why until a real sender exists. **And** the follow-up log gets due dates
   and a "who to call today" list, which works with no sender at all. Both, not either.
3. **Entrance tests: date, place, and a list of who is sitting it.** Plus the paper
   generated on the platform and marking done on the platform.
4. **An applicant may sit the test on paper or on screen, the school picks per test.**
   Paper first. The on-screen route needs a sign-in for someone who is not a student, which
   is an open question in Part 4, not a settled decision.
5. **The three overlapping enquiry screens merge into one admissions screen.** Owner,
   principal and the admissions desk reach it. Each still sees exactly what their permission
   table already allows, so **the merge grants nobody anything**. The three old entries go.
6. **Two stages.** Stage one is the join and the screen. Stage two is tests and messaging.

## Part 2: what is actually there today, read not assumed

**The first half works.** Eight enquiry stages, each move written into that family's own
timeline with a note (`services/enquiry_service.py`).

**The second half works.** Eight application stages, and the refusals are careful: no
submitting without a guardian name and phone, no marking assessed without an assessment,
no accepting without an offer, and enrolling creates the child and the guardians together
in one transaction, properly linked (`services/admissions_service.py`).

**The break.** `create_application` already accepts an `enquiry_id`, copies the child's
name, class, parent name and phone across, and refuses a second application for the same
family. The screen (`AdmissionsWorkflow.js`) starts from a blank four-field form with no
enquiry picker. **The server can do it; the screen cannot ask for it.**

**The false enrolment.** `ALLOWED_TRANSITIONS` permits `fee_paid` to `enrolled` as an
ordinary move with no check that an application or a child exists, and the owner branch
above it lets the owner jump to any stage from anywhere. The only guard is that an
already enrolled enquiry cannot be reversed once a child is linked.

**Two things nobody had written down before:**

- **Enquiry families cannot be contacted through the platform at all.**
  `messaging_service.resolve_recipients` builds its list from `db.students` and
  `db.guardians` only. An enquiry parent is in `db.enquiries` and is invisible to it.
  Every follow-up call is made off platform and typed back in as a note.
- **The admission test is a word, not a record.** `assessment_scheduled` is a status and
  nothing else. No date, no place, no list of who is sitting it. The only test data on the
  record is the score, entered afterwards. The school cannot pull a list for Sunday.

**Also:** Flo has `create_enquiry`, `update_enquiry_status`, `get_admissions_pipeline` and
`delete_enquiry`, and **no application tool at all**, so the chat half of the platform can
only work the first half of the funnel.

**Reusable, already built:** `POST /api/academics/question-papers/generate` writes a CBSE
paper with the AI and is not tied to children on the roll, so an entrance paper can use it
as it stands. `services/quiz_service.py` is a working self-marking engine, but
`start_attempt` takes a student record, so an applicant cannot reach it without the
sign-in question in Part 4 being answered.

**Worth knowing about the numbers.** Most children arrive by the directory or the
spreadsheet load, both legitimate. The funnel describes a slice of the intake, never all
of it, and any count on the new screen should say so rather than read as the whole roll.

## Part 3: the work

### Stage one: join the halves and give them one home

**A1. Start an application from an enquiry.**
An enquiry picker on the application form, and a "Start application" button on each enquiry
row that carries the family across. The server call already exists and already refuses
duplicates. Test: starting from an enquiry produces an application carrying the parent's
name and phone, and a second attempt returns the first application rather than a duplicate.

**A2. The enrolled stage comes off the list.**
Remove `enrolled` from what a person may choose, on every path including the owner's.
Enrolment stays automatic from `enroll_application`. Test: every route and every Flo tool
refuses a hand-made move to enrolled, and an application enrolment still sets it.

**A3. The stages, said once.**
Publish which enquiry stage matches which application stage, in one place both halves read,
so the two vocabularies stop describing the same journey in different words. The screen
shows a family's position once, not twice.

**A4. One admissions screen.**
Merge Admission Funnel, Enquiry Register and the admissions part of Legal Entities into a
single screen with enquiries, applications and tests on it. The old entries go. Grouping
never grants: each profile's tool list resolves exactly as before. Nothing is dropped: any
tool that lived on the old screens and has no home on the new one is still listed. Test:
pinned reach counts per profile do not move.

**A5. Who to call today.**
Due dates on follow-up activities and a worklist of families overdue a call. No sender
needed, so this works from the day it ships.

**A6. Flo can work the second half.**
Application tools for Flo, reaching the same service functions as the screen, with the
parity test that pins screen and chat to identical writes. Bulk or state-changing ones
behind the usual confirm card.

### Stage two: tests, and talking to families

**B1. A test is a record.**
Date, time, place, and the applicants sitting it. A list for a given test, marked attended
or absent. Scores entered against that list, feeding the existing offer decision.

**B2. The paper.**
Generate the entrance paper on the platform using the generator that already exists, keyed
to the test rather than to a class.

**B3. Marking.**
On paper: the office enters marks per applicant against the test list, which is close to
what `record_assessment` already does. On screen: the applicant sits it and it marks
itself, which needs Part 4's answer first.

**B4. Enquiry families as a messaging audience.**
The same single send path, with enquiry parents as an audience of its own, and templates
for the follow-up, the visit reminder and the call letter. Every send written into that
family's timeline. It refuses and names the missing piece until a sender exists, exactly
like the existing channels do. **Nothing may report a send that did not happen.**

## Part 4: the open question, to settle before B3's on-screen half

An applicant is not a student and has no login. Letting one sit a test on a device means
creating a sign-in for a person outside the school, which is a new category of account.
There is no way to create a staff or teacher login through the platform today either, so
this is new ground rather than an extension of something. It needs deciding on its own
merits, and the paper route ships without it.

## Part 5: what this does not touch

Direct entry on the directory and the spreadsheet load both stay exactly as they are. They
are how most children arrive and neither is a defect.
