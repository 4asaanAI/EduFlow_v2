# Part 2 (AI Layer) — Consolidated Findings + Fix Plan

**Created:** 2026-05-15
**Status:** ⏸️ awaiting user review before patches land
**Source reports:** `audit-adversarial.md` (8 H / 10 M / 6 L) + `audit-edgecases.md` (3 H / 12 M / 5 L)
**De-duplicated total:** 11 patches (P1–P11), of which 7 are Critical, 3 Important, 1 Polish-bundle.

The two reviewers converged on a small set of root causes. This plan consolidates overlapping findings, orders them by blast-radius, and proposes acceptance tests per patch.

---

## Top-line takeaways

1. **Tenancy in the AI surface is broken in three places at once** (H1 + H2 + H3 / E13). Half the tools have no scope plumbing, `Scope.branch_id` is never populated so even the tools that *think* they apply it are no-ops, and entity-name resolution happens cross-tenant before the confirm card even renders. Combined, this is the largest single risk in the layer.
2. **Conversation memory is loaded wrong end** (E2). After 20 turns the AI silently loses every recent message — users will rationalize this as the AI "forgetting." Pure off-by-one.
3. **Failure paths leak internals into chat and erase audit trails** (E20 / M10 / H5 / M4 / E23). Mongo error strings reach the LLM and the user; audit rows default `success=True` on missing key and can silently fail to write.
4. **SSE robustness is paper-thin** (H6 / E19 / E22). No client-disconnect detection, no LLM timeout, orphan `asyncio.create_task`. A single client disconnecting cleanly is fine; at scale or with flaky LLM, this leaks workers and Azure spend.
5. **Confirm/rate-limit flow has small operational papercuts** (E18 / M5 / E11 / M2 / M3) that distort the operator dashboard but don't currently allow a real bypass.
6. **Story 7-47 (announcement moderation) is bypassed via AI** (H4) — a separate compliance regression.

---

## Patches (ordered)

### Patch P1 — Wire tenancy through the AI tool surface

**Closes:** H1, H2, H3, E12, E13, M6 (partial), M9, E21
**Severity:** Critical
**Blast radius:** Every AI read/write tool. Cross-branch and (in future) cross-school leakage.

**Three subtasks executed together:**

1. **Populate `Scope.branch_id` in `resolve_scope`.**
   - In `backend/ai/scope_resolver.py`, every `Scope(...)` construction in `resolve_scope` / `_resolve_admin_scope` / `_resolve_teacher_scope` should pass `branch_id=user.get("branch_id")`. Owner stays `None` (intentional cross-branch).
   - Add a `Scope.filter()` branch that always emits a `branch_id` clause when `self.branch_id` is set, regardless of `type` (currently only `type="branch"` does, and that type is never produced).

2. **Migrate v1 tools (`backend/ai/tool_functions.py`) to accept `scope`.**
   - All ~14 v1 tools become `(params, user, scope)` and apply `_apply_branch_filter(query, scope)` + `scoped_query(...)` (which already exists from Part 1.5).
   - Until migration of a given tool is done, gate the v1 dispatch behind a feature flag forcing `{"success": False, "error": "tool_under_migration"}` for non-default tenants. Default-tenant single-school deployments continue working.
   - Acceptance: `grep -rn 'def tool_' backend/ai/tool_functions.py | grep -v ', scope)'` returns zero.

3. **Scope-aware `_resolve_params` in `chat.py`.**
   - `_resolve_params` takes `scope` and applies `scope.filter(collection="students")` (etc.) before the regex name search.
   - Drop the unanchored substring match: require `^name$` exact OR ambiguity-disambiguation. Two-or-more matches return `{"_resolution_error": "Multiple students match 'Sam' — please specify the admission number"}` which the chat surface renders.
   - Drop the `is_active: True` filter at resolution time (E12) — let the tool decide. Pass a `_resolved_inactive: True` flag in the params dict so the model can mention it.
   - Resolution result includes original `_resolved_label` AND a re-fetched canonical name; if the canonical name has drifted between resolution and dispatch, abort with a "student record changed" message (closes E14).

**Acceptance tests (one new `tests/backend/api/test_ai_tenancy.py`):**
- Seed 2 branches under 1 school. Teacher in branch A calls `tool_search_students` (v1) → only branch-A students. Same for one v2 tool that exercises `_apply_branch_filter`.
- `_resolve_params` with two name-collision students returns ambiguity error.
- `_resolve_params` finds inactive student and flags inactivity (no silent miss).
- `resolve_scope` always sets `scope.branch_id` when JWT carries it.
- Unit test: `Scope(type="all", role="owner", user_id="x", branch_id=None).filter()` returns `{}`; `Scope(type="all", role="admin", sub_category="principal", user_id="x", branch_id="b1").filter()` includes `branch_id: "b1"`.

---

### Patch P2 — Fix conversation history loading direction

**Closes:** E2, E1, E3
**Severity:** Critical (UX-shattering after 20 turns)
**Blast radius:** Every conversation longer than 20 messages.

**Subtasks:**

1. **Load the right end** (`backend/routes/chat.py:987-996`). Two-step query: first 2 messages by `created_at ASC, to_list(2)`, last `HISTORY_KEEP_RECENT` by `created_at DESC, to_list(N), reverse()`. Concatenate. Single round-trip if a clever aggregation, but two trivial finds are fine.

2. **Add an elision marker in `_trim_history`** (`chat.py:530-559`): when truncating, splice `{"role": "system", "content": f"[{N} earlier messages omitted for context length]"}` between anchors and recent.

3. **Truncate oversize anchors** (`chat.py:552-557`): after the existing pop loop, if `total_chars` still exceeds `CHAR_BUDGET`, truncate the *content* of the kept anchors (e.g., last 4000 chars each). Otherwise the prompt ships oversize and Azure returns 400 → `llm_client` mis-maps it to "content policy" (E3).

**Acceptance:**
- Test seeding 30 chat messages: handler input to LLM contains message #30 and includes elision marker; does NOT contain messages #3-#28.
- Test with two oversize anchors (20KB each): aggregate `<= CHAR_BUDGET`.

---

### Patch P3 — Don't leak internal errors into LLM context or chat

**Closes:** E20, M10, E5
**Severity:** Critical (info disclosure)
**Blast radius:** Every tool exception path.

**Subtasks:**

1. **Replace `str(e)` in `tool_call`/`tool_result` SSE events and chat history** (`chat.py:1137-1141`, `1329-1334`, `1659-1661`). Map every tool exception to `{"error": "data_unavailable", "correlation_id": <uuid>}`. Log the full exception with `logger.exception` keyed to the correlation_id.

2. **Defensive `isinstance` guards** in `_parse_tool_call`, `_strip_tool_json_from_text`, and `filter_response` callsites (E5). Any non-string input returns the input unchanged / None. Phase 10 → Phase 11 sequence becomes resilient to a dict slipping through.

3. **HTTPException re-raises** at `chat.py:1661` use `detail="An internal error occurred"`, never `str(exc)`. Correlation_id returned to client so support can grep logs.

**Acceptance:**
- Mock a tool to raise `Exception("mongodb://user:pass@host/db ...")`. SSE stream contains `"data_unavailable"`, never `mongodb://`. Server logs DO contain the original (look for the correlation_id).
- Mock `llm_client.chat` to return `{}` (dict) and `_is_ai_unavailable` to return False. SSE stream still terminates with `done`.

---

### Patch P4 — Audit log integrity (write-ahead, real `success`, always-write)

**Closes:** H5, M4, E23
**Severity:** Critical (compliance gap)
**Blast radius:** Every AI write dispatch.

**Subtasks:**

1. **Write-ahead audit row** in `_execute_confirmed_dispatch` (`chat.py:~1620`): insert `{..., "status": "pending", "executed_at": null}` BEFORE the tool runs. After the tool returns, update the row with `success`, `executed_at`, `result_summary`. If the pre-write itself fails, return 503 and DO NOT run the tool.

2. **Fix `success` semantics** in `audit_ai_dispatch` (`backend/services/confirm_tokens.py:175`):
   ```python
   inferred_success = result.get("success") is True or result.get("status") == "ok"
   # treat missing key as failure (was: defaulted to True)
   ```

3. **Always-write on the exception path**: wrap `_execute_confirmed_dispatch` so that 5xx still produces an audit row with `success=False, error=<correlation_id>`.

**Acceptance:**
- Patch Mongo to throw on `audit_ai_dispatch_log.insert_one`. Endpoint returns 503; tool side-effect did NOT happen (verify the DB doc isn't there).
- Tool returns `{}` (no `success` key). Audit row records `success=False`.
- Tool raises. Audit row exists with `success=False, error=<id>`.

---

### Patch P5 — SSE robustness: timeout, disconnect, no orphans

**Closes:** H6, E19, E22, L4 (loop condition), E5 (partial), L6 (cosmetic)
**Severity:** Critical at scale (worker leak)
**Blast radius:** Every chat stream.

**Subtasks:**

1. **LLM call has a hard timeout.** Pass `timeout=45` to `chat.completions.create` in `llm_client.py`. Map timeout exceptions to `ai_unavailable_result("timeout")`.

2. **No orphan tasks.** In `chat.py:1176-1194` and `1364-1381`:
   ```python
   task = asyncio.create_task(_llm_call())
   try:
       while not llm_task_done.is_set():
           try: await asyncio.wait_for(llm_task_done.wait(), timeout=KEEPALIVE_INTERVAL)
           except asyncio.TimeoutError:
               if await request.is_disconnected():
                   task.cancel(); return
               yield keepalive_event()
   finally:
       if not task.done(): task.cancel()
   ```

3. **Wrap `_llm_call` body** in `try/finally` so `llm_task_done.set()` ALWAYS fires, even on uncaught exception (otherwise the loop spins keepalives forever).

4. **Cap total wait** at 90s. After that, emit `ai_unavailable_result("timeout_wallclock")` and bail.

5. **Fix loop condition** at `chat.py:1221`: change `while not tool_result or tool_rounds < MAX_TOOL_ROUNDS:` to `while tool_rounds < MAX_TOOL_ROUNDS:`. Treat the keyword-detected tool as round 1: initialize `tool_rounds = 1 if detected_tool else 0` (closes E6).

6. **Always emit `done`** — wrap the whole generator in a `try/except/finally` that emits `done` exactly once on any exit path (normal, exception, cancellation).

**Acceptance:**
- Simulate LLM call hanging 120s. Stream returns within ≤90s with `ai_unavailable` and a `done` event.
- Simulate client disconnect mid-stream. `asyncio.all_tasks()` returns to baseline within 1s.
- Trigger 3 keyword + LLM tool calls in a row. Total tool executions = 3, not 4.
- Mock tool to raise. Stream still ends with `done`.

---

### Patch P6 — Move tool authorization fully into the registry

**Closes:** M5 (registry/body disagreement), partial overlap with H4
**Severity:** Important
**Blast radius:** Every tool with a body-level sub_category check.

**Subtasks:**

1. **Extend `TOOL_REGISTRY` schema** with `sub_categories: list[str] | None`. Default `None` = any.

2. **Single helper** `_is_tool_authorized(user, tool_def)` that checks both `roles` and `sub_categories`.

3. **Single enforcement point** at three locations: keyword dispatch (chat.py:1126), LLM-requested tool (chat.py:1318), and `_execute_confirmed_dispatch` (chat.py:1654). All three call `_is_tool_authorized`. Return `"Forbidden"` (Part 1.5 precedent) — no role/sub_category names in the body.

4. **Remove body-level role checks** (`_is_accountant`/`_can_owner_or_principal` in tool bodies). Where they remain, convert to `assert` (post-condition: registry should have caught it). The pre-confirm gate prevents:
   - Confirm-token issue for unauthorized tool
   - Rate-limit slot consumed on unauthorized dispatch

**Acceptance:**
- Admin/accountant calls `create_announcement` via chat → rejection BEFORE confirm-token issue; no token in DB, no rate counter increment, response is `"Forbidden"`.
- `tool_record_fee_payment` for a teacher → registry rejection; tool body never reached.

---

### Patch P7 — Story 7-47 moderation gate in `tool_create_announcement`

**Closes:** H4
**Severity:** Critical (compliance regression)
**Blast radius:** Announcement moderation pipeline.

**Subtask:**
- In `backend/ai/tool_functions_v2.py:1464-1501`, when `audience_roles` includes `teacher` or `student`, set `status="pending_approval"` and skip immediate broadcast. Return a message describing the pending id; don't write `sent_at`. Mirror `routes/operations.py` create-announcement helper, or call into it directly (preferred — DRY).

**Acceptance:**
- AI dispatches `create_announcement` with `audience_type="students"`. The inserted doc has `status="pending_approval"`. It appears in `GET /api/ops/announcements/pending`. Its content has NOT been broadcast.

---

### Patch P8 — Content filter covers rich_blocks and tool results

**Closes:** H7
**Severity:** Important
**Blast radius:** Student-role chat surface.

**Subtask:**
- In `chat.py:1419-1435`, run `filter_response(json.dumps(rich_blocks), "student")` for student-role users before emitting. Also apply to `tool_result` content before splicing into LLM messages.

**Acceptance:**
- Student calls a tool that returns `{"reason": "drug abuse"}`. The emitted rich_block JSON has the matched terms replaced by the filter's sentinel.

---

### Patch P9 — Confirm-token & dispatch tenant binding + idempotency

**Closes:** M1, M9, M7, E18 (counter inflation), E21 (multi-tenant readiness)
**Severity:** Important
**Blast radius:** Confirm flow and operator dashboard accuracy.

**Subtasks:**

1. **Persist `school_id` + `branch_id` on confirm token** at issue (`confirm_tokens.py:30-53`). On consume, assert match with `get_school_id()` / `user["branch_id"]`. Reject 409 if drifted.

2. **Compensating decrement on consume failure (E18):** if `consume_confirm_token` returns 0 modified (replay) after the rate-limit pre-check has already incremented, decrement the counter. Net delta exactly +1 for the winning concurrent call.

3. **Write idempotency:** persist the consumed token as `dispatch_id` on the resulting write row (fee_transactions, student_attendance, etc.). Unique-index it. On retry, the second dispatch returns the existing row instead of duplicating. The audit log surfaces both attempts.

4. **`peek_confirm_token` error semantics (E9):** raise on Mongo errors instead of returning None. Route converts to 503. None remains "not found / wrong owner / used".

**Acceptance:**
- Token doc inspection shows `school_id`, `branch_id`.
- Two parallel `POST /confirm` with same token → exactly one success, counter += 1.
- Same write attempted twice → exactly one DB row.
- Mock `find_one` in peek to throw → endpoint returns 503, not 400.

---

### Patch P10 — Rate-limit & override hardening

**Closes:** M2 (TOCTOU), M3 (tiebreak), E11 (missing expires_at), L2 detection scope
**Severity:** Important
**Blast radius:** Operator dashboard accuracy, override correctness.

**Subtasks:**

1. **`expires_at` is required at override write time** (operator route). Reject if missing. Migration backfills any existing rows.

2. **Stable tie-break** in `resolve_limit` cursor sort: `.sort([("created_at", -1), ("_id", -1)])`.

3. **TOCTOU compensation** is folded into P9 step 2 (decrement on consume-failure).

4. **Match update filter for `expires_at: None`** vs `expires_at: missing` — require explicit `null` for "permanent"; reject missing.

**Acceptance:**
- POST override without `expires_at` returns 400.
- Two overrides with identical `created_at` → resolver picks consistently across 100 calls.
- Override doc with `expires_at` field missing → `resolve_limit` IGNORES it (treats as malformed) and returns default.

---

### Patch P11 — Polish bundle (low-severity hygiene)

**Closes:** L1/E4, L3, L5, L6, E7, E8, E10, E15, E16, E17, H8 (partial)
**Severity:** Low (bundle commit; each fix < 30 LOC)
**Blast radius:** Targeted defense-in-depth and UX.

**Subtasks (each one line to a few lines):**

- `safe_token_count`: coerce non-string `fallback_text` to `""` (E4/L1).
- `_safe_tool_result_for_chat`: extend `restricted_exact` to include `password_hash`, `salt`, `secret`, `api_key`, `private_key`, `refresh_token`, `access_token`, `session_token`, `webhook_secret`. Use exact match for `phone` keys (closes L3 + E16).
- `_thinking_delay`: switch to `random.uniform(MIN, MAX)` (L5).
- Keepalive event: switch to SSE-comment `:keepalive\n\n` (L6).
- Normalize whitespace (including zero-width) before empty-message rejection (E7).
- Confirm-token TTL boundary: change `$gt` → `$gte` OR add a 5s grace to `expires_at` (E8).
- Document hour-boundary 2x burst (E10) as an accepted property in operator dashboard tooltip; no code change.
- `_extract_rich_content`: use `_json_candidates` balance-aware extraction instead of `<<<END>>>` regex (E15).
- `_missing_required_params`: tool-specific numeric validators (`points`, `amount` must be `> 0`) (E17).
- Cap `_strip_tool_json_from_text` scan time and candidate count (H8). Bound `llm_client.chat` response to 32KB before returning.

**Acceptance:**
- Existing tests still pass. New regression tests for each subtask (small).

---

## Suggested execution order

Run as **two waves**, each a coherent commit:

**Wave 1 — Critical correctness (P1, P2, P3, P4, P5):**
1. P1 (tenancy plumbing) — the largest, most invasive. Touches resolver, all v1 tools, `_resolve_params`. Land first; everything else depends on this working.
2. P2 (history direction) — small, isolated; ship right after.
3. P3 (error opacity) — small, multi-site; can land in same PR as P2 if separate is too much overhead.
4. P4 (audit integrity) — touches the dispatch hot path; isolated to confirm_tokens + chat.py:_execute_confirmed_dispatch.
5. P5 (SSE robustness) — biggest invasive change to chat.py generator. Land last in wave 1 so tests against new tenancy/audit semantics are stable first.

**Wave 2 — Important hardening (P6, P7, P8, P9, P10, P11):**
6. P6 (registry sub_categories) — touches every tool. Mechanical.
7. P7 (announcement moderation in tool) — small, surgical.
8. P8 (filter rich_blocks) — small.
9. P9 (confirm-token tenancy + idempotency) — touches the dispatch flow again.
10. P10 (rate-limit hardening) — depends on P9 for the TOCTOU compensation.
11. P11 (polish bundle) — last; safety net.

**Test budget:** ~30 new tests expected. Existing 260 should stay green throughout.

---

## Findings explicitly NOT actioned

- **L2 (Devanagari-only language detect):** UX-only, not a quality blocker. Defer to a future i18n story.
- **E14 (resolved labels not persisted in audit):** P1 step 3 partially addresses this via the canonical-name re-fetch + abort-on-drift; full label persistence deferred unless audit-replay tooling needs it.

---

## After all patches

- Update master tracker (row 2 of `_bmad-output/platform-quality-sweep.md`) to ✅ done.
- Update `_bmad-output/project-context.md` AI sections with new invariants:
  - `Scope.branch_id` is now always populated from JWT
  - `_resolve_params` is scope-aware and ambiguity-rejecting
  - Confirm tokens persist `school_id`/`branch_id`
  - Write tools must include `dispatch_id` (from confirm token) for idempotency
  - Audit rows now use `success = result.get("success") is True or status == "ok"`
- Bring Part 1.5-style memory note updating MEMORY.md and `eduflow-part2-...md` into the closeout commit.
