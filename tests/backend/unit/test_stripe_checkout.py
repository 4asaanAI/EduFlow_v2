from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake_key_for_tests")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_fake_secret")
os.environ.setdefault("STRIPE_PRICE_MONTHLY_SCHOOL_STARTER", "price_test_starter")
os.environ.setdefault("STRIPE_PRICE_MONTHLY_SCHOOL_PRO", "price_test_pro")

pytestmark = pytest.mark.asyncio

from fastapi.testclient import TestClient

import stripe as stripe_lib
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _bearer(payload: dict) -> dict:
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}


def _owner_headers():
    return _bearer({"user_id": "owner-1", "role": "owner", "name": "Aman", "branch_id": "branch-a"})


def _admin_headers():
    return _bearer({"user_id": "admin-1", "role": "admin", "name": "Adesh", "branch_id": "branch-a"})


# ─── Fake Stripe objects ──────────────────────────────────────────────────────

class FakeStripeSession:
    id = "cs_test_abc123"
    url = "https://checkout.stripe.com/pay/cs_test_abc123"


def _make_stripe_event(event_type: str, data_obj: dict):
    """Build a minimal Stripe event-like object for webhook testing."""
    return type(
        "StripeEvent",
        (),
        {
            "type": event_type,
            "data": type("D", (), {"object": data_obj})(),
        },
    )()


# ─── Fixtures ────────────────────────────────────────────────────────────────

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
    import services.stripe_service as svc
    monkeypatch.setattr(svc, "get_db", lambda: db)
    import routes.tokens as tok_routes
    monkeypatch.setattr(tok_routes, "get_db", lambda: db, raising=False)
    return db


@pytest.fixture
def mock_stripe_session(monkeypatch):
    monkeypatch.setattr(
        "stripe.checkout.Session.create",
        lambda **kw: FakeStripeSession(),
    )
    return FakeStripeSession()


@pytest.fixture
def app_client(token_db, mock_stripe_session):
    """Spin up a minimal FastAPI app with the tokens router attached."""
    from fastapi import FastAPI
    from routes.tokens import router as tokens_router

    mini = FastAPI()
    mini.include_router(tokens_router)
    return TestClient(mini, raise_server_exceptions=False)


@pytest.fixture
def autouse_clean(token_db):
    token_db.token_balances.docs[:] = []
    token_db.token_purchases.docs[:] = []
    token_db.token_usage.docs[:] = []
    yield
    token_db.token_balances.docs[:] = []
    token_db.token_purchases.docs[:] = []
    token_db.token_usage.docs[:] = []


# ─── AC1: Stripe one-time checkout session ────────────────────────────────────

def test_create_checkout_session_owner_success(app_client, autouse_clean):
    """Owner + valid pack → 200 with checkout_url and session_id."""
    resp = app_client.post(
        "/api/tokens/create-checkout-session",
        json={"pack_id": "basic", "success_url": "https://app.test?recharge=success", "cancel_url": "https://app.test?recharge=cancel"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["checkout_url"] == FakeStripeSession.url
    assert data["data"]["session_id"] == FakeStripeSession.id


def test_create_checkout_session_unauthenticated_401(app_client, autouse_clean):
    """No JWT → 401."""
    resp = app_client.post(
        "/api/tokens/create-checkout-session",
        json={"pack_id": "basic"},
    )
    assert resp.status_code == 401


def test_create_checkout_session_wrong_role_403(app_client, autouse_clean):
    """Admin (non-owner) → 403."""
    resp = app_client.post(
        "/api/tokens/create-checkout-session",
        json={"pack_id": "basic"},
        headers=_admin_headers(),
    )
    assert resp.status_code == 403


def test_create_checkout_session_unknown_pack_400(app_client, autouse_clean):
    """Unknown pack_id → 400."""
    resp = app_client.post(
        "/api/tokens/create-checkout-session",
        json={"pack_id": "nonexistent_pack"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 400


# ─── AC2: Stripe subscription checkout session ────────────────────────────────

def test_create_subscription_session_owner_success(app_client, autouse_clean):
    """Owner + valid plan_id → 200 with checkout_url."""
    resp = app_client.post(
        "/api/tokens/create-subscription-session",
        json={"plan_id": "monthly_school_starter", "success_url": "https://app.test?recharge=success", "cancel_url": "https://app.test?recharge=cancel"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "checkout_url" in data["data"]


def test_create_subscription_session_unauthenticated_401(app_client, autouse_clean):
    """No JWT → 401."""
    resp = app_client.post(
        "/api/tokens/create-subscription-session",
        json={"plan_id": "monthly_school_starter"},
    )
    assert resp.status_code == 401


def test_create_subscription_session_unknown_plan_400(app_client, autouse_clean):
    """Unknown plan_id → 400."""
    resp = app_client.post(
        "/api/tokens/create-subscription-session",
        json={"plan_id": "nonexistent_plan"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 400


# ─── AC3 + AC4: Webhook — checkout.session.completed ────────────────────────

async def test_webhook_checkout_completed_credits_tokens(token_db, monkeypatch):
    """Valid checkout.session.completed → school_topup_pool credited + purchase recorded."""
    token_db.token_balances.docs[:] = [
        {"branch_id": "branch-a", "school_topup_pool": 0, "role_limits": {}}
    ]

    session_obj = {
        "id": "cs_unique_session_1",
        "payment_status": "paid",
        "mode": "payment",
        "metadata": {"branch_id": "branch-a", "user_id": "owner-1", "pack_id": "basic"},
    }

    import services.stripe_service as svc
    await svc.handle_checkout_completed(session_obj)

    balance = token_db.token_balances.docs[0]
    assert balance["school_topup_pool"] == 200_000

    assert len(token_db.token_purchases.docs) == 1
    purchase = token_db.token_purchases.docs[0]
    assert purchase["stripe_session_id"] == "cs_unique_session_1"
    assert purchase["payment_provider"] == "stripe"
    assert purchase["payment_id"] is None


async def test_webhook_checkout_completed_idempotent(token_db, monkeypatch):
    """Session already in DB → tokens NOT double-credited."""
    token_db.token_balances.docs[:] = [
        {"branch_id": "branch-a", "school_topup_pool": 200_000, "role_limits": {}}
    ]
    token_db.token_purchases.docs[:] = [
        {"stripe_session_id": "cs_already_processed", "payment_provider": "stripe"}
    ]

    session_obj = {
        "id": "cs_already_processed",
        "payment_status": "paid",
        "mode": "payment",
        "metadata": {"branch_id": "branch-a", "user_id": "owner-1", "pack_id": "basic"},
    }

    import services.stripe_service as svc
    await svc.handle_checkout_completed(session_obj)

    balance = token_db.token_balances.docs[0]
    assert balance["school_topup_pool"] == 200_000
    assert len(token_db.token_purchases.docs) == 1


# ─── AC3: Webhook — invalid signature ────────────────────────────────────────

def test_webhook_invalid_signature_400(token_db, monkeypatch):
    """Invalid/missing Stripe-Signature → 400."""
    import stripe

    def _raise_sig_error(body, sig, secret):
        raise stripe.error.SignatureVerificationError("bad sig", "bad_header")

    monkeypatch.setattr("stripe.Webhook.construct_event", _raise_sig_error)

    from fastapi import FastAPI
    from routes.tokens import router as tokens_router

    mini = FastAPI()
    mini.include_router(tokens_router)
    client = TestClient(mini, raise_server_exceptions=False)

    resp = client.post(
        "/api/tokens/webhook",
        content=b'{"type":"checkout.session.completed"}',
        headers={"stripe-signature": "bad_sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


# ─── AC3: Webhook — subscription created ─────────────────────────────────────

async def test_webhook_subscription_created_updates_balance(token_db, monkeypatch):
    """customer.subscription.created → subscription fields stored on token_balances."""
    token_db.token_balances.docs[:] = []

    sub_obj = {
        "id": "sub_test_001",
        "status": "active",
        "customer": "cus_test_001",
        "current_period_end": 1750000000,
        "metadata": {"branch_id": "branch-a", "plan_id": "monthly_school_starter"},
    }

    import services.stripe_service as svc
    await svc.handle_subscription_created(sub_obj)

    assert len(token_db.token_balances.docs) == 1
    doc = token_db.token_balances.docs[0]
    assert doc["subscription_id"] == "sub_test_001"
    assert doc["subscription_status"] == "active"
    assert doc["subscription_plan"] == "monthly_school_starter"
    assert doc["stripe_customer_id"] == "cus_test_001"
    assert doc["subscription_current_period_end"] is not None


# ─── AC3: Webhook — invoice.payment_succeeded ────────────────────────────────

async def test_webhook_invoice_payment_succeeded_credits_pool(token_db, monkeypatch):
    """Subscription renewal invoice → school_topup_pool credited."""
    token_db.token_balances.docs[:] = [
        {
            "branch_id": "branch-a",
            "school_topup_pool": 500_000,
            "subscription_id": "sub_test_001",
            "subscription_plan": "monthly_school_starter",
        }
    ]

    invoice_obj = {
        "id": "in_test_001",
        "subscription": "sub_test_001",
        "billing_reason": "subscription_cycle",
        "lines": {"data": []},
    }

    import services.stripe_service as svc
    await svc.handle_invoice_payment_succeeded(invoice_obj)

    balance = token_db.token_balances.docs[0]
    assert balance["school_topup_pool"] == 500_000 + 2_000_000

    assert any(p["stripe_session_id"] == "invoice_in_test_001" for p in token_db.token_purchases.docs)


async def test_webhook_invoice_not_renewal_skipped(token_db, monkeypatch):
    """invoice with billing_reason != subscription_cycle → no credits."""
    token_db.token_balances.docs[:] = [
        {"branch_id": "branch-a", "school_topup_pool": 100_000, "subscription_id": "sub_x", "subscription_plan": "monthly_school_starter"}
    ]
    invoice_obj = {
        "id": "in_initial",
        "subscription": "sub_x",
        "billing_reason": "subscription_create",
        "lines": {"data": []},
    }

    import services.stripe_service as svc
    await svc.handle_invoice_payment_succeeded(invoice_obj)

    assert token_db.token_balances.docs[0]["school_topup_pool"] == 100_000
    assert len(token_db.token_purchases.docs) == 0


# ─── AC3: Webhook — subscription deleted ─────────────────────────────────────

async def test_webhook_subscription_deleted_marks_canceled(token_db, monkeypatch):
    """customer.subscription.deleted → subscription_status=canceled."""
    token_db.token_balances.docs[:] = [
        {
            "branch_id": "branch-a",
            "subscription_id": "sub_del_001",
            "subscription_status": "active",
        }
    ]

    sub_obj = {
        "id": "sub_del_001",
        "metadata": {"branch_id": "branch-a"},
    }

    import services.stripe_service as svc
    await svc.handle_subscription_deleted(sub_obj)

    doc = token_db.token_balances.docs[0]
    assert doc["subscription_status"] == "canceled"


# ─── AC3: Webhook — unknown event passthrough ─────────────────────────────────

def test_webhook_unknown_event_returns_200(token_db, monkeypatch):
    """Unhandled event type → 200 (Stripe requires 2xx for all deliveries)."""

    def _fake_construct(body, sig, secret):
        return _make_stripe_event("payment_intent.created", {"id": "pi_123"})

    monkeypatch.setattr("stripe.Webhook.construct_event", _fake_construct)

    from fastapi import FastAPI
    from routes.tokens import router as tokens_router

    mini = FastAPI()
    mini.include_router(tokens_router)
    client = TestClient(mini, raise_server_exceptions=False)

    resp = client.post(
        "/api/tokens/webhook",
        content=b'{"type":"payment_intent.created"}',
        headers={"stripe-signature": "valid_sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200


# ─── AC3: Webhook — no JWT auth required ─────────────────────────────────────

def test_webhook_no_auth_header_needed(monkeypatch):
    """Webhook succeeds without Authorization header (Stripe sig replaces JWT)."""

    def _fake_construct(body, sig, secret):
        return _make_stripe_event("payment_intent.created", {"id": "pi_456"})

    monkeypatch.setattr("stripe.Webhook.construct_event", _fake_construct)

    db = type("Db", (), {"token_purchases": FakeCollection(), "token_balances": FakeCollection()})()
    import services.stripe_service as svc
    monkeypatch.setattr(svc, "get_db", lambda: db)

    from fastapi import FastAPI
    from routes.tokens import router as tokens_router

    mini = FastAPI()
    mini.include_router(tokens_router)
    client = TestClient(mini, raise_server_exceptions=False)

    resp = client.post(
        "/api/tokens/webhook",
        content=b'{}',
        headers={"stripe-signature": "valid_sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200


# ─── AC5: Balance includes subscription fields ────────────────────────────────

async def test_get_balance_includes_subscription_fields(token_db, monkeypatch):
    """get_balance() returns subscription_status, subscription_plan, etc."""
    token_db.token_balances.docs[:] = [
        {
            "branch_id": "branch-a",
            "role_limits": {},
            "school_topup_pool": 1_000_000,
            "personal_topups": {},
            "self_recharge_enabled": True,
            "subscription_status": "active",
            "subscription_plan": "monthly_school_starter",
            "subscription_current_period_end": "2026-06-18T00:00:00+00:00",
            "stripe_customer_id": "cus_test_abc",
        }
    ]
    token_db.token_usage.docs[:] = []

    from services import token_service
    monkeypatch.setattr(token_service, "get_db", lambda: token_db)

    result = await token_service.get_balance("branch-a")
    assert result["subscription_status"] == "active"
    assert result["subscription_plan"] == "monthly_school_starter"
    assert result["stripe_customer_id"] == "cus_test_abc"
    assert result["subscription_current_period_end"] is not None


async def test_get_balance_no_doc_returns_null_subscription_fields(token_db, monkeypatch):
    """get_balance() with no balance doc → subscription fields are null."""
    token_db.token_balances.docs[:] = []

    from services import token_service
    monkeypatch.setattr(token_service, "get_db", lambda: token_db)

    result = await token_service.get_balance("branch-missing")
    assert result["subscription_status"] is None
    assert result["subscription_plan"] is None
    assert result["stripe_customer_id"] is None


# ─── AC6: Packs endpoint includes subscriptions ───────────────────────────────

def test_packs_endpoint_includes_subscriptions(app_client, autouse_clean):
    """GET /api/tokens/packs returns both packs and subscriptions lists."""
    headers = _owner_headers()
    resp = app_client.get("/api/tokens/packs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "packs" in data["data"]
    assert "subscriptions" in data["data"]
    sub_ids = [s["id"] for s in data["data"]["subscriptions"]]
    assert "monthly_school_starter" in sub_ids
    assert "monthly_school_pro" in sub_ids
