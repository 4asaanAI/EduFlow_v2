from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ai import tool_functions as legacy_tools
from ai import tool_functions_v2 as owner_tools
from ai.tool_functions_v2 import TOOL_REGISTRY
from middleware.auth import create_jwt
from routes.chat import _is_tool_authorized


TOUCHED_COLLECTIONS = (
    "students",
    "fee_transactions",
    "fee_discounts",
    "fee_discount_types",
    "fee_sync_jobs",
    "facility_requests",
    "incidents",
    "approval_requests",
    "staff_attendance",
    "audit_logs",
    "notifications",
    "expenses",
    "school_settings",
)


@pytest.fixture(autouse=True)
def _restore_collections(fake_db):
    originals = {name: list(getattr(fake_db, name).docs) for name in TOUCHED_COLLECTIONS}
    for name in TOUCHED_COLLECTIONS:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _headers(role: str, sub_category: str | None = None) -> dict:
    payload = {
        "user_id": f"{role}-{sub_category or 'user'}",
        "role": role,
        "name": f"{role} user",
    }
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner() -> dict:
    return {"id": "owner-1", "role": "owner", "name": "Owner"}


OWNER_ONLY_ENDPOINTS = (
    ("GET", "/api/reports/fee-collection-summary", None, None),
    ("GET", "/api/fees/discount-summary", None, None),
    ("POST", "/api/fees/sync/job-1/resolve-conflict", {"conflict_id": "c1", "decision": "keep_ours"}, None),
    ("POST", "/api/issues/facility/fr-1/confirm-resolution", None, None),
    ("PATCH", "/api/settings/school", {"school_name": "Aaryans"}, None),
    ("POST", "/api/students/student-1/erase", None, {"reason": "Detailed erasure reason for QA"}),
    ("PUT", "/api/tokens/limits", {"limits": {"teacher": 1, "student": 1}}, None),
    (
        "PATCH",
        "/api/operator/schools/aaryans-joya/ai-rate-limit",
        {"role": "teacher", "limit": 10, "reason": "QA matrix", "expires_at": None},
        None,
    ),
    ("GET", "/api/operator/ai-action-counts?user_id=teacher-1&session_id=session-1", None, None),
    ("GET", "/api/export/expenses", None, None),
)


@pytest.mark.parametrize("method,url,json_body,form_body", OWNER_ONLY_ENDPOINTS)
@pytest.mark.parametrize(
    "headers",
    [
        _headers("teacher"),
        _headers("admin", "principal"),
        _headers("student"),
    ],
)
@pytest.mark.asyncio
async def test_owner_only_endpoints_reject_teacher_admin_and_student(
    client,
    method,
    url,
    json_body,
    form_body,
    headers,
):
    kwargs = {"headers": headers}
    if json_body is not None:
        kwargs["json"] = json_body
    if form_body is not None:
        kwargs["data"] = form_body

    response = client.request(method, url, **kwargs)

    assert response.status_code == 403


@pytest.mark.parametrize("tool_name", ["get_financial_report", "query_dashboard_summary", "confirm_resolution"])
@pytest.mark.parametrize(
    "user",
    [
        {"id": "teacher-1", "role": "teacher"},
        {"id": "principal-1", "role": "admin", "sub_category": "principal"},
        {"id": "student-1", "role": "student"},
    ],
)
@pytest.mark.asyncio
async def test_owner_only_ai_tools_reject_non_owner_roles(tool_name, user):
    assert _is_tool_authorized(user, TOOL_REGISTRY[tool_name]) is False


@pytest.mark.parametrize("tool_name", ["get_financial_report", "query_dashboard_summary", "confirm_resolution"])
@pytest.mark.asyncio
async def test_owner_only_ai_tools_allow_owner(tool_name):
    assert _is_tool_authorized(_owner(), TOOL_REGISTRY[tool_name]) is True


@pytest.mark.asyncio
async def test_get_financial_report_excludes_other_school_transactions(fake_db, monkeypatch):
    monkeypatch.setattr(legacy_tools, "get_db", lambda: fake_db)
    fake_db.fee_transactions.docs.extend([
        {"schoolId": "aaryans-joya", "fee_type": "tuition", "status": "paid", "amount": 1000},
        {"schoolId": "aaryans-joya", "fee_type": "tuition", "status": "pending", "amount": 3000},
        {"schoolId": "other-school", "fee_type": "tuition", "status": "paid", "amount": 9000},
    ])

    result = await legacy_tools.tool_get_financial_report({}, _owner())

    assert "4,000" in result["total_expected"]
    assert "1,000" in result["total_collected"]
    assert "9,000" not in str(result)
    assert result["collection_rate"] == "25.0%"


@pytest.mark.asyncio
async def test_query_dashboard_summary_counts_current_school_only(fake_db, monkeypatch):
    monkeypatch.setattr(owner_tools, "get_db", lambda: fake_db)
    today = date.today().isoformat()
    fake_db.incidents.docs.extend([
        {"schoolId": "aaryans-joya", "id": "i1", "status": "open"},
        {"schoolId": "aaryans-joya", "id": "i2", "status": "closed"},
        {"schoolId": "other-school", "id": "i3", "status": "open"},
    ])
    fake_db.approval_requests.docs.extend([
        {"schoolId": "aaryans-joya", "id": "a1", "status": "pending"},
        {"schoolId": "other-school", "id": "a2", "status": "pending"},
    ])
    fake_db.staff_attendance.docs.extend([
        {"schoolId": "aaryans-joya", "id": "sa1", "date": today, "status": "absent"},
        {"schoolId": "other-school", "id": "sa2", "date": today, "status": "absent"},
    ])
    fake_db.fee_transactions.docs.extend([
        {"schoolId": "aaryans-joya", "id": "f1", "status": "pending"},
        {"schoolId": "other-school", "id": "f2", "status": "pending"},
    ])

    result = await owner_tools.tool_query_dashboard_summary({}, _owner())
    summary = result["data"][0]

    assert summary == {
        "open_incidents": 1,
        "pending_approvals": 1,
        "staff_absent_today": 1,
        "fee_outstanding_transactions": 1,
    }


@pytest.mark.asyncio
async def test_facility_resolution_ai_lifecycle_closes_and_audits(fake_db, monkeypatch):
    monkeypatch.setattr(owner_tools, "get_db", lambda: fake_db)
    fake_db.facility_requests.docs.append({
        "_id": "fr-1",
        "id": "fr-1",
        "schoolId": "aaryans-joya",
        "status": "in_progress",
        "logged_by": "maintenance-1",
        "notes": [],
    })
    maintenance = {
        "id": "maintenance-1",
        "role": "admin",
        "sub_category": "maintenance",
        "name": "Maintenance",
    }

    marked = await owner_tools.tool_update_incident_status(
        {"record_id": "fr-1", "new_status": "pending_owner_confirmation", "note": "Work completed"},
        maintenance,
    )
    closed = await owner_tools.tool_confirm_resolution(
        {"request_id": "fr-1", "confirmation_note": "Verified by owner"},
        _owner(),
    )

    row = fake_db.facility_requests.docs[0]
    assert marked["success"] is True
    assert closed["success"] is True
    assert row["status"] == "closed"
    assert row["resolved_by"] == "owner-1"
    assert [entry["content"] for entry in row["notes"]] == ["Work completed", "Verified by owner"]
    assert {item["action"] for item in fake_db.audit_logs.docs} >= {
        "update_incident_status",
        "confirm_resolution",
    }


@pytest.mark.asyncio
async def test_fee_export_student_lookup_is_school_scoped(client, fake_db):
    fake_db.fee_transactions.docs.append({
        "_id": "txn-1",
        "id": "txn-1",
        "schoolId": "aaryans-joya",
        "student_id": "shared-student",
        "fee_head": "tuition",
        "amount": 1200,
        "paid_date": "2026-05-10",
        "status": "paid",
    })
    fake_db.students.docs.extend([
        {"id": "shared-student", "schoolId": "other-school", "name": "Other School Student", "class_name": "X"},
        {"id": "shared-student", "schoolId": "aaryans-joya", "name": "Current School Student", "class_name": "V"},
    ])

    response = client.get("/api/fees/export", headers=_headers("owner"))

    assert response.status_code == 200
    assert "Current School Student" in response.text
    assert "Other School Student" not in response.text


def test_frontend_announcement_broadcaster_sends_moderated_roles():
    source = Path("frontend/src/components/tools/OwnerTools.js").read_text(encoding="utf-8")

    assert "form.audience_type === 'all'" in source
    assert "['teacher', 'student', 'admin', 'parent']" in source
    assert "form.audience_type === 'class'" in source
    assert "['student']" in source
    assert "audience_roles: targetRoles" in source
    assert "target_roles: targetRoles" in source


@pytest.mark.parametrize(
    "path",
    [
        "frontend/src/components/tools/OwnerTools.js",
        "frontend/src/components/tools/FeeCollection.js",
        "frontend/src/components/tools/FeeSync.js",
    ],
)
def test_frontend_auth_headers_do_not_pass_stale_current_user(path):
    source = Path(path).read_text(encoding="utf-8")

    assert "h(currentUser)" not in source


def test_fee_sync_ui_displays_use_theirs_overwritten_fields():
    source = Path("frontend/src/components/tools/FeeSync.js").read_text(encoding="utf-8")

    assert "resolved_fields" in source
    assert "resolvedFieldNames" in source
    assert "Overwritten:" in source
