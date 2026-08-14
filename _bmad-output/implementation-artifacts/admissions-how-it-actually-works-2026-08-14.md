# How admissions actually works today, from a family's enquiry to a child on the roll

**Read from the code on 2026-08-14, not from any earlier document. Nothing was changed.
No live school data was read.**

Abhimanyu asked two things: how the admission funnel works today, and whether there is a
proper workflow from a family's first enquiry through to the child being enrolled.

**The short answer: the pieces all exist and are individually well built, but they are not
joined up. There are TWO separate admission tracks running side by side, they do not
connect through any screen, and one of them can mark a child "enrolled" without a student
record ever being created.**

---

## Track one: the enquiry pipeline

This is what the school sees on **Enquiry Register** (admin) and **Admission Funnel**
(owner), and again on the CRM tab of **Legal Entities & Admissions**. All three read the
same records.

Eight stages, and a move is only allowed to the next one or to "lost":

`new` → `contacted` → `visit_scheduled` → `visited` → `documents_submitted` → `fee_paid`
→ `enrolled`, with `lost` reachable from any of them.

The school's owner may move a stage freely rather than one at a time. Everyone else follows
the ladder. Once an enquiry is `enrolled` **and** has a student attached, it cannot be
reverted without deleting the student first, which is a good guard.

Each move is written to the enquiry's own timeline with a note, so the history of chasing a
family is kept.

## Track two: the application lifecycle

This is the **Applicant to student workflow**, and it is not a menu entry of its own. It is
a panel sitting at the bottom of the Admission Funnel and the Enquiry Register, which is
why it is easy to miss.

Eight statuses, with a proper state machine that refuses an invalid jump:

`draft` → `submitted` → `under_review` → `assessment_scheduled` → `assessed` → `offered`
→ `accepted` → `enrolled`, with `rejected` and `withdrawn` available at most steps.

It is genuinely careful work. It refuses to submit without a guardian name and phone,
refuses to mark assessed without an assessment result, refuses to accept without an offer
on record, and refuses to reach enrolled by a status change at all: enrolment has to go
through its own step. It carries documents, an assessment, a dated offer, and a full
history of who moved what and when.

**Only this track creates a student.** Enrolling here creates the child and the guardians
in one transaction, links the student back to the application, and marks the enquiry
enrolled too.

---

## The problems, in the order they would bite

### 1. There is no way to turn an enquiry into an application. On any screen.

The server supports it: creating an application accepts an enquiry to build from, and will
copy across the child's name, the class, the parent's name and phone, and will refuse to
create a second application for the same enquiry.

**The form on screen has no field for it.** It asks only for applicant name, guardian name,
guardian phone and class. So in practice every application is typed in from scratch, and
the family's whole enquiry history is left behind.

That is the single break in the chain. Everything either side of it works.

### 2. An enquiry can reach "enrolled" without any child being created

`fee_paid` → `enrolled` is an ordinary stage move on the enquiry. Nothing checks that an
application exists, and nothing creates a student.

So the funnel can show a child as enrolled while the school has no student record for them.
Whoever is looking at the funnel has no way to tell that apart from a real enrolment. **This
is the same shape as the fault Release 4 was written to close: a person cannot tell "done"
from "we only wrote down that it was done".**

The reverse guard exists and is good, but it only triggers when a student IS attached, so
it never fires on the case above.

### 3. Three screens show the same enquiries under three names

Enquiry Register, Admission Funnel, and the CRM tab of Legal Entities & Admissions all read
the same records. The menu labels the Enquiry Register "Admissions CRM", which is the name
of the other screen's main tab.

They differ only in extras: the CRM tab adds a follow-up activity log, a rupee value and
probability per lead, and a weighted total. The other two do not show any of that.

### 4. The application workflow has no front door

It is a panel at the bottom of two other screens rather than a menu entry. Somebody looking
for "where do I process an admission" would not find it.

### 5. Two different vocabularies for one journey

A family passes through `visited`, `documents_submitted`, `fee_paid` on one track and
`under_review`, `assessed`, `offered`, `accepted` on the other. Both end in `enrolled`.
Nobody has said which stage on one corresponds to which on the other, and the two do not
move together.

---

## So: is there a proper workflow from enquiry to enrolment?

**No, not end to end.** There are two good halves with nothing joining them.

- Capturing and chasing a family's enquiry: **works properly.**
- Running an application through assessment, offer, acceptance and creating the child:
  **works properly, and carefully.**
- **Getting from the first to the second: there is no path on any screen.** The server
  supports it and no screen offers it.

A family enquiry today therefore ends in one of two ways. Either somebody re-types the
family into the application workflow and the enquiry history is orphaned, or somebody
walks the enquiry to `enrolled` and no student is created at all.

## Other ways a child gets onto the roll

Worth knowing, because the admissions workflow is not the only door:

1. **The application workflow.** The proper one, described above.
2. **Adding a student directly** on the School Directory, or by asking Flo. No enquiry, no
   application.
3. **The spreadsheet import**, "Add new students". Creates children in bulk with generated
   admission numbers. Owner and principal only.

Doors 2 and 3 are legitimate and needed, particularly for loading an existing school. The
point is only that **most children will not arrive through the admissions workflow**, so
the funnel's numbers describe a slice rather than the whole intake.

---

## What I would suggest, for a decision rather than as a plan

Smallest first. None of this is started.

1. **Add "start an application" to the enquiry screen.** The server already does the work
   and refuses duplicates. This is a button and a field, and it closes the one real break.
2. **Stop an enquiry reaching "enrolled" on its own.** Either require an application, or
   rename that stage so it does not claim something that did not happen. This is the same
   test as Release 4: can a person tell "enrolled" from "we marked it enrolled"?
3. **Decide what happens to the three duplicate screens**, the same question the school's
   owner settled for the student and staff directories on 2026-08-07 when he asked for one
   place rather than three.
4. **Give the application workflow its own menu entry**, so it can be found.

Item 1 is the one that turns two working halves into a working whole, and it is the
smallest of the four.
