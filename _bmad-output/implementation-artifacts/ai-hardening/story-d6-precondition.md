# Story D.6 — Optimistic-concurrency precondition revalidation

**Epic:** D. **Status:** DONE (4 FakeDb tests + 1 mongo_real test; baseline unchanged; 891 pass).
**ADs:** AD5 (precondition, distinct from AD3 plan-hash), P7 (409 taxonomy). **FRs/NFRs:** NFR21.

## Acceptance Criteria
1. Each write step carries a `precondition` (version/updatedAt or key fields) — DONE
   (`Step.precondition`; Epic E's planner populates it, Epic D proves the mechanism).
2. The executor re-reads inside the transaction and aborts the whole plan if a value
   changed since planning — DONE (`_revalidate_precondition`, runs inside the txn
   before the write + idempotency claim).
3. Aborts with a `plan_stale` 409 distinct from `plan_tampered` — DONE
   (`PlanStaleError.code == "plan_stale"`; chat.py maps it to 409;
   `test_plan_stale_is_distinct_from_plan_tampered`).
4. No partial write occurs — DONE (`test_changed_precondition_raises_plan_stale_no_write`
   + `mongo_real/test_precondition_d6.py`: the update never applies, no idempotency row).

## What shipped
- `ai/plan_executor._revalidate_precondition(db, step, branch_id)` — re-reads
  `precondition.collection/id` inside the txn via `scoped_query(branch_id=...)` and
  raises `PlanStaleError` on a missing record or a changed `field` (default `updated_at`,
  or explicit `version`). Runs BEFORE the write and the idempotency claim, so a stale
  plan leaves zero side effects.
- `routes/chat.py` already maps `PlanStaleError`→`409 {code: plan_stale}` (D.3 wiring).

## Division of labor (AD5)
- `plan_hash` (AD3, Epic E) = identity/structure/tamper integrity → `plan_tampered`.
- `precondition` (this story) = data-freshness/lost-update → `plan_stale`.
The two raise DISTINCT 409 codes so the frontend (Epic I) can say "re-confirm" vs
"data changed — re-plan" (UX-DR5).
