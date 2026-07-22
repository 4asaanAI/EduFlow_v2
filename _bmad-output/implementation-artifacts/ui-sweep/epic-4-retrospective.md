# Epic 4 — Retrospective

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

---

## What went well

**Finding the root cause before writing a single story changed the whole epic.**
The epic document itself said owner item 7 was an FR5 scoping fault. It was not — it
was a second result envelope wrapped around the first. Had the stories been written
from the map, the run would have hunted a scoping bug in the fee and attendance
queries, failed to find one, and "fixed" the Board Report with better fallbacks. That
is precisely the PRIME DIRECTIVE failure. **Half an hour reading `routes/tools.py`
turned a one-screen cosmetic story into an eleven-screen root-cause fix.**

**Asking before building, and being told yes.** Story 4.5 changes what people are
permitted to do. It was put to Abhimanyu with the trade-offs before any code existed,
and he approved all three parts. D-18 cost a full rebuild last time because the
question was asked at the demo instead of before the build. This time the question
came first and cost nothing.

**The party-mode pass earned its place twice.** It produced the single most valuable
insight of the run: *fixing the numbers without the honest labels in the same breath
makes things worse.* The school has one fee record for 1,802 students, so the moment
real figures flowed, "₹0 collected" would have been indistinguishable from the broken
₹0. It also caught that "0% attendance" on a Monday morning reads as a school-wide
catastrophe. Both became acceptance criteria and then code. Neither came from me.

**Applying the last retrospective's rules caught defects rather than decorating the
log.** "After changing a shared component, list every screen that uses it" found F-3
— my own change to `attendance_rate` would have made two health scores report a
healthy school as failing every morning. That is the epic's own defect reappearing in
a new place, and the rule caught it before the owner did.

**The tests found my bugs, not just the old ones.** Six of fifteen findings (F-3,
F-6…F-10) were introduced **by this epic** and caught by its own tests within minutes
of being written. Proving the key regression fails against the old code — restoring
the pre-fix endpoint and watching 9 of 12 tests fail — took two minutes and converted
"this should catch it" into "this does catch it".

**Refusing to write a test that would have lied.** The in-memory database cannot
evaluate the Class Strength aggregation and returns the same count for every bucket.
An assertion through it would have passed and proved nothing — the identical trap as
the browser-test double that hid the original defect for an entire initiative.
Extracting the rule into a pure function and testing that, then saying plainly that
the arithmetic is unverified, is worth more than a green tick that means nothing.

---

## What did not go well

**Both of the owner's mid-run findings were in screens I had already been in.**
The Class Strength "Other == Total" defect is in `StudentDatabase.js`, which Epic 3
converted. The missing column sorting is in `ToolPage.js`, which I edited twice this
run. He found them by opening the app; I did not, because I was reading the files I
had decided were relevant. **Six of fifteen findings still came from him.** Better
than the last run's eleven of fifteen, but the pattern has not broken.

**I answered "is sorting available everywhere?" by counting, and the honest count was
bad.** Two screens had it. Thirty-three shared one component that did not. Twenty-two
more were hand-rolled. Epic 3 was called "Finding One Record Among Two Thousand" and
closed, and FR82 was mapped to it as covered. It was covered for the two lists Epic 3
converted, and the completion log did say so — but the epic's *name* promised the
platform and the coverage map read as satisfied. **A coverage map that says "covered"
should mean covered, or say the number.**

**The gate ran twice instead of once over a frozen diff.** Exactly the weakness the
last retrospective told me to fix. Live feedback arrived mid-gate, and rather than
defer it I implemented it and re-ran everything. The result is honest and the suite is
green, but it is a second consecutive epic where the diff moved under the review.

**Three defects I introduced were all the same shape: a control that disappears.**
The retry button unmounted (F-6), then flipped back to stale content (F-7), then was
disabled on press (F-8) — each independently throwing keyboard focus to the top of the
page. I was thinking about what the screen *says* and not about what happens to the
person's hands. One test written early — "press the button, is focus still there" —
would have caught all three at once.

**My own estimate of the test count was wrong in the log doc before I measured it.**
Small, but it is the same reflex as reporting a fix as done: writing the number I
expected rather than the number the tool printed. I corrected it from the run output.

---

## What changes for the next epic

1. **Open the screen before deciding a story is done.** Not the file — the screen. Both
   of his findings this run were visible on first render of a page I had edited.
2. **When a requirement says "every X", count the X.** Do it before claiming coverage
   and put the number in the log. "Sorting works" and "sorting works on 2 of 57 tables"
   are different sentences.
3. **Fix defects in the shared component, and check the count of consumers.** This
   worked twice this run (33 tables got sorting from one edit; the token layer reached
   25 panels last run). It is the highest-leverage move available.
4. **Write the keyboard test first for any control that changes state on press.** Focus
   loss is invisible to a mouse user, invisible in a screenshot, and caught instantly by
   one assertion.
5. **Freeze the diff, or say plainly that it moved.** Two epics running. If live
   feedback is expected, the honest structure is a first gate on the planned diff and a
   named second gate on the additions — which is what happened, and what the review doc
   now says.
6. **Never report a number I have not read off the tool's output.**

---

## Numbers

| | |
|---|---|
| Stories | 5 (4.5 added by the readiness review, owner-approved before build) |
| Findings | 15 fixed, 5 dismissed with reasons |
| — introduced by this epic, caught by its own tests | **6** |
| — from Abhimanyu testing live | **2** |
| — from the readiness review, before any code | **2** (one of them the epic's own wrong root cause) |
| — from the party-mode pass | **3** |
| New tests | **66** (39 backend, 27 frontend) |
| Backend suite | 1784 passed / 2 pinned / 14 deselected |
| Frontend suite | 184 passed / 2 pre-existing |
| Production builds broken | 0 |
| Live-data writes | **0** |
| Screens whose figures were wrong before this run | **11** |
| Tables that gained column sorting | **34** (33 shared + Class Strength) |
