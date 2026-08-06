from __future__ import annotations

"""Flo must never report the roll count as though the NSO list did not exist.

Owner request 10, 2026-08-06. The school has three states and two true counts:
the roll (students the school has) and the daily register (names a teacher marks),
which is the roll PLUS the NSO list. Answering "1,801 students" when three more are
marked absent every morning is not a rounding difference, it is the wrong answer to
"how many children does this school look after".
"""

from ai.prompts import _resolve_tools, build_system_prompt
from ai.tool_functions_v2 import TOOL_REGISTRY, tool_get_enrolment_summary
from tests.backend.factories import make_staff, make_student

OWNER = {"id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}


async def test_the_summary_separates_the_roll_from_the_nso_list(fake_db, monkeypatch):
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    fake_db.students.docs[:] = [
        make_student(id="s1", name="On Roll", is_active=True, status="active"),
        make_student(id="s2", name="On Roll Two", is_active=True, status="active"),
        make_student(id="s3", name="Nso One", is_active=False, status="nso"),
        make_student(id="s4", name="Gone", is_active=False, status="tc_issued"),
    ]
    fake_db.staff.docs[:] = [
        make_staff(id="t1", name="Teacher On Roll", is_active=True, status="active"),
        make_staff(id="t2", name="Teacher Nso", is_active=False, status="nso"),
    ]

    result = await tool_get_enrolment_summary({}, OWNER)

    assert result["success"] is True
    students = next(row for row in result["data"] if row["group"] == "students")
    assert students["on_roll"] == 2
    assert students["nso"] == 1
    assert students["left_with_tc"] == 1
    # The number a teacher actually marks: on the roll plus NSO, never the child who
    # has taken their TC.
    assert students["marked_on_the_daily_register"] == 3

    staff = next(row for row in result["data"] if row["group"] == "staff_and_teachers")
    assert staff["on_roll"] == 1
    assert staff["nso"] == 1


async def test_the_message_tells_flo_to_give_both_numbers(fake_db, monkeypatch):
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    fake_db.students.docs[:] = [
        make_student(id="s1", is_active=True, status="active"),
        make_student(id="s2", is_active=False, status="nso"),
    ]
    fake_db.staff.docs[:] = []

    result = await tool_get_enrolment_summary({}, OWNER)

    assert "NSO" in result["message"]
    assert "daily register" in result["message"]


async def test_a_legacy_withdrawn_record_counts_as_having_left(fake_db, monkeypatch):
    # Records switched off before any of this existed carry status "withdrawn". They
    # behaved exactly like a TC-issued record yesterday and must keep doing so, or the
    # school's existing data quietly changes meaning.
    monkeypatch.setattr("ai.tool_functions_v2.get_db", lambda: fake_db)
    fake_db.students.docs[:] = [make_student(id="s1", is_active=False, status="withdrawn")]
    fake_db.staff.docs[:] = []

    students = next(
        row for row in (await tool_get_enrolment_summary({}, OWNER))["data"]
        if row["group"] == "students"
    )

    assert students["left_with_tc"] == 1
    assert students["nso"] == 0
    assert students["marked_on_the_daily_register"] == 0


def test_the_tool_is_offered_to_the_owner_and_the_principal():
    for role, sub in (("owner", "owner"), ("admin", "principal")):
        names = {tool["name"] for tool in _resolve_tools(role, sub)}
        assert "get_enrolment_summary" in names, f"{role}/{sub} cannot ask for the honest count"


def test_the_tool_is_a_read_and_needs_no_confirmation():
    entry = TOOL_REGISTRY["get_enrolment_summary"]
    assert "dispatch_type" not in entry
    assert not entry.get("requires_confirmation")


def test_the_standing_rule_reaches_the_prompt():
    """The rule has to be in the prompt itself, not only in a tool description —
    a tool description is only read once Flo has already decided to call it."""
    prompt = build_system_prompt(
        {"role": "owner", "sub_category": "owner", "name": "Aman Litt"},
        {},
    )
    assert "NSO" in prompt
    assert "still marked" in prompt.lower() or "still appears" in prompt.lower()
    assert "get_enrolment_summary" in prompt
