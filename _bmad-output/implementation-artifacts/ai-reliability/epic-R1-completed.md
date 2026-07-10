# Epic R1 — Turn Completion Contract — COMPLETED

**Date:** 2026-07-08 · **Executing model:** Claude Opus 4.8
**Baseline before:** 1278 passed, 0 failed, 12 deselected
**Baseline after:** 1290 passed, 0 failed, 12 deselected (12 new R1 tests)

Goal: no user chat turn can ever end with nothing on screen. Fixes RC-1…RC-5, S1–S13.

---

## R1.7 — Kill the tuple|dict dual return (LLMResult)
Files: `backend/ai/llm_client.py`, `backend/routes/chat.py`, `backend/routes/academics.py`, `backend/routes/assistant.py`, `backend/services/memory/extractor.py`
- [x] AC1: `chat()` returns `LLMResult(text, tokens, ok, reason)` dataclass. No caller does isinstance/tuple/dict gymnastics.
- [x] AC2: `academics.generate_question_paper` stores/returns `result.text` only; `ok=False` → HTTPException 503 (fixes X1 — previously persisted the tuple/dict as paper content). Added `except HTTPException: raise` so the 503 isn't swallowed by the generic 500 handler.
- [x] AC3: `assistant.py` returns a 503 error payload on `ok=False`, not `success:True` wrapping the failure.
- [x] AC4: grep gate clean — no remaining tuple/dict handling of `llm_client.chat` results (the `result` at chat.py:~2818 is a tool-dispatch result, not an LLM result).
- Tests: `tests/backend/unit/test_r1_llm_client.py` (LLMResult shape, not-configured/empty/exception → ok=False).

## R1.6 — finish_reason retry + completion headroom
Files: `backend/ai/llm_client.py`
- [x] AC1: empty content + `finish_reason == "length"` → retry once with more headroom; logged at warning with finish_reason.
- [x] AC2: default `max_completion_tokens` raised 1200 → 4000 (`DEFAULT_MAX_COMPLETION_TOKENS`).
- [x] AC3: empty content (even after retry) returns a typed failure (`ok=False`), never a "successful" empty string.
- **Deliberate refinement (logged):** AC1 literally says "retry with 4000", but with the default already 4000 (AC2) that retry would be a no-op. The retry uses `RETRY_MAX_COMPLETION_TOKENS = 8000` so it is actually effective — honours AC2 exactly and AC1's intent (retry with *raised* budget). Test asserts retry uses more headroom than the first call.

## R1.3 — Phase 14 turn-completion choke point
Files: `backend/routes/chat.py`
- [x] AC1: empty final turn → `clean_text = FALLBACK_TEXT`, streamed as `text_delta`, persisted with a real uuid `message_id` (the `f"empty-{conv_id}"` sentinel + no-persist short-circuit is deleted).
- [x] AC2: every assistant turn is persisted (the confirm/param/unavailable early-returns already persisted; the only non-persisting path — the empty Phase-14 branch — is fixed).
- [x] AC3 (incident path): the Phase-8 first-LLM error path now persists an assistant message with the same text + `done` real id. Phase-13 streaming error falls through to the (now always-persisting) Phase 14. Phase-9 tool-loop exceptions covered by R1.5 AC4. **Partial (logged):** the pre-turn Phase-1 (save-message) and Phase-4 (context-build) fatal error paths still `yield error + done` without persisting — see DEFERRED.
- [x] AC4 (incident path): tokens are now debited on the empty/fallback turn (previously the empty short-circuit skipped `record_usage`). **Partial (logged):** the confirm/missing-param/resolution-error early returns still don't route through the single Phase-14 debit — see DEFERRED.
- [x] AC5: turn-contract test (`tests/backend/api/test_r1_turn_contract.py`) covers LLM empty/unavailable, LLM exception, marker text, and normal answer — each asserts a persisted assistant message + a `done` with a real id.

## R1.4 — `_CONTENT_POLICY_MARKERS` never blanks the reply
Files: `backend/routes/chat.py`
- [x] AC1: a marker match replaces the response with `FALLBACK_TEXT`, never `""`.
- [x] AC2: removed the innocuous markers ("try rephrasing your question", "wasn't able to process that") that were nuking genuine replies; kept only true policy boilerplate.
- [x] AC3: covered by `test_content_policy_marker_becomes_fallback_not_blank` (a response containing policy boilerplate reaches the user as fallback, never silence).

## R1.5 — Narrate tool-loop dead ends
Files: `backend/routes/chat.py`
- [x] AC1: unknown tool → `I don't have a capability called "X".` + close authorized matches (`_close_tool_matches`, filtered to tools the caller may use so it can't leak other roles' tools). No bare `break`.
- [x] AC2: unauthorized tool → `That action isn't available for your role.` (distinct from unknown).
- [x] AC3: MAX_TOOL_ROUNDS exhausted with a still-pending tool call → `This request needs more steps than I can chain…` (via `while/else`).
- [x] AC4: Phase-9 loop-body exception → `error` event AND a persisted fallback message (falls through to Phase 14).
- Tests: `_close_tool_matches` unit test; loop narration exercised structurally + normal path in the turn-contract suite.

## R1.1 — Frontend: handle `error` events + unknown-event default
Files: `frontend/src/components/ChatInterface.js`, `frontend/src/lib/api.js`
- [x] AC1: `event.type === 'error'` renders an interrupted assistant bubble with the server message + Retry (reuses the `stream_error` affordance).
- [x] AC2: default `else` branch → `console.warn('unhandled SSE event', …)`.
- [x] AC3: malformed SSE JSON in `api.js` now `console.warn`s instead of `catch {}`.
- [ ] AC4 (deferred): a jest unit test simulating each event type — see DEFERRED (frontend component-harness; behavior covered by the backend turn-contract test + manual reasoning). Both changed files babel-parse clean.

## R1.2 — Frontend: never render nothing on `done`
Files: `frontend/src/components/ChatInterface.js`
- [x] AC1: an empty finalized assistant message is no longer filtered out of the render — it shows "The assistant couldn't produce a reply. Try again."
- [x] AC2: post-await backstop — if a turn produced no user-visible output and no pending final message, a fallback bubble is rendered (`producedOutput` flag; covers S12 silent resolves).
- [x] AC3: the `done` dedupe no longer gates on `processedMessageIds` (which could silently drop streamed content, S10/FM2) — the streamed body is always finalized; the flush effect still dedupes by id.
