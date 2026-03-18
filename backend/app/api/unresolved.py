"""Unresolved messages management API endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.offer import Offer
from app.models.price_history import PriceHistory
from app.models.raw_message import RawMessage
from app.models.source import Source
from app.schemas.raw_message import (
    ManualResolveRequest,
    RawMessageResponse,
    UnresolvedListResponse,
)

router = APIRouter(prefix="/unresolved", tags=["Unresolved Messages"])


@router.get("", response_model=UnresolvedListResponse)
async def list_unresolved(
    status: str = Query("needs_review", pattern="^(needs_review|failed|pending)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> UnresolvedListResponse:
    """List unresolved/failed messages."""
    query = (
        select(RawMessage)
        .where(RawMessage.parse_status == status)
        .order_by(RawMessage.created_at.desc())
    )

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await session.execute(query)
    messages = result.scalars().all()

    items = []
    for msg in messages:
        resp = RawMessageResponse.model_validate(msg)
        if msg.source:
            resp.source_name = msg.source.source_name
        items.append(resp)

    pages = max(1, (total + per_page - 1) // per_page)

    return UnresolvedListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post("/{message_id}/resolve", response_model=RawMessageResponse)
async def resolve_message(
    message_id: int,
    data: ManualResolveRequest,
    session: AsyncSession = Depends(get_session),
) -> RawMessageResponse:
    """Manually resolve an unresolved message by providing product and price."""
    result = await session.execute(
        select(RawMessage).where(RawMessage.id == message_id)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Create/update offer
    offer = Offer(
        supplier_id=data.supplier_id,
        product_id=data.product_id,
        raw_message_id=message.id,
        price=data.price,
        currency=data.currency,
        detected_confidence=1.0,
        is_current=True,
    )
    session.add(offer)
    await session.flush()

    # Record price history
    history = PriceHistory(
        offer_id=offer.id,
        supplier_id=data.supplier_id,
        product_id=data.product_id,
        price=data.price,
        currency=data.currency,
    )
    session.add(history)

    # Mark message as resolved
    message.is_processed = True
    message.parse_status = "parsed"
    message.parse_error = None
    await session.flush()
    await session.refresh(message)

    resp = RawMessageResponse.model_validate(message)
    if message.source:
        resp.source_name = message.source.source_name
    return resp
