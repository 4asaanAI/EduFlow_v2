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


def test_audit_log_rejects_invalid_pagination(client):
    headers = _headers("owner-1", "owner")

    page_zero = client.get("/api/audit-log?page=0", headers=headers)
    negative_limit = client.get("/api/audit-log?limit=-5", headers=headers)

    assert page_zero.status_code == 400
    assert page_zero.json()["detail"] == "page must be >= 1"
    assert negative_limit.status_code == 400
    assert negative_limit.json()["detail"] == "limit must be between 1 and 100"
