"""Parent messaging - dual-entrypoint parity (Flo vs the panel).

Flo can send real WhatsApp/SMS to families. The whole safety argument for that rests on
Flo using the SAME code path as a staff member pressing Send, so this pins it: the same
input through `/api/parent-messaging/*` and through the AI tool must leave byte-identical
`message_logs`, `message_templates` and audit rows (modulo a volatile allowlist).

Also pins the three things that must never regress, because each one reaches real
families or misleads the person sending:
  * WhatsApp refuses free-typed wording (Meta forbids it).
  * A template still awaiting Meta's approval cannot be used to send.
  * An unconfigured channel FAILS LOUDLY instead of reporting success sending nothing.
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "sent_at",
             "batch_id", "provider_sid", "entity_id", "record_id", "changes"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}


def _owner_headers():
    return {"Authorization": "Bearer " + create_jwt(
        {"user_id": "own-1", "role": "owner", "name": "Owner", "schoolId": "aaryans-joya"}
    )}


class _FakeMsg:
    sid = "SM-fake"


class _FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeMsg()


class _FakeTwilio:
    def __init__(self):
        self.messages = _FakeMessages()


@pytest.fixture(autouse=True)
def _twilio_and_config(monkeypatch, fake_db):
    """Configure both channels and stub Twilio, so nothing leaves the test process."""
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok-test")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+12286410951")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+14155238886")
    from services import messaging_service as msg
    monkeypatch.setattr(msg, "get_twilio_client", lambda: _FakeTwilio())

    # `_fake_db` is shared for the whole session, so this seed MUST be restored on the
    # way out. Replacing it without restoring broke five unrelated student parity tests
    # when the suite ran as a whole - invisible when this file ran alone.
    _saved = {
        col: list(getattr(fake_db, col).docs)
        for col in ("students", "guardians", "classes")
    }

    fake_db.students.docs[:] = [
        {"id": "stu-1", "name": "Aryan", "class_id": "cls-1", "section": "A",
         "phone": "9000000001", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
    ]
    fake_db.guardians.docs[:] = [
        {"student_id": "stu-1", "name": "Rakesh", "phone": "9000000001",
         "is_primary": True, "schoolId": "aaryans-joya"},
    ]
    fake_db.classes.docs[:] = [
        {"id": "cls-1", "name": "5", "section": "A",
         "schoolId": "aaryans-joya", "branch_id": "branch-a"},
    ]
    _clear(fake_db)
    yield
    _clear(fake_db)
    for col, docs in _saved.items():
        getattr(fake_db, col).docs[:] = docs


def _clear(fake_db):
    for col in ("message_logs", "message_templates", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


def _mask(docs):
    out = [{k: v for k, v in d.items() if k not in _VOLATILE} for d in docs]
    out.sort(key=lambda d: (str(d.get("student_id", "")), str(d.get("name", "")),
                            str(d.get("action", ""))))
    return out


def _snapshot(fake_db):
    return {
        "message_logs": _mask(copy.deepcopy(fake_db.message_logs.docs)),
        "message_templates": _mask(copy.deepcopy(fake_db.message_templates.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("entity_type") in ("message_batch", "message_template")]),
    }


_SEND = {
    "channel": "sms",
    "audience": "students",
    "student_ids": ["stu-1"],
    "body": "Dear {guardian_name}, fees for {student_name} ({class_section}) are due.",
}


async def test_send_parent_message_ai_and_rest_are_identical(client, fake_db):
    resp = client.post("/api/parent-messaging/send", json=_SEND, headers=_owner_headers())
    assert resp.status_code == 200, resp.text
    rest_state = _snapshot(fake_db)
    _clear(fake_db)

    result = await tool_functions_v2.TOOL_REGISTRY["send_parent_message"]["fn"](
        dict(_SEND), OWNER_USER, None
    )
    assert result["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state


async def test_template_crud_ai_and_rest_are_identical(client, fake_db):
    body = {"name": "Bus delay", "channel": "sms",
            "body": "Dear {guardian_name}, the bus is delayed today."}

    resp = client.post("/api/parent-messaging/templates", json=body, headers=_owner_headers())
    assert resp.status_code == 200, resp.text
    rest_state = _snapshot(fake_db)
    _clear(fake_db)

    result = await tool_functions_v2.TOOL_REGISTRY["create_message_template"]["fn"](
        dict(body), OWNER_USER, None
    )
    assert result["success"] is True
    assert _snapshot(fake_db) == rest_state


# ─── The guarantees that protect real families ───────────────────────────────

async def test_whatsapp_refuses_free_typed_wording(fake_db):
    """Meta forbids free text on business-initiated WhatsApp. Refuse before sending."""
    result = await tool_functions_v2.TOOL_REGISTRY["send_parent_message"]["fn"](
        {"channel": "whatsapp", "audience": "students", "student_ids": ["stu-1"],
         "body": "anything at all"},
        OWNER_USER, None,
    )
    assert result["success"] is False
    assert "template" in result["message"].lower()
    assert fake_db.message_logs.docs == []


async def test_template_pending_approval_cannot_send(fake_db):
    """A template Meta has not approved would fail at the provider for every recipient."""
    fake_db.message_templates.docs[:] = [{
        "id": "tpl-p", "schoolId": "aaryans-joya", "name": "New notice",
        "channel": "whatsapp", "body": "hi {guardian_name}",
        "twilio_template_sid": "HX123", "variables": ["guardian_name"],
        "approval_status": "pending",
    }]
    result = await tool_functions_v2.TOOL_REGISTRY["send_parent_message"]["fn"](
        {"channel": "whatsapp", "audience": "students", "student_ids": ["stu-1"],
         "template_name": "New notice"},
        OWNER_USER, None,
    )
    assert result["success"] is False
    assert "pending" in result["message"].lower()
    assert fake_db.message_logs.docs == []


async def test_unconfigured_channel_fails_loudly(monkeypatch, fake_db):
    """The bug this system exists to remove: reporting success having sent nothing.

    Production had exactly this on 2026-08-08 - TWILIO_WHATSAPP_FROM was unset, and the
    old bulk route recorded every recipient as 'not_configured' and returned success.
    """
    monkeypatch.delenv("TWILIO_WHATSAPP_FROM", raising=False)
    result = await tool_functions_v2.TOOL_REGISTRY["send_parent_message"]["fn"](
        {"channel": "whatsapp", "audience": "students", "student_ids": ["stu-1"],
         "template_name": "x"},
        OWNER_USER, None,
    )
    assert result["success"] is False
    assert "not configured" in result["message"].lower()
    assert "TWILIO_WHATSAPP_FROM" in result["message"]
    assert fake_db.message_logs.docs == []


async def test_siblings_sharing_a_phone_get_one_message(fake_db):
    """Two children, one guardian number - the family should not be messaged twice."""
    fake_db.students.docs.append(
        {"id": "stu-2", "name": "Priya", "class_id": "cls-1", "section": "A",
         "phone": "9000000001", "schoolId": "aaryans-joya", "branch_id": "branch-a"}
    )
    fake_db.guardians.docs.append(
        {"student_id": "stu-2", "name": "Rakesh", "phone": "9000000001",
         "is_primary": True, "schoolId": "aaryans-joya"}
    )
    result = await tool_functions_v2.TOOL_REGISTRY["send_parent_message"]["fn"](
        {**_SEND, "student_ids": ["stu-1", "stu-2"]}, OWNER_USER, None
    )
    assert result["success"] is True
    assert result["data"]["recipient_count"] == 1
    assert len(fake_db.message_logs.docs) == 1
