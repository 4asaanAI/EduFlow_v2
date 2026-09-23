---
title: 'Search-result profile open + student Fee Collection CTA'
type: 'feature'
created: '2026-09-23'
status: 'done'
context: []
baseline_commit: '131836307f77a863a118d01dc2a8d01d2f784546'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The top-bar search panel (`Header.js` `SearchPanel`) finds students/staff but its
click handler only opens the *list* tool (`student-database` with no `focus`, or the wrong tool
`staff-attendance-tracker` for staff) — it never opens that person's actual profile, unlike
School Directory's row click which deep-links `?tool=...&focus=<id>` straight into the profile
drawer. Separately, a student's profile drawer (`StudentDatabase.js` `DetailPanel`) has no way
for finance staff to see the student's full fee picture or record a payment without leaving the
profile and hunting the student down again inside the Fee Collection tool.

**Approach:** (1) Make the search panel's result click reuse the exact same `?tool=&focus=`
deep-link mechanism Directory already uses, routing students to `student-database` and staff to
`staff-tracker` (matching Directory, not the currently-wrong `staff-attendance-tracker`). (2) Add
a "Fee Collection" CTA to the student `DetailPanel`, visible only to finance-authorized roles
(owner, admin+principal, admin+accountant/accounts — mirroring backend `require_finance_profile`),
opening an embedded panel that lists the student's fee transactions (collected/pending/history)
and lets the user record a payment, reusing the existing `/api/fees/transactions` GET/POST
endpoints already used by `FeeCollection.js` — no new backend routes.

## Boundaries & Constraints

**Always:**
- Reuse the existing `focus`-param deep-link pattern (`StudentDatabase.js`, `StaffTracker.js`)
  unchanged — do not invent a second way to open a profile.
- Fee Collection CTA renders only for `owner`, or `admin` with `sub_category` in
  (`principal`, `accountant`, `accounts`) — same set as backend `require_finance_profile` in
  `backend/routes/fees.py`. Staff profiles never show this CTA (student-only, per intent).
- Reuse `getFeeTransactions`, `recordFeePayment` from `frontend/src/lib/api.js` — no new backend
  endpoints, no duplicate fee-math.
- Idempotency key for the payment POST follows the existing pattern in `FeeCollection.js`:
  `` `${student_id}|${fee_period}|${fee_head.trim().toLowerCase()}` ``.
- New embedded UI code goes in `frontend/src/components/ui/StudentFeePanel.js` (a widget, like
  `ProfileDocuments.js`/`ProfileNotes.js`, not a routed tool).

**Ask First:** none identified — both changes are additive and reuse existing gated endpoints.

**Never:**
- Do not change `staff-tracker`'s own `focus` handling, `StudentDatabase`'s `DetailPanel` fee
  display (`feeStatus`/`feeExplain`), or any backend route/RBAC — this spec is UI wiring only.
- Do not widen who can view/record fees beyond the existing finance-profile set.
- Do not touch the `own["id"]` gap in the student-self search result (backend/routes/search.py
  line ~193) — out of scope, unrelated to either pointer.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Search → open student | Owner searches "Sharma", clicks a student result | Navigates to `?tool=student-database&focus=<id>`; `DetailPanel` opens with that student loaded | N/A |
| Search → open staff | Owner clicks a staff result | Navigates to `?tool=staff-tracker&focus=<id>`; staff editor opens with that record | N/A |
| Search → open tool/announcement | Click a tool or announcement result | Unchanged existing behavior (dispatch `open-tool` with the tool id) | N/A |
| Fee CTA visible | Owner/accountant/principal opens a student's `DetailPanel` | "Fee Collection" button shown in the Actions row | N/A |
| Fee CTA hidden | Teacher (or any non-finance role that can still reach `DetailPanel`) opens a student's `DetailPanel` | No "Fee Collection" button rendered | N/A |
| Fee CTA hidden on staff | Any role opens `StaffTracker`'s editor | No Fee Collection CTA present (student-only) | N/A |
| View fee data | Finance user clicks "Fee Collection" | Panel opens, fetches `getFeeTransactions({student_id})`, shows collected total, pending total, and a transaction history list | Fetch failure shows an inline error, does not crash the drawer |
| Record payment | Finance user fills fee_period/fee_head/amount and submits | `recordFeePayment` POSTs with idempotency key; on success the transaction list and totals refresh in place | Validation error (missing field) shown inline before submit; API error (e.g. 403 from a stale session) shown inline, panel stays open |
| Duplicate submit | Same idempotency key resubmitted (e.g. double-click) | Backend returns idempotent replay; UI shows "Duplicate submission recovered" per existing `FeeCollection.js` convention | N/A |

</frozen-after-approval>

## Code Map

- `frontend/src/components/Header.js` -- `SearchPanel.handleResultClick` currently mis-routes student/staff clicks; fix to dispatch `open-tool` with `{tool, focus}`.
- `frontend/src/components/Layout.js` -- `open-tool` listener (~line 289) and `setActiveToolParam` (~line 158) only handle a plain tool-id string; extend to accept `{tool, focus}` and set both search params in one navigation.
- `frontend/src/components/tools/StudentDatabase.js` -- `DetailPanel` (line 510) gets the new CTA + embedded `StudentFeePanel`; top-level component (line 923) computes and passes a `canManageFees` prop alongside existing `canManage`.
- `frontend/src/components/ui/StudentFeePanel.js` -- NEW. Embedded fee summary + history + record-payment widget, mirroring `ProfileDocuments.js`/`ProfileNotes.js` conventions.
- `frontend/src/lib/api.js` -- no changes; `getFeeTransactions`, `recordFeePayment` already exported (lines ~727, ~733).
- `backend/routes/fees.py` -- no changes; `GET/POST /api/fees/transactions` already scoped by `require_finance_profile` (line 78) and support `student_id` filter (line 372).

## Tasks & Acceptance

**Execution:**
- [x] `frontend/src/components/Layout.js` -- extend `setActiveToolParam` to accept an object `{focus}` in its `options` and set/clear the `focus` search param; extend the `open-tool` event handler to accept `e.detail` as either a string (back-compat) or `{tool, focus}` -- lets any caller open a profile the same way Directory does.
- [x] `frontend/src/components/Header.js` -- rewrite `handleResultClick`: `student` → dispatch `open-tool` detail `{tool: 'student-database', focus: r.id}`; `staff` → `{tool: 'staff-tracker', focus: r.id}`; `tool`/`announcement` unchanged.
- [x] `frontend/src/components/ui/StudentFeePanel.js` -- new component: props `{studentId, studentName, onClose}`; on mount calls `getFeeTransactions({student_id: studentId})`; computes collected (`sum of paid/partial paid_amount`) and pending (`sum of amount - paid_amount for pending/overdue/partial`) totals; renders a transaction table (period, head, amount, status, due date) and a record-payment form (fee_period, fee_head, amount, payment_mode, status) that calls `recordFeePayment` with the same idempotency-key pattern as `FeeCollection.js`; refetches on success.
- [x] `frontend/src/components/tools/StudentDatabase.js` -- compute `canManageFees = currentUser.role === 'owner' || (currentUser.role === 'admin' && ['principal','accountant','accounts'].includes(currentUser.sub_category))` near existing `canManage`/`isHeadOfSchool`; pass to `DetailPanel`; in `DetailPanel`, add a "Fee Collection" `Btn` next to "Edit Profile" gated on this prop, opening `StudentFeePanel` (state `showFeePanel`).
- [x] `frontend/src/components/__tests__/` -- add/extend a test covering: search result click for a student sets `focus` + `tool` params (or dispatches the right event payload); `DetailPanel` shows the Fee Collection CTA only for finance roles.

**Acceptance Criteria:**
- Given the owner searches for a student in the top-bar search and clicks the result, when the panel closes, then the URL/tool state matches exactly what clicking that same student in School Directory would produce (`tool=student-database`, `focus=<id>`), and the profile drawer opens with that student loaded.
- Given the owner searches for a staff member and clicks the result, then it opens `staff-tracker` with `focus=<id>` (the staff editor for that person), not the staff attendance tracker.
- Given an accountant opens a student's profile, when they click "Fee Collection", then they see that student's collected total, pending total, and transaction history, and can submit a new payment that appears in the list without leaving the profile.
- Given a teacher (non-finance role) opens a student's profile (wherever their access already permits it), then no "Fee Collection" CTA is rendered.
- Given a payment submission is missing a required field, then the form shows a validation message and does not call the API.

## Spec Change Log

## Design Notes

`StudentFeePanel` renders as a slide-over layered above `DetailPanel` (`position: fixed`, higher
`zIndex` than the drawer's 190), matching the existing pattern where `EnrolmentStateModal` /
`EraseConfirmModal` stack above `DetailPanel` in `StudentDatabase.js`. It does not reuse
`FeeCollection.js` wholesale (that component is a full multi-tab tool screen with payroll,
discounts, WhatsApp reminders, etc. — far outside this CTA's scope) — it borrows only the
payment-form field set and the idempotency-key convention.

## Verification

**Commands:**
- `cd frontend && npm run build` -- expected: lint (`eslint --max-warnings=0`) and Vite build both pass
- `cd frontend && CI=true npx jest` -- expected: 0 failures, including new/updated tests
- `python -m pytest tests/backend/ -q` -- expected: 0 failures (no backend files touched, but confirms nothing else regressed)

**Manual checks (if no CLI):**
- Start both servers, log in as owner: search a known student's name in the top-bar search, click the result, confirm the profile drawer opens (not just the list).
- Log in as owner: open a student profile, click "Fee Collection", confirm totals and history render, record a small test payment, confirm it shows up immediately.
- Log in as a teacher (or any non-finance role reachable in this build): confirm the Fee Collection CTA is absent from any student profile they can open.

## Suggested Review Order

**Search result → profile deep-link**

- Entry point: student/staff results now dispatch `{tool, focus}` instead of a bare tool id, matching Directory's own click handler.
  [`Header.js:80`](../../frontend/src/components/Header.js#L80)

- `open-tool` handler learns the `{tool, focus}` shape while staying back-compatible with plain string callers.
  [`Layout.js:297`](../../frontend/src/components/Layout.js#L297)

- Fix for a real bug the review caught: a second, different `focus` while already mounted on the same tool used to be silently dropped.
  [`StudentDatabase.js:973`](../../frontend/src/components/tools/StudentDatabase.js#L973)
  [`StaffTracker.js:468`](../../frontend/src/components/tools/StaffTracker.js#L468)

**Fee Collection CTA**

- Role gate mirrors the backend's `require_finance_profile` set exactly, so the button never appears where the panel would just 403.
  [`StudentDatabase.js:1001`](../../frontend/src/components/tools/StudentDatabase.js#L1001)

- The CTA itself, next to Edit Profile, opening the new embedded panel.
  [`StudentDatabase.js:628`](../../frontend/src/components/tools/StudentDatabase.js#L628)

- New embedded fee panel: fetch, totals, history, and the record-payment form reusing `FeeCollection.js`'s field set and idempotency-key convention.
  [`StudentFeePanel.js:41`](../../frontend/src/components/ui/StudentFeePanel.js#L41)

- Review-driven hardening: closes itself if the underlying student changes mid-open, and blocks a partial payment with no amount entered.
  [`StudentDatabase.js:567`](../../frontend/src/components/tools/StudentDatabase.js#L567)
  [`StudentFeePanel.js:82`](../../frontend/src/components/ui/StudentFeePanel.js#L82)

**Tests**

- [`LayoutRouting.test.js`](../../frontend/src/components/__tests__/LayoutRouting.test.js#L169)
- [`HeaderSearchResultClick.test.js`](../../frontend/src/components/__tests__/HeaderSearchResultClick.test.js#L1)
- [`StudentFeeCollectionCTA.test.js`](../../frontend/src/components/__tests__/StudentFeeCollectionCTA.test.js#L1)
