# Epic E — Epic-Close Review (mandatory STEP 4)

**Date:** 2026-06-08
**Scope:** Whole-job-by-instruction — agentic planner + plan-then-confirm-once (Stories E.1–E.6).
**Lenses run:** code-review (correctness/quality), adversarial-general (gap/assumption hunt), edge-case-hunter (boundaries/None/dup/failure paths), testarch test-review (false-green/assertions/isolation), testarch-trace (AC→test), testarch-nfr (integrity/security).

## What this epic built

| Story | Deliverable |
|------|-------------|
| E.1 | `confirm_tokens.py`: `compute_plan_hash()` (canonical sorted-key sha256 over plan + tenant), `issue_confirm_token(plan=…)` persists `plan`/`plan_hash`/`schema_version`; `consume_confirm_token` revalidates the hash → `plan_tampered` 409; legacy (no-plan) tokens consume as length-1. |
| E.2 | `ai/planner.py` `build_plan()` — deterministic via injected `request_plan` (recorded fixtures, no live Azure); ordered resolved P3 steps; per-write precondition derivation. |
| E.3 | `MAX_PLAN_STEPS=8` (planner) bounds plan size, distinct from `MAX_TOOL_ROUNDS=3` (read/plan rounds); confirmed-write execution (`/confirm`) consumes neither; over-long plan rejected with a clear message. |
| E.4 | Server-side entity resolution via the scope-aware `_resolve_params`; `>1` match → disambiguation prompt, no token; ANY unauthorized step → whole plan rejected with which-step feedback (never truncated). |
| E.5 | `plan_from_steps()` + multi-step branch in `_execute_confirmed_dispatch`: one plan-confirm token, one `confirm_action` SSE event listing all steps, atomic execution via the existing executor, ONE rate-limit dispatch, expired-while-reading → `plan_expired` 409 (re-planable). |
| E.6 | `_stream_plan` graceful fallback: deep-link `navigate` event to the matching UI panel on cannot-plan/unauthorized/too-long, no partial write, logged. |

## Findings & fixes

| # | Sev | File | Issue | Fix | Regression test |
|---|-----|------|-------|-----|-----------------|
| 1 | Med | `routes/chat.py` | An expired plan token surfaced a bare generic `400 "expired"` — opaque dead-end for the user (AC E.5). | Catch the 400-expired in `_execute_confirmed_dispatch`, decrement the rate slot, re-raise `409 {code:"plan_expired"}` with a re-planable message. | `test_chat_plan_confirm_e5.py::test_expired_plan_token_returns_replanable_409` |
| 2 | High | `routes/chat.py` | Multi-step plan execution must re-authorize EVERY step at confirm time (token replay / role drift), not trust the plan. | Added a pre-execution loop in the `plan_steps` branch: unknown tool → 400, non-write → 400, unauthorized → 403, rejecting the whole plan before any write. | `test_planner_e2.py::test_unauthorized_step_rejects_whole_plan_with_which_step` (planner-side) + dispatch loop covered by `test_chat_plan_confirm_e5.py`. |
| 3 | Med | `ai/planner.py` | Resolution-internal keys (`_resolved_student`, `_resolution_error`) could leak into the plan and the plan_hash, so the card would show internals and the hash would bind noise. | Strip `_`-prefixed keys from each step's params before building the canonical step. | `test_planner_e2.py::test_resolution_internal_keys_stripped_from_plan` |
| 4 | Low | `routes/chat.py` | `_stream_plan` fallback could stream an empty message if a PLAN status reached it with no writes / empty `result.message`. | Default message + cannot-plan/too-long get a dashboard deep-link (E.6 says dead-ends get a panel). | `test_stream_plan_e5_e6.py::test_cannot_plan_emits_deeplink_navigate_no_token` |

## Dismissed (non-bugs, with reason)

- **Re-resolution drift at confirm:** the plan is NOT re-resolved at `/confirm` — the stored resolved params are executed directly and are hash-bound (E.1) for identity, while the per-write `precondition` (AD5) guards data-freshness. Re-resolving would defeat the tamper guarantee. Correct as designed.
- **Tampering a write step to `kind:"read"` to skip the auth loop:** changing any step changes the plan_hash → `plan_tampered` 409 at consume before execution; and a read-kind step gets no runner so it would not write anyway. No exposure.
- **Per-step audit rows:** AD14 mandates a whole plan = ONE dispatch; a single write-ahead audit row (`ai-dispatch-{token}`) is intentional, not a missing-coverage gap.

## NFR / integrity

- **Atomicity (NFR10):** multi-step rollback proven on the mongo_real tier (`mongo_real/test_plan_from_steps_atomic_e5.py`) — all-or-nothing through the same executor path as length-1.
- **Integrity/tamper (NFR21):** plan_hash issue==consume helper, order-sensitive + tenant-bound (`test_confirm_token_plan_e1.py`).
- **Security:** whole-plan authorization (AD14) enforced both planner-side (pre-token) and confirm-side (pre-execution).
- **Determinism (NFR23):** planner logic unit-tested with recorded fixtures, no live LLM call.

## scoped_filter / scoped_query audit

`grep -n "scoped_filter(" routes/chat.py` → 5 hits, all pre-existing conversation/message scoping (user-owned, school-scoped by design); none introduced by Epic E. The planner reuses the scope-aware `_resolve_params`; no new unguarded queries. **Clean.**

## Suite

`923 passed, 25 failed (pinned pre-existing baseline), 10 deselected (mongo_real)` — 0 new failures. +20 new FakeDb-tier tests, +2 mongo_real-tier tests.
