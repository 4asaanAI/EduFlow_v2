# Epic Execution Protocol — EduFlow AI Layer Hardening

**Purpose:** Implement this initiative **one Epic per context window**. Each session implements exactly one Epic, then emits a handoff prompt — in the **fixed format below** — for the next context window. The format is fixed and reused verbatim (only the epic identifiers change) so the prompt **does not drift** across epics.

## Epic order (deterministic — do not reorder)

| # | Epic | Name | Next |
|---|------|------|------|
| 1 | **A** | Trustworthy single-writer foundation (aligned domains) | B |
| 2 | **B** | Parity + defect resolution (fees, discounts, house-points) | C |
| 3 | **C** | Parity — dynamic-collection incident/complaint tools | D |
| 4 | **D** | Safe execution — atomic, idempotent, real-Mongo test tier | E |
| 5 | **E** | Whole-job-by-instruction — planner + plan-then-confirm-once | I |
| 6 | **I** | Frontend — multi-step plan card & status messaging | F |
| 7 | **F** | Compliant & operable — DPDP + safety-ops + parity harness | J |
| 8 | **J** | Student & staff CRUD (hardened AI tools) | K |
| 9 | **K** | School-internals CRUD (hardened AI tools) | G |
| 10 | **G** | AI self-learning (Memory + Skills) — cloned from Odysseus | H |
| 11 | **H** | (Phase 2 — GATED on Owner/Principal pilot sign-off) Role extension | — (initiative complete) |

> After **G**, the next Epic is **H**, but **H is Phase 2 and is GATED on the Owner+Principal pilot sign-off** — do not auto-start it; the end-of-G prompt must say so and stop.

## The FIXED handoff-prompt format (copy verbatim; fill only the 4 `{...}` slots)

```
You are implementing the EduFlow "AI Layer Hardening" initiative, ONE EPIC per context window.

CURRENT EPIC: {EPIC_ID} — {EPIC_NAME}

STEP 1 — Reload context (read in this order):
- _bmad-output/EPIC-EXECUTION-PROTOCOL.md   ← this process + the fixed prompt format (follow EXACTLY)
- AI-LAYER-HARDENING-HANDOFF.md             ← initiative overview
- _bmad-output/planning-artifacts/epics-ai-layer-hardening.md      ← find Epic {EPIC_ID} + its stories
- _bmad-output/planning-artifacts/architecture-ai-layer-hardening.md  ← ADs + 8 patterns
- _bmad-output/planning-artifacts/prd-ai-layer-hardening.md        ← FRs/NFRs
- _bmad-output/project-context.md AND CLAUDE.md                    ← platform rules

STEP 2 — Guardrails (NON-NEGOTIABLE):
- Phase-1 = Owner + Principal ONLY (Story F.11 / FR43 lockdown); students unchanged & excluded; data scope = whole school DB those two are authorized over (Owner cross-branch, Principal scoped).
- No new UI surface. Plan-then-confirm-once. AI↔UI parity via the shared service layer (AD7). DPDP controls (Azure residency deferred; PII-minimization is a hard control).
- Preserve Part 2 invariants; keep the existing 699 backend tests green (0 skipped). Python 3.9: `from __future__ import annotations` first line where union syntax is used. No TypeScript.
- Clone-from-Odysseus where the epic/stories say so (esp. Epic G memory/skills; Epic E planner patterns).

STEP 3 — Implement EVERY story in Epic {EPIC_ID}, in order, using the per-story loop:
  bmad-create-story  →  bmad-dev-story  →  run tests  →  bmad-code-review
Characterization-test-FIRST for any service extraction (pin REST behavior, then prove AI path byte-identical). Add migrations + regression guards exactly as the stories specify. Do NOT start any later Epic.

STEP 4 — Epic DONE criteria (all must hold):
- Every story's Given/When/Then ACs met; new + existing tests green (>=699, 0 skipped); parity/regression tests added where required.
- `scoped_filter`/`scoped_query` audit clean on every touched route file (CLAUDE.md rule).
- Tracker row 17 in _bmad-output/platform-quality-sweep.md updated; commit + push to branch `ai-layer-hardening-plan`.

STEP 5 — MANDATORY FINAL STEP (prevents drift): emit the next-Epic prompt.
- Open _bmad-output/EPIC-EXECUTION-PROTOCOL.md, copy this fixed template VERBATIM, and fill ONLY {EPIC_ID}/{EPIC_NAME} with the NEXT epic per the "Epic order" table, then output it in a code block for the user to paste into a fresh context window. Do NOT reword the template.
- If the just-finished epic was the LAST before a gate (after G → H), DO NOT emit an H prompt: instead state that Phase 1 is complete and H is gated on the Owner/Principal pilot sign-off.
```

## Rules that keep the prompt from drifting
1. The template above is the **single source of truth**. Sessions **copy it verbatim** and change only the `{EPIC_ID}` and `{EPIC_NAME}` slots from the order table — never reword STEPs 1–5.
2. Guardrails (STEP 2) are fixed text; do not paraphrase or trim them.
3. One Epic per context window — never chain two epics in one session (keeps context lean and the protocol intact).
4. If the plan changes, edit it **here** (and in the epics doc), not ad-hoc inside a session's emitted prompt.
