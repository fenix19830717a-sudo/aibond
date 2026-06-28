"""资源路由 - 群组资源管理"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists
from typing import Optional

from app.database import get_db
from app.models.models import GroupResource, Group, GroupMember
from app.security import get_current_user_id, rate_limit, sanitize_text

router = APIRouter(prefix="/api/resources", tags=["resources"])


class CreateResourceReq(BaseModel):
    group_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=200)
    resource_type: str = Field(..., min_length=1, max_length=50)
    value: str = Field("", max_length=10000)
    description: str = Field("", max_length=2000)


@router.get("/")
async def list_resources(
    uid: str = Depends(get_current_user_id),
    group_id: Optional[str] = None,
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """资源列表（支持 group_id, type 过滤）"""
    # 只返回用户所在群组的资源
    query = select(GroupResource).where(
        exists().where(
            GroupMember.group_id == GroupResource.group_id,
            GroupMember.user_id == uid
        ) |
        (select(Group.owner_id).where(Group.id == GroupResource.group_id).correlate(GroupResource).scalar_subquery() == uid)
    )
    if group_id:
        query = query.where(GroupResource.group_id == group_id)
    if type:
        query = query.where(GroupResource.resource_type == type)

    query = query.order_by(GroupResource.created_at.desc())
    result = await db.execute(query)
    resources = result.scalars().all()

    return [{
        "id": r.id,
        "group_id": r.group_id,
        "name": r.name,
        "resource_type": r.resource_type,
        "value": r.value,
        "description": r.description,
        "created_by": r.created_by,
        "created_at": str(r.created_at),
    } for r in resources]


@router.get("/accessible")
async def list_accessible_resources(
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """可访问资源（用户所在所有群组的资源）"""
    # 先查询用户所在的所有群组
    groups_result = await db.execute(
        select(Group.id).where(
            (Group.owner_id == uid) |
            exists().where(GroupMember.group_id == Group.id, GroupMember.user_id == uid)
        )
    )
    group_ids = [row[0] for row in groups_result.all()]

    if not group_ids:
        return {"resources": []}

    result = await db.execute(
        select(GroupResource)
        .where(GroupResource.group_id.in_(group_ids))
        .order_by(GroupResource.created_at.desc())
    )
    resources = result.scalars().all()

    return {"resources": [{
        "id": r.id,
        "group_id": r.group_id,
        "name": r.name,
        "resource_type": r.resource_type,
        "value": r.value,
        "description": r.description,
        "created_by": r.created_by,
        "created_at": str(r.created_at),
    } for r in resources]}


@router.post("/")
async def create_resource(
    req: CreateResourceReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建资源"""
    await rate_limit(request, limit=30, window=60)

    # 验证用户是群组成员
    group = await db.execute(select(Group).where(Group.id == req.group_id))
    g = group.scalar_one_or_none()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")

    membership = await db.execute(
        select(GroupMember).where(GroupMember.group_id == req.group_id, GroupMember.user_id == uid)
    )
    if not membership.scalar_one_or_none() and g.owner_id != uid:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    resource = GroupResource(
        id=str(uuid.uuid4()),
        group_id=req.group_id,
        name=sanitize_text(req.name, max_length=200),
        resource_type=req.resource_type,
        value=req.value,
        description=sanitize_text(req.description, max_length=2000),
        created_by=uid,
    )
    db.add(resource)
    await db.commit()
    await db.refresh(resource)

    return {"status": "ok", "id": resource.id}
