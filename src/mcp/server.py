"""
src/mcp/server.py
──────────────────
MCP Server — FastAPI Router يعرض الـ MCP tools للـ clients.

Endpoints:
  GET  /mcp/tools          → قائمة كل الـ tools المتاحة
  POST /mcp/execute        → تنفيذ tool بالاسم والـ arguments
  GET  /mcp/tools/{name}   → تفاصيل tool معين

هذا الـ endpoint يتيح للـ frontend أو أي MCP client خارجي
استكشاف وتنفيذ الـ tools الخاصة بالنظام.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, Optional

from src.mcp.registry import mcp_registry
from src.helpers.auth import get_current_user

logger = logging.getLogger("uvicorn.error")

mcp_router = APIRouter(
    prefix="/api/v1/mcp",
    tags=["MCP — Model Context Protocol"],
)


# ── Request/Response Models ───────────────────────────────────────────────────

class ExecuteToolRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


class ExecuteToolResponse(BaseModel):
    status: str
    tool_name: str
    result: Any
    error: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@mcp_router.get("/tools")
async def list_tools(category: Optional[str] = None):
    """
    قائمة كل الـ MCP tools المتاحة في النظام.

    - بدون category → كل الـ tools
    - مع category → فلتر (knowledge, calculation, student, general)
    """
    if category:
        tools = [
            t.to_manifest()
            for t in mcp_registry.list_by_category(category)
        ]
    else:
        tools = mcp_registry.list_all()

    return JSONResponse(content={
        "status": "success",
        "total": len(tools),
        "tools": tools,
    })


@mcp_router.get("/tools/{tool_name}")
async def get_tool_info(tool_name: str):
    """تفاصيل tool معين."""
    tool = mcp_registry.get(tool_name)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. Use GET /mcp/tools to see available tools."
        )
    return JSONResponse(content={
        "status": "success",
        "tool": tool.to_manifest(),
    })


@mcp_router.post("/execute")
async def execute_tool(
    body: ExecuteToolRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    تنفيذ MCP tool.

    مثال:
    {
        "tool_name": "calculator",
        "arguments": {"expression": "2 + 2 * 3"}
    }
    """
    tool = mcp_registry.get(body.tool_name)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{body.tool_name}' not found"
        )

    # فحص auth لو الـ tool يتطلبها
    if tool.requires_auth and not current_user:
        raise HTTPException(status_code=401, detail="Authentication required for this tool")

    try:
        result = await tool.execute(**body.arguments)
        return JSONResponse(content={
            "status": "success",
            "tool_name": body.tool_name,
            "result": result,
        })
    except TypeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid arguments for tool '{body.tool_name}': {e}"
        )
    except Exception as e:
        logger.error(f"[MCP] Tool execution error: {body.tool_name} — {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp_router.get("/manifest")
async def get_manifest():
    """
    MCP Manifest — بيانات كاملة عن الـ MCP Server.
    Compatible مع MCP Protocol standard.
    """
    tools = mcp_registry.list_all()
    return JSONResponse(content={
        "protocol_version": "1.0",
        "server_name": "Satr-Edu MCP Server",
        "server_version": "1.0.0",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False,
        },
        "tools": tools,
    })
