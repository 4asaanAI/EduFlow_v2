"""UI Sweep Epic 1 — Access That Cannot Be Talked Around.

Story 1.1  owner authority is not grantable (or removable) through the staff API
Story 1.2  role / sub_category values the permission system does not recognize
Story 1.3  a person maintains their own contact details, not their own authority

Closes D-02: the 2026-07-22 change removed "Owner" from a dropdown and was
reported as closing the privilege-escalation hole. It did not — the API still
accepted it. These tests are the proof that it no longer does, and they are
written against the API, deliberately bypassing the UI entirely.
"""

from __future__ import annotations

import pytest

from middleware.auth import SUB_CATEGORIES_BY_ROLE, VALID_SUB_CATEGORIES, create_jwt
from services import staff_service
from services.actor_context import actor_ctx_from_user

pytestmark = pytest.mark.asyncio

SCHOOL = "aaryans-joya"
OWNER = {"id": "own-1", "role": "owner", "name": "Owner"}
PRINCIPAL = {"id": "prin-1", "role": "admin", "sub_category": "principal", "name": "P"}


def _headers(payload):
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner_headers():
    return _headers({"user_id": "own-1", "role": "owner", "name": "Owner"})


def _principal_headers():
    return _headers({"user_id": "prin-1", "role": "admin", "name": "P", "sub_category": "principal"})


def _teacher_headers():
    return _headers({"user_id": "tch-1", "role": "teacher", "name": "T"})


@pytest.fixture(autouse=True)
def _clean(fake_db):
    """Isolate every test — these assert on document COUNTS, so leftovers lie."""
    staff_before = list(fake_db.staff.docs)
    auth_before = list(fake_db.auth_users.docs)
    fake_db.staff.docs[:] = []
    fake_db.auth_users.docs[:] = [d for d in auth_before if d.get("username") == "admin"]
    fake_db.audit_logs.docs[:] = []
    yield
    fake_db.staff.docs[:] = staff_before
    fake_db.auth_users.docs[:] = auth_before
    fake_db.audit_logs.docs[:] = []


def _payload(**overrides):
    body = {"name": "New Person", "staff_type": "teacher", "email": "new.person@school.test"}
    body.update(overrides)
    return body


# ── Story 1.1 · create ────────────────────────────────────────────────────────


def test_owner_cannot_create_an_owner_through_the_api(client, fake_db):
    """The hole D-02 is about. Even the Owner cannot mint another owner here."""
    resp = client.post("/api/staff/", json=_payload(role="owner"), headers=_owner_headers())
    assert resp.status_code == 403


def test_admin_cannot_create_an_owner_through_the_api(client, fake_db):
    resp = client.post("/api/staff/", json=_payload(role="owner"), headers=_principal_headers())
    assert resp.status_code == 403


def test_denied_create_writes_neither_a_staff_record_nor_a_login(client, fake_db):
    """The gate runs BEFORE the login account is written.

    `auth_users.user_info.role` is what sign-in reads to mint the token, so a
    403 that still left a privileged login behind would be worse than no gate:
    it would look fixed.
    """
    logins_before = len(fake_db.auth_users.docs)
    resp = client.post("/api/staff/", json=_payload(role="owner"), headers=_owner_headers())
    assert resp.status_code == 403
    assert fake_db.staff.docs == []
    assert len(fake_db.auth_users.docs) == logins_before


def test_sub_category_owner_is_refused_on_create(client, fake_db):
    resp = client.post(
        "/api/staff/", json=_payload(role="admin", sub_category="owner"), headers=_owner_headers()
    )
    assert resp.status_code == 403
    assert fake_db.staff.docs == []


@pytest.mark.parametrize("spelling", ["owner", "Owner", "OWNER", " owner ", "OwNeR"])
def test_owner_role_refused_however_it_is_spelled(client, fake_db, spelling):
    """Case and whitespace must not be a way around the gate."""
    resp = client.post("/api/staff/", json=_payload(role=spelling), headers=_owner_headers())
    assert resp.status_code == 403
    assert fake_db.staff.docs == []


async def test_denied_create_is_audited_with_the_callers_id(fake_db):
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    with pytest.raises(staff_service.StaffAuthorizationError):
        await staff_service.create_staff(
            fake_db, ctx, {"name": "Sneaky", "staff_type": "teacher", "role": "owner"}
        )
    denials = [a for a in fake_db.audit_logs.docs if a.get("action") == "privilege_escalation_denied"]
    assert denials, "a refused privilege change must leave a record"
    assert denials[-1]["changed_by"] == "own-1"
    assert denials[-1]["changes"]["reason"] == "grant_owner_authority"


async def test_audit_failure_does_not_turn_the_403_into_a_500(fake_db, monkeypatch):
    """ADR-002 fail-open: a broken audit backend must not mask the denial."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("audit backend down")

    monkeypatch.setattr(staff_service, "_write_staff_audit", _boom)
    ctx = actor_ctx_from_user(OWNER, school_id=SCHOOL)
    with pytest.raises(staff_service.StaffAuthorizationError):
        await staff_service.create_staff(
            fake_db, ctx, {"name": "Sneaky", "staff_type": "teacher", "role": "owner"}
        )


# ── Story 1.1 · update ────────────────────────────────────────────────────────


def test_owner_cannot_promote_an_existing_staff_member_to_owner(client, fake_db):
    fake_db.staff.docs.append(
        {"id": "s-1", "schoolId": SCHOOL, "name": "Bob", "role": "teacher", "sub_category": None}
    )
    resp = client.patch("/api/staff/s-1", json={"role": "owner"}, headers=_owner_headers())
    assert resp.status_code == 403
    assert fake_db.staff.docs[0]["role"] == "teacher"


def test_the_last_owner_cannot_be_demoted_through_the_api(client, fake_db):
    """Owner cannot be re-granted here, so allowing removal could strand the
    school with no owner and no in-app way to appoint one."""
    fake_db.staff.docs.append(
        {"id": "s-own", "schoolId": SCHOOL, "name": "The Owner", "role": "owner", "sub_category": "owner"}
    )
    resp = client.patch("/api/staff/s-own", json={"role": "teacher"}, headers=_owner_headers())
    assert resp.status_code == 403
    assert fake_db.staff.docs[0]["role"] == "owner"


def test_owner_editing_their_own_record_may_resend_the_unchanged_role(client, fake_db):
    """The staff form posts every field back. Resending `role: "owner"` on a
    record that already holds it changes nothing and must not be refused —
    the rule is about a CHANGE of authority, not about a string in a body."""
    fake_db.staff.docs.append(
        {"id": "s-own2", "schoolId": SCHOOL, "name": "The Owner", "role": "owner",
         "sub_category": "owner", "phone": "9000000000"}
    )
    resp = client.patch(
        "/api/staff/s-own2",
        json={"name": "The Owner", "role": "owner", "sub_category": "owner", "phone": "9111111111"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    assert fake_db.staff.docs[0]["phone"] == "9111111111"
    assert fake_db.staff.docs[0]["role"] == "owner"


def test_owner_can_still_change_an_ordinary_role(client, fake_db):
    """The gate is owner-specific — normal role administration is untouched."""
    fake_db.staff.docs.append(
        {"id": "s-2", "schoolId": SCHOOL, "name": "Carol", "role": "teacher", "sub_category": None}
    )
    resp = client.patch(
        "/api/staff/s-2", json={"role": "admin", "sub_category": "receptionist"}, headers=_owner_headers()
    )
    assert resp.status_code == 200
    assert fake_db.staff.docs[0]["role"] == "admin"
    assert fake_db.staff.docs[0]["sub_category"] == "receptionist"


# ── Story 1.1 · D-12, staff records cannot claim someone else's login ─────────


async def test_a_staff_record_cannot_be_linked_to_an_owner_login(fake_db):
    """Otherwise deactivating that staff record would deactivate the owner's
    login and revoke their sessions — locking the owner out of the school."""
    fake_db.auth_users.docs.append({
        "id": "auth-owner", "schoolId": SCHOOL, "username": "theowner",
        "username_lower": "theowner", "user_info": {"id": "auth-owner", "role": "owner"},
    })
    ctx = actor_ctx_from_user(PRINCIPAL, school_id=SCHOOL)
    with pytest.raises(staff_service.StaffAuthorizationError):
        await staff_service.create_staff(
            fake_db, ctx, {"name": "Piggyback", "staff_type": "teacher", "user_id": "auth-owner"}
        )
    assert fake_db.staff.docs == []


async def test_a_login_already_claimed_by_another_staff_record_is_refused(fake_db):
    fake_db.auth_users.docs.append({
        "id": "auth-x", "schoolId": SCHOOL, "username": "someone",
        "username_lower": "someone", "user_info": {"id": "auth-x", "role": "teacher"},
    })
    fake_db.staff.docs.append(
        {"id": "s-x", "schoolId": SCHOOL, "name": "Existing", "role": "teacher", "user_id": "auth-x"}
    )
    ctx = actor_ctx_from_user(PRINCIPAL, school_id=SCHOOL)
    with pytest.raises(staff_service.StaffAuthorizationError):
        await staff_service.create_staff(
            fake_db, ctx, {"name": "Second Claim", "staff_type": "teacher", "user_id": "auth-x"}
        )
    assert len(fake_db.staff.docs) == 1


# ── Story 1.2 · values the permission system does not recognize ───────────────


def test_unrecognised_sub_category_is_rejected_with_422(client, fake_db):
    resp = client.post(
        "/api/staff/", json=_payload(role="admin", sub_category="acountant"), headers=_owner_headers()
    )
    assert resp.status_code == 422
    assert "sub_category" in resp.json()["detail"]
    assert fake_db.staff.docs == []


def test_sub_category_valid_but_wrong_for_the_role_is_rejected(client, fake_db):
    """`class_teacher` on an admin matches no permission rule, so it would
    silently grant nothing at all."""
    resp = client.post(
        "/api/staff/", json=_payload(role="admin", sub_category="class_teacher"), headers=_owner_headers()
    )
    assert resp.status_code == 422
    assert fake_db.staff.docs == []


def test_unrecognised_role_is_rejected_with_422(client, fake_db):
    """`principal` is a sub_category, not a role — accepted before this story,
    and it granted nothing."""
    resp = client.post("/api/staff/", json=_payload(role="principal"), headers=_owner_headers())
    assert resp.status_code == 422
    assert fake_db.staff.docs == []


def test_changing_only_the_role_cannot_strand_a_mismatched_sub_category(client, fake_db):
    """Found by the Epic 1 adversarial pass, not by the original ACs.

    Moving a class_teacher to role "admin" without sending a sub_category left
    `class_teacher` attached to an admin — the exact pairing that matches no
    permission rule, reached by changing the OTHER half of the pair. The record
    is judged as it will end up, not by the shape of the request.
    """
    fake_db.staff.docs.append(
        {"id": "s-pair", "schoolId": SCHOOL, "name": "Dev", "role": "teacher",
         "sub_category": "class_teacher"}
    )
    resp = client.patch("/api/staff/s-pair", json={"role": "admin"}, headers=_owner_headers())
    assert resp.status_code == 422
    assert "sub_category" in resp.json()["detail"]
    assert fake_db.staff.docs[0]["role"] == "teacher"


def test_changing_role_and_sub_category_together_is_accepted(client, fake_db):
    """The counterpart: supply a matching pair and the move goes through."""
    fake_db.staff.docs.append(
        {"id": "s-pair2", "schoolId": SCHOOL, "name": "Dev", "role": "teacher",
         "sub_category": "class_teacher"}
    )
    resp = client.patch(
        "/api/staff/s-pair2",
        json={"role": "admin", "sub_category": "receptionist"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200
    assert fake_db.staff.docs[0]["role"] == "admin"
    assert fake_db.staff.docs[0]["sub_category"] == "receptionist"


def test_a_legacy_stored_value_does_not_block_an_unrelated_edit(client, fake_db):
    """Validation applies to what is being WRITTEN, never to what is stored.

    Some of the 88 live records may carry a legacy spelling (`accounts` rather
    than `accountant`). If validating the stored value, the first person to fix
    a phone number on such a record would get an error they cannot clear.
    """
    fake_db.staff.docs.append(
        {"id": "s-legacy", "schoolId": SCHOOL, "name": "Old Record",
         "role": "admin", "sub_category": "accounts", "phone": "9000000001"}
    )
    resp = client.patch("/api/staff/s-legacy", json={"phone": "9000000002"}, headers=_owner_headers())
    assert resp.status_code == 200
    assert fake_db.staff.docs[0]["phone"] == "9000000002"
    assert fake_db.staff.docs[0]["sub_category"] == "accounts"  # left exactly as found


def test_every_valid_sub_category_belongs_to_exactly_one_role():
    """The grouped map and the flat set cannot drift apart."""
    flat = set()
    for subs in SUB_CATEGORIES_BY_ROLE.values():
        assert not (flat & set(subs)), "a sub_category must qualify exactly one role"
        flat |= set(subs)
    assert flat == set(VALID_SUB_CATEGORIES)


def test_the_ai_tool_description_matches_what_the_server_accepts():
    """D-13 — the prompt used to offer the model `role: "owner"` and a
    sub_category of `accounts`, neither of which the server will accept."""
    from ai.prompts import TOOL_CREATE_STAFF

    described = TOOL_CREATE_STAFF["params_schema"]["sub_category"]
    for canonical in SUB_CATEGORIES_BY_ROLE["admin"] | SUB_CATEGORIES_BY_ROLE["teacher"]:
        assert canonical in described, f"{canonical} missing from the tool description"
    assert "accounts," not in described, "legacy 'accounts' spelling is back in the prompt"
    assert "NEVER" in TOOL_CREATE_STAFF["params_schema"]["role"]


# ── Story 1.2 · standing endpoint-test convention ────────────────────────────


def test_staff_create_unauthenticated_returns_401(client):
    assert client.post("/api/staff/", json=_payload()).status_code == 401


def test_staff_update_unauthenticated_returns_401(client):
    assert client.patch("/api/staff/some-id", json={"name": "X"}).status_code == 401


def test_staff_create_wrong_role_returns_403(client):
    assert client.post("/api/staff/", json=_payload(), headers=_teacher_headers()).status_code == 403


def test_staff_update_wrong_role_returns_403(client):
    assert client.patch(
        "/api/staff/some-id", json={"name": "X"}, headers=_teacher_headers()
    ).status_code == 403


# ── Story 1.3 · maintain your own details, not your own authority ─────────────


def _seed_self(fake_db, **overrides):
    doc = {
        "id": "s-self", "schoolId": SCHOOL, "user_id": "tch-1", "name": "Teacher T",
        "staff_type": "teacher", "role": "teacher", "sub_category": "subject_teacher",
        "phone": "9000000010", "email": "t@school.test", "salary": 40000, "is_active": True,
    }
    doc.update(overrides)
    fake_db.staff.docs.append(doc)
    fake_db.auth_users.docs.append({
        "id": "tch-1", "schoolId": SCHOOL, "username": "teacher.t", "username_lower": "teacher.t",
        "user_info": {"id": "tch-1", "role": "teacher", "name": "Teacher T", "phone": "9000000010"},
    })
    return doc


@pytest.mark.parametrize("body", [
    {"name": "Teacher Tina"},
    {"phone": "9999999999"},
    {"email": "tina@school.test"},
    {"name": "Teacher Tina", "phone": "9999999999", "email": "tina@school.test"},
    {"role": "owner"},
    {"sub_category": "principal"},
    {"schoolId": "some-other-school"},
    {"salary": 999999},
    {"token_limit": 10_000_000},
    {"is_active": True},
    {"name": "Teacher Tina", "role": "owner"},
    {},
])
def test_nobody_changes_their_own_record(client, fake_db, body):
    """Owner's decision, 2026-07-22 — reversing the first version of this story.

    Changing your own name or phone number is itself a way to misuse an
    account, so nothing about your own record is self-editable: not the
    authority fields, and not the contact details either. Corrections are made
    by the Owner or Principal on the staff screen. Parametrised over contact
    details, authority fields, a mixed body and an empty one, because "refused"
    must not depend on WHAT was asked for.
    """
    _seed_self(fake_db)
    resp = client.patch("/api/staff/me", json=body, headers=_teacher_headers())
    assert resp.status_code == 403
    stored = fake_db.staff.docs[0]
    assert stored["name"] == "Teacher T"
    assert stored["phone"] == "9000000010"
    assert stored["email"] == "t@school.test"
    assert stored["role"] == "teacher"
    assert stored["sub_category"] == "subject_teacher"
    assert stored["schoolId"] == SCHOOL
    assert stored["salary"] == 40000


def test_the_owner_cannot_self_edit_either(client, fake_db):
    """The rule is not "staff are restricted" — it is "nobody edits themselves"."""
    fake_db.staff.docs.append({
        "id": "s-own3", "schoolId": SCHOOL, "user_id": "own-1", "name": "The Owner",
        "role": "owner", "sub_category": "owner", "phone": "9000000000",
    })
    resp = client.patch("/api/staff/me", json={"phone": "9111111111"}, headers=_owner_headers())
    assert resp.status_code == 403
    assert fake_db.staff.docs[0]["phone"] == "9000000000"


def test_a_self_edit_never_reaches_the_login_record(client, fake_db):
    """The login record carries the name and phone the JWT is minted from. A
    refused self-edit must not touch it either."""
    _seed_self(fake_db)
    client.patch("/api/staff/me", json={"name": "Teacher Tina"}, headers=_teacher_headers())
    login = next(u for u in fake_db.auth_users.docs if u["id"] == "tch-1")
    assert login["user_info"]["name"] == "Teacher T"
    assert login["user_info"]["phone"] == "9000000010"


def test_no_self_service_field_is_writable(client, fake_db):
    """Guards the empty allow-list itself. Epic 8 will replace this handler with
    "record a requested change"; until then, adding a field back here would
    silently restore direct self-editing."""
    from routes.staff import SELF_SERVICE_FIELDS

    assert SELF_SERVICE_FIELDS == set()


def test_the_refusal_says_who_can_make_the_change(client, fake_db):
    """A refusal that does not say what to do next is a dead end for a teacher
    whose phone number really has changed."""
    _seed_self(fake_db)
    resp = client.patch("/api/staff/me", json={"phone": "9999999999"}, headers=_teacher_headers())
    detail = resp.json()["detail"].lower()
    assert "owner" in detail and "principal" in detail


def test_self_profile_never_exposes_salary(client, fake_db):
    _seed_self(fake_db)
    resp = client.get("/api/staff/me", headers=_teacher_headers())
    assert resp.status_code == 200
    assert "salary" not in resp.json()["data"]


def test_self_profile_endpoints_are_not_shadowed_by_the_id_route(client, fake_db):
    """`/me` is declared before `/{staff_id}`. If that order is ever reversed,
    this asks for the staff member whose id is literally "me" and 404s."""
    _seed_self(fake_db)
    resp = client.get("/api/staff/me", headers=_teacher_headers())
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "s-self"


def test_self_profile_unauthenticated_returns_401(client):
    """401 before 403 — an anonymous caller is told to sign in, not told the
    rule about self-editing."""
    assert client.get("/api/staff/me").status_code == 401
    assert client.patch("/api/staff/me", json={"name": "X"}).status_code == 401
