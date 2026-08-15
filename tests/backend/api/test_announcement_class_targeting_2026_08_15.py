"""A notice sent to one class reaches that class, and nobody else (2026-08-15).

Before this, "By Class" saved the chosen classes and then nothing ever read them back.
Delivery was decided by role alone, so a notice meant for one class went to every student
in the school while the sender was told it had worked.

These tests pin the fix at every surface a person can read an announcement from, because
fixing one screen and leaving the others is indistinguishable from not fixing it.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_class, make_student

SCHOOL = "aaryans-joya"
BRANCH = "branch-a"


def _headers(user_id: str, role: str, sub_category: str | None = None):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": BRANCH}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _seed(fake_db):
    names = ("announcements", "classes", "students", "guardians", "notifications")
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []

    fake_db.classes.docs.extend([
        make_class(id="cls-10-a", name="10th", section="A", branch_id=BRANCH),
        make_class(id="cls-10-b", name="10th", section="B", branch_id=BRANCH),
    ])
    fake_db.students.docs.extend([
        make_student(id="stu-a", user_id="user-stu-a", class_id="cls-10-a", branch_id=BRANCH, name="In 10 A"),
        make_student(id="stu-b", user_id="user-stu-b", class_id="cls-10-b", branch_id=BRANCH, name="In 10 B"),
    ])
    fake_db.guardians.docs.extend([
        {"id": "g-a", "schoolId": SCHOOL, "branch_id": BRANCH, "student_id": "stu-a", "user_id": "parent-a", "relation": "Mother"},
        {"id": "g-b", "schoolId": SCHOOL, "branch_id": BRANCH, "student_id": "stu-b", "user_id": "parent-b", "relation": "Father"},
    ])
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _send_to_class(client, labels, title="Trip on Sunday"):
    return client.post(
        "/api/ops/announcements",
        json={
            "title": title,
            "content": "Please be at school by 7am.",
            "audience_type": "class",
            "audience_classes": labels,
        },
        headers=_headers("owner-1", "owner"),
    )


# ---------------------------------------------------------------- the class is stored

@pytest.mark.parametrize("label", ["10th A", "10th-A", "10TH  -  a", "Class 10th A"])
def test_every_wording_of_a_class_resolves_to_the_same_class(client, fake_db, label):
    """The two screens wrote '10th A' and '10th-A'. Both mean the same class."""
    resp = _send_to_class(client, [label])
    assert resp.status_code == 200, resp.text
    stored = fake_db.announcements.docs[-1]
    assert stored["audience_class_ids"] == ["cls-10-a"]
    # The label is normalised for display too, so the list stops showing two spellings.
    assert stored["audience_classes"] == ["10th A"]


def test_a_class_that_does_not_exist_is_refused_and_named(client):
    """Never silently dropped: a discarded class looks exactly like a delivered one."""
    resp = _send_to_class(client, ["10th A", "14th Z"])
    assert resp.status_code == 400
    assert "14th Z" in resp.json()["detail"]


def test_by_class_with_no_class_chosen_is_refused(client):
    resp = _send_to_class(client, [])
    assert resp.status_code == 400
    assert "at least one class" in resp.json()["detail"].lower()


# ------------------------------------------------------------------- who receives it

def test_only_the_targeted_class_sees_it_in_the_announcements_list(client, fake_db):
    assert _send_to_class(client, ["10th A"]).status_code == 200

    in_class = client.get("/api/ops/announcements", headers=_headers("user-stu-a", "student"))
    other_class = client.get("/api/ops/announcements", headers=_headers("user-stu-b", "student"))
    assert in_class.status_code == 200 and other_class.status_code == 200

    assert [a["title"] for a in in_class.json()["data"]] == ["Trip on Sunday"]
    assert other_class.json()["data"] == []
    # The count must agree with the rows, or "showing 0 of 1" teaches people to distrust it.
    assert other_class.json()["meta"]["total"] == 0


def test_only_the_targeted_class_is_notified(client, fake_db):
    assert _send_to_class(client, ["10th A"]).status_code == 200

    def _titles(user_id):
        resp = client.get("/api/notifications", headers=_headers(user_id, "student"))
        assert resp.status_code == 200
        return [row["message"] for row in resp.json()["data"]]

    assert "Trip on Sunday" in _titles("user-stu-a")
    assert "Trip on Sunday" not in _titles("user-stu-b")


def test_a_school_wide_notice_still_reaches_every_student(client):
    """The fix narrows class notices. It must not narrow anything else."""
    resp = client.post(
        "/api/ops/announcements",
        json={"title": "Holiday Monday", "content": "School closed.", "audience_type": "all"},
        headers=_headers("owner-1", "owner"),
    )
    assert resp.status_code == 200
    for user_id in ("user-stu-a", "user-stu-b"):
        titles = [a["title"] for a in client.get("/api/ops/announcements", headers=_headers(user_id, "student")).json()["data"]]
        assert "Holiday Monday" in titles


def test_a_teacher_is_not_reached_by_a_class_notice(client):
    """"By Class" means the class. A teacher belongs to no class, so it is not for them."""
    assert _send_to_class(client, ["10th A"]).status_code == 200
    resp = client.get("/api/ops/announcements", headers=_headers("teacher-1", "teacher"))
    assert [a["title"] for a in resp.json()["data"]] == []


def test_search_cannot_turn_up_another_class_notice(client, fake_db, monkeypatch):
    import routes.search as search_routes

    assert _send_to_class(client, ["10th A"]).status_code == 200
    monkeypatch.setattr(search_routes, "get_db", lambda: fake_db)

    mine = client.get("/api/search?q=Trip", headers=_headers("user-stu-a", "student")).json()["data"]
    theirs = client.get("/api/search?q=Trip", headers=_headers("user-stu-b", "student")).json()["data"]
    assert [h["name"] for h in mine if h.get("type") == "announcement"] == ["Trip on Sunday"]
    assert [h for h in theirs if h.get("type") == "announcement"] == []


# ------------------------------------------------------------------- the parent portal

def test_a_parent_sees_their_own_child_class_notice_and_not_another_class(client):
    assert _send_to_class(client, ["10th A"]).status_code == 200
    mine = client.get("/api/guardian/wards/stu-a/dashboard", headers=_headers("parent-a", "parent"))
    theirs = client.get("/api/guardian/wards/stu-b/dashboard", headers=_headers("parent-b", "parent"))
    assert [a["title"] for a in mine.json()["data"]["announcements"]] == ["Trip on Sunday"]
    assert theirs.json()["data"]["announcements"] == []


def test_a_parent_never_sees_an_unapproved_announcement(client, fake_db):
    """The old filter read two fields announcements have never carried, so it matched
    everything: parents were shown drafts and rejected notices."""
    fake_db.announcements.docs.append({
        "id": "ann-pending", "schoolId": SCHOOL, "branch_id": BRANCH,
        "title": "Not approved yet", "content": "...",
        "audience_type": "all", "audience_roles": ["parent"], "target_roles": ["parent"],
        "audience_class_ids": [], "audience_classes": [],
        "is_draft": False, "status": "pending_approval", "created_at": "2026-08-15",
    })
    resp = client.get("/api/guardian/wards/stu-a/dashboard", headers=_headers("parent-a", "parent"))
    assert [a["title"] for a in resp.json()["data"]["announcements"]] == []


def test_a_parent_is_not_shown_a_staff_only_notice(client, fake_db):
    fake_db.announcements.docs.append({
        "id": "ann-staff", "schoolId": SCHOOL, "branch_id": BRANCH,
        "title": "Salary review meeting", "content": "...",
        "audience_type": "role", "audience_roles": ["admin", "teacher"],
        "target_roles": ["admin", "teacher"],
        "audience_class_ids": [], "audience_classes": [],
        "is_draft": False, "status": "active", "created_at": "2026-08-15",
    })
    resp = client.get("/api/guardian/wards/stu-a/dashboard", headers=_headers("parent-a", "parent"))
    assert [a["title"] for a in resp.json()["data"]["announcements"]] == []


# --------------------------------------------------- "Everyone" reaches the owner too

def test_everyone_includes_the_school_owner(client, fake_db):
    """Abhimanyu, 2026-08-15: an announcement must reach Aman and Adesh. Adesh was
    already reached as an `admin`; the owner was in no audience list at all."""
    resp = client.post(
        "/api/ops/announcements",
        json={"title": "Sports day", "content": "Friday.", "audience_type": "all"},
        headers=_headers("principal-1", "admin", "principal"),
    )
    assert resp.status_code == 200, resp.text
    assert "owner" in fake_db.announcements.docs[-1]["audience_roles"]


def test_a_principal_still_cannot_single_the_owner_out(client):
    """Widening "Everyone" must not quietly retire the guard beside it."""
    resp = client.post(
        "/api/ops/announcements",
        json={"title": "For you only", "content": "...", "audience_roles": ["owner"]},
        headers=_headers("principal-1", "admin", "principal"),
    )
    assert resp.status_code == 422
