# Epic R11 — Excellence & Evaluation: COMPLETED

**Date:** 2026-07-10  
**Branch:** ai-reliability-r1-turn-completion  
**Suite result:** 1551 passed, 14 deselected (was 1527 before R11; +24 new tests)  
**Stories:** R11.1 (done after R3), R11.2, R11.3, R11.4, R11.5, R11.6

---

## Summary

R11 is the final epic of the AI Layer Reliability initiative (11 epics / ~51 stories). It moved the AI layer from "works reliably" to "works excellently": native Azure function calling eliminates invented-tool-name hallucinations at the API level; true token streaming delivers first-token latency; a language directive enables natural Hinglish/Hindi responses; a per-turn trace viewer makes the "AI didn't reply" incident class diagnosable from the panel (no server-log access); and a residual audit sweep closed the last two in-scope hardenings.

**Layaa AI confidentiality:** The user's binding constraint — Azure/OpenAI/model names must never appear on any client-facing surface — was implemented as a structural rule: provider/model stored internally in `ai_turn_traces` and `layaastat` only; the trace endpoint hardcodes `"assistant": "Layaa AI"` and drops all internal fields; a grep-verified provider-leak check confirms zero frontend hits.

---

## Stories Completed

### R11.1 — Eval Corpus & Judge Infrastructure (done after R3)
- 48-conversation eval corpus (`_bmad-output/test-artifacts/eval-corpus/corpus.json`)
- Structural test gate (`test_eval_corpus_structure.py`)
- LLM-judge scaffold + regression-block logic (`evals/judge.py`, `test_eval_judge_logic.py`)
- Baseline: structural/judge-logic tiers always-on; credentialed LLM tier deferred to nightly CI

### R11.2 — Native Azure Function Calling
- **Files changed:** `backend/ai/llm_client.py`, `backend/ai/tool_functions_v2.py`, `backend/routes/chat.py`
- Added `ToolCall` + updated `LLMResult` dataclasses in `llm_client.py`
- Added `_build_messages()` to handle role=tool + assistant-with-tool_calls turn shapes
- Added `chat()` params: `tools: list`, `tool_choice: str`; returns `LLMResult.tool_calls`
- Added `openai_tool_schema()` in `tool_functions_v2.py` — derives provider schema directly from TOOL_REGISTRY (single source of truth)
- Added `_tool_calls_to_candidates()`, `_build_llm_tools()` in `chat.py`
- Phase 7 write-param extraction now uses `tool_choice={"type":"function","function":{"name":...}}` (native forced-tool call)
- Phase 8: model receives authorized tool schemas; model can no longer emit JSON-in-text or invent a tool name
- **Deleted:** `_normalize_tool_call`, `_parse_tool_calls`, `_parse_tool_call`, `_strip_tool_json_from_text`
- Azure verification: `gpt-4.1` on CockRoach endpoint returns structured `tool_calls`, `finish_reason=tool_calls` ✓

### R11.3 — True Token Streaming
- **Files changed:** `backend/ai/llm_client.py`, `backend/routes/chat.py`
- Added `chat_stream()` async generator: drains Azure sync SDK stream on daemon thread via `queue.Queue(maxsize=256)`, bridges to event loop via `asyncio.to_thread(q.get)`
- Added `_RICH_MARKER`, `_stream_final_answer()`: streams visible prefix; holds back trailing run that could be a forming `<<<RICH_CONTENT>>>` marker; fills `sink` dict on completion or error
- Phase 13: `stream_final` boolean enables streaming for non-student roles; progressive-enhancement falls back transparently to buffered path if streamed text is empty
- Mid-stream error (R1 AC3): partial text preserved, appended with `_(reply interrupted — please retry)_`

### R11.4 — Hindi/Hinglish Language Competence
- **Files changed:** `backend/ai/prompts.py`, `_bmad-output/test-artifacts/eval-corpus/corpus.json`
- `TOOL_CALL_FORMAT` rewritten for native FC (no JSON-emission instructions)
- Added 5-line language directive: English→English, Devanagari→Hindi, Hinglish→Hinglish, data fields verbatim
- Corpus expanded 48→52: 10 Hinglish-tagged entries (was 6), 2 Devanagari-tagged (new)
- `test_eval_corpus_structure.py` gate updated: `hinglish >= 8`, `devanagari >= 1`

### R11.5 — Conversation Trace Viewer
- **Files changed:** `backend/routes/chat.py`, `backend/database.py`, `frontend/src/components/tools/ConversationTrace.js`, `frontend/src/lib/api.js`, `frontend/src/components/Layout.js`, `frontend/src/components/ToolDashboard.js`
- Added `_record_turn_trace()` (fail-open) — persists to `ai_turn_traces` at all major exits
- Added `GET /api/chat/conversations/{conv_id}/trace` (owner-only, school-scoped)
- Response abstracts provider: `"assistant": "Layaa AI"` hardcoded; `provider`/`model` fields never returned
- Frontend `ConversationTrace.js` panel — per-turn outcome/language/tools timeline
- New index: `ai_turn_traces (conversation_id, created_at)` in `database.py`

### R11.6 — Residual Audit Sweep (in-scope hardenings only)
- **Files changed:** `backend/services/idempotency.py`, `backend/services/ai_metrics.py`
- `get_replay_response`: added `"schoolId": get_school_id()` to `find_one` filter (defence-in-depth)
- `_FORBIDDEN_KEYS` expanded: 7→~20 PII synonyms (student, guardian_phone, parent, contact, mobile, title, content, message, reason, date_of_birth, aadhaar, full_name, label, query)
- 4 larger findings deferred (see DEFERRED-AND-DISCOVERIES.md): rate-limiter ScopedCollection gap, actor_context naive clock, sse.py eviction, ai_shadow_mode force_fresh

---

## New Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `tests/backend/api/test_r11_native_function_calling.py` | 8 | R11.2 + R11.3 |
| `tests/backend/api/test_r11_trace_viewer.py` | 6 | R11.5 |
| `tests/backend/unit/test_r11_hinglish.py` | 8 | R11.4 |
| `tests/backend/unit/test_r11_residual_audit.py` | 2 | R11.6 |
| `frontend/src/components/__tests__/ConversationTrace.test.js` | 2 | R11.5 frontend |
| Total | 26 new | — |

---

## Modified Tests

| File | Change |
|------|--------|
| `tests/backend/unit/test_chat_confirm_gate_phase5.py` | Removed old JSON-in-text parser tests; added 3 native FC tests |
| `tests/backend/unit/test_p3_error_opacity.py` | Removed `_parse_tool_calls` tests; added `_tool_calls_to_candidates` defensive tests |
| `tests/backend/evals/test_eval_corpus_structure.py` | Bumped Hinglish gate ≥8; added Devanagari gate ≥1 |
| `tests/backend/conftest.py` | Added `self.ai_turn_traces = FakeCollection()` to FakeDb |

---

## Quality Gate

- ✅ Full backend suite: **1551 passed, 14 deselected, 0 skipped**
- ✅ Eval corpus structural + judge-logic tests: **18 passed**
- ✅ R11 test files: **24 passed** (all stories)
- ✅ scoped_filter/scoped_query audit: clean (conversation/trace routes school-scoped; no branch needed)
- ✅ Provider-leak grep: zero hits in all new/modified frontend files
- ✅ Code review (adversarial, edge-case, AC trace, NFR): no critical findings
