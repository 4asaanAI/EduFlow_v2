"""
Chat routes — conversation CRUD + SSE streaming message handler
"""
import json
import asyncio
import re
import uuid
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from database import get_db
from models.schemas import Conversation, Message, ConversationUpdate
from ai.llm_client import llm_client
from ai.prompts import build_system_prompt
from ai.context_builder import build_school_context, detect_language
from ai.tool_functions import TOOL_REGISTRY

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_current_user(request: Request) -> dict:
    role = request.headers.get("X-User-Role", "owner")
    user_id = request.headers.get("X-User-Id", "user-owner-001")
    name = request.headers.get("X-User-Name", "Aman")
    return {"id": user_id, "role": role, "name": name}


@router.get("/conversations")
async def list_conversations(request: Request):
    db = get_db()
    user = get_current_user(request)
    convs = await db.conversations.find(
        {"user_id": user["id"]}, {"_id": 0}
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
    update_data = {k: v for k, v in body.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now().isoformat()
    await db.conversations.update_one({"id": conv_id}, {"$set": update_data})
    return {"success": True}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, request: Request):
    db = get_db()
    await db.conversations.delete_one({"id": conv_id})
    await db.messages.delete_many({"conversation_id": conv_id})
    return {"success": True}


@router.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: str, request: Request):
    db = get_db()
    msgs = await db.messages.find(
        {"conversation_id": conv_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    return {"success": True, "data": msgs}


def _extract_rich_content(text: str):
    """Extract <<<RICH_CONTENT>>>...<<<END>>> block from LLM response."""
    pattern = r"<<<RICH_CONTENT>>>\s*(.*?)\s*<<<END>>>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        clean_text = text[:match.start()].strip()
        try:
            rich = json.loads(match.group(1))
            return clean_text, rich
        except Exception:
            pass
    return text.strip(), None


def _parse_tool_call(text: str):
    """Check if LLM response contains a tool call JSON anywhere in the text."""
    # Search for {"action": ...} pattern anywhere in the response
    pattern = r'\{[^{}]*"action"\s*:\s*"([^"]+)"[^{}]*\}'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if "action" in data:
                return data
        except Exception:
            pass
    return None


# Keyword-based tool detection for reliable intent routing
KEYWORD_TOOL_MAP = [
    # School pulse - with slash variants
    (["/school-pulse", "school status", "school pulse", "today's status", "today's overview", "school overview", "how is school", "pulse", "aaj ka status", "school ka status"], "get_school_pulse"),
    # Daily brief
    (["/daily-brief", "daily brief", "morning summary", "morning brief", "aaj ka haal", "morning status", "what happened today", "today's summary"], "get_daily_brief"),
    # Fee collection
    (["/fee-collection", "/fee-summary", "fee defaulter", "fee summary", "fee collection", "who owes", "overdue fee", "pending fee", "collect fee", "fee ke baare mein"], "get_fee_summary"),
    # Staff status
    (["/staff-tracker", "/leave-manager", "staff absent", "staff status", "staff tracker", "who is absent", "which staff", "staff attendance", "leave request", "pending leave", "staff ki leave"], "get_staff_status"),
    # Attendance
    (["/attendance-overview", "attendance trend", "attendance overview", "attendance report", "how is attendance", "attendance kaisi hai"], "get_attendance_overview"),
    # Alerts
    (["/smart-alerts", "smart alert", "active alert", "flag", "exception", "koi dikkat"], "get_smart_alerts"),
    # Financial
    (["/financial-reports", "financial report", "financial summary", "revenue", "expense", "paisa", "finance"], "get_financial_report"),
    # Students
    (["/student-database", "search student", "find student", "student named", "student list", "which student", "student dhundo"], "search_students"),
    # Fee transactions
    (["/fee-tracker", "fee transaction", "payment history", "who paid", "payment record"], "get_fee_transactions"),
    # Leave approval
    (["approve leave", "reject leave", "leave approve"], "approve_leave"),
    # Enquiries
    (["/admission-funnel", "/enquiry-register", "enquiry", "admission funnel", "new student inquiry", "admission"], "get_enquiries"),
    # Health report
    (["/health-report", "/ai-health-report", "health report", "school health", "health score"], "get_smart_alerts"),
]


def detect_tool_from_keywords(text: str, role: str) -> str | None:
    """Detect which tool to call based on keywords in the user message."""
    text_lower = text.lower()
    for keywords, tool_name in KEYWORD_TOOL_MAP:
        if any(kw in text_lower for kw in keywords):
            tool_def = TOOL_REGISTRY.get(tool_name)
            if tool_def and role in tool_def["roles"]:
                return tool_name
    return None


async def _generate_chat_sse(conv_id: str, user_text: str, user: dict):
    """SSE generator for chat streaming."""
    db = get_db()

    try:
        # 1. Save user message
        lang = detect_language(user_text)
        user_msg = Message(
            conversation_id=conv_id,
            role="user",
            content=user_text,
            language_detected=lang,
        )
        await db.messages.insert_one({**user_msg.dict(), "_id": user_msg.id})

        # Update conversation timestamp and auto-title
        conv = await db.conversations.find_one({"id": conv_id})
        update_fields = {"updated_at": datetime.now().isoformat()}
        if conv and conv.get("title") in ("New conversation", None, ""):
            update_fields["title"] = user_text[:50].strip()
        await db.conversations.update_one({"id": conv_id}, {"$set": update_fields})

        # 2. Build context and system prompt
        school_context = await build_school_context(user["role"], user["id"])
        system_prompt = build_system_prompt(user, school_context, lang)

        # 3. Get conversation history (last 14 messages, not including current)
        history = await db.messages.find(
            {"conversation_id": conv_id, "role": {"$in": ["user", "assistant"]}},
            {"_id": 0},
        ).sort("created_at", 1).to_list(20)

        messages_for_llm = [{"role": m["role"], "content": m.get("content", "") or ""} for m in history]

        # 4. Detect tool from keywords FIRST (reliable intent detection)
        detected_tool = detect_tool_from_keywords(user_text, user["role"])
        tool_result = None
        tool_name = None

        if detected_tool:
            tool_name = detected_tool
            tool_def = TOOL_REGISTRY.get(tool_name)
            yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'running'})}\n\n"
            try:
                tool_result = await tool_def["fn"]({}, user)
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'done'})}\n\n"
            except Exception as e:
                tool_result = {"error": str(e)}
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'error'})}\n\n"

        # 5. Build LLM message list
        if tool_result:
            tool_result_msg = f"Tool '{tool_name}' returned the following data:\n{json.dumps(tool_result, ensure_ascii=False, indent=2)}\n\nNow provide a comprehensive, well-formatted response to the user's question based on this data. Use markdown tables and formatting. Include a <<<RICH_CONTENT>>> block if you have stats or tables to show."
            messages_for_llm_final = messages_for_llm[:-1] + [  # exclude the user msg we just saved
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": f"Fetching {tool_name} data..."},
                {"role": "user", "content": tool_result_msg},
            ]
        else:
            messages_for_llm_final = messages_for_llm

        # 6. Call LLM
        session_id = f"{conv_id}-{uuid.uuid4()}"
        llm_response, tokens_used = await llm_client.chat(system_prompt, messages_for_llm_final, session_id)

        # 7. Check if LLM also wants a tool call (for cases not caught by keywords)
        if not tool_result:
            llm_tool_call = _parse_tool_call(llm_response)
            if llm_tool_call:
                llm_tool_name = llm_tool_call.get("action")
                llm_tool_params = llm_tool_call.get("params", {})
                tool_def = TOOL_REGISTRY.get(llm_tool_name)
                if tool_def and user["role"] in tool_def["roles"]:
                    tool_name = llm_tool_name
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'running'})}\n\n"
                    try:
                        tool_result = await tool_def["fn"](llm_tool_params, user)
                        yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'status': 'done'})}\n\n"
                    except Exception as e:
                        tool_result = {"error": str(e)}

                    # Second LLM pass — provide data, ask for formatted response
                    # IMPORTANT: Strip any JSON from previous response to prevent it showing to user
                    tool_msg = f"Tool '{tool_name}' data:\n{json.dumps(tool_result, ensure_ascii=False, indent=2)}\n\nNow provide a comprehensive, well-formatted natural language response. Do NOT output any JSON tool calls."
                    messages_for_llm_final = messages_for_llm[:-1] + [
                        {"role": "user", "content": user_text},
                        {"role": "assistant", "content": "Fetching data..."},
                        {"role": "user", "content": tool_msg},
                    ]
                    session_id_2 = f"{conv_id}-{uuid.uuid4()}"
                    second_response, second_tokens = await llm_client.chat(system_prompt, messages_for_llm_final, session_id_2)
                    llm_response = second_response
                    tokens_used += second_tokens

        # Strip any residual JSON tool call patterns from final response (safety net)
        llm_response = re.sub(
            r'\{"action"\s*:\s*"[^"]+"\s*,\s*"params"\s*:\s*\{[^}]*\}\s*\}',
            '', llm_response
        ).strip()

        # 8. Parse rich content from final response
        clean_text, rich_content = _extract_rich_content(llm_response)

        # 9. Stream text response
        chunk_size = 4
        for i in range(0, len(clean_text), chunk_size):
            chunk = clean_text[i: i + chunk_size]
            yield f"data: {json.dumps({'type': 'text_delta', 'delta': chunk})}\n\n"
            await asyncio.sleep(0.008)

        # 10. Send rich content block
        if rich_content:
            yield f"data: {json.dumps({'type': 'rich_blocks', 'blocks': rich_content.get('rich_blocks', []), 'action_buttons': rich_content.get('action_buttons', [])})}\n\n"

        # 11. Save AI message to DB
        ai_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=clean_text,
            rich_content=rich_content,
            tool_calls=[{"tool": tool_name, "result": tool_result}] if tool_name else None,
            language_detected=lang,
        )
        await db.messages.insert_one({**ai_msg.dict(), "_id": ai_msg.id})

        yield f"data: {json.dumps({'type': 'done', 'message_id': ai_msg.id, 'tokens_used': tokens_used})}\n\n"

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"I encountered an error: {str(e)}. Please try again."
        yield f"data: {json.dumps({'type': 'text_delta', 'delta': error_msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/conversations/{conv_id}/messages")
async def send_message(conv_id: str, request: Request):
    user = get_current_user(request)
    body = await request.json()
    user_text = body.get("text", "").strip()
    if not user_text:
        return {"success": False, "error": "Empty message"}

    return StreamingResponse(
        _generate_chat_sse(conv_id, user_text, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/conversations/{conv_id}/action")
async def execute_action(conv_id: str, request: Request):
    """Execute an action button directly (not through LLM) and add result to chat."""
    db = get_db()
    user = get_current_user(request)
    body = await request.json()
    action = body.get("action")
    params = body.get("params", {})
    label = body.get("label", action)

    tool_def = TOOL_REGISTRY.get(action)
    if not tool_def:
        return {"success": False, "error": f"Unknown action: {action}"}
    if user["role"] not in tool_def["roles"]:
        return {"success": False, "error": "Not allowed for your role"}

    try:
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
        await db.conversations.update_one({"id": conv_id}, {"$set": {"updated_at": datetime.now().isoformat()}})

        return {"success": True, "data": {"message": msg_content, "result": result, "message_id": ai_msg.id}}
    except Exception as e:
        return {"success": False, "error": str(e)}
