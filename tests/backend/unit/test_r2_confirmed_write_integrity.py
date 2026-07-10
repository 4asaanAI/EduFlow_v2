"""Epic R2 — Confirmed-Write Integrity (unit tier, FakeDb).

Covers the plan-executor failure matrix (X2/X4), the fail-loud txn-session policy
(X5), and the confirm-token HMAC + typed-reason hardening (XM6). API-level wiring
(the /confirm dispatch surfacing these) lives in test_r2_confirm_dispatch.py.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from ai import plan_executor
from ai.plan_executor import StepExecutionError
from ai.plan_schema import Plan, Step, WRITE, single_write_plan
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


class _FakeDb:
    def __init__(self):
        self.ai_write_idempotency = FakeCollection()


# ── R2.1 (X2): a returned failure envelope aborts and reports failure ──────────

async def test_single_step_failure_envelope_raises_step_error():
    db = _FakeDb()

    async def runner():
        return {"success": False, "message": "leave already decided"}

    plan = single_write_plan(
        tool="approve_leave", params={}, runner=runner, school_id="s", plan_token="tok-f1",
    )
    with pytest.raises(StepExecutionError) as ei:
        await plan_executor.run(plan, db=db)
    assert ei.value.tool == "approve_leave"
    assert "leave already decided" in str(ei.value)
    assert ei.value.result == {"success": False, "message": "leave already decided"}


async def test_multistep_aborts_on_failed_step_and_names_it():
    db = _FakeDb()
    ran = []

    async def ok():
        ran.append("s0")
        return {"success": True}

    async def fail():
        ran.append("s1")
        return {"success": False, "message": "target not found"}

    async def never():
        ran.append("s2")
        return {"success": True}

    plan = Plan(
        steps=[
            Step(tool="approve_leave", kind=WRITE, idx=0, runner=ok),
            Step(tool="create_announcement", kind=WRITE, idx=1, runner=fail),
            Step(tool="award_house_points", kind=WRITE, idx=2, runner=never),
        ],
        school_id="s", plan_token="tok-f2",
    )
    with pytest.raises(StepExecutionError) as ei:
        await plan_executor.run(plan, db=db)
    # The failing step aborts the plan; the step AFTER it never runs.
    assert ran == ["s0", "s1"]
    assert ei.value.step_idx == 1
    assert ei.value.tool == "create_announcement"


async def test_success_envelope_commits_normally():
    db = _FakeDb()

    async def runner():
        return {"success": True, "message": "done"}

    plan = single_write_plan(tool="t", params={}, runner=runner, school_id="s", plan_token="tok-ok")
    result = await plan_executor.run(plan, db=db)
    assert result.status == "committed"
    assert result.step_results[0]["status"] == "ok"


async def test_missing_success_key_is_not_treated_as_failure():
    """Architecture §5.1: step success = `result.get('success') is not False`."""
    db = _FakeDb()

    async def runner():
        return {"message": "legacy tool, no success key"}

    plan = single_write_plan(tool="t", params={}, runner=runner, school_id="s", plan_token="tok-legacy")
    result = await plan_executor.run(plan, db=db)
    assert result.status == "committed"
    assert result.step_results[0]["status"] == "ok"


# ── R2.2 (X4): already_applied semantics ───────────────────────────────────────

async def test_domain_duplicate_key_is_a_step_failure_not_already_applied():
    db = _FakeDb()

    async def runner():
        raise DuplicateKeyError(
            "E11000 duplicate key error collection: eduflow.students "
            "index: admission_number_1 dup key: { admission_number: \"A1\" }"
        )

    plan = single_write_plan(
        tool="create_student", params={}, runner=runner, school_id="s", plan_token="tok-dup",
    )
    with pytest.raises(StepExecutionError) as ei:
        await plan_executor.run(plan, db=db)
    msg = str(ei.value)
    # The failure names the offending index + collection (never 'already applied').
    assert "admission_number_1" in msg
    assert "eduflow.students" in msg
    assert ei.value.result["error"] == "duplicate_key"


async def test_idempotency_claim_duplicate_is_already_applied():
    db = _FakeDb()
    await db.ai_write_idempotency.create_index("idempotency_key", unique=True)
    runs = []

    async def runner():
        runs.append(1)
        return {"success": True}

    plan = single_write_plan(tool="t", params={}, runner=runner, school_id="s", plan_token="tok-idem")
    first = await plan_executor.run(plan, db=db)
    assert first.status == "committed"
    second = await plan_executor.run(plan, db=db)
    assert second.status == "already_applied"
    assert runs == [1]  # the write did not re-run


# ── R2.3 (X5): no silent no-op transactions ────────────────────────────────────

async def test_get_txn_session_raises_outside_development(monkeypatch):
    import database

    class _BoomClient:
        async def start_session(self):
            raise RuntimeError("no replica set")

    monkeypatch.setattr(database, "_client", _BoomClient())
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(database.TransactionUnavailableError):
        await database.get_txn_session()


async def test_get_txn_session_falls_back_to_noop_in_development(monkeypatch):
    import database

    class _BoomClient:
        async def start_session(self):
            raise RuntimeError("no replica set")

    monkeypatch.setattr(database, "_client", _BoomClient())
    monkeypatch.setenv("ENVIRONMENT", "development")
    sess = await database.get_txn_session()
    assert isinstance(sess, database._NoopSession)


async def test_get_txn_session_no_client_is_noop(monkeypatch):
    import database

    monkeypatch.setattr(database, "_client", None)
    monkeypatch.setenv("ENVIRONMENT", "production")
    # No client at all is the legitimate FakeDb/test tier — never a fail-loud case.
    sess = await database.get_txn_session()
    assert isinstance(sess, database._NoopSession)


# ── R2.4 (XM6): confirm-token HMAC + typed reasons ─────────────────────────────

_PLAN = [{"idx": 0, "tool": "approve_leave", "kind": "write", "params": {"leave_id": "lv-1"}}]


def test_plan_hash_is_hmac_keyed(monkeypatch):
    """The MAC must depend on the server secret — an attacker without JWT_SECRET
    cannot forge a matching digest."""
    from services import confirm_tokens

    import middleware.auth as auth
    monkeypatch.setattr(auth, "JWT_SECRET", "secret-A")
    h1 = confirm_tokens.compute_plan_hash(_PLAN, school_id="s", branch_id="b")
    monkeypatch.setattr(auth, "JWT_SECRET", "secret-B")
    h2 = confirm_tokens.compute_plan_hash(_PLAN, school_id="s", branch_id="b")
    assert h1 != h2  # different key ⇒ different MAC


def test_plan_hash_stable_for_same_key(monkeypatch):
    from services import confirm_tokens
    import middleware.auth as auth

    monkeypatch.setattr(auth, "JWT_SECRET", "secret-A")
    a = confirm_tokens.compute_plan_hash(_PLAN, school_id="s", branch_id="b")
    b = confirm_tokens.compute_plan_hash(_PLAN, school_id="s", branch_id="b")
    assert a == b


class _OneDocDb:
    def __init__(self, doc):
        self._doc = doc

        class Col:
            async def update_one(inner, filt, update):
                # The token is expired/used → no match, so the inspect path runs.
                class R:
                    modified_count = 0
                return R()

            async def find_one(inner, filt):
                return self._doc

        self.confirm_tokens = Col()


# ── R2.5 (XM1): AC3 decision — notifications are transactional, not post-commit ─
#
# The saga side_effect/compensate machinery is retained (it is correct and tested
# for genuine non-Mongo effects), but the LIVE AI-write notification path is a Mongo
# write that enlists in the executor's transaction, so a rolled-back plan sends
# nothing. This test locks that: create_notification forwards the ambient session.

async def test_notification_enlists_ambient_txn_session():
    from services import notification_service
    from services.txn_context import set_current_session, reset_current_session

    captured = {}

    class _Col:
        async def insert_one(self, doc, **kwargs):
            captured["session"] = kwargs.get("session")
            return None

    class _Db:
        notifications = _Col()

    sentinel = object()
    tok = set_current_session(sentinel)
    try:
        ok = await notification_service.create_notification(
            _Db(), user_id="u1", notification_type="test", message="hi", school_id="s",
        )
    finally:
        reset_current_session(tok)
    assert ok is True
    # The write enlisted in the ambient plan-executor session → rolls back with it.
    assert captured["session"] is sentinel


async def test_expired_token_returns_typed_code_with_intent():
    from services.confirm_tokens import consume_confirm_token

    now = datetime.now(timezone.utc)
    doc = {
        "token": "t", "user_id": "u1", "session_id": "s1", "used": False,
        "expires_at": now - timedelta(minutes=1),
        "plan": _PLAN,
    }
    with pytest.raises(HTTPException) as ei:
        await consume_confirm_token(token="t", user_id="u1", session_id="s1", db=_OneDocDb(doc))
    assert ei.value.status_code == 400
    assert ei.value.detail["code"] == "token_expired"
    # AC3: the intent is echoed so the client can re-issue in one tap.
    assert ei.value.detail["intent"] == {"kind": "plan", "tools": ["approve_leave"]}


async def test_post_consume_plan_tampered_echoes_intent(monkeypatch):
    """AC3: a POST-consume validation failure (token already marked used) echoes
    the original intent so the user can re-issue without re-typing."""
    from services import confirm_tokens
    import middleware.auth as auth

    monkeypatch.setattr(auth, "JWT_SECRET", "secret-A")
    tampered = [dict(_PLAN[0], params={"leave_id": "lv-1", "action": "reject"})]
    doc = {
        "token": "t", "user_id": "u1", "session_id": "s1",
        "school_id": "sch", "branch_id": "b1", "used": False,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "plan": tampered,
        # MAC bound to the ORIGINAL plan — the persisted plan was edited.
        "plan_hash": confirm_tokens.compute_plan_hash(_PLAN, school_id="sch", branch_id="b1"),
    }

    class _ConsumeDb:
        class Col:
            async def update_one(inner, filt, update):
                class R:
                    modified_count = 1
                return R()

            async def find_one(inner, filt):
                return dict(doc)

        confirm_tokens = Col()

    with pytest.raises(HTTPException) as ei:
        await confirm_tokens.consume_confirm_token(
            token="t", user_id="u1", session_id="s1",
            school_id="sch", branch_id="b1", db=_ConsumeDb(),
        )
    assert ei.value.status_code == 409
    assert ei.value.detail["code"] == "plan_tampered"
    assert ei.value.detail["intent"] == {"kind": "plan", "tools": ["approve_leave"]}
