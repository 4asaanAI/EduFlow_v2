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
def test_messaging_endpoints_reject_students(client, method, path, body):
    """Messaging opened to the whole staff room on 2026-08-12. Students did not."""
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
    found = {item["id"] for item in response.json()["data"]}
    # What this test is actually about: the other school and the other branch stay out.
    # The teacher is also absent, but for a different reason and it is pinned elsewhere:
    # teachers are step 5 of the access ladder and have not landed (2026-08-14).
    assert found == {"owner-1", "principal-1", "accountant-1", "management-1"}
    assert "other-school-owner" not in found
    assert "other-branch" not in found


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


# ── R2-10, 2026-08-11 - the colleague list stopped joining on usernames ──────
#
# "0 colleagues available" in the owner's screenshots. The lookup matched four
# hardcoded usernames - aman.litt, adesh.singh, sonu.ruhal, lalit.thomas - against
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


def test_the_colleague_list_holds_only_profiles_whose_release_has_landed(client, messaging_db):
    # 2026-08-14, Abhimanyu: a profile appears in the staff room WHEN ITS RELEASE LANDS,
    # not before and not after. Today that is Release 2's four: the owner, the principal,
    # the accountant head and the management head.
    #
    # This replaces the 2026-08-12 version, which asserted the opposite because the rule
    # then was "you are in if you work here". That rule was right about who belongs and
    # wrong about when. Logins already exist for the front desk, the helpers and the seven
    # office accounts made by migration 041, and NONE of them can sign in: their passwords
    # were never handed out. A colleague you can see and message but who can never answer
    # reads as somebody ignoring you.
    messaging_db.auth_users.docs.extend([
        make_auth_user(id="teacher-9", name="A Teacher", role="teacher",
                       sub_category="class_teacher", username="teacher9"),
        make_auth_user(id="student-9", name="A Student", role="student",
                       sub_category="student", username="student9"),
        make_auth_user(id="reception-9", name="Front Desk", sub_category="receptionist",
                       username="reception9"),
        make_auth_user(id="support-9", name="A Helper", sub_category="support_staff",
                       username="support9"),
        make_auth_user(id="transport-9", name="Transport Head", sub_category="transport_head",
                       username="transport9"),
        # A shared desk account whose sub_category is not a profile at all. Four of these
        # exist in production (transport, reception, ittech, maintenance).
        make_auth_user(id="desk-9", name="Reception Desk", sub_category="reception",
                       username="desk9"),
    ])

    response = client.get("/api/messaging/contacts", headers=_headers("owner-1", role="owner", sub_category="owner"))

    found = {item["id"] for item in response.json()["data"]}
    # R3-2, 2026-08-15: FIVE, not four. The transport head's release landed, so he is in
    # the staff room. Nothing in `messaging.py` changed to put him there - his row in the
    # permission table was marked live and the list followed, which is the behaviour
    # `test_switching_a_profile_on_puts_them_in_the_staff_room_with_no_code_change` was
    # written to predict. This assertion moving is that prediction coming true.
    assert found == {"owner-1", "principal-1", "accountant-1", "management-1", "transport-9"}, (
        "the staff room should hold exactly the live profiles, and held: "
        + ", ".join(sorted(found))
    )
    assert "student-9" not in found, "a student appeared in the staff messaging list"
    assert "reception-9" not in found, "the front desk is still dormant and appeared"
    assert "support-9" not in found, "a helper is still dormant and appeared"


def test_a_dormant_profile_cannot_be_messaged_directly_either(client, messaging_db):
    """Hiding somebody from the list is not the same as refusing to open a chat with them.

    Without this, a stale screen or a typed id would still start a conversation with a
    colleague whose release has not landed.
    """
    # R3-2, 2026-08-15: the example moved from the transport head to maintenance, because
    # the transport head is live now. The rule under test is unchanged and so is its
    # coverage; only the profile standing in for "not yet switched on" moved.
    messaging_db.auth_users.docs.append(
        make_auth_user(id="maint-9", name="Maintenance",
                       sub_category="maintenance", username="maint9")
    )

    response = client.post(
        "/api/messaging/threads/direct",
        json={"user_id": "maint-9"},
        headers=_headers("owner-1", role="owner", sub_category="owner"),
    )

    assert response.status_code == 404


def test_switching_a_profile_on_puts_them_in_the_staff_room_with_no_code_change(
    client, messaging_db, monkeypatch
):
    """The whole point of reading the permission table instead of a list of names.

    This was written on 2026-08-14 against the transport head, predicting that Release 3
    would switch him on. **It happened on 2026-08-15 (R3-2) and the prediction held**: his
    row was marked live, he appeared in the staff room, and `messaging.py` was not opened.

    The example has moved to maintenance, the next profile still waiting, so the test goes
    on proving the mechanism rather than becoming a record of something already done.
    """
    from services import profile_matrix

    entry = dict(profile_matrix.PROFILE_MATRIX["maintenance"])
    entry["status"] = "live"
    patched = dict(profile_matrix.PROFILE_MATRIX)
    patched["maintenance"] = entry
    monkeypatch.setattr(profile_matrix, "PROFILE_MATRIX", patched)
    monkeypatch.setattr("routes.messaging.PROFILE_MATRIX", patched)

    messaging_db.auth_users.docs.append(
        make_auth_user(id="maint-9", name="Maintenance",
                       sub_category="maintenance", username="maint9")
    )

    response = client.get("/api/messaging/contacts", headers=_headers("owner-1", role="owner", sub_category="owner"))

    assert "maint-9" in {item["id"] for item in response.json()["data"]}


def test_an_inactive_colleague_does_not_appear(client, messaging_db):
    messaging_db.auth_users.docs.append(
        make_auth_user(id="left-1", name="Someone Who Left", username="left",
                       sub_category="principal", is_active=False)
    )

    response = client.get("/api/messaging/contacts", headers=_headers("owner-1", role="owner", sub_category="owner"))

    assert "left-1" not in {item["id"] for item in response.json()["data"]}


# ── 2026-08-12: the staff room ───────────────────────────────────────────────
#
# Messaging was four leadership profiles. It is now everyone who works at the school,
# on Abhimanyu's instruction, so that colleagues can reach each other and make groups.
# These tests pin the two halves of that: every colleague is in, and nobody who is not
# staff can get in.



def _with_profile_live(monkeypatch, name):
    """Mark one profile live, the way its release will.

    Used so the teacher tests keep proving that messaging WORKS for a teacher, while
    today's answer stays "not until Release 5". Deleting them would have lost the
    coverage; asserting a 403 forever would have baked in a temporary state.
    """
    from services import profile_matrix

    entry = dict(profile_matrix.PROFILE_MATRIX[name])
    entry["status"] = "live"
    patched = dict(profile_matrix.PROFILE_MATRIX)
    patched[name] = entry
    monkeypatch.setattr(profile_matrix, "PROFILE_MATRIX", patched)
    monkeypatch.setattr("routes.messaging.PROFILE_MATRIX", patched)


def test_a_teacher_is_not_in_the_staff_room_until_release_5(client, messaging_db):
    """Today's answer. Teachers are step 5 of the access ladder and have not landed."""
    messaging_db.auth_users.docs.append(
        make_auth_user(id="teacher-76", name="A Teacher", role="teacher",
                       sub_category="class_teacher", username="teacher76")
    )

    response = client.get("/api/messaging/contacts",
                          headers=_headers("owner-1", role="owner", sub_category="owner"))

    assert "teacher-76" not in {item["id"] for item in response.json()["data"]}

def test_a_teacher_can_actually_use_messaging_not_merely_appear_in_it(client, messaging_db, monkeypatch):
    """Appearing in a colleague list and being allowed to open the tool are different
    things, and the old rule granted neither to a teacher. Proven with Release 5 in
    place, because that is when it becomes true."""
    _with_profile_live(monkeypatch, "teacher")
    messaging_db.auth_users.docs.append(
        make_auth_user(id="teacher-77", name="A Teacher", role="teacher",
                       sub_category="class_teacher", username="teacher77")
    )
    headers = _headers("teacher-77", role="teacher", sub_category="class_teacher")

    contacts = client.get("/api/messaging/contacts", headers=headers)
    assert contacts.status_code == 200
    assert "teacher-77" in {item["id"] for item in contacts.json()["data"]}

    threads = client.get("/api/messaging/threads", headers=headers)
    assert threads.status_code == 200


def test_a_teacher_can_start_a_chat_with_the_principal(client, messaging_db, monkeypatch):
    _with_profile_live(monkeypatch, "teacher")
    messaging_db.auth_users.docs.append(
        make_auth_user(id="teacher-78", name="Another Teacher", role="teacher",
                       sub_category="subject_teacher", username="teacher78")
    )
    headers = _headers("teacher-78", role="teacher", sub_category="subject_teacher")

    created = client.post("/api/messaging/threads/direct",
                          headers=headers, json={"user_id": "principal-1"})

    assert created.status_code == 201
    thread_id = created.json()["data"]["id"]
    sent = client.post(f"/api/messaging/threads/{thread_id}/messages",
                       headers=headers, json={"text": "Good morning sir"})
    assert sent.status_code == 201


def test_a_teacher_can_make_a_group(client, messaging_db, monkeypatch):
    _with_profile_live(monkeypatch, "teacher")
    messaging_db.auth_users.docs.append(
        make_auth_user(id="teacher-79", name="Group Maker", role="teacher",
                       sub_category="class_teacher", username="teacher79")
    )
    headers = _headers("teacher-79", role="teacher", sub_category="class_teacher")

    created = client.post(
        "/api/messaging/threads/groups",
        headers=headers,
        json={"name": "Class 4 teachers", "member_ids": ["principal-1", "management-1"]},
    )

    assert created.status_code == 201
    assert created.json()["data"]["name"] == "Class 4 teachers"


@pytest.mark.parametrize("role,sub_category", [
    ("student", "student"),
    ("parent", "parent"),
    ("guardian", "guardian"),
])
def test_children_and_parents_are_refused_the_staff_room(client, messaging_db, role, sub_category):
    """The line that must not move. Widening this again has to be a written decision,
    not a side effect of somebody adding a role name to a list."""
    response = client.get("/api/messaging/contacts",
                          headers=_headers(f"{role}-55", role=role, sub_category=sub_category))
    assert response.status_code == 403


def test_a_parent_never_appears_as_a_colleague(client, messaging_db):
    messaging_db.auth_users.docs.extend([
        make_auth_user(id="parent-55", name="A Parent", role="parent",
                       sub_category="parent", username="parent55"),
        make_auth_user(id="guardian-55", name="A Guardian", role="guardian",
                       sub_category="guardian", username="guardian55"),
    ])

    response = client.get("/api/messaging/contacts",
                          headers=_headers("owner-1", role="owner", sub_category="owner"))

    found = {item["id"] for item in response.json()["data"]}
    assert "parent-55" not in found
    assert "guardian-55" not in found


def test_somebody_who_has_left_the_school_is_not_a_colleague(client, messaging_db):
    """The 21 staff who left in August had their logins switched off (migration 048).
    This is what that switch is for: a colleague list is a list of people you can
    message, and somebody who has left is not one of them."""
    messaging_db.auth_users.docs.append(
        make_auth_user(id="teacher-gone", name="Departed Teacher", role="teacher",
                       sub_category="class_teacher", username="gone", is_active=False)
    )

    response = client.get("/api/messaging/contacts",
                          headers=_headers("owner-1", role="owner", sub_category="owner"))

    assert "teacher-gone" not in {item["id"] for item in response.json()["data"]}


def test_the_whole_staff_room_fits_and_nobody_is_silently_truncated(client, messaging_db, monkeypatch):
    """The old cap was 50, set when four people could message each other. The school has
    96 staff logins. A colleague missing because of a cap looks exactly like a colleague
    who has left, which is why this is pinned rather than left to a comment.

    Run with teachers switched on, since that is the release that makes the staff room
    big enough for the cap to matter at all."""
    _with_profile_live(monkeypatch, "teacher")
    messaging_db.auth_users.docs.extend([
        make_auth_user(id=f"teacher-bulk-{index}", name=f"Teacher {index}", role="teacher",
                       sub_category="subject_teacher", username=f"bulk{index}")
        for index in range(120)
    ])

    response = client.get("/api/messaging/contacts",
                          headers=_headers("owner-1", role="owner", sub_category="owner"))

    data = response.json()["data"]
    assert len(data) == 124
    assert response.json()["meta"]["count"] == 124


def test_replying_to_a_colleague_does_not_500_on_mongos_own_id(client, messaging_db):
    """Reported live on 2026-08-12: Aman replying to Lalit got "An internal error
    occurred" while the message was in fact saved and delivered.

    `insert_one` writes Mongo's `_id` back into the dict IN PLACE, and the send
    route echoed that same dict to the sender. An ObjectId cannot be turned into
    JSON, so the response blew up AFTER the write had already happened - the
    worst shape of failure, because the sender is told the opposite of what
    occurred and sends again.

    The stand-in database used to leave `_id` alone, which is why a green suite
    said nothing. It now stamps `_id` like the real thing, so this test fails
    without the fix.
    """
    owner_headers = _headers("owner-1", role="owner", sub_category="owner")
    management_headers = _headers("management-1", sub_category="management")

    thread_id = client.post(
        "/api/messaging/threads/direct",
        headers=management_headers,
        json={"user_id": "owner-1"},
    ).json()["data"]["id"]

    first = client.post(
        f"/api/messaging/threads/{thread_id}/messages",
        headers=management_headers,
        json={"text": "Sir, please check the transport list."},
    )
    assert first.status_code == 201, first.text

    reply = client.post(
        f"/api/messaging/threads/{thread_id}/messages",
        headers=owner_headers,
        json={"text": "hello", "reply_to_id": first.json()["data"]["id"]},
    )

    assert reply.status_code == 201, reply.text
    assert "_id" not in reply.json()["data"], (
        "Mongo's internal id must never reach the browser - it is what made the "
        "send fail while the message had already been written"
    )
    assert reply.json()["data"]["text"] == "hello"


def test_deleting_a_message_records_who_removed_it_and_what_was_lost(client, messaging_db):
    """Editing a message is audited; deleting one was not. The row survives with an
    empty body, but without the audit record the fact of the deletion - and the only
    copy of what was deleted - disappeared from the school's history."""
    owner_headers = _headers("owner-1", role="owner", sub_category="owner")

    thread_id = client.post(
        "/api/messaging/threads/direct",
        headers=owner_headers,
        json={"user_id": "principal-1"},
    ).json()["data"]["id"]
    sent = client.post(
        f"/api/messaging/threads/{thread_id}/messages",
        headers=owner_headers,
        json={"text": "The bus leaves at six."},
    )
    assert sent.status_code == 201
    message_id = sent.json()["data"]["id"]

    response = client.delete(f"/api/messaging/messages/{message_id}", headers=owner_headers)

    assert response.status_code == 200
    audits = [doc for doc in messaging_db.audit_logs.docs if doc.get("entity_id") == message_id]
    assert len(audits) == 1
    audit = audits[0]
    assert audit["action"] == "message_delete"
    assert audit["changed_by"] == "owner-1"
    snapshot = audit["changes"]["snapshot"]
    assert audit["changes"]["kind"] == "delete"
    assert snapshot["id"] == message_id
    assert snapshot["text"] == "The bus leaves at six."
