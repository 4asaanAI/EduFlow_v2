"""Inspection Remediation BLOCK 3 — T13 (NEW-07), error shape.

Three refusals on the chat routes answered HTTP 200 with `{"success": False, ...}`.
The action was correctly blocked in every case, so this was never a hole — but a
refusal that reports itself as a success cannot be counted by anything watching
rejected requests, and it made the browser try to read a stream that was not there.

CLAUDE.md: "Errors — ALWAYS raise HTTPException, never return raw dicts."
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt

SCHOOL = "aaryans-joya"


def _headers(user_id="u1", role="owner", sub_category=None):
    claims = {"user_id": user_id, "role": role, "name": "T"}
    if sub_category:
        claims["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(claims)}"}


def _seed_conversation(fake_db, user_id="u1"):
    fake_db.conversations.docs[:] = [
        {"_id": "conv-1", "id": "conv-1", "schoolId": SCHOOL, "user_id": user_id}
    ]
    fake_db.messages.docs[:] = []


def test_unknown_action_is_404_not_a_200_success_false(client, fake_db):
    _seed_conversation(fake_db)
    resp = client.post(
        "/api/chat/conversations/conv-1/action",
        json={"action": "no_such_tool", "params": {}, "label": "x"},
        headers=_headers(),
    )
    assert resp.status_code == 404
    assert "no_such_tool" in resp.json()["detail"]
    # And the old shape is genuinely gone, not merely accompanied.
    assert "success" not in resp.json()


def test_unauthorized_action_is_403_and_says_why(client, fake_db):
    """A student asking for an owner tool. The refusal itself is unchanged; what
    changed is that it now registers as a refusal."""
    _seed_conversation(fake_db, user_id="stu-1")
    resp = client.post(
        "/api/chat/conversations/conv-1/action",
        json={"action": "get_school_pulse", "params": {}, "label": "Pulse"},
        headers=_headers(user_id="stu-1", role="student"),
    )
    assert resp.status_code == 403
    assert "permission" in resp.json()["detail"].lower()
    assert "success" not in resp.json()


def test_empty_message_is_400(client, fake_db):
    _seed_conversation(fake_db)
    resp = client.post(
        "/api/chat/conversations/conv-1/messages",
        json={"text": "   "},
        headers=_headers(),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Empty message"


def test_bad_attachment_is_400(client, fake_db):
    _seed_conversation(fake_db)
    resp = client.post(
        "/api/chat/conversations/conv-1/messages",
        json={"text": "look at this", "image_data": "not-a-data-url"},
        headers=_headers(),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]
    assert "success" not in resp.json()


def test_action_endpoint_unauthenticated_returns_401(client, fake_db):
    _seed_conversation(fake_db)
    resp = client.post(
        "/api/chat/conversations/conv-1/action",
        json={"action": "get_school_pulse", "params": {}, "label": "Pulse"},
    )
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "route,payload",
    [
        ("/api/fees/discounts/pending-approvals", None),
        ("/api/issues/facility/req-1", None),
    ],
    ids=["pending-discounts", "facility-request"],
)
def test_internal_ids_are_not_in_response_bodies(client, fake_db, route, payload):
    """T13 second half: reads that ARE the response body must exclude `_id`."""
    fake_db.pending_discount_approvals.docs[:] = [
        {"_id": "mongo-internal-1", "id": "pa-1", "schoolId": SCHOOL,
         "status": "pending", "student_id": "s1", "amount": 5000}
    ]
    fake_db.facility_requests.docs[:] = [
        {"_id": "mongo-internal-2", "id": "req-1", "schoolId": SCHOOL,
         "status": "open", "title": "Broken fan", "created_at": "2026-08-01T00:00:00"}
    ]
    resp = client.get(route, headers=_headers())
    assert resp.status_code == 200
    assert "mongo-internal" not in resp.text, "an internal Mongo id reached the response body"
