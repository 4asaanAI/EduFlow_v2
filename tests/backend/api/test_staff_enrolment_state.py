from __future__ import annotations

"""POST /api/staff/{id}/enrolment - the three states for staff and teachers.

Owner request 10 decision 2, Abhimanyu 2026-08-06: NSO applies to students, staff AND
teachers, with the same three stages for all of them. Before this, `DELETE /api/staff/{id}`
switched a colleague off and nothing in the product could switch them back on - the same
one-way door that lost a student during the 2026-08-05 demo.
"""

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
PRINCIPAL = {"user_id": "prn-1", "role": "admin", "sub_category": "principal", "name": "P"}
ACCOUNTANT = {"user_id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "A"}
TEACHER = {"user_id": "tch-1", "role": "teacher", "name": "T"}


def _create(client, auth_headers, staff_data) -> str:
    # `staff_type` is required by the create route and the shared fixture does not
    # carry it, so it is supplied here rather than by widening a fixture other tests
    # already depend on.
    payload = {"staff_type": "teacher", **staff_data}
    resp = client.post("/api/staff/", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _set(client, headers, staff_id, state, **extra):
    return client.post(
        f"/api/staff/{staff_id}/enrolment",
        json={"state": state, **extra},
        headers=headers,
    )


# ─── Security pair, required for every new endpoint ─────────────────────────────

def test_staff_enrolment_unauthenticated_returns_401(client):
    resp = client.post("/api/staff/any-id/enrolment", json={"state": "active"})
    assert resp.status_code == 401


def test_staff_enrolment_wrong_role_returns_403(client):
    resp = _set(client, _bearer(TEACHER), "any-id", "active")
    assert resp.status_code == 403


def test_an_accountant_may_not_take_a_teacher_off_the_roll(client):
    resp = _set(client, _bearer(ACCOUNTANT), "any-id", "tc_issued")
    assert resp.status_code == 403


# ─── The three states ───────────────────────────────────────────────────────────

def test_a_teacher_can_be_put_on_the_nso_list(client, auth_headers, staff_data):
    staff_id = _create(client, auth_headers, staff_data)

    resp = _set(client, _bearer(OWNER), staff_id, "nso")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["state"] == "nso"
    assert body["data"]["status"] == "nso"
    assert body["data"]["is_active"] is False


def test_a_teacher_who_has_left_is_marked_tc_issued(client, auth_headers, staff_data):
    staff_id = _create(client, auth_headers, staff_data)
    body = _set(client, _bearer(OWNER), staff_id, "tc_issued").json()
    assert body["meta"]["state"] == "tc_issued"
    assert body["data"]["is_active"] is False


def test_an_unknown_state_is_refused(client, auth_headers, staff_data):
    staff_id = _create(client, auth_headers, staff_data)
    assert _set(client, _bearer(OWNER), staff_id, "sacked").status_code == 400


def test_a_missing_staff_member_is_a_404(client):
    assert _set(client, _bearer(OWNER), "no-such-staff", "active").status_code == 404


# ─── The way back ───────────────────────────────────────────────────────────────

def test_a_deactivated_teacher_can_be_restored(client, auth_headers, staff_data):
    staff_id = _create(client, auth_headers, staff_data)
    assert client.delete(f"/api/staff/{staff_id}", headers=auth_headers).status_code == 200

    listed = client.get("/api/staff/", headers=auth_headers).json()
    assert staff_id not in [s["id"] for s in listed["data"]]

    restored = _set(client, _bearer(OWNER), staff_id, "active")
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["is_active"] is True

    back = client.get("/api/staff/", headers=auth_headers).json()
    assert staff_id in [s["id"] for s in back["data"]]


def test_setting_the_state_it_already_has_changes_nothing(client, auth_headers, staff_data):
    staff_id = _create(client, auth_headers, staff_data)
    assert _set(client, _bearer(OWNER), staff_id, "nso").json()["meta"]["noop"] is False
    assert _set(client, _bearer(OWNER), staff_id, "nso").json()["meta"]["noop"] is True


# ─── The login follows the state ────────────────────────────────────────────────

def test_taking_a_teacher_off_the_roll_switches_their_login_off(client, auth_headers, staff_data, fake_db):
    """Someone who is no longer on the roll must not still be able to sign in."""
    resp = client.post("/api/staff/", json={"staff_type": "teacher", **staff_data}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    staff_id = resp.json()["data"]["id"]
    user_id = resp.json()["data"]["user_id"]
    assert user_id, "a staff record is always created with a login attached"

    _set(client, _bearer(OWNER), staff_id, "nso")

    account = next((u for u in fake_db.auth_users.docs if u.get("id") == user_id), None)
    assert account is not None
    assert account.get("is_active") is False


def test_putting_a_teacher_back_on_the_roll_switches_their_login_on(client, auth_headers, staff_data, fake_db):
    resp = client.post("/api/staff/", json={"staff_type": "teacher", **staff_data}, headers=auth_headers)
    staff_id = resp.json()["data"]["id"]
    user_id = resp.json()["data"]["user_id"]

    _set(client, _bearer(OWNER), staff_id, "tc_issued")
    _set(client, _bearer(OWNER), staff_id, "active")

    account = next((u for u in fake_db.auth_users.docs if u.get("id") == user_id), None)
    assert account.get("is_active") is True


# ─── The log ────────────────────────────────────────────────────────────────────

def test_every_staff_move_is_recorded_with_who_and_what(client, auth_headers, staff_data, fake_db):
    staff_id = _create(client, auth_headers, staff_data)
    _set(client, _bearer(OWNER), staff_id, "nso", reason="Stopped reporting in November")

    rows = [
        a for a in fake_db.audit_logs.docs
        if a["entity_id"] == staff_id and a["action"] == "enrolment_nso"
    ]
    assert len(rows) == 1, "the move onto the NSO list was not recorded"
    row = rows[0]
    assert row["changed_by"] == OWNER["user_id"]
    assert row["changed_by_role"] == "owner"
    assert row["created_at"]
    assert row["reason"] == "Stopped reporting in November"
    assert row["changes"]["previous_state"] == {"previous": "active", "new": "nso"}


def test_a_staff_restore_is_logged_under_its_own_action(client, auth_headers, staff_data, fake_db):
    staff_id = _create(client, auth_headers, staff_data)
    client.delete(f"/api/staff/{staff_id}", headers=auth_headers)
    _set(client, _bearer(PRINCIPAL), staff_id, "active")

    rows = [
        a for a in fake_db.audit_logs.docs
        if a["entity_id"] == staff_id and a["action"] == "enrolment_active"
    ]
    assert len(rows) == 1
    assert rows[0]["changed_by"] == PRINCIPAL["user_id"]


# ─── Permanent erasure, owner only, reason compulsory ───────────────────────────

def test_staff_erase_unauthenticated_returns_401(client):
    assert client.post("/api/staff/any-id/erase", data={"reason": "x" * 12}).status_code == 401


def test_staff_erase_wrong_role_returns_403(client):
    resp = client.post(
        "/api/staff/any-id/erase", data={"reason": "x" * 12}, headers=_bearer(PRINCIPAL)
    )
    assert resp.status_code == 403


def test_staff_erase_without_a_reason_is_refused(client, auth_headers, staff_data):
    staff_id = _create(client, auth_headers, staff_data)
    resp = client.post(f"/api/staff/{staff_id}/erase", data={}, headers=_bearer(OWNER))
    assert resp.status_code == 400


def test_staff_erase_with_a_token_reason_is_refused(client, auth_headers, staff_data):
    # Ten characters is the bar. "x" is what a person types when the box is in the way.
    staff_id = _create(client, auth_headers, staff_data)
    resp = client.post(f"/api/staff/{staff_id}/erase", data={"reason": "x"}, headers=_bearer(OWNER))
    assert resp.status_code == 400


def test_staff_erase_destroys_the_record_and_keeps_the_reason(client, auth_headers, staff_data, fake_db):
    staff_id = _create(client, auth_headers, staff_data)

    resp = client.post(
        f"/api/staff/{staff_id}/erase",
        data={"reason": "Duplicate record created during the data import"},
        headers=_bearer(OWNER),
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["erasure_token"]
    assert not [s for s in fake_db.staff.docs if s.get("id") == staff_id]
    rows = [a for a in fake_db.audit_logs.docs if a["entity_id"] == staff_id and a["action"] == "dpdp_erase"]
    assert len(rows) == 1
    assert rows[0]["reason"] == "Duplicate record created during the data import"
    # The whole record is copied into the log before it is destroyed, so the school
    # can still answer "what did we delete" afterwards.
    assert rows[0]["changes"]["staff_snapshot"]["id"] == staff_id
