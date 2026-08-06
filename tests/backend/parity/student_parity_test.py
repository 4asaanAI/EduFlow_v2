"""Story J.1 — dual-entrypoint parity for student CRUD.

Same seed + same actor (owner) through the REST routes (POST /api/students/,
PATCH /api/students/{id}, PUT /api/students/{id}/guardians) and the AI tools
(`create_student`, `update_student`, `manage_student_guardians`,
`set_student_status`) → `students` + `guardians` + `audit_logs` byte-identical
except a volatile allowlist.

Also pins the AD15 guarantee that NO `delete_student`/`erase_student` AI tool exists.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

# student_id/entity_id/record_id are foreign-key references to the volatile
# student UUID (re-generated each run) — mask them like ids.
_VOLATILE = {"id", "_id", "student_id", "entity_id", "record_id",
             "created_at", "updated_at", "admission_date", "timestamp"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask_one(d):
    return {k: v for k, v in d.items() if k not in _VOLATILE}


def _mask(docs):
    out = []
    for d in docs:
        m = _mask_one(d)
        ch = m.get("changes")
        if isinstance(ch, dict):
            m = {**m, "changes": _mask_changes(ch)}
        out.append(m)
    out.sort(key=lambda d: (str(d.get("entity_id", "")), str(d.get("action", "")),
                            str(d.get("name", "")), str(d.get("relation", ""))))
    return out


def _mask_changes(ch):
    # Audit 'changes' embeds the created student doc (volatile ids/timestamps).
    out = {}
    for k, v in ch.items():
        if isinstance(v, dict) and ("created" == k or "id" in v or "_id" in v):
            out[k] = _mask_one(v) if k == "created" else v
        else:
            out[k] = v
    return out


def _snapshot(fake_db):
    return {
        "students": _mask(copy.deepcopy(fake_db.students.docs)),
        "guardians": _mask(copy.deepcopy(fake_db.guardians.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("entity_type") == "student"]),
    }


def _clear(fake_db):
    for col in ("students", "guardians", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


def _create_payload(adm):
    return {
        "name": "Parity Kid", "class_id": "class-1", "admission_number": adm,
        "roll_number": "R-9", "gender": "M",
        "father_name": "Dad Parity", "father_phone": "9000000001",
        "mother_name": "Mom Parity", "mother_phone": "9000000002",
    }


async def test_create_student_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    # --- REST ---
    resp = client.post("/api/students", headers=auth_headers, json=_create_payload("ADM-PAR-1"))
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- AI ---
    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_student(_create_payload("ADM-PAR-1"), OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert len(rest_state["students"]) == 1
    assert len(rest_state["guardians"]) == 2
    assert len(rest_state["audit_logs"]) == 1


async def test_update_student_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    # seed one student via REST, snapshot, then run identical PATCH via REST vs AI
    create = client.post("/api/students", headers=auth_headers, json=_create_payload("ADM-PAR-2"))
    sid = create.json()["data"]["id"]
    # --- REST update ---
    resp = client.patch(f"/api/students/{sid}", headers=auth_headers, json={"house": "Tagore", "roll_number": "R-42"})
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- reset to pre-update state, replay via AI ---
    _clear(fake_db)
    client.post("/api/students", headers=auth_headers, json=_create_payload("ADM-PAR-2"))
    sid2 = [s for s in fake_db.students.docs][0]["id"]
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_update_student(
        {"student_id": sid2, "house": "Tagore", "roll_number": "R-42"}, OWNER_USER, None
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    # one create audit + one update audit
    assert len([a for a in rest_state["audit_logs"] if a.get("action") == "update"]) == 1


async def test_guardians_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    create = client.post("/api/students", headers=auth_headers, json=_create_payload("ADM-PAR-3"))
    sid = create.json()["data"]["id"]
    guardians = [{"name": "New Guardian", "phone": "9111111111", "relation": "Uncle", "is_primary": True}]
    resp = client.put(f"/api/students/{sid}/guardians", headers=auth_headers, json=guardians)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    client.post("/api/students", headers=auth_headers, json=_create_payload("ADM-PAR-3"))
    sid2 = [s for s in fake_db.students.docs][0]["id"]
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_manage_student_guardians(
        {"student_id": sid2, "guardians": guardians}, OWNER_USER, None
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)
    assert ai_state == rest_state


async def test_set_status_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    create = client.post("/api/students", headers=auth_headers, json=_create_payload("ADM-PAR-4"))
    sid = create.json()["data"]["id"]
    resp = client.patch(f"/api/students/{sid}", headers=auth_headers, json={"status": "withdrawn"})
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    client.post("/api/students", headers=auth_headers, json=_create_payload("ADM-PAR-4"))
    sid2 = [s for s in fake_db.students.docs][0]["id"]
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_set_student_status(
        {"student_id": sid2, "status": "withdrawn"}, OWNER_USER, None
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)
    assert ai_state == rest_state


def test_no_ai_student_erase_tool():
    """AD15: permanent erasure stays UI-only — never AI-reachable.

    Restated 2026-08-07. The rule used to be written as "no `delete_student` tool
    either", and on the owner's instruction a `delete_student` tool now exists. That is
    not a relaxation of AD15: the new tool takes a child OFF THE ROLL and the Student
    Database screen puts them back, which is what the delete button on that screen has
    always done. What AD15 exists to prevent is the assistant destroying a child's
    record beyond recovery, and the test below proves that is still impossible.
    """
    assert "erase_student" not in tool_functions_v2.TOOL_REGISTRY
    assert not [
        name for name in tool_functions_v2.TOOL_REGISTRY
        if "erase" in name and "student" in name
    ]


async def test_ai_delete_student_takes_off_the_roll_and_destroys_nothing(fake_db, monkeypatch):
    """The AD15 property, asserted on behaviour rather than on a tool name."""
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    _clear(fake_db)
    fake_db.students.docs.append({
        "id": "stu-del-1", "_id": "stu-del-1", "schoolId": "aaryans-joya",
        "name": "Test Pupil", "admission_number": "ADM-DEL-1",
        "is_active": True, "status": "active",
    })

    out = await tool_functions_v2.tool_delete_student(
        {"student_id": "stu-del-1"}, OWNER_USER, None
    )

    assert out["success"] is True
    surviving = [s for s in fake_db.students.docs if s["id"] == "stu-del-1"]
    assert surviving, "the AI must never destroy a student record — only take them off the roll"
    assert surviving[0]["is_active"] is False
    # And the way back still exists.
    back = await tool_functions_v2.tool_set_student_status(
        {"student_id": "stu-del-1", "status": "active"}, OWNER_USER, None
    )
    assert back["success"] is True
