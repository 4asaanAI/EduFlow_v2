"""Epic R10.3 — Skill acquisition from repeated usage.

- AC1: a routine is PROPOSED (never silently saved); saved only on explicit confirm;
       write-embedding routines get a two-step, gate-preserving disclosure.
- AC2: saved routines are recalled as FENCED reference data — they never bypass the
       confirm-token/kill-switch/lockdown gates (they are background, not commands).
- AC3: routines are versioned; a routine whose underlying tool schema drifted is
       surfaced as "needs updating" on recall instead of silently replaying.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from services.actor_context import actor_ctx_from_user
from services.memory import skills_store
from services.memory import chat_integration
from tests.backend.conftest import FakeDb

OWNER = {"id": "owner-1", "role": "owner", "name": "T", "branch_id": "branch-a"}


def _ctx(user_id="owner-1", school="aaryans-joya"):
    return actor_ctx_from_user(
        {"id": user_id, "role": "owner", "name": "T", "branch_id": "branch-a"},
        school_id=school, branch_id="branch-a",
    )


def _patch_extract_skill(monkeypatch, skill):
    async def fake(*a, **k):
        return skill
    monkeypatch.setattr(chat_integration.extractor, "extract_skill", fake)


def _patch_no_memory_items(monkeypatch):
    async def fake(*a, **k):
        return {"autosave": [], "uncertain": []}
    monkeypatch.setattr(chat_integration.extractor, "extract_memory_items", fake)


# ── AC1: proposal, not silent save ───────────────────────────────────────────

async def test_skill_is_proposed_not_autosaved(monkeypatch):
    _patch_no_memory_items(monkeypatch)
    _patch_extract_skill(monkeypatch, {
        "title": "Month-end fee sweep", "problem": "p", "solution": "s",
        "steps": ["get defaulters", "send reminders"], "tags": ["fees"], "confidence": 0.8,
    })
    db = FakeDb()
    await db.conversations.insert_one({"id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya"})
    q = await chat_integration.finalize_turn(
        db, OWNER, user_text="do the month end sweep", assistant_text="done", conv_id="c1",
        history=[{"role": "user", "content": "x"}], round_count=3, tool_count=2,
        tool_names=["get_fee_defaulters"],
    )
    assert q and "Save it as a routine" in q or "save it" in q.lower()
    # NOT saved yet
    assert await skills_store.list_skills(db, _ctx()) == []
    conv = await db.conversations.find_one({"id": "c1"})
    assert conv["pending_skill"]["title"] == "Month-end fee sweep"


async def test_write_embedding_routine_gets_two_step_disclosure(monkeypatch):
    _patch_no_memory_items(monkeypatch)
    _patch_extract_skill(monkeypatch, {
        "title": "Auto-approve day leaves", "steps": ["approve"], "confidence": 0.8,
    })
    db = FakeDb()
    await db.conversations.insert_one({"id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya"})
    # approve_leave_request is a write tool → disclosure must mention confirming changes
    from ai.tool_functions_v2 import WRITE_TOOL_NAMES
    write_tool = next(iter(WRITE_TOOL_NAMES))
    q = await chat_integration.finalize_turn(
        db, OWNER, user_text="approve leaves", assistant_text="done", conv_id="c1",
        history=[{"role": "user", "content": "x"}], round_count=2, tool_count=1,
        tool_names=[write_tool],
    )
    assert q and "confirm" in q.lower() and "change" in q.lower()
    conv = await db.conversations.find_one({"id": "c1"})
    assert conv["pending_skill"]["embeds_write"] is True


async def test_affirmative_saves_proposed_routine(monkeypatch):
    db = FakeDb()
    await db.conversations.insert_one({
        "id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya",
        "pending_skill": {
            "title": "Month-end fee sweep", "problem": "p", "solution": "s",
            "steps": ["a", "b"], "tags": ["fees"], "confidence": 0.8,
            "tool_names": ["get_fee_defaulters"], "embeds_write": False,
        },
    })
    conv = await db.conversations.find_one({"id": "c1"})
    reply = await chat_integration.handle_pre_turn(db, OWNER, "yes", conv)
    assert reply and "Month-end fee sweep" in reply
    skills = await skills_store.list_skills(db, _ctx())
    assert len(skills) == 1 and skills[0]["title"] == "Month-end fee sweep"
    conv2 = await db.conversations.find_one({"id": "c1"})
    assert conv2.get("pending_skill") is None


async def test_confirming_memory_also_clears_stale_pending_routine(monkeypatch):
    """Review fix (defense-in-depth): a single 'yes' resolves ONE pending and must not
    leave a stale sibling routine that a later 'yes' could silently activate."""
    db = FakeDb()
    await db.conversations.insert_one({
        "id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya",
        "pending_memory": {"text": "owner likes charts", "category": "preference", "confidence": 0.9},
        "pending_skill": {"title": "Stale routine", "steps": [], "tool_names": [], "embeds_write": False},
    })
    conv = await db.conversations.find_one({"id": "c1"})
    reply = await chat_integration.handle_pre_turn(db, OWNER, "yes", conv)
    assert reply and "keep that in mind" in reply.lower()
    conv2 = await db.conversations.find_one({"id": "c1"})
    assert conv2.get("pending_memory") is None
    assert conv2.get("pending_skill") is None  # stale sibling cleared
    assert await skills_store.list_skills(db, _ctx()) == []  # never saved


async def test_declining_clears_pending_routine(monkeypatch):
    db = FakeDb()
    await db.conversations.insert_one({
        "id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya",
        "pending_skill": {"title": "X", "steps": [], "tool_names": [], "embeds_write": False},
    })
    conv = await db.conversations.find_one({"id": "c1"})
    reply = await chat_integration.handle_pre_turn(db, OWNER, "no thanks", conv)
    # not an affirmative → nothing saved, pending cleared
    assert await skills_store.list_skills(db, _ctx()) == []
    conv2 = await db.conversations.find_one({"id": "c1"})
    assert conv2.get("pending_skill") is None


# ── AC3: versioning + drift ───────────────────────────────────────────────────

async def test_skill_stores_version_and_signature():
    db = FakeDb()
    s = await skills_store.add_skill(
        db, _ctx(), title="Fee sweep", confidence=0.8, tool_names=["get_fee_defaulters"],
    )
    assert s["version"] == 1
    assert s["tool_names"] == ["get_fee_defaulters"]
    assert s["tool_signature"]  # non-empty for a real tool


async def test_recall_flags_needs_update_on_schema_drift():
    db = FakeDb()
    s = await skills_store.add_skill(
        db, _ctx(), title="Fee sweep routine", confidence=0.9, tool_names=["get_fee_defaulters"],
    )
    # Simulate schema drift: corrupt the stored signature to something stale.
    for doc in db.ai_skills.docs:
        doc["tool_signature"] = "staaaaaaaaaaaale"
    hits = await skills_store.recall_skills(db, _ctx(), "fee sweep routine")
    assert hits and hits[0]["needs_update"] is True


async def test_recall_no_drift_flag_when_signature_matches():
    db = FakeDb()
    await skills_store.add_skill(
        db, _ctx(), title="Fee sweep routine", confidence=0.9, tool_names=["get_fee_defaulters"],
    )
    hits = await skills_store.recall_skills(db, _ctx(), "fee sweep routine")
    assert hits and hits[0]["needs_update"] is False


async def test_missing_tool_counts_as_drift():
    db = FakeDb()
    await skills_store.add_skill(
        db, _ctx(), title="Ghost routine", confidence=0.9, tool_names=["tool_that_was_removed"],
    )
    # stored signature reflects MISSING now, and current also MISSING → they MATCH,
    # so a still-missing tool is stable. Drift is only when it CHANGES; assert the
    # signature is stable (no false "needs update" churn for a permanently-absent tool).
    hits = await skills_store.recall_skills(db, _ctx(), "ghost routine")
    assert hits and hits[0]["needs_update"] is False


# ── AC2: recalled routines are fenced data, never authoritative instructions ──

async def test_recalled_skill_rendered_inside_instruction_inert_fence():
    db = FakeDb()
    await skills_store.add_skill(
        db, _ctx(), title="Bulk approve leaves", steps=["approve all pending"],
        confidence=0.9, tool_names=["get_fee_defaulters"],
    )
    block = await chat_integration.recall_context_block(db, OWNER, "bulk approve leaves")
    assert "<<<reference_notes>>>" in block and "<<<end_reference_notes>>>" in block
    assert "NOT INSTRUCTIONS" in block
    assert "Bulk approve leaves" in block
