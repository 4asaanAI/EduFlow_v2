"""Deciding an approval through Flo and through the screen must be the same act.

Approvals workflow, 2026-08-15. `decide_any_approval` is the one tool that decides any
of the six kinds, and the promise it makes is that it grants nobody anything: whoever
cannot approve something on that kind's own screen cannot approve it by asking Flo.

That promise is only worth as much as a test that drives BOTH doors and compares them,
because the two are separate code paths and a promise in a comment does not run.
"""

from __future__ import annotations

import pytest

from ai.tool_functions_v2 import TOOL_REGISTRY
from services import approval_registry as registry
from services.actor_context import actor_ctx_from_user

SCHOOL = "aaryans-joya"

OWNER = {"id": "aman", "role": "owner", "name": "Aman"}
PRINCIPAL = {"id": "adesh", "role": "admin", "sub_category": "principal", "name": "Adesh"}
ACCOUNTANT = {"id": "sonu", "role": "admin", "sub_category": "accountant", "name": "Sonu"}
TRANSPORT = {"id": "chaman", "role": "admin", "sub_category": "transport_head",
             "name": "Chaman"}


def _request(request_id, **over):
    return {
        "id": request_id, "schoolId": SCHOOL, "status": "pending",
        "routing": "owner_and_principal", "title": "A bus repair",
        "description": "The clutch", "submitted_by": TRANSPORT["id"],
        "submitted_at": "2026-08-15T09:00:00+00:00", **over,
    }


@pytest.fixture
def seeded(fake_db):
    users_before = list(fake_db.users.docs)
    requests_before = list(fake_db.approval_requests.docs)
    threads_before = list(fake_db.approval_threads.docs)
    messages_before = list(fake_db.approval_messages.docs)
    notifications_before = list(fake_db.notifications.docs)
    fake_db.users.docs.extend([
        {"id": OWNER["id"], "schoolId": SCHOOL, "role": "owner", "name": "Aman"},
        {"id": PRINCIPAL["id"], "schoolId": SCHOOL, "role": "admin",
         "sub_category": "principal", "name": "Adesh"},
    ])
    yield fake_db
    fake_db.users.docs[:] = users_before
    fake_db.approval_requests.docs[:] = requests_before
    fake_db.approval_threads.docs[:] = threads_before
    fake_db.approval_messages.docs[:] = messages_before
    fake_db.notifications.docs[:] = notifications_before


async def test_the_chat_door_and_the_screen_door_produce_the_same_record(seeded, monkeypatch):
    """One request decided through Flo, one identical request decided through the
    service the screen calls. The stored result must be indistinguishable."""
    import ai.tool_functions_v2 as tools

    monkeypatch.setattr(tools, "get_db", lambda: seeded)
    seeded.approval_requests.docs.append(_request("via-chat"))
    seeded.approval_requests.docs.append(_request("via-screen"))

    chat = await TOOL_REGISTRY["decide_any_approval"]["fn"](
        {"kind": "general", "request_id": "via-chat", "decision": "approve",
         "reason": "Go ahead"}, OWNER)
    assert chat["success"] is True

    await registry.decide(
        seeded, actor_ctx_from_user(OWNER, school_id=SCHOOL), OWNER,
        "general", "via-screen", "approve", "Go ahead")

    ignore = {"id", "_id", "decided_at", "submitted_at", "title"}
    stored = {
        doc["id"]: {k: v for k, v in doc.items() if k not in ignore}
        for doc in seeded.approval_requests.docs
        if doc["id"] in ("via-chat", "via-screen")
    }
    assert stored["via-chat"] == stored["via-screen"]
    assert stored["via-chat"]["status"] == "approved"


async def test_the_chat_door_refuses_exactly_who_the_screen_refuses(seeded, monkeypatch):
    """The accountant head holds `decide_any_approval` because it is classified shared.

    Holding the tool is not holding the decision. This is the test that makes that
    claim true rather than merely stated: he is refused through chat exactly as the
    registry refuses him, and nothing is decided.
    """
    import ai.tool_functions_v2 as tools

    monkeypatch.setattr(tools, "get_db", lambda: seeded)
    seeded.approval_requests.docs.append(_request("not-his"))

    assert await registry.may_decide(
        seeded, "general", ACCOUNTANT, _request("not-his")) is False
    result = await TOOL_REGISTRY["decide_any_approval"]["fn"](
        {"kind": "general", "request_id": "not-his", "decision": "approve",
         "reason": "why not"}, ACCOUNTANT)
    assert result["success"] is False
    stored = [d for d in seeded.approval_requests.docs if d["id"] == "not-his"][0]
    assert stored["status"] == "pending"


async def test_the_person_who_raised_it_cannot_approve_it_through_chat_either(
        seeded, monkeypatch):
    import ai.tool_functions_v2 as tools

    monkeypatch.setattr(tools, "get_db", lambda: seeded)
    seeded.approval_requests.docs.append(_request("his-own"))
    result = await TOOL_REGISTRY["decide_any_approval"]["fn"](
        {"kind": "general", "request_id": "his-own", "decision": "approve",
         "reason": "mine"}, TRANSPORT)
    assert result["success"] is False
    stored = [d for d in seeded.approval_requests.docs if d["id"] == "his-own"][0]
    assert stored["status"] == "pending"


async def test_refusing_through_chat_without_a_reason_is_refused(seeded, monkeypatch):
    import ai.tool_functions_v2 as tools

    monkeypatch.setattr(tools, "get_db", lambda: seeded)
    seeded.approval_requests.docs.append(_request("needs-reason"))
    result = await TOOL_REGISTRY["decide_any_approval"]["fn"](
        {"kind": "general", "request_id": "needs-reason", "decision": "reject"}, OWNER)
    assert result["success"] is False
    stored = [d for d in seeded.approval_requests.docs if d["id"] == "needs-reason"][0]
    assert stored["status"] == "pending"


async def test_deciding_through_chat_closes_the_conversation_too(seeded, monkeypatch):
    """Otherwise a request decided in chat would leave a conversation still open, and
    somebody would go on replying to something that had already been settled."""
    import ai.tool_functions_v2 as tools

    monkeypatch.setattr(tools, "get_db", lambda: seeded)
    seeded.approval_requests.docs.append(_request("closes"))
    await TOOL_REGISTRY["decide_any_approval"]["fn"](
        {"kind": "general", "request_id": "closes", "decision": "approve",
         "reason": "fine"}, OWNER)
    thread = await seeded.approval_threads.find_one({"id": "general:closes"}, {"_id": 0})
    assert thread["status"] == "closed"


async def test_flo_asks_before_it_decides(seeded):
    """Decision 30: deciding through Flo always shows a confirm card first."""
    from routes import chat

    entry = TOOL_REGISTRY["decide_any_approval"]
    assert entry["dispatch_type"] == "write"
    assert entry.get("requires_confirmation") is True
    assert "decide_any_approval" in chat.WRITE_ACTION_TOOLS
