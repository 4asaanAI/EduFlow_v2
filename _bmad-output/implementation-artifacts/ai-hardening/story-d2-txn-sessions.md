# Story D.2 — Tenant-safe transaction sessions

**Epic:** D — Safe execution. **Status:** DONE (5 new FakeDb-tier tests + 2 mongo_real; baseline 25-fail unchanged; 875 pass).
**ADs:** AD4 (session), AD7 (service contract). **FRs/NFRs:** NFR10, NFR18.

## Acceptance Criteria
1. `database.get_txn_session()` returns `_client.start_session()` (real) — DONE; returns
   a usable `_NoopSession` when no replica-set client is configured (FakeDb/dev) so the
   executor has ONE code path.
2. `ScopedCollection` forwards `session=` through its scoped ops — DONE (ops already
   splat `*args/**kwargs` after injecting the tenant filter; verified by spy test).
3. A write inside a transaction still injects `schoolId` (no tenant leak) — DONE
   (`mongo_real/test_txn_tenant_scope_d2.py`).
4. `get_raw_db()` is never used inside the executor — DONE (executor uses the scoped
   `get_db()` only; see D.3).

## What shipped
- `services/txn_context.py` — a `contextvars.ContextVar` carrying the active txn
  session + `session_kwargs(session=None)` that resolves explicit → ambient → `{}`.
  This lets the executor bind one session for the whole plan and have every existing
  Epic A–C service auto-enlist WITHOUT changing tool/service signatures.
- All 10 domain services' `_session_kwargs(session)` now delegate to
  `txn_context.session_kwargs` (ambient fallback). Outside a txn the behavior is
  identical to pre-D.2 (`{}`), so the 875 stay green.
- `database.py` — `get_txn_session()` + `_NoopSession`/`_NoopTransaction`
  (inert async-context txn; never swallows exceptions so the executor still sees
  failures for saga/abort). Clarifying comment on `ScopedCollection` re: no
  tenant-leaking raw write path inside a txn.

## Design note
The contextvar propagates across `await` within the single `/confirm` request task and
is `reset()` in the executor's `finally`, so a session can never leak into another
request. This is the seam D.3's executor uses to make even the existing
session-unaware tools transactional.
