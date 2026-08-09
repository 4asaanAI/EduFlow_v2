# Release 2 — Person profiles for Sonu and Lalit

**Raised:** 2026-08-10, by Abhimanyu, after meeting Aman and Adesh at Aaryans.
**Branch:** `release-2-person-profiles` (to be created)
**Live progress log:** `_bmad-output/implementation-artifacts/release-2/PROGRESS.md`
← *that file, not this one, records what is done. This one records what the work is.*

**Goal:** give the accountant head (Sonu Ruhal) and the management person (Lalit Thomas)
their own logins so they keep the school's data current, without either of them reaching
what they should not.

**Hierarchy the school asked for:** Aman (owner) > Adesh (principal) > Sonu (accountant
head) > Lalit (management). Close-enough tools, because for now only these four people
touch the platform.

**Rollout this belongs to:**

| Release | Who gets in |
|---|---|
| 1 (live) | Aman, Adesh |
| **2 (this document)** | + Sonu, Lalit |
| 3 | + department heads, starting with Chaman Singh (transport head) |
| 4 | + whole admin staff |
| 5 | + teachers |
| 6 | + students |
| 7 | + parents (may merge with 6) |

---

## Decisions taken (Abhimanyu, 2026-08-10)

These are settled. Do not re-open them; ask about something else if it is unclear.

1. **Lalit and money.** He may see a family's paid / unpaid flag. He may never see a
   rupee figure, anywhere.
2. **Sonu's non-money reach.** Staff attendance and leave, read only. Student attendance,
   read only. Full directory read, plus the columns he already owns. Vendor records in
   full.
3. **Transport.** Build the transport head profile now, for **Chaman Singh**, who already
   exists in the staff records with `sub_category: transport_head`. It stays dormant
   until Release 3. **In the meantime transport stays with Aman, Adesh and Sonu** — this
   revises the first answer, which had put transport outside Sonu's reach.
4. **Lalit and people records.** He may add and edit students and staff. He may not
   delete them, and he may not create or reset any login.
5. **Creating students.** Sonu may create new students, alongside Aman and Adesh.
6. **Certificates and ID cards.** Lalit may create all of them, but nothing leaves the
   platform until Aman or Adesh approves it, and that approval happens on the platform.
7. **Logins.** *Revised 2026-08-10, later the same day.* **All four** move to the form
   migration 031 already declares: `aman.litt`, `adesh.singh`, `sonu.ruhal`,
   `lalit.thomas`. Every password stays exactly as it is. Display names go with them, so
   Adesh shows as "Adesh Singh" everywhere. This supersedes the earlier instruction to
   leave Aman's and Adesh's credentials alone: Abhimanyu chose the tidier end state
   knowing it logs both of them out once.
8. **Staff messaging.** Every school employee must be reachable by chat inside the
   platform, appearing as each release lets them in.

---

## Part 1 — What is actually wrong today

Every item below was read out of the code on 2026-08-10 and verified, not assumed.
File and line references are given so the next agent can re-check rather than re-discover.

### 1.1 The root cause: the platform grants by subtraction

Two places decide what Sonu and Lalit get, and both work the same way:

- `frontend/src/lib/toolPermissions.js:71-73` — management = *"anything not in
  `FINANCE_TOOL_IDS` and not in `LEADERSHIP_ONLY_TOOL_IDS`"*.
- `backend/ai/tool_functions_v2.py:6796-6804` — every tool not named in
  `FINANCE_TOOL_NAMES`, `SHARED_LOOKUP_TOOL_NAMES` or `LEADERSHIP_ONLY_TOOL_NAMES`
  falls into the `else` branch and is stamped `access_domain = "non_finance"`, which is
  Lalit's.

Subtraction is why every defect below exists, and it is a permanent leak: any tool or
screen added tomorrow lands in Lalit's hands by default, silently. **Nothing in the
codebase states what Sonu and Lalit are supposed to have.** There is no list to read.

Today's totals, measured on 2026-08-10:

| Profile | Flo tools reachable (of 161) | of those, writes | API routes reachable (of 483) | Screens offered |
|---|---|---|---|---|
| Aman (owner) | 155 | — | 350 | 56 |
| Adesh (principal) | 155 | — | 336 | 57 |
| Sonu (accountant) | 48 | — | 266 | 11 |
| Lalit (management) | 112 | 71 | 221 | 37 |

Reproduce these with the two scripts described in §4.2.

### 1.2 The screenshot: Lalit is offered the principal's screens

`frontend/src/lib/managementHubs.js:154-158`. `hubItemsForUser` sets
`hasProfileMatrix = true` for principal, accountant and management, and that flag then
skips the check for whether a screen was meant for the owner or the principal. Lalit
inherits 12 principal screens: **Principal Daily**, Document Scanner, Admissions CRM,
Circulars, Parent Messages, Student Transfer, Academic Structure, Timetable, Student
Attendance, Report an Issue, Routes & Vehicles, Route Optimisation.

### 1.3 Lalit can see the school's money, in nine places

| # | Where | What leaks |
|---|---|---|
| 1 | **School Pulse** (`SchoolPulse.js:103-104,176-177`) | "Fees Collected ₹…" and "Overdue Fees ₹…" tiles, plus a fee-collection summary line |
| 2 | **Smart Alerts** (`OwnerTools.js:1497`) | "Overdue fees: ₹… needs follow-up" |
| 3 | `GET /api/fees/class-summary` | fee dues per class. Guard `require_role("owner","admin")` — any admin |
| 4 | `GET /api/fees/status/{student_id}` | full fee status including amounts |
| 5 | `GET /api/fees/discounts/{student_id}` | discounts granted to a family |
| 6 | `GET /api/accounting/periods` | the accounting calendar |
| 7 | `PATCH /api/accounting/periods/{id}/status` | **he can open or close the posting lock** |
| 8 | `PATCH /api/ops/expenses/{id}` | **he can edit an expense** |
| 9 | `GET /api/staff/{staff_id}` (`routes/staff.py:556-565`) | **every teacher's salary**, one record at a time |

On #9: the staff *list* strips salary with the projection `{"_id":0,"salary":0}`
(`staff.py:280`); the single record returns `_public_staff(staff)`, which keeps it.

In the menu, Lalit is also offered **Vendor Log**, which decision 2 keeps with Aman,
Adesh and Sonu.

### 1.4 Lalit can do owner-only things through Flo

`backend/services/ai_action_policy.py:70-80`, called from `ai/tool_access.py:33-35`.
The profile decision returns first and short-circuits the registry's own `roles` check.
It tests only whether `roles` *intersects* `{owner, admin}` — a tool marked
`roles=["owner"]` passes that test, and the domain check then hands it to Lalit.

Owner-only tools Lalit can run today: **`year_end_transition`** (promotes every student
on the roll to the next class), `create_branch`, `update_branch`, `delete_branch`,
`update_school_settings`, `get_branch_comparison`, `query_dashboard_summary`. Sonu gets
the finance-side equivalents: `create_legal_entity`, `delete_legal_entity`,
`set_default_legal_entity`.

None of these services carry their own role check. `org_config_service.py:10` says in so
many words that it relies on the route guard and the registry roles, and the Flo path
bypasses both.

### 1.5 Lalit and Sonu can both take people off the roll

`delete_student` and `delete_staff` have no role check inside the service. The REST
routes (`DELETE /api/students/{id}`, `DELETE /api/staff/{id}`) check only
`role in ADMIN_ROLES` (`students.py:103`, `staff.py:108`), which is any admin
sub-category, and the Flo path grants them as `non_finance`. This is a reversible
deactivation rather than destruction, and `set_enrolment_state` puts a person back, so it
is not a disaster. It is still against decision 4.

### 1.6 Certificates: the record asks permission, the printer does not

There are two certificate paths and only one of them respects Aman's rule.

- `services/certificate_service.py:41-75` **already does what decision 6 asks.** A TC,
  bonafide, transfer, character or merit certificate created by anyone who is not the
  owner or principal lands in `pending_approval` and raises a notification. Aman or
  Adesh approve it. This is good, and predates this initiative.
- `routes/image_gen.py:403-478` is the path that actually **prints** the document, and it
  has no approval step at all. Its guard (`require_document_issuer`, line 29) admits
  admin+management by a deliberate decision of 2026-08-08. So **Lalit can produce a
  Transfer Certificate PDF carrying the school's name, immediately, with nobody asked.**

### 1.7 Staff messaging is empty because the contact list is four hardcoded usernames

This is the "0 colleagues available" in the screenshots. `routes/messaging.py:37-40`:

```python
LEADERSHIP_USERNAMES = {"aman.litt", "adesh.singh", "sonu.ruhal", "lalit.thomas"}
```

`_leadership_contacts` (line 145) looks people up by `username_lower` against exactly
that set. The logins actually in production are `accountant` and `management`, and Aman's
and Adesh's are whatever they were created as, so the lookup matches nobody and the
screen truthfully reports zero. Renaming the logins (decision 7) fixes it by accident for
these four, which is precisely the wrong reason for it to work: the next employee to join
would still be invisible.

Two further things visible in the screenshots: the header reads **RECONNECTING**, so the
live message stream is not connecting in production and needs its own diagnosis; and
there is **no way to search for a person** in the New Message dialog, only Direct and
Group buttons and, for a group, a name field with no member picker.

### 1.8 Promises the platform breaks in the other direction

- **Adesh is offered Payroll & Payslips and then refused.** The menu grants the principal
  every screen; the payroll routes use `_require_owner_or_accountant`
  (`routes/payroll.py:43`), which excludes the principal. Eight routes.
- **Sonu is offered 11 screens and none of what he actually does.** No staff attendance,
  no student attendance, no vendors, no staff leave, no transport.
- **Sonu's Flo brief tells him attendance is out of scope** (`ai/prompts.py:1575`).
- **Lalit's Flo brief promises him logins** (`ai/prompts.py:1584`), which decision 4
  removes.

### 1.9 What the platform already gets right — do not "fix" these

- **Password resets are already safe.** `account_management_service.py:237-240`:
  management may change only *student* passwords, and nobody but the owner may change an
  owner's. An early read of the tool registry suggested Lalit could reset Aman's
  password; reading the service proved that wrong. Verify before alarming.
- **Salary edits are already blocked.** `salary` is in `staff_service.OWNER_ONLY_FIELDS`
  and is stripped for every non-owner.
- **Spreadsheet import is already scoped per profile**, and out-of-segment columns are
  reported rather than silently dropped (`data_import_service.IMPORT_FIELD_SCOPES`).
- **Flo already has a separate written brief** per profile (`ai/prompts.py:1569-1587`).
  They need correcting, not inventing.
- **The directory screens carry no money at all** — School Directory, Student Database
  and Staff Tracker were searched for fee, salary, amount and rupee fields. Clean.
- **The certificate record flow already has approval** (§1.6). Extend it to printing;
  do not rebuild it.

---

## Part 2 — The plan, broken into sub-parts

**The principle.** Stop granting by subtraction. Write down, in one file, exactly what
each person gets: every screen, every tool, every route, named. Anything not on the list
is denied. The menu, the server and Flo all read that one file, so they cannot drift
apart, and a feature added next month gives nobody anything until someone decides who it
belongs to.

That file is also what Releases 3 through 7 extend. This is the pattern, not a patch.

### R2-1 — The permission matrix (one source of truth)

Create `backend/services/profile_matrix.py`, plus a generated JS mirror the frontend
imports. Profiles keyed by the person's job, not their department. Every entry names
screen ids, Flo tool names, API route groups, and read versus write. **Default deny.**
A build step generates the mirror from the Python so the two cannot disagree.

Include `transport_head` from the start, marked dormant, so R2-12 is a switch and not a
new design.

*Done when:* the file exists, all three surfaces read it, and no other file makes a
per-profile decision.

### R2-2 — Close the nine money leaks to Lalit

Fix everything in §1.3. For School Pulse and Smart Alerts, build a non-finance variant
rather than hiding the whole screen; Lalit still needs the attendance and staffing half
of both. For `GET /api/fees/status/{id}`, return the paid / unpaid flag with amounts
stripped, per decision 1. For `GET /api/staff/{id}`, drop `salary` at the response
boundary for anyone who is not owner, principal or accountant. Move the accounting-period
and expense routes onto the finance profiles. Take Vendor Log out of Lalit's menu.

*Done when:* a test logs in as Lalit, sweeps every screen and route he can reach, and
finds no rupee figure and no salary.

### R2-3 — Close the owner-only hole

Fix `profile_authorization_decision` so the registry's `roles` list is still honoured: a
tool marked owner-only stays owner-only whatever its domain says. Re-check the twelve
tools in §1.4.

*Done when:* a test asserts that for every owner-only tool in the registry, all three
non-owner profiles are refused.

### R2-4 — People records: who may add, edit, remove

Per decision 4. Lalit: add and edit students and staff, yes; delete, no; logins, no.
Move the delete guard off `role in ADMIN_ROLES` and into the service, so the screen and
Flo inherit the same answer. Remove `create_student_login` and `set_profile_password`
from Lalit. Per decision 5, add student creation to Sonu.

### R2-5 — Sonu's full remit

Add, read only: staff attendance, staff leave, student attendance. Add in full: vendor
records, and transport (routes, vehicles, optimisation) as the contingency under decision
3. Add student creation. Correct his Flo brief so it no longer says attendance is out of
scope.

### R2-6 — Fix the principal's dead buttons

Reconcile Adesh's menu with what the server accepts, both directions. Payroll is the
known one; the sweep in R2-13 finds the rest. Rule: if the menu offers it, the server
accepts it, or it comes out of the menu.

### R2-7 — Profiles built for the person, not the department

*Decided 2026-08-10: one vocabulary for the whole school.* Sonu and Lalit keep the same
department groups Aman and Adesh see, by name: School Overview, School Database,
Finance & Campus Sales, Admissions & Communication, Academics & Activities,
People & Attendance, Campus Library & Assets, Transport, Reports AI & Governance. They
see only the rows their profile grants, and **a group with nothing in it does not appear
at all** rather than opening onto an empty page. Do not invent per-person group names:
one word for one thing across the school, and Releases 3 through 7 slot straight in.

The problem being fixed is not the group names, it is that today Sonu gets 2 of the 9
groups and Lalit gets a principal's rows inside them. Remove the accidental principal
rows from Lalit (§1.2) and give Sonu the groups his work actually spans (§1.8).

### R2-8 — Flo per person

Correct both briefs against the decisions above. Make Flo introduce itself in terms of
that person's job. Make every refusal name who to ask instead ("that is Sonu's to change,
or Adesh's") rather than a flat "not available to me", which this project has already
been bitten by once.

### R2-9 — Certificates and ID cards need approval before they print

Per decision 6. Lalit creates any certificate or ID card; nothing is produced until Aman
or Adesh approves it on the platform. The record side already does this (§1.6): extend
the same rule to `routes/image_gen.py`, do not build a second approval system. Add the
approval queue to Aman's and Adesh's screens and to their notifications, and give Lalit a
clear "waiting for approval" state so he is never left wondering.

ID cards need the rule too, and are not in `APPROVAL_REQUIRED_TYPES` today.

### R2-10 — Staff messaging: a real colleague directory

⚠️ **There are two unrelated messaging systems and they are easily confused.** This
sub-part is about `backend/routes/messaging.py`, the **staff-to-staff** chat: threads,
groups, read receipts, live stream. It is NOT `backend/routes/parent_messaging.py` and
`services/messaging_service.py`, which send WhatsApp and SMS to families and shipped on
2026-08-08 (see `_bmad-output/outdated/handoffs/HANDOFF-2026-08-08-messaging-toolsearch-import.md`, which
warns about exactly this mix-up). Nothing in R2-10 touches the parent path.

Per decision 8, and the three screenshots. Replace the four hardcoded usernames (§1.7)
with "everyone whose login exists and whose release has arrived", read from the same
matrix as R2-1. Then:

- add a person search to the New Message dialog, and a member picker to New Group,
  because neither exists;
- diagnose the **RECONNECTING** state on the live message stream;
- decide and write down who may message whom as later releases land. Release 5 puts
  teachers in; Release 6 puts students in, and a student-to-staff channel is a different
  question from staff-to-staff. **This needs an explicit answer before Release 5**, not
  at the time.

*Done when:* Aman, Adesh, Sonu and Lalit see each other, can search, can start a direct
chat and a group, and the header does not say RECONNECTING.

### R2-11 — Rename all four logins

Per decision 7 as revised. All four move to the form migration
`031_provision_school_leadership_accounts.py` already declares: `aman.litt`,
`adesh.singh`, `sonu.ruhal`, `lalit.thomas`. Passwords unchanged. Display names go with
them, so Adesh reads "Adesh Singh" in the header, in chat and in the audit trail.

First establish whether 031 ran in production and what the live rows actually say.
**Read before writing.**

**This logs Aman and Adesh out**, and they are the only two people using the platform
today. So: tell the school the day before, do it at a quiet hour, and have the four new
usernames written down and in Abhimanyu's hand before the change, not after. Getting this
wrong locks the school's owner out of his own school.

### R2-12 — Build the transport head profile for Chaman Singh

Per decision 3. Chaman Singh already exists in staff with `sub_category: transport_head`
(confirmed in `scripts/apply_owner_corrections_2026_08_06.py:25-26`); he has no login.
Define his profile in the matrix now, with transport in full and nothing else, and leave
it dormant. Release 3 turns it on and hands transport over from Sonu.

### R2-13 — The proof

One test that walks all four live profiles plus the dormant one across all three
surfaces: every screen the menu offers, every route, all 161 Flo tools. It asserts the
matrix and fails when a new tool or screen is added without an owner. This file is what
keeps Releases 3 through 7 honest.

### R2-14 — Accounts, handover, go-live

Hand credentials over in person, watch the first week, then start Release 3.

---

## Part 3 — Order of work

One sub-part per run. Suite green before the next. Update the progress log every time.

1. **R2-1** — the matrix. Everything else reads it.
2. **R2-3** — the owner-only hole. Smallest, highest severity.
3. **R2-2** — the money leaks. Biggest single block.
4. **R2-4** — people records.
5. **R2-5** and **R2-6** — Sonu's additions and Adesh's refusals. Can pair.
6. **R2-9** — certificate and ID card approval.
7. **R2-10** — staff messaging. Largest unknown; may split once the RECONNECTING cause is known.
8. **R2-7** and **R2-8** — per-person layouts and Flo briefs. Can pair.
9. **R2-12** — transport head profile, dormant.
10. **R2-13** — the proof. Written alongside each step above, run whole here.
11. **R2-11** — rename the logins. Late on purpose: it revokes sessions.
12. **R2-14** — go-live.

## Part 4 — Working notes for whoever picks this up

### 4.1 The rules that govern this work

Inherited from `CLAUDE.md` and the earlier execution protocols; they still apply.

1. **The suite baseline is 0 failures.** Never pin a pass count; run the suite and read
   what it prints.
2. **Never run `backend/migrations/run_all.py` against the live school database.** One
   migration at a time, after reading what that file does.
3. **Deploys run as the `claude-hosting` IAM user.** Confirm with
   `aws sts get-caller-identity` first; the Arn must end `user/claude-hosting`.
4. **No TypeScript.** `.js` and `.jsx` only.
5. **`from __future__ import annotations` is the first line** of any Python file using
   `str | None`.
6. **Do not add `pytestmark = pytest.mark.asyncio`** to test files; `asyncio_mode = auto`
   already handles it.
7. **`owner` is the school's owner (Aman), never Abhimanyu.** In prose written to
   Abhimanyu, say "the school's owner", not "you".
8. **Never read or modify the live school database** while doing this work.

### 4.2 How to reproduce the audit numbers

Two throwaway scripts produced the table in §1.1. Both are safe: they import the app and
the registry and touch no database.

- **Flo tools per profile:** import `TOOL_REGISTRY` from `backend/ai/tool_functions_v2.py`
  and `profile_authorization_decision` from `backend/services/ai_action_policy.py`, then
  evaluate every tool against the four user dicts
  (`{"role":"owner"}`, `{"role":"admin","sub_category":"principal"}`, `…"accountant"`,
  `…"management"`).
- **API routes per profile:** import `server.app`, walk `app.routes`, read
  `route.dependant.dependencies` recursively, and unwrap the closures named `dependency`
  via `__closure__` to recover the roles and sub-categories from `require_role` and
  `require_access`. **106 routes carry no dependency-level guard at all** and check
  permission inside the function body instead, so an introspection-only sweep understates
  the guards; those must be read by hand. The important ones are `students.py`,
  `staff.py`, `payroll.py`, `audit.py`, `import_data.py` and `tools.py`.
- **Menus per profile:** import `hubsForUser` and `hubItemsForUser` from
  `frontend/src/lib/managementHubs.js` under Node. The imports are extensionless, so copy
  the two files to a scratch folder and add `.js` to the import specifier first.

Use the environment `backend/.venv/Scripts/python.exe` (Python 3.12). The machine's
`py -3.9` is 3.9.0 and cannot build the bcrypt and cryptography wheels.

### 4.3 Still open with Abhimanyu

- Has migration `031` run in production, and what do the live login rows actually say?
  R2-11 must not be attempted until this is answered by reading, not assuming.
- Who may message whom from Release 5 onward (teachers), and Release 6 (students)?
  Needed before Release 5, not during it.
- After R2-2, is the paid / unpaid flag wanted on Lalit's student screens as a visible
  field, or only not-forbidden?

---

## Change log for this document

| Date | Change |
|---|---|
| 2026-08-10 | Created after the audit. Decisions 1-4 recorded. |
| 2026-08-10 | Revised after Abhimanyu's answers: transport returns to Sonu as a contingency and Chaman Singh's profile is built dormant (3); Sonu may create students (5); certificates and ID cards need approval before printing (6); logins rename to sonu.ruhal / lalit.thomas (7); staff messaging added as R2-10 (8). Added Part 4 so any agent can resume. |
| 2026-08-10 (later) | Decision 7 widened to all four logins including Aman and Adesh, with display names, so Adesh reads "Adesh Singh". R2-11 rewritten and now carries a lock-out warning. R2-7 settled: Sonu and Lalit keep the same nine department group names Aman and Adesh see, empty groups simply do not appear, and no per-person vocabulary is invented. |
