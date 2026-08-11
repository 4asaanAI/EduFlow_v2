# Resume prompt: the six unblocked steps of Release 2

Paste everything below the line into a fresh session.

---

Continue Release 2 on branch `release-2-person-profiles`. Do not start anything else.

**Read these three first, in this order, before touching any code.** Do not trust my
summary of them; read the files.

1. `_bmad-output/implementation-artifacts/release-2/FINISHING-PLAN-2026-08-11.md`
   The eleven remaining steps and what each one needs.
2. `_bmad-output/implementation-artifacts/release-2/fee-rules-from-sonu-2026-08-11.md`
   How the school actually charges. This is the authority. Where it disagrees with any
   other document in the repo, including the previous vendor's exports, it wins.
3. `_bmad-output/implementation-artifacts/release-2/PROGRESS.md`
   What is already done. Read the last session entry at the bottom. Update it at the end
   of your run, before the session ends, even if the run fails.

## What to do

Work these six steps, in this order, one per commit, gates green between each:

- **Step 1** reconcile the nine fee documents (writes nothing)
- **Step 2, the unblocked half** create the four Commerce and Science class records, add
  `stream` to the class record, and place the 158 senior students whose stream the
  payment ledger names. Leave the rest; they need the school.
- **Step 3** load the fee structures
- **Step 4** transport: routes, the rate card, eleven months, and fix the flag that says
  no child uses the bus while 1,235 demonstrably pay for it
- **Step 5** the four concessions
- **Step 9** the late fine engine

Then stop and report. Steps 6, 7, 8, 10 and 11 are for a later run.

**Step 1 gates everything.** It writes nothing and needs no approval. If it turns up a
disagreement between the documents, stop and report it rather than picking a winner. A
wrong fee structure reaches 1,842 families and they find out through a bill.

## Rules that are not negotiable

- **One step per commit. Full gates green before the next one.**
  ```
  MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test \
    backend/.venv/Scripts/python.exe -m pytest tests/backend/ -q     # bar is 0 failed
  cd frontend && CI=true npx jest                                    # bar is 0 failed
  cd frontend && npm run build                                       # lint fails the deploy
  ```
- **Measure before and after, and explain every number that moves.**
  ```
  backend/.venv/Scripts/python.exe scripts/audit_profile_reach.py
  node scripts/audit_profile_menus.mjs
  ```
  A number that moved and was not intended is a defect, not a detail. None of these six
  steps should move a permission number at all; if one does, find out why before
  continuing.
- **Every write to the live database saves a rollback file first**, outside the
  repository, and is dry-run first. Abhimanyu has approved the fee writes; that approval
  does not extend to anything else.
- **Never run `backend/migrations/run_all.py`.** One migration at a time, after reading
  what that specific file does.
- **No long dashes anywhere in prose.** See `backend/ai/writing_style.py`.
- **Write to Abhimanyu in plain, non-technical language.** He relays these messages to the
  school. Plain does not mean softened: be just as direct about failures and risks.

## Things already established, so you do not rediscover them

- The payment ledger `aaryans_database/Fees-log-detailed-11-08-2026-17-36.xlsx` is the
  real thing: 10,720 fee lines, 3,177 receipts, 1,723 children, 3.56 crore collected,
  23 January to 7 August 2026. Its per-class amounts match the photographed fee sheet to
  the rupee on all seven bands.
- Transport is **eleven months, June excluded**. Confirmed exactly: 5,587 transport lines
  and not one June.
- **The late fine is where the previous vendor is wrong.** It keeps a quarter's daily fine
  running after the next quarter begins, so two accrue at once and families are
  overcharged. Only one daily fine ever runs, the current quarter's. The 1,000 at quarter
  end DOES repeat, four times over a full year of arrears. The fine is worked out on the
  whole outstanding bill, transport included.
- The seven sibling concession values are already loaded and correct. Do not recreate
  them.
- The four profiles' permissions are settled and pinned. `EXPECTED_REACH` in
  `tests/backend/unit/test_all_nine_profiles_sweep_r2_13.py` and `EXPECTED_SCREEN_COUNT`
  in `frontend/src/lib/__tests__/ProfileMenuSweep.test.js` are pinned counts. Never
  silence one; explain it.
- `frontend/src/lib/profileMatrix.generated.js` is generated. Regenerate with
  `backend/.venv/Scripts/python.exe scripts/generate_profile_matrix.py`.

## What is blocked, so do not wait on it and do not guess at it

- The stream for senior students beyond the 158 the ledger names.
- Confirming the 21 Right to Education children, and admission number 15067 whose name
  says RTE while the flag says no.
- Confirming the proposed sibling groups.
- What happens to the 1,844 children carrying fee figures labelled as not the ledger.
- The go-ahead to deploy.

If a step needs one of these, do the part that does not and say plainly what you left.

## When you finish

Update `PROGRESS.md` with a session entry saying what you did, what you proved, and what
is left. Push the branch. Then tell Abhimanyu, in plain words: what a person at the school
would now be able to do that they could not before, what you wrote to the live database
and how to undo it, and what still needs a human answer.
