"""R3-2, 2026-08-15: the three defaults that leaked, pinned so they cannot come back.

None of these was decided by anybody. Each was a default that happened to be permissive,
sitting in a place nobody looked at again. They were found while surveying what Chaman
Singh's profile would land on, and they are fixed BEFORE granting him anything behind
them, because building access on top of a hole is how the hole gets forgotten.

Every test here asserts a REFUSAL. If one of them starts failing, somebody has widened
access, and the question to ask is who decided that, not how to make the test pass.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt


def _h(**claims):
    return {"Authorization": f"Bearer {create_jwt({'name': 'T', **claims})}"}


def _owner():
    return _h(user_id="o1", role="owner")


def _principal():
    return _h(user_id="p1", role="admin", sub_category="principal")


def _admin_no_job_title():
    """An admin carrying no sub_category at all.

    This is a data fault, not a profile: migration 016 exists precisely to backfill
    legacy rows so that none is left in this state, and `scope_resolver` already denies
    by default when it is missing. `issues.py` was the outlier that read it as
    'principal'.
    """
    return _h(user_id="ghost", role="admin")


def _teacher():
    return _h(user_id="t1", role="teacher")


# ── 1. An admin with no job title is not the principal ───────────────────────
#
# `_can_view_all` used to read `sub_category in ("principal", None)`. That one `None`
# handed the maintenance calendar, the contractor list, the whole issue register and the
# request history to any admin row missing its sub_category.


@pytest.mark.parametrize(
    "path",
    [
        "/api/issues/maintenance/schedule",
        "/api/issues/maintenance/vendors",
        "/api/issues/maintenance/vendors/preferred",
        "/api/issues",
    ],
)
def test_admin_with_no_job_title_is_refused(client, path):
    assert client.get(path, headers=_admin_no_job_title()).status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/issues/maintenance/schedule",
        "/api/issues/maintenance/vendors",
        "/api/issues",
    ],
)
def test_the_principal_still_reaches_all_of_it(client, path):
    """The narrowing must not cost the principal anything. He is the reason the helper
    exists."""
    assert client.get(path, headers=_principal()).status_code == 200


def test_admin_with_no_job_title_cannot_write_the_maintenance_calendar(client):
    resp = client.post(
        "/api/issues/maintenance/schedule",
        headers=_admin_no_job_title(),
        json={"title": "Service the buses", "scheduled_date": "2026-09-01"},
    )
    assert resp.status_code == 403


def test_admin_with_no_job_title_cannot_add_a_contractor(client):
    resp = client.post(
        "/api/issues/maintenance/vendors",
        headers=_admin_no_job_title(),
        json={"name": "Somebody"},
    )
    assert resp.status_code == 403


# ── 2. A single repair request is not less sensitive than the list ───────────
#
# `GET /api/issues/facility/{id}` was signed-in-only. Any account could read any repair
# request by its id, INCLUDING `estimated_cost` and `actual_cost`, while the list route
# beside it refused the same people. Facility requests are where every repair amount on
# this platform lives.

_A_REPAIR = {
    "id": "fr-r32",
    "schoolId": "aaryans-joya",
    "title": "Leaking tap",
    "status": "open",
    "priority": "medium",
    "created_at": "2026-08-15T00:00:00",
    "logged_by": "somebody-else",
    "estimated_cost": 4500,
    "actual_cost": 5200,
}


@pytest.fixture
def a_repair_request(fake_db):
    original = fake_db.facility_requests.docs[:]
    fake_db.facility_requests.docs = [dict(_A_REPAIR)]
    yield
    fake_db.facility_requests.docs = original


def test_a_teacher_cannot_read_somebody_elses_repair_request(client, a_repair_request):
    assert client.get("/api/issues/facility/fr-r32", headers=_teacher()).status_code == 403


def test_it_is_refused_a_repair_request_outright(client, a_repair_request):
    """The list route says in so many words that facility work is not IT's. The single
    record now agrees with it."""
    it = _h(user_id="it1", role="admin", sub_category="it_tech")
    assert client.get("/api/issues/facility/fr-r32", headers=it).status_code == 403


def test_an_admin_with_no_job_title_cannot_read_a_repair_amount(client, a_repair_request):
    assert client.get(
        "/api/issues/facility/fr-r32", headers=_admin_no_job_title()
    ).status_code == 403


def test_the_person_who_raised_it_may_still_follow_it_up(client, fake_db):
    """Refusing strangers must not refuse the person who reported the fault. Following up
    your own repair is not a permission grant."""
    original = fake_db.facility_requests.docs[:]
    fake_db.facility_requests.docs = [{**_A_REPAIR, "logged_by": "t1"}]
    try:
        assert client.get("/api/issues/facility/fr-r32", headers=_teacher()).status_code == 200
    finally:
        fake_db.facility_requests.docs = original


def test_owner_and_maintenance_still_read_it(client, a_repair_request):
    maint = _h(user_id="m1", role="admin", sub_category="maintenance")
    assert client.get("/api/issues/facility/fr-r32", headers=_owner()).status_code == 200
    assert client.get("/api/issues/facility/fr-r32", headers=maint).status_code == 200


# ── 3. The certificate list narrowed students and nobody else ────────────────
#
# `GET /api/ops/certificates` took care to limit a STUDENT to their own certificates and
# then handed every other signed-in account the school's whole list, transfer
# certificates included.


def test_a_teacher_cannot_read_the_schools_certificate_list(client):
    assert client.get("/api/ops/certificates", headers=_teacher()).status_code == 403


def test_a_guardian_cannot_read_the_schools_certificate_list(client):
    """Guardians reach their own ward through `/api/guardian`, so nothing is lost."""
    parent = _h(user_id="g1", role="parent")
    assert client.get("/api/ops/certificates", headers=parent).status_code == 403


def test_the_office_and_students_still_reach_it(client):
    assert client.get("/api/ops/certificates", headers=_owner()).status_code == 200
    assert client.get("/api/ops/certificates", headers=_principal()).status_code == 200
    student = _h(user_id="s1", role="student")
    assert client.get("/api/ops/certificates", headers=student).status_code == 200
