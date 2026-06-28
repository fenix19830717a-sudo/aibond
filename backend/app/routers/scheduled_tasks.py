"""定时任务路由 - 管理定时任务"""

import uuid
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.models import ScheduledTask
from app.security import get_current_user_id, rate_limit, sanitize_text
from app.workflows.nl_cron import parse_nl_cron, is_valid_cron

router = APIRouter(prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])

# 标准 cron 表达式正则 (5 字段)
_CRON_PATTERN = re.compile(
    r"^("
    r"\*(\/\d+)?|"
    r"\d+(-\d+)?(/\d+)?"
    r")(,(\*(\/\d+)?|\d+(-\d+)?(/\d+)?))*$"
)


class ParseCronReq(BaseModel):
    natural_language: str = Field(..., min_length=1, max_length=200, description="自然语言时间描述，如 '每天早上9点'")

class CreateScheduledTaskReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    cron_expression: str = Field(..., min_length=1, max_length=100)
    tz: str = Field("UTC", max_length=50)
    action_type: str = Field(..., min_length=1, max_length=50)
    action_config: dict | None = None
    group_id: str | None = Field(None, min_length=1)

class UpdateScheduledTaskReq(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    cron_expression: str | None = Field(None, min_length=1, max_length=100)
    timezone: str | None = Field(None, max_length=50)
    action_type: str | None = Field(None, min_length=1, max_length=50)
    action_config: dict | None = None
    is_active: bool | None = None


def _auto_parse_cron(expression: str) -> str:
    """如果 expression 不是标准 cron 格式，尝试用自然语言解析。"""
    expression = expression.strip()
    # 先检查是否为标准 cron 格式
    if is_valid_cron(expression):
        return expression
    # 尝试自然语言解析
    result = parse_nl_cron(expression)
    if "error" not in result and result.get("cron"):
        return result["cron"]
    # 无法解析，保留原值（后续由数据库层或调度器验证）
    return expression


@router.get("/")
async def list_scheduled_tasks(
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """定时任务列表"""
    result = await db.execute(
        select(ScheduledTask).where(ScheduledTask.owner_id == uid)
        .order_by(ScheduledTask.created_at.desc())
    )
    tasks = result.scalars().all()

    return [{
        "id": t.id,
        "name": t.name,
        "cron_expression": t.cron_expression,
        "timezone": t.timezone,
        "action_type": t.action_type,
        "action_config": t.action_config,
        "group_id": t.group_id,
        "is_active": t.is_active,
        "last_run_at": str(t.last_run_at) if t.last_run_at else None,
        "next_run_at": str(t.next_run_at) if t.next_run_at else None,
        "created_at": str(t.created_at),
    } for t in tasks]


@router.post("/parse-cron")
async def parse_cron_endpoint(req: ParseCronReq):
    """解析自然语言时间描述为 cron 表达式"""
    result = parse_nl_cron(req.natural_language)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"cron": result["cron"], "description": result["description"]}


@router.post("/")
async def create_scheduled_task(
    req: CreateScheduledTaskReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建定时任务
    如果 cron_expression 不是标准 cron 格式，自动调用自然语言解析器转换。
    """
    await rate_limit(request, limit=20, window=60)

    # 自动解析自然语言 cron 表达式
    cron_expression = _auto_parse_cron(req.cron_expression)

    task = ScheduledTask(
        id=str(uuid.uuid4()),
        owner_id=uid,
        name=sanitize_text(req.name, max_length=100),
        cron_expression=cron_expression,
        timezone=req.tz,
        action_type=req.action_type,
        action_config=req.action_config or {},
        group_id=req.group_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 写入审计日志
    from app.routers.audit import write_audit_log
    await write_audit_log(db, "user", uid, "scheduled_task.create",
                          target_type="scheduled_task", target_id=task.id,
                          ip_address=request.client.host if request.client else "")

    return {"status": "ok", "id": task.id}


@router.put("/{task_id}")
async def update_scheduled_task(
    task_id: str,
    req: UpdateScheduledTaskReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """更新定时任务"""
    result = await db.execute(
        select(ScheduledTask).where(ScheduledTask.id == task_id, ScheduledTask.owner_id == uid)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if req.name is not None:
        task.name = sanitize_text(req.name, max_length=100)
    if req.cron_expression is not None:
        task.cron_expression = _auto_parse_cron(req.cron_expression)
    if req.timezone is not None:
        task.timezone = req.timezone
    if req.action_type is not None:
        task.action_type = req.action_type
    if req.action_config is not None:
        task.action_config = req.action_config
    if req.is_active is not None:
        task.is_active = req.is_active

    await db.commit()

    return {"status": "ok"}


@router.delete("/{task_id}")
async def delete_scheduled_task(
    task_id: str,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """删除定时任务"""
    result = await db.execute(
        select(ScheduledTask).where(ScheduledTask.id == task_id, ScheduledTask.owner_id == uid)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.delete(task)
    await db.commit()

    # 写入审计日志
    from app.routers.audit import write_audit_log
    await write_audit_log(db, "user", uid, "scheduled_task.delete",
                          target_type="scheduled_task", target_id=task_id,
                          ip_address=request.client.host if request.client else "")

    return {"status": "ok"}
