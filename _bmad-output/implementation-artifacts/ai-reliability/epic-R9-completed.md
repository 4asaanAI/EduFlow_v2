# Epic R9 — Guardrails, Config & Adjacent Surfaces — COMPLETED

**Date:** 2026-07-10 · **Branch:** `ai-reliability-r1-turn-completion`
**Fixes:** C2, M8, M9, M10, X8, X9
**Goal met:** the AI's configuration fails loud instead of degrading silently; its
content guardrails are surgical (they stop harm without nuking legitimate work);
its kill-switch takes effect immediately across all servers; and its two adjacent
AI surfaces (chat uploads, certificate/ID-card generation) are hardened against
abuse, forgery, and cross-provider data egress.

**Baseline in:** 1444 passed / 0 failed. **Baseline out:** **1456 passed / 0 failed
/ 14 deselected / 0 skipped** (+12 net R9 tests). Eval tier 18 passed.

---

## R9.1 — Azure config fail-loud (C2)
The incident-class config bug: the code read only `AZURE_OPENAI_API_KEY` while the
docs/.env.example named `AZURE_OPENAI_KEY` — a mismatch that left the client
silently unconfigured (every turn degraded, no error).
- **AC1** ✅ `llm_client.get_azure_key()` accepts BOTH names (prefers
  `AZURE_OPENAI_API_KEY`); `.env.example` + CLAUDE.md aligned to say so.
- **AC2** ✅ `llm_client.validate_ai_config()` raises `ValueError` at startup
  (`server.startup`) when `ENVIRONMENT != development` and the key/endpoint are
  missing — the same fail-loud posture as `validate_school_id`.
- **AC3** ✅ the readiness check (`server._check_ai`) now also verifies the KEY is
  present (was endpoint-only).
- Tests: `test_get_azure_key_accepts_both_env_names`,
  `test_validate_ai_config_dev_ok_but_prod_missing_raises`.

## R9.2 — Surgical content filtering (M10, DPDP calibration)
- **AC1** ✅ (M10 — the "nukes the whole dataset" one) topic-blocking no longer runs
  over serialized **tool JSON** (`chat.py` 4 sites). The tool result is already
  PII-redacted upstream (`_safe_tool_result_for_chat` → `redact_for_llm`); running
  `filter_response` over the JSON let one blocked word inside legitimate data
  replace the ENTIRE dataset with a refusal. Structured output now gets a narrow
  PII-only pass (`redact_for_llm`) for rich blocks; the LLM's natural-language
  prose is still topic-filtered (`clean_response`).
- **AC2** ✅ the bomb patterns block only weaponization how-to + concrete threats,
  so "the atomic bombing of Hiroshima" / "an explosive chemical reaction" pass;
  `\bDAN\b` is scoped to jailbreak phrasing (`DAN mode`, `you are (now) DAN`) so a
  student named Dan is no longer blocked. Tests assert both.
- **AC3** ✅ `blood_group` removed from the redaction restricted-set — it's standard
  low-sensitivity operational data (printed on physical ID cards) that
  `get_student_profile` legitimately surfaces; the permanent "[restricted in chat]"
  was an over-block. Genuine health data (medical/allergies/disability) stays masked.
- Tests: `test_bomb_curriculum_allowed_but_howto_and_threat_blocked`,
  `test_student_named_dan_allowed_but_dan_jailbreak_blocked`,
  `test_blood_group_allowed_medical_still_restricted`; existing F.1 redaction test
  updated to the corrected contract.

## R9.3 — Kill-switch & observability honesty (M8, M9)
- **AC1** ✅ (M8) the confirm/write path calls `ai_writes_enabled(db,
  force_fresh=True)` — a direct Mongo read that bypasses the per-worker cache — so
  an operator's disable takes effect on the next confirmed write across ALL
  workers immediately (not up to a cache-TTL later on a stale worker). Documented
  in `docs/deployment-runbook.md §8.1`.
- **AC2** ✅ (M9) layaastat fire-and-forget spans/events are now held in a task set
  (`_spawn`) so the event loop can't GC a still-pending post; post failures log at
  **warning** (were `debug`, suppressed under the INFO root).
- **AC3** ✅ a new `ai_turn_outcome` counter (`status=answered|fallback|…`) is
  emitted from Phase 14 — the permanent alarm for the silent-empty-turn incident
  class (architecture §8). Fail-open.
- Tests: `test_kill_switch_force_fresh_bypasses_stale_cache`.

## R9.4 — chat_upload limits (X8)
- **AC1** ✅ the upload body is no longer fully buffered before the size check: reject
  early on `Content-Length`, then read in 1 MB chunks and abort the moment the 20 MB
  cap is exceeded.
- **AC2** ✅ zip members are size-checked against the archive DIRECTORY's declared
  `ZipInfo.file_size` BEFORE any decompression (per-member 5 MB + total 50 MB caps) —
  a zip bomb can no longer be expanded.
- **AC3** ✅ `image_data` posted to `POST /chat` is validated server-side (data-URL
  image format, base64 decodes, ≤20 MB decoded) before it reaches the LLM.
- Tests: `test_validate_image_data`, `test_zip_member_size_guard_uses_declared_size`.

## R9.5 — image_gen lockdown (X9)
- **AC1** ✅ `/certificate` and `/id-cards` are gated `require_owner_or_principal`
  (was any admin sub_category — a forgery surface). Content is resolved from the DB
  by `student_id` (certificate requires it; ID cards fetch by student_id `$in`
  batch) — client-supplied names/classes/marks are ignored, closing the forgery hole.
- **AC2** ✅ the Google **Gemini/Imagen** leg was REMOVED — it shipped school data to
  Google (contradicting the Azure-residency/DPDP ADR) and degraded silently on
  failure. Backgrounds are drawn locally (deterministic, zero egress, zero cost, no
  silent degrade).
- **AC3** ✅ per-school, per-kind daily generation cap (`_enforce_daily_cap`, 200/day)
  as an abuse brake; `cls.lower()` type-guarded (`str(cls or "")`).
- Tests (`test_image_gen_persistence.py`, rewritten): DB-resolved persist/binary
  paths, `student_id` required (400), unknown student (404), non-principal admin
  denied (403), ID-cards require student_ids (400), daily cap blocks over limit.

## Test-infra
- `conftest.FakeDb` gained an `image_gen_quota` collection.

## Deferred / decisions (logged in DEFERRED-AND-DISCOVERIES.md)
- L7–L9 (listed under the R9 goal line) were not separately specced as stories in
  the epics doc; R9.1–R9.5 cover C2/M8–M10/X8/X9. Any residual L7–L9 items fold
  into R11.6 (residual audit sweep).
- R1 backend early-return persistence (from R8) remains a dedicated chat.py
  single-exit story — candidate to pick up alongside R9's chat.py work or later.

## Files touched
`backend/ai/llm_client.py`, `backend/ai/content_filter.py`, `backend/ai/redaction.py`,
`backend/services/ai_kill_switch.py`, `backend/services/layaastat.py`,
`backend/routes/chat.py`, `backend/routes/chat_upload.py`, `backend/routes/image_gen.py`,
`backend/server.py`, `docs/deployment-runbook.md`, `backend/.env.example`, `CLAUDE.md`,
`tests/backend/conftest.py` + 2 test files (`test_r9_guardrails_config.py`,
`test_image_gen_persistence.py` rewritten) + `test_ai_redaction_f1_f2.py` (contract update).
