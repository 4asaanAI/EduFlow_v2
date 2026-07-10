"""
Unit Tests: Phase 5 token budget service.
"""

import pytest

from services import token_service
from tests.backend.conftest import FakeCollection


@pytest.fixture
def token_db(monkeypatch):
    db = type(
        "TokenDb",
        (),
        {
            "token_balances": FakeCollection(),
            "token_usage": FakeCollection(),
            "token_purchases": FakeCollection(),
        },
    )()
    monkeypatch.setattr(token_service, "get_db", lambda: db)
    return db


@pytest.mark.asyncio
async def test_check_and_reserve_tokens_falls_through_plan_personal_school_then_exhausted(token_db):
    month = token_service._current_month_key()
    token_db.token_balances.docs[:] = [
        {
            "branch_id": "branch-1",
            "role_limits": {"teacher": 100},
            "personal_topups": {"teacher-1": 50},
            "school_topup_pool": 75,
            "self_recharge_enabled": False,
        }
    ]
    token_db.token_usage.docs[:] = [
        {
            "branch_id": "branch-1",
            "user_id": "teacher-1",
            "month": month,
            "tokens_used": 90,
        }
    ]
    user = {"id": "teacher-1", "role": "teacher"}

    personal = await token_service.check_and_reserve_tokens(user, "branch-1", estimated_tokens=20)
    school = await token_service.check_and_reserve_tokens(user, "branch-1", estimated_tokens=60)
    exhausted = await token_service.check_and_reserve_tokens(user, "branch-1", estimated_tokens=80)

    assert personal["allowed"] is True
    assert personal["source"] == "personal_topup"
    assert school["allowed"] is True
    assert school["source"] == "school_topup"
    assert exhausted == {
        "allowed": False,
        "source": "exhausted",
        "message": "Your monthly AI token limit has been reached. Please contact your school administrator.",
        "can_recharge": False,
    }


@pytest.mark.asyncio
async def test_check_and_reserve_tokens_allows_unconfigured_and_unlimited_roles(token_db):
    unconfigured = await token_service.check_and_reserve_tokens(
        {"id": "owner-1", "role": "owner"}, "new-branch", estimated_tokens=10_000
    )
    token_db.token_balances.docs[:] = [
        {"branch_id": "branch-1", "role_limits": {"owner": -1}, "school_topup_pool": 0}
    ]

    unlimited = await token_service.check_and_reserve_tokens(
        {"id": "owner-1", "role": "owner"}, "branch-1", estimated_tokens=10_000
    )

    assert unconfigured["allowed"] is True
    assert unconfigured["source"] == "unlimited"
    assert unlimited["allowed"] is True
    assert unlimited["source"] == "plan"


@pytest.mark.asyncio
async def test_record_usage_logs_usage_deducts_topups_and_sets_warning(token_db):
    token_db.token_balances.docs[:] = [
        {
            "branch_id": "branch-1",
            "role_limits": {"teacher": 100},
            "personal_topups": {"teacher-1": 500},
            "school_topup_pool": 1000,
            "self_recharge_enabled": True,
        }
    ]
    user = {"id": "teacher-1", "role": "teacher"}

    await token_service.record_usage(user, "branch-1", 40, "personal_topup", conversation_id="conv-1")
    await token_service.record_usage(user, "branch-1", 50, "plan", conversation_id="conv-2")

    assert len(token_db.token_usage.docs) == 2
    assert token_db.token_balances.docs[0]["personal_topups"]["teacher-1"] == 460
    warning = token_db.token_balances.docs[0]["warnings"]["teacher-1"]
    assert warning["total_used"] == 90
    assert warning["usage_ratio"] == 0.9


@pytest.mark.asyncio
async def test_record_usage_personal_topup_floors_at_zero(token_db):
    """R15.1 (P-L6): a debit larger than the remaining balance clamps at 0.

    Before the fix `$inc: -tokens_used` could drive the balance negative (a
    single big turn or a burst of concurrent turns). The atomic `$max`-clamp
    pipeline guarantees the personal top-up never goes below zero.
    """
    token_db.token_balances.docs[:] = [
        {
            "branch_id": "branch-1",
            "role_limits": {"teacher": 100},
            "personal_topups": {"teacher-1": 30},
            "school_topup_pool": 1000,
            "self_recharge_enabled": True,
        }
    ]
    user = {"id": "teacher-1", "role": "teacher"}

    # Debit 200 against a 30-token balance — must floor at 0, never -170.
    await token_service.record_usage(user, "branch-1", 200, "personal_topup", conversation_id="c1")

    assert token_db.token_balances.docs[0]["personal_topups"]["teacher-1"] == 0

    # A subsequent debit stays at 0 (idempotent floor, no drift into negatives).
    await token_service.record_usage(user, "branch-1", 75, "personal_topup", conversation_id="c2")
    assert token_db.token_balances.docs[0]["personal_topups"]["teacher-1"] == 0


@pytest.mark.asyncio
async def test_purchase_topup_is_idempotent_by_payment_id(token_db):
    first = await token_service.purchase_topup("branch-1", "teacher-1", "micro", "pay-1")
    duplicate = await token_service.purchase_topup("branch-1", "teacher-1", "micro", "pay-1")

    assert first["success"] is True
    assert first["tokens_added"] == token_service.PACKS["micro"]["tokens"]
    assert duplicate == {"success": False, "error": "Payment already processed."}
    assert token_db.token_balances.docs[0]["personal_topups"]["teacher-1"] == token_service.PACKS["micro"]["tokens"]
