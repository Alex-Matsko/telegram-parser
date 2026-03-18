"""Unresolved / failed messages queue — ТЗ 9.4."""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.raw_message import RawMessage
from app.models.source import Source

router = APIRouter(prefix="/unresolved", tags=["Unresolved"])


class UnresolvedMessage(BaseModel):
    id: int
    source_id: int
    source_name: Optional[str] = None
    message_text: str
    message_date: datetime
    parse_status: str
    parse_error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnresolvedListResponse(BaseModel):
    items: list[UnresolvedMessage]
    total: int
    page: int
    per_page: int
    pages: int


class RetryRequest(BaseModel):
    message_ids: list[int]


class ManualResolveRequest(BaseModel):
    parse_status: str = "parsed"
    note: Optional[str] = None


@router.get("", response_model=UnresolvedListResponse)
async def list_unresolved(
    page: int = 1,
    per_page: int = 50,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List failed/needs_review messages with pagination."""
    filters = [or_(
        RawMessage.parse_status == "needs_review",
        RawMessage.parse_status == "failed",
    )]
    if status:
        filters = [RawMessage.parse_status == status]

    count = (await db.execute(
        select(func.count(RawMessage.id)).where(*filters)
    )).scalar() or 0

    result = await db.execute(
        select(RawMessage)
        .where(*filters)
        .order_by(RawMessage.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    messages = result.scalars().all()

    # Enrich with source names
    source_ids = list({m.source_id for m in messages})
    sources_map = {}
    if source_ids:
        src_result = await db.execute(
            select(Source).where(Source.id.in_(source_ids))
        )
        sources_map = {s.id: s.source_name for s in src_result.scalars().all()}

    items = [
        UnresolvedMessage(
            id=m.id,
            source_id=m.source_id,
            source_name=sources_map.get(m.source_id),
            message_text=m.message_text,
            message_date=m.message_date,
            parse_status=m.parse_status,
            parse_error=m.parse_error,
            created_at=m.created_at,
        )
        for m in messages
    ]

    return UnresolvedListResponse(
        items=items,
        total=count,
        page=page,
        per_page=per_page,
        pages=max(1, (count + per_page - 1) // per_page),
    )


@router.post("/retry", status_code=202)
async def retry_messages(
    body: RetryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset selected messages back to 'pending' so Celery will reparse them.
    Frontend 'Retry' button calls this.
    """
    result = await db.execute(
        select(RawMessage).where(RawMessage.id.in_(body.message_ids))
    )
    messages = result.scalars().all()
    for msg in messages:
        msg.parse_status = "pending"
        msg.is_processed = False
        msg.parse_error = None
    await db.commit()
    return {"queued": len(messages), "message_ids": body.message_ids}


@router.post("/retry-all", status_code=202)
async def retry_all_failed(
    db: AsyncSession = Depends(get_db),
):
    """Reset ALL failed/needs_review messages to pending."""
    result = await db.execute(
        select(RawMessage).where(
            or_(
                RawMessage.parse_status == "needs_review",
                RawMessage.parse_status == "failed",
            )
        )
    )
    messages = result.scalars().all()
    count = len(messages)
    for msg in messages:
        msg.parse_status = "pending"
        msg.is_processed = False
        msg.parse_error = None
    await db.commit()
    return {"queued": count}


@router.post("/{message_id}/resolve", status_code=200)
async def manual_resolve(
    message_id: int,
    body: ManualResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually mark a message as resolved (e.g. after human review)."""
    result = await db.execute(
        select(RawMessage).where(RawMessage.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.parse_status = body.parse_status
    msg.is_processed = True
    await db.commit()
    return {"id": message_id, "parse_status": msg.parse_status}
