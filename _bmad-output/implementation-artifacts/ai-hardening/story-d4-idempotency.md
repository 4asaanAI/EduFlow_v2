# Story D.4 — Idempotency key + unique index + migration

**Epic:** D. **Status:** DONE (4 FakeDb tests + 2 mongo_real concurrency tests; baseline 25-fail unchanged; 883 pass).
**ADs:** AD6, AD14 (REST-key parity), P5. **FRs/NFRs:** FR11, NFR11.

## Acceptance Criteria
1. `idempotency_key = f"{plan_token}:{step_idx}"` stored on write rows — DONE
   (`plan_executor._claim_idempotency`; format pinned by `test_idempotency_index_d4`).
2. Unique index in `database._create_indexes()` + migration in `migrations/` (+ `run_all.py`)
   — DONE (`025_ai_write_idempotency_index.py`; `_create_indexes` declares
   `ai_write_idempotency.idempotency_key` unique).
3. Two concurrent confirms of the same plan → exactly one effect + one DuplicateKey-mapped
   "already applied" — DONE (`mongo_real/test_idempotency_concurrency_d4.py`).
4. An index-existence introspection test guards the index — DONE (two guards:
   migration + `_create_indexes`).
5. Where a REST route already has a content-based idempotency key, the AI path derives the
   SAME key — DONE: `fees_service.normalize_fee_key == routes.fees._normalize_fee_key`
   (established in Epic B; pinned here by `test_ai_fee_key_matches_rest_route_key`).

## What shipped
- `ai/plan_executor._claim_idempotency` — inserts the per-step key inside the txn;
  DuplicateKey propagates → txn aborts → caller returns `already_applied` (exactly-once).
- `database._create_indexes()` — `ai_write_idempotency.idempotency_key` unique index.
- `migrations/025_ai_write_idempotency_index.py` + `run_all.py` entry (idempotent).
- `tests/backend/unit/test_idempotency_index_d4.py`,
  `tests/backend/mongo_real/test_idempotency_concurrency_d4.py`.

## Two layers of idempotency (intentional)
- **Plan-level (NEW, D.4):** `{plan_token}:{step_idx}` — guards confirm replays /
  concurrent confirms of the SAME plan.
- **Content-level (Epic B):** e.g. `fees_service` `student|period|head` — guards two
  DIFFERENT AI instructions (or AI vs REST) that mean the same payment. Both apply; the
  content key is what makes AI and REST dedupe against one another (AD14).
