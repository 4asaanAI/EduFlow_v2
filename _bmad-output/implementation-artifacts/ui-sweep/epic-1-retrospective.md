# Epic 1 — Retrospective

**Date:** 2026-07-22 · **Branch:** `ui-sweep-2026-07-22`

---

## What went well

**The pre-implementation passes earned their cost.** STEP 3 (elicitation +
party mode) was run before a line of code and produced nine changes to the
acceptance criteria. Two of them were not polish — they were the difference
between a working fix and a broken one:

- A blanket "refuse `role: owner`" would have made the staff form unusable for
  the Owner's own record, because the form posts every field back. Caught by a
  pre-mortem, not by testing.
- Nobody had noticed that refusing to *grant* owner without also refusing to
  *remove* it would let the last owner be demoted into a school with no owner
  and no in-app way to appoint one.

Both would have shipped, and both would have been found by Aman rather than by
us.

**Writing the negative-space tests first.** The test that matters most is not
"does it return 403" — it is "after the 403, is there no half-written login
account". That framing came from the party-mode pass and immediately shaped the
implementation: the gate had to move above `_create_or_link_user`, which is
where the real authority (`auth_users.user_info.role`) is written. A 403 that
still left a privileged login behind would have *looked* fixed.

**Tests caught my own mistakes twice.** The first run of the new file failed
two tests — both were real defects in my implementation, not bad tests. The
adversarial pass then found a third, higher-severity one (F-1) that no
acceptance criterion covered.

**Rewriting the three inherited tests rather than deleting them.** They encoded
the weaker contract. Each now asserts the stronger one, and the behaviour they
were really protecting (the salary silent-strip) kept its own test.

## What did not go well

**The biggest miss was not a bug — it was building the wrong thing.** Story 1.3
let staff edit their own contact details. The acceptance criteria were argued
through two review passes; the implementation satisfied all of them; 44 tests
passed. The owner read one sentence of the summary and reversed it: a person
changing their own name or phone is itself a way to misuse an account.

No review lens available here could have caught that. Adversarial review asks
"is this built correctly"; it does not ask "should this exist". The story came
from a defect list, and somewhere between the defect and the story it acquired
a product decision — *who may change a person's details* — that nobody
recognised as a decision, so nobody took it to the person whose school it is.
**Rule for the epics after this: anything that changes what a person is allowed
to do gets confirmed with Abhimanyu before it is built, not at the demo.**
Cheap to ask, and the reversal cost a rebuild of a whole story plus a new epic.

**The root cause of D-02 repeated itself in miniature.** D-02 exists because a
frontend change was reported as a security fix. In this epic I initially wrote
the field-validation check *before* the authority check — which would have
handed an unauthorised caller a helpful error listing the values that would
have worked. Same family of error: fixing the visible surface rather than the
gate. The lesson is not "be careful"; it is that **the ordering of guards is
part of the guard**, and belongs in the AC.

**Hands-on verification was only partly possible, and that is a standing
problem, not a one-off.** The only working environment points at live
production, and the browser here is signed into the owner's real account. So
step 4e cannot be completed for any story that involves saving something —
this epic, and every epic after it. Two items went to the human checklist that
should have been verifiable by the person doing the work.

**Scope crept, defensibly but really.** Four items outside Epic 1's literal
scope were fixed in-run (D-11 through D-14). Each was small, safe and adjacent,
and each is logged — but "adjacent to a security fix" is an elastic phrase and
I should watch it.

**The window would not shrink below ~1400px**, so the mobile check — the
initiative's whole premise — could not be made. Worth solving before Epic 2,
which is entirely about phone width.

## What changes for Epic 2

0. **Confirm product decisions with Abhimanyu before building them.** Any story
   that changes who may do what to whom. See D-18 — this cost a full rebuild.
1. **Get a local environment that is not production.** Epic 2 is the mobile
   epic; verifying it against a system where every save is real is untenable.
   Before starting: either a local backend against a throwaway database, or
   explicit owner approval for a named test account on production. This is the
   single highest-value change and it blocks honest verification of everything
   after it.
2. **Use Chrome's device emulation, not window resizing.** Window resizing hit
   an OS floor. Device-mode emulation reports a true 390px viewport.
3. **Put guard *ordering* in the acceptance criteria**, not just guard
   existence, wherever a story has more than one check on the same path.
4. **Confirm Epic 2's real remaining scope before writing stories.** The epic
   document says it is "largely SHIPPED" with only the UX-DR7 type scale
   outstanding. That claim comes from the same session that mis-reported D-02,
   so it should be verified against the code rather than believed. (This is why
   the next handoff targets Epic 3, with Epic 2's remainder to be confirmed
   first.)
5. **Keep the STEP 3 passes.** They found more than the epic-close gate did,
   at lower cost, because nothing had been built yet.

## Numbers

| | |
|---|---|
| Stories | 3, all ACs met |
| Findings from the pre-implementation passes | 9, all folded into ACs before coding |
| Findings from the epic-close gate | 10 fixed, 5 dismissed with reasons |
| New tests | 44 (+2 net in rewritten files) |
| Suite | 1682 passed / 2 failed (pinned) / 14 deselected |
| Writes to production | 0 |
