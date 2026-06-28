"""模板路由 - 管理群组模板"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.models import Template
from app.security import get_current_user_id, rate_limit, sanitize_text

router = APIRouter(prefix="/api/templates", tags=["templates"])


class CreateTemplateReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field("", max_length=100)
    description: str = Field("", max_length=1000)
    config: dict | None = None
    is_public: bool = Field(True)


@router.get("/")
async def list_templates(
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """模板列表（公开模板 + 自己创建的私有模板）"""
    result = await db.execute(
        select(Template).where(
            (Template.is_public == True) | (Template.created_by == uid)
        )
    )
    templates = result.scalars().all()

    return [{
        "id": t.id,
        "name": t.name,
        "display_name": t.display_name,
        "description": t.description,
        "is_public": t.is_public,
        "created_by": t.created_by,
        "created_at": str(t.created_at),
    } for t in templates]


@router.post("/")
async def create_template(
    req: CreateTemplateReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建模板（需要鉴权）"""
    await rate_limit(request, limit=20, window=60)

    template = Template(
        id=str(uuid.uuid4()),
        name=req.name,
        display_name=sanitize_text(req.display_name, max_length=100),
        description=sanitize_text(req.description, max_length=1000),
        config=req.config or {},
        is_public=req.is_public,
        created_by=uid,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    # 写入审计日志
    from app.routers.audit import write_audit_log
    await write_audit_log(db, "user", uid, "template.create",
                          target_type="template", target_id=template.id,
                          ip_address=request.client.host if request.client else "")

    return {"status": "ok", "id": template.id}


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """模板详情"""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 私有模板只能创建者查看
    if not template.is_public and template.created_by != uid:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": template.id,
        "name": template.name,
        "display_name": template.display_name,
        "description": template.description,
        "config": template.config,
        "is_public": template.is_public,
        "created_by": template.created_by,
        "created_at": str(template.created_at),
    }
