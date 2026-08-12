"""The school's concessions and its late fine - Flo and the screen, one path.

Release 2 step 10. Abhimanyu's standing rule: anything that can be done by hand, Flo must
do on request, through the same service, proved here. The chat is the flagship of this
product, so a fee capability that exists only on a screen is half built.

Same input through `/api/fees/concessions/*` and through the matching AI tool must leave
the student record and the audit trail identical.
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id",
             "rte_marked_at", "authorised_on", "recorded_by", "rte_source"}

OWNER_USER = {"id": "own-c", "role": "owner", "name": "Owner"}


def _owner_headers():
    return {"Authorization": "Bearer " + create_jwt(
        {"user_id": "own-c", "role": "owner", "name": "Owner", "schoolId": "aaryans-joya"}
    )}


def _mask(docs):
    out = []
    for doc in docs:
        out.append({k: v for k, v in sorted(doc.items()) if k not in _VOLATILE})
    return out


def _seed(fake_db):
    fake_db.students.docs[:] = [{
        "_id": "stu-c", "id": "stu-c", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "name": "A Child", "admission_number": "adm-c", "class_id": "cls-6th",
        "is_active": True,
    }]
    fake_db.audit_logs.docs[:] = []


def _audit(fake_db, action):
    return _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs) if a.get("action") == action])


async def test_setting_a_concession_writes_the_same_thing_either_way(client, fake_db, monkeypatch):
    _seed(fake_db)
    body = {"student_id": "stu-c", "concession": "employee_child", "granted": True}
    assert client.post("/api/fees/concessions/set", json=body,
                       headers=_owner_headers()).status_code == 200
    rest_student = _mask(copy.deepcopy(fake_db.students.docs))
    rest_audit = _audit(fake_db, "concession_set")

    _seed(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_set_student_concession(dict(body), OWNER_USER, None)
    assert out["success"] is True

    assert _mask(copy.deepcopy(fake_db.students.docs)) == rest_student
    assert _audit(fake_db, "concession_set") == rest_audit


async def test_the_one_time_admission_concession_writes_the_same_thing_either_way(
        client, fake_db, monkeypatch):
    _seed(fake_db)
    body = {"student_id": "stu-c", "amount": 6000, "authorised_by": "Aman Litt"}
    assert client.post("/api/fees/concessions/admission", json=body,
                       headers=_owner_headers()).status_code == 200
    rest_student = _mask(copy.deepcopy(fake_db.students.docs))

    _seed(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_record_admission_concession(dict(body), OWNER_USER, None)
    assert out["success"] is True
    assert _mask(copy.deepcopy(fake_db.students.docs)) == rest_student


async def test_a_right_to_education_place_writes_the_same_thing_either_way(
        client, fake_db, monkeypatch):
    _seed(fake_db)
    body = {"student_id": "stu-c", "holds_place": True, "reason": "government letter seen"}
    assert client.post("/api/fees/concessions/right-to-education", json=body,
                       headers=_owner_headers()).status_code == 200
    rest_student = _mask(copy.deepcopy(fake_db.students.docs))

    _seed(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_set_right_to_education(dict(body), OWNER_USER, None)
    assert out["success"] is True
    assert _mask(copy.deepcopy(fake_db.students.docs)) == rest_student


async def test_both_doors_refuse_a_one_time_concession_with_nobody_named(
        client, fake_db, monkeypatch):
    _seed(fake_db)
    body = {"student_id": "stu-c", "amount": 6000}
    assert client.post("/api/fees/concessions/admission", json=body,
                       headers=_owner_headers()).status_code == 400

    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_record_admission_concession(dict(body), OWNER_USER, None)
    assert out["success"] is False
    assert "authorised_by" in out["message"]
    assert not fake_db.students.docs[0].get("concessions")


async def test_both_doors_refuse_to_hand_out_the_one_time_amount_twice(
        client, fake_db, monkeypatch):
    _seed(fake_db)
    fake_db.students.docs[0]["concessions"] = {
        "admission_discount": {"amount": 6000, "authorised_by": "Aman Litt", "applied_to": "q1"}
    }
    body = {"student_id": "stu-c", "amount": 5000, "authorised_by": "Aman Litt"}
    assert client.post("/api/fees/concessions/admission", json=body,
                       headers=_owner_headers()).status_code == 409

    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_record_admission_concession(dict(body), OWNER_USER, None)
    assert out["success"] is False
    assert "once-only" in out["message"]


async def test_removing_a_right_to_education_place_needs_a_reason_at_both_doors(
        client, fake_db, monkeypatch):
    # Taking the mark off starts billing a family the government pays for.
    _seed(fake_db)
    body = {"student_id": "stu-c", "holds_place": False}
    assert client.post("/api/fees/concessions/right-to-education", json=body,
                       headers=_owner_headers()).status_code == 400

    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_set_right_to_education(dict(body), OWNER_USER, None)
    assert out["success"] is False
    assert "reason is required" in out["message"]


async def test_the_late_fine_answers_the_same_at_both_doors(client, fake_db, monkeypatch):
    body = {"quarters": [{"quarter": "q1", "outstanding_amount": 9750},
                         {"quarter": "q2", "outstanding_amount": 9750}],
            "as_of": "2026-09-01", "session_start_year": 2026}
    rest = client.post("/api/fees/late-fine/calculate", json=body, headers=_owner_headers())
    assert rest.status_code == 200

    out = await tool_functions_v2.tool_calculate_late_fine(dict(body), OWNER_USER, None)
    assert out["success"] is True
    assert out["data"] == rest.json()["data"]
    # And it says the thing that matters: only one daily fine runs.
    assert out["data"]["daily_running"] == "q2"
    assert "Q2" in out["message"]


async def test_explaining_a_childs_fee_answers_the_same_at_both_doors(
        client, fake_db, monkeypatch):
    _seed(fake_db)
    fake_db.students.docs[0]["concessions"] = {"sibling": True}
    fake_db.students.docs[0]["siblings"] = ["adm-other"]
    fake_db.fee_structures.docs[:] = [{
        "_id": "str-6", "id": "str-6", "schoolId": "aaryans-joya", "name": "6th fees",
        "class_id": "cls-6th", "status": "active", "quarterly_amount": 9750,
    }]
    rest = client.get("/api/fees/concessions/stu-c/explain", headers=_owner_headers())
    assert rest.status_code == 200

    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_explain_student_fee({"student_id": "stu-c"},
                                                           OWNER_USER, None)
    assert out["success"] is True
    assert out["data"] == rest.json()["data"]

    # The answer is the one the office actually needs.
    assert out["data"]["band"]["quarterly_amount"] == 9750
    assert out["data"]["concessions"]["net"] == 7950
    assert out["data"]["siblings"] == ["adm-other"]


async def test_a_right_to_education_child_is_explained_as_owing_nothing(
        client, fake_db, monkeypatch):
    _seed(fake_db)
    fake_db.students.docs[0]["rte_place"] = True
    fake_db.fee_structures.docs[:] = [{
        "_id": "str-6", "id": "str-6", "schoolId": "aaryans-joya", "name": "6th fees",
        "class_id": "cls-6th", "status": "active", "quarterly_amount": 9750,
    }]
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_explain_student_fee({"student_id": "stu-c"},
                                                           OWNER_USER, None)
    assert out["data"]["concessions"]["net"] == 0.0
    assert "not a discount" in out["data"]["note"]
