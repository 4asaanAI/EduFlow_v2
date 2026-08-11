# Release 2 — live progress log

**This file is the only record of what is done.** The plan says what the work is; this
says where it stands. Update it at the end of every run, before the session ends, even if
the run failed. A run that changed code and left this file untouched is an incomplete run.

- **Plan:** `_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md`
- **Branch:** `release-2-person-profiles` (created 2026-08-10)
- **Started:** 2026-08-10

---

## ▶ NEXT SESSION STARTS HERE

**Read the LAST session entry at the bottom of this file first.** The permission
sub-parts are done and green (R2-1 to R2-6, R2-12, R2-13), and **R2-9 is now done too**.
The fee ledger below still needs Abhimanyu awake.

**Every permission sub-part is now built and green, R2-11 included and applied live.**
What is left is the fee ledger, R2-19, the deploy and R2-14 (handover).

**The measured table below is the 2026-08-10 baseline and is out of date in several
places, all of them deliberate.** The current numbers, measured 2026-08-11 at the end of
the fourth run:

| Profile | Flo tools | writes | API routes | Hubs | Hub screens |
|---|---|---|---|---|---|
| owner | 155 | 100 | 354 | 9 | 57 |
| principal | 155 | 100 | 340 | 9 | 58 |
| accountant | **57** | **32** | 272 | 6 | 19 |
| management | 98 | 59 | 224 | 7 | 39 |
| transport_head | 28 | 0 | 191 | 0 | flat list |
| receptionist | 28 | 0 | 207 | 0 | flat list |
| it_tech | 28 | 0 | 192 | 0 | flat list |
| maintenance | 28 | 0 | 191 | 0 | flat list |
| support_staff | 27 | 0 | 191 | 0 | flat list |

Registry still 161 Flo tools. **API routes 483 to 487** (the ID-card approval request,
the daily digest and the two undo routes), which is why every profile's route count is
up by three or four on the 2026-08-10 baseline. The accountant head's +1 tool and +1
write is `update_staff`, salary only, explained in the last session entry. No dormant
profile has gained anything at any point.

**Do this next: `FINISHING-PLAN-2026-08-11.md`, in this folder, step 1.**

That document replaces the five bullets that used to sit here. It breaks everything left
in Release 2 into eleven steps, says what each needs from a person, and says what is
blocked and on whom. The fee rules themselves are settled and written down separately in
`fee-rules-from-sonu-2026-08-11.md`, which is the authority on how the school charges.

The short version: **steps 1 to 9 are the fee ledger**, step 10 is Flo parity (R2-19),
step 11 is the deploy and handover (R2-14). Step 1 reconciles nine documents and writes
nothing, so it needs no approval. Late fines are held to step 9 on Abhimanyu's explicit
instruction, so that a wrong fine never reaches a family while the rest is being settled.

Everything else in this file still applies.

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
| R2-0 | Who can log in right now | **✅ DONE** | Read from the live database 2026-08-10. **1,898 accounts, ALL active**, including 1,802 students and 88 teachers. Login has no role gate. Migration 031 has not run. Plan R2-0 has the full table. |
| R2-19 | Flo can do the fee work too | NOT STARTED | Abhimanyu, 2026-08-10: anything done by hand, Flo must do on request. Parity tests required. |
| R2-1 | The permission matrix (one source of truth) | **✅ BUILT, GATE GREEN** | `backend/services/profile_matrix.py` + checked-in JS mirror + drift test. All nine profiles. Default deny. Commit `72a4bed`. |
| R2-2 | Close the nine money leaks to Lalit | **✅ BUILT, GATE GREEN** | Only THREE of the nine were still open; four were already closed and one was the opposite of a leak. Commits `7893726`, `2f6eb4b` (the flag on screen). |
| R2-3 | Close the owner-only hole in Flo | **✅ BUILT, GATE GREEN** | Commit `6a90cff`. The handoff's "all eight non-owner profiles" was wrong about the principal; see the session entry. |
| R2-4 | People records: add/edit yes, delete/logins no | **✅ BUILT, GATE GREEN** | Guard in the service, so the screen and Flo give one answer. Commit `84e330d`. |
| R2-5 | Sonu's full remit | **✅ BUILT, GATE GREEN** | Attendance and leave to read, vendors, transport in full until Release 3; Lalit loses vendors and transport. Commit `5eeb553`. |
| R2-6 | Fix the dead buttons, Adesh and support staff | **✅ BUILT, GATE GREEN** | Adesh could open payroll and then be refused a payslip. Support staff closed in R2-1. Commit `ca701e5`. |
| R2-7 | One vocabulary: same department groups for everyone | **✅ BUILT, GATE GREEN** | Commit `7770ffd`. The nine names were already shared; what was missing was that a granted screen could be opened. Lalit held seven screens inside a group he did not have. |
| R2-8 | Flo briefs per person | **✅ BUILT, GATE GREEN** | Commit `7770ffd`. All five dormant briefs were wrong in both directions at once. Pinned against measured reach by `test_flo_briefs_match_reality_r2_8.py`. |
| R2-9 | Certificates and ID cards need approval before printing | **✅ BUILT, GATE GREEN** | Commit `e19a124`. The vocabulary was reconciled first and that is where the real defect was: the screen's word `transfer` was on nobody's approval list, so Transfer Certificates were auto-issued. `backend/services/certificate_types.py` is now the one place that names a document. |
| R2-10 | Staff messaging: a real colleague directory | **BUILT, GATE GREEN** | Commit `a2cde0d`. The list joined on four hardcoded usernames that do not exist in production. RECONNECTING was diagnosed, not guessed: both sides are configured correctly, so it points at the network path and cannot be confirmed from here. |
| R2-11 | Rename the two office logins, plus Adesh's display name | **DONE, LIVE** | Applied to the live database 2026-08-11 with Abhimanyu's approval, after a dry run. `accountant` -> `sonu.ruhal`, `management` -> `lalit.thomas`, Adesh's display name fixed from ALL CAPS. Aman's login untouched. **Passwords NOT changed**, so each is still the one tied to the OLD account name. Migration 033, recorded in `_migrations`. |
| R2-12 | Transport head profile for Chaman Singh, dormant | **✅ BUILT, GATE GREEN** | Defined in the R2-1 matrix, six screens, zero tool domains, zero writes, dormant. Pinned by the R2-13 sweep. Still no login, by design. |
| R2-13 | The proof: all-nine-profile sweep test | **✅ BUILT, GATE GREEN** | Found a real leak on its first run: all five dormant profiles could read the fee ledger and the action log. Commit `0c1cc9d`. |
| R2-15 | A daily digest for Aman and Adesh | **BUILT, GATE GREEN** | Commit `a2cde0d`. Gated exactly like the action log. Data plus a plain-text rendering so WhatsApp can be added later without a rewrite. |
| R2-16 | What data is still missing, and who fills it | **DONE** | Read from the live database 2026-08-11, counts only, no child named. `what-the-school-still-owes-2026-08-11.md` is the report for Aman. Four lists are entirely empty. Re-run any time with `scripts/missing_data_report.py`. |
| R2-17 | One page each for Sonu and Lalit | **WRITTEN** | `guide-for-sonu.md` and `guide-for-lalit.md` in this folder. Re-read them if any screen moves before handover. |
| R2-18 | Same-day undo of your own change | **BUILT, GATE GREEN** | Commit `a2cde0d`. The shape check found EIGHT shapes, most with no previous value at all, so it reads each row and refuses out loud rather than silently doing nothing. |
| R2-14 | Accounts, handover, go-live | NOT STARTED | Definition of done is in the plan, R2-14. Now eight items, not five. |

Statuses: `NOT STARTED` · `IN PROGRESS` · `BUILT, GATE GREEN` · `DEPLOYED` · `BLOCKED`.
`BLOCKED` must name what it is blocked on and who can unblock it.

---

## Open questions

| # | Question | Blocks | Asked | Answered |
|---|---|---|---|---|
| 1 | **Aman:** the nine questions in `staff-profiles-draft-for-aman-2026-08-10.md`, covering the five profiles below Lalit. | The five dormant profiles in R2-1 and R2-6. Not the four live ones. | 2026-08-10 | — |
| 2 | **Abhimanyu:** who may message whom from Release 5 (teachers) and Release 6 (students)? | Release 5, not R2-10 | 2026-08-10 | — |
| 3 | **Reading task, needs approval to look:** has 031 run in production, have the two accounts been used by anyone but Abhimanyu, and what are Aman's and Adesh's exact login strings? | R2-11 | 2026-08-10 | — |
| 4 | **Abhimanyu:** approval to run the empty-field scan against the live database, read-only, counts only. | R2-16 | 2026-08-10 | — |
| 5 | **The school, via Aman:** do the fee structures and balances arrive as a spreadsheet, or does Sonu type them in? Same question for transport routes. | R2-16 | 2026-08-10 | — |
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

### 2026-08-10 — four readiness gaps closed (Claude, Opus 5)

**Did.** Asked Abhimanyu what was still missing for the four profiles, and added four
sub-parts from his answers. The plan went from 14 to 18 sub-parts and from 17-22 days to
23-30.

**R2-15, Aman's daily digest.** He asked for everything on the platform to be visible to
him, and today that means remembering to open the Audit Log. A once-a-day summary of what
Sonu and Lalit changed. It reads `audit_logs` and records nothing new, so it is a reader
over data that already exists. **Not WhatsApp:** there is still no production sender.

**R2-16, what data is still missing.** Aman says only the database upload is pending, so
Abhimanyu asked for a list of which fields are empty across the roll, to hand him one list
rather than discovering gaps for six months. Also the fee structures and balances, which
Sonu cannot start without, and the transport routes. **This one needs Abhimanyu's approval
to read the live database**, read-only, counts only, never an export of children's records.

**R2-17, one page each** for Sonu and Lalit, plus Abhimanyu walking them through once.

**R2-18, same-day undo.** Lalit types all day and cannot delete, so he and Sonu get to
reverse their own change on the same day; older or somebody else's goes to Adesh.

**Checked rather than assumed.** Before writing R2-18 as if it were easy, I verified the
audit rows carry `changed_by`, `created_at` and the previous value of each field, so an
undo is a write-back. **But the shape is not consistent:** most paths use
`{field: {"previous": …, "new": …}}` and `student_service.py:393` uses
`{"previous_state": {…}}`. An undo built on an assumed shape silently does nothing on the
paths that differ, which is worse than not having one. R2-18 now says audit every write
path first.

**Left.** Two more questions for Abhimanyu, both in the table above: approval for the
read-only database scan, and whether the fee and transport data arrives as spreadsheets or
gets typed. Nothing else changed. R2-1 is still the next thing to build.

### 2026-08-10 — read the live database, and the fee ledger arrives (Claude, Opus 5)

**Did.** Abhimanyu approved a read-only pass. Ran it. Nothing was written, no password hash
was read, no child's details were printed. Also received the school's official 2026-27 fee
sheet as a photograph and checked what fee data already exists.

**The account finding, which reframes the whole initiative.** There are **1,898 login
accounts and every one is active**: 1,802 students, 88 teachers, 8 owner and admin desks.
The release ladder is enforced by nothing except nobody having handed the passwords out;
`routes/auth.py:190` has no role gate. **The platform also never records that anyone logged
in** (`last_login` is written nowhere), so a person who logs in and only reads leaves no
trace at all. Both office accounts have zero audit entries, which is the reassuring half.
Four admin logins are shared desks rather than named people. Migration 031 has not run.
Full table in plan R2-0.

**The fee finding.** `fee_structures` is **completely empty**, so Aman is right that this is
the missing piece. But 1,844 students already carry a `fee_snapshot` whose own `source`
field reads *"Students-06-08-2026 export; NOT the fee ledger"* — numbers on the platform
that nobody has vouched for. The seven sibling concessions are already loaded and match the
school's sheet to the rupee. One payment transaction exists for the entire school.
`transport_opted` is false for all 1,876 students while their snapshots carry non-zero
transport fees, so one of those two is wrong.

**Decisions taken.** Split the 11th and 12th class records into Commerce and Science, since
no stream field exists anywhere and the bands differ by 4,800 a year. Enforce the school's
fee rules rather than merely recording them (late fine, 5% early payment, strike-off flag).
Flo must be able to do all the fee work on request, which is now **R2-19**.

**Why the fee write did NOT happen this session, despite approval.** Approval stands. But
`aaryans_database/` turned out to hold **eight fee documents nobody has reconciled against
the photograph**, including `Transport-Fees-Structure-Report-Summary-06-08-2026-16-58.pdf`,
which is exactly the missing transport rate card, plus `Ledger-Report-06-08-2026-01-03.xlsx`
and six more. Writing the photo's numbers before reading those risks contradicting them,
and a wrong fee structure reaches 1,842 families. **Read the eight files, reconcile, then
write.** That is the first job of the next session.

**Left.** Fee structure prepared but not written; approval is in hand. Class split not
started. R2-1 still unbuilt.

### 2026-08-10 — overnight run: Priorities 1 to 5 (Claude, Opus 5)

## Is it safe to hand Sonu and Lalit their credentials?

**Yes, on the permission side. The five things the handoff called Priorities 1 to 5
are built and the whole suite is green.** Lalit can no longer see a single rupee
figure, cannot run the year-end promotion that moves every child up a class, cannot
take a student or a colleague off the roll, and cannot create or reset anybody's
login. Sonu can no longer create or delete the school's legal entities. Every one of
those was open when the night started, on accounts that are already live.

**Three things Abhimanyu should know before he hands the passwords over.**

1. **None of this is deployed.** It is committed on the branch and nothing has been
   pushed or released. The live school platform tonight behaves exactly as it did
   this morning, holes and all. Handing out credentials before this ships would hand
   out the old behaviour.
2. **The passwords are still the guessable ones**, by his own recorded decision. That
   was fine while only he held them. The moment two more people have them, the
   decision is worth taking again — it is item 11 in the plan and is due to be raised
   at R2-14 anyway.
3. **Sonu's remit is not finished.** R2-5 gives him attendance and leave to read,
   vendor records and transport. He can do his fee work and the student record today;
   the rest arrives in a later run. Nothing about that is unsafe, it is just
   incomplete, and he should be told rather than left to find gaps.

---

**Did.** Priorities 1 to 5 in the order given, one sub-part per commit, gates run
between each: R2-3, R2-1, R2-2, R2-4, R2-13. The fee loading was deliberately not
touched, per the handoff.

**Measured, start to finish.** Both committed scripts, before and after.

| Profile | Flo tools | writes | API routes | Hubs | Hub screens |
|---|---|---|---|---|---|
| owner | 155 → **155** | 100 → **100** | 350 → **350** | 9 | 56 |
| principal | 155 → **155** | 100 → **100** | 336 → **336** | 9 | 57 |
| accountant | 48 → **46** | 29 → **27** | 266 → **266** | 2 | 11 |
| management | 112 → **102** | 71 → **63** | 221 → **220** | 7 | 37 |
| transport_head | 32 → **27** | 0 → **0** | 189 → **188** | 0 | flat list |
| receptionist | 32 → **27** | 0 → **0** | 205 → **204** | 0 | flat list |
| it_tech | 32 → **27** | 0 → **0** | 190 → **189** | 0 | flat list |
| maintenance | 32 → **27** | 0 → **0** | 189 → **188** | 0 | flat list |
| support_staff | 31 → **26** | 0 → **0** | 189 → **188** | 0 | flat list |

**Every number that moved, and why.** No number moved that was not meant to.

- **accountant −2 tools, −2 writes** — the legal-entity create, delete and
  set-default were marked owner-only in the registry and reached him through the hole
  R2-3 closed. He gained `create_student` back (decision 5), so the net is −2.
- **management −10 tools, −8 writes** — `year_end_transition`, the three branch
  tools, `update_school_settings`, `get_branch_comparison`, `query_dashboard_summary`
  and `confirm_resolution` (R2-3), plus `create_student_login` and
  `set_profile_password` (R2-4).
- **management −1 route, and −1 for each of the five dormant profiles** — the
  per-class fee summary was open to *every* admin desk. The three people who need it
  keep it.
- **the five dormant profiles, −5 tools each** — R2-13's first run found them all
  able to read the fee summary, fee transactions, the defaulter list, the fee
  structures and the action log. Closing that is a pure tightening.
- **Hub menus: not one number moved.** R2-1 was a refactor and looks like one.

**Two smaller narrowings no committed script measures, both deliberate.** Lalit was
offered the School Settings screen, which is a dead button — the screen is backed by
an owner-only tool, so it could only ever answer no. And `support_staff` had no menu
list anywhere, so it fell through to most of the admin menu; it now has two screens.

---

**Found, and it contradicts the handoff. The code is the truth.**

1. **The handoff said to refuse owner-only tools to "all eight non-owner profiles".
   That would have stripped the principal of eleven tools**, including the branch
   records and the year-end promotion. The platform's own committed tests say the
   owner and the principal share the complete school-management surface by design,
   and the handoff's own baseline agrees — it lists both at 155 tools. Adesh stands
   directly below Aman in the school's hierarchy. I took the code's answer and left
   leadership untouched. Worth a sentence from Abhimanyu confirming that is what he
   meant.

2. **Four of the nine "money leaks" were already closed.** The student discount
   route, both accounting-period routes and the expense edit all refuse Lalit today.
   So does payroll for Adesh — `routes/payroll.py` already admits the principal, so
   the "principal is excluded from payroll" item is stale too. The register was
   written before those were fixed and then copied forward.

3. **One of the nine was the opposite of a leak.** `/api/fees/status/{id}` *refused*
   Lalit, and returns a paid-or-unpaid flag with no amount in it at all — exactly what
   decision 1 promises him. Without it his student screens could not tell him who was
   in arrears, which is the work he is there to do. He is now allowed in.

4. **`get_financial_report` was marked owner-only** and reached the principal and the
   accountant head only through the hole. Both plainly need the fee-type breakdown, so
   the registry now grants it to them by name instead of by accident.

5. **A latent test flake, not a regression.** `test_notes_come_back_newest_first`
   passed by luck: Windows' clock resolves to about 15 milliseconds, so two notes
   written back to back can carry the same timestamp and "newest first" is a coin
   toss. The test now sets the two timestamps and checks the sort, which is what it
   was always for. Worth knowing that the same ambiguity exists in the product: two
   notes written within the same moment have no defined order.

---

**Proved.** Backend 2,807 passed / 0 failed / 15 deselected. Frontend 569 passed /
0 failed. Production build passed with lint clean. Every gate run after every
sub-part, not once at the end.

The three separate acceptance checks R2-2 asked for all exist: routes
(`tests/backend/api/test_management_money_leaks_r2_2.py`), payload keys asserted **by
key name** and never by searching for a rupee sign, and the screens rendered as Lalit
(`frontend/src/components/__tests__/ManagementSeesNoMoney.test.js`).

**Left.**

- **Nothing is deployed and nothing was pushed.** No production system was touched, no
  live database was read or written.
- **R2-5** (Sonu's attendance, vendors, transport), **R2-6** (dead buttons, support
  staff), **R2-7/R2-8** (menu vocabulary, Flo briefs), **R2-9** (certificate
  approval), **R2-10** (staff messaging), **R2-12** (transport head), **R2-15** to
  **R2-18**.
- **R2-11**, the login rename, still last on purpose.
- **The fee ledger.** Untouched, as instructed. Eight unreconciled documents in
  `aaryans_database/` have to be read against the school's photographed fee sheet
  first, and a wrong fee structure reaches 1,842 families. Fresh session, Abhimanyu
  awake.
- **The five dormant profiles still wait on Aman's nine questions.** Nothing tonight
  guessed at his answers: every change to those five took access away, never gave it.

**Watch out for.**

- The classification loop at the bottom of `ai/tool_functions_v2.py` **still ends in
  `else: non_finance`**. A new tool that nobody classifies still lands with Lalit by
  default. R2-13 is what now catches that, and it will fail loudly — but read its
  message rather than adjusting the number it prints.
- **`EXPECTED_REACH`** in `tests/backend/unit/test_all_nine_profiles_sweep_r2_13.py`
  and `EXPECTED_SCREEN_COUNT` in `frontend/src/lib/__tests__/ProfileMenuSweep.test.js`
  are pinned counts. A number moving there is somebody's access changing. Never
  silence one; explain it.
- **`frontend/src/lib/profileMatrix.generated.js` is generated.** Editing it by hand
  changes no permissions and only breaks the drift test. Run
  `backend/.venv/Scripts/python.exe scripts/generate_profile_matrix.py`.

### 2026-08-10 — overnight run, continued: R2-5, R2-6, R2-12 (Claude, Opus 5)

**The credentials answer above is unchanged and still stands.** These three sub-parts
make Sonu's job whole and take two refusals off Adesh; none of them reopens anything.

**Did.** R2-5 (Sonu's full remit), R2-6 (the dead buttons), and R2-12 fell out of the
matrix work rather than needing a sub-part of its own.

**R2-5. The four access domains could not express decision 2.** "Sonu yes, Lalit no"
about a school bus route would have meant calling transport *finance*, which is a lie
in the one file whose whole job is to say truthfully who may do what. So the matrix
now names individual tools in both directions — `extra_tools` and `denied_tools` —
which is what the handoff asked an entry to carry all along: screen ids, Flo tool
names, and read versus write. A denial always beats a grant, because the safe answer
to a contradiction is no.

Read versus write is the substance of it. Sonu can now SEE attendance and leave; he
cannot mark a register or approve leave. He needs the first to settle a fee or a
transport charge; the second was never his.

**Found while doing it.** `hubsForUser` had the accountant head's two hubs
**hardcoded**, inside the very module written to stop there being a second copy of the
answer. His menu would have stayed at two hubs while the matrix said six, and nobody
would have seen it. Every profile below leadership now asks the same table.

**R2-6. Adesh could open the payroll screen and then be refused a payslip.** The screen
gate had been widened to include the principal; the payslip check twenty lines below it
still used the older, narrower list. That is the dead-button shape exactly: he would
have concluded the platform was broken rather than that he was not allowed. Both now
ask one helper. Staff opening their own payslip still works, which is what the narrower
check was for.

**R2-12** needed nothing new. Chaman Singh's transport-head profile is defined in the
matrix with six screens, no tool domains, no writes, dormant — and the R2-13 sweep is
what now stops it drifting. He still has no login, by design.

**Measured.**

| Profile | Flo tools | writes | Hubs | Hub screens |
|---|---|---|---|---|
| accountant | 46 → **56** | 27 → **31** | 2 → **6** | 11 → **17** |
| management | 102 → **97** | 63 → **59** | 7 → **6** | 37 → **34** |

Everyone else unchanged, including all five dormant profiles and every route count.
The accountant's ten new tools are the five attendance-and-leave reads and the five
transport tools; his four new writes are the four transport writes. The management
head's five losses are the same transport tools, and his three lost screens are the
transport hub, the transport screens and the vendor log.

**Three committed tests reversed, each with the reason written into it.** The clearest
is `test_accountant_blocked_from_non_accountant_tool`, which pinned Sonu OUT of staff
attendance. The school asked for the opposite. It now pins the read-versus-write split
instead, which is the part that actually matters.

**Proved.** Backend 2,812 passed / 0 failed / 15 deselected. Frontend 569 passed /
0 failed. Production build passed with lint clean.

**Left.** Unchanged from the entry above, minus R2-5, R2-6 and R2-12. Still open:
R2-7/R2-8 (menu vocabulary and Flo briefs), R2-9 (certificate approval before
printing — read plan §1.6 twice, the approval list and the printer use different words
for the same documents), R2-10, R2-15 to R2-18, R2-19, and R2-11 last. The fee ledger
still waits for Abhimanyu awake. Nothing deployed, nothing pushed, no production system
touched.

**One new thing to watch.** `extra_tools` and `denied_tools` are powerful and quiet: a
name in either list silently overrides the domain rule for one profile. Use them only
when the domains genuinely cannot say what the school meant, and write the reason on
the same line — every entry there today has one.

### 2026-08-10 — Abhimanyu's four points, and a line-by-line check against the plan (Claude, Opus 5)

**Still safe to hand over the credentials, on the permission side. Still not deployed.**
Nothing in this entry reopens anything.

**Points 1 and 4 needed no work; both were already true.** Adesh reaches all eleven
owner-only tools and the same 155 as Aman — leadership was never narrowed, which was
the deliberate deviation from the handoff recorded in the previous entry, and Abhimanyu
has now confirmed it was right. The payslip refusal was fixed in R2-6.

**Point 3 was two decisions, not one, and both were put back to him.**

*The fee rate card is public.* What a class is charged per year is on the school's own
fee sheet and any parent may ask for it. It is the school's price list, not the school's
money. `get_fee_structures` moved from finance to shared and every staff profile can now
look it up, the management head included. That is the single exception to "Lalit never
sees a rupee figure", and it is an exception because the number says nothing about any
family.

*What is actually the school's money did not move.* Collections, the defaulter list,
individual payments and the finance report stay finance-only, and so do the three tools
that WRITE the rate card. A test pins that list by name, because "the fee data is
public" is exactly the kind of sentence that grows over time.

*The action log stays with Aman and Adesh.* His message could have been read as adding
Sonu and Lalit. That would have reversed Aman's own request 10 of 2026-08-06, so it went
back to him and he chose the narrower answer. The five junior profiles are shut out
either way, which was the unambiguous half of what he asked for.

**Point 2, the check against the plan, found three real gaps.** All three are fixed.

1. **Flo's briefs were telling both new people the wrong thing.** Sonu's said attendance
   and transport were outside his scope; both are his now. Lalit's promised him student
   logins and password changes, which R2-4 removed, and offered him transport and school
   settings, which he no longer has. On day one Flo would have contradicted the platform
   to the two people being handed credentials. Both rewritten.
2. **The paid-or-unpaid flag was returned but never displayed.** R2-2 asked for two
   things and only the first was done: `getStudentFeeStatus` existed and nothing in the
   frontend called it, so opening a student as Lalit still told him nothing. That is the
   half that matters to him. The student panel now shows Paid, Unpaid or Overdue.
3. **Plan §1.8's "eight payroll routes refuse Adesh" was stale**, like several other
   entries in that register. The shared helper already admitted the principal; only the
   payslip route was left, and R2-6 closed it.

**One deviation from the plan, stated rather than hidden.** R2-1 asked the matrix to
name screen ids, Flo tool names AND API route groups. It names the first two. Routes are
still guarded in each route file. Closing that properly means moving 483 route guards
onto the table, which is its own piece of work and not something to start at the end of
a run. The R2-13 sweep measures route reach per profile, so a change there is at least
visible.

**Measured.**

| Profile | Flo tools | writes |
|---|---|---|
| owner | 155 | 100 |
| principal | 155 | 100 |
| accountant | 56 | 31 |
| management | 97 → **98** | 59 |
| the four dormant with lists | 27 → **28** | 0 |
| support_staff | 26 → **27** | 0 |

The single +1 everywhere is the fee rate card. Writes, routes and menus unchanged.

**Proved.** Backend 2,815 passed / 0 failed / 15 deselected. Frontend 569 passed /
0 failed. Production build passed with lint clean.

**Left.** R2-7/R2-8 (menu vocabulary; the briefs for the seven other profiles),
R2-9 (certificate approval before printing), R2-10, R2-14 to R2-19, and R2-11 last.
The fee ledger still waits. Nothing deployed, nothing pushed, no production system
touched.

### 2026-08-11 — R2-9: nothing official prints until somebody has said yes (Claude, Opus 5)

**Is it safe to hand Sonu and Lalit their credentials?** On the permission side, yes,
and it is safer tonight than it was this morning. **Has any of it shipped? No.** Not one
line of this work is on the live platform. It sits on the branch
`release-2-person-profiles`, seventeen commits, nothing pushed and nothing deployed. The
school's live system still behaves exactly as it did before any of this started, holes
and all. That answer does not change until Abhimanyu approves a deploy.

**Did.** R2-9 only. One sub-part, as instructed.

**What was actually wrong was worse than the brief said.** The brief warned that the
approval list and the printer use different words for the same documents. They do. What
that mismatch was already causing, today, on the live platform:

The Certificate Generator screen's dropdown uses the printer's word, `transfer`. The
approval rule had never heard of `transfer` — it knew `tc` and `transfer_certificate`.
So a **Transfer Certificate raised from that screen was issued immediately, to whoever
asked, with nobody consulted.** The same is true of the Transfer Certificate the platform
raises automatically when a child is withdrawn from the school. A Transfer Certificate is
the document that ends a child's enrolment. It was the one document in the building that
skipped the approval step entirely, and it skipped it because of a spelling.

Migration Certificates had no approval rule of any kind. And two document types that
could be approved, `tc` and `merit`, could never be printed at all.

**So the vocabulary was reconciled first, as instructed.** There is now one file that
decides what a school document is called, whether it needs approving, and what it is
called on the page: `backend/services/certificate_types.py`. `transfer` and `tc` both
mean the same thing as `transfer_certificate` and always did. It is **default deny** —
a document type nobody has classified needs approval, because the safe answer for an
unrecognised piece of paper carrying the school's name is to ask a person.

**Which documents need approving.** Anything that asserts a fact about a child's
standing: Transfer, Bonafide, Character, Migration, Merit, and ID cards. Not the awards:
a Sports or Participation certificate records that a child took part, claims nothing
about them, and needs nobody's permission. That is the recommendation in plan §1.6 and
nothing was widened beyond it.

**Then the printer was made to respect it.** Aman and Adesh print directly, as decision 6
says. Lalit creates a request and prints once one of them has approved it. Three ways of
getting round that are closed by name: an approval cannot be re-used for a different
child, for a different document, or stretched to cover a bigger batch of ID cards than
was approved. Without the last one an approval for four children could have printed the
whole roll of 1,842.

**ID cards go through the same queue, one request per batch.** Not one per child. A class
of forty would otherwise put forty rows in front of the principal, which is how an
approval step quietly becomes a rubber stamp.

**Four things found and fixed while in there.**

1. **A refused print used to spend one of the school's 200 documents for the day.** The
   daily cap was counted before the question of whether the print was even allowed. It is
   counted after now.
2. **The school's owner was never told an approval was waiting.** The notification looked
   for principals only, although Aman may approve and stands above Adesh in the school's
   own hierarchy. Both are told now.
3. **Every certificate the school has ever issued was shown on screen in red**, as though
   it had been refused. The list looked for a status called `approved`; the status an
   approved certificate actually carries is `generated`, and nothing has ever written
   `approved`. It now reads "Issued", and one still waiting reads "Awaiting approval".
4. **Flo told people the wrong thing about who approves.** Its message said a certificate
   was "queued for principal approval". The owner approves these too.

**The office is offered the right button, not a refusal.** Lalit now sees "Ask for
approval" where he used to see "Download", and the PDF button on a request still waiting
is greyed out with a reason on it. A button that says no when pressed reads as a broken
platform, which is the same defect shape this initiative keeps turning up.

**Measured.**

| | Before | After | Why |
|---|---|---|---|
| API routes, total | 483 | **484** | The new ID-card approval request. |
| routes: owner | 350 | **351** | Same route. |
| routes: principal | 336 | **337** | Same route. |
| routes: management | 220 | **221** | Same route. |
| routes: accountant | 266 | 266 | Sonu cannot reach the ID card screen, so he is not given its request route either. |
| routes: all five dormant | unchanged | unchanged | Deliberate. See below. |
| Flo tools and writes, all nine | unchanged | unchanged | No tool was added or moved. |
| Hubs and hub screens, all nine | unchanged | unchanged | No screen was added or moved. |

**The one thing worth checking in that table.** The new route is gated to the three desks
that can already reach the ID Card Generator — the owner, the principal and the admin
office. The obvious spelling, `require_role("admin", "owner")`, is what the certificate
routes beside it use, and it means *every admin desk in the school*. That would have
handed a write route to the five dormant profiles, which today have none, and the handoff
is explicit that Release 2 must not be what gives them any. A test names all six refused
desks.

**Two committed tests were reversed, each with the reason written into it.** Both
asserted that the admin office could print a certificate and a set of ID cards outright.
That was the settled rule until decision 6 changed it. They were not deleted, because the
thing they were written to protect still matters: the office must REACH those routes, or
its own screens become dead buttons. They now pin that it reaches them and is told what to
do next.

**Proved.** Backend 2,842 passed / 0 failed / 15 deselected. Frontend 575 passed /
0 failed. Production build passed with lint clean. Gates run before the work and after it.

**Not done, on purpose.**

- **Flo has no ID-card tool** and did not gain one. It never had one, so no parity gap was
  created. Adding one would have moved the pinned tool counts for a reason unrelated to
  this sub-part.
- **Sonu still cannot reach the certificate printer or the ID card screen.** Decision 6
  says he creates and waits, and he does — through the certificate record, which he can
  already raise. Giving him the print screens is a screen grant, which belongs to a
  decision about his remit (R2-5, settled) rather than to this sub-part. Worth putting to
  Abhimanyu if the school expects Sonu to hand a parent a printed Bonafide.

**Left.** R2-7 and R2-8 (one menu vocabulary; the Flo briefs for the seven untouched
profiles), R2-10, R2-15 to R2-18, R2-19, and R2-11 last because it revokes sessions. The
fee ledger is untouched, as instructed, and still needs Abhimanyu awake and eight
documents reconciled. Nothing deployed, nothing pushed, no live database read or written.

### 2026-08-11 — Sonu's documents, then R2-7 and R2-8 (Claude, Opus 5)

**Is it safe to hand Sonu and Lalit their credentials?** On the permission side, yes.
**Has any of it shipped? No.** Twenty commits on the branch, nothing pushed, nothing
deployed, no live database read or written. The school's live platform still behaves as
it did before any of this began.

**Abhimanyu's instruction of 2026-08-11**, in his words: give Sonu the ability and the
screen for certificates and ID cards, approval going through Adesh and Aman both, and
the same for Lalit for whatever he makes.

**How "both" was implemented, and what it does not mean.** Both Aman and Adesh are now
told when a document is waiting, and **either one of them can approve it**. It is not two
separate sign-offs on the same document. If the school wants a document to need both
names, that is a real change and should be asked for on purpose rather than assumed.
Lalit's half already worked that way from R2-9; the missing half was that only principals
were being notified, so Aman was never told. That is fixed.

**Sonu now has the two screens.** He was taken off the document routes on 2026-08-08,
when reaching those routes MEANT issuing the document with nobody watching. After R2-9
that is no longer what reaching them means: he creates a request and prints only once
Aman or Adesh has approved. So the reason for keeping him out has gone. A test pins that
he **cannot approve his own request**, which is the whole point of the rule.

---

**R2-7. The nine department names were already shared.** That part was done by R2-1 and
R2-5. What nobody had checked was whether a screen a person is granted can actually be
opened, and twice it could not:

1. **Lalit was granted seven screens that live in Reports, AI & Governance, and did not
   have that group.** Custom Reports, Board Report, Automated Reports, Incidents &
   Visitors, Query & Support, Form Builder and Tech Issues: all granted, none reachable.
   The group's name had been swept into the leadership-private list alongside the action
   log and the AI screens, which is a decision about screens applied to a door. Holding
   the group does not reveal the private rows; they are filtered one at a time, and a
   test now proves that.
2. **Tech Issues sat in no group at all**, so only the profiles that use the flat sidebar
   could find it.

**Two of those seven turned out to be money, and came off Lalit's list instead of being
made reachable.** Board Report totals the school's expenses. Custom Reports offers Fee
Transactions and Expenses as data sources, and the server already refused him six of its
seven sources, so the screen was mostly buttons that answer no. Decision 1 says he never
sees a rupee figure, so taking them away is the right direction and the safe one.

**R2-8. The seven untouched briefs were measured against what each profile really holds.
All five dormant ones were wrong in both directions at the same time.**

- **They denied what the profile has.** Every one of the five can read the school
  directory, attendance, the staff list and the day's brief. Every brief said some
  version of "you CANNOT see student data". Flo would have refused work the platform
  allows, which is exactly the failure that once had Flo telling the school's *owner* an
  operation was not available to it.
- **They promised what the profile does not have.** IT support was told it could reset
  passwords and read system health: it has neither tool. Maintenance was told it could
  update tickets, manage the schedule and edit the vendor directory: it has one read
  tool. That is a dead button spoken out loud.

Every rewritten brief now states plainly that the profile has no write tools, and names
who to ask instead of stopping at "not available to me".

**Also corrected in the leadership briefs.** The owner's called the finance report "owner
exclusive", which stopped being true on 2026-08-10, and labelled school configuration
"owner only" when the principal holds the identical surface. That last one was measured,
not assumed: the two tool sets are exactly the same, 155 each, with nothing on either
side that the other lacks. Both briefs now mention that they approve documents, which is
the one action only those two can take.

**Measured. Every movement was intended.**

| | Before today | Now | Why |
|---|---|---|---|
| API routes, total | 483 | **484** | The ID-card approval request (R2-9). |
| routes: owner / principal / management | 350 / 336 / 220 | **351 / 337 / 221** | That same route. |
| routes: accountant | 266 | **269** | The two print routes and the request route, now his. |
| hub screens: accountant | 17 | **19** | Certificates and ID Cards. |
| hub screens: management | 34 | **39** | +7 he was granted and could not reach, -2 money screens removed. |
| hub screens: owner / principal | 56 / 57 | **57 / 58** | The Tech Issues row they already had permission for. |
| matrix screens: accountant | 23 | **25** | Same two screens. |
| matrix screens: management | 48 | **47** | +governance-ai-hub, -board-report, -custom-report-builder. |
| Flo tools and writes, all nine | unchanged | unchanged | **No Flo tool was added, moved or removed all day.** |
| the five dormant profiles | unchanged | unchanged | Nothing was given to any of them. |

**Proved.** Backend 2,885 passed / 0 failed / 15 deselected. Frontend 592 passed /
0 failed. Production build passed with lint clean. Gates run after each piece.

**⚠️ One thing to watch, reported rather than buried.** On one backend run out of six,
a single unrelated test failed — `test_staff_erase_destroys_the_record_and_keeps_the_reason`
in `tests/backend/api/test_staff_enrolment_state.py`, with a 403 creating a staff record.
It has not repeated in five further full runs, nor in three runs of that file with today's
changes stashed, and the file passes alone every time. **I could not reproduce it and I
have not fixed it.** The shape fits the known trap that the `fake_db` fixture is shared
across the whole session. If it appears again, that is the place to look, and it should
be chased rather than re-run until it passes.

**Two things worth Abhimanyu's attention, neither urgent.**

- **The Automated Reports screen is a mock-up.** It shows two hardcoded rows ("Weekly
  Attendance Report", "Monthly Fee Summary") and calls nothing. Nobody is receiving a
  scheduled report. It is offered to Lalit and to leadership. Not touched today; it is
  not a permission problem.
- **The five dormant profiles can read more than their job needs.** Every one of them,
  including support staff, can look up any child's record, attendance and the staff list
  through Flo. That is the status quo the matrix recorded rather than anything given
  today, and none of them has a login. It belongs with Aman's nine unanswered questions.
  Nothing today widened it; the briefs now describe it accurately instead of denying it.

**Left.** **R2-10** (staff messaging; diagnose the RECONNECTING state before fixing, it
may be infrastructure), **R2-15 to R2-18**, **R2-19**, and **R2-11 last** because it
revokes sessions. The fee ledger is untouched, as instructed, and still needs Abhimanyu
awake and eight documents reconciled first.

### 2026-08-11 (later) - the rest of Release 2, Aman's answers, and no more long dashes (Claude, Opus 5)

**Is it safe to hand Sonu and Lalit their credentials?** On the permission side, yes.
**Has any of it shipped? No.** Twenty-three commits on the branch, nothing pushed, nothing
deployed, no live database read or written. That answer does not change until Abhimanyu
approves a deploy.

**Done this run:** Sonu's document screens, R2-7, R2-8, R2-10, R2-15, R2-17, R2-18, the
twelve answers from Abhimanyu, R2-11 prepared but deliberately not run, and the long-dash
sweep.

---

#### Abhimanyu answered all twelve questions

The register calls these "the nine questions". There were always **twelve**, across five
roles. All twelve are now answered and written into the ANSWERS section at the foot of
`staff-profiles-draft-for-aman-2026-08-10.md`, which wins wherever it disagrees with the
draft above it.

**Only the two answers that TAKE access away were acted on**, because Release 2 must not
be what gives a dormant profile anything. The front desk loses Student Transfer and
Commercial Operations. Every other answer is a grant and waits for its own release.

**Three things from those answers that need saying out loud:**

- **IT support today is a person from Vedmarg, the school's previous ERP supplier.** No IT
  login should be issued while that is true. A standing login into a database of 1,876
  children, held by a competing product's employee, is not a permission question the
  platform can answer. It moves to a computer teacher, and it switches on then.
- **Drivers and conductors are to get a profile of their own.** That is a **tenth**
  profile and the platform has nine. It belongs with the transport release.
- **The front desk does run the shop counter**, so she is to get the till and nothing
  else. That screen also carries the school's legal entities, so it has to be split
  first. Until then she has none of it.

#### R2-10, staff messaging

**The "0 colleagues available" screen was a lookup joining on four hardcoded usernames**
(`aman.litt`, `adesh.singh`, `sonu.ruhal`, `lalit.thomas`). Production uses `accountant`
and `management`, so it matched nobody and the screen was honestly reporting nothing.
Renaming the logins in R2-11 would have fixed it **by accident**, which is the wrong
reason for it to work: the next employee to join would still have been invisible. It now
asks who somebody IS, which is the question the code already answered three lines lower.

**RECONNECTING was diagnosed, not guessed at, as the plan insisted.** It is not the code.
Keepalive is 30 seconds, inside both the 300-second load-balancer timeout and nginx's
60-second one; every stream disables proxy buffering; the browser refreshes an expired
login once and reopens rather than retrying into a wall. **So the remaining suspect is the
network path, and that cannot be confirmed without watching it in production.** Said
plainly rather than changing something and calling it fixed.

#### R2-18, same-day undo, and why it refuses so much

The plan said to verify the audit `changes` shape before designing around it. **Verifying
found eight different shapes**, most carrying no previous value at all: bulk attendance
records a count, a delete records the whole document, an import records a batch id.

An undo written against the assumed shape would have **appeared to work and done nothing**
on most paths, which is worse than no undo at all, because the person believes the mistake
is fixed and walks away. So it reads each row and decides, and when it cannot honestly
reverse something it says so in a sentence the person can act on. Only your own change,
only today (in Indian time, or a 3am edit is refused as yesterday's), only a student or
staff record, never money, never whether a child is on the roll, never a login. A row
mixing a name and a salary restores the name only. Every undo writes its own entry.

#### R2-11 is prepared and has NOT been run

`backend/migrations/033_rename_two_office_logins.py`. Dry run by default, a preflight that
stops if the account is missing or the target name already exists, and a rollback file.
**It writes to the live database and it signs those two people out.** It needs Abhimanyu's
explicit yes, on the day, after the deploy, with both people standing there to sign back
in. Checked while writing it: nothing else in the platform still joins on a login name.

#### No long dashes anywhere, and Flo cannot print one

3,588 removed from 497 files across the platform. The archived planning folders (about
12,000 more) were left alone deliberately: they are a historical record, not the product,
and rewriting them would bury every real change in noise.

**The sweep broke Flo's own rule, and a committed test caught it.** The instruction named
the characters by printing them, so removing them rewrote it into "never use a hyphen".
The rule had deleted itself. It now names them by unicode number, which no text sweep can
touch.

**And a prompt rule is only a request.** `backend/ai/writing_style.py` now replaces every
long dash at the one point all model text passes through, covering replies and generated
documents alike. Six dash characters, not one: a model reaching for "a long dash" does not
always reach for the same one.

#### Measured

| | Before this run | Now | Why |
|---|---|---|---|
| API routes, total | 484 | **487** | The digest and the two undo routes. |
| routes, every profile | +3 | | The same three. The undo routes are open to anyone signed in **and only ever show your own work**; the digest is refused inside the handler, which the audit script cannot see. |
| screens: receptionist | 9 | **7** | Student Transfer and Commercial Operations, on Abhimanyu's answers. |
| Flo tools and writes, all nine | unchanged | unchanged | **No Flo tool was added, moved or removed in this whole session.** |
| hubs and screens, the four live | unchanged since the earlier entry | | |

**Proved.** Backend 2,941 passed / 0 failed / 15 deselected. Frontend 592 passed /
0 failed. Production build passed with lint clean.

#### Left, and who it needs

- **R2-16** (what data is still missing): needs Abhimanyu's approval to READ the live
  database. Counts only, never an export of children's records.
- **R2-19 and the fee ledger**: still needs him awake and eight documents reconciled
  first. Untouched, as instructed.
- **R2-11**: prepared, needs his yes on the day, after deploy.
- **R2-14**, go-live: his.
- **The till-only view** for the front desk, and the other grants from the twelve
  answers, in each profile's own release.
- **The unreproduced test flake** from the earlier entry has not recurred in any of the
  eight full suite runs since. Still worth chasing if it reappears rather than re-running
  until it passes.

### 2026-08-11 (third run) - the undo made to work, the logins renamed for real, and the school's data measured (Claude, Opus 5)

**Is it safe to hand Sonu and Lalit their credentials? Yes, and their logins have now
actually changed**, so this is the first entry where the answer involves the live system.
**Has the CODE shipped? No.** Twenty-six commits on the branch, nothing pushed, nothing
deployed. Abhimanyu's instruction is that the deploy happens when Release 2 is finished.

**Abhimanyu's four instructions this run**, all done: make the undo work rather than
refuse; go ahead with the login rename; the fee ledger comes very last; the missing-data
read is approved.

---

#### THE LOGINS HAVE CHANGED. This is live.

| Was | Is now | Shown as |
|---|---|---|
| `accountant` | **`sonu.ruhal`** | Sonu Ruhal (was the generic "Accountant") |
| `management` | **`lalit.thomas`** | Lalit Thomas (was "Management Desk") |
| `Adesh` | **unchanged** | Adesh Singh (was "ADESH SINGH", all capitals) |
| `Aman Litt` | **unchanged, not written to at all** | Aman Litt |

**The passwords were not changed**, deliberately, per decision 11. So each password is
still the one that goes with the OLD account name. Anyone signing in as `sonu.ruhal` uses
the password that used to go with `accountant`. Both old logins now resolve to nothing,
which is what signed those two sessions out.

Dry run first, then applied, verified afterwards by reading the accounts back, rollback
file saved outside the repository. Migration 033 is recorded in `_migrations` so nobody
runs it twice. **If it ever has to be undone**, the previous values were exactly
`accountant` / "Accountant" and `management` / "Management Desk".

#### The undo now works, rather than refusing safely

It had **two** defects, and the first is the one that matters.

1. **It refused every real edit on the platform.** It looked for the collection names
   `students` and `staff`; the services write `student` and `staff`, singular. So an
   ordinary edit by Lalit was answered with "only a student or staff record can be put
   back this way", about a student record. Its own tests passed because they built their
   audit rows by hand using the plural, which proves only that the test agrees with
   itself. There are now tests that drive the real services and undo what those services
   recorded. Those are the ones that would have caught it.
2. **A spreadsheet import could never be undone, and a comment claimed it could.** The
   audit row said `{"import_batch": ..., "fields": {field: new_value}}` under a comment
   reading "carrying the BEFORE values, so an import can be unpicked later". It carried
   only the new ones. An import is the single thing Lalit does in bulk and was the least
   reversible thing on the platform. It now records the same shape every other write path
   uses.

#### What the school still owes, measured from the live records

Full report for Aman: `what-the-school-still-owes-2026-08-11.md`. Counts only, no child
named anywhere. **Four lists are entirely empty**: fee structures, transport routes,
vendors and message templates. Every one of the 110 staff is missing a joining date and a
salary. 787 children have no date of birth, all 1,842 have no blood group, and 11th and
12th are not split into Commerce and Science.

**The first version of that report was wrong, and it is worth knowing why.** It said all
1,842 children had no date of birth and no contact number. The platform has stored the
same thing under different names over time: 1,055 have a date of birth under `dob` and
1,833 have a number under `phone`. Publishing that would have sent the school hunting for
1,842 dates of birth it already holds. The report now counts a gap only when the value is
missing under **every** name, and prints where the records that have it keep it.

#### One defect the live data exposed, which nothing else would have

**Sonu and Lalit have no person record at all, only a login.** The daily digest built the
previous run resolved names from the person records, so on day one it would have told Aman
that "Somebody no longer on the platform" made forty changes, about the two people he had
just handed credentials to. It now reads the login records too, which everybody who can
change anything has by definition. Pinned by a test.

#### Measured

Nothing moved. No profile gained or lost a screen, a Flo tool or a route this run. Backend
**2,946 passed / 0 failed / 15 deselected**, frontend **592 passed / 0 failed**, build
clean with lint.

#### What is left before Release 2 can ship

1. **The fee ledger**, which Abhimanyu has put very last. Eight documents to reconcile
   first, and the report above shows exactly how much waits on it: every child is on no
   fee plan and there is one payment in the whole system.
2. **R2-19**, proving Flo can do the same fee work through the same services. Follows the
   ledger.
3. **The deploy**, which Abhimanyu has said happens when everything else is done. It needs
   the `claude-hosting` IAM user.
4. **R2-14**, the handover itself.

Everything else in Release 2 is built and green.

### 2026-08-11 (fifth run) - the fee rules settled, the student columns carried across, and the finishing plan (Claude, Opus 5)

**Has the code shipped? No.** 34 commits on the branch, pushed to GitHub for the first
time this run, nothing deployed. The only thing that has ever touched production is the
login rename (R2-11).

**Did.** Finished the accountant salary work left half-done in the working folder; got the
school's fee rules out of Sonu through Abhimanyu and checked every one of them against the
school's own ledger; carried the remaining student columns across; and wrote the finishing
plan for everything left.

#### The new fee log changed the picture

`Fees-log-detailed-11-08-2026-17-36.xlsx`, added by Abhimanyu mid-run: **10,720 fee lines,
3,177 receipts, 1,723 children, 3.56 crore collected**, 23 January to 7 August. It is the
real ledger rather than an export of estimates, and it independently confirms the
photographed fee sheet to the rupee on all seven bands.

It also answers three things that were about to be asked of the school: the senior streams
are recorded in it (158 students), 1,235 children demonstrably use the bus while the
platform says none do, and transport runs eleven months with **no June line in 5,587
rows**.

#### The rules, all checked rather than transcribed

`fee-rules-from-sonu-2026-08-11.md` is now the authority. 853 ledger lines sit at exactly
one of the seven sibling band values; 154 at exactly half a quarterly fee; **all 1,217
fine lines are exact multiples of 10**. The rules are real and in daily use.

**The one to build carefully** is the late fine, because the previous system gets it
wrong: it keeps a quarter's daily fine running after the next quarter starts, so two
accrue at once and families are overcharged. Only one daily fine ever runs. The 1,000 at
quarter end, however, repeats: four times over a full year of arrears. That was queried
because Abhimanyu's own worked example read the other way, and he confirmed it against a
number.

#### Two defects found by looking at the school's real columns

Both are the same shape, and the second was live.

1. **Eleven import columns pointed at fields the student record does not have** -
   `whatsapp_phone` beside the real `whatsapp`, `aadhaar_number` beside `aadhaar_no`.
   Importing the school's own export would have written a second copy of each and every
   screen reads the first, so it would have reported success and changed nothing visible.
2. **The messaging service had the same fault, in production.** It asked only for
   `whatsapp_phone` on the student record, so the WhatsApp number the school holds for
   **1,096 children was never looked at**. Messages still went out on the general contact
   number, so nothing appeared broken.

All 122 columns of the school's export now have a decision: 75 mapped, 47 refused by name
with the reason on the line. A test asserts there is no third category.

**Right to Education, and the list nobody had looked for.** The export carries an
`IsRteStudent` column with **21 children marked**, and the school marks them again inside
the child's name. Of the 13 who appear in the ledger, not one was charged a school fee. It
is recorded as its own mark and deliberately NOT as a 100% discount, and deliberately not
importable in bulk: it decides whether a child owes any school fee at all.

#### Measured

| | Before this run | Now | Why |
|---|---|---|---|
| Flo tools / writes: accountant | 56 / 31 | **57 / 32** | `update_staff`, salary only. |
| everything else, all nine profiles | unchanged | unchanged | Nothing else moved on any surface. |

**Proved.** Backend 2,999 passed / 0 failed / 15 deselected. Frontend 592 passed /
0 failed. Build clean with lint.

**Left.** `FINISHING-PLAN-2026-08-11.md`, eleven steps, about fourteen days. Five things
wait on a person: the senior streams, confirming the 21 Right to Education children,
confirming the sibling groups, what happens to the 1,844 unvouched fee figures, and the
go-ahead to deploy. Nothing else is blocked.

### 2026-08-11 (fourth run) - Sonu gets the salary figure, and a grant that had never worked (Claude, Opus 5)

**Has the code shipped? No.** Still nothing pushed and nothing deployed. The deploy
happens when Release 2 is finished, per Abhimanyu.

**Did.** Finished and proved the one piece of work left half-done in the working folder
from the previous session: the accountant head can now correct a colleague's base salary.
Abhimanyu's instruction, relaying Aman's and Adesh's: Sonu already knows and handles
everyone's pay, so the platform should say so.

**What was already true and was not touched.** Sonu has run payroll in full since this
project began - salary structures, disbursements, corrections and payslips - and he could
already READ the salary on a colleague's record when he opened it. The gap was the one
figure that sits outside the payroll system, the base salary on the staff record itself.

**The defect underneath it, which is the part worth reading.** The code already contained
a line granting the accountant head that field. It had never once worked. Three lines
below it, the owner-only strip removed `salary` from the update unconditionally, undoing
the grant it had just made. So a permission had been written, read as authoritative by
anyone reviewing the file, and silently taken back before it reached the database. Nothing
caught it because no test had ever driven a real write through that path. There are tests
now, and they call the real service rather than asserting against hand-built rows.

**Two more inconsistencies fixed while in there.**

1. **The same field answered two different ways depending on which door was used.** Sonu
   could see a colleague's pay by opening their record, and not see it in the table listing
   all of them - the list view stripped salary from everybody regardless of who was asking.
2. **Flo could not reach the tool at all**, so the fix would have been a dead door on the
   chat side while working on the screen.

**Deliberately narrow.** An accountant caller of `update_staff` may change `salary` and
nothing else; a name, phone or department correction is silently dropped and stays with
Lalit and Adesh. The instruction was about salary, not about staff records generally.
Granting the role, the sub-category or whether somebody is still employed remains the
school's owner alone, for everyone, with no exception.

**One committed test reversed, with the reason written into it.**
`test_phase1_lockdown_blocks_everyone_else` pinned the accountant head OUT of
`update_staff`. That was the settled rule until this instruction. It now records that he
reaches the tool and points at the file proving how narrow his reach is, in the same shape
as the `create_student` exception beside it from R2-5.

**Measured.**

| | Before | Now | Why |
|---|---|---|---|
| Flo tools: accountant | 56 | **57** | `update_staff`, salary only. |
| writes: accountant | 31 | **32** | The same tool. |
| every other profile, all three surfaces | unchanged | unchanged | Nobody else gained or lost anything. |
| API routes | 487 | 487 | No route added; the salary change reuses `PATCH /api/staff/{id}`. |

The route counts in the summary table at the top of this file were stale by three - they
still read 484 from two entries ago while the digest and the two undo routes had already
landed. Corrected rather than left to be misread as a movement today.

**Proved.** Backend 2,962 passed / 0 failed / 15 deselected. Frontend 592 passed /
0 failed. Production build passed with lint clean.

**Left.** The fee ledger (eight documents to reconcile first, Abhimanyu has put it very
last), R2-19 after it, the deploy, and R2-14 handover. Nothing else in Release 2 is open.
