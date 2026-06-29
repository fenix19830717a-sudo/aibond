"""任务路由 - 群组任务管理（创建、分配、完成、审核）"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists
from typing import Optional

from app.database import get_db
from app.models.models import Task, Review, Group, GroupMember, GroupResource
from app.security import get_current_user_id, get_current_actor, rate_limit, sanitize_text

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── 请求模型 ──

class CreateTaskReq(BaseModel):
    group_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=5000)
    priority: str = Field("normal", pattern=r"^(low|normal|high|urgent)$")
    assignee_type: str = Field(..., pattern=r"^(user|agent)$")
    assignee_id: str = Field(..., min_length=1)
    due_date: str | None = Field(None)

class UpdateTaskReq(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    status: str | None = Field(None, pattern=r"^(pending|assigned|in_progress|done|failed|cancelled)$")
    priority: str | None = Field(None, pattern=r"^(low|normal|high|urgent)$")
    progress: int | None = Field(None, ge=0, le=100)
    result: dict | None = None
    due_date: str | None = None

class AssignTaskReq(BaseModel):
    assignee_type: str = Field(..., pattern=r"^(user|agent)$")
    assignee_id: str = Field(..., min_length=1)

class CompleteTaskReq(BaseModel):
    result: dict | None = None

class ReviewTaskReq(BaseModel):
    conclusion: str = Field(..., pattern=r"^(approved|changes_requested|rejected)$")
    comment: str = Field("", max_length=2000)


# ── 辅助函数 ──

async def _verify_group_member(db: AsyncSession, group_id: str, uid: str) -> bool:
    """验证用户是群组成员"""
    # 检查是否是 owner
    group = await db.execute(select(Group).where(Group.id == group_id))
    g = group.scalar_one_or_none()
    if g and g.owner_id == uid:
        return True
    # 检查成员表
    membership = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == uid)
    )
    return membership.scalar_one_or_none() is not None


# ── 路由 ──

@router.get("/")
async def list_tasks(
    uid: str = Depends(get_current_user_id),
    group_id: Optional[str] = None,
    status: Optional[str] = None,
    assignee_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """任务列表（支持 group_id, status, assignee_id 过滤）"""
    query = select(Task).where(
        # 只返回用户所在群组的任务
        exists().where(
            GroupMember.group_id == Task.group_id,
            GroupMember.user_id == uid
        ) |
        (select(Group.owner_id).where(Group.id == Task.group_id).correlate(Task).scalar_subquery() == uid)
    )
    if group_id:
        query = query.where(Task.group_id == group_id)
    if status:
        query = query.where(Task.status == status)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)

    query = query.order_by(Task.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()

    return [{
        "id": t.id,
        "group_id": t.group_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "assignee_type": t.assignee_type,
        "assignee_id": t.assignee_id,
        "delegator_type": t.delegator_type,
        "delegator_id": t.delegator_id,
        "result": t.result,
        "progress": t.progress,
        "due_date": str(t.due_date) if t.due_date else None,
        "created_at": str(t.created_at),
        "updated_at": str(t.updated_at),
    } for t in tasks]


@router.post("/")
async def create_task(
    req: CreateTaskReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建任务"""
    await rate_limit(request, limit=30, window=60)

    # 验证用户是群组成员
    if not await _verify_group_member(db, req.group_id, uid):
        raise HTTPException(status_code=403, detail="Not a member of this group")

    due_date = None
    if req.due_date:
        try:
            due_date = datetime.fromisoformat(req.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format")

    task = Task(
        id=str(uuid.uuid4()),
        group_id=req.group_id,
        title=sanitize_text(req.title, max_length=200),
        description=sanitize_text(req.description, max_length=5000),
        status="pending",
        priority=req.priority,
        assignee_type=req.assignee_type,
        assignee_id=req.assignee_id,
        delegator_type="user",
        delegator_id=uid,
        due_date=due_date,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 写入审计日志
    from app.routers.audit import write_audit_log
    await write_audit_log(db, "user", uid, "task.create",
                          target_type="task", target_id=task.id,
                          ip_address=request.client.host if request.client else "")

    return {"status": "ok", "id": task.id}


@router.put("/{task_id}")
async def update_task(
    task_id: str,
    req: UpdateTaskReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """更新任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify group membership
    if not await _verify_group_member(db, task.group_id, uid):
        raise HTTPException(status_code=403, detail="Not a member of the task's group")

    if req.title is not None:
        task.title = sanitize_text(req.title, max_length=200)
    if req.description is not None:
        task.description = sanitize_text(req.description, max_length=5000)
    if req.status is not None:
        task.status = req.status
    if req.priority is not None:
        task.priority = req.priority
    if req.progress is not None:
        task.progress = req.progress
    if req.result is not None:
        task.result = req.result
    if req.due_date is not None:
        try:
            task.due_date = datetime.fromisoformat(req.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format")

    task.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "ok"}


@router.post("/{task_id}/assign")
async def assign_task(
    task_id: str,
    req: AssignTaskReq,
    request: Request,
    actor: tuple = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """分配/委派任务（支持用户和 Agent）"""
    actor_id, actor_type = actor

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify authorization: user must be group member, agent must be task assignee
    if actor_type == "user":
        if not await _verify_group_member(db, task.group_id, actor_id):
            raise HTTPException(status_code=403, detail="Not a member of the task's group")
    elif actor_type == "agent" and task.assignee_id != actor_id:
        raise HTTPException(status_code=403, detail="Only the assignee can reassign this task")

    task.assignee_type = req.assignee_type
    task.assignee_id = req.assignee_id
    task.delegator_type = actor_type
    task.delegator_id = actor_id
    task.status = "assigned"
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "ok"}


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: str,
    req: CompleteTaskReq,
    request: Request,
    actor: tuple = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    """完成任务（支持用户和 Agent）"""
    actor_id, actor_type = actor

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 只有被分配者可以完成（同时校验类型和 ID）
    if task.assignee_type != actor_type or task.assignee_id != actor_id:
        raise HTTPException(status_code=403, detail="Only assignee can complete the task")

    task.status = "done"
    task.result = req.result or {}
    task.progress = 100
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "ok"}


@router.post("/{task_id}/review")
async def review_task(
    task_id: str,
    req: ReviewTaskReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """审核任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Verify group membership
    if not await _verify_group_member(db, task.group_id, uid):
        raise HTTPException(status_code=403, detail="Not a member of the task's group")

    review = Review(
        id=str(uuid.uuid4()),
        task_id=task_id,
        reviewer_id=uid,
        reviewer_type="user",
        conclusion=req.conclusion,
        comment=sanitize_text(req.comment, max_length=2000),
    )
    db.add(review)

    # 如果审核通过，更新任务状态
    if req.conclusion == "approved":
        task.status = "done"
    elif req.conclusion == "rejected":
        task.status = "failed"

    task.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # 写入审计日志
    from app.routers.audit import write_audit_log
    await write_audit_log(db, "user", uid, f"task.review.{req.conclusion}",
                          target_type="task", target_id=task_id,
                          details={"review_id": review.id},
                          ip_address=request.client.host if request.client else "")

    return {"status": "ok", "review_id": review.id}
