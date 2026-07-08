# Epics & Stories — AI Layer Reliability (Zero Silent Failures)

**Date:** 2026-07-08 · **Source:** `audit-ai-layer-reliability-2026-07-08.md` · **Architecture:** `architecture-ai-layer-reliability.md`
**Execution:** ONE EPIC PER RUN per `_bmad-output/EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md` (the 7 standing rules, fixed handoff prompt, and per-epic quality gate live THERE — read it first). This doc is written for **any executing agent/model** (Anthropic Sonnet/Opus or others incl. OpenAI): every story carries exact files, line numbers, and acceptance criteria so no model has to guess. Baseline `python -m pytest tests/backend/ -x -q` before and after every epic; the 25 pinned pre-existing failures stay deferred to the end.
**Build order:** R1 → R2 → R3 → R4 → R5 → R6 → R7 → R8 → R9 → (gated) R10 → R11 — except R11.1 (eval corpus), which should land immediately after R3 so all later epics are quality-guarded. R1+R2 are the incident fix and ship first. R3 (parity gate) is the permanent regression backstop and must ship before any new tools are added. R10 (self-learning Phase 2) is gated on R1–R9 shipping and R6's safety fixes being verified.
**Total: 11 epics / 51 stories (R10/R11 are gated follow-ons).** Every story lists exact files and acceptance criteria (AC). Audit finding IDs (RC/S/C/H/M/X/F*) refer to the audit doc.

---

## EPIC R1 — Turn Completion Contract (the incident fix)
*Goal: no user turn can ever end with nothing on screen. Fixes RC-1…RC-5, S1–S13.*

**R1.1 — Frontend: handle `error` events + unknown-event default (RC-4/S6)**
Files: `frontend/src/components/ChatInterface.js:367-501`, `frontend/src/lib/api.js:131-135`
- AC1: `event.type === 'error'` renders an interrupted assistant bubble with `event.message` + Retry button (reuse the `stream_error` rendering).
- AC2: A default `else` branch logs `console.warn('unhandled SSE event', event.type)`.
- AC3: Malformed SSE JSON in `api.js` logs a warn instead of `catch {}`.
- AC4: Unit test: simulate each backend event type incl. `error` and a bogus type; assert something renders / warns.

**R1.2 — Frontend: never render nothing on `done` (S1/S10 client side)**
Files: `frontend/src/components/ChatInterface.js:493-500, 649-654`
- AC1: When a stream finalizes with empty content/blocks/buttons, render fallback text "The assistant couldn't produce a reply. Try again." instead of filtering the message out.
- AC2: Post-await backstop: if a turn produced neither an assistant message nor an error bubble, render the fallback (covers S12-type silent resolves).
- AC3: `processedMessageIds` dedupe cannot drop streamed content (S10/FM2): only dedupe when an identical message body was already rendered.

**R1.3 — Backend: Phase 14 contract choke point (S1/S9)**
Files: `backend/routes/chat.py:2258-2349`
- AC1: Empty final turn → `clean_text = FALLBACK_TEXT`, streamed as `text_delta`, **persisted** as an assistant message with a real uuid `message_id` (never `f"empty-{conv_id}"`).
- AC2: Every assistant turn is persisted, including error/fallback turns — reload shows them; LLM history is never user-question-with-no-reply.
- AC3: Every `yield error(...)` path also persists an assistant message with the same text.
- AC4: Token usage debited at the single Phase-14 exit for every path (fixes undercounting on early returns).
- AC5: Turn-contract test (see architecture §10) passes for injections: LLM empty, LLM exception, tool crash, marker text.

**R1.4 — Backend: fix `_CONTENT_POLICY_MARKERS` blanket null (RC-2/S3)**
Files: `backend/routes/chat.py:2273-2282`
- AC1: Marker match replaces the response with `FALLBACK_TEXT`, never `""`.
- AC2: Remove innocuous markers ("try rephrasing your question", "wasn't able to process that"); keep only true policy boilerplate.
- AC3: Test: a response containing "please try rephrasing your question" reaches the user (as fallback or verbatim per new rules), never silence.

**R1.5 — Backend: narrate tool-loop dead ends (RC-3/S4/S5/S8)**
Files: `backend/routes/chat.py:2005, 2028-2030, 2233-2235`
- AC1: Unknown tool name → assistant text "I don't have a capability called X" + list of close matches; no bare `break`.
- AC2: Unauthorized tool → "That action isn't available for your role." (distinct from unknown).
- AC3: `MAX_TOOL_ROUNDS` exhausted with a pending tool call → "This request needs more steps than I can chain — try narrowing it."
- AC4: Phase-9 loop-body exceptions produce an `error` event AND a persisted fallback message.

**R1.6 — LLM client: finish_reason + retry + completion headroom (RC-1/S2)**
Files: `backend/ai/llm_client.py:69-92`
- AC1: If `content` is empty and `finish_reason == "length"`, retry once with `max_completion_tokens=4000`; log at warning with finish_reason.
- AC2: Default `max_completion_tokens` raised to 4000 (reasoning-family deployment burns budget on reasoning).
- AC3: Empty content after retry returns a typed failure (see R2.1), never a success-tuple with `""`.

**R1.7 — LLM client: kill the tuple|dict dual return (L7/X1 enabler)**
Files: `backend/ai/llm_client.py`, callers: `backend/routes/chat.py` (all call sites incl. `1750-1757`), `backend/routes/academics.py:695-717`, `backend/routes/assistant.py:232-237`, `backend/services/memory/extractor.py`
- AC1: `chat()` returns `LLMResult(text: str, tokens: int, ok: bool, reason: str|None)` (dataclass). No caller does isinstance/tuple unpacking gymnastics.
- AC2: `academics.py generate_question_paper` stores/returns `result.text` only; `ok=False` → HTTPException 503 (fixes X1 — currently persists the tuple/dict as paper content).
- AC3: `assistant.py` returns a proper error payload on `ok=False`, not `success: True` with the failure dict.
- AC4: Grep gate: no remaining call site treats `llm_client.chat` result as tuple or dict.

---

## EPIC R2 — Confirmed-Write Integrity
*Goal: a confirmed action's reported outcome is always the true outcome. Fixes X2, X4, X5, XM1, XM2, XM6, XM9.*

**R2.1 — Plan executor honors tool failure envelopes (X2)**
Files: `backend/ai/plan_executor.py:276-324`, `backend/routes/chat.py:2711-2724, 2822-2826`
- AC1: A step whose runner returns `{"success": False}` is recorded `failed`, aborts the txn, and the user reply names the failed step + "no changes were applied".
- AC2: Single-step confirm reply is composed from the actual result message; user reply and audit row always agree.
- AC3: Failure matrix test (architecture §10) passes.

**R2.2 — Correct `already_applied` semantics (X4)**
Files: `backend/ai/plan_executor.py:296-324`
- AC1: `already_applied` returned ONLY when the idempotency-claim insert raised `DuplicateKeyError`; domain unique-index collisions surface as step failures naming the collection/index.

**R2.3 — No silent no-op transactions (X5)**
Files: `backend/database.py:232-236`
- AC1: `_NoopSession` fallback permitted only when `ENVIRONMENT == "development"`; otherwise `start_session()` failure raises and the confirm endpoint returns a visible 503 "couldn't guarantee transactional safety; nothing was applied".
- AC2: Dry-run/shadow mode with a real session verifies rollback; test asserts no writes persist.

**R2.4 — Confirm-token hardening + expiry UX (XM6)**
Files: `backend/services/confirm_tokens.py:28-50, 185-218`, `backend/routes/chat.py:2590-2639`
- AC1: Plan hash uses HMAC-SHA256 keyed with `JWT_SECRET`.
- AC2: Expiry/validation failures return typed reason codes; frontend shows "This confirmation expired — ask me again" (no string-matching `"expired"`).
- AC3: Post-consume validation failure response echoes the original intent so the user can re-issue in one tap.

**R2.5 — Post-commit safety + dead saga cleanup (XM1/XM2/XM9)**
Files: `backend/ai/plan_executor.py`, `backend/routes/chat.py:2731-2814`, `backend/ai/plan_schema.py:74-110`, `backend/ai/planner.py:160-188`
- AC1: Exceptions after commit (metrics/audit) are caught + logged; the user still gets the success reply.
- AC2: Read steps: either executed before writes as documented, or removed from plan schema and confirm card. Pick and implement one (recommended: remove).
- AC3: `side_effect`/`compensate` fields: wire notifications to fire post-commit only, or remove the dead schema. Document the choice in the epic retro.

**R2.6 — Write-tool classification guard (X7)**
Files: `tests/backend/parity/` (new test), `backend/ai/tool_functions_v2.py:4320-4323`
- AC1: CI test walks `TOOL_REGISTRY`; every tool whose dispatch target is a known-mutating service (maintain explicit allowlist of read-only dispatches) must have `requires_confirmation` or `dispatch_type == "write"`.
- AC2: Test fails if a new mutating tool is registered without flags (would bypass confirm/kill-switch/audit).

---

## EPIC R3 — Prompt ↔ Registry Parity (permanent backstop)
*Goal: the LLM is never advertised a tool that doesn't exist, isn't authorized, or has a different schema. Fixes C4, H1, H2, H3, L4, L5, XM8.*

**R3.1 — Canonical sub_category keys (C4)**
Files: `backend/ai/prompts.py:920-958`, `backend/ai/context_builder.py:537-544`
- AC1: `("admin", "accounts")` → `("admin", "accountant")` in prompts; `"accounts"` → `"accountant"` in context_builder.
- AC2: Accountant receives the accountant tool list and accountant-scoped context (NOT principal context). Test with a `sub_category="accountant"` user asserting the resolved prompt contains no `approve_leave`/`mark_attendance` and the context contains no school-wide leave/attendance blocks.

**R3.2 — Fix advertised schemas + duplicated constants (H1, H3, L4)**
Files: `backend/ai/prompts.py:84-150, 888-912`, `backend/ai/tool_functions_v2.py:962-1014`, `backend/ai/tool_functions.py:633`
- AC1: `award_house_points` prompt schema matches impl (`student_name`, `points`, `reason`, optional `category`); `category` actually persisted to the service or dropped from schema+confirm message.
- AC2: `TOOL_CONFIRM_RESOLUTION`/`TOOL_QUERY_AUDIT_LOG`/`TOOL_QUERY_MAINTENANCE_REQUESTS` defined once; maintenance variant matches impl params (`request_id`, `confirmation_note`) and its registry roles.
- AC3: `search_students` reads `search_term` (or prompt says `query`) — name searches actually filter; `get_student_profile.sections` and `get_fee_transactions` ghost filters removed or implemented.
- AC4: `WRITE_TOOL_PARAM_LABELS` duplicate keys deduped (`chat.py:216-286`).

**R3.3 — Missing/unadvertised tools (H2, L5)**
Files: `backend/ai/tool_functions_v2.py` (registry), `backend/ai/prompts.py:210-214, 722, 879`
- AC1: `get_announcements` implemented and registered (student-safe, branch-scoped) OR removed from student prompt. Recommended: implement (students genuinely need it).
- AC2: `recall_history` advertised to principals (registry already allows it).

**R3.4 — The parity gate itself (XM8)**
Files: new `tests/backend/parity/prompt_registry_parity_test.py`
- AC1–AC4: assertions 1–4 from architecture §4 implemented for every role/sub_category variant; runs in CI; currently-known drift fixed so the gate is green at merge.
- AC5: Gate imports canonical sub_categories from `middleware/auth.py` — prompt keys must be a subset.

---

## EPIC R4 — One Tool Envelope + Denied ≠ Empty
*Goal: uniform machine-readable tool results. Fixes C1, C3, M1, M2, H5, L1, L3.*

**R4.1 — `import json` + recall_history section fix (C1, C3)**
Files: `backend/ai/tool_functions_v2.py:1-30, 2337-2350`
- AC1: `import json` added; `recall_history` with non-empty enquiries no longer raises `NameError`.
- AC2: recall_history consumes actual v1 shapes (or v1 tools ship the envelope in R4.2 first): briefings include fees + enquiries sections. Regression test with populated fake collections asserts all sections present.

**R4.2 — Envelope for all tools (M1)**
Files: `backend/ai/tool_functions.py` (all 14 tools), `backend/ai/tool_functions_v2.py` write adapters (`:998, 1242, 2559` et al.), `backend/routes/chat.py:898-930`
- AC1: Every registry tool returns `{"success", "data", "meta", "message", "denied"}`; v1 `{"error": ...}` shapes eliminated.
- AC2: `_extract_result_count`/`_extract_empty_message` simplified to the single envelope.
- AC3: CI envelope-shape test over the whole registry.

**R4.3 — Denied ≠ empty (M2, L1)**
Files: `backend/ai/tool_functions_v2.py:313, 642-650, 803-805, 979-994`
- AC1: Authorization/permission failures return `success: False, denied: True` with the reason; prompts instruct the model to relay denials honestly.
- AC2: `HouseNotFoundError` and student-not-found on writes return `success: False`, not empty-success.

**R4.4 — v1 robustness + PII at source (H5)**
Files: `backend/ai/tool_functions.py:68, 110-116, 122-133, 334, 684, 746-762`
- AC1: All `["key"]` accesses on DB docs → `.get()` with sane defaults; one malformed doc cannot 500 a tool.
- AC2: Enquiry phone masking = last-3-digits (currently first 5 — `:752`), matching `redaction.py:86`.
- AC3: `get_fee_defaulters` masks guardian phones at source like `get_transport_status` does (`v2:602-605`).
- AC4: `get_leave_requests` includes the leave `id` (approve_leave needs it — L3).

---

## EPIC R5 — Tenancy & Scope Fail-Closed
*Goal: empty/ambiguous scope never widens access. Fixes H4, X6, L6.*

**R5.1 — Branch-scoping sweep of read tools (H4)**
Files: `backend/ai/tool_functions_v2.py:282, 350, 393, 518, 557, 856, 1028, 1079, 2372, 2413, 2513`
- AC1: Each listed tool uses `scoped_query(..., branch_id=_branch_id(user, scope))` OR carries `# branch-scope: intentional — <reason>`; grep audit per CLAUDE.md passes.
- AC2: Cross-branch fixture test per tool: branch-A admin sees no branch-B rows (unless intentional-commented).

**R5.2 — Branch-scope the `find_one` lookups (H4)**
Files: `backend/ai/tool_functions_v2.py:625-634, 977, 1867`
- AC1: `get_student_profile` id/search lookups branch-scoped for branch-bound users; branch-A principal cannot read branch-B profiles.
- AC2: `award_house_points` and `mark_attendance` name lookups cannot resolve to another branch's student/class.

**R5.3 — scope_resolver fail-closed (X6)**
Files: `backend/ai/scope_resolver.py:64-68, 218-236, 693, 722-725, 756, 881`
- AC1: Coordinator range regexes anchored — "Class 1" never matches "Class 10/11/12" (matrix test).
- AC2: Zero-resolved-classes (HOD, coordinator, class_teacher) → impossible filter `{"id": {"$in": []}}`, never `{}`.
- AC3: `class_list` scope yields impossible filters for fee/exam collections instead of `{}`.
- AC4: All regex interpolations wrapped in `re.escape` ("C++" subject works).
- AC5: HOD/coordinator class lookups branch-scoped; class-teacher resolution accepts both `staff.id` and `user_id` consistently with `tool_get_class_list` (L6).

---

## EPIC R6 — Memory Subsystem Safety (Epic G hardening)
*Goal: memory never hijacks, injects, leaks, or destroys. Fixes X3, XM3, XM4, XM5, XM10.*

**R6.1 — Stop the pre-turn hijack (X3)**
Files: `backend/services/memory/extractor.py:157-163`, `chat_integration.py:98-121`
- AC1: Inline save/forget requires an explicit memory cue (`remember`, `note to self`, `save a note that`, `forget the note`); bare `delete/remove/note/save + <domain object>` falls through to the normal pipeline.
- AC2: Regression tests: "delete student Rahul Sharma", "remove fee record for…", "note attendance for class 5" reach the LLM/tool path.
- AC3: Bare "yes" only confirms a pending memory if the pending memory was created this conversation within N turns and the card is re-shown.

**R6.2 — Two-step destructive forget (X3 companion)**
Files: `backend/services/memory/store.py:169-171`
- AC1: Forget lists exact matching memories and requires confirmation (F.10 convention); never substring-deletes all matches.

**R6.3 — Injection fencing + redaction parity (XM3, XM4)**
Files: `backend/services/memory/chat_integration.py:47-59`, `backend/routes/chat.py:1659-1661, 2290-2291`
- AC1: Recalled memories injected inside a fenced block labeled reference-notes-not-instructions.
- AC2: `memory_followup_question` and stored `pending_memory` pass `redact_for_llm`/content rules.

**R6.4 — DPDP erasure + durability (XM5, XM10)**
Files: `backend/services/memory/store.py:39-41, 251, 271-291`, `vector.py:64`
- AC1: `erase_owner_memories`/`erase_owner_skills` wired into the existing DPDP erasure endpoint; test proves invocation.
- AC2: `purge_student_references` paginates past 5000.
- AC3: Chroma index rebuilt from Mongo on startup (or hybrid recall logs degraded mode visibly); per-user memory cap documented and enforced.

---

## EPIC R7 — Data Correctness & Performance
*Goal: numbers the AI reports are right, and fast. Fixes M3–M7, misc.*

**R7.1 — Wrong-collection & formula unification (M3, M5)**
Files: `backend/ai/tool_functions_v2.py:2478-2483, 556-569`, `backend/ai/tool_functions.py:206-208, 551-553`, `backend/ai/context_builder.py:54`
- AC1: Branch comparison reads `student_attendance`.
- AC2: One shared fee-outstanding helper (paid + partial `paid_amount`, includes unpaid/pending) used by fee_summary, defaulters, smart-alerts, context_builder; all four agree on a shared fixture.
- AC3: Defaulter definition documented and consistent with fee_summary.

**R7.2 — N+1 batching (M4)**
Files: `backend/ai/tool_functions_v2.py:324, 441, 485, 576-584, 916, 1106-1147`, `backend/ai/tool_functions.py:122-133`
- AC1: Loops replaced with `$in` batch + dict per CLAUDE.md rule.
- AC2: Chronic-absence calculation covers all students (the 50-cap made results wrong, not just slow).

**R7.3 — Small correctness batch (M6, M7, misc)**
Files: `backend/ai/tool_functions_v2.py:838, 2088, 2138-2267`, `backend/routes/chat.py:806-812, 910-912, 1839-1846, 2402, 2934`
- AC1: AI-created announcements appear in `get_upcoming_events` (status/`event_date` reconciled).
- AC2: Exam pass-rate uses actual `max_marks` (no silent /100 fallback); attendance rate clamped/derived so >100% impossible.
- AC3: `detect_navigate` anchors to navigation intent (prefix/verb match), not substring-anywhere.
- AC4: `_extract_result_count` counts the envelope's `data` list, not first-dict-field.
- AC5: Keyword-tool keepalive actually started; analytics `distinct_id=user["id"]`.

---

## EPIC R8 — Frontend Chat Resilience
*Goal: every frontend failure mode is visible and recoverable. Fixes FH1–FH5, FM1–FM4, FL.*

**R8.1 — Auth + conversation lifecycle failures visible (FH1, FH2, FM3)**
Files: `frontend/src/lib/api.js:105-110`, `frontend/src/components/ChatInterface.js:320-343`, `InputBar.js:229-231`
- AC1: 401 mid-stream attempts one token refresh + retry; on failure emits a visible error event (never a silent resolve).
- AC2: createConversation failure restores the typed text into the input and shows an error toast; network throw caught.
- AC3: loadMessages failure shows "couldn't load history — retry".

**R8.2 — State hygiene across conversations (FH4, FM4)**
Files: `frontend/src/components/ChatInterface.js:235-248, 454-475, 493-499`
- AC1: Conversation switch resets `confirmAction`, `followup`, `aiUnavailable`, `thinkingSteps`, stream state.
- AC2: Side effects moved out of React state updaters (StrictMode-safe).

**R8.3 — Token exhaustion & recharge dead-end (FH5, FM1)**
Files: `frontend/src/components/ChatInterface.js:300-318, 432-436, 756`
- AC1: `token_exhausted` renders an assistant-style bubble explaining the block.
- AC2: Failed recharge checkout shows an error with retry; the input is never locked with a no-op button.

**R8.4 — Stream retry + renderer fixes (FH3, FL)**
Files: `frontend/src/lib/api.js:92-153`, `frontend/src/components/ChatInterface.js:557-565`, `MessageRenderer.js:7-9, 88, 333-338`
- AC1: One automatic reconnect/retry for transient network `stream_error` (real `retryCount`), then manual Retry.
- AC2: `handleRetry` doesn't duplicate the user bubble and clears the error bubble.
- AC3: Sanitizer and renderer reconciled (allow the renderer's own style attrs via sanitizer config or migrate to classes); markdown links get `href` with safe protocol allowlist.
- AC4: SSE buffer tail flushed on stream end (`api.js:127-128`).

---

## EPIC R9 — Guardrails, Config & Adjacent Surfaces
*Goal: fail-loud config, surgical guardrails, safe adjacent AI surfaces. Fixes C2, M8–M10, X8, X9, L7–L9.*

**R9.1 — Azure config fail-loud (C2)**
Files: `backend/ai/llm_client.py:30-45`, `backend/server.py:304`, CLAUDE.md/env docs
- AC1: Accepts `AZURE_OPENAI_KEY` and `AZURE_OPENAI_API_KEY`; docs and `.env.example` aligned.
- AC2: `ENVIRONMENT != development` + missing key/endpoint → startup ValueError (same pattern as `SCHOOL_ID`).
- AC3: Health check verifies key presence.

**R9.2 — Surgical content filtering (M10, DPDP calibration)**
Files: `backend/ai/content_filter.py:108, 375, 656-741`, `backend/routes/chat.py` Phase 8
- AC1: Topic-blocking applies to user text + final prose, not serialized tool JSON; structured tool output gets a narrow PII-only pass.
- AC2: `\bDAN\b` scoped to jailbreak phrasing; bomb-regex allows curriculum contexts; tests assert "Hiroshima bombing essay" and a student named Dan work.
- AC3: `redaction.py` blood_group vs `get_student_profile` reconciled (drop field or allow it) — no permanent "[restricted in chat]".

**R9.3 — Kill-switch & observability honesty (M8, M9)**
Files: `backend/services/ai_kill_switch.py:61-79`, `backend/services/layaastat.py:40, 55, 79`
- AC1: Kill-switch cache TTL cross-worker behavior documented in runbook §8; TTL lowered or DB-checked on confirm path.
- AC2: layaastat tasks held in a task set; emit failures at `warning`.
- AC3: New `ai_turn_outcome` metric emitted from Phase 14 (architecture §8).

**R9.4 — chat_upload limits (X8)**
Files: `backend/routes/chat_upload.py:151-157, 220-227`, `backend/routes/chat.py:2390`
- AC1: Size enforced before/while reading the body (reject on Content-Length; cap streamed reads).
- AC2: Zip members size-checked via `ZipInfo.file_size` + total-decompressed cap before extraction.
- AC3: `image_data` validated (size, base64/format) at `POST /chat`.

**R9.5 — image_gen lockdown (X9)**
Files: `backend/routes/image_gen.py:29, 99, 115-117, 138, 377-415`
- AC1: Certificate/ID endpoints gated `require_owner_or_principal`; content resolved from DB by `student_id` (no client-supplied names/marks).
- AC2: School PII never sent to Gemini — per the Azure-residency ADR, either remove the Gemini leg or send only non-PII template params. Surface provider failure to the caller (no silent degrade).
- AC3: Per-school daily rate/cost cap; `cls.lower()` type-guarded.

---

## Story-count summary
| Epic | Stories | Theme |
|---|---|---|
| R1 | 7 | Turn completion contract (incident fix) |
| R2 | 6 | Confirmed-write integrity |
| R3 | 4 | Prompt↔registry parity |
| R4 | 4 | Tool envelope + denied≠empty |
| R5 | 3 | Tenancy/scope fail-closed |
| R6 | 4 | Memory safety |
| R7 | 3 | Data correctness & perf |
| R8 | 4 | Frontend resilience |
| R9 | 5 | Guardrails/config/adjacent |
| R10 | 5 | Self-learning Phase 2 (gated) |
| R11 | 6 | Excellence & evaluation (gated; R11.1 early) |
| **Total** | **51** | |

## EPIC R10 — Self-Learning Phase 2 (memory-driven improvement with usage)
*Goal: the AI measurably gets better with usage — durable memory, feedback loop, wider rollout. Builds on R6 (which makes the existing subsystem safe); R10 makes it genuinely self-improving. **Gated: implement only after R1–R9 ship and R6's safety fixes are verified.***

**R10.1 — Durable, scalable recall (prerequisite for "learns over time")**
Files: `backend/services/memory/vector.py`, `store.py`, `database.py → _create_indexes()`
- AC1: Vector index persists across deploys — either ChromaDB persistent storage on a mounted volume or (recommended, one less moving part) MongoDB Atlas Vector Search on the existing cluster; index rebuild job on startup as fallback.
- AC2: Recall no longer does full `.to_list(2000)` scans — indexed queries; memories beyond any cap are still recallable (paginated / scored retrieval).
- AC3: Per-user memory cap with LRU/importance eviction (never a silent hard wall); eviction is logged and auditable.
- AC4: Recall latency budget: pre-turn memory phase ≤ 1 extra LLM call and ≤ 300ms retrieval p95; measured via `layaastat` span.

**R10.2 — Feedback loop: Helpful/Improve buttons feed learning**
Files: `frontend/src/components/ChatInterface.js` (feedback handlers), new `backend/routes/feedback.py` or extend chat routes, `backend/services/memory/`
- AC1: Helpful/Improve clicks persist a feedback record `{schoolId, user_id, conversation_id, message_id, verdict, tool_names_used, created_at}` (branch-scoped where applicable).
- AC2: "Improve" opens an optional one-line reason; the reason + turn context is stored as a **candidate correction memory** (pending, not auto-active).
- AC3: Owner/Principal can review pending corrections via a "What I've learned" surface (see R10.4) and activate/reject — activated corrections are recalled on matching future turns (fenced per R6.3, never as instructions with authority over policy/guardrails).
- AC4: Feedback records are DPDP-erasable and included in the tenant erasure path.
- AC5: Aggregate metric `ai_feedback_ratio` per school emitted; regression alarm if helpful-rate drops after a deploy.

**R10.3 — Skill acquisition from repeated usage**
Files: `backend/services/memory/` (skills store), `backend/routes/chat.py` post-turn hook
- AC1: After a successful multi-step/confirmed flow, the AI may propose saving it as a named skill ("Every month-end you ask for X then Y — save as a one-command routine?") — explicit user confirm required, two-step per F.10 for anything embedding write actions.
- AC2: Saved skills are recallable by name/intent and pre-fill the plan for confirmation — they never bypass confirm-token/kill-switch/lockdown gates.
- AC3: Skills are versioned; invoking a skill whose underlying tool schema drifted (parity gate data) surfaces "this routine needs updating" instead of failing silently.
- AC4: Tenanted + role-gated identically to memories; erasure wired.

**R10.4 — Transparency & control surface ("What I've learned")**
Files: `frontend/src/components/tools/` (new panel), backend list/activate/delete endpoints
- AC1: Owner/Principal panel lists active memories, skills, and pending correction candidates with source turn links; supports edit, deactivate, delete (two-step for bulk delete).
- AC2: Every recalled memory used in a reply is disclosed in the "Data used" footer (extends the existing "Data used · N tools" chip).
- AC3: Standard 401/403 security test pair on every new endpoint; cross-tenant fixture test.

**R10.5 — Widen rollout beyond Owner/Principal (gated)**
Files: `backend/services/ai_action_policy.py`-style single switch in memory `chat_integration.py`
- AC1: A single `MEMORY_ROLES` policy switch (mirroring the `LOCKDOWN_ENABLED` pattern) controls which roles get memory/skills; widening to teachers/accountants is a config change, not an engine change.
- AC2: Non-privileged roles get **read-recall only** at first (no auto-extraction) — capture for them requires a separate explicit decision.
- AC3: Per-role prompt disclosure updated via the R3.4 parity gate so advertised behavior matches actual gating.

---

## EPIC R11 — Excellence & Evaluation (quality, latency, language, debuggability)
*Goal: beyond correct-and-safe → measurably excellent. **Gated: after R1–R3 minimum (R11.1 ideally lands right after R3 so every later epic is quality-guarded).***

**R11.1 — Golden eval corpus + LLM-judge CI (quality regression gate)**
Files: new `tests/backend/evals/` + corpus `_bmad-output/test-artifacts/eval-corpus/`
- AC1: ≥40 golden conversations covering every role/sub_category, incl. the incident conversation, follow-ups referencing prior turns, ambiguous asks, denials, and Hinglish variants (see R11.4).
- AC2: Nightly/pre-release CI runs the corpus against the live pipeline (faked DB, real prompts + parsing) and an LLM judge scores correctness/completeness/tone per rubric; score drop > threshold blocks release.
- AC3: Every future prompt change to `prompts.py` requires a green eval run (documented in EPIC-EXECUTION-PROTOCOL).

**R11.2 — Migrate to native Azure OpenAI function calling**
Files: `backend/ai/llm_client.py`, `backend/routes/chat.py` (tool-loop Phases 7–10), `backend/ai/prompts.py` (tool schemas → JSON Schema `tools` param)
- AC1: Tool calls arrive as structured `tool_calls` from the API — the JSON-in-text emission, regex parsing, and `_strip_tool_json_from_text` layer are deleted.
- AC2: Tool schemas generated from `TOOL_REGISTRY` (single source — makes R3's parity gate structural rather than test-enforced).
- AC3: Invented tool names become impossible (API constrains to provided tools); eval corpus (R11.1) passes at equal-or-better scores.
- AC4: Confirm-card, kill-switch, lockdown, and audit flows unchanged and re-verified.

**R11.3 — True token streaming from Azure**
Files: `backend/ai/llm_client.py`, `backend/routes/chat.py` final-answer phase
- AC1: Final-answer LLM call uses `stream=True`; deltas forwarded through existing `text_delta` SSE events.
- AC2: First-token p95 < 3s on the standard turn; keepalives unnecessary during active streaming.
- AC3: Mid-stream provider errors surface via the R1 turn contract (partial text kept + interrupted marker).

**R11.4 — Hindi/Hinglish competence**
Files: `backend/ai/prompts.py` (language directive), eval corpus
- AC1: System prompt instructs reply-in-user's-language (Hindi/Hinglish/English) while keeping data fields (names, amounts) exact.
- AC2: ≥8 Hinglish golden conversations in the eval corpus (e.g. "class 5 ka attendance batao", "Rahul ki fees kitni bachi hai") pass tool-routing and judge scoring.
- AC3: Content filter and redaction verified non-degraded on Devanagari/romanized input.

**R11.5 — Conversation trace viewer for support**
Files: new `frontend/src/components/tools/` panel (Owner + platform-operator), backend endpoint over existing `layaastat` spans + audit rows
- AC1: Given a conversation id, show per-turn timeline: phases hit, tools called (params redacted per DPDP), LLM spans (model, tokens, duration, finish_reason, error_type), outcome (`ai_turn_outcome`).
- AC2: RBAC: owner sees own school only; standard 401/403 test pair; no PII beyond what the role already accesses.
- AC3: The incident class ("user says AI didn't reply") is diagnosable from the panel alone, without server log access.

**R11.6 — Residual audit sweep (close the blind spots)**
Files: `backend/services/{ai_rate_limiter,ai_metrics,ai_shadow_mode,actor_context,txn_context,idempotency}.py`, `backend/services/sse.py`, domain service write paths dispatched by AI tools
- AC1: Each file audited with the same severity rubric; findings either fixed in-story (if small) or appended to this doc as new stories.
- AC2: Audit doc §6 "residual blind spots" section updated to empty or to a justified accepted-risk list.

---

## Considered and deliberately excluded (revisit only with a product reason)
- **Model fine-tuning** — memory/skills (R10) + evals (R11.1) capture the benefit without training-ops burden.
- **Multi-model routing / fallback provider** — adds failure modes; single well-monitored Azure deployment is right at this scale.
- **RAG over school documents** — a product feature (separate PRD), not an AI-layer reliability/excellence item.

---

## Finding → fix traceability (nothing may be skipped)

**Prime directive: every story FIXES the underlying defect. UI error-surfacing (R1.1/R1.2) is a last-line safety net, never a substitute for the root-cause fix.** A story is not done if the bug still exists behind a nicer error message.

| Audit finding | Fixed by |
|---|---|
| RC-1/S1/S2 empty LLM turn | R1.3, R1.6 |
| RC-2/S3 marker blanket-null | R1.4 |
| RC-3/S4/S5/S8 tool-loop dead ends | R1.5 |
| RC-4/S6 unhandled error events | R1.1 |
| RC-5/S9 history poisoning | R1.3 (persist every turn) |
| S10–S13, FM1–FM4, FH1–FH5, FL | R1.2, R8.1–R8.4, R8.3 |
| C1 `import json` NameError | R4.1 |
| C2 Azure key env mismatch | R9.1 |
| C3 recall_history dropped sections | R4.1 + R4.2 |
| C4 accountant→principal prompt/context leak | R3.1 |
| H1 award_house_points drift | R3.2 |
| H2 missing get_announcements | R3.3 |
| H3 rebound TOOL_* constants | R3.2 |
| H4 branch-scoping gaps | R5.1, R5.2 |
| H5 v1 crashes + phone masking | R4.4 |
| M1/M2/L1/L3 envelopes & denied≠empty | R4.2, R4.3, R4.4 |
| M3–M7 data correctness | R7.1–R7.3 |
| M8/M9 kill-switch/layaastat | R9.3 |
| M10 over-blocking filter | R9.2 |
| X1 corrupted question papers | R1.7 |
| X2/X4/X5/XM1/XM2/XM9 confirmed-write integrity | R2.1–R2.3, R2.5 |
| X3 memory hijack + destructive forget | R6.1, R6.2 |
| X6/L6 scope-resolver widening | R5.3 |
| X7 write-classification bypass | R2.6 |
| X8 upload limits | R9.4 |
| X9 image_gen forgery/provider | R9.5 |
| XM3/XM4/XM5/XM10 memory injection/redaction/erasure/durability | R6.3, R6.4 |
| XM6 confirm-token HMAC/expiry | R2.4 |
| XM7 assistant.py false success | R1.7 |
| XM8 no prompt↔registry gate | R3.4 |
| L4/L5 prompt param drift / unadvertised | R3.2, R3.3 |
| L2/L7–L9 misc | R2.5 (timestamps in executor pass), R1.7, R9.2 |

## Definition of done (initiative)
1. Turn-contract failure-injection suite green; `ai_turn_outcome` metric live.
2. Parity gates (prompt↔registry, envelope, write-classification) in CI and green.
3. Branch-scope grep audit clean over `backend/ai/`.
4. Full backend suite green (modulo the 25 pinned deferred failures — fix those LAST per standing directive).
5. Manual repro of the incident conversation ("people count" → "Who all are included in staff?" → "??") produces three visible replies.
