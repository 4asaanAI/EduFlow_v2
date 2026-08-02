"""
Role-to-tool mapping configuration.

This is the single place to review or adjust which tools each role receives
in the LLM tool list. The base mapping is derived automatically from
TOOL_REGISTRY roles[] — this file adds:
  1. A readable view of what each role sees
  2. EXCLUDE_FOR_ROLE — remove specific tools per role without touching TOOL_REGISTRY
  3. get_tool_names_for_role() — used by _build_llm_tools() in routes/chat.py

To add a new tool: add it to TOOL_REGISTRY in tool_functions_v2.py with the
correct roles[]. It will appear here automatically. If you want to hide it from
a role's LLM tool list despite the registry entry, add it to EXCLUDE_FOR_ROLE.

PARENT ROLE NOTE: No parent-facing tools are registered yet. When parent tools
are added to TOOL_REGISTRY, add "parent" to their roles[] and they will appear
automatically.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Tool exclusions per role
# Add a tool name here to hide it from a role's LLM advertised list even if
# TOOL_REGISTRY.roles[] includes that role. The tool remains in the registry
# (it can still be called via keyword detection), it just won't be offered to
# the model for autonomous selection on every turn.
#
# Use this to reduce payload size for high-tool-count roles like owner/admin.
# Common candidates: rarely-used destructive tools, high-impact config tools
# that should only be accessed via explicit UI flows.
# ---------------------------------------------------------------------------
EXCLUDE_FOR_ROLE: dict[str, set[str]] = {
    # Owner gets 107 tools by default — way over Groq's 8k TPM free-tier limit.
    # Keep the ~34 highest-value CHAT tools; exclude the rest (they remain in the
    # registry and still fire via keyword detection and UI panels).
    # To reinstate a tool in chat, remove it from this set.
    "owner": {
        # Branch/school settings — done in Settings panel
        "create_branch", "update_branch", "delete_branch", "update_school_settings",
        # Academic structure — done in Academic Structure panel
        "create_class", "update_class", "delete_class",
        "create_house", "update_house", "delete_house",
        # Fee settings — done in Fee Structures panel
        "create_fee_structure", "update_fee_structure",
        "create_discount_type", "update_discount_type", "delete_discount_type",
        "apply_discount", "correct_fee_transaction", "delete_fee_transaction",
        # Staff mgmt details — rarely typed in chat
        "update_staff", "create_asset", "update_asset", "delete_asset",
        # Transport — UI panel
        "add_transport_vehicle", "create_transport_route",
        "update_transport_route", "delete_transport_route", "get_transport_status",
        # Visitor log — front-desk UI action
        "log_visitor", "checkout_visitor", "delete_visitor",
        # Ticket/query workflow — support staff actions
        "create_query_ticket", "assign_query_ticket", "resolve_query_ticket",
        "reopen_query_ticket", "delete_query_ticket", "assign_followup",
        # Approval/decision workflow — notification-driven
        "decide_approval_request", "decide_announcement", "decide_certificate",
        "confirm_resolution",
        # Certificates — issued from certificate panel
        "create_certificate",
        # Attendance corrections — rare, done via panel
        "correct_attendance", "mark_staff_attendance",
        # Thread/contact ops — staff actions
        "add_thread_entry", "log_contact_event",
        # Rare owner operations
        "year_end_transition", "trigger_fee_sync", "get_fee_sync_status",
        # Misc seldom-used in chat
        "get_today_class_attendance", "get_house_details",
        "get_student_council", "get_inventory_status", "get_library_status",
        "get_upcoming_events",
        "query_maintenance_requests", "query_staff_availability",
        "update_enquiry_status", "update_incident_status",
        "delete_announcement", "delete_expense",
        "reopen_query_ticket", "initiate_substitution",
        "set_student_status", "manage_student_guardians",
        "draft_parent_message", "create_incident",
        "award_house_points", "get_timetable",
        # Redundant with get_school_pulse / get_fee_summary
        "get_daily_brief", "get_financial_report",
        # Less common in daily chat
        "query_audit_log", "get_exam_results_summary", "create_enquiry",
        # Heavy write schemas — done via panels, not chat (frees ~800 tokens)
        "create_staff", "update_student", "update_expense", "create_expense",
        "mark_attendance",
        # Additional reductions for Groq 8k free-tier fit
        "create_student",   # admissions done in Admissions panel (276 tokens)
        "get_expenses",     # expense summary done in Finance panel (90 tokens)
        "query_incidents",  # incident mgmt done in Operations panel (67 tokens)
    },
    "admin": set(),
    "teacher": set(),
    "student": set(),
    "parent": set(),  # no parent tools registered yet
}


def get_tool_names_for_role(role: str, sub_category: str | None = None) -> set[str]:
    """Return the set of tool names this role is eligible to receive in the LLM payload.

    Applies:
      - role membership (role in tdef["roles"])
      - admin sub_category filtering (admin with sub_category only gets tools
        that either have no sub_categories restriction OR include their sub_category)
      - EXCLUDE_FOR_ROLE overrides

    NOTE: Phase-1 lockdown (write tools restricted to owner+principal) is still
    applied downstream by _build_llm_tools -> _is_tool_authorized. This function
    is a pre-filter, not the final authority.
    """
    # Import inside the function to avoid circular-import at module level
    # (tool_functions_v2 imports many services; importing at the top of this
    # config module would pull in the entire service layer at startup).
    from ai.tool_functions_v2 import TOOL_REGISTRY

    excluded = EXCLUDE_FOR_ROLE.get(role, set())
    result: set[str] = set()

    for name, tdef in TOOL_REGISTRY.items():
        if name in excluded:
            continue
        if role not in tdef.get("roles", []):
            continue
        # For admin with a known sub_category: skip tools that require a
        # different sub_category (same logic as is_tool_authorized, without
        # the Phase-1 lockdown which is handled separately).
        sub_categories = tdef.get("sub_categories")
        if sub_categories is not None and role == "admin":
            if sub_category not in sub_categories:
                continue
        result.add(name)

    return result
