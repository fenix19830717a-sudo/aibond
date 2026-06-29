"""MCP 组网 API 路由

提供 MCP 协议相关的 REST API 端点:
- MCP Server 端点（JSON-RPC 消息处理）
- Agent 能力注册与发现
- 工具搜索与调用代理
- 连接管理
"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.models import Agent
from app.security import get_current_user_id, get_current_actor, rate_limit
from app.mcp.registry import global_registry
from app.mcp.client import global_mcp_client
import app.mcp.server as mcp_server_module  # Use module-level ref to get latest instance
from app.mcp.protocol import (
    ToolSchema,
    ToolInputSchema,
    CapabilityManifest,
)
from app.mcp.transport import TransportConfig, TransportType

# Lazy accessor for the MCP server (re-initialized at startup)
def _get_mcp_server():
    return mcp_server_module.global_mcp_server

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


# ============================================================
# 请求/响应模型
# ============================================================

class RegisterToolRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    tools: list[dict] = Field(default_factory=list, description="Tool 定义列表")
    resources: list[dict] = Field(default_factory=list)
    prompts: list[dict] = Field(default_factory=list)


class AgentConnectRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    transport: str = Field("websocket", pattern=r"^(stdio|sse|websocket|streamable_http)$")
    command: str | None = Field(None, description="stdio 模式下的可执行文件路径")
    url: str | None = Field(None, description="SSE 模式下的 URL")
    args: list[str] = Field(default_factory=list)


class CallToolRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    arguments: dict = Field(default_factory=dict)


class ToolSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


# ============================================================
# MCP JSON-RPC 端点（供外部 MCP Client 调用）
# ============================================================

@router.post("/message")
async def mcp_message(
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
):
    """MCP JSON-RPC 消息处理端点

    外部 MCP Client（如 Claude Desktop、Trae IDE）通过此端点
    发送 JSON-RPC 请求，实现 MCP 协议交互。

    Security: Requires authentication via Bearer token (JWT) or API Key (abk_).
    """
    try:
        body = await request.json()
    except Exception:
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error"},
        }

    session_id = request.headers.get("X-MCP-Session-ID", "default")
    result = await _get_mcp_server().handle_message(body, session_id)

    # 通知不需要响应
    if result is None:
        return None

    return result


@router.get("/sse")
async def mcp_sse(request: Request):
    """MCP SSE 端点（预留）

    用于 SSE 传输模式，建立长连接推送事件流。
    当前返回基础的 SSE 端点信息。
    """
    from fastapi.responses import StreamingResponse
    import asyncio

    async def event_stream():
        yield f"data: {json.dumps({'jsonrpc': '2.0', 'method': 'notifications/ready'})}\n\n"
        # 保持连接
        while True:
            await asyncio.sleep(30)
            yield f": heartbeat\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# Agent 能力注册（Agent 通过 WebSocket 或 REST 注册能力）
# ============================================================

@router.post("/register-tools")
async def register_agent_tools(
    req: RegisterToolRequest,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Agent 注册自己的 Tools/Resources/Prompts

    Agent 连接后，通过此端点向 Registry 注册标准化的 MCP 能力。
    """
    await rate_limit(request, limit=30, window=60)

    # 验证 Agent 存在且属于当前用户
    result = await db.execute(
        select(Agent).where(Agent.id == req.agent_id, Agent.owner_id == uid)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 构建能力清单
    tools = [ToolSchema(**t) for t in req.tools]
    resources = [{"uri": r.get("uri", ""), "name": r.get("name", ""),
                   "description": r.get("description", ""), "mimeType": r.get("mimeType", "text/plain")}
                  for r in req.resources]
    prompts = [{"name": p.get("name", ""), "description": p.get("description", ""),
                 "arguments": p.get("arguments", [])}
                for p in req.prompts]

    from app.mcp.protocol import ResourceSchema, PromptSchema
    manifest = CapabilityManifest(
        agent_id=req.agent_id,
        agent_name=agent.name,
        transport="websocket",
        tools=tools,
        resources=[ResourceSchema(**r) for r in resources],
        prompts=[PromptSchema(**p) for p in prompts],
        server_capabilities={"tools": {"listChanged": True}},
    )

    global_registry.register(manifest)

    # 同时更新 Agent 的 skills 字段（保持向后兼容）
    agent.skills = [t.name for t in tools]
    if req.tools:
        agent.tool_schemas = json.dumps([t.model_dump() for t in tools], ensure_ascii=False)
    await db.commit()

    return {
        "status": "ok",
        "agent_id": req.agent_id,
        "tools_registered": len(tools),
        "resources_registered": len(resources),
        "prompts_registered": len(prompts),
    }


@router.post("/register-from-skills")
async def register_from_skills(
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """批量将现有 Agent 的 skills 升级为 MCP 能力清单"""
    await rate_limit(request, limit=10, window=60)

    result = await db.execute(
        select(Agent).where(Agent.owner_id == uid)
    )
    agents = result.scalars().all()

    registered = 0
    for agent in agents:
        skills = agent.skills or []
        if skills and agent.id not in global_registry._manifests:
            global_registry.register_from_skills(
                agent_id=agent.id,
                agent_name=agent.name,
                skills=skills,
                transport="websocket",
            )
            registered += 1

    return {
        "status": "ok",
        "total_agents": len(agents),
        "registered": registered,
    }


# ============================================================
# 服务发现
# ============================================================

@router.get("/discovery")
async def mcp_discovery():
    """MCP 服务发现端点

    返回所有已注册 Agent 的能力摘要，供 MCP Client 发现可用服务。
    """
    agents = global_registry.list_all_agents()
    return {
        "protocol": "mcp",
        "version": "2024-11-05",
        "agents": agents,
        "total_agents": len(agents),
        "total_tools": global_registry.tool_count,
        "total_resources": global_registry.resource_count,
        "total_prompts": global_registry.prompt_count,
    }


@router.get("/agents/{agent_id}/manifest")
async def get_agent_manifest(agent_id: str):
    """获取指定 Agent 的完整能力清单"""
    manifest = global_registry.get_manifest(agent_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Agent manifest not found")
    return manifest.to_discovery_dict()


@router.get("/agents/{agent_id}/tools")
async def get_agent_tools(agent_id: str):
    """获取指定 Agent 的所有 Tools"""
    manifest = global_registry.get_manifest(agent_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Agent manifest not found")
    return {"agent_id": agent_id, "tools": [t.model_dump() for t in manifest.tools]}


# ============================================================
# 工具搜索与调用代理
# ============================================================

@router.post("/search-tools")
async def search_tools(req: ToolSearchRequest):
    """搜索所有 Agent 提供的工具"""
    results = global_registry.search_tools(req.query)
    return {"query": req.query, "results": results, "count": len(results)}


@router.get("/tools")
async def list_all_tools():
    """列出所有已注册的 Tools"""
    tools = global_registry.list_all_tools()
    return {"tools": tools, "count": len(tools)}


@router.post("/call-tool")
async def call_agent_tool(
    req: CallToolRequest,
    request: Request,
    uid: str = Depends(get_current_user_id),
):
    """通过平台代理调用 Agent 的工具

    平台作为 MCP 中间层，路由工具调用到正确的 Agent。
    """
    await rate_limit(request, limit=30, window=60)

    try:
        result = await global_mcp_client.call_agent_tool(
            req.agent_id, req.tool_name, req.arguments,
        )
        return {"status": "ok", "agent_id": req.agent_id, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 连接管理
# ============================================================

@router.post("/connect")
async def connect_agent(
    req: AgentConnectRequest,
    request: Request,
    uid: str = Depends(get_current_user_id),
):
    """建立与 Agent 的 MCP 连接"""
    await rate_limit(request, limit=10, window=60)

    transport_config = TransportConfig(
        transport_type=TransportType(req.transport),
        command=req.command,
        args=req.args,
        url=req.url,
    )

    try:
        connection = await global_mcp_client.connect_agent(req.agent_id, transport_config)
        return {
            "status": "ok",
            "agent_id": req.agent_id,
            "connected": True,
            "transport": req.transport,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@router.post("/disconnect/{agent_id}")
async def disconnect_agent(
    agent_id: str,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """断开与 Agent 的 MCP 连接"""
    # Verify agent ownership
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.owner_id == uid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied: not the agent owner")
    await global_mcp_client.disconnect_agent(agent_id)
    return {"status": "ok", "agent_id": agent_id, "connected": False}


@router.post("/discover/{agent_id}")
async def discover_agent(
    agent_id: str,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """触发 Agent 能力发现流程"""
    await rate_limit(request, limit=10, window=60)

    # Verify agent ownership
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.owner_id == uid))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied: not the agent owner")

    try:
        manifest = await global_mcp_client.discover_agent(agent_id)
        # 同步到 registry
        global_registry.register(manifest)
        return {
            "status": "ok",
            "agent_id": agent_id,
            "manifest": manifest.to_discovery_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/connections")
async def list_connections(uid: str = Depends(get_current_user_id)):
    """列出所有 MCP 连接"""
    connected = global_mcp_client.list_connected_agents()
    return {
        "connected_agents": connected,
        "count": len(connected),
    }


# ============================================================
# 平台信息
# ============================================================

@router.get("/info")
async def mcp_info():
    """MCP 平台信息"""
    return {
        "protocol": "mcp",
        "version": "2024-11-05",
        "server": "aibond-mcp",
        "server_version": "1.3.0",
        "transports": ["stdio", "sse", "websocket"],
        "endpoints": {
            "message": "/api/mcp/message",
            "sse": "/api/mcp/sse",
            "discovery": "/api/mcp/discovery",
        },
        "stats": {
            "registered_agents": global_registry.agent_count,
            "total_tools": global_registry.tool_count,
            "connected_agents": len(global_mcp_client.list_connected_agents()),
        },
    }