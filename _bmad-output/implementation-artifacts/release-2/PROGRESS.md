# Release 2 — live progress log

**This file is the only record of what is done.** The plan says what the work is; this
says where it stands. Update it at the end of every run, before the session ends, even if
the run failed. A run that changed code and left this file untouched is an incomplete run.

- **Plan:** `_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md`
- **Branch:** `release-2-person-profiles` (not yet created)
- **Started:** 2026-08-10

---

## Read this first if you are picking the work up

1. Read the plan document, all of Part 1 (what is broken) and Part 4 (working notes).
2. Read the status table below and take the topmost sub-part that is `NOT STARTED`,
   unless the order in the plan's Part 3 says otherwise.
3. Confirm the baseline before you touch anything:
   ```
   MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test \
     python -m pytest tests/backend/ -q          # bar is 0 failed
   cd frontend && CI=true npx jest               # bar is 0 failed
   cd frontend && npm run build                  # lint runs first; a warning fails the deploy
   ```
4. Do one sub-part. Not two.
5. Write what you did in the session log at the bottom, update the status table, and say
   plainly what is left.

**Never assume a finding in the plan is still true without re-reading the file it names.**
The plan records line numbers as of 2026-08-10; the work itself moves them.

---

## Status

| Sub-part | What it is | Status | Notes |
|---|---|---|---|
| R2-1 | The permission matrix (one source of truth) | NOT STARTED | Everything else depends on it. Do first. |
| R2-2 | Close the nine money leaks to Lalit | NOT STARTED | Biggest block. Plan §1.3 lists all nine. |
| R2-3 | Close the owner-only hole in Flo | NOT STARTED | Smallest, highest severity. Plan §1.4. |
| R2-4 | People records: add/edit yes, delete/logins no | NOT STARTED | Plan §1.5, decisions 4 and 5. |
| R2-5 | Sonu's full remit | NOT STARTED | Attendance read, vendors, transport, create students. |
| R2-6 | Fix the principal's dead buttons | NOT STARTED | Payroll is the known one. Plan §1.8. |
| R2-7 | Per-person menu layouts | NOT STARTED | Pairs with R2-8. |
| R2-8 | Flo briefs per person | NOT STARTED | Pairs with R2-7. |
| R2-9 | Certificates and ID cards need approval before printing | NOT STARTED | Record side already does this. Plan §1.6. |
| R2-10 | Staff messaging: a real colleague directory | NOT STARTED | Largest unknown. Plan §1.7. |
| R2-11 | Rename ALL FOUR logins to the 031 form, with display names | NOT STARTED | Late on purpose: logs Aman and Adesh out. Blocked on the 031 question. |
| R2-12 | Transport head profile for Chaman Singh, dormant | NOT STARTED | He exists in staff already; no login. |
| R2-13 | The proof: four-profile sweep test | NOT STARTED | Write alongside each step; run whole here. |
| R2-14 | Accounts, handover, go-live | NOT STARTED | |

Statuses: `NOT STARTED` · `IN PROGRESS` · `BUILT, GATE GREEN` · `DEPLOYED` · `BLOCKED`.
`BLOCKED` must name what it is blocked on and who can unblock it.

---

## Blocked on Abhimanyu

| # | Question | Blocks | Asked |
|---|---|---|---|
| 1 | Has migration `031` run in production, and what do the live login rows say? | R2-11 | 2026-08-10 |
| 2 | Who may message whom from Release 5 (teachers) and Release 6 (students)? | Release 5, not R2-10 | 2026-08-10 |
| 3 | Should the paid / unpaid flag be a visible field on Lalit's student screens, or merely not-forbidden? | R2-2 finishing touch | 2026-08-10 |

---

## What must not be broken

Verified working on 2026-08-10. If a change makes one of these fail, the change is wrong.

- Management can change **only student** passwords, and nobody but the owner may change
  an owner's (`services/account_management_service.py:237-240`).
- `salary` is in `staff_service.OWNER_ONLY_FIELDS` and stripped for every non-owner.
- Spreadsheet import is column-scoped per profile and reports out-of-segment columns
  rather than dropping them (`services/data_import_service.py`).
- The certificate **record** flow already sends non-leadership requests to
  `pending_approval` with a notification (`services/certificate_service.py:41-75`).
- School Directory, Student Database and Staff Tracker contain no money fields.
- *(Superseded 2026-08-10: Aman's and Adesh's usernames DO change in R2-11, to
  `aman.litt` and `adesh.singh`. Passwords still do not change, for anyone.)*

---

## Session log

Newest last. One entry per run. Say what you did, what you proved, and what you left.

### 2026-08-10 — audit and plan (Claude, Opus 5)

**Did.** Full audit of who can reach what across three surfaces: the sidebar and hub
menus, all 483 API routes, and all 161 Flo tools, for owner, principal, accountant and
management. Wrote the plan document and this log. Investigated the empty Messages screen
from Abhimanyu's screenshots and found the cause.

**Proved.** The numbers in the plan's §1.1 table were measured, not estimated; §4.2 says
how to reproduce them. Every defect in §1.2 through §1.8 was read in the file named.
Two early suspicions were checked and turned out to be wrong, and are recorded in §1.9 as
things not to "fix": management cannot reset the owner's password, and cannot edit salary.

**Left.** No code changed. Nothing deployed. R2-1 is the next thing to do. Three
questions are open with Abhimanyu, listed above.

**Watch out for.** The audit's route sweep understates the guards, because 106 routes
check permission inside the function body rather than through a dependency. Those were
read by hand for the files that matter to this work, but a future sweep that only
introspects dependencies will draw the wrong conclusion.
