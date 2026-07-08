# Epic Execution Protocol — AI Layer Reliability (R1–R11)

**Purpose:** Implement the AI Layer Reliability initiative **one Epic per run/context window**. This protocol is written for **any executing agent** — Anthropic models (Sonnet, Opus, Haiku or newer), OpenAI models, or any other coding agent. It assumes nothing about the agent except that it can read this repo, edit files, and run tests. Where BMAD skills are named, an agent without access to those skills must open the corresponding workflow file under `_bmad/` and follow its steps manually — the *workflow* is mandatory, the *skill invocation mechanism* is not.

**Predecessor:** `EPIC-EXECUTION-PROTOCOL.md` governed the (shipped) AI Layer Hardening initiative and is kept for history. THIS file governs R1–R11. Where they differ, this file wins.

---

## Portability guarantee — no dependence on any account, machine, or model

Everything an executing agent needs is **committed to this repository**; nothing required lives in any personal account memory, local settings, or a specific machine:
- The BMAD method itself: `_bmad/` (workflows/config) and `.claude/commands/bmad-*.md` (skill wrappers) are tracked in git. Agents without the Claude Code skill mechanism follow the `_bmad/` workflow files directly.
- All plan/audit/protocol docs use repo-relative paths only.
- The pinned test baseline is committed (`_bmad-output/ai-hardening-epic-a-baseline.txt`).
- Standing directives previously held in session memory are restated here as the source of truth:
  1. **Git push via the git CLI only** (authenticated as `4asaanAI`); never use a GitHub MCP/integration for pushes.
  2. **The 25 pinned pre-existing test failures are fixed LAST**, after all epics — never mid-epic.
  3. **DPDP guardrails stay surgical** — never over-block the LLM into refusals/non-compliance.
  4. **AI-write scope Phase 1 = Owner + Principal only** (lockdown policy); widening is a config/policy change, never an engine change.
- Environment note: local secrets (`backend/.env`) are machine-local by design and never required by these docs — tests run against fakes; anything needing real credentials must say so in plain English rather than assume them.

If a future session learns a NEW standing directive from Abhishek or Shubham, it must be added to this section (and committed) — never only to personal/session memory.

## The 7 standing rules (set by Abhishek, 2026-07-08 — do not relax)

1. **One run = one full Epic** (never one story, never two epics). A run ends only when the whole epic passes the epic-close gate (STEP 5).
2. **BMAD workflow steps are followed for every story and every epic** — even though the whole epic is done in one run, each story still individually goes through story-creation and dev-story discipline (context load, AC-driven implementation, self-review). No story is "just coded".
3. **Testing and quality checks run at the END of the EPIC, not per story.** Per-story you implement only; the full test suite, review skills, and quality gates run once, over the whole epic's combined diff, at epic close. (Exception: if a story's change breaks something so fundamentally that later stories can't proceed, run the minimum tests needed to unblock — then still do the full gate at the end.)
4. **Every run ends by emitting the next-epic handoff prompt in the FIXED format below, verbatim** — only the `{...}` slots change. This is what prevents drift across many fresh sessions and different models.
5. **Every run ends with the three log docs updated** (see "Logging" below): what was completed, what is pending/deferred, and every bug/finding from the epic-close review. Nothing lives only in the chat transcript.
6. **Anything new discovered mid-run** (a bug, a gap, a smell, a question) is either **fixed in this run** or **explicitly logged in the deferred log with a reason and a pointer** — never silently skipped.
7. **All communication with Abhishek or Shubham is in plain English.** Explain what happened and what it means for the school/product, not stack traces or jargon. Example: say "the assistant will now always answer or clearly say it hit a problem — it can no longer go silent" — not "Phase 14 now yields a fallback text_delta before done". Technical detail goes in the log docs, not in messages to people.

## Epic order (deterministic — do not reorder)

| # | Epic | Name | Next |
|---|------|------|------|
| 1 | **R1** | Turn Completion Contract (the incident fix) | R2 |
| 2 | **R2** | Confirmed-Write Integrity | R3 |
| 3 | **R3** | Prompt ↔ Registry Parity | R11.1* |
| 4 | **R11.1*** | Golden eval corpus + LLM-judge CI (pulled forward from R11) | R4 |
| 5 | **R4** | One Tool Envelope + Denied ≠ Empty | R5 |
| 6 | **R5** | Tenancy & Scope Fail-Closed | R6 |
| 7 | **R6** | Memory Subsystem Safety | R7 |
| 8 | **R7** | Data Correctness & Performance | R8 |
| 9 | **R8** | Frontend Chat Resilience | R9 |
| 10 | **R9** | Guardrails, Config & Adjacent Surfaces | R10 (GATED) |
| 11 | **R10** | Self-Learning Phase 2 — GATED: needs Abhishek's go-ahead after R1–R9 verified | R11 |
| 12 | **R11** | Excellence & Evaluation (remaining stories R11.2–R11.6) | — initiative complete |

*R11.1 runs as its own mini-run right after R3 so every later epic is guarded by the quality-eval gate.
After **R9**, do NOT auto-start R10 — the end-of-R9 handoff must state in plain English that the remaining two epics need Abhishek's explicit go-ahead, and stop.

## Logging (rule 5) — the three docs, updated at the END of every epic

All under `_bmad-output/implementation-artifacts/ai-reliability/`:

1. **`epic-{ID}-completed.md`** — per story: what was built, files touched, ACs met (checklist), tests added. Written fresh each epic.
2. **`DEFERRED-AND-DISCOVERIES.md`** — ONE running file across the whole initiative. Every mid-run discovery that was not fixed in-run gets a row: `date · epic · what was found · why deferred · where it should be fixed (epic/story or "new story needed")`. Items fixed in-run that were *outside* the epic's scope also get a row marked FIXED (so scope creep is visible). Review this file at the START of every run — if an entry belongs to the current epic, it must be handled now.
3. **`epic-{ID}-review.md`** — the epic-close quality gate output: findings table (`severity · file · issue · fix · regression test`), dismissed findings with reasons, final test counts, grep-audit results, eval scores (once R11.1 exists).

## The FIXED handoff-prompt format (copy VERBATIM; fill only the `{...}` slots)

```
You are the executing agent for the EduFlow "AI Layer Reliability" initiative, ONE EPIC per run. You may be any model (Anthropic, OpenAI, or other) — follow this protocol exactly; do not improvise the process.

CURRENT EPIC: {EPIC_ID} — {EPIC_NAME}

STEP 1 — Reload context (read in this order):
- _bmad-output/EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md  ← this process, the 7 standing rules, and this prompt format (follow EXACTLY)
- _bmad-output/planning-artifacts/epics-ai-layer-reliability.md      ← find Epic {EPIC_ID} + its stories/ACs (file:line targets included)
- _bmad-output/planning-artifacts/architecture-ai-layer-reliability.md ← target design + testing strategy
- _bmad-output/planning-artifacts/audit-ai-layer-reliability-2026-07-08.md ← the findings each story fixes
- _bmad-output/implementation-artifacts/ai-reliability/DEFERRED-AND-DISCOVERIES.md ← handle any entry that belongs to this epic
- _bmad-output/project-context.md AND CLAUDE.md ← platform rules (Python 3.9 future-annotations, no TypeScript, Motor async, tenancy, test conventions)

STEP 2 — Guardrails (NON-NEGOTIABLE, fixed text):
- PRIME DIRECTIVE: every story FIXES the underlying defect at its root. Error-surfacing/fallback UI is a safety net, never the fix. A story is not done if the bug still exists behind a nicer message.
- Do not regress: confirm-token → kill-switch → lockdown → audit gating on AI writes; DPDP guardrails stay surgical (never over-block); Owner/Principal-only Phase-1 AI writes; branch/school tenancy rules.
- Keep the full backend suite green versus the pinned baseline (the 25 pinned pre-existing failures are deferred to the END of the initiative — do not fix or worsen them mid-epic).
- Do NOT start any other epic. Anything discovered outside this epic's scope: fix it only if small and safe, and in all cases log it in DEFERRED-AND-DISCOVERIES.md (rule 6).

STEP 3 — Implement EVERY story in Epic {EPIC_ID}, in order. For EACH story follow the BMAD per-story discipline: bmad-create-story → bmad-dev-story (if these skills are unavailable in your harness, open the matching workflow under _bmad/ and follow its steps manually). Do NOT run the full test suite or review skills per story — implementation only (rule 3). Write tests as you go, but the quality gate is at epic close.

STEP 4 — MANDATORY EPIC-CLOSE QUALITY GATE (the epic is NOT done until this is clean), over the WHOLE epic's combined diff:
  a. Run the full backend suite (python -m pytest tests/backend/ -x -q) + any frontend tests touched; green vs pinned baseline, 0 skipped.
  b. Run ALL of: bmad-code-review, bmad-review-adversarial-general, bmad-review-edge-case-hunter, bmad-testarch-test-review, bmad-testarch-trace (every story AC traced to a test), bmad-testarch-nfr. (No skills? Follow the _bmad/ workflow files manually — the review lenses are mandatory either way.)
  c. FIX every finding NOW (with a fails-before/passes-after regression test) or dismiss it with a written reason. Bugs born in this epic never carry into the next.
  d. Re-run the scoped_filter/scoped_query grep audit on every touched backend file.
  e. From R11.1 onward: run the golden eval corpus; scores must be equal-or-better than the previous epic's record.

STEP 5 — Epic DONE criteria (all must hold):
- Every story's ACs met; STEP 4 gate fully clean.
- The three log docs written/updated: epic-{EPIC_ID}-completed.md, epic-{EPIC_ID}-review.md, DEFERRED-AND-DISCOVERIES.md (rule 5/6).
- Tracker updated: _bmad-output/platform-quality-sweep.md (AI Layer Reliability row). Commit + push to main via git CLI.

STEP 6 — MANDATORY FINAL STEP: emit the next-epic prompt.
- Copy this template VERBATIM from _bmad-output/EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md, fill ONLY {EPIC_ID}/{EPIC_NAME} from the epic-order table, and output it in a code block for the user to paste into a fresh session. Do NOT reword any step.
- If the finished epic is R9: do NOT emit the R10 prompt; state in plain English that the remaining self-learning and excellence epics need Abhishek's go-ahead, and stop.

STEP 7 — Report to the humans in PLAIN ENGLISH (rule 7): 2–6 sentences on what the assistant/platform now does better for the school, anything they should know or decide, and what comes next. No jargon, no file paths, no stack traces — that detail lives in the log docs.
```

## Rules that keep the prompt from drifting
1. The template above is the **single source of truth**. Sessions copy it verbatim and change only `{EPIC_ID}`/`{EPIC_NAME}` from the order table — never reword STEPs 1–7.
2. Guardrails (STEP 2) are fixed text; do not paraphrase or trim.
3. One epic per run — never chain two epics in one session.
4. If the plan changes, edit it **here** and in the epics doc — never ad-hoc inside a session's emitted prompt.
5. This protocol supersedes any per-story test/review habit an agent may have from BMAD defaults: **implementation per story, quality gate per epic** (rule 3).
