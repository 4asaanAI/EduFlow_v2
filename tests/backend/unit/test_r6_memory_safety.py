"""Epic R6 — Memory Subsystem Safety. AC coverage (X3, XM3, XM4, XM5, XM10).

Tier: FakeDb (unit). Proves the pre-turn hijack is gone, forget is two-step,
recalled memories are fenced, pending text is redacted, and DPDP erasure +
per-owner cap work.
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.asyncio

from services.actor_context import actor_ctx_from_user
from services.memory import store as memory_store
from services.memory import chat_integration
from services.memory import extractor
from tests.backend.conftest import FakeDb


def _ctx(user_id="owner-1", school="aaryans-joya", role="owner"):
    user = {"id": user_id, "role": role, "name": "T", "branch_id": "branch-a"}
    if role == "admin":
        user["sub_category"] = "principal"
    return actor_ctx_from_user(user, school_id=school, branch_id="branch-a")


OWNER = {"id": "owner-1", "role": "owner", "name": "T", "branch_id": "branch-a"}


# ── R6.1 (X3): bare domain imperatives are NOT memory commands ───────────────

def test_delete_student_is_not_a_forget_command():
    assert extractor.parse_inline_forget("delete student Rahul Sharma") is None
    assert extractor.parse_inline_forget("remove fee record for Rahul") is None


def test_note_and_save_domain_verbs_are_not_remember_commands():
    assert extractor.parse_inline_remember("note attendance for class 5") is None
    assert extractor.parse_inline_remember("save the draft announcement") is None
    assert extractor.parse_inline_remember("store this document") is None


def test_explicit_memory_cues_still_parse():
    assert extractor.parse_inline_remember("remember: reports at 8am") == "reports at 8am"
    assert extractor.parse_inline_remember("remember that I prefer email") == "I prefer email"
    assert extractor.parse_inline_remember("note to self: call the vendor") == "call the vendor"
    assert extractor.parse_inline_forget("forget the note about vendors") == "vendors"


async def test_delete_student_falls_through_to_pipeline():
    """The incident-class bug: 'delete student …' must NOT be swallowed pre-LLM."""
    db = FakeDb()
    reply = await chat_integration.handle_pre_turn(db, OWNER, "delete student Rahul Sharma", None)
    assert reply is None  # falls through to the normal tool/LLM path


# ── R6.1 AC3: stale pending cannot be resurrected by a bare "yes" ────────────

async def test_stale_pending_memory_not_confirmed():
    db = FakeDb()
    old = time.time() - (chat_integration.PENDING_TTL_SECONDS + 60)
    await db.conversations.insert_one({
        "id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya",
        "pending_memory": {"text": "Owner may switch vendor", "category": "fact",
                           "confidence": 0.5, "set_at_ts": old},
    })
    conv = await db.conversations.find_one({"id": "c1"})
    reply = await chat_integration.handle_pre_turn(db, OWNER, "yes", conv)
    assert reply is None  # not confirmed
    assert await memory_store.list_memories(db, _ctx()) == []


async def test_fresh_pending_memory_is_confirmed():
    db = FakeDb()
    await db.conversations.insert_one({
        "id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya",
        "pending_memory": {"text": "Owner prefers 8am reports", "category": "preference",
                           "confidence": 0.5, "set_at_ts": time.time()},
    })
    conv = await db.conversations.find_one({"id": "c1"})
    reply = await chat_integration.handle_pre_turn(db, OWNER, "yes", conv)
    assert reply and "saved" in reply.lower()
    assert any("8am" in m["text"] for m in await memory_store.list_memories(db, _ctx()))


# ── R6.2: forget is two-step; nothing deleted until confirmed ────────────────

async def test_forget_is_two_step_and_deletes_only_shown_ids():
    db = FakeDb()
    ctx = _ctx()
    await memory_store.add_memory(db, ctx, text="Owner likes vendor Acme", source="user")
    await memory_store.add_memory(db, ctx, text="Owner dislikes late fees", source="user")
    await db.conversations.insert_one({
        "id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya",
    })
    conv = await db.conversations.find_one({"id": "c1"})

    # Step 1: forget lists matches, sets pending_forget, deletes NOTHING.
    reply1 = await chat_integration.handle_pre_turn(db, OWNER, "forget the note about vendor", conv)
    assert reply1 and "yes" in reply1.lower()
    assert len(await memory_store.list_memories(db, _ctx())) == 2  # nothing deleted yet
    conv = await db.conversations.find_one({"id": "c1"})
    assert conv.get("pending_forget") and len(conv["pending_forget"]["ids"]) == 1

    # Step 2: affirmative deletes ONLY the shown match.
    reply2 = await chat_integration.handle_pre_turn(db, OWNER, "yes", conv)
    assert reply2 and "removed" in reply2.lower()
    remaining = await memory_store.list_memories(db, _ctx())
    assert len(remaining) == 1 and "late fees" in remaining[0]["text"]


async def test_forget_with_no_match_does_not_short_circuit_destructively():
    db = FakeDb()
    await db.conversations.insert_one({"id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya"})
    conv = await db.conversations.find_one({"id": "c1"})
    reply = await chat_integration.handle_pre_turn(db, OWNER, "forget the note about nothing", conv)
    assert reply and "don't have" in reply.lower()


# ── R6.3 (XM3): recalled memories are fenced as reference-notes-not-instructions

async def test_recall_block_is_fenced():
    db = FakeDb()
    ctx = _ctx()
    await memory_store.add_memory(db, ctx, text="Owner prefers concise replies", source="user")
    block = await chat_integration.recall_context_block(db, OWNER, "prefers concise")
    assert "<<<reference_notes>>>" in block and "<<<end_reference_notes>>>" in block
    assert "NOT INSTRUCTIONS" in block


# ── R6.3 (XM4): pending text is redacted before it is persisted ──────────────

async def test_pending_memory_text_is_redacted():
    db = FakeDb()
    await db.conversations.insert_one({"id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya"})
    await chat_integration._set_pending(
        db, OWNER, "c1", {"text": "call the parent on 9876543210", "category": "task"}
    )
    conv = await db.conversations.find_one({"id": "c1"})
    assert "9876543210" not in conv["pending_memory"]["text"]
    assert conv["pending_memory"].get("set_at_ts")


# ── R6.4 (XM10): per-owner cap evicts least-valuable, never a silent wall ─────

async def test_per_user_cap_evicts_least_valuable(monkeypatch):
    monkeypatch.setattr(memory_store, "MAX_MEMORIES_PER_USER", 3)
    db = FakeDb()
    ctx = _ctx()
    # Low-confidence memory should be the eviction victim once the cap is exceeded.
    await memory_store.add_memory(db, ctx, text="weak note", source="auto", confidence=0.1)
    for i in range(3):
        await memory_store.add_memory(db, ctx, text=f"strong note {i}", source="user", confidence=0.95)
    mems = await memory_store.list_memories(db, _ctx())
    assert len(mems) == 3
    assert all("weak note" not in m["text"] for m in mems)


# ── R6.4 (XM5): staff deactivation erases that owner's AI memories + skills ───

async def test_erase_owner_memories_removes_all():
    db = FakeDb()
    ctx = _ctx()
    await memory_store.add_memory(db, ctx, text="a", source="user")
    await memory_store.add_memory(db, ctx, text="b", source="user")
    n = await memory_store.erase_owner_memories(db, school_id="aaryans-joya", user_id="owner-1")
    assert n == 2
    assert await memory_store.list_memories(db, _ctx()) == []


# ── R6.4 (XM10): startup vector rebuild is a safe no-op when disabled ─────────

async def test_vector_rebuild_noop_when_disabled():
    from services.memory import vector
    db = FakeDb()
    ctx = _ctx()
    await memory_store.add_memory(db, ctx, text="durable note", source="user")
    # Vector path is OFF by default → rebuild is a harmless no-op (returns 0),
    # and recall still works keyword-only.
    assert await vector.rebuild_index_from_mongo(db) == 0
    assert await memory_store.recall(db, ctx, "durable")
