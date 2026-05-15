# Part 2 — AI Layer: Scope

**Status:** 🟢 in-progress (scoping + audit)
**Opened:** 2026-05-15
**Depends on:** Part 1 (Auth + RBAC) ✅ — scope_resolver, require_role helpers, JWT staleness model are inputs to this part

## Goal

Bring the EduFlow AI dispatch pipeline to enterprise quality. The AI layer is the platform's primary UX — a chat surface that reads/writes school data through a registry of tools, gated by role-aware scope, content filters, confirm-action tokens, idempotency, and per-role rate limits. This part audits that pipeline end-to-end and closes every quality gap before the role-vertical parts start consuming it.

## In scope

**Code surface (~7.5K LOC):**
- `backend/routes/chat.py` (1767 LOC) — SSE streaming endpoint, tool-call orchestration, MAX_TOOL_ROUNDS loop, `_execute_confirmed_dispatch`, confirm-action flow
- `backend/ai/llm_client.py` (104 LOC) — Azure OpenAI client wrapper, deployment `gpt-5.3-chat`
- `backend/ai/prompts.py` (846 LOC) — system prompts per role
- `backend/ai/tool_functions.py` (665 LOC) + `tool_functions_v2.py` (1950 LOC) — TOOL_REGISTRY entries
- `backend/ai/content_filter.py` (684 LOC) — `check_input_safety`, `filter_response`
- `backend/ai/context_builder.py` (466 LOC) — chat history shaping, HISTORY_LIMIT/KEEP_FIRST/KEEP_RECENT
- `backend/ai/scope_resolver.py` — already Part 1 surface; in Part 2 only verify consumers actually call `scope.filter()`
- `backend/services/ai_rate_limiter.py` (262 LOC) — atomic counter, override resolver, audit hooks
- `backend/services/confirm_tokens.py` (if present) + audit (`db.ai_dispatch_audit_log`)

**Deliverables:**
1. **Audit report** — adversarial-general + edge-case-hunter findings against the AI dispatch path. Findings triaged into patches A–Z.
2. **Fix sweep** — close every High/Medium finding. Lows triaged.
3. **Property-style tests** — at minimum:
   - confirm-token replay rejection
   - confirm-token cross-user/cross-session rejection
   - rate-limit pre-check semantics (no counter inflation past limit)
   - tool-role enforcement (registry's `roles` list is the only gate)
   - SSE termination invariants (every stream ends with `done` event)
   - content filter required-for-student path
4. **Behavior tests** that exercise the dispatch loop with mocked LLM responses (today's tests are mostly unit-level)
5. **Documentation update** — `_bmad-output/project-context.md` AI section refreshed where audit reveals undocumented invariants

## Out of scope

- LLM provider replacement / fallback (Azure OpenAI stays)
- New tools (additions belong in role-vertical parts)
- Frontend chat UI (Part 8 Frontend Foundation)
- New role-specific prompt tuning (role-vertical parts)
- Telemetry / cost reporting dashboards (Part 7 Observability)

## Success criteria

- **All audit findings closed.** High and Medium findings become patches; Lows triaged with explicit accept/defer rationale.
- **`scope.filter()` is consumed in production code** (currently it's resolved but never threaded into tool queries — Part 1.5 behavior tests proved the contract works against fake collections, but no caller actually uses the result yet).
- **Confirm-token model is provably safe:** unit tests covering replay, expiry, cross-user, cross-session, and "rate-limit-rejected-must-not-burn-token" cases.
- **SSE invariants enforced by test:** every dispatch path emits exactly one `done` event; mid-stream exceptions still emit `done` before propagating.
- **Tool registry is grep-auditable:** the `roles` list is the only authorization gate; no tool function performs its own inline role check.
- **Content filter is honored** for student-role users on all chat replies. Test coverage proves a student request that violates the filter never reaches a write.
- **Rate-limit counter never inflates** past the configured ceiling. Property test covers concurrent dispatch.
- **Audit log row written for every dispatch** (success, rejection, content-filter-block, rate-limit-block) with required fields.
- **Test count** climbs from 260 → ≥320.
- **Tracker:** Part 2 → ✅ done.

## Pre-existing inputs from Part 1 / Part 1.5

- `scope_resolver` denies-by-default for missing sub_category
- `require_role`/`require_owner`/`require_owner_or_principal` exist and are adopted
- `scoped_query` enforces both schoolId + branch_id axes; rejects cross-branch attempts
- 260 backend tests passing as baseline
- Story 7-48 (AI rate limiting) shipped — semantics documented in `project-context.md` and must not regress

## Procedure

1. **Scope (this doc)** ✅
2. **Audit** — adversarial-general + edge-case-hunter agents in parallel against the AI dispatch surface
3. **Findings triage** — save consolidated report to `_bmad-output/parts/ai-layer/review-findings-and-fix-plan.md`
4. **Patch sweep** — work patches in severity order, run tests after each cluster
5. **Retrospective** — what changed, what's still risky
6. **Tracker → ✅ done** — only after grep-auditability + test-count goals are met

## Files / locations

- This scope: `_bmad-output/parts/ai-layer/scope.md`
- Audit findings: `_bmad-output/parts/ai-layer/audit.md`
- Fix plan: `_bmad-output/parts/ai-layer/review-findings-and-fix-plan.md`
- Master tracker entry: row 2 of `_bmad-output/platform-quality-sweep.md`
