from __future__ import annotations

"""B1: an entrance test is a record, not a word.

Before this, `assessment_scheduled` was a status and nothing else, so the school could not
pull a list for Sunday. These tests pin the record, and the two rules that stop it lying:
"nobody has marked this yet" is not "absent", and the seat and the application can never
disagree about a mark.
"""

import pytest

from middleware.auth import create_jwt


SCHOOL = "aaryans-joya"
PATH = "/api/admissions/tests"


def _headers(user_id: str, role: str, sub_category: str | None = None, branch_id: str = "branch-a"):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": branch_id}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = ("admission_tests", "admission_test_seats", "admission_applications",
             "enquiries", "students", "audit_logs")
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


@pytest.fixture
def owner():
    return _headers("owner-1", "owner")


def _seed_application(fake_db, application_id, *, name, status="under_review",
                      school=SCHOOL, branch="branch-a"):
    fake_db.admission_applications.docs.append({
        "_id": application_id, "id": application_id, "schoolId": school,
        "branch_id": branch, "applicant_name": name, "class_applying": "Class 5",
        "guardian_name": f"{name}'s parent", "guardian_phone": "9000000000",
        "status": status, "assessment": None, "offer": None, "student_id": None,
        "documents": [], "created_at": "2026-08-01T00:00:00",
    })
    return application_id


def _make_test(client, owner, **overrides):
    body = {"title": "Class 5 entrance", "scheduled_for": "2026-08-23",
            "start_time": "09:30", "place": "Main hall", "maximum_marks": 50}
    body.update(overrides)
    response = client.post(PATH, headers=owner, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _seat(client, owner, test_id, *application_ids):
    return client.post(f"{PATH}/{test_id}/seats", headers=owner,
                       json={"application_ids": list(application_ids)})


# ─── Security convention: every new endpoint ─────────────────────────────────

@pytest.mark.parametrize(("method", "path"), [
    ("get", PATH),
    ("post", PATH),
    ("get", f"{PATH}/t-1"),
    ("patch", f"{PATH}/t-1"),
    ("post", f"{PATH}/t-1/seats"),
    ("patch", f"{PATH}/t-1/seats/s-1"),
    ("delete", f"{PATH}/t-1/seats/s-1"),
])
def test_every_entrance_test_endpoint_needs_a_login(client, method, path):
    assert client.request(method.upper(), path, json={}).status_code == 401


@pytest.mark.parametrize(("method", "path"), [
    ("get", PATH),
    ("post", PATH),
    ("get", f"{PATH}/t-1"),
    ("patch", f"{PATH}/t-1"),
    ("post", f"{PATH}/t-1/seats"),
    ("patch", f"{PATH}/t-1/seats/s-1"),
    ("delete", f"{PATH}/t-1/seats/s-1"),
])
def test_every_entrance_test_endpoint_refuses_the_wrong_role(client, method, path):
    for user in (_headers("stu-1", "student"), _headers("tch-1", "teacher")):
        assert client.request(method.upper(), path, headers=user, json={}).status_code == 403


# ─── The record itself ───────────────────────────────────────────────────────

def test_a_test_now_has_a_date_a_time_and_a_place(client, owner):
    row = _make_test(client, owner)
    assert row["scheduled_for"] == "2026-08-23"
    assert row["start_time"] == "09:30"
    assert row["place"] == "Main hall"
    assert row["maximum_marks"] == 50
    assert row["status"] == "planned"


def test_a_test_with_no_place_is_refused(client, owner):
    """A list of children with a date and no place is not something you hand to a parent."""
    response = client.post(PATH, headers=owner, json={
        "title": "Class 5 entrance", "scheduled_for": "2026-08-23", "maximum_marks": 50,
    })
    assert response.status_code == 400
    assert "place" in response.json()["detail"]


@pytest.mark.parametrize(("field", "value"), [
    ("scheduled_for", "next Sunday"),
    ("start_time", "half nine"),
    ("maximum_marks", "fifty"),
    ("maximum_marks", 0),
])
def test_nonsense_is_refused_rather_than_stored(client, owner, field, value):
    body = {"title": "T", "scheduled_for": "2026-08-23", "place": "Hall",
            "maximum_marks": 50, field: value}
    assert client.post(PATH, headers=owner, json=body).status_code == 400


def test_the_school_can_pull_the_list_for_a_given_test(client, owner, fake_db):
    """The thing that could not be done at all before B1."""
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seed_application(fake_db, "app-2", name="Bhavna Rao")
    assert _seat(client, owner, test["id"], "app-1", "app-2").status_code == 200

    body = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]

    assert [row["applicant_name"] for row in body["seats"]] == ["Aarav Singh", "Bhavna Rao"]
    assert body["seats"][0]["guardian_phone"] == "9000000000"
    assert body["counts"]["seated"] == 2


# ─── Rule one: not marked is not the same as absent ──────────────────────────

def test_nobody_is_absent_until_somebody_says_so(client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seed_application(fake_db, "app-2", name="Bhavna Rao")
    _seat(client, owner, test["id"], "app-1", "app-2")

    body = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]

    assert all(row["attendance"] is None for row in body["seats"])
    # A register nobody has filled in must not read as a test nobody came to.
    assert body["counts"]["not_yet_marked"] == 2
    assert body["counts"]["absent"] == 0
    assert body["counts"]["present"] == 0


def test_the_list_says_who_is_still_waiting_to_be_marked(client, owner, fake_db):
    test = _make_test(client, owner)
    for index, name in enumerate(["Aarav", "Bhavna", "Chetan"]):
        _seed_application(fake_db, f"app-{index}", name=name)
    _seat(client, owner, test["id"], "app-0", "app-1", "app-2")
    seats = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"]
    by_name = {row["applicant_name"]: row for row in seats}

    client.patch(f"{PATH}/{test['id']}/seats/{by_name['Aarav']['id']}", headers=owner,
                 json={"attendance": "present"})
    client.patch(f"{PATH}/{test['id']}/seats/{by_name['Bhavna']['id']}", headers=owner,
                 json={"attendance": "absent"})

    counts = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["counts"]
    assert counts == {"seated": 3, "present": 1, "absent": 1, "not_yet_marked": 1,
                      "scored": 0, "present_but_not_yet_scored": 1}


# ─── Rule two: the seat and the application never disagree ───────────────────

def test_a_mark_reaches_the_application_through_the_one_function_that_records_it(
        client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]

    response = client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                            json={"attendance": "present", "score": 38})
    assert response.status_code == 200, response.text

    application = fake_db.admission_applications.docs[0]
    assert application["assessment"]["score"] == 38
    assert application["assessment"]["maximum"] == 50
    assert application["assessment"]["percentage"] == 76.0
    # Marked on the day of the test, not on the day somebody typed it in.
    assert application["assessment"]["assessed_on"] == "2026-08-23"
    assert "Class 5 entrance" in application["assessment"]["notes"]


def test_when_the_application_refuses_the_mark_nothing_at_all_is_stored(client, owner, fake_db):
    """The heart of rule two. A mark on the list with none on the application would be two
    answers to one question."""
    test = _make_test(client, owner)
    # `draft` cannot take an assessment; `record_assessment` refuses it.
    _seed_application(fake_db, "app-1", name="Aarav Singh", status="draft")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]

    response = client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                            json={"attendance": "present", "score": 38})
    assert response.status_code == 409

    after = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]
    assert after["score"] is None
    assert after["attendance"] is None          # the attendance went with it
    assert fake_db.admission_applications.docs[0]["assessment"] is None


def test_a_score_needs_somebody_to_have_turned_up(client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]

    # Nobody has said either way yet.
    unmarked = client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                            json={"score": 38})
    assert unmarked.status_code == 400
    assert "present" in unmarked.json()["detail"]

    # And explicitly absent is refused too: that is a mark from an empty chair.
    client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                 json={"attendance": "absent"})
    absent = client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                          json={"score": 38})
    assert absent.status_code == 400
    assert fake_db.admission_applications.docs[0]["assessment"] is None


def test_a_score_outside_the_papers_total_is_refused(client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]
    client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                 json={"attendance": "present"})

    for bad in (51, -1):
        response = client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                                json={"score": bad})
        assert response.status_code == 400


def test_everybody_on_one_test_is_marked_out_of_one_total(client, owner, fake_db):
    """Before B1 the maximum was typed per child, so two children sitting the same paper
    could be recorded out of different totals and nobody would see it."""
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seed_application(fake_db, "app-2", name="Bhavna Rao")
    _seat(client, owner, test["id"], "app-1", "app-2")
    for seat in client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"]:
        client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                     json={"attendance": "present", "score": 25})

    maximums = {row["assessment"]["maximum"] for row in fake_db.admission_applications.docs}
    assert maximums == {50}


def test_the_total_cannot_be_changed_once_anybody_is_marked(client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]
    client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                 json={"attendance": "present", "score": 38})

    response = client.patch(f"{PATH}/{test['id']}", headers=owner, json={"maximum_marks": 100})

    assert response.status_code == 409
    assert "percentage" in response.json()["detail"]
    # Changing the date or the place is still fine.
    assert client.patch(f"{PATH}/{test['id']}", headers=owner,
                        json={"place": "Room 4"}).status_code == 200


# ─── Seating: refusals are named, never silent ───────────────────────────────

def test_a_partly_refused_seating_reports_both_halves(client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-ok", name="Aarav Singh")
    _seed_application(fake_db, "app-gone", name="Withdrawn Child", status="withdrawn")

    body = _seat(client, owner, test["id"], "app-ok", "app-gone", "app-missing").json()["data"]

    assert [row["applicant_name"] for row in body["seated"]] == ["Aarav Singh"]
    assert body["counts"] == {"seated": 1, "refused": 2, "asked_for": 3}
    reasons = {row.get("applicant_name") or row["application_id"]: row["reason"]
               for row in body["refused"]}
    assert "withdrawn" in reasons["Withdrawn Child"]
    assert "No such application" in reasons["app-missing"]


def test_the_same_applicant_cannot_be_seated_twice(client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")

    body = _seat(client, owner, test["id"], "app-1").json()["data"]

    assert body["counts"]["seated"] == 0
    assert body["refused"][0]["reason"] == "Already on this test."
    assert len(fake_db.admission_test_seats.docs) == 1


def test_somebody_seated_by_mistake_can_be_taken_off_until_they_are_marked(
        client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]

    assert client.delete(f"{PATH}/{test['id']}/seats/{seat['id']}",
                         headers=owner).status_code == 200
    assert fake_db.admission_test_seats.docs == []


def test_a_marked_applicant_cannot_be_quietly_removed(client, owner, fake_db):
    """Their mark is already on their application. Removing the seat would leave a mark
    with nothing explaining where it came from."""
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]
    client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                 json={"attendance": "present", "score": 38})

    response = client.delete(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner)

    assert response.status_code == 409
    assert len(fake_db.admission_test_seats.docs) == 1


# ─── Cancelling ──────────────────────────────────────────────────────────────

def test_a_cancelled_test_takes_no_more_applicants_and_no_more_marks(client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]
    assert client.patch(f"{PATH}/{test['id']}", headers=owner,
                        json={"status": "cancelled"}).status_code == 200

    _seed_application(fake_db, "app-2", name="Bhavna Rao")
    assert _seat(client, owner, test["id"], "app-2").status_code == 409
    assert client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                        json={"attendance": "present"}).status_code == 409


def test_a_test_that_has_already_been_marked_cannot_be_called_off(client, owner, fake_db):
    """Those marks are on real applications. A status change must not claim the test
    never happened."""
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-1", name="Aarav Singh")
    _seat(client, owner, test["id"], "app-1")
    seat = client.get(f"{PATH}/{test['id']}", headers=owner).json()["data"]["seats"][0]
    client.patch(f"{PATH}/{test['id']}/seats/{seat['id']}", headers=owner,
                 json={"attendance": "present", "score": 38})

    response = client.patch(f"{PATH}/{test['id']}", headers=owner, json={"status": "cancelled"})

    assert response.status_code == 409
    assert "already on their applications" in response.json()["detail"]


# ─── Tenancy ─────────────────────────────────────────────────────────────────

def test_another_school_and_another_branch_are_never_on_the_list(client, owner, fake_db):
    test = _make_test(client, owner)
    _seed_application(fake_db, "app-mine", name="Our Child")
    _seed_application(fake_db, "app-other-school", name="Other School Child",
                      school="other-school")
    _seed_application(fake_db, "app-other-branch", name="Other Branch Child",
                      branch="branch-b")

    body = _seat(client, owner, test["id"], "app-mine", "app-other-school",
                 "app-other-branch").json()["data"]

    assert [row["applicant_name"] for row in body["seated"]] == ["Our Child"]
    assert body["counts"]["refused"] == 2


def test_another_schools_test_is_not_readable(client, owner, fake_db):
    fake_db.admission_tests.docs.append({
        "_id": "t-other", "id": "t-other", "schoolId": "other-school",
        "branch_id": "branch-a", "title": "Someone else's test",
        "scheduled_for": "2026-08-23", "place": "Elsewhere", "maximum_marks": 50,
        "status": "planned",
    })
    assert client.get(f"{PATH}/t-other", headers=owner).status_code == 404
    assert client.get(PATH, headers=owner).json()["data"] == []
