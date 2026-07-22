# Epic 8 — Ask, Don't Just Change · COMPLETED

**Branch:** `ui-sweep-2026-07-22` · **Date:** 2026-07-22
**Origin:** requested by Abhimanyu mid-run, reversing the first version of
Story 1.3 and then asking for the approval flow to be built.
**Requirements covered:** FR3, FR78, NFR-S1

---

## What the school gets

Nobody can change their own name, phone number or email any more — not a
teacher, not an accountant, not the Principal, not the Owner. Instead a person
*asks*, the Owner or the Principal sees the request beside their pending leave
approvals with the old and new values side by side, and nothing changes until
one of them approves it. If it is approved the correction is applied and the
person is told; if it is rejected nothing changes and they are told that too.

---

## Story 8.1 — A member of staff can ask for a correction

`POST /api/staff/me/change-requests` · `GET /api/staff/me/change-requests`

| AC | Met | How |
|---|---|---|
| A request is recorded and the record itself is unchanged | ✅ | Every refusal and every submission test asserts the staff record **and** the login record are untouched |
| The Owner and the Principal are notified | ✅ | via `create_notification()` (canonical), best-effort so a failed notification never loses the request |
| Only name, phone and email may be asked for | ✅ | Parametrised over six authority fields — the request route must not be a side door around the rule it serves |
| A mixed body is refused whole | ✅ | tested |
| Only one request may be waiting | ✅ | 409, so the queue cannot be flooded and a reviewer never has to guess which is current |
| Asking for what is already stored is refused | ✅ | An approval queue should not fill with changes that change nothing |
| No staff record → refused, none conjured | ✅ | tested |
| Audited | ✅ | `profile_change_requested` |

## Story 8.2 — The Owner or Principal decides

`GET /api/staff/change-requests` · `PATCH /api/staff/change-requests/{id}`

| AC | Met | How |
|---|---|---|
| Owner and Principal see the queue with old beside new | ✅ | Both values are stored on the request, so a reviewer never has to go and look up the current one — and the audit trail survives later edits |
| Everyone else is refused | ✅ | `require_owner_or_principal`; tested for a teacher and for an accountant, on both listing and deciding |
| Approval applies the change to the staff record **and** the login record | ✅ | The login record is what the sign-in token is built from; skipping it would make the correction vanish at the next sign-in |
| Rejection changes nothing, with an optional reason | ✅ | Optional by design — forcing a sentence makes people type "no" to get past it |
| The requester is told the outcome either way | ✅ | tested |
| A settled request cannot be decided twice | ✅ | 409; the first decision stands |
| **A Principal cannot approve their own request** | ✅ | Otherwise the Principal is an administrator who can approve their own change — exactly the self-editing this feature exists to prevent. Theirs go to the Owner. |
| Approving for a deleted staff record fails cleanly | ✅ | 404 rather than writing to a record that is no longer there |
| A nonsense decision is refused | ✅ | 422 |
| Audited | ✅ | `profile_change_approved` / `profile_change_rejected`, with who decided |

## Story 8.3 — Both sides are visible in the app

- **Profile dialog** — read-only details, then "Ask for a correction". Once a
  request is in, it shows what was asked and that it is waiting, and the button
  is gone until it is settled. Only the fields the person actually altered are
  sent, so a reviewer sees one clear change rather than three fields of which
  two are identical.
- **Staff screen** — a "Corrections" tab beside "Pending Leaves", visible only
  to the Owner and Principal, each row showing old → new with Approve/Reject.
- Every control carries a `data-testid`, uses CSS variables, and reuses the
  existing `.focus-ring` utility.

## Tests

`tests/backend/api/test_ui_sweep_epic8_change_requests.py` — 34 tests, passing
first run. New `profile_change_requests` collection registered in the test
harness.

**Full suite: 1720 passed, 2 failed (the pinned pre-existing pair), 14 deselected.**

## Not done

Hands-on verification in the running app — the only working environment points
at live production and the flow ends in a real write. On
`HUMAN-VERIFICATION-CHECKLIST.md` for Abhimanyu, marked as not verified by this
run. No production data was written.
