# Release 2 — live progress log

**This file is the only record of what is done.** The plan says what the work is; this
says where it stands. Update it at the end of every run, before the session ends, even if
the run failed. A run that changed code and left this file untouched is an incomplete run.

- **Plan:** `_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md`
- **Branch:** `release-2-person-profiles` (created 2026-08-10)
- **Started:** 2026-08-10

---

## Read this first if you are picking the work up

1. Read the plan document: all of Part 1 (what is broken) and Part 4 (working notes).
2. Read the status table below and take the topmost sub-part that is `NOT STARTED`,
   unless the order in the plan's Part 3 says otherwise.
3. Confirm the baseline before you touch anything:
   ```bash
   MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test \
     python -m pytest tests/backend/ -q          # bar is 0 failed
   cd frontend && CI=true npx jest               # bar is 0 failed
   cd frontend && npm run build                  # lint runs first; a warning fails the deploy
   ```
4. Take the "before" measurement, so you can explain every number you move:
   ```bash
   backend/.venv/Scripts/python.exe scripts/audit_profile_reach.py
   node scripts/audit_profile_menus.mjs
   ```
5. Do one sub-part. Not two.
6. Re-run step 4. **Every number that moved must be explained in your session entry.**
   A number that moved and was not intended is a defect, not a detail.
7. Write what you did in the session log at the bottom, update the status table, and say
   plainly what is left.

**Never assume a finding in the plan is still true without re-reading the file it names.**
The plan records line numbers as of 2026-08-10; the work itself moves them.

---

## Baseline measured 2026-08-10, before any change

The bar for every sub-part except the ones that deliberately move a number.

| Profile | Flo tools | writes | API routes | Hubs | Hub screens |
|---|---|---|---|---|---|
| owner | 155 | 100 | 350 | 9 | 56 |
| principal | 155 | 100 | 336 | 9 | 57 |
| accountant | 48 | 29 | 266 | 2 | 11 |
| management | 112 | 71 | 221 | 7 | 37 |
| transport_head | 32 | 0 | 189 | 0 | flat list, 6 |
| receptionist | 32 | 0 | 205 | 0 | flat list, 9 |
| it_tech | 32 | 0 | 190 | 0 | flat list, 4 |
| maintenance | 32 | 0 | 189 | 0 | flat list, 3 |
| support_staff | 31 | 0 | 189 | 0 | flat list, falls through to most of the admin menu |

Registry: 161 Flo tools. API: 483 routes, of which 106 check permission inside the handler
body and are counted as unreachable by the script, so the route column understates reach.

---

## Status

| Sub-part | What it is | Status | Notes |
|---|---|---|---|
| R2-0 | Who can log in right now | **MOSTLY ANSWERED** | **The `accountant` and `management` accounts ARE live.** Part 1 is a present condition, not a plan. Three reading tasks left; they block R2-11. |
| R2-1 | The permission matrix (one source of truth) | NOT STARTED | All nine profiles, properly defined. The five below Lalit need Aman's answers first. |
| R2-2 | Close the nine money leaks to Lalit | NOT STARTED | Biggest block. Plan §1.3. Three separate acceptance checks. |
| R2-3 | Close the owner-only hole in Flo | NOT STARTED | Smallest, highest severity. Plan §1.4. |
| R2-4 | People records: add/edit yes, delete/logins no | NOT STARTED | Plan §1.5, decisions 4 and 5. |
| R2-5 | Sonu's full remit | NOT STARTED | Attendance read, vendors, transport, create students. |
| R2-6 | Fix the dead buttons, Adesh and support staff | NOT STARTED | Payroll for Adesh (§1.8); support staff has no menu list at all (§1.10). |
| R2-7 | One vocabulary: same department groups for everyone | NOT STARTED | Pairs with R2-8. Do NOT invent per-person group names. |
| R2-8 | Flo briefs per person | NOT STARTED | Pairs with R2-7. |
| R2-9 | Certificates and ID cards need approval before printing | NOT STARTED | Read plan §1.6 twice. The two systems use different words for the same documents. |
| R2-10 | Staff messaging: a real colleague directory | NOT STARTED | Diagnose RECONNECTING before fixing. May be infrastructure. |
| R2-11 | Rename the two office logins, plus Adesh's display name | **BLOCKED** | On R2-0's reading tasks. Scope shrank 2026-08-10: only `accountant` → `sonu.ruhal` and `management` → `lalit.thomas`. **Aman's login is not touched.** Do not widen it back out. |
| R2-12 | Transport head profile for Chaman Singh, dormant | NOT STARTED | He exists in staff already; no login. |
| R2-13 | The proof: all-nine-profile sweep test | NOT STARTED | Nine, not four. The only thing guarding the five dormant profiles from silently losing or gaining access. |
| R2-14 | Accounts, handover, go-live | NOT STARTED | Definition of done is in the plan, R2-14. |

Statuses: `NOT STARTED` · `IN PROGRESS` · `BUILT, GATE GREEN` · `DEPLOYED` · `BLOCKED`.
`BLOCKED` must name what it is blocked on and who can unblock it.

---

## Open questions

| # | Question | Blocks | Asked | Answered |
|---|---|---|---|---|
| 1 | **Aman:** the nine questions in `staff-profiles-draft-for-aman-2026-08-10.md`, covering the five profiles below Lalit. | The five dormant profiles in R2-1 and R2-6. Not the four live ones. | 2026-08-10 | — |
| 2 | **Abhimanyu:** who may message whom from Release 5 (teachers) and Release 6 (students)? | Release 5, not R2-10 | 2026-08-10 | — |
| 3 | **Reading task, needs approval to look:** has 031 run in production, have the two accounts been used by anyone but Abhimanyu, and what are Aman's and Adesh's exact login strings? | R2-11 | 2026-08-10 | — |
| ~~4~~ | ~~Decision 9: Sonu's certificate rights~~ | ~~R2-9~~ | 2026-08-10 | **Yes.** Sonu and Lalit both create-and-await-approval; Aman and Adesh issue directly. |
| ~~5~~ | ~~Decision 10: freeze the other four profiles?~~ | ~~R2-1~~ | 2026-08-10 | **No, define them properly now.** Drafted for Aman; dormant until their release. |
| ~~6~~ | ~~R2-0: are the accounts live?~~ | ~~everything~~ | 2026-08-10 | **Yes, both are live.** See the note below. |

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
- **The four profiles below Lalit have zero write tools**, and Release 2 must not be what
  gives them any. Pinned by R2-13.
- **Passwords do not change for anyone, and that is a decision, not an omission.** They
  are guessable (account name plus `@123`) and Abhimanyu was offered strong replacements
  on 2026-08-10 and declined, knowingly, while only he holds them. Do not quietly "fix"
  this: it would lock him out of the accounts he uses to check the work. Raise it again at
  R2-14, when the school is about to be given the address. Plan, decision 11.
  *(Two usernames change in R2-11: `accountant` → `sonu.ruhal` and `management` →
  `lalit.thomas`. **Aman's login is not touched**, and Adesh gains "Singh". Migration 031
  declares the dotted form for all four; the file is wrong and Abhimanyu's instruction
  wins.)*

---

## Session log

Newest last. One entry per run. Say what you did, what you proved, and what you left.

### 2026-08-10 — audit and plan (Claude, Opus 5)

**Did.** Full audit of who can reach what across three surfaces: the hub menus, all 483
API routes, and all 161 Flo tools, for every one of the nine profiles the platform
recognises. Wrote the plan and this log. Investigated the empty Messages screen from
Abhimanyu's screenshots and found the cause. Committed both audit scripts. Moved seven
superseded handoff notes and two stale root documents into `_bmad-output/outdated/`.

**Proved.** Every number in the baseline table above came out of
`scripts/audit_profile_reach.py` and `scripts/audit_profile_menus.mjs`, which anyone can
re-run. Every defect in plan §1.2 through §1.8 was read in the file named.

**Left.** No production code changed. Nothing deployed. R2-0 is the next thing to do, and
it is a question rather than a change. Four questions are open with Abhimanyu.

**Watch out for.**
- The route sweep **understates** the guards: 106 routes check permission inside the
  handler body rather than through a dependency. A future sweep that only introspects
  dependencies will draw the wrong conclusion.
- The menu sweep covers **hubs only**. A zero for the bottom five profiles means "no hubs",
  not "no screens"; they come from a different list in `Sidebar.js`.

### 2026-08-10 — adversarial review of the plan (Claude, Opus 5)

**Did.** Reviewed both documents adversarially and folded nineteen findings back in. No
production code changed; the two audit scripts under `scripts/` were added.

**Found, worst first.**
1. **The plan never asked whether Sonu's and Lalit's logins are already live.** It was
   written as though Release 2 has not happened, on the strength of a passing remark. If
   `accountant` and `management` are enabled accounts, everything in Part 1 is present
   exposure. This became **R2-0** and now blocks everything.
2. **A default-deny matrix covering four profiles would have silently stripped four
   others.** The platform recognises eight admin sub-categories. Receptionist, IT,
   maintenance and support staff were nowhere in the plan, and the proof step tested four
   profiles, so nothing would have caught it. Now §1.10, decision 10, and R2-13 covers all
   nine.
3. **R2-9 would have passed Transfer Certificates through unapproved.** The approval list
   and the printer use different words for the same documents and only two strings overlap:
   the printer's `transfer` does not match `transfer_certificate`. "Apply the same rule"
   looked like a copy-paste and was a trap. §1.6 now spells it out and R2-9 reconciles the
   vocabulary first.

**Also fixed.** Sonu's certificate rights were undefined (now decision 9, awaiting a yes).
R2-11 had a warning where it needed a rollback and a rehearsal. R2-2's acceptance criterion
could not be tested as written and is now three checks. R2-10 fixed a symptom before
anyone had diagnosed it. §1.2 said 12 rows by eye; the measured number is 18. The writes
column was filled for one profile out of nine. The scripts were described rather than
committed. No sizing, no definition of done, nobody named to sign off, and nothing said
where any of this is verified given there is no staging environment.

**Left.** Both documents rewritten. R2-0 is still the next thing to do.

### 2026-08-10 — Abhimanyu's answers, and R2-0 comes back live (Claude, Opus 5)

**Did.** Put the three open questions to Abhimanyu and folded the answers into both
documents. Drafted the five staff profiles below Lalit for Aman to confirm, in
`_bmad-output/planning-artifacts/staff-profiles-draft-for-aman-2026-08-10.md`.

**The answer that matters. The `accountant` and `management` accounts are LIVE.** The
screenshot that started this work was taken by logging into the management account. So
everything in plan Part 1 describes a present condition, not a future risk: those two
logins reach the nine money leaks in §1.3 and the owner-only tools in §1.4 today. Right now
Abhimanyu alone holds them. It does not change the order of work; it changes how the
findings read.

**Passwords stay as they are.** Guessable, on a public login page, guarding 1,876
children's records. Abhimanyu was offered strong replacements and declined knowingly.
Login locks out after 5 wrong tries for 15 minutes (`routes/auth.py:55-56`), so the
exposure is the guessability of two specific strings and nothing else. **Recorded as an
accepted risk, to be raised again at R2-14 (handover), and not to be quietly reversed.**

**The other two answers.** Certificate approval now follows the hierarchy exactly: Aman and
Adesh issue directly, Sonu and Lalit create and wait. And the five profiles below Lalit get
proper definitions now rather than being frozen until Release 4, which reverses the
proposal in the previous entry. They are built and tested now and stay dormant until each
one's release; defining is not switching on.

**Left.** Nothing to build until Aman answers the nine questions in the draft, for the five
dormant profiles. The four live profiles are unblocked, so R2-1 can start on those. Three
reading tasks remain in R2-0 and they block R2-11; all three need approval to look at the
live database.

### 2026-08-10 — final credentials, and R2-11 shrinks (Claude, Opus 5)

**Did.** Recorded the final credential state and cut R2-11 down to match it.

**The change.** Only the two office logins move: `accountant` → `sonu.ruhal` and
`management` → `lalit.thomas`. **Aman's login is not touched.** Adesh gains "Singh".
Passwords unchanged for all four. This reverses the earlier "all four move to the dotted
form migration 031 declares".

**Why that is good news.** Aman and Adesh are the only two people using the platform today,
so a rename that skips them removes almost all of the lock-out risk that made R2-11 the
scariest step. R2-11 went from a day to half a day. **Do not widen it back out for
tidiness**, and expect to be tempted, because migration 031 does declare `aman.litt` and
`adesh.singh`. The file and the instruction disagree, and the instruction wins.

**Caught while doing it.** I had written the four actual passwords into the plan document.
Removed before committing. The passwords add nothing for anyone implementing this, they
follow an obvious pattern, and git history is permanent. The rule is now written into
decision 7: login strings in the repo, passwords never.

**Left.** Unchanged from the entry above.
