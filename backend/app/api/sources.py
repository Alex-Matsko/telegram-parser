"""Sources API — manage Telegram data sources."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.source import Source

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreate(BaseModel):
    source_name: str
    type: str  # channel / group / bot
    telegram_id: str
    supplier_id: Optional[int] = None
    is_active: bool = True
    poll_interval: int = 900
    parsing_strategy: str = "auto"
    bot_scenario_id: Optional[int] = None


class SourceUpdate(BaseModel):
    source_name: Optional[str] = None
    type: Optional[str] = None
    telegram_id: Optional[str] = None
    supplier_id: Optional[int] = None
    is_active: Optional[bool] = None
    poll_interval: Optional[int] = None
    parsing_strategy: Optional[str] = None
    bot_scenario_id: Optional[int] = None


class SourceResponse(BaseModel):
    id: int
    source_name: str
    type: str
    telegram_id: str
    supplier_id: Optional[int]
    is_active: bool
    poll_interval: int
    parsing_strategy: str
    bot_scenario_id: Optional[int]
    last_message_id: Optional[int]
    last_read_at: Optional[str]
    error_count: Optional[int]
    last_error: Optional[str]

    class Config:
        from_attributes = True


@router.get("", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all configured Telegram sources."""
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
    """Create a new Telegram source."""
    source = Source(**data.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int, data: SourceUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a source — including linking a supplier_id."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()


@router.post("/{source_id}/trigger", status_code=202)
async def trigger_collect(source_id: int, db: AsyncSession = Depends(get_db)):
    """
    Manually trigger collection for a single source.
    Useful for testing without waiting for the scheduler.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    from app.tasks.collect import collect_from_source
    task = collect_from_source.delay(source_id)
    return {"task_id": task.id, "source_id": source_id, "status": "queued"}
