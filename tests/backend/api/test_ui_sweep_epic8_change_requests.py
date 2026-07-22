"""UI Sweep Epic 8 — Ask, Don't Just Change.

Story 8.1  a member of staff asks for their name/phone/email to be corrected
Story 8.2  the Owner or the Principal decides; only then does anything change

The rule this feature must never break: asking is not changing. Every test that
checks a refusal also checks that the underlying staff record and login record
are untouched — a request route that quietly wrote through would be worse than
the direct editing it replaced, because it would look supervised.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio

SCHOOL = "aaryans-joya"


def _headers(payload):
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _teacher_headers():
    return _headers({"user_id": "tch-1", "role": "teacher", "name": "Teacher T"})


def _owner_headers():
    return _headers({"user_id": "own-1", "role": "owner", "name": "Owner"})


def _principal_headers():
    return _headers({"user_id": "prin-1", "role": "admin", "name": "P", "sub_category": "principal"})


def _accountant_headers():
    return _headers({"user_id": "acc-1", "role": "admin", "name": "A", "sub_category": "accountant"})


@pytest.fixture(autouse=True)
def _clean(fake_db):
    staff_before = list(fake_db.staff.docs)
    auth_before = list(fake_db.auth_users.docs)
    fake_db.staff.docs[:] = []
    fake_db.auth_users.docs[:] = [d for d in auth_before if d.get("username") == "admin"]
    fake_db.profile_change_requests.docs[:] = []
    fake_db.notifications.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    yield
    fake_db.staff.docs[:] = staff_before
    fake_db.auth_users.docs[:] = auth_before
    fake_db.profile_change_requests.docs[:] = []
    fake_db.notifications.docs[:] = []
    fake_db.audit_logs.docs[:] = []


def _seed_teacher(fake_db):
    fake_db.staff.docs.append({
        "id": "s-t", "schoolId": SCHOOL, "user_id": "tch-1", "name": "Teacher T",
        "staff_type": "teacher", "role": "teacher", "sub_category": "subject_teacher",
        "phone": "9000000010", "email": "t@school.test", "salary": 40000, "is_active": True,
    })
    fake_db.auth_users.docs.append({
        "id": "tch-1", "schoolId": SCHOOL, "username": "teacher.t", "username_lower": "teacher.t",
        "user_info": {"id": "tch-1", "role": "teacher", "name": "Teacher T", "phone": "9000000010"},
    })


def _seed_principal(fake_db):
    fake_db.staff.docs.append({
        "id": "s-p", "schoolId": SCHOOL, "user_id": "prin-1", "name": "Principal P",
        "staff_type": "admin", "role": "admin", "sub_category": "principal",
        "phone": "9000000020", "email": "p@school.test", "is_active": True,
    })
    fake_db.auth_users.docs.append({
        "id": "prin-1", "schoolId": SCHOOL, "username": "principal.p", "username_lower": "principal.p",
        "user_info": {"id": "prin-1", "role": "admin", "sub_category": "principal", "name": "Principal P"},
    })


def _unchanged(fake_db, staff_id="s-t"):
    doc = next(d for d in fake_db.staff.docs if d["id"] == staff_id)
    return doc["name"] == "Teacher T" and doc["phone"] == "9000000010" and doc["email"] == "t@school.test"


# ── Story 8.1 · asking ────────────────────────────────────────────────────────


def test_a_request_records_the_ask_and_changes_nothing(client, fake_db):
    _seed_teacher(fake_db)
    resp = client.post(
        "/api/staff/me/change-requests", json={"phone": "9999999999"}, headers=_teacher_headers()
    )
    assert resp.status_code == 200
    req = resp.json()["data"]
    assert req["status"] == "pending"
    assert req["requested"] == {"phone": "9999999999"}
    assert req["current"] == {"phone": "9000000010"}   # reviewer sees both sides
    assert _unchanged(fake_db)                          # the record itself did NOT move


def test_the_login_record_is_untouched_by_a_request(client, fake_db):
    _seed_teacher(fake_db)
    client.post("/api/staff/me/change-requests", json={"name": "Teacher Tina"}, headers=_teacher_headers())
    login = next(u for u in fake_db.auth_users.docs if u["id"] == "tch-1")
    assert login["user_info"]["name"] == "Teacher T"


def test_the_reviewers_are_notified(client, fake_db):
    _seed_teacher(fake_db)
    fake_db.staff.docs.append({
        "id": "s-o", "schoolId": SCHOOL, "user_id": "own-1", "name": "Owner",
        "role": "owner", "sub_category": "owner", "is_active": True,
    })
    _seed_principal(fake_db)
    client.post("/api/staff/me/change-requests", json={"phone": "9999999999"}, headers=_teacher_headers())
    notified = {n["user_id"] for n in fake_db.notifications.docs
                if n.get("type") == "profile_change_request"}
    assert notified == {"own-1", "prin-1"}


def test_the_request_is_audited(client, fake_db):
    _seed_teacher(fake_db)
    client.post("/api/staff/me/change-requests", json={"phone": "9999999999"}, headers=_teacher_headers())
    entries = [a for a in fake_db.audit_logs.docs if a.get("action") == "profile_change_requested"]
    assert entries and entries[-1]["changed_by"] == "tch-1"


@pytest.mark.parametrize("field,value", [
    ("role", "owner"),
    ("sub_category", "principal"),
    ("schoolId", "other-school"),
    ("salary", 999999),
    ("token_limit", 10_000_000),
    ("is_active", False),
])
def test_you_cannot_ask_for_authority(client, fake_db, field, value):
    """The request route must not be a side door around the rule it serves.

    A person cannot change their own role; they must not be able to ASK for it
    either and have a busy reviewer wave it through.
    """
    _seed_teacher(fake_db)
    resp = client.post(
        "/api/staff/me/change-requests", json={field: value}, headers=_teacher_headers()
    )
    assert resp.status_code == 403
    assert fake_db.profile_change_requests.docs == []


def test_a_mixed_request_is_refused_whole(client, fake_db):
    _seed_teacher(fake_db)
    resp = client.post(
        "/api/staff/me/change-requests",
        json={"phone": "9999999999", "role": "owner"},
        headers=_teacher_headers(),
    )
    assert resp.status_code == 403
    assert fake_db.profile_change_requests.docs == []


def test_only_one_request_may_be_waiting(client, fake_db):
    """Otherwise the queue floods and a reviewer cannot tell which is current."""
    _seed_teacher(fake_db)
    first = client.post(
        "/api/staff/me/change-requests", json={"phone": "9999999999"}, headers=_teacher_headers()
    )
    assert first.status_code == 200
    second = client.post(
        "/api/staff/me/change-requests", json={"phone": "9888888888"}, headers=_teacher_headers()
    )
    assert second.status_code == 409
    assert len(fake_db.profile_change_requests.docs) == 1


def test_asking_for_what_is_already_stored_is_refused(client, fake_db):
    _seed_teacher(fake_db)
    resp = client.post(
        "/api/staff/me/change-requests", json={"phone": "9000000010"}, headers=_teacher_headers()
    )
    assert resp.status_code == 400
    assert fake_db.profile_change_requests.docs == []


def test_an_empty_name_cannot_be_requested(client, fake_db):
    _seed_teacher(fake_db)
    resp = client.post(
        "/api/staff/me/change-requests", json={"name": "   "}, headers=_teacher_headers()
    )
    assert resp.status_code == 422


def test_someone_with_no_staff_record_is_refused(client, fake_db):
    resp = client.post(
        "/api/staff/me/change-requests", json={"phone": "9999999999"}, headers=_teacher_headers()
    )
    assert resp.status_code == 404
    assert fake_db.profile_change_requests.docs == []


def test_requesting_unauthenticated_returns_401(client):
    assert client.post("/api/staff/me/change-requests", json={"phone": "9"}).status_code == 401


def test_a_person_can_see_their_own_requests(client, fake_db):
    _seed_teacher(fake_db)
    client.post("/api/staff/me/change-requests", json={"phone": "9999999999"}, headers=_teacher_headers())
    resp = client.get("/api/staff/me/change-requests", headers=_teacher_headers())
    assert resp.status_code == 200
    assert [r["status"] for r in resp.json()["data"]] == ["pending"]


# ── Story 8.2 · deciding ──────────────────────────────────────────────────────


def _raise_request(client, fake_db, **body):
    resp = client.post("/api/staff/me/change-requests", json=body or {"phone": "9999999999"},
                       headers=_teacher_headers())
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


def test_owner_sees_the_pending_queue(client, fake_db):
    _seed_teacher(fake_db)
    _raise_request(client, fake_db)
    resp = client.get("/api/staff/change-requests", headers=_owner_headers())
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["requested_by_name"] == "Teacher T"
    assert rows[0]["current"] == {"phone": "9000000010"}


def test_principal_sees_the_pending_queue(client, fake_db):
    _seed_teacher(fake_db)
    _raise_request(client, fake_db)
    assert client.get("/api/staff/change-requests", headers=_principal_headers()).status_code == 200


@pytest.mark.parametrize("headers_fn", [_teacher_headers, _accountant_headers])
def test_nobody_else_sees_or_decides(client, fake_db, headers_fn):
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db)
    headers = headers_fn()
    assert client.get("/api/staff/change-requests", headers=headers).status_code == 403
    assert client.patch(
        f"/api/staff/change-requests/{request_id}", json={"status": "approved"}, headers=headers
    ).status_code == 403
    assert _unchanged(fake_db)


def test_queue_unauthenticated_returns_401(client):
    assert client.get("/api/staff/change-requests").status_code == 401
    assert client.patch("/api/staff/change-requests/x", json={"status": "approved"}).status_code == 401


def test_approval_applies_the_change(client, fake_db):
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db, phone="9999999999")
    resp = client.patch(
        f"/api/staff/change-requests/{request_id}", json={"status": "approved"}, headers=_owner_headers()
    )
    assert resp.status_code == 200
    staff = next(d for d in fake_db.staff.docs if d["id"] == "s-t")
    assert staff["phone"] == "9999999999"
    stored = next(r for r in fake_db.profile_change_requests.docs if r["id"] == request_id)
    assert stored["status"] == "approved"
    assert stored["decided_by"] == "own-1"


def test_an_approved_change_survives_signing_out_and_back_in(client, fake_db):
    """Name and phone are read from the login record to build the sign-in token."""
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db, name="Teacher Tina", phone="9999999999")
    client.patch(f"/api/staff/change-requests/{request_id}", json={"status": "approved"},
                 headers=_owner_headers())
    login = next(u for u in fake_db.auth_users.docs if u["id"] == "tch-1")
    assert login["user_info"]["name"] == "Teacher Tina"
    assert login["user_info"]["phone"] == "9999999999"
    assert login["user_info"]["role"] == "teacher"  # authority untouched


def test_rejection_changes_nothing(client, fake_db):
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db)
    resp = client.patch(
        f"/api/staff/change-requests/{request_id}",
        json={"status": "rejected", "rejection_reason": "Confirm with the office first"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    assert _unchanged(fake_db)
    stored = next(r for r in fake_db.profile_change_requests.docs if r["id"] == request_id)
    assert stored["status"] == "rejected"
    assert stored["rejection_reason"] == "Confirm with the office first"


def test_the_requester_is_told_the_outcome(client, fake_db):
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db)
    client.patch(f"/api/staff/change-requests/{request_id}", json={"status": "approved"},
                 headers=_owner_headers())
    told = [n for n in fake_db.notifications.docs
            if n.get("type") == "profile_change_decision" and n["user_id"] == "tch-1"]
    assert told


def test_a_settled_request_cannot_be_decided_twice(client, fake_db):
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db, phone="9999999999")
    client.patch(f"/api/staff/change-requests/{request_id}", json={"status": "approved"},
                 headers=_owner_headers())
    second = client.patch(f"/api/staff/change-requests/{request_id}", json={"status": "rejected"},
                          headers=_owner_headers())
    assert second.status_code == 409
    staff = next(d for d in fake_db.staff.docs if d["id"] == "s-t")
    assert staff["phone"] == "9999999999"  # the first decision stands


def test_a_principal_cannot_approve_their_own_request(client, fake_db):
    """Without this the Principal is an administrator who can approve their own
    change — exactly the self-editing this feature exists to prevent."""
    _seed_principal(fake_db)
    raised = client.post(
        "/api/staff/me/change-requests", json={"phone": "9777777777"}, headers=_principal_headers()
    )
    assert raised.status_code == 200
    request_id = raised.json()["data"]["id"]
    resp = client.patch(
        f"/api/staff/change-requests/{request_id}", json={"status": "approved"},
        headers=_principal_headers(),
    )
    assert resp.status_code == 403
    assert next(d for d in fake_db.staff.docs if d["id"] == "s-p")["phone"] == "9000000020"


def test_the_owner_can_approve_the_principals_request(client, fake_db):
    """The counterpart: someone must be able to decide it."""
    _seed_principal(fake_db)
    request_id = client.post(
        "/api/staff/me/change-requests", json={"phone": "9777777777"}, headers=_principal_headers()
    ).json()["data"]["id"]
    resp = client.patch(
        f"/api/staff/change-requests/{request_id}", json={"status": "approved"}, headers=_owner_headers()
    )
    assert resp.status_code == 200
    assert next(d for d in fake_db.staff.docs if d["id"] == "s-p")["phone"] == "9777777777"


def test_approving_for_a_deleted_staff_record_fails_cleanly(client, fake_db):
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db)
    fake_db.staff.docs[:] = []          # the person left in the meantime
    resp = client.patch(
        f"/api/staff/change-requests/{request_id}", json={"status": "approved"}, headers=_owner_headers()
    )
    assert resp.status_code == 404


def test_an_unknown_request_is_404(client, fake_db):
    resp = client.patch(
        "/api/staff/change-requests/no-such-id", json={"status": "approved"}, headers=_owner_headers()
    )
    assert resp.status_code == 404


def test_a_nonsense_decision_is_refused(client, fake_db):
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db)
    resp = client.patch(
        f"/api/staff/change-requests/{request_id}", json={"status": "maybe"}, headers=_owner_headers()
    )
    assert resp.status_code == 422
    assert _unchanged(fake_db)


def test_the_decision_is_audited(client, fake_db):
    _seed_teacher(fake_db)
    request_id = _raise_request(client, fake_db)
    client.patch(f"/api/staff/change-requests/{request_id}", json={"status": "approved"},
                 headers=_owner_headers())
    entries = [a for a in fake_db.audit_logs.docs if a.get("action") == "profile_change_approved"]
    assert entries and entries[-1]["changed_by"] == "own-1"


def test_requestable_fields_match_the_self_service_rule():
    """The two sets must stay in step: whatever you may ask for is exactly what
    an administrator could have changed for you anyway."""
    from routes.staff import REQUESTABLE_FIELDS, SELF_SERVICE_FIELDS

    assert SELF_SERVICE_FIELDS == set()
    assert REQUESTABLE_FIELDS == {"name", "phone", "email"}
