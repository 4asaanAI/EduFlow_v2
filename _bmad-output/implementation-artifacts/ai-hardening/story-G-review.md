# Epic G — AI self-learning (Memory + Skills): Epic-Close Multi-Lens Review

**Date:** 2026-06-08 · **Branch:** `ai-layer-hardening-plan` · **Reviewer:** Claude (epic-close, STEP 4)
**Baseline:** 25 pinned pre-existing failures (`ai-hardening-epic-a-baseline.txt`).
**Result after epic:** `1148 passed, 25 failed (pinned), 0 new failures` (+27 new tests).

## What this epic built
| Story | Deliverable |
|---|---|
| G.1 | Infra spike report → **GO, keyword-first, vector behind `MEMORY_VECTOR_ENABLED` (default OFF)**. `services/memory/vector.py` (graceful-degradation wrapper), `retrieval.py` (pure-Python keyword scoring). |
| G.2 | `services/memory/store.py` — Mongo `ai_memories`, scoped `(user_id, schoolId)`; `redact_text_for_memory()` on write; dedup; audit. |
| G.3 | `store.recall()` hybrid (vector ∪ keyword, re-ranked by deterministic keyword score; degrades to keyword-only); injected into the system prompt via `chat_integration.recall_context_block`. |
| G.4 | `extractor.extract_memory_items` (auto-save vs uncertain by confidence); `chat_integration.finalize_turn` auto-saves + asks an in-chat yes/no; inline `remember:`/`forget`; affirmative-confirm of pending. No UI (FR32). |
| G.5 | `tool_recall_history` (registry) — synthesis that **delegates to existing read tools** (identical authz/scope), Owner/Principal-gated, in `MINOR_READ_TOOLS` (FR35 audit). |
| G.6 | `extractor.extract_skill` + `skills_store` — confidence floor (0.6), dedup-by-title, in-chat feedback, `(user_id, schoolId)` isolation. |
| G.7 | `erase_owner_memories`, `purge_student_references` (wired into `routes/students.py:erase_student`), `prune_expired` + `expire_at` TTL index (migration 026). |
| G.8 | `correct_memory` (update/remove), confidence+recency decay in `retrieval.score_memories`. |

## Findings & fixes (all fixed in-epic)

| # | Severity | File | Issue | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | **High** | `extractor.py` | `looks_like_correction` matched a bare mid-sentence "actually" (`re.search`), so "actually, show me attendance" would **silently delete** the top-matching memory — data loss. | Anchored regex to START + explicit "that's wrong/not right" phrasings only; removed bare "actually". | `test_reg_correction_detection_is_conservative` |
| 2 | **High** | `extractor.py` / `chat_integration.py` | `is_affirmative` matched any message starting with "ok"/"sure", so "ok show me the fees" (with a pending memory) was treated as a confirmation, **saved the memory and swallowed the real request**. | Made `_AFFIRM_RE` a full-message match (only trailing courtesy words allowed). | `test_reg_affirmative_does_not_swallow_real_request`, `test_reg_affirmative_request_not_short_circuited` |
| 3 | Med | `skills_store.py` | Skill text (replayed into the LLM on recall) was not PII-minimized, unlike memories. | Scrub title/problem/solution/steps via `redact_text_for_memory` on write (DPDP hard control). | `test_reg_skill_text_pii_scrubbed` |
| 4 | Med | `database.py` | Initial TTL index was on `updated_at` (an ISO **string**) — Mongo TTL only acts on BSON Date, so retention would silently never fire. | Added a real Date `expire_at` field (now + RETENTION_DAYS) and TTL `expireAfterSeconds=0`; refreshed on correction. | `test_g7_retention_prune_expired` (app-side review path); index asserted in migration 026. |
| 5 | Low | `store.purge_student_references` | Mongo array-contains (`student_refs: id`) isn't modeled by FakeDb, and the query was brittle. | Filter array membership in Python — identical behavior on both test tiers and real Mongo. | `test_g7_purge_student_references` |

## Lenses applied
- **bmad-code-review (correctness/quality):** found #4, #5. Shared-service signature parity (AD7) preserved — all store/skills fns take `ActorContext`.
- **bmad-review-adversarial-general:** found #1, #2 (intent-detection over-trigger). Also confirmed: memory is self-injection only (owner writes own memory), so prompt-injection-via-memory cannot cross owners/tenants.
- **bmad-review-edge-case-hunter:** verified empty/None text (ignored), AI-unavailable turns never reach the extraction call (Phase 8/9 return first), dedup, double-increment (benign), and that the short-circuit reply persists via `_stream_text_message`.
- **bmad-testarch-test-review:** isolation asserted on FakeDb (no auto-scoping → leaks would surface); LLM mocked deterministically; no false-greens.
- **bmad-testarch-trace:** every G.* AC has ≥1 test (see mapping in the test file headers / function names `test_g2_*` … `test_g8_*`).
- **bmad-testarch-nfr:** Integrity — `(user_id, schoolId)` isolation tested (owner + tenant). Security/Privacy — write redaction + skill redaction + minor-read audit reuse. Perf — see accepted tradeoff below.

## Accepted (non-bug) notes
- **Perf:** `finalize_turn` adds one extraction LLM call per Owner/Principal turn (skill extraction only fires above the complexity threshold and is short-circuited to zero LLM calls below it — `test_g6_skill_below_complexity_threshold_dropped`). Accepted for the Owner/Principal pilot; revisit (async/off-thread) before Phase-2 widening.
- **Vector path** does a blocking embed in an async context when enabled; default OFF per the G.1 spike, so production is unaffected. Flagged for the staging enablement follow-up.
- **Inline `remember:`** runs before the input content-filter, but the reply is fixed text and the stored text is PII-redacted; trusted pilot users only.

## Audits
- `scoped_filter`/`scoped_query` audit on touched routes: `routes/chat.py` (5 pre-existing hits, unchanged; new memory queries carry explicit `schoolId`+`user_id` inside the service layer). `routes/students.py` erase uses `get_school_id()` school-wide purge — **intentional**: a student may be referenced in any owner's memory, so purge is school-wide, not branch-scoped.
- FR32 (no UI surface): asserted by `test_g4_no_memory_ui_surface_exists` (no `/memory` or `/skills` route).
