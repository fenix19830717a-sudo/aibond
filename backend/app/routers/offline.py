from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import get_db
from app.models.models import OfflineMessage
from app.security import get_current_actor

router = APIRouter(prefix="/api/offline", tags=["offline"])


@router.get("/")
async def get_offline_messages(
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    actor_id, actor_type = actor

    result = await db.execute(
        select(OfflineMessage)
        .where(
            OfflineMessage.target_type == actor_type,
            OfflineMessage.target_id == actor_id,
            OfflineMessage.delivered_at == None,
        )
        .order_by(OfflineMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id": m.id,
            "message": m.message_json,
            "created_at": str(m.created_at),
        }
        for m in messages
    ]


@router.post("/{msg_id}/ack")
async def acknowledge_message(msg_id: str, actor: tuple[str, str] = Depends(get_current_actor), db: AsyncSession = Depends(get_db)):
    actor_id, actor_type = actor

    result = await db.execute(
        select(OfflineMessage).where(OfflineMessage.id == msg_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify the message belongs to the current actor
    if msg.target_type != actor_type or msg.target_id != actor_id:
        raise HTTPException(status_code=403, detail="Message does not belong to current user")

    msg.delivered_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "ok"}
