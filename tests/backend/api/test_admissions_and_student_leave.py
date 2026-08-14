from __future__ import annotations

from datetime import date, timedelta

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_class, make_student, make_staff

def _headers(user_id: str, role: str, sub_category: str | None = None):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": "branch-a"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = (
        "admission_applications", "enquiries", "students", "guardians", "classes",
        "staff", "student_leave_policies", "student_leave_requests",
        "student_leave_days", "audit_logs", "notifications",
    )
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def test_full_applicant_to_student_enrollment_is_linked_and_idempotent(client, fake_db):
    fake_db.classes.docs.append(make_class(id="class-a", branch_id="branch-a"))
    fake_db.enquiries.docs.append({
        "id": "enquiry-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "student_name": "Applicant One", "parent_name": "Guardian One",
        "phone": "9999999999", "class_applying": "Class 5", "status": "qualified",
    })
    owner = _headers("owner-1", "owner")

    created = client.post("/api/admissions/applications", headers=owner, json={
        "enquiry_id": "enquiry-1", "class_id": "class-a", "dob": "2015-05-01",
    })
    assert created.status_code == 200
    application_id = created.json()["data"]["id"]
    assert fake_db.enquiries.docs[0]["application_id"] == application_id

    assert client.patch(
        f"/api/admissions/applications/{application_id}/status",
        headers=owner, json={"status": "submitted"},
    ).status_code == 200
    assert client.patch(
        f"/api/admissions/applications/{application_id}/status",
        headers=owner, json={"status": "under_review"},
    ).status_code == 200
    offered = client.post(
        f"/api/admissions/applications/{application_id}/offer", headers=owner,
        json={"class_id": "class-a", "valid_until": (date.today() + timedelta(days=14)).isoformat()},
    )
    assert offered.status_code == 200
    assert client.patch(
        f"/api/admissions/applications/{application_id}/status",
        headers=owner, json={"status": "accepted"},
    ).status_code == 200

    enrolled = client.post(
        f"/api/admissions/applications/{application_id}/enroll",
        headers=owner, json={"admission_number": "ADM-NEW-1"},
    )
    assert enrolled.status_code == 200
    student_id = enrolled.json()["data"]["student"]["id"]
    assert len(fake_db.students.docs) == 1
    assert fake_db.students.docs[0]["admission_application_id"] == application_id
    assert fake_db.admission_applications.docs[0]["student_id"] == student_id

    repeated = client.post(
        f"/api/admissions/applications/{application_id}/enroll", headers=owner, json={}
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["existing"] is True
    assert len(fake_db.students.docs) == 1


def test_starting_an_application_from_an_enquiry_carries_the_family_and_never_duplicates(client, fake_db):
    """A1: the enquiry screen's "Start application" button.

    Two things have to hold for the screen to be honest. The family has to arrive on
    the application without being retyped, and a second press must hand back the first
    application rather than quietly making a second one for the same child.
    """
    fake_db.classes.docs.append(make_class(id="class-a", branch_id="branch-a"))
    fake_db.enquiries.docs.append({
        "id": "enquiry-9", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "student_name": "Applicant Nine", "parent_name": "Guardian Nine",
        "phone": "9800000009", "class_applying": "Class 3", "status": "contacted",
    })
    owner = _headers("owner-1", "owner")

    first = client.post("/api/admissions/applications", headers=owner,
                        json={"enquiry_id": "enquiry-9"})
    assert first.status_code == 200
    body = first.json()
    assert body["meta"]["existing"] is False
    application = body["data"]
    assert application["applicant_name"] == "Applicant Nine"
    assert application["guardian_name"] == "Guardian Nine"
    assert application["guardian_phone"] == "9800000009"
    assert application["class_applying"] == "Class 3"
    assert application["enquiry_id"] == "enquiry-9"
    # The enquiry now carries the link, which is what hides the button on the screen.
    assert fake_db.enquiries.docs[0]["application_id"] == application["id"]

    second = client.post("/api/admissions/applications", headers=owner,
                         json={"enquiry_id": "enquiry-9"})
    assert second.status_code == 200
    assert second.json()["meta"]["existing"] is True
    assert second.json()["data"]["id"] == application["id"]
    assert len(fake_db.admission_applications.docs) == 1


def test_starting_an_application_from_a_missing_enquiry_is_refused(client, fake_db):
    refused = client.post("/api/admissions/applications", headers=_headers("owner-1", "owner"),
                          json={"enquiry_id": "no-such-enquiry"})
    assert refused.status_code == 404
    assert len(fake_db.admission_applications.docs) == 0


def test_admission_enrollment_rejects_unprivileged_admin_and_invalid_transition(client, fake_db):
    fake_db.classes.docs.append(make_class(id="class-a", branch_id="branch-a"))
    created = client.post("/api/admissions/applications", headers=_headers("owner-1", "owner"), json={
        "applicant_name": "Applicant", "class_id": "class-a",
        "guardian_name": "Guardian", "guardian_phone": "9999999999",
    })
    application_id = created.json()["data"]["id"]
    invalid = client.patch(
        f"/api/admissions/applications/{application_id}/status",
        headers=_headers("owner-1", "owner"), json={"status": "accepted"},
    )
    assert invalid.status_code == 409
    forbidden = client.post(
        f"/api/admissions/applications/{application_id}/enroll",
        headers=_headers("acct-1", "admin", "accountant"), json={},
    )
    assert forbidden.status_code == 403


def test_student_leave_follows_teacher_then_principal_policy(client, fake_db):
    fake_db.staff.docs.append(make_staff(
        id="teacher-staff", user_id="teacher-user", branch_id="branch-a", staff_type="teacher"
    ))
    class_doc = make_class(id="class-a", branch_id="branch-a")
    class_doc["class_teacher_id"] = "teacher-staff"
    fake_db.classes.docs.append(class_doc)
    fake_db.students.docs.append(make_student(
        id="student-a", user_id="student-user", class_id="class-a", branch_id="branch-a"
    ))
    fake_db.guardians.docs.append({
        "id": "guardian-a", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "student_id": "student-a", "user_id": "parent-user", "name": "Parent",
    })
    start = date.today() + timedelta(days=2)
    end = start + timedelta(days=4)
    created = client.post("/api/student-leave/requests", headers=_headers("parent-user", "parent"), json={
        "student_id": "student-a", "start_date": start.isoformat(),
        "end_date": end.isoformat(), "reason": "Family function", "leave_type": "planned",
    })
    assert created.status_code == 200
    request_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "pending_teacher"

    teacher_decision = client.patch(
        f"/api/student-leave/requests/{request_id}/decision",
        headers=_headers("teacher-user", "teacher"), json={"decision": "approve"},
    )
    assert teacher_decision.status_code == 200
    assert teacher_decision.json()["data"]["status"] == "pending_principal"

    final = client.patch(
        f"/api/student-leave/requests/{request_id}/decision",
        headers=_headers("principal-user", "admin", "principal"), json={"decision": "approve"},
    )
    assert final.status_code == 200
    assert final.json()["data"]["status"] == "approved"
    assert len(fake_db.student_leave_days.docs) == 5


def test_student_leave_blocks_foreign_guardian_and_overlapping_request(client, fake_db):
    fake_db.classes.docs.append(make_class(id="class-a", branch_id="branch-a"))
    fake_db.students.docs.append(make_student(id="student-a", class_id="class-a", branch_id="branch-a"))
    fake_db.guardians.docs.append({
        "id": "guardian-a", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "student_id": "student-a", "user_id": "parent-user",
    })
    start = date.today() + timedelta(days=2)
    body = {"student_id": "student-a", "start_date": start.isoformat(), "end_date": start.isoformat(), "reason": "Appointment"}
    assert client.post(
        "/api/student-leave/requests", headers=_headers("other-parent", "parent"), json=body
    ).status_code == 403
    assert client.post(
        "/api/student-leave/requests", headers=_headers("parent-user", "parent"), json=body
    ).status_code == 200
    assert client.post(
        "/api/student-leave/requests", headers=_headers("parent-user", "parent"), json=body
    ).status_code == 409


@pytest.mark.parametrize("path", [
    "/api/admissions/applications",
    "/api/student-leave/policy",
    "/api/student-leave/requests",
])
def test_enterprise_student_workflows_require_authentication(client, path):
    assert client.get(path).status_code == 401
