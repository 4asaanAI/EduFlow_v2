from __future__ import annotations

"""POST /api/students/{id}/enrolment - the way out of the roll and the way back.

Owner requests 9 and 10, 2026-08-06.

The case that produced the report: a student was deactivated during a demo and could
not be recovered, because `is_active` was absent from UPDATABLE_FIELDS and no endpoint
and no AI tool could write it. The record had been there the whole time; the headcount
read 1,801 and nothing in the product could put the 1,802nd back.
"""

import pytest

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
PRINCIPAL = {"user_id": "prn-1", "role": "admin", "sub_category": "principal", "name": "P"}
ACCOUNTANT = {"user_id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "A"}
TEACHER = {"user_id": "tch-1", "role": "teacher", "name": "T"}


def _create(client, auth_headers, student_data) -> str:
    resp = client.post("/api/students", json=student_data, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _set(client, headers, student_id, state, **extra):
    return client.post(
        f"/api/students/{student_id}/enrolment",
        json={"state": state, **extra},
        headers=headers,
    )


# ─── Security pair, required for every new endpoint ─────────────────────────────

def test_enrolment_unauthenticated_returns_401(client):
    resp = client.post("/api/students/any-id/enrolment", json={"state": "active"})
    assert resp.status_code == 401


def test_enrolment_wrong_role_returns_403(client):
    resp = _set(client, _bearer(TEACHER), "any-id", "active")
    assert resp.status_code == 403


def test_an_accountant_may_not_decide_a_child_has_left(client):
    # Deciding a student has left the school, or putting one back on the roll, is a
    # head-of-school decision. The wider admin set can still deactivate.
    resp = _set(client, _bearer(ACCOUNTANT), "any-id", "tc_issued")
    assert resp.status_code == 403


# ─── The three states ───────────────────────────────────────────────────────────

def test_a_student_can_be_put_on_the_nso_list(client, auth_headers, student_data):
    student_id = _create(client, auth_headers, student_data)

    resp = _set(client, _bearer(OWNER), student_id, "nso")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meta"]["state"] == "nso"
    assert body["data"]["status"] == "nso"
    # Off the roll: an NSO student is not counted in "how many students are there".
    assert body["data"]["is_active"] is False


def test_an_nso_student_has_no_leaving_date(client, auth_headers, student_data):
    # A leaving date belongs to the TC. An NSO student has not left; they have stopped
    # turning up, which is a different thing and the whole reason the list exists.
    student_id = _create(client, auth_headers, student_data)
    body = _set(client, _bearer(OWNER), student_id, "nso").json()
    assert not body["data"].get("withdrawal_date")


def test_issuing_a_tc_stamps_the_leaving_date(client, auth_headers, student_data):
    student_id = _create(client, auth_headers, student_data)
    body = _set(client, _bearer(OWNER), student_id, "tc_issued").json()
    assert body["meta"]["state"] == "tc_issued"
    assert body["data"]["withdrawal_date"]


def test_an_unknown_state_is_refused(client, auth_headers, student_data):
    student_id = _create(client, auth_headers, student_data)
    resp = _set(client, _bearer(OWNER), student_id, "deleted")
    assert resp.status_code == 400


def test_a_missing_student_is_a_404_not_a_silent_success(client):
    resp = _set(client, _bearer(OWNER), "no-such-student", "active")
    assert resp.status_code == 404


# ─── The way back - owner request 9 ─────────────────────────────────────────────

def test_a_deactivated_student_can_be_restored(client, auth_headers, student_data):
    """THE test for owner request 9. Deactivate exactly as the row button does, then
    put the student back. Before this endpoint the second half was impossible."""
    student_id = _create(client, auth_headers, student_data)
    assert client.delete(f"/api/students/{student_id}", headers=auth_headers).status_code == 200

    # Gone from the default listing, which is why the count read one short.
    listed = client.get("/api/students", headers=auth_headers).json()
    assert student_id not in [s["id"] for s in listed["data"]]

    restored = _set(client, _bearer(OWNER), student_id, "active")
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["is_active"] is True
    assert restored.json()["data"]["status"] == "active"

    back = client.get("/api/students", headers=auth_headers).json()
    assert student_id in [s["id"] for s in back["data"]]


def test_restoring_clears_the_leaving_date(client, auth_headers, student_data):
    # Without this a restored student carries a withdrawal date that every report
    # would still believe.
    student_id = _create(client, auth_headers, student_data)
    _set(client, _bearer(OWNER), student_id, "tc_issued")
    body = _set(client, _bearer(OWNER), student_id, "active").json()
    assert not body["data"].get("withdrawal_date")


def test_setting_the_state_it_already_has_changes_nothing(client, auth_headers, student_data):
    student_id = _create(client, auth_headers, student_data)
    body = _set(client, _bearer(OWNER), student_id, "active").json()
    assert body["meta"]["noop"] is True


# ─── The log ────────────────────────────────────────────────────────────────────

def test_every_move_is_recorded_with_who_and_what(client, auth_headers, student_data, fake_db):
    """Owner request 10: "each and every action happening over the live database should
    get recorded properly along with what happened, who took that action, when, and the
    note they wrote"."""
    student_id = _create(client, auth_headers, student_data)
    _set(client, _bearer(OWNER), student_id, "nso", reason="Stopped attending after Diwali")

    rows = [
        a for a in fake_db.audit_logs.docs
        if a["entity_id"] == student_id and a["action"] == "enrolment_nso"
    ]
    assert len(rows) == 1, "the move onto the NSO list was not recorded"
    row = rows[0]
    assert row["changed_by"] == OWNER["user_id"]
    assert row["changed_by_role"] == "owner"
    assert row["created_at"]
    assert row["reason"] == "Stopped attending after Diwali"
    assert row["changes"]["previous_state"] == {"previous": "active", "new": "nso"}


def test_a_restore_is_logged_under_its_own_action(client, auth_headers, student_data, fake_db):
    # "Who put this child back on the roll" has to be answerable without reading a
    # diff, which is why the action names the state rather than saying "update".
    student_id = _create(client, auth_headers, student_data)
    client.delete(f"/api/students/{student_id}", headers=auth_headers)
    _set(client, _bearer(PRINCIPAL), student_id, "active")

    rows = [
        a for a in fake_db.audit_logs.docs
        if a["entity_id"] == student_id and a["action"] == "enrolment_active"
    ]
    assert len(rows) == 1
    assert rows[0]["changed_by"] == PRINCIPAL["user_id"]


def test_a_reason_is_optional_for_a_reversible_move(client, auth_headers, student_data):
    # Compulsory only for permanent erasure, which destroys the record. Demanding a
    # paragraph for something reversible is how people learn to type "x" in the box.
    student_id = _create(client, auth_headers, student_data)
    assert _set(client, _bearer(OWNER), student_id, "nso").status_code == 200
