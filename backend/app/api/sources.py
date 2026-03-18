"""Sources API — manage Telegram data sources."""
from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.source import Source
from app.models.raw_message import RawMessage

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreate(BaseModel):
    source_name: str
    type: str
    telegram_id: int
    supplier_id: Optional[int] = None
    is_active: bool = True
    poll_interval_minutes: int = 30
    parsing_strategy: str = "auto"
    bot_scenario_id: Optional[int] = None


class SourceUpdate(BaseModel):
    source_name: Optional[str] = None
    type: Optional[str] = None
    telegram_id: Optional[int] = None
    supplier_id: Optional[int] = None
    is_active: Optional[bool] = None
    poll_interval_minutes: Optional[int] = None
    parsing_strategy: Optional[str] = None
    bot_scenario_id: Optional[int] = None


class SourceResponse(BaseModel):
    id: int
    source_name: str
    type: str
    telegram_id: int
    supplier_id: Optional[int] = None
    is_active: bool
    poll_interval_minutes: int
    parsing_strategy: str
    bot_scenario_id: Optional[int] = None
    last_message_id: Optional[int] = None
    last_read_at: Optional[datetime] = None
    error_count: Optional[int] = None
    last_error: Optional[str] = None

    class Config:
        from_attributes = True


class RecentMessage(BaseModel):
    id: int
    message_text: str
    message_date: datetime
    parse_status: str
    parse_error: Optional[str] = None


class SourceStatsResponse(BaseModel):
    source_id: int
    source_name: str
    telegram_id: int
    type: str
    is_active: bool
    supplier_id: Optional[int] = None
    last_read_at: Optional[datetime] = None
    error_count: int
    last_error: Optional[str] = None
    poll_interval_minutes: int
    parsing_strategy: str
    messages_total: int
    messages_24h: int
    messages_pending: int
    messages_parsed: int
    messages_failed: int
    messages_needs_review: int
    parse_success_rate: float
    offers_total: int
    offers_current: int
    products_covered: int
    recent_messages: list[RecentMessage]


@router.get("", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).order_by(Source.id))
    return result.scalars().all()


@router.get("/{source_id}/stats", response_model=SourceStatsResponse)
async def get_source_stats(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    rows = (await db.execute(
        select(RawMessage.parse_status, func.count(RawMessage.id))
        .where(RawMessage.source_id == source_id)
        .group_by(RawMessage.parse_status)
    )).all()
    status_counts = {s: c for s, c in rows}

    messages_parsed       = status_counts.get("parsed", 0)
    messages_failed       = status_counts.get("failed", 0)
    messages_pending      = status_counts.get("pending", 0)
    messages_needs_review = status_counts.get("needs_review", 0)
    messages_total        = sum(status_counts.values())

    messages_24h = (await db.execute(
        select(func.count(RawMessage.id)).where(
            and_(RawMessage.source_id == source_id, RawMessage.created_at >= since_24h)
        )
    )).scalar() or 0

    processed = messages_parsed + messages_failed + messages_needs_review
    parse_success_rate = round(messages_parsed / processed, 3) if processed else 0.0

    offers_total = offers_current = products_covered = 0
    if source.supplier_id:
        from app.models.offer import Offer
        offers_total = (await db.execute(
            select(func.count(Offer.id)).where(Offer.supplier_id == source.supplier_id)
        )).scalar() or 0
        offers_current = (await db.execute(
            select(func.count(Offer.id)).where(
                and_(Offer.supplier_id == source.supplier_id, Offer.is_current == True)  # noqa
            )
        )).scalar() or 0
        products_covered = (await db.execute(
            select(func.count(func.distinct(Offer.product_id))).where(
                and_(Offer.supplier_id == source.supplier_id, Offer.is_current == True)  # noqa
            )
        )).scalar() or 0

    recent_rows = (await db.execute(
        select(RawMessage)
        .where(RawMessage.source_id == source_id)
        .order_by(RawMessage.created_at.desc())
        .limit(30)
    )).scalars().all()

    return SourceStatsResponse(
        source_id=source.id,
        source_name=source.source_name,
        telegram_id=source.telegram_id,
        type=source.type,
        is_active=source.is_active,
        supplier_id=source.supplier_id,
        last_read_at=source.last_read_at,
        error_count=source.error_count,
        last_error=source.last_error,
        poll_interval_minutes=source.poll_interval_minutes,
        parsing_strategy=source.parsing_strategy,
        messages_total=messages_total,
        messages_24h=messages_24h,
        messages_pending=messages_pending,
        messages_parsed=messages_parsed,
        messages_failed=messages_failed,
        messages_needs_review=messages_needs_review,
        parse_success_rate=parse_success_rate,
        offers_total=offers_total,
        offers_current=offers_current,
        products_covered=products_covered,
        recent_messages=[
            RecentMessage(
                id=m.id,
                message_text=m.message_text[:400],
                message_date=m.message_date,
                parse_status=m.parse_status,
                parse_error=m.parse_error,
            ) for m in recent_rows
        ],
    )


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(data: SourceCreate, db: AsyncSession = Depends(get_db)):
    source = Source(**data.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: int, data: SourceUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=200)
async def delete_source(source_id: int, delete_messages: bool = False, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source_name = source.source_name
    messages_affected = 0
    if delete_messages:
        msgs = (await db.execute(select(RawMessage).where(RawMessage.source_id == source_id))).scalars().all()
        messages_affected = len(msgs)
        for msg in msgs:
            await db.delete(msg)
        await db.flush()
    else:
        await db.execute(update(RawMessage).where(RawMessage.source_id == source_id).values(source_id=None))
        await db.flush()
    await db.delete(source)
    await db.commit()
    return {"deleted": True, "source_id": source_id, "source_name": source_name, "messages_affected": messages_affected}


@router.post("/{source_id}/trigger", status_code=202)
async def trigger_collect(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    from app.tasks.collect import collect_from_source
    task = collect_from_source.delay(source_id)
    return {"task_id": task.id, "source_id": source_id, "status": "queued"}


@router.post("/{source_id}/reset-errors", status_code=200)
async def reset_source_errors(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.error_count = 0
    source.last_error = None
    await db.commit()
    return {"source_id": source_id, "error_count": 0}
