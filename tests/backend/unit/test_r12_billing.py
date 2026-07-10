from __future__ import annotations
"""R12.2 + R12.3: Webhook tenant-correctness and atomic credit tests."""

import pytest
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


# ─── Fixtures ─────────────────────────────────────────────────────────────────

class _MultiSchoolRawDb:
    """Simulates two schools with separate branches."""
    def __init__(self):
        self.branches = FakeCollection([
            {"id": "branch-school-a", "schoolId": "school-a"},
            {"id": "branch-school-b", "schoolId": "school-b"},
        ])
        self.token_balances = FakeCollection([
            {"branch_id": "branch-school-a", "schoolId": "school-a", "personal_topups": {}, "school_topup_pool": 0, "subscription_id": "sub-a"},
            {"branch_id": "branch-school-b", "schoolId": "school-b", "personal_topups": {}, "school_topup_pool": 0, "subscription_id": "sub-b"},
        ])
        self.token_purchases = FakeCollection()


@pytest.fixture
def multi_school_db(monkeypatch):
    raw_db = _MultiSchoolRawDb()
    import services.razorpay_service as svc
    # Both get_db and get_raw_db return the same fake (no ScopedDatabase in tests).
    monkeypatch.setattr(svc, "get_db", lambda: raw_db)
    monkeypatch.setattr(svc, "get_raw_db", lambda: raw_db)
    return raw_db


# ─── R12.2 AC3: cross-tenant isolation ───────────────────────────────────────

async def test_payment_link_credits_school_b_not_school_a(multi_school_db):
    """Webhook with branch-school-b notes credits school-b balance, not school-a."""
    import services.razorpay_service as svc
    link = {
        "id": "plink-school-b-001",
        "status": "paid",
        "notes": {"branch_id": "branch-school-b", "user_id": "user-b", "pack_id": "basic"},
    }
    await svc.handle_payment_link_paid(link)

    school_b_bal = next(
        d for d in multi_school_db.token_balances.docs if d["branch_id"] == "branch-school-b"
    )
    school_a_bal = next(
        d for d in multi_school_db.token_balances.docs if d["branch_id"] == "branch-school-a"
    )
    assert school_b_bal["personal_topups"].get("user-b", 0) == 200_000
    assert school_a_bal["personal_topups"] == {}  # school-a untouched


async def test_payment_link_unresolvable_branch_rejected(multi_school_db):
    """R12.2 AC4: a webhook whose branch can't be resolved is logged and rejected."""
    import services.razorpay_service as svc
    link = {
        "id": "plink-ghost-branch",
        "status": "paid",
        "notes": {"branch_id": "branch-ghost", "user_id": "user-x", "pack_id": "basic"},
    }
    await svc.handle_payment_link_paid(link)
    # No purchase should have been recorded.
    assert multi_school_db.token_purchases.docs == []


# ─── R12.3 AC1: first-topup path conflict fix ────────────────────────────────

async def test_first_topup_for_new_branch_succeeds(monkeypatch):
    """R12.3 AC1: first top-up for a branch with no token_balances doc must not raise."""
    import services.razorpay_service as svc
    raw_db = _MultiSchoolRawDb()
    raw_db.token_balances.docs[:] = []  # No existing balance doc
    monkeypatch.setattr(svc, "get_db", lambda: raw_db)
    monkeypatch.setattr(svc, "get_raw_db", lambda: raw_db)

    link = {
        "id": "plink-new-branch",
        "status": "paid",
        "notes": {"branch_id": "branch-school-a", "user_id": "user-a", "pack_id": "basic"},
    }
    await svc.handle_payment_link_paid(link)

    assert len(raw_db.token_purchases.docs) == 1
    # A new balance doc should have been created via upsert.
    assert len(raw_db.token_balances.docs) == 1
    bal = raw_db.token_balances.docs[0]
    assert bal["personal_topups"]["user-a"] == 200_000


# ─── R12.3 AC2/AC3: idempotency after simulated failure ──────────────────────

async def test_topup_idempotent_on_replay(monkeypatch):
    """R12.3: replaying the same webhook doesn't double-credit."""
    import services.razorpay_service as svc

    class _Db:
        branches = FakeCollection([{"id": "branch-school-a", "schoolId": "school-a"}])
        token_balances = FakeCollection([
            {"branch_id": "branch-school-a", "schoolId": "school-a", "personal_topups": {"user-a": 200_000}, "school_topup_pool": 0},
        ])
        token_purchases = FakeCollection([
            {"razorpay_reference_id": "plink-replay", "branch_id": "branch-school-a"},
        ])

    db = _Db()
    monkeypatch.setattr(svc, "get_db", lambda: db)
    monkeypatch.setattr(svc, "get_raw_db", lambda: db)

    link = {
        "id": "plink-replay",
        "status": "paid",
        "notes": {"branch_id": "branch-school-a", "user_id": "user-a", "pack_id": "basic"},
    }
    await svc.handle_payment_link_paid(link)

    # Balance must NOT have been incremented again.
    assert db.token_balances.docs[0]["personal_topups"]["user-a"] == 200_000
    assert len(db.token_purchases.docs) == 1  # Still only one purchase record.


async def test_subscription_charged_cross_tenant_credits_correct_school(multi_school_db):
    """R12.2: subscription.charged credits school-b's subscription, not school-a's."""
    import services.razorpay_service as svc
    sub = {
        "id": "sub-b",
        "current_end": 1750000000,
        "notes": {"user_id": "user-b"},
    }
    # Ensure subscription_plan is set on the balance doc
    for doc in multi_school_db.token_balances.docs:
        if doc["branch_id"] == "branch-school-b":
            doc["subscription_plan"] = "monthly_growth"
            doc["subscription_user_id"] = "user-b"

    await svc.handle_subscription_charged(sub, "pay-school-b-renewal")

    school_b_bal = next(d for d in multi_school_db.token_balances.docs if d["branch_id"] == "branch-school-b")
    school_a_bal = next(d for d in multi_school_db.token_balances.docs if d["branch_id"] == "branch-school-a")
    assert school_b_bal["personal_topups"].get("user-b", 0) == 3_000_000
    assert school_a_bal["personal_topups"] == {}
