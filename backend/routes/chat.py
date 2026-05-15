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
import random
import re
import time
import uuid
import logging
from datetime import datetime, date, timedelta
from typing import Any, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from database import get_db
from models.schemas import Conversation, Message, ConversationUpdate
from ai.llm_client import ai_unavailable_result, llm_client
from ai.prompts import build_system_prompt
from ai.context_builder import build_school_context, detect_language
from ai.tool_functions_v2 import TOOL_REGISTRY, WRITE_TOOL_NAMES
from ai.scope_resolver import resolve_scope, Scope
from ai.content_filter import filter_response, check_input_safety
from middleware.auth import get_current_user
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
from tenant import get_school_id, scoped_filter


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

MAX_TOOL_ROUNDS = 3
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
    "content": "announcement content",
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

@router.get("/conversations")
async def list_conversations(request: Request):
    db = get_db()
    user = get_current_user(request)
    convs = await db.conversations.find(
        scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    return {"success": True, "data": convs}


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


def _normalize_tool_call(data: Any) -> Optional[dict]:
    """Normalize supported model tool JSON shapes to {action, params, reason}."""
    if not isinstance(data, dict):
        return None

    if "action" in data:
        action = data.get("action")
        params = data.get("params") or {}
        if isinstance(action, str) and isinstance(params, dict):
            return {
                "action": action,
                "params": params,
                "reason": data.get("reason", ""),
                "confirm_requested": False,
            }

    if data.get("confirm_action") is True and isinstance(data.get("tool"), str):
        params = data.get("params") or {}
        if isinstance(params, dict):
            return {
                "action": data["tool"],
                "params": params,
                "reason": data.get("display") or data.get("reason", ""),
                "confirm_requested": True,
            }

    return None


def _parse_tool_calls(text) -> list[dict]:
    """
    Parse one or more model tool calls.

    Handles:
      - Raw JSON object: {"action": "tool_name", "params": {...}}
      - Confirmation JSON: {"confirm_action": true, "tool": "...", "params": {...}}
      - JSON arrays of either shape
      - Markdown-fenced JSON
      - JSON embedded in prose
    """
    # Part 2 Patch P3: defensive — if upstream slipped a non-string (e.g. an
    # ai_unavailable dict from llm_client), do not raise inside json/regex code.
    if not isinstance(text, str):
        return []
    parsed_calls: list[dict] = []
    for candidate in _json_candidates(text):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue

        if isinstance(data, list):
            for item in data:
                normalized = _normalize_tool_call(item)
                if normalized:
                    parsed_calls.append(normalized)
        else:
            normalized = _normalize_tool_call(data)
            if normalized:
                parsed_calls.append(normalized)

    return parsed_calls


def _parse_tool_call(text: str) -> Optional[dict]:
    """Return the first model tool call, preserving the legacy helper contract."""
    calls = _parse_tool_calls(text)
    return calls[0] if calls else None


def _strip_tool_json_from_text(text) -> str:
    """Remove residual tool/navigation JSON from a natural-language response."""
    # Part 2 Patch P3: bail out cleanly on non-string input.
    if not isinstance(text, str):
        return ""
    cleaned = text
    for candidate in _json_candidates(text):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        is_tool_array = isinstance(data, list) and any(_normalize_tool_call(item) for item in data)
        if _normalize_tool_call(data) or is_tool_array or (isinstance(data, dict) and "navigate" in data):
            cleaned = cleaned.replace(candidate, "")
    cleaned = re.sub(r"```(?:json)?\s*```", "", cleaned)
    return cleaned.strip()


# ─── Tool authorization ───────────────────────────────────────────────────────

def _is_tool_authorized(user: dict, tool_def: dict) -> bool:
    """Check role + sub_category authorization against TOOL_REGISTRY definition.

    sub_categories: None means no sub_category restriction (any admin).
    sub_categories: [...] means admin must have a matching sub_category;
    non-admin roles that appear in roles[] are never blocked by sub_categories.
    """
    if user.get("role") not in tool_def.get("roles", []):
        return False
    sub_categories = tool_def.get("sub_categories")
    if sub_categories is None:
        return True
    if user.get("role") != "admin":
        return True
    return user.get("sub_category") in sub_categories


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

def detect_navigate(text: str) -> Optional[str]:
    """Detect if user wants to navigate to a specific tool/page."""
    text_lower = text.lower().strip()
    for phrase, tool_id in NAVIGATE_MAP.items():
        if phrase in text_lower:
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
    """Try to extract a record count from a tool result dict."""
    if not isinstance(result, dict):
        return None

    # Direct count fields
    for key in ("total", "count", "total_alerts", "total_defaulters",
                "total_staff", "total_students"):
        if key in result and isinstance(result[key], (int, float)):
            return int(result[key])

    # Check for lists and return their length
    for key, val in result.items():
        if isinstance(val, list) and key not in ("rich_blocks", "action_buttons"):
            return len(val)

    # Check nested summary
    if "summary" in result and isinstance(result["summary"], dict):
        for key in ("total_students", "total_staff"):
            if key in result["summary"]:
                return int(result["summary"][key])

    return None


# ─── Extract empty-result message (BUG FIX #6) ───────────────────────────────

def _extract_empty_message(result: dict) -> Optional[str]:
    """
    If tool returned an empty data set, extract the context-aware
    empty message if present.
    """
    if not isinstance(result, dict):
        return None

    # Check if there's an explicit message with empty data
    has_empty_data = False
    for key, val in result.items():
        if isinstance(val, list) and len(val) == 0:
            has_empty_data = True
            break

    if has_empty_data and "message" in result:
        return result["message"]

    # Also check total == 0
    for count_key in ("total", "count", "total_alerts", "total_defaulters"):
        if result.get(count_key) == 0 and "message" in result:
            return result["message"]

    return None


def _mask_phone(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "XX"
    return f"{digits[:2]}XX-XXX-{digits[-3:]}"


def _safe_tool_result_for_chat(value: Any) -> Any:
    """
    Redact high-risk personal fields before storing tool traces or sending
    tool output back into the model for final narration.
    """
    if isinstance(value, list):
        return [_safe_tool_result_for_chat(item) for item in value]

    if not isinstance(value, dict):
        return value

    safe: dict[str, Any] = {}
    restricted_exact = {
        "address",
        "home_address",
        "date_of_birth",
        "dob",
        "aadhaar",
        "aadhaar_number",
        "password",
        "password_hash",
        "salt",
        "secret",
        "api_key",
        "private_key",
        "refresh_token",
        "access_token",
        "session_token",
        "webhook_secret",
        "medical_record",
        "medical_records",
    }
    # Exact phone keys + keys that end/start with phone/mobile (e.g. guardian_phone)
    # but NOT keys like is_phone_verified that contain "phone" but aren't numbers.
    phone_field_prefixes_suffixes = ("phone", "mobile", "_phone", "_mobile", "phone_", "mobile_")
    for key, raw in value.items():
        key_lower = str(key).lower()
        is_phone_field = (
            key_lower in ("phone", "mobile", "phone_number", "mobile_number")
            or key_lower.endswith(("_phone", "_mobile"))
            or key_lower.startswith(("phone_", "mobile_"))
        )
        if key_lower in restricted_exact:
            safe[key] = "[restricted in chat]"
        elif is_phone_field or "contact" in key_lower:
            if isinstance(raw, str):
                safe[key] = _mask_phone(raw)
            elif isinstance(raw, (dict, list)):
                safe[key] = _safe_tool_result_for_chat(raw)
            else:
                safe[key] = "[restricted in chat]"
        else:
            safe[key] = _safe_tool_result_for_chat(raw)
    return safe


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
            matches = []
        else:
            matches = await db.staff.find(_scoped("staff", {
                "name": {"$regex": re.escape(staff_name), "$options": "i"},
            })).to_list(5)
            if len(matches) > 1:
                resolved["_resolution_error"] = (
                    f"Multiple staff match '{staff_name}'."
                )
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


def _is_ai_unavailable(result) -> bool:
    return isinstance(result, dict) and result.get("type") == "ai_unavailable"


def _ai_unavailable_event(result: dict) -> str:
    return f"data: {json.dumps({'type': 'ai_unavailable', 'message': result.get('message', 'AI is temporarily unavailable.')})}\n\n"


# ─── Thinking delay helper ────────────────────────────────────────────────────

async def _thinking_delay():
    """Add a small random delay between thinking steps for natural feel."""
    await asyncio.sleep(random.uniform(THINKING_DELAY_MIN, THINKING_DELAY_MAX))


# ─── SSE Generator (main pipeline) ───────────────────────────────────────────

async def _generate_chat_sse(conv_id: str, user_text: str, user: dict, session_id: str = None, request=None):
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
    try:
        school_context = await build_school_context(user["role"], user["id"])
        system_prompt = build_system_prompt(user, school_context, lang)

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
        msg_filter = scoped_filter({"conversation_id": conv_id, "role": {"$in": ["user", "assistant"]}}, get_school_id())
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
        messages_for_llm = [{"role": "user", "content": user_text}]

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
                    extraction_prompt = (
                        f"Extract parameters for the EduFlow tool '{tool_name}' from this user message. "
                        f"Output ONLY JSON in this shape: "
                        f'{{"action":"{tool_name}","params":{{}},"reason":"parameter extraction"}}. '
                        f"User message: {user_text}"
                    )
                    extraction_result = await llm_client.chat(
                        system_prompt,
                        [{"role": "user", "content": extraction_prompt}],
                        f"{conv_id}-extract-{uuid.uuid4()}",
                    )
                    extraction_text = extraction_result[0] if isinstance(extraction_result, tuple) else extraction_result
                    extracted_call = _parse_tool_call(extraction_text if isinstance(extraction_text, str) else "")
                    if extracted_call and extracted_call.get("action") == tool_name:
                        params = extracted_call.get("params", {}) or {}
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

            # Start keepalive task
            keepalive_stop = asyncio.Event()

            async def _keepalive_sender():
                while not keepalive_stop.is_set():
                    try:
                        await asyncio.wait_for(keepalive_stop.wait(), timeout=KEEPALIVE_INTERVAL)
                    except asyncio.TimeoutError:
                        pass  # keepalive will be yielded in the main loop
                    if keepalive_stop.is_set():
                        break

            try:
                raw_tool_result = await tool_def["fn"]({}, user, scope) if _tool_accepts_scope(tool_def) else await tool_def["fn"]({}, user)
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

            tool_data_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
            if user.get("role") == "student":
                tool_data_str = filter_response(tool_data_str, "student")
            tool_result_msg = (
                f"Tool '{tool_name}' returned the following data:\n"
                f"{tool_data_str}"
                f"{empty_note}\n\n"
                f"Now provide a comprehensive, well-formatted response to the user's question "
                f"based on this data. Use markdown tables and formatting. "
                f"Include a <<<RICH_CONTENT>>> block if you have stats or tables to show."
            )
            messages_for_llm_final = messages_for_llm[:-1] + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": f"Fetching {tool_name} data..."},
                {"role": "user", "content": tool_result_msg},
            ]
        else:
            messages_for_llm_final = messages_for_llm

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
        # LLM_WALLCLOCK_BUDGET is a module constant (see top of file)

        async def _llm_call():
            nonlocal llm_response, llm_tokens
            try:
                session_id = f"{conv_id}-{uuid.uuid4()}"
                result = await llm_client.chat(system_prompt, messages_for_llm_final, session_id)
                if isinstance(result, tuple):
                    llm_response, llm_tokens = result
                else:
                    llm_response = result
                    llm_tokens = 0
            except Exception:
                logger.exception("LLM call raised unexpectedly in Phase 8")
                llm_response = ai_unavailable_result("call_failed")
                llm_tokens = 0
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
                        llm_response = ai_unavailable_result("timeout_wallclock")
                        llm_tokens = 0
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

        if _is_ai_unavailable(llm_response):
            yield _ai_unavailable_event(llm_response)
            ai_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=llm_response.get("message", "AI is temporarily unavailable."),
                language_detected=lang,
            )
            await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
            yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"
            return

        # BUG FIX #1: Safe token counting
        total_tokens_used += safe_token_count(llm_tokens, llm_response)

    except Exception as e:
        logger.error(f"Phase 8 (first LLM call) error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'phase': 'llm_call', 'message': 'Failed to generate response. Please try again.'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # ── Phase 9: LLM tool detection + multi-tool chaining ─────────────────
    # Part 2 Patch P5 (E6/L4): treat the keyword-detected tool as round 1 so
    # MAX_TOOL_ROUNDS is honored (was previously off-by-one: 4 effective rounds
    # when a keyword tool fired). Loop condition is now `<` only — relying on
    # the inner `break` to handle "no further tool requested".
    tool_rounds = 1 if detected_tool else 0

    try:
        while tool_rounds < MAX_TOOL_ROUNDS:
            # Only enter the loop body if we haven't already executed a keyword tool
            # or if the LLM is requesting another tool after a previous result
            if tool_result and tool_rounds == 0:
                # Already have a result from keyword detection; check if LLM wants another tool
                llm_tool_call = _parse_tool_call(llm_response)
                if not llm_tool_call:
                    break
            elif not tool_result and tool_rounds == 0:
                # No keyword tool was triggered; check if LLM wants a tool
                llm_tool_call = _parse_tool_call(llm_response)
                if not llm_tool_call:
                    break
            else:
                # Subsequent rounds: check if the latest LLM response requests another tool
                llm_tool_call = _parse_tool_call(llm_response)
                if not llm_tool_call:
                    break

            tool_rounds += 1
            llm_tool_name = llm_tool_call.get("action")
            llm_tool_params = llm_tool_call.get("params", {})

            tool_def = TOOL_REGISTRY.get(llm_tool_name)
            if not tool_def or not _is_tool_authorized(user, tool_def):
                break  # Not allowed

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

            tool_data_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
            if user.get("role") == "student":
                tool_data_str = filter_response(tool_data_str, "student")
            tool_msg = (
                f"Tool '{tool_name}' data:\n"
                f"{tool_data_str}"
                f"{empty_note}\n\n"
                f"Now provide a comprehensive, well-formatted natural language response. "
                f"Do NOT output any JSON tool calls."
            )
            messages_for_llm_final = messages_for_llm[:-1] + [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": "Fetching data..."},
                {"role": "user", "content": tool_msg},
            ]

            # Part 2 Patch P5: bounded LLM call with cleanup (mirrors Phase 8).
            llm_task_done = asyncio.Event()
            llm_response = ""
            llm_tokens = 0
            # LLM_WALLCLOCK_BUDGET is a module constant (see top of file)

            async def _llm_followup():
                nonlocal llm_response, llm_tokens
                try:
                    session_id = f"{conv_id}-{uuid.uuid4()}"
                    result = await llm_client.chat(system_prompt, messages_for_llm_final, session_id)
                    if isinstance(result, tuple):
                        llm_response, llm_tokens = result
                    else:
                        llm_response = result
                        llm_tokens = 0
                except Exception:
                    logger.exception("LLM follow-up call raised unexpectedly")
                    llm_response = ai_unavailable_result("call_failed")
                    llm_tokens = 0
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
                            llm_response = ai_unavailable_result("timeout_wallclock")
                            llm_tokens = 0
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

            if _is_ai_unavailable(llm_response):
                yield _ai_unavailable_event(llm_response)
                ai_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=llm_response.get("message", "AI is temporarily unavailable."),
                    tool_calls=all_tool_calls if all_tool_calls else None,
                    language_detected=lang,
                )
                await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})
                yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': total_tokens_used})}\n\n"
                return

            total_tokens_used += safe_token_count(llm_tokens, llm_response)

            # Check if LLM wants yet another tool (will loop back)
            # The while condition + _parse_tool_call at top of loop handles this

    except Exception as e:
        logger.error(f"Phase 9 (multi-tool chaining) error: {e}")
        # Continue with whatever llm_response we have

    # ── Phase 10: Strip residual JSON tool patterns from final response ───
    try:
        llm_response = _strip_tool_json_from_text(llm_response)

    except Exception as e:
        logger.error(f"Phase 10 (strip JSON) error: {e}")

    # ── Phase 11: Content filter on output ────────────────────────────────
    try:
        clean_response = filter_response(llm_response, user["role"])
    except Exception as e:
        logger.error(f"Phase 11 (content filter) error: {e}")
        clean_response = llm_response

    # ── Phase 12: Parse rich content ──────────────────────────────────────
    clean_text, rich_content = _extract_rich_content(clean_response)

    # ── Phase 13: Stream text response ────────────────────────────────────
    yield thinking_event("composing", "Writing your answer...")
    await _thinking_delay()

    try:
        chunk_size = 4
        for i in range(0, len(clean_text), chunk_size):
            chunk = clean_text[i:i + chunk_size]
            yield f"data: {json.dumps({'type': 'text_delta', 'delta': chunk})}\n\n"
            await asyncio.sleep(0.008)

        # Send rich content block (P8: filter rich_blocks AND action_buttons for students)
        if rich_content:
            if user.get("role") == "student":
                try:
                    filtered_str = filter_response(json.dumps(rich_content.get("rich_blocks", [])), "student")
                    rich_content["rich_blocks"] = json.loads(filtered_str)
                except Exception:
                    pass
                try:
                    filtered_btn = filter_response(json.dumps(rich_content.get("action_buttons", [])), "student")
                    rich_content["action_buttons"] = json.loads(filtered_btn)
                except Exception:
                    pass
            yield f"data: {json.dumps({'type': 'rich_blocks', 'blocks': rich_content.get('rich_blocks', []), 'action_buttons': rich_content.get('action_buttons', [])})}\n\n"

    except Exception as e:
        logger.error(f"Phase 13 (streaming) error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'phase': 'streaming', 'message': 'Error while streaming response.'})}\n\n"

    # ── Phase 14: Save AI message to DB (BUG FIX #7: persist BEFORE done event) ──
    try:
        has_content = bool(clean_text and clean_text.strip())
        has_rich = bool(rich_content and (rich_content.get('rich_blocks') or rich_content.get('action_buttons')))
        if not has_content and not has_rich:
            yield f"data: {json.dumps({'type': 'done', 'message_id': f'empty-{conv_id}', 'tokens_used': total_tokens_used})}\n\n"
            return
        ai_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=clean_text,
            rich_content=rich_content,
            tool_calls=all_tool_calls if all_tool_calls else None,
            language_detected=lang,
        )
        await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})

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
    if not user_text:
        return {"success": False, "error": "Empty message"}
    raw_session_id = body.get("session_id") or request.headers.get("x-session-id") or request.headers.get("X-SSE-Session-ID")
    session_id = (raw_session_id or "").strip()
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.warning("chat_sse_session_id_missing", extra={"conversation_id": conv_id, "generated_session_id": session_id})

    return StreamingResponse(
        _generate_chat_sse(conv_id, user_text, user, session_id=session_id, request=request),
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

async def _execute_confirmed_dispatch(token: str, session_id: str, user: dict, db, conv_id: str = None):
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
        raise
    tool_name = token_doc.get("action")
    params = token_doc.get("params") or {}

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
        if _tool_accepts_scope(tool_def):
            result = await tool_def["fn"](params, user, scope)
        else:
            result = await tool_def["fn"](params, user)
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

    try:
        return await _execute_confirmed_dispatch(token, session_id, user, db, body.get("conversation_id"))
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
    try:
        return await _execute_confirmed_dispatch(token, session_id, user, db, conv_id)
    except RateLimitExceeded as exc:
        return JSONResponse(
            status_code=429,
            content=exc.payload,
            headers={"Retry-After": str(exc.retry_after)},
        )
