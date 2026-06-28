"""审核路由 - 审核列表查询"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists

from app.database import get_db
from app.models.models import Review, Task, Group, GroupMember
from app.security import get_current_user_id

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/")
async def list_reviews(
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """审核列表（返回用户所在群组的所有审核）"""
    result = await db.execute(
        select(Review).where(
            exists().where(
                GroupMember.group_id == Task.group_id,
                GroupMember.user_id == uid
            ) |
            (select(Group.owner_id).where(Group.id == Task.group_id).correlate(Task).scalar_subquery() == uid)
        ).order_by(Review.created_at.desc())
    )
    reviews = result.scalars().all()

    return [{
        "id": r.id,
        "task_id": r.task_id,
        "reviewer_id": r.reviewer_id,
        "reviewer_type": r.reviewer_type,
        "conclusion": r.conclusion,
        "comment": r.comment,
        "created_at": str(r.created_at),
    } for r in reviews]


@router.get("/pending-for-me")
async def pending_reviews_for_me(
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """待我审核（delegator_id == uid 且 status != done 的任务列表）"""
    result = await db.execute(
        select(Task).where(
            Task.delegator_id == uid,
            Task.status.in_(["in_progress", "assigned"]),
            Task.delegator_type == "user"
        ).order_by(Task.created_at.desc())
    )
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
        "progress": t.progress,
        "created_at": str(t.created_at),
        "updated_at": str(t.updated_at),
    } for t in tasks]
