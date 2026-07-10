from types import SimpleNamespace

import pytest

from middleware.auth import create_jwt
from routes import sms as sms_routes


def _headers(role="owner", sub_category=None):
    payload = {"id": f"{role}-1", "role": role, "name": role.title()}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _sms_db(monkeypatch, fake_db):
    fake_db.sms_logs.docs[:] = []
    fake_db.students.docs[:] = [
        {"id": "stu-1", "schoolId": "aaryans-joya", "name": "Asha"},
        {"id": "stu-2", "schoolId": "aaryans-joya", "name": "Ravi"},
    ]
    monkeypatch.setattr(sms_routes, "get_db", lambda: fake_db)
    return fake_db


def test_sms_reminder_logs_not_configured_status(client, fake_db, monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_PHONE_NUMBER", raising=False)

    response = client.post(
        "/api/sms/send-reminder",
        headers=_headers(),
        json={
            "student_id": "stu-1",
            "student_name": "Asha",
            "phone": "9876543210",
            "message": "Fee reminder",
            "amount": 1200,
        },
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "not_configured"
    assert fake_db.sms_logs.docs[0]["status"] == "not_configured"
    assert fake_db.sms_logs.docs[0]["schoolId"]
    assert fake_db.sms_logs.docs[0]["created_at"]


def test_sms_reminder_with_mocked_twilio_logs_sent(client, fake_db, monkeypatch):
    class Messages:
        def create(self, **kwargs):
            assert kwargs["to"] == "+919876543210"
            return SimpleNamespace(sid="SM123")

    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+15551234567")
    monkeypatch.setattr(sms_routes, "get_twilio_client", lambda: SimpleNamespace(messages=Messages()))

    response = client.post(
        "/api/sms/send-reminder",
        headers=_headers("admin", "accountant"),
        json={
            "student_id": "stu-1",
            "student_name": "Asha",
            "phone": "9876543210",
            "message": "Fee reminder",
            "amount": 1200,
        },
    )

    assert response.status_code == 200
    log = fake_db.sms_logs.docs[0]
    assert log["status"] == "sent"
    assert log["sms_sid"] == "SM123"
    assert log["student_id"] == "stu-1"
    assert log["phone"] == "9876543210"
    assert log["message"] == "Fee reminder"
    assert log["schoolId"]


def test_sms_bulk_limit_rejects_large_request(client):
    recipients = [{"student_id": f"stu-{idx}", "phone": "9876543210"} for idx in range(501)]

    response = client.post(
        "/api/sms/send-bulk",
        headers=_headers(),
        json={"recipients": recipients, "message_template": "Hello {name}"},
    )

    assert response.status_code == 400
    assert "500" in response.json()["detail"]


def test_sms_bulk_logs_each_recipient_when_not_configured(client, fake_db, monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_PHONE_NUMBER", raising=False)

    response = client.post(
        "/api/sms/send-bulk",
        headers=_headers(),
        json={
            "recipients": [
                {"student_id": "stu-1", "student_name": "Asha", "phone": "9876543210", "amount": 100},
                {"student_id": "stu-2", "student_name": "Ravi", "phone": "9876543211", "amount": 200},
            ],
            "message_template": "Hi {name}, pay {amount}",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["not_configured"] == 2
    assert len(fake_db.sms_logs.docs) == 2
    assert fake_db.sms_logs.docs[0]["message"] == "Hi Asha, pay 100"


def test_sms_config_status_reflects_environment(client, monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_PHONE_NUMBER", raising=False)

    missing = client.get("/api/sms/config-status", headers=_headers())
    assert missing.status_code == 200
    assert missing.json()["data"]["configured"] is False

    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+15551234567")

    configured = client.get("/api/sms/config-status", headers=_headers())
    assert configured.status_code == 200
    data = configured.json()["data"]
    assert data["configured"] is True
    assert data["phone_number"] == "+15551234567"
