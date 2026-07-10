from __future__ import annotations

"""R15 — Residual Confirmatory Sweep: HTTP-level regressions.

  * R15.5 (P-L7) manual attendance duplicate → idempotent / 409, never a 500
  * R15.5 (P-L8) house seeding is idempotent (no duplicate houses)
  * R15.4 (P-L5) seed-status is gated in production
  * R15.3/R15.5 (P-L9) assistant rate-limit (429) + token accounting + 503
"""

from types import SimpleNamespace

import pytest

from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


# ─── R15.5 (P-L7): manual attendance duplicate handling ─────────────────────

def test_manual_attendance_duplicate_is_idempotent_or_conflict(client, auth_headers, fake_db, monkeypatch):
    monkeypatch.setenv("BIOMETRIC_ATTENDANCE_ENABLED", "false")
    # Fresh collection carrying the real (student_id, date) unique index, isolated
    # from the shared session fake so we don't poison other attendance tests.
    fresh = FakeCollection()
    fresh.indexes["uniq_student_date"] = {
        "key": [("student_id", 1), ("date", 1)], "unique": True,
    }
    monkeypatch.setattr(fake_db, "student_attendance", fresh)

    payload = {
        "student_id": "student-1", "class_id": "class-1", "date": "2026-09-09",
        "status": "present", "reason": "Biometric terminal was offline",
    }
    r1 = client.post("/api/attendance", json=payload, headers=auth_headers)
    assert r1.status_code == 200

    # Same status → idempotent replay returns the existing record (NOT a 500).
    r2 = client.post("/api/attendance", json=payload, headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "present"
    assert len(fresh.docs) == 1  # no duplicate row

    # Different status → genuine conflict → 409 (caller must use /correct).
    r3 = client.post("/api/attendance", json={**payload, "status": "absent"}, headers=auth_headers)
    assert r3.status_code == 409
    assert len(fresh.docs) == 1


# ─── R15.5 (P-L8): idempotent house seeding ─────────────────────────────────

def test_house_seed_creates_four_distinct_houses(client, auth_headers, fake_db, monkeypatch):
    fresh = FakeCollection()
    monkeypatch.setattr(fake_db, "houses", fresh)

    r1 = client.get("/api/activities/houses", headers=auth_headers)
    assert r1.status_code == 200
    names = sorted(h["name"] for h in r1.json()["data"])
    assert names == ["Blue", "Green", "Red", "Yellow"]
    assert len(fresh.docs) == 4
    assert all(h.get("schoolId") for h in fresh.docs)  # seeded rows are tenant-tagged

    # A second load must not re-seed / duplicate.
    r2 = client.get("/api/activities/houses", headers=auth_headers)
    assert len(r2.json()["data"]) == 4
    assert len(fresh.docs) == 4


# ─── R15.4 (P-L5): seed-status gated in production ──────────────────────────

def test_seed_status_open_in_dev(client):
    r = client.get("/api/auth/seed-status")
    assert r.status_code == 200
    assert "auth_users" in r.json()


def test_seed_status_requires_owner_in_production(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert client.get("/api/auth/seed-status").status_code == 401
    assert client.get("/api/auth/seed-status", headers=_bearer({"user_id": "t1", "role": "teacher", "name": "T"})).status_code == 403
    assert client.get("/api/auth/seed-status", headers=_bearer({"user_id": "o1", "role": "owner", "name": "O"})).status_code == 200


# ─── R15.3/R15.5 (P-L9): assistant rate-limit + accounting + 503 ────────────

def _assistant_body():
    return {"messages": [{"role": "user", "content": "How do I collect a fee?"}]}


def test_assistant_records_token_usage(client, fake_db, monkeypatch):
    from routes import assistant
    from services import token_service

    assistant._assistant_calls.clear()
    monkeypatch.setattr(token_service, "get_db", lambda: fake_db)

    async def fake_chat(system, messages):
        return SimpleNamespace(ok=True, text="Open the Fee Tracker tool.", tokens=123)

    monkeypatch.setattr(assistant.llm_client, "chat", fake_chat)

    headers = _bearer({"user_id": "assist-acct-1", "role": "owner", "name": "O", "branch_id": "branch-a"})
    r = client.post("/api/assistant", json=_assistant_body(), headers=headers)
    assert r.status_code == 200
    assert r.json()["reply"] == "Open the Fee Tracker tool."

    entries = [d for d in fake_db.token_usage.docs
               if d.get("source") == "assistant" and d.get("user_id") == "assist-acct-1"]
    assert len(entries) == 1
    assert entries[0]["tokens_used"] == 123


def test_assistant_rate_limit_returns_429(client, fake_db, monkeypatch):
    from routes import assistant
    from services import token_service

    assistant._assistant_calls.clear()
    monkeypatch.setattr(token_service, "get_db", lambda: fake_db)

    async def fake_chat(system, messages):
        return SimpleNamespace(ok=True, text="ok", tokens=1)

    monkeypatch.setattr(assistant.llm_client, "chat", fake_chat)

    headers = _bearer({"user_id": "assist-rl-1", "role": "teacher", "name": "T"})
    for _ in range(assistant.ASSISTANT_HOURLY_LIMIT):
        assert client.post("/api/assistant", json=_assistant_body(), headers=headers).status_code == 200

    throttled = client.post("/api/assistant", json=_assistant_body(), headers=headers)
    assert throttled.status_code == 429
    assert throttled.json()["success"] is False


def test_assistant_unavailable_returns_503(client, monkeypatch):
    """R1.7 confirmation (P-L9 AC2): ok=False is a real 503, not success:true."""
    from routes import assistant

    assistant._assistant_calls.clear()

    async def fake_chat(system, messages):
        return SimpleNamespace(ok=False, text="", tokens=0)

    monkeypatch.setattr(assistant.llm_client, "chat", fake_chat)

    headers = _bearer({"user_id": "assist-503-1", "role": "admin", "name": "A"})
    r = client.post("/api/assistant", json=_assistant_body(), headers=headers)
    assert r.status_code == 503
    assert r.json()["success"] is False


def test_assistant_unauthenticated_returns_401(client):
    r = client.post("/api/assistant", json=_assistant_body())
    assert r.status_code == 401


def test_assistant_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "stu-1", "role": "student", "name": "S"})
    r = client.post("/api/assistant", json=_assistant_body(), headers=headers)
    assert r.status_code == 403
