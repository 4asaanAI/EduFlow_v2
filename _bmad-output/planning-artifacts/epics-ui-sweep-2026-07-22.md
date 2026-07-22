---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories:epic-1', 'step-03-create-stories:epic-8', 'step-03-create-stories:epic-9', 'step-03-create-stories:epic-3', 'step-03-create-stories:epic-4']
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
| FR5 | Epic 1, Epic 4 | Role data scoping (Story 4.5 — the tool-panel endpoint passed no scope, so branch data crossed branches). **The Board Report zeroes are NOT a scoping fault** — that hypothesis, recorded here on 2026-07-22, was disproved by Epic 4's root-cause analysis; the cause was a double result envelope. Both are real and both are fixed in Epic 4. |
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

### Epic 10: Something You Can Actually Hand Someone
Added by the owner 2026-07-22 and **pulled forward ahead of Epic 5** at his instruction.
When Flo drafts a circular, a fee sheet or a notice, the school gets a **file they can
send, print or sign** — not text to copy out of a chat window.
**Requirements covered:** FR7, NFR-S1, NFR-S2, UX-DR4, UX-DR9
**Owner items:** the 2026-07-22 screenshot in which Flo told the owner it could produce
the *content* of a Word, Excel, PowerPoint or PDF file but not the file itself; plus the
same day's instruction to read printed paper on the school's own server for nothing,
falling back to the paid service only when a photo must genuinely be understood.
**Explicitly excluded by the owner:** image and video **generation**.
**Standalone:** yes. 6 stories — documents out (10.1–10.4), paper in (10.5–10.6).

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

---

## Epic 4: Numbers And Details That Are Actually True

Owner and Principal see real figures and the school's real identity — never a zero that
means "failed to load", never an invented address.

**Requirements covered:** FR5, FR83, UX-DR6 · UX-DR1, UX-DR4, UX-DR9, NFR-A1, NFR-A2
**Owner items:** 7 (Board Report zeroes), 8 (placeholder school data)
**Closes:** D-21 (the school's remaining placeholder details)
**Builds on:** Epic 9's `EmptyState` primitive, which was written for exactly this epic.

### Root cause established before story creation — read this first

The owner reported item 7 as "the Board Report shows zeros". It is not a Board Report
defect. Commit `8789fea` (Epic R4 of the shipped AI-reliability initiative) introduced
`_env()` in `backend/ai/tool_functions.py` so that every tool returns **one** envelope —
`{success, data, meta, message, denied}`. `backend/routes/tools.py`, which is the
non-chat tool-panel path, has not been touched since Part 1.5 and still does
`return {"success": True, "data": result}` — wrapping the envelope in a second envelope.

Every screen that reads a tool therefore reads one level too shallow, and every
`|| 0` / `|| 'N/A'` fallback in those screens fires. That is **eleven** surfaces, not
one: Board Report, School Pulse, Fee Collection, Attendance Overview, Staff Tracker,
Admission Funnel, Smart Alerts, Financial Reports, AI Health Report, the health score in
the chat greeting, and a student's own My Attendance and My Results.

This is the epic's PRIME DIRECTIVE case: the fix is one envelope at the source, not
eleven unwrappers, and not a nicer message over a wrong number.

**Why nothing caught it for a whole initiative.** The end-to-end test double,
`tests/support/e2e_backend.py:86`, answers this endpoint with a **single** envelope —
the correct contract. Every browser test therefore passed against a fake server that
did not behave like the real one. A test double that disagrees with production tests
nothing. Correcting the double is part of Story 4.1, and it must be corrected in the
direction of the *fixed* server, never bent back to match the bug.

### Sequencing constraint — 4.1 and 4.2 land together (party-mode finding, John)

**Story 4.1 must not reach the Owner without Story 4.2.** The school has **one** fee
transaction for 1,802 students, and no attendance marked for today. The instant the
envelope is fixed, the real figures flow — and the real figure for fee collection is
₹0. An unlabelled ₹0 is indistinguishable from the broken ₹0 this epic exists to
remove. Shipping 4.1 alone would move the defect rather than fix it, and would be
reported back as defect #19. Neither story is "done" alone.

There are currently **no tests of any kind** for `backend/routes/tools.py` — the file at
the centre of this epic. That is the second reason this survived.

### Epic-wide rule (from the D-15b lesson, restated as a condition of "done")

No part of this epic may be reported as done on the strength of a passing test. A
change that reaches the Owner's screen only after a deploy or a data edit is reported
as **"not yet visible to you"**. Every figure claimed to be fixed is named, with what
it now shows.

### Story 4.1: One envelope, so every tool screen shows the real number

As the school Owner or Principal,
I want the figures on every tool screen to be the figures in my school,
So that I can act on them instead of wondering whether the screen is broken.

**Acceptance Criteria:**

**Given** `_env()` is the platform's single tool-result envelope (R4.2/M1) and
`POST /api/tools/{tool_id}/execute` currently wraps it in a second one
**When** this story ships
**Then** the endpoint returns the tool's own envelope **unchanged** — one `success`, one
`data`, one `meta`, `message` and `denied` — so `data` is the tool's payload and never
another envelope

**Given** any tool in `TOOL_REGISTRY`
**When** it is executed through the tool-panel endpoint
**Then** a test asserts, over the registry rather than over a hand-picked tool, that the
response's `data` is **not itself an envelope** — this is the regression that must fail
before the fix and pass after, and it is what stops a third envelope being added in 2027

**Given** a tool that refuses the request (`denied=True`)
**When** the screen renders the result
**Then** the refusal is shown as a refusal and never as an empty or zero result — R4's
"denied ≠ empty" principle applies to the tool panels exactly as it does to chat

**Given** the eleven screens listed in the root-cause note above
**When** the story closes
**Then** **every one of them has been opened and read**, and the completion log names each
screen and what it now shows — a fix verified only on the Board Report would repeat the
Epic 9 fault where a shared-component defect was fixed on the one screen that was reported

**Given** a caller whose role is not in a tool's allowlist
**When** they call the endpoint
**Then** it still returns 403 with `detail="Forbidden"`, and both the 401-unauthenticated
and 403-wrong-role tests exist for the endpoint per the standing convention

**Given** the endpoint's response shape changes
**When** the backend suite runs
**Then** any existing test that encoded the double envelope is **rewritten to assert the
correct contract, never deleted** — the D-14 rule

**Given** `_env()` and the chat tool-loop both depend on the envelope as it is
**When** this story is implemented
**Then** the change is confined to `backend/routes/tools.py`. `ai/tool_functions.py`,
`ai/tool_functions_v2.py` and the chat dispatch path are **not** touched — moving the
envelope instead of removing the second wrapper would repair eleven screens by breaking
the assistant *(elicitation: failure-mode analysis)*

**Given** the 22 `executeTool` call sites, three of which read the result differently
from the rest — `r.data?.data ?? r.data` in the WhatsApp reminder modal,
`r.data?.summary` in the chat greeting, and the `useToolData` wrapper
**When** the envelope changes
**Then** each of the 22 is examined individually and its before/after access path
recorded in the completion log. A defensive `?? ` fallback that happens to keep working
is not evidence it is correct *(elicitation: pre-mortem)*

**Given** `tests/support/e2e_backend.py`, the browser-test double, which already returns
the single correct envelope and so hid this defect for an entire initiative
**When** the server is fixed
**Then** the double is confirmed to match the real server's shape, and a note in that
file records that its job is to mirror production — not to model what production ought
to do *(elicitation: 5 whys → root cause of the miss)*

**Given** that a unit test which mocks the tool and asserts "the endpoint passed it
through" would pass trivially and prove nothing about the eleven screens
**When** the regression test is written
**Then** it exercises the **real route** with a **real registry tool** and asserts the
response body **equals that tool's own `_env()` output** — no second `data` key, no
re-shaping. A pass-through assertion against a mock is explicitly not sufficient
*(party mode: Murat)*

**Given** frontend tests for the tool panels
**When** their fixtures are written
**Then** the fixture is the shape the **fixed server actually returns**, and the test
asserts the **rendered number** a person would read — not that a promise resolved. A
fixture hand-shaped to match whatever the component currently expects is the same
disease as the browser-test double, in a new place *(party mode: Murat)*

### Story 4.2: A zero means zero, and a failure says so

As the school Owner presenting figures to a trust meeting,
I want a number I cannot load to look different from a number that is genuinely nought,
So that I never read a broken request out loud as though it were a fact about my school.

**Acceptance Criteria:**

**Given** UX-DR6, which requires the shared empty state to distinguish "no data yet" from
"not recorded" from "failed to load", and `EmptyState` in
`frontend/src/components/ui/primitives.js`, which already implements all three
**When** a Board Report section cannot be loaded
**Then** that section renders the `error` state and offers a retry — it does not render
`0`, `₹0`, `N/A`, or an empty table

**Given** the Board Report currently loads six sources under one `Promise.all`, catches
everything into a single banner reading "Some data could not be loaded. Showing partial
report.", and then shows **no report at all** because `data` was never set
**When** the story ships
**Then** each source succeeds or fails **independently**, the sections that loaded are
shown, and the banner names which sections are missing rather than making an unkeepable
promise

**Given** the staff and expenses calls, which today do
`.catch(() => ({ data: [] }))` — turning any failure, including a 403, into "0 staff"
**When** either fails
**Then** the failure is surfaced in that section's state; silently substituting an empty
list for an error is forbidden, and a test proves a failing call does not render `0`

**Given** the exported PDF
**When** a section failed to load
**Then** the PDF prints "not available" for that section rather than a fabricated `0` or
`₹0` — a number in a downloadable board document is the most dangerous place for this
defect, because it outlives the screen

**Given** a metric whose underlying field was never captured — date of birth, gender,
house and admission date are empty for all 1,802 students
**When** it is displayed
**Then** it says **"not recorded"**, consistent with Epic 9's decision and §12 of the
source-of-truth document

**Given** `StatCard`, which is used across many tool screens
**When** it is given a value that is unavailable rather than zero
**Then** it can express that, and every screen already consuming `StatCard` is checked —
the shared-component rule from the Epic 3/9 retrospective

**Given** a figure that is **genuinely nought** — fee collection is ₹0 because the school
has one fee transaction on file for 1,802 students, and that is the truth
**When** it is shown
**Then** the card carries a short honest footnote on the card itself — "as recorded",
"1 transaction on file" — so a real zero and an unavailable one are told apart **at a
glance, on a phone, without hovering anything**. A bare number with no signal of whether
it is real is the same lie this epic exists to remove, merely relabelled
*(party mode: Sally, John)*

**Given** attendance, where `tool_get_school_pulse` computes
`att_rate = 0 if total_marked == 0` and `tool_get_attendance_overview` computes
`avg_rate = 0 if not daily_list`
**When** nobody has marked attendance yet
**Then** the answer is **"not marked yet"**, never **"0%"**. A principal opening the
report on a Monday morning and reading 0% attendance has been told the school is empty.
This AC deliberately changes `ai/tool_functions.py`, which the assistant shares — the
assistant is telling people the same falsehood, and both surfaces are fixed by fixing
the number once *(party mode: John)*

**Given** a section the Owner has retried once and which fails again
**When** the second failure renders
**Then** it says something **different** from the first — acknowledging the retry and
naming the likely cause — so he can tell "it tried again and failed" from "my tap did
nothing" *(party mode: Sally)*

**Given** the PDF export and a report in which one section failed
**When** he exports it
**Then** **the export still works**, containing every section that loaded and
"not available" for the one that did not. An export that refuses because one of six
promises rejected leaves him in front of the trustees with no document at all
*(party mode: Sally)*

**Given** every new or changed control in this story
**When** rendered
**Then** it uses CSS variables only, carries a `data-testid`, has a visible focus state,
and the error state is announced to assistive technology (`role="alert"`)

### Story 4.3: The school's own identity, stored once and complete

As the school Owner,
I want the platform to hold my school's real name, address, contacts and affiliation,
So that nothing it shows a parent, prints on a document, or tells the assistant is invented.

**Acceptance Criteria:**

**Given** the school's official details, confirmed by Abhimanyu on 2026-07-22 as coming
from the school's own website `theaaryans.in`
**When** the values are recorded anywhere in this repository
**Then** they are exactly:
`address` "Prem Nagar, P.O. Joya, N.H. 24, Distt. Amroha, Uttar Pradesh 244222" ·
`phone` "+91 81269 65555, +91 81269 68888" · `email` "theaaryansjoya@gmail.com" ·
`website` "www.theaaryans.in" · `board` "CBSE" · `affiliation_no` "2133014" ·
`school_code` "81936" · `established` "2015" · `principal` "Adesh Singh" ·
`city` "Joya, Amroha" · `state` "Uttar Pradesh"

**Given** there is today no field anywhere for a CBSE affiliation number, though it
belongs on every official document a school issues
**When** this story ships
**Then** `affiliation_no` and `school_code` exist on the school record, are editable by
the Owner on the School Settings screen, are readable by every role that can already read
the school profile, and are added to the server-side whitelist of settable fields — a
field the form posts but the whitelist drops would silently discard the Owner's edit

**Given** `AdminTools.js`, which prints its own hard-coded
`'Affiliated to CBSE · Joya, Amroha, Uttar Pradesh'`
**When** the story ships
**Then** it reads the stored record instead, and a grep proves no screen still carries a
hard-coded school identity string — this is the D-15 fault, where the same wrong city was
written into five separate files

**Given** a school record in which a field is **absent**
**When** the settings endpoint answers
**Then** the verified official value is used for that field, so a missing `website` or
`affiliation_no` shows the truth without any database write — the same mechanism that let
D-15's city correction reach the code without touching data

**Given** a field the Owner has deliberately **cleared** — stored as an empty string
**When** the settings endpoint answers
**Then** it stays cleared. The fallback fills absent keys only; a helpful default that
reinstates a value someone chose to delete is a defect wearing a good intention, and it
would be impossible for him to diagnose *(elicitation: pre-mortem)*

**Given** a field that is present in the record but **wrong** — `address`, `phone`,
`email` and `principal` are all placeholder values today (D-21)
**When** this story ships
**Then** it does **not** overwrite them. Correcting stored data is a write against 1,802
students' live database and needs the Owner's separate approval. The story delivers the
audited in-app path (School Settings → Save, which writes through
`update_school_settings()` and is recorded in the audit log as the Owner's action) and the
exact values above, and the epic reports these fields as **"not yet visible to you"** —
never as done — until he saves them. This is the D-15b lesson, stated as an acceptance
criterion so it cannot be forgotten.

**Given** the School Settings form, whose Phone field still suggests the placeholder
`0522-4567890`
**When** it renders
**Then** its suggested values are the school's real ones, so nobody types a Lucknow
landline back in

### Story 4.4: The assistant is briefed from the school's record, not a constant

As anyone asking the assistant about the school,
I want it to answer from what the school has actually recorded,
So that it stops being confidently wrong about the school it works for.

**Acceptance Criteria:**

**Given** `build_system_prompt()` opens with "…assistant for {SCHOOL_NAME} ({SCHOOL_BOARD}
board, {SCHOOL_CITY})" read from module-level environment constants, not from the school
record
**When** this story ships
**Then** the briefing is built from the stored school settings, falling back to the
verified defaults only when a field is absent — so correcting the record corrects the
assistant, which is precisely what did not happen with "Lucknow"

**Given** `build_system_prompt()` reads `school_settings.get("principal_name")` while the
record stores the field as `principal`, and `owner_name` is not in the settable whitelist
at all
**When** the mismatch is fixed
**Then** the assistant knows the principal is **Adesh Singh**, and a test asserts the
briefing contains the stored principal — this is the same prompt↔data drift class that
epic R3 was built to prevent, and D-13 caught once already

**Given** the `ai_context.fee_structure` field, which already exists on the school record
and is empty
**When** the Owner records the 2026-27 fee structure summary there
**Then** the assistant is briefed with it and can answer a fee question from the school's
own table rather than from nothing. The story provides the field, the briefing wiring and
the summary text drawn from §5 of the source-of-truth document; **entering it is a write
and follows the same approval rule as Story 4.3.** It summarises the published fee table
only — it is not the fee-record data load, which stays out of scope in Track 2

**Given** the standing directive that any change to `ai/prompts.py` requires a green
golden-eval run before merge (execution protocol, portability guarantee §5)
**When** this story closes
**Then** the always-on structural and judge-logic evals are green, and the epic-close log
records whether the credentialed LLM-judge tier was runnable on this machine — if it was
not, that is stated plainly rather than implied

**Given** the assistant's organisation briefing, which hard-codes
"School Organisation — The Aaryans (CBSE, Joya, Amroha, U.P.)"
**When** the story ships
**Then** that line too comes from the record, so there is exactly one place the school's
identity is decided

**Given** `context_builder.build_school_context()` already reads the school record once
per turn, projecting only `principal`, `owner_name` and `school_name`
**When** the briefing needs the other identity fields
**Then** that existing projection is widened — **no second query is added**. A per-turn
database round trip for data that is already in hand would cost every user of the
assistant, permanently, to save one line of code *(elicitation: failure-mode analysis)*

**Given** the school's phone number and email address now enter the assistant's briefing
**When** a future privacy review reads this
**Then** it is recorded here that these are the *organisation's* own published contact
details, taken from its public website, not personal data — the DPDP redaction rule
(`ai/redaction.py`) is deliberately surgical and must not be widened to strip them, which
would leave the assistant unable to tell a parent how to contact the school
*(elicitation: red team on the privacy surface)*

### Story 4.5: The screen tools play by the same rules as the assistant

As the school Owner,
I want the tool screens to obey exactly the permissions the assistant obeys,
So that a figure someone can see is one they are entitled to see, and the branch a
number belongs to is the branch it is reported for.

**Added during Epic 4's readiness review, not from the owner's defect list. Approved
by Abhimanyu on 2026-07-22 before any code was written, per the D-18 rule that anything
changing what a person is ALLOWED to do is asked about first, never reviewed into
existence afterwards.**

`POST /api/tools/{tool_id}/execute` predates the assistant's safety machinery (its last
change was Part 1.5) and was never brought in line with it. Three gaps, all in the same
nine lines Story 4.1 rewrites.

**Acceptance Criteria:**

**Given** the endpoint gates on `user["role"] not in tool_def["roles"]` alone, while the
assistant uses `_is_tool_authorized(user, tool_def)` — which additionally honours the 49
registry entries carrying `sub_categories`, and the Phase-1 action lockdown
**When** this story ships
**Then** the endpoint uses **the same single gate function**, so a job category that
cannot ask the assistant for something cannot get it from a screen either; a test proves
an admin whose `sub_category` is outside a tool's list is refused

**Given** the endpoint can today invoke **any** tool in the registry, including the ones
marked `dispatch_type: "write"` / `requires_confirmation: True`, with no confirm token, no
AI-write kill-switch, no lockdown and no audit row — every protection F.4, F.10 and F.11
were built to guarantee
**When** a write tool is requested through this endpoint
**Then** it is refused. This path serves **reads only**; writes go through the chat
confirm flow that already confirms and audits them. No screen in the application calls a
write tool through this endpoint today — a grep of all 22 `executeTool` call sites shows
every one is a `get_*` read — so nothing the school uses changes

**Given** tools take `(params, user, scope)` and the endpoint calls `fn(params, user)`
with **no scope**, so `_tenant_query(None, …)` emits no `branch_id` clause
**When** a branch-bound admin or principal opens a tool screen
**Then** they see their own branch's figures only. `await resolve_scope(user)` is called
before invocation, exactly as the chat path does — this is the FR5 scoping fault the
original defect list suspected behind item 7, and it is real, though it is not what made
the Board Report show zeros

**Given** the refusals above
**When** they are returned
**Then** they use `detail="Forbidden"` with no role or sub-category leak (403 hygiene),
and the endpoint keeps its 401-unauthenticated and 403-wrong-role tests

**Given** the 14 original v1 tools carry no `dispatch_type` key at all, so a rule of
"refuse anything not marked read" would refuse every tool panel, while a rule of "refuse
only what is marked write" lets a future tool added without the key through unnoticed
**When** the read-only rule is written
**Then** refusal is by `dispatch_type == "write"`, `requires_confirmation`, or membership
of the write-tool sets — **and** a drift test holds a frozen inventory of every tool
lacking `dispatch_type`, so a newly added tool that omits it fails the test rather than
silently becoming callable. This is the F.6 parity-gate pattern applied to a second
door *(elicitation: failure-mode analysis)*

**Given** branch scoping that is correct in an isolated unit test can still leak on the
composed path, because each tool builds its own query
**When** the tests are written
**Then** branch isolation is asserted **per allowed read tool through the endpoint
itself** — a branch-bound caller, a second branch's data seeded, and the assertion that
the second branch is absent from the response. A generic "the gate calls resolve_scope"
test would pass while a specific tool quietly queries without `branch_id`
*(party mode: Murat)*

**Given** refusing write tools removes a capability that something might depend on
**When** the story is implemented
**Then** the repository is searched for **every** caller of this endpoint before the
refusal ships, and the completion log states what was found and what could not be seen
from here. Today the only callers are the 22 `executeTool` sites in the SPA, all reads
*(party mode: Winston)*

**Given** the endpoint today answers 404 for an unknown tool **before** it checks
whether the caller is allowed anything at all
**When** an authenticated student probes tool names
**Then** they learn nothing: authorization is decided before existence is revealed, so an
unknown tool and a forbidden tool are indistinguishable from outside
*(elicitation: red team)*

**Given** the branch-scoping change
**When** the story closes
**Then** the `scoped_filter`/`scoped_query` grep audit is re-run over every touched
backend file and every hit is either migrated or annotated
`# branch-scope: intentional — <reason>`

---

## Epic 10: Something You Can Actually Hand Someone

When Flo drafts a circular, a fee sheet or a notice, the school gets a **file they can
send, print or sign** â€” not text to copy out of a chat window.

**Requirements covered:** FR7, NFR-S1, NFR-S2 Â· UX-DR4, UX-DR9
**Owner item:** the 2026-07-22 screenshot, in which Flo told the owner it could produce
the *content* of a Word, Excel, PowerPoint or PDF file but "not directly generate a real
`.docx` file in this setup".
**Sequencing:** pulled forward ahead of Epic 5 on the owner's instruction, 2026-07-22.

### What was found before the stories were written

**Flo was underselling the platform.** Every library needed is already installed and
pinned in `backend/requirements.txt`: `python-docx`, `openpyxl`, `python-pptx`, `fpdf2`.
Three of the four are already used â€” but only for *reading*
(`routes/chat_upload.py` extracts text from `.docx`, `.xlsx`, `.pptx`, `.pdf`). Only PDF
is used for *writing*, in `routes/image_gen.py` (certificates) and `routes/fees.py`
(receipts).

**The whole store-and-deliver path already exists and is proven.** `image_gen.py` takes
generated bytes â†’ `upload_bytes()` to S3 under the `{school_id}/uploads/...` key
convention â†’ inserts a `file_uploads` record â†’ `write_audit()` â†’ returns a presigned URL
with an expiry. Certificates have shipped through it. This epic reuses that path rather
than inventing a second one.

So this is **not a missing capability. It is unwired plumbing** â€” which is why it was
cheap enough to pull forward.

### The security fact that shapes every story

**Generating a document IS a data export.** "Make me a spreadsheet of every student" and
`GET /api/export/students` return the same 1,802 children by different routes. If the
document tool were gated more loosely than `routes/exports.py`, it would become a way to
walk around export permissions by asking Flo politely.

Therefore: **every generated document inherits the exact role gate its data already
has** â€” `require_owner_or_principal` for students and staff, owner-or-accountant for fee
and expense data, and so on, copied from `exports.py` rather than re-derived. No new
permission is created by this epic, which is why it needed no separate product decision.

### Story 10.1: One place that turns content into a real file

As the school,
I want the platform to produce genuine Word, Excel, PowerPoint and PDF files,
So that what Flo writes can be printed, signed, emailed to parents or filed.

**Acceptance Criteria:**

**Given** `python-docx`, `openpyxl`, `python-pptx` and `fpdf2` are already installed
**When** this story ships
**Then** there is **one** document builder â€” a single module every caller uses â€” that
takes a structured document description and returns bytes plus a content type, for each
of `docx`, `xlsx`, `pptx` and `pdf`. Four separate half-built generators scattered
across route files is the outcome this AC exists to prevent

**Given** the proven store-and-deliver path in `routes/image_gen.py`
**When** a generated file is saved
**Then** it reuses that path exactly â€” S3 under `{school_id}/uploads/...` (the Part 6
convention), a `file_uploads` record, an audit row, and a **presigned URL with an
expiry**. A generated document must never be served from an unauthenticated public URL,
which is the defect `hotfix-1` was raised for

**Given** a document containing a student's name, a parent's phone number or a fee
amount
**When** it is stored
**Then** the S3 key carries the `school_id` namespace so one school's generated files
can never sit in another's prefix, and the `file_uploads` record is school-scoped like
every other operational record

**Given** a caller asks for a document type the builder does not support, or supplies a
description that is malformed
**When** the request is handled
**Then** it fails with a clear error and writes nothing â€” a half-written file in S3 with
no `file_uploads` record is an orphan nobody can find or delete

**Given** the filename comes from a person or from Flo
**When** it is used
**Then** it is sanitised before it reaches S3 or a `Content-Disposition` header â€” a
filename containing a path separator, a newline or a quote is the classic way to write
outside the intended prefix or to forge a response header

**Given** a document could be enormous (every one of 1,802 students, every fee row)
**When** one is generated
**Then** row and size caps apply, mirroring the existing `.to_list(N)` limits in
`exports.py`, and the caller is told plainly when output was truncated rather than being
handed a silently short file

### Story 10.2: Flo hands you the file, not the homework

As anyone using Flo,
I want to ask for a circular or a fee sheet and be given the actual file,
So that I do not have to copy text out of a chat window and reformat it myself.

**Acceptance Criteria:**

**Given** the tool registry and the Epic 4 rule that the tool-panel endpoint serves
**reads only**
**When** the document tool is registered
**Then** its `roles` and `sub_categories` mirror the gate on the equivalent export in
`routes/exports.py` for whatever data it draws on â€” students and staff to
owner-or-principal, fees and expenses to owner-or-accountant â€” so **no one can obtain
through Flo a document they could not already export**. A test asserts this
correspondence rather than trusting it was copied correctly

**Given** the tool produces a file and an audit row but changes **no** school record
**When** it is classified
**Then** it is a read-class tool, not a `dispatch_type: "write"` â€” it needs no
confirm-action step, because there is nothing to undo. This is a deliberate decision and
is recorded, so a later reviewer does not "fix" it into a confirm flow

**Given** every generated document is a copy of school data leaving the platform
**When** one is generated
**Then** an audit row records who asked, what data, and which file id â€” consistent with
the F.2 rule that reads of student records through the assistant are audited

**Given** generation costs storage and can be requested in a loop
**When** the same school generates repeatedly
**Then** a per-school daily cap applies, reusing `_enforce_daily_cap` from
`image_gen.py` rather than a second counter, and the refusal says plainly that the day's
limit is reached

**Given** NFR-S2 (no PII in structured log fields)
**When** generation is logged
**Then** the log records the file id, the type and the row count â€” never a student name,
a phone number or the document body

**Given** the standing directive that any change to `ai/prompts.py` or the tool registry
needs a green eval run
**When** this story closes
**Then** the structural and judge-logic evals are green, and the log states plainly
whether the credentialed judge tier could be run on this machine

### Story 10.3: The file arrives where you can reach it

As the school Owner on a phone,
I want the file to appear in the conversation as something I can tap and open,
So that a document I asked for does not become a link I have to hunt for.

**Acceptance Criteria:**

**Given** a document has been generated
**When** Flo's reply renders
**Then** the file appears as a clearly labelled, tappable item showing its **name, type
and size**, not a bare URL pasted into prose

**Given** the presigned URL expires
**When** the Owner opens an old conversation and taps a document from last week
**Then** he is told it has expired and offered to generate it again â€” a dead link that
simply fails is the "failure that looks like a zero" defect of Epic 4 in a new place

**Given** UX-DR4 and UX-DR9
**When** the item renders
**Then** it carries a `data-testid`, is reachable and operable by keyboard, has a visible
focus state, and states its file type in **text** rather than by icon colour alone

**Given** the file item is a shared component
**When** the story closes
**Then** every screen that could show a generated file is listed in the completion log,
per the standing shared-component rule

### Story 10.4: The exports people already have, in the format they asked for

As the school Accountant or Principal,
I want the existing export buttons to give me Excel as well as CSV,
So that a fee sheet opens with its columns and totals intact instead of as raw commas.

**Acceptance Criteria:**

**Given** `routes/exports.py` already offers CSV for students, fee transactions,
attendance, staff, expenses, enquiries and exam results, and `export_students` already
accepts an unused `format` parameter
**When** this story ships
**Then** `format=xlsx` produces a real workbook through the Story 10.1 builder, and
`format=csv` remains the default so **every existing caller keeps working unchanged**

**Given** the role gate on each existing export
**When** the format option is added
**Then** the gate is **untouched** â€” this story changes packaging, never permission, and
a test asserts each endpoint still refuses the roles it refused before

**Given** an unrecognised `format` value
**When** it is requested
**Then** the server falls back to CSV rather than erroring, matching how Epic 3 handled
an unrecognised sort field

### Story 10.5: Flo reads a printed page, on your own server, for nothing

As a school administrator holding a fee slip, an admission form or a printed circular,
I want to photograph it and have Flo read the words off it,
So that I do not retype what is already written down.

**Added by the owner 2026-07-22**, choosing on-server OCR over a paid vision service for
printed paper: *"make the ability or skill of using Tesseract or PaddleOCR for printed
paper available to Flo â€” free, private, on your own server."*

**Why this is the right default, recorded so it is not undone:** most of what a school
photographs is **printed** â€” fee slips, forms, circulars, mark sheets. OCR reads those
accurately, costs nothing per use, and **the image never leaves the school's own
server**. For children's photographs that privacy property is worth more than the
accuracy a hosted model would add.

**Acceptance Criteria:**

**Given** the backend runs on a small Elastic Beanstalk instance
**When** the OCR engine is chosen
**Then** it is **Tesseract** (via `pytesseract`), not PaddleOCR or EasyOCR: those pull
PaddlePaddle or Torch, hundreds of megabytes of model and a memory footprint this
instance does not have. The choice is recorded with that reason so it is not revisited
blind

**Given** Tesseract is a **system binary**, not a Python package, and is not installed
on the server today
**When** the binary is absent
**Then** the feature reports itself **unavailable, in plain words**, and nothing crashes
â€” the same fail-honestly rule as Epic 4. It must never return an empty string as though
the page were blank, which is that epic's defect in a new place. An `.ebextensions`
entry installs `tesseract` and the **Hindi/Devanagari language data**, but installing it
on production is a **deploy, and needs the owner's approval** â€” until then this ships
dark and says so

**Given** the school's paperwork is in English and Hindi
**When** text is extracted
**Then** both `eng` and `hin` are attempted, and the answer records which language was
detected

**Given** a photograph of a person rather than a document
**When** OCR runs
**Then** it returns little or no text, and Flo says the page could not be read rather
than inventing content. OCR does not "see" â€” it only reads letters, and Flo must not
imply otherwise

**Given** the access rule settled on 2026-07-22 and **revised the same day**
**When** an image is submitted
**Then** **Owner, Principal and the other office staff** (accountant, receptionist and
the rest of the admin roles) may use it, and **teachers and students may not**.
An earlier draft included teachers on the reasoning that they photograph forms; the
owner narrowed it to the office, because this is paperwork handling and it belongs with
the people who do the paperwork. Teachers were removed DELIBERATELY - do not restore
them assuming it was an oversight. Note this matches neither `is_owner_or_principal`
(which would exclude the accountant and receptionist who handle most of the paper) nor
the general read gate (which would include students, the children a photograph is most
likely to contain), so it needs its own predicate

**Given** every image read is a read of school records
**When** OCR runs
**Then** it writes an audit row (who, when, file id) and the log records **no extracted
text** â€” NFR-S2, and doubly so here, since the extracted text may be a child's medical
note

**Given** an uploaded file that is enormous, is not an image, or is a corrupt file
claiming to be one
**When** it is submitted
**Then** it is refused on **content sniffing**, not on the file extension, with a size
cap â€” a `.png` that is really a 200 MB archive must not reach the OCR process

### Story 10.6: When reading the words is not enough

As the school Owner,
I want Flo to fall back to genuinely understanding a photograph only when reading the
text off it was not enough,
So that we pay for the clever service rarely, and keep printed paper free and private.

**Added by the owner 2026-07-22:** *"fall back to the service you already pay for only
when someone needs a photo genuinely understood."*

**Acceptance Criteria:**

**Given** OCR runs first and costs nothing
**When** a request could be answered from the text on the page
**Then** the paid vision path is **not** called. It is a fallback, not a parallel
attempt, and a test asserts that a successful OCR read does not trigger it

**Given** OCR returned little or no text, or the person explicitly asked what a picture
*shows* rather than what it *says*
**When** the fallback runs
**Then** it uses the Azure OpenAI deployment the platform **already uses for chat** â€”
adding no new service, no new subscription and no standing charge, which is the
correction recorded in D-26

**Given** the deployment in use may not accept images
**When** the fallback is attempted and the model refuses the image
**Then** the failure is reported plainly as "this server cannot look at pictures yet",
never as an empty or invented description

**Given** the fallback costs money per image
**When** it is used
**Then** it obeys the same per-school daily cap as document generation, and the audit row
records that the **paid** path was taken â€” so the owner can see how often it happens

**Given** the owner's instruction that Flo must **NOT generate** images or video
**When** this epic closes
**Then** no image-generation capability is added, and a test asserts no such tool exists
in the registry. `routes/image_gen.py` continues to render certificate **templates**,
which is document rendering and not AI generation â€” this is stated so the file's name
does not later be mistaken for a breach of that instruction

---

## Epic 5: A Conversation That Feels Alive

Asking Flo a question feels immediate and continuous â€” no stalls, no sudden dumps, no
overlapping progress boxes, and a composer that is pleasant to type in.

**Requirements covered:** FR7, FR11, NFR-P3, NFR-SSE1â€“4, UX-DR8
**Owner items:** 9, 10, 12, 13

### What was found before the stories were written

The chat surface has already been hardened twice (epic R8 for resilience, Epic 9 for
the visual language), so the honest starting point was to find what is actually still
broken rather than assume the whole surface needs work.

**Already correct, and deliberately not re-done:**
- The composer auto-grows to a 160px ceiling, sends on Enter, opens a newline on
  Shift+Enter, and has its focus ring on the pill rather than the inner field (Epic 9).
- A stream that ends without its terminal `done` event, drops mid-flight, or returns
  401 already surfaces a visible, retryable error rather than a silent stall
  (`lib/api.js`, epic R8). The decoder tail is flushed so a final frame is never lost.
- The server sends an SSE keepalive every 5 seconds (`routes/chat.py`).

**Genuinely still broken â€” these are the stories:**

1. **Two progress boxes report the same work.** While streaming, `ChatInterface`
   renders a `ToolCallBadge` for `currentStreamMsg.toolCall` AND a `ThinkingProcess`
   panel fed by `thinkingSteps`, which contains `tool_start` / `tool_done` for the same
   tool. The same activity is announced twice, in two different shapes.
2. **They do not line up.** The tool badge is indented 42px to clear the avatar
   gutter; the thinking panel has no left padding at all and sits flush against the
   edge; the message body starts at 42px again. Three stacked elements, three different
   left edges, and vertical gaps of 4px, 8px and 24px. That is owner item 12 and the
   reason UX-DR8 exists.
3. **A silent connection spins forever.** Every *detectable* failure is handled, but a
   connection that is accepted and then goes quiet â€” the server wedged, the network
   dropped without a FIN â€” leaves `reader.read()` waiting indefinitely and the typing
   dots animating with nothing behind them. There is no client-side watchdog, so
   NFR-P3 ("first token â‰¤ 3s") has nothing enforcing it and no way to report a breach.

### Story 5.1: One progress box, lined up with everything else

As anyone watching Flo work,
I want a single, tidy account of what it is doing,
So that the wait is legible rather than a stack of boxes that disagree.

**Acceptance Criteria:**

**Given** `ToolCallBadge` and `ThinkingProcess` both report tool activity while
streaming
**When** a tool runs
**Then** it is reported **once**. The thinking panel is the single account of progress;
the separate badge is not rendered alongside it for the same work

**Given** UX-DR8 (a consistent spacing scale for stacked stream elements) and the 42px
avatar gutter every assistant message uses
**When** the progress panel, any badge and the reply body are stacked
**Then** they share **one left edge** and **one vertical rhythm**. A test asserts the
alignment value rather than a person eyeballing it, because this is precisely the class
of defect that survives a screenshot

**Given** the panel is the only progress indicator
**When** there are no steps worth showing
**Then** the typing indicator is shown instead â€” and never both at once

**Given** the collapsed summary bar is interactive
**When** it renders
**Then** it keeps its `role="button"`, keyboard operation and visible focus state
(NFR-A2), and carries a `data-testid` (UX-DR4)

### Story 5.2: A reply that stalls says so, instead of spinning forever

As the school Owner waiting on an answer,
I want to be told when nothing is coming,
So that I retry rather than watching three dots and guessing.

**Acceptance Criteria:**

**Given** NFR-P3 â€” first token within 3 seconds â€” which today has nothing enforcing it
**When** a stream is accepted but sends nothing at all
**Then** a client-side watchdog notices. After a **first threshold** it says Flo is
taking longer than usual, and after a **second** it declares the turn failed and offers
retry. It must never sit silent indefinitely

**Given** the server sends a keepalive every 5 seconds
**When** the keepalive is arriving but no content is
**Then** the connection is known to be alive and the message says so â€” "still working"
is a different statement from "nothing is coming", and conflating them would send the
owner to retry a request that was about to succeed (NFR-SSE1, NFR-SSE4)

**Given** any activity at all â€” a token, a thinking step, a keepalive
**When** it arrives
**Then** the watchdog resets. A long, genuinely-working answer must never be declared
stalled

**Given** the turn ends normally, errors, or is aborted
**When** it finishes
**Then** the watchdog is cleared. A timer left running after unmount would fire against
a dead component, which is how "cannot update state on an unmounted component" warnings
and phantom error banners appear

**Given** the existing `stream_error` handling from epic R8
**When** the watchdog fires
**Then** it reuses that path rather than inventing a second error surface, so a stall
and a dropped connection look the same to the person reading the screen
