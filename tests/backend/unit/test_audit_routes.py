from __future__ import annotations

from middleware.auth import create_jwt


def _headers(user_id: str, role: str, *, sub_category: str | None = None, branch_id: str | None = None) -> dict:
    payload = {"user_id": user_id, "role": role, "name": user_id}
    if sub_category:
        payload["sub_category"] = sub_category
    if branch_id:
        payload["branch_id"] = branch_id
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def test_audit_log_branch_param_filters_owner_results(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "branch_id": "branch-1", "action": "one", "created_at": "2026-01-02"},
        {"id": "a2", "schoolId": "aaryans-joya", "branch_id": "branch-2", "action": "two", "created_at": "2026-01-01"},
    ]

    response = client.get(
        "/api/audit-log?branch_id=branch-1",
        headers=_headers("owner-1", "owner"),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["a1"]


def test_principal_audit_log_auto_filters_to_own_branch(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "branch_id": "branch-1", "collection": "students", "created_at": "2026-01-02"},
        {"id": "a2", "schoolId": "aaryans-joya", "branch_id": "branch-2", "collection": "students", "created_at": "2026-01-01"},
    ]

    response = client.get(
        "/api/audit-log",
        headers=_headers("principal-1", "admin", sub_category="principal", branch_id="branch-2"),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["a2"]


def test_principal_audit_log_cannot_override_branch_param(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "branch_id": "branch-1", "collection": "students", "created_at": "2026-01-02"},
        {"id": "a2", "schoolId": "aaryans-joya", "branch_id": "branch-2", "collection": "students", "created_at": "2026-01-01"},
    ]

    response = client.get(
        "/api/audit-log?branch_id=branch-1",
        headers=_headers("principal-1", "admin", sub_category="principal", branch_id="branch-2"),
    )

    assert response.status_code == 403


def test_owner_audit_log_without_branch_param_sees_all_school_branches(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "branch_id": "branch-1", "created_at": "2026-01-02"},
        {"id": "a2", "schoolId": "aaryans-joya", "branch_id": "branch-2", "created_at": "2026-01-01"},
    ]

    response = client.get("/api/audit-log", headers=_headers("owner-1", "owner"))

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["data"]} == {"a1", "a2"}


def test_audit_record_history_is_paginated(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": f"a{i}", "schoolId": "aaryans-joya", "entity_id": "record-1", "created_at": f"2026-01-{i:02d}"}
        for i in range(1, 26)
    ]

    response = client.get(
        "/api/audit-log/record/record-1?page=2&limit=10",
        headers=_headers("owner-1", "owner"),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 10
    assert body["meta"] == {"page": 2, "limit": 10, "total": 25}


# ── Who may read the log at all (owner request 10, 2026-08-06) ──────────────
# Owner and principal only. `it_tech` and `management` used to be admitted here
# and by the Help & Support menu; both sides are now closed.

def test_audit_log_unauthenticated_returns_401(client):
    assert client.get("/api/audit-log").status_code == 401


def test_audit_log_wrong_role_returns_403(client):
    response = client.get("/api/audit-log", headers=_headers("t1", "teacher"))
    assert response.status_code == 403


def test_it_tech_admin_cannot_read_audit_log(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "collection": "students", "created_at": "2026-01-02"},
    ]

    response = client.get(
        "/api/audit-log",
        headers=_headers("it-1", "admin", sub_category="it_tech"),
    )

    assert response.status_code == 403


def test_management_admin_cannot_read_audit_log(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "collection": "students", "created_at": "2026-01-02"},
    ]

    response = client.get(
        "/api/audit-log",
        headers=_headers("mgmt-1", "admin", sub_category="management"),
    )

    assert response.status_code == 403


def test_it_tech_admin_cannot_read_record_history(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "entity_id": "record-1", "created_at": "2026-01-02"},
    ]

    response = client.get(
        "/api/audit-log/record/record-1",
        headers=_headers("it-1", "admin", sub_category="it_tech"),
    )

    assert response.status_code == 403


def test_management_admin_cannot_read_record_history(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "entity_id": "record-1", "created_at": "2026-01-02"},
    ]

    response = client.get(
        "/api/audit-log/record/record-1",
        headers=_headers("mgmt-1", "admin", sub_category="management"),
    )

    assert response.status_code == 403


def test_principal_still_reads_the_audit_log(client, fake_db):
    fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "collection": "students", "created_at": "2026-01-02"},
    ]

    response = client.get(
        "/api/audit-log",
        headers=_headers("principal-1", "admin", sub_category="principal"),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == ["a1"]


def test_audit_log_rejects_invalid_pagination(client):
    headers = _headers("owner-1", "owner")

    page_zero = client.get("/api/audit-log?page=0", headers=headers)
    negative_limit = client.get("/api/audit-log?limit=-5", headers=headers)

    # Still refused, still a 400. Release 3 moved the check into the shared
    # `backend/pagination.py` so that every list refuses the same things the same
    # way, which changed the wording; the assertion now pins the substance.
    assert page_zero.status_code == 400
    assert "page must be 1 or more" in page_zero.json()["detail"]
    assert negative_limit.status_code == 400
    assert "limit must be 1 or more" in negative_limit.json()["detail"]
