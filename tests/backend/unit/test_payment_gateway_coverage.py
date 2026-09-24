from __future__ import annotations

"""
Payment gateway + token budget coverage tests.

Covers the gaps identified after reviewing the existing
test_token_service_phase5.py and test_razorpay_checkout.py suites.

Three concern areas:
  A. Transaction creation (Razorpay API path, validation, failure)
  B. Token recharge (purchase crediting, subscription lifecycle, edge cases)
  C. AI reply blocked when limit is reached (chat route SSE behaviour)
"""

import json
import os
import sys

import pytest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_fake_key")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "rzp_test_fake_secret")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "whsec_test_fake_secret")
os.environ.setdefault("RAZORPAY_PLAN_MONTHLY_STARTER", "plan_test_starter")
os.environ.setdefault("RAZORPAY_PLAN_MONTHLY_GROWTH", "plan_test_growth")
os.environ.setdefault("RAZORPAY_PLAN_MONTHLY_ENTERPRISE", "plan_test_enterprise")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _bearer(payload: dict) -> dict:
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}


def _owner_headers(branch="branch-a"):
    return _bearer({"user_id": "owner-1", "role": "owner", "name": "Aman", "branch_id": branch})


def _teacher_headers():
    return _bearer({"user_id": "teacher-1", "role": "teacher", "name": "Ravi", "branch_id": "branch-a"})


def _student_headers():
    return _bearer({"user_id": "stu-1", "role": "student", "name": "Kid", "branch_id": "branch-a"})


FAKE_PAYMENT_LINK = {
    "id": "plink_test_abc123",
    "short_url": "https://rzp.io/i/abc123",
    "status": "created",
}
FAKE_SUBSCRIPTION = {
    "id": "sub_test_001",
    "short_url": "https://rzp.io/i/sub001",
    "status": "created",
}


class _FakePaymentLink:
    def __init__(self, raises=None):
        self._raises = raises

    def create(self, data):
        if self._raises:
            raise self._raises
        return FAKE_PAYMENT_LINK


class _FakeSubscription:
    def __init__(self, raises=None):
        self._raises = raises

    def create(self, data):
        if self._raises:
            raise self._raises
        return FAKE_SUBSCRIPTION


class FakeRazorpayClient:
    def __init__(self, link_raises=None, sub_raises=None):
        self.payment_link = _FakePaymentLink(raises=link_raises)
        self.subscription = _FakeSubscription(raises=sub_raises)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def token_db(monkeypatch):
    db = type(
        "TokenDb",
        (),
        {
            "token_balances": FakeCollection(),
            "token_usage": FakeCollection(),
            "token_purchases": FakeCollection(),
            "razorpay_webhook_inbox": FakeCollection(),
            "school_fee_checkouts": FakeCollection(),
            "fee_transactions": FakeCollection(),
            "branches": FakeCollection([{"id": "branch-a", "schoolId": "school-a"}]),
            "audit_logs": FakeCollection(),
        },
    )()
    import services.razorpay_service as svc
    monkeypatch.setattr(svc, "get_db", lambda: db)
    monkeypatch.setattr(svc, "get_raw_db", lambda: db)
    monkeypatch.setattr(svc, "_razorpay_client", lambda: FakeRazorpayClient())
    import routes.tokens as tok_routes
    monkeypatch.setattr(tok_routes, "get_db", lambda: db, raising=False)
    import services.token_service as ts
    monkeypatch.setattr(ts, "get_db", lambda: db)
    return db


@pytest.fixture
def app_client(token_db):
    from routes.tokens import router as tokens_router
    mini = FastAPI()
    mini.include_router(tokens_router)
    return TestClient(mini, raise_server_exceptions=False)


@pytest.fixture(autouse=False)
def clean_db(token_db):
    for col in ("token_balances", "token_purchases", "token_usage",
                "razorpay_webhook_inbox", "school_fee_checkouts", "fee_transactions"):
        getattr(token_db, col).docs[:] = []
    yield
    for col in ("token_balances", "token_purchases", "token_usage",
                "razorpay_webhook_inbox", "school_fee_checkouts", "fee_transactions"):
        getattr(token_db, col).docs[:] = []


# ══════════════════════════════════════════════════════════════════════════════
# A. TRANSACTION CREATION
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckoutSessionValidation:
    """Route-level validation before the Razorpay API is called."""

    def test_http_success_url_rejected_400(self, app_client, clean_db):
        """success_url with http:// (not https://) must be rejected before calling Razorpay."""
        resp = app_client.post(
            "/api/tokens/create-checkout-session",
            json={"pack_id": "basic", "success_url": "http://not-secure.example.com"},
            headers=_owner_headers(),
        )
        assert resp.status_code == 400
        assert "HTTPS" in resp.json()["detail"]

    def test_http_cancel_url_rejected_400(self, app_client, clean_db):
        resp = app_client.post(
            "/api/tokens/create-checkout-session",
            json={"pack_id": "basic", "cancel_url": "http://not-secure.example.com"},
            headers=_owner_headers(),
        )
        assert resp.status_code == 400
        assert "HTTPS" in resp.json()["detail"]

    def test_missing_pack_id_returns_400(self, app_client, clean_db):
        resp = app_client.post(
            "/api/tokens/create-checkout-session",
            json={},
            headers=_owner_headers(),
        )
        assert resp.status_code == 400
        assert "pack_id" in resp.json()["detail"]

    def test_missing_plan_id_returns_400(self, app_client, clean_db):
        resp = app_client.post(
            "/api/tokens/create-subscription-session",
            json={},
            headers=_owner_headers(),
        )
        assert resp.status_code == 400
        assert "plan_id" in resp.json()["detail"]

    def test_teacher_can_purchase_pack(self, app_client, clean_db):
        """Teachers are in the allowed-purchaser role list."""
        resp = app_client.post(
            "/api/tokens/create-checkout-session",
            json={"pack_id": "micro"},
            headers=_teacher_headers(),
        )
        assert resp.status_code == 200

    def test_admin_can_purchase_pack(self, app_client, clean_db):
        admin_headers = _bearer({"user_id": "admin-1", "role": "admin", "name": "Adesh", "branch_id": "branch-a"})
        resp = app_client.post(
            "/api/tokens/create-checkout-session",
            json={"pack_id": "micro"},
            headers=admin_headers,
        )
        assert resp.status_code == 200


class TestCheckoutSessionRazorpayFailure:
    """What the route returns when the Razorpay SDK itself throws."""

    def test_checkout_session_razorpay_api_failure_returns_500(self, token_db, monkeypatch, clean_db):
        import services.razorpay_service as svc
        monkeypatch.setattr(
            svc, "_razorpay_client",
            lambda: FakeRazorpayClient(link_raises=RuntimeError("Razorpay down"))
        )
        from routes.tokens import router as tokens_router
        mini = FastAPI()
        mini.include_router(tokens_router)
        client = TestClient(mini, raise_server_exceptions=False)

        resp = client.post(
            "/api/tokens/create-checkout-session",
            json={"pack_id": "basic"},
            headers=_owner_headers(),
        )
        assert resp.status_code == 500

    def test_subscription_session_razorpay_api_failure_returns_500(self, token_db, monkeypatch, clean_db):
        import services.razorpay_service as svc
        monkeypatch.setattr(
            svc, "_razorpay_client",
            lambda: FakeRazorpayClient(sub_raises=RuntimeError("Razorpay down"))
        )
        from routes.tokens import router as tokens_router
        mini = FastAPI()
        mini.include_router(tokens_router)
        client = TestClient(mini, raise_server_exceptions=False)

        resp = client.post(
            "/api/tokens/create-subscription-session",
            json={"plan_id": "monthly_starter"},
            headers=_owner_headers(),
        )
        assert resp.status_code == 500


class TestSchoolFeeCheckout:
    """create_school_fee_checkout error paths."""

    async def test_checkout_fails_when_transaction_id_not_found(self, token_db, monkeypatch):
        """If any transaction_id doesn't exist in the DB, ValueError is raised."""
        import services.razorpay_service as svc
        with pytest.raises(ValueError, match="not found"):
            await svc.create_school_fee_checkout(
                token_db,
                school_id="school-a",
                branch_id="branch-a",
                user_id="owner-1",
                transaction_ids=["nonexistent-txn-id"],
            )

    async def test_checkout_fails_when_empty_transaction_list(self, token_db, monkeypatch):
        import services.razorpay_service as svc
        with pytest.raises(ValueError):
            await svc.create_school_fee_checkout(
                token_db,
                school_id="school-a",
                branch_id="branch-a",
                user_id="owner-1",
                transaction_ids=[],
            )

    async def test_checkout_fails_when_all_transactions_already_paid(self, token_db, monkeypatch):
        """A checkout where every selected fee is already paid has zero outstanding balance."""
        token_db.fee_transactions.docs[:] = [
            {"id": "fee-paid", "schoolId": "school-a", "branch_id": "branch-a",
             "amount": 500, "status": "paid"},
        ]
        import services.razorpay_service as svc
        with pytest.raises(ValueError, match="no outstanding balance"):
            await svc.create_school_fee_checkout(
                token_db,
                school_id="school-a",
                branch_id="branch-a",
                user_id="owner-1",
                transaction_ids=["fee-paid"],
            )

    async def test_checkout_deduplicates_transaction_ids(self, token_db, monkeypatch):
        """Duplicate transaction IDs in the input are de-duped before the Razorpay call."""
        token_db.fee_transactions.docs[:] = [
            {"id": "fee-1", "schoolId": "school-a", "branch_id": "branch-a",
             "amount": 300, "status": "pending"},
        ]
        import services.razorpay_service as svc
        doc = await svc.create_school_fee_checkout(
            token_db,
            school_id="school-a",
            branch_id="branch-a",
            user_id="owner-1",
            transaction_ids=["fee-1", "fee-1", "fee-1"],
        )
        assert doc["transaction_ids"] == ["fee-1"]


# ══════════════════════════════════════════════════════════════════════════════
# B. TOKEN RECHARGE
# ══════════════════════════════════════════════════════════════════════════════

class TestPurchaseTopupAccumulation:
    """Multiple purchases must add up, not replace."""

    async def test_two_purchases_accumulate_for_same_user(self, token_db):
        from services import token_service
        first = await token_service.purchase_topup("branch-a", "user-1", "micro", "pay-aaa")
        second = await token_service.purchase_topup("branch-a", "user-1", "micro", "pay-bbb")

        assert first["success"] is True
        assert second["success"] is True
        balance = token_db.token_balances.docs[0]["personal_topups"]["user-1"]
        expected = token_service.PACKS["micro"]["tokens"] * 2
        assert balance == expected

    async def test_two_users_each_get_their_own_balance(self, token_db):
        from services import token_service
        await token_service.purchase_topup("branch-a", "user-A", "basic", "pay-u1")
        await token_service.purchase_topup("branch-a", "user-B", "micro", "pay-u2")

        topups = token_db.token_balances.docs[0]["personal_topups"]
        assert topups["user-A"] == token_service.PACKS["basic"]["tokens"]
        assert topups["user-B"] == token_service.PACKS["micro"]["tokens"]

    async def test_purchase_creates_balance_doc_when_none_exists(self, token_db):
        """upsert=True must create the token_balances doc if the branch is new."""
        from services import token_service
        assert token_db.token_balances.docs == []

        result = await token_service.purchase_topup("new-branch", "user-1", "standard", "pay-new")
        assert result["success"] is True
        assert len(token_db.token_balances.docs) == 1
        assert token_db.token_balances.docs[0]["branch_id"] == "new-branch"

    async def test_purchase_with_unknown_pack_id_fails_gracefully(self, token_db):
        from services import token_service
        result = await token_service.purchase_topup("branch-a", "user-1", "nonexistent_pack", "pay-x")
        assert result["success"] is False
        assert "Unknown pack" in result["error"]
        assert token_db.token_purchases.docs == []


class TestRecordUsageSchoolPool:
    """school_topup pool is decremented when source='school_topup'."""

    async def test_school_topup_pool_decremented_on_usage(self, token_db):
        from services import token_service
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"teacher": 100},
                "school_topup_pool": 1000,
                "personal_topups": {},
            }
        ]
        user = {"id": "teacher-1", "role": "teacher"}
        await token_service.record_usage(user, "branch-a", 300, "school_topup")

        assert token_db.token_balances.docs[0]["school_topup_pool"] == 700

    async def test_plan_usage_does_not_touch_school_pool(self, token_db):
        """Plan usage is tracked only in token_usage; the pool must not change."""
        from services import token_service
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"teacher": 1_000_000},
                "school_topup_pool": 500,
                "personal_topups": {},
            }
        ]
        user = {"id": "teacher-1", "role": "teacher"}
        await token_service.record_usage(user, "branch-a", 100, "plan")

        assert token_db.token_balances.docs[0]["school_topup_pool"] == 500

    async def test_zero_tokens_used_is_a_noop(self, token_db):
        from services import token_service
        token_db.token_balances.docs[:] = [
            {"branch_id": "branch-a", "school_topup_pool": 200, "personal_topups": {}}
        ]
        user = {"id": "u1", "role": "teacher"}
        await token_service.record_usage(user, "branch-a", 0, "school_topup")

        assert token_db.token_usage.docs == []
        assert token_db.token_balances.docs[0]["school_topup_pool"] == 200


class TestSubcategoryLimitOverride:
    """Sub-category limits override role limits when both are defined."""

    async def test_principal_uses_subcategory_limit_not_admin_role_limit(self, token_db):
        from services import token_service
        month = token_service._current_month_key()
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"admin": 100},
                "sub_category_limits": {"principal": 5_000},
                "personal_topups": {},
                "school_topup_pool": 0,
                "self_recharge_enabled": False,
            }
        ]
        token_db.token_usage.docs[:] = [
            {"branch_id": "branch-a", "user_id": "p-1", "month": month, "tokens_used": 200}
        ]
        principal = {"id": "p-1", "role": "admin", "sub_category": "principal"}

        result = await token_service.check_and_reserve_tokens(principal, "branch-a", estimated_tokens=500)

        # Principal limit is 5,000 and only 200 used → allowed from plan
        assert result["allowed"] is True
        assert result["source"] == "plan"

    async def test_admin_without_subcategory_uses_role_limit(self, token_db):
        from services import token_service
        month = token_service._current_month_key()
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"admin": 100},
                "sub_category_limits": {"principal": 5_000},
                "personal_topups": {},
                "school_topup_pool": 0,
                "self_recharge_enabled": False,
            }
        ]
        token_db.token_usage.docs[:] = [
            {"branch_id": "branch-a", "user_id": "admin-2", "month": month, "tokens_used": 90}
        ]
        plain_admin = {"id": "admin-2", "role": "admin"}

        result = await token_service.check_and_reserve_tokens(plain_admin, "branch-a", estimated_tokens=50)

        # Admin limit is 100, used 90, asking for 50 → exhausted
        assert result["allowed"] is False


class TestUpdateRoleLimits:
    """update_role_limits validation."""

    async def test_invalid_role_name_returns_error(self, token_db):
        from services import token_service
        result = await token_service.update_role_limits("branch-a", {"ghost": 1000})
        assert result["success"] is False
        assert "ghost" in result["error"]

    async def test_non_integer_limit_returns_error(self, token_db):
        from services import token_service
        result = await token_service.update_role_limits("branch-a", {"teacher": "lots"})
        assert result["success"] is False
        assert "teacher" in result["error"]

    async def test_partial_update_preserves_other_roles(self, token_db):
        from services import token_service
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"owner": 500_000, "admin": 300_000, "teacher": 100_000, "student": 50_000},
            }
        ]
        result = await token_service.update_role_limits("branch-a", {"teacher": 200_000})
        assert result["success"] is True
        limits = result["role_limits"]
        assert limits["teacher"] == 200_000
        assert limits["owner"] == 500_000  # untouched
        assert limits["admin"] == 300_000  # untouched

    async def test_unlimited_minus_one_is_accepted(self, token_db):
        from services import token_service
        result = await token_service.update_role_limits("branch-a", {"owner": -1})
        assert result["success"] is True
        assert result["role_limits"]["owner"] == -1


class TestSubscriptionLifecycle:
    """Subscription activation with unknown plan and other edge cases."""

    async def test_subscription_activated_unknown_plan_stores_plan_id_as_given(self, token_db, monkeypatch):
        """An unknown plan_id is stored as-is; it does not crash or silently drop."""
        import services.razorpay_service as svc
        sub = {
            "id": "sub-unknown-plan",
            "status": "active",
            "customer_id": "cust-1",
            "current_end": 1750000000,
            "notes": {"branch_id": "branch-a", "plan_id": "mystery_plan"},
        }
        await svc.handle_subscription_activated(sub)

        assert len(token_db.token_balances.docs) == 1
        assert token_db.token_balances.docs[0]["subscription_plan"] == "mystery_plan"

    async def test_subscription_activated_missing_branch_id_is_skipped(self, token_db):
        """A subscription with no branch_id in notes must not write anything."""
        import services.razorpay_service as svc
        sub = {
            "id": "sub-no-branch",
            "status": "active",
            "notes": {},
        }
        await svc.handle_subscription_activated(sub)
        assert token_db.token_balances.docs == []

    async def test_payment_link_paid_missing_notes_fields_skipped(self, token_db):
        """A paid link with incomplete notes (e.g. no user_id) must not crash."""
        import services.razorpay_service as svc
        link = {
            "id": "plink-incomplete",
            "status": "paid",
            "notes": {"branch_id": "branch-a"},  # user_id and pack_id missing
        }
        await svc.handle_payment_link_paid(link)
        assert token_db.token_purchases.docs == []
        assert token_db.token_balances.docs == []

    async def test_payment_link_paid_unknown_pack_id_skipped(self, token_db):
        """A paid link referencing a pack that no longer exists must not crash."""
        import services.razorpay_service as svc
        link = {
            "id": "plink-bad-pack",
            "status": "paid",
            "notes": {"branch_id": "branch-a", "user_id": "u1", "pack_id": "discontinued_pack"},
        }
        await svc.handle_payment_link_paid(link)
        assert token_db.token_purchases.docs == []

    async def test_subscription_charged_credits_personal_topup_for_subscriber(self, token_db):
        """Subscription renewal credits go to the subscribing user's personal balance."""
        import services.razorpay_service as svc
        from services.razorpay_service import SUBSCRIPTION_PLANS
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "school_topup_pool": 100,
                "personal_topups": {},
                "subscription_id": "sub-r1",
                "subscription_plan": "monthly_starter",
            }
        ]
        sub = {"id": "sub-r1", "current_end": 1750000000, "notes": {"user_id": "owner-1"}}
        await svc.handle_subscription_charged(sub, "pay-renewal-x")

        expected = SUBSCRIPTION_PLANS["monthly_starter"]["tokens_per_month"]
        assert token_db.token_balances.docs[0]["personal_topups"]["owner-1"] == expected
        # School pool must be untouched
        assert token_db.token_balances.docs[0]["school_topup_pool"] == 100


# ══════════════════════════════════════════════════════════════════════════════
# C. AI REPLY BLOCKED WHEN LIMIT IS REACHED
# ══════════════════════════════════════════════════════════════════════════════

# Helper: collect all SSE events from a streaming response body.
def _collect_sse_events(body: bytes) -> list[dict]:
    events = []
    for line in body.decode().splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


@pytest.fixture
def chat_db(monkeypatch):
    """Minimal DB wiring for the chat route token-budget tests."""
    import routes.chat as chat
    import services.token_service as ts

    db = type(
        "ChatDb",
        (),
        {
            "conversations": FakeCollection([
                {"id": "conv-1", "user_id": "owner-1", "schoolId": "aaryans-joya",
                 "branch_id": "branch-a", "title": "Test"}
            ]),
            "messages": FakeCollection(),
            "token_balances": FakeCollection(),
            "token_usage": FakeCollection(),
            "token_purchases": FakeCollection(),
        },
    )()
    monkeypatch.setattr(chat, "get_db", lambda: db)
    monkeypatch.setattr(ts, "get_db", lambda: db)
    return db


@pytest.fixture
def chat_client(chat_db):
    # The chat router already carries the /api/chat prefix in every route path.
    # Mount it on a plain app and hit the full paths as declared.
    import routes.chat as chat
    mini = FastAPI()
    mini.include_router(chat.router, prefix="")
    return TestClient(mini, raise_server_exceptions=False)


# Canonical URL for the messages endpoint used by all chat tests.
_MESSAGES_URL = "/api/chat/conversations/conv-1/messages"


class TestChatRouteTokenBudget:
    """Verify the SSE events emitted when the token budget is exhausted."""

    def test_exhausted_budget_blocks_ai_reply_and_emits_done(self, chat_client, chat_db, monkeypatch):
        """When check_and_reserve_tokens returns allowed=False, the route emits
        text_delta with the error message and then done — no LLM call."""
        import routes.chat as chat  # patch where the name is used, not where it's defined

        async def _exhausted(user, branch_id, estimated_tokens=2000):
            return {
                "allowed": False,
                "source": "exhausted",
                "message": "Your monthly AI token limit has been reached.",
                "can_recharge": False,
            }

        monkeypatch.setattr(chat, "check_and_reserve_tokens", _exhausted)

        headers = _owner_headers()
        resp = chat_client.post(
            _MESSAGES_URL,
            json={"text": "hello", "session_id": "sess-1"},
            headers=headers,
        )
        assert resp.status_code == 200
        events = _collect_sse_events(resp.content)
        types = [e.get("type") for e in events]
        assert "text_delta" in types
        assert "done" in types
        # No token_exhausted event because can_recharge=False
        assert "token_exhausted" not in types

    def test_exhausted_with_recharge_emits_token_exhausted_event(self, chat_client, chat_db, monkeypatch):
        """When can_recharge=True the route also emits a token_exhausted event
        so the frontend can show the upgrade modal."""
        import routes.chat as chat

        async def _exhausted_rechargeable(user, branch_id, estimated_tokens=2000):
            return {
                "allowed": False,
                "source": "exhausted",
                "message": "Limit reached. You can purchase a top-up pack.",
                "can_recharge": True,
            }

        monkeypatch.setattr(chat, "check_and_reserve_tokens", _exhausted_rechargeable)

        headers = _owner_headers()
        resp = chat_client.post(
            _MESSAGES_URL,
            json={"text": "hello", "session_id": "sess-2"},
            headers=headers,
        )
        assert resp.status_code == 200
        events = _collect_sse_events(resp.content)
        types = [e.get("type") for e in events]
        assert "token_exhausted" in types
        token_event = next(e for e in events if e.get("type") == "token_exhausted")
        assert token_event["can_recharge"] is True

    def test_budget_check_failure_falls_open_and_allows_call(self, chat_client, chat_db, monkeypatch):
        """If check_and_reserve_tokens raises, the chat route must NOT block the
        call — it falls open so a budget-service outage never silences Flo."""
        import services.token_service as ts

        async def _boom(user, branch_id, estimated_tokens=2000):
            raise RuntimeError("DB connection lost")

        monkeypatch.setattr(ts, "check_and_reserve_tokens", _boom)

        # Also stub the LLM so we don't need real credentials
        import routes.chat as chat

        async def _fake_llm_gen(*args, **kwargs):
            yield f"data: {json.dumps({'type': 'text_delta', 'delta': 'hi'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        monkeypatch.setattr(chat, "_generate_chat_sse", _fake_llm_gen)

        headers = _owner_headers()
        resp = chat_client.post(
            _MESSAGES_URL,
            json={"text": "hello", "session_id": "sess-3"},
            headers=headers,
        )
        # The call must reach the LLM path, not terminate with a budget error.
        # A 200 streaming response (even if short) proves it was not blocked.
        assert resp.status_code == 200
        events = _collect_sse_events(resp.content)
        types = [e.get("type") for e in events]
        assert "text_delta" in types

    def test_allowed_budget_does_not_emit_exhausted_events(self, chat_client, chat_db, monkeypatch):
        """When check_and_reserve_tokens returns allowed=True, the route must not
        emit any token_exhausted or budget-related error events."""
        import services.token_service as ts

        async def _allowed(user, branch_id, estimated_tokens=2000):
            return {"allowed": True, "source": "plan", "message": "500,000 tokens remaining.", "can_recharge": False}

        monkeypatch.setattr(ts, "check_and_reserve_tokens", _allowed)

        import routes.chat as chat

        async def _fake_llm_gen(*args, **kwargs):
            yield f"data: {json.dumps({'type': 'text_delta', 'delta': 'ok'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        monkeypatch.setattr(chat, "_generate_chat_sse", _fake_llm_gen)

        headers = _owner_headers()
        resp = chat_client.post(
            _MESSAGES_URL,
            json={"text": "hello", "session_id": "sess-4"},
            headers=headers,
        )
        assert resp.status_code == 200
        events = _collect_sse_events(resp.content)
        types = [e.get("type") for e in events]
        assert "token_exhausted" not in types


class TestCheckAndReserveEdgeCases:
    """Edge cases in the priority-chain logic."""

    async def test_exactly_at_limit_is_exhausted(self, token_db):
        """Used == limit with no top-up pools → exhausted, not allowed."""
        from services import token_service
        month = token_service._current_month_key()
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"teacher": 1000},
                "personal_topups": {},
                "school_topup_pool": 0,
                "self_recharge_enabled": True,
            }
        ]
        token_db.token_usage.docs[:] = [
            {"branch_id": "branch-a", "user_id": "t1", "month": month, "tokens_used": 1000}
        ]
        user = {"id": "t1", "role": "teacher"}
        result = await token_service.check_and_reserve_tokens(user, "branch-a", estimated_tokens=1)

        assert result["allowed"] is False
        assert result["source"] == "exhausted"

    async def test_estimated_tokens_larger_than_remaining_plan_falls_to_personal(self, token_db):
        """Remaining plan tokens < estimated_tokens → skip plan, check personal top-up."""
        from services import token_service
        month = token_service._current_month_key()
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"teacher": 100},
                "personal_topups": {"t1": 2000},
                "school_topup_pool": 0,
                "self_recharge_enabled": True,
            }
        ]
        token_db.token_usage.docs[:] = [
            {"branch_id": "branch-a", "user_id": "t1", "month": month, "tokens_used": 95}
        ]
        user = {"id": "t1", "role": "teacher"}
        result = await token_service.check_and_reserve_tokens(user, "branch-a", estimated_tokens=50)

        # Plan has only 5 left (100-95), estimated is 50 → falls to personal top-up
        assert result["allowed"] is True
        assert result["source"] == "personal_topup"

    async def test_self_recharge_disabled_exhausted_says_contact_admin(self, token_db):
        from services import token_service
        month = token_service._current_month_key()
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"teacher": 100},
                "personal_topups": {},
                "school_topup_pool": 0,
                "self_recharge_enabled": False,
            }
        ]
        token_db.token_usage.docs[:] = [
            {"branch_id": "branch-a", "user_id": "t1", "month": month, "tokens_used": 100}
        ]
        user = {"id": "t1", "role": "teacher"}
        result = await token_service.check_and_reserve_tokens(user, "branch-a", estimated_tokens=10)

        assert result["allowed"] is False
        assert result["can_recharge"] is False
        assert "administrator" in result["message"]

    async def test_warning_not_set_below_80_percent(self, token_db):
        """The 80% warning flag must NOT fire below the threshold."""
        from services import token_service
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"teacher": 1000},
                "personal_topups": {},
                "school_topup_pool": 0,
            }
        ]
        user = {"id": "t1", "role": "teacher"}
        await token_service.record_usage(user, "branch-a", 750, "plan")

        warnings = token_db.token_balances.docs[0].get("warnings", {})
        assert "t1" not in warnings

    async def test_warning_is_set_at_80_percent_exactly(self, token_db):
        from services import token_service
        token_db.token_balances.docs[:] = [
            {
                "branch_id": "branch-a",
                "role_limits": {"teacher": 1000},
                "personal_topups": {},
                "school_topup_pool": 0,
            }
        ]
        user = {"id": "t1", "role": "teacher"}
        await token_service.record_usage(user, "branch-a", 800, "plan")

        warnings = token_db.token_balances.docs[0].get("warnings", {})
        assert "t1" in warnings
        assert warnings["t1"]["usage_ratio"] >= 0.80
