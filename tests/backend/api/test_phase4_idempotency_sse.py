from datetime import datetime, timedelta, timezone

from middleware.auth import create_jwt


def _headers(role="owner", sub_category=None, user_id="owner-1", extra=None):
    payload = {"user_id": user_id, "role": role, "name": "Phase 4 User"}
    if sub_category:
        payload["sub_category"] = sub_category
    headers = {"Authorization": f"Bearer {create_jwt(payload)}"}
    if extra:
        headers.update(extra)
    return headers


def test_generic_idempotency_replays_mutating_endpoint_without_duplicate(client, fake_db, monkeypatch):
    fake_db.student_attendance.docs.clear()
    fake_db.idempotency_keys.docs.clear()
    monkeypatch.setenv("BIOMETRIC_ATTENDANCE_ENABLED", "false")
    headers = _headers(extra={"Idempotency-Key": "manual-attendance-2026-05-12"})
    payload = {
        "student_id": "student-1",
        "class_id": "class-1",
        "date": "2026-05-12",
        "status": "present",
        "reason": "Idempotency replay check",
    }

    first = client.post("/api/attendance", json=payload, headers=headers)
    second = client.post("/api/attendance", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers["X-Idempotent-Replay"] == "true"
    assert first.json() == second.json()
    assert len(fake_db.student_attendance.docs) == 1


def test_used_confirmation_token_replay_returns_409(client, fake_db):
    fake_db.confirm_tokens.docs[:] = [
        {
            "_id": "used-token",
            "token": "used-token",
            "action": "record_fee_payment",
            "params": {"student_id": "student-1"},
            "user_id": "owner-1",
            "session_id": "conv-1",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used": True,
        }
    ]

    response = client.post(
        "/api/chat/confirm",
        json={"token": "used-token", "session_id": "conv-1", "confirmed": True},
        headers=_headers(),
    )

    assert response.status_code == 409


def test_cross_session_confirmation_token_returns_401(client, fake_db):
    fake_db.confirm_tokens.docs[:] = [
        {
            "_id": "session-token",
            "token": "session-token",
            "action": "record_fee_payment",
            "params": {"student_id": "student-1"},
            "user_id": "owner-1",
            "session_id": "conv-1",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used": False,
        }
    ]

    response = client.post(
        "/api/chat/confirm",
        json={"token": "session-token", "session_id": "conv-2", "confirmed": True},
        headers=_headers(),
    )

    assert response.status_code == 401


def test_fee_stream_emits_snapshot_with_session_header(client, fake_db):
    fake_db.fee_transactions.docs[:] = [
        {
            "_id": "fee-1",
            "id": "fee-1",
            "schoolId": "aaryans-joya",
            "student_id": "student-1",
            "fee_period": "2026-05",
            "fee_head": "tuition",
            "amount": 100,
            "status": "paid",
        }
    ]

    with client.stream(
        "GET",
        "/api/fees/stream?keepalive=1&once=true",
        headers=_headers(extra={"X-SSE-Session-ID": "tab-fees-1"}),
    ) as response:
        assert response.status_code == 200
        line = next(response.iter_lines())

    assert line.startswith("data: ")
    assert '"type": "snapshot"' in line
    assert '"channel": "fees"' in line


def test_attendance_stream_emits_snapshot_with_session_header(client, fake_db):
    fake_db.staff_attendance.docs[:] = [
        {
            "_id": "att-1",
            "id": "att-1",
            "schoolId": "aaryans-joya",
            "staff_id": "staff-1",
            "date": "2026-05-12",
            "status": "present",
        }
    ]

    with client.stream(
        "GET",
        "/api/attendance/stream?keepalive=1&once=true",
        headers=_headers(extra={"X-SSE-Session-ID": "tab-attendance-1"}),
    ) as response:
        assert response.status_code == 200
        line = next(response.iter_lines())

    assert line.startswith("data: ")
    assert '"type": "snapshot"' in line
    assert '"channel": "attendance"' in line


def test_chat_message_stream_rejects_unowned_conversation_before_insert(client, fake_db):
    fake_db.conversations.docs[:] = [
        {"_id": "victim-conv", "id": "victim-conv", "schoolId": "aaryans-joya", "user_id": "other-user"},
    ]
    fake_db.messages.docs[:] = []

    response = client.post(
        "/api/chat/conversations/victim-conv/messages",
        json={"text": "hello", "session_id": "attacker-tab"},
        headers=_headers(user_id="owner-1"),
    )

    assert response.status_code == 404
    assert fake_db.messages.docs == []


def test_chat_action_rejects_unowned_conversation_before_insert(client, fake_db):
    fake_db.conversations.docs[:] = [
        {"_id": "victim-conv", "id": "victim-conv", "schoolId": "aaryans-joya", "user_id": "other-user"},
    ]
    fake_db.messages.docs[:] = []

    response = client.post(
        "/api/chat/conversations/victim-conv/action",
        json={"action": "get_school_pulse", "params": {}, "label": "Pulse"},
        headers=_headers(user_id="owner-1"),
    )

    assert response.status_code == 404
    assert fake_db.messages.docs == []


def test_chat_confirm_cancel_rejects_unowned_conversation_before_insert(client, fake_db):
    fake_db.conversations.docs[:] = [
        {"_id": "victim-conv", "id": "victim-conv", "schoolId": "aaryans-joya", "user_id": "other-user"},
    ]
    fake_db.messages.docs[:] = []

    response = client.post(
        "/api/chat/conversations/victim-conv/confirm",
        json={"confirmed": False, "decision": "cancel"},
        headers=_headers(user_id="owner-1"),
    )

    assert response.status_code == 404
    assert fake_db.messages.docs == []


def test_standalone_confirm_rejects_unowned_conversation_id_before_token_use(client, fake_db):
    token = "conv-pollution-token"
    fake_db.conversations.docs[:] = [
        {"_id": "owned-conv", "id": "owned-conv", "schoolId": "aaryans-joya", "user_id": "owner-1"},
        {"_id": "victim-conv", "id": "victim-conv", "schoolId": "aaryans-joya", "user_id": "other-user"},
    ]
    fake_db.confirm_tokens.docs[:] = [
        {
            "_id": token,
            "token": token,
            "action": "record_fee_payment",
            "params": {"student_id": "student-1", "amount": 1, "fee_head": "tuition", "mode": "cash"},
            "user_id": "owner-1",
            "session_id": "owned-conv",
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            "used": False,
        }
    ]

    response = client.post(
        "/api/chat/confirm",
        json={"token": token, "session_id": "owned-conv", "conversation_id": "victim-conv", "confirmed": True},
        headers=_headers(user_id="owner-1"),
    )

    assert response.status_code == 404
    assert fake_db.confirm_tokens.docs[0]["used"] is False
