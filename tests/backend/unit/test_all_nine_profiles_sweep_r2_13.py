"""R2-13 - the proof. All nine profiles, every Flo tool, every screen in the matrix.

This is the thing that keeps Releases 3 to 7 honest. Everything else in Release 2 is a
fix; this is what stops the fixes rotting.

It exists because of how the platform used to grant access: by SUBTRACTION. The
classification loop at the bottom of `ai/tool_functions_v2.py` still ends in
`else: non_finance`, so a tool nobody classifies lands with the management head by
default and nobody finds out. R2-1 put a written grant table in front of that, and this
file is what makes the table true rather than aspirational.

NINE profiles, not the four in this release. `middleware/auth.py` recognises eight
admin sub-categories plus the school's owner. A sweep covering only the four under
discussion cannot see the other five being silently stripped or silently widened -
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


def test_five_are_live_and_eight_are_dormant():
    """R3-2 and R3-3, 2026-08-15: live went 4 to 5, and dormant 8 to 8 by way of 7.

    Two separate moves on the same day, and they happen to cancel out in the dormant
    count, which is exactly the kind of thing this file exists to make visible rather
    than let pass. **The transport head became LIVE** (R3-2), taking dormant from 8 to 7.
    **A tenth profile was defined, drivers and conductors** (R3-3), taking it back to 8.
    The set assertions below are what actually check this; the number alone would not
    have noticed.

    Chaman Singh's release is R3-2. He is granted tool by tool rather than by domain,
    holds transport money in full and no other money at all, sees only children who are
    on a route, and needs Aman or Adesh to agree a deletion. All of that is written down
    and approved in
    `implementation-artifacts/release-3-access/R3-2-proposal-chamans-profile-2026-08-15.md`.

    Everything below is the previous note, kept because it explains the other number.

    R4-6, 2026-08-12: dormant went from five to eight, and here is the reason.

    A count moving without a written reason means somebody's access changed and nobody
    decided to. This one moved on purpose: teacher, student and parent were added to the
    matrix because they were the last three roles outside it, with hand-written menus
    that nothing checked against the server. Their lists were copied from those menus
    exactly, they carry no tool domains and may_write False, and all three are dormant
    until Releases 5, 6 and 7 respectively.

    **Nobody gained or lost a screen.** `test_r4_6_no_role_gained_or_lost_a_screen` is
    what actually proves that; this only records why the number moved.
    """
    assert set(LIVE_PROFILES) == {
        "owner", "principal", "accountant", "management", "transport_head",
    }
    # R3-3 added the tenth profile on 2026-08-15, so dormant went 7 to 8.
    assert len(DORMANT_PROFILES) == 8
    assert {"teacher", "student", "parent"} <= set(DORMANT_PROFILES)
    # The four office desks still waiting for their own release. If one of these ever
    # goes live without a written reason beside it, somebody was switched on by accident.
    assert {"receptionist", "it_tech", "maintenance", "support_staff"} <= set(DORMANT_PROFILES)


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
            #
            # R2-5 then lets the matrix name individual tools in either direction,
            # because four domains cannot say "the accountant head yes, the management
            # head no" about a school bus route. A denial always wins over a grant.
            expected = "admin" in roles and domain in domains
            if name in entry["extra_tools"] and "admin" in roles:
                expected = True
            if name in entry["denied_tools"]:
                expected = False
        elif entry["extra_tools"] and entry["may_write"]:
            # R3-2, 2026-08-15: a profile granted TOOL BY TOOL rather than by domain.
            # The transport head is the first, because no domain means "transport":
            # finance is wrong for a school bus and non_finance is the management head's
            # whole surface.
            #
            # `extra_tools` is the WHOLE grant here rather than a set of exceptions to a
            # domain. Two things pass on top of it, and only two:
            #
            #  - `shared` READS, which is what every staff profile holds whatever their
            #    job: the school's published rate card, how full the disk is. Refusing
            #    those would take from a department head what his dormant colleagues
            #    already have.
            #  - nothing else. A WRITE is his only if his name is against it. A first
            #    version inherited shared writes and this suite caught what that meant:
            #    `import_data_file` and `create_student` are shared, so he could have
            #    rewritten the roll from a spreadsheet. That is the whole reason the rule
            #    is written this way.
            if name in entry["denied_tools"]:
                expected = False
            elif name in entry["extra_tools"]:
                expected = "admin" in roles
            else:
                expected = "admin" in roles and domain == SHARED and not is_action_tool(tool)
        else:
            # A dormant profile is NOT domain-widened. It reaches what the plain
            # registry gives any admin - reads only, because the Phase-1 lockdown
            # refuses it every write - with the R2-13 floor underneath: no money, and
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
    """Decision 1: the management head never sees a rupee figure.

    R3-2, 2026-08-15 adds the one exception, and it is worth reading rather than
    skimming, because "money reaches somebody without the finance domain" is exactly the
    sentence this test exists to make impossible.

    Abhimanyu's decision: the transport head holds full financial visibility of school
    TRANSPORT, fares and who owes what included, because he is the transport head. He is
    NOT given the finance domain, which would have handed him payroll, the ledger, the
    fee structures and every family's whole bill. He is given ONE named tool,
    `get_transport_fee_status`, which can only return the four transport fields the
    school keeps on a child's record.

    So the boundary is in what the tool is able to answer, not in remembering to filter
    it, and the exception is one line long and has a name. Any SECOND finance tool
    arriving in his grant fails this test and should: it would mean the boundary moved.
    """
    finance_tools = [
        name for name, tool in TOOL_REGISTRY.items()
        if tool.get("access_domain") == FINANCE and "admin" in set(tool.get("roles") or ())
    ]
    assert finance_tools

    for profile_name, user in PROFILES.items():
        entry = PROFILE_MATRIX[profile_name]
        has_domain = FINANCE in entry["tool_domains"]
        for name in finance_tools:
            may = has_domain or name in entry["extra_tools"]
            got = is_tool_authorized(user, TOOL_REGISTRY[name])
            assert got is may, f"{profile_name} / {name}: reached={got}, entitled={may}"


def test_the_transport_head_holds_exactly_one_money_tool_and_it_is_transport_only():
    """The named exception above, pinned by name so it cannot quietly become two."""
    entry = PROFILE_MATRIX["transport_head"]
    money = sorted(
        name for name in entry["extra_tools"]
        if (TOOL_REGISTRY.get(name) or {}).get("access_domain") == FINANCE
    )
    assert money == ["get_transport_fee_status"], (
        "the transport head's money access changed. He was granted transport money and "
        "no other money at all (Abhimanyu, 2026-08-15). Reaching a second finance tool "
        "means that boundary moved, and somebody has to have decided it: " + ", ".join(money)
    )


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
# Release 2 step 10, 2026-08-12: +5 tools and +3 writes for the owner, the principal and
# the accountant head, and NOBODY else. They are the school's own fee work made askable in
# words: explain_student_fee and calculate_late_fine (reads), and set_student_concession,
# record_admission_concession and set_right_to_education (writes, each behind a confirm
# card). All five are in FINANCE_TOOL_NAMES by name, which is why the management head and
# the five dormant profiles are unchanged: every one of them either names a rupee figure on
# a family's bill or decides whether one is owed.
# 2026-08-12: +1 READ tool for the two leadership profiles and nobody else,
# `get_school_summary` (Abhimanyu: build the scheduled reports so Aman and Adesh have a
# summary of everything in one place). It carries money, the roll and everyone's changes
# in one answer, so it sits behind the same gate as the action log.
# EVERY PROFILE GAINED EXACTLY ONE READ TOOL ON 2026-08-12 (Release 3, item 4):
# `export_data_file`, which hands over a whole data set as an Excel workbook or CSV.
# It is classified `shared`, so it reaches everyone, and NO write count moved.
#
# Reaching the tool is not the same as getting the file. Its own gate, `may_export`,
# is `require_export`'s rule rather than a copy of it, and it asks the permission table
# per DATA SET: management is refused the ledger and gets the children and the staff,
# the accountant gets both, and **every dormant profile is refused everything** even
# though the five below can now see the tool exists. That is why five zero-write
# profiles gained a tool and gained no access.
# 2026-08-12 (Release 3, item B): +1 READ tool for the two leadership profiles and NOBODY
# else, `export_whole_school_workbook` - the whole school as one Excel file with a sheet
# per area. Abhimanyu's decision is that it is Aman's and Adesh's only, so it is in
# LEADERSHIP_ONLY_TOOL_NAMES, which is the domain that means exactly those two. No write
# count moved: it reads and formats, and changes no school record.
# 2026-08-12 (Release 4, R4-5): +1 tool and +1 WRITE for the four live profiles, and
# nothing at all for the five dormant ones. `report_platform_problem` lets Flo tell Layaa
# AI that the platform itself is broken. It is classified `shared`, because reporting a
# fault is neither the school's money nor the school's records and the management head
# must be able to report a broken fees screen; and it counts as a write because it
# records a ticket and sends it. The dormant profiles are unchanged because they hold no
# Flo domains and may not write, which is the same reason they gained a read tool in
# Release 3 and gained no access with it.
# 2026-08-12 (Release 4, R4-5, second change): EVERY profile gained exactly ONE READ tool
# and NO write count moved: `get_storage_room`, which says how much room the school's
# records are using and whether they are running out. Classified `shared` for the same
# reason as the tool above: how full the disk is is a fact about the platform, not about
# the school's money or its children. The five dormant profiles gain it too, exactly as
# they gained `export_data_file` in Release 3, and gain no access with it: it reads a
# figure the database already keeps and touches no school record.
# 2026-08-15 (R3-2): EVERY profile except the accountant head gained exactly ONE READ
# tool and NO write count moved: `get_student_to_add_to_a_route`. It looks up one child
# by their EXACT admission number and returns their name, their class and whether they
# are already on a bus. No address, no guardian's number, no fee, and it refuses to
# search by name.
#
# It exists because the transport head sees only children who are on a route, which
# would otherwise have left him unable to put a child on one for the first time. It is
# classified non_finance because it names no money at all, which is why the accountant
# head is the one profile that does not move, and why the four dormant desks pick it up
# the same way they pick up every other registry read: it tells them strictly less than
# the student lookup they already hold.
# 2026-08-15 (R3-2, second change): +1 tool and +1 WRITE for the owner, the principal and
# the transport head, and NOBODY else. `remove_transport_vehicle` takes a bus, van or auto
# off the register; before it there was no way to remove one at all, so a vehicle sold or
# scrapped stayed on the register for ever.
#
# **The management head does NOT move, and that took a deliberate edit.** The tool is
# classified non_finance, which is his entire domain, so it reached him by default and this
# very test caught it. Decision 2 of 2026-08-10 moved transport off him, so it is now named
# in his `denied_tools` beside the original five. Any future transport tool belongs there
# too, or the denial rots one tool at a time as transport grows.
# 2026-08-15 (R3-2, third change): +1 tool and +1 WRITE for the TRANSPORT HEAD ONLY.
# `delete_staff`, so he can ask for a driver or conductor to be taken off the roll. It was
# asked for in the same breath as adding one and was half-built: the approval could be
# carried out and nothing could raise it, so he could not ask at all. Found by auditing
# every decision against the code rather than against memory.
#
# **His `may_delete_people` is still False and that is not a contradiction.** He cannot
# remove anybody himself. The service turns his request into an approval routed to Aman
# and Adesh before the deny is reached, and narrows it to his own transport staff, so the
# path built for retiring a bus driver cannot ask for a teacher's removal. Nobody else
# moves: `delete_staff` is non_finance, and the owner, principal and management head all
# already held it.
EXPECTED_REACH = {
    # 165/104 until 2026-08-14. MINUS SIX tools, all six of them writes: campus retail
    # was removed on Abhimanyu's instruction, taking create_retail_product,
    # delete_retail_product, open_pos_shift, close_pos_shift, post_pos_sale and
    # post_pos_return with it. The Aaryans runs no shop; the canteen is an outside vendor
    # renting space.
    #
    # Worth reading the whole block rather than just these two lines: the drop is exactly
    # six on the owner, the principal AND the accountant head, and **management did not
    # move at all**. That is the proof the removal hit precisely what it aimed at. The six
    # were finance-classified, which is why the management head never had them, and if his
    # number had moved it would have meant the cut caught something else on the way past.
    #
    # 159/98 until 2026-08-14 (A6). PLUS FIVE tools, all five of them writes: the second
    # half of the admissions funnel reached Flo. `create_admission_application`,
    # `update_admission_application_status`, `record_admission_assessment`,
    # `issue_admission_offer` and `enroll_admission_application`, each a thin adapter
    # over the same service function `routes/admissions.py` already calls. Flo could work
    # the enquiry half of the journey and nothing beyond it.
    #
    # Read the three moves together rather than one line at a time. The owner and the
    # principal gain five. **The management head gains only three**, because issuing an
    # offer and enrolling a child are refused to him on the REST route by `_can_enroll`
    # and are named in his `denied_tools` so chat gives the same answer as the screen.
    # The six dormant desks and the accountant head do not move at all, which is the
    # proof this landed where it was aimed: admissions is not money and it is not theirs.
    # 164/103 until 2026-08-15 (R3-2). PLUS ONE READ and no write, for the owner, the
    # principal AND the accountant head, and nobody else: `get_transport_fee_status`,
    # what the children on the buses pay and whether it is cleared. It is classified
    # finance because it names what a family owes, which is why the management head does
    # not move (decision 1: he never sees a rupee figure) and why the four dormant office
    # desks do not either.
    # 167/104 (owner and principal), 60/30 (accountant), 105/63 (management),
    # 25/10 (transport head) and 30 or 31 with no writes (the dormant desks) until
    # 2026-08-15, when the APPROVALS WORKFLOW landed. Read this block once and the ten
    # numbers below explain themselves.
    #
    # TWO tools were added, both classified `shared`: `get_my_approvals`, a read, and
    # `decide_any_approval`, a write. So:
    #
    #   +1 READ for EVERY profile, including the dormant ones. Asked "is anything waiting
    #   on me", anybody may ask. The answer is built by `approval_registry`, which returns
    #   only what that person may decide, so for a profile that decides nothing the honest
    #   answer is an empty list rather than a refusal.
    #
    #   +1 WRITE for the profiles that write at all, and for nobody else. The transport
    #   head does NOT gain it, and neither do the five dormant desks. That is the R3-2
    #   rule holding: a named-grant profile inherits `shared` reads and never inherits a
    #   `shared` write, and a dormant profile has `may_write` False.
    #
    # **The accountant head and the management head gaining the write tool grants them
    # nothing, and that is worth understanding rather than trusting.** The tool decides
    # nothing itself; it asks each kind's own service, which refuses them exactly as its
    # own screen does. Pinned by name in
    # `tests/backend/api/test_approvals_one_workflow_2026_08_15.py`, which asserts that
    # both are refused every one of the six kinds. If either ever gains a real decision,
    # that file goes red before this one does.
    "owner":          (169, 105),
    "principal":      (169, 105),
    # 56/31 until 2026-08-11. +1 tool, +1 write: update_staff, named in
    # PROFILE_MATRIX["accountant"]["extra_tools"], scoped by the SERVICE to salary
    # only (Abhimanyu, relaying Aman's and Adesh's instruction).
    # 65/36 until 2026-08-14, minus the same six campus-retail tools.
    # 59/30 until 2026-08-15, plus the same one transport-fee read as the two above.
    "accountant":     (62, 31),
    # 101/60 until 2026-08-14. PLUS THREE, not five: see the A6 note above.
    "management":     (107, 64),
    # 30/0 until 2026-08-15. Now 22/8, and BOTH halves of that move are the point of R3-2.
    #
    # **The write count went 0 to 8, which is the grant.** Chaman Singh's release landed.
    # He creates, changes and deletes a bus route, registers a vehicle, moves a child
    # between routes, adds and edits a driver or conductor, and tells Layaa AI the
    # platform is broken. Every one is named against his row in `profile_matrix.py` and
    # approved in writing (R3-2-proposal-chamans-profile-2026-08-15.md).
    #
    # **The tool count went DOWN, 30 to 22, and that is a narrowing, not a loss.** As a
    # dormant profile with no domain he FELL THROUGH to about thirty registry reads that
    # nobody had granted him: he simply reached whatever the registry offered any admin.
    # He is now default-deny - his named list, plus the `shared` reads every staff profile
    # holds whatever their job. So he has more of what is his and none of what was never
    # his, which is the whole argument for granting by name rather than by subtraction.
    #
    # If this pair moves again, read it as two separate questions. The write number moving
    # means somebody's authority changed. The tool number moving on its own usually means
    # a `shared` tool was added or reclassified.
    "transport_head": (26, 10),
    "receptionist":   (32, 0),
    "it_tech":        (32, 0),
    "maintenance":    (32, 0),
    "support_staff":  (31, 0),
    # R3-3, 2026-08-15: the tenth profile, drivers and conductors. Defined so the
    # transport head can record his own team on the staff roll without filing them as
    # something they are not.
    #
    # **30 and 0, the same as every other dormant profile, and the 30 deserves a word
    # rather than being read as a grant.** It is what the gate WOULD say, not what
    # anybody can do: like the four dormant office desks, this profile falls through to
    # the plain registry reads and holds no write tool at all. Nobody can exercise any of
    # it, because answer 10 of 2026-08-11 gives these colleagues NO LOGIN, which is also
    # why they hold no screens. If the write number ever moves off 0, somebody granted a
    # driver the ability to change the school's records.
    "transport_staff": (31, 0),
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
