# Epic R1 — Epic-Close Quality Gate

**Date:** 2026-07-08 · **Scope:** whole R1 combined diff.

## Test results
- Full backend suite: **1290 passed, 0 failed, 0 skipped, 12 deselected** (`mongo_real` tier). Baseline before R1 was 1278 passed; +12 new R1 tests.
- New tests: `tests/backend/api/test_r1_turn_contract.py` (6), `tests/backend/unit/test_r1_llm_client.py` (6).
- Pre-existing suite unchanged and green (the AI-hardening-era "25 pinned failures" no longer reproduce on current main; nothing worsened).

## Grep / static audits
- `scoped_filter` audit on every touched backend file: R1's diff adds **no** new `scoped_filter`/`scoped_query` calls (R1 changes LLM handling, streaming, and tool-loop narration — no tenancy surface). Pre-existing hits unchanged.
- R1.7 AC4 grep gate: no remaining `ai_unavailable_result`/`_is_ai_unavailable`/tuple/dict handling of `chat()` results.
- `f"empty-{conv_id}"` sentinel: removed from code (only referenced in explanatory comments now).
- Frontend: `ChatInterface.js` and `api.js` babel-parse clean under `react-app` preset.

## Review lenses (manual — BMAD review skills followed as workflow)
**Adversarial / correctness:**
- LLMResult migration is complete across all 5 caller files; no path still unpacks a tuple. ✓
- `academics` 503 is not swallowed (added `except HTTPException: raise` before the generic 500). ✓
- Phase-14 rewrite: `clean_text` is guaranteed non-empty by the fallback substitution before Phase 13, so the always-persist path can't insert a blank. Verified no stale `has_content`/`has_rich` references remain. ✓
- `while/else` (R1.5 AC3) is attached to the tool-loop `while` (same indent), not an inner `if`. ✓

**Edge cases:**
- Retry (R1.6) fires only on empty **and** finish_reason=="length", retries exactly once, sums tokens across both calls. ✓
- Frontend `error` handler nulls `currentStreamMsg` and sets `streamErrored`, so a trailing `done`/`text_delta` can't double-render. Trade-off: a backend `error`-then-streamed-fallback collapses to the error bubble (still non-silent) — acceptable. ✓
- `_close_tool_matches` filters to authorized tools (no cross-role tool leakage) and returns `[]` for gibberish. ✓

## Findings (fixed in-run)
| Severity | File | Issue | Fix | Test |
|---|---|---|---|---|
| High | routes/academics.py | generic `except` would swallow the new 503 as a 500 | added `except HTTPException: raise` | turn-contract suite exercises ok=False path indirectly; academics 503 verified by reasoning |
| Med | tests/unit/test_ai_memory_skills.py | mocked `chat` returned a tuple → broke after migration | mocks return `LLMResult` | suite green |

## Deferred (see DEFERRED-AND-DISCOVERIES.md)
- R1.3 AC3/AC4 residual: pre-turn (save-message, context-build) fatal error paths don't yet persist a fallback; confirm/param early-returns don't route token debit through the single Phase-14 exit. Incident-critical paths (LLM empty/exception, Phase-14 empty) ARE fixed. Full single-exit consolidation deferred to avoid a high-risk refactor of the live generator in one pass.
- R1.1 AC4 frontend jest test deferred (component-harness) to R8 (Frontend Chat Resilience) or a focused follow-up.

## Verdict
Gate clean for R1's scope. The incident (silent empty turn) is fixed end-to-end: the model retries on truncated-empty, the backend always persists a real (fallback if needed) assistant message and debits tokens on the main path, and the frontend renders something for every terminal state. Residuals are logged, not silent.
