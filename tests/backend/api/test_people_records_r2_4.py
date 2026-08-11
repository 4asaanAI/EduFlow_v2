from __future__ import annotations

"""R2-4 - who may add, edit, remove and let people in.

Decision 4, 2026-08-10: the management head may add and edit students and staff. He
may NOT take them off the roll, and he may not create or reset any login.
Decision 5: the accountant head may create students too.

Before this, `DELETE /api/students/{id}` and `DELETE /api/staff/{id}` asked only
whether the caller's role was owner or admin - which is every admin desk in the
school - and the Flo tools `create_student_login` and `set_profile_password` reached
the management head because the classification loop at the bottom of
`ai/tool_functions_v2.py` ends in `else: non_finance`. Anything nobody classified
became his by default.

The delete guard lives in the SERVICE, not on the route, so the screen and Flo inherit
one answer. A check on the route alone would have left the chat door open, which is
precisely the drift the shared-service pattern exists to prevent - so there is a test
below for each door.
"""

import pytest

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
PRINCIPAL = {"user_id": "prn-1", "role": "admin", "sub_category": "principal", "name": "Adesh Singh"}
ACCOUNTANT = {"user_id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "Sonu Ruhal"}
MANAGEMENT = {"user_id": "mgt-1", "role": "admin", "sub_category": "management", "name": "Lalit Thomas"}


# `fake_db` is shared across the whole session, so a fixture that replaces a
# collection has to put it back. Leaving "A Child" in the students list broke an
# unrelated attendance-export test three files away, which is a slow and confusing
# thing to debug.
@pytest.fixture
def one_student(fake_db):
    original = list(fake_db.students.docs)
    fake_db.students.docs[:] = [{
        "id": "student-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "name": "A Child", "admission_number": "A001", "is_active": True,
        "status": "active", "class_id": "class-1",
    }]
    yield fake_db
    fake_db.students.docs[:] = original


@pytest.fixture
def one_staff(fake_db):
    original = list(fake_db.staff.docs)
    fake_db.staff.docs[:] = [{
        "id": "staff-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "name": "A Colleague", "is_active": True, "status": "active",
    }]
    yield fake_db
    fake_db.staff.docs[:] = original


# ─── Taking someone off the roll ───────────────────────────────────────────────

def test_the_management_head_cannot_take_a_student_off_the_roll(client, one_student):
    resp = client.delete("/api/students/student-1", headers=_bearer(MANAGEMENT))
    assert resp.status_code == 403, resp.text
    # And the child is still on the roll afterwards, which is the thing that matters.
    assert one_student.students.docs[0]["is_active"] is True


def test_the_management_head_cannot_take_a_colleague_off_the_roll(client, one_staff):
    resp = client.delete("/api/staff/staff-1", headers=_bearer(MANAGEMENT))
    assert resp.status_code == 403, resp.text
    assert one_staff.staff.docs[0]["is_active"] is True


def test_the_accountant_head_cannot_either(client, one_student):
    """Not in decision 4 by name, but the matrix is default deny.

    Sonu may CREATE students (decision 5). Removing one is not the same act, nobody
    asked for it, and the safe answer to a question the school has not been asked is
    no. Raise it with them if it turns out he needs it.
    """
    assert client.delete("/api/students/student-1", headers=_bearer(ACCOUNTANT)).status_code == 403


def test_the_owner_and_the_principal_still_can(client, one_student, one_staff):
    for who in (OWNER, PRINCIPAL):
        one_student.students.docs[0]["is_active"] = True
        resp = client.delete("/api/students/student-1", headers=_bearer(who))
        assert resp.status_code == 200, f"{who['name']}: {resp.text}"


async def test_the_same_answer_comes_back_through_flo(one_student):
    """The guard is in the service, so the chat door gives the identical answer.

    If this ever passes while the route test above fails, or the other way round, the
    two doors have drifted and one of them is wrong.
    """
    from services.actor_context import ActorContext
    from services.student_service import StudentAuthorizationError, delete_student

    actor = ActorContext(
        user_id="mgt-1", role="admin", sub_category="management",
        school_id="aaryans-joya", branch_id="branch-joya", actor_name="Lalit Thomas",
    )
    with pytest.raises(StudentAuthorizationError):
        await delete_student(one_student, actor, {"student_id": "student-1"})

    assert one_student.students.docs[0]["is_active"] is True


# ─── Letting people in ─────────────────────────────────────────────────────────

def test_the_management_head_cannot_create_a_login_or_reset_a_password():
    """Handing out a way into the platform is the school leadership's to do.

    Guarded by naming both tools leadership-only. They were reachable purely because
    the classification loop's last branch is `else: non_finance`.
    """
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    management = {"role": "admin", "sub_category": "management"}
    for tool_name in ("create_student_login", "set_profile_password"):
        assert is_tool_authorized(management, TOOL_REGISTRY[tool_name]) is False, tool_name


def test_the_owner_and_principal_keep_the_login_tools():
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    for who in ({"role": "owner"}, {"role": "admin", "sub_category": "principal"}):
        for tool_name in ("create_student_login", "set_profile_password"):
            assert is_tool_authorized(who, TOOL_REGISTRY[tool_name]) is True, (who, tool_name)


def test_no_profile_below_leadership_holds_a_login_tool():
    """Including the five dormant ones, which must never acquire one by default."""
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    for sub_category in (
        "accountant", "management", "transport_head", "receptionist",
        "it_tech", "maintenance", "support_staff",
    ):
        user = {"role": "admin", "sub_category": sub_category}
        for tool_name in ("create_student_login", "set_profile_password"):
            assert is_tool_authorized(user, TOOL_REGISTRY[tool_name]) is False, (
                f"{sub_category} can reach {tool_name}"
            )


# ─── What he KEEPS. Narrowing his job is as much a defect as widening it. ──────

def test_the_management_head_can_still_add_and_edit_a_student(client, one_student):
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    management = {"role": "admin", "sub_category": "management"}
    for tool_name in ("create_student", "update_student"):
        assert is_tool_authorized(management, TOOL_REGISTRY[tool_name]) is True, tool_name

    resp = client.patch(
        "/api/students/student-1",
        json={"phone": "9000000001"},
        headers=_bearer(MANAGEMENT),
    )
    assert resp.status_code == 200, resp.text


def test_the_management_head_can_still_add_and_edit_a_colleague():
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    management = {"role": "admin", "sub_category": "management"}
    for tool_name in ("create_staff", "update_staff"):
        assert is_tool_authorized(management, TOOL_REGISTRY[tool_name]) is True, tool_name


def test_the_accountant_head_may_create_students(client):
    """Decision 5, 2026-08-10."""
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    accountant = {"role": "admin", "sub_category": "accountant"}
    assert is_tool_authorized(accountant, TOOL_REGISTRY["create_student"]) is True
