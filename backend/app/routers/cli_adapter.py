"""CLI Adapter API 路由

提供 CLI Agent 接入、Pull Queue 操作、Gate 状态机控制的 REST API。
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
from app.cli_adapter.adapters import AgentSpec, build_adapter, load_specs
from app.cli_adapter.pull_queue import global_pull_queue, PullWorker
from app.cli_adapter.gate import GateStatus, GateStateMachine, acceptance_evidence, VALID_TRANSITIONS
from app.cli_adapter.model_selector import select_model, ModelSelector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cli", tags=["cli-adapter"])
gate_sm = GateStateMachine()


# ============================================================
# 请求/响应模型
# ============================================================

class ConfigureCLIAgentRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    mode: str = Field("command", pattern=r"^(command|mock|websocket)$")
    command: list[str] = Field(default_factory=list)
    timeout: int = Field(1800, ge=10, le=36000)
    cwd: str = Field("")
    env: dict = Field(default_factory=dict)
    model_tier: str = Field("standard", pattern=r"^(budget|standard|premium)$")
    model_strengths: list[str] = Field(default_factory=list)


class SubmitTaskRequest(BaseModel):
    target_agent: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    task_type: str = Field("general")
    cwd: str = Field("")
    auto_select_model: bool = Field(True)


class WorkerRunRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    task_id: str | None = Field(None)


class TransitionGateRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    to_status: str = Field(..., min_length=1)
    acceptance_reason: str | None = Field(None)


class SendMessageRequest(BaseModel):
    source_agent: str = Field(..., min_length=1)
    target_agent: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    task_id: str | None = Field(None)


class ModelSelectRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    task_type: str = Field("general")
    agent_id: str | None = Field(None)


# ============================================================
# CLI Agent 配置
# ============================================================

@router.post("/agents/configure")
async def configure_cli_agent(
    req: ConfigureCLIAgentRequest,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """配置 Agent 为 CLI 模式"""
    await rate_limit(request, limit=20, window=60)

    result = await db.execute(
        select(Agent).where(Agent.id == req.agent_id, Agent.owner_id == uid)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.adapter_mode = req.mode
    agent.adapter_command = req.command
    agent.adapter_timeout = req.timeout
    agent.adapter_cwd = req.cwd
    agent.adapter_env = req.env
    agent.model_tier = req.model_tier
    agent.model_strengths = req.model_strengths

    # 更新 capabilities
    caps = agent.capabilities or {}
    caps["accepts_polling"] = req.mode == "command"
    caps["accepts_websocket"] = req.mode == "websocket"
    agent.capabilities = caps

    await db.commit()

    return {
        "status": "ok",
        "agent_id": req.agent_id,
        "mode": req.mode,
        "command": req.command,
    }


@router.get("/agents/{agent_id}/spec")
async def get_agent_spec(
    agent_id: str,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取 Agent 的 CLI 规格"""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.owner_id == uid)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent_id": agent.id,
        "name": agent.name,
        "mode": agent.adapter_mode,
        "command": agent.adapter_command,
        "timeout": agent.adapter_timeout,
        "cwd": agent.adapter_cwd,
        "env": agent.adapter_env,
        "model_tier": agent.model_tier,
        "model_strengths": agent.model_strengths,
        "roles": agent.skills or [],
        "capabilities": agent.capabilities or {},
    }


# ============================================================
# Pull Queue 操作
# ============================================================

@router.post("/tasks/submit")
async def submit_task(
    req: SubmitTaskRequest,
    request: Request,
    uid: str = Depends(get_current_user_id),
):
    """提交任务到 Pull Queue"""
    await rate_limit(request, limit=30, window=60)

    # 智能模型选择
    if req.auto_select_model:
        result = select_model(req.prompt, req.task_type)
        logger.info(f"Model selected: {result.model} ({result.reason})")

    task_id = await global_pull_queue.submit_task(
        target_agent=req.target_agent,
        prompt=req.prompt,
        task_type=req.task_type,
        cwd=req.cwd,
        source_agent=str(uid),
    )

    return {"status": "ok", "task_id": task_id}


@router.post("/tasks/pull")
async def worker_pull(
    req: WorkerRunRequest,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
):
    """Worker 拉取并执行一个任务（CLI 模式）"""
    await rate_limit(request, limit=60, window=60)

    # 从数据库加载 Agent 规格
    spec = await _load_agent_spec(req.agent_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Agent not found or not CLI mode")

    adapter = build_adapter(spec)
    worker = PullWorker(req.agent_id, global_pull_queue, adapter)
    task = await worker.run_once(req.task_id)

    if task is None:
        return {"status": "no_task", "agent_id": req.agent_id}

    return {
        "status": "ok",
        "task_id": task.id,
        "task_status": task.status,
        "result": task.result[:500] if task.result else None,
        "error": task.error,
    }


@router.get("/tasks")
async def list_tasks(
    target_agent: str | None = None,
    status: str | None = None,
    limit: int = 50,
    actor: tuple[str, str] = Depends(get_current_actor),
):
    """列出 Pull Queue 任务"""
    tasks = await global_pull_queue.list_tasks(
        target_agent=target_agent,
        status=status,
        limit=limit,
    )
    return {
        "tasks": [
            {
                "id": t.id, "target_agent": t.target_agent,
                "task_type": t.task_type, "status": t.status,
                "prompt": t.prompt[:200], "created_at": t.created_at,
                "gate_status": t.gate_status,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, actor: tuple[str, str] = Depends(get_current_actor)):
    """获取任务详情"""
    task = await global_pull_queue.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id, "source_agent": task.source_agent,
        "target_agent": task.target_agent, "task_type": task.task_type,
        "prompt": task.prompt, "status": task.status,
        "result": task.result, "error": task.error,
        "created_at": task.created_at, "started_at": task.started_at,
        "finished_at": task.finished_at,
        "gate_status": task.gate_status,
        "acceptance_status": task.acceptance_status,
        "acceptance_reason": task.acceptance_reason,
        "accepted_at": task.accepted_at,
    }


# ============================================================
# Gate 状态机
# ============================================================

@router.post("/gate/transition")
async def transition_gate(
    req: TransitionGateRequest,
    request: Request,
    uid: str = Depends(get_current_user_id),
):
    """Gate 状态转换"""
    await rate_limit(request, limit=30, window=60)

    task = await global_pull_queue.get_task(req.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        from_status = GateStatus(task.gate_status or "primary_pending")
        to_status = GateStatus(req.to_status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid gate status")

    if not gate_sm.can_transition(from_status, to_status):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {from_status.value} -> {to_status.value}. "
                   f"Valid next: {[s.value for s in VALID_TRANSITIONS.get(from_status, set())]}"
        )

    gate_sm.transition(req.task_id, from_status, to_status)

    # 更新数据库
    evidence = acceptance_evidence(
        task_id=req.task_id,
        gate_status=to_status,
        acceptance_reason=req.acceptance_reason,
    )
    await global_pull_queue.update_gate(
        req.task_id,
        gate_status=to_status.value,
        acceptance_reason=req.acceptance_reason,
        accepted_at=evidence.accepted_at,
    )

    return {
        "status": "ok",
        "task_id": req.task_id,
        "from_status": from_status.value,
        "to_status": to_status.value,
        "valid_next": [s.value for s in VALID_TRANSITIONS.get(to_status, set())],
    }


@router.get("/gate/{task_id}/status")
async def get_gate_status(task_id: str, actor: tuple[str, str] = Depends(get_current_actor)):
    """获取 Gate 状态"""
    task = await global_pull_queue.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    current = GateStatus(task.gate_status or "primary_pending")
    return {
        "task_id": task_id,
        "gate_status": current.value,
        "is_terminal": current.is_terminal,
        "is_blocked": current.is_blocked,
        "valid_next": [s.value for s in VALID_TRANSITIONS.get(current, set())],
        "acceptance_status": task.acceptance_status,
        "acceptance_reason": task.acceptance_reason,
        "accepted_at": task.accepted_at,
    }


# ============================================================
# Agent 消息
# ============================================================

@router.post("/messages/send")
async def send_message(
    req: SendMessageRequest,
    request: Request,
    actor: tuple[str, str] = Depends(get_current_actor),
):
    """发送 Agent 间消息"""
    await rate_limit(request, limit=30, window=60)

    await global_pull_queue.send_message(
        source_agent=req.source_agent,
        target_agent=req.target_agent,
        message=req.message,
        task_id=req.task_id,
    )
    return {"status": "ok"}


@router.get("/messages/inbox/{agent_id}")
async def get_inbox(
    agent_id: str,
    unread_only: bool = False,
    limit: int = 20,
    actor: tuple[str, str] = Depends(get_current_actor),
):
    """获取 Agent 收件箱"""
    messages = await global_pull_queue.get_inbox(
        target_agent=agent_id,
        unread_only=unread_only,
        limit=limit,
    )
    return {"agent_id": agent_id, "messages": messages, "total": len(messages)}


# ============================================================
# 模型选择
# ============================================================

@router.post("/model/select")
async def model_select(
    req: ModelSelectRequest,
    uid: str = Depends(get_current_user_id),
):
    """智能模型选择"""
    result = select_model(req.prompt, req.task_type, req.agent_id)
    return {
        "model": result.model,
        "tier": result.tier,
        "reason": result.reason,
        "bypassed": result.bypassed,
    }


@router.get("/model/pool")
async def get_model_pool():
    """获取模型池配置"""
    selector = ModelSelector()
    return {
        "models": {
            name: {
                "tier": info.tier,
                "strengths": info.strengths,
                "api_type": info.api_type,
            }
            for name, info in selector.model_pool.items()
        }
    }


# ============================================================
# 默认 Agent 规格
# ============================================================

@router.get("/specs/defaults")
async def get_default_specs():
    """获取内置默认 CLI Agent 规格"""
    specs = load_specs()
    return {
        "agents": {
            agent_id: {
                "name": spec.agent_name,
                "command": spec.command,
                "roles": spec.roles,
                "capabilities": spec.capabilities,
                "model_tier": spec.model_tier,
                "model_strengths": spec.model_strengths,
            }
            for agent_id, spec in specs.items()
        }
    }


# ============================================================
# 辅助函数
# ============================================================

async def _load_agent_spec(agent_id: str) -> AgentSpec | None:
    """从数据库加载 Agent 的 CLI 规格"""
    from app.database import async_session
    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None or agent.adapter_mode not in ("command", "mock"):
            return None

        return AgentSpec(
            agent_id=agent.id,
            agent_name=agent.name,
            mode=agent.adapter_mode,
            command=agent.adapter_command or [],
            timeout=agent.adapter_timeout or 1800,
            roles=agent.skills or [],
            capabilities=[c for c in (agent.capabilities or {}).get("accepts_polling", [])],
            cwd=agent.adapter_cwd or "",
            env=agent.adapter_env or {},
            model_tier=agent.model_tier or "standard",
            model_strengths=agent.model_strengths or [],
        )