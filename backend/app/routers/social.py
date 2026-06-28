"""社交功能路由 - 好友、朋友圈、Agent 雇佣"""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.models import (
    User, Agent, SocialFriend, SocialMoment, SocialMomentComment, AgentHire,
)
from app.security import get_current_user_id, rate_limit, sanitize_text

router = APIRouter(prefix="/api/social", tags=["social"])


# ── 请求模型 ──

class FriendRequestReq(BaseModel):
    friend_id: str = Field(..., min_length=1)

class FriendActionReq(BaseModel):
    action: str = Field(..., pattern=r"^(accept|reject)$")

class HireAgentReq(BaseModel):
    agent_id: str = Field(..., min_length=1)

class CreateMomentReq(BaseModel):
    content: str = Field(..., max_length=5000)
    image_url: str = Field("", max_length=500)
    visibility: str = Field("public", pattern=r"^(public|friends|private)$")

class CreateCommentReq(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


# ── 好友接口 ──

@router.get("/friends")
async def list_friends(
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """好友列表，支持 accepted / pending_sent / pending_received"""
    # 已接受的好友
    accepted_result = await db.execute(
        select(SocialFriend).where(
            SocialFriend.status == "accepted",
            (SocialFriend.user_id == uid) | (SocialFriend.friend_id == uid)
        )
    )
    accepted = accepted_result.scalars().all()

    # 我发送的待处理请求
    sent_result = await db.execute(
        select(SocialFriend).where(
            SocialFriend.requested_by == uid,
            SocialFriend.status == "pending"
        )
    )
    sent = sent_result.scalars().all()

    # 我收到的待处理请求
    received_result = await db.execute(
        select(SocialFriend).where(
            SocialFriend.friend_id == uid,
            SocialFriend.requested_by != uid,
            SocialFriend.status == "pending"
        )
    )
    received = received_result.scalars().all()

    def _format(f):
        other_id = f.friend_id if f.user_id == uid else f.user_id
        return {"id": f.id, "friend_id": other_id, "status": f.status, "created_at": str(f.created_at)}

    return {
        "accepted": [_format(f) for f in accepted],
        "pending_sent": [_format(f) for f in sent],
        "pending_received": [_format(f) for f in received],
    }


@router.post("/friends/request")
async def send_friend_request(
    req: FriendRequestReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """发送好友请求"""
    await rate_limit(request, limit=20, window=60)

    if req.friend_id == uid:
        raise HTTPException(status_code=400, detail="Cannot add yourself as friend")

    # 验证对方用户存在
    friend = await db.execute(select(User).where(User.id == req.friend_id))
    if not friend.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # 检查是否已有关系
    existing = await db.execute(
        select(SocialFriend).where(
            ((SocialFriend.user_id == uid) & (SocialFriend.friend_id == req.friend_id)) |
            ((SocialFriend.user_id == req.friend_id) & (SocialFriend.friend_id == uid))
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Friend request already exists")

    friendship = SocialFriend(
        id=str(uuid.uuid4()),
        user_id=uid,
        friend_id=req.friend_id,
        status="pending",
        requested_by=uid,
    )
    db.add(friendship)
    await db.commit()

    return {"status": "ok", "id": friendship.id}


@router.post("/friends/{friend_id}")
async def handle_friend_request(
    friend_id: str,
    req: FriendActionReq,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """接受/拒绝好友请求"""
    friendship = await db.execute(
        select(SocialFriend).where(
            SocialFriend.friend_id == uid,
            SocialFriend.user_id == friend_id,
            SocialFriend.status == "pending"
        )
    )
    f = friendship.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=404, detail="No pending request from this user")

    f.status = "accepted" if req.action == "accept" else "rejected"
    await db.commit()

    return {"status": "ok", "new_status": f.status}


# ── Agent 雇佣接口 ──

@router.get("/agents/hires")
async def list_agent_hires(
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Agent 雇佣列表"""
    result = await db.execute(
        select(AgentHire).where(
            (AgentHire.owner_id == uid) | (AgentHire.hirer_id == uid),
            AgentHire.status == "active"
        )
    )
    hires = result.scalars().all()

    return [{
        "id": h.id,
        "agent_id": h.agent_id,
        "owner_id": h.owner_id,
        "hirer_id": h.hirer_id,
        "hirer_type": h.hirer_type,
        "status": h.status,
        "created_at": str(h.created_at),
    } for h in hires]


@router.post("/agents/hire")
async def hire_agent(
    req: HireAgentReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """雇佣 Agent"""
    await rate_limit(request, limit=20, window=60)

    # 验证 Agent 存在
    agent = await db.execute(select(Agent).where(Agent.id == req.agent_id))
    agent_obj = agent.scalar_one_or_none()
    if not agent_obj:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 检查是否已雇佣
    existing = await db.execute(
        select(AgentHire).where(
            AgentHire.agent_id == req.agent_id,
            AgentHire.hirer_id == uid,
            AgentHire.status == "active"
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already hired this agent")

    hire = AgentHire(
        id=str(uuid.uuid4()),
        agent_id=req.agent_id,
        owner_id=agent_obj.owner_id,
        hirer_id=uid,
        hirer_type="user",
        status="active",
    )
    db.add(hire)
    await db.commit()

    return {"status": "ok", "id": hire.id}


# ── 朋友圈接口 ──

@router.get("/moments/feed")
async def moments_feed(
    uid: str = Depends(get_current_user_id),
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """朋友圈 Feed"""
    if limit < 1 or limit > 100:
        limit = 20
    if offset < 0:
        offset = 0

    # 查询 public 和 friends 的动态
    result = await db.execute(
        select(SocialMoment)
        .where(SocialMoment.visibility.in_(["public", "friends"]))
        .order_by(SocialMoment.created_at.desc())
        .limit(limit).offset(offset)
    )
    moments = result.scalars().all()

    return [{
        "id": m.id,
        "author_type": m.author_type,
        "author_id": m.author_id,
        "content": m.content,
        "image_url": m.image_url,
        "visibility": m.visibility,
        "likes": m.likes,
        "comment_count": m.comment_count,
        "created_at": str(m.created_at),
    } for m in moments]


@router.post("/moments")
async def create_moment(
    req: CreateMomentReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """发朋友圈"""
    await rate_limit(request, limit=10, window=60)

    safe_content = sanitize_text(req.content, max_length=5000)

    moment = SocialMoment(
        id=str(uuid.uuid4()),
        author_type="user",
        author_id=uid,
        content=safe_content,
        image_url=req.image_url,
        visibility=req.visibility,
    )
    db.add(moment)
    await db.commit()
    await db.refresh(moment)

    return {"status": "ok", "id": moment.id}


@router.post("/moments/{moment_id}/comments")
async def add_comment(
    moment_id: str,
    req: CreateCommentReq,
    request: Request,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """评论动态"""
    await rate_limit(request, limit=30, window=60)

    # 验证动态存在
    moment = await db.execute(select(SocialMoment).where(SocialMoment.id == moment_id))
    if not moment.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Moment not found")

    safe_content = sanitize_text(req.content, max_length=2000)

    comment = SocialMomentComment(
        id=str(uuid.uuid4()),
        moment_id=moment_id,
        author_type="user",
        author_id=uid,
        content=safe_content,
    )
    db.add(comment)

    # 更新评论计数
    from sqlalchemy import update
    await db.execute(
        update(SocialMoment)
        .where(SocialMoment.id == moment_id)
        .values(comment_count=SocialMoment.comment_count + 1)
    )
    await db.commit()

    return {"status": "ok", "id": comment.id}


@router.post("/moments/{moment_id}/like")
async def like_moment(
    moment_id: str,
    uid: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """点赞动态"""
    moment = await db.execute(select(SocialMoment).where(SocialMoment.id == moment_id))
    m = moment.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Moment not found")

    from sqlalchemy import update
    await db.execute(
        update(SocialMoment)
        .where(SocialMoment.id == moment_id)
        .values(likes=SocialMoment.likes + 1)
    )
    await db.commit()

    return {"status": "ok", "likes": m.likes + 1}
