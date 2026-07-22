from __future__ import annotations
"""Epic 6, Story 6.4 — the chat archive can be paged, searched and cleared out.

Two tests here guard traps rather than features, and both would pass against a
plausible-looking wrong implementation of the neighbouring code:

  * test_bulk_delete_refuses_a_query_operator_as_an_id — an untyped body turns
    "delete these three" into "delete everything you own".
  * test_bulk_delete_does_not_touch_another_users_messages — the messages filter
    carries no user_id. It is safe in the single-delete path only because
    ownership is proven one id at a time first.
"""

import pytest

from middleware.auth import create_jwt

SCHOOL_ID = "aaryans-joya"


@pytest.fixture(autouse=True)
def _clean(fake_db):
    fake_db.conversations.docs[:] = []
    fake_db.messages.docs[:] = []
    yield
    fake_db.conversations.docs[:] = []
    fake_db.messages.docs[:] = []


def _headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(user)}"}


MINE = {"user_id": "conv-owner", "role": "owner", "name": "Aman"}
THEIRS = {"user_id": "conv-other", "role": "teacher", "name": "Someone Else"}


def _conv(idx: int, *, user_id: str = "conv-owner", title: str | None = None, updated: str | None = None) -> dict:
    return {
        "_id": f"c-{user_id}-{idx}",
        "id": f"c-{user_id}-{idx}",
        "schoolId": SCHOOL_ID,
        "user_id": user_id,
        "title": title if title is not None else f"Conversation {idx}",
        "is_pinned": False,
        "is_starred": False,
        "created_at": f"2026-07-{idx + 1:02d}T09:00:00",
        "updated_at": updated or f"2026-07-{idx + 1:02d}T10:00:00",
    }


def _msg(idx: int, conv_id: str) -> dict:
    return {
        "_id": f"m-{conv_id}-{idx}",
        "id": f"m-{conv_id}-{idx}",
        "schoolId": SCHOOL_ID,
        "conversation_id": conv_id,
        "role": "user",
        "content": f"message {idx}",
        "created_at": "2026-07-01T09:00:00",
    }


# ── The sidebar's bare call must not change (readiness Q-4) ──────────────────

def test_sidebar_call_still_gets_newest_fifty_most_recent_first(client, fake_db):
    """The sidebar calls this with NO arguments and is on every screen."""
    fake_db.conversations.docs.extend([_conv(i) for i in range(60)])

    body = client.get("/api/chat/conversations", headers=_headers(MINE)).json()

    assert body["success"] is True
    assert len(body["data"]) == 50
    assert body["data"][0]["id"] == "c-conv-owner-59"
    assert body["data"][-1]["id"] == "c-conv-owner-10"


def test_sidebar_call_gains_meta_without_reshaping_data(client, fake_db):
    fake_db.conversations.docs.extend([_conv(i) for i in range(3)])

    body = client.get("/api/chat/conversations", headers=_headers(MINE)).json()

    assert set(body.keys()) == {"success", "data", "meta"}
    assert body["meta"]["total"] == 3
    assert body["meta"]["page"] == 1
    assert body["meta"]["sort"] == "recent"


# ── Paging and ordering ──────────────────────────────────────────────────────

def test_paging_reaches_past_the_fifty_that_used_to_be_the_end(client, fake_db):
    """The defect this story exists to fix: conversation 51 was unreachable by any
    route in the product."""
    fake_db.conversations.docs.extend([_conv(i) for i in range(60)])

    page_two = client.get("/api/chat/conversations?page=2&limit=50", headers=_headers(MINE)).json()

    assert body_ids(page_two) == [f"c-conv-owner-{i}" for i in range(9, -1, -1)]
    assert page_two["meta"]["total"] == 60


def body_ids(body):
    return [c["id"] for c in body["data"]]


def test_sort_oldest_and_title_are_honoured(client, fake_db):
    fake_db.conversations.docs.extend([
        _conv(0, title="Zebra"), _conv(1, title="Apple"), _conv(2, title="Mango"),
    ])

    oldest = client.get("/api/chat/conversations?sort=oldest", headers=_headers(MINE)).json()
    by_title = client.get("/api/chat/conversations?sort=title", headers=_headers(MINE)).json()

    assert body_ids(oldest) == ["c-conv-owner-0", "c-conv-owner-1", "c-conv-owner-2"]
    assert [c["title"] for c in by_title["data"]] == ["Apple", "Mango", "Zebra"]


def test_unrecognised_sort_falls_back_to_recent(client, fake_db):
    fake_db.conversations.docs.extend([_conv(i) for i in range(3)])

    body = client.get("/api/chat/conversations?sort=updated_at%20DESC", headers=_headers(MINE)).json()

    assert body["meta"]["sort"] == "recent"
    assert body_ids(body) == ["c-conv-owner-2", "c-conv-owner-1", "c-conv-owner-0"]


def test_limit_is_clamped_server_side(client, fake_db):
    fake_db.conversations.docs.extend([_conv(i) for i in range(30)])

    body = client.get("/api/chat/conversations?limit=100000", headers=_headers(MINE)).json()

    assert body["meta"]["limit"] == 100


# ── Search ───────────────────────────────────────────────────────────────────

def test_search_matches_titles_case_insensitively(client, fake_db):
    fake_db.conversations.docs.extend([
        _conv(0, title="Fee reminders for class 9"),
        _conv(1, title="Staff leave in August"),
        _conv(2, title="FEE structure question"),
    ])

    body = client.get("/api/chat/conversations?search=fee", headers=_headers(MINE)).json()

    assert sorted(c["title"] for c in body["data"]) == ["FEE structure question", "Fee reminders for class 9"]
    assert body["meta"]["total"] == 2


def test_search_term_is_escaped_not_interpreted(client, fake_db):
    """`.*` must match a chat literally called ".*", never every chat."""
    fake_db.conversations.docs.extend([_conv(0, title="Anything"), _conv(1, title="literally .* here")])

    body = client.get("/api/chat/conversations?search=.*", headers=_headers(MINE)).json()

    assert [c["title"] for c in body["data"]] == ["literally .* here"]


def test_a_catastrophic_pattern_is_neutralised(client, fake_db):
    fake_db.conversations.docs.extend([_conv(0, title="a" * 40)])

    resp = client.get("/api/chat/conversations?search=" + "(a+)+" * 12, headers=_headers(MINE))

    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ── Bulk delete ──────────────────────────────────────────────────────────────

def test_bulk_delete_removes_conversations_and_their_messages(client, fake_db):
    fake_db.conversations.docs.extend([_conv(i) for i in range(3)])
    fake_db.messages.docs.extend([_msg(0, "c-conv-owner-0"), _msg(0, "c-conv-owner-2")])

    body = client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": ["c-conv-owner-0", "c-conv-owner-2"]},
    ).json()

    assert body["data"] == {"deleted": 2, "not_found": 0}
    assert [c["id"] for c in fake_db.conversations.docs] == ["c-conv-owner-1"]
    assert fake_db.messages.docs == []


def test_bulk_delete_reports_what_actually_happened(client, fake_db):
    """A partial result is stated, never presented as success (NFR-R1)."""
    fake_db.conversations.docs.extend([_conv(0)])

    body = client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": ["c-conv-owner-0", "does-not-exist", "nor-this"]},
    ).json()

    assert body["data"] == {"deleted": 1, "not_found": 2}


def test_bulk_delete_counts_from_the_database_not_the_request(client, fake_db):
    """A caller repeating one id ten times must not be told ten chats were removed."""
    fake_db.conversations.docs.extend([_conv(0)])

    body = client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": ["c-conv-owner-0"] * 10},
    ).json()

    assert body["data"]["deleted"] == 1


def test_bulk_delete_refuses_a_query_operator_as_an_id(client, fake_db):
    """THE TRAP. Against an untyped body, {"$gt": ""} inside `ids` produces
    {"id": {"$in": [{"$gt": ""}]}} — a query matching every conversation the
    caller owns. The request reads "delete this one" and executes as "delete
    everything". Typing the body makes it a 422 before any query is built."""
    fake_db.conversations.docs.extend([_conv(i) for i in range(5)])

    resp = client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": [{"$gt": ""}]},
    )

    assert resp.status_code == 422
    assert len(fake_db.conversations.docs) == 5


def test_bulk_delete_refuses_an_empty_or_oversized_list(client, fake_db):
    from models.schemas import CONVERSATION_BULK_DELETE_MAX

    empty = client.post("/api/chat/conversations/bulk-delete", headers=_headers(MINE), json={"ids": []})
    huge = client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": [f"id-{i}" for i in range(CONVERSATION_BULK_DELETE_MAX + 1)]},
    )

    assert empty.status_code == 422
    assert huge.status_code == 422


def test_bulk_delete_skips_another_users_conversation(client, fake_db):
    fake_db.conversations.docs.extend([_conv(0, user_id="conv-owner"), _conv(0, user_id="conv-other")])

    body = client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": ["c-conv-owner-0", "c-conv-other-0"]},
    ).json()

    # "not found" and "someone else's" are reported identically — from outside
    # they must be indistinguishable.
    assert body["data"] == {"deleted": 1, "not_found": 1}
    assert [c["id"] for c in fake_db.conversations.docs] == ["c-conv-other-0"]


def test_bulk_delete_does_not_touch_another_users_messages(client, fake_db):
    """THE SECOND TRAP. The messages filter carries no user_id. Deleting on the
    caller's RAW id list destroys another user's messages while leaving their
    conversation standing — a chat they can still open and find empty, with
    nothing in any log to explain it."""
    fake_db.conversations.docs.extend([_conv(0, user_id="conv-owner"), _conv(0, user_id="conv-other")])
    fake_db.messages.docs.extend([_msg(0, "c-conv-owner-0"), _msg(0, "c-conv-other-0"), _msg(1, "c-conv-other-0")])

    client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": ["c-conv-owner-0", "c-conv-other-0"]},
    )

    surviving = [m["conversation_id"] for m in fake_db.messages.docs]
    assert surviving == ["c-conv-other-0", "c-conv-other-0"]


def test_bulk_delete_is_school_scoped(client, fake_db):
    foreign = _conv(0, user_id="conv-owner")
    foreign["schoolId"] = "other-school"
    fake_db.conversations.docs.append(foreign)

    body = client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": ["c-conv-owner-0"]},
    ).json()

    assert body["data"] == {"deleted": 0, "not_found": 1}
    assert len(fake_db.conversations.docs) == 1


def test_bulk_delete_writes_one_audit_row_with_counts_only(client, fake_db):
    """Ids and counts, never a title or any message text (NFR-S2)."""
    fake_db.audit_logs.docs[:] = []
    fake_db.conversations.docs.extend([_conv(0, title="Fee arrears for Ravi Kumar")])
    fake_db.messages.docs.append(_msg(0, "c-conv-owner-0"))

    client.post(
        "/api/chat/conversations/bulk-delete",
        headers=_headers(MINE),
        json={"ids": ["c-conv-owner-0"]},
    )

    rows = [r for r in fake_db.audit_logs.docs if r.get("action") == "conversation_bulk_delete"]
    assert len(rows) == 1
    assert rows[0]["changes"] == {
        "deleted": 1, "requested": 1, "conversation_ids": ["c-conv-owner-0"],
    }
    # The ids live in `changes`, not `entity_id`: audit_logs indexes entity_id,
    # and 100 joined UUIDs would make a bulk delete the biggest key in the log.
    assert rows[0]["entity_id"] == "conv-owner"
    assert "Ravi Kumar" not in str(rows[0])
    assert "message 0" not in str(rows[0])


# ── Standing endpoint conventions ────────────────────────────────────────────

def test_bulk_delete_unauthenticated_returns_401(client):
    resp = client.post("/api/chat/conversations/bulk-delete", json={"ids": ["x"]})
    assert resp.status_code == 401


def test_list_conversations_unauthenticated_returns_401(client):
    assert client.get("/api/chat/conversations").status_code == 401


def test_one_user_never_sees_anothers_conversations(client, fake_db):
    """Stands in for the usual 403-wrong-role test: these routes are scoped to the
    caller rather than gated by role, so the boundary is between users. The Owner
    seeing everyone's chats was put to him on 2026-07-23 and refused."""
    fake_db.conversations.docs.extend([_conv(i, user_id="conv-owner") for i in range(3)])
    fake_db.conversations.docs.append(_conv(0, user_id="conv-other"))

    body = client.get("/api/chat/conversations?limit=100", headers=_headers(THEIRS)).json()

    assert body_ids(body) == ["c-conv-other-0"]
    assert body["meta"]["total"] == 1


def test_search_cannot_reach_another_users_conversations(client, fake_db):
    fake_db.conversations.docs.extend([_conv(0, user_id="conv-owner", title="Secret fee plan")])

    body = client.get("/api/chat/conversations?search=Secret", headers=_headers(THEIRS)).json()

    assert body["data"] == []
    assert body["meta"]["total"] == 0
