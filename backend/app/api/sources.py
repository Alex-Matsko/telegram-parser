"""Source management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.source import Source
from app.models.supplier import Supplier
from app.schemas.source import (
    SourceCreate,
    SourceLogEntry,
    SourceResponse,
    SourceUpdate,
)

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("", response_model=list[SourceResponse])
async def list_sources(
    session: AsyncSession = Depends(get_session),
) -> list[SourceResponse]:
    """List all sources with status."""
    result = await session.execute(
        select(Source).order_by(Source.created_at.desc())
    )
    sources = result.scalars().all()
    responses = []
    for s in sources:
        resp = SourceResponse.model_validate(s)
        if s.supplier:
            resp.supplier_name = s.supplier.display_name
        responses.append(resp)
    return responses


@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(
    data: SourceCreate,
    session: AsyncSession = Depends(get_session),
) -> SourceResponse:
    """Add a new source."""
    source = Source(
        type=data.type,
        telegram_id=data.telegram_id,
        source_name=data.source_name,
        supplier_id=data.supplier_id,
        is_active=data.is_active,
        poll_interval_minutes=data.poll_interval_minutes,
        parsing_strategy=data.parsing_strategy,
        bot_scenario_id=data.bot_scenario_id,
    )
    session.add(source)
    await session.flush()
    await session.refresh(source)
    return SourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    data: SourceUpdate,
    session: AsyncSession = Depends(get_session),
) -> SourceResponse:
    """Update an existing source."""
    result = await session.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(source, key, value)

    await session.flush()
    await session.refresh(source)
    return SourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=204)
async def deactivate_source(
    source_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Deactivate a source (soft delete)."""
    result = await session.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.is_active = False
    await session.flush()


@router.get("/{source_id}/logs", response_model=list[SourceLogEntry])
async def get_source_logs(
    source_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[SourceLogEntry]:
    """Get error logs for a source."""
    result = await session.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    logs = []
    if source.last_error:
        logs.append(
            SourceLogEntry(
                timestamp=source.updated_at,
                error=source.last_error,
                error_count=source.error_count,
            )
        )
    return logs
