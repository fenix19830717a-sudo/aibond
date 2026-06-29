from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid

from app.database import get_db
from app.models.models import Agent
from app.security import get_current_user_id, get_current_actor, rate_limit, sanitize_command_arg
from app.config import settings

router = APIRouter(prefix="/api/agents", tags=["agents"])

class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    api_key: str | None = Field(None, max_length=128)
    skills: list[str] | None = None
    mcp_endpoints: list[str] | None = None
    callback_url: str = Field("", max_length=255)

class AgentUpdateRequest(BaseModel):
    agent_role: Optional[str] = Field(None, pattern=r"^(arbiter|reviewer|analyst|executor|observer)$")
    tier: Optional[int] = Field(None, ge=1, le=3)
    reliability_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    description: Optional[str] = Field(None, max_length=1000)

class MeByTokenRequest(BaseModel):
    token: str = Field(..., min_length=10)

class HeartbeatRequest(BaseModel):
    api_key: str = Field(..., min_length=10)
    address: str = Field("", max_length=255)

class CreateTokenRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

@router.post("/create-token")
async def create_agent_token(req: CreateTokenRequest, request: Request, uid: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    # Rate limit: 10 token creations per minute per IP
    await rate_limit(request, limit=10, window=60)

    agent_id = str(uuid.uuid4())
    api_key = f"abk_{uuid.uuid4().hex[:32]}"

    agent = Agent(
        id=agent_id,
        name=req.name,
        api_key=api_key,
        owner_id=uid,
        status="pending",
        skills=[],
        mcp_endpoints=[],
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # 安全地转义名称，防止命令注入
    safe_name = sanitize_command_arg(req.name)
    server_url = settings.PUBLIC_URL.replace("https://", "wss://") if settings.PUBLIC_URL else "ws://localhost:8000"
    http_server_url = settings.PUBLIC_URL if settings.PUBLIC_URL else "http://localhost:8000"

    register_command = f'aibond-agent connect --server {server_url} --token {api_key} --name "{safe_name}"'
    register_command_fallback = f'python -m aibond_agent.cli connect --server {server_url} --token {api_key} --name "{safe_name}"'
    mcp_config = f'{{"mcpServers":{{"aibond":{{"command":"aibond-agent","args":["mcp","--server","{server_url}","--token","{api_key}"]}}}}}}'

    connection_guide = (
        f"=== aibond Agent 连接指南 ===\n\n"
        f"1. 安装 SDK（三选一）：\n"
        f"   pip install aibond-agent\n"
        f"   或从服务器下载:\n"
        f"   wget {http_server_url}/api/sdk/download\n"
        f"   pip install ./aibond_agent-0.1.0-py3-none-any.whl\n"
        f"   或远程安装：pip install {http_server_url}/api/sdk/download\n\n"
        f"2. 连接平台：\n"
        f"   {register_command}\n"
        f"   如果 CLI 不在 PATH 中:\n"
        f"   {register_command_fallback}\n\n"
        f"3. MCP 客户端（Claude/Trae）配置：\n"
        f"   {mcp_config}\n\n"
        f"Agent ID: {agent.id}\n"
        f"API Key: {api_key}\n"
        f"Server: {server_url}"
    )

    return {
        "id": agent.id,
        "name": agent.name,
        "api_key": agent.api_key,
        "status": "pending",
        "server_url": server_url,
        "http_server_url": http_server_url,
        "register_command": register_command,
        "register_command_fallback": register_command_fallback,
        "mcp_config": mcp_config,
        "connection_guide": connection_guide,
    }

@router.post("/register")
async def register_agent(req: AgentRegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await rate_limit(request, limit=10, window=60)

    api_key = req.api_key or f"abk_{uuid.uuid4().hex[:32]}"

    agent = Agent(
        id=str(uuid.uuid4()),
        name=req.name,
        api_key=api_key,
        skills=req.skills or [],
        mcp_endpoints=req.mcp_endpoints or [],
        callback_url=req.callback_url,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return {
        "id": agent.id,
        "name": agent.name,
        "api_key": agent.api_key,
        "status": agent.status,
        "skills": agent.skills,
    }

@router.get("/")
async def list_agents(
    status: Optional[str] = None,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # 强制鉴权，仅返回当前用户拥有的 Agent
    query = select(Agent).where(Agent.is_active == True, Agent.owner_id == uid)
    if status:
        # Validate status to prevent injection
        if status not in ("online", "offline", "busy", "pending"):
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.where(Agent.status == status)
    result = await db.execute(query)
    agents = result.scalars().all()

    return [{
        "id": a.id,
        "name": a.name,
        "api_key": a.api_key,
        "status": a.status,
        "skills": a.skills,
        "last_heartbeat": str(a.last_heartbeat) if a.last_heartbeat else None,
        "current_address": a.current_address,
    } for a in agents]

@router.get("/available")
async def list_available_agents(uid: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """列出所有活跃的Agent，供下拉选择使用（不返回敏感信息）"""
    result = await db.execute(
        select(Agent).where(Agent.is_active == True)
    )
    agents = result.scalars().all()
    sorted_agents = sorted(agents, key=lambda a: (a.status != "online", a.name))
    return [{
        "id": a.id,
        "name": a.name,
        "status": a.status,
        "skills": a.skills or [],
    } for a in sorted_agents]

@router.post("/me")
async def get_agent_by_token(req: MeByTokenRequest, db: AsyncSession = Depends(get_db)):
    """Agent 通过 API Key 查询自己的 ID（SDK 连接时使用）"""
    result = await db.execute(select(Agent).where(Agent.api_key == req.token, Agent.is_active == True))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found with this token")
    return {
        "id": agent.id,
        "name": agent.name,
        "status": agent.status,
    }

@router.put("/{agent_id}")
async def update_agent_info(
    agent_id: str,
    req: AgentUpdateRequest,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """Update agent role, tier, reliability_score. Only the agent itself or owner can update."""
    actor_id, actor_type = actor

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Only agent itself or owner can update
    if actor_type == "agent" and actor_id != agent_id:
        raise HTTPException(status_code=403, detail="Only the agent itself can update")
    if actor_type == "user" and agent.owner_id != actor_id:
        raise HTTPException(status_code=403, detail="Only the owner can update")

    if req.agent_role is not None:
        agent.agent_role = req.agent_role
    if req.tier is not None:
        agent.tier = req.tier
    if req.reliability_score is not None:
        agent.reliability_score = req.reliability_score
    if req.description is not None:
        agent.description = req.description

    await db.commit()
    await db.refresh(agent)

    return {
        "id": agent.id,
        "name": agent.name,
        "agent_role": agent.agent_role,
        "tier": agent.tier,
        "reliability_score": agent.reliability_score,
        "description": agent.description,
    }

@router.get("/{agent_id}")
async def get_agent(agent_id: str, actor: tuple[str, str] = Depends(get_current_actor), db: AsyncSession = Depends(get_db)):
    actor_id, actor_type = actor

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Only allow the agent itself or the owner to view
    if actor_type == "agent" and actor_id != agent_id:
        raise HTTPException(status_code=403, detail="Only the agent itself can view")
    if actor_type == "user" and agent.owner_id != actor_id:
        raise HTTPException(status_code=403, detail="Only the owner can view this agent")

    return {
        "id": agent.id,
        "name": agent.name,
        "status": agent.status,
        "skills": agent.skills,
        "mcp_endpoints": agent.mcp_endpoints,
        "callback_url": agent.callback_url,
        "capabilities": agent.capabilities,
        "last_heartbeat": str(agent.last_heartbeat) if agent.last_heartbeat else None,
        "current_address": agent.current_address,
    }

@router.post("/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, req: HeartbeatRequest, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone
    result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.api_key == req.api_key))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent credentials")

    agent.status = "online"
    agent.last_heartbeat = datetime.now(timezone.utc)
    if req.address:
        agent.current_address = req.address
    await db.commit()

    return {"status": "ok", "agent_status": agent.status}
