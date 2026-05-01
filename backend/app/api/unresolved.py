"""Unresolved / failed messages — Review Queue (Push 5)."""
from __future__ import annotations

from typing import Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.offer import Offer
from app.models.product_catalog import ProductCatalog
from app.models.raw_message import RawMessage
from app.models.source import Source
from app.models.supplier import Supplier

router = APIRouter(prefix="/unresolved", tags=["Unresolved"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UnresolvedMessage(BaseModel):
    id: int
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    telegram_message_id: int
    message_text: str
    message_date: datetime
    sender_name: Optional[str] = None
    parse_status: str
    parse_error: Optional[str] = None
    # Best-effort hint from previous parse attempt
    suggested_product: Optional[str] = None
    suggested_product_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnresolvedListResponse(BaseModel):
    items: list[UnresolvedMessage]
    total: int
    page: int
    per_page: int
    pages: int


class BulkIdsRequest(BaseModel):
    ids: list[int]


class ManualResolveRequest(BaseModel):
    """Full resolve: create an Offer record from the manual input."""
    product_id: int
    price: float
    currency: str = "RUB"
    supplier_id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _enrich_messages(
    messages: list[RawMessage],
    db: AsyncSession,
) -> list[UnresolvedMessage]:
    """Attach source names and best-guess product hints."""
    source_ids = list({m.source_id for m in messages if m.source_id})
    sources_map: dict[int, str] = {}
    if source_ids:
        src_result = await db.execute(
            select(Source).where(Source.id.in_(source_ids))
        )
        sources_map = {s.id: s.source_name for s in src_result.scalars().all()}

    items = []
    for m in messages:
        # Try to find a hinted product from an existing offer linked to this message
        suggested_product: Optional[str] = None
        suggested_product_id: Optional[int] = None

        offer_result = await db.execute(
            select(Offer)
            .where(Offer.raw_message_id == m.id)
            .limit(1)
        )
        hint_offer = offer_result.scalar_one_or_none()
        if hint_offer:
            prod_result = await db.execute(
                select(ProductCatalog).where(ProductCatalog.id == hint_offer.product_id)
            )
            prod = prod_result.scalar_one_or_none()
            if prod:
                suggested_product = prod.normalized_name
                suggested_product_id = prod.id

        items.append(
            UnresolvedMessage(
                id=m.id,
                source_id=m.source_id,
                source_name=sources_map.get(m.source_id) if m.source_id else None,
                telegram_message_id=m.telegram_message_id,
                message_text=m.message_text,
                message_date=m.message_date,
                sender_name=m.sender_name,
                parse_status=m.parse_status,
                parse_error=m.parse_error,
                suggested_product=suggested_product,
                suggested_product_id=suggested_product_id,
                created_at=m.created_at,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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
    if status and status in ("needs_review", "failed"):
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
    items = await _enrich_messages(list(messages), db)

    return UnresolvedListResponse(
        items=items,
        total=count,
        page=page,
        per_page=per_page,
        pages=max(1, (count + per_page - 1) // per_page),
    )


@router.post("/bulk-reparse", status_code=202)
async def bulk_reparse(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset selected messages back to 'pending' so Celery will reparse them."""
    result = await db.execute(
        select(RawMessage).where(RawMessage.id.in_(body.ids))
    )
    messages = result.scalars().all()
    for msg in messages:
        msg.parse_status = "pending"
        msg.is_processed = False
        msg.parse_error = None
    await db.commit()
    return {"queued": len(messages), "message_ids": body.ids}


@router.post("/bulk-resolve", status_code=200)
async def bulk_resolve(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Mark selected messages as resolved (ignore / skip) without creating offers."""
    result = await db.execute(
        select(RawMessage).where(RawMessage.id.in_(body.ids))
    )
    messages = result.scalars().all()
    for msg in messages:
        msg.parse_status = "parsed"
        msg.is_processed = True
    await db.commit()
    return {"resolved": len(messages)}


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
    """
    Manually resolve a message: creates a real Offer record from the
    operator-provided product_id / price / currency / supplier_id.
    Marks the raw_message as parsed.
    """
    # Validate message
    msg_result = await db.execute(
        select(RawMessage).where(RawMessage.id == message_id)
    )
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Validate product
    prod_result = await db.execute(
        select(ProductCatalog).where(ProductCatalog.id == body.product_id)
    )
    if not prod_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Product not found in catalog")

    # Validate supplier
    sup_result = await db.execute(
        select(Supplier).where(Supplier.id == body.supplier_id)
    )
    if not sup_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Mark existing offers for this product+supplier as not current
    existing = await db.execute(
        select(Offer).where(
            Offer.product_id == body.product_id,
            Offer.supplier_id == body.supplier_id,
            Offer.is_current == True,  # noqa: E712
        )
    )
    for old_offer in existing.scalars().all():
        old_offer.is_current = False

    # Create new Offer
    new_offer = Offer(
        supplier_id=body.supplier_id,
        product_id=body.product_id,
        raw_message_id=message_id,
        raw_line=msg.message_text[:500],
        price=Decimal(str(body.price)),
        currency=body.currency,
        detected_confidence=1.0,  # manual = full confidence
        is_current=True,
    )
    db.add(new_offer)

    # Mark message resolved
    msg.parse_status = "parsed"
    msg.is_processed = True
    msg.parse_error = None

    await db.commit()
    await db.refresh(new_offer)

    return {
        "id": message_id,
        "parse_status": "parsed",
        "offer_id": new_offer.id,
        "product_id": body.product_id,
        "price": body.price,
        "currency": body.currency,
    }
