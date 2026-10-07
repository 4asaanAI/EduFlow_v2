from __future__ import annotations
"""`export_data_file` for dataset "students" with a `class_name` filter.

THE DEFECT THIS CLOSES. Asked for "all students of class 1A in excel", the AI
reported the class was empty. `build_students` never looked at a class filter at
all - it always dumped the whole active roster - so the model, finding no class
column to check "1A" against, told the user nobody was there.

Class records store grade and section in separate fields (`name="1"`,
`section="A"`); every screen DISPLAYS them joined ("1A", "1-A", "1 A"). This is
the same class-label trap documented in `ai/class_resolver.py` and
`backend/services/announcement_audience.py` - a label match must go through the
shared resolver, never a fresh regex on `name` alone.
"""

from fastapi import HTTPException
import pytest

from ai import tool_functions_v2
from routes.exports import build_students

OWNER = {"id": "own-1", "role": "owner", "name": "Owner", "branch_id": "branch-a"}


@pytest.fixture(autouse=True)
def _class_1a_and_4c(fake_db):
    """Two classes, two students, so a filter has something to prove it excludes."""
    saved_students = list(fake_db.students.docs)
    saved_classes = list(fake_db.classes.docs)
    fake_db.classes.docs[:] = [
        {"id": "cls-1a", "schoolId": "aaryans-joya", "branch_id": "branch-a", "name": "1", "section": "A"},
        {"id": "cls-4c", "schoolId": "aaryans-joya", "branch_id": "branch-a", "name": "4", "section": "C"},
    ]
    fake_db.students.docs[:] = [
        {"id": "s-1a", "schoolId": "aaryans-joya", "branch_id": "branch-a", "name": "Asha",
         "class_id": "cls-1a", "is_active": True, "admission_number": "ADM1"},
        {"id": "s-4c", "schoolId": "aaryans-joya", "branch_id": "branch-a", "name": "Ravi",
         "class_id": "cls-4c", "is_active": True, "admission_number": "ADM2"},
    ]
    yield
    fake_db.students.docs[:] = saved_students
    fake_db.classes.docs[:] = saved_classes


@pytest.mark.parametrize("label", ["1A", "1-A", "1 A", "Class 1-A", "class 1 a"])
async def test_every_way_of_typing_the_label_resolves_to_the_same_class(fake_db, label):
    headers, rows, title = await build_students(fake_db, OWNER, {"class_name": label})
    names = [row[0] for row in rows]
    assert names == ["Asha"]


async def test_the_other_class_is_excluded_not_just_the_one_included(fake_db):
    headers, rows, title = await build_students(fake_db, OWNER, {"class_name": "1A"})
    names = [row[0] for row in rows]
    assert "Ravi" not in names


async def test_class_column_is_on_the_sheet(fake_db):
    headers, rows, title = await build_students(fake_db, OWNER, {"class_name": "1A"})
    assert "Class" in headers
    class_col = headers.index("Class")
    assert rows[0][class_col] == "1 A"


async def test_unmatched_label_refuses_rather_than_answering_about_the_whole_school(fake_db):
    """A miss must say so. It must NOT silently drop the filter and return everyone -
    that silent fallback is the exact fault `class_resolver.py` was written to end."""
    with pytest.raises(HTTPException) as exc_info:
        await build_students(fake_db, OWNER, {"class_name": "9Z"})
    assert exc_info.value.status_code == 404
    assert "9" not in exc_info.value.detail or "could not find" in exc_info.value.detail.lower()


async def test_no_filter_still_returns_everyone(fake_db):
    headers, rows, title = await build_students(fake_db, OWNER, {})
    names = {row[0] for row in rows}
    assert names == {"Asha", "Ravi"}


# ── Through the AI tool layer, exactly as Flo calls it ───────────────────────

@pytest.fixture(autouse=True)
def _s3_configured(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "eduflow-test-bucket")


@pytest.fixture(autouse=True)
def _fake_s3(monkeypatch):
    from services import document_export

    class _Stored:
        bucket = "test-bucket"
        key = "aaryans-joya/uploads/x/x.xlsx"
        etag = "etag"
        sha256 = "sha"

    monkeypatch.setattr(document_export, "upload_bytes", lambda **kw: _Stored())


async def test_flo_asking_for_class_1a_in_excel_gets_only_that_class(fake_db):
    """The exact ask that was broken: "all students of class 1A in excel"."""
    result = await tool_functions_v2.tool_export_data_file(
        {"dataset": "students", "class_name": "1A", "format": "excel"}, OWNER,
    )
    assert result["success"] is True
    assert result["data"]["row_count"] == 1
    assert result["data"]["file_name"].endswith(".xlsx")


async def test_flo_asking_for_a_class_that_does_not_exist_is_told_so_not_given_an_empty_file(fake_db):
    result = await tool_functions_v2.tool_export_data_file(
        {"dataset": "students", "class_name": "9Z"}, OWNER,
    )
    assert result["success"] is False
    assert "could not find" in result["message"].lower()
