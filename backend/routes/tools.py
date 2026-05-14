"""
Direct tool execution endpoint — for tool panel UI (non-chat mode)
"""
import logging
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from ai.tool_functions_v2 import TOOL_REGISTRY
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


def get_user(req: Request):
    return get_current_user(req)


@router.post("/{tool_id}/execute")
async def execute_tool(tool_id: str, request: Request):
    user = get_user(request)
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    params = body.get("params", {})

    tool_def = TOOL_REGISTRY.get(tool_id)
    if not tool_def:
        raise HTTPException(404, f"Tool '{tool_id}' not found")

    # auth: dynamic per-tool role allowlist — see TOOL_REGISTRY
    if user["role"] not in tool_def["roles"]:
        raise HTTPException(403, "Forbidden")

    try:
        result = await tool_def["fn"](params, user)
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception("Tool '%s' execution failed", tool_id)
        raise HTTPException(500, f"Tool execution failed: {str(e)}")
