# LIVE TO-DO: the three approvals leftovers (2026-08-15)

**This file is updated as the work happens.** Re-read it any time to see where things stand.

Last updated: all three DONE and green. Surveying pick-lists next.

| # | Task | State |
|---|---|---|
| 1 | The raise form. A person can only answer a request, not start one. Screen half only. | **DONE** |
| 2 | The colleague pick-list, and opening an attachment. | **DONE** |
| 3 | Merge the two staff leave decision paths, keep the one that marks the person away. Pin with a test that Aman or Adesh can act on all six kinds. | **DONE** |
| 4 | **NEW, asked 2026-08-15:** make every pick-list across EduFlow type-to-search. List them all first. | Survey in progress |

**Gate after 1 to 3:** backend 4,000 passed / 0 failed / 14 deselected. Frontend 875 passed
across 73 suites. Production build clean including lint. Baseline before this work was
3,941 and 868 across 73. No live school data was read or changed. **NOT DEPLOYED.**

---

## 1. The raise form

`ApprovalsQueue.js` now has an "Ask for something" control and a form behind it.

- **The control appears only when the server says so.** `GET /api/approvals/kinds` already
  answered `may_raise` per kind and nothing read it. So the screen never holds its own
  idea of who may ask for what, which is how a button ends up offered to somebody the
  route then refuses. The school's owner does not see it: decision 25 says he approves,
  he does not raise.
- **Only the general kind is raisable, deliberately.** A certificate is asked for on the
  certificates screen and leave on the leave screen. A second way to create the same
  record is how two ways to create one thing drift apart.
- **One honest limit, written down rather than left to be found.** There is exactly one
  create route today. If a seventh kind ever declares itself raisable it needs its own
  route and a line in the form. The kind picker only appears when the server offers more
  than one, so nothing today can be sent to the wrong place.
- The empty box is named before anything is sent, rather than one refusal for the lot.

## 2. The colleague pick-list, and opening an attachment

**The pick-list.** New route `GET /api/approvals/{kind}/{record_id}/people`.

- **Scoped to the record, NOT a staff directory.** Every approvals route is signed-in-only
  by design, because who may see a request is a question about the record. A flat
  colleague list on that gate would have handed the school's staff list to any student or
  guardian with a login. It refuses anybody who may not read that conversation.
- **The list is the staff room's own rule** (`_staff_contacts`): the login is active, the
  person is staff, and their release has landed. Nobody is offered who could not answer,
  and a profile switched on for its release appears the same day with no code change.
- **Names on screen, ids only on the wire.** Type-to-search, the count of matches always
  visible, and somebody already in the conversation is shown as such rather than hidden,
  so nobody adds them twice and wonders why nothing happened.

**The attachment.** It reached the screen as an id and nothing else, so the only honest
thing to draw was "2 attached". A count is not a document.

- The read route now names each file. That grants nobody anything: the file itself is
  still fetched one at a time through `/api/uploads/link/{file_id}`, which already carries
  the ordinary file rules plus the narrow approvals rule built on 2026-08-15.
- **The link is minted on click, never held.** A stored link goes stale and then fails with
  a signature error, which reads to the person like the file being gone.
- A file whose record has vanished says so instead of offering a button that fails.

## 3. The two staff leave decision paths are one

`decide_leave` is **deleted**. `decide_leave_request` survives, because it also marks the
colleague unavailable in `staff_availability`, and **without that row a colleague given
leave still reads as available on every screen that asks.** Every caller was repointed:
the staff screen, Flo's `approve_leave` tool and the approvals queue.

**Four things were carried across from the deleted one**, because losing them would have
been a silent regression rather than a merge:

1. **The pending-only guard.** Without it a second decision quietly overwrites the first
   and sends the person a second notification saying the opposite.
2. **Branch scoping.** The survivor filtered on the school only. Branch scoping is what
   stops one branch's principal deciding another branch's leave, and a test proves it.
   Merging without this would have dropped that isolation in silence.
3. **The old field names.** `approved_by` and `rejection_reason` are still written beside
   `decided_by` and `decision_reason`, because screens, exports and the approvals card
   read the old ones on every row written before today.
4. **The better audit action name and notification wording.** The survivor wrote
   `leave_decide`, so the action log could not tell an approval from a refusal without
   opening the row. It is `leave_approved` / `leave_rejected` again, and the notification
   carries the dates. Nothing read `leave_decide`; checked before changing it.

**One rule deliberately did NOT move.** The operations screen has always insisted on a
reason either way; the staff screen and Flo never demanded one to approve. Rather than
pick a winner and quietly loosen one or tighten the other two, the stricter rule stays
where it already applied, as that screen's own rule, written down in the route.

**The pin asked for:** `test_approvals_screen_half_2026_08_15.py` proves either Aman or
Adesh can act on all six kinds, and, in the half that matters more, that nobody else can.
The six are named individually rather than counted, and a second test fails if the
registry ever holds a kind the pin does not cover.
