# Epic R10 — Self-Learning Phase 2 — COMPLETED

**Status:** ✅ DONE (2026-07-10)
**Gate:** Abhimanyu gave the full-R10 go-ahead (owner override, logged in `HUMAN-VERIFICATION-CHECKLIST.md` §C decision log). R10.5 role-*widening* stays OFF (Owner/Principal only).
**Suite:** backend `1464 → 1526 passed / 0 failed / 0 skipped` (+62 tests over the two increments); eval always-on tier `18 passed`; frontend R10 tests `13 passed` (MessageRenderer +3, LearningTools +3, plus existing).

R10 makes the assistant *measurably improve with use* while keeping the owner in full control. It was built in two increments:
- **Increment 1** (prior run, already merged on this branch): R10.2 feedback capture + candidate corrections, R10.1 AC4 recall-latency span.
- **Increment 2** (this run): everything below.

---

## R10.1 — Durable, scalable recall

- **AC1 (durable index / rebuild fallback):** the Chroma vector index is rebuilt from Mongo on startup (`vector.rebuild_index_from_mongo`, wired in `server.py` startup — shipped in R6.4). Vectors stay OFF by default; keyword recall is always-on. No change needed this epic beyond confirming the fallback.
- **AC2 (indexed/paginated recall — no full scans):** `store.recall` now fetches candidates via `_recall_candidates` — an index-ordered (`schoolId, user_id, updated_at_ts` DESC), **paginated** read (`_SWEEP_PAGE` batches) up to a **documented, logged** `RECALL_SCAN_CEILING` (2000). The old blind `list_memories(...).to_list(2000)` on the hot path is gone; memories beyond a single page stay recallable; hitting the ceiling is logged (never a silent wall, XM10 ethos).
- **AC3 (per-user cap + LRU/importance eviction):** shipped in R6.4 (`_enforce_user_cap`, logged + audited). Unchanged.
- **AC4 (recall latency span):** shipped in increment 1 (`layaastat` `ai_memory_recall` span with duration/candidates/returned/vector).

Files: `backend/services/memory/store.py`. Tests: `tests/backend/unit/test_r10_recall_scale.py` (pagination across pages, indexed-not-blind-scan spy, ceiling logged, owner/tenant scope preserved).

## R10.2 — Feedback loop

- **AC1/AC2 (capture + pending candidate correction):** shipped in increment 1 (`feedback_store.record_feedback`, `ai_feedback` collection + index, frontend Helpful/Improve with optional reason).
- **AC3 (activate/reject → fenced active memory):** `feedback_store.activate_correction` promotes a pending correction into a real memory (`source="correction"`, `category="preference"`, confidence 0.95) recalled inside the R6.3 instruction-inert fence; `reject_correction` marks it rejected. Both scoped to the reviewer's OWN pending queue (no cross-user note exposure — see review fixes) and idempotent (`status:"pending"` in the update filter). Activation only consumes the row when a memory was actually created.
- **AC4 (DPDP erasable):** shipped in increment 1 (`erase_owner_feedback` wired into `delete_staff`).
- **AC5 (`ai_feedback_ratio` metric):** shipped in increment 1 (`feedback_ratio` + `ai_feedback` metric emit).

Files: `backend/services/memory/feedback_store.py`, `backend/routes/chat.py`. Tests: `tests/backend/unit/test_r10_feedback.py`.

## R10.3 — Skill acquisition from repeated usage

- **AC1 (propose, don't silently save; two-step for write-embedding):** `chat_integration.finalize_turn` no longer auto-saves a distilled skill — it PROPOSES one ("save as a one-command routine?") and parks it as `pending_skill` on the conversation doc; it is saved only on an explicit affirmative next turn (`handle_pre_turn` step 3b). Write-embedding routines get a distinct disclosure ("it includes steps that change data … it will still ask you to confirm before every change").
- **AC2 (recallable, pre-fill, never bypass gates):** skills are recalled as FENCED reference data (`recall_context_block`) — background, never authoritative instructions; any write the LLM proposes still routes through confirm-token/kill-switch/lockdown. A recalled routine only pre-fills a plan.
- **AC3 (versioned + drift):** `add_skill` stores `version`, `tool_names`, and a `tool_signature` snapshot (`tools_signature` — a stable hash of the referenced tools' registry schemas). `recall_skills` (and the R10.4 overview) recompute the signature and flag `needs_update` when the underlying tool schema drifted; the recall block renders "⚠ this routine needs updating" instead of silently replaying a stale plan.
- **AC4 (tenanted + erasure):** skills are `(user_id, schoolId)`-scoped (unchanged); `erase_owner_skills` (R6.4) + the new `delete_skill` cover erasure.

Files: `backend/services/memory/chat_integration.py`, `backend/services/memory/skills_store.py`, `backend/routes/chat.py`. Tests: `tests/backend/unit/test_r10_skills.py`.

## R10.4 — Transparency & control surface ("What I've learned")

- **AC1 (panel + endpoints):** new `backend/routes/learning.py` — `GET /overview` (active memories, deactivated memories, skills w/ drift flag, this reviewer's pending corrections), `POST /corrections/{id}/activate|reject`, `PATCH /memories/{id}` (edit), `POST /memories/{id}/deactivate` (soft, reactivatable), `DELETE /memories/{id}`, `POST /memories/bulk-delete` (two-step: preview → confirm), `DELETE /skills/{id}`. New frontend panel `frontend/src/components/tools/LearningTools.js` (registered as the `what-ive-learned` tool for owner + principal).
- **AC2 ("Data used" discloses recalled memories):** `recall_context_block` populates a `recalled_sink`; the turn persists `Message.recalled_memories` and emits a `recalled_memories` SSE event; `MessageRenderer`'s "Data used" footer now shows "N remembered notes" alongside tools. Disclosure uses the stored (already-redacted) text.
- **AC3 (401/403 + cross-tenant):** every endpoint is `Depends(require_owner_or_principal)`; parametrized 401 (unauthenticated) + 403 (teacher) tests over all 8 endpoints; cross-tenant + cross-user isolation tests.

Files: `backend/routes/learning.py` (new), `backend/server.py`, `backend/models/schemas.py`, `backend/services/memory/{store,skills_store,chat_integration}.py`, `backend/routes/chat.py`, `frontend/src/components/tools/LearningTools.js` (new), `frontend/src/components/{MessageRenderer,ChatInterface,Layout,ToolDashboard}.js`, `frontend/src/lib/api.js`, `tests/backend/conftest.py`. Tests: `tests/backend/api/test_r10_learning_endpoints.py`, `frontend .../MessageRenderer.test.js`, `frontend .../tools/__tests__/LearningTools.test.js`.

## R10.5 — Widen rollout beyond Owner/Principal (gated, default OFF)

- **AC1 (single switch):** new `backend/services/memory/policy.py` mirrors `ai_action_policy.LOCKDOWN_ENABLED` — `MEMORY_RECALL_EXTRA_ROLES` / `MEMORY_CAPTURE_EXTRA_ROLES` are the one-line, greppable config; both ship EMPTY (Owner/Principal only, widening OFF).
- **AC2 (recall-only first):** `can_recall_memories` vs `can_capture_memories` are split; a widened role gets read-recall only — capture requires the role be in BOTH sets (a separate explicit decision). `recall_context_block` and `tool_recall_history` gate on recall; capture stays on the narrower `is_memory_subject`.
- **AC3 (advertised behavior matches gating):** parity guard `tests/backend/parity/memory_roles_parity_test.py` enforces Capture ⊆ Recall and default-OFF, so any widening is a reviewed change that must land with the matching prompt disclosure.

Files: `backend/services/memory/policy.py` (new), `backend/services/memory/__init__.py`, `backend/services/memory/chat_integration.py`, `backend/ai/tool_functions_v2.py`. Tests: `tests/backend/unit/test_r10_memory_roles.py`, `tests/backend/parity/memory_roles_parity_test.py`.

---

## Contract change worth flagging
FR32 ("no memory/skills HTTP surface") was a Phase-1 constraint. R10.4 **deliberately** introduces the owner/principal "What I've learned" control surface under `/api/learning/*`. The old FR32 test is updated to assert the new contract: the ONLY memory/skills-touching routes are the `/api/learning/*` panel endpoints (nothing leaked one in elsewhere).
