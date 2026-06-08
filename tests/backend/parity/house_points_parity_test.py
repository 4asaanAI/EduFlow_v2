"""Story B.3 — dual-entrypoint parity for house-points awards.

The AI `award_house_points` tool now updates the real standings (houses.points +
house_points_log + audit) identically to the panel, replacing the old un-audited
`house_points`-only write.
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _mask(docs):
    out = [{k: v for k, v in d.items() if k not in _VOLATILE} for d in docs]
    out.sort(key=lambda d: (d.get("house_id", ""), d.get("action", "")))
    return out


def _clear(fake_db):
    for col in ("houses", "house_points_log", "students", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


def _seed(fake_db):
    fake_db.houses.docs.append({"id": "h-1", "schoolId": "aaryans-joya", "name": "Blue", "points": 100})
    fake_db.students.docs.append({"id": "stu-1", "schoolId": "aaryans-joya", "name": "Alice",
                                  "house_id": "h-1", "is_active": True})


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


def _snapshot(fake_db):
    return {
        "houses": [{"id": d["id"], "points": d["points"]} for d in fake_db.houses.docs],
        "house_points_log": _mask(copy.deepcopy(fake_db.house_points_log.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("action") == "house_points_award"]),
    }


async def test_ai_and_rest_house_points_identical(client, fake_db, monkeypatch):
    _seed(fake_db)
    resp = client.post("/api/activities/houses/h-1/points",
                      json={"delta": 10, "reason": "Quiz win"}, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    _seed(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_award_house_points(
        {"student_name": "Alice", "points": 10, "reason": "Quiz win"}, OWNER_USER, None,
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    # B.3 regression guard: standings actually updated + audited (old path did neither).
    assert ai_state["houses"][0]["points"] == 110
    assert len(ai_state["house_points_log"]) == 1
    assert len(ai_state["audit_logs"]) == 1
    # Old un-audited collection is no longer written (it may not even exist anymore).
    legacy = getattr(fake_db, "house_points", None)
    assert legacy is None or len(legacy.docs) == 0
