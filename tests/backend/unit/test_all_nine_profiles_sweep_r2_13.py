"""R2-13 — the proof. All nine profiles, every Flo tool, every screen in the matrix.

This is the thing that keeps Releases 3 to 7 honest. Everything else in Release 2 is a
fix; this is what stops the fixes rotting.

It exists because of how the platform used to grant access: by SUBTRACTION. The
classification loop at the bottom of `ai/tool_functions_v2.py` still ends in
`else: non_finance`, so a tool nobody classifies lands with the management head by
default and nobody finds out. R2-1 put a written grant table in front of that, and this
file is what makes the table true rather than aspirational.

NINE profiles, not the four in this release. `middleware/auth.py` recognises eight
admin sub-categories plus the school's owner. A sweep covering only the four under
discussion cannot see the other five being silently stripped or silently widened —
which is exactly what a four-profile matrix would have done on the day it shipped.

WHAT FAILS THIS FILE, on purpose:
  - adding a Flo tool and leaving it to fall through to `non_finance`;
  - giving any of the five dormant profiles a write tool;
  - letting an owner-only tool reach anyone below the school's leadership;
  - changing what any profile reaches, without saying so.

The last one is the counts at the bottom. If you moved a number deliberately, change it
here and explain the move in your commit message and in PROGRESS.md. If you did not
move it deliberately, you have found a defect.
"""

from __future__ import annotations

import pytest

from ai.tool_access import is_tool_authorized
from ai.tool_functions_v2 import TOOL_REGISTRY
from services.ai_action_policy import is_action_tool
from services.profile_matrix import (
    ALL_SCREENS,
    DORMANT_PROFILES,
    FINANCE,
    LEADERSHIP,
    LIVE_PROFILES,
    NON_FINANCE,
    PROFILE_MATRIX,
    SHARED,
)

# Every profile the platform issues a token for, in the shape a request handler sees.
PROFILES = {
    name: (
        {"id": f"u-{name}", "role": "owner", "sub_category": "owner"}
        if name == "owner"
        else {"id": f"u-{name}", "role": "admin", "sub_category": name}
    )
    for name in PROFILE_MATRIX
}

KNOWN_DOMAINS = {FINANCE, NON_FINANCE, SHARED, LEADERSHIP, "meta", "communication"}


# ─── The matrix itself is well formed ──────────────────────────────────────────

def test_all_nine_profiles_are_defined():
    """Eight admin sub-categories plus the school's owner. Not four."""
    from middleware.auth import SUB_CATEGORIES_BY_ROLE

    recognised = set(SUB_CATEGORIES_BY_ROLE.get("admin") or ())
    missing = recognised - set(PROFILE_MATRIX)
    assert not missing, (
        "these profiles can hold a login but are not in the matrix, so default deny "
        "will strip them silently: " + ", ".join(sorted(missing))
    )


def test_four_are_live_and_five_are_dormant():
    assert set(LIVE_PROFILES) == {"owner", "principal", "accountant", "management"}
    assert len(DORMANT_PROFILES) == 5


def test_every_profile_states_what_it_may_do():
    for name, entry in PROFILE_MATRIX.items():
        assert entry["screens"] == ALL_SCREENS or isinstance(entry["screens"], frozenset), name
        assert entry["tool_domains"] <= KNOWN_DOMAINS, name
        assert isinstance(entry["may_write"], bool), name
        assert isinstance(entry["may_delete_people"], bool), name
        assert entry["status"] in {"live", "dormant"}, name
        assert entry["notes"], f"{name} has no note saying why it is what it is"


# ─── Every tool has an owner ───────────────────────────────────────────────────

def test_every_flo_tool_is_classified():
    """A tool with no access_domain has fallen through to `else: non_finance`.

    That is the subtraction defect: it means nobody decided who this tool is for, and
    the management head got it because he is the default.
    """
    unclassified = sorted(
        name for name, tool in TOOL_REGISTRY.items()
        if tool.get("access_domain") not in KNOWN_DOMAINS
    )
    assert unclassified == [], (
        "these tools carry no recognised access_domain: " + ", ".join(unclassified)
    )


def test_the_school_owner_can_reach_every_school_management_tool():
    """If the owner cannot reach it, nobody in the school can, and it is dead code."""
    unreachable = sorted(
        name for name, tool in TOOL_REGISTRY.items()
        if "admin" in set(tool.get("roles") or ()) or "owner" in set(tool.get("roles") or ())
        if not is_tool_authorized(PROFILES["owner"], tool)
    )
    assert unreachable == [], (
        "the school's owner cannot reach: " + ", ".join(unreachable)
    )


# ─── The rule holds for every tool and every profile ───────────────────────────

@pytest.mark.parametrize("profile_name", sorted(PROFILE_MATRIX))
def test_each_profile_reaches_exactly_what_the_matrix_grants(profile_name):
    """The gate and the written table agree, tool by tool, for all 161 tools."""
    user = PROFILES[profile_name]
    entry = PROFILE_MATRIX[profile_name]
    domains = entry["tool_domains"]
    disagreements = []

    for name, tool in TOOL_REGISTRY.items():
        roles = set(tool.get("roles") or ())
        if not roles.intersection({"owner", "admin"}):
            continue  # a student/teacher/guardian tool; not this table's business
        allowed = is_tool_authorized(user, tool)

        domain = tool.get("access_domain")
        if profile_name in {"owner", "principal"}:
            # Leadership holds the whole school-management surface by design.
            expected = True
        elif domains:
            # A domain-widened profile (the accountant and management heads): the
            # registry must offer it to an admin at all, AND the profile must hold
            # its domain. Both, not either. That second half is R2-3.
            expected = "admin" in roles and domain in domains
        else:
            # A dormant profile is NOT domain-widened. It reaches what the plain
            # registry gives any admin — reads only, because the Phase-1 lockdown
            # refuses it every write — with the R2-13 floor underneath: no money, and
            # no action log.
            sub_categories = tool.get("sub_categories")
            expected = (
                "admin" in roles
                and (sub_categories is None or profile_name in sub_categories)
                and not is_action_tool(tool)
                and domain not in {FINANCE, LEADERSHIP}
            )

        if allowed != expected:
            disagreements.append((name, tool.get("access_domain"), allowed, expected))

    assert disagreements == [], (
        f"{profile_name}: the gate and the matrix disagree about "
        + ", ".join(d[0] for d in disagreements)
    )


# ─── The five dormant profiles hold nothing they can write with ────────────────

@pytest.mark.parametrize("profile_name", sorted(DORMANT_PROFILES))
def test_a_dormant_profile_has_no_write_tool(profile_name):
    """The single most important line in this file.

    The five profiles below the management head have zero write tools today, and
    Release 2 must not be what gives them any. Switching a profile on is its own
    release, with its own decision from the school.
    """
    user = PROFILES[profile_name]
    writes = sorted(
        name for name, tool in TOOL_REGISTRY.items()
        if is_action_tool(tool) and is_tool_authorized(user, tool)
    )
    assert writes == [], f"{profile_name} gained write tools: " + ", ".join(writes)


@pytest.mark.parametrize("profile_name", sorted(DORMANT_PROFILES))
def test_a_dormant_profile_holds_no_tool_domain(profile_name):
    assert PROFILE_MATRIX[profile_name]["tool_domains"] == frozenset()
    assert PROFILE_MATRIX[profile_name]["may_write"] is False
    assert PROFILE_MATRIX[profile_name]["may_delete_people"] is False


# ─── Owner-only stays owner-only, and money stays with finance ─────────────────

def test_no_profile_below_leadership_reaches_an_owner_only_tool():
    owner_only = [
        name for name, tool in TOOL_REGISTRY.items()
        if set(tool.get("roles") or ()) == {"owner"}
    ]
    assert owner_only, "expected the registry to still mark some tools owner-only"

    breaches = []
    for profile_name, user in PROFILES.items():
        if profile_name in {"owner", "principal"}:
            continue
        for name in owner_only:
            if is_tool_authorized(user, TOOL_REGISTRY[name]):
                breaches.append(f"{profile_name} -> {name}")
    assert breaches == [], "owner-only tools leaked: " + ", ".join(breaches)


def test_only_the_finance_profiles_reach_a_finance_tool():
    """Decision 1: the management head never sees a rupee figure."""
    finance_tools = [
        name for name, tool in TOOL_REGISTRY.items()
        if tool.get("access_domain") == FINANCE and "admin" in set(tool.get("roles") or ())
    ]
    assert finance_tools

    for profile_name, user in PROFILES.items():
        may = FINANCE in PROFILE_MATRIX[profile_name]["tool_domains"]
        for name in finance_tools:
            got = is_tool_authorized(user, TOOL_REGISTRY[name])
            assert got is may, f"{profile_name} / {name}: reached={got}, entitled={may}"


def test_only_leadership_reaches_the_private_leadership_tools():
    """The action log, the AI's own reasoning, and notes about named people."""
    leadership_tools = [
        name for name, tool in TOOL_REGISTRY.items()
        if tool.get("access_domain") == LEADERSHIP
    ]
    assert leadership_tools

    for profile_name, user in PROFILES.items():
        may = profile_name in {"owner", "principal"}
        for name in leadership_tools:
            got = is_tool_authorized(user, TOOL_REGISTRY[name])
            assert got is may, f"{profile_name} / {name}: reached={got}, entitled={may}"


# ─── The counts. Change these deliberately or not at all. ──────────────────────

# Measured 2026-08-10 after R2-4. `scripts/audit_profile_reach.py` prints the same
# numbers and is what PROGRESS.md quotes, so the two never disagree.
#
# A number here moving is not a test failure to be silenced. It means somebody's
# access changed. If you meant it, edit the number and say why in the commit message
# and in PROGRESS.md. If you did not, you have found a defect.
EXPECTED_REACH = {
    "owner":          (155, 100),
    "principal":      (155, 100),
    "accountant":     (46, 27),
    "management":     (102, 63),
    "transport_head":(27, 0),
    "receptionist": (27, 0),
    "it_tech":      (27, 0),
    "maintenance":  (27, 0),
    "support_staff":(26, 0),
}


@pytest.mark.parametrize("profile_name", sorted(EXPECTED_REACH))
def test_what_each_profile_reaches_has_not_changed_by_accident(profile_name):
    user = PROFILES[profile_name]
    tools = [name for name, tool in TOOL_REGISTRY.items() if is_tool_authorized(user, tool)]
    writes = [name for name in tools if is_action_tool(TOOL_REGISTRY[name])]

    expected_tools, expected_writes = EXPECTED_REACH[profile_name]
    assert (len(tools), len(writes)) == (expected_tools, expected_writes), (
        f"{profile_name} now reaches {len(tools)} tools ({len(writes)} of them writes), "
        f"not {expected_tools} ({expected_writes}). If that was deliberate, update "
        f"EXPECTED_REACH and say why. If it was not, somebody's access just changed "
        f"without anyone deciding to change it."
    )
