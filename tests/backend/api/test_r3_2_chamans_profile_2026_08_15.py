"""R3-2, 2026-08-15: what Chaman Singh, the transport head, may and may not do.

Approved by Abhimanyu on 2026-08-15. The written record is
`_bmad-output/implementation-artifacts/release-3-access/R3-2-proposal-chamans-profile-2026-08-15.md`.

Six decisions, and every one of them is pinned below:

1. He holds full financial visibility of school TRANSPORT, fares and who owes what
   included, and NO other money at all.
2. He sees children who are on a bus. Not the other ~1,500.
3. He deletes a route, a vehicle, a driver or a conductor with Aman OR Adesh agreeing.
4. Drivers and conductors go on the staff roll with NO logins.
5. He sees what a VEHICLE repair costs, and not what repairs to buildings cost, and a
   repair cost is agreed before the money is committed.
6. He moves a child between routes himself, with nobody's approval.

**Why these are worth reading rather than counting.** Every test here that asserts a
refusal is protecting a boundary somebody drew on purpose. If one starts failing, the
question is who decided to move it, not how to make it pass.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt


def _h(**claims):
    return {"Authorization": f"Bearer {create_jwt({'name': 'T', **claims})}"}


def _chaman():
    return _h(user_id="chaman-1", role="admin", sub_category="transport_head")


def _owner():
    return _h(user_id="o1", role="owner")


# ─── 1. Transport money is his. No other money is. ────────────────────────────

def test_he_reaches_the_transport_fee_tool():
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    user = {"role": "admin", "sub_category": "transport_head", "id": "c1"}
    assert is_tool_authorized(user, TOOL_REGISTRY["get_transport_fee_status"]) is True


@pytest.mark.parametrize("money_tool", [
    "get_fee_summary",
    "get_fee_transactions",
    "get_fee_defaulters",
    "query_fee_status",
    "explain_student_fee",
    "get_financial_report",
    "get_payroll",
    "get_expenses",
    "record_fee_payment",
])
def test_no_other_money_reaches_him(money_tool):
    """The boundary is TRANSPORT money, not money. `explain_student_fee` is the one to
    watch: it answers with the class band, concessions, Right to Education places and the
    whole payment history, and it would have looked like a reasonable thing to grant a
    man who is allowed to see fares."""
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    user = {"role": "admin", "sub_category": "transport_head", "id": "c1"}
    assert is_tool_authorized(user, TOOL_REGISTRY[money_tool]) is False, money_tool


async def test_the_transport_fee_answer_carries_no_tuition_or_concession():
    """Checked on the tool's OUTPUT, not on its permission. A tool that is allowed to
    answer with tuition is one refactor away from doing so, whoever holds it."""
    from ai.tool_functions_v2 import tool_get_transport_fee_status

    user = {"role": "admin", "sub_category": "transport_head", "id": "c1"}
    result = await (
        tool_get_transport_fee_status({}, user)
    )
    # Checked on the RIDER ROWS, not on the whole payload: the answer carries a note
    # saying in words that tuition and concessions are not in it, and matching against
    # the whole thing would trip on the note that exists to make the boundary clear.
    keys = {"riders", "riders_on_the_bus", "monthly_transport_billing",
            "children_with_no_fare_set", "note"}
    assert set(result["data"]) == keys, (
        "the transport fee answer grew a field. Every one has to be transport, so a new "
        "key needs somebody to have decided it: " + str(sorted(set(result["data"]) - keys))
    )
    allowed_per_rider = {"student_id", "name", "admission_number", "class", "route",
                         "stop", "monthly_fare", "fare_is_set", "transport_fee_cleared"}
    for rider in result["data"]["riders"]:
        assert set(rider) <= allowed_per_rider, sorted(set(rider) - allowed_per_rider)


async def test_a_child_with_no_fare_set_is_counted_separately_not_as_zero():
    """A child nobody has priced and a child who pays nothing are opposite facts.
    Adding them together is how a monthly total quietly comes out short."""
    from ai.tool_functions_v2 import tool_get_transport_fee_status

    result = await (
        tool_get_transport_fee_status({}, {"role": "owner", "id": "o1"})
    )
    assert "children_with_no_fare_set" in result["data"]


# ─── 2. Children on a bus, and only those ─────────────────────────────────────

_RIDER = {"id": "kid-bus", "schoolId": "aaryans-joya", "name": "Rides The Bus",
          "admission_number": "A-1", "is_active": True, "route_zone_id": "route-1",
          "address": "12 Some Lane", "class_name": "5-A"}
_WALKER = {"id": "kid-walks", "schoolId": "aaryans-joya", "name": "Walks To School",
           "admission_number": "A-2", "is_active": True, "route_zone_id": "",
           "address": "99 Other Lane", "class_name": "5-A"}


@pytest.fixture
def two_children(fake_db):
    original = fake_db.students.docs[:]
    fake_db.students.docs = [dict(_RIDER), dict(_WALKER)]
    yield
    fake_db.students.docs = original


def test_the_student_list_shows_him_only_children_on_a_bus(client, two_children):
    resp = client.get("/api/students", headers=_chaman())
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()["data"]}
    assert names == {"Rides The Bus"}


def test_the_count_agrees_with_the_rows(client, two_children):
    """A total that says 2 over a list of 1 is the 'partial answer that reads as
    complete' fault Release 3 was written to remove."""
    resp = client.get("/api/students", headers=_chaman())
    body = resp.json()
    assert body["meta"]["total"] == len(body["data"]) == 1


def test_the_owner_still_sees_both(client, two_children):
    """The narrowing is his alone. If this fails, a filter meant for one profile has
    been applied to the school."""
    resp = client.get("/api/students", headers=_owner())
    assert len(resp.json()["data"]) == 2


def test_typing_the_id_of_a_child_who_does_not_ride_answers_not_found(client, two_children):
    """404 rather than 403, matching the list. Saying 'that child exists but is not
    yours' still tells him the child is there."""
    assert client.get("/api/students/kid-walks", headers=_chaman()).status_code == 404
    assert client.get("/api/students/kid-bus", headers=_chaman()).status_code == 200


def test_the_roster_does_not_fall_back_to_the_whole_school(client, two_children):
    """Its own docstring promised a zone-specific list, and without a zone_id it used to
    return every child in the school with 'Not Assigned' beside them."""
    resp = client.get("/api/ops/transport/roster", headers=_chaman())
    assert resp.status_code == 200
    assert {s["name"] for s in resp.json()["data"]} == {"Rides The Bus"}


async def test_he_can_look_up_one_child_by_admission_number_to_add_them(client, two_children):
    """The hole the narrowing opened: a child's FIRST day on a bus means finding a child
    who is not on one. This answers that and nothing else."""
    from ai.tool_functions_v2 import tool_get_student_to_add_to_a_route

    result = await (
        tool_get_student_to_add_to_a_route({"admission_number": "A-2"}, {"role": "admin", "sub_category": "transport_head", "id": "c1"})
    )
    assert result["success"] is True
    assert result["data"]["name"] == "Walks To School"
    assert result["data"]["already_on_a_route"] is False
    # And it hands over nothing he was not given.
    for leaked in ("address", "guardian_phone", "fees", "phone"):
        assert leaked not in result["data"], leaked


async def test_that_lookup_refuses_to_be_used_as_a_search(client, two_children):
    """Without this it is the narrowing undone in slow motion: a name search would let
    him walk the roll a letter at a time."""
    from ai.tool_functions_v2 import tool_get_student_to_add_to_a_route

    result = await (
        tool_get_student_to_add_to_a_route({"admission_number": ""}, {"role": "admin", "sub_category": "transport_head", "id": "c1"})
    )
    assert result["success"] is False


# ─── 3 and 6. He moves a child himself; he deletes only with agreement ────────

def test_he_moves_a_child_between_routes_with_nobody_approving():
    """Answer 1 of 2026-08-11, and it is the thing he does most days."""
    from services.student_service import TRANSPORT_HEAD_FIELDS

    assert {"route_zone_id", "transport_stop"} <= TRANSPORT_HEAD_FIELDS


def test_he_cannot_edit_anything_else_about_a_child():
    from services.student_service import TRANSPORT_HEAD_FIELDS

    for not_his in ("name", "class_id", "admission_number", "address", "status"):
        assert not_his not in TRANSPORT_HEAD_FIELDS, not_his


def test_he_cannot_set_what_a_family_is_charged_for_the_bus():
    """Seeing what a family is charged and DECIDING it are different acts. He was given
    the first. Setting the fare on a route is his; setting it on a child is billing."""
    from services.student_service import TRANSPORT_HEAD_FIELDS

    assert "transport_monthly_fare" not in TRANSPORT_HEAD_FIELDS


# ─── 4. Drivers and conductors: on the roll, with no logins ───────────────────

async def test_a_driver_created_by_him_gets_no_login(fake_db):
    from services.actor_context import ActorContext
    from services.staff_service import create_staff

    ctx = ActorContext(user_id="chaman-1", role="admin", sub_category="transport_head",
                       school_id="aaryans-joya", branch_id=None)
    before = len(fake_db.auth_users.docs)
    result = await (
        create_staff(fake_db, ctx, {"name": "A Driver", "staff_type": "transport"})
    )
    assert result["staff"]["user_id"] == ""
    assert result["temporary_password"] is None
    assert len(fake_db.auth_users.docs) == before, "a login was minted for a driver"


async def test_he_cannot_smuggle_a_login_in_with_the_driver(fake_db):
    """Refused outright rather than the password being quietly dropped. Silently
    ignoring it would report success and leave the next person believing a login exists."""
    from services.actor_context import ActorContext
    from services.staff_service import create_staff, StaffAuthorizationError

    ctx = ActorContext(user_id="chaman-1", role="admin", sub_category="transport_head",
                       school_id="aaryans-joya", branch_id=None)
    with pytest.raises(StaffAuthorizationError):
        await (
            create_staff(fake_db, ctx, {"name": "A Driver", "staff_type": "transport",
                                        "password": "letmein12345"})
        )


async def test_he_cannot_create_a_teacher_or_an_office_desk(fake_db):
    """The gate narrowing staff creation to the owner and the principal was closed on
    2026-08-15 because creating a colleague mints a login. This must not reopen it."""
    from services.actor_context import ActorContext
    from services.staff_service import create_staff, StaffAuthorizationError

    ctx = ActorContext(user_id="chaman-1", role="admin", sub_category="transport_head",
                       school_id="aaryans-joya", branch_id=None)
    for staff_type in ("teacher", "admin", "support"):
        with pytest.raises(StaffAuthorizationError):
            await (
                create_staff(fake_db, ctx, {"name": "Somebody", "staff_type": staff_type})
            )


async def test_drivers_and_conductors_are_not_filed_as_support_staff(fake_db):
    """Answer 10 of 2026-08-11 took them OUT of support staff and gave them their own
    place. R3-3 built it so the record is truthful."""
    from services.actor_context import ActorContext
    from services.staff_service import create_staff

    ctx = ActorContext(user_id="chaman-1", role="admin", sub_category="transport_head",
                       school_id="aaryans-joya", branch_id=None)
    result = await (
        create_staff(fake_db, ctx, {"name": "A Conductor", "staff_type": "transport"})
    )
    assert result["staff"]["sub_category"] == "transport_staff"


def test_the_tenth_profile_holds_nothing_at_all():
    from services.profile_matrix import PROFILE_MATRIX

    entry = PROFILE_MATRIX["transport_staff"]
    assert entry["status"] == "dormant"
    assert not entry["screens"]
    assert not entry["tool_domains"]
    assert entry["may_write"] is False


# ─── 5. Vehicle repair costs yes, building repair costs no ────────────────────

_VEHICLE_REPAIR = {"id": "fr-bus", "schoolId": "aaryans-joya", "type": "facility",
                   "description": "Bus brakes", "category": "vehicle", "status": "open",
                   "priority": "high", "created_at": "2026-08-15T00:00:00",
                   "logged_by": "chaman-1", "estimated_cost": 8000}
_BUILDING_REPAIR = {"id": "fr-tap", "schoolId": "aaryans-joya", "type": "facility",
                    "description": "Leaking tap", "category": "plumbing", "status": "open",
                    "priority": "low", "created_at": "2026-08-15T00:00:00",
                    "logged_by": "someone", "estimated_cost": 500}


@pytest.fixture
def two_repairs(fake_db):
    original = fake_db.facility_requests.docs[:]
    fake_db.facility_requests.docs = [dict(_VEHICLE_REPAIR), dict(_BUILDING_REPAIR)]
    yield
    fake_db.facility_requests.docs = original


def test_he_sees_the_cost_of_a_vehicle_repair(client, two_repairs):
    resp = client.get("/api/issues/facility/fr-bus", headers=_chaman())
    assert resp.status_code == 200
    assert resp.json()["data"]["estimated_cost"] == 8000


def test_he_does_not_see_the_cost_of_a_building_repair(client, two_repairs):
    """Removed, not zeroed. A repair showing 0 and a repair nobody has priced look the
    same, and this platform has been bitten by a partial answer reading as complete."""
    resp = client.get("/api/issues/facility/fr-tap", headers=_chaman())
    body = resp.json()
    if resp.status_code == 200:
        assert "estimated_cost" not in body["data"]
        assert "actual_cost" not in body["data"]
    else:
        assert resp.status_code == 403


def test_the_repair_list_hides_building_repairs_from_him(client, two_repairs):
    resp = client.get("/api/issues/facility", headers=_chaman())
    assert resp.status_code == 200
    assert {r["id"] for r in resp.json()["data"]} == {"fr-bus"}


def test_he_cannot_ask_for_the_building_queue_by_naming_its_category(client, two_repairs):
    """The restriction and the caller's own `category` filter are set on the same key,
    so a plain assignment would have let him read the whole campus queue."""
    resp = client.get("/api/issues/facility?category=plumbing", headers=_chaman())
    assert resp.status_code == 403


def test_a_repair_cost_is_agreed_before_the_money_is_committed(client, two_repairs, fake_db):
    resp = client.post("/api/issues/facility/fr-bus/propose-cost",
                       headers=_chaman(), json={"estimated_cost": 12000})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["awaiting_approval"] is True
    # The figure has NOT landed on the request. It waits beside it.
    stored = next(r for r in fake_db.facility_requests.docs if r["id"] == "fr-bus")
    assert stored["estimated_cost"] == 8000, "the proposed cost overwrote the real one"
    assert stored["cost_awaiting_approval"] == 12000
    # And somebody has actually been asked.
    approval = next(a for a in fake_db.approval_requests.docs
                    if a["id"] == body["data"]["approval_id"])
    assert approval["status"] == "pending"
    assert approval["routing"] == "owner_and_principal"


def test_he_cannot_propose_a_cost_for_a_building_repair(client, two_repairs):
    resp = client.post("/api/issues/facility/fr-tap/propose-cost",
                       headers=_chaman(), json={"estimated_cost": 900})
    assert resp.status_code == 403


# ─── The second source of truth this release also had to close ────────────────

def test_he_can_report_a_problem(client):
    """He holds the 'report a problem' screen and arranges the servicing, so a screen he
    is offered has to work when he presses it."""
    resp = client.post("/api/issues/facility", headers=_chaman(),
                       json={"description": "Bus 3 making a noise", "category": "vehicle"})
    assert resp.status_code in (200, 201), resp.text


# ─── 3. Deleting needs Aman OR Adesh, and approving actually deletes ──────────

_A_ROUTE = {"id": "route-9", "schoolId": "aaryans-joya", "route_name": "Joya Town",
            "is_active": True}


@pytest.fixture
def a_route(fake_db):
    original = fake_db.transport_routes.docs[:]
    students = fake_db.students.docs[:]
    fake_db.transport_routes.docs = [dict(_A_ROUTE)]
    fake_db.students.docs = []
    yield
    fake_db.transport_routes.docs = original
    fake_db.students.docs = students


def test_his_delete_records_a_request_and_deletes_nothing(client, a_route, fake_db):
    resp = client.delete("/api/ops/transport/route-9", headers=_chaman())
    # 202, not 200: "sent for agreement" and "deleted" are different facts and the screen
    # has to be able to tell them apart.
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["awaiting_approval"] is True
    assert fake_db.transport_routes.docs, "the route was deleted without agreement"
    approval = next(a for a in fake_db.approval_requests.docs
                    if a["id"] == body["data"]["approval_id"])
    assert approval["routing"] == "owner_and_principal", "only one of them was asked"
    assert approval["pending_action"]["kind"] == "delete_transport_route"


def test_approving_it_actually_deletes_the_route(client, a_route, fake_db):
    """The whole reason the request CARRIES the action. The cheap version - raise a
    request and leave somebody to go and delete it by hand - produces a card saying
    APPROVED over a route that is still there."""
    created = client.delete("/api/ops/transport/route-9", headers=_chaman()).json()
    approval_id = created["data"]["approval_id"]

    resp = client.patch(f"/api/operations/approval-requests/{approval_id}/decide",
                        headers=_owner(),
                        json={"status": "approved", "reason": "Route no longer runs"})
    assert resp.status_code == 200, resp.text
    assert not fake_db.transport_routes.docs, "approved, and the route is still there"


def test_rejecting_it_deletes_nothing(client, a_route, fake_db):
    created = client.delete("/api/ops/transport/route-9", headers=_chaman()).json()
    approval_id = created["data"]["approval_id"]

    resp = client.patch(f"/api/operations/approval-requests/{approval_id}/decide",
                        headers=_owner(),
                        json={"status": "rejected", "reason": "Still needed"})
    assert resp.status_code == 200, resp.text
    assert fake_db.transport_routes.docs, "rejected, and the route was deleted anyway"


def test_the_principal_can_agree_it_too(client, a_route, fake_db):
    """Abhimanyu, 2026-08-15: Aman OR Adesh, either one. Not both."""
    created = client.delete("/api/ops/transport/route-9", headers=_chaman()).json()
    approval_id = created["data"]["approval_id"]

    resp = client.patch(
        f"/api/operations/approval-requests/{approval_id}/decide",
        headers=_h(user_id="p1", role="admin", sub_category="principal"),
        json={"status": "approved", "reason": "Agreed"},
    )
    assert resp.status_code == 200, resp.text
    assert not fake_db.transport_routes.docs


def test_the_owner_still_deletes_a_route_outright(client, a_route, fake_db):
    """The approval step is the transport head's alone. Putting the owner behind it would
    take away something nobody asked to take away."""
    resp = client.delete("/api/ops/transport/route-9", headers=_owner())
    assert resp.status_code == 200
    assert not fake_db.transport_routes.docs


def test_children_still_on_a_route_is_refused_without_troubling_anybody(client, fake_db):
    """Checked BEFORE the approval is raised. Sending Aman a request that would have been
    refused anyway wastes his time and teaches the transport head nothing."""
    routes = fake_db.transport_routes.docs[:]
    students = fake_db.students.docs[:]
    approvals = len(fake_db.approval_requests.docs)
    fake_db.transport_routes.docs = [dict(_A_ROUTE)]
    fake_db.students.docs = [{"id": "k1", "schoolId": "aaryans-joya",
                              "route_zone_id": "route-9", "is_active": True}]
    try:
        resp = client.delete("/api/ops/transport/route-9", headers=_chaman())
        assert resp.status_code == 409
        assert len(fake_db.approval_requests.docs) == approvals, (
            "a request was raised for a deletion the platform was going to refuse"
        )
    finally:
        fake_db.transport_routes.docs = routes
        fake_db.students.docs = students


def test_a_vehicle_still_on_a_route_cannot_be_removed(client, fake_db):
    """There was no way to remove a vehicle at all before R3-2. The rule mirrors the
    route one: a record that vanishes while something still points at it leaves the
    thing pointing at nothing."""
    vehicles = fake_db.vehicles.docs[:]
    routes = fake_db.transport_routes.docs[:]
    fake_db.vehicles.docs = [{"id": "veh-1", "schoolId": "aaryans-joya",
                              "vehicle_number": "UP81AB1234"}]
    fake_db.transport_routes.docs = [{"id": "r1", "schoolId": "aaryans-joya",
                                      "vehicle_no": "UP81AB1234", "is_active": True}]
    try:
        resp = client.delete("/api/ops/transport/vehicles/veh-1", headers=_chaman())
        assert resp.status_code == 409
    finally:
        fake_db.vehicles.docs = vehicles
        fake_db.transport_routes.docs = routes


# ─── Removing a driver or conductor: asked for, and it needs agreement ────────
#
# Abhimanyu, 2026-08-15, in the same breath as "adding a driver, a conductor": removing
# one, behind the SAME gate as deleting a bus route.
#
# **This was half-built and the audit caught it.** The approval could be CARRIED OUT and
# nothing anywhere RAISED it, so the transport head could not ask at all. Every test below
# exists because the working half looked complete on its own.

_A_DRIVER = {"id": "drv-1", "schoolId": "aaryans-joya", "name": "A Driver",
             "staff_type": "transport", "sub_category": "transport_staff",
             "role": "admin", "user_id": "", "is_active": True}
_A_TEACHER = {"id": "tch-1", "schoolId": "aaryans-joya", "name": "A Teacher",
              "staff_type": "teacher", "role": "teacher", "user_id": "u-t1",
              "is_active": True}


@pytest.fixture
def a_driver_and_a_teacher(fake_db):
    original = fake_db.staff.docs[:]
    fake_db.staff.docs = [dict(_A_DRIVER), dict(_A_TEACHER)]
    yield
    fake_db.staff.docs = original


def test_asking_to_remove_a_driver_records_a_request_and_removes_nobody(
    client, a_driver_and_a_teacher, fake_db
):
    resp = client.delete("/api/staff/drv-1", headers=_chaman())
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["awaiting_approval"] is True

    approval = next(a for a in fake_db.approval_requests.docs
                    if a["id"] == body["data"]["approval_id"])
    assert approval["routing"] == "owner_and_principal", "only one of them was asked"
    assert approval["pending_action"]["kind"] == "remove_staff_member"
    # Nobody has been removed.
    driver = next(s for s in fake_db.staff.docs if s["id"] == "drv-1")
    assert driver.get("is_active") is not False


def test_he_cannot_ask_for_a_teacher_to_be_removed(client, a_driver_and_a_teacher, fake_db):
    """The path was built so he could retire a bus driver. Without this narrowing it would
    also let him ask for a teacher's removal, which is nobody's idea of transport."""
    before = len(fake_db.approval_requests.docs)
    resp = client.delete("/api/staff/tch-1", headers=_chaman())
    assert resp.status_code == 403
    assert len(fake_db.approval_requests.docs) == before, (
        "a request was raised for somebody who is not his to ask about"
    )


def test_approving_it_actually_takes_the_driver_off_the_roll(
    client, a_driver_and_a_teacher, fake_db
):
    """And it goes through the REAL removal path, not a flag written by hand.

    A first version of the executor wrote `is_active: False` directly. It looked
    equivalent and was not: the real path also closes the login, revokes any refresh token
    so an open session cannot outlive the decision, records the leaving state so it can be
    undone, and erases what the assistant learned about the person.
    """
    created = client.delete("/api/staff/drv-1", headers=_chaman()).json()
    resp = client.patch(
        f"/api/operations/approval-requests/{created['data']['approval_id']}/decide",
        headers=_owner(),
        json={"status": "approved", "reason": "Left the school"},
    )
    assert resp.status_code == 200, resp.text
    driver = next(s for s in fake_db.staff.docs if s["id"] == "drv-1")
    assert driver.get("is_active") is False or driver.get("status") == "tc_issued", (
        "approved, and the driver is still on the roll"
    )


def test_rejecting_it_leaves_the_driver_where_they_are(
    client, a_driver_and_a_teacher, fake_db
):
    created = client.delete("/api/staff/drv-1", headers=_chaman()).json()
    resp = client.patch(
        f"/api/operations/approval-requests/{created['data']['approval_id']}/decide",
        headers=_owner(),
        json={"status": "rejected", "reason": "Still driving"},
    )
    assert resp.status_code == 200, resp.text
    driver = next(s for s in fake_db.staff.docs if s["id"] == "drv-1")
    assert driver.get("is_active") is not False


def test_the_owner_still_removes_a_colleague_outright(client, a_driver_and_a_teacher):
    """The agreement step is the transport head's alone. Putting the owner behind it would
    take away something nobody asked to take away."""
    assert client.delete("/api/staff/tch-1", headers=_owner()).status_code == 200


def test_he_still_may_not_remove_anybody_himself():
    """`may_delete_people` stays False for him, and that is not a contradiction with the
    grant above: he ASKS, and somebody else carries it out."""
    from services.profile_matrix import PROFILE_MATRIX

    assert PROFILE_MATRIX["transport_head"]["may_delete_people"] is False
