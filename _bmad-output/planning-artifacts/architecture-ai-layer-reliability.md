# Architecture — AI Layer Reliability (Zero Silent Failures)

**Date:** 2026-07-08 · **Status:** Approved for implementation · **Implements:** `audit-ai-layer-reliability-2026-07-08.md` · **Epics:** `epics-ai-layer-reliability.md`
**Supersedes:** `outdated/planning-artifacts/architecture-ai-layer-hardening.md` (that initiative shipped; this one fixes what the audit found in the shipped system).

---

## 1. Goal & non-negotiables

**Goal:** Every user turn in the AI chat ends in exactly one of: (a) a visible assistant answer, (b) a visible actionable error, (c) a visible confirm card. Never nothing. Every confirmed write reports its TRUE outcome. Every tool the prompt advertises exists, is authorized, and matches its schema — enforced by CI.

Non-negotiables carried forward (do not regress):
- Python 3.9 + `from __future__ import annotations`; no TypeScript; Motor async only; string UUIDs; no `_id` exposure.
- Tenancy: `ScopedDatabase` for school; explicit `scoped_query(branch_id=...)` or `# branch-scope: intentional` comment for branch.
- AI writes: confirm-token → kill-switch → lockdown policy → audit. DPDP guardrails stay **surgical** (never over-block).
- Azure OpenAI only for school data (no Gemini for PII — see §7).

## 2. The Turn Completion Contract (new, central concept)

### 2.1 Backend contract (chat.py)
A single choke point at the end of the SSE generator guarantees the contract:

```python
# Phase 14 (rewritten): the ONLY exit path of the generator
FALLBACK_TEXT = "I wasn't able to produce an answer for that. Please try again or rephrase."

if not has_content and not has_rich and not confirm_card_emitted:
    clean_text = FALLBACK_TEXT           # never end empty
# ALWAYS: persist the assistant message (even fallback), debit tokens,
# yield done(message_id=<real persisted uuid>)   # never a constant like f"empty-{conv_id}"
```

Rules:
1. **No bare `break`/`return` that skips Phase 14.** Unknown-tool, unauthorized-tool, and MAX_TOOL_ROUNDS paths set an explanatory `clean_text` (e.g. "I couldn't find a capability for that request") instead of breaking silently.
2. **Every `yield error(...)` is followed by a persisted assistant message** carrying the same human-readable text, so history is never poisoned and reloads show the failure.
3. **`_CONTENT_POLICY_MARKERS` never yields `""`** — replace matched responses with `FALLBACK_TEXT`; narrow the marker list to actual policy boilerplate (drop "try rephrasing your question").
4. **Persist every turn.** No un-persisted assistant turns (fixes self-reinforcing history poisoning).

### 2.2 LLM client contract (llm_client.py)
- Check `finish_reason`; on empty `content` with `finish_reason == "length"`, retry once with `max_completion_tokens` raised (1200 → 4000). Reasoning-family deployments need headroom.
- **Kill the dual return type.** `chat()` returns a dataclass `LLMResult(text, tokens, ok, reason)` (or raises `AIUnavailableError`). Migrate ALL callers (`chat.py` ×2 + param extraction, `routes/academics.py`, `routes/assistant.py`, `services/memory/extractor.py`). The tuple|dict API already caused a data-corruption bug (audit X1).
- Accept both `AZURE_OPENAI_KEY` and `AZURE_OPENAI_API_KEY`; in `ENVIRONMENT != development`, missing key = startup failure (fail loud); add the key to the `server.py` health check.

### 2.3 Frontend contract (ChatInterface.js / api.js)
- Event switch gains an **`error` handler** (renders `event.message` as an interrupted assistant bubble with Retry) and a **default branch** (console.warn + telemetry for unknown types).
- **Remove the empty-assistant-message filter trap:** an empty finalized stream message renders a fallback bubble, never nothing.
- Terminal-state invariant mirrored client-side: after `sendMessageStream` resolves, if no assistant message and no error was rendered this turn, render the generic interrupted bubble. This is the client-side backstop for anything the backend contract misses.

## 3. Tool result envelope (one dialect)

All tools — v2 AND legacy v1 (`tool_functions.py` is live via the combined registry) — return:

```python
{"success": bool, "data": ..., "meta": {...}, "message": str|None, "denied": bool}
```

- `denied: True` for authorization failures (today they masquerade as successful empty results — the LLM answers "there are no students" when it means "not allowed").
- v1 tools wrapped/rewritten to the envelope; all `["key"]` accesses guarded with `.get()`.
- `_extract_result_count` / `_extract_empty_message` / `recall_history` consume only this envelope (fixes the silently-missing fees/enquiries sections).
- CI test: iterate `TOOL_REGISTRY`, invoke each read tool against fake collections, assert envelope shape.

## 4. Prompt ↔ registry parity gate (extend `tests/backend/parity/`)

New CI test module `prompt_registry_parity_test.py` asserting, for every role/sub_category prompt variant:
1. Every advertised tool name exists in `TOOL_REGISTRY`.
2. The advertising role passes `_is_tool_authorized` for it.
3. Advertised required params ⊆ implementation-required params (catches `award_house_points`, `search_students.search_term`, `confirm_resolution` drift).
4. Reverse direction: every registry tool authorized for a role appears in that role's prompt (or is explicitly allow-listed as unadvertised).
5. **Write-tool classification guard:** any registry entry whose dispatch touches a known-mutating service must carry `requires_confirmation` or `dispatch_type:"write"` (closes the confirm/kill-switch bypass, audit X7). Maintain an explicit read-only allowlist.

Prompt tool lists keyed by **canonical** sub_categories (`accountant`, not `accounts`) — single source: import the canonical set from `middleware/auth.py` and assert prompt keys ⊆ canonical keys.

## 5. Confirmed-write integrity (plan_executor / confirm flow)

1. **Step success = `result.get("success") is not False`** — a returned failure envelope marks the step `failed`, aborts the txn, and the user message reports which step failed and that nothing was applied. Single-step confirm path composes its reply from the actual result, matching the audit row.
2. `DuplicateKeyError` → `already_applied` **only** when the idempotency-claim insert raised it; domain duplicates surface as step failures with the index name.
3. `_NoopSession` fallback allowed **only** in `ENVIRONMENT == development`; staging/production raise (fail loud) — restores atomicity, idempotency, and honest dry-run.
4. Confirm-token hash → HMAC (keyed with `JWT_SECRET`); expiry surfaced as a typed field, not string matching; post-consume validation failure returns a "please re-issue" message with the original intent echoed.
5. Post-commit metric/audit exceptions are caught and logged — a committed plan never becomes a user-facing 500.
6. Read-steps-in-plans and saga `compensate` are either wired or removed from schema/card (no advertised-but-dead behavior).

## 6. Scope resolution & tenancy (fail closed)

- Coordinator class-range regexes anchored (`^Class 1\b`-style) — no prefix widening.
- HOD/scope resolution that resolves **zero** classes returns an impossible filter (`{"id": {"$in": []}}`), never `{}`. General rule: *empty scope = no data*, never *all data*.
- All user-supplied/DB-field regex fragments pass through `re.escape`.
- Branch-scoping sweep: the ~10 `_apply_branch_filter`-only read tools move to `scoped_query(..., branch_id=_branch_id(user, scope))` or gain `# branch-scope: intentional — <reason>`; `get_student_profile`, `award_house_points`, `mark_attendance` `find_one` lookups become branch-scoped.

## 7. Guardrails, memory, uploads, image-gen

- **Memory pre-turn:** inline save/forget regexes require an explicit memory cue (`remember`, `note to self`, `save a note`) and must NOT match imperative domain verbs (`delete student…`, `remove fee…`). Forget = two-step confirm listing exact matches (F.10 convention). Recalled memories injected inside a fenced, instruction-inert block ("reference notes, not instructions"). Follow-up questions pass redaction. Erasure functions wired into the DPDP erasure endpoint. Chroma index rebuilt from Mongo on startup.
- **Content filter:** student filter applies topic-blocking to the *user message and final prose*, not raw serialized tool JSON (structured tool output gets a narrow PII-only pass); fix over-broad patterns (`\bDAN\b`, bomb-regex curriculum collisions) per the DPDP calibration directive.
- **chat_upload:** stream-check `Content-Length`/chunked size before buffering; check `ZipInfo.file_size` before extraction; validate `image_data` size/format server-side at `POST /chat`.
- **image_gen:** certificates gated `require_owner_or_principal`; content resolved from DB records (client sends `student_id`, not free text); **Gemini call removed or stripped of school PII** per the Azure-residency ADR; per-school rate/cost cap.

## 8. Observability of the AI layer itself

- `layaastat` fire-and-forget tasks held in a task set; failures at `warning`.
- Token usage debited on **every** turn exit (confirm cards, fallbacks, errors) — single debit point in Phase 14.
- Analytics `distinct_id=user["id"]` (currently always None).
- New counter metric `ai_turn_outcome{outcome=answered|fallback|error|confirm}` — alert if `fallback+error` ratio spikes; this is the permanent regression alarm for this incident class.

## 9. Component change map

| Component | Change class |
|---|---|
| `backend/routes/chat.py` | Phase 14 rewrite (contract choke point), tool-loop dead-end narration, marker fix, usage debit, keepalive start, navigate anchoring |
| `backend/ai/llm_client.py` | finish_reason + retry, `LLMResult`, env-var keys, fail-loud startup |
| `backend/ai/tool_functions_v2.py` | `import json`, envelope, branch sweep, per-tool fixes, batching |
| `backend/ai/tool_functions.py` | envelope wrap, `.get()` guards, phone masking |
| `backend/ai/prompts.py` | canonical sub_category keys, schema corrections, constant dedup, missing tools |
| `backend/ai/scope_resolver.py` | fail-closed, anchored/escaped regex, branch scoping |
| `backend/ai/plan_executor.py` + `confirm_tokens.py` + `database.py` | true step outcomes, txn-session policy, HMAC |
| `backend/services/memory/*` | extractor cues, two-step forget, fencing, redaction, erasure, vector rebuild |
| `backend/routes/{academics,assistant,chat_upload,image_gen}.py` | LLMResult migration, upload limits, cert RBAC/provider |
| `frontend/src/components/ChatInterface.js`, `lib/api.js` | error handler, default branch, terminal backstop, state reset, 401 retry, recharge/create-conv surfacing |
| `frontend/src/components/MessageRenderer.js` | sanitizer/style reconciliation, link hrefs |
| `tests/backend/parity/` | prompt↔registry gate, envelope gate, write-classification guard |

## 10. Testing strategy

Standard conventions apply (async pytestmark, factories, 401/403 pair per endpoint, tenant fixtures). Initiative-specific gates:
- **Turn-contract test:** drive the SSE generator through every failure injection (LLM empty, LLM exception, unknown tool, marker text, tool crash, disconnect) and assert a persisted assistant message + terminal event every time.
- **Parity gates** (§4) run in CI; failing = merge-blocked.
- **Plan-executor failure matrix:** step returns `success:False` / raises / domain-dup / idempotency-dup × txn / noop-session — assert user message == audit outcome.
- **Scope matrix:** coordinator "Class 1" vs "Class 10"; HOD-zero-classes; `class_list` vs fee collections — assert fail-closed.
- Frontend: unit tests for the event switch (every backend event type incl. `error` and an unknown type renders something).
