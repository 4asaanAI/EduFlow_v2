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
os.environ.setdefault("RAZORPAY_KEY_ID", "rzp_test_fake_key")
os.environ.setdefault("RAZORPAY_KEY_SECRET", "rzp_test_fake_secret")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "whsec_test_fake_secret")
os.environ.setdefault("RAZORPAY_PLAN_MONTHLY_SCHOOL_STARTER", "plan_test_starter")
os.environ.setdefault("RAZORPAY_PLAN_MONTHLY_SCHOOL_PRO", "plan_test_pro")

pytestmark = pytest.mark.asyncio

import razorpay
from fastapi.testclient import TestClient
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


# ─── Fake Razorpay client ──────────────────────────────────────────────────────

FAKE_PAYMENT_LINK = {"id": "plink_test_abc123", "short_url": "https://rzp.io/i/abc123", "status": "created"}
FAKE_SUBSCRIPTION = {"id": "sub_test_001", "short_url": "https://rzp.io/i/sub001", "status": "created"}


class _FakePaymentLink:
    def create(self, data):
        return FAKE_PAYMENT_LINK


class _FakeSubscription:
    def create(self, data):
        return FAKE_SUBSCRIPTION


class FakeRazorpayClient:
    payment_link = _FakePaymentLink()
    subscription = _FakeSubscription()


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
    import services.razorpay_service as svc
    monkeypatch.setattr(svc, "get_db", lambda: db)
    monkeypatch.setattr(svc, "_razorpay_client", lambda: FakeRazorpayClient())
    import routes.tokens as tok_routes
    monkeypatch.setattr(tok_routes, "get_db", lambda: db, raising=False)
    return db


@pytest.fixture
def app_client(token_db):
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


# ─── AC1: Razorpay one-time payment link ──────────────────────────────────────

def test_create_checkout_session_owner_success(app_client, autouse_clean):
    """Owner + valid pack → 200 with checkout_url (Razorpay payment-link short_url) + session_id."""
    resp = app_client.post(
        "/api/tokens/create-checkout-session",
        json={"pack_id": "basic", "success_url": "https://app.test?recharge=success", "cancel_url": "https://app.test?recharge=cancel"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["checkout_url"] == FAKE_PAYMENT_LINK["short_url"]
    assert data["data"]["session_id"] == FAKE_PAYMENT_LINK["id"]


def test_create_checkout_session_unauthenticated_401(app_client, autouse_clean):
    resp = app_client.post("/api/tokens/create-checkout-session", json={"pack_id": "basic"})
    assert resp.status_code == 401


def test_create_checkout_session_wrong_role_403(app_client, autouse_clean):
    resp = app_client.post(
        "/api/tokens/create-checkout-session",
        json={"pack_id": "basic"},
        headers=_admin_headers(),
    )
    assert resp.status_code == 403


def test_create_checkout_session_unknown_pack_400(app_client, autouse_clean):
    resp = app_client.post(
        "/api/tokens/create-checkout-session",
        json={"pack_id": "nonexistent_pack"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 400


# ─── AC2: Razorpay subscription ────────────────────────────────────────────────

def test_create_subscription_session_owner_success(app_client, autouse_clean):
    resp = app_client.post(
        "/api/tokens/create-subscription-session",
        json={"plan_id": "monthly_school_starter", "success_url": "https://app.test?recharge=success", "cancel_url": "https://app.test?recharge=cancel"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["checkout_url"] == FAKE_SUBSCRIPTION["short_url"]


def test_create_subscription_session_unauthenticated_401(app_client, autouse_clean):
    resp = app_client.post(
        "/api/tokens/create-subscription-session",
        json={"plan_id": "monthly_school_starter"},
    )
    assert resp.status_code == 401


def test_create_subscription_session_wrong_role_403(app_client, autouse_clean):
    resp = app_client.post(
        "/api/tokens/create-subscription-session",
        json={"plan_id": "monthly_school_starter"},
        headers=_admin_headers(),
    )
    assert resp.status_code == 403


def test_create_subscription_session_unknown_plan_400(app_client, autouse_clean):
    resp = app_client.post(
        "/api/tokens/create-subscription-session",
        json={"plan_id": "nonexistent_plan"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 400


# ─── AC3 + AC4: Webhook handler — payment_link.paid ───────────────────────────

async def test_webhook_payment_link_paid_credits_tokens(token_db, monkeypatch):
    token_db.token_balances.docs[:] = [
        {"branch_id": "branch-a", "school_topup_pool": 0, "role_limits": {}}
    ]
    link = {
        "id": "plink_unique_1",
        "status": "paid",
        "notes": {"branch_id": "branch-a", "user_id": "owner-1", "pack_id": "basic"},
    }

    import services.razorpay_service as svc
    await svc.handle_payment_link_paid(link)

    assert token_db.token_balances.docs[0]["school_topup_pool"] == 200_000
    assert len(token_db.token_purchases.docs) == 1
    purchase = token_db.token_purchases.docs[0]
    assert purchase["razorpay_reference_id"] == "plink_unique_1"
    assert purchase["payment_provider"] == "razorpay"
    assert "stripe_session_id" not in purchase


async def test_webhook_payment_link_paid_idempotent(token_db, monkeypatch):
    token_db.token_balances.docs[:] = [
        {"branch_id": "branch-a", "school_topup_pool": 200_000, "role_limits": {}}
    ]
    token_db.token_purchases.docs[:] = [
        {"razorpay_reference_id": "plink_already", "payment_provider": "razorpay"}
    ]
    link = {
        "id": "plink_already",
        "status": "paid",
        "notes": {"branch_id": "branch-a", "user_id": "owner-1", "pack_id": "basic"},
    }

    import services.razorpay_service as svc
    await svc.handle_payment_link_paid(link)

    assert token_db.token_balances.docs[0]["school_topup_pool"] == 200_000
    assert len(token_db.token_purchases.docs) == 1


async def test_webhook_payment_link_not_paid_skipped(token_db, monkeypatch):
    token_db.token_balances.docs[:] = [{"branch_id": "branch-a", "school_topup_pool": 0, "role_limits": {}}]
    link = {"id": "plink_x", "status": "created", "notes": {"branch_id": "branch-a", "user_id": "u", "pack_id": "basic"}}

    import services.razorpay_service as svc
    await svc.handle_payment_link_paid(link)

    assert token_db.token_balances.docs[0]["school_topup_pool"] == 0
    assert len(token_db.token_purchases.docs) == 0


# ─── AC3: Webhook route — invalid signature ───────────────────────────────────

def test_webhook_invalid_signature_400(token_db, monkeypatch):
    def _raise_sig_error(body, sig):
        raise razorpay.errors.SignatureVerificationError("bad sig")

    import routes.tokens as tok_routes
    monkeypatch.setattr(tok_routes, "verify_webhook", _raise_sig_error)

    from fastapi import FastAPI
    mini = FastAPI()
    mini.include_router(tok_routes.router)
    client = TestClient(mini, raise_server_exceptions=False)

    resp = client.post(
        "/api/tokens/webhook",
        content=b'{"event":"payment_link.paid"}',
        headers={"x-razorpay-signature": "bad_sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


# ─── AC3: Webhook handler — subscription.activated ────────────────────────────

async def test_webhook_subscription_activated_updates_balance(token_db, monkeypatch):
    token_db.token_balances.docs[:] = []
    sub = {
        "id": "sub_test_001",
        "status": "active",
        "customer_id": "cust_test_001",
        "current_end": 1750000000,
        "notes": {"branch_id": "branch-a", "plan_id": "monthly_school_starter"},
    }

    import services.razorpay_service as svc
    await svc.handle_subscription_activated(sub)

    assert len(token_db.token_balances.docs) == 1
    doc = token_db.token_balances.docs[0]
    assert doc["subscription_id"] == "sub_test_001"
    assert doc["subscription_status"] == "active"
    assert doc["subscription_plan"] == "monthly_school_starter"
    assert doc["razorpay_customer_id"] == "cust_test_001"
    assert doc["subscription_current_period_end"] is not None


# ─── AC3: Webhook handler — subscription.charged (renewal) ────────────────────

async def test_webhook_subscription_charged_credits_pool(token_db, monkeypatch):
    token_db.token_balances.docs[:] = [
        {
            "branch_id": "branch-a",
            "school_topup_pool": 500_000,
            "subscription_id": "sub_test_001",
            "subscription_plan": "monthly_school_starter",
        }
    ]
    sub = {"id": "sub_test_001", "current_end": 1750000000}

    import services.razorpay_service as svc
    await svc.handle_subscription_charged(sub, "pay_renewal_1")

    assert token_db.token_balances.docs[0]["school_topup_pool"] == 500_000 + 2_000_000
    assert any(p["razorpay_reference_id"] == "subcharge_pay_renewal_1" for p in token_db.token_purchases.docs)


async def test_webhook_subscription_charged_idempotent(token_db, monkeypatch):
    token_db.token_balances.docs[:] = [
        {"branch_id": "branch-a", "school_topup_pool": 2_000_000, "subscription_id": "sub_test_001", "subscription_plan": "monthly_school_starter"}
    ]
    token_db.token_purchases.docs[:] = [{"razorpay_reference_id": "subcharge_pay_dup"}]
    sub = {"id": "sub_test_001", "current_end": 1750000000}

    import services.razorpay_service as svc
    await svc.handle_subscription_charged(sub, "pay_dup")

    assert token_db.token_balances.docs[0]["school_topup_pool"] == 2_000_000
    assert len(token_db.token_purchases.docs) == 1


# ─── AC3: Webhook handler — subscription.cancelled ────────────────────────────

async def test_webhook_subscription_cancelled_marks_canceled(token_db, monkeypatch):
    token_db.token_balances.docs[:] = [
        {"branch_id": "branch-a", "subscription_id": "sub_del_001", "subscription_status": "active"}
    ]
    sub = {"id": "sub_del_001", "notes": {"branch_id": "branch-a"}}

    import services.razorpay_service as svc
    await svc.handle_subscription_cancelled(sub)

    assert token_db.token_balances.docs[0]["subscription_status"] == "canceled"


# ─── AC3: Webhook route — unknown event passthrough ───────────────────────────

def test_webhook_unknown_event_returns_200(token_db, monkeypatch):
    import routes.tokens as tok_routes
    monkeypatch.setattr(tok_routes, "verify_webhook", lambda body, sig: {"event": "payment.authorized", "payload": {}})

    from fastapi import FastAPI
    mini = FastAPI()
    mini.include_router(tok_routes.router)
    client = TestClient(mini, raise_server_exceptions=False)

    resp = client.post(
        "/api/tokens/webhook",
        content=b'{"event":"payment.authorized"}',
        headers={"x-razorpay-signature": "valid_sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200


# ─── AC3: Webhook route — no JWT auth required ────────────────────────────────

def test_webhook_no_auth_header_needed(token_db, monkeypatch):
    import routes.tokens as tok_routes
    monkeypatch.setattr(tok_routes, "verify_webhook", lambda body, sig: {"event": "payment.authorized", "payload": {}})

    from fastapi import FastAPI
    mini = FastAPI()
    mini.include_router(tok_routes.router)
    client = TestClient(mini, raise_server_exceptions=False)

    resp = client.post(
        "/api/tokens/webhook",
        content=b'{}',
        headers={"x-razorpay-signature": "valid_sig", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200


# ─── AC5: Balance includes subscription fields ────────────────────────────────

async def test_get_balance_includes_subscription_fields(token_db, monkeypatch):
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
            "razorpay_customer_id": "cust_test_abc",
        }
    ]
    token_db.token_usage.docs[:] = []

    from services import token_service
    monkeypatch.setattr(token_service, "get_db", lambda: token_db)

    result = await token_service.get_balance("branch-a")
    assert result["subscription_status"] == "active"
    assert result["subscription_plan"] == "monthly_school_starter"
    assert result["razorpay_customer_id"] == "cust_test_abc"
    assert result["subscription_current_period_end"] is not None


async def test_get_balance_no_doc_returns_null_subscription_fields(token_db, monkeypatch):
    token_db.token_balances.docs[:] = []

    from services import token_service
    monkeypatch.setattr(token_service, "get_db", lambda: token_db)

    result = await token_service.get_balance("branch-missing")
    assert result["subscription_status"] is None
    assert result["subscription_plan"] is None
    assert result["razorpay_customer_id"] is None


# ─── AC6: Packs endpoint includes subscriptions ───────────────────────────────

def test_packs_endpoint_includes_subscriptions(app_client, autouse_clean):
    resp = app_client.get("/api/tokens/packs", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "packs" in data["data"]
    assert "subscriptions" in data["data"]
    sub_ids = [s["id"] for s in data["data"]["subscriptions"]]
    assert "monthly_school_starter" in sub_ids
    assert "monthly_school_pro" in sub_ids
