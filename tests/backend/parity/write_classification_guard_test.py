"""R2.6 (audit X7) — write-tool classification guard.

`WRITE_TOOL_NAMES` in `ai/tool_functions_v2.py` derives purely from per-tool flags
(`requires_confirmation` / `dispatch_type == "write"`). A mutating tool registered
WITHOUT those flags silently bypasses the confirm gate, the AI-write kill-switch,
the write-ahead audit, and the parity gate — it would be treated as a harmless read.

This CI test closes that hole. Every tool in `TOOL_REGISTRY` must be classified
EXACTLY once: either it is flagged as a write, or it is on the explicit
`READ_ONLY_ALLOWLIST` below. A newly added tool that is neither fails this test,
forcing a conscious classification decision at review time. Read tools also must
carry a read-ish name prefix, so a mutating tool cannot be quietly parked on the
allowlist to dodge the gate.
"""

from __future__ import annotations

import pytest

from ai.tool_functions_v2 import TOOL_REGISTRY, WRITE_TOOL_NAMES

# The explicit set of tools that only READ (never mutate persisted state). This is
# the maintained allowlist the architecture calls for: adding a genuinely new read
# tool means adding it here; adding a write tool means giving it write flags. A tool
# that is on neither list is a classification gap and fails the guard below.
READ_ONLY_ALLOWLIST = frozenset({
    "draft_parent_message",
    "get_attendance_overview",
    "get_branch_comparison",
    "get_class_list",
    "get_class_wise_attendance",
    "get_daily_brief",
    "get_enquiries",
    "get_exam_results_summary",
    "get_expenses",
    "get_fee_defaulters",
    "get_fee_structures",
    "get_fee_summary",
    "get_fee_sync_status",
    "get_fee_transactions",
    "get_financial_report",
    "get_house_details",
    "get_house_standings",
    "get_inventory_status",
    "get_leave_requests",
    "get_library_status",
    "get_my_attendance",
    "get_my_class_students",
    "get_my_fees",
    "get_my_results",
    "get_school_pulse",
    "get_smart_alerts",
    "get_staff_list",
    "get_staff_status",
    "get_student_council",
    "get_student_database",
    "get_student_profile",
    "get_timetable",
    "get_today_class_attendance",
    "get_transport_status",
    "get_upcoming_events",
    "query_attendance_status",
    "query_audit_log",
    "query_dashboard_summary",
    "query_fee_status",
    "query_incidents",
    "query_maintenance_requests",
    "query_staff_availability",
    "query_student_record",
    "recall_history",
    "search_students",
})

# Read tools follow a small set of naming conventions. A tool on the read-only
# allowlist whose name doesn't match one of these prefixes is suspicious — the most
# likely way X7 recurs is a mutating tool (create_/update_/delete_/…) being dropped
# onto the allowlist to skip the confirm gate.
_READ_PREFIXES = ("get_", "query_", "search_", "recall_", "draft_")


def _is_flagged_write(tool_def: dict) -> bool:
    return bool(tool_def.get("requires_confirmation")) or tool_def.get("dispatch_type") == "write"


def test_every_tool_is_classified_exactly_once():
    """No tool may be both flagged-write and allowlisted, and none may be neither.

    A tool that is NEITHER is the X7 hole: a mutating tool added without flags would
    land here and fail, forcing the author to flag it (write) or allowlist it (read).
    """
    unclassified = []
    double_classified = []
    for name, tool_def in TOOL_REGISTRY.items():
        is_write = _is_flagged_write(tool_def)
        is_read = name in READ_ONLY_ALLOWLIST
        if is_write and is_read:
            double_classified.append(name)
        if not is_write and not is_read:
            unclassified.append(name)
    assert not unclassified, (
        "These registry tools are neither flagged as writes "
        "(requires_confirmation / dispatch_type=='write') nor on READ_ONLY_ALLOWLIST. "
        "A new MUTATING tool here would bypass confirm/kill-switch/audit — flag it as a "
        f"write, or add it to READ_ONLY_ALLOWLIST if it truly only reads: {sorted(unclassified)}"
    )
    assert not double_classified, (
        "These tools are BOTH flagged-write and on READ_ONLY_ALLOWLIST — remove them from "
        f"the allowlist: {sorted(double_classified)}"
    )


def test_write_flags_match_write_tool_names():
    """`WRITE_TOOL_NAMES` is exactly the set of flagged-write tools (no drift)."""
    flagged = {n for n, d in TOOL_REGISTRY.items() if _is_flagged_write(d)}
    assert flagged == set(WRITE_TOOL_NAMES)


def test_allowlisted_read_tools_use_read_prefix():
    """A mutating tool cannot be quietly parked on the read-only allowlist."""
    misnamed = [n for n in READ_ONLY_ALLOWLIST if not n.startswith(_READ_PREFIXES)]
    assert not misnamed, (
        "These allowlisted tools don't use a read-only naming convention — verify they "
        f"do not mutate state before allowlisting: {sorted(misnamed)}"
    )


def test_no_write_tool_uses_a_read_prefix():
    """A write tool named like a reader would be a classification smell."""
    suspects = [n for n in WRITE_TOOL_NAMES if n.startswith(_READ_PREFIXES)]
    assert not suspects, (
        f"These write-flagged tools use a read-only name prefix — rename or reclassify: {sorted(suspects)}"
    )


def test_allowlist_has_no_stale_entries():
    """Every allowlisted name still exists in the registry (catches renames/removals)."""
    stale = [n for n in READ_ONLY_ALLOWLIST if n not in TOOL_REGISTRY]
    assert not stale, f"READ_ONLY_ALLOWLIST references tools no longer in the registry: {sorted(stale)}"
