# Inspection Remediation — Execution Protocol (2026-08-04)

Governs the 14 findings from the 2026-08-04 platform inspection.
Register of findings: `_bmad-output/planning-artifacts/inspection-findings-2026-08-04.md`
Report: `https://claude.ai/code/artifact/d43debb3-779b-4068-bc3e-7988e78a1541`

This protocol is modelled on `EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md` and inherits its
7 standing rules unchanged. Where the two differ, the difference is stated explicitly below.

## Portability guarantee

Any capable coding model may execute this, on any machine, in any harness. The protocol never
depends on a particular account, a particular tool being installed, or memory from a previous
session. **All state lives in the register file, never in the prompt.** The prompt carries only
which block is current. That is the anti-drift mechanism: a prompt that carries state drifts as
it is retyped; a prompt that carries a pointer cannot.

## Inherited standing rules (from EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md, do not relax)

Rules 1–7 apply, with these substitutions for this initiative:

- **Rule 1 becomes: one run = one BLOCK of tasks** (five tasks, or four in the final block).
  Never one task, never two blocks.
- **Rule 3 becomes: implement per task, run the full quality gate once per block.** Exception
  unchanged: if a task breaks something so fundamentally that later tasks cannot proceed, run
  the minimum needed to unblock, then still do the full gate at block close.
- Rules 2, 4, 5, 6, 7 apply verbatim. In particular **rule 7**: every message to Abhimanyu or
  Shubham is plain English, no file paths, no jargon.

Two additions specific to this initiative:

- **Rule 8 — the baseline is 0 failures from T2 onward.** Before T2 the backend suite is
  1967 passed / 1 failed. After T2 it is 1967+ passed / **0 failed**. Any later block that ends
  with a failing test has not passed its gate. Do not re-pin a non-zero baseline.
- **Rule 9 — a task that needs Abhimanyu's decision stops and asks, in plain English, before any
  code is written for it.** It is marked `⏸ Blocked on owner` in the register and the block
  continues with the next task. A blocked task never silently becomes a guess. T1, T8 (second
  half), T9 (if credentials are unavailable) and T14 are known to need him.

## Prime directive

Every task **fixes the underlying defect at its root**. A nicer error message is a safety net,
never the fix. A task is not done if the problem still exists behind better wording.

## Block order (deterministic — do NOT reorder)

| Block | Tasks | Theme | Next |
|---|---|---|---|
| **BLOCK 1** | T1–T5 | Make it correct; make the safety net trustworthy | BLOCK 2 |
| **BLOCK 2** | T6–T10 | Correctness under real data volume, and cost | BLOCK 3 |
| **BLOCK 3** | T11–T14 | Hygiene and standing risk | initiative complete |

Task detail, in order, is in the register. Do not re-derive the order from severity.

## Logging (rule 5) — updated at the END of every block

Under `_bmad-output/implementation-artifacts/inspection-2026-08-04/`:

1. **`block-{N}-completed.md`** — per task: what was built, files touched, how it was proven,
   tests added. Written fresh each block.
2. **`block-{N}-review.md`** — the block-close gate output: findings table
   (`severity · file · issue · fix · regression test`), dismissed findings with reasons, final
   test counts, audit results.
3. The **register** (`planning-artifacts/inspection-findings-2026-08-04.md`) — Status column
   updated for every task touched. This is the file the next session reads.
4. **`HUMAN-VERIFICATION-CHECKLIST.md`** (the existing one under `ui-sweep/`) — append anything
   Abhimanyu must check or decide from his side. Never delete a ticked item.
5. Anything discovered mid-run that is not fixed in-run goes in the existing
   `ui-sweep/DEFERRED-AND-DISCOVERIES.md` with a reason and a pointer (rule 6).

## The FIXED handoff-prompt format (copy VERBATIM; fill only the `{...}` slots)

```
You are the executing agent for the EduFlow "Inspection Remediation" initiative (findings from the 2026-08-04 platform inspection), ONE BLOCK per run. You may be any model — follow this protocol exactly; do not improvise the process.

CURRENT BLOCK: {BLOCK_ID} — tasks {TASK_RANGE}

STEP 1 — Reload context (read in this order, do not skip):
- _bmad-output/INSPECTION-REMEDIATION-PROTOCOL-2026-08-04.md  ← this process, the standing rules, and this prompt format (follow EXACTLY)
- _bmad-output/planning-artifacts/inspection-findings-2026-08-04.md  ← the register: find {BLOCK_ID}'s tasks, their detail, and the CURRENT Status of every task. The register is the source of truth, not this prompt.
- _bmad-output/implementation-artifacts/ui-sweep/DEFERRED-AND-DISCOVERIES.md  ← handle any entry that belongs to a task in this block
- _bmad-output/project-context.md AND CLAUDE.md  ← platform rules (Python 3.9 future-annotations, no TypeScript, Motor async cursors, tenancy, API/response conventions, test conventions)

STEP 2 — Guardrails (NON-NEGOTIABLE, fixed text):
- PRIME DIRECTIVE: every task fixes the defect at its ROOT. A nicer error message is a safety net, never the fix. A task is not done if the problem still exists behind better wording.
- Do not regress: confirm-token → kill-switch → lockdown → audit gating on AI writes; Owner/Principal-only Phase-1 AI writes; school and branch tenancy; DPDP redaction stays surgical and never over-blocks.
- The backend suite baseline is 1967 passed / 1 failed BEFORE T2, and 0 failed from T2 onward. Never re-pin a non-zero baseline.
- Any change to ai/prompts.py, ai/tool_functions*.py, ai/context_builder.py, ai/llm_client.py, or the chat tool-loop requires the structural + judge-logic evals green before the block closes.
- A task needing Abhimanyu's decision STOPS and ASKS in plain English before any code is written for it; mark it "⏸ Blocked on owner" in the register and continue with the next task. Never guess on his behalf.
- Do NOT start any task outside {BLOCK_ID}. Anything discovered outside this block's scope: fix it only if small and safe, and in all cases log it in DEFERRED-AND-DISCOVERIES.md.
- No production system is touched and no live school data is read or written without Abhimanyu's explicit approval in this session, with a stated rollback path.

STEP 3 — Work the tasks of {BLOCK_ID} in register order, one at a time. For each task: read its register entry in full, implement the root fix, write the tests that prove it, and update that task's Status in the register to "✅ Done (date)" or "⏸ Blocked on owner (reason)". Implementation only per task — do NOT run the full suite or the review lenses per task; the gate is at block close.

STEP 4 — MANDATORY BLOCK-CLOSE QUALITY GATE (the block is NOT done until this is clean), over the WHOLE block's combined diff:
  a. Full backend suite: python -m pytest tests/backend/ -q with MONGO_URL and DB_NAME pinned to a LOCAL test database. Zero failures (see the baseline rule above).
  b. Frontend: CI=true npx craco test --watchAll=false, and a production build.
  c. Run the review lenses: bmad-code-review, bmad-review-adversarial-general, bmad-review-edge-case-hunter, bmad-testarch-test-review, bmad-testarch-trace. If those skills are unavailable in your harness, follow the matching workflow files under _bmad/ manually — the lenses are mandatory either way.
  d. FIX every finding NOW with a fails-before/passes-after regression test, or dismiss it with a written reason. Defects born in this block never carry into the next.
  e. Re-run the scoped_filter/scoped_query audit on every touched backend file.
  f. If the AI layer was touched: structural + judge-logic evals green.

STEP 5 — Block DONE criteria (all must hold):
- Every task in {BLOCK_ID} is either Done or explicitly Blocked-on-owner in the register, with no task silently skipped.
- STEP 4 gate fully clean.
- Logs written: block-{N}-completed.md, block-{N}-review.md, the register Status column, HUMAN-VERIFICATION-CHECKLIST.md (append anything Abhimanyu must check or decide), DEFERRED-AND-DISCOVERIES.md (anything found but not fixed).
- Committed on a branch and pushed. Do NOT merge to main without Abhimanyu's explicit go-ahead in this session — merging to main auto-deploys the app to the school.

STEP 6 — MANDATORY FINAL STEP: emit the next-block prompt.
- Copy this template VERBATIM from _bmad-output/INSPECTION-REMEDIATION-PROTOCOL-2026-08-04.md, fill ONLY {BLOCK_ID} and {TASK_RANGE} from the block-order table, and output it in a code block for the user to paste into a fresh session. Do NOT reword any step, do NOT summarise it, and do NOT add what happened this run — the register carries that.
- If the finished block is BLOCK 3: do not emit another prompt. State in plain English that all 14 findings are closed or waiting on him, and list what is waiting.

STEP 7 — Report to the humans in PLAIN ENGLISH (rule 7): 2–6 sentences on what is better for the school now, anything Abhimanyu must decide or check, and what comes next. No file paths, no jargon, no stack traces — that detail lives in the logs.
```

## Rules that keep the prompt from drifting

1. The template above is the **single source of truth**. Sessions copy it verbatim and change
   only `{BLOCK_ID}` and `{TASK_RANGE}` from the block-order table. Never reword STEPs 1–7.
2. Guardrails (STEP 2) are fixed text. Do not paraphrase, trim, or "improve" them.
3. **The prompt never carries progress.** It does not say what was finished, what broke, or what
   is left. All of that is read from the register in STEP 1. A prompt that carries state drifts;
   a prompt that carries a pointer cannot.
4. One block per run. Never chain two blocks in one session.
5. If the plan changes, edit it **here and in the register** — never ad-hoc inside a session's
   emitted prompt.
6. This protocol supersedes any per-task test/review habit an agent may bring from BMAD
   defaults: **implementation per task, quality gate per block.**
