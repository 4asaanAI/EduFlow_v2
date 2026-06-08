"""Regression guards for the Epic A–D collective review (2026-06-08).

Each test pins a bug found by the BMAD multi-lens epic-close review so it can never
silently return. Atomic-rollback proofs that need a real transaction live on the
mongo_real tier (`mongo_real/test_review_atomicity_ad.py`).
"""

from __future__ import annotations

import pytest
from pymongo.errors import OperationFailure

from ai import plan_executor
from ai.plan_executor import NeedsManualReconciliationError, PlanStaleError
from ai.plan_schema import Plan, Step, WRITE, single_write_plan
from services import txn_context
from services.notification_service import create_notification
from services.audit_service import write_audit_doc
from services.actor_context import ActorContext
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


# ── #1/#2 — create_notification / write_audit_doc enlist the ambient txn session ──

class _SpyCol(FakeCollection):
    def __init__(self):
        super().__init__()
        self.session_seen = "UNSET"

    async def insert_one(self, doc, **kwargs):
        self.session_seen = kwargs.get("session", None)
        return await super().insert_one(doc)


class _SpyDb:
    def __init__(self):
        self.notifications = _SpyCol()
        self.audit_logs = _SpyCol()


async def test_create_notification_picks_up_ambient_session():
    db = _SpyDb()
    sentinel = object()
    tok = txn_context.set_current_session(sentinel)
    try:
        await create_notification(db, user_id="u1", notification_type="t", message="m")
    finally:
        txn_context.reset_current_session(tok)
    assert db.notifications.session_seen is sentinel  # enlisted in the txn


async def test_create_notification_no_session_outside_txn():
    db = _SpyDb()
    await create_notification(db, user_id="u1", notification_type="t", message="m")
    assert db.notifications.session_seen is None  # unchanged behavior outside executor


async def test_write_audit_doc_picks_up_ambient_session():
    db = _SpyDb()
    sentinel = object()
    tok = txn_context.set_current_session(sentinel)
    try:
        await write_audit_doc(db, {"action": "x", "entity_id": "e", "entity_type": "c"})
    finally:
        txn_context.reset_current_session(tok)
    assert db.audit_logs.session_seen is sentinel


# ── #4/#5 — idempotency robustness ──

class _IdemDb:
    def __init__(self):
        self.ai_write_idempotency = FakeCollection()


async def test_noop_path_cleans_up_idempotency_claim_on_failure():
    """On the non-transactional (noop) path a failed runner must NOT leave a claimed
    key behind (it would falsely reject a legitimate retry as already_applied)."""
    db = _IdemDb()
    await db.ai_write_idempotency.create_index("idempotency_key", unique=True)

    async def boom():
        raise RuntimeError("write failed mid-runner")

    plan = single_write_plan(tool="t", params={}, runner=boom, school_id="s", plan_token="tok-x")
    with pytest.raises(RuntimeError):
        await plan_executor.run(plan, db=db)
    # claim was compensated → a retry can proceed (no orphan row)
    assert await db.ai_write_idempotency.count_documents({"idempotency_key": "tok-x:0"}) == 0


async def test_write_conflict_maps_to_already_applied_when_key_committed():
    """A concurrent WriteConflict (OperationFailure, not DuplicateKey) where the winner
    already committed the key must map to already_applied, not a 500."""
    class _ConflictDb:
        class _Col:
            async def insert_one(self, doc, **kwargs):
                raise OperationFailure("write conflict", code=112)
            async def find_one(self, query, *a, **k):
                return {"idempotency_key": query.get("idempotency_key")}  # winner committed it
        ai_write_idempotency = _Col()

    async def runner():
        return {"success": True}

    plan = single_write_plan(tool="t", params={}, runner=runner, school_id="s", plan_token="tok-c")
    result = await plan_executor.run(plan, db=_ConflictDb())
    assert result.status == "already_applied"


async def test_dry_run_does_not_claim_idempotency():
    db = _IdemDb()
    await db.ai_write_idempotency.create_index("idempotency_key", unique=True)

    async def runner():
        return {"ok": True}

    plan = single_write_plan(tool="t", params={}, runner=runner, school_id="s", plan_token="tok-d")
    result = await plan_executor.run(plan, db=db, dry_run=True)
    assert result.status == "dry_run"
    # No claim persisted → a later REAL confirm of the same plan is not falsely rejected.
    assert await db.ai_write_idempotency.count_documents({}) == 0


# ── #6 — saga: a completed side-effect with NO compensator escalates to recon ──

async def test_uncompensatable_completed_side_effect_escalates_to_recon():
    db = _IdemDb()
    fired = []

    async def runner():
        pass

    async def se0():
        fired.append("se0")  # succeeds, but has NO compensator

    async def se1_fail():
        raise RuntimeError("second side effect failed")

    plan = Plan(
        steps=[
            Step(tool="t0", kind=WRITE, idx=0, runner=runner, side_effect=se0, compensate=None),
            Step(tool="t1", kind=WRITE, idx=1, runner=runner, side_effect=se1_fail),
        ],
        school_id="s", plan_token="tok",
    )
    # Cannot cleanly undo se0 → must NOT claim "compensated"; escalate to recon.
    with pytest.raises(NeedsManualReconciliationError):
        await plan_executor.run(plan, db=db)


# ── #11/#12 — numeric coercion is a domain (400) error, not an uncaught 500 ──

def _ctx():
    return ActorContext(user_id="u1", role="owner", sub_category=None, school_id="aaryans-joya", branch_id=None, actor_name="O")


async def test_house_points_non_numeric_delta_is_domain_error():
    from services.house_points_service import award_points, HousePointsValidationError

    with pytest.raises(HousePointsValidationError):
        await award_points(_IdemDbHouses(), _ctx(), {"house_id": "h1", "delta": "lots"})


class _IdemDbHouses:
    def __init__(self):
        self.houses = FakeCollection([{"id": "h1", "schoolId": "aaryans-joya", "points": 10}])
        self.house_points_log = FakeCollection()
        self.audit_logs = FakeCollection()


async def test_fees_non_numeric_amount_is_domain_error():
    from services.fees_service import record_payment, FeeValidationError

    class _FeesDb:
        fee_transactions = FakeCollection()
        fee_idempotency_keys = FakeCollection()
        audit_logs = FakeCollection()

    with pytest.raises(FeeValidationError):
        await record_payment(
            _FeesDb(), _ctx(),
            {"student_id": "s1", "amount": "abc", "payment_mode": "cash", "fee_period": "2026-Q1"},
        )


# ── #3 — attendance bulk: a per-record failure under a txn aborts (all-or-nothing) ──

async def test_attendance_per_record_failure_raises_under_session():
    from services.attendance_service import mark_attendance

    class _FailingAttendance(FakeCollection):
        async def update_one(self, *a, **k):
            raise RuntimeError("record write conflict")

    class _Db:
        def __init__(self):
            self.student_attendance = _FailingAttendance()
            self.attendance_bulk_keys = FakeCollection()
            self.audit_logs = FakeCollection()

    params = {"class_id": "c1", "date": "2026-06-08",
              "records": [{"student_id": "s1", "status": "present"}]}

    # With an ambient session (inside the executor txn) the failure must PROPAGATE so
    # the transaction aborts — not be swallowed into a per-record "error" result.
    tok = txn_context.set_current_session(object())
    try:
        with pytest.raises(RuntimeError):
            await mark_attendance(_Db(), _ctx(), params)
    finally:
        txn_context.reset_current_session(tok)


async def test_attendance_per_record_failure_reported_without_session():
    """REST path (no session): per-record error is REPORTED, not raised — the A.1
    characterization behavior is preserved."""
    from services.attendance_service import mark_attendance

    class _FailingAttendance(FakeCollection):
        async def update_one(self, *a, **k):
            raise RuntimeError("record write conflict")

    class _Db:
        def __init__(self):
            self.student_attendance = _FailingAttendance()
            self.attendance_bulk_keys = FakeCollection()
            self.audit_logs = FakeCollection()

    params = {"class_id": "c1", "date": "2026-06-08",
              "records": [{"student_id": "s1", "status": "present"}]}
    result = await mark_attendance(_Db(), _ctx(), params)
    assert result["results"][0]["status"] == "error"


# ── #13 — precondition: nested field + malformed precondition does not silently pass ──

async def test_precondition_supports_nested_field():
    class _Db:
        def __init__(self):
            self.ai_write_idempotency = FakeCollection()
            self.fee_structures = FakeCollection(
                [{"id": "f1", "schoolId": "aaryans-joya", "meta": {"version": 2}}]
            )

    db = _Db()

    async def runner():
        pass

    step = Step(
        tool="t", kind=WRITE, idx=0, runner=runner,
        precondition={"collection": "fee_structures", "id": "f1", "field": "meta.version", "version": 9},
    )
    plan = Plan(steps=[step], school_id="s", plan_token="tok")
    with pytest.raises(PlanStaleError):  # nested 2 != expected 9
        await plan_executor.run(plan, db=db)
