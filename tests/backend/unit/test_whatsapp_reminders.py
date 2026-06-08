from __future__ import annotations

import json
import os
import sys
from unittest.mock import patch

import pytest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

from fastapi.testclient import TestClient
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection, APP_AVAILABLE

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from server import app
from tests.backend.conftest import _fake_db

client = TestClient(app, raise_server_exceptions=False)


def _bearer(payload: dict) -> dict:
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}


def _owner_headers():
    return _bearer({
        "user_id": "owner-1", "role": "owner", "name": "Aman",
        "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


def _accountant_headers():
    return _bearer({
        "user_id": "acc-1", "role": "admin", "name": "Raj",
        "sub_category": "accountant", "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


def _principal_headers():
    return _bearer({
        "user_id": "prin-1", "role": "admin", "name": "Meena",
        "sub_category": "principal", "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


def _teacher_headers():
    return _bearer({
        "user_id": "t1", "role": "teacher", "name": "Ravi",
        "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


# ─── GET /api/sms/whatsapp-defaulters ─────────────────────────────────────────

def test_whatsapp_defaulters_unauthenticated_returns_401():
    resp = client.get("/api/sms/whatsapp-defaulters")
    assert resp.status_code == 401


def test_whatsapp_defaulters_teacher_returns_403():
    resp = client.get("/api/sms/whatsapp-defaulters", headers=_teacher_headers())
    assert resp.status_code == 403


def test_whatsapp_defaulters_owner_returns_ok():
    _fake_db.fee_transactions.docs = [
        {"student_id": "stu-1", "amount": 5000, "status": "pending", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
    ]
    # Endpoint scopes attendance to the CURRENT month — generate dates within it
    # so the test is not fragile across month boundaries.
    from datetime import datetime, timezone
    _m = datetime.now(timezone.utc).strftime("%Y-%m")
    _fake_db.student_attendance.docs = [
        {"student_id": "stu-2", "status": "absent", "date": f"{_m}-01", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
        {"student_id": "stu-2", "status": "absent", "date": f"{_m}-02", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
        {"student_id": "stu-2", "status": "absent", "date": f"{_m}-03", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
        {"student_id": "stu-2", "status": "absent", "date": f"{_m}-04", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
        {"student_id": "stu-2", "status": "present", "date": f"{_m}-05", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
    ]
    _fake_db.students.docs = [
        {"id": "stu-1", "name": "Aryan", "class_id": "X", "section": "A", "phone": "+919000000001", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
        {"id": "stu-2", "name": "Priya", "class_id": "IX", "section": "B", "phone": "", "schoolId": "aaryans-joya", "branch_id": "branch-a"},
    ]
    _fake_db.guardians.docs = [
        {"student_id": "stu-1", "name": "Rakesh", "phone": "+919000000001", "schoolId": "aaryans-joya"},
        {"student_id": "stu-2", "name": "Sunita", "phone": "+919000000002", "schoolId": "aaryans-joya"},
    ]

    resp = client.get("/api/sms/whatsapp-defaulters", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "fee_defaulters" in data["data"]
    assert "attendance_defaulters" in data["data"]
    fee_ids = [d["student_id"] for d in data["data"]["fee_defaulters"]]
    assert "stu-1" in fee_ids
    att_ids = [d["student_id"] for d in data["data"]["attendance_defaulters"]]
    assert "stu-2" in att_ids


def test_whatsapp_defaulters_accountant_returns_ok():
    _fake_db.fee_transactions.docs = []
    _fake_db.student_attendance.docs = []
    _fake_db.students.docs = []
    _fake_db.guardians.docs = []
    resp = client.get("/api/sms/whatsapp-defaulters", headers=_accountant_headers())
    assert resp.status_code == 200


def test_whatsapp_defaulters_skips_students_without_phone():
    """Students with no phone on student doc AND no guardian phone are excluded."""
    _fake_db.fee_transactions.docs = [
        {"student_id": "stu-nophone", "amount": 3000, "status": "overdue", "schoolId": "aaryans-joya", "branch_id": "branch-a"}
    ]
    _fake_db.student_attendance.docs = []
    _fake_db.students.docs = [
        {"id": "stu-nophone", "name": "Ghost", "class_id": "VII", "section": "A", "phone": "", "schoolId": "aaryans-joya", "branch_id": "branch-a"}
    ]
    _fake_db.guardians.docs = []

    resp = client.get("/api/sms/whatsapp-defaulters", headers=_owner_headers())
    assert resp.status_code == 200
    assert resp.json()["data"]["fee_defaulters"] == []


# ─── POST /api/sms/whatsapp-fee-reminders ─────────────────────────────────────

def test_fee_reminders_unauthenticated_returns_401():
    resp = client.post("/api/sms/whatsapp-fee-reminders", json={"recipients": []})
    assert resp.status_code == 401


def test_fee_reminders_teacher_returns_403():
    resp = client.post(
        "/api/sms/whatsapp-fee-reminders",
        json={"recipients": [{"student_id": "s1", "phone": "+919000000001"}]},
        headers=_teacher_headers(),
    )
    assert resp.status_code == 403


def test_fee_reminders_empty_recipients_returns_400():
    resp = client.post(
        "/api/sms/whatsapp-fee-reminders",
        json={"recipients": []},
        headers=_accountant_headers(),
    )
    assert resp.status_code == 400


def test_fee_reminders_not_configured_logs_and_returns_ok():
    """When Twilio is not configured, status is not_configured but request succeeds."""
    _fake_db.sms_logs.docs = []
    recipient = {
        "student_id": "s1", "student_name": "Aryan", "guardian_name": "Rakesh",
        "phone": "+919000000001", "class_section": "X A", "outstanding_amount": 5000,
    }
    with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": ""}):
        resp = client.post(
            "/api/sms/whatsapp-fee-reminders",
            json={"recipients": [recipient]},
            headers=_accountant_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["not_configured"] == 1


def test_fee_reminders_uses_content_sid_not_body():
    """Critical: WhatsApp template messages MUST use content_sid, not body."""
    sent_messages = []

    class FakeTwilioMessage:
        sid = "SM_FAKE_123"

    class FakeTwilioMessages:
        def create(self, **kwargs):
            sent_messages.append(kwargs)
            return FakeTwilioMessage()

    class FakeTwilioClient:
        messages = FakeTwilioMessages()

    _fake_db.sms_logs.docs = []
    recipient = {
        "student_id": "s1", "student_name": "Aryan", "guardian_name": "Rakesh",
        "phone": "+919000000001", "class_section": "X A", "outstanding_amount": 5000,
    }

    env_override = {
        "TWILIO_ACCOUNT_SID": "ACtest123",
        "TWILIO_AUTH_TOKEN": "authtest",
        "TWILIO_WHATSAPP_FROM": "+19000000001",
        "TWILIO_WHATSAPP_FEE_TEMPLATE_SID": "HXfee_template_sid",
    }

    with patch("routes.sms.get_twilio_client", return_value=FakeTwilioClient()):
        with patch.dict(os.environ, env_override):
            resp = client.post(
                "/api/sms/whatsapp-fee-reminders",
                json={"recipients": [recipient]},
                headers=_accountant_headers(),
            )

    assert resp.status_code == 200
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert "body" not in msg, "WhatsApp templates must use content_sid, not body="
    assert msg["content_sid"] == "HXfee_template_sid"
    assert msg["from_"].startswith("whatsapp:")
    assert msg["to"].startswith("whatsapp:")
    variables = json.loads(msg["content_variables"])
    assert variables["2"] == "Aryan"  # student_name


def test_fee_reminders_over_500_returns_400():
    recipients = [{"student_id": f"s{i}", "phone": "+919000000001"} for i in range(501)]
    resp = client.post(
        "/api/sms/whatsapp-fee-reminders",
        json={"recipients": recipients},
        headers=_owner_headers(),
    )
    assert resp.status_code == 400


# ─── POST /api/sms/whatsapp-attendance-alerts ─────────────────────────────────

def test_attendance_alerts_unauthenticated_returns_401():
    resp = client.post("/api/sms/whatsapp-attendance-alerts", json={"recipients": []})
    assert resp.status_code == 401


def test_attendance_alerts_accountant_returns_403():
    """Accountant cannot send attendance alerts — only owner or principal."""
    resp = client.post(
        "/api/sms/whatsapp-attendance-alerts",
        json={"recipients": [{"student_id": "s1", "phone": "+919000000001"}]},
        headers=_accountant_headers(),
    )
    assert resp.status_code == 403


def test_attendance_alerts_principal_allowed():
    _fake_db.sms_logs.docs = []
    recipient = {
        "student_id": "s1", "student_name": "Priya", "guardian_name": "Sunita",
        "phone": "+919000000002", "class_section": "IX B", "attendance_pct": 20.0,
    }
    with patch.dict(os.environ, {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": ""}):
        resp = client.post(
            "/api/sms/whatsapp-attendance-alerts",
            json={"recipients": [recipient]},
            headers=_principal_headers(),
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_attendance_alerts_uses_content_sid_not_body():
    """Critical: WhatsApp attendance template must use content_sid."""
    sent_messages = []

    class FakeTwilioMessage:
        sid = "SM_ATT_456"

    class FakeTwilioMessages:
        def create(self, **kwargs):
            sent_messages.append(kwargs)
            return FakeTwilioMessage()

    class FakeTwilioClient:
        messages = FakeTwilioMessages()

    _fake_db.sms_logs.docs = []
    recipient = {
        "student_id": "s1", "student_name": "Priya", "guardian_name": "Sunita",
        "phone": "+919000000002", "class_section": "IX B", "attendance_pct": 20.0,
    }

    env_override = {
        "TWILIO_ACCOUNT_SID": "ACtest123",
        "TWILIO_AUTH_TOKEN": "authtest",
        "TWILIO_WHATSAPP_FROM": "+19000000001",
        "TWILIO_WHATSAPP_ATTENDANCE_TEMPLATE_SID": "HXatt_template_sid",
    }

    with patch("routes.sms.get_twilio_client", return_value=FakeTwilioClient()):
        with patch.dict(os.environ, env_override):
            resp = client.post(
                "/api/sms/whatsapp-attendance-alerts",
                json={"recipients": [recipient]},
                headers=_principal_headers(),
            )

    assert resp.status_code == 200
    assert len(sent_messages) == 1
    msg = sent_messages[0]
    assert "body" not in msg, "WhatsApp templates must use content_sid, not body="
    assert msg["content_sid"] == "HXatt_template_sid"
    assert msg["from_"].startswith("whatsapp:")
    assert msg["to"].startswith("whatsapp:")
    variables = json.loads(msg["content_variables"])
    assert variables["2"] == "Priya"  # student_name


def test_attendance_alerts_empty_recipients_returns_400():
    resp = client.post(
        "/api/sms/whatsapp-attendance-alerts",
        json={"recipients": []},
        headers=_principal_headers(),
    )
    assert resp.status_code == 400


def test_attendance_alerts_over_500_returns_400():
    recipients = [{"student_id": f"s{i}", "phone": "+919000000001"} for i in range(501)]
    resp = client.post(
        "/api/sms/whatsapp-attendance-alerts",
        json={"recipients": recipients},
        headers=_owner_headers(),
    )
    assert resp.status_code == 400


# ─── GET /api/sms/config-status — WhatsApp fields ─────────────────────────────

def test_config_status_includes_whatsapp_fields():
    env_override = {
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "tok",
        "TWILIO_PHONE_NUMBER": "+919000000000",
        "TWILIO_WHATSAPP_FROM": "+919000000000",
        "TWILIO_WHATSAPP_FEE_TEMPLATE_SID": "HXfee",
        "TWILIO_WHATSAPP_ATTENDANCE_TEMPLATE_SID": "HXatt",
    }
    with patch.dict(os.environ, env_override):
        resp = client.get("/api/sms/config-status", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "whatsapp_configured" in data
    assert data["whatsapp_configured"] is True
    assert data["whatsapp_from"] == "+919000000000"


def test_config_status_whatsapp_not_configured_when_template_sid_missing():
    env_override = {
        "TWILIO_ACCOUNT_SID": "ACtest",
        "TWILIO_AUTH_TOKEN": "tok",
        "TWILIO_PHONE_NUMBER": "+919000000000",
        "TWILIO_WHATSAPP_FROM": "+919000000000",
        "TWILIO_WHATSAPP_FEE_TEMPLATE_SID": "",
        "TWILIO_WHATSAPP_ATTENDANCE_TEMPLATE_SID": "",
    }
    with patch.dict(os.environ, env_override):
        resp = client.get("/api/sms/config-status", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["whatsapp_configured"] is False
    assert data["whatsapp_from"] is None


# ─── Normalize phone helper ────────────────────────────────────────────────────

def test_normalize_whatsapp_phone_adds_country_code():
    from routes.sms import _normalize_whatsapp_phone
    assert _normalize_whatsapp_phone("9876543210") == "+919876543210"


def test_normalize_whatsapp_phone_preserves_plus_prefix():
    from routes.sms import _normalize_whatsapp_phone
    assert _normalize_whatsapp_phone("+919876543210") == "+919876543210"


def test_normalize_whatsapp_phone_strips_leading_zero():
    from routes.sms import _normalize_whatsapp_phone
    assert _normalize_whatsapp_phone("09876543210") == "+919876543210"
