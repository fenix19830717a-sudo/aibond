"""Hub 路由 - 公开统计、manifest、MCP 组网发现"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Agent, User, Group, Template
from app.security import get_current_user_id, rate_limit, sanitize_text
from app.mcp.registry import global_registry

router = APIRouter(prefix="/api/hub", tags=["hub"])


@router.get("/stats")
async def hub_stats(db: AsyncSession = Depends(get_db)):
    """公开统计（无需鉴权）"""
    users = await db.execute(select(func.count(User.id)))
    agents = await db.execute(select(func.count(Agent.id)).where(Agent.is_active == True))
    groups = await db.execute(select(func.count(Group.id)).where(Group.is_active == True))
    templates = await db.execute(select(func.count(Template.id)))

    return {
        "total_users": users.scalar(),
        "total_agents": agents.scalar(),
        "total_groups": groups.scalar(),
        "total_templates": templates.scalar(),
        "mcp_registered_agents": global_registry.agent_count,
        "mcp_total_tools": global_registry.tool_count,
        "version": "1.3.0",
    }


@router.get("/manifest")
async def hub_manifest(db: AsyncSession = Depends(get_db)):
    """公开 manifest（无需鉴权）— 含 MCP 能力摘要"""
    # 获取在线 Agent 列表
    result = await db.execute(
        select(Agent).where(Agent.is_active == True, Agent.status == "online")
    )
    agents = result.scalars().all()

    # 获取公开模板
    tmpl_result = await db.execute(select(Template).where(Template.is_public == True))
    templates = tmpl_result.scalars().all()

    return {
        "name": "aibond-hub",
        "version": "1.3.0",
        "protocol": "mcp+websocket",
        "agents": [{
            "id": a.id,
            "name": a.name,
            "status": a.status,
            "skills": a.skills or [],
            "mcp_transport": a.mcp_transport or "websocket",
            "mcp_tools_count": len(a.tool_schemas) if a.tool_schemas else 0,
            "capabilities": a.capabilities or {},
        } for a in agents],
        "templates": [{
            "id": t.id,
            "name": t.name,
            "display_name": t.display_name,
            "description": t.description,
        } for t in templates],
        "mcp": {
            "endpoint": "/api/mcp/message",
            "discovery": "/api/mcp/discovery",
            "registered_agents": global_registry.agent_count,
            "total_tools": global_registry.tool_count,
        },
    }


@router.get("/mcp/discovery")
async def hub_mcp_discovery():
    """MCP 组网发现端点（公开）

    返回所有已注册 Agent 的 MCP 能力清单，供外部 MCP Client 发现可用服务。
    这是 MCP 组网的核心入口。
    """
    agents = global_registry.list_all_agents()
    return {
        "protocol": "mcp",
        "version": "2024-11-05",
        "server": "aibond-hub",
        "agents": agents,
        "total_agents": len(agents),
        "total_tools": global_registry.tool_count,
        "total_resources": global_registry.resource_count,
        "total_prompts": global_registry.prompt_count,
        "endpoints": {
            "message": "/api/mcp/message",
            "sse": "/api/mcp/sse",
        },
    }


@router.get("/mcp/search")
async def hub_mcp_search(q: str = ""):
    """搜索 MCP 工具（公开）

    在所有已注册 Agent 中搜索工具。
    """
    if not q:
        return {"query": "", "results": [], "count": 0}
    results = global_registry.search_tools(q)
    return {"query": q, "results": results, "count": len(results)}


class PublishReq(BaseModel):
    type: str = Field(..., pattern=r"^(agent|template)$")
    id: str = Field(..., min_length=1)
    description: str = Field("", max_length=2000)


@router.post("/publish")
async def publish(
    req: PublishReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """发布到 Hub（需要鉴权）"""
    await rate_limit(request, limit=10, window=60)

    if req.type == "agent":
        agent = await db.execute(select(Agent).where(Agent.id == req.id, Agent.owner_id == uid))
        a = agent.scalar_one_or_none()
        if not a:
            raise HTTPException(status_code=404, detail="Agent not found or not owned by you")
        # Agent 发布逻辑：同时注册到 MCP Registry
        if a.skills:
            global_registry.register_from_skills(
                agent_id=a.id,
                agent_name=a.name,
                skills=a.skills,
                transport=a.mcp_transport or "websocket",
            )
        return {"status": "ok", "type": "agent", "id": a.id, "mcp_registered": True}

    elif req.type == "template":
        template = await db.execute(select(Template).where(Template.id == req.id, Template.created_by == uid))
        t = template.scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found or not owned by you")
        t.is_public = True
        await db.commit()

        # 写入审计日志
        from app.routers.audit import write_audit_log
        await write_audit_log(db, "user", uid, "hub.publish",
                              target_type="template", target_id=t.id,
                              ip_address=request.client.host if request.client else "")

        return {"status": "ok", "type": "template", "id": t.id}

    raise HTTPException(status_code=400, detail="Invalid publish type")