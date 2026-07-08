# Epic R11.1 — Golden Eval Corpus + LLM-judge CI · Completed Log

**Goal:** a quality-regression gate for the AI layer — pulled forward to run right
after R3 so every later epic (R4→R9) ships measured. Implements audit-plan R11.1.

**Branch:** `ai-reliability-r1-turn-completion` (same branch as R1/R2/R3 per standing instruction).
**Baseline:** 1326 passed (after R3) → **after R11.1: 1344 passed / 0 failed / 0 skipped** (14 deselected = 13 mongo_real + 1 credentialed llm_eval).

---

## What was built

A three-tier evaluation harness. No backend source files were modified — the harness
reuses the real prompt pipeline (`build_system_prompt`, `LLMClient.chat`).

### The corpus (AC1)
`_bmad-output/test-artifacts/eval-corpus/corpus.json` — **48 golden conversations**:
- Every role/sub_category variant in `TOOLS_BY_ROLE` (owner, principal, accountant,
  transport_head, receptionist, it_tech, maintenance, class_teacher, hod,
  coordinator, subject_teacher, kg_incharge, student, support_staff).
- The production **incident** conversation (owner "summarise today…" — must never go silent).
- **Follow-ups** referencing a prior turn (2), **ambiguous** asks (2), **denials** (6
  — a role asking for something outside its toolset), and **Hinglish** variants (6).
- Each entry declares `expected_tool`, `expected_outcome`
  (`answer|confirm|denial|disambiguation|chat`), `language`, `tags`, and a `rubric`.

### Tier 1 — deterministic structural eval (AC1 coherence, runs every CI run)
`tests/backend/evals/test_eval_corpus_structure.py` (7 tests, no credentials):
- ≥40 conversations, unique ids, every variant + every scenario tag covered.
- **Coherence invariant:** answer/confirm entries' `expected_tool` exists AND is
  advertised to the role; denial entries' tool is NOT advertised (that is what makes
  the refusal correct); disambiguation/chat name no tool.
- The real `build_system_prompt` produces a usable prompt advertising the expected
  tool for every entry.
This tier makes the corpus a living artifact that fails if it drifts from the
prompt↔registry wiring — complementing R3's parity gate.

### Tier 2 — judge-logic unit tests (AC2 plumbing, runs every CI run)
`tests/backend/evals/judge.py` + `test_eval_judge_logic.py` (11 tests, no credentials):
- Pure functions `parse_judge_scores` (robust JSON extraction, clamps to [0,1],
  missing/garbage → 0.0 worst-case), `aggregate` (per-dimension + overall means; an
  errored/silent turn scores 0.0, never excused), `regression_check` (blocks on a
  >threshold drop vs baseline; accepts within-threshold + improvements; first run
  establishes the baseline).
- `run_eval` orchestration verified end-to-end with a FAKE assistant + judge,
  including the incident case (empty reply → recorded as error → overall 0.0).

### Tier 3 — credentialed LLM-judge gate (AC2, `@llm_eval`, deselected by default)
`tests/backend/evals/test_eval_llm_judge.py`:
- Runs the whole corpus through the real prompt pipeline + a real Azure LLM judge,
  scores correctness/completeness/tone per rubric, and **blocks** if any dimension
  drops >0.05 below the recorded baseline (`scores-baseline.json`, written on the
  first credentialed run).
- Marked `llm_eval` and deselected via `addopts -m "not mongo_real and not llm_eval"`,
  so it is neither run nor skipped in the standard suite (0 skips preserved). Run in
  credentialed nightly/pre-release CI with `pytest -m llm_eval`.

### AC3 — process rule
`EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md` gained a standing directive: any change
to `prompts.py` / `tool_functions*.py` / `context_builder.py` / `llm_client.py` /
the tool-loop must keep the always-on evals green and run the credentialed LLM-judge
tier (equal-or-better than baseline) before merge. `pytest.ini` registers the
`llm_eval` marker; `tests/backend/evals/README.md` documents how to run each tier.

---

## ACs
- **AC1** ✅ 48 conversations (≥40), full role/sub_category + incident + follow-ups + ambiguous + denials + Hinglish coverage, structurally validated.
- **AC2** ✅ LLM judge scores correctness/completeness/tone per rubric; >threshold drop vs baseline blocks release; plumbing unit-tested with fakes.
- **AC3** ✅ documented in the execution protocol + README; `llm_eval` marker registered.

## Note on STEP 4e (eval scores equal-or-better)
R11.1 CREATES the eval corpus, so there is no prior epic's score record to beat — this
epic establishes the baseline. The always-on structural + judge-logic tiers are green
in CI. The credentialed LLM-judge baseline is written on the first run in an
environment with Azure OpenAI credentials (not available in this dev/test environment
by design — tests run against fakes). From R4 onward, STEP 4e compares against that
baseline.

## Files added
- `_bmad-output/test-artifacts/eval-corpus/corpus.json` (48 conversations).
- `tests/backend/evals/`: `__init__.py`, `corpus.py`, `judge.py`,
  `test_eval_corpus_structure.py`, `test_eval_judge_logic.py`,
  `test_eval_llm_judge.py`, `README.md`.
- Modified: `pytest.ini` (llm_eval marker + deselect), `EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md` (AC3 rule).
