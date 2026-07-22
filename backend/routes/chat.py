from __future__ import annotations

"""
Chat routes — conversation CRUD + SSE streaming message handler

Handles:
  - Conversation CRUD (list, create, update, delete, get messages)
  - SSE streaming chat with tool detection, execution, and response generation
  - Thinking events for frontend progress indication
  - Scope enforcement per user role
  - Content filtering (especially for students)
  - Confirm-action flow for write operations
  - Navigate events for "open X" commands
  - Multi-tool chaining (up to 3 rounds)
  - LLM parameter extraction with entity resolution
"""
import json
import asyncio
import base64
import random
import re
import time
import uuid
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from database import get_db
from models.schemas import (
    Conversation,
    Message,
    ConversationUpdate,
    ConversationBulkDelete,
    CONVERSATION_BULK_DELETE_MAX,
)
from ai.llm_client import llm_client, AI_UNAVAILABLE_MESSAGE
from ai.prompts import build_system_prompt
from ai.context_builder import build_school_context, detect_language
from ai.tool_functions_v2 import TOOL_REGISTRY, WRITE_TOOL_NAMES, openai_tool_schema
from ai.scope_resolver import resolve_scope, Scope
from ai.tool_access import is_tool_authorized
from ai.content_filter import filter_response, check_input_safety
from ai.redaction import redact_for_llm
from middleware.auth import get_current_user, require_owner
from services.token_service import check_and_reserve_tokens, record_usage
from services.confirm_tokens import (
    issue_confirm_token,
    consume_confirm_token,
    peek_confirm_token,
    audit_ai_dispatch,
    audit_ai_dispatch_pending,
    audit_ai_dispatch_finalize,
    audit_ai_rate_limit_hit,
)
from services.ai_rate_limiter import increment_and_check as _ai_rate_check, decrement_count as _ai_rate_decrement
from services.ai_action_policy import is_action_authorized_phase1
from services.memory import chat_integration as chat_memory
from services.ai_kill_switch import ai_writes_enabled
from services.ai_shadow_mode import ai_dry_run_enabled
from services.ai_metrics import record_ai_metric
from services.audit_service import write_audit
from tenant import get_school_id, scoped_filter
from ai import plan_executor
from ai.plan_executor import (
    PlanStaleError,
    NeedsManualReconciliationError,
    SagaCompensatedError,
    PlanScopeViolationError,
    StepExecutionError,
)
from database import TransactionUnavailableError
from ai.plan_schema import single_write_plan, plan_from_steps
from ai import planner as ai_planner


class RateLimitExceeded(Exception):
    """Raised when the confirm dispatch rate limiter rejects a request.

    Caught at the route handler boundary and converted to a 429 JSONResponse
    with the `Retry-After` header. We use an exception (rather than returning
    a sentinel) so the dispatch helper retains a single happy-path signature.
    """

    def __init__(self, payload: dict, retry_after: int):
        super().__init__(payload.get("error", "rate_limit_exceeded"))
        self.payload = payload
        self.retry_after = retry_after

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ─── Constants ────────────────────────────────────────────────────────────────

# R1.3 Turn Completion Contract: a user turn can NEVER end with nothing on screen.
# Any turn that would otherwise finish empty (LLM produced no content, all tool
# rounds dead-ended, content-policy boilerplate stripped, etc.) substitutes this
# text — streamed and persisted like any real answer — instead of a silent blank.
FALLBACK_TEXT = "I wasn't able to produce an answer for that. Please try again or rephrase."

MAX_TOOL_ROUNDS = 3  # AD2/FR5: bounds planning/read iterations ONLY (not confirmed writes)
MAX_PLAN_STEPS = ai_planner.MAX_PLAN_STEPS  # AD2/FR5: bounds plan SIZE
KEEPALIVE_INTERVAL = 5  # seconds — keep short for fast disconnect detection
LLM_WALLCLOCK_BUDGET = 90  # seconds; bounded ceiling above per-call 45s timeout
CHAR_BUDGET = 24000
HISTORY_LIMIT = 20
HISTORY_KEEP_FIRST = 2
HISTORY_KEEP_RECENT = 10
THINKING_DELAY_MIN = 0.15  # 150ms
THINKING_DELAY_MAX = 0.30  # 300ms

# Tools that require user confirmation before execution
WRITE_ACTION_TOOLS = set(WRITE_TOOL_NAMES)

# F.10/FR42: destructive (delete) tools require a SECOND explicit acknowledgment
# beyond the plan-confirm, and write an actor-tagged deletion audit row. Derived
# from the registry `destructive` flag; Epics J/K register the actual delete tools.
DESTRUCTIVE_TOOL_NAMES = {
    name for name, tool in TOOL_REGISTRY.items() if tool.get("destructive")
}

# F.10: student hard-delete / DPDP-erase are NEVER exposed to the assistant — they
# stay UI-only. These names are refused outright even if a future planner emits one.
FORBIDDEN_AI_TOOLS = {
    "delete_student",
    "erase_student",
    "dpdp_erase_student",
    "hard_delete_student",
}

# E.6: deep-link target panel per tool, used when the assistant cannot complete
# a job and must hand the user off to the matching UI panel.
_TOOL_DEEP_LINKS = {
    "record_fee_payment": "fees",
    "apply_discount": "fees",
    "approve_leave": "staff",
    "initiate_substitution": "staff",
    "mark_attendance": "attendance",
    "correct_attendance": "attendance",
    "award_house_points": "houses",
    "create_announcement": "announcements",
    "log_contact_event": "students",
    "update_incident_status": "incidents",
    "assign_followup": "incidents",
    "add_thread_entry": "incidents",
    "confirm_resolution": "incidents",
    "decide_approval_request": "approvals",
    "correct_fee_transaction": "fees",
    "delete_fee_transaction": "fees",
    "trigger_fee_sync": "fees",
    "mark_staff_attendance": "attendance",
    "decide_announcement": "announcements",
    "delete_announcement": "announcements",
}

WRITE_TOOL_REQUIRED_PARAMS = {
    "assign_followup": ("record_id", "assignee_staff_id", "due_date", "note"),
    "update_incident_status": ("record_id", "new_status", "note"),
    "add_thread_entry": ("record_id", "content"),
    "initiate_substitution": ("absent_staff_id", "substitute_staff_id", "class_id", "period_id"),
    "correct_attendance": ("record_id", "correction_type", "reason"),
    "log_contact_event": ("student_id", "contact_type", "outcome", "note"),
    "apply_discount": ("student_id", "discount_type_id", "effective_from"),
    "decide_approval_request": ("request_id", "decision", "reason"),
    "confirm_resolution": ("request_id", "confirmation_note"),
    "record_fee_payment": ("student_id", "amount", "fee_head", "mode"),
    "mark_attendance": ("class_id", "attendance"),
    "approve_leave": ("leave_id", "action"),
    "award_house_points": ("student_name", "points"),
    "create_announcement": ("title", "content"),
    # Epic J — student & staff CRUD
    "create_student": ("name", "class_id"),
    "update_student": ("student_id",),
    "set_student_status": ("student_id", "status"),
    "manage_student_guardians": ("student_id", "guardians"),
    "create_staff": ("name", "staff_type"),
    "update_staff": ("staff_id",),
    # Epic K.1 — fee-config CRUD
    "create_fee_structure": ("name",),
    "update_fee_structure": ("structure_id",),
    "create_discount_type": ("name", "value", "value_type", "recurrence", "reason_note"),
    "update_discount_type": ("discount_type_id",),
    "delete_discount_type": ("discount_type_id",),
    # Epic K.2 — academic-structure CRUD
    "create_class": ("name",),
    "update_class": ("class_id",),
    "delete_class": ("class_id",),
    "create_house": ("name",),
    "update_house": ("house_id",),
    "delete_house": ("house_id",),
    # Epic K.3 — org-config CRUD
    "create_branch": ("name",),
    "update_branch": ("branch_id", "name"),
    "delete_branch": ("branch_id",),
    "update_school_settings": (),
    "year_end_transition": ("new_year_name",),
    # Drift-gate remediation — operations tools added post-Phase-1 (ff2e929)
    "create_expense": ("category", "amount"),
    "create_enquiry": ("student_name",),
    "update_enquiry_status": ("enquiry_id", "status"),
    "create_incident": ("description",),
    # Owner coverage gap-close — expenses edit/delete, staff attendance, fee txn, fee sync
    "update_expense": ("expense_id",),
    "delete_expense": ("expense_id",),
    "mark_staff_attendance": (),
    "correct_fee_transaction": ("transaction_id", "reason"),
    "delete_fee_transaction": ("transaction_id",),
    "trigger_fee_sync": (),
    # Wave 2 — assets, visitors, certificates, query tickets, transport, announcement moderation
    "create_asset": ("name",),
    "update_asset": ("asset_id",),
    "delete_asset": ("asset_id",),
    "log_visitor": ("visitor_name",),
    "checkout_visitor": ("visitor_id",),
    "delete_visitor": ("visitor_id",),
    "create_certificate": ("student_id",),
    "decide_certificate": ("cert_id", "decision"),
    "create_query_ticket": ("title", "description", "priority"),
    "resolve_query_ticket": ("ticket_id",),
    "reopen_query_ticket": ("ticket_id",),
    "assign_query_ticket": ("ticket_id", "assigned_to"),
    "delete_query_ticket": ("ticket_id",),
    "create_transport_route": ("route_name",),
    "update_transport_route": ("route_id",),
    "delete_transport_route": ("route_id",),
    "add_transport_vehicle": ("vehicle_number",),
    "decide_announcement": ("announcement_id", "decision"),
    "delete_announcement": ("announcement_id",),
}

WRITE_TOOL_PARAM_LABELS = {
    "record_id": "record",
    "assignee_staff_id": "assignee",
    "due_date": "due date",
    "note": "note",
    "new_status": "new status",
    "content": "content",
    "absent_staff_id": "absent teacher",
    "substitute_staff_id": "substitute teacher",
    "period_id": "period",
    "correction_type": "correction",
    "contact_type": "contact type",
    "outcome": "outcome",
    "discount_type_id": "discount type",
    "effective_from": "effective date",
    "request_id": "request",
    "decision": "decision",
    "confirmation_note": "confirmation note",
    "student_id": "student",
    "student_name": "student",
    "amount": "amount",
    "fee_head": "fee head",
    "mode": "payment mode",
    "class_id": "class",
    "attendance": "attendance list",
    "leave_id": "leave request",
    "action": "approve or reject",
    "house_name": "house",
    "points": "points",
    "reason": "reason",
    "title": "announcement title",
    # NOTE: "content" is defined once above (generic label) — do not redefine per tool.
    # Epic J — student & staff CRUD
    "name": "name",
    "status": "status",
    "guardians": "guardians",
    "staff_type": "staff type",
    "staff_id": "staff member",
    # Epic K.1 — fee-config CRUD
    "structure_id": "fee structure",
    "value": "discount value",
    "value_type": "discount value type",
    "recurrence": "recurrence",
    "reason_note": "reason note",
    # Epic K.2 — academic-structure CRUD
    "section": "section",
    "house_id": "house",
    "colour": "colour",
    # Epic K.3 — org-config CRUD
    "branch_id": "branch",
    "new_year_name": "new academic year",
    # Operations + fee-record tools
    "category": "expense category",
    "expense_id": "expense",
    # NOTE: "student_name" is defined once above ("student") — do not redefine.
    "enquiry_id": "enquiry",
    "description": "description",
    "transaction_id": "fee transaction",
    # Wave 2
    "asset_id": "asset",
    "visitor_name": "visitor name",
    "visitor_id": "visitor entry",
    "cert_id": "certificate",
    "ticket_id": "ticket",
    "assigned_to": "assignee",
    "route_name": "route name",
    "route_id": "transport route",
    "vehicle_number": "vehicle number",
    "announcement_id": "announcement",
    "priority": "priority",
}

# ─── Keyword → Tool Map ──────────────────────────────────────────────────────

KEYWORD_TOOL_MAP = [
    # School pulse
    (["/school-pulse", "school status", "school pulse", "today's status",
      "today's overview", "school overview", "how is school", "pulse",
      "aaj ka status", "school ka status"], "get_school_pulse"),
    # Daily brief
    (["/daily-brief", "daily brief", "morning summary", "morning brief",
      "aaj ka haal", "morning status", "what happened today",
      "today's summary"], "get_daily_brief"),
    # Fee collection / summary
    (["/fee-collection", "/fee-summary", "fee defaulter", "fee summary",
      "fee collection", "who owes", "overdue fee", "pending fee",
      "collect fee", "fee ke baare mein"], "get_fee_summary"),
    # Staff status
    (["/staff-tracker", "/leave-manager", "staff absent", "staff status",
      "staff tracker", "who is absent", "which staff", "staff attendance",
      "leave request", "pending leave", "staff ki leave"], "get_staff_status"),
    # Attendance overview
    (["/attendance-overview", "attendance trend", "attendance overview",
      "attendance report", "how is attendance",
      "attendance kaisi hai"], "get_attendance_overview"),
    # Alerts
    (["/smart-alerts", "smart alert", "active alert", "flag", "exception",
      "koi dikkat"], "get_smart_alerts"),
    # Financial
    (["/financial-reports", "financial report", "financial summary",
      "revenue", "expense", "paisa", "finance"], "get_financial_report"),
    # Students search
    (["/student-database", "search student", "find student", "student named",
      "which student", "student dhundo"], "search_students"),
    # Fee transactions
    (["/fee-tracker", "fee transaction", "payment history", "who paid",
      "payment record"], "get_fee_transactions"),
    # Leave approval
    (["approve leave", "reject leave", "leave approve"], "approve_leave"),
    # Enquiries
    (["/admission-funnel", "/enquiry-register", "enquiry",
      "admission funnel", "new student inquiry",
      "admission"], "get_enquiries"),
    # Health report
    (["/health-report", "/ai-health-report", "health report",
      "school health", "health score"], "get_smart_alerts"),
    # ── NEW keyword entries ──
    # Student database
    (["student database", "all students", "student list"], "get_student_database"),
    # Fee structure
    (["fee structure", "class fees", "annual fee"], "get_fee_structures"),
    # Class-wise attendance
    (["class attendance", "class wise attendance"], "get_class_wise_attendance"),
    # Pending leaves
    (["pending leaves", "leave requests", "leave status"], "get_leave_requests"),
    # Staff list
    (["staff list", "all teachers", "all staff",
      "teacher list"], "get_staff_list"),
    # Class list
    (["class list", "all classes", "class teacher"], "get_class_list"),
    # Fee defaulters
    (["fee defaulters", "defaulters list",
      "who hasn't paid"], "get_fee_defaulters"),
    # Student profile
    (["student profile", "student details"], "get_student_profile"),
    # House standings
    (["house standings", "house points",
      "which house is leading"], "get_house_standings"),
    # My class students (teacher)
    (["my class students", "my students"], "get_my_class_students"),
    # Today class attendance
    (["today's class attendance", "mark attendance"], "get_today_class_attendance"),
    # Library
    (["library books", "overdue books", "book issue"], "get_library_status"),
    # Transport
    (["transport", "bus route", "bus status"], "get_transport_status"),
    # Inventory
    (["inventory", "school items", "stock"], "get_inventory_status"),
    # Parent complaints / incidents / grievances
    (["parent complaint", "parent grievance", "open complaint", "open issue",
      "pending grievance", "unresolved complaint", "visitor log",
      "incident report", "complaint status"], "query_incidents"),
    # Staff list (broader keywords)
    (["staff directory", "all teachers", "teacher directory",
      "show staff", "list staff"], "get_staff_list"),
    # ── CRUD keyword entries ──
    # Create student
    (["add student", "create student", "new student", "enroll student",
      "admit student", "register student", "naya student",
      "student add karo"], "create_student"),
    # Update student
    (["update student", "edit student", "change student name",
      "student ka naam", "student transfer", "move student to class",
      "student class change"], "update_student"),
    # Student status
    (["withdraw student", "deactivate student", "mark student withdrawn",
      "tc student", "issue tc", "student status change"], "set_student_status"),
    # Guardian update
    (["update guardian", "change parent number", "guardian contact",
      "parent phone change", "update parent"], "manage_student_guardians"),
    # Create staff
    (["add staff", "create staff", "new teacher", "hire teacher",
      "hire staff", "add teacher", "naya teacher", "add employee"], "create_staff"),
    # Update staff
    (["update staff", "edit staff", "change staff", "staff details update",
      "teacher profile update"], "update_staff"),
    # Fee structure
    (["create fee structure", "add fee structure", "new fee structure",
      "fee structure banao"], "create_fee_structure"),
    (["update fee structure", "edit fee structure",
      "change fee structure"], "update_fee_structure"),
    # Discount
    (["create discount", "add discount", "new discount type",
      "sibling discount", "merit discount"], "create_discount_type"),
    # Class management
    (["create class", "add class", "new class", "naya class",
      "add section"], "create_class"),
    (["update class", "edit class", "change class teacher",
      "class teacher assign"], "update_class"),
    # House management
    (["create house", "add house", "new house"], "create_house"),
    (["update house", "edit house", "rename house"], "update_house"),
    # Branch management
    (["create branch", "add branch", "new branch"], "create_branch"),
    (["update branch", "edit branch", "branch details"], "update_branch"),
    # School settings
    (["update school settings", "school name change", "change school name",
      "update school name", "school board change"], "update_school_settings"),
    # Incident management
    (["assign followup", "assign follow up", "assign complaint",
      "follow up assign karo"], "assign_followup"),
    (["update incident", "close incident", "resolve complaint",
      "incident status"], "update_incident_status"),
    # Attendance correction
    (["correct attendance", "attendance correction",
      "fix attendance", "attendance mistake"], "correct_attendance"),
    # Dashboard query
    (["dashboard summary", "all open issues", "pending approvals",
      "summary of everything"], "query_dashboard_summary"),
    # Audit log
    (["/audit-log", "audit log", "who changed what",
      "system log", "activity log"], "query_audit_log"),
    # Expenses
    (["show expenses", "list expenses", "expenses this month",
      "expense summary", "kitna kharch hua", "kharch dekho"], "get_expenses"),
    (["add expense", "create expense", "log expense", "new expense",
      "record expense", "kharch add karo", "expense daalo"], "create_expense"),
    # Enquiry CRUD
    (["add enquiry", "create enquiry", "new enquiry", "new admission enquiry",
      "add admission lead", "enquiry add karo", "naya enquiry"], "create_enquiry"),
    (["update enquiry", "enquiry status", "move enquiry", "advance enquiry",
      "enquiry ko contacted", "enquiry enrolled", "mark enquiry"], "update_enquiry_status"),
    # Incident logging
    (["log incident", "create incident", "new incident", "report incident",
      "incident log karo", "add incident", "file complaint",
      "log complaint"], "create_incident"),
]

# ─── Navigate Map ─────────────────────────────────────────────────────────────

NAVIGATE_MAP = {
    "open student database": "student-database",
    "show student database": "student-database",
    "go to student database": "student-database",
    "open fee collection": "fee-collection",
    "show fee collection": "fee-collection",
    "go to fee collection": "fee-collection",
    "open attendance": "attendance-recorder",
    "show attendance": "attendance-recorder",
    "go to attendance": "attendance-recorder",
    "open attendance recorder": "attendance-recorder",
    "open staff tracker": "staff-tracker",
    "show staff tracker": "staff-tracker",
    "open leave manager": "leave-manager",
    "show leave manager": "leave-manager",
    "open fee tracker": "fee-tracker",
    "show fee tracker": "fee-tracker",
    "open admission funnel": "admission-funnel",
    "show admission funnel": "admission-funnel",
    "open enquiry register": "enquiry-register",
    "show enquiry register": "enquiry-register",
    "open smart alerts": "smart-alerts",
    "show smart alerts": "smart-alerts",
    "open financial reports": "financial-reports",
    "show financial reports": "financial-reports",
    "open school pulse": "school-pulse",
    "show school pulse": "school-pulse",
    "open daily brief": "daily-brief",
    "show daily brief": "daily-brief",
    "open settings": "settings",
    "open profile": "profile",
    "open library": "library",
    "show library": "library",
    "open transport": "transport",
    "show transport": "transport",
    "open inventory": "inventory",
    "show inventory": "inventory",
    "open house points": "house-points",
    "show house points": "house-points",
    "open timetable": "timetable",
    "show timetable": "timetable",
    "open exam results": "exam-results",
    "show exam results": "exam-results",
    "open report cards": "report-cards",
    "show report cards": "report-cards",
    # Additional panel navigations
    "open audit log": "audit-log",
    "show audit log": "audit-log",
    "go to audit log": "audit-log",
    "open data import": "data-import",
    "show data import": "data-import",
    "open fee sync": "fee-sync",
    "show fee sync": "fee-sync",
    "open attendance overview": "attendance-overview",
    "show attendance overview": "attendance-overview",
    "open staff attendance": "staff-attendance-tracker",
    "show staff attendance": "staff-attendance-tracker",
    "open staff attendance tracker": "staff-attendance-tracker",
    "open fee defaulter": "smart-fee-defaulter",
    "show fee defaulter": "smart-fee-defaulter",
    "open defaulters": "smart-fee-defaulter",
    "open incident tracker": "incident-tracker",
    "show incident tracker": "incident-tracker",
    "open incidents": "incident-tracker",
    "open facility requests": "facility-requests",
    "show facility requests": "facility-requests",
    "open maintenance": "facility-requests",
    "open school activities": "school-activities",
    "show school activities": "school-activities",
    "open fee receipts": "fee-receipts",
    "show fee receipts": "fee-receipts",
    "open certificates": "certificate-generator",
    "show certificates": "certificate-generator",
    "open certificate generator": "certificate-generator",
    "open asset tracker": "asset-tracker",
    "show asset tracker": "asset-tracker",
    "open assets": "asset-tracker",
    "open form builder": "custom-form-builder",
    "show form builder": "custom-form-builder",
    "open parent messages": "parent-message",
    "show parent messages": "parent-message",
    "open admission pipeline": "admission-pipeline",
    "show admission pipeline": "admission-pipeline",
    "open staff leave manager": "staff-leave-manager",
    "show staff leave manager": "staff-leave-manager",
    "open staff performance": "staff-performance",
    "show staff performance": "staff-performance",
    "open timetable builder": "timetable-builder",
    "show timetable builder": "timetable-builder",
}


# ─── CRUD routes (unchanged) ─────────────────────────────────────────────────
# Note: get_current_user is imported from middleware.auth


def _owned_conversation_filter(conv_id: str, user: dict) -> dict:
    return scoped_filter({"id": conv_id, "user_id": user["id"]}, get_school_id())


async def _require_owned_conversation(db, conv_id: str, user: dict) -> dict:
    conv = await db.conversations.find_one(_owned_conversation_filter(conv_id, user))
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv

# Epic 6, Story 6.4: the server-side sort whitelist for the chat archive. An
# unrecognised value falls back to the default rather than reaching a query.
CONVERSATION_SORTS = {
    "recent": ("updated_at", -1),
    "oldest": ("updated_at", 1),
    "title": ("title", 1),
}
DEFAULT_CONVERSATION_SORT = "recent"
# The sidebar has always shown the newest 50 and still does when called bare.
DEFAULT_CONVERSATION_LIMIT = 50
MAX_CONVERSATION_LIMIT = 100
# Escaping a search term bounds what it MEANS, not what it COSTS: a 100 KB
# escaped literal is still a 100 KB pattern.
MAX_CONVERSATION_SEARCH = 200


@router.get("/conversations")
async def list_conversations(
    request: Request,
    page: int = 1,
    limit: int = DEFAULT_CONVERSATION_LIMIT,
    sort: str = DEFAULT_CONVERSATION_SORT,
    search: str = "",
):
    """List the caller's conversations.

    CALLED WITH NO ARGUMENTS BY THE SIDEBAR, which is on every screen. The
    defaults are therefore exactly what it received before this endpoint learned
    to page — the newest 50, most-recent first — and `meta` is added alongside
    rather than reshaping anything. A test pins that against the old behaviour.

    Everyone sees only their own conversations. That was put to the Owner on
    2026-07-23 and settled deliberately: cross-user visibility would be a new
    power over staff, and the owner-only `/conversations/{id}/trace` view already
    covers diagnosing a specific reported chat.
    """
    db = get_db()
    user = get_current_user(request)
    per_page = max(1, min(limit, MAX_CONVERSATION_LIMIT))
    skip = max(page - 1, 0) * per_page
    sort_field, sort_dir = CONVERSATION_SORTS.get(sort, CONVERSATION_SORTS[DEFAULT_CONVERSATION_SORT])

    # branch-scope: intentional — a conversation belongs to ONE user, and user_id
    # is strictly narrower than branch_id. Conversation documents carry no
    # branch_id field (models/schemas.py Conversation is school-scoped only), so
    # a branch clause here would match nothing and empty everyone's history.
    query = scoped_filter({"user_id": user["id"]}, get_school_id())
    term = (search or "").strip()[:MAX_CONVERSATION_SEARCH]
    if term:
        # re.escape or the term is a pattern: an injection surface, and a way to
        # hang the server on catastrophic backtracking.
        query["title"] = {"$regex": re.escape(term), "$options": "i"}

    total = await db.conversations.count_documents(query)
    convs = await db.conversations.find(query, {"_id": 0}).sort(
        sort_field, sort_dir
    ).skip(skip).limit(per_page).to_list(per_page)
    return {
        "success": True,
        "data": convs,
        "meta": {
            "page": page,
            "limit": per_page,
            "total": total,
            "sort": sort if sort in CONVERSATION_SORTS else DEFAULT_CONVERSATION_SORT,
            "max_bulk_delete": CONVERSATION_BULK_DELETE_MAX,
        },
    }


@router.post("/conversations/bulk-delete")
async def bulk_delete_conversations(body: ConversationBulkDelete, request: Request):
    """Delete several of the caller's own conversations in one request.

    Approved by the Owner on 2026-07-23 before it was built: deleting a chat
    already exists one at a time, so this is the same authority, faster. It is
    irreversible, which is why the screen makes the reader type the count.

    TWO THINGS HERE ARE LOAD-BEARING AND EASY TO "TIDY" AWAY:

    1. `body` is a Pydantic model, never `await request.json()`. See
       ConversationBulkDelete — untyped ids turn this into "delete everything".
    2. The MESSAGE delete uses `owned_ids` — what the ownership query actually
       returned — never `body.ids`. The messages filter carries no user_id; it is
       safe in the single-delete path only because ownership is proven one id at
       a time first. Passing the caller's raw list here would destroy another
       user's messages while leaving their conversation standing: a chat they can
       open and find empty, with nothing in any log to explain it.
    """
    db = get_db()
    user = get_current_user(request)
    school_id = get_school_id()

    # Deduplicated, so a caller repeating one id ten times is not told ten chats
    # were removed.
    requested = list(dict.fromkeys(body.ids))
    # branch-scope: intentional — pinned to the caller's own user_id, which is
    # narrower than branch; conversations carry no branch_id field.
    owned = await db.conversations.find(
        scoped_filter({"id": {"$in": requested}, "user_id": user["id"]}, school_id),
        {"_id": 0, "id": 1},
    ).to_list(len(requested))
    owned_ids = [c["id"] for c in owned]

    if owned_ids:
        # Conversations first: an orphaned message is invisible and harmless, a
        # conversation that outlives its messages is a chat that opens empty.
        # branch-scope: intentional — own user_id, as above.
        await db.conversations.delete_many(
            scoped_filter({"id": {"$in": owned_ids}, "user_id": user["id"]}, school_id)
        )
        # branch-scope: intentional — `owned_ids` are already proven to be this
        # caller's, which is what makes a filter with no user_id safe here. Same
        # reasoning as the single-delete path directly below.
        await db.messages.delete_many(
            scoped_filter({"conversation_id": {"$in": owned_ids}}, school_id)
        )

    # Ids only, never a title or any message text (NFR-S2).
    #
    # The ids go in `changes`, NOT in `entity_id`. `audit_logs` carries an index
    # on entity_id, and joining up to 100 UUIDs makes a ~3.6 KB indexed key — a
    # bulk action would quietly become the most expensive row in the log.
    await write_audit(
        db,
        action="conversation_bulk_delete",
        entity_id=user["id"],
        collection="conversations",
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=school_id,
        branch_id=user.get("branch_id") or "",
        changes={
            "deleted": len(owned_ids),
            "requested": len(requested),
            "conversation_ids": owned_ids,
        },
    )

    # An id that was not found and an id belonging to somebody else are reported
    # identically — from outside, they are indistinguishable.
    return {
        "success": True,
        "data": {"deleted": len(owned_ids), "not_found": len(requested) - len(owned_ids)},
    }


@router.post("/conversations")
async def create_conversation(request: Request):
    db = get_db()
    user = get_current_user(request)
    conv = Conversation(user_id=user["id"])
    await db.conversations.insert_one({**conv.dict(), "_id": conv.id})
    return {"success": True, "data": conv.dict()}


@router.patch("/conversations/{conv_id}")
async def update_conversation(conv_id: str, body: ConversationUpdate, request: Request):
    db = get_db()
    user = get_current_user(request)
    await _require_owned_conversation(db, conv_id, user)
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now().isoformat()
    await db.conversations.update_one(_owned_conversation_filter(conv_id, user), {"$set": update_data})
    return {"success": True}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, request: Request):
    db = get_db()
    user = get_current_user(request)
    await _require_owned_conversation(db, conv_id, user)
    await db.conversations.delete_one(_owned_conversation_filter(conv_id, user))
    await db.messages.delete_many(scoped_filter({"conversation_id": conv_id}, get_school_id()))
    return {"success": True}


@router.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str, request: Request):
    db = get_db()
    user = get_current_user(request)
    await _require_owned_conversation(db, conv_id, user)
    msgs = await db.messages.find(
        scoped_filter({"conversation_id": conv_id}, get_school_id()), {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return {"success": True, "data": msgs}


@router.get("/conversations/{conv_id}/trace")
async def conversation_trace(conv_id: str, request: Request, user: dict = Depends(require_owner)):
    """R11.5: per-turn diagnostic timeline for support — answers "did the user
    get a reply, and if not, why?" without server-log access (AC3).

    RBAC: owner-only, and school-scoped so an owner sees only their own school's
    conversations (AC2). CONFIDENTIALITY: the underlying provider/model is NEVER
    revealed to any client — every turn reports the assistant as "Layaa AI". The
    raw provider/model stays in the internal `ai_turn_traces` collection for
    platform operators / telemetry only.
    """
    db = get_db()
    traces = await db.ai_turn_traces.find(
        scoped_filter({"conversation_id": conv_id}, get_school_id()), {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    turns = []
    for t in traces:
        llm = t.get("llm") or {}
        turns.append({
            "message_id": t.get("message_id"),
            "created_at": t.get("created_at"),
            "outcome": t.get("outcome"),
            "language": t.get("language"),
            "tools": t.get("tools") or [],
            # Confidentiality: no Azure/OpenAI/model name — always "Layaa AI".
            "assistant": "Layaa AI",
            "finish_reason": llm.get("finish_reason"),
            "ok": llm.get("ok"),
            "error_type": llm.get("error_type"),
            "tokens": llm.get("tokens"),
        })
    return {
        "success": True,
        "data": turns,
        "meta": {"count": len(turns), "conversation_id": conv_id},
    }


# ─── Rich content extraction ─────────────────────────────────────────────────

def _extract_rich_content(text: str):
    """Extract <<<RICH_CONTENT>>>...<<<END>>> block from LLM response.

    Uses balance-aware _json_candidates instead of regex to correctly handle
    nested JSON objects that might confuse a greedy `.*?<<<END>>>` pattern.
    """
    marker = "<<<RICH_CONTENT>>>"
    idx = text.find(marker)
    if idx == -1:
        return text.strip(), None
    clean_text = text[:idx].strip()
    after_marker = text[idx + len(marker):]
    for candidate in _json_candidates(after_marker):
        try:
            rich = json.loads(candidate)
            if isinstance(rich, dict):
                return clean_text, rich
        except Exception:
            continue
    return text.strip(), None


# ─── Tool call JSON parser (BUG FIX #3: strip markdown fences) ───────────────

def _json_candidates(text) -> list[str]:
    """
    Return balanced JSON object/array candidates from model text.

    The model is instructed to output JSON only for tools, but in practice it
    may wrap JSON in fences or include prose. This scanner handles nested
    braces without relying on brittle regexes.
    """
    # Part 2 Patch P3 defense-in-depth: tolerate non-string input. Also cap
    # input size to avoid quadratic-ish scans on adversarial LLM output (H8).
    if not isinstance(text, str):
        return []
    if len(text) > 32000:
        text = text[:32000]
    cleaned = text.strip()
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    fenced = re.findall(fence_pattern, cleaned, re.DOTALL)
    scan_text = "\n".join(fenced) if fenced else cleaned

    candidates: list[str] = []
    starts = {"{": "}", "[": "]"}
    for idx, ch in enumerate(scan_text):
        if ch not in starts:
            continue
        expected_stack = [starts[ch]]
        in_string = False
        escape = False
        for pos in range(idx + 1, len(scan_text)):
            cur = scan_text[pos]
            if escape:
                escape = False
                continue
            if cur == "\\":
                escape = True
                continue
            if cur == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if cur in starts:
                expected_stack.append(starts[cur])
            elif expected_stack and cur == expected_stack[-1]:
                expected_stack.pop()
                if not expected_stack:
                    candidates.append(scan_text[idx:pos + 1])
                    break
    return candidates


def _tool_calls_to_candidates(tool_calls) -> list[dict]:
    """R11.2: map native `ToolCall`s to the internal {action, params, reason}
    shape the planner and tool-loop consume.

    Replaces the deleted JSON-in-text parsers (`_parse_tool_calls`/
    `_parse_tool_call`/`_normalize_tool_call`/`_strip_tool_json_from_text`). The
    model can no longer emit tool JSON in prose — tool calls arrive as structured
    `tool_calls` from the provider, so there is nothing to regex out of the text.
    """
    out: list[dict] = []
    for tc in (tool_calls or []):
        name = getattr(tc, "name", None)
        args = getattr(tc, "arguments", None)
        if not isinstance(name, str) or not name:
            continue
        out.append({
            "action": name,
            "params": args if isinstance(args, dict) else {},
            "reason": "",
            "confirm_requested": name in WRITE_ACTION_TOOLS,
            "id": getattr(tc, "id", "") or "",
        })
    return out


# ─── Tool authorization ───────────────────────────────────────────────────────

def _is_tool_authorized(user: dict, tool_def: dict) -> bool:
    """Check role + sub_category authorization against TOOL_REGISTRY definition.

    sub_categories: None means no sub_category restriction (any admin).
    sub_categories: [...] means admin must have a matching sub_category;
    non-admin roles that appear in roles[] are never blocked by sub_categories.

    The implementation moved to `ai/tool_access.py` in Epic 4 (Story 4.5) so the
    tool-panel endpoint enforces the SAME gate instead of its own weaker one. This
    wrapper stays so every call site and every test that patches
    `routes.chat._is_tool_authorized` keeps working unchanged.
    """
    return is_tool_authorized(user, tool_def)


def _close_tool_matches(name: str, user: dict, limit: int = 3) -> list:
    """R1.5: closest AUTHORIZED tool names to a mistaken/unknown tool name.

    Suggestions are filtered to tools the caller is actually allowed to use, so an
    'unknown capability' hint never leaks the existence of tools for other roles.
    """
    import difflib
    candidates = [
        tname for tname, tdef in TOOL_REGISTRY.items()
        if _is_tool_authorized(user, tdef)
    ]
    return difflib.get_close_matches(name or "", candidates, n=limit, cutoff=0.6)


def _build_llm_tools(user: dict, only: "set | None" = None) -> list:
    """R11.2: the native function-calling `tools` list for this caller.

    Only tools the caller is authorized for (role + sub_category + Phase-1
    lockdown) are advertised, so the provider can never let the model invoke a
    tool the caller can't use — the same gate that `_is_tool_authorized` applies
    at dispatch, now enforced at the model boundary too. Schemas come straight
    from TOOL_REGISTRY (single source, AC2).
    """
    tools = []
    for name, tdef in TOOL_REGISTRY.items():
        if only is not None and name not in only:
            continue
        if not _is_tool_authorized(user, tdef):
            continue
        required = WRITE_TOOL_REQUIRED_PARAMS.get(name, ())
        tools.append(openai_tool_schema(name, tdef, required))
    return tools


# ─── Keyword detection ────────────────────────────────────────────────────────

def detect_tool_from_keywords(text: str, user: dict) -> Optional[str]:
    """Detect which tool to call based on keywords in the user message."""
    text_lower = text.lower()
    for keywords, tool_name in KEYWORD_TOOL_MAP:
        if any(kw in text_lower for kw in keywords):
            tool_def = TOOL_REGISTRY.get(tool_name)
            if tool_def and _is_tool_authorized(user, tool_def):
                return tool_name
    return None


# ─── Navigate detection ──────────────────────────────────────────────────────

# Polite/filler lead-ins stripped before anchoring a navigation command, so
# "please open library" still navigates but "why can't we open library on Sundays"
# does not (the verb no longer leads the sentence).
_NAV_LEAD_INS = ("please ", "can you ", "could you ", "kindly ", "hey ", "hi ", "ok ", "okay ", "now ", "just ")


def detect_navigate(text: str) -> Optional[str]:
    """Detect if the user is issuing a navigation COMMAND (verb-led), not merely
    mentioning a panel name somewhere in a sentence (R7.3/AC3).

    Anchors on the navigation verb: the phrase must lead the message (after
    stripping polite lead-ins), rather than matching as a substring anywhere.
    """
    text_lower = text.lower().strip()
    # Strip a leading politeness/filler token (repeatedly, e.g. "hey can you ...").
    changed = True
    while changed:
        changed = False
        for lead in _NAV_LEAD_INS:
            if text_lower.startswith(lead):
                text_lower = text_lower[len(lead):].lstrip()
                changed = True
    for phrase, tool_id in NAVIGATE_MAP.items():
        # Prefix match anchored to the verb; allow exact or phrase-then-boundary.
        if text_lower == phrase or text_lower.startswith(phrase + " "):
            return tool_id
    return None


# ─── Thinking event helper ────────────────────────────────────────────────────

def thinking_event(step: str, message: str, tool: str = None, count: int = None) -> str:
    """Build a thinking SSE event."""
    data = {
        "type": "thinking",
        "step": step,
        "message": message,
        "ts": time.time(),
    }
    if tool:
        data["tool"] = tool
    if count is not None:
        data["count"] = count
    return f"data: {json.dumps(data)}\n\n"


# ─── Keepalive SSE event ─────────────────────────────────────────────────────

def keepalive_event() -> str:
    return 'data: {"type":"keepalive"}\n\n'


# ─── Token counting with null-check (BUG FIX #1) ────────────────────────────

def safe_token_count(tokens_from_api, fallback_text: str = "") -> int:
    """Return token count with fallback if API returns None."""
    if tokens_from_api is not None and isinstance(tokens_from_api, (int, float)):
        return int(tokens_from_api)
    # Fallback: rough estimate of 1 token per 4 characters
    if not isinstance(fallback_text, str):
        fallback_text = ""
    return max(1, len(fallback_text) // 4)


# ─── Conversation history trimming (BUG FIX #2) ──────────────────────────────

def _trim_history(messages: list[dict]) -> list[dict]:
    """
    Trim conversation history to fit within char budget.
    If total chars > CHAR_BUDGET, keep first HISTORY_KEEP_FIRST messages
    and most recent HISTORY_KEEP_RECENT messages.
    """
    if not messages:
        return messages

    total_chars = sum(len(m.get("content", "") or "") for m in messages)
    if total_chars <= CHAR_BUDGET:
        return messages

    # Keep first N and last M messages
    if len(messages) <= HISTORY_KEEP_FIRST + HISTORY_KEEP_RECENT:
        return messages

    first_msgs = messages[:HISTORY_KEEP_FIRST]
    recent_msgs = messages[-HISTORY_KEEP_RECENT:]
    trimmed = first_msgs + recent_msgs

    # If still too large, progressively drop the oldest from the recent set
    while len(trimmed) > HISTORY_KEEP_FIRST + 2:
        total = sum(len(m.get("content", "") or "") for m in trimmed)
        if total <= CHAR_BUDGET:
            break
        # Remove the message right after the preserved first messages
        trimmed.pop(HISTORY_KEEP_FIRST)

    # Part 2 Patch P2: if two oversize anchors alone still blow the budget,
    # truncate their content rather than shipping oversize to Azure (which
    # returns 400 → llm_client mis-maps to the content-policy message).
    total = sum(len(m.get("content", "") or "") for m in trimmed)
    if total > CHAR_BUDGET:
        anchor_budget = max(2000, CHAR_BUDGET // max(1, len(trimmed)))
        for m in trimmed[:HISTORY_KEEP_FIRST]:
            content = m.get("content", "") or ""
            if len(content) > anchor_budget:
                # Keep the tail — most recent context within the anchor.
                m["content"] = "[…truncated…] " + content[-anchor_budget:]

    return trimmed


# ─── Extract count from tool result ──────────────────────────────────────────

def _extract_result_count(result: dict) -> Optional[int]:
    """Record count from a tool result. R4.2: every registry tool now returns the
    single envelope, so `meta.count` is authoritative. A tiny legacy fallback
    remains only for any non-envelope dict that might reach here."""
    if not isinstance(result, dict):
        return None

    meta = result.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("count"), (int, float)):
        return int(meta["count"])

    # R7.3/AC4: count the envelope's own `data` list, never a stray first list
    # field (e.g. a nested "action_buttons" or a per-row list) which mis-counted.
    data = result.get("data")
    if isinstance(data, list):
        return len(data)

    # Legacy fallback (pre-envelope shapes) — retained defensively.
    for key in ("total", "count", "total_alerts", "total_defaulters",
                "total_staff", "total_students"):
        if key in result and isinstance(result[key], (int, float)):
            return int(result[key])
    for key, val in result.items():
        if isinstance(val, list) and key not in ("rich_blocks", "action_buttons"):
            return len(val)
    return None


# ─── Extract empty-result message (BUG FIX #6) ───────────────────────────────

def _extract_empty_message(result: dict) -> Optional[str]:
    """The context-aware message for an empty/denied/failed tool result. R4.2:
    read the single envelope — surface the message when the tool denied, failed,
    or returned zero records."""
    if not isinstance(result, dict):
        return None
    message = result.get("message")
    if not message:
        return None

    # Envelope: a denial/failure or a zero-count read carries a meaningful message.
    if result.get("denied") or result.get("success") is False:
        return message
    meta = result.get("meta")
    if isinstance(meta, dict) and meta.get("count") == 0:
        return message

    # Legacy fallback (pre-envelope shapes).
    for key, val in result.items():
        if isinstance(val, list) and len(val) == 0:
            return message
    for count_key in ("total", "count", "total_alerts", "total_defaulters"):
        if result.get(count_key) == 0:
            return message
    return None


# F.2/FR21: read tools that return individual minor (student) records. Every
# assistant read through one of these is audited (actor/target/purpose) so the
# school can demonstrate purpose-limited, traceable handling of children's data.
MINOR_READ_TOOLS = {
    "search_students",
    "get_fee_transactions",
    "get_fee_defaulters",
    "get_student_database",
    "get_student_profile",
    "get_my_class_students",
    "query_student_record",
    "draft_parent_message",
    "recall_history",
}


def _collect_student_refs(value: Any, acc: set, depth: int = 0) -> None:
    """Recursively collect student identifiers from a raw tool result."""
    if depth > 8 or len(acc) >= 200:
        return
    if isinstance(value, list):
        for item in value:
            _collect_student_refs(item, acc, depth + 1)
        return
    if isinstance(value, dict):
        for key, raw in value.items():
            kl = str(key).lower()
            if kl in ("student_id", "admission_number") and isinstance(raw, (str, int)):
                acc.add(str(raw))
            else:
                _collect_student_refs(raw, acc, depth + 1)


async def _audit_minor_read(db, user: dict, tool_name: str, raw_result: Any) -> None:
    """F.2/FR21: write an audit row for an assistant read of minor records.

    Fail-open (write_audit never raises). Target ids come from the RAW (pre-redaction)
    result; the audit row itself stores only ids/counts (no special-category PII).
    """
    if tool_name not in MINOR_READ_TOOLS:
        return
    refs: set = set()
    _collect_student_refs(raw_result, refs)
    if not refs:
        return
    ref_list = sorted(refs)
    await write_audit(
        db,
        action="minor_record_read",
        entity_id=ref_list[0],
        collection="students",
        changed_by=user.get("id", ""),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id") or "",
        changes={"student_refs": ref_list, "count": len(ref_list)},
        reason=f"ai_read:{tool_name}",
    )


def _token_meta_destructive_steps(token_meta: dict) -> list:
    """F.10: return the destructive step dicts of a peeked token (legacy or plan).

    A plan step is destructive if its `destructive` flag is set OR its tool is in
    DESTRUCTIVE_TOOL_NAMES. A legacy single-action token is destructive if its
    action tool is destructive.
    """
    plan_steps = token_meta.get("plan")
    out: list = []
    if plan_steps:
        for s in plan_steps:
            if s.get("destructive") or s.get("tool") in DESTRUCTIVE_TOOL_NAMES:
                out.append(s)
    else:
        action = token_meta.get("action")
        if action in DESTRUCTIVE_TOOL_NAMES:
            out.append({"idx": 0, "tool": action, "params": token_meta.get("params") or {}})
    return out


async def _audit_destructive_step(db, user: dict, step: dict) -> None:
    """F.10/FR42: actor-tagged deletion audit row — 'who deleted what, when'."""
    params = step.get("params") or {}
    target = (
        params.get("id")
        or params.get("target_id")
        or params.get("record_id")
        or step.get("tool", "")
    )
    await write_audit(
        db,
        action="delete",
        entity_id=str(target),
        collection=step.get("tool", "destructive"),
        changed_by=user.get("id", ""),
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id") or "",
        changes={
            "actor": user.get("id", ""),
            "actor_name": user.get("name", ""),
            "tool": step.get("tool"),
            "destructive": True,
        },
        reason="ai_destructive_action",
    )


def _safe_tool_result_for_chat(value: Any) -> Any:
    """
    Redact high-risk personal fields before storing tool traces or sending
    tool output back into the model for final narration.

    F.1: delegates to the canonical `ai.redaction.redact_for_llm` so the SAME
    DPDP masking (special-category fields: DOB/contact/health/address/Aadhaar +
    secrets) applies at both the outbound LLM payload and trace persistence.
    """
    return redact_for_llm(value)


_NUMERIC_POSITIVE_PARAMS = {"points", "amount"}


def _missing_required_params(tool_name: str, params: dict) -> list[str]:
    required = WRITE_TOOL_REQUIRED_PARAMS.get(tool_name, ())
    missing: list[str] = []
    for key in required:
        val = params.get(key)
        if val is None or val == "" or val == []:
            missing.append(key)
        elif key in _NUMERIC_POSITIVE_PARAMS:
            try:
                if float(val) <= 0:
                    missing.append(key)
            except (TypeError, ValueError):
                missing.append(key)
    return missing


def _missing_param_message(tool_name: str, missing: list[str]) -> str:
    labels = [WRITE_TOOL_PARAM_LABELS.get(key, key.replace("_", " ")) for key in missing]
    joined = ", ".join(labels)
    tool_label = tool_name.replace("_", " ")
    return f"I can prepare that {tool_label}, but I still need: {joined}."


# ─── Parameter resolution ────────────────────────────────────────────────────

async def _resolve_params(params: dict, db, scope=None) -> dict:
    """
    Resolve human-readable parameters to database IDs.
    e.g. class_name "4B" → class_id, student_name "Rahul" → student_id,
         "last 7 days" → date range.

    Part 2 Patch P1: name resolution is now scope-aware.
    - Lookups respect ``scope.filter()`` so a teacher in branch A cannot
      silently resolve a student name to a record in branch B.
    - Substring/unanchored matches with 2+ hits return an explicit ambiguity
      sentinel (``_resolution_error``) instead of picking arbitrarily; callers
      surface this to the user as "please specify the admission number".
    - The ``is_active`` filter is no longer applied at resolution time —
      tools can decide for themselves. An inactive match adds
      ``_resolved_inactive: True`` so the model can mention it.
    """
    from tenant import scoped_query  # local to avoid circular at import time

    resolved = dict(params)

    def _student_options(docs: list) -> list:
        """I.3: build selectable disambiguation options from candidate students.
        `value` is the admission number (re-resolves uniquely); `label` is human."""
        opts = []
        for d in docs[:5]:
            adm = d.get("admission_number")
            cls = d.get("class_name") or d.get("class_id")
            label_bits = [d.get("name", "Unknown")]
            if cls:
                label_bits.append(f"Class {cls}")
            if adm:
                label_bits.append(f"Adm {adm}")
            opts.append({
                "label": " — ".join(str(b) for b in label_bits),
                # Prefer the admission number (unique); fall back to the id.
                "value": str(adm) if adm else str(d.get("id", "")),
            })
        return opts

    def _staff_options(docs: list) -> list:
        opts = []
        for d in docs[:5]:
            role = d.get("designation") or d.get("role")
            label = d.get("name", "Unknown")
            if role:
                label = f"{label} — {role}"
            opts.append({"label": label, "value": str(d.get("id", ""))})
        return opts

    def _scoped(collection: str, base: dict) -> dict:
        """Compose base query with the user's scope.filter() + scoped_query."""
        if scope is None:
            return scoped_query(base)
        f = scope.filter(collection=collection)
        if not f:
            return scoped_query(base, branch_id=scope.branch_id)
        if "$and" in f:
            merged = {"$and": [*f["$and"], base]}
        else:
            merged = {"$and": [f, base]}
        return scoped_query(merged, branch_id=scope.branch_id)

    # ---- class_name → class_id (exact match preferred; ambiguity = error) ----
    if "class_name" in resolved and "class_id" not in resolved:
        class_name = resolved["class_name"]
        # Exact match within scope first.
        matches = await db.classes.find(
            _scoped("classes", {"name": {"$regex": f"^{re.escape(class_name)}$", "$options": "i"}})
        ).to_list(5)
        if not matches:
            m = re.match(r"^(\d+)\s*([A-Za-z])$", class_name)
            if m:
                matches = await db.classes.find(_scoped("classes", {
                    "name": {"$regex": f"^{re.escape(m.group(1))}$", "$options": "i"},
                    "section": {"$regex": f"^{re.escape(m.group(2))}$", "$options": "i"},
                })).to_list(5)
        if len(matches) > 1:
            resolved["_resolution_error"] = (
                f"Multiple classes match '{class_name}' — please specify both class and section."
            )
        elif len(matches) == 1:
            cls = matches[0]
            resolved["class_id"] = cls["id"]
            resolved["_resolved_class"] = f"{cls.get('name', '')}-{cls.get('section', '')}"

    # ---- student_name → student_id (exact OR unique substring within scope) ----
    if "student_name" in resolved and "student_id" not in resolved and "_resolution_error" not in resolved:
        student_name = resolved["student_name"]
        # Try exact match first (anchored).
        exact = await db.students.find(_scoped("students", {
            "name": {"$regex": f"^{re.escape(student_name)}$", "$options": "i"},
        })).to_list(5)
        if len(exact) == 1:
            matches = exact
        elif len(exact) > 1:
            resolved["_resolution_error"] = (
                f"Multiple students share the name '{student_name}' — "
                f"please specify the admission number."
            )
            resolved["_resolution_options"] = _student_options(exact)
            matches = []
        else:
            # Fall back to substring; require uniqueness within scope.
            matches = await db.students.find(_scoped("students", {
                "name": {"$regex": re.escape(student_name), "$options": "i"},
            })).to_list(5)
            if len(matches) > 1:
                resolved["_resolution_error"] = (
                    f"Multiple students match '{student_name}' — "
                    f"please specify the admission number."
                )
                resolved["_resolution_options"] = _student_options(matches)
                matches = []
        if len(matches) == 1:
            student = matches[0]
            resolved["student_id"] = student["id"]
            resolved["_resolved_student"] = student["name"]
            if student.get("is_active") is False:
                resolved["_resolved_inactive"] = True

    if "search_term" in resolved and "student_id" not in resolved and "_resolution_error" not in resolved:
        search_term = resolved["search_term"]
        matches = await db.students.find(_scoped("students", {
            "$or": [
                {"name": {"$regex": re.escape(search_term), "$options": "i"}},
                {"admission_number": {"$regex": re.escape(search_term), "$options": "i"}},
            ],
        })).to_list(5)
        if len(matches) > 1:
            resolved["_resolution_error"] = (
                f"Multiple students match '{search_term}' — "
                f"please specify the admission number."
            )
            resolved["_resolution_options"] = _student_options(matches)
        elif len(matches) == 1:
            student = matches[0]
            resolved["student_id"] = student["id"]
            resolved["_resolved_student"] = student.get("name", student["id"])
            if student.get("is_active") is False:
                resolved["_resolved_inactive"] = True

    # Resolve "days" or date descriptors → date range
    if "days" in resolved:
        try:
            days = int(resolved["days"])
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            resolved["start_date"] = start_date.strftime("%Y-%m-%d")
            resolved["end_date"] = end_date.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    # ---- staff_name → staff_id (same ambiguity discipline) ----
    if "staff_name" in resolved and "staff_id" not in resolved and "_resolution_error" not in resolved:
        staff_name = resolved["staff_name"]
        exact = await db.staff.find(_scoped("staff", {
            "name": {"$regex": f"^{re.escape(staff_name)}$", "$options": "i"},
        })).to_list(5)
        if len(exact) == 1:
            matches = exact
        elif len(exact) > 1:
            resolved["_resolution_error"] = (
                f"Multiple staff members share the name '{staff_name}'."
            )
            resolved["_resolution_options"] = _staff_options(exact)
            matches = []
        else:
            matches = await db.staff.find(_scoped("staff", {
                "name": {"$regex": re.escape(staff_name), "$options": "i"},
            })).to_list(5)
            if len(matches) > 1:
                resolved["_resolution_error"] = (
                    f"Multiple staff match '{staff_name}'."
                )
                resolved["_resolution_options"] = _staff_options(matches)
                matches = []
        if len(matches) == 1:
            staff = matches[0]
            resolved["staff_id"] = staff["id"]
            resolved["_resolved_staff"] = staff["name"]

    return resolved


# ─── Build confirm action display text ────────────────────────────────────────

def _build_confirm_display(tool_name: str, params: dict) -> str:
    """Build a human-readable confirmation message for a write action."""
    displays = {
        "record_fee_payment": lambda p: (
            f"Record fee payment of {p.get('amount', '?')} "
            f"for student {p.get('_resolved_student', p.get('student_id', '?'))} "
            f"via {p.get('payment_mode', p.get('mode', 'N/A'))}"
        ),
        "mark_attendance": lambda p: (
            f"Mark attendance for class "
            f"{p.get('_resolved_class', p.get('class_id', '?'))} "
            f"on {p.get('date', date.today().strftime('%Y-%m-%d'))}"
        ),
        "approve_leave": lambda p: (
            f"{p.get('action', 'Approve').capitalize()} leave request "
            f"{p.get('leave_id', '?')}"
        ),
        "award_house_points": lambda p: (
            f"Award {p.get('points', '?')} house points to "
            f"{p.get('house_name', p.get('house', '?'))} for {p.get('reason', 'N/A')}"
        ),
        "create_announcement": lambda p: (
            f"Publish announcement '{p.get('title', '?')}' to "
            f"{p.get('audience_type', 'all')} — \"{p.get('content', '')[:80]}{'...' if len(p.get('content','')) > 80 else ''}\""
        ),
    }
    builder = displays.get(tool_name)
    if builder:
        try:
            return builder(params)
        except Exception:
            pass
    return f"Execute {tool_name} with parameters: {json.dumps(params, ensure_ascii=False)}"


async def _build_confirm_event(tool_name: str, params: dict, user: dict, session_id: str, db) -> dict:
    """Create the server-side confirmation token and SSE payload for a write tool."""
    public_params = {k: v for k, v in params.items() if not k.startswith("_")}
    token = await issue_confirm_token(
        action=tool_name,
        params=public_params,
        user_id=user["id"],
        session_id=session_id,
        school_id=get_school_id(),
        branch_id=user.get("branch_id"),
        db=db,
    )
    return {
        "type": "confirm_action",
        "action_id": token,
        "token": token,
        "tool": tool_name,
        "params": public_params,
        "display": _build_confirm_display(tool_name, params),
        "expires_in_seconds": 5 * 60,
        "buttons": [
            {"label": "Confirm", "action": "confirm"},
            {"label": "Cancel", "action": "cancel"},
        ],
    }


def _deep_link_for_tool(tool_name: str) -> str:
    """E.6: map a tool the assistant can't run to the UI panel that can."""
    panel = _TOOL_DEEP_LINKS.get(tool_name, "dashboard")
    return f"/app?tool={panel}"


async def _build_plan_confirm_event(
    plan_steps: list, user: dict, session_id: str, db
) -> dict:
    """E.5/UX-DR1: issue ONE plan-confirm token and a single confirm_action SSE
    event that lists every step of the resolved multi-step plan."""
    token = await issue_confirm_token(
        action="plan",
        params={},
        user_id=user["id"],
        session_id=session_id,
        school_id=get_school_id(),
        branch_id=user.get("branch_id"),
        plan=plan_steps,
        db=db,
    )
    step_displays = [
        {
            "idx": s.get("idx", i),
            "tool": s.get("tool"),
            "kind": s.get("kind", "write"),
            "destructive": bool(s.get("destructive", False)),
            "display": _build_confirm_display(s.get("tool"), s.get("params") or {}),
        }
        for i, s in enumerate(plan_steps)
    ]
    return {
        "type": "confirm_action",
        "action_id": token,
        "token": token,
        "tool": "plan",
        "is_plan": True,
        "steps": step_displays,
        "display": "I'll run these steps in order — confirm to proceed:",
        "expires_in_seconds": 5 * 60,
        "buttons": [
            {"label": "Confirm", "action": "confirm"},
            {"label": "Cancel", "action": "cancel"},
        ],
    }


async def _stream_text_message(text: str, conv_id, user, db, lang, total_tokens_used, *, actions=None, extra_events=None):
    """Stream a plain assistant message (text deltas), persist it, then close."""
    yield thinking_event("composing", "Writing your answer...")
    await _thinking_delay()
    for i in range(0, len(text), 4):
        yield f"data: {json.dumps({'type': 'text_delta', 'delta': text[i:i + 4]})}\n\n"
        await asyncio.sleep(0.008)
    for ev in (extra_events or []):
        yield ev
    message_id = None
    if conv_id:
        ai_msg = Message(
            conversation_id=conv_id, role="assistant", content=text,
            actions=actions, language_detected=lang,
        )
        await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
        message_id = ai_msg.id
    yield f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'tokens_used': total_tokens_used})}\n\n"


async def _stream_plan(calls, user, db, scope, session_id, conv_id, lang, total_tokens_used):
    """Epic E end-to-end: resolve+authorize a compound plan and gate it behind
    ONE confirm card, or fall back gracefully (disambiguation / deep-link)."""

    async def _request_plan(*, instruction, user, scope):
        return [{"tool": c.get("action"), "params": c.get("params") or {}} for c in calls]

    result = await ai_planner.build_plan(
        instruction="",
        user=user,
        db=db,
        scope=scope,
        registry=TOOL_REGISTRY,
        write_tools=WRITE_ACTION_TOOLS,
        is_authorized=_is_tool_authorized,
        resolve_params=_resolve_params,
        request_plan=_request_plan,
        deep_link_for=_deep_link_for_tool,
    )

    if result.status == ai_planner.PLAN and result.has_writes:
        try:
            confirm_event = await _build_plan_confirm_event(result.steps, user, session_id, db)
        except HTTPException as exc:
            yield f"data: {json.dumps({'type': 'error', 'phase': 'confirm_token', 'message': exc.detail})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        yield f"data: {json.dumps(confirm_event)}\n\n"
        confirm_text = "I need your confirmation before proceeding. Please review the plan above."
        async for ev in _stream_text_message(
            confirm_text, conv_id, user, db, lang, total_tokens_used, actions=[confirm_event]
        ):
            yield ev
        return

    # E.6: graceful fallback — disambiguation, unauthorized, too-long, or
    # cannot-plan. NOTHING was written and no token issued; hand off to the UI.
    # Disambiguation is a question (no dead-end), so it gets no deep-link; the
    # other dead-ends offer a panel to finish the job by hand (UX-DR4).
    deep_link = result.deep_link
    if deep_link is None and result.status in (ai_planner.CANNOT_PLAN, ai_planner.TOO_LONG):
        deep_link = "/app?tool=dashboard"
    extra_events = []
    # I.3: a disambiguation is a question with selectable candidates — emit a
    # structured event the chat renders as clickable options (no deep-link, no
    # token, no write). The picked option's `value` continues the flow.
    if result.status == ai_planner.DISAMBIGUATION and result.options:
        extra_events.append(
            f"data: {json.dumps({'type': 'disambiguation', 'message': result.message, 'options': result.options})}\n\n"
        )
    elif deep_link:
        extra_events.append(
            f"data: {json.dumps({'type': 'navigate', 'url': deep_link})}\n\n"
        )
    logger.info(
        "planner_fallback status=%s user=%s tool=%s",
        result.status, user.get("id"), result.unauthorized_tool,
    )
    message = result.message or "I wasn't able to complete that. Try the matching panel."
    async for ev in _stream_text_message(
        message, conv_id, user, db, lang, total_tokens_used, extra_events=extra_events
    ):
        yield ev


def _ai_unavailable_event(message: str = AI_UNAVAILABLE_MESSAGE) -> str:
    return f"data: {json.dumps({'type': 'ai_unavailable', 'message': message})}\n\n"


# ─── Thinking delay helper ────────────────────────────────────────────────────

async def _thinking_delay():
    """Add a small random delay between thinking steps for natural feel."""
    await asyncio.sleep(random.uniform(THINKING_DELAY_MIN, THINKING_DELAY_MAX))


_RICH_MARKER = "<<<RICH_CONTENT>>>"


async def _stream_final_answer(system_prompt, messages, session_id, sink: dict):
    """R11.3: stream the final answer token-by-token from the model.

    Yields SSE `text_delta` events for the SAFE visible prefix — the text before
    any ``<<<RICH_CONTENT>>>`` marker — holding back a short tail so a partial
    marker is never shown to the user. The rich-content JSON that follows the
    marker is buffered (parsed downstream), never streamed as visible prose.

    `sink` is filled with {text, tokens, ok, error}. On a mid-stream provider
    error the partial text is preserved so the R1 turn contract can keep what was
    produced and mark the turn interrupted (AC3).
    """
    buf: list[str] = []
    emitted = 0
    marker_seen = False
    sink.update({"text": "", "tokens": 0, "ok": False, "error": None})

    async for ev in llm_client.chat_stream(system_prompt, messages, session_id):
        et = ev.get("type")
        if et == "delta":
            buf.append(ev.get("text", ""))
            if marker_seen:
                continue
            full = "".join(buf)
            midx = full.find(_RICH_MARKER)
            if midx >= 0:
                visible = full[:midx]
                marker_seen = True
            else:
                # Hold back the longest trailing run that could be a forming
                # marker so we never emit "<<<RICH_CON…" and have to retract it.
                hold = 0
                for h in range(min(len(_RICH_MARKER) - 1, len(full)), 0, -1):
                    if _RICH_MARKER.startswith(full[-h:]):
                        hold = h
                        break
                visible = full[: len(full) - hold] if hold else full
            if len(visible) > emitted:
                delta = visible[emitted:]
                emitted = len(visible)
                yield f"data: {json.dumps({'type': 'text_delta', 'delta': delta})}\n\n"
        elif et == "done":
            full = "".join(buf)
            if not marker_seen and len(full) > emitted:
                yield f"data: {json.dumps({'type': 'text_delta', 'delta': full[emitted:]})}\n\n"
            sink.update({"text": full, "tokens": ev.get("tokens", 0), "ok": True})
            return
        elif et == "error":
            sink.update({
                "text": ev.get("text", "") or "".join(buf),
                "ok": False,
                "error": ev.get("reason") or "stream_failed",
            })
            return
    # Stream ended without an explicit terminal event — best-effort salvage.
    sink["text"] = "".join(buf)


async def _record_turn_trace(db, *, conv_id, message_id, user, outcome, lang,
                             tool_calls=None, llm_reason=None, llm_ok=True,
                             error_type=None, tokens=0):
    """R11.5: persist a compact per-turn diagnostic row so the "AI didn't reply"
    incident class is diagnosable from the trace viewer WITHOUT server-log access.

    Confidentiality: the real provider/model are stored here for INTERNAL
    operator/telemetry use only; the client-facing trace endpoint abstracts them
    to "Layaa AI" and never reveals the vendor to a school user. Fail-open — a
    trace write must never break or delay a turn.
    """
    try:
        tools = []
        for c in (tool_calls or []):
            res = c.get("result")
            status = "error" if isinstance(res, dict) and res.get("error") else "done"
            tools.append({"tool": c.get("tool"), "status": status})
        doc = {
            "id": str(uuid.uuid4()),
            "schoolId": get_school_id(),
            "branch_id": user.get("branch_id"),
            "conversation_id": conv_id,
            "message_id": message_id,
            "user_id": user.get("id"),
            "role": user.get("role"),
            "outcome": outcome,
            "language": lang,
            "tools": tools,
            # Internal-only provider/model — NEVER surfaced to a client (R11.5
            # confidentiality); the endpoint reports the assistant as "Layaa AI".
            "llm": {
                "provider": "azure_openai",
                "model": llm_client.deployment,
                "finish_reason": llm_reason,
                "ok": llm_ok,
                "error_type": error_type,
                "tokens": tokens,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.ai_turn_traces.insert_one(doc)
    except Exception as e:  # fail-open
        logger.warning("R11.5 turn-trace record failed (non-fatal): %s", e)


# ─── SSE Generator (main pipeline) ───────────────────────────────────────────

def _user_content(text: str, image_data: str | None):
    """Build user message content — plain string or multimodal list if image attached."""
    if not image_data:
        return text
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": image_data}},
    ]


# R9.4 (X8) AC3: chat `image_data` re-enters POST /chat as a client-supplied base64
# data URL — validate its format and decoded size server-side (the upload endpoint's
# checks don't apply to a value posted directly to /chat).
_MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB decoded
_IMAGE_DATA_URL_RE = re.compile(
    r"^data:image/(?:png|jpe?g|gif|webp|heic|bmp|tiff);base64,", re.IGNORECASE
)


def _validate_image_data(image_data) -> str | None:
    """Return an error message if the image data URL is invalid, else None."""
    if not isinstance(image_data, str) or not _IMAGE_DATA_URL_RE.match(image_data):
        return "Invalid image format"
    b64 = image_data.split(",", 1)[1] if "," in image_data else ""
    if not b64:
        return "Invalid image data"
    # Size from base64 length (≈3/4) BEFORE decoding a potentially huge blob.
    if (len(b64) * 3) // 4 > _MAX_IMAGE_BYTES:
        return f"Image too large (max {_MAX_IMAGE_BYTES // (1024*1024)} MB)"
    try:
        base64.b64decode(b64, validate=True)
    except Exception:
        return "Invalid image encoding"
    return None


async def _generate_chat_sse(conv_id: str, user_text: str, user: dict, session_id: str = None, request=None, image_data: str = None):
    """
    SSE generator for chat streaming.

    Pipeline:
      1. Save user message + auto-title
      2. Input safety check (content filter)
      3. Navigate detection
      4. Build context + system prompt
      5. Load + trim conversation history
      6. Keyword tool detection
      7. If no keyword match, ask LLM → parse tool call from response
      8. Scope enforcement + tool execution (or confirm-action for writes)
      9. Multi-tool chaining (up to 3 rounds)
      10. Final LLM response generation
      11. Content filtering on output
      12. Stream text + rich content
      13. Persist assistant message
      14. Done event
    """
    db = get_db()
    session_id = session_id or conv_id
    total_tokens_used = 0

    # ── Phase 0: Token budget check ──────────────────────────────────────
    branch_id = user.get("branch_id") or "branch-aaryans-joya"
    budget_check = {"allowed": True, "source": "unlimited", "message": "", "can_recharge": False}
    try:
        budget_check = await check_and_reserve_tokens(user, branch_id, estimated_tokens=2000)
        if not budget_check["allowed"]:
            yield thinking_event("error", budget_check["message"])
            yield f"data: {json.dumps({'type': 'text_delta', 'delta': budget_check['message']})}\n\n"
            if budget_check.get("can_recharge"):
                yield f"data: {json.dumps({'type': 'token_exhausted', 'can_recharge': True, 'message': budget_check['message']})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
    except Exception as e:
        logger.error(f"Phase 0 (token budget check) error: {e}")
        # Non-fatal: allow the call to proceed if the budget system fails
        budget_check = {"allowed": True, "source": "unlimited", "message": "", "can_recharge": False}

    # ── Phase 1: Save user message ────────────────────────────────────────
    try:
        lang = detect_language(user_text)
        user_msg = Message(
            conversation_id=conv_id,
            role="user",
            content=user_text,
            language_detected=lang,
        )
        await db.messages.insert_one({**user_msg.dict(), "_id": user_msg.id})

        # Update conversation timestamp + auto-title
        conv = await db.conversations.find_one(_owned_conversation_filter(conv_id, user))
        update_fields = {"updated_at": datetime.now().isoformat()}
        if conv and conv.get("title") in ("New conversation", None, ""):
            update_fields["title"] = user_text[:50].strip()
        await db.conversations.update_one(_owned_conversation_filter(conv_id, user), {"$set": update_fields})

    except Exception as e:
        logger.error(f"Phase 1 (save user message) error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'phase': 'save_message', 'message': 'Failed to save your message. Please try again.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # ── Phase 1b: Memory commands / confirmations (Epic G — Owner/Principal) ──
    # Inline "remember:"/"forget", an affirmative reply to a pending memory, or a
    # correction are handled BEFORE the LLM. A returned string short-circuits the
    # turn. Best-effort: any failure falls through to the normal flow.
    try:
        conv_for_memory = await db.conversations.find_one(_owned_conversation_filter(conv_id, user))
        pre_turn_reply = await chat_memory.handle_pre_turn(db, user, user_text, conv_for_memory)
        if pre_turn_reply:
            async for _ev in _stream_text_message(pre_turn_reply, conv_id, user, db, lang, 0):
                yield _ev
            return
    except Exception as e:
        logger.error(f"Phase 1b (memory pre-turn) error: {e}")

    # ── Thinking: understanding ───────────────────────────────────────────
    yield thinking_event("understanding", "Reading your question...")
    await _thinking_delay()

    # ── Phase 2: Input safety check (BUG FIX #8 + CONTENT FILTER) ────────
    try:
        safety = check_input_safety(user_text, user["role"])
        if not safety["safe"]:
            rejection_text = safety.get("filtered_message", safety.get("message",
                "I can't process that request. Please ask a school-related question."))
            logger.info(f"Input blocked for user {user['id']}: {safety.get('reason', 'unknown')}")

            # Stream the rejection message
            yield thinking_event("composing", "Writing your answer...")
            await _thinking_delay()

            chunk_size = 4
            for i in range(0, len(rejection_text), chunk_size):
                chunk = rejection_text[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'text_delta', 'delta': chunk})}\n\n"
                await asyncio.sleep(0.008)

            # Persist the rejection as assistant message
            ai_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=rejection_text,
                language_detected=lang,
                is_flagged=True,
                flag_reason=safety.get("reason", "content_filter"),
            )
            await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
            yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': 0})}\n\n"
            return

    except Exception as e:
        logger.error(f"Phase 2 (input safety) error: {e}")
        # Non-fatal: continue even if filter fails

    # ── Phase 3: Navigate detection ───────────────────────────────────────
    try:
        nav_target = detect_navigate(user_text)
        if nav_target:
            yield f"data: {json.dumps({'type': 'navigate', 'tool_id': nav_target})}\n\n"
            # Also send a brief text response
            nav_text = f"Opening **{nav_target.replace('-', ' ').title()}** for you."
            chunk_size = 4
            for i in range(0, len(nav_text), chunk_size):
                chunk = nav_text[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'text_delta', 'delta': chunk})}\n\n"
                await asyncio.sleep(0.008)

            ai_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=nav_text,
                language_detected=lang,
            )
            await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
            yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': 0})}\n\n"
            return

    except Exception as e:
        logger.error(f"Phase 3 (navigate detection) error: {e}")
        # Non-fatal: continue to normal chat flow

    # ── Phase 4: Build context + system prompt ────────────────────────────
    recalled_memories: list = []  # R10.4 AC2: recalled-memory disclosure (Data used)
    try:
        school_context = await build_school_context(user["role"], user["id"])
        system_prompt = build_system_prompt(user, school_context, lang)

        # Epic G (G.3): inject recalled memories/skills for Owner/Principal. Hybrid
        # recall degrades to keyword-only when the vector store is unavailable.
        # R10.4 AC2: capture the recalled memories so they can be disclosed in the
        # "Data used" footer of the reply.
        try:
            recall_block = await chat_memory.recall_context_block(
                db, user, user_text, recalled_sink=recalled_memories
            )
            if recall_block:
                system_prompt += recall_block
        except Exception as e:
            logger.warning(f"Phase 4 (memory recall) non-fatal: {e}")

    except Exception as e:
        logger.error(f"Phase 4 (build context) error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'phase': 'context', 'message': 'Failed to load school context. Please try again.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # ── Phase 5: Load + trim conversation history ────────────────────────
    # Part 2 Patch P2: the prior implementation used `.sort("created_at", 1).to_list(HISTORY_LIMIT)`
    # which loads the OLDEST 20 messages — defeating `HISTORY_KEEP_FIRST=2 + HISTORY_KEEP_RECENT=10`
    # entirely. After 20 turns the AI silently lost all recent context.
    # Fix: load first HISTORY_KEEP_FIRST anchors ASC + last HISTORY_KEEP_RECENT
    # by DESC and re-sort. Total messages == both ends, never the middle.
    try:
        msg_filter = scoped_filter({"conversation_id": conv_id, "role": {"$in": ["user", "assistant"]}, "is_flagged": {"$ne": True}}, get_school_id())
        anchors = await db.messages.find(msg_filter, {"_id": 0}).sort("created_at", 1).to_list(HISTORY_KEEP_FIRST)
        anchor_ids = {a.get("id") for a in anchors if a.get("id")}
        recent = await db.messages.find(msg_filter, {"_id": 0}).sort("created_at", -1).to_list(HISTORY_KEEP_RECENT)
        # Drop anchors that overlap with recent (short conversations).
        recent.reverse()
        recent_clean = [m for m in recent if not (m.get("id") and m.get("id") in anchor_ids)]
        history_raw = list(anchors) + recent_clean

        # Total-message count for elision marker.
        total_msgs = await db.messages.count_documents(msg_filter)
        omitted = max(0, total_msgs - len(history_raw))

        messages_for_llm = [
            {"role": m["role"], "content": m.get("content", "") or ""}
            for m in history_raw
        ]
        messages_for_llm = _trim_history(messages_for_llm)
        if omitted > 0 and len(anchors) >= 1:
            # Splice AFTER trim so _trim_history never drops the marker.
            insert_pos = min(len(anchors), len(messages_for_llm))
            messages_for_llm.insert(
                insert_pos,
                {"role": "system",
                 "content": f"[{omitted} earlier messages omitted for context length]"},
            )

    except Exception as e:
        logger.error(f"Phase 5 (load history) error: {e}")
        # Fall back to just the current message
        messages_for_llm = [{"role": "user", "content": _user_content(user_text, image_data)}]

    # ── Phase 6: Resolve scope ────────────────────────────────────────────
    try:
        scope = await resolve_scope(user, db)
    except Exception as e:
        logger.error(f"Scope resolution error: {e}")
        scope = Scope(type="self_only", role=user.get("role", ""), user_id=user.get("id", ""))

    # ── Phase 7: Keyword tool detection ───────────────────────────────────
    detected_tool = detect_tool_from_keywords(user_text, user)
    tool_result = None
    tool_name = None
    all_tool_calls = []  # Track all tool calls for message persistence

    if detected_tool:
        tool_name = detected_tool
        tool_def = TOOL_REGISTRY.get(tool_name)

        # Determine intent description for thinking event
        intent_desc = tool_name.replace("get_", "").replace("_", " ")
        yield thinking_event("decision", f"You're asking about {intent_desc}. Fetching data...")
        await _thinking_delay()

        # ── BUG FIX #5: Role validation (explicit check) ─────────────
        if not tool_def or not _is_tool_authorized(user, tool_def):
            logger.warning(f"Role {user['role']} not allowed for tool {tool_name}")
            tool_name = None
            detected_tool = None
        else:
            # ── Check if this is a write action requiring confirmation ──
            if tool_name in WRITE_ACTION_TOOLS:
                # Keyword detection identified the write intent, but params still
                # need model extraction so the confirmation card is meaningful.
                params = {}
                try:
                    # R11.2: force the single detected tool via native function
                    # calling and read its structured arguments — no JSON-in-text
                    # to parse, and the model cannot name a different tool.
                    extraction_result = await llm_client.chat(
                        system_prompt,
                        [{"role": "user", "content": user_text}],
                        f"{conv_id}-extract-{uuid.uuid4()}",
                        tools=_build_llm_tools(user, only={tool_name}),
                        tool_choice={"type": "function", "function": {"name": tool_name}},
                    )
                    _calls = _tool_calls_to_candidates(extraction_result.tool_calls)
                    for _c in _calls:
                        if _c.get("action") == tool_name:
                            params = _c.get("params", {}) or {}
                            break
                except Exception as e:
                    logger.warning(f"Write parameter extraction failed for {tool_name}: {e}")
                resolved_params = await _resolve_params(params, db, scope)
                # Part 2 P1: surface ambiguous-name resolution as a user prompt
                # before any confirm token is issued or rate slot consumed.
                if resolved_params.get("_resolution_error"):
                    err_text = resolved_params["_resolution_error"]
                    yield thinking_event("composing", "Writing your answer...")
                    await _thinking_delay()
                    for i in range(0, len(err_text), 4):
                        yield f"data: {json.dumps({'type': 'text_delta', 'delta': err_text[i:i + 4]})}\n\n"
                        await asyncio.sleep(0.008)
                    ai_msg = Message(
                        conversation_id=conv_id, role="assistant",
                        content=err_text, language_detected=lang,
                    )
                    await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
                    yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': 0})}\n\n"
                    return
                missing = _missing_required_params(tool_name, resolved_params)

                if missing:
                    prompt_text = _missing_param_message(tool_name, missing)
                    yield thinking_event("composing", "Writing your answer...")
                    await _thinking_delay()
                    for i in range(0, len(prompt_text), 4):
                        yield f"data: {json.dumps({'type': 'text_delta', 'delta': prompt_text[i:i + 4]})}\n\n"
                        await asyncio.sleep(0.008)
                    ai_msg = Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=prompt_text,
                        language_detected=lang,
                    )
                    await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
                    yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"
                    return

                yield thinking_event("tool_start", f"Preparing {tool_name}...", tool=tool_name)
                await _thinking_delay()

                try:
                    confirm_event = await _build_confirm_event(tool_name, resolved_params, user, session_id, db)
                except HTTPException as exc:
                    yield f"data: {json.dumps({'type': 'error', 'phase': 'confirm_token', 'message': exc.detail})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return
                yield f"data: {json.dumps(confirm_event)}\n\n"

                # Send a brief explanation
                confirm_text = f"I need your confirmation before proceeding. Please review the action above."
                yield thinking_event("composing", "Writing your answer...")
                await _thinking_delay()

                chunk_size = 4
                for i in range(0, len(confirm_text), chunk_size):
                    chunk = confirm_text[i:i + chunk_size]
                    yield f"data: {json.dumps({'type': 'text_delta', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.008)

                ai_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=confirm_text,
                    actions=[confirm_event],
                    language_detected=lang,
                )
                await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
                yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': 0})}\n\n"
                return

            # ── Execute read tool ─────────────────────────────────────
            yield thinking_event("tool_start", f"Querying {tool_name}...", tool=tool_name)
            await _thinking_delay()

            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'running'})}\n\n"

            # R7.3/AC5: actually START a keepalive — run the read tool as a task and
            # emit keepalive frames while it runs, so a slow query can't stall the SSE
            # stream into an idle-timeout. (Previously the keepalive coroutine was
            # defined but never scheduled, and yielded nothing.)
            try:
                if _tool_accepts_scope(tool_def):
                    tool_task = asyncio.create_task(tool_def["fn"]({}, user, scope))
                else:
                    tool_task = asyncio.create_task(tool_def["fn"]({}, user))
                try:
                    while not tool_task.done():
                        try:
                            await asyncio.wait_for(asyncio.shield(tool_task), timeout=KEEPALIVE_INTERVAL)
                        except asyncio.TimeoutError:
                            yield keepalive_event()
                    raw_tool_result = tool_task.result()
                finally:
                    if not tool_task.done():
                        tool_task.cancel()

                await _audit_minor_read(db, user, tool_name, raw_tool_result)
                result_count = _extract_result_count(raw_tool_result)
                tool_result = _safe_tool_result_for_chat(raw_tool_result)
                count_msg = f"Found {result_count} records" if result_count is not None else "Data retrieved"

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'done'})}\n\n"
                yield thinking_event("tool_done", count_msg, tool=tool_name, count=result_count)
                await _thinking_delay()

                all_tool_calls.append({"tool": tool_name, "result": tool_result})

            except Exception as e:
                # Part 2 Patch P3: never expose `str(e)` to the LLM / client —
                # may contain Mongo URIs, collection names, stack frame paths.
                # Log to server with a correlation_id; surface a generic token.
                corr_id = str(uuid.uuid4())
                logger.exception("Tool execution error (%s) [%s]", tool_name, corr_id)
                tool_result = {"error": "data_unavailable", "correlation_id": corr_id}
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'error', 'error': 'data_unavailable', 'correlation_id': corr_id})}\n\n"
                all_tool_calls.append({"tool": tool_name, "result": tool_result})

    # ── Phase 8: First LLM call ───────────────────────────────────────────
    try:
        if tool_result:
            # BUG FIX #6: Check for empty results message
            empty_msg = _extract_empty_message(tool_result)
            empty_note = ""
            if empty_msg:
                empty_note = f"\n\nNote: The tool returned no data with this message: \"{empty_msg}\". Relay this to the user helpfully."

            # R9.2 AC1 (M10): do NOT run topic-blocking over serialized tool JSON —
            # `tool_result` is ALREADY PII-redacted (_safe_tool_result_for_chat →
            # redact_for_llm above), and running filter_response over the JSON would
            # let one blocked word in legitimate data nuke the ENTIRE dataset. The
            # LLM's natural-language prose is topic-filtered downstream (clean_response).
            tool_data_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
            tool_result_msg = (
                f"Tool '{tool_name}' returned the following data:\n"
                f"{tool_data_str}"
                f"{empty_note}\n\n"
                f"Now provide a comprehensive, well-formatted response to the user's question "
                f"based on this data. Use markdown tables and formatting. "
                f"Include a <<<RICH_CONTENT>>> block if you have stats or tables to show. "
                f"Call another tool only if it is strictly required to answer."
            )
            messages_for_llm_final = messages_for_llm[:-1] + [
                {"role": "user", "content": _user_content(user_text, image_data)},
                {"role": "assistant", "content": f"Fetching {tool_name} data..."},
                {"role": "user", "content": tool_result_msg},
            ]
        else:
            messages_for_llm_final = messages_for_llm

        # R11.2: advertise the caller's authorized tools via native function
        # calling — the model returns structured tool_calls (or a final answer),
        # never JSON-in-text, and can only name a tool it is allowed to use.
        llm_tools = _build_llm_tools(user)

        yield thinking_event("analyzing", "Processing the data..." if tool_result else "Thinking about your question...")
        await _thinking_delay()

        # Part 2 Patch P5: keepalive + bounded wait + clean task lifecycle.
        # Previously the LLM task was spawned via fire-and-forget
        # `asyncio.create_task` and the keepalive loop spun forever if the
        # task raised before setting the event. Now: track the task, finally-
        # cancel it on any exit (including client disconnect), and cap the
        # wallclock wait at LLM_WALLCLOCK_BUDGET so a hung Azure call cannot
        # leak workers.
        llm_task_done = asyncio.Event()
        llm_response = ""
        llm_tokens = 0
        llm_ok = True           # R1.7: availability tracked explicitly, not by result type
        llm_tool_calls = []     # R11.2: structured tool calls requested by the model
        llm_reason = None       # R11.5: finish_reason for the turn trace
        # LLM_WALLCLOCK_BUDGET is a module constant (see top of file)

        async def _llm_call():
            nonlocal llm_response, llm_tokens, llm_ok, llm_tool_calls, llm_reason
            try:
                session_id = f"{conv_id}-{uuid.uuid4()}"
                result = await llm_client.chat(system_prompt, messages_for_llm_final, session_id, tools=llm_tools)
                llm_response = result.text
                llm_tokens = result.tokens
                llm_ok = result.ok
                llm_tool_calls = result.tool_calls or []
                llm_reason = result.reason
            except Exception:
                logger.exception("LLM call raised unexpectedly in Phase 8")
                llm_response = ""
                llm_tokens = 0
                llm_ok = False
                llm_tool_calls = []
            finally:
                # ALWAYS set the event so the keepalive loop never spins.
                llm_task_done.set()

        llm_task = asyncio.create_task(_llm_call())

        try:
            elapsed = 0
            while not llm_task_done.is_set():
                try:
                    await asyncio.wait_for(
                        llm_task_done.wait(),
                        timeout=KEEPALIVE_INTERVAL,
                    )
                except asyncio.TimeoutError:
                    elapsed += KEEPALIVE_INTERVAL
                    if elapsed >= LLM_WALLCLOCK_BUDGET:
                        logger.warning("LLM wallclock budget exceeded (%ds) — bailing", elapsed)
                        llm_response = ""
                        llm_tokens = 0
                        llm_ok = False
                        break
                    if request is not None:
                        try:
                            if await request.is_disconnected():
                                logger.info("Client disconnected during LLM call; cancelling")
                                break
                        except Exception:
                            pass
                    yield keepalive_event()
        finally:
            if not llm_task.done():
                llm_task.cancel()

        if not llm_ok:
            yield _ai_unavailable_event()
            ai_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=AI_UNAVAILABLE_MESSAGE,
                language_detected=lang,
            )
            await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
            await _record_turn_trace(
                db, conv_id=conv_id, message_id=ai_msg.id, user=user, outcome="unavailable",
                lang=lang, llm_reason=llm_reason, llm_ok=False, error_type="ai_unavailable",
                tokens=total_tokens_used,
            )
            yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"
            return

        # BUG FIX #1: Safe token counting
        total_tokens_used += safe_token_count(llm_tokens, llm_response)
        # R11.2: the model's structured tool requests drive Phases 8.5 + 9.
        pending_calls = _tool_calls_to_candidates(llm_tool_calls)

    except Exception as e:
        logger.error(f"Phase 8 (first LLM call) error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'phase': 'llm_call', 'message': 'Failed to generate response. Please try again.'})}\n\n"
        # R1.3 AC3: an error event also persists an assistant message with the
        # same text, so a reload shows the failure and history is never poisoned
        # with a user question that has no reply.
        try:
            err_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content="Failed to generate response. Please try again.",
                language_detected=lang,
            )
            await db.messages.insert_one({**err_msg.dict(), "_id": err_msg.id})
            await _record_turn_trace(
                db, conv_id=conv_id, message_id=err_msg.id, user=user, outcome="error",
                lang=lang, llm_ok=False, error_type="llm_call", tokens=total_tokens_used,
            )
            yield f"data: {json.dumps({'type': 'done', 'message_id': err_msg.id, 'tokens_used': total_tokens_used})}\n\n"
        except Exception as persist_err:
            logger.error(f"Phase 8 error-path persistence failed: {persist_err}")
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # ── Phase 8.5: agentic planner (Epic E) — whole-job-by-instruction ────
    # When the model proposes MORE THAN ONE tool call in a turn and at least one
    # is a write, treat it as a compound job: resolve + authorize the whole plan
    # server-side and gate it behind ONE plan-confirm card (plan-then-confirm-once).
    # The common single-tool path below is unchanged (≤1 parsed call skips this).
    if not detected_tool:
        _candidate_calls = pending_calls
        _has_write = any(c.get("action") in WRITE_ACTION_TOOLS for c in _candidate_calls)
        if len(_candidate_calls) > 1 and _has_write:
            async for _ev in _stream_plan(
                _candidate_calls, user, db, scope, session_id, conv_id, lang, total_tokens_used
            ):
                yield _ev
            return

    # ── Phase 9: LLM tool detection + multi-tool chaining ─────────────────
    # Part 2 Patch P5 (E6/L4): treat the keyword-detected tool as round 1 so
    # MAX_TOOL_ROUNDS is honored (was previously off-by-one: 4 effective rounds
    # when a keyword tool fired). Loop condition is now `<` only — relying on
    # the inner `break` to handle "no further tool requested".
    tool_rounds = 1 if detected_tool else 0

    try:
        while tool_rounds < MAX_TOOL_ROUNDS:
            # R11.2: the model's next tool request is the first structured
            # tool_call from the most recent LLM turn (Phase 8 or a follow-up).
            # No text parsing — if there is no pending call, the model produced a
            # final answer and we stop chaining.
            llm_tool_call = pending_calls[0] if pending_calls else None
            if not llm_tool_call:
                break

            tool_rounds += 1
            llm_tool_name = llm_tool_call.get("action")
            llm_tool_params = llm_tool_call.get("params", {})

            tool_def = TOOL_REGISTRY.get(llm_tool_name)
            if not tool_def:
                # R1.5 AC1: name the missing capability + suggest close authorized
                # matches. Setting llm_response (not a bare break) means Phase 14
                # streams + persists this explanation instead of a silent dead end.
                _close = _close_tool_matches(llm_tool_name, user)
                _suffix = f" Did you mean: {', '.join(_close)}?" if _close else ""
                llm_response = f'I don\'t have a capability called "{llm_tool_name}".{_suffix}'
                break
            if not _is_tool_authorized(user, tool_def):
                # R1.5 AC2: a real capability the caller's role can't use — distinct
                # message from "unknown" so we don't imply the feature doesn't exist.
                llm_response = "That action isn't available for your role."
                break

            tool_name = llm_tool_name

            # Thinking: decision (if first round)
            if tool_rounds == 1 and not detected_tool:
                intent_desc = tool_name.replace("get_", "").replace("_", " ")
                reason = llm_tool_call.get("reason", f"Fetching {intent_desc}")
                yield thinking_event("decision", f"You're asking about {intent_desc}. {reason}")
                await _thinking_delay()

            # Resolve parameters
            resolved_params = await _resolve_params(llm_tool_params, db, scope)
            if resolved_params.get("_resolution_error"):
                err_text = resolved_params["_resolution_error"]
                yield thinking_event("composing", "Writing your answer...")
                await _thinking_delay()
                for i in range(0, len(err_text), 4):
                    yield f"data: {json.dumps({'type': 'text_delta', 'delta': err_text[i:i + 4]})}\n\n"
                    await asyncio.sleep(0.008)
                ai_msg = Message(
                    conversation_id=conv_id, role="assistant",
                    content=err_text,
                    tool_calls=all_tool_calls if all_tool_calls else None,
                    language_detected=lang,
                )
                await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
                yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"
                return

            # ── Write action confirmation ─────────────────────────────
            if tool_name in WRITE_ACTION_TOOLS:
                missing = _missing_required_params(tool_name, resolved_params)
                if missing:
                    prompt_text = _missing_param_message(tool_name, missing)
                    yield thinking_event("composing", "Writing your answer...")
                    await _thinking_delay()
                    for i in range(0, len(prompt_text), 4):
                        yield f"data: {json.dumps({'type': 'text_delta', 'delta': prompt_text[i:i + 4]})}\n\n"
                        await asyncio.sleep(0.008)
                    ai_msg = Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=prompt_text,
                        tool_calls=all_tool_calls if all_tool_calls else None,
                        language_detected=lang,
                    )
                    await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
                    yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"
                    return

                try:
                    confirm_event = await _build_confirm_event(tool_name, resolved_params, user, session_id, db)
                except HTTPException as exc:
                    yield f"data: {json.dumps({'type': 'error', 'phase': 'confirm_token', 'message': exc.detail})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return
                yield f"data: {json.dumps(confirm_event)}\n\n"

                confirm_text = "I need your confirmation before proceeding. Please review the action above."
                yield thinking_event("composing", "Writing your answer...")
                await _thinking_delay()

                chunk_size = 4
                for i in range(0, len(confirm_text), chunk_size):
                    chunk = confirm_text[i:i + chunk_size]
                    yield f"data: {json.dumps({'type': 'text_delta', 'delta': chunk})}\n\n"
                    await asyncio.sleep(0.008)

                ai_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=confirm_text,
                    actions=[confirm_event],
                    tool_calls=all_tool_calls if all_tool_calls else None,
                    language_detected=lang,
                )
                await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
                yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"
                return

            # ── Execute read tool ─────────────────────────────────────
            yield thinking_event("tool_start", f"Querying {tool_name}...", tool=tool_name)
            await _thinking_delay()

            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'running'})}\n\n"

            try:
                raw_tool_result = await tool_def["fn"](resolved_params, user, scope) if _tool_accepts_scope(tool_def) else await tool_def["fn"](resolved_params, user)
                await _audit_minor_read(db, user, tool_name, raw_tool_result)
                result_count = _extract_result_count(raw_tool_result)
                tool_result = _safe_tool_result_for_chat(raw_tool_result)
                count_msg = f"Found {result_count} records" if result_count is not None else "Data retrieved"

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'done'})}\n\n"
                yield thinking_event("tool_done", count_msg, tool=tool_name, count=result_count)
                await _thinking_delay()

                all_tool_calls.append({"tool": tool_name, "params": resolved_params, "result": tool_result})

            except Exception as e:
                # Part 2 Patch P3: opaque error to LLM/client, full exception logged.
                corr_id = str(uuid.uuid4())
                logger.exception("Tool execution error (%s) [%s]", tool_name, corr_id)
                tool_result = {"error": "data_unavailable", "correlation_id": corr_id}
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'error', 'error': 'data_unavailable', 'correlation_id': corr_id})}\n\n"
                all_tool_calls.append({"tool": tool_name, "params": resolved_params, "result": tool_result})
                break  # Stop chaining on error

            # ── Second (or subsequent) LLM pass with tool data ────────
            yield thinking_event("analyzing", "Processing the data...")
            await _thinking_delay()

            # BUG FIX #6: Check for empty results
            empty_msg = _extract_empty_message(tool_result)
            empty_note = ""
            if empty_msg:
                empty_note = f"\n\nNote: The tool returned no data with this message: \"{empty_msg}\". Relay this to the user helpfully."

            # R9.2 AC1 (M10): tool JSON is already PII-redacted upstream; topic-
            # blocking over it would nuke legitimate data on one stray keyword.
            tool_data_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
            tool_msg = (
                f"Tool '{tool_name}' data:\n"
                f"{tool_data_str}"
                f"{empty_note}\n\n"
                f"Now provide a comprehensive, well-formatted natural language response. "
                f"Call another tool only if it is strictly required to answer."
            )
            messages_for_llm_final = messages_for_llm[:-1] + [
                {"role": "user", "content": _user_content(user_text, image_data)},
                {"role": "assistant", "content": "Fetching data..."},
                {"role": "user", "content": tool_msg},
            ]

            # Part 2 Patch P5: bounded LLM call with cleanup (mirrors Phase 8).
            llm_task_done = asyncio.Event()
            llm_response = ""
            llm_tokens = 0
            llm_ok = True           # R1.7: availability tracked explicitly, not by result type
            llm_tool_calls = []     # R11.2: reset per round
            # LLM_WALLCLOCK_BUDGET is a module constant (see top of file)

            async def _llm_followup():
                nonlocal llm_response, llm_tokens, llm_ok, llm_tool_calls, llm_reason
                try:
                    session_id = f"{conv_id}-{uuid.uuid4()}"
                    result = await llm_client.chat(system_prompt, messages_for_llm_final, session_id, tools=llm_tools)
                    llm_response = result.text
                    llm_tokens = result.tokens
                    llm_ok = result.ok
                    llm_tool_calls = result.tool_calls or []
                    llm_reason = result.reason
                except Exception:
                    logger.exception("LLM follow-up call raised unexpectedly")
                    llm_response = ""
                    llm_tokens = 0
                    llm_ok = False
                    llm_tool_calls = []
                finally:
                    llm_task_done.set()

            llm_task = asyncio.create_task(_llm_followup())

            try:
                elapsed = 0
                while not llm_task_done.is_set():
                    try:
                        await asyncio.wait_for(
                            llm_task_done.wait(),
                            timeout=KEEPALIVE_INTERVAL,
                        )
                    except asyncio.TimeoutError:
                        elapsed += KEEPALIVE_INTERVAL
                        if elapsed >= LLM_WALLCLOCK_BUDGET:
                            llm_response = ""
                            llm_tokens = 0
                            llm_ok = False
                            break
                        if request is not None:
                            try:
                                if await request.is_disconnected():
                                    break
                            except Exception:
                                pass
                        yield keepalive_event()
            finally:
                if not llm_task.done():
                    llm_task.cancel()

            if not llm_ok:
                yield _ai_unavailable_event()
                ai_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=AI_UNAVAILABLE_MESSAGE,
                    tool_calls=all_tool_calls if all_tool_calls else None,
                    language_detected=lang,
                )
                await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
                await _record_turn_trace(
                    db, conv_id=conv_id, message_id=ai_msg.id, user=user, outcome="unavailable",
                    lang=lang, tool_calls=all_tool_calls, llm_reason=llm_reason, llm_ok=False,
                    error_type="ai_unavailable", tokens=total_tokens_used,
                )
                yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"
                return

            total_tokens_used += safe_token_count(llm_tokens, llm_response)

            # R11.2: the follow-up may request another tool — that structured
            # request drives the next loop iteration (bounded by MAX_TOOL_ROUNDS).
            pending_calls = _tool_calls_to_candidates(llm_tool_calls)
        else:
            # R1.5 AC3: while-else runs only when the loop exits by exhausting
            # MAX_TOOL_ROUNDS (no break). If the model STILL wants another tool,
            # we've hit the chaining limit — narrate it instead of ending on a
            # dangling, answerless tool request.
            if pending_calls:
                llm_response = (
                    "This request needs more steps than I can chain in one go — "
                    "try narrowing it or asking for one part at a time."
                )

    except Exception as e:
        logger.error(f"Phase 9 (multi-tool chaining) error: {e}")
        # R1.5 AC4: surface an error event; Phase 14's contract then persists a
        # fallback assistant message so the turn is never silent and history is
        # not poisoned with an unanswered question.
        yield f"data: {json.dumps({'type': 'error', 'phase': 'tool_chaining', 'message': 'I hit a problem while working through that request.'})}\n\n"
        if not (llm_response and llm_response.strip()):
            llm_response = FALLBACK_TEXT

    # ── Phase 9b: Memory auto-save + skill distillation (Epic G) ──────────
    # Owner/Principal only. Auto-saves clearly-durable info, distills a skill from
    # complex runs, and returns an in-chat yes/no question for uncertain items that
    # is appended to the reply (no UI). Best-effort; never blocks the answer.
    memory_followup_question = None
    try:
        _history_for_skill = list(messages_for_llm) + [{"role": "assistant", "content": llm_response or ""}]
        memory_followup_question = await chat_memory.finalize_turn(
            db, user,
            user_text=user_text,
            assistant_text=llm_response or "",
            conv_id=conv_id,
            history=_history_for_skill,
            round_count=tool_rounds,
            tool_count=len(all_tool_calls),
            # R10.3 AC1/AC3: the tools this turn used anchor the routine proposal +
            # its drift signature.
            tool_names=[c.get("tool") for c in all_tool_calls if c.get("tool")],
        )
    except Exception as e:
        logger.warning(f"Phase 9b (memory finalize) non-fatal: {e}")

    # ── Phase 10: (removed) residual tool-JSON stripping ──────────────────
    # R11.2: with native function calling the model emits tool calls as
    # structured `tool_calls`, never as JSON embedded in prose, so there is no
    # residual tool JSON to strip out of the final answer. `llm_response` is
    # already clean natural-language text (or the fallback set above).

    # ── Phase 13a: TRUE token streaming of the final answer (R11.3) ───────
    # The final-answer LLM call uses stream=True and its deltas are forwarded as
    # `text_delta` events for real first-token latency (AC1/AC2). We stream only
    # a genuine model synthesis (not a canned dead-end message, not a pending
    # tool request) and only for non-student roles — the student content filter
    # must run BEFORE any text reaches a student, so students keep the buffered
    # filter-then-emit path below. Confidentiality: no provider/model identity is
    # ever emitted — deltas carry only the assistant's words.
    _role = user.get("role")
    stream_error = None
    stream_final = (
        _role != "student"
        and llm_ok
        and not pending_calls
        and (llm_response or "") != FALLBACK_TEXT
        and bool(messages_for_llm_final)
    )
    raw_final = llm_response or ""

    _composing_sent = False
    if stream_final:
        yield thinking_event("composing", "Writing your answer...")
        await _thinking_delay()
        _composing_sent = True
        _sink: dict = {}
        try:
            async for _ev in _stream_final_answer(
                system_prompt, messages_for_llm_final, f"{conv_id}-final-{uuid.uuid4()}", _sink
            ):
                yield _ev
        except Exception as e:
            logger.error("Phase 13 (stream final answer) error: %s", e)
            _sink.setdefault("text", "")
            _sink["ok"] = False
            _sink["error"] = "stream_failed"

        streamed_text = _sink.get("text") or ""
        if streamed_text.strip():
            # Streaming produced real content.
            raw_final = streamed_text
            total_tokens_used += safe_token_count(_sink.get("tokens", 0), raw_final)
            if not _sink.get("ok"):
                # AC3: a mid-stream provider failure keeps the partial text and
                # marks the turn interrupted; the R1 contract persists it below.
                stream_error = _sink.get("error") or "stream_failed"
                raw_final = raw_final.rstrip() + "\n\n_(reply interrupted — please retry)_"
                yield f"data: {json.dumps({'type': 'error', 'phase': 'streaming', 'message': 'The reply was interrupted. Please try again.'})}\n\n"
        else:
            # Streaming yielded nothing (e.g. not configured / instant failure):
            # progressive enhancement falls back to the buffered detection-call
            # answer, delivered via the simulated-chunk path below. Nothing was
            # shown to the user yet, so this is seamless.
            stream_final = False
            raw_final = llm_response or ""

    # ── Phase 11: Content filter on output ────────────────────────────────
    # Passthrough for non-student roles; enforces topic-blocking for students.
    try:
        clean_response = filter_response(raw_final, _role)
    except Exception as e:
        logger.error(f"Phase 11 (content filter) error: {e}")
        clean_response = raw_final

    # Strip content-policy hallucination — the LLM occasionally generates this
    # boilerplate from poisoned conversation history. Detect and remove it so
    # it never reaches the user regardless of role.
    # R1.4: keep ONLY true content-policy boilerplate. The removed markers
    # ("try rephrasing your question", "wasn't able to process that") are ordinary
    # phrases a genuine answer may contain — matching them nuked real replies.
    _CONTENT_POLICY_MARKERS = [
        "content policy settings on the AI service",
        "school management tools in the sidebar are fully available",
    ]
    if any(marker.lower() in clean_response.lower() for marker in _CONTENT_POLICY_MARKERS):
        # R1.4: replace with the fallback, NEVER blank the response to "".
        logger.warning("LLM generated content-policy boilerplate; replacing with fallback | conv=%s", conv_id)
        clean_response = FALLBACK_TEXT

    # ── Phase 12: Parse rich content ──────────────────────────────────────
    clean_text, rich_content = _extract_rich_content(clean_response)

    # Epic G (G.4): append the in-chat "remember that?" question to the reply when
    # the assistant is genuinely uncertain (never a UI control). Only when there is
    # already some answer text, so we don't surface a bare question.
    _followup_appended = False
    if memory_followup_question and clean_text and clean_text.strip():
        clean_text = clean_text + memory_followup_question
        _followup_appended = True

    # ── R1.3 Turn Completion Contract: substitute the fallback BEFORE streaming ──
    # This is the choke point for the silent-empty-turn incident. If the turn has
    # neither text nor rich blocks (confirm/error/tool paths already returned with
    # their own persisted message above), the user still gets words — streamed and
    # persisted below with a real message id (never the old f"empty-{conv_id}").
    _has_rich = bool(rich_content and (rich_content.get('rich_blocks') or rich_content.get('action_buttons')))
    if not (clean_text and clean_text.strip()) and not _has_rich:
        logger.warning("Empty final turn — substituting FALLBACK_TEXT | conv=%s", conv_id)
        clean_text = FALLBACK_TEXT

    # ── Phase 13: Deliver the answer ──────────────────────────────────────
    try:
        if stream_final and not stream_error:
            # Visible prose already streamed live above. Only the trailing
            # memory-followup question (if any) still needs to reach the wire so
            # the live view matches the persisted message.
            if _followup_appended and memory_followup_question:
                yield f"data: {json.dumps({'type': 'text_delta', 'delta': memory_followup_question})}\n\n"
        else:
            # Buffered path: students, canned dead-ends, streams that yielded
            # nothing (progressive-enhancement fallback).
            if not _composing_sent:
                yield thinking_event("composing", "Writing your answer...")
                await _thinking_delay()
            chunk_size = 4
            for i in range(0, len(clean_text), chunk_size):
                chunk = clean_text[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'text_delta', 'delta': chunk})}\n\n"
                await asyncio.sleep(0.008)

        # Send rich content block. R9.2 AC1 (M10): structured output gets a narrow
        # PII-only pass (redact_for_llm), NOT topic-blocking — a blocked word inside
        # a legitimate table cell must not nuke the whole block. The LLM's prose is
        # already topic-filtered above (clean_response).
        if rich_content:
            if _role == "student":
                try:
                    rich_content["rich_blocks"] = redact_for_llm(rich_content.get("rich_blocks", []))
                    rich_content["action_buttons"] = redact_for_llm(rich_content.get("action_buttons", []))
                except Exception:
                    pass
            yield f"data: {json.dumps({'type': 'rich_blocks', 'blocks': rich_content.get('rich_blocks', []), 'action_buttons': rich_content.get('action_buttons', [])})}\n\n"

    except Exception as e:
        logger.error(f"Phase 13 (streaming) error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'phase': 'streaming', 'message': 'Error while streaming response.'})}\n\n"

    # ── Phase 14: Save AI message to DB (BUG FIX #7: persist BEFORE done event) ──
    # R1.3: single completion choke point. clean_text is guaranteed non-empty by
    # the fallback substitution above, so this ALWAYS persists a real assistant
    # message with a real uuid and ALWAYS debits tokens — the old
    # empty-turn short-circuit (done + f"empty-{conv_id}", no persist, no debit)
    # is gone. A turn can no longer end silently or escape token accounting.
    try:
        ai_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=clean_text,
            rich_content=rich_content,
            tool_calls=all_tool_calls if all_tool_calls else None,
            # R10.4 AC2: disclose the memories recalled into this reply.
            recalled_memories=recalled_memories if recalled_memories else None,
            language_detected=lang,
        )
        await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
        # R10.4 AC2: surface recalled memories to the live stream so the "Data used"
        # footer shows them without a reload (matches the persisted message).
        if recalled_memories:
            yield f"data: {json.dumps({'type': 'recalled_memories', 'memories': recalled_memories})}\n\n"

        # ── Phase 14b: Record token usage ────────────────────────────────
        try:
            await record_usage(
                user, branch_id, total_tokens_used,
                budget_check.get("source", "unlimited"),
                conversation_id=conv_id,
                tool_name=tool_name,
            )
        except Exception as e:
            logger.error(f"Phase 14b (record token usage) error: {e}")

        # ── Phase 14c: turn-outcome metric (R9.3 AC3 / architecture §8) ──
        # The permanent alarm for the silent-empty-turn incident class: a spike in
        # `fallback`/`error` relative to `answered` is the regression signal.
        # Fail-open (record_ai_metric never raises).
        outcome = "error" if stream_error else ("fallback" if clean_text == FALLBACK_TEXT else "answered")
        await record_ai_metric(
            db, event="ai_turn_outcome", status=outcome,
            user_id=user["id"], tool_name=tool_name or "",
            school_id=get_school_id(), branch_id=branch_id,
        )
        # R11.5: per-turn diagnostic trace for the conversation trace viewer.
        await _record_turn_trace(
            db, conv_id=conv_id, message_id=ai_msg.id, user=user, outcome=outcome,
            lang=lang, tool_calls=all_tool_calls, llm_reason=llm_reason,
            llm_ok=(not stream_error), error_type=stream_error, tokens=total_tokens_used,
        )

        # BUG FIX #7: done event comes AFTER persistence
        yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"

    except Exception as e:
        logger.error(f"Phase 14 (persistence) error: {e}")
        # Still send done event even if persistence fails
        yield f"data: {json.dumps({'type': 'done', 'tokens_used': total_tokens_used, 'error': 'Message saved but may not persist.'})}\n\n"


# ─── Helper: check if tool function accepts scope parameter ───────────────────

def _tool_accepts_scope(tool_def: dict) -> bool:
    """
    Check if a tool function accepts a scope parameter (3 args vs 2).
    Existing tools take (params, user). New tools may take (params, user, scope).
    We try gracefully: if the function signature has 3+ params, pass scope.
    """
    import inspect
    fn = tool_def.get("fn")
    if fn is None:
        return False
    try:
        sig = inspect.signature(fn)
        return len(sig.parameters) >= 3
    except (ValueError, TypeError):
        return False


# ─── SSE streaming endpoint ──────────────────────────────────────────────────

@router.post("/conversations/{conv_id}/messages")
async def send_message(conv_id: str, request: Request):
    db = get_db()
    user = get_current_user(request)
    await _require_owned_conversation(db, conv_id, user)
    body = await request.json()
    _raw_text = body.get("text", "") or ""
    # Strip zero-width and normal whitespace before empty-message check (P11 E7)
    user_text = re.sub(r"[​‌‍⁠﻿\s]+", " ", _raw_text).strip()
    image_data = body.get("image_data") or None  # base64 data URL for vision
    if image_data is not None:
        # R9.4 (X8) AC3: reject a malformed/oversized image before it reaches the LLM.
        img_err = _validate_image_data(image_data)
        if img_err:
            return {"success": False, "error": img_err}
    if not user_text and not image_data:
        return {"success": False, "error": "Empty message"}
    if not user_text:
        user_text = "[Image attached — please describe or ask about the image]"
    raw_session_id = body.get("session_id") or request.headers.get("x-session-id") or request.headers.get("X-SSE-Session-ID")
    session_id = (raw_session_id or "").strip()
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.warning("chat_sse_session_id_missing", extra={"conversation_id": conv_id, "generated_session_id": session_id})

    from services.layaastat import emit_event
    # R7.3/AC5: the auth user dict keys id as "id" (not "user_id"), so the old
    # user.get("user_id") sent distinct_id=None — anonymising every analytics event.
    await emit_event("ai_chat_message", distinct_id=user["id"], payload={"role": user.get("role", "")})
    return StreamingResponse(
        _generate_chat_sse(conv_id, user_text, user, session_id=session_id, request=request, image_data=image_data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ─── Action execution endpoint ───────────────────────────────────────────────

@router.post("/conversations/{conv_id}/action")
async def execute_action(conv_id: str, request: Request):
    """Execute an action button directly (not through LLM) and add result to chat."""
    db = get_db()
    user = get_current_user(request)
    await _require_owned_conversation(db, conv_id, user)
    body = await request.json()
    action = body.get("action")
    params = body.get("params", {})
    label = body.get("label", action)

    tool_def = TOOL_REGISTRY.get(action)
    if not tool_def:
        return {"success": False, "error": f"Unknown action: {action}"}
    # auth: registry enforces role + sub_category — see _is_tool_authorized
    if not _is_tool_authorized(user, tool_def):
        return {"success": False, "error": "Forbidden"}
    if action in WRITE_ACTION_TOOLS:
        raise HTTPException(
            status_code=400,
            detail="Write actions must be confirmed through /api/chat/confirm",
        )

    try:
        # Resolve scope for the action
        scope = await resolve_scope(user, db)

        if _tool_accepts_scope(tool_def):
            result = await tool_def["fn"](params, user, scope)
        else:
            result = await tool_def["fn"](params, user)

        msg_content = result.get("message", f"Action '{label}' completed successfully.")

        # Save as AI message
        ai_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=msg_content,
            tool_calls=[{"tool": action, "params": params, "result": result}],
            language_detected="en",
        )
        await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
        await db.conversations.update_one(
            _owned_conversation_filter(conv_id, user),
            {"$set": {"updated_at": datetime.now().isoformat()}},
        )

        return {
            "success": True,
            "data": {
                "message": msg_content,
                "result": result,
                "message_id": ai_msg.id,
            },
        }
    except Exception as e:
        # Part 2 Patch P3: opaque error to client; correlation_id for log lookup.
        corr_id = str(uuid.uuid4())
        logger.exception("Action execution error (%s) [%s]", action, corr_id)
        return {"success": False, "error": "internal_error", "correlation_id": corr_id}


# ─── Confirm action endpoint ─────────────────────────────────────────────────

async def _execute_confirmed_dispatch(token: str, session_id: str, user: dict, db, conv_id: str = None, destructive_ack: bool = False):
    if conv_id:
        await _require_owned_conversation(db, conv_id, user)

    # Validate token ownership BEFORE incrementing the rate-limit counter.
    # If we incremented first, an attacker (or a buggy client) firing
    # invalid/expired tokens could DoS a user's hourly budget. The peek call
    # returns the token doc (including used=True replays) when (user, session)
    # match, else None — giving us authentication-style proof of intent.
    token_meta = await peek_confirm_token(
        token=token,
        user_id=user["id"],
        session_id=session_id,
        db=db,
    )
    if token_meta is None or token_meta.get("used"):
        # Missing / wrong owner / wrong session / already-used token: surface
        # the precise 4xx via the existing consume path without touching the
        # rate counter. Invalid tokens must not burn a user's hourly budget.
        await consume_confirm_token(
            token=token,
            user_id=user["id"],
            session_id=session_id,
            db=db,
        )
        # consume_confirm_token always raises in this path; defensive fallthrough.
        raise HTTPException(status_code=400, detail="Confirmation token is invalid")

    # F.4/AD9: AI-write kill-switch. Checked BEFORE the rate gate AND token consume
    # so a blocked write neither burns the one-shot token nor a rate slot — the user
    # can retry once an operator re-enables writes. Reads never reach this path.
    # R9.3 (M8): force_fresh bypasses the per-worker cache and reads Mongo directly,
    # so an operator's disable takes effect on the next confirmed write across ALL
    # workers (not up to CACHE_TTL_SECONDS later on a stale worker).
    if not await ai_writes_enabled(db, force_fresh=True):
        await record_ai_metric(
            db, event="kill_switch_blocked",
            user_id=user["id"], tool_name=token_meta.get("action", "<unknown>"),
        )
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ai_writes_disabled",
                "message": (
                    "AI actions are temporarily disabled by your administrator. "
                    "You can still ask questions, or use the panel directly."
                ),
            },
        )

    # F.10/FR42: two-step destructive confirmation. A plan/action containing a
    # delete requires a SECOND explicit acknowledgment beyond the plan-confirm.
    # Checked on the PEEKED token, before the rate gate + consume, so a missing ack
    # burns neither the one-shot token nor a rate slot — the client re-confirms with
    # destructive_ack=True (a single rate slot is taken on the acknowledged attempt).
    destructive_steps = _token_meta_destructive_steps(token_meta)
    if destructive_steps and not destructive_ack:
        tools = sorted({s.get("tool") for s in destructive_steps})
        raise HTTPException(
            status_code=409,
            detail={
                "code": "destructive_confirmation_required",
                "message": (
                    "This includes a permanent deletion. Please confirm a second "
                    "time to proceed — this cannot be undone."
                ),
                "destructive_tools": tools,
            },
        )

    # Rate-limit gate runs BEFORE token consumption. A rejected request must
    # not burn the user's one-shot confirm token — they should be able to
    # retry the same action once the next clock-hour begins. school_id comes
    # from the authoritative tenant context (env), never from caller-supplied
    # fields, so per-tenant overrides cannot be spoofed.
    rate_result = await _ai_rate_check(
        user_id=user["id"],
        role=user.get("role") or "",
        school_id=get_school_id(),
        db=db,
    )
    if not rate_result.allowed:
        await audit_ai_rate_limit_hit(
            tool_name=token_meta.get("action", "<unknown>"),
            params=token_meta.get("params") or {},
            user_id=user["id"],
            session_id=session_id,
            limit=rate_result.limit,
            db=db,
        )
        raise RateLimitExceeded(
            payload=rate_result.to_response_payload(),
            retry_after=rate_result.retry_after_seconds,
        )

    try:
        token_doc = await consume_confirm_token(
            token=token,
            user_id=user["id"],
            session_id=session_id,
            school_id=get_school_id(),
            branch_id=user.get("branch_id"),
            db=db,
        )
    except HTTPException as exc:
        if exc.status_code == 409:
            # Concurrent replay or tenant mismatch: rate-limit counter was already
            # incremented for this request but the dispatch won't happen. Undo the
            # increment so the losing request doesn't permanently reduce the budget.
            await _ai_rate_decrement(user_id=user["id"], db=db)
        # XM6/E.5: a token that expired while the user was reading the plan gets a
        # clear, re-planable message — keyed off the TYPED reason code, never a
        # brittle string-match on the detail text. The original intent is echoed
        # so the client can re-issue in one tap.
        detail_code = exc.detail.get("code") if isinstance(exc.detail, dict) else None
        if exc.status_code == 400 and detail_code == "token_expired":
            await _ai_rate_decrement(user_id=user["id"], db=db)
            intent = exc.detail.get("intent") if isinstance(exc.detail, dict) else None
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "plan_expired",
                    "message": (
                        "This plan expired before it was confirmed. Just ask again "
                        "and I'll rebuild it for you."
                    ),
                    "intent": intent,
                },
            ) from exc
        raise
    # Epic E (AD3): a token may carry an ordered multi-step `plan`; a legacy
    # token carries a single `action`/`params` and consumes as a length-1 plan.
    plan_steps = token_doc.get("plan")
    if plan_steps:
        write_step_dicts = [s for s in plan_steps if s.get("kind", "write") == "write"]
        if not write_step_dicts:
            raise HTTPException(status_code=400, detail="Confirmation token has no write steps")
        # AD14: authorize EVERY step before executing any — a plan with one
        # unauthorized step is rejected whole, never partially executed.
        for s in write_step_dicts:
            s_tool = s.get("tool")
            # F.10: student hard-delete / DPDP-erase are never AI-executable.
            if s_tool in FORBIDDEN_AI_TOOLS:
                raise HTTPException(status_code=403, detail="Forbidden")
            s_def = TOOL_REGISTRY.get(s_tool)
            if not s_def:
                raise HTTPException(status_code=400, detail=f"Unknown tool: {s_tool}")
            if s_tool not in WRITE_ACTION_TOOLS:
                raise HTTPException(status_code=400, detail=f"Step '{s_tool}' is not a write action")
            if not _is_tool_authorized(user, s_def):
                raise HTTPException(status_code=403, detail="Forbidden")
        tool_name = "plan"  # audit/forensic label for the whole dispatch
        params = {"steps": plan_steps}
    else:
        tool_name = token_doc.get("action")
        params = token_doc.get("params") or {}
        # F.10: student hard-delete / DPDP-erase are never AI-executable.
        if tool_name in FORBIDDEN_AI_TOOLS:
            raise HTTPException(status_code=403, detail="Forbidden")
        tool_def = TOOL_REGISTRY.get(tool_name)
        if not tool_def:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
        if tool_name not in WRITE_ACTION_TOOLS:
            raise HTTPException(status_code=400, detail="Confirmation token is not for a write action")
        # auth: registry enforces role + sub_category — see _is_tool_authorized
        if not _is_tool_authorized(user, tool_def):
            raise HTTPException(status_code=403, detail="Forbidden")

    # Part 4 Story 4.2: write-ahead audit row — fail-open with structured warning.
    # Audit failure must not block AI responses; proceed and log loudly.
    # AD14: a whole plan is ONE dispatch — a single audit row, not one per step.
    audit_id = None
    try:
        audit_id = await audit_ai_dispatch_pending(
            tool_name=tool_name,
            params=params,
            user_id=user["id"],
            session_id=session_id,
            confirmed_at=token_doc.get("confirmed_at"),
            school_id=get_school_id(),
            branch_id=user.get("branch_id"),
            db=db,
            dispatch_id=f"ai-dispatch-{token}",
        )
    except Exception:
        logger.warning(
            "audit_pre_write_failed",
            exc_info=True,
            extra={"action_name": tool_name, "user_id": user.get("id", "")},
        )
        # Proceed — audit failure must not block AI responses

    try:
        scope = await resolve_scope(user, db)

        def _make_runner(s_tool: str, s_params: dict):
            s_def = TOOL_REGISTRY.get(s_tool)
            accepts_scope = _tool_accepts_scope(s_def)

            async def _runner():
                # The forward write action. Runs inside the executor's transaction;
                # the tool's services enlist via the ambient txn-session contextvar.
                if accepts_scope:
                    return await s_def["fn"](s_params, user, scope)
                return await s_def["fn"](s_params, user)

            return _runner

        if plan_steps:
            # AD4/D.3: same single execution path — a resolved multi-step plan.
            plan = plan_from_steps(
                steps=plan_steps,
                runner_factory=lambda raw: _make_runner(raw.get("tool"), raw.get("params") or {}),
                school_id=get_school_id(),
                branch_id=user.get("branch_id"),
                plan_token=token,
            )
        else:
            # Legacy single confirmed write — a one-step plan (no len==1 fork).
            plan = single_write_plan(
                tool=tool_name,
                params=params,
                runner=_make_runner(tool_name, params),
                school_id=get_school_id(),
                branch_id=user.get("branch_id"),
                plan_token=token,
            )
        # F.5: shadow/dry-run — runs the writes in an always-aborted txn and
        # reports the would-be effect, committing nothing (saga side-effects skipped).
        dry_run = await ai_dry_run_enabled(db)
        exec_result = await plan_executor.run(plan, db=db, dry_run=dry_run)
        if exec_result.dry_run:
            result = {
                "success": True,
                "dry_run": True,
                "message": "Shadow mode: showing what would change — nothing was committed.",
                "would_change": exec_result.step_results,
            }
        elif exec_result.status == "already_applied":
            # Idempotent replay (concurrent/duplicate confirm) — nothing re-applied.
            result = {
                "success": True,
                "idempotent_replay": True,
                "message": "This action was already applied.",
            }
        elif plan_steps:
            # Surface every step's result for the multi-step plan.
            result = {
                "success": True,
                "message": f"Completed all {len(exec_result.step_results)} steps.",
                "steps": exec_result.step_results,
            }
        elif exec_result.step_results:
            result = exec_result.step_results[0].get("result")
        else:
            result = None
        # XM9: everything below runs AFTER the transaction committed. A failure in
        # a post-commit metric/audit write must NEVER turn a committed plan into a
        # user-facing 500 — the writes are already durable. Catch + log loudly and
        # still return the success reply.
        try:
            # F.7: pilot observability — one confirmation + plan_executed event per
            # dispatch, plus a per-step outcome. PII-free (tool names + statuses only).
            await record_ai_metric(
                db, event="confirmation", user_id=user["id"], tool_name=tool_name,
                status=exec_result.status, school_id=get_school_id(), branch_id=user.get("branch_id"),
            )
            await record_ai_metric(
                db, event="plan_executed", user_id=user["id"], tool_name=tool_name,
                status=exec_result.status, school_id=get_school_id(), branch_id=user.get("branch_id"),
                count=len(exec_result.step_results) or 1,
            )
            await record_ai_metric(
                db, event="ai_action", user_id=user["id"], tool_name=tool_name,
                school_id=get_school_id(), branch_id=user.get("branch_id"),
            )
            for sr in exec_result.step_results:
                await record_ai_metric(
                    db, event="step_outcome", user_id=user["id"], tool_name=sr.get("tool", tool_name),
                    status=sr.get("status", "ok"), school_id=get_school_id(), branch_id=user.get("branch_id"),
                )
            # F.10/FR42: actor-tagged deletion audit per destructive step — only when
            # the dispatch actually committed (not on an idempotent no-op replay).
            if exec_result.status == "committed":
                for ds in destructive_steps:
                    await _audit_destructive_step(db, user, ds)
        except Exception:
            logger.warning(
                "post_commit_bookkeeping_failed tool=%s user=%s — plan already committed",
                tool_name, user.get("id"), exc_info=True,
            )
    except PlanStaleError as stale:
        await audit_ai_dispatch_finalize(
            audit_id=audit_id, result=None, error="plan_stale", db=db,
        )
        raise HTTPException(
            status_code=409,
            detail={"code": stale.code, "message": str(stale)},
        )
    except NeedsManualReconciliationError as recon:
        await audit_ai_dispatch_finalize(
            audit_id=audit_id, result=None, error="needs_manual_reconciliation", db=db,
        )
        await record_ai_metric(
            db, event="torn_state", user_id=user["id"], tool_name=tool_name,
            status="needs_manual_reconciliation", school_id=get_school_id(),
            branch_id=user.get("branch_id"),
        )
        raise HTTPException(
            status_code=409,
            detail={"code": recon.code, "message": str(recon)},
        )
    except PlanScopeViolationError as scope_exc:
        # F.3: a step tried to widen tenant/branch scope — refused, nothing applied.
        await audit_ai_dispatch_finalize(
            audit_id=audit_id, result=None, error="plan_scope_violation", db=db,
        )
        await record_ai_metric(
            db, event="torn_state", user_id=user["id"], tool_name=tool_name,
            status="plan_scope_violation", school_id=get_school_id(),
            branch_id=user.get("branch_id"),
        )
        logger.warning("plan_scope_violation user=%s step=%s", user.get("id"), scope_exc.step_idx)
        raise HTTPException(status_code=403, detail="Forbidden")
    except SagaCompensatedError as saga:
        await audit_ai_dispatch_finalize(
            audit_id=audit_id, result=None, error="saga_compensated", db=db,
        )
        await record_ai_metric(
            db, event="torn_state", user_id=user["id"], tool_name=tool_name,
            status="saga_compensated", school_id=get_school_id(),
            branch_id=user.get("branch_id"),
        )
        raise HTTPException(status_code=502, detail={"code": "side_effect_failed", "message": str(saga)})
    except StepExecutionError as step_err:
        # X2/X4: a confirmed step reported failure — the transaction aborted and
        # NOTHING was applied. The audit row records the real failure and the user
        # reply names the failed step, so reply and audit always agree.
        await audit_ai_dispatch_finalize(
            audit_id=audit_id,
            result=step_err.result if isinstance(step_err.result, dict) else {"success": False},
            error=f"step_failed:{step_err.tool}", db=db,
        )
        await record_ai_metric(
            db, event="plan_executed", user_id=user["id"], tool_name=tool_name,
            status="failed", school_id=get_school_id(), branch_id=user.get("branch_id"),
        )
        logger.info(
            "confirmed_step_failed tool=%s step=%s user=%s",
            step_err.tool, step_err.step_idx, user.get("id"),
        )
        raise HTTPException(
            status_code=422,
            detail={
                "code": "step_failed",
                "message": f"{step_err} No changes were applied.",
                "failed_tool": step_err.tool,
                "failed_step": step_err.step_idx,
            },
        )
    except TransactionUnavailableError:
        # X5: outside development we refuse to run writes without a real
        # transaction. Nothing was applied; the user can retry.
        await audit_ai_dispatch_finalize(
            audit_id=audit_id, result=None, error="txn_unavailable", db=db,
        )
        logger.error("txn_unavailable — refused non-transactional confirmed write tool=%s", tool_name)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "txn_unavailable",
                "message": (
                    "We couldn't guarantee transactional safety, so nothing was "
                    "applied. Please try again in a moment."
                ),
            },
        )
    except HTTPException as http_exc:
        await audit_ai_dispatch_finalize(
            audit_id=audit_id, result=None,
            error=f"http_{http_exc.status_code}", db=db,
        )
        raise
    except Exception as exc:
        # Part 2 Patch P3: opaque to client; full exception in server logs.
        corr_id = str(uuid.uuid4())
        logger.exception("Confirm action execution error (%s) [%s]", tool_name, corr_id)
        await audit_ai_dispatch_finalize(
            audit_id=audit_id, result=None,
            error=f"internal:{corr_id}", db=db,
        )
        raise HTTPException(
            status_code=500,
            detail=f"An internal error occurred (id={corr_id})",
        ) from exc

    await audit_ai_dispatch_finalize(
        audit_id=audit_id,
        result=result if isinstance(result, dict) else None,
        db=db,
    )

    msg_content = (
        result.get("message", f"Action '{tool_name}' completed successfully.")
        if isinstance(result, dict)
        else f"Action '{tool_name}' completed successfully."
    )
    message_id = None
    if conv_id:
        # XM9: the plan already committed. Persisting the assistant transcript
        # message is best-effort — a Mongo hiccup here must NOT turn a durable,
        # committed action into a user-facing 500.
        try:
            ai_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=msg_content,
                tool_calls=[{"tool": tool_name, "params": params, "result": result, "token": token}],
                language_detected="en",
            )
            await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
            await db.conversations.update_one(
                _owned_conversation_filter(conv_id, user),
                {"$set": {"updated_at": datetime.now().isoformat()}},
            )
            message_id = ai_msg.id
        except Exception:
            logger.warning(
                "post_commit_message_persist_failed tool=%s user=%s — action already committed",
                tool_name, user.get("id"), exc_info=True,
            )

    return {
        "success": True,
        "data": {
            "message": msg_content,
            "result": result,
            "message_id": message_id,
            "tool": tool_name,
        },
    }


@router.post("/confirm")
async def confirm_token_action(request: Request):
    """Execute a server-issued AI confirmation token."""
    db = get_db()
    user = get_current_user(request)
    body = await request.json()
    decision = body.get("decision", "")
    confirmed = body.get("confirmed", False) or decision == "confirm"

    if not confirmed:
        return {"success": True, "data": {"message": "Action cancelled.", "cancelled": True}}

    token = body.get("token") or body.get("action_id")
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    destructive_ack = bool(body.get("destructive_ack") or body.get("acknowledge_destructive"))
    try:
        return await _execute_confirmed_dispatch(
            token, session_id, user, db, body.get("conversation_id"), destructive_ack=destructive_ack
        )
    except RateLimitExceeded as exc:
        return JSONResponse(
            status_code=429,
            content=exc.payload,
            headers={"Retry-After": str(exc.retry_after)},
        )


@router.post("/conversations/{conv_id}/confirm")
async def confirm_action(conv_id: str, request: Request):
    """
    Compatibility endpoint for confirm_action events.
    Body: {"token": "...", "session_id": "...", "confirmed": true/false}
    """
    db = get_db()
    user = get_current_user(request)
    body = await request.json()
    decision = body.get("decision", "")
    confirmed = body.get("confirmed", False) or decision == "confirm"

    if not confirmed:
        await _require_owned_conversation(db, conv_id, user)
        cancel_msg = "Action cancelled. Let me know if you need anything else."
        ai_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=cancel_msg,
            language_detected="en",
        )
        await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
        return {
            "success": True,
            "data": {"message": cancel_msg, "message_id": ai_msg.id, "cancelled": True},
        }

    token = body.get("token") or body.get("action_id")
    session_id = body.get("session_id") or conv_id
    destructive_ack = bool(body.get("destructive_ack") or body.get("acknowledge_destructive"))
    try:
        return await _execute_confirmed_dispatch(
            token, session_id, user, db, conv_id, destructive_ack=destructive_ack
        )
    except RateLimitExceeded as exc:
        return JSONResponse(
            status_code=429,
            content=exc.payload,
            headers={"Retry-After": str(exc.retry_after)},
        )


@router.post("/feedback")
async def submit_feedback(request: Request):
    user = get_current_user(request)
    db = get_db()
    body = await request.json()
    rating = body.get("rating")
    if rating not in (0, 1):
        raise HTTPException(400, "rating must be 0 or 1")
    # R10.2 AC1/AC2: persist a tenant-scoped feedback record; an "Improve" (0) with
    # a one-line reason is parked as a PENDING candidate correction (never
    # auto-active, never recalled until an owner/principal activates it via R10.4).
    from services.memory.feedback_store import record_feedback
    await record_feedback(
        db, user,
        verdict=int(rating),
        conversation_id=(body.get("conversation_id") or "").strip() or None,
        message_id=(body.get("message_id") or "").strip() or None,
        reason=body.get("reason") or "",
        tool_names=body.get("tool_names") if isinstance(body.get("tool_names"), list) else None,
    )
    from services.layaastat import emit_event
    # R7.3/AC5 parity: distinct_id keys on "id" (user.get("user_id") was always None).
    await emit_event("ai_feedback", distinct_id=user.get("id"), payload={"rating": rating})
    return {"success": True}
