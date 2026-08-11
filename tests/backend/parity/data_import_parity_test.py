"""Spreadsheet import - dual-entrypoint parity, and the rules protecting real records.

This path writes to 1,876 children's records from a file, so the guarantees matter as
much as the feature:
  * EVERY row is read - the whole reason this exists is that the chat attachment showed
    Flo 3.4% of the school's export and it answered as if it had read all of it.
  * Blanks are filled; information already on record is NOT overwritten unless asked.
  * Rows are matched on admission number, never on name.
"""

from __future__ import annotations

import copy
import io

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id",
             "import_batch", "changes", "record_id"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}


def _owner_headers():
    return {"Authorization": "Bearer " + create_jwt(
        {"user_id": "own-1", "role": "owner", "name": "Owner", "schoolId": "aaryans-joya"}
    )}


def _sheet(rows: list) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


HEADER = ["AdmissionNo", "Name", "Mobile", "Whatsapp", "AadharNo", "FatherName"]
ROWS = [
    HEADER,
    ["ADM-1", "Aryan", "9000000001", "9000000011", "1111 2222 3333", "Rakesh"],
    ["ADM-2", "Priya", "9000000002", "9000000022", "4444 5555 6666", "Suresh"],
]


@pytest.fixture(autouse=True)
def _seed(fake_db, monkeypatch):
    saved = {c: list(getattr(fake_db, c).docs) for c in ("students", "audit_logs")}
    fake_db.students.docs[:] = [
        # Aryan already HAS a mobile - that value must survive the import.
        {"id": "s1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "admission_number": "ADM-1", "name": "Aryan", "phone": "9999999999"},
        {"id": "s2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "admission_number": "ADM-2", "name": "Priya"},
    ]
    fake_db.audit_logs.docs[:] = []
    fake_db.chat_uploaded_files.docs[:] = [
        {"_id": "f1", "id": "f1", "schoolId": "aaryans-joya", "filename": "students.xlsx",
         "s3_key": "aaryans-joya/uploads/f1/students.xlsx"},
    ]

    from services import data_import_service as imp

    payload = _sheet(ROWS)

    async def _fake_load(db, ctx, file_id):
        record = await db.chat_uploaded_files.find_one({"id": file_id}, {"_id": 0})
        if not record:
            raise imp.ImportFileUnavailableError(f"no file {file_id}")
        return payload, record

    monkeypatch.setattr(imp, "_load_file", _fake_load)
    yield
    for col, docs in saved.items():
        getattr(fake_db, col).docs[:] = docs
    fake_db.chat_uploaded_files.docs[:] = []


def _mask(docs):
    out = [{k: v for k, v in d.items() if k not in _VOLATILE} for d in docs]
    out.sort(key=lambda d: str(d.get("admission_number", "")) + str(d.get("action", "")))
    return out


def _snapshot(fake_db):
    return {
        "students": _mask(copy.deepcopy(fake_db.students.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("action") == "data_import_update"]),
    }


def _reset(fake_db):
    fake_db.students.docs[:] = [
        {"id": "s1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "admission_number": "ADM-1", "name": "Aryan", "phone": "9999999999"},
        {"id": "s2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "admission_number": "ADM-2", "name": "Priya"},
    ]
    fake_db.audit_logs.docs[:] = []


async def test_import_ai_and_rest_are_identical(client, fake_db):
    resp = client.post("/api/data-import/apply", json={"file_id": "f1"}, headers=_owner_headers())
    assert resp.status_code == 200, resp.text
    rest_state = _snapshot(fake_db)

    _reset(fake_db)
    result = await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, OWNER_USER, None
    )
    assert result["success"] is True
    assert _snapshot(fake_db) == rest_state


async def test_existing_information_is_never_overwritten_by_default(fake_db):
    """A spreadsheet is usually a stale export. Replacing a live number with an older
    one, silently, across 1,876 students, is the worst outcome this path could have."""
    await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, OWNER_USER, None
    )
    aryan = next(s for s in fake_db.students.docs if s["admission_number"] == "ADM-1")
    assert aryan["phone"] == "9999999999", "the existing mobile was overwritten"
    assert aryan["whatsapp_phone"] == "9000000011", "the blank was not filled"


async def test_overwrite_is_possible_when_asked_for_explicitly(fake_db):
    await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1", "overwrite": True}, OWNER_USER, None
    )
    aryan = next(s for s in fake_db.students.docs if s["admission_number"] == "ADM-1")
    assert aryan["phone"] == "9000000001"


async def test_preview_writes_nothing(fake_db):
    before = copy.deepcopy(fake_db.students.docs)
    result = await tool_functions_v2.TOOL_REGISTRY["preview_data_import"]["fn"](
        {"file_id": "f1"}, OWNER_USER, None
    )
    assert result["success"] is True
    assert fake_db.students.docs == before
    plan = result["data"][0]
    assert plan["rows_read"] == 2
    assert plan["students_to_update"] == 2


async def test_preview_and_apply_agree(fake_db):
    """The number a person approves must be the number that happens."""
    preview = await tool_functions_v2.TOOL_REGISTRY["preview_data_import"]["fn"](
        {"file_id": "f1"}, OWNER_USER, None
    )
    planned = preview["data"][0]["fields_to_fill"]
    applied = await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, OWNER_USER, None
    )
    assert applied["data"]["fields_to_fill"] == planned


async def test_rows_without_an_admission_number_are_reported_never_guessed(fake_db, monkeypatch):
    """Two children share a name far more often than an admission number. Merging two
    pupils' records is not recoverable, so an unidentifiable row must be reported."""
    from services import data_import_service as imp

    payload = _sheet([HEADER, ["", "Aryan", "9000000003", "", "", ""]])

    async def _load(db, ctx, file_id):
        return payload, {"filename": "x.xlsx"}

    monkeypatch.setattr(imp, "_load_file", _load)
    result = await tool_functions_v2.TOOL_REGISTRY["preview_data_import"]["fn"](
        {"file_id": "f1"}, OWNER_USER, None
    )
    plan = result["data"][0]
    assert plan["rows_without_admission_number"] == 1
    assert plan["students_to_update"] == 0


async def test_every_row_is_read_not_a_sample(monkeypatch, fake_db):
    """The defect that motivated this service: 3.4% of the file being treated as all
    of it. A 5,000-row sheet must report 5,000 rows read."""
    from services import data_import_service as imp

    big = [HEADER] + [[f"ADM-{i}", f"Child {i}", f"90000{i:05d}", "", "", ""]
                      for i in range(5000)]
    payload = _sheet(big)

    async def _load(db, ctx, file_id):
        return payload, {"filename": "big.xlsx"}

    monkeypatch.setattr(imp, "_load_file", _load)
    result = await tool_functions_v2.TOOL_REGISTRY["preview_data_import"]["fn"](
        {"file_id": "f1"}, OWNER_USER, None
    )
    assert result["data"][0]["rows_read"] == 5000


async def test_protected_fields_cannot_be_set_from_a_spreadsheet(fake_db, monkeypatch):
    """Fees and enrolment status are reconciled elsewhere; a stale sheet must not
    change a child's standing at the school or their balance."""
    from services import data_import_service as imp

    payload = _sheet([
        ["AdmissionNo", "Name", "Status", "BalanceFees", "Class"],
        ["ADM-1", "Aryan", "inactive", "0", "12"],
    ])

    async def _load(db, ctx, file_id):
        return payload, {"filename": "x.xlsx"}

    monkeypatch.setattr(imp, "_load_file", _load)
    await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1", "overwrite": True}, OWNER_USER, None
    )
    aryan = next(s for s in fake_db.students.docs if s["admission_number"] == "ADM-1")
    assert aryan.get("status") != "inactive"
    assert "balance" not in aryan and "class_id" not in aryan


async def test_each_change_is_audited_with_the_fields_it_set(fake_db):
    await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, OWNER_USER, None
    )
    rows = [a for a in fake_db.audit_logs.docs if a.get("action") == "data_import_update"]
    assert len(rows) == 2
    # R2-18, 2026-08-11: the shape changed from {"import_batch": ..., "fields": {field:
    # new_value}} to the canonical {field: {"previous": ..., "new": ...}} every other
    # write path uses. The old shape recorded only the NEW values, while the comment
    # above it claimed it carried the before values so an import "can be unpicked
    # later" - it could not, and an import is the one thing done in bulk. The batch id
    # moved to its own key rather than being mixed in with the fields.
    assert all(r["changes"] for r in rows)
    assert all(r.get("import_batch") for r in rows)
    for row in rows:
        for field, change in row["changes"].items():
            assert set(change) == {"previous", "new"}, (
                f"{field} was audited without the value it held before the import"
            )
