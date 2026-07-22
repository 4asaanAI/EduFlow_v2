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

**Given** an authenticated admin who can manage staff
**When** they POST to `/api/staff/` with `role: "owner"`, bypassing the UI entirely
**Then** the request is rejected with 403 and no staff or user record is created
**And** the attempt is recorded via `write_audit()` with the caller's user id

**Given** the same caller
**When** they PATCH an existing staff member to `role: "owner"`
**Then** the request is rejected with 403 and the stored role is unchanged

**Given** the platform's single existing owner account
**When** Story 1.1 ships
**Then** that account is unaffected and can still sign in and manage staff
**And** owner assignment remains possible only out of band, never through this API

**Given** the test suite
**When** it runs
**Then** it contains an unauthenticated 401 test and a wrong-role 403 test for both the
create and update paths, per the platform's standing endpoint-test convention

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
**And** no record is written

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

**Given** any authenticated user viewing their own profile
**When** they open it
**Then** name, phone and email are editable, and role, school, sub-category and AI token
allowance are shown read-only

**Given** that same user
**When** they submit a change to their own `role`, `sub_category`, `schoolId` or token
allowance by any means including a direct API call
**Then** the server ignores or rejects the change and the stored values are unaltered

**Given** an Owner viewing another person's profile
**When** they edit it
**Then** they may change that person's role and sub-category, subject to Stories 1.1
and 1.2

**Given** any profile edit that succeeds
**When** it is written
**Then** an audit entry records who changed what, and the change is visible immediately
without a page reload

**Given** the profile dialog
**When** it is rendered
**Then** every control carries a `data-testid`, uses CSS variables rather than raw hex,
and has a visible focus state at ≥3:1 contrast (UX-DR1, UX-DR4, UX-DR9)
