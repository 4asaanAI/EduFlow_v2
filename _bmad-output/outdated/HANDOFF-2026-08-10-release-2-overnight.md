# Handoff — Release 2, overnight run, 2026-08-10

**Give this whole file to the next agent.** It is written to be pasted or opened cold.

---

## Who you are and what this is

You are continuing work on **EduFlow**, a chat-first school management platform built by
**Layaa AI** for **The Aaryans**, a CBSE school in Joya, Amroha, Uttar Pradesh. One branch,
1,876 students on the roll (1,842 active). React frontend on AWS Amplify, FastAPI backend on
Elastic Beanstalk, MongoDB Atlas, Azure OpenAI behind the assistant called **Flo**.

**Abhimanyu** is the founder of Layaa AI. He commissions this work and approves deploys. He
has gone to sleep and wants progress by morning. He is **not** the school's owner: in this
codebase `owner` means **Aman Litt**, who runs the school. Never write "you" to Abhimanyu
about something an `owner` can do; say "the school's owner".

The four people this release is about:

| Person | Role in the school | Platform profile | Login today |
|---|---|---|---|
| Aman Litt | Owner | `owner` | `Aman Litt` |
| Adesh Singh | Principal | `admin` / `principal` | `Adesh` |
| Sonu Ruhal | Accountant head | `admin` / `accountant` | `accountant` |
| Lalit Thomas | Management, day-to-day data | `admin` / `management` | `management` |

Hierarchy the school asked for: **Aman > Adesh > Sonu > Lalit.**

---

## Read these three files before you write any code

1. `_bmad-output/implementation-artifacts/release-2/PROGRESS.md` — **the only record of what
   is done.** Read first, update last, every single run.
2. `_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md` — the audit,
   the settled decisions, sub-parts R2-0 to R2-19, order, sizing, cold-resume notes.
3. `CLAUDE.md` — the project's standing rules. They are not optional.

Branch: **`release-2-person-profiles`**, already checked out, six commits, nothing pushed.

---

## The one thing to understand

Sonu's and Lalit's permissions are granted today by **subtraction**. "Management" is defined
as *everything not tagged finance*, in `frontend/src/lib/toolPermissions.js` and at the
bottom of `backend/ai/tool_functions_v2.py`. **Nothing anywhere states what either of them
is supposed to have.**

That is why Lalit can currently read every teacher's salary, see the school's fee totals,
open and close the accounting posting lock, edit expenses, and run the year-end promotion
that moves every student up a class. It is also a permanent leak: anything built next month
lands in his hands by default and nobody notices.

**Do not patch the symptoms one at a time.** R2-1 replaces subtraction with one written-down
grant table, default deny, read by the menu, the server and Flo alike.

---

## Your goal tonight, in priority order

Abhimanyu wants to hand credentials to all four people when he wakes. **That is only safe
once the permission work is done and proven.** So the order below is deliberately safety
first, and the fee loading, which he also wants, comes after. Do not reorder it.

### Priority 1 — R2-3, close the owner-only hole (smallest, highest severity)

`backend/services/ai_action_policy.py:70-80`, called from `backend/ai/tool_access.py:33-35`.
The profile decision returns first and short-circuits the registry's own `roles` check. It
only tests whether `roles` *intersects* `{owner, admin}`, so a tool marked `roles=["owner"]`
passes and the domain check then hands it to Lalit.

Twelve tools are reachable that should not be, including **`year_end_transition`**,
`create_branch`, `update_branch`, `delete_branch`, `update_school_settings`. Sonu gets the
finance equivalents: `create_legal_entity`, `delete_legal_entity`, `set_default_legal_entity`.

Fix: honour the registry's `roles` list. Owner-only stays owner-only whatever the domain
says. Add a test asserting that for every owner-only tool, all eight non-owner profiles are
refused.

### Priority 2 — R2-1, the permission matrix

Create `backend/services/profile_matrix.py` plus a generated JS mirror the frontend imports.
Every entry names screen ids, Flo tool names, route groups, and read versus write. **Default
deny.**

**All nine profiles go in, not four.** `middleware/auth.py:89-97` recognises eight admin
sub-categories: principal, accountant, transport_head, receptionist, it_tech, maintenance,
management, support_staff. A matrix naming only the four in this release silently strips the
others. The five below Lalit are drafted in
`_bmad-output/planning-artifacts/staff-profiles-draft-for-aman-2026-08-10.md`, **await Aman's
confirmation, and stay dormant.** If his answers have not arrived, build the four live
profiles and leave the five as clearly labelled stubs. Do not guess.

Prefer a checked-in generated mirror with a drift test over a build step: Jest and Vite then
do not have to learn to run Python. The drift test is the point.

This sub-part is a **refactor**: the measured numbers must not move. See "How to check
yourself" below.

### Priority 3 — R2-2, close the nine money leaks to Lalit

All nine are listed in plan §1.3 with file and line references. Briefly:

1. **School Pulse** (`SchoolPulse.js:103-104,176-177`) shows "Fees Collected" and "Overdue
   Fees" in rupees.
2. **Smart Alerts** (`OwnerTools.js:1497`) shows overdue fees.
3. `GET /api/fees/class-summary`
4. `GET /api/fees/status/{student_id}`
5. `GET /api/fees/discounts/{student_id}`
6. `GET /api/accounting/periods`
7. `PATCH /api/accounting/periods/{id}/status` — he can open or close the posting lock
8. `PATCH /api/ops/expenses/{id}` — he can edit an expense
9. `GET /api/staff/{staff_id}` (`routes/staff.py:556-565`) returns **salary**. The list
   strips it with a projection; the single record does not.

For 1 and 2, build a **non-finance variant** rather than hiding the screen: Lalit still needs
the attendance and staffing half of both. For 4, return the paid or unpaid **flag** with
amounts stripped and surface that flag on his student screens (decision 1). For 9, drop
`salary` at the response boundary for anyone who is not owner, principal or accountant.

**Aman and Adesh must both see everyone's salary** (Abhimanyu, 2026-08-10). Today the
principal is *excluded* from payroll by `_require_owner_or_accountant` in
`routes/payroll.py:43`, which is a bug in the other direction. Fix it here or in R2-6.

Three separate acceptance checks, because no single test can do this:
- routes: Lalit gets 403 on items 3 to 8, and no `salary` key on item 9;
- payloads: the fee-status response has the flag and no amount field, asserted **by key
  name**, never by grepping for a rupee sign;
- screens: render School Pulse and Smart Alerts as Lalit and assert the money tiles are gone.

### Priority 4 — R2-4, people records

Lalit may add and edit students and staff. He may **not** delete them and may **not** create
or reset any login. Sonu may create students too.

`DELETE /api/students/{id}` and `DELETE /api/staff/{id}` currently check only
`role in ADMIN_ROLES` (`students.py:103`, `staff.py:108`), which is any admin. Move the
guard into the service so the screen and Flo inherit one answer. Remove
`create_student_login` and `set_profile_password` from Lalit.

### Priority 5 — R2-13, the proof

One test walking **all nine profiles** across all three surfaces: menus, routes, and all 161
Flo tools. It asserts the matrix and fails when a new tool or screen is added without an
owner. This is the thing that keeps Releases 3 to 7 honest.

### If you still have time — R2-6, R2-7, R2-8

Dead buttons, menu grouping, Flo briefs. Details in the plan. **Lower priority than
everything above**; do not start them at the cost of Priority 1 to 5.

---

## The settled decisions. Do not re-open these.

1. **Lalit and money.** He sees a paid or unpaid flag, as a visible field. He never sees a
   rupee figure anywhere.
2. **Sonu.** Staff attendance and leave read-only, student attendance read-only, full
   directory read plus his own columns, vendor records in full, and transport in full until
   Release 3. Lalit loses vendors and transport.
3. **Transport head profile** is built now for Chaman Singh and stays dormant until
   Release 3.
4. **Lalit and people.** Add and edit yes. Delete no. Logins no.
5. **Sonu may create students**, alongside Aman and Adesh.
6. **Certificates and ID cards.** Aman and Adesh issue directly. **Sonu and Lalit create and
   wait for approval.**
7. **Logins.** Only two change: `accountant` → `sonu.ruhal`, `management` → `lalit.thomas`.
   **Aman's login is not touched.** Adesh gains "Singh". Passwords unchanged for everyone.
   Migration 031 declares the dotted form for all four; the file is wrong and the instruction
   wins. **This is R2-11 and it is deliberately last: do not do it tonight.**
8. **Staff messaging.** Every employee becomes reachable in the platform's staff chat as
   releases land.
9. **Aman and Adesh see everyone's salary.**
10. **All nine profiles get proper definitions**, dormant until their release.
11. **Passwords stay guessable** (`owner@123`, `admin@123`, `accountant@123`,
    `management@123`). Abhimanyu was offered strong replacements and declined, knowingly.
    **Do not change them.** It would lock him out of the accounts he uses to check the work.

---

## What is already correct. Do not "fix" these.

- **Password resets are already safe.** `account_management_service.py:237-240` limits
  management to *student* passwords, and nobody but the owner may change an owner's. An
  early read of the tool registry suggested otherwise; reading the service proved it wrong.
- **Salary edits are already blocked.** `salary` is in `staff_service.OWNER_ONLY_FIELDS`.
- **Spreadsheet import is already scoped per profile** and reports out-of-segment columns
  rather than dropping them.
- **The certificate *record* flow already requires approval**
  (`certificate_service.py:41-75`). Only the *printing* path (`routes/image_gen.py`) does
  not. Extend, do not rebuild.
- **The directory screens carry no money fields at all.**
- **The five profiles below Lalit have zero write tools today.** Whatever you do, do not be
  the change that gives them writes.

---

## Traps that have already caught someone

- **The platform has eight admin sub-categories, not four.** A default-deny matrix covering
  only the ones under discussion silently strips receptionist, IT, maintenance and support
  staff. Always sweep all nine profiles.
- **106 of 483 routes check permission inside the handler body**, not through a FastAPI
  dependency. Any sweep that only introspects dependencies understates the guards and will
  draw the wrong conclusion. The ones that matter here are `students.py`, `staff.py`,
  `payroll.py`, `audit.py`, `import_data.py`, `tools.py`.
- **The certificate approval list and the certificate printer use different words for the
  same documents.** Approval knows `bonafide, tc, transfer_certificate, character, merit`;
  the printer knows `transfer, bonafide, character, sports, participation, migration`. Only
  two overlap, so `transfer` never matches `transfer_certificate` and a naive fix passes
  Transfer Certificates through unapproved. Relevant to R2-9, not tonight.
- **Two unrelated messaging systems.** `routes/messaging.py` is staff-to-staff chat.
  `routes/parent_messaging.py` sends WhatsApp and SMS to families. Do not confuse them.
- **`support_staff` has no menu list at all**, so it falls through to most of the admin menu.

---

## How to check yourself

Two committed, read-only scripts measure everything. **Run them before you start and after
every sub-part, and explain every number that moved.** A number that moved and was not
intended is a defect.

```bash
backend/.venv/Scripts/python.exe scripts/audit_profile_reach.py   # Flo tools + API routes
node scripts/audit_profile_menus.mjs                              # hub menus
```

Baseline, measured 2026-08-10 before any change:

| Profile | Flo tools | writes | API routes | Hubs | Hub screens |
|---|---|---|---|---|---|
| owner | 155 | 100 | 350 | 9 | 56 |
| principal | 155 | 100 | 336 | 9 | 57 |
| accountant | 48 | 29 | 266 | 2 | 11 |
| management | 112 | 71 | 221 | 7 | 37 |
| transport_head | 32 | 0 | 189 | 0 | flat list |
| receptionist | 32 | 0 | 205 | 0 | flat list |
| it_tech | 32 | 0 | 190 | 0 | flat list |
| maintenance | 32 | 0 | 189 | 0 | flat list |
| support_staff | 31 | 0 | 189 | 0 | falls through |

Both scripts print their own limits. Read them before quoting a number.

Gates, and the bar is **0 failures** in each. Never pin a pass count.

```bash
MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test \
  python -m pytest tests/backend/ -q
cd frontend && CI=true npx jest
cd frontend && npm run build      # lint runs first; one warning fails the deploy
```

---

## Rules you must not break

1. **Never modify the live school database.** Read-only access was approved for a specific
   audit that is finished. Any write needs Abhimanyu's explicit approval, and he is asleep.
2. **Never run `backend/migrations/run_all.py`.** One migration at a time, after reading it.
   Six of them insert convincing fake data into what they assume is a demo school.
3. **Do not deploy.** Deploys need the `claude-hosting` IAM user and Abhimanyu's approval.
4. **No TypeScript.** `.js` and `.jsx` only.
5. **`from __future__ import annotations` is the first line** of any Python file using
   `str | None`, or the file fails at collection and its tests silently skip.
6. **No `pytestmark = pytest.mark.asyncio`** in test files; `asyncio_mode = auto` handles it.
7. **Every new endpoint needs two tests**: unauthenticated returns 401, wrong role returns
   403.
8. **Never put a password in the repository.**
9. **Write to Abhimanyu in plain, non-technical language.** He relays it to the school. Be
   just as direct about failures, only in everyday words.
10. **Update `PROGRESS.md` before the session ends, even if the run failed.** A run that
    changed code and left it untouched is an incomplete run.

---

## Not tonight

- **R2-11**, the login rename. Last on purpose: it revokes sessions.
- **Loading the fee structure.** Abhimanyu has approved the write, but `aaryans_database/`
  holds **eight unreconciled fee documents**, including
  `Transport-Fees-Structure-Report-Summary-06-08-2026-16-58.pdf` and
  `Ledger-Report-06-08-2026-01-03.xlsx`. They must be read and reconciled against the
  official fee sheet transcribed in plan R2-16 first. A wrong fee structure reaches 1,842
  families. This is a fresh-session job with Abhimanyu awake.
- **Anything touching production.**

---

## What to leave for the morning

Write these in `PROGRESS.md` and say them plainly:

1. Which sub-parts you finished, and the measured numbers before and after.
2. **Your honest answer to: is it now safe to give Sonu and Lalit their credentials?** That
   is the decision Abhimanyu wants to make when he wakes. If Priorities 1 to 4 are not done
   and green, the answer is no, and say so rather than softening it.
3. Anything you found that contradicts this handoff. Documents go stale; the code is the
   truth.

---

## Context Abhimanyu will want in the morning

Facts established 2026-08-10 by an approved read-only pass on the live database, which he
already knows but the next agent may need:

- **1,898 login accounts exist and every one is active**: 1,802 students, 88 teachers, 8
  owner and admin desks. `routes/auth.py:190` has **no role gate**, so the release ladder is
  held up by nothing except nobody having handed out passwords.
- **The platform never records that anyone logged in.** `last_login` is written nowhere.
- Both office accounts have **zero audit entries**, so nobody has acted through them.
- **Migration 031 has not run.**
- **`fee_structures` is empty.** 1,844 students carry a `fee_snapshot` whose own `source`
  field says *"NOT the fee ledger"*. The seven sibling concessions are loaded and correct.
  One payment transaction exists for the whole school.
