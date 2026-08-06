"""Who may permanently erase a student (owner request, 2026-08-07).

The principal reported there was no way to delete a student: the erase endpoint was
owner-only, so their screen offered View / Edit / Status and nothing else. Erase is now
owner or principal — and nobody else, because it anonymises attendance history and
purges notes and AI memory.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
PRINCIPAL = {"user_id": "prn-1", "role": "admin", "sub_category": "principal", "name": "Adesh Singh"}
ACCOUNTANT = {"user_id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "A"}
RECEPTIONIST = {"user_id": "rec-1", "role": "admin", "sub_category": "receptionist", "name": "R"}
TEACHER = {"user_id": "tch-1", "role": "teacher", "name": "T"}
STUDENT = {"user_id": "stu-1", "role": "student", "name": "S"}

GOOD_REASON = {"reason": "Parent submitted verified DPDP erasure request"}


def _make_student(client, auth_headers, student_data) -> str:
    return client.post("/api/students", json=student_data, headers=auth_headers).json()["data"]["id"]


class TestWhoMayErase:
    def test_principal_may_now_erase(self, client, auth_headers, student_data):
        sid = _make_student(client, auth_headers, student_data)

        resp = client.post(f"/api/students/{sid}/erase", data=GOOD_REASON, headers=_bearer(PRINCIPAL))

        assert resp.status_code == 200, resp.text

    def test_owner_may_still_erase(self, client, auth_headers, student_data):
        sid = _make_student(client, auth_headers, student_data)

        resp = client.post(f"/api/students/{sid}/erase", data=GOOD_REASON, headers=_bearer(OWNER))

        assert resp.status_code == 200, resp.text

    @pytest.mark.parametrize("who", [ACCOUNTANT, RECEPTIONIST, TEACHER, STUDENT],
                             ids=["accountant", "receptionist", "teacher", "student"])
    def test_nobody_else_may_erase(self, client, auth_headers, student_data, who):
        sid = _make_student(client, auth_headers, student_data)

        resp = client.post(f"/api/students/{sid}/erase", data=GOOD_REASON, headers=_bearer(who))

        assert resp.status_code == 403

    def test_erase_unauthenticated_returns_401(self, client):
        assert client.post("/api/students/any-id/erase", data=GOOD_REASON).status_code == 401


class TestTheSafeguardsAreUnchanged:
    """Widening WHO may erase must not soften WHAT erase demands."""

    def test_principal_still_needs_a_written_reason(self, client, auth_headers, student_data):
        sid = _make_student(client, auth_headers, student_data)

        resp = client.post(f"/api/students/{sid}/erase", data={"reason": "short"},
                           headers=_bearer(PRINCIPAL))

        assert resp.status_code == 400

    def test_principal_erase_is_written_to_the_audit_trail(self, client, auth_headers, student_data, fake_db):
        sid = _make_student(client, auth_headers, student_data)

        client.post(f"/api/students/{sid}/erase", data=GOOD_REASON, headers=_bearer(PRINCIPAL))

        erasures = [d for d in fake_db.audit_logs.docs if d.get("action") == "dpdp_erase"]
        assert erasures, "erasing a child must leave an audit row naming who did it"
        assert erasures[-1].get("changed_by") == PRINCIPAL["user_id"]

    def test_erasing_a_student_who_is_not_there_is_a_404(self, client):
        resp = client.post("/api/students/no-such-id/erase", data=GOOD_REASON,
                           headers=_bearer(PRINCIPAL))

        assert resp.status_code == 404
