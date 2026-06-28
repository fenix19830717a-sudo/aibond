"""审计日志路由 - 记录和查询系统操作日志"""

import csv
import io
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.database import get_db
from app.models.models import AuditLog
from app.security import get_current_user_id

router = APIRouter(prefix="/api/audit", tags=["audit"])


async def write_audit_log(
    db: AsyncSession,
    actor_type: str,
    actor_id: str,
    action: str,
    target_type: str = "",
    target_id: str = "",
    details: dict = None,
    ip_address: str = "",
):
    """写入审计日志的辅助函数，供其他路由调用"""
    log = AuditLog(
        id=str(uuid.uuid4()),
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(log)
    await db.commit()


@router.get("/")
async def list_audit_logs(
    uid: str = Depends(get_current_user_id),
    actor_type: Optional[str] = Query(None, description="过滤 actor_type: user/agent/system"),
    action: Optional[str] = Query(None, description="过滤 action，如 auth.login"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """审计日志列表（需要鉴权）"""
    query = select(AuditLog)
    if actor_type:
        query = query.where(AuditLog.actor_type == actor_type)
    if action:
        query = query.where(AuditLog.action == action)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [{
        "id": log.id,
        "actor_type": log.actor_type,
        "actor_id": log.actor_id,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "details": log.details,
        "ip_address": log.ip_address,
        "created_at": str(log.created_at),
    } for log in logs]


@router.get("/stats")
async def audit_stats(
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """操作统计"""
    # 按 action 分组统计
    result = await db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
    )
    action_counts = {row[0]: row[1] for row in result.all()}

    # 按日期统计（最近7天）
    seven_days_ago = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_result = await db.execute(
        select(func.date(AuditLog.created_at), func.count(AuditLog.id))
        .where(AuditLog.created_at >= seven_days_ago)
        .group_by(func.date(AuditLog.created_at))
        .order_by(func.date(AuditLog.created_at))
    )
    daily_counts = {str(row[0]): row[1] for row in daily_result.all()}

    return {
        "total_actions": sum(action_counts.values()),
        "by_action": action_counts,
        "daily_last_7d": daily_counts,
    }


@router.get("/export.csv")
async def export_audit_csv(
    uid: str = Depends(get_current_user_id),
    actor_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """导出审计日志为 CSV"""
    query = select(AuditLog)
    if actor_type:
        query = query.where(AuditLog.actor_type == actor_type)
    if action:
        query = query.where(AuditLog.action == action)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    # 生成 CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "actor_type", "actor_id", "action", "target_type", "target_id", "details", "ip_address", "created_at"])
    for log in logs:
        writer.writerow([
            log.id, log.actor_type, log.actor_id, log.action,
            log.target_type, log.target_id,
            str(log.details) if log.details else "",
            log.ip_address, str(log.created_at),
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
