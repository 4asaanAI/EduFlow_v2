"""R2-3 — owner-only Flo tools stay owner-only for every other profile.

The profile overlay in `services/ai_action_policy.py` returns an authoritative
decision that short-circuits the ordinary role check in `ai/tool_access.py`. It used
to ask only whether the registry's `roles` list *intersected* {owner, admin}, so a
tool marked `roles=["owner"]` passed that test and was then handed to any profile
whose `access_domain` matched — which put `year_end_transition`, the branch CRUD,
`update_school_settings` and the legal-entity CRUD in the hands of the management and
accountant heads.

This file pins the rule: if the registry names the roles, the gate obeys them.

The principal is deliberately NOT covered by that rule. The school's owner and the
principal share the complete school-management surface by design — pinned by
`test_epic_k_crud_guardrails.py` and `test_owner_part3_qa.py`, and visible in the
2026-08-10 baseline where both reach 155 tools. The leak was the two profiles below
them.
"""

from __future__ import annotations

import pytest

from ai.tool_access import is_tool_authorized
from ai.tool_functions_v2 import TOOL_REGISTRY

OWNER = {"id": "o1", "role": "owner"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal"}

# Every profile below leadership that the platform recognises. `middleware/auth.py`
# lists eight admin sub-categories; the seven non-principal ones appear here plus
# teacher, so a new profile cannot quietly acquire an owner-only tool.
NON_OWNER_PROFILES = {
    "accountant": {"id": "a1", "role": "admin", "sub_category": "accountant"},
    "management": {"id": "m1", "role": "admin", "sub_category": "management"},
    "transport_head": {"id": "t1", "role": "admin", "sub_category": "transport_head"},
    "receptionist": {"id": "r1", "role": "admin", "sub_category": "receptionist"},
    "it_tech": {"id": "i1", "role": "admin", "sub_category": "it_tech"},
    "maintenance": {"id": "n1", "role": "admin", "sub_category": "maintenance"},
    "support_staff": {"id": "s1", "role": "admin", "sub_category": "support_staff"},
    "teacher": {"id": "te1", "role": "teacher"},
}

OWNER_ONLY_TOOLS = sorted(
    name
    for name, tool_def in TOOL_REGISTRY.items()
    if set(tool_def.get("roles") or ()) == {"owner"}
)

# The ones the 2026-08-10 audit found reachable by the management or accountant head.
# Named literally so that deleting or renaming one is a visible change, not a silently
# shrinking test.
KNOWN_OWNER_ONLY = {
    "year_end_transition",
    "create_branch",
    "update_branch",
    "delete_branch",
    "update_school_settings",
    "get_branch_comparison",
    "query_dashboard_summary",
    "confirm_resolution",
    "create_legal_entity",
    "delete_legal_entity",
    "set_default_legal_entity",
}


def test_the_known_owner_only_tools_are_still_marked_owner_only():
    missing = KNOWN_OWNER_ONLY - set(OWNER_ONLY_TOOLS)
    assert not missing, (
        "these tools stopped being owner-only in the registry: " + ", ".join(sorted(missing))
    )


@pytest.mark.parametrize("tool_name", OWNER_ONLY_TOOLS)
@pytest.mark.parametrize("profile_name", sorted(NON_OWNER_PROFILES))
def test_owner_only_tool_is_refused_to_every_non_owner_profile(tool_name, profile_name):
    user = NON_OWNER_PROFILES[profile_name]
    assert is_tool_authorized(user, TOOL_REGISTRY[tool_name]) is False, (
        f"{profile_name} can reach owner-only tool {tool_name}"
    )


@pytest.mark.parametrize("tool_name", sorted(KNOWN_OWNER_ONLY))
def test_leadership_keeps_every_owner_only_tool(tool_name):
    """The school's owner keeps all of them, and so does the principal.

    Owner and principal are one profile ("leadership") on purpose. Narrowing the
    principal here would break the school's own hierarchy, in which Adesh stands
    directly below Aman, and would contradict the two suites named in the docstring.
    """
    assert is_tool_authorized(OWNER, TOOL_REGISTRY[tool_name]) is True
    assert is_tool_authorized(PRINCIPAL, TOOL_REGISTRY[tool_name]) is True


def test_year_end_transition_specifically_is_out_of_reach_of_the_management_head():
    """Named on its own because it moves every student up a class."""
    assert (
        is_tool_authorized(
            NON_OWNER_PROFILES["management"], TOOL_REGISTRY["year_end_transition"]
        )
        is False
    )


def test_the_financial_report_still_reaches_the_principal_and_the_accountant():
    """R2-3 tightened the gate; this is the one entry that was widened by name.

    It was `roles=["owner"]` and reached the principal and accountant head only by
    accident. Both genuinely need it, so the registry now says so out loud.
    """
    tool_def = TOOL_REGISTRY["get_financial_report"]
    assert is_tool_authorized(PRINCIPAL, tool_def) is True
    assert is_tool_authorized(NON_OWNER_PROFILES["accountant"], tool_def) is True
    # ...and it still does not reach the management head, whose domain is non-finance.
    assert is_tool_authorized(NON_OWNER_PROFILES["management"], tool_def) is False


def test_domain_expansion_still_works_for_the_ordinary_case():
    """The fix must not collapse the profile overlay itself.

    A tool the registry offers to any admin is still widened by access_domain: the
    management head reaches the non-finance one, the accountant head does not.
    """
    non_finance_tool = {
        "roles": ["owner", "admin"],
        "access_domain": "non_finance",
        "sub_categories": ["principal"],
    }
    assert is_tool_authorized(NON_OWNER_PROFILES["management"], non_finance_tool) is True
    assert is_tool_authorized(NON_OWNER_PROFILES["accountant"], non_finance_tool) is False
