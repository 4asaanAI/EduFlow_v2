"""Deferred tool loading - stop paying for 134 tool schemas on every turn.

Measured on 2026-08-08: an owner or principal turn shipped ~14,600 tokens of tool
schemas BEFORE the person had typed anything. Every turn, whether they asked about
fees or said "thanks". Accountants paid ~5,200, management ~12,200.

The fix is the pattern coding agents use on large tool sets: advertise a small CORE of
genuinely everyday tools in full, plus one `search_tools` tool, and reduce everything
else to a bare name in the prompt. When the model needs a deferred tool it searches for
it, gets the real schema back, and the tool becomes callable for the rest of the turn.

**This is a cost optimisation and NOTHING else.** It changes what the model is shown,
never what the caller may do: `is_tool_authorized` remains the only authorization gate,
is unchanged, and still runs at dispatch. A deferred tool is not a forbidden tool - it
is one whose instructions arrive on demand. Searching never widens access: the catalogue
and the search results are both filtered by the caller's own authorization first.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

# Kill switch. Set EDUFLOW_TOOL_SEARCH=0 to advertise everything again, instantly,
# without a deploy - the behaviour this replaces is one env var away.
def enabled() -> bool:
    return os.environ.get("EDUFLOW_TOOL_SEARCH", "1") not in ("0", "false", "False")


# Tools worth their tokens on every turn: the things people actually ask for daily, plus
# the search tool itself. Deliberately short - every name here is paid for on every turn
# by every user of that role. Anything seasonal or specialist belongs in the deferred
# set, one search away.
CORE_TOOL_NAMES = frozenset({
    "search_tools",
    # The daily rhythm of a school.
    "get_daily_brief",
    "get_school_pulse",
    "get_student_profile",
    "get_student_database",
    "search_students",
    "get_class_list",
    "get_attendance_overview",
    "mark_attendance",
    "get_fee_summary",
    "get_fee_defaulters",
    "record_fee_payment",
    "get_staff_list",
    "get_leave_requests",
    "approve_leave",
    "get_timetable",
    "create_announcement",
    "draft_document",
    "get_smart_alerts",
    # Sending to families is high-stakes and frequently asked for by name; keeping it
    # core means Flo can never "forget" it exists mid-conversation.
    "send_parent_message",
    "get_messaging_status",
})

# Words that should pull a tool up even though they do not appear in its name.
_SYNONYMS = {
    "message": ("send_parent_message", "draft_parent_message", "create_announcement"),
    "whatsapp": ("send_parent_message", "get_message_templates", "submit_whatsapp_template"),
    "sms": ("send_parent_message", "get_messaging_status"),
    "parent": ("send_parent_message", "draft_parent_message"),
    "salary": ("disburse_salary", "upsert_salary_structure"),
    "payroll": ("disburse_salary", "upsert_salary_structure"),
    "bus": ("get_transport_status", "update_transport_route", "add_transport_vehicle"),
    "transport": ("get_transport_status", "update_transport_route"),
    "exam": ("get_exam_results_summary",),
    "marks": ("get_exam_results_summary",),
    "admission": ("get_admissions_pipeline", "get_enquiries"),
    "enquiry": ("get_enquiries", "update_enquiry_status"),
    "expense": ("get_expenses", "update_expense"),
    "library": ("get_library_status",),
    "house": ("get_house_standings", "award_house_points"),
    "certificate": ("draft_document",),
    "visitor": ("log_visitor",),
    "complaint": ("query_incidents", "update_incident_status"),
    "incident": ("query_incidents", "update_incident_status"),
    # Release 2 audit, 2026-08-12. The office calls the school's four named concessions
    # "discounts", and the ranking is name-weighted, so "the employee discount" was
    # putting `apply_discount` first. That tool types a figure in by hand and would be
    # wrong the next quarter, which is the whole reason the concessions were built as
    # rules. These entries point the everyday words at the tool that recomputes.
    "concession": ("set_student_concession", "explain_student_fee",
                   "record_admission_concession"),
    "sibling": ("set_student_concession", "explain_student_fee"),
    "employee": ("set_student_concession",),
    "rte": ("set_right_to_education", "explain_student_fee"),
    "fine": ("calculate_late_fine",),
    "late": ("calculate_late_fine",),
    "overdue": ("calculate_late_fine", "get_fee_defaulters"),
}

_WORD_RE = re.compile(r"[a-z0-9]+")


def _words(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def core_names() -> frozenset:
    return CORE_TOOL_NAMES


def is_core(tool_name: str) -> bool:
    return tool_name in CORE_TOOL_NAMES


def deferred_names(authorized_names: List[str]) -> List[str]:
    """The authorized tools NOT advertised in full this turn."""
    return sorted(n for n in authorized_names if n not in CORE_TOOL_NAMES)


def catalogue_block(authorized_names: List[str]) -> str:
    """The compact deferred-tool listing embedded in the system prompt.

    Names only. A one-line description each would be clearer but costs roughly what
    this whole mechanism saves - the names are descriptive enough for the model to
    know what to search for, which is all this needs to do.
    """
    names = deferred_names(authorized_names)
    if not names:
        return ""
    return (
        "\n\nADDITIONAL TOOLS (names only - schemas not loaded).\n"
        "To use any of these you MUST first call `search_tools` to fetch its schema; "
        "it then becomes callable for the rest of this conversation. Do NOT guess a "
        "deferred tool's parameters, and do NOT tell the person a capability is "
        "missing just because it is listed here - searching takes one step.\n"
        + ", ".join(names)
    )


def rank(query: str, tool_defs: Dict[str, Dict[str, Any]], limit: int = 8) -> List[str]:
    """Rank authorized tools against a query. Returns tool names, best first.

    Supports three query forms, mirroring how coding agents do this:
      * ``select:a,b,c`` - exact names, no ranking (the model already knows what it wants)
      * ``+fee reminder`` - require "fee" in the name, rank the rest by the other words
      * ``fee reminder``  - plain keyword ranking
    """
    q = (query or "").strip()
    if not q:
        return []

    if q.lower().startswith("select:"):
        wanted = [n.strip() for n in q.split(":", 1)[1].split(",") if n.strip()]
        return [n for n in wanted if n in tool_defs][:limit]

    required: Optional[str] = None
    if q.startswith("+"):
        parts = q[1:].split(None, 1)
        required = parts[0].lower()
        q = parts[1] if len(parts) > 1 else ""

    terms = _words(q)
    scored = []
    for name, tdef in tool_defs.items():
        if required and required not in name.lower():
            continue
        haystack_name = name.lower()
        haystack_desc = (tdef.get("description") or "").lower()
        score = 0
        for t in terms:
            if t in haystack_name:
                score += 10
            # A whole-word hit in the description is worth more than a substring, so
            # "fee" does not rank every tool containing "coffee"-like fragments.
            if re.search(rf"\b{re.escape(t)}\b", haystack_desc):
                score += 4
            elif t in haystack_desc:
                score += 1
            for syn_tool in _SYNONYMS.get(t, ()):
                if syn_tool == name:
                    score += 8
        if required and not terms:
            score = max(score, 1)
        if score > 0:
            scored.append((score, name))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [name for _, name in scored[:limit]]
