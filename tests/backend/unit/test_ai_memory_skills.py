"""Epic G — AI self-learning (Memory + Skills). Story-by-story AC coverage.

Tier: FakeDb (unit). Tenant/owner isolation is asserted by querying the store with
different (user_id, schoolId) scopes — FakeDb does NOT auto-scope, so any leak would
show up here. Vector path is OFF by default (MEMORY_VECTOR_ENABLED unset) so these
also prove the keyword-only graceful-degradation path (FR33).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.asyncio

from services.actor_context import actor_ctx_from_user
from services.memory import store as memory_store
from services.memory import skills_store
from services.memory import retrieval
from services.memory import extractor
from services.memory import chat_integration
from services.memory import is_memory_subject
from tests.backend.conftest import FakeDb


def _ctx(user_id="owner-1", school="aaryans-joya", role="owner", now=None):
    user = {"id": user_id, "role": role, "name": "T", "branch_id": "branch-a"}
    if role == "admin":
        user["sub_category"] = "principal"
    now_fn = (lambda: now) if now else None
    return actor_ctx_from_user(user, school_id=school, branch_id="branch-a", now_fn=now_fn)


# ── G.2: owner-scoped memory store, redaction, isolation ──────────────────────

async def test_g2_memory_write_redacts_pii():
    db = FakeDb()
    ctx = _ctx()
    saved = await memory_store.add_memory(
        db, ctx, text="Owner prefers fee reminders; reach him at 9876543210 / a@b.com", source="auto"
    )
    assert saved is not None
    assert "9876543210" not in saved["text"]
    assert "a@b.com" not in saved["text"]
    assert "[restricted in chat]" in saved["text"]


async def test_g2_owner_isolation():
    db = FakeDb()
    await memory_store.add_memory(db, _ctx("owner-1"), text="owner one secret note")
    await memory_store.add_memory(db, _ctx("owner-2"), text="owner two private note")
    one = await memory_store.list_memories(db, _ctx("owner-1"))
    assert len(one) == 1
    assert one[0]["text"] == "owner one secret note"


async def test_g2_tenant_isolation():
    db = FakeDb()
    await memory_store.add_memory(db, _ctx("owner-1", school="aaryans-joya"), text="aaryans note")
    await memory_store.add_memory(db, _ctx("owner-1", school="other-school"), text="other school note")
    aaryans = await memory_store.list_memories(db, _ctx("owner-1", school="aaryans-joya"))
    assert [m["text"] for m in aaryans] == ["aaryans note"]


async def test_g2_dedup_bumps_uses():
    db = FakeDb()
    ctx = _ctx()
    await memory_store.add_memory(db, ctx, text="same fact")
    await memory_store.add_memory(db, ctx, text="same fact")
    mems = await memory_store.list_memories(db, ctx)
    assert len(mems) == 1
    assert mems[0]["uses"] == 1


# ── G.3: hybrid recall (keyword fallback) ─────────────────────────────────────

async def test_g3_recall_returns_relevant_and_increments_uses():
    db = FakeDb()
    ctx = _ctx()
    await memory_store.add_memory(db, ctx, text="Owner wants weekly fee defaulter reports")
    await memory_store.add_memory(db, ctx, text="The annual sports day is in December")
    hits = await memory_store.recall(db, ctx, "show me fee defaulters")
    assert hits, "expected at least one keyword-relevant memory"
    assert "fee defaulter" in hits[0]["text"].lower()
    # uses incremented on the returned memory
    mems = await memory_store.list_memories(db, ctx)
    fee_mem = [m for m in mems if "defaulter" in m["text"].lower()][0]
    assert fee_mem["uses"] == 1


async def test_g3_recall_keyword_only_when_vector_disabled():
    from services.memory.vector import get_memory_vector_store

    assert get_memory_vector_store().healthy is False  # off by default → graceful
    db = FakeDb()
    ctx = _ctx()
    await memory_store.add_memory(db, ctx, text="Principal reviews leave requests on Mondays")
    hits = await memory_store.recall(db, ctx, "leave requests review")
    assert hits and "leave" in hits[0]["text"].lower()


# ── G.4: auto-save + uncertain confirm + inline commands ──────────────────────

def _patch_llm(monkeypatch, payload):
    from ai.llm_client import LLMResult
    async def fake_chat(system_prompt, messages, session_id=None, role=None):
        return LLMResult(text=payload, tokens=5, ok=True)  # R1.7: LLMResult, not tuple
    monkeypatch.setattr("services.memory.extractor.llm_client.chat", fake_chat)


async def test_g4_extract_splits_autosave_and_uncertain(monkeypatch):
    _patch_llm(monkeypatch, '{"items": ['
        '{"text": "Owner prefers concise morning briefs", "category": "preference", "confidence": 0.9},'
        '{"text": "Owner might be planning a new branch", "category": "fact", "confidence": 0.55},'
        '{"text": "trivial", "category": "fact", "confidence": 0.1}]}')
    out = await extractor.extract_memory_items("u", "a")
    assert [i["text"] for i in out["autosave"]] == ["Owner prefers concise morning briefs"]
    assert [i["text"] for i in out["uncertain"]] == ["Owner might be planning a new branch"]


async def test_g4_finalize_autosaves_and_asks_uncertain(monkeypatch):
    _patch_llm(monkeypatch, '{"items": ['
        '{"text": "Owner prefers Hindi summaries", "category": "preference", "confidence": 0.85},'
        '{"text": "Owner may switch fee vendor", "category": "fact", "confidence": 0.5}]}')
    # skill extractor also calls the LLM; with rounds/tools=0 it short-circuits to None.
    db = FakeDb()
    user = {"id": "owner-1", "role": "owner", "name": "T", "branch_id": "branch-a"}
    await db.conversations.insert_one({"id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya"})
    q = await chat_integration.finalize_turn(
        db, user, user_text="hi", assistant_text="hello", conv_id="c1",
        history=[], round_count=0, tool_count=0,
    )
    assert q and "Owner may switch fee vendor" in q
    mems = await memory_store.list_memories(db, _ctx())
    assert any("Hindi summaries" in m["text"] for m in mems)
    conv = await db.conversations.find_one({"id": "c1"})
    assert conv["pending_memory"]["text"] == "Owner may switch fee vendor"


async def test_g4_inline_remember_command():
    db = FakeDb()
    user = {"id": "owner-1", "role": "owner", "name": "T", "branch_id": "branch-a"}
    reply = await chat_integration.handle_pre_turn(db, user, "remember: I like reports at 8am", None)
    assert reply and "remember" in reply.lower()
    mems = await memory_store.list_memories(db, _ctx())
    assert len(mems) == 1 and "8am" in mems[0]["text"]


async def test_g4_affirmative_confirms_pending():
    db = FakeDb()
    user = {"id": "owner-1", "role": "owner", "name": "T", "branch_id": "branch-a"}
    await db.conversations.insert_one({
        "id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya",
        "pending_memory": {"text": "Owner may switch vendor", "category": "fact", "confidence": 0.5},
    })
    conv = await db.conversations.find_one({"id": "c1"})
    reply = await chat_integration.handle_pre_turn(db, user, "yes", conv)
    assert reply and "saved" in reply.lower()
    mems = await memory_store.list_memories(db, _ctx())
    assert any("switch vendor" in m["text"] for m in mems)
    conv2 = await db.conversations.find_one({"id": "c1"})
    assert conv2.get("pending_memory") is None


async def test_g4_non_owner_excluded_from_self_learning():
    db = FakeDb()
    teacher = {"id": "t-1", "role": "teacher", "name": "T"}
    assert is_memory_subject(teacher) is False
    reply = await chat_integration.handle_pre_turn(db, teacher, "remember: x", None)
    assert reply is None
    block = await chat_integration.recall_context_block(db, teacher, "anything")
    assert block == ""


async def test_g4_no_memory_ui_surface_exists():
    """FR32: no memory/skills HTTP surface anywhere."""
    import server

    paths = [getattr(r, "path", "") for r in server.app.routes]
    offenders = [p for p in paths if "/memory" in p.lower() or "/skills" in p.lower()]
    assert offenders == [], f"unexpected memory/skills routes: {offenders}"


# ── Regression: conservative intent detection (epic-close review) ────────────

async def test_reg_affirmative_does_not_swallow_real_request():
    # Bug: a request that merely starts with "ok" was treated as a bare yes and
    # swallowed the user's actual ask. These must NOT be affirmative.
    assert extractor.is_affirmative("ok show me the fees") is False
    assert extractor.is_affirmative("sure, but first list defaulters") is False
    # genuine bare confirmations still are
    assert extractor.is_affirmative("yes") is True
    assert extractor.is_affirmative("yes please") is True
    assert extractor.is_affirmative("ok") is True


async def test_reg_correction_detection_is_conservative():
    # Bug: bare mid-sentence "actually" deleted a relevant memory. Must NOT trigger.
    assert extractor.looks_like_correction("actually, show me attendance") is False
    assert extractor.looks_like_correction("can you actually open the fee panel") is False
    # explicit corrections still trigger
    assert extractor.looks_like_correction("that's not right") is True
    assert extractor.looks_like_correction("no, that's wrong") is True


async def test_reg_affirmative_request_not_short_circuited():
    """An 'ok <request>' with a pending memory must let the turn proceed (return
    None), not save-and-swallow."""
    db = FakeDb()
    user = {"id": "owner-1", "role": "owner", "name": "T", "branch_id": "branch-a"}
    await db.conversations.insert_one({
        "id": "c1", "user_id": "owner-1", "schoolId": "aaryans-joya",
        "pending_memory": {"text": "Owner may switch vendor", "category": "fact", "confidence": 0.5},
    })
    conv = await db.conversations.find_one({"id": "c1"})
    reply = await chat_integration.handle_pre_turn(db, user, "ok show me the fees", conv)
    assert reply is None  # turn proceeds normally
    # pending was cleared (not confirmed) and the memory was NOT saved
    assert await memory_store.list_memories(db, _ctx()) == []


async def test_reg_skill_text_pii_scrubbed():
    db = FakeDb()
    ctx = _ctx()
    s = await skills_store.add_skill(
        db, ctx, title="Call guardian 9876543210", confidence=0.8,
        steps=["email a@b.com", "note it"],
    )
    assert "9876543210" not in s["title"]
    assert "a@b.com" not in s["steps"][0]


# ── G.5: on-demand recall & synthesis (authorization parity) ──────────────────

async def test_g5_recall_history_gated_to_owner_principal():
    from routes.chat import _is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    tool = TOOL_REGISTRY["recall_history"]
    assert _is_tool_authorized({"id": "o", "role": "owner"}, tool) is True
    assert _is_tool_authorized({"id": "p", "role": "admin", "sub_category": "principal"}, tool) is True
    # an accountant admin is NOT a memory subject and must be refused
    assert _is_tool_authorized({"id": "a", "role": "admin", "sub_category": "accountant"}, tool) is False


async def test_g5_recall_history_in_minor_read_audit_set():
    from routes.chat import MINOR_READ_TOOLS

    assert "recall_history" in MINOR_READ_TOOLS


# ── G.6: skill auto-extraction + feedback ─────────────────────────────────────

async def test_g6_skill_below_complexity_threshold_dropped(monkeypatch):
    called = {"n": 0}

    from ai.llm_client import LLMResult
    async def fake_chat(*a, **k):
        called["n"] += 1
        return LLMResult(text="{}", tokens=1, ok=True)  # R1.7: LLMResult, not tuple
    monkeypatch.setattr("services.memory.extractor.llm_client.chat", fake_chat)
    out = await extractor.extract_skill([{"role": "user", "content": "hi"}], round_count=1, tool_count=1)
    assert out is None
    assert called["n"] == 0  # never even calls the LLM below threshold


async def test_g6_add_skill_drops_low_confidence_and_dupes():
    db = FakeDb()
    ctx = _ctx()
    assert await skills_store.add_skill(db, ctx, title="Weak", confidence=0.3) is None
    first = await skills_store.add_skill(db, ctx, title="Bulk fee reminder", confidence=0.8)
    assert first is not None
    dup = await skills_store.add_skill(db, ctx, title="bulk fee reminder", confidence=0.9)
    assert dup is None
    assert len(await skills_store.list_skills(db, ctx)) == 1


async def test_g6_skill_feedback_and_isolation():
    db = FakeDb()
    ctx = _ctx("owner-1")
    s = await skills_store.add_skill(db, ctx, title="Publish notice", confidence=0.8)
    assert await skills_store.record_feedback(db, ctx, skill_id=s["id"], helpful=True) is True
    # other owner cannot give feedback on this skill
    assert await skills_store.record_feedback(db, _ctx("owner-2"), skill_id=s["id"], helpful=True) is False
    refreshed = (await skills_store.list_skills(db, ctx))[0]
    assert refreshed["helpful"] == 1


# ── G.7: erasure & retention ──────────────────────────────────────────────────

async def test_g7_erase_owner_memories():
    db = FakeDb()
    await memory_store.add_memory(db, _ctx("owner-1"), text="a")
    await memory_store.add_memory(db, _ctx("owner-1"), text="b")
    await memory_store.add_memory(db, _ctx("owner-2"), text="keep me")
    n = await memory_store.erase_owner_memories(db, school_id="aaryans-joya", user_id="owner-1")
    assert n == 2
    assert await memory_store.list_memories(db, _ctx("owner-1")) == []
    assert len(await memory_store.list_memories(db, _ctx("owner-2"))) == 1


async def test_g7_purge_student_references():
    db = FakeDb()
    await memory_store.add_memory(db, _ctx(), text="family X owes fees", student_refs=["stu-9"])
    await memory_store.add_memory(db, _ctx(), text="unrelated note")
    n = await memory_store.purge_student_references(db, school_id="aaryans-joya", student_id="stu-9")
    assert n == 1
    remaining = await memory_store.list_memories(db, _ctx())
    assert [m["text"] for m in remaining] == ["unrelated note"]


async def test_g7_retention_prune_expired():
    db = FakeDb()
    old = datetime(2020, 1, 1)
    await memory_store.add_memory(db, _ctx(now=old), text="ancient memory")
    await memory_store.add_memory(db, _ctx(), text="fresh memory")
    pruned = await memory_store.prune_expired(db, _ctx())  # ctx.now defaults to real now
    assert pruned == 1
    remaining = await memory_store.list_memories(db, _ctx())
    assert [m["text"] for m in remaining] == ["fresh memory"]


# ── G.8: correction & confidence/recency decay ────────────────────────────────

async def test_g8_correct_memory_removes():
    db = FakeDb()
    ctx = _ctx()
    await memory_store.add_memory(db, ctx, text="Owner dislikes SMS reminders")
    res = await memory_store.correct_memory(db, ctx, match_text="SMS reminders")
    assert res["removed"] == 1
    assert await memory_store.list_memories(db, ctx) == []


async def test_g8_correct_memory_updates_and_boosts_confidence():
    db = FakeDb()
    ctx = _ctx()
    m = await memory_store.add_memory(db, ctx, text="Owner has 2 branches", confidence=0.6)
    res = await memory_store.correct_memory(db, ctx, memory_id=m["id"], new_text="Owner has 3 branches")
    assert res["updated"] == 1
    mems = await memory_store.list_memories(db, ctx)
    assert mems[0]["text"] == "Owner has 3 branches"
    assert mems[0]["confidence"] >= 0.9


async def test_g8_recency_and_confidence_decay_ranking():
    now = datetime(2026, 6, 8, 12, 0, 0).timestamp()
    fresh = {"text": "owner likes fee reports", "confidence": 0.9, "updated_at_ts": now}
    stale = {"text": "owner likes fee reports", "confidence": 0.3,
             "updated_at_ts": now - 400 * 24 * 3600}
    ranked = retrieval.score_memories("fee reports", [stale, fresh], now=now)
    assert ranked[0] is not None
    assert ranked[0]["text"] == "owner likes fee reports"
    # fresh+high-confidence outranks stale+low-confidence for identical lexical match
    assert ranked[0]["confidence"] == 0.9
    assert ranked[0]["_score"] > ranked[1]["_score"]
