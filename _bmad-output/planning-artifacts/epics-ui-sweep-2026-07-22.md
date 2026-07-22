---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics']
executionDirective: 'The 7 Standing Rules (Abhimanyu, 2026-07-08) — binding, see body'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md (targeted extraction)
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-design-specification.md
  - _bmad-output/planning-artifacts/aaryans-source-of-truth-2026-07-22.md
documentsExcluded:
  - epics-ai-layer-reliability.md, architecture-ai-layer-reliability.md (separate shipped initiative;
    SSE contract carried instead from project-context.md)
source: 'Owner-reported defects (Aman Litt via Abhimanyu), 2026-07-22, 18 items'
branch: ui-sweep-2026-07-22
---

# eduflow — UI Sweep Epic Breakdown

## Overview

Decomposes the 18 owner-reported defects of 2026-07-22 into implementable stories.
This epic is **defect-driven**: its requirements originate from observed behaviour in
the running platform, traced back to existing PRD/UX requirements that are being
violated. PRD extraction is targeted to the requirements these defects touch — the
full PRD FR set (93 FRs) is not reproduced here.

## Binding Execution Directive — The 7 Standing Rules

Set by Abhimanyu 2026-07-08, re-affirmed for this epic set 2026-07-22. **Do not relax.**
Originally recorded in `_bmad-output/EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md`; they
apply to this UI sweep unchanged.

1. **One run = one full Epic.** Never one story, never two epics. A run ends only when
   the whole epic passes the epic-close gate.
2. **BMAD workflow steps are followed for every story and every epic.** Each story goes
   through story-creation and dev-story discipline. No story is "just coded".
3. **Testing and quality checks run at the END of the EPIC, not per story.** Exception:
   a story so fundamental that later stories cannot proceed gets the minimum tests to
   unblock, and the full gate still runs at the end.
4. **Every run ends by emitting the next-epic handoff prompt in the FIXED format,
   verbatim** — only the `{...}` slots change.
5. **Every run ends with the three log docs updated** (run log, deferred log, change
   log): completed, pending/deferred, and every bug or finding from the epic-close
   review. Nothing lives only in the chat transcript.
6. **Anything discovered mid-run** (bug, gap, smell, question) is either fixed in this
   run or explicitly logged in the deferred log with a reason and a pointer — never
   silently skipped.
7. **All communication with Abhimanyu or Shubham is in plain English.** Explain what
   happened and what it means for the product — not stack traces or jargon. Technical
   detail belongs in these log docs, not in messages to people.

### Rule-6 entries already open against this epic set

| Ref | Finding | Disposition |
|---|---|---|
| RISK-1 | "Owner" removed from the staff role dropdown is a frontend-only change; FR4 and NFR-S1 require server-side denial. Reported to the owner as closed — it was not. | Epic 1, must fix |
| RISK-2 | Backend test suite has 2 order-dependent failures in `test_r13_tenancy_rbac.py` (pass alone, fail in full run). Pre-existing on `main`, verified via clean worktree. | Deferred — logged, not this epic |
| RISK-3 | `backend/.env` now holds the live production connection string. Tests must be run with `MONGO_URL` overridden; no guard exists to enforce it. | Deferred — proposed guard awaiting owner decision |
| RISK-4 | `_bmad-output/project-context.md` states "Sidebar width is 120px fixed"; actual is 260px (280px mobile drawer). Loaded as authoritative by BMAD workflows. | Deferred — documentation correction |

---

## Requirements Inventory

### Functional Requirements

Extracted from `prd.md`, limited to requirements governing the reported defects.

- **FR2:** The system grants each user access to exactly the data and operations
  permitted by their assigned role, per the RBAC matrix; enforcement precedes any
  role-gated endpoint. *(governs items 11, and the shipped Owner-role lockdown)*
- **FR3:** Owner can create, edit, deactivate, and reassign roles for staff accounts.
  *(governs item 11 and the shipped staff-form changes)*
- **FR4:** The system denies any API request where the caller's role lacks permission,
  **regardless of UI state — enforcement is at the API layer, not the frontend**.
  *(critical: the shipped removal of "Owner" from the staff dropdown is a UI change
  only and does NOT satisfy FR4 — see RISK-1)*
- **FR5:** Each role sees only their permitted data scope; cross-role access blocked at
  the API layer. *(governs item 7 — a scoping fault is the suspected cause)*
- **FR7:** Any authenticated user can submit a natural-language query and receive a
  response scoped to their role's permitted data. *(governs items 9, 12, 13)*
- **FR11:** When Azure OpenAI is unavailable the platform still functions; chat shows a
  clear unavailable state. *(governs item 13 — stall handling)*
- **FR35:** Owner can view all open complaints, incidents and visitor logs across the
  school **in a single view**. *(precedent for item 17's consolidation)*
- **FR77:** Any authorised user can create, view, edit and deactivate a **student**
  profile per their role scope. *(governs item 17 School Directory)*
- **FR78:** Any authorised user can create, view, edit and deactivate a **staff**
  profile per their role scope. *(governs items 11, 17)*
- **FR81:** Any authenticated user can navigate between all capability areas available
  to their role from a **persistent navigation surface accessible from every screen**.
  *(governs items 2, 4, 16, 17 — and constrains removing the Back button)*
- **FR82:** Any list view that may contain more than 20 records supports pagination or
  infinite scroll, **and at minimum one column-level sort option**.
  *(governs item 6 — CURRENTLY VIOLATED across every data table)*
- **FR83:** The Owner dashboard presents a prioritised real-time summary composited as
  a single first-screen view **optimised for mobile**, in priority order: high-severity
  incidents → pending approvals → staff attendance → fee collection.
  *(governs items 1–5, 7, 8 — the mobile sweep is a PRD requirement, not a nicety)*

### NonFunctional Requirements

- **NFR-P1:** API response p95 ≤ 500ms for standard data operations.
- **NFR-P2:** Tool panel initial load ≤ 3s to interactive on simulated 4G (10 Mbps).
- **NFR-P3:** AI chat first token ≤ 3s from message submit. *(governs item 13)*
- **NFR-S1:** RBAC enforced **server-side**; client-side role checks are UI conveniences
  and are never the authoritative gate. *(governs items 11 and RISK-1)*
- **NFR-S2:** No PII in structured log fields; log records reference entity IDs only.
- **NFR-R1:** Write operations are atomic — no silent partial writes.
- **NFR-SSE1:** Server sends an SSE keepalive every 30s so the client can distinguish a
  dead connection from a quiet one. *(governs item 13)*
- **NFR-SSE2:** On tab re-visibility the client reconnects and fetches a fresh snapshot
  before resuming the stream. *(governs item 13)*
- **NFR-SSE3:** Multiple tabs for the same user must not double-process events.
- **NFR-SSE4:** If the upstream source is unavailable the channel stays open and silent,
  and the client shows "last updated X ago". *(governs item 13)*
- **NFR-A1:** Colour contrast ≥ 4.5:1 for body text in **both** light and dark themes.
- **NFR-A2:** All interactive elements have a visible focus state — minimum 2px solid
  outline at ≥3:1 contrast against the adjacent background.
  *(governs items 6, 9, 14, 16 — every new control)*

### Additional Requirements

From `architecture.md`, `project-context.md` and the platform's standing rules.

- Python 3.9: `from __future__ import annotations` must be the first line of any file
  using `str | None`, or the whole fixture-dependent suite silently skips.
- No TypeScript. `.js`/`.jsx` only.
- All frontend API calls go through `lib/api.js`; `axios` only for file uploads.
- `lucide-react` is the only icon library.
- Multi-tenancy: reads use `scoped_filter(query, get_school_id())`; branch isolation uses
  `scoped_query(..., branch_id=...)`. Intentional cross-branch queries carry a
  `# branch-scope: intentional` comment.
- Motor: `find()` returns a cursor — always `.to_list(N)` with an explicit limit.
- Every new endpoint requires a 401 unauthenticated test and a 403 wrong-role test.
- Notifications are written only via `create_notification()`; audit via `write_audit()`.
- SSE `done` must always be the final event or the client spinner never stops.
- **Live production data**: 1,802 students, 88 staff, 1,892 users. Read-only. No database
  writes without separate owner approval. The Track 2 data load (student DOB, gender,
  house, admission date from the FY2025-26 workbook) is **explicitly out of scope**.

### UX Design Requirements

From `ux-design-specification.md` (2026-07-08) and `ui-ux-pro-max`.

- **UX-DR1:** Use CSS variables (`var(--bg-card)`, `var(--text-primary)`), never raw hex.
- **UX-DR2:** Dark-first; every change must be verified in light theme too.
- **UX-DR3:** Fonts are Inter (body) and JetBrains Mono (code) — not to be changed.
- **UX-DR4:** `data-testid` on all interactive elements.
- **UX-DR5:** A shared sortable table component, so FR82 is satisfied once rather than
  re-implemented per screen. *(item 6)*
- **UX-DR6:** A shared empty-state treatment distinguishing "no data yet" from "not
  recorded" from "failed to load" — item 7 currently shows a load failure as a zero.
- **UX-DR7:** Mobile type scale. The platform renders labels at 12–13px throughout,
  below comfortable reading size and below the 16px threshold at which iOS zooms a
  focused field. Controls and their labels must be raised together.
- **UX-DR8:** Consistent spacing scale for stacked stream/step elements. *(item 12)*
- **UX-DR9:** Visible focus states at ≥3:1 contrast on every new control. *(NFR-A2)*
- **UX-DR10:** **Rows-per-page selector** on every paginated list, offering
  5 / 10 / 15 / 20 / 25 / 30 with 15 as the default, rendered beside the pagination
  control and showing the active value. Owner-specified 2026-07-22.
  Applies wherever a list can exceed one page — Student/School Directory (1,802 rows),
  Staff (89), notifications, All Chats, audit log, fee transactions, attendance.
  Requirements: the choice persists for the user across sessions (localStorage, keyed
  per table); changing it returns to page 1 rather than stranding the user on a page
  that no longer exists; the selected size is sent to the API so the server paginates
  — it must never be a client-side slice of an already-large payload, which would
  defeat the purpose on a 1,802-row table.
  This **extends FR82**, which mandates pagination and column sorting but says nothing
  about page size.

### FR Coverage Map

| Requirement | Epic | Covered by |
|---|---|---|
| FR2 | Epic 1 | Role permissions enforced server-side |
| FR3 | Epic 1 | Owner manages staff accounts and role assignment |
| FR4 | Epic 1 | **API-layer denial** — closes RISK-1 (UI-only fix shipped 2026-07-22) |
| FR5 | Epic 1, Epic 4 | Role data scoping; Board Report zero-count fault |
| FR7 | Epic 5 | Natural-language query and response surface |
| FR11 | Epic 5 | Clear unavailable/stalled state when AI is degraded |
| FR35 | Epic 7 | Single unified view precedent for the School Directory |
| FR77 | Epic 7 | Student profile view/edit within the Directory |
| FR78 | Epic 1, Epic 7 | Staff profile edit permissions; Directory staff records |
| FR81 | Epic 2, Epic 6, Epic 7 | Persistent navigation on every screen |
| FR82 | Epic 3 | Pagination + column sorting on lists over 20 rows |
| FR83 | Epic 2, Epic 4 | Mobile-optimised owner first-screen summary |
| NFR-P3 | Epic 5 | First AI token ≤ 3s |
| NFR-S1 | Epic 1 | Server-side RBAC is the authoritative gate |
| NFR-SSE1–4 | Epic 5 | Keepalive, reconnect, dedupe, silent-channel behaviour |
| NFR-A1, NFR-A2 | Epics 2–7 | Contrast and focus states on every new control |
| UX-DR1–4, DR9 | Epics 2–7 | Applied to all UI work (standing constraints) |
| UX-DR5, DR10 | Epic 3 | Shared sortable table; rows-per-page selector |
| UX-DR6 | Epic 4 | Shared empty-state treatment |
| UX-DR7 | Epic 2 | Mobile type scale |
| UX-DR8 | Epic 5 | Stream/step spacing scale |

## Epic List

### Epic 1: Access That Cannot Be Talked Around
Owner and Principal can trust that what a person may see and change is enforced by the
server, not merely hidden in the interface — and each person can maintain their own
details without being able to elevate themselves.
**Requirements covered:** FR2, FR3, FR4, FR5, FR78, NFR-S1
**Owner items:** 11, plus RISK-1 (the incomplete Owner-role fix)
**Standalone:** yes. Touches `middleware/auth.py`, `routes/staff.py`, `ProfileModal.js`.

### Epic 2: Usable On The Phone In Your Hand
A school owner can run the platform one-handed on a phone: nothing spills off screen,
the notification bell is reachable, and text is large enough to read.
**Requirements covered:** FR81, FR83, UX-DR7, NFR-A1, NFR-A2
**Owner items:** 1, 2, 3, 4, 8(partial), 9(keybind)
**Status:** largely SHIPPED 2026-07-22 (commits 401a4ac, later). UX-DR7 type scale outstanding.
**Standalone:** yes. `Header.js`, `Layout.js`, `Sidebar.js`, `index.css`.

### Epic 3: Finding One Record Among Two Thousand
Any user can order, page through and size any list in the platform, so a school of
1,802 students is navigable rather than merely displayed.
**Requirements covered:** FR82, UX-DR5, UX-DR10
**Owner items:** 5 (class ordering, SHIPPED), 6 (column sorting), rows-per-page
**Standalone:** yes, and it creates the shared table Epic 7 consumes.

### Epic 4: Numbers And Details That Are Actually True
Owner and Principal see real figures and the school's real identity — never a zero that
means "failed to load", never an invented address.
**Requirements covered:** FR5, FR83, UX-DR6
**Owner items:** 7 (Board Report zeroes), 8 (placeholder school data)
**Standalone:** yes. Note: correcting stored school details is a WRITE and needs
separate owner approval; the story covers the mechanism and the verified values.

### Epic 5: A Conversation That Feels Alive
Asking the assistant a question feels immediate and continuous — no stalls, no sudden
dumps, no overlapping progress boxes, and a composer that is pleasant to type in.
**Requirements covered:** FR7, FR11, NFR-P3, NFR-SSE1–4, UX-DR8
**Owner items:** 9, 10, 12, 13
**Standalone:** yes. `ChatInterface.js`, `MessageRenderer.js`, `services/sse.py`.

### Epic 6: Nothing Gets Lost
Every notification and every past conversation is reachable, reviewable and dismissable
in bulk — not just the most recent handful.
**Requirements covered:** FR81, NFR-A2
**Owner items:** 14 (View all + mark all read), 16 (All Chats page)
**Standalone:** yes. Two new pages plus `NotificationsPanel`.

### Epic 8: Ask, Don't Just Change
Added by the owner 2026-07-22, reversing the first version of Story 1.3. A member of
staff can ask for their own name, phone or email to be corrected; the Owner or the
Principal decides. Nothing changes until it is approved.
**Requirements covered:** FR3, FR78, NFR-S1
**Owner items:** the 2026-07-22 reversal of self-service editing
**Standalone:** yes. `routes/staff.py`, `ProfileModal.js`, `StaffTracker.js`.

### Epic 7: A Directory Shaped Like The School
Owner and Principal find any person in the school — student, teacher or admin — in one
place, and reach the tools they need without wading through a long list of near-duplicates.
**Requirements covered:** FR35, FR77, FR78, FR81
**Owner items:** 17 (tool consolidation; School Directory) — Owner and Principal ONLY
**Depends on:** Epic 3's shared table (builds upon it; does not require future epics).
**Note:** contains genuinely new product scope, not just defect repair. Recommended for
`bmad-party-mode` before story creation.

---

## Epic 1: Access That Cannot Be Talked Around

Owner and Principal can trust that what a person may see and change is enforced by the
server, not merely hidden in the interface — and each person can maintain their own
details without being able to elevate themselves.

**Requirements covered:** FR2, FR3, FR4, FR5, FR78, NFR-S1 · UX-DR1, UX-DR4, UX-DR9

### Story 1.1: Reject privileged role assignment at the API, not the dropdown

As the school Owner,
I want the server itself to refuse any attempt to create or promote someone to owner
through the staff endpoints,
So that removing the option from a dropdown is not the only thing standing between a
staff member and full control of the school's data.

**Acceptance Criteria:**

**Given** **any** caller with staff-management rights — **including the Owner**
**When** they POST to `/api/staff/` with `role: "owner"` or `sub_category: "owner"`,
bypassing the UI entirely
**Then** the request is rejected with 403
**And** **no `staff` document and no `auth_users` document is created** — the gate runs
before the login account is written, because `auth_users.user_info.role` is what login
reads to build the JWT and is therefore the real seat of authority (E-2)
**And** the attempt is recorded via `write_audit()` with the caller's user id
**And** a failure of the audit write does not turn the 403 into a 500 (ADR-002 fail-open)

**Given** the same caller
**When** they PATCH an existing staff member so that owner authority would **change** —
either granting it (`role`/`sub_category` → `"owner"`) or removing it from a record that
currently holds it
**Then** the request is rejected with 403, the stored values are unchanged, and the
attempt is audited
**And** the rejection is a hard error, not the silent strip used for salary — a caller
attempting escalation must never be left believing it succeeded (E-4)

**Given** an Owner editing the Owner's own staff record from the staff screen, where the
form posts every field back including `role: "owner"` (E-3)
**When** the submitted value is identical to the stored value
**Then** it is treated as a no-op and the edit succeeds — the rule is "no *change* of
owner authority through this API", evaluated against the stored record, not "the string
owner may not appear in a request body"

**Given** the platform's single existing owner account
**When** Story 1.1 ships
**Then** that account is unaffected and can still sign in and manage staff
**And** it cannot be demoted through this API either, so the school can never be left
with no owner and no way to appoint one (E-3)
**And** owner assignment remains possible only out of band, never through this API

**Given** a caller supplying `user_id` (or a name/email/phone that collides with an
existing login's username) pointing at an account that holds owner authority (E-5)
**When** the staff record is created
**Then** the link is refused — otherwise deactivating that staff record would deactivate
the owner's login and revoke their sessions, locking the owner out of the school

**Given** the AI assistant's `create_staff` tool description, which today tells the model
that `role` may be `"owner"` (E-7)
**When** Story 1.1 ships
**Then** the tool description matches what the server will actually accept

**Given** the test suite
**When** it runs
**Then** it contains an unauthenticated 401 test and a wrong-role 403 test for both the
create and update paths, per the platform's standing endpoint-test convention
**And** the denial is proven for every casing/whitespace variant of the value
(`owner`, `Owner`, `OWNER`, `" owner"`), which a normalised whitelist gives for free

*Closes RISK-1. The 2026-07-22 frontend change is a defence-in-depth layer only and was
incorrectly reported to the owner as closing this gap.*

### Story 1.2: Refuse job categories the permission system does not recognise

As the school Owner,
I want the server to reject a staff sub-category that is not one of the recognised
values,
So that a typo cannot leave a principal or accountant silently holding no permissions
at all.

**Acceptance Criteria:**

**Given** any caller with staff-management rights
**When** they submit a `sub_category` outside `VALID_SUB_CATEGORIES`
**Then** the request is rejected with 422 and an error naming the field
**And** no record is written — neither `staff` nor `auth_users`

**Given** a submitted `role` that is not one of the roles the platform recognises —
for example `role: "principal"`, which is accepted today and grants nothing (E-6)
**When** the request is processed
**Then** it is rejected with 422 naming the field

**Given** the 88 live staff records, some of which may hold values this validator would
reject (for example the legacy `"accounts"` spelling that `_is_accounts()` still honours)
**When** an authorised user edits an unrelated field on such a record
**Then** the edit succeeds — validation applies only to values being **written**, never
to values already stored, or the first phone-number correction would be unclearable

**Given** the AI assistant's `create_staff` tool description, which today names
`"accounts"` — a value `VALID_SUB_CATEGORIES` does not contain (E-7)
**When** Story 1.2 ships
**Then** the description lists only canonical values

**Given** a submitted `sub_category` that is valid in itself but does not belong to the
submitted `role` — for example `class_teacher` paired with `role: "admin"`
**When** the request is processed
**Then** it is rejected, because such a record would match no permission rule and grant
nothing

**Given** the 88 existing staff records
**When** this validation ships
**Then** none of them is modified, and any record already holding a non-canonical value
is reported rather than auto-corrected — correcting live data requires separate approval

### Story 1.3: Let people maintain their own details, but not their own authority

As any signed-in member of school staff,
I want to correct my own name, phone number and email from my profile,
So that my contact details stay current without an administrator having to do it for me.

**Acceptance Criteria:**

> ### ⚠️ REVERSED BY THE OWNER, 2026-07-22
> The first version of this story let a person edit their own name, phone and email
> directly. Abhimanyu reversed it: *"no one changes their name, phone, email to misuse
> the power — only after admin approval should be able to do that."*
> **Story 1.3 is now: your own details are visible but nobody edits their own record.**
> The ask-and-approve flow is **Epic 8**, below. The self-service write path built in the
> first pass was removed, not merely hidden — see `epic-1-review.md`.

**Scope decision:** changing anyone's details — including your own — happens on the
staff screen, done by the Owner or Principal. There is exactly one place in the platform
where a person's record changes.

**Given** any authenticated user viewing their own profile
**When** they open it
**Then** their name, phone, email, role, job and school are shown, and **none** of them
is editable
**And** the screen says plainly who to ask for a correction

**Given** any authenticated user, **including the Owner**
**When** they submit a change to their own record by any means including a direct API
call — contact details or authority fields, alone or mixed, or an empty body
**Then** it is refused with 403 and nothing is written, to either the staff record or
the login record
**And** the refusal names who can make the change instead, so a teacher whose number
really has changed is not left at a dead end

**Given** a signed-in user who has no staff record
**When** they attempt a profile change
**Then** they are refused — and no record is created for them

**Given** the set of self-editable fields
**When** the test suite runs
**Then** it asserts the set is **empty**, so a field cannot be quietly added back and
silently restore direct self-editing

**Given** the profile dialog, which today prints a hard-coded
"The Aaryans, Lucknow, CBSE" — the wrong city for a school in Joya, Amroha (D-11)
**When** it is rendered
**Then** the school line is not a hard-coded string

**Given** the profile dialog
**When** it is rendered
**Then** every control carries a `data-testid`, uses CSS variables rather than raw hex,
and has a visible focus state at ≥3:1 contrast (UX-DR1, UX-DR4, UX-DR9)

---

## Epic 8: Ask, Don't Just Change

Added by the owner 2026-07-22 alongside the reversal of Story 1.3. A member of staff can
**ask** for their own contact details to be corrected; the Owner or the Principal
**decides**; nothing changes until it is approved.

**Requirements covered:** FR3, FR78, NFR-S1

### Story 8.1: A member of staff can ask for a correction

As a teacher or a member of the admin staff,
I want to ask for my name, phone number or email to be corrected,
So that my details can be put right without me being able to change them myself.

**Acceptance Criteria:**

**Given** any signed-in member of staff with a staff record
**When** they submit a requested correction to their name, phone or email
**Then** a pending request is recorded, **their own record is unchanged**, and the Owner
and the Principal are notified

**Given** the same person
**When** they include any field beyond name, phone and email — role, sub-category,
school, salary, token allowance
**Then** the whole request is refused, exactly as Story 1.3 refuses a direct edit; the
request route must not become a side door around the rule it exists to serve

**Given** a person who already has a request waiting
**When** they submit another
**Then** it is refused with a message saying one is already pending, so the queue cannot
be flooded and a reviewer never has to guess which of several is current

**Given** a requested value identical to what is already stored
**When** it is submitted
**Then** it is refused — an approval queue should not fill with changes that change nothing

**Given** a person with no staff record
**When** they submit a request
**Then** they are refused, and no record is created for them

### Story 8.2: The Owner or Principal decides

As the Owner or the Principal,
I want to see what corrections people have asked for and approve or reject each one,
So that details stay accurate without anyone being able to edit themselves.

**Acceptance Criteria:**

**Given** an Owner or a Principal
**When** they list pending requests
**Then** they see who asked, what they want changed, the current value beside the
requested one, and when it was asked

**Given** anyone else — a teacher, an accountant, any other admin sub-category
**When** they try to list or decide requests
**Then** they are refused with 403

**Given** a pending request
**When** the Owner or Principal approves it
**Then** the change is applied to the staff record **and** to the login record, so it
survives signing out and back in
**And** the request is marked approved with who decided and when
**And** the requester is notified
**And** it cannot be approved twice — a second decision on a settled request is refused

**Given** a pending request
**When** it is rejected
**Then** nothing is changed, the requester is notified, and a reason may be recorded

**Given** a Principal who has raised a request of their own
**When** they try to approve it themselves
**Then** they are refused. Otherwise the Principal is an administrator who can approve
their own change, which is exactly the self-editing this feature exists to prevent.
Their request is decided by the Owner.

**Given** an approval whose target staff record has since been deactivated or deleted
**When** the decision is made
**Then** it fails cleanly rather than writing to a record that is no longer there

**Given** any decision
**When** it is made
**Then** an audit entry records who decided what, on whose behalf

### Story 8.3: Both sides of it are visible in the app

**Acceptance Criteria:**

**Given** a member of staff who has asked for a correction
**When** they open their profile
**Then** they see what they asked for and that it is waiting, and they cannot ask again
until it is settled

**Given** an Owner or Principal with requests waiting
**When** they open the staff screen
**Then** the pending requests are shown there, alongside the pending leave requests they
already review, with approve and reject on each

**Given** any of these controls
**When** rendered
**Then** each carries a `data-testid`, uses CSS variables rather than raw hex, and has a
visible focus state (UX-DR1, UX-DR4, UX-DR9)

---

## Epic 9: Looks Like The Brochure

Added by Abhimanyu 2026-07-22. The marketing site (`eduflow.layaa.ai`) is warm, rounded
and playful; the product it sells is flat grey. A parent or a teacher who arrives from
the website should recognise that they are in the same place.

This is the **design foundation** epic. It changes the shared vocabulary — colour,
type, shape, motion — and the shared shell. It deliberately does **not** hand-restyle
the 25 individual tool screens: those consume the same tokens and follow automatically,
then get polished screen-by-screen in Epics 4–7.

**Requirements covered:** UX-DR1, UX-DR2, UX-DR3 (superseded — see 9.1), UX-DR4,
UX-DR7, UX-DR9, NFR-A1, NFR-A2
**Owner decisions, 2026-07-22:** navy dark theme **and** a light theme; "playful but
calm" — no mascot on daily working screens.
**Absorbs:** Epic 2's outstanding UX-DR7 mobile type scale, and D-05.

### The measured source

The design language was read off the running marketing site, not invented:
Baloo 2 (display) + Nunito (body); navy `#0D1323` / `#16203A`; brand blue `#2B8FF0`;
orange `#F2811D`; mint `#34D399`; violet `#A78BFA`; yellow `#FFC93C`; solid offset
shadows (`0 5px 0 0`); radii 999px / 28 / 24 / 18 / 14 / 12px.

> **⚠️ The brochure's button colours fail WCAG and must not be copied literally.**
> Measured: white on `#F2811D` = **2.65:1**; white on `#2B8FF0` = **3.34:1**. NFR-A1
> requires 4.5:1 for body text. The website carries one huge headline CTA and gets
> away with it; the app puts 14px labels on hundreds of buttons and does not.
> Resolution, preserving the look: orange fills take **navy `#16203A` text (6.09:1)**,
> which reads as *more* toy-like, not less; the blue fill deepens to `#1A6FCE` for
> white text (**4.99:1**); `#2B8FF0` stays as the accent, link and glow colour on navy
> (**5.34:1**), where it is genuinely accessible.

### Story 9.1: One place that decides what the platform looks like

As a developer working on any later epic,
I want a single token file that defines colour, type, shape, elevation and motion for
both themes,
So that a screen restyled in Epic 5 cannot drift from one restyled in Epic 4.

**Acceptance Criteria:**

**Given** the existing token architecture — semantic `--color-*` names, legacy
`--bg-*`/`--c-*` aliases, and 781 uses of generated `--tool-hex-*` aliases across 19
files
**When** the new design language ships
**Then** it ships by **changing the values of the existing tokens**, not by introducing
a second parallel system — the `--tool-hex-*` aliases are remapped to the navy family so
the 25 tool screens follow automatically without being edited

**Given** an alias such as `--tool-hex-fff` that is used both as button *text* and as a
*background* (already noted in `App.css`)
**When** the remap is written
**Then** ambiguous aliases are left alone rather than guessed at — a remap that flips one
usage correctly and the other invisibly is worse than no remap

**Given** both themes
**When** any token pair is used for body text
**Then** it measures ≥4.5:1, and ≥3:1 for borders, icons and large text — **verified by a
committed test that computes the ratios**, not by eye. Light theme is checked
independently of dark (UX-DR2).

**Given** the `--tool-hex-*` aliases, which today are defined for dark in `index.css` and
only **partially** overridden for light in `App.css`
**When** the audit runs
**Then** any alias whose dark value is a dark surface and which has **no** light override
is reported, because in light theme it currently renders a dark block on a white page —
a pre-existing defect the retheme must not inherit

**Given** UX-DR3, which pinned the fonts to Inter and JetBrains Mono
**When** this story ships
**Then** UX-DR3 is **superseded and recorded as such** — Baloo 2 (display) and Nunito
(body) replace Inter; JetBrains Mono is retained for code and tabular figures. A
requirement is not silently broken; it is explicitly retired with the reason.

**Given** the font change alters text metrics across an inline-styled codebase
**When** it ships
**Then** the base size and line-height are held constant so the change is colour-and-shape,
not a reflow, and fonts load with `font-display: swap` against a matched fallback stack

### Story 9.2: Controls that feel good to press

As anyone using the platform,
I want buttons, cards, inputs and status pills that look friendly and respond when I
touch them,
So that the software feels like it was made for a school rather than for a bank.

**Acceptance Criteria:**

**Given** a primary, secondary, ghost or destructive button
**When** it is rendered
**Then** it uses the chunky solid-offset shadow of the brand, a pill or large radius, and
its label meets 4.5:1 against its own fill (per the palette resolution above)

**Given** a button being pressed
**When** the press happens
**Then** it depresses into its shadow using **`transform` only** — never `top`, `margin`
or `height` — so pressing a button never reflows the row it sits in (this is exactly the
class of fault that produced D-01)

**Given** a user who has asked their system for reduced motion
**When** any transition, hover lift or entrance animation would play
**Then** it is reduced to a near-instant state change — the platform has **no**
`prefers-reduced-motion` support today, and adding playful motion without it would make
the product actively worse for the people who need that setting

**Given** any control
**When** it is focused by keyboard
**Then** it shows a visible ring of ≥2px at ≥3:1 against the adjacent background, in
**both** themes (NFR-A2, UX-DR9), and the ring is never removed by a hover or active rule

**Given** a disabled control
**When** it is rendered
**Then** it is distinguishable by more than colour alone and carries the real `disabled`
attribute, not just a faded style

**Given** every primitive
**When** it is rendered
**Then** it accepts and forwards a `data-testid` (UX-DR4) and uses CSS variables only,
never raw hex (UX-DR1)

### Story 9.3: The shell, and text you can actually read on a phone

As the school Owner working one-handed on a phone,
I want the sidebar, header and chat to carry the new look, and text large enough to read,
So that the platform is pleasant rather than merely functional at 390px.

**Acceptance Criteria:**

**Given** the mobile type scale, deferred from Epic 2 as UX-DR7 and explicitly parked in
`index.css` for "the design pass"
**When** it ships
**Then** controls **and their labels are raised together**, so the failure the owner
flagged on 2026-07-22 — 16px dropdowns beside 12px labels — cannot recur. It is a type
*scale*, not a blanket `!important` on form controls.

**Given** the reverted `pointer: coarse` rule that also fired in Chrome's device
simulator (D-01)
**When** the new scale is written
**Then** it keys off **viewport width**, not input modality, so a desktop browser
simulating a phone gets the same result as a phone

**Given** a focused input on iOS at the new scale
**When** it receives focus
**Then** its computed size is ≥16px so Safari does not zoom the page — achieved *by* the
scale rather than by overriding it

**Given** the sidebar, header, mobile drawer and chat surfaces
**When** they render
**Then** they use the new tokens, and every behaviour Epic 2 shipped — the drawer, the
overlay, the close button, the notification dot, class ordering — still works unchanged

**Given** `project-context.md`, which tells every future agent the sidebar is "120px
fixed" (D-05)
**When** this story ships
**Then** it states the real width, because it is loaded as authoritative context by every
BMAD workflow and is currently misinforming them

**Given** the login screen, empty states and error states
**When** they render
**Then** they may carry the brand's warmth (mascot, friendly copy); **daily working
screens may not** — the owner's decision was "playful but calm", because a teacher
marking 40 attendance rows every morning needs calm

---

## Epic 3: Finding One Record Among Two Thousand

Any user can order, page through and size any list in the platform, so a school of
1,802 students is navigable rather than merely displayed.

**Requirements covered:** FR82, UX-DR5, UX-DR10 · UX-DR1, UX-DR4, UX-DR9, NFR-A2
**Owner items:** 5 (class ordering — SHIPPED), 6 (column sorting), rows-per-page
**Builds on:** Epic 9's primitives. **Consumed by:** Epic 7's School Directory.

### Story 3.1: A table that sorts, once, for the whole platform

As anyone looking at a list of people or records,
I want to click a column heading to order by it,
So that finding one record among two thousand is a decision rather than a scroll.

**Acceptance Criteria:**

**Given** FR82, which requires at minimum one column-level sort on any list that may
exceed 20 rows, and UX-DR5, which requires this be solved **once**
**When** the story ships
**Then** there is a single shared table component, and the lists that adopt it are listed
explicitly in the completion log — including which lists were **not** converted and why,
so partial coverage is never reported as complete

**Given** a sortable column heading
**When** it is rendered
**Then** it is a real `<button>` inside the `<th>`, reachable by keyboard, and the `<th>`
carries `aria-sort` of `ascending`/`descending`/`none` so a screen-reader user knows the
current order (WCAG `sortable-table`)

**Given** a table of 1,802 students
**When** the user sorts by a column
**Then** **the server performs the sort across the whole result set** and returns page 1
— sorting only the 20 rows already on screen would be a lie, and is the single most
likely wrong implementation of this story

**Given** a sort field the server does not recognise
**When** it is requested
**Then** the server falls back to its default order rather than interpolating the value
into a query, and the whitelist of sortable fields is server-side

**Given** a column whose value is missing for every record — `dob`, `gender`, `house` and
`admission_date` are empty for all 1,802 students
**When** it is sorted
**Then** the empty state says **"not recorded"** rather than showing blanks or a zero
(UX-DR6 precedent, and §12 of the source-of-truth document)

**Given** the table on a phone
**When** it renders
**Then** it stays a single element that scrolls inside its wrapper — the `display:block`
split that broke heading alignment on 2026-07-22 (D-01) must not return, and a test
asserts the wrapper scrolls rather than the table being re-laid-out

**Given** the shared table
**When** rendered
**Then** every interactive element carries a `data-testid`, uses CSS variables, and has a
visible focus state (UX-DR1, UX-DR4, UX-DR9)

### Story 3.2: Choosing how much you want to see

As the school Owner,
I want to choose how many rows a list shows me,
So that I can scan quickly on a laptop and read comfortably on a phone.

**Acceptance Criteria:**

**Given** UX-DR10, specified by the owner on 2026-07-22
**When** the selector renders
**Then** it offers **5 / 10 / 15 / 20 / 25 / 30**, defaults to **15**, sits beside the
pagination control, and shows the active value

**Given** a 1,802-row table
**When** a page size is chosen
**Then** **the size is sent to the API and the server paginates** — a client-side slice of
an already-fetched large payload defeats the entire purpose and is explicitly forbidden
by UX-DR10

**Given** a user on page 40 of a 20-row listing
**When** they change the size to 30
**Then** they are returned to **page 1** rather than stranded on a page that no longer
exists

**Given** a user who has chosen a size
**When** they sign out and return
**Then** their choice is remembered, **keyed per table** — one preference for the whole
app would mean sizing the student list resizes the audit log

**Given** a stored preference that is corrupt, absent, or a value no longer offered
(a `localStorage` string, an old build's `50`, or a hand-edited `"abc"`)
**When** it is read
**Then** it falls back to 15 without throwing — reading `localStorage` is parsing
untrusted input, and a crash here would white-screen the whole list

**Given** the server, which today caps `limit` at 500
**When** a caller requests a size outside the offered set
**Then** the server still clamps to its own bounds — the client's option list is a
convenience, never the enforcement

**Given** the selector
**When** rendered
**Then** it is a labelled control (not placeholder-only), carries a `data-testid`, and has
a visible focus state

### Story 3.3: The lists people actually use

As anyone using the platform,
I want ordering and sizing to work on the lists I open every day, not just in principle,
So that the capability is real rather than architectural.

**Acceptance Criteria:**

**Given** the backend sort whitelists — `students` allows only `created_at`, `name`,
`class`; `staff` allows `name`, `staff_type`, `department`, `created_at`
**When** this story ships
**Then** the whitelists cover the columns the shared table actually offers, and any column
the table presents as sortable is one the server can sort — a heading that sorts nothing
is worse than a heading that does not offer to

**Given** the student list, which sorts by `class_id`
**When** it is ordered by class
**Then** it uses the school's real class order — **NUR → LKG → UKG → 1st … 12th**, then
section A→E — not the raw stored order (`11th-A, 1st-A, 2nd-C…`), which is owner item 5
and already solved for dropdowns in `lib/classOrder.js`

**Given** every list converted to the shared table
**When** the story closes
**Then** each has a 401-unauthenticated and 403-wrong-role test for any endpoint whose
signature changed, per the platform's standing convention

**Given** the staff list
**When** it renders
**Then** it shows `designation` — the readable label already populated for all 89 records
— rather than `role / sub_category`, which is the exact column the owner objected to
(§11 of the source-of-truth document). *(Small, safe, adjacent; logged under rule 6.)*
