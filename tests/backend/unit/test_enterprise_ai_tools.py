from __future__ import annotations

import pytest

from ai.prompts import _resolve_tools
from ai.tool_functions_v2 import (
    tool_get_admissions_pipeline,
    tool_get_my_school_hub,
    tool_query_maintenance_requests,
)
from tests.backend.factories import make_student

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = (
        "students", "guardians", "fee_transactions", "student_leave_requests",
        "library_loans", "quizzes", "quiz_attempts", "admission_applications",
        "tech_requests", "facility_requests",
    )
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


async def test_parent_ai_hub_is_limited_to_linked_ward(fake_db, monkeypatch):
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    fake_db.students.docs.extend([
        make_student(id="ward-a", class_id="class-a", branch_id="branch-a", name="Ward A"),
        make_student(id="ward-b", class_id="class-a", branch_id="branch-a", name="Ward B"),
    ])
    fake_db.guardians.docs.append({
        "id": "guardian-a", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "user_id": "parent-a", "student_id": "ward-a",
    })
    fake_db.fee_transactions.docs.extend([
        {"id": "fee-a", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "ward-a", "status": "pending", "amount": 1000},
        {"id": "fee-b", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "ward-b", "status": "pending", "amount": 9000},
    ])

    allowed = await tool_get_my_school_hub(
        {"student_id": "ward-a"}, {"id": "parent-a", "role": "parent", "branch_id": "branch-a"}
    )
    denied = await tool_get_my_school_hub(
        {"student_id": "ward-b"}, {"id": "parent-a", "role": "parent", "branch_id": "branch-a"}
    )

    assert allowed["success"] is True
    assert allowed["data"]["student"]["id"] == "ward-a"
    assert allowed["data"]["fee_outstanding"]["owed"] == 1000
    assert denied["success"] is False


async def test_admissions_ai_tool_masks_phone_and_is_branch_scoped(fake_db, monkeypatch):
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    fake_db.admission_applications.docs.extend([
        {"id": "app-a", "schoolId": "aaryans-joya", "branch_id": "branch-a", "applicant_name": "A", "phone": "9876543210", "status": "submitted", "created_at": "2026-08-05"},
        {"id": "app-b", "schoolId": "aaryans-joya", "branch_id": "branch-b", "applicant_name": "B", "phone": "9999999999", "status": "submitted", "created_at": "2026-08-05"},
    ])

    result = await tool_get_admissions_pipeline(
        {}, {"id": "owner-a", "role": "owner", "branch_id": "branch-a"}
    )

    assert result["meta"]["count"] == 1
    assert result["data"]["applications"][0]["id"] == "app-a"
    assert result["data"]["applications"][0]["phone"] != "9876543210"


async def test_parent_prompt_exposes_only_guardian_hub():
    assert [item["name"] for item in _resolve_tools("parent", None)] == ["get_my_school_hub"]


async def test_reviewed_accountant_prompt_has_finance_writes_but_teacher_stays_locked_down():
    accountant = {item["name"] for item in _resolve_tools("admin", "accountant")}
    teacher = {item["name"] for item in _resolve_tools("teacher", "class_teacher")}
    assert "record_fee_payment" in accountant
    assert "mark_attendance" not in teacher
    assert "award_house_points" not in teacher


async def test_it_tool_reads_technology_requests_not_facility_requests(fake_db, monkeypatch):
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    fake_db.tech_requests.docs.append({
        "id": "tech-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "status": "open", "title": "Projector offline", "created_at": "2026-08-05",
    })
    fake_db.facility_requests.docs.append({
        "id": "facility-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "status": "open", "title": "Broken chair", "created_at": "2026-08-05",
    })
    result = await tool_query_maintenance_requests(
        {"status": "open"},
        {"id": "it-user", "role": "admin", "sub_category": "it_tech", "branch_id": "branch-a"},
    )
    assert [item["id"] for item in result["data"]] == ["tech-1"]
