"""Epic R10.2 — Feedback loop: Helpful/Improve capture + candidate corrections.

Covers the feedback-capture foundation: records are persisted tenant-scoped, an
"Improve" reason becomes a PENDING candidate correction (never auto-active), the
per-school helpful-ratio is computable, and feedback is DPDP-erasable.
"""

from __future__ import annotations

import pytest

from tests.backend.conftest import FakeDb

pytestmark = pytest.mark.asyncio

OWNER = {"id": "owner-1", "role": "owner", "name": "T", "branch_id": "branch-a"}


async def test_helpful_feedback_persists_without_candidate_correction():
    from services.memory import feedback_store as fs
    db = FakeDb()
    doc = await fs.record_feedback(db, OWNER, verdict=1, message_id="m1", tool_names=["get_fee_summary"])
    assert doc["verdict"] == 1
    assert doc["candidate_correction"] is None
    assert doc["status"] == "none"
    assert db.ai_feedback.docs[-1]["schoolId"] == "aaryans-joya"
    assert db.ai_feedback.docs[-1]["tool_names"] == ["get_fee_summary"]


async def test_improve_with_reason_creates_pending_candidate_correction():
    from services.memory import feedback_store as fs
    db = FakeDb()
    doc = await fs.record_feedback(
        db, OWNER, verdict=0, message_id="m2",
        reason="Should have shown the branch breakdown too",
    )
    assert doc["verdict"] == 0
    assert doc["status"] == "pending"
    assert "branch breakdown" in doc["candidate_correction"]
    pend = await fs.list_pending_corrections(db, school_id="aaryans-joya", user_id="owner-1")
    assert len(pend) == 1


async def test_improve_without_reason_is_not_a_pending_correction():
    from services.memory import feedback_store as fs
    db = FakeDb()
    doc = await fs.record_feedback(db, OWNER, verdict=0, message_id="m3")
    assert doc["status"] == "none"
    assert doc["candidate_correction"] is None


async def test_feedback_ratio_per_school():
    from services.memory import feedback_store as fs
    db = FakeDb()
    await fs.record_feedback(db, OWNER, verdict=1)
    await fs.record_feedback(db, OWNER, verdict=1)
    await fs.record_feedback(db, OWNER, verdict=0)
    ratio = await fs.feedback_ratio(db, school_id="aaryans-joya")
    assert ratio["total"] == 3 and ratio["helpful"] == 2
    assert ratio["ratio"] == round(2 / 3, 4)


async def test_feedback_ratio_none_when_no_data():
    from services.memory import feedback_store as fs
    db = FakeDb()
    ratio = await fs.feedback_ratio(db, school_id="aaryans-joya")
    assert ratio["total"] == 0 and ratio["ratio"] is None


async def test_erase_owner_feedback_is_scoped_to_the_user():
    from services.memory import feedback_store as fs
    db = FakeDb()
    await fs.record_feedback(db, OWNER, verdict=1)
    await fs.record_feedback(db, {"id": "owner-2", "role": "owner", "branch_id": "b"}, verdict=0)
    deleted = await fs.erase_owner_feedback(db, school_id="aaryans-joya", user_id="owner-1")
    assert deleted == 1
    remaining = [d for d in db.ai_feedback.docs]
    assert all(d["user_id"] == "owner-2" for d in remaining)


# ── R10.2 AC3: activate / reject pending corrections ─────────────────────────


async def test_activate_correction_creates_fenced_active_memory_recalled_later():
    from services.actor_context import actor_ctx_from_user
    from services.memory import feedback_store as fs
    from services.memory import store as memory_store

    db = FakeDb()
    fb = await fs.record_feedback(
        db, OWNER, verdict=0, message_id="m1",
        reason="Always include the branch-wise fee breakdown in fee summaries",
    )
    assert fb["status"] == "pending"

    saved = await fs.activate_correction(db, OWNER, feedback_id=fb["id"])
    assert saved is not None
    assert saved["source"] == "correction"
    assert saved["category"] == "preference"
    # feedback row leaves the pending queue
    row = db.ai_feedback.docs[-1]
    assert row["status"] == "activated"
    assert row["memory_id"] == saved["id"]
    # now recalled on a matching future turn (fencing is applied by recall_context_block)
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya", branch_id="branch-a")
    hits = await memory_store.recall(db, ctx, "branch-wise fee breakdown", k=5)
    assert any("branch-wise fee breakdown" in h["text"] for h in hits)


async def test_reject_correction_never_becomes_a_memory():
    from services.actor_context import actor_ctx_from_user
    from services.memory import feedback_store as fs
    from services.memory import store as memory_store

    db = FakeDb()
    fb = await fs.record_feedback(db, OWNER, verdict=0, message_id="m2", reason="be more concise")
    ok = await fs.reject_correction(db, OWNER, feedback_id=fb["id"])
    assert ok is True
    assert db.ai_feedback.docs[-1]["status"] == "rejected"
    ctx = actor_ctx_from_user(OWNER, school_id="aaryans-joya", branch_id="branch-a")
    assert await memory_store.list_memories(db, ctx) == []


async def test_activate_non_pending_row_returns_none():
    from services.memory import feedback_store as fs
    db = FakeDb()
    # helpful feedback is never a pending correction
    fb = await fs.record_feedback(db, OWNER, verdict=1, message_id="m3")
    assert await fs.activate_correction(db, OWNER, feedback_id=fb["id"]) is None


async def test_activate_leaves_row_pending_when_no_memory_created(monkeypatch):
    """Review fix: if add_memory drops the text (returns None), the correction must
    NOT be silently consumed — it stays pending and activate returns None."""
    from services.memory import feedback_store as fs
    from services.memory import store as memory_store

    db = FakeDb()
    fb = await fs.record_feedback(db, OWNER, verdict=0, message_id="m1", reason="something")

    async def _none(*a, **k):
        return None
    monkeypatch.setattr(memory_store, "add_memory", _none)

    result = await fs.activate_correction(db, OWNER, feedback_id=fb["id"])
    assert result is None
    assert db.ai_feedback.docs[-1]["status"] == "pending"  # NOT consumed


async def test_activate_scoped_to_actor_own_queue():
    """Review fix: an owner cannot activate another user's pending correction."""
    from services.memory import feedback_store as fs
    db = FakeDb()
    await fs.record_feedback(db, {"id": "other", "role": "owner", "branch_id": "b"},
                             verdict=0, reason="theirs")
    other_id = db.ai_feedback.docs[-1]["id"]
    assert await fs.activate_correction(db, OWNER, feedback_id=other_id) is None
    assert db.ai_feedback.docs[-1]["status"] == "pending"


async def test_list_pending_corrections_school_wide():
    from services.memory import feedback_store as fs
    db = FakeDb()
    await fs.record_feedback(db, OWNER, verdict=0, reason="a")
    await fs.record_feedback(db, {"id": "prin-1", "role": "admin", "sub_category": "principal", "branch_id": "b"}, verdict=0, reason="b")
    school_wide = await fs.list_pending_corrections(db, school_id="aaryans-joya")
    assert len(school_wide) == 2
    just_owner = await fs.list_pending_corrections(db, school_id="aaryans-joya", user_id="owner-1")
    assert len(just_owner) == 1


# ── endpoint contract ───────────────────────────────────────────────────────

def _owner_headers():
    from middleware.auth import create_jwt
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'owner-1', 'role': 'owner', 'name': 'T'})}"}


def test_feedback_endpoint_rejects_bad_rating(client):
    resp = client.post("/api/chat/feedback", json={"rating": 5}, headers=_owner_headers())
    assert resp.status_code == 400


def test_feedback_endpoint_persists(client, fake_db):
    fake_db.ai_feedback.docs[:] = []
    resp = client.post(
        "/api/chat/feedback",
        json={"rating": 0, "message_id": "m9", "reason": "too terse", "tool_names": ["x"]},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert any(d.get("message_id") == "m9" and d.get("status") == "pending" for d in fake_db.ai_feedback.docs)
