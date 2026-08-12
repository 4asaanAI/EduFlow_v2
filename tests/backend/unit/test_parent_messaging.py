"""Parent messaging - access control, caps, and wording rules.

Sending reaches real families and cannot be recalled, so the gates matter as much as
the feature. Every endpoint carries the mandatory unauthenticated + wrong-role pair.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

from fastapi.testclient import TestClient
from middleware.auth import create_jwt
from tests.backend.conftest import APP_AVAILABLE

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from server import app
from tests.backend.conftest import _fake_db
from services import messaging_service as msg
from services.actor_context import actor_ctx_from_user

client = TestClient(app, raise_server_exceptions=False)

BASE = "/api/parent-messaging"


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "own-1", "role": "owner", "name": "Aman",
                    "branch_id": "branch-a", "schoolId": "aaryans-joya"})


def _principal():
    return _bearer({"user_id": "pr-1", "role": "admin", "sub_category": "principal",
                    "name": "Meena", "branch_id": "branch-a", "schoolId": "aaryans-joya"})


def _accountant():
    return _bearer({"user_id": "ac-1", "role": "admin", "sub_category": "accountant",
                    "name": "Raj", "branch_id": "branch-a", "schoolId": "aaryans-joya"})


def _teacher():
    return _bearer({"user_id": "t-1", "role": "teacher", "name": "Ravi",
                    "branch_id": "branch-a", "schoolId": "aaryans-joya"})


def _ctx(user_id="own-1", role="owner"):
    return actor_ctx_from_user(
        {"id": user_id, "role": role, "name": "T", "branch_id": "branch-a"},
        school_id="aaryans-joya",
    )


# ─── Security: the mandatory pair on every endpoint ──────────────────────────

@pytest.mark.parametrize("method,path", [
    ("get", f"{BASE}/status"),
    ("get", f"{BASE}/templates"),
    ("post", f"{BASE}/templates"),
    ("post", f"{BASE}/preview"),
    ("post", f"{BASE}/send"),
    ("get", f"{BASE}/logs"),
])
def test_endpoint_unauthenticated_returns_401(method, path):
    kwargs = {"json": {}} if method == "post" else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401


@pytest.mark.parametrize("method,path", [
    ("get", f"{BASE}/status"),
    ("get", f"{BASE}/templates"),
    ("post", f"{BASE}/templates"),
    ("post", f"{BASE}/preview"),
    ("post", f"{BASE}/send"),
    ("get", f"{BASE}/logs"),
])
def test_endpoint_teacher_returns_403(method, path):
    """A teacher must not be able to message the whole school."""
    kwargs = {"json": {}} if method == "post" else {}
    assert getattr(client, method)(path, headers=_teacher(), **kwargs).status_code == 403


def test_student_cannot_send():
    headers = _bearer({"user_id": "s-1", "role": "student", "name": "Kid",
                       "schoolId": "aaryans-joya"})
    assert client.post(f"{BASE}/send", json={}, headers=headers).status_code == 403


def test_accountant_may_send_but_not_edit_templates():
    """Accountants chase fees, so they send. Changing school-wide wording is
    leadership's call, so template writes stay with owner/principal."""
    assert client.get(f"{BASE}/templates", headers=_accountant()).status_code == 200
    assert client.post(f"{BASE}/templates", json={"name": "x", "channel": "sms", "body": "y"},
                       headers=_accountant()).status_code == 403


def test_principal_may_edit_templates():
    _fake_db.message_templates.docs[:] = []
    resp = client.post(f"{BASE}/templates",
                       json={"name": "Principal note", "channel": "sms", "body": "Hello {guardian_name}"},
                       headers=_principal())
    assert resp.status_code == 200, resp.text


# ─── Wording rules ───────────────────────────────────────────────────────────

def test_whatsapp_template_requires_approved_sid():
    _fake_db.message_templates.docs[:] = []
    resp = client.post(f"{BASE}/templates",
                       json={"name": "WA notice", "channel": "whatsapp", "body": "hi"},
                       headers=_owner())
    assert resp.status_code == 400
    assert "twilio_template_sid" in resp.json()["detail"]


def test_sms_template_accepts_any_wording():
    _fake_db.message_templates.docs[:] = []
    resp = client.post(f"{BASE}/templates",
                       json={"name": "Anything", "channel": "sms",
                             "body": "Bus is late by 30 minutes today."},
                       headers=_owner())
    assert resp.status_code == 200


def test_updating_whatsapp_wording_warns_it_is_preview_only():
    """The single most misleading outcome would be someone 'fixing' WhatsApp wording
    and believing parents will see it. The response must say otherwise."""
    _fake_db.message_templates.docs[:] = [{
        "id": "tpl-1", "schoolId": "aaryans-joya", "name": "Fee due", "channel": "whatsapp",
        "body": "old", "twilio_template_sid": "HX1", "variables": [],
        "approval_status": "approved",
    }]
    resp = client.patch(f"{BASE}/templates/tpl-1", json={"body": "new wording"},
                        headers=_owner())
    assert resp.status_code == 200
    note = resp.json()["note"].lower()
    assert "preview" in note and "approval" in note


def test_duplicate_template_name_rejected():
    _fake_db.message_templates.docs[:] = [
        {"id": "t1", "schoolId": "aaryans-joya", "name": "Fee due", "channel": "sms", "body": "x"}
    ]
    resp = client.post(f"{BASE}/templates",
                       json={"name": "fee due", "channel": "sms", "body": "y"},
                       headers=_owner())
    assert resp.status_code == 400


# ─── Rendering ───────────────────────────────────────────────────────────────

def test_render_substitutes_known_placeholders():
    out = msg.render(
        "Dear {guardian_name}, {student_name} of {class_section} owes {amount}.",
        {"guardian_name": "Rakesh", "student_name": "Aryan",
         "class_section": "5-A", "amount": "5,000"},
    )
    assert out == "Dear Rakesh, Aryan of 5-A owes 5,000."


def test_render_leaves_unknown_placeholder_visible():
    """A typo must be visible on the confirm card, not silently blanked - otherwise a
    message goes out reading 'Dear ,'."""
    out = msg.render("Hi {guardain_name}", {"guardian_name": "Rakesh"})
    assert "{guardain_name}" in out


def test_render_falls_back_for_missing_guardian_name():
    assert msg.render("Dear {guardian_name},", {}) == "Dear Parent,"


# ─── Channel readiness ───────────────────────────────────────────────────────

def test_channel_status_reports_exactly_what_is_missing(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-x")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)
    status = msg.channel_status("whatsapp")
    assert status["ready"] is False
    assert status["missing"] == ["TWILIO_WHATSAPP_FROM"]


def test_channel_status_ready_when_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-x")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+14155238886")
    assert msg.channel_status("whatsapp")["ready"] is True


def test_send_refuses_when_channel_not_configured(monkeypatch):
    """Must raise, not record 'not_configured' rows and report success."""
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-x")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.delenv("TWILIO_PHONE_NUMBER", raising=False)
    resp = client.post(f"{BASE}/send",
                       json={"channel": "sms", "audience": "students",
                             "student_ids": ["stu-1"], "body": "hi"},
                       headers=_owner())
    assert resp.status_code == 503
    assert "TWILIO_PHONE_NUMBER" in resp.json()["detail"]


# ─── Phone normalisation ─────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("9000000001", "+919000000001"),
    ("09000000001", "+919000000001"),
    ("+919000000001", "+919000000001"),
    ("90000 00001", "+919000000001"),
    ("9000-000-001", "+919000000001"),
    ("", ""),
])
def test_normalize_phone(raw, expected):
    assert msg.normalize_phone(raw) == expected


# ─── The confirm card must state the blast radius ────────────────────────────

def test_confirm_card_states_how_many_families():
    """Approving a send without seeing the number is not informed consent."""
    from routes.chat import _build_confirm_display

    text = _build_confirm_display("send_parent_message", {
        "channel": "sms", "audience": "class",
        "_recipient_count": 42, "_message_preview": "Dear Rakesh, fees are due.",
    })
    assert "42 families" in text
    assert "SMS" in text
    assert "Dear Rakesh" in text


def test_confirm_card_says_family_singular_for_one():
    from routes.chat import _build_confirm_display

    text = _build_confirm_display("send_parent_message", {
        "channel": "whatsapp", "audience": "students", "_recipient_count": 1,
    })
    assert "1 family" in text and "families" not in text


async def test_resolution_freezes_the_recipient_list(monkeypatch):
    """The set approved must be the set sent - not a re-query that may have drifted."""
    from routes.chat import _resolve_messaging_audience
    from tests.backend.conftest import _fake_db

    _fake_db.students.docs[:] = [
        {"id": "stu-1", "name": "Aryan", "class_id": "cls-1", "section": "A",
         "phone": "9000000001", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
    ]
    _fake_db.guardians.docs[:] = [
        {"student_id": "stu-1", "name": "Rakesh", "phone": "9000000001",
         "is_primary": True, "schoolId": "aaryans-joya"},
    ]
    _fake_db.classes.docs[:] = [
        {"id": "cls-1", "name": "5", "section": "A",
         "schoolId": "aaryans-joya", "branch_id": "branch-a"},
    ]
    out = await _resolve_messaging_audience(
        {"channel": "sms", "audience": "students", "student_ids": ["stu-1"],
         "body": "Dear {guardian_name}, hello."},
        {"id": "own-1", "role": "owner", "name": "Aman", "branch_id": "branch-a"},
        _fake_db,
    )
    assert out["_recipient_count"] == 1
    assert out["_recipients"][0]["phone"] == "+919000000001"
    assert out["_message_preview"] == "Dear Rakesh, hello."


async def test_resolution_failure_is_reported_not_hidden():
    """A resolution that cannot work out the audience must say so on the card."""
    from routes.chat import _resolve_messaging_audience
    from tests.backend.conftest import _fake_db

    out = await _resolve_messaging_audience(
        {"channel": "sms", "audience": "class", "body": "hi"},  # no class_id
        {"id": "own-1", "role": "owner", "name": "Aman", "branch_id": "branch-a"},
        _fake_db,
    )
    assert out["_recipient_count"] == 0
    assert "could not work out" in out["_message_preview"]
