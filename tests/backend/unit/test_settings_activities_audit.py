from __future__ import annotations

from middleware.auth import create_jwt


def _headers(
    user_id: str = "admin-1", role: str = "owner", *, branch_id: str = "branch-1",
    sub_category: str | None = None,
) -> dict:
    token = create_jwt({
        "user_id": user_id, "role": role, "name": user_id,
        "branch_id": branch_id, "sub_category": sub_category,
    })
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


def test_custom_form_schema_update_and_validated_row_are_audited(client, fake_db):
    created = client.post(
        "/api/settings/forms",
        json={
            "title": "Transport Requests",
            "fields": [
                {"key": "student", "label": "Student", "type": "text", "required": True},
                {"key": "route", "label": "Route", "type": "select", "options": ["A", "B"]},
            ],
        },
        headers=_headers(role="admin", sub_category="management"),
    )
    assert created.status_code == 200
    form_id = created.json()["data"]["id"]

    updated = client.patch(
        f"/api/settings/forms/{form_id}",
        json={"fields": [
            {"key": "student", "label": "Student", "type": "text", "required": True},
            {"key": "route", "label": "Route", "type": "select", "options": ["A", "B"]},
            {"key": "approved", "label": "Approved", "type": "checkbox"},
        ]},
        headers=_headers(role="admin", sub_category="management"),
    )
    submitted = client.post(
        f"/api/settings/forms/{form_id}/responses",
        json={"answers": {"student": "  Riya  ", "route": "A", "approved": False}},
        headers=_headers(role="admin", sub_category="management"),
    )

    assert updated.status_code == 200
    assert updated.json()["data"]["schema_version"] == 2
    assert submitted.status_code == 200
    assert submitted.json()["data"]["answers"]["student"] == "Riya"
    assert [row["action"] for row in fake_db.audit_logs.docs[-2:]] == [
        "custom_form_update", "form_response_submit",
    ]


def test_custom_form_rejects_unknown_or_invalid_values(client):
    created = client.post(
        "/api/settings/forms",
        json={
            "title": "Contacts",
            "fields": [{"key": "email", "label": "Email", "type": "email", "required": True}],
        },
        headers=_headers(),
    )
    form_id = created.json()["data"]["id"]

    invalid = client.post(
        f"/api/settings/forms/{form_id}/responses",
        json={"answers": {"email": "not-an-email", "extra": "x"}},
        headers=_headers(),
    )
    assert invalid.status_code == 400
    assert "Unknown field keys" in invalid.json()["detail"]


def test_custom_form_schema_mutations_reject_accountant_and_student(client):
    payload = {"title": "Restricted", "fields": [{"id": "value", "type": "text"}]}
    accountant = client.post(
        "/api/settings/forms", json=payload,
        headers=_headers(role="admin", sub_category="accountant"),
    )
    student = client.post(
        "/api/settings/forms", json=payload,
        headers=_headers(role="student"),
    )
    assert accountant.status_code == 403
    assert student.status_code == 403


def test_custom_form_data_is_hidden_from_finance_profile(client, fake_db):
    fake_db.custom_forms.docs[:] = [{
        "id": "form-1", "schoolId": "aaryans-joya", "title": "Office register",
        "fields": [{"key": "value", "label": "Value", "type": "text"}],
        "is_active": True,
    }]
    headers = _headers(role="admin", sub_category="accountant")

    assert client.get("/api/settings/forms", headers=headers).status_code == 403
    assert client.get("/api/settings/forms/form-1", headers=headers).status_code == 403
    assert client.post(
        "/api/settings/forms/form-1/responses",
        json={"answers": {"value": "hidden"}},
        headers=headers,
    ).status_code == 403


def test_custom_form_data_is_available_to_management_profile(client, fake_db):
    fake_db.custom_forms.docs[:] = [{
        "id": "form-1", "schoolId": "aaryans-joya", "title": "Office register",
        "fields": [{"key": "value", "label": "Value", "type": "text"}],
        "is_active": True,
    }]
    headers = _headers(role="admin", sub_category="management")

    assert client.get("/api/settings/forms", headers=headers).status_code == 200
    assert client.get("/api/settings/forms/form-1", headers=headers).status_code == 200


def test_custom_form_schema_mutation_requires_authentication(client):
    response = client.patch("/api/settings/forms/form-1", json={"title": "No"})
    assert response.status_code == 401


def test_house_points_award_writes_audit(client, fake_db):
    fake_db.audit_logs.docs[:] = []
    fake_db.houses.docs[:] = [
        {
            "id": "blue",
            "schoolId": "aaryans-joya",
            "branch_id": "branch-1",
            "name": "Blue",
            "points": 10,
        }
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
