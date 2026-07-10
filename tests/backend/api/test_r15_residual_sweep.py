from __future__ import annotations

"""R15 — Residual Confirmatory Sweep: HTTP-level regressions.

  * R15.5 (P-L7) manual attendance duplicate → idempotent / 409, never a 500
  * R15.5 (P-L8) house seeding is idempotent (no duplicate houses)
  * R15.4 (P-L5) seed-status is gated in production

Note: the R15.3/R15.5 (P-L9) in-app help assistant (`/api/assistant`) was retired
after R15 (redundant with the main AI chat), so its tests were removed with it.
"""

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
