"""A2: nobody moves an enquiry to enrolled by hand, on any path.

An enrolment means a child exists on the roll. Before this, `fee_paid` to `enrolled` was
an ordinary stage move with no check that any child had been created, and the owner could
jump an enquiry to enrolled from anywhere. The funnel could then report an enrolment that
had never happened, and nobody looking at the screen could tell that apart from a real
one. The only thing that may set the stage is `enroll_application`, which creates the
child and the guardians in one transaction.

The test behind every case here: can a person tell "this child joined the school" from
"somebody moved a row to the last column"?
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ai import tool_functions_v2
from middleware.auth import create_jwt
from tests.backend.factories import make_class


def _headers(user_id: str, role: str, sub_category: str | None = None):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": "branch-a"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


REFUSAL = "cannot be moved to enrolled by hand"


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


def _seed_enquiry(fake_db, status: str = "fee_paid"):
    fake_db.enquiries.docs[:] = [{
        "_id": "enq-a2", "id": "enq-a2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "student_name": "Applicant Two", "parent_name": "Guardian Two",
        "phone": "9700000007", "class_applying": "Class 4", "status": status,
        "source": "walk_in", "created_at": "2026-08-01T00:00:00",
    }]


@pytest.mark.parametrize("role,sub_category", [
    ("owner", None),
    ("admin", "principal"),
    ("admin", "admission"),
])
def test_no_role_can_move_an_enquiry_to_enrolled(client, fake_db, role, sub_category):
    """Including the owner. The owner may move stages freely everywhere else."""
    _seed_enquiry(fake_db)
    refused = client.patch("/api/ops/enquiries/enq-a2",
                           headers=_headers("u-1", role, sub_category),
                           json={"status": "enrolled"})
    assert refused.status_code == 400
    assert REFUSAL in refused.json()["detail"]
    assert fake_db.enquiries.docs[0]["status"] == "fee_paid"
    assert len(fake_db.students.docs) == 0


@pytest.mark.parametrize("start", ["new", "contacted", "fee_paid", "applied", "admitted"])
def test_enrolled_is_unreachable_from_every_stage(client, fake_db, start):
    _seed_enquiry(fake_db, status=start)
    refused = client.patch("/api/ops/enquiries/enq-a2", headers=_headers("own-1", "owner"),
                           json={"status": "enrolled"})
    assert refused.status_code == 400
    assert fake_db.enquiries.docs[0]["status"] == start


async def test_flo_is_refused_too_and_says_what_to_do_instead(client, fake_db):
    _seed_enquiry(fake_db)
    out = await tool_functions_v2.tool_update_enquiry_status(
        {"enquiry_id": "enq-a2", "status": "enrolled"},
        {"id": "own-1", "role": "owner", "name": "Owner"}, None,
    )
    assert out["success"] is False
    assert REFUSAL in out["message"]
    # A refusal that does not say what to do instead reads as a broken platform.
    assert "application" in out["message"]
    assert fake_db.enquiries.docs[0]["status"] == "fee_paid"


def test_the_stage_a_person_may_pick_never_includes_enrolled():
    """Pins the list itself, so a future edit cannot quietly put it back."""
    from services.enquiry_service import ALLOWED_TRANSITIONS

    for stage, targets in ALLOWED_TRANSITIONS.items():
        assert "enrolled" not in targets, f"{stage} can still be moved to enrolled"


def test_enrolling_an_application_still_sets_the_enquiry_to_enrolled(client, fake_db):
    """The one real path. It has to keep working, or A2 has broken enrolment."""
    fake_db.classes.docs.append(make_class(id="class-a", branch_id="branch-a"))
    _seed_enquiry(fake_db, status="fee_paid")
    owner = _headers("own-1", "owner")

    created = client.post("/api/admissions/applications", headers=owner,
                          json={"enquiry_id": "enq-a2", "class_id": "class-a"})
    application_id = created.json()["data"]["id"]
    for target in ("submitted", "under_review"):
        assert client.patch(f"/api/admissions/applications/{application_id}/status",
                            headers=owner, json={"status": target}).status_code == 200
    assert client.post(f"/api/admissions/applications/{application_id}/offer", headers=owner, json={
        "class_id": "class-a", "valid_until": (date.today() + timedelta(days=14)).isoformat(),
    }).status_code == 200
    assert client.patch(f"/api/admissions/applications/{application_id}/status",
                        headers=owner, json={"status": "accepted"}).status_code == 200

    enrolled = client.post(f"/api/admissions/applications/{application_id}/enroll",
                           headers=owner, json={"admission_number": "ADM-A2-1"})
    assert enrolled.status_code == 200
    # The enquiry says enrolled, and a child exists to back it up. That is the whole point.
    assert fake_db.enquiries.docs[0]["status"] == "enrolled"
    assert len(fake_db.students.docs) == 1
    assert fake_db.enquiries.docs[0]["student_id"] == fake_db.students.docs[0]["id"]
