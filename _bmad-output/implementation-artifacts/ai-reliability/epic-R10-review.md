# Epic R10 — Epic-Close Quality Gate — REVIEW

**Date:** 2026-07-10
**Reviewers/lenses:** bmad-code-review (inline), bmad-review-adversarial-general (subagent), bmad-review-edge-case-hunter (subagent), bmad-testarch-test-review, bmad-testarch-trace, bmad-testarch-nfr.

## Final test counts
- Backend: **1526 passed / 0 failed / 0 skipped** (14 deselected = `mongo_real` + `llm_eval` credentialed tiers). Baseline before R10 increment 2: 1464.
- Frontend: **53 passed** of the touched/new suites; the only red tests are the 2 pre-existing `LayoutRouting` AggregateError tests (fail on `main` before R8 — logged/deferred). New R10 frontend tests (MessageRenderer +3, LearningTools +3) pass.
- Eval corpus always-on tier: **18 passed** (credentialed LLM-judge tier deselected — no Azure creds here; unchanged from R9). No prompt/tool wording changed in R10, so the LLM-judge score is not expected to move.

## Findings (from the adversarial + edge-case lenses) and disposition

| Sev | File | Issue | Disposition | Regression test |
|-----|------|-------|-------------|-----------------|
| **High** | `routes/learning.py` overview + `feedback_store.list_pending_corrections` | Cross-user PII leak: overview returned the WHOLE school's pending "Improve" notes to any owner/principal — another staff member's free-text notes exposed. | **FIXED** — overview + activate + reject now scope to the reviewer's OWN pending queue (`user_id=user["id"]`). | `api/test_r10_learning_endpoints.py::test_overview_pending_scoped_to_reviewer_only`, `::test_activate_anothers_correction_is_404`, `unit/test_r10_feedback.py::test_activate_scoped_to_actor_own_queue` |
| **High** | `feedback_store.activate_correction` | Row was marked `activated` even when `add_memory` returned None → correction silently consumed + caller told 404 (data loss). | **FIXED** — only leave the pending queue when a memory was created; else stay pending + return None. Added `status:"pending"` to the update filter for idempotency parity with reject. | `unit/test_r10_feedback.py::test_activate_leaves_row_pending_when_no_memory_created` |
| **Med** | `routes/learning.py` bulk-delete + edit | `await request.json()` unguarded → 500 on empty/malformed body; `ids` non-list silently char-iterated; `>100 ids` silently truncated. | **FIXED** — JSON body guarded (→ {}), `ids` must be a list, `>_MAX_BULK_DELETE` → 400 (no silent truncation). | `::test_bulk_delete_rejects_non_list_ids`, `::test_bulk_delete_rejects_too_many_ids`, `::test_edit_memory_missing_body_is_400_not_500` |
| **Med** | `routes/learning.py` overview + `LearningTools.js` | Deactivate was a UI dead-end — deactivated memories vanished from the panel with no reactivate path (AC1 "kept for history"). | **FIXED** — overview returns `deactivated_memories` separately; panel shows a "Deactivated notes" section with Reactivate (`deactivateMemory(id,false)`). `memories` stays active-only. | `::test_overview_separates_deactivated_and_supports_reactivate`, frontend `LearningTools.test.js` reactivate case |
| **Low (defensive)** | `chat_integration.handle_pre_turn` | Theoretical: a stale `pending_skill` could survive a `pending_memory` confirm and be activated by a later "yes" (edge-case reviewer verified the non-affirmative clear already prevents coexistence, but hardened anyway). | **FIXED** — a confirm now clears any sibling pending (belt-and-suspenders). | `unit/test_r10_skills.py::test_confirming_memory_also_clears_stale_pending_routine` |
| **Low (cosmetic)** | `MessageRenderer.js` | A recalled-memory ref with `id` but empty `text` rendered an empty disclosure row. | **FIXED** — display filter requires `m.text`. | covered by `MessageRenderer.test.js` (no-footer + both-counts cases) |

### Investigated and confirmed NOT a bug (no change)
- **`recalled_memories` NameError risk** (Phase 4 raises before recall) — initialized to `[]` *before* the Phase-4 try; the early-return on context-build failure never reaches Phase 14 with it referenced. Verified safe.
- **pending_memory vs pending_skill "yes" ambiguity** — deterministic (memory resolved before skill) AND they cannot coexist (non-affirmative turns clear all pendings before finalize sets exactly one). Verified safe; hardened defensively anyway (above).
- **Cross-user/cross-school PATCH/DELETE/deactivate** — all store ops filter by `_scope(ctx)` = `{schoolId, user_id}` → foreign ids 404, never act. Verified by `test_cross_tenant_memory_cannot_be_deleted`.
- **Skills never bypass gates (AC2)** — recalled skills are fenced data; `add_skill` stores steps/tool_names, never executes; downstream writes still hit confirm/kill-switch/lockdown. Verified.

### Dismissed / accepted (documented, not fixed now)
- **`activate` author-recall-eligibility** — moot after scoping activation to the actor (owner/principal, always recall-eligible).
- **`embeds_write` captured but unused on the save path** — intentional: the write-embedding two-step is the *proposal disclosure*; saving a routine is not itself a write, and every later action still hits the gates. Field retained for audit/telemetry.
- **`FakeCursor.sort` TypeError on mixed float/missing `updated_at_ts`** — test-shim-only, not triggered by any current test (all product docs carry `updated_at_ts`; real Mongo tolerates missing keys). Logged in DEFERRED as a test-infra hardening item to avoid destabilizing the 1526-test suite with a broad shared-shim change at epic close.

## scoped_filter / scoped_query grep audit (STEP 4d)
Touched backend files audited. Memory stores (`store.py`, `feedback_store.py`, `skills_store.py`) scope by `(schoolId, user_id)` via `_scope(ctx)` — the correct per-user memory tenancy model, not branch-scoped operational data. `chat_integration.py` conversation-doc updates use `scoped_filter({id,user_id}, get_school_id())` (school + user + conversation — correct, matches the existing R6 pending-memory pattern; extended identically for `pending_skill`). `routes/learning.py` delegates all DB access to the ctx-scoped store layer. No un-migrated `scoped_filter({})` hits.

## Traceability (STEP 4b — every AC → a test)
Every R10 AC maps to at least one test (see `epic-R10-completed.md` per-story "Tests:" lines). Highlights: R10.1 AC2 → `test_r10_recall_scale`; R10.2 AC3 → `test_r10_feedback` activate/reject + endpoints; R10.3 AC1/AC3 → `test_r10_skills` proposal/version/drift; R10.4 AC1/AC3 → `test_r10_learning_endpoints` (401/403 ×8, cross-tenant), AC2 → `MessageRenderer.test.js`; R10.5 AC1/AC2 → `test_r10_memory_roles`, AC3 → `memory_roles_parity_test`.

## NFR (STEP 4b)
- **Security:** all learning endpoints owner/principal-gated (401/403 proven); cross-tenant + cross-user isolation proven; corrections scoped to the actor's own queue (closed the cross-user note leak); disclosure uses redacted-at-storage text only.
- **Performance:** recall is now indexed + paginated + bounded (was a blind `to_list(2000)`); latency measured via span. Endpoints are single-collection reads/writes; no N+1 introduced.
- **Reliability:** memory hooks remain best-effort (never raise into a turn); `recalled_memories` always bound; activate is a safe no-op when nothing is created.
- **DPDP:** feedback + memory + skill all erasable and wired into the staff lifecycle-end path; no raw PII surfaced.

## Verdict
Gate clean. All epic-born findings fixed in-run with fails-before/passes-after regression tests. One accepted test-infra item deferred (logged). Ready to merge.
