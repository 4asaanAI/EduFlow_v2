"""R4-6 - a tool a profile may not use does not appear in that profile's directory.

Decision 9, 2026-08-12.

Two rules govern this part, and neither may be relaxed for a layout change:

  **Nothing offered that will be refused.** A button that answers "no" is worse than an
  absent one: it is discovered in front of a parent, and it teaches people the platform
  is unreliable rather than that they lack permission.

  **Nothing dropped.** A screen a profile DOES hold must never vanish because a list
  moved. To the person looking, a missing screen is identical to access being withdrawn.
  That rule is what saved Staff Tracker after Release 3, and it stands.

The load-bearing test here is `test_no_role_gained_or_lost_a_screen`. Bringing teachers,
students and guardians into the permission table is only safe if it changes where the
answer comes from and not what the answer is.
"""

from __future__ import annotations

import pytest

from services.profile_matrix import (
    ALL_SCREENS,
    DORMANT_PROFILES,
    PROFILE_MATRIX,
    granted_domains,
    may_open_screen,
    may_write,
    profile_of,
)

#: The menus exactly as they stood in `Sidebar.js` before R4-6, recorded here so the
#: comparison is against what the school actually had rather than against the new table
#: describing itself.
MENUS_BEFORE_R4_6 = {
    "teacher": [
        "class-attendance-marker", "assignment-generator", "question-paper-creator",
        "quiz-manager", "report-card-builder", "student-performance-viewer",
        "leave-application", "my-payslips", "lesson-plan-generator", "worksheet-creator",
        "class-performance-analytics", "substitution-viewer", "ptm-notes",
        "curriculum-tracker", "exam-manager", "form-submissions", "resource-calendar",
        "library-circulation", "raise-maintenance",
    ],
    "student": [
        "ai-tutor", "doubt-solver", "homework-viewer", "attendance-self-check",
        "result-viewer", "practice-test", "study-planner", "career-guidance",
        "fee-status-viewer", "student-leave-request", "library-circulation",
        "ptm-summary-viewer", "form-submissions", "raise-maintenance",
    ],
    "parent": ["guardian-portal"],
}


def _user(role):
    return {"role": role, "id": "u1"}


# ---------------------------------------------------------------------------
# Nothing dropped, nothing gained
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", sorted(MENUS_BEFORE_R4_6))
def test_no_role_gained_or_lost_a_screen(role):
    """The whole point: the ANSWER is unchanged, only where it comes from."""
    before = set(MENUS_BEFORE_R4_6[role])
    now = set(PROFILE_MATRIX[role]["screens"])
    assert now == before, (
        f"{role}: gained {sorted(now - before)}, lost {sorted(before - now)}. "
        "A menu change may never widen or narrow what somebody holds."
    )


@pytest.mark.parametrize("role", sorted(MENUS_BEFORE_R4_6))
def test_every_screen_the_role_had_is_still_offered(role):
    for screen in MENUS_BEFORE_R4_6[role]:
        assert may_open_screen(_user(role), screen) is True, f"{role} lost {screen}"


# ---------------------------------------------------------------------------
# Nothing offered that will be refused
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", sorted(MENUS_BEFORE_R4_6))
def test_a_role_is_refused_a_screen_it_does_not_hold(role):
    """Default deny, which is what these three roles never had before."""
    assert may_open_screen(_user(role), "financial-reports") is False
    assert may_open_screen(_user(role), "accounting-periods") is False
    assert may_open_screen(_user(role), "audit-log") is False


def test_a_teacher_is_not_offered_a_students_own_screens_and_the_reverse():
    assert may_open_screen(_user("teacher"), "fee-status-viewer") is False
    assert may_open_screen(_user("student"), "report-card-builder") is False


def test_an_unknown_role_is_refused_everything():
    assert profile_of({"role": "caretaker"}) == ""
    assert may_open_screen({"role": "caretaker"}, "raise-maintenance") is False


# ---------------------------------------------------------------------------
# Recognising these roles must not widen anything except the menu
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", sorted(MENUS_BEFORE_R4_6))
def test_the_three_roles_hold_no_flo_domains(role):
    """Those domains describe the office's Flo tools. A menu change must not grant one."""
    assert granted_domains(_user(role)) == frozenset()


@pytest.mark.parametrize("role", sorted(MENUS_BEFORE_R4_6))
def test_the_three_roles_may_not_write_through_the_matrix(role):
    """Exactly what the old "no profile" answer produced. Unchanged."""
    assert may_write(_user(role)) is False


@pytest.mark.parametrize("role", sorted(MENUS_BEFORE_R4_6))
def test_the_three_roles_are_dormant(role):
    """Defining is not switching on. Releases 5, 6 and 7 decide that, not this one."""
    assert role in DORMANT_PROFILES


def test_recognising_them_did_not_disturb_the_office_desks():
    """The eight desks were already default-deny. R4-6 must leave them exactly as they were."""
    assert may_open_screen({"role": "owner"}, "financial-reports") is True
    assert may_open_screen({"role": "admin", "sub_category": "management"},
                           "financial-reports") is False
    assert may_open_screen({"role": "admin", "sub_category": "accountant"},
                           "fee-collection") is True


def test_a_teacher_can_still_download_attendance_and_results():
    """R4-6 regression, caught by test_r13_tenancy_rbac and pinned here.

    Teachers were outside the permission table, so the export gate fell through to an
    explicit list of roles. Adding them to the table gave them a profile - a DORMANT
    one, since their logins are not switched on yet - and the dormant-profile refusal
    then caught the two exports teachers have always had. A menu change had quietly
    taken away a working feature, which is precisely the failure this release exists to
    end. The explicit grant is asked FIRST now.
    """
    from routes.exports import may_export

    teacher = {"role": "teacher", "id": "t1"}
    assert may_export(teacher, "attendance") is True
    assert may_export(teacher, "exam-results") is True
    # And it did not widen: a teacher still cannot download the whole roll or the money.
    assert may_export(teacher, "students") is False
    assert may_export(teacher, "fee-transactions") is False


def test_a_dormant_office_profile_still_cannot_export():
    """The dormant rule must survive the fix above, not be traded away for it."""
    from routes.exports import may_export

    receptionist = {"role": "admin", "sub_category": "receptionist", "id": "r1"}
    assert may_export(receptionist, "students") is False


# R3-3, 2026-08-15. The one profile in the table that holds NO screen, on purpose.
#
# Drivers and conductors get a profile of their own (Abhimanyu's answer 10 of 2026-08-11)
# and get NO LOGIN (the same answer, unchanged on 2026-08-15). It exists so the transport
# head can record his own team truthfully on the staff roll, and so that if the school
# ever asks for them to sign in it is one decision rather than another round of them.
#
# A profile with no screens AND a login would be a broken menu, which is what the rule
# below is really guarding. A profile with no screens and no login is a category on the
# staff roll, and giving it screens to satisfy a test would state something false: that
# somebody is expected to open them.
#
# Named here rather than allowed by a general rule, so that the NEXT empty profile is a
# deliberate edit to this list and somebody has to write down why.
PROFILES_WITH_NO_SCREENS_BECAUSE_THEY_HAVE_NO_LOGIN = {"transport_staff"}


def test_every_profile_in_the_table_states_a_reason_for_itself():
    for name, entry in PROFILE_MATRIX.items():
        assert entry.get("notes"), f"{name} has no note explaining what it is"
        if name in PROFILES_WITH_NO_SCREENS_BECAUSE_THEY_HAVE_NO_LOGIN:
            assert not entry["screens"], (
                f"{name} is listed as holding no screens because it holds no login, and "
                "it now has screens. Either it was given a login, in which case take it "
                "off that list, or somebody granted a screen nobody can open."
            )
            assert "NO logins" in entry["notes"] or "no login" in entry["notes"].lower(), (
                f"{name} holds no screens, so its note has to say that it holds no login "
                "either. Otherwise it reads as a profile somebody forgot to finish."
            )
            continue
        assert entry["screens"] == ALL_SCREENS or entry["screens"], f"{name} has no screens"
