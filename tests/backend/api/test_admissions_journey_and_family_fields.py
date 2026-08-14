"""A3: the journey said once, and the family the school actually records.

Two things, both aimed at the same fault. The platform described one journey in two
vocabularies, so a family part way through had a position in each and a reader could not
tell whether they were seeing one family twice. And the enquiry held a single
`parent_name` while the school's own admission form records the mother and the father
separately and fills both in on essentially every enquiry, so starting an application
carried one of the two parents across with no way of telling which.
"""

from __future__ import annotations

import pytest

from ai import tool_functions_v2
from middleware.auth import create_jwt
from services.admissions_journey import describe_position
from tests.backend.factories import make_class


def _headers(user_id: str = "own-1", role: str = "owner", sub_category: str | None = None):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": "branch-a"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = ("enquiries", "admission_applications", "students", "guardians", "classes",
             "audit_logs", "notifications")
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _enquiry(fake_db, **overrides):
    doc = {
        "_id": "enq-a3", "id": "enq-a3", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "student_name": "Applicant Three", "parent_name": "Guardian Three",
        "phone": "9600000006", "class_applying": "Class 2", "status": "contacted",
        "source": "walk_in", "created_at": "2026-08-02T00:00:00",
    }
    doc.update(overrides)
    fake_db.enquiries.docs.append(doc)
    return doc


# ─── The vocabulary itself ───────────────────────────────────────────────────

def test_a_family_with_only_an_enquiry_is_placed_by_the_enquiry():
    position = describe_position(enquiry={"status": "visit_scheduled"})
    assert position["step"] == "visiting"
    assert position["source"] == "enquiry"
    assert position["index"] == 3


def test_the_application_wins_when_it_is_further_along():
    """The whole point: one answer, and it says which record gave it."""
    position = describe_position(
        enquiry={"status": "contacted"}, application={"status": "offered"},
    )
    assert position["step"] == "offered"
    assert position["source"] == "application"


def test_the_enquiry_wins_when_it_is_further_along_than_a_draft_application():
    position = describe_position(
        enquiry={"status": "fee_paid"}, application={"status": "draft"},
    )
    assert position["step"] == "accepted"
    assert position["source"] == "enquiry"


def test_a_closed_record_never_outranks_a_live_one():
    """A withdrawn application must not drag a live enquiry to "closed", and a lost
    enquiry must not hide an application that is still moving."""
    assert describe_position(
        enquiry={"status": "visited"}, application={"status": "withdrawn"},
    )["step"] == "visiting"
    assert describe_position(
        enquiry={"status": "lost"}, application={"status": "offered"},
    )["step"] == "offered"


def test_closed_has_no_position_number_because_it_is_an_ending_not_a_rung():
    position = describe_position(enquiry={"status": "lost"})
    assert position["step"] == "closed"
    assert position["index"] is None
    assert position["closed"] is True


def test_nothing_at_all_says_not_known_rather_than_guessing():
    position = describe_position()
    assert position["step"] is None
    assert position["label"] == "Not known"
    assert position["source"] is None


# ─── The lists answer in that one vocabulary ─────────────────────────────────

def test_the_enquiry_list_gives_one_position_per_family(client, fake_db):
    _enquiry(fake_db, status="contacted", application_id="app-a3")
    fake_db.admission_applications.docs.append({
        "_id": "app-a3", "id": "app-a3", "schoolId": "aaryans-joya",
        "branch_id": "branch-a", "enquiry_id": "enq-a3", "status": "offered",
    })
    body = client.get("/api/ops/enquiries", headers=_headers()).json()
    assert body["success"] is True
    row = body["data"][0]
    assert row["journey"]["label"] == "Offered a place"
    assert row["journey"]["source"] == "application"


def test_the_enquiry_list_says_how_many_there_are_in_total(client, fake_db):
    """It used to stop at 50 rows with no total beside it, so a school with 200 enquiries
    looked like a school with 50 and the funnel counts were wrong with nothing saying so."""
    for index in range(3):
        _enquiry(fake_db, _id=f"enq-{index}", id=f"enq-{index}")
    body = client.get("/api/ops/enquiries?limit=2", headers=_headers()).json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 3
    assert body["meta"]["count"] == 2


def test_a_nonsense_page_size_is_refused_not_quietly_turned_into_one(client, fake_db):
    _enquiry(fake_db)
    assert client.get("/api/ops/enquiries?limit=0", headers=_headers()).status_code == 400
    assert client.get("/api/ops/enquiries?limit=-1", headers=_headers()).status_code == 400


def test_the_application_list_answers_in_the_same_vocabulary(client, fake_db):
    fake_db.admission_applications.docs.append({
        "_id": "app-b", "id": "app-b", "schoolId": "aaryans-joya",
        "branch_id": "branch-a", "status": "under_review", "applicant_name": "A",
    })
    body = client.get("/api/admissions/applications", headers=_headers()).json()
    assert body["data"][0]["journey"]["label"] == "Applied"


# ─── The family the school actually records ──────────────────────────────────

FAMILY = {
    "mother_name": "Mother Three", "father_name": "Father Three",
    "dob": "2018-04-11", "gender": "female", "previous_school": "Little Star School",
}


def test_an_enquiry_records_both_parents_and_the_child_s_details(client, fake_db):
    created = client.post("/api/ops/enquiries", headers=_headers(), json={
        "student_name": "Applicant Three", "parent_name": "Guardian Three",
        "phone": "9600000006", **FAMILY,
    })
    assert created.status_code == 200
    row = created.json()["data"]
    for key, value in FAMILY.items():
        assert row[key] == value
    # `parent_name` stays. It is what messaging and every export already read.
    assert row["parent_name"] == "Guardian Three"


def test_an_enquiry_taken_with_only_a_name_stores_the_fields_as_empty(client, fake_db):
    """Present and empty, not absent. A record nobody asked for the mother's name on
    should not look like a record written before the field existed."""
    row = client.post("/api/ops/enquiries", headers=_headers(), json={
        "student_name": "Phone Enquiry",
    }).json()["data"]
    for key in FAMILY:
        assert key in row
        assert row[key] is None


def test_both_parents_can_be_added_to_an_enquiry_afterwards(client, fake_db):
    _enquiry(fake_db)
    updated = client.patch("/api/ops/enquiries/enq-a3", headers=_headers(), json=FAMILY)
    assert updated.status_code == 200
    for key, value in FAMILY.items():
        assert updated.json()["data"][key] == value


async def test_flo_records_the_same_family_fields(client, fake_db):
    out = await tool_functions_v2.tool_create_enquiry(
        {"student_name": "Chat Enquiry", **FAMILY},
        {"id": "own-1", "role": "owner", "name": "Owner"}, None,
    )
    assert out["success"] is True
    for key, value in FAMILY.items():
        assert out["data"][key] == value


def test_starting_an_application_carries_both_parents_across(client, fake_db):
    """A1 carried one parent of two with no way of telling which. This is that hole."""
    fake_db.classes.docs.append(make_class(id="class-a", branch_id="branch-a"))
    _enquiry(fake_db, **FAMILY)
    application = client.post("/api/admissions/applications", headers=_headers(), json={
        "enquiry_id": "enq-a3", "class_id": "class-a",
    }).json()["data"]
    assert application["mother_name"] == "Mother Three"
    assert application["father_name"] == "Father Three"
    assert application["dob"] == "2018-04-11"
    assert application["gender"] == "female"
    assert application["previous_school"] == "Little Star School"
    # And the contact the office deals with still arrives, as before.
    assert application["guardian_name"] == "Guardian Three"
    assert application["guardian_phone"] == "9600000006"


def test_what_is_typed_on_the_application_beats_what_the_enquiry_held(client, fake_db):
    fake_db.classes.docs.append(make_class(id="class-a", branch_id="branch-a"))
    _enquiry(fake_db, **FAMILY)
    application = client.post("/api/admissions/applications", headers=_headers(), json={
        "enquiry_id": "enq-a3", "class_id": "class-a",
        "father_name": "Corrected Father", "dob": "2018-04-12",
    }).json()["data"]
    assert application["father_name"] == "Corrected Father"
    assert application["dob"] == "2018-04-12"
    assert application["mother_name"] == "Mother Three"


def test_the_enquiry_list_requires_a_sign_in(client):
    assert client.get("/api/ops/enquiries").status_code == 401


def test_a_student_cannot_read_the_enquiry_list(client):
    assert client.get(
        "/api/ops/enquiries", headers=_headers("stu-1", "student")
    ).status_code == 403
