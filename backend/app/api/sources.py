"""Sources API — manage Telegram data sources."""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
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


@router.get("", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).order_by(Source.id))
    return result.scalars().all()


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
async def update_source(
    source_id: int, data: SourceUpdate, db: AsyncSession = Depends(get_db)
):
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
async def delete_source(
    source_id: int,
    delete_messages: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a source.
    - delete_messages=False (default): raw_messages are kept, source_id set to NULL.
    - delete_messages=True: raw_messages for this source are deleted first.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source_name = source.source_name
    messages_affected = 0

    if delete_messages:
        # Hard delete all raw_messages for this source
        msgs_result = await db.execute(
            select(RawMessage).where(RawMessage.source_id == source_id)
        )
        msgs = msgs_result.scalars().all()
        messages_affected = len(msgs)
        for msg in msgs:
            await db.delete(msg)
        await db.flush()
    else:
        # Nullify source_id so messages are kept but FK is released
        await db.execute(
            update(RawMessage)
            .where(RawMessage.source_id == source_id)
            .values(source_id=None)
        )
        await db.flush()

    await db.delete(source)
    await db.commit()

    return {
        "deleted": True,
        "source_id": source_id,
        "source_name": source_name,
        "messages_affected": messages_affected,
    }


@router.post("/{source_id}/trigger", status_code=202)
async def trigger_collect(source_id: int, db: AsyncSession = Depends(get_db)):
    """Manually trigger collection for a single source."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    from app.tasks.collect import collect_from_source
    task = collect_from_source.delay(source_id)
    return {"task_id": task.id, "source_id": source_id, "status": "queued"}


@router.post("/{source_id}/reset-errors", status_code=200)
async def reset_source_errors(source_id: int, db: AsyncSession = Depends(get_db)):
    """Reset error counter for a source."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.error_count = 0
    source.last_error = None
    await db.commit()
    return {"source_id": source_id, "error_count": 0}
