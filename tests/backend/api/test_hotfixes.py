"""Regression tests for the P0 hotfix block before Part 5."""

from __future__ import annotations

from middleware.auth import create_jwt
import routes.upload as upload_routes


def _token_headers(user_id: str, role: str, *, sub_category: str | None = None) -> dict:
    payload = {"user_id": user_id, "role": role, "name": user_id}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def test_upload_serve_requires_auth_and_school_scopes_lookup(client, auth_headers, fake_db, monkeypatch):
    monkeypatch.setattr(upload_routes, "get_db", lambda: fake_db)
    fake_db.file_uploads.docs[:] = [
        {
            "_id": "upload-1",
            "id": "upload-1",
            "schoolId": "aaryans-joya",
            "safe_filename": "allowed.pdf",
            "s3_key": "uploads/allowed.pdf",
        },
        {
            "_id": "upload-2",
            "id": "upload-2",
            "schoolId": "other-school",
            "safe_filename": "blocked.pdf",
            "s3_key": "uploads/blocked.pdf",
        },
    ]
    monkeypatch.setattr(
        upload_routes,
        "create_presigned_get_url",
        lambda key: f"https://signed.test/{key}",
    )

    unauthenticated = client.get("/api/uploads/serve/allowed.pdf", follow_redirects=False)
    allowed = client.get(
        "/api/uploads/serve/allowed.pdf",
        headers=auth_headers,
        follow_redirects=False,
    )
    blocked = client.get(
        "/api/uploads/serve/blocked.pdf",
        headers=auth_headers,
        follow_redirects=False,
    )

    assert unauthenticated.status_code == 401
    assert allowed.status_code == 307
    assert allowed.headers["location"] == "https://signed.test/uploads/allowed.pdf"
    assert blocked.status_code == 404


def test_fee_receipt_endpoint_exists_for_frontend_download(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "student-1|2026-05|tuition"}
    created = client.post(
        "/api/fees/transactions",
        json={
            "student_id": "student-1",
            "fee_period": "2026-05",
            "fee_head": "tuition",
            "fee_type": "tuition",
            "amount": 2500,
            "payment_mode": "upi",
            "status": "paid",
            "due_date": "2026-05-10",
        },
        headers=headers,
    ).json()["data"]

    response = client.get(
        f"/api/fees/transactions/{created['id']}/receipt",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_staff_leave_decision_denies_non_principal_admin(client, fake_db):
    fake_db.leave_requests.docs[:] = [
        {
            "_id": "leave-1",
            "id": "leave-1",
            "schoolId": "aaryans-joya",
            "staff_id": "staff-1",
            "user_id": "teacher-1",
            "status": "pending",
        }
    ]
    accountant_headers = _token_headers("acct-1", "admin", sub_category="accountant")

    response = client.patch(
        "/api/staff/leaves/leave-1",
        json={"status": "approved"},
        headers=accountant_headers,
    )

    assert response.status_code == 403
    assert fake_db.leave_requests.docs[0]["status"] == "pending"


def test_staff_leave_decision_allows_principal_admin(client, fake_db):
    fake_db.leave_requests.docs[:] = [
        {
            "_id": "leave-2",
            "id": "leave-2",
            "schoolId": "aaryans-joya",
            "staff_id": "staff-1",
            "user_id": "teacher-1",
            "status": "pending",
        }
    ]
    principal_headers = _token_headers("principal-1", "admin", sub_category="principal")

    response = client.patch(
        "/api/staff/leaves/leave-2",
        json={"status": "approved"},
        headers=principal_headers,
    )

    assert response.status_code == 200
    assert fake_db.leave_requests.docs[0]["status"] == "approved"
    assert fake_db.leave_requests.docs[0]["approved_by"] == "principal-1"
