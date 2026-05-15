# AI Dispatch Pipeline — Edge-Case Audit

Scope: `backend/routes/chat.py`, `backend/ai/{llm_client,content_filter,context_builder,tool_functions_v2}.py`, `backend/services/{confirm_tokens,ai_rate_limiter}.py`.

Each finding is a concrete boundary-condition / state-transition / input-validation bug. Severity uses the rubric requested (High = data loss / hung connection ; Medium = wrong answer / silent fail ; Low = cosmetic).

---

## E1 — `_trim_history` keeps first+last and silently discards the middle 8 messages with no summary

**Category:** numeric
**File:** `backend/routes/chat.py:530-559`
**Trigger:** Conversation with >12 messages where total chars > `CHAR_BUDGET` (24000). E.g. 20 messages of ~1500 chars each.
**Observed behavior:** `_trim_history` returns `messages[:2] + messages[-10:]` (12 messages). Middle 8 are dropped entirely. No summary is inserted, and the LLM has zero awareness that intervening context existed.
**Expected behavior:** Either (a) emit a synthetic system/assistant note such as `"[N earlier messages omitted to fit context]"` between the kept prefix and recent tail, or (b) summarise the dropped middle range before discarding. Today the model can confidently contradict prior turns it can no longer see.
**Severity:** Medium
**Suggested fix:** After slicing, splice in `{"role": "system", "content": f"[{len(messages)-12} earlier messages omitted for length]"}` (or `assistant` role if system slot already occupied). The marker is cheap, deterministic, and prevents hallucinated continuity.
**Acceptance check:** Unit test feeds 20 messages each 2000 chars, asserts return length == 13 and includes the elision marker at index 2.

---

## E2 — `HISTORY_LIMIT=20` `to_list(20)` truncates the *oldest* records first, defeating `HISTORY_KEEP_FIRST=2`

**Category:** fencepost
**File:** `backend/routes/chat.py:987-996`
**Trigger:** Conversation with >20 turns. `find().sort("created_at", 1).to_list(HISTORY_LIMIT)` with ascending sort + `to_list(20)` returns the *earliest* 20, not the latest 20.
**Observed behavior:** As the conversation grows beyond 20 messages, only the original first 20 reach `_trim_history`; the recent activity the user is most likely referring to is never loaded. Then `_trim_history` is a no-op because `total_chars` of those early messages usually fits in 24KB.
**Expected behavior:** Either sort descending + reverse, or use a two-step query (first 2 by ASC, last `HISTORY_KEEP_RECENT` by DESC reversed). The intended semantics — "first 2 anchors + most recent N" — require both ends, not the head.
**Severity:** High — the AI silently loses all recent context once conversations cross 20 messages. Users will perceive amnesia.
**Acceptance check:** Insert 30 messages; call the handler; assert the LLM input includes message #30 and not messages #3-#28.

---

## E3 — `_trim_history` `while` loop reads `total` only after pop, can drop below char budget then stop unexpectedly

**Category:** fencepost
**File:** `backend/routes/chat.py:552-557`
**Trigger:** Two giant first messages (`HISTORY_KEEP_FIRST=2`) each >12KB combined with small recent messages. After progressive `trimmed.pop(HISTORY_KEEP_FIRST)`, only the 2 huge first messages plus 2 recent remain (loop terminator `len(trimmed) > HISTORY_KEEP_FIRST + 2`), still >24KB.
**Observed behavior:** Loop terminates with `trimmed` still exceeding `CHAR_BUDGET`. No truncation of message *content*; the oversize prompt is sent straight to Azure OpenAI, risking a 400 `context_length_exceeded` which `llm_client` mis-maps to the "content policy" message (since it includes `"400"`).
**Expected behavior:** After popping the recent set, if total still > budget, truncate the *content* of the first 2 anchors (e.g., last 4000 chars each) rather than ship oversize. Or raise a typed error the route can convert to a user-facing message distinct from the content-filter copy.
**Severity:** Medium — user sees the misleading "content policy" rephrase prompt when the true cause is context length.
**Acceptance check:** Two messages of 20000 chars each → `_trim_history` returns aggregate < CHAR_BUDGET or raises.

---

## E4 — `safe_token_count` returns garbage when `llm_response` is a dict (ai_unavailable result)

**Category:** encoding
**File:** `backend/routes/chat.py:520-525`, called at `1209` and `1396`
**Trigger:** Azure returns timeout → `llm_client.chat()` returns `ai_unavailable_result(...)` (a dict). Code path: `_is_ai_unavailable(llm_response)` triggers the early-return *only after* `safe_token_count(llm_tokens, llm_response)` is computed at L1209 — but actually L1209 runs only when not unavailable, so this is safe. **BUT** at the followup loop L1396, `safe_token_count(llm_tokens, llm_response)` is called *after* the `_is_ai_unavailable` check, only when `llm_response` is a string. The bug is at the fallback `len(fallback_text) // 4` — if `llm_response` is ever the empty string `""` (legitimate "" reply from LLM), it returns `max(1, 0) = 1`, charging the user 1 token for an empty completion.
**Observed behavior:** Empty LLM response charges 1 fallback token even when actual usage came back as 0.
**Expected behavior:** When tokens_from_api is `0` (an integer), trust it. Currently `if tokens is not None and isinstance(tokens, (int, float))` returns `0` correctly — but `_llm_call` initialises `llm_tokens = 0` and only overwrites when `result` is a tuple. When the call raised+the error-path returned a `(text, 0)` tuple (content-filter branch at `llm_client.py:88`), tokens=0 is correct. The fallback path is only reached when `tokens_from_api is None`, which is only when caller passed None — not currently exercised. So this is **Low**: a latent footgun rather than a live bug.
**Severity:** Low
**Acceptance check:** Add unit test asserting `safe_token_count(0, "")` returns 0, not 1.

---

## E5 — Phase-9 multi-tool loop runs again when `tool_result` is truthy AND `tool_rounds=0`, but `_parse_tool_call(llm_response)` is sometimes called against a *dict* (`ai_unavailable` result) rather than a string

**Category:** state
**File:** `backend/routes/chat.py:1221-1238`
**Trigger:** Keyword detection fires a tool (e.g., `get_school_pulse`), tool succeeds, *first* Phase-8 LLM call to narrate the result returns `ai_unavailable_result(...)` (dict). The `_is_ai_unavailable` branch at L1196 returns early — OK. But if it does *not* return early (different error path that nevertheless leaves `llm_response` as something other than `str`), the Phase-9 `while not tool_result or tool_rounds < MAX_TOOL_ROUNDS` is entered with `llm_response` non-string and `_parse_tool_call` is called on a dict.
**Observed behavior:** `_json_candidates(text)` at L354 does `text.strip()` — `dict.strip()` raises AttributeError, which is caught by outer `try` at L1220 but logs an error and breaks out of the loop. Whatever tool_result we had is then narrated (or not), and stream still ends. Soft fail.
**Expected behavior:** `_parse_tool_call` should defensively guard against non-string input: `if not isinstance(text, str): return None`. Same for `_strip_tool_json_from_text` (called at L1407 with potentially-dict `llm_response`).
**Severity:** Medium — Phase 10 strip at L1407 *does* receive the dict if Phase 9 broke out without resetting `llm_response`, and `_strip_tool_json_from_text` will raise (caught) and proceed with the unstripped dict, which then gets passed to `filter_response(llm_response, role)` → `text.startswith` etc. inside the regex calls will raise TypeError → caught → `clean_response = llm_response` (still a dict) → `_extract_rich_content(clean_response)` → `re.search(pattern, dict, re.DOTALL)` raises → uncaught (no try around L1420). Stream truncates without a `done` event.
**Acceptance check:** Mock `llm_client.chat` to return a dict in Phase 8, mock `_is_ai_unavailable` to return False, assert the SSE response still ends with a `done` event.

---

## E6 — Phase-9 loop condition `while not tool_result or tool_rounds < MAX_TOOL_ROUNDS` permits 4 LLM rounds, not 3

**Category:** fencepost
**File:** `backend/routes/chat.py:1221`
**Trigger:** No keyword tool fires (`tool_result is None`), LLM returns a tool call every time, all three tools succeed.
**Observed behavior:** Round 1: `not tool_result` (True) → enter, `tool_rounds=1`, tool executes, `tool_result` set, followup LLM call. Round 2: condition `not tool_result (False) or tool_rounds<3 (1<3 True)` → True → enter, `tool_rounds=2`. Round 3: `2<3` True → enter, `tool_rounds=3`. Round 4: `3<3` False AND `not tool_result` False → exits. **OK, 3 rounds.** *But* if the *initial* keyword tool fires (`tool_result` set BEFORE loop) AND LLM keeps requesting tools: Round 1: `not tool_result` False, `0<3` True → enter, runs tool, `tool_rounds=1`. … this gives 3 *additional* LLM-requested rounds *on top of* the keyword tool = 4 total tool executions in a turn. The constant name `MAX_TOOL_ROUNDS = 3` implies 3 total. Off-by-one against the documented invariant ("Max 3 tool-call rounds per chat turn" in project-context.md L121).
**Expected behavior:** Treat the keyword tool as round 1. Initialise `tool_rounds = 1 if detected_tool else 0` so the cap is honoured.
**Severity:** Medium — exceeds documented budget, can cause quota inflation and longer SSE latency.
**Acceptance check:** Set `MAX_TOOL_ROUNDS=2` for test; trigger keyword tool + mock LLM to return another tool call each round; assert ≤2 tool executions.

---

## E7 — `send_message` accepts whitespace-only `text` after `.strip()` rejection, but Devanagari-only / emoji-only / control-only strings pass through with no semantic content

**Category:** empty-input
**File:** `backend/routes/chat.py:1503-1505`
**Trigger:** POST body `{"text": "   ​​​   "}` (zero-width joiners only). After `.strip()` the ASCII whitespace is removed but zero-width chars survive, so `user_text` is non-empty and the pipeline runs full LLM call.
**Observed behavior:** Burns LLM tokens + rate-limit budget for a message that contains no information. Conversation title is also set to `user_text[:50].strip()` (L899) → conversation auto-titled with invisible characters.
**Expected behavior:** Normalise whitespace via `re.sub(r"[\s​-‏‪-‮﻿]+", " ", text).strip()` and reject if result is empty. Same normalisation should apply before content-filter checks.
**Severity:** Low (DoS-y but bounded by per-user rate limit)
**Acceptance check:** POST `{"text": "​‌‍"}` returns `{success: false, error: "Empty message"}`.

---

## E8 — Confirm-token TTL comparison uses strict `$gt`; tokens with `expires_at == now` (microsecond equality) are rejected as expired

**Category:** numeric
**File:** `backend/services/confirm_tokens.py:117` and `:148`
**Trigger:** Mongo server clock and app server clock skew so that a token issued at T+0 with `expires_at = T+300s` is read at exactly T+300s (or the rare microsecond-equal case). `expires_at: {"$gt": now}` filter excludes; fallback inspect returns 400 "expired".
**Observed behavior:** Edge boundary 400 instead of valid consume. Inconsistent with L148 which uses `<=` (token doc `expires_at <= now` → "expired"). The two branches treat the boundary differently: update path treats `==` as expired (rejection), inspect path also treats `==` as expired — consistent within file, but the message "Confirmation token has expired" can fire for a token that *just* expired this microsecond.
**Expected behavior:** Use `$gte` in the update filter or `$gt` only with a +1 second grace. Treat `expires_at >= now - epsilon` as valid. Tokens are one-shot anyway, so a 5-second grace is harmless and prevents clock-skew flakes between Mongo (UTC) and app server.
**Severity:** Low — boundary case, rare in practice.
**Acceptance check:** Insert token with `expires_at = now`. Call `consume_confirm_token` → assert 400. Same with `expires_at = now + 1ms` → assert 200.

---

## E9 — `peek_confirm_token` silently returns None on DB error, causing `_execute_confirmed_dispatch` to call `consume_confirm_token` which raises 400 ("token required") instead of 503

**Category:** failure
**File:** `backend/services/confirm_tokens.py:78-87` then `backend/routes/chat.py:1589-1606`
**Trigger:** Transient Mongo connection blip during `find_one` in `peek_confirm_token`.
**Observed behavior:** `peek` swallows the exception and returns None. The route interprets None as "missing / wrong owner / used" and falls through to `consume_confirm_token` to surface the precise 4xx. `consume` will hit the same Mongo blip and raise 503 — but if the blip is transient and Mongo recovers between the two calls, `consume` finds no doc and returns 400 "Confirmation token not found". User sees 400 for what is actually a transient DB failure.
**Expected behavior:** Either propagate the DB exception from `peek` (let the route convert to 503) or have `peek` distinguish "not found" (None) from "lookup failed" (raise/special sentinel).
**Severity:** Medium — wrong status code masks infrastructure issues, defeating retry logic on the client.
**Acceptance check:** Mock `find_one` to raise once then succeed; expect 503, not 400, from the confirm endpoint.

---

## E10 — Rate-limit `seconds_until_next_hour` returns minimum 1, but at exactly `HH:00:00.000` (top of hour) returns 3600 — first request of the new hour gets `Retry-After: 3600` if the bucket is already full from a clock-skew race

**Category:** temporal
**File:** `backend/services/ai_rate_limiter.py:45-51`
**Trigger:** Two requests, one at `13:59:59.999` (bucket `13:00`), one at `14:00:00.000` (bucket `14:00`). The rare boundary where two near-simultaneous requests land in different buckets. If the first put us at the limit in bucket `13` and the second triggers a fresh bucket `14`, `seconds_until_next_hour` for `14:00:00.000` returns 3600 — correct for *that* bucket. **The real bug:** at `13:59:59.999`, `seconds_until_next_hour` returns `max(1, 0)` = 1, so the client retries in 1s, lands at `14:00:00.999` in a *fresh* bucket — and rate-limit pre-check now passes. Net effect: a user can effectively get `2 × limit` requests across the second straddling the hour boundary.
**Observed behavior:** Hourly limit is enforced per UTC clock-hour, but bursts straddling the boundary effectively double the budget.
**Expected behavior:** This is documented as acceptable in the comment at `ai_rate_limiter.py:191-193` for the TOCTOU concurrency case, but the *hour-boundary* burst is a different vector. Mitigation: sliding window or token bucket. Without changing the design, at least document it explicitly in the operator dashboard tooltip.
**Severity:** Low (by design, but undocumented for this specific vector).
**Acceptance check:** Simulate `now` = `13:59:59.500` → 5 dispatches consuming budget. Advance `now` to `14:00:00.100` → 5 more should succeed; verify both audit-log buckets show counts within limit individually.

---

## E11 — `resolve_limit` accepts override row with `expires_at = None` as "never expires" but `$or: [{expires_at: None}, {expires_at: {$gt: now}}]` matches docs *without* the field too — overrides written without `expires_at` are perpetual whether intended or not

**Category:** state
**File:** `backend/services/ai_rate_limiter.py:108-113`
**Trigger:** Operator inserts an override doc that omits `expires_at` entirely (e.g., admin UI bug forgot to pass the field).
**Observed behavior:** `$or: [{expires_at: None}, ...]` in Mongo matches both `{expires_at: null}` and `{expires_at: missing}`. The override silently becomes permanent. There's no validation at insert time.
**Expected behavior:** Either enforce `expires_at` as required at write time (operator route should default to a 30-day cap if unspecified) or require explicit `{"expires_at": null}` for "permanent" and reject missing.
**Severity:** Medium — silent permanent escalation of rate limits.
**Acceptance check:** Insert override doc with no `expires_at` field; call `resolve_limit`; assert it returns the *default* (override ignored) — not the override's value.

---

## E12 — `_resolve_params` resolves `student_name` via `is_active: True` only — students marked inactive (graduated, withdrawn) silently fall through, leading the LLM to ask the user the same question again

**Category:** state
**File:** `backend/routes/chat.py:715-723`, `725-736`, `750-758`
**Trigger:** Teacher: "show fee history for Rahul" where Rahul graduated last term (`is_active: False`).
**Observed behavior:** `_resolve_params` finds no match → no `student_id` injected → tool either fails entity-resolution check or returns "no records". User sees a generic "I couldn't find Rahul" with no hint that the student exists but is inactive. Likely to cause friction in fee/follow-up flows that operate on historical/withdrawn students.
**Expected behavior:** Drop the `is_active` filter at resolution time. Let the *tool itself* decide whether to expose inactive records via scope. Or attach `_resolved_student_inactive: True` to the resolved params so the model can mention it in the response.
**Severity:** Medium — wrong-answer for an entire class of legitimate queries (alumni fee reconciliation, withdrawal records).
**Acceptance check:** Seed inactive student `Rahul`; call `_resolve_params({"student_name": "Rahul"}, db)`; assert `student_id` is populated and a flag indicates inactivity.

---

## E13 — `_resolve_params` regex matching on `student_name` and `staff_name` is unanchored — `"Ra"` matches `"Rahul"`, `"Ranjit"`, `"Rashmi"` — first match in DB order wins silently

**Category:** input-validation
**File:** `backend/routes/chat.py:717-720`, `751-755`
**Trigger:** User says "Mark attendance for Sam" and there are two students: "Sam Patel" and "Samantha Roy". `find_one` returns whichever Mongo lists first (no sort).
**Observed behavior:** Wrong student silently selected. Write action (attendance, fee posting) executes against unintended record. The `_resolved_student` field is fed into the confirmation card display, so the user *might* catch it — but only if they read the card carefully and notice "Samantha Roy" instead of "Sam Patel".
**Expected behavior:** When `find_one` would have multiple matches, return an ambiguity error and surface a disambiguation question to the user. Or at minimum sort deterministically (e.g., `created_at` ASC) and require an exact `^name$` match before resolving.
**Severity:** High — write actions on the wrong student. Mitigated by confirmation flow but not eliminated.
**Acceptance check:** Seed two students with names beginning "Sam". `_resolve_params({"student_name": "Sam"})` should return an error/ambiguity marker, not silently pick one.

---

## E14 — `_build_confirm_event` strips underscore-prefixed params from the token payload, *including* `_resolved_student` / `_resolved_class` — the display text on the confirmation card may reference an entity the executor cannot see

**Category:** state
**File:** `backend/routes/chat.py:801-822`
**Trigger:** AI resolves "Rahul" → `student_id="stu_42"` plus `_resolved_student="Rahul Sharma"`. `_build_confirm_display` is called with `resolved_params` (includes the underscore keys, so display shows "Rahul Sharma"). Then `public_params = {k: v for k, v in params.items() if not k.startswith("_")}` strips them before issuing the token. Token stores only `student_id`. On confirm dispatch, `audit_ai_dispatch` records the bare ID — fine for the DB but the audit trail loses the human label the user actually saw.
**Observed behavior:** Audit log says `params: {"student_id": "stu_42"}` while user clicked "Confirm" on a card that said "Rahul Sharma". Forensic reconstruction requires a join. Worse: between display and dispatch, if `stu_42` is reassigned (admin renames or merges student records), the executed action targets the new entity.
**Expected behavior:** Persist the resolved labels in the token doc alongside IDs (perhaps under `display_context` to keep them out of the live params). At dispatch, re-fetch the entity and compare label — abort if changed.
**Severity:** Medium — audit forensics + edge race during admin renames.
**Acceptance check:** Seed token with `_resolved_student="Old Name"`; rename student between issue and consume; assert the consume path either includes original label in audit or rejects on label mismatch.

---

## E15 — `_extract_rich_content` regex is greedy by `re.DOTALL` and grabs the *first* `<<<END>>>` — if rich JSON itself contains the literal `<<<END>>>` inside a string field, parsing truncates

**Category:** encoding
**File:** `backend/routes/chat.py:330-341`
**Trigger:** LLM emits `<<<RICH_CONTENT>>>{"blocks": [{"text": "Use <<<END>>> as terminator"}]}<<<END>>>`. Non-greedy `(.*?)` stops at the first `<<<END>>>` — inside the JSON string — producing malformed JSON, `json.loads` raises, the `except Exception: pass` swallows, full text including markers is returned to the user.
**Observed behavior:** Markers leak into the rendered chat (`<<<RICH_CONTENT>>>... <<<END>>>` shown to user). Looks like a bug to the user.
**Expected behavior:** Use a sentinel less likely to appear in content, or balance-aware JSON extraction (the same `_json_candidates` already used for tool calls).
**Severity:** Low (rare in practice).
**Acceptance check:** Pass response containing nested `<<<END>>>` inside JSON; assert clean output has no markers (either parses or removes both fences).

---

## E16 — `_safe_tool_result_for_chat` redacts on key substring `"phone"` but also matches `"telephone"`, `"phoneme"`, `"iphone_model"` (asset inventory) — over-redaction silently breaks legitimate queries

**Category:** encoding
**File:** `backend/routes/chat.py:649-661`
**Trigger:** `tool_get_inventory_status` returns `{"items": [{"name": "iphone_charger", "stock": 12, "phone_compat": "iPhone 14"}]}`. The `phone_compat` key gets masked to `"XX"` (string) → "XXXX-XXX-XXX" garbled output to the model.
**Observed behavior:** LLM narrates inventory with masked nonsense fields. Subtle wrong-answer for any inventory/asset module that uses "phone" in a non-PII context.
**Expected behavior:** Use exact-match key set (already done for `restricted_exact`) for `"phone"`, `"contact"`, `"phone_number"`, `"contact_number"`, plus suffixes like `_phone`. Don't substring-match.
**Severity:** Medium — corrupts legitimate non-PII data with the same key name.
**Acceptance check:** Call `_safe_tool_result_for_chat({"phone_compat": "iPhone 14"})` → expect `"iPhone 14"` unchanged.

---

## E17 — `_missing_required_params` treats `0` (int) as truthy: `val == ""` and `val == []` false but `val is None or val == ""` lets `0` through

**Category:** input-validation
**File:** `backend/routes/chat.py:665-672`
**Trigger:** `award_house_points` with `params={"student_name": "X", "points": 0}`. `val=0`, `is None` False, `== ""` False, `== []` False → not flagged as missing. Confirm card shows "Award 0 house points" — semantically a no-op write that nonetheless burns the rate-limit slot and audit row.
**Observed behavior:** Zero-value writes proceed (fee payment of 0, points of 0, attendance with empty list `attendance: []` — wait, `[]` *is* caught).
**Expected behavior:** For numeric required params (`points`, `amount`), validate `> 0` or have tool-specific param validators. The current generic check is too lax for numeric fields and too strict for fields where 0 is meaningful.
**Severity:** Low — wastes budget on no-ops; could be Medium if `record_fee_payment` accepts amount=0 (creates phantom receipt).
**Acceptance check:** `_missing_required_params("award_house_points", {"student_name": "X", "points": 0})` should include `"points"`.

---

## E18 — Two concurrent `POST /api/chat/confirm` requests with the same token race past `peek_confirm_token`; both hit `_ai_rate_check` (atomic, OK) then both try `consume_confirm_token` — exactly one succeeds (atomic), the other gets 409, but the loser has *already* incremented the rate counter and written an audit row

**Category:** concurrency
**File:** `backend/routes/chat.py:1589-1638`
**Trigger:** Two browser tabs, both fire `POST /confirm` with the same token within 10ms.
**Observed behavior:** Tab A: peek passes → rate-check increments counter to N → consume succeeds → action executes. Tab B: peek passes (token not yet marked used) → rate-check increments counter to N+1 → consume fails with 409. Net: rate counter inflated by 1 even though only one action ran; audit log has a successful row + a rate-rejection row that is misleading (rate wasn't the cause, replay was).
**Expected behavior:** Either (a) move `consume_confirm_token` before `_ai_rate_check` and decrement counter on token-consume failure (cleaner accounting at the cost of burning the token on rate-rejection — exactly the property current order tries to preserve), or (b) recognise 409 from `consume` and decrement the rate counter to compensate. Option (b) is most accurate.
**Severity:** Medium — counter inflation distorts operator dashboard and can prematurely trigger a real rate-limit reject for the same user in the same hour.
**Acceptance check:** Fire two parallel `POST /confirm` with identical token; assert the post-test counter delta is exactly +1, not +2.

---

## E19 — `_generate_chat_sse` does not handle SSE client disconnect — long-running tool execution (e.g., `get_school_pulse` heavy aggregation) continues to completion after the browser closes the connection, then `yield` raises `ConnectionResetError` and the audit row for an action that the user never saw still gets written

**Category:** concurrency / failure
**File:** `backend/routes/chat.py:843-1476` (whole generator)
**Trigger:** Client closes tab during Phase 9 tool execution.
**Observed behavior:** No `request.is_disconnected()` polling. Tool runs, audit log records success, follow-up LLM call burns tokens — but the response never reaches the user. For write actions this is fine (confirm path is separate POST) but read tools still consume budget invisibly.
**Expected behavior:** Check `request.is_disconnected()` between phases and short-circuit gracefully (skip remaining LLM calls, still persist whatever data was collected). FastAPI supports this via `await request.is_disconnected()`.
**Severity:** Medium — wastes Azure tokens on cancelled requests; could be High at scale.
**Acceptance check:** Open SSE stream, close client mid-stream, assert no follow-up Azure call is made after disconnect.

---

## E20 — Phase-9 tool exception breaks out of the chain but the *failed* tool result `{"error": str(e)}` is then narrated by the final LLM call as if it were valid data — user sees fabricated facts about "the data showed an error"

**Category:** state / failure
**File:** `backend/routes/chat.py:1329-1334`
**Trigger:** `tool_get_fee_summary` raises `Exception("Mongo timeout")`. `tool_result = {"error": "Mongo timeout"}`. Loop breaks. `_extract_empty_message` returns None. Phase 9's last `messages_for_llm_final` is never updated for this round (the `tool_msg` construction at L1346 is inside the loop body *before* the break — it's actually below the exception handler, so it doesn't run for the errored tool). **But** the *previous* round's `messages_for_llm_final` is what reaches Phase 10. Or, in the first-round case after Phase-7 keyword tool error at L1137-1142, `tool_result = {"error": ...}` flows into Phase 8 L1147 where `_extract_empty_message` returns None and the full `tool_result_msg` containing `{"error": "Mongo timeout"}` is sent to the LLM — which then narrates "I encountered Mongo timeout while fetching fee summary".
**Observed behavior:** Internal infrastructure errors leak verbatim into user-facing chat ("Mongo timeout while fetching fee summary"). Mongo connection string fragments or Python tracebacks could leak this way.
**Expected behavior:** On tool exception, replace the result with a sanitised placeholder (`{"error": "data_unavailable"}`) and have the system prompt instruct the LLM to render a graceful fallback. Never pass raw `str(e)` into the LLM context.
**Severity:** High — info disclosure of internal error messages.
**Acceptance check:** Mock tool to raise `Exception("mongodb://user:pass@host/db connection failed")`; assert the SSE stream's text_deltas do not contain "mongodb://" or "user:pass".

---

## E21 — `_ai_rate_check` runs with `school_id=get_school_id()` (env-level, single-tenant) while confirm token was issued for a user whose `user.schoolId` differs — multi-tenant deployments will rate-limit the wrong school's quota

**Category:** tenancy
**File:** `backend/routes/chat.py:1616` (`school_id=get_school_id()`), `backend/services/ai_rate_limiter.py:177`
**Trigger:** Future multi-tenant deployment where `get_school_id()` reflects the *server* default but the JWT's `schoolId` differs. project-context.md L197 specifically calls this out: "school_id MUST come from `tenant.get_school_id()` unconditionally — never trust caller-supplied user.schoolId (spoofable)". So this is intentional today, but for multi-tenant mode the override resolver will use the wrong school's overrides. The comment at L1610-1612 acknowledges single-tenant scope.
**Observed behavior:** Documented one-tenant assumption. Will produce wrong limits the day multi-tenant deploys.
**Expected behavior:** When multi-tenant is enabled, swap to a tenant-aware resolver that derives `school_id` from the JWT *after* a verified mapping (e.g., user's school_id field cross-checked against a server-side users.school_id record — not the JWT claim itself).
**Severity:** Low for now (single-tenant); Medium when multi-tenant ships.
**Acceptance check:** Add a `MULTI_TENANT=true` mode flag; verify `_ai_rate_check` receives the user-record school_id, not the env default.

---

## E22 — `_llm_call` uses `asyncio.create_task` without awaiting/cancelling; if the SSE generator's `wait_for` raises (e.g., asyncio.CancelledError when the request is cancelled), the background task continues to run and writes nothing, but still burns Azure quota

**Category:** concurrency / failure
**File:** `backend/routes/chat.py:1176-1194` and `1364-1381`
**Trigger:** SSE consumer cancels the request mid-keepalive. The outer try at L1144 doesn't cancel the spawned `_llm_call` task.
**Observed behavior:** Orphaned coroutine completes its Azure call. Tokens are paid for, no user receives the result, no audit row written (token recording at L1460 never reached).
**Expected behavior:** Track the task: `task = asyncio.create_task(...)`; in a `finally` block, `task.cancel()` if not done. Or use a context-managed pattern.
**Severity:** Medium — silent token burn on cancellation; compounds with E19.
**Acceptance check:** Start SSE, cancel client after first keepalive; assert the `_call` thread in `llm_client.chat` is interrupted (or at least logged) rather than completing silently.

---

## E23 — `audit_ai_dispatch` infers `success` from `result.get("success", True)` — tools that return a dict without `success` key (e.g., legacy tools or write tools returning `{"status": "ok", "id": ...}`) are recorded as success regardless of actual outcome

**Category:** state
**File:** `backend/services/confirm_tokens.py:175`
**Trigger:** Write tool returns `{"status": "failed", "reason": "duplicate"}` — no `success` field, defaults to True.
**Observed behavior:** Audit log shows `success: True` for a failed write. Operator dashboard miscounts failures.
**Expected behavior:** Require write tools to return an explicit `success` boolean (enforce via interface). Until then, infer failure from common alternatives: `result.get("status") in {"failed", "error"}` or `"error" in result`.
**Severity:** Medium — wrong audit data.
**Acceptance check:** Mock tool returning `{"status": "failed"}`; assert audit row's `success` is False.

---

## Summary

- **High (3):** E2 (history loading reversed), E13 (silent wrong-entity write), E20 (raw exception leak into chat)
- **Medium (12):** E1, E3, E5, E6, E9, E11, E12, E14, E16, E18, E19, E22, E23
- **Low (5):** E4, E7, E8, E10, E15, E17, E21

E2, E13, E20 should block any further AI-layer rollout. E18 and E22 are operationally costly (counter inflation and token waste) and should be queued for the next sprint.
