"""Asking Flo for a spreadsheet must give the same file as pressing Download.

THE DEFECT THIS CLOSES, found 2026-08-12 while finishing Release 3.

Flo could already make an Excel workbook, through `draft_document`. But that tool
formats rows Flo is HOLDING: it would fetch a page of students with a read tool and
hand those rows over. Ask it for "all 1,876 children in Excel" and you would get a
sheet containing whatever it happened to have seen, with nothing on the sheet to say
so.

That is this release's defining fault in the worst place it can happen. A short screen
is an annoyance. A short file leaves the building, gets mailed to the trust, filed as a
record, and reconciled against, and nothing on its face admits it is partial.

`export_data_file` therefore reads the rows itself, through the same builder the
download button on the screen uses, so nothing passes through the model. These tests
pin the two things that makes true:

  1. the file holds EVERY row, past the point where a conversation would have stopped;
  2. Flo's gate is the permission table's gate, not a second copy of it - a download
     is not a way around who may see what.
"""

from __future__ import annotations

import pytest

from ai import tool_functions_v2
from middleware.auth import create_jwt

OWNER = {"id": "own-1", "role": "owner", "name": "Owner"}
PRINCIPAL = {"id": "pri-1", "role": "admin", "sub_category": "principal", "name": "Principal"}
ACCOUNTANT = {"id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "Accountant"}
MANAGEMENT = {"id": "mgt-1", "role": "admin", "sub_category": "management", "name": "Management"}


@pytest.fixture(autouse=True)
def _s3_configured(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "eduflow-test-bucket")


@pytest.fixture(autouse=True)
def _fake_s3(monkeypatch):
    """S3 is not reachable from a test run, so storage is faked at that boundary only.
    Everything either side of it - the reading, the gate, the row count - is real."""
    from services import document_export

    class _Stored:
        bucket = "test-bucket"
        key = "aaryans-joya/uploads/x/x.xlsx"
        etag = "etag"
        sha256 = "sha"

    monkeypatch.setattr(document_export, "upload_bytes", lambda **kw: _Stored())


@pytest.fixture(autouse=True)
def _roll(fake_db):
    """A roll bigger than any page a conversation would have carried."""
    saved = list(fake_db.students.docs)
    fake_db.students.docs[:] = [
        {"id": f"s-{i}", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": f"Child {i}", "admission_number": f"ADM{i}", "is_active": True}
        for i in range(1200)
    ]
    yield
    fake_db.students.docs[:] = saved


async def _run(params, user):
    return await tool_functions_v2.tool_export_data_file(params, user)


# ── The file holds everything ────────────────────────────────────────────────

async def test_the_file_holds_every_row_not_the_ones_flo_happened_to_see():
    result = await _run({"dataset": "students", "format": "xlsx"}, OWNER)

    assert result["success"] is True
    # 1,200 children, not one page of them. This is the whole point of the tool.
    assert result["data"]["row_count"] == 1200
    assert result["meta"]["count"] == 1200


async def test_it_says_how_many_rows_are_in_the_file():
    """The count is what lets somebody notice a wrong file. "Here is your file" does
    not, and a person cannot count 1,200 rows by eye to check."""
    result = await _run({"dataset": "students"}, OWNER)
    assert "1,200 rows" in result["message"]


async def test_excel_is_the_default_because_the_office_works_in_excel():
    result = await _run({"dataset": "students"}, OWNER)
    assert result["data"]["file_name"].endswith(".xlsx")


@pytest.mark.parametrize("asked", ["excel", "Excel", "spreadsheet", "sheet", "xls"])
async def test_the_words_a_person_actually_uses_all_mean_excel(asked):
    """Nobody asks for "xlsx". They ask for it in Excel, or as a spreadsheet."""
    result = await _run({"dataset": "students", "format": asked}, OWNER)
    assert result["data"]["file_name"].endswith(".xlsx")


async def test_csv_when_asked_for():
    result = await _run({"dataset": "students", "format": "csv"}, OWNER)
    assert result["data"]["file_name"].endswith(".csv")


# ── The Excel path does not trim ─────────────────────────────────────────────

async def test_the_workbook_is_not_trimmed_at_the_document_builders_own_limit(monkeypatch):
    """The shared document builder trims a table at 5,000 rows and adds a note near
    the bottom of the sheet. That is the right trade for a document somebody reads and
    the wrong one for an export, so the export's own ceiling - which REFUSES rather
    than trims - is what applies. Dropped to 5 here so the wiring is under test rather
    than openpyxl's speed."""
    monkeypatch.setattr("services.document_builder.MAX_ROWS", 5)

    result = await _run({"dataset": "students"}, OWNER)

    assert result["success"] is True
    assert result["data"]["row_count"] == 1200
    assert result["data"]["truncated"] is False
    assert "only the first" not in result["message"]


# ── The gate is the permission table's, not a second copy ────────────────────

async def test_management_is_refused_the_money_and_told_why():
    """The wall Abhimanyu asked for by name. Flo must not be the way round it."""
    result = await _run({"dataset": "fee-transactions"}, MANAGEMENT)

    assert result["success"] is False
    # `denied`, so the reply reads as a permission answer rather than a fault.
    assert result["denied"] is True
    assert "permission" in result["message"].lower()


async def test_management_may_still_download_the_children_and_the_staff():
    for dataset in ("students", "staff"):
        result = await _run({"dataset": dataset}, MANAGEMENT)
        assert result["success"] is True, dataset


async def test_the_accountant_may_download_the_ledger_and_the_roll():
    for dataset in ("fee-transactions", "students"):
        result = await _run({"dataset": dataset}, ACCOUNTANT)
        assert result["success"] is True, dataset


async def test_the_principal_may_download_the_money():
    result = await _run({"dataset": "expenses"}, PRINCIPAL)
    assert result["success"] is True


async def test_an_unknown_data_set_lists_what_there_is_instead_of_failing_blankly():
    result = await _run({"dataset": "salaries"}, OWNER)
    assert result["success"] is False
    assert result["denied"] is False
    assert "students" in result["message"]


async def test_asking_with_no_data_set_asks_which_one():
    result = await _run({}, OWNER)
    assert result["success"] is False
    assert "students" in result["message"]


# ── Flo and the screen produce the same rows ─────────────────────────────────

async def test_flo_and_the_download_button_read_the_same_rows(client, fake_db):
    """The parity that matters: one definition of what "the student list" is.

    Both go through `build_students`. If somebody ever gives Flo its own query, this
    is the test that should stop them.
    """
    headers = {"Authorization": "Bearer " + create_jwt(
        {"user_id": "own-1", "role": "owner", "name": "Owner", "schoolId": "aaryans-joya"},
    )}
    from_screen = client.get("/api/export/students", headers=headers)
    assert from_screen.status_code == 200
    screen_rows = [ln for ln in from_screen.content.decode().splitlines() if ln.strip()]

    from_flo = await _run({"dataset": "students", "format": "csv"}, OWNER)

    # The screen's file carries a heading row; the tool reports data rows only.
    assert from_flo["data"]["row_count"] == len(screen_rows) - 1
