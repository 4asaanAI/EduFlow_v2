"""R2-8 - what Flo tells a person about their job has to be true.

Flo's brief per profile is prose, so nothing checks it. That is how, by 2026-08-11,
every one of the five dormant profiles' briefs was wrong in BOTH directions at once:

  * Denying what the profile has. All five can read the school directory, attendance,
    the staff list and the day's brief, and every brief said a version of "you CANNOT
    see student data". Flo would have refused work the platform allows, which is the
    same defect that once had Flo telling the school's OWNER an operation was not
    available to it.
  * Promising what the profile does not have. IT support was told it could reset
    passwords and read system health; it has neither tool. Maintenance was told it
    could update tickets, manage the schedule and edit vendors; it has one read tool.
    A promise Flo cannot keep is a dead button, spoken aloud.

Prose cannot be checked line by line. What CAN be checked is the handful of claims that
turn into a person being sent to the wrong desk, and that is what this file pins.
"""

from __future__ import annotations

import pytest

from ai.prompts import ROLE_RULES
from ai.tool_access import is_tool_authorized
from ai.tool_functions_v2 import TOOL_REGISTRY
from services.profile_matrix import PROFILE_MATRIX

PROFILE_KEYS = {
    "owner": ("owner", None),
    "principal": ("admin", "principal"),
    "accountant": ("admin", "accountant"),
    "management": ("admin", "management"),
    "transport_head": ("admin", "transport_head"),
    "receptionist": ("admin", "receptionist"),
    "it_tech": ("admin", "it_tech"),
    "maintenance": ("admin", "maintenance"),
    "support_staff": ("support_staff", None),
}

USERS = {
    "owner": {"role": "owner", "sub_category": "owner", "id": "u"},
    "principal": {"role": "admin", "sub_category": "principal", "id": "u"},
    "accountant": {"role": "admin", "sub_category": "accountant", "id": "u"},
    "management": {"role": "admin", "sub_category": "management", "id": "u"},
    "transport_head": {"role": "admin", "sub_category": "transport_head", "id": "u"},
    "receptionist": {"role": "admin", "sub_category": "receptionist", "id": "u"},
    "it_tech": {"role": "admin", "sub_category": "it_tech", "id": "u"},
    "maintenance": {"role": "admin", "sub_category": "maintenance", "id": "u"},
    "support_staff": {"role": "admin", "sub_category": "support_staff", "id": "u"},
}

DORMANT = ("transport_head", "receptionist", "it_tech", "maintenance", "support_staff")


def _brief(profile: str) -> str:
    return ROLE_RULES.get(PROFILE_KEYS[profile], "")


def _tools(profile: str) -> set:
    user = USERS[profile]
    return {name for name, tool in TOOL_REGISTRY.items() if is_tool_authorized(user, tool)}


@pytest.mark.parametrize("profile", sorted(PROFILE_KEYS))
def test_every_profile_has_a_brief(profile):
    assert _brief(profile).strip(), f"{profile} has no brief, so Flo improvises"


@pytest.mark.parametrize("profile", DORMANT)
def test_a_dormant_brief_never_claims_a_write(profile):
    # None of these five has a single write tool, deliberately, and Release 2 must not
    # be what gives them one. The brief must not imply otherwise.
    writes = {
        name for name in _tools(profile)
        if TOOL_REGISTRY[name].get("dispatch_type") == "write"
        or TOOL_REGISTRY[name].get("requires_confirmation")
    }
    assert writes == set(), f"{profile} gained write tools: {sorted(writes)}"
    assert "NO write tools" in _brief(profile), (
        f"{profile}'s brief has to say it cannot change anything, or Flo will promise "
        "an action it has no tool for"
    )


@pytest.mark.parametrize("profile", DORMANT)
def test_a_dormant_brief_names_somebody_to_ask(profile):
    # The refusal these five give all day must send the person somewhere, not stop at
    # "not available to me" - the wording this project has already been bitten by.
    brief = _brief(profile)
    assert any(who in brief for who in ("Sonu Ruhal", "Lalit Thomas", "Adesh Singh",
                                        "the Principal", "the school's owner")), (
        f"{profile}'s brief refuses without naming who to ask instead"
    )


@pytest.mark.parametrize("profile", DORMANT)
def test_a_dormant_brief_does_not_deny_the_lookups_it_has(profile):
    # Each of the five really can read the school directory. A brief that flatly says
    # otherwise makes Flo refuse a question it is allowed to answer.
    assert "get_student_database" in _tools(profile) or "search_students" in _tools(profile)
    brief = _brief(profile)
    for lie in ("CANNOT see: student data", "CANNOT see student data",
                "no access to any school management tools"):
        assert lie not in brief, f"{profile}'s brief denies a lookup it actually has"


def test_it_support_is_not_promised_password_tools_it_does_not_have():
    tools = _tools("it_tech")
    assert "set_profile_password" not in tools
    assert "create_student_login" not in tools
    brief = _brief("it_tech")
    assert "CANNOT create a login, reset anybody's password" in brief


def test_maintenance_is_not_promised_writes_it_does_not_have():
    tools = _tools("maintenance")
    for write_tool in ("update_incident_status", "confirm_resolution"):
        assert write_tool not in tools
    assert "cannot close a request" in _brief("maintenance")


def test_the_action_log_stays_with_the_two_who_run_the_school():
    # Aman's request 10 of 2026-08-06, reconfirmed 2026-08-10.
    for profile in ("owner", "principal"):
        assert "query_audit_log" in _tools(profile)
    for profile in ("accountant", "management", *DORMANT):
        assert "query_audit_log" not in _tools(profile), (
            f"{profile} can read the action log, which is the owner's and the "
            "principal's only"
        )


def test_the_two_office_briefs_still_say_they_wait_for_approval():
    for profile in ("accountant", "management"):
        brief = _brief(profile)
        assert "wait for the school's owner or the Principal to approve" in brief, (
            f"{profile}'s brief no longer states the approval rule (R2-9, decision 6)"
        )


def test_leadership_is_told_it_approves_documents():
    for profile in ("owner", "principal"):
        assert "decide_certificate" in _brief(profile), (
            f"{profile}'s brief does not mention approving documents, so Flo cannot "
            "offer the one action only these two can take"
        )


def test_no_brief_calls_the_finance_report_owner_exclusive():
    # It stopped being owner-exclusive on 2026-08-10: the Principal and the Accountant
    # Head were granted it by name.
    for profile in ("principal", "accountant"):
        assert "get_financial_report" in _tools(profile)
    for profile in sorted(PROFILE_KEYS):
        assert "owner exclusive" not in _brief(profile), (
            f"{profile}'s brief still calls a shared report owner-exclusive"
        )


@pytest.mark.parametrize("profile", sorted(PROFILE_KEYS))
def test_a_brief_never_offers_a_screen_the_profile_cannot_open(profile):
    # Screen ids named in a brief must be ones the profile actually holds. The matrix
    # is the authority; the brief only describes it.
    screens = PROFILE_MATRIX[profile]["screens"]
    if not isinstance(screens, frozenset):
        return  # owner and principal hold everything
    brief = _brief(profile)
    for screen_id in ("audit-log", "school-settings"):
        assert screen_id not in screens
        assert f"use {screen_id}" not in brief
