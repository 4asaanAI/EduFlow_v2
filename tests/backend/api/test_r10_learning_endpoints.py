"""Epic R10.4 — "What I've learned" control-surface endpoints.

Covers AC1 (list + activate/reject + edit/deactivate/delete + two-step bulk delete),
AC3 (401 unauthenticated + 403 wrong-role on every endpoint; cross-tenant + cross-user
isolation). Tier: FakeDb via the `client`/`fake_db` fixtures.
"""

from __future__ import annotations

import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio

SCHOOL = "aaryans-joya"


def _owner():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'owner-1', 'role': 'owner', 'name': 'O'})}"}


def _principal():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'prin-1', 'role': 'admin', 'sub_category': 'principal', 'name': 'P'})}"}


def _teacher():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'tch-1', 'role': 'teacher', 'name': 'T'})}"}


@pytest.fixture(autouse=True)
def _seed(fake_db):
    fake_db.ai_memories.docs[:] = []
    fake_db.ai_skills.docs[:] = []
    fake_db.ai_feedback.docs[:] = []
    fake_db.ai_memories.docs.extend([
        {"id": "mem-a", "user_id": "owner-1", "schoolId": SCHOOL, "text": "owner prefers concise fee summaries",
         "category": "preference", "superseded": False, "confidence": 0.8, "updated_at_ts": 100.0, "created_at_ts": 100.0},
        # cross-tenant: same user, different school → must never surface
        {"id": "mem-other-school", "user_id": "owner-1", "schoolId": "other-school", "text": "leak me",
         "category": "fact", "superseded": False, "confidence": 0.8, "updated_at_ts": 100.0},
        # cross-user: same school, different user → must never surface
        {"id": "mem-other-user", "user_id": "someone-else", "schoolId": SCHOOL, "text": "not owners note",
         "category": "fact", "superseded": False, "confidence": 0.8, "updated_at_ts": 100.0},
    ])
    fake_db.ai_skills.docs.append(
        {"id": "skill-a", "user_id": "owner-1", "schoolId": SCHOOL, "title": "Month-end sweep",
         "steps": ["a"], "tool_names": ["get_fee_defaulters"], "tool_signature": "x", "version": 1,
         "confidence": 0.8, "updated_at_ts": 100.0}
    )
    fake_db.ai_feedback.docs.extend([
        {"id": "fb-1", "_id": "fb-1", "schoolId": SCHOOL, "user_id": "owner-1", "verdict": 0,
         "candidate_correction": "always include branch breakdown", "status": "pending",
         "conversation_id": "c1", "message_id": "m1", "tool_names": [], "created_at": "2026-07-10T00:00:00+00:00"},
        # another staff member's pending Improve note — must NOT surface to owner-1
        {"id": "fb-other", "_id": "fb-other", "schoolId": SCHOOL, "user_id": "someone-else", "verdict": 0,
         "candidate_correction": "someone else private note", "status": "pending",
         "tool_names": [], "created_at": "2026-07-10T00:00:00+00:00"},
    ])
    yield
    fake_db.ai_memories.docs[:] = []
    fake_db.ai_skills.docs[:] = []
    fake_db.ai_feedback.docs[:] = []


# ── AC3: 401 unauthenticated + 403 wrong-role on every endpoint ──────────────

ENDPOINTS = [
    ("get", "/api/learning/overview", None),
    ("post", "/api/learning/corrections/fb-1/activate", {}),
    ("post", "/api/learning/corrections/fb-1/reject", {}),
    ("patch", "/api/learning/memories/mem-a", {"text": "x"}),
    ("post", "/api/learning/memories/mem-a/deactivate", {}),
    ("delete", "/api/learning/memories/mem-a", None),
    ("post", "/api/learning/memories/bulk-delete", {"ids": ["mem-a"]}),
    ("delete", "/api/learning/skills/skill-a", None),
]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_endpoint_unauthenticated_returns_401(client, method, path, body):
    resp = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_endpoint_wrong_role_returns_403(client, method, path, body):
    kw = {"headers": _teacher()}
    if body is not None:
        kw["json"] = body
    resp = getattr(client, method)(path, **kw)
    assert resp.status_code == 403


# ── AC1: functional behavior (owner) ─────────────────────────────────────────

def test_overview_lists_only_this_owner_this_school(client, fake_db):
    resp = client.get("/api/learning/overview", headers=_owner())
    assert resp.status_code == 200
    data = resp.json()["data"]
    mem_ids = [m["id"] for m in data["memories"]]
    assert mem_ids == ["mem-a"]  # not the cross-school or cross-user rows
    assert len(data["skills"]) == 1
    assert len(data["pending_corrections"]) == 1


def test_principal_also_allowed(client, fake_db):
    resp = client.get("/api/learning/overview", headers=_principal())
    assert resp.status_code == 200


def test_activate_correction_promotes_to_memory(client, fake_db):
    resp = client.post("/api/learning/corrections/fb-1/activate", headers=_owner())
    assert resp.status_code == 200
    assert any(m.get("source") == "correction" and "branch breakdown" in (m.get("text") or "")
               for m in fake_db.ai_memories.docs)
    assert next(f for f in fake_db.ai_feedback.docs if f["id"] == "fb-1")["status"] == "activated"


def test_activate_unknown_correction_404(client, fake_db):
    resp = client.post("/api/learning/corrections/nope/activate", headers=_owner())
    assert resp.status_code == 404


def test_reject_correction(client, fake_db):
    resp = client.post("/api/learning/corrections/fb-1/reject", headers=_owner())
    assert resp.status_code == 200
    assert next(f for f in fake_db.ai_feedback.docs if f["id"] == "fb-1")["status"] == "rejected"


def test_edit_memory(client, fake_db):
    resp = client.patch("/api/learning/memories/mem-a", json={"text": "owner likes charts"}, headers=_owner())
    assert resp.status_code == 200
    assert any(m["id"] == "mem-a" and "charts" in m["text"] for m in fake_db.ai_memories.docs)


def test_edit_memory_requires_text(client, fake_db):
    resp = client.patch("/api/learning/memories/mem-a", json={"text": "  "}, headers=_owner())
    assert resp.status_code == 400


def test_deactivate_memory_excludes_from_overview(client, fake_db):
    assert client.post("/api/learning/memories/mem-a/deactivate", headers=_owner()).status_code == 200
    assert next(m for m in fake_db.ai_memories.docs if m["id"] == "mem-a")["superseded"] is True
    data = client.get("/api/learning/overview", headers=_owner()).json()["data"]
    assert [m["id"] for m in data["memories"]] == []


def test_delete_memory(client, fake_db):
    assert client.delete("/api/learning/memories/mem-a", headers=_owner()).status_code == 200
    assert not any(m["id"] == "mem-a" for m in fake_db.ai_memories.docs)


def test_delete_skill(client, fake_db):
    assert client.delete("/api/learning/skills/skill-a", headers=_owner()).status_code == 200
    assert not any(s["id"] == "skill-a" for s in fake_db.ai_skills.docs)


def test_bulk_delete_is_two_step(client, fake_db):
    # step 1: no confirm → preview only, nothing deleted
    r1 = client.post("/api/learning/memories/bulk-delete", json={"ids": ["mem-a"]}, headers=_owner())
    assert r1.status_code == 200 and r1.json()["data"]["confirm_required"] is True
    assert any(m["id"] == "mem-a" for m in fake_db.ai_memories.docs)
    # step 2: confirm → actually deletes
    r2 = client.post("/api/learning/memories/bulk-delete", json={"ids": ["mem-a"], "confirm": True}, headers=_owner())
    assert r2.status_code == 200 and r2.json()["data"]["removed"] == 1
    assert not any(m["id"] == "mem-a" for m in fake_db.ai_memories.docs)


def test_cross_tenant_memory_cannot_be_deleted(client, fake_db):
    # owner-1 in aaryans-joya must not be able to touch the other-school row
    resp = client.delete("/api/learning/memories/mem-other-school", headers=_owner())
    assert resp.status_code == 404
    assert any(m["id"] == "mem-other-school" for m in fake_db.ai_memories.docs)


# ── epic-close review regressions ────────────────────────────────────────────

def test_overview_pending_scoped_to_reviewer_only(client, fake_db):
    """Review fix: another staff member's raw Improve note must NOT leak to owner-1."""
    data = client.get("/api/learning/overview", headers=_owner()).json()["data"]
    ids = [c["id"] for c in data["pending_corrections"]]
    assert ids == ["fb-1"]  # not fb-other
    assert not any("someone else private note" in (c.get("candidate_correction") or "")
                   for c in data["pending_corrections"])


def test_activate_anothers_correction_is_404(client, fake_db):
    """Review fix: owner-1 cannot activate someone-else's pending correction by id."""
    resp = client.post("/api/learning/corrections/fb-other/activate", headers=_owner())
    assert resp.status_code == 404
    # untouched, and no memory created for owner-1
    assert next(f for f in fake_db.ai_feedback.docs if f["id"] == "fb-other")["status"] == "pending"


def test_bulk_delete_rejects_non_list_ids(client, fake_db):
    resp = client.post("/api/learning/memories/bulk-delete", json={"ids": "mem-a"}, headers=_owner())
    assert resp.status_code == 400


def test_bulk_delete_rejects_too_many_ids(client, fake_db):
    resp = client.post("/api/learning/memories/bulk-delete",
                       json={"ids": [f"m{i}" for i in range(101)], "confirm": True}, headers=_owner())
    assert resp.status_code == 400
    # nothing deleted
    assert any(m["id"] == "mem-a" for m in fake_db.ai_memories.docs)


def test_edit_memory_missing_body_is_400_not_500(client, fake_db):
    resp = client.patch("/api/learning/memories/mem-a", headers=_owner())
    assert resp.status_code == 400


def test_overview_separates_deactivated_and_supports_reactivate(client, fake_db):
    assert client.post("/api/learning/memories/mem-a/deactivate", headers=_owner()).status_code == 200
    data = client.get("/api/learning/overview", headers=_owner()).json()["data"]
    assert [m["id"] for m in data["memories"]] == []
    assert [m["id"] for m in data["deactivated_memories"]] == ["mem-a"]
    # reactivate (superseded=false) brings it back to the active list
    r = client.post("/api/learning/memories/mem-a/deactivate", json={"superseded": False}, headers=_owner())
    assert r.status_code == 200
    data2 = client.get("/api/learning/overview", headers=_owner()).json()["data"]
    assert [m["id"] for m in data2["memories"]] == ["mem-a"]
