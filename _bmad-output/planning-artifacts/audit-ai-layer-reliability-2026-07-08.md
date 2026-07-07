# AI Layer Reliability Audit & Incident Investigation

**Date:** 2026-07-08
**Trigger:** Production incident — school owner (Aman Litt, The Aaryans) asked the AI chat "Who all are included in staff?" as a follow-up and received **no reply at all** — no answer bubble, no error card. A subsequent "??" also got silence. First question of the session ("people count in DB") answered correctly. Token budget at 5% (26K/500K) — not exhaustion.
**Method:** Three parallel deep-read audits: (1) chat SSE pipeline root-cause, (2) backend AI layer (`backend/ai/*`, AI services), (3) frontend chat surface.
**Companion docs:** `architecture-ai-layer-reliability.md`, `epics-ai-layer-reliability.md` (same folder).

---

## 1. Incident root cause

The incident is a **compound failure**: multiple backend paths end a turn with an *empty* final response, and the frontend is architecturally incapable of showing anything when that happens. Ranked mechanisms for this repro:

### RC-1 — Empty final LLM text is silently swallowed (most likely)
- `backend/ai/llm_client.py:81-83`: `max_completion_tokens=1200` with a reasoning-family Azure deployment; `finish_reason` is **never checked**; `content=None → ""` is returned as a *successful* `("", tokens)` tuple. On a longer follow-up turn (26K context with prior tool data in history), the model can exhaust the completion budget on reasoning and return empty content.
- `backend/routes/chat.py:2325-2329` (Phase 14): if final text is empty and no rich blocks → `yield done(message_id=f'empty-{conv_id}')` and return. **No text, no error event.**
- `frontend/src/components/ChatInterface.js:649-654`: assistant messages with no content/blocks/buttons are filtered out of the render list. Net: thinking dots, then nothing.

### RC-2 — Content-policy marker stripper nulls legitimate replies
- `backend/routes/chat.py:2273-2282`: if the final response contains ANY substring from `_CONTENT_POLICY_MARKERS` (including the innocuous "try rephrasing your question"), the **entire response is set to `""`** for every role → flows into RC-1's empty-done path. A model replying to "??" with "…please try rephrasing your question" is erased. Smoking-gun log line to grep in production: `"LLM generated content-policy boilerplate; stripping | conv="`.

### RC-3 — Tool-call dead ends
- `backend/routes/chat.py:2028-2030`: LLM requests a tool name not in `TOOL_REGISTRY` (e.g. invents `list_staff` instead of `get_staff_list`) or fails authorization → **bare `break`**, JSON stripped at Phase 10 → empty → invisible. "Who all are included in staff?" reliably produces a tool-call-JSON first response, so a name mismatch lands exactly here.
- `chat.py:2005`: `MAX_TOOL_ROUNDS` (3) exhausted while last response is still a tool request → same empty path.

### RC-4 — Frontend has NO handler for backend `error` events
- Backend emits `{"type":"error", "phase":…}` in 7 places (`chat.py:1438, 1567, 1667, 1803, 1978, 2084, 2321`), each followed by a bare `done`. The event switch in `ChatInterface.js:367-501` handles 13 event types but **not `error`** and has no default branch. Every backend error phase (including LLM-call failure) is therefore total silence. Because `done` follows, the `stream_closed_without_done` safety net (`api.js:145-148`) never fires.

### RC-5 — Self-reinforcing silence (explains "??" also failing)
- Empty turns are **not persisted** (`chat.py:2325-2329`), so the LLM's next-turn history contains user questions with no assistant replies. The model then tends to apologize / ask to rephrase → re-triggers RC-2 → every subsequent turn in the conversation stays silent.

### Environment check (do first in prod)
- `backend/ai/llm_client.py:30` reads `AZURE_OPENAI_API_KEY`, but CLAUDE.md and deploy docs specify `AZURE_OPENAI_KEY`. If the EB environment follows the docs, **every** call returns `ai_unavailable("not_configured")` (only a startup `logger.warning`). Not this exact repro (turn 1 worked), but a standing binary outage risk; `server.py:304` health-checks only the endpoint var, so this misconfig passes health checks.

---

## 2. Complete silent-failure inventory (chat pipeline)

| # | Location | Trigger | User sees |
|---|----------|---------|-----------|
| S1 | `chat.py:2325-2329` + `ChatInterface.js:649-654` | Empty final text, no rich content | Nothing |
| S2 | `llm_client.py:83` | Azure `content=None` (reasoning-token exhaustion, filtered success); `finish_reason` unchecked | Nothing (feeds S1) |
| S3 | `chat.py:2273-2282` | `_CONTENT_POLICY_MARKERS` substring match — all roles | Nothing (response nulled) |
| S4 | `chat.py:2028-2030` | Unknown/unauthorized tool → bare `break` | Nothing |
| S5 | `chat.py:2005` + `2258` | `MAX_TOOL_ROUNDS` exhausted mid-chain | Nothing |
| S6 | `ChatInterface.js:367-501` | Backend `type:"error"` events — no frontend handler, no default branch | Nothing |
| S7 | `chat.py:1949-1955, 2204-2209` | Client disconnect mid-LLM → message never persisted | Lost turn |
| S8 | `chat.py:2233-2235` | Exception in Phase 9 loop body → logged, falls through to stripped-empty | Nothing |
| S9 | History poisoning (S1 not persisted) | Every turn after a silent one degrades | Repeated silence |
| S10 | `ChatInterface.js:493-499` | `empty-{conv_id}` message id is constant → dedupe blocks any future non-empty done reuse | Nothing |
| S11 | `api.js:131-135` | Malformed SSE JSON → `catch {}` | Event lost |
| S12 | `api.js:105-110` | 401 mid-chat with redirect already consumed → clean resolve, no event | Nothing |
| S13 | `ChatInterface.js:336-343` + `InputBar.js:229-231` | createConversation failure → `return`, textarea already cleared | Message lost silently |

## 3. Backend AI-layer findings (severity-ranked)

### Critical
- **C1** `tool_functions_v2.py:2347` — `json.dumps` used but **`import json` missing** from the module → `NameError` crash in `tool_recall_history` whenever enquiries are non-empty. Flagship G.5 briefing tool broken.
- **C2** `llm_client.py:30` — `AZURE_OPENAI_API_KEY` vs documented `AZURE_OPENAI_KEY` (see above). Health check (`server.py:304`) doesn't cover the key.
- **C3** `tool_functions_v2.py:2337-2350` — `recall_history` checks `.get("success")` on v1 tool results that have **no `success` key** (`tool_functions.py:691, 746-762`) → fee history and enquiries sections silently always dropped from briefings.
- **C4** `prompts.py:920` keys accountant tools as `("admin", "accounts")` but canonical sub_category is `accountant` (`middleware/auth.py:197`) → accountants fall through to the **Principal** tool list (`prompts.py:941-958`) — the LLM attempts tools that always 403. Same bug in `context_builder.py:537` (`"accounts"`) → accountants receive **principal-level context** (attendance, leaves, transport) in their system prompt — an information over-exposure.

### High
- **H1** `award_house_points`: prompt schema (`prompts.py:146-150`: `house_name/points/reason`) vs implementation (`v2:962-974`: requires `student_name`); `category` accepted but never persisted (`v2:991`); denials/not-found returned as `success: True` empty results (`v2:979-985`).
- **H2** `get_announcements` advertised to every student (`prompts.py:210-214, 879`) but **absent from `TOOL_REGISTRY`** → guaranteed dead tool call.
- **H3** `prompts.py:888-902` rebinds `TOOL_CONFIRM_RESOLUTION`/`TOOL_QUERY_AUDIT_LOG`/`TOOL_QUERY_MAINTENANCE_REQUESTS` mid-module with drifted schemas; maintenance admins taught `confirm_resolution(ticket_id, resolution_note)` while the impl requires `request_id/confirmation_note` (`v2:1450`) and registry restricts to owner (`v2:3435`).
- **H4** Branch-scoping inconsistency: ~10 read tools rely on `_apply_branch_filter(query, scope)` only and never consult the JWT branch (`v2:282, 350, 393, 518, 557, 856, 1028, 1079, 2372, 2413`) — none with `# branch-scope: intentional` comments. `tool_get_student_profile` (`v2:625-634`) lets a branch-A principal read any branch-B student's full profile. `award_house_points` (`v2:977`) and `mark_attendance` (`v2:1867`) do branch-unscoped `find_one` name lookups — cross-branch write misfires possible.
- **H5** v1 tools use unguarded `["key"]` access throughout (`tool_functions.py:68, 110-116, 334, 684, 752`) — one malformed doc kills a whole tool. `:752` also exposes the FIRST 5 phone digits, contradicting the last-3-digits rule (`prompts.py:1309`, `redaction.py:86`).

### Medium
- **M1** Three incompatible tool-result envelopes (v2 `_ok/_empty_result`, v2 bare write dicts, v1 raw dicts with `{"error":…}`) — root of C3.
- **M2** Permission denials returned as `success: True` empty results (`v2:313, 642-650, 803-805`) — LLM answers "there are no students" when it means "denied".
- **M3** `tool_get_branch_comparison` queries `db.attendance` instead of `db.student_attendance` (`v2:2478-2483`) — branch attendance always empty.
- **M4** N+1 query storms (`v2:324, 485, 576-584, 441, 916, 1106-1147`; `tool_functions.py:122-133` — chronic-absence loop also capped at 50 students so results are *wrong*, not just slow).
- **M5** Three different fee-outstanding formulas across tools (`tool_functions.py:206-208` vs `v2:556-569` vs `tool_functions.py:551-553` vs `context_builder.py:54`).
- **M6** AI-created announcements never appear in `get_upcoming_events` (status/`event_date` mismatch, `v2:2138` vs `2249-2267`).
- **M7** Exam pass-rate fallback `max_marks=100` (`v2:2088`); attendance rate can exceed 100% (`v2:838`).
- **M8** Kill-switch cache is per-process; other EB workers accept writes up to TTL after disable (`ai_kill_switch.py:61-79`).
- **M9** `layaastat.py:55, 79` — `asyncio.ensure_future` without holding refs (tasks can be GC'd); failures logged at `debug`.
- **M10** Student content filter runs over serialized tool JSON — one blocked word in legitimate data nukes the whole dataset; `\bbomb…\b` (`content_filter.py:108`) blocks curriculum content; `\bDAN\b` (`:375`) blocks a student named Dan. Violates the DPDP "never over-block" calibration.

### Low
- L1 `v2:994` write failure masked as empty read; L2 mixed naive/UTC audit timestamps (`v2:1203`); L3 `get_leave_requests` omits `id` yet `approve_leave` needs it; L4 prompt param drift (`get_student_profile.sections`, `search_students.search_term` vs impl `query` — name searches silently return unfiltered list; `get_fee_transactions` ghost filters); L5 `recall_history` allowed for principals but never advertised to them; L6 teacher scope `class_teacher_id` id-vs-user_id ambiguity (`scope_resolver.py:756` vs `v2:527-529`); L7 `llm_client` tuple|dict dual return type — param-extraction path degrades silently (`chat.py:1750-1757`); L8 `redaction.py:38` masks `blood_group` that `v2:715` deliberately includes; defaulter phones raw at source (`v2:602-605`).

### Pipeline misc (chat.py)
- `chat.py:2402, 2934` — analytics `distinct_id=user.get("user_id")` but key is `id` → always None.
- `chat.py:216-286` — duplicate literal keys in `WRITE_TOOL_PARAM_LABELS` (`"content"`, `"student_name"`).
- Token usage not debited on early-return turns (confirm cards, empty responses) — sidebar undercounts.
- `chat.py:1839-1846` — keepalive sender defined but never started on keyword-tool path.
- `detect_navigate` (`chat.py:806-812`) substring-matches anywhere → questions hijacked into panel navigation.

## 4. Frontend chat-surface findings (beyond RC-4)

- **FH1** 401 mid-stream: no token-refresh retry in `sendMessageStream`; suppressed redirect → silent no-op (`api.js:105-110`).
- **FH2** createConversation failure: message lost, textarea already cleared, network throw is an unhandled rejection (`ChatInterface.js:336-343`).
- **FH3** No reconnect/resume for chat stream; `retryCount` branch is dead code (`api.js:92-153`, `ChatInterface.js:456`); `sse_reconnecting` events unconsumed.
- **FH4** Conversation switch doesn't reset `confirmAction`/`followup`/`aiUnavailable`/`thinkingSteps` (`ChatInterface.js:235-248`) — stale confirm card posts into the wrong conversation.
- **FH5** Recharge dead-end: failed checkout swallowed while input is disabled by `tokenExhausted` (`ChatInterface.js:300-318, 756`) — chat permanently locked.
- **FM1** `token_exhausted` before any delta → question disappears (`ChatInterface.js:432-436`).
- **FM2** `done` dedupe can drop streamed content (`ChatInterface.js:494`).
- **FM3** `loadMessages` failure indistinguishable from empty conversation (`ChatInterface.js:320-329`).
- **FM4** Side effects inside React state updaters — StrictMode double-invocation hazards (`ChatInterface.js:454-475, 493-499`).
- **FL** DOMPurify `FORBID_ATTR: ['style']` strips all of MessageRenderer's own inline styling (`MessageRenderer.js:7-9, 333-338`); markdown links rendered without `href` (`:88`); `handleRetry` duplicates the user bubble (`ChatInterface.js:557-565`); `executeAction` uses raw fetch, no 401 refresh (`:20-26`); SSE buffer tail loss (`api.js:127-128`).

## 5. Systemic conclusions

1. **No turn-completion contract.** Nothing guarantees that every user turn ends in a visible assistant message or a visible error. Fix the contract at both ends (backend: never end empty; frontend: render every terminal event, default branch for unknown types).
2. **Three tool-envelope dialects** caused real silent data loss (C3) and make every consumer special-case. One envelope, enforced by test.
3. **Prompt ↔ registry drift is untested.** Four Critical/High findings (C4, H1, H2, H3) are pure drift a parity test would catch: every advertised tool must exist in `TOOL_REGISTRY`, be authorized for the advertising role, and have matching required params.
4. **Denied ≠ empty.** Authorization failures must be distinguishable by the LLM or it fabricates "no data" answers.
5. **Guardrails over-block** (marker stripper, student filter over tool JSON) — violating the standing DPDP calibration directive.

---

## 6. Completeness sweep — remaining AI paths (fourth audit pass)

Covered: planner/plan_executor/plan_schema, scope_resolver in full, chat_upload, image_gen, memory/skills (Epic G), confirm_tokens, all other `llm_client` callers, parity-gate coverage.

### Critical / High
- **X1** `backend/routes/academics.py:695-717` — `generate_question_paper` never unpacks `await llm_client.chat(...)`: the `(text, tokens)` **tuple is persisted and returned as the paper content**; on AI failure the `ai_unavailable` dict is stored and returned with `success: True`. Every generated paper is corrupted.
- **X2** `backend/ai/plan_executor.py:294-295` — every non-raising step is recorded `"status": "ok"`, but tools signal failure by *returning* `{"success": False}`. A confirmed multi-step plan commits around failed steps and chat replies "Completed all N steps" (`chat.py:2718-2724`). Single-step confirm (`chat.py:2822-2826`) defaults to "completed successfully" while the audit row records failure. **Confirmed actions fail silently; token is burned so no retry.**
- **X3** Memory pre-turn regex hijack — `backend/services/memory/extractor.py:157-158` + `chat_integration.py:98-110` + `chat.py:1577-1581`: `^(save|note|store|delete|remove|forget)\s+…` consumes Owner/Principal turns like **"delete student Rahul Sharma"** pre-LLM ("Got it — I'll remember that") — the real request never runs. Companion: `store.py:169-171` forget does lowercase-substring match and deletes **all** matching memories with no confirmation (violates the F.10 destructive two-step convention).
- **X4** `plan_executor.py:301-304` — broad `DuplicateKeyError` catch around the whole txn returns `already_applied` for *domain* unique-index collisions → user told "already applied" on data that was never written.
- **X5** `database.py:232-236` + `plan_executor.py:296-324` — `_NoopSession` fallback on any `start_session()` error, in any environment: writes become non-transactional (partial commits), idempotency claims are deleted on failure (retry double-writes), and **dry-run/shadow mode actually persists writes**.
- **X6** `backend/ai/scope_resolver.py` privilege widening: `:64-68, 722, 881` unanchored coordinator range regex ("Class 1" matches "Class 10/11/12"); `:218-226` HOD with zero resolved classes gets `{}` → **all students school-wide** (fails open); `:235-236` `class_list` scope returns `{}` for fee/exam collections; `:693, 881` un-escaped `$regex` interpolation ("C++" subject → 500 on every request).
- **X7** `tool_functions_v2.py:4320-4323` + `chat.py:98, 2427-2446` — `WRITE_TOOL_NAMES` derives from flags; a mutating tool registered without `requires_confirmation`/`dispatch_type:"write"` **bypasses confirm, kill-switch, audit, and the parity gate**. No test guards classification.
- **X8** `backend/routes/chat_upload.py:220-227, 151-157` — full body buffered before the 20 MB check; zip members fully decompressed before size check (zip bomb); `image_data` re-enters `POST /chat` (`chat.py:2390`) with no server-side size/format validation.
- **X9** `backend/routes/image_gen.py:377-415, 29, 99` — any admin sub_category can mint TCs/ID cards with client-supplied, DB-unvalidated content (forgery surface); sends school data to **Google Gemini**, contradicting the Azure-residency/DPDP ADR; no rate/cost limit.

### Medium
- **XM1** Saga/compensation is dead code — no plan populates `side_effect`/`compensate` (`plan_schema.py:74, 94-110`); notifications fire inside the txn and survive rollback. D.5's guarantee isn't wired.
- **XM2** Read steps in confirmed plans never execute (`plan_executor.py:276-285`; `planner.py:160-188`) — confirm card shows steps that silently don't run.
- **XM3** Recalled memories injected verbatim into the system prompt (`chat_integration.py:47-59` → `chat.py:1659-1661`) — persistent self-prompt-injection channel; no fencing.
- **XM4** `memory_followup_question` appended after content filter/redaction (`chat.py:2290-2291`); `pending_memory` stored unredacted; bare "yes" confirms an invisible pending memory.
- **XM5** DPDP erasure functions (`erase_owner_memories`/`erase_owner_skills`) defined but never called; `purge_student_references` caps at 5000 (`store.py:251, 271-291`).
- **XM6** Confirm-token "tamper-evident" hash is unkeyed sha256 stored beside the plan (`confirm_tokens.py:28-50`) — needs HMAC; token burned on post-consume validation failures with no re-plan guidance; expiry UX via string-matching `"expired"` (`chat.py:2590`).
- **XM7** `routes/assistant.py:232-237` returns the `ai_unavailable` dict as the reply with `success: True`.
- **XM8** Parity gate never reads `ai/prompts.py` — no automated prompt↔registry check in either direction.
- **XM9** Post-commit metric/audit exceptions turn a *committed* plan into a user-facing 500 (`chat.py:2731-2753, 2803-2814`).
- **XM10** ChromaDB vector index is in-memory — empty after every redeploy; recall silently degrades to keyword-only (`services/memory/vector.py:64`). Memory recall does two full `.to_list(2000)` scans per Owner/Principal turn; +2 LLM calls per turn pre-stream.

### Verified sound
Confirm-token replay protection (atomic CAS + expiry + user/session/school/branch binding); memory subsystem tenancy and Owner/Principal RBAC; chat_upload auth; chat.py's own two `llm_client` call sites handle the dual return correctly; MAX_PLAN_STEPS bound hash-protected.

### Residual blind spots (not yet audited in depth)
`services/ai_rate_limiter.py`, `ai_metrics.py`, `ai_shadow_mode.py`, `actor_context.py`, `txn_context.py`, `idempotency.py` internals; the domain service-layer write paths AI tools dispatch into (parity covers one happy path each); `services/sse.py` internals; per-role prompt content accuracy (no automated backstop until the parity story ships).
