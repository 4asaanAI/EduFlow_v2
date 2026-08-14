> ## SUPERSEDED 2026-08-14
> This is history. The current handoff is `HANDOFF-2026-08-14-access-ladder.md`.
> Kept because it records how Release 2 was reasoned about, not because it is current.

# Handoff — Release 2, after the permission work, 2026-08-10

**Give this whole file to the next agent.** It is written to be opened cold. It replaces
`HANDOFF-2026-08-10-release-2-overnight.md`, whose Priorities 1 to 5 are all done.

---

## Who you are and what this is

You are continuing work on **EduFlow**, a chat-first school management platform built by
**Layaa AI** for **The Aaryans**, a CBSE school in Joya, Amroha, Uttar Pradesh. One
branch, 1,876 students on the roll (1,842 active). React frontend on AWS Amplify,
FastAPI backend on Elastic Beanstalk, MongoDB Atlas, Azure OpenAI behind the assistant
called **Flo**.

**Abhimanyu** is the founder of Layaa AI. He commissions this work and approves deploys.
He is **not** the school's owner: in this codebase `owner` means **Aman Litt**, who runs
the school. Never write "you" to Abhimanyu about something an `owner` can do; say "the
school's owner".

| Person | Role in the school | Platform profile | Login today |
|---|---|---|---|
| Aman Litt | Owner | `owner` | `Aman Litt` |
| Adesh Singh | Principal | `admin` / `principal` | `Adesh` |
| Sonu Ruhal | Accountant head | `admin` / `accountant` | `accountant` |
| Lalit Thomas | Management, day-to-day data | `admin` / `management` | `management` |

Hierarchy the school asked for: **Aman > Adesh > Sonu > Lalit.**

Branch: **`release-2-person-profiles`**. Sixteen commits, **nothing pushed, nothing
deployed**.

---

## Read these three files before you write any code

1. `_bmad-output/implementation-artifacts/release-2/PROGRESS.md` — **the only record of
   what is done.** Read it first, update it last, every single run. Start with the last
   session entry.
2. `_bmad-output/planning-artifacts/release-2-person-profiles-2026-08-10.md` — what the
   work is. **Parts of it are now stale**; see the warning below.
3. `CLAUDE.md` — the project's standing rules. Not optional.

---

## What changed, and the one thing you must understand

**The permission work is done.** R2-1 to R2-6, R2-12 and R2-13 are built and green.

Access used to be granted by **subtraction**: "management" meant *everything not tagged
finance*, and the last line of the frontend's permission check was `return true`.
Nothing anywhere stated what anyone was supposed to have.

**That is over. There is now one written grant table:**

```
backend/services/profile_matrix.py          ← THE SOURCE OF TRUTH
frontend/src/lib/profileMatrix.generated.js ← generated mirror, checked in
scripts/generate_profile_matrix.py          ← regenerate after ANY edit
tests/backend/unit/test_profile_matrix_drift.py ← fails if they drift apart
```

It covers **all nine profiles** the platform recognises, is **default deny**, and names
screen ids, Flo tool names, read-versus-write, and who may remove a person. Four
profiles are live; five are dormant, defined so they cannot drift, switched on in their
own release.

**If you change who may reach what, you change that file and regenerate the mirror.**
Never hand-edit the JS: it changes no permissions and only breaks the drift test.

**One thing subtraction has NOT been removed from.** The classification loop at the
bottom of `backend/ai/tool_functions_v2.py` still ends in `else: non_finance`. A new Flo
tool that nobody classifies still lands with Lalit by default. R2-13 now catches it.

---

## How to check yourself

Two committed read-only scripts. **Run them before you start and after every sub-part,
and explain every number that moved.** A number that moved and was not intended is a
defect.

```bash
backend/.venv/Scripts/python.exe scripts/audit_profile_reach.py   # Flo tools + API routes
node scripts/audit_profile_menus.mjs                              # hub menus
```

**Current state, measured 2026-08-10 after all the permission work:**

| Profile | Flo tools | writes | API routes | Hubs | Hub screens |
|---|---|---|---|---|---|
| owner | 155 | 100 | 350 | 9 | 56 |
| principal | 155 | 100 | 336 | 9 | 57 |
| accountant | 56 | 31 | 266 | 6 | 17 |
| management | 98 | 59 | 220 | 6 | 34 |
| transport_head | 28 | 0 | 188 | 0 | flat list |
| receptionist | 28 | 0 | 204 | 0 | flat list |
| it_tech | 28 | 0 | 189 | 0 | flat list |
| maintenance | 28 | 0 | 188 | 0 | flat list |
| support_staff | 27 | 0 | 188 | 0 | flat list |

These same numbers are **pinned in two test files**, deliberately:

- `EXPECTED_REACH` in `tests/backend/unit/test_all_nine_profiles_sweep_r2_13.py`
- `EXPECTED_SCREEN_COUNT` in `frontend/src/lib/__tests__/ProfileMenuSweep.test.js`

A number moving there is **somebody's access changing**. Never silence it. Either it was
deliberate, in which case update the number and say why in the commit message and in
PROGRESS.md, or you have found a defect.

Gates, and the bar is **0 failures** in each. Never pin a pass count.

```bash
MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test \
  python -m pytest tests/backend/ -q
cd frontend && CI=true npx jest
cd frontend && npm run build      # lint runs first; one warning fails the deploy
```

---

## ⚠️ The plan document is now stale in places. Trust the code.

The 2026-08-10 audit register was written before several of its own findings were fixed,
and the fixes were never struck off. Checking it line by line on 2026-08-10 found:

- **Four of the nine "money leaks to Lalit" were already closed.** The student discount
  route, both accounting-period routes, and the expense edit all refused him already.
- **One of the nine was the opposite of a leak.** `/api/fees/status/{id}` *refused* him
  and carries no amount at all. He is now allowed in; that is the flag he was promised.
- **§1.8's "eight payroll routes refuse Adesh" was stale.** The shared helper already
  admitted the principal. Only the payslip route was left.
- **The handoff said owner-only tools should be refused to "all eight non-owner
  profiles".** That would have stripped **Adesh** of eleven tools. Owner and principal
  share the complete surface by design, pinned by two committed test suites, and
  Abhimanyu confirmed on 2026-08-10 that this is what he meant.

**Never assume a finding in the plan is still true without re-reading the file it
names.** Re-measure, do not re-trust.

---

## The settled decisions. Do not re-open these.

1. **Lalit and money.** He sees a paid-or-unpaid flag, as a visible field, and never a
   rupee figure — **with one exception, added 2026-08-10**: the school's published fee
   **rate card** (what a class is charged per year) is public, it is on the school's own
   fee sheet, and every staff profile may look it up. Collections, arrears, individual
   payments and the finance report are not, and neither is changing the rate card.
2. **Sonu.** Staff and student attendance and leave, read-only. Full directory plus his
   own columns. Vendor records in full. Transport in full until Release 3. He may create
   students. Lalit lost vendors and transport.
3. **Transport head profile** is built and dormant until Release 3.
4. **Lalit and people.** Add and edit yes. Delete no. Logins no — not even student ones.
5. **Sonu may create students**, alongside Aman and Adesh.
6. **Certificates and ID cards.** Aman and Adesh issue directly. **Sonu and Lalit create
   and wait for approval.** (Still to build: R2-9.)
7. **Logins.** Only two change: `accountant` → `sonu.ruhal`, `management` →
   `lalit.thomas`. **Aman's login is not touched.** Adesh gains "Singh". Passwords
   unchanged. Migration 031 declares the dotted form for all four; the file is wrong and
   the instruction wins. **This is R2-11 and it is deliberately LAST.**
8. **Staff messaging.** Every employee becomes reachable in staff chat as releases land.
9. **Aman and Adesh see everything**, including every salary, and including the eleven
   owner-only Flo tools. Reconfirmed 2026-08-10.
10. **All nine profiles get proper definitions**, dormant until their release.
11. **Passwords stay guessable** (account name plus `@123`). Abhimanyu was offered strong
    replacements and declined, knowingly. **Do not change them**; it would lock him out
    of the accounts he uses to check the work. Raise it again at R2-14.
12. **The action log stays with Aman and Adesh only** (Aman's request 10 of 2026-08-06,
    reconfirmed 2026-08-10). Not Sonu, not Lalit, and none of the five below them.

---

## What is already correct. Do not "fix" these.

- **Password resets are already safe** at the service level
  (`account_management_service.py`), and R2-4 put an outer door in front of them.
- **Salary edits are already blocked.** `salary` is in `staff_service.OWNER_ONLY_FIELDS`.
- **Spreadsheet import is already scoped per profile** and reports out-of-segment
  columns rather than dropping them.
- **The certificate *record* flow already requires approval**
  (`certificate_service.py:41-75`). Only the *printing* path (`routes/image_gen.py`)
  does not. **Extend, do not rebuild.**
- **The directory screens carry no money fields at all.**
- **The five profiles below Lalit have zero write tools.** Do not be the change that
  gives them any. R2-13 fails if you do.

---

## Traps that have already caught someone

- **`extra_tools` and `denied_tools` in the matrix are powerful and quiet.** A name in
  either overrides the domain rule for one profile, silently. Use them only when the
  four domains genuinely cannot say what the school meant, and write the reason on the
  same line. Every entry there today has one.
- **The certificate approval list and the certificate printer use different words for
  the same documents.** Approval knows `bonafide, tc, transfer_certificate, character,
  merit`; the printer knows `transfer, bonafide, character, sports, participation,
  migration`. Only two overlap, so `transfer` never matches `transfer_certificate` and a
  naive fix passes Transfer Certificates through **unapproved**. This is R2-9 and it is
  the next job.
- **106 of 483 routes check permission inside the handler body**, not through a FastAPI
  dependency. Any sweep that only introspects dependencies understates the guards.
- **Two unrelated messaging systems.** `routes/messaging.py` is staff-to-staff chat.
  `routes/parent_messaging.py` sends WhatsApp and SMS to families. Do not confuse them.
- **Windows' clock resolves to about 15 milliseconds.** Two records written back to back
  can carry an identical timestamp, so any test asserting "newest first" on freshly
  written rows is a coin toss. Set the timestamps explicitly.
- **The `fake_db` fixture is shared across the whole session.** A test that replaces a
  collection must put it back, or it breaks an unrelated test files away.

---

## What to do next, in order

### 1. R2-9 — certificates and ID cards need approval before they print

The record flow already sends non-leadership requests to `pending_approval`. The
**printing** path (`routes/image_gen.py`) does not. **Reconcile the two vocabularies
first** — see the trap above — then extend. Read plan §1.6 twice.

### 2. R2-7 and R2-8 — one vocabulary, and the remaining Flo briefs

Sonu's and Lalit's briefs were rewritten on 2026-08-10 because they had become actively
wrong. **The other seven profiles' briefs are untouched** and should be checked against
the matrix the same way. Do NOT invent per-person group names.

### 3. R2-10, R2-15 to R2-18

Details in the plan. R2-10: diagnose the RECONNECTING state before fixing it; it may be
infrastructure. R2-18: verify the audit `changes` shape first, it is **not consistent**
across write paths.

### 4. R2-11 — the login rename. LAST, on purpose: it revokes sessions.

---

## Needs Abhimanyu awake, do not start alone

**Loading the fee structure.** He has approved the write, but `aaryans_database/` holds
**eight unreconciled fee documents**, including
`Transport-Fees-Structure-Report-Summary-06-08-2026-16-58.pdf` and
`Ledger-Report-06-08-2026-01-03.xlsx`. They must be read and reconciled against the
official fee sheet transcribed in plan R2-16 **before** anything is written. A wrong fee
structure reaches 1,842 families. `fee_structures` is currently empty, so the rollback
is deleting exactly what you inserted. Then R2-19: prove Flo can do the same work
through the same services.

**R2-16**, the empty-field scan, needs his approval to read the live database.

---

## Open questions

| # | Question | Blocks | Who |
|---|---|---|---|
| 1 | The nine questions in `staff-profiles-draft-for-aman-2026-08-10.md`, covering the five profiles below Lalit. | Switching those five on. Not the four live ones. | Aman |
| 2 | Who may message whom from Release 5 (teachers) and Release 6 (students)? | Release 5 | Abhimanyu |
| 3 | Do the fee structures and balances arrive as a spreadsheet, or does Sonu type them in? Same for transport routes. | R2-16 | The school, via Aman |
| 4 | Should the matrix eventually own the API route guards too? R2-1 asked for it; it names screens and tools only. Moving 483 route guards is its own piece of work. | Nothing today | Abhimanyu |

---

## Rules you must not break

1. **Never modify the live school database** without Abhimanyu's explicit approval.
2. **Never run `backend/migrations/run_all.py`.** One migration at a time, after reading
   it. Six of them insert convincing fake data into what they assume is a demo school.
3. **Do not deploy.** Deploys need the `claude-hosting` IAM user and Abhimanyu's
   approval.
4. **No TypeScript.** `.js` and `.jsx` only.
5. **`from __future__ import annotations` is the first line** of any Python file using
   `str | None`, or the file fails at collection and its tests silently skip.
6. **No `pytestmark = pytest.mark.asyncio`** in test files; `asyncio_mode = auto` does it.
7. **Every new endpoint needs two tests**: unauthenticated 401, wrong role 403.
8. **Never put a password in the repository.**
9. **Write to Abhimanyu in plain, non-technical language.** He relays it to the school.
   Be just as direct about failures, only in everyday words.
10. **Update `PROGRESS.md` before the session ends, even if the run failed.**
11. **One sub-part per run. Suite green before the next.**

---

## The question Abhimanyu keeps asking

**Is it safe to hand Sonu and Lalit their credentials?**

On the permission side, yes. But **none of this is deployed** — it is committed on a
branch and nothing has been pushed. The live platform still behaves as it did before
this work, holes and all. Answer that question honestly every run, and say "not until it
ships" for as long as that stays true.
