from __future__ import annotations

import copy

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_auth_user


SCHOOL_ID = "aaryans-joya"
BRANCH_ID = "branch-a"


def _headers(user_id: str, role: str = "admin", sub_category: str = "principal") -> dict:
    token = create_jwt({
        "user_id": user_id,
        "name": user_id,
        "role": role,
        "sub_category": sub_category,
        "branch_id": BRANCH_ID,
        "school_id": SCHOOL_ID,
    })
    return {"Authorization": f"Bearer {token}"}


def _leadership_accounts() -> list[dict]:
    return [
        make_auth_user(id="owner-1", name="Aman Litt", username="aman.litt", role="owner", sub_category="owner"),
        make_auth_user(id="principal-1", name="Adesh Singh", username="adesh.singh", sub_category="principal"),
        make_auth_user(id="accountant-1", name="Sonu Ruhal", username="sonu.ruhal", sub_category="accountant"),
        make_auth_user(id="management-1", name="Lalit Thomas", username="lalit.thomas", sub_category="management"),
    ]


@pytest.fixture
def messaging_db(fake_db):
    collections = (
        "auth_users",
        "platform_message_threads",
        "platform_messages",
        "platform_message_receipts",
        "platform_message_presence",
    )
    before = {name: copy.deepcopy(getattr(fake_db, name).docs) for name in collections}
    fake_db.auth_users.docs[:] = _leadership_accounts()
    for name in collections[1:]:
        getattr(fake_db, name).docs[:] = []
    yield fake_db
    for name, docs in before.items():
        getattr(fake_db, name).docs[:] = docs


ENDPOINTS = [
    ("get", "/api/messaging/contacts", None),
    ("get", "/api/messaging/threads", None),
    ("post", "/api/messaging/threads/direct", {"user_id": "principal-1"}),
    ("post", "/api/messaging/threads/groups", {"name": "Leadership", "member_ids": ["principal-1", "accountant-1"]}),
    ("patch", "/api/messaging/threads/thread-1", {"name": "Office"}),
    ("get", "/api/messaging/threads/thread-1/messages", None),
    ("post", "/api/messaging/threads/thread-1/messages", {"text": "Hello"}),
    ("patch", "/api/messaging/threads/thread-1/read", None),
    ("post", "/api/messaging/threads/thread-1/typing", None),
    ("patch", "/api/messaging/messages/message-1", {"text": "Updated"}),
    ("delete", "/api/messaging/messages/message-1", None),
    ("get", "/api/messaging/stream", None),
]


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_messaging_endpoints_require_authentication(client, method, path, body):
    response = client.request(method, path, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_messaging_endpoints_reject_non_leadership_roles(client, method, path, body):
    response = client.request(
        method,
        path,
        headers=_headers("student-1", role="student", sub_category="student"),
        json=body,
    )
    assert response.status_code == 403


def test_contacts_are_limited_to_same_school_and_branch(client, messaging_db):
    messaging_db.auth_users.docs.extend([
        make_auth_user(
            id="other-school-owner", name="Other Owner", role="owner", sub_category="owner",
            username="aman.litt", schoolId="other-school",
        ),
        make_auth_user(
            id="other-branch", name="Other Principal", sub_category="principal",
            username="adesh.singh", branch_id="branch-b",
        ),
        make_auth_user(
            id="teacher-1", name="Teacher", role="teacher", sub_category="class_teacher",
            username="sonu.ruhal",
        ),
    ])

    response = client.get("/api/messaging/contacts", headers=_headers("owner-1", role="owner", sub_category="owner"))

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["data"]} == {
        "owner-1", "principal-1", "accountant-1", "management-1"
    }


def test_direct_group_and_message_receipts_flow(client, messaging_db):
    owner_headers = _headers("owner-1", role="owner", sub_category="owner")
    principal_headers = _headers("principal-1")

    direct_response = client.post(
        "/api/messaging/threads/direct",
        headers=owner_headers,
        json={"user_id": "principal-1"},
    )
    assert direct_response.status_code == 201
    thread_id = direct_response.json()["data"]["id"]

    group_response = client.post(
        "/api/messaging/threads/groups",
        headers=owner_headers,
        json={"name": "Leadership", "member_ids": ["principal-1", "accountant-1", "management-1"]},
    )
    assert group_response.status_code == 201
    assert group_response.json()["data"]["title"] == "Leadership"
    assert len(group_response.json()["data"]["members"]) == 4

    send_response = client.post(
        f"/api/messaging/threads/{thread_id}/messages",
        headers=owner_headers,
        json={"text": "Please review today's operations."},
    )
    assert send_response.status_code == 201
    message = send_response.json()["data"]
    assert message["receipt"]["status"] == "sent"
    assert all(row["schoolId"] == SCHOOL_ID for row in messaging_db.platform_messages.docs)

    principal_threads = client.get("/api/messaging/threads", headers=principal_headers).json()
    assert principal_threads["meta"]["unread_total"] == 1
    assert principal_threads["data"][0]["title"] == "Aman Litt"

    read_response = client.patch(
        f"/api/messaging/threads/{thread_id}/read", headers=principal_headers
    )
    assert read_response.status_code == 200
    assert read_response.json()["data"]["updated"] == 1

    messages_response = client.get(
        f"/api/messaging/threads/{thread_id}/messages", headers=owner_headers
    )
    assert messages_response.status_code == 200
    stored_message = messages_response.json()["data"][0]
    assert stored_message["id"] == message["id"]
    assert stored_message["receipt"]["status"] == "read"


def test_thread_membership_and_branch_scope_fail_closed(client, messaging_db):
    messaging_db.platform_message_threads.docs.extend([
        {
            "id": "not-mine",
            "schoolId": SCHOOL_ID,
            "branch_id": BRANCH_ID,
            "kind": "direct",
            "member_ids": ["principal-1", "accountant-1"],
            "updated_at": "2026-08-08T10:00:00+00:00",
        },
        {
            "id": "other-branch-thread",
            "schoolId": SCHOOL_ID,
            "branch_id": "branch-b",
            "kind": "direct",
            "member_ids": ["owner-1", "principal-1"],
            "updated_at": "2026-08-08T11:00:00+00:00",
        },
    ])
    owner_headers = _headers("owner-1", role="owner", sub_category="owner")

    response = client.get("/api/messaging/threads", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["data"] == []

    response = client.get(
        "/api/messaging/threads/not-mine/messages", headers=owner_headers
    )
    assert response.status_code == 404


# ── R2-10, 2026-08-11 — the colleague list stopped joining on usernames ──────
#
# "0 colleagues available" in the owner's screenshots. The lookup matched four
# hardcoded usernames — aman.litt, adesh.singh, sonu.ruhal, lalit.thomas — against
# `username_lower`. The logins actually in production are `accountant` and
# `management`, so it matched nobody and the screen truthfully reported nothing.
#
# Renaming the logins (R2-11) would have made it work again by accident, which is the
# wrong reason for it to work: the next employee to join would still be invisible.
# These tests pin that WHO SOMEBODY IS decides whether they appear, not what they typed
# to log in.

def _account_with_login(user_id: str, name: str, username: str, sub_category: str) -> dict:
    return make_auth_user(id=user_id, name=name, username=username, sub_category=sub_category)


def test_colleagues_appear_under_the_logins_production_actually_uses(client, messaging_db):
    # The real thing: `accountant` and `management`, not the dotted names.
    messaging_db.auth_users.docs[:] = [
        make_auth_user(id="owner-1", name="Aman Litt", username="aman", role="owner", sub_category="owner"),
        _account_with_login("principal-1", "Adesh", "adesh", "principal"),
        _account_with_login("accountant-1", "Sonu Ruhal", "accountant", "accountant"),
        _account_with_login("management-1", "Lalit Thomas", "management", "management"),
    ]

    response = client.get("/api/messaging/contacts", headers=_headers("owner-1", role="owner", sub_category="owner"))

    assert response.status_code == 200
    found = {item["id"] for item in response.json()["data"]}
    assert found == {"owner-1", "principal-1", "accountant-1", "management-1"}, (
        "the colleague list is still deciding who exists from their login name"
    )


def test_a_new_colleague_appears_without_anybody_adding_their_login_to_a_list(client, messaging_db):
    # The half that the login rename would NOT have fixed. A second accountant joins
    # the school with a login nobody has hardcoded anywhere.
    messaging_db.auth_users.docs.append(
        _account_with_login("accountant-2", "A New Accounts Person", "newjoiner2027", "accountant")
    )

    response = client.get("/api/messaging/contacts", headers=_headers("owner-1", role="owner", sub_category="owner"))

    assert "accountant-2" in {item["id"] for item in response.json()["data"]}


def test_the_colleague_list_still_refuses_everyone_outside_leadership(client, messaging_db):
    # Asking by role is looser than asking by username, so this is the guard that
    # matters: a teacher, a student and a receptionist must not appear just because the
    # query changed shape.
    messaging_db.auth_users.docs.extend([
        make_auth_user(id="teacher-9", name="A Teacher", role="teacher",
                       sub_category="class_teacher", username="teacher9"),
        make_auth_user(id="student-9", name="A Student", role="student",
                       sub_category="student", username="student9"),
        make_auth_user(id="reception-9", name="Front Desk", sub_category="receptionist",
                       username="reception9"),
        make_auth_user(id="support-9", name="A Helper", sub_category="support_staff",
                       username="support9"),
    ])

    response = client.get("/api/messaging/contacts", headers=_headers("owner-1", role="owner", sub_category="owner"))

    found = {item["id"] for item in response.json()["data"]}
    for outsider in ("teacher-9", "student-9", "reception-9", "support-9"):
        assert outsider not in found, f"{outsider} appeared in the leadership colleague list"


def test_an_inactive_colleague_does_not_appear(client, messaging_db):
    messaging_db.auth_users.docs.append(
        make_auth_user(id="left-1", name="Someone Who Left", username="left",
                       sub_category="principal", is_active=False)
    )

    response = client.get("/api/messaging/contacts", headers=_headers("owner-1", role="owner", sub_category="owner"))

    assert "left-1" not in {item["id"] for item in response.json()["data"]}
