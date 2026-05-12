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
