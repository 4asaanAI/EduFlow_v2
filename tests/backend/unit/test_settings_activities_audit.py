from __future__ import annotations

from middleware.auth import create_jwt


def _headers(user_id: str = "admin-1", role: str = "owner", *, branch_id: str = "branch-1") -> dict:
    token = create_jwt({"user_id": user_id, "role": role, "name": user_id, "branch_id": branch_id})
    return {"Authorization": f"Bearer {token}"}


def test_school_settings_update_writes_audit_with_branch(client, fake_db):
    fake_db.audit_logs.docs[:] = []

    response = client.patch(
        "/api/settings/school",
        json={"school_name": "New Name", "ignored": "x"},
        headers=_headers(),
    )

    assert response.status_code == 200
    audit = fake_db.audit_logs.docs[-1]
    assert audit["action"] == "school_settings_update"
    assert audit["collection"] == "school_settings"
    assert audit["branch_id"] == "branch-1"
    assert audit["changes"] == {"school_name": "New Name"}


def test_custom_form_create_and_delete_write_audit(client, fake_db):
    fake_db.audit_logs.docs[:] = []

    created = client.post(
        "/api/settings/forms",
        json={"title": "Consent", "fields": [{"id": "name", "type": "text"}], "audience": "students"},
        headers=_headers(),
    )
    form_id = created.json()["data"]["id"]
    deleted = client.delete(f"/api/settings/forms/{form_id}", headers=_headers())

    assert created.status_code == 200
    assert deleted.status_code == 200
    assert [row["action"] for row in fake_db.audit_logs.docs[-2:]] == [
        "custom_form_create",
        "custom_form_delete",
    ]


def test_house_points_award_writes_audit(client, fake_db):
    fake_db.audit_logs.docs[:] = []
    fake_db.houses.docs[:] = [
        {"id": "blue", "schoolId": "aaryans-joya", "name": "Blue", "points": 10}
    ]

    response = client.post(
        "/api/activities/houses/blue/points",
        json={"delta": 5, "reason": "quiz"},
        headers=_headers(),
    )

    assert response.status_code == 200
    audit = fake_db.audit_logs.docs[-1]
    assert audit["action"] == "house_points_award"
    assert audit["entity_id"] == "blue"
    assert audit["branch_id"] == "branch-1"


def test_sports_team_create_update_delete_write_audit(client, fake_db):
    fake_db.audit_logs.docs[:] = []

    created = client.post(
        "/api/activities/teams",
        json={"name": "A Team", "sport": "Cricket"},
        headers=_headers(),
    )
    team_id = created.json()["data"]["id"]
    updated = client.patch(
        f"/api/activities/teams/{team_id}",
        json={"captain_name": "Demo Student"},
        headers=_headers(),
    )
    deleted = client.delete(f"/api/activities/teams/{team_id}", headers=_headers())

    assert created.status_code == 200
    assert updated.status_code == 200
    assert deleted.status_code == 200
    assert [row["action"] for row in fake_db.audit_logs.docs[-3:]] == [
        "sports_team_create",
        "sports_team_update",
        "sports_team_delete",
    ]
