# Epic R4 — One Tool Envelope + Denied ≠ Empty · Completed Log

**Goal:** uniform, machine-readable tool results so the assistant reads outcomes
correctly. Fixes audit C1, C3, M1, M2, H5, L1, L3.

**Branch:** `ai-reliability-r1-turn-completion` (same branch as R1/R2/R3/R11.1).
**Baseline:** 1344 passed (after R11.1) → **after R4: 1396 passed / 0 failed / 0 skipped** (14 deselected = 13 mongo_real + 1 llm_eval).

---

## R4.1 — `import json` + recall_history sections (C1, C3)
**Files:** `backend/ai/tool_functions_v2.py`

- **C1:** added the missing `import json` — `recall_history` no longer raises
  `NameError` when enquiries are non-empty (the flagship briefing tool was broken).
- **C3:** `recall_history` already consumed the envelope (`.get("success")` /
  `.get("data")`), but the v1 `get_fee_transactions` / `get_enquiries` returned
  `{transactions:…}` / `{enquiries:…}` with no `success`/`data`, so those sections
  were silently dropped. With v1 now on the envelope (R4.2), the fees and enquiries
  sections populate. Regression test seeds a student + fee txns + enquiry and
  asserts both sections present.

**ACs:** AC1 ✅ AC2 ✅ · Tests: `test_r4_tool_envelope.py::test_recall_history_includes_fees_and_enquiries`.

## R4.2 — Envelope for all tools (M1)
**Files:** `backend/ai/tool_functions.py` (all 14 v1 tools), `backend/ai/tool_functions_v2.py`, `backend/routes/chat.py`

- **AC1:** every registry tool returns the single envelope
  `{success, data, meta:{count,…}, message, denied}`. The three incompatible
  dialects are gone: v1 `{error:…}` shapes eliminated; v1 tools wrapped via a new
  `_env()` helper (payload under `data` — a list for list-primary tools so
  recall_history / extractors read it uniformly, a dict for composite dashboards);
  v2 helpers `_ok`/`_empty_result` now carry `denied`; the few v2 tools that built
  the envelope by hand (`get_transport_status`, `get_expenses`, `get_fee_sync_status`,
  `query_student_record`, `get_announcements`) were normalized.
- **AC2:** `chat._extract_result_count` / `_extract_empty_message` simplified to
  read the envelope (`meta.count`, `message`, `denied`/`success`), with a minimal
  legacy fallback.
- **AC3:** new CI test `parity/tool_envelope_shape_test.py` iterates the registry,
  invokes every read tool against an empty permissive fake DB, and asserts the
  envelope shape — doubling as an H5 robustness check (a tool that raises on an
  empty DB fails here).
- `daily_brief` updated to read its sub-tools' payloads from `.data`.

**ACs:** AC1 ✅ AC2 ✅ AC3 ✅ · Tests: `tool_envelope_shape_test.py` (47 read tools + partition check).

## R4.3 — Denied ≠ empty (M2, L1)
**Files:** `backend/ai/tool_functions_v2.py`, `backend/ai/prompts.py`

- **AC1 (M2):** authorization/permission failures now return
  `success: False, denied: True` with the reason (new `_denied()` helper) — the
  class-access denials in `get_student_database`, the profile-permission denial in
  `get_student_profile`, the award-points permission gate, and the approval-request
  authorization check. `RESPONSE_FORMAT_RULES` gained a directive telling the model
  to relay denials honestly ("outside their access") and NEVER say "there are none"
  on a denied/failed result.
- **AC2 (L1):** `HouseNotFoundError` and student-not-found on the `award_house_points`
  WRITE now return `success: False` (new `_failed()` helper), not empty-success —
  a failed write can no longer be reported as a benign empty read.

**ACs:** AC1 ✅ AC2 ✅ · Tests: `test_student_database_class_denial_is_denied`, `test_award_points_student_not_found_is_failure`.

## R4.4 — v1 robustness + PII at source (H5, L3)
**Files:** `backend/ai/tool_functions.py`, `backend/ai/tool_functions_v2.py`

- **AC1 (H5):** every `["key"]` access on a DB doc in the v1 tools is now `.get()`
  with sane defaults — one malformed/partial doc can no longer 500 a whole tool
  (enforced broadly by the envelope-shape test running each tool on an empty DB).
- **AC2:** enquiry phone masking switched from exposing the FIRST 5 digits to the
  canonical `_mask_phone` (first-2 + last-3), imported from `redaction.py`.
- **AC3:** `get_fee_defaulters` (and the `get_fee_summary` defaulter list) mask
  guardian phones AT SOURCE via `_mask_phone`; `get_transport_status`'s weaker
  inline mask (exposed 7 digits) was also switched to the canonical mask.
- **AC4 (L3):** `get_leave_requests` now includes the leave `id`/`leave_id` — which
  `approve_leave` needs to act on a request surfaced by the list.

**ACs:** AC1 ✅ AC2 ✅ AC3 ✅ AC4 ✅ · Tests: `test_enquiry_phone_masked_canonically`, `test_get_leave_requests_includes_id`, envelope-shape H5 coverage.

---

## Files touched
- `backend/ai/tool_functions.py` — `_env` helper, all 14 v1 tools enveloped + `.get()`-guarded, canonical phone mask, `{error:…}` eliminated.
- `backend/ai/tool_functions_v2.py` — `import json`, `_denied`/`_failed` helpers + `denied` on `_ok`/`_empty_result`, denial/failure sites, leave id, defaulter/transport phone masking, `get_announcements`/`get_expenses`/`get_fee_sync_status`/`get_transport_status`/`query_student_record` normalized.
- `backend/routes/chat.py` — extractors read the single envelope.
- `backend/ai/prompts.py` — honest denial-relay directive.
- Tests: `parity/tool_envelope_shape_test.py` (new), `unit/test_r4_tool_envelope.py` (new, 5); updated `api/test_v1_tools_tenancy.py`, `api/test_owner_part3_qa.py`, `unit/test_leave_service_a2.py`.
