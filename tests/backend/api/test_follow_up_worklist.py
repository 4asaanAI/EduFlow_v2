from __future__ import annotations

"""A5: who to call today.

The follow-up date has been written onto the enquiry since the CRM shipped and nothing
ever read it back. These tests pin the two halves of the fix: the list itself, and the
honesty that stops an EMPTY list reading as "the office is up to date" when the truth is
"nobody has planned a single call".
"""

import pytest

from middleware.auth import create_jwt


def _headers(user_id: str, role: str, sub_category: str | None = None, branch_id: str = "branch-a"):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": branch_id}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


PATH = "/api/commercial/crm/follow-ups"


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = ("legal_entities", "enquiries", "crm_activities", "crm_contact_keys", "audit_logs")
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


@pytest.fixture
def entity(client, fake_db):
    owner = _headers("owner-1", "owner")
    response = client.post("/api/commercial/entities", headers=owner, json={
        "name": "The Aaryans School", "code": "TAS", "entity_type": "school",
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _seed_enquiry(fake_db, entity, enquiry_id, *, name, due=None, status="contacted",
                  school="aaryans-joya", branch="branch-a"):
    doc = {
        "_id": enquiry_id, "id": enquiry_id, "schoolId": school, "branch_id": branch,
        "entity_id": entity["id"], "student_name": name, "parent_name": f"{name}'s parent",
        "phone": "9000000000", "class_applying": "Class 5", "status": status,
        "created_at": "2026-08-01T00:00:00",
    }
    if due is not None:
        doc["next_follow_up"] = due
    fake_db.enquiries.docs.append(doc)
    return doc


# ─── Security convention: every new endpoint ─────────────────────────────────

def test_follow_up_worklist_unauthenticated_returns_401(client):
    assert client.get(PATH).status_code == 401


def test_follow_up_worklist_wrong_role_returns_403(client):
    assert client.get(PATH, headers=_headers("stu-1", "student")).status_code == 403
    assert client.get(PATH, headers=_headers("tch-1", "teacher")).status_code == 403
    # The accountant head does not hold the admissions screen and does not hold this.
    assert client.get(PATH, headers=_headers("acc-1", "admin", "accountant")).status_code == 403


def test_the_same_desks_that_write_a_follow_up_date_can_read_the_list(client, entity):
    for user in (_headers("owner-1", "owner"),
                 _headers("pri-1", "admin", "principal"),
                 _headers("rec-1", "admin", "receptionist")):
        assert client.get(PATH, headers=user).status_code == 200


# ─── The list itself ─────────────────────────────────────────────────────────

def test_families_are_split_into_missed_today_and_the_week_ahead(client, fake_db, entity):
    owner = _headers("owner-1", "owner")
    _seed_enquiry(fake_db, entity, "e-late", name="Missed Child", due="2026-08-09")
    _seed_enquiry(fake_db, entity, "e-today", name="Today Child", due="2026-08-14")
    _seed_enquiry(fake_db, entity, "e-soon", name="Soon Child", due="2026-08-18")
    _seed_enquiry(fake_db, entity, "e-far", name="Far Child", due="2026-09-30")

    body = client.get(f"{PATH}?today=2026-08-14", headers=owner).json()["data"]

    assert [row["student_name"] for row in body["overdue"]] == ["Missed Child"]
    assert [row["student_name"] for row in body["due_today"]] == ["Today Child"]
    assert [row["student_name"] for row in body["upcoming"]] == ["Soon Child"]
    # The one scheduled beyond the window is not shown and is not hidden either.
    assert body["counts"]["scheduled_beyond_the_window"] == 1
    assert body["overdue"][0]["days_overdue"] == 5
    assert body["due_today"][0]["days_overdue"] == 0


def test_an_empty_list_says_how_many_families_nobody_has_planned_a_call_with(client, fake_db, entity):
    """The point of the whole item. A list built only from rows that carry a date is
    empty both when the office is up to date and when the office has planned nothing,
    and those are opposite facts."""
    owner = _headers("owner-1", "owner")
    for index in range(3):
        _seed_enquiry(fake_db, entity, f"e-{index}", name=f"Child {index}")

    body = client.get(f"{PATH}?today=2026-08-14", headers=owner).json()["data"]

    assert body["overdue"] == [] and body["due_today"] == [] and body["upcoming"] == []
    assert body["counts"]["active_enquiries"] == 3
    assert body["counts"]["no_follow_up_date_set"] == 3


def test_finished_families_are_never_chased(client, fake_db, entity):
    owner = _headers("owner-1", "owner")
    _seed_enquiry(fake_db, entity, "e-lost", name="Gone Child", due="2026-08-01", status="lost")
    _seed_enquiry(fake_db, entity, "e-enrolled", name="Joined Child", due="2026-08-01", status="enrolled")
    _seed_enquiry(fake_db, entity, "e-live", name="Live Child", due="2026-08-01")

    body = client.get(f"{PATH}?today=2026-08-14", headers=owner).json()["data"]

    assert [row["student_name"] for row in body["overdue"]] == ["Live Child"]
    assert body["counts"]["active_enquiries"] == 1


def test_another_school_and_another_branch_are_never_in_the_list(client, fake_db, entity):
    owner = _headers("owner-1", "owner")
    _seed_enquiry(fake_db, entity, "e-mine", name="Our Child", due="2026-08-01")
    _seed_enquiry(fake_db, entity, "e-other-school", name="Other School Child",
                  due="2026-08-01", school="other-school")
    _seed_enquiry(fake_db, entity, "e-other-branch", name="Other Branch Child",
                  due="2026-08-01", branch="branch-b")

    body = client.get(f"{PATH}?today=2026-08-14", headers=owner).json()["data"]

    assert [row["student_name"] for row in body["overdue"]] == ["Our Child"]


def test_the_last_thing_written_down_travels_with_the_row(client, fake_db, entity):
    owner = _headers("owner-1", "owner")
    _seed_enquiry(fake_db, entity, "e-1", name="Aarav Singh", due="2026-08-10")
    fake_db.crm_activities.docs.extend([
        {"_id": "a-1", "id": "a-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "enquiry_id": "e-1", "activity_type": "call", "subject": "First call",
         "occurred_at": "2026-08-02T09:00:00"},
        {"_id": "a-2", "id": "a-2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "enquiry_id": "e-1", "activity_type": "visit", "subject": "Campus visit",
         "occurred_at": "2026-08-08T09:00:00"},
    ])

    body = client.get(f"{PATH}?today=2026-08-14", headers=owner).json()["data"]

    assert body["overdue"][0]["last_activity"]["subject"] == "Campus visit"


def test_logging_a_call_with_a_date_puts_that_family_on_the_list(client, fake_db, entity):
    """End to end through the real write path, not a seeded row: the activity route is
    what the screen calls, and it is what makes the worklist non-empty."""
    owner = _headers("owner-1", "owner")
    lead = client.post("/api/commercial/crm/leads", headers=owner, json={
        "entity_id": entity["id"], "student_name": "Aarav Singh", "parent_name": "Neha Singh",
        "phone": "9111111111", "class_applying": "Class 5",
    })
    assert lead.status_code == 200, lead.text
    lead_id = lead.json()["data"]["id"]
    assert client.get(f"{PATH}?today=2026-08-14", headers=owner).json()["meta"]["due_today"] == 0

    logged = client.post(f"/api/commercial/crm/leads/{lead_id}/activities", headers=owner, json={
        "activity_type": "call", "subject": "Spoke to mother", "next_follow_up": "2026-08-14",
    })
    assert logged.status_code == 200, logged.text

    body = client.get(f"{PATH}?today=2026-08-14", headers=owner).json()["data"]
    assert [row["student_name"] for row in body["due_today"]] == ["Aarav Singh"]
    assert body["counts"]["no_follow_up_date_set"] == 0


# ─── A date the platform cannot read ─────────────────────────────────────────

def test_an_unreadable_follow_up_date_is_refused_at_every_entrance(client, entity):
    owner = _headers("owner-1", "owner")
    bad = client.post("/api/commercial/crm/leads", headers=owner, json={
        "entity_id": entity["id"], "student_name": "Aarav Singh", "phone": "9222222222",
        "next_follow_up": "next Tuesday",
    })
    assert bad.status_code == 400
    assert "YYYY-MM-DD" in bad.json()["detail"]

    lead_id = client.post("/api/commercial/crm/leads", headers=owner, json={
        "entity_id": entity["id"], "student_name": "Aarav Singh", "phone": "9333333333",
    }).json()["data"]["id"]
    assert client.patch(f"/api/commercial/crm/leads/{lead_id}", headers=owner,
                        json={"next_follow_up": "soon"}).status_code == 400
    assert client.post(f"/api/commercial/crm/leads/{lead_id}/activities", headers=owner, json={
        "activity_type": "call", "subject": "Called", "next_follow_up": "31/08/2026",
    }).status_code == 400


def test_a_date_already_in_the_records_that_cannot_be_read_is_shown_not_dropped(client, fake_db, entity):
    """102 real enquiries predate the rule above. One carrying rubbish must still reach
    a person: a row in no bucket at all is the silent short answer again."""
    owner = _headers("owner-1", "owner")
    _seed_enquiry(fake_db, entity, "e-odd", name="Odd Child", due="sometime soon")

    body = client.get(f"{PATH}?today=2026-08-14", headers=owner).json()["data"]

    assert [row["student_name"] for row in body["overdue"]] == ["Odd Child"]
    assert body["overdue"][0]["date_is_readable"] is False


def test_a_nonsense_window_is_refused_rather_than_quietly_adjusted(client, entity):
    owner = _headers("owner-1", "owner")
    assert client.get(f"{PATH}?today=not-a-date", headers=owner).status_code == 400
    assert client.get(f"{PATH}?upcoming_days=-1", headers=owner).status_code == 400
    assert client.get(f"{PATH}?upcoming_days=900", headers=owner).status_code == 400
