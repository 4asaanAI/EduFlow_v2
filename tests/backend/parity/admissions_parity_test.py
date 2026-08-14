"""A6 parity: the admissions screen and Flo must write the same thing.

Same seed through both write entrypoints (the REST routes in `routes/admissions.py`
via TestClient, and the AI tools via their real dispatch fns) leaves the application
document, the student, the enquiry and the audit rows identical except for a volatile
allowlist. Covers the five tools added on 2026-08-14:

    create_admission_application          -> services/admissions_service.create_application
    update_admission_application_status   -> ...transition_application
    record_admission_assessment           -> ...record_assessment
    issue_admission_offer                 -> ...issue_offer
    enroll_admission_application          -> ...enroll_application

There is nothing clever in the tools: each is a thin adapter. That is exactly what this
file exists to keep true, because the moment one of them grows a rule of its own, chat
and screen start describing different schools.
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

# No module-level `pytestmark = pytest.mark.asyncio`: `pytest.ini` sets
# `asyncio_mode = auto`, and adding the mark by hand also lands it on the two sync tests
# at the foot of this file, which pytest then warns about once each.

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id", "record_id",
             "at", "issued_at", "recorded_at", "enrolled_at", "assessed_on", "date",
             "application_id", "student_id", "admission_application_id", "enquiry_id",
             "valid_until", "created_by", "guardian_ids"}

SCHOOL = "aaryans-joya"
OWNER_USER = {"id": "own-1", "user_id": "own-1", "role": "owner", "name": "Owner",
              "branch_id": "branch-a"}


def _owner_headers():
    token = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner",
                        "branch_id": "branch-a"})
    return {"Authorization": f"Bearer {token}"}


def _scrub(value):
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _mask(docs):
    out = [_scrub(d) for d in copy.deepcopy(docs)]
    return sorted(out, key=lambda d: str(sorted(d.items())))


_COLLECTIONS = ("admission_applications", "enquiries", "students", "guardians",
                "audit_logs", "notifications", "classes")


def _clear(fake_db, cols=_COLLECTIONS):
    for col in cols:
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _ai_db(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    originals = {name: list(getattr(fake_db, name).docs) for name in _COLLECTIONS}
    _clear(fake_db)
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _seed_class(fake_db):
    fake_db.classes.docs.append({
        "_id": "cls-5", "id": "cls-5", "schoolId": SCHOOL, "branch_id": "branch-a",
        "name": "Class 5", "section": "A",
    })


def _seed_enquiry(fake_db, enquiry_id="enq-1"):
    fake_db.enquiries.docs.append({
        "_id": enquiry_id, "id": enquiry_id, "schoolId": SCHOOL, "branch_id": "branch-a",
        "student_name": "Aarav Singh", "parent_name": "Neha Singh", "phone": "9999999999",
        "class_applying": "Class 5", "mother_name": "Neha Singh", "father_name": "Raj Singh",
        "dob": "2016-04-02", "gender": "male", "previous_school": "Little Stars",
        "status": "contacted", "created_at": "2026-08-01T00:00:00",
    })


def _seed_application(fake_db, *, status="draft", assessment=None, offer=None,
                      application_id="app-1"):
    fake_db.admission_applications.docs.append({
        "_id": application_id, "id": application_id, "schoolId": SCHOOL,
        "branch_id": "branch-a", "enquiry_id": "enq-1", "applicant_name": "Aarav Singh",
        "dob": "2016-04-02", "gender": "male", "class_id": "cls-5",
        "class_applying": "Class 5", "academic_year": "2026-27",
        "guardian_name": "Neha Singh", "guardian_phone": "9999999999",
        "guardian_email": None, "mother_name": "Neha Singh", "father_name": "Raj Singh",
        "address": None, "previous_school": "Little Stars", "documents": [],
        "assessment": assessment, "offer": offer, "status": status, "student_id": None,
        "created_by": "own-1", "created_at": "2026-08-01T00:00:00",
        "updated_at": "2026-08-01T00:00:00",
    })


def _state(fake_db):
    return {
        "applications": _mask(fake_db.admission_applications.docs),
        "enquiries": _mask(fake_db.enquiries.docs),
        "students": _mask(fake_db.students.docs),
        "guardians": _mask(fake_db.guardians.docs),
        "audit": _mask([row for row in fake_db.audit_logs.docs
                        if row.get("entity_type") == "admission_application"]),
    }


# ─── create ──────────────────────────────────────────────────────────────────

async def test_create_application_parity(client, fake_db):
    _seed_enquiry(fake_db)
    payload = {"enquiry_id": "enq-1", "class_applying": "Class 5", "academic_year": "2026-27"}

    response = client.post("/api/admissions/applications", json=dict(payload),
                           headers=_owner_headers())
    assert response.status_code == 200, response.text
    rest_state = _state(fake_db)

    _clear(fake_db)
    _seed_enquiry(fake_db)
    out = await tool_functions_v2.tool_create_admission_application(dict(payload), OWNER_USER, None)
    assert out["success"] is True
    assert _state(fake_db) == rest_state
    # The family came across, and it came across the same way through both doors.
    application = rest_state["applications"][0]
    assert application["applicant_name"] == "Aarav Singh"
    assert application["guardian_phone"] == "9999999999"
    assert application["mother_name"] == "Neha Singh"
    assert application["status"] == "draft"


async def test_a_second_application_is_reported_as_the_first_one_not_a_new_record(client, fake_db):
    _seed_enquiry(fake_db)
    _seed_application(fake_db)

    response = client.post("/api/admissions/applications", json={"enquiry_id": "enq-1"},
                           headers=_owner_headers())
    assert response.status_code == 200
    assert response.json()["meta"]["existing"] is True

    out = await tool_functions_v2.tool_create_admission_application(
        {"enquiry_id": "enq-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert "already had an application" in out["message"]
    assert len(fake_db.admission_applications.docs) == 1


# ─── stage moves ─────────────────────────────────────────────────────────────

async def test_status_transition_parity(client, fake_db):
    _seed_application(fake_db)
    payload = {"status": "submitted", "note": "Papers handed in"}

    response = client.patch("/api/admissions/applications/app-1/status", json=dict(payload),
                            headers=_owner_headers())
    assert response.status_code == 200, response.text
    rest_state = _state(fake_db)

    _clear(fake_db)
    _seed_application(fake_db)
    out = await tool_functions_v2.tool_update_admission_application_status(
        {"application_id": "app-1", **payload}, OWNER_USER, None)
    assert out["success"] is True
    assert _state(fake_db) == rest_state
    assert rest_state["applications"][0]["status"] == "submitted"


async def test_the_services_refusals_reach_chat_unchanged(client, fake_db):
    """The rules live in the service, so Flo gets them for free. Three of them, each a
    place where saying yes would report something that had not happened."""
    _seed_application(fake_db)
    fake_db.admission_applications.docs[0]["guardian_name"] = None

    assert client.patch("/api/admissions/applications/app-1/status",
                        json={"status": "submitted"},
                        headers=_owner_headers()).status_code == 400
    refused = await tool_functions_v2.tool_update_admission_application_status(
        {"application_id": "app-1", "status": "submitted"}, OWNER_USER, None)
    assert refused["success"] is False
    assert "guardian_name" in refused["message"]

    # A2: nobody sets enrolled by hand, on any path, including through Flo.
    _clear(fake_db)
    _seed_application(fake_db, status="accepted", offer={"class_id": "cls-5"})
    blocked = await tool_functions_v2.tool_update_admission_application_status(
        {"application_id": "app-1", "status": "enrolled"}, OWNER_USER, None)
    assert blocked["success"] is False
    assert "enrollment endpoint" in blocked["message"]
    assert fake_db.students.docs == []

    # An application that is not there is said to be not there, not silently ignored.
    missing = await tool_functions_v2.tool_update_admission_application_status(
        {"application_id": "nope", "status": "submitted"}, OWNER_USER, None)
    assert missing["success"] is False
    assert "not found" in missing["message"]


async def test_a_stage_move_that_changes_nothing_says_so(fake_db):
    _seed_application(fake_db, status="submitted")
    out = await tool_functions_v2.tool_update_admission_application_status(
        {"application_id": "app-1", "status": "submitted"}, OWNER_USER, None)
    assert out["success"] is True
    assert "already at 'submitted'" in out["message"]


# ─── assessment and offer ────────────────────────────────────────────────────

async def test_assessment_parity(client, fake_db):
    _seed_application(fake_db, status="assessment_scheduled")
    payload = {"score": 38, "maximum": 50, "assessed_on": "2026-08-12", "notes": "Steady"}

    response = client.post("/api/admissions/applications/app-1/assessment", json=dict(payload),
                           headers=_owner_headers())
    assert response.status_code == 200, response.text
    rest_state = _state(fake_db)

    _clear(fake_db)
    _seed_application(fake_db, status="assessment_scheduled")
    out = await tool_functions_v2.tool_record_admission_assessment(
        {"application_id": "app-1", **payload}, OWNER_USER, None)
    assert out["success"] is True
    assert _state(fake_db) == rest_state
    assert rest_state["applications"][0]["assessment"]["percentage"] == 76.0


async def test_offer_parity(client, fake_db):
    _seed_class(fake_db)
    _seed_application(fake_db, status="assessed",
                      assessment={"score": 38.0, "maximum": 50.0, "percentage": 76.0})
    payload = {"class_id": "cls-5", "valid_until": "2099-01-01", "admission_fee": 15000}

    response = client.post("/api/admissions/applications/app-1/offer", json=dict(payload),
                           headers=_owner_headers())
    assert response.status_code == 200, response.text
    rest_state = _state(fake_db)

    _clear(fake_db)
    _seed_class(fake_db)
    _seed_application(fake_db, status="assessed",
                      assessment={"score": 38.0, "maximum": 50.0, "percentage": 76.0})
    out = await tool_functions_v2.tool_issue_admission_offer(
        {"application_id": "app-1", **payload}, OWNER_USER, None)
    assert out["success"] is True
    assert _state(fake_db) == rest_state
    assert rest_state["applications"][0]["status"] == "offered"


# ─── enrolment: the one that brings a person into existence ──────────────────

async def test_enrolment_parity_creates_the_same_child_through_both_doors(client, fake_db):
    _seed_class(fake_db)
    _seed_enquiry(fake_db)
    _seed_application(fake_db, status="accepted",
                      offer={"class_id": "cls-5", "valid_until": "2099-01-01"})
    payload = {"admission_number": "ADM-A6-1"}

    response = client.post("/api/admissions/applications/app-1/enroll", json=dict(payload),
                           headers=_owner_headers())
    assert response.status_code == 200, response.text
    rest_state = _state(fake_db)

    _clear(fake_db)
    _seed_class(fake_db)
    _seed_enquiry(fake_db)
    _seed_application(fake_db, status="accepted",
                      offer={"class_id": "cls-5", "valid_until": "2099-01-01"})
    out = await tool_functions_v2.tool_enroll_admission_application(
        {"application_id": "app-1", **payload}, OWNER_USER, None)
    assert out["success"] is True
    assert _state(fake_db) == rest_state

    # Enrolment is the ONE source, and it moves all three records together.
    assert rest_state["students"][0]["name"] == "Aarav Singh"
    assert rest_state["applications"][0]["status"] == "enrolled"
    assert rest_state["enquiries"][0]["status"] == "enrolled"
    assert "on the roll" in out["message"]


async def test_only_an_accepted_application_enrols_anybody(fake_db):
    _seed_class(fake_db)
    _seed_application(fake_db, status="offered", offer={"class_id": "cls-5"})
    out = await tool_functions_v2.tool_enroll_admission_application(
        {"application_id": "app-1"}, OWNER_USER, None)
    assert out["success"] is False
    assert "accepted" in out["message"]
    assert fake_db.students.docs == []


async def test_enrolling_twice_does_not_make_a_second_child(client, fake_db):
    _seed_class(fake_db)
    _seed_enquiry(fake_db)
    _seed_application(fake_db, status="accepted", offer={"class_id": "cls-5"})
    first = await tool_functions_v2.tool_enroll_admission_application(
        {"application_id": "app-1", "admission_number": "ADM-A6-2"}, OWNER_USER, None)
    assert first["success"] is True

    second = await tool_functions_v2.tool_enroll_admission_application(
        {"application_id": "app-1"}, OWNER_USER, None)
    assert second["success"] is True
    assert "no second record was created" in second["message"]
    assert len(fake_db.students.docs) == 1


# ─── the confirm card ────────────────────────────────────────────────────────

def test_only_enrolment_stops_for_a_confirmation():
    registry = tool_functions_v2.TOOL_REGISTRY
    assert registry["enroll_admission_application"]["requires_confirmation"] is True
    for name in ("create_admission_application", "update_admission_application_status",
                 "record_admission_assessment", "issue_admission_offer"):
        assert registry[name]["requires_confirmation"] is False, name
        assert registry[name]["dispatch_type"] == "write"


def test_the_management_head_is_refused_the_two_the_rest_route_refuses_him():
    """Chat gives the same answer as the screen. `_can_enroll` allows the owner and the
    principal only, so the management head must not reach these through Flo either."""
    from ai.tool_access import is_tool_authorized

    registry = tool_functions_v2.TOOL_REGISTRY
    management = {"user_id": "mgmt-1", "role": "admin", "sub_category": "management"}
    for name in ("issue_admission_offer", "enroll_admission_application"):
        assert is_tool_authorized(management, registry[name]) is False, name
    # And he keeps the three the screen does let him do.
    for name in ("create_admission_application", "update_admission_application_status",
                 "record_admission_assessment"):
        assert is_tool_authorized(management, registry[name]) is True, name
