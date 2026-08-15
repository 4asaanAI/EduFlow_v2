"""R2.6 (audit X7) - write-tool classification guard.

`WRITE_TOOL_NAMES` in `ai/tool_functions_v2.py` derives purely from per-tool flags
(`requires_confirmation` / `dispatch_type == "write"`). A mutating tool registered
WITHOUT those flags silently bypasses the confirm gate, the AI-write kill-switch,
the write-ahead audit, and the parity gate - it would be treated as a harmless read.

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
    # R4-5, 2026-08-12. `get_storage_room` reads one figure MongoDB already keeps
    # about itself (dbStats). It writes nothing at all, not even a file, and touches no
    # school record. Note that the storage WATCH can raise a ticket, and that is a
    # different thing in a different module: it goes through
    # `platform_ticket_service.raise_ticket`, which is classified as a write, requires
    # confirmation when Flo calls it, and audits. This tool only answers the question.
    "get_storage_room",
    # Approvals workflow, 2026-08-15. `get_my_approvals` answers "is anything waiting
    # on me" across all six kinds and in both directions. It writes nothing whatsoever:
    # it reads each kind's own collection and filters the rows by what that person may
    # decide. The tool that DECIDES is `decide_any_approval`, which is a separate tool,
    # is flagged as a write, and shows a confirm card.
    "get_my_approvals",
    # UI Sweep Epic 10. A considered classification, not a convenience.
    # `draft_document` DOES create an S3 object, a `file_uploads` row and an audit
    # row - but it changes NO school record: no student, fee, staff member or
    # attendance mark differs afterwards. There is nothing to undo, so a confirm
    # step would add friction without adding safety, and the kill-switch guards AI
    # writes to school data rather than the production of a file. Its real controls
    # are the role gate (owner/admin/teacher, students excluded exactly as in
    # routes/exports.py), the audit row, and the per-school daily cap it shares with
    # certificate generation. It was renamed FROM `generate_document` because this
    # guard was right that "generate_" reads as mutating.
    "draft_document",
    # Release 3, 2026-08-12. Same considered classification as `draft_document`
    # directly above, and for the same reason: it stores a file, a `file_uploads` row
    # and an audit row, and changes NO school record. It reads rows the caller may
    # already read - through `may_export`, which is `require_export`'s own rule rather
    # than a copy of it - and formats them. There is nothing to undo, and Abhimanyu's
    # decision of 2026-08-12 is explicit that an export needs no confirm window on a
    # screen or through Flo. If this tool is ever changed to WRITE anything about a
    # student, a fee or a staff member, it leaves this list.
    "export_data_file",
    # Release 3 item B, 2026-08-12. The whole school as one workbook. Identical
    # classification to `export_data_file` directly above and for identical reasons: it
    # stores a file, a `file_uploads` row and an audit row, and changes no school
    # record. It is a bigger READ, not a different kind of act. Same rule applies - if
    # it is ever changed to write anything about a person, it leaves this list.
    "export_whole_school_workbook",
    "draft_parent_message",
    # Deferred tool loading: reveals tool INSTRUCTIONS the caller is already
    # authorized for. Reads the registry, writes nothing.
    "search_tools",
    # Reads every row of an uploaded spreadsheet and reports what WOULD change.
    # Writes nothing - `import_data_file` is the confirm-gated write.
    "preview_data_import",
    # Parent messaging reads. `get_messaging_status` and `get_message_templates` are
    # plainly read-only. `get_whatsapp_template_status` is a considered classification,
    # like `draft_document` above: it DOES write one field - it stores the approval
    # state Twilio just reported back onto the local template row. That row is a mirror
    # of state owned by Meta, not a school record: no student, fee, staff member or
    # message differs afterwards, and re-running it simply re-reads the same truth.
    # A confirm step would ask a human to approve copying someone else's fact.
    "get_messaging_status",
    "get_message_templates",
    "get_whatsapp_template_status",
    "get_attendance_overview",
    "get_branch_comparison",
    "get_class_list",
    "get_class_wise_attendance",
    # Read-only adapter over commercial_service reporting. It lists scoped CRM,
    # retail, and entity summaries and exposes no mutation path.
    "get_commercial_operations",
    "get_custom_forms",
    "get_daily_brief",
    "get_announcements",
    "get_admissions_pipeline",
    "get_enquiries",
    "get_enterprise_operations",
    "get_exam_results_summary",
    "get_expenses",
    "get_fee_defaulters",
    "get_fee_structures",
    "get_fee_summary",
    "get_fee_sync_status",
    "get_fee_transactions",
    "get_financial_report",
    "get_finance_controls",
    "get_payroll",
    "get_house_details",
    "get_house_standings",
    "get_inventory_status",
    "get_leave_requests",
    "get_library_status",
    "get_my_attendance",
    "get_my_class_students",
    "get_my_fees",
    "get_my_results",
    "get_my_school_hub",
    # Owner request 10 (2026-08-06): counts only - the roll, the NSO list and the
    # people who have left. It writes nothing.
    "get_enrolment_summary",
    # Owner request 4: reads back only the caller's OWN notes. Writes nothing.
    "get_profile_notes",
    "get_school_pulse",
    "get_smart_alerts",
    "get_staff_list",
    "get_staff_status",
    "get_student_council",
    "get_student_database",
    "get_student_profile",
    "get_timetable",
    "get_today_class_attendance",
    # R3-2, 2026-08-15. Both read and change nothing, which is why they belong here
    # rather than being flagged as writes.
    "get_student_to_add_to_a_route",
    "get_transport_fee_status",
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
    # Release 2 step 10. Both only read. `explain_student_fee` answers why one family's
    # bill is the figure it is; `calculate_late_fine` is pure arithmetic and touches no
    # collection at all. Neither can change a school record.
    "explain_student_fee",
    "calculate_late_fine",
    # The school on one page. Reads six areas and writes one thing: the day's summary is
    # KEPT the first time it is produced, so tomorrow's reading of today cannot quietly
    # differ from today's. No school record changes.
    "get_school_summary",
})

# Read tools follow a small set of naming conventions. A tool on the read-only
# allowlist whose name doesn't match one of these prefixes is suspicious - the most
# likely way X7 recurs is a mutating tool (create_/update_/delete_/…) being dropped
# onto the allowlist to skip the confirm gate.
# `preview_` added 2026-08-08 for `preview_data_import`. It is a read verb in the same
# sense as `draft_`: it reports what a write WOULD do and performs none of it. Deliberately
# narrow - "preview" cannot plausibly name a mutating tool, so it does not weaken the guard.
# `explain_` and `calculate_` added 2026-08-12 for `explain_student_fee` and
# `calculate_late_fine` (Release 2 step 10). Both are read verbs in the same narrow sense:
# one reports why a family's bill is what it is, the other works out an arithmetic answer,
# and neither can name a mutating tool without lying about what it does. They were named
# this way on purpose rather than as `query_…`, because these are the words a person and a
# model both reach for, and a tool the model does not recognise is a tool nobody uses.
# `export_` added 2026-08-12 for `export_data_file` (Release 3). It is a read verb in
# the same narrow sense as the two above: an export takes data OUT and cannot name a
# tool that changes a record without lying about what it does. It was named this way
# rather than `get_…` because "export" and "download" are the words a person and a
# model both reach for, and a tool the model does not recognise is a tool nobody uses.
_READ_PREFIXES = ("get_", "query_", "search_", "recall_", "draft_", "preview_",
                  "explain_", "calculate_", "export_")


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
        "A new MUTATING tool here would bypass confirm/kill-switch/audit - flag it as a "
        f"write, or add it to READ_ONLY_ALLOWLIST if it truly only reads: {sorted(unclassified)}"
    )
    assert not double_classified, (
        "These tools are BOTH flagged-write and on READ_ONLY_ALLOWLIST - remove them from "
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
        "These allowlisted tools don't use a read-only naming convention - verify they "
        f"do not mutate state before allowlisting: {sorted(misnamed)}"
    )


def test_no_write_tool_uses_a_read_prefix():
    """A write tool named like a reader would be a classification smell."""
    suspects = [n for n in WRITE_TOOL_NAMES if n.startswith(_READ_PREFIXES)]
    assert not suspects, (
        f"These write-flagged tools use a read-only name prefix - rename or reclassify: {sorted(suspects)}"
    )


def test_allowlist_has_no_stale_entries():
    """Every allowlisted name still exists in the registry (catches renames/removals)."""
    stale = [n for n in READ_ONLY_ALLOWLIST if n not in TOOL_REGISTRY]
    assert not stale, f"READ_ONLY_ALLOWLIST references tools no longer in the registry: {sorted(stale)}"
