from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import os
import shutil

from app.database import get_db
from app.models.models import File as FileModel, Group, GroupMember, Session as SessionModel, SessionMember
from app.security import get_current_actor

router = APIRouter(prefix="/api/files", tags=["files"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_MIME_TYPES = {
    "text/plain", "application/json", "application/pdf",
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/zip", "application/x-tar", "application/gzip",
    "application/octet-stream", "application/x-python-code",
    "text/csv", "text/markdown", "application/javascript",
    "text/html", "text/css", "application/xml",
}


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    group_id: str = "",
    session_id: str = "",
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    actor_id, actor_type = actor

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    storage_name = f"{file_id}{ext}"
    storage_path = os.path.join(UPLOAD_DIR, storage_name)

    # Read content with size limit
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Validate MIME type (skip for empty content_type to avoid false rejects)
    mime_type = file.content_type or ""
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {mime_type}")

    with open(storage_path, "wb") as f:
        f.write(content)

    file_record = FileModel(
        id=file_id,
        filename=storage_name,
        original_name=file.filename or "unnamed",
        file_size=len(content),
        mime_type=file.content_type or "",
        uploader_type=actor_type,
        uploader_id=actor_id,
        group_id=group_id or None,
        session_id=session_id or None,
        storage_path=storage_path,
    )
    db.add(file_record)
    await db.commit()

    return {
        "id": file_id,
        "filename": file.filename,
        "size": len(content),
        "mime_type": file.content_type,
    }


@router.get("/list")
async def list_files(
    group_id: str = None,
    session_id: str = None,
    actor: tuple[str, str] = Depends(get_current_actor),
    db: AsyncSession = Depends(get_db),
):
    actor_id, actor_type = actor
    query = select(FileModel).where(
        FileModel.uploader_id == actor_id,
        FileModel.uploader_type == actor_type,
    )
    if group_id:
        query = query.where(FileModel.group_id == group_id)
    if session_id:
        query = query.where(FileModel.session_id == session_id)
    result = await db.execute(query)
    files = result.scalars().all()
    return [
        {
            "id": f.id,
            "filename": f.original_name,
            "size": f.file_size,
            "mime_type": f.mime_type,
            "uploader_type": f.uploader_type,
            "uploader_id": f.uploader_id,
            "created_at": str(f.created_at),
        }
        for f in files
    ]


@router.get("/{file_id}")
async def download_file(file_id: str, actor: tuple[str, str] = Depends(get_current_actor), db: AsyncSession = Depends(get_db)):
    actor_id, actor_type = actor
    result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    file_record = result.scalar_one_or_none()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    # Ownership check: uploader OR member of the file's group/session
    if file_record.uploader_id == actor_id and file_record.uploader_type == actor_type:
        pass  # Owner can download
    elif file_record.group_id:
        # Check group membership
        if actor_type == "user":
            member_result = await db.execute(
                select(GroupMember).where(
                    GroupMember.group_id == file_record.group_id,
                    GroupMember.user_id == actor_id,
                )
            )
            if not member_result.scalar_one_or_none():
                # Also check if user is group owner
                group_result = await db.execute(select(Group).where(Group.id == file_record.group_id))
                group = group_result.scalar_one_or_none()
                if not group or group.owner_id != actor_id:
                    raise HTTPException(status_code=403, detail="Access denied: not a member of this group")
        else:
            raise HTTPException(status_code=403, detail="Access denied")
    elif file_record.session_id:
        # Check session membership
        member_result = await db.execute(
            select(SessionMember).where(
                SessionMember.session_id == file_record.session_id,
                SessionMember.member_id == actor_id,
            )
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied: not a member of this session")
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        path=file_record.storage_path,
        filename=file_record.original_name,
        media_type=file_record.mime_type,
    )
