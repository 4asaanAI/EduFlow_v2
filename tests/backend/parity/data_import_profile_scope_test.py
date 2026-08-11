"""Spreadsheet import for the accountant and management profiles - segment-scoped.

Owner and principal import the whole student record. On 2026-08-08 import was widened
to the other two reviewed authority profiles, but NOT to the whole record: the
accountant imports bank and contact columns, management imports the non-finance ones,
and anything outside a profile's segment is REPORTED rather than written.

The reporting matters as much as the blocking. A column that is silently dropped looks
identical, to the person who uploaded the file, to a column that was imported.
"""

from __future__ import annotations

import copy
import io

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2
from ai.tool_access import is_tool_authorized

ACCOUNTANT_USER = {"id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "Accountant"}
MANAGEMENT_USER = {"id": "mgt-1", "role": "admin", "sub_category": "management", "name": "Management"}
TEACHER_USER = {"id": "tch-1", "role": "teacher", "sub_category": "class_teacher", "name": "Teacher"}


def _headers(user_id: str, role: str, sub_category: str = ""):
    claims = {"user_id": user_id, "role": role, "name": "T", "schoolId": "aaryans-joya"}
    if sub_category:
        claims["sub_category"] = sub_category
    return {"Authorization": "Bearer " + create_jwt(claims)}


def _sheet(rows: list) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# One finance column (BankName), one clearly non-finance column (FatherName), and one
# contact column (Whatsapp) that both profiles are allowed to fill.
HEADER = ["AdmissionNo", "Whatsapp", "BankName", "FatherName"]
ROWS = [
    HEADER,
    ["ADM-1", "9000000011", "State Bank", "Rakesh"],
    ["ADM-2", "9000000022", "Canara Bank", "Suresh"],
]


def _students():
    return [
        {"id": "s1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "admission_number": "ADM-1", "name": "Aryan"},
        {"id": "s2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "admission_number": "ADM-2", "name": "Priya"},
    ]


@pytest.fixture(autouse=True)
def _seed(fake_db, monkeypatch):
    saved = {c: list(getattr(fake_db, c).docs) for c in ("students", "audit_logs")}
    fake_db.students.docs[:] = _students()
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


def _by_admission(fake_db, admission):
    return next(s for s in fake_db.students.docs if s["admission_number"] == admission)


# ─── The segments themselves ─────────────────────────────────────────────────

async def test_accountant_imports_bank_and_contact_but_not_family_details(fake_db):
    result = await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, ACCOUNTANT_USER, None
    )
    assert result["success"] is True
    aryan = _by_admission(fake_db, "ADM-1")
    assert aryan["bank_name"] == "State Bank"
    # `whatsapp`, not `whatsapp_phone` - the name the student records actually use.
    assert aryan["whatsapp"] == "9000000011"
    assert "father_name" not in aryan, "the accountant wrote a non-finance column"


async def test_management_imports_family_and_contact_but_not_bank_details(fake_db):
    result = await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, MANAGEMENT_USER, None
    )
    assert result["success"] is True
    aryan = _by_admission(fake_db, "ADM-1")
    assert aryan["father_name"] == "Rakesh"
    assert aryan["whatsapp"] == "9000000011"
    assert "bank_name" not in aryan, "management wrote a finance column"


async def test_owner_still_imports_the_whole_record(fake_db):
    await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, {"id": "own-1", "role": "owner", "name": "Owner"}, None
    )
    aryan = _by_admission(fake_db, "ADM-1")
    assert aryan["bank_name"] == "State Bank"
    assert aryan["father_name"] == "Rakesh"


# ─── Skipped columns are reported, never silently dropped ────────────────────

async def test_out_of_segment_columns_are_named_back_to_the_person(fake_db):
    result = await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, ACCOUNTANT_USER, None
    )
    outside = result["data"]["columns_outside_your_access"]
    assert "father_name" in outside
    assert "bank_name" not in outside
    assert "father_name" in result["data"]["message"]


async def test_preview_reports_the_same_segment_as_apply(fake_db):
    preview = await tool_functions_v2.TOOL_REGISTRY["preview_data_import"]["fn"](
        {"file_id": "f1"}, MANAGEMENT_USER, None
    )
    plan = preview["data"][0]
    assert "bank_name" in plan["columns_outside_your_access"]
    assert "bank_name" not in plan["by_field"]
    # The person must be told before they confirm, not after the import has run.
    assert "bank_name" in preview["message"]


async def test_import_of_only_out_of_segment_columns_does_not_claim_nothing_to_change(fake_db):
    """The honest-failure case: an accountant handed a purely academic sheet must be
    told the columns were outside their access, not that the data was already on file."""
    from services import data_import_service as imp

    payload = _sheet([["AdmissionNo", "FatherName"], ["ADM-1", "Rakesh"]])

    async def _only_family(db, ctx, file_id):
        return payload, {"id": "f1", "filename": "family.xlsx"}

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as mp:
        mp.setattr(imp, "_load_file", _only_family)
        result = await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
            {"file_id": "f1"}, ACCOUNTANT_USER, None
        )
    message = result["data"]["message"]
    assert "outside your access" in message
    assert "already has this information" not in message


# ─── Access boundaries ───────────────────────────────────────────────────────

@pytest.mark.parametrize("user", [ACCOUNTANT_USER, MANAGEMENT_USER])
def test_both_widened_profiles_are_authorized_for_both_import_tools(user):
    for name in ("preview_data_import", "import_data_file"):
        assert is_tool_authorized(user, tool_functions_v2.TOOL_REGISTRY[name]) is True


@pytest.mark.parametrize("sub_category", ["receptionist", "transport_head", "maintenance", "it_tech"])
def test_other_admin_profiles_are_still_refused(sub_category):
    user = {"id": "x", "role": "admin", "sub_category": sub_category}
    assert is_tool_authorized(user, tool_functions_v2.TOOL_REGISTRY["import_data_file"]) is False


def test_teachers_are_still_refused():
    assert is_tool_authorized(TEACHER_USER, tool_functions_v2.TOOL_REGISTRY["import_data_file"]) is False


def test_import_is_a_bulk_write_and_stops_for_confirmation():
    """It rewrites fields on up to every student on the roll in one call. It was
    missing from BULK_TOOL_NAMES, so the confirm card its own description promises
    never appeared."""
    tool = tool_functions_v2.TOOL_REGISTRY["import_data_file"]
    assert tool["requires_confirmation"] is True
    assert tool.get("bulk") is True


# ─── REST twin agrees with Flo ───────────────────────────────────────────────

def test_rest_import_unauthenticated_returns_401(client):
    resp = client.post("/api/data-import/apply", json={"file_id": "f1"})
    assert resp.status_code == 401


def test_rest_import_wrong_role_returns_403(client):
    resp = client.post("/api/data-import/apply", json={"file_id": "f1"},
                       headers=_headers("t1", "teacher"))
    assert resp.status_code == 403


@pytest.mark.parametrize("sub_category", ["accountant", "management"])
def test_rest_import_allows_the_widened_profiles(client, sub_category):
    resp = client.post("/api/data-import/apply", json={"file_id": "f1"},
                       headers=_headers("u1", "admin", sub_category))
    assert resp.status_code == 200, resp.text


def test_rest_import_still_refuses_receptionist(client):
    resp = client.post("/api/data-import/apply", json={"file_id": "f1"},
                       headers=_headers("u1", "admin", "receptionist"))
    assert resp.status_code == 403


async def test_rest_and_flo_write_the_same_fields_for_the_accountant(client, fake_db):
    client.post("/api/data-import/apply", json={"file_id": "f1"},
                headers=_headers("acc-1", "admin", "accountant"))
    rest_state = copy.deepcopy(fake_db.students.docs)

    fake_db.students.docs[:] = _students()
    await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, ACCOUNTANT_USER, None
    )

    def _mask(docs):
        return sorted(
            [{k: v for k, v in d.items() if k not in {"updated_at", "updated_by"}} for d in docs],
            key=lambda d: d["admission_number"],
        )

    assert _mask(fake_db.students.docs) == _mask(rest_state)


# ─── The screen upload reaches the same service as the chat attachment ───────
# The Data Import panel uploads a file directly. If that grew its own rules, the
# segment scoping would apply in chat and not on the screen.

def _upload(client, headers, endpoint="upload-apply", overwrite=False):
    return client.post(
        f"/api/data-import/{endpoint}",
        files={"file": ("students.xlsx", _sheet(ROWS),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"overwrite": "true" if overwrite else "false"},
        headers=headers,
    )


def test_upload_import_unauthenticated_returns_401(client):
    resp = client.post("/api/data-import/upload-apply",
                       files={"file": ("s.xlsx", b"x", "application/octet-stream")})
    assert resp.status_code == 401


def test_upload_import_wrong_role_returns_403(client):
    resp = _upload(client, _headers("t1", "teacher"))
    assert resp.status_code == 403


def test_upload_preview_writes_nothing(client, fake_db):
    before = copy.deepcopy(fake_db.students.docs)
    resp = _upload(client, _headers("own-1", "owner"), endpoint="upload-preview")
    assert resp.status_code == 200, resp.text
    assert fake_db.students.docs == before


def test_uploaded_file_obeys_the_accountant_segment(client, fake_db):
    resp = _upload(client, _headers("acc-1", "admin", "accountant"))
    assert resp.status_code == 200, resp.text
    aryan = _by_admission(fake_db, "ADM-1")
    assert aryan["bank_name"] == "State Bank"
    assert "father_name" not in aryan
    assert "father_name" in resp.json()["data"]["columns_outside_your_access"]


def test_uploaded_file_obeys_the_management_segment(client, fake_db):
    resp = _upload(client, _headers("mgt-1", "admin", "management"))
    assert resp.status_code == 200, resp.text
    aryan = _by_admission(fake_db, "ADM-1")
    assert aryan["father_name"] == "Rakesh"
    assert "bank_name" not in aryan


async def test_screen_upload_and_chat_attachment_write_the_same_fields(client, fake_db):
    _upload(client, _headers("acc-1", "admin", "accountant"))
    screen_state = copy.deepcopy(fake_db.students.docs)

    fake_db.students.docs[:] = _students()
    await tool_functions_v2.TOOL_REGISTRY["import_data_file"]["fn"](
        {"file_id": "f1"}, ACCOUNTANT_USER, None
    )

    def _mask(docs):
        return sorted(
            [{k: v for k, v in d.items() if k not in {"updated_at", "updated_by"}} for d in docs],
            key=lambda d: d["admission_number"],
        )

    assert _mask(fake_db.students.docs) == _mask(screen_state)


def test_empty_upload_is_refused_clearly(client):
    resp = client.post("/api/data-import/upload-apply",
                       files={"file": ("s.xlsx", b"", "application/octet-stream")},
                       headers=_headers("own-1", "owner"))
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()
