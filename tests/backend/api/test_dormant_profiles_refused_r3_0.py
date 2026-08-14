"""R3-0: a profile whose release has not landed is turned away at the door.

Until 2026-08-14 "dormant" was documentation. Nothing at runtime read the `status` field,
so a dormant office account could reach any route whose gate said
`require_role("owner", "admin")`, which ignores the sub-category. The findings that
prompted this are recorded in
`_bmad-output/planning-artifacts/release-3-access-department-heads-2026-08-14.md`, Part 2.

The tests below are written as the harm, not as the mechanism: what a person could
actually do, so that a later refactor that keeps the function but loses the effect fails
here.
"""
from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from services.profile_matrix import DORMANT_PROFILES, LIVE_PROFILES


OFFICE_DORMANT = ("transport_head", "receptionist", "it_tech", "maintenance", "support_staff")


def _bearer(payload: dict) -> dict:
    return {"Authorization": "Bearer " + create_jwt(payload)}


def _office(sub_category: str) -> dict:
    return _bearer({
        "user_id": "u-" + sub_category,
        "name": "Office Person",
        "role": "admin",
        "sub_category": sub_category,
    })


# ─── The harm, closed ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("sub_category", OFFICE_DORMANT)
def test_a_dormant_office_profile_cannot_create_a_school_bus_route(client, sub_category):
    """The sharpest of the probe findings: this returned 200 before R3-0."""
    response = client.post(
        "/api/transport",
        json={"route_name": "Invented", "vehicle_number": "UP-00-0000"},
        headers=_office(sub_category),
    )
    assert response.status_code == 403


@pytest.mark.parametrize("sub_category", OFFICE_DORMANT)
@pytest.mark.parametrize("path", ["/api/students", "/api/staff", "/api/transport"])
def test_a_dormant_office_profile_cannot_read_the_school(client, sub_category, path):
    response = client.get(path, headers=_office(sub_category))
    assert response.status_code == 403


@pytest.mark.parametrize("sub_category", OFFICE_DORMANT)
def test_the_refusal_explains_itself_and_is_not_a_sign_in_failure(client, sub_category):
    """403 and not 401, with wording a person can act on.

    Telling somebody their password is wrong when it is right sends them off to reset a
    password that works, and they end up believing the platform is broken.
    """
    response = client.get("/api/students", headers=_office(sub_category))
    assert response.status_code == 403
    detail = response.json()["detail"].lower()
    assert "not switched on yet" in detail
    assert "nothing is wrong with your sign-in" in detail


# ─── The line the other way: nobody working today is disturbed ────────────────

@pytest.mark.parametrize("sub_category", ["principal", "accountant", "management"])
def test_a_live_office_profile_is_untouched(client, sub_category):
    """Release 2's people must not notice R3-0 at all."""
    response = client.get("/api/students", headers=_office(sub_category))
    assert response.status_code == 200


def test_the_owner_is_untouched(client):
    headers = _bearer({"user_id": "owner-1", "name": "Aman Litt", "role": "owner",
                       "sub_category": "owner"})
    assert client.get("/api/students", headers=headers).status_code == 200


@pytest.mark.parametrize("role", ["teacher", "student", "parent"])
def test_teachers_students_and_guardians_are_not_touched_by_this_gate(client, role):
    """Their rows are dormant too, and this gate deliberately leaves them alone.

    They are reached through their own routes, student logins can already be created
    through a real endpoint, and refusing them here would take out the child-facing side
    of the platform to fix an office problem. Whatever answer they got before R3-0 they
    still get: this asserts only that it is not R3-0's refusal.
    """
    headers = _bearer({"user_id": "u-" + role, "name": "Somebody", "role": role,
                       "sub_category": role})
    response = client.get("/api/students", headers=headers)
    if response.status_code == 403:
        assert "not switched on yet" not in response.json()["detail"].lower()


def test_an_admin_with_an_unrecognised_profile_is_logged_not_refused(client):
    """The one place this falls short of default-deny, on purpose.

    Three of the four shared desks in production carry sub-categories that are not
    profile names. Refusing the unknown might lock a working account out of a live
    school, so they are logged instead. If this test ever needs changing, read the
    docstring on `_refuse_if_release_has_not_landed` first: tightening it is a decision
    about real accounts, not a tidy-up.
    """
    headers = _bearer({"user_id": "desk-1", "name": "Reception Desk", "role": "admin",
                       "sub_category": "reception"})
    response = client.get("/api/students", headers=headers)
    if response.status_code == 403:
        assert "not switched on yet" not in response.json()["detail"].lower()


# ─── The table stays honest ───────────────────────────────────────────────────

def test_every_office_profile_named_here_is_still_dormant_in_the_table():
    """If a release switches one on, this list must shrink in the same change.

    Without this, R3-0's tests would keep asserting a refusal for somebody who has since
    been let in, and the suite would go red for the right reason at the wrong moment.
    """
    for name in OFFICE_DORMANT:
        assert name in DORMANT_PROFILES, (
            name + " is no longer dormant. Its release has landed, so remove it from "
            "OFFICE_DORMANT in this file as part of that release."
        )


def test_the_four_live_profiles_are_exactly_release_2s():
    assert set(LIVE_PROFILES) == {"owner", "principal", "accountant", "management"}
