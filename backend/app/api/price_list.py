"""Price list API endpoints."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.price_list import PriceListDetailItem, PriceListResponse
from app.services.price_service import get_price_list, get_product_detail

router = APIRouter(prefix="/price-list", tags=["Price List"])


@router.get("", response_model=PriceListResponse)
async def list_prices(
    brand: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    memory: Optional[str] = Query(None),
    color: Optional[str] = Query(None),
    condition: Optional[str] = Query(None),
    supplier: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    price_min: Optional[float] = Query(None, ge=0),
    price_max: Optional[float] = Query(None, ge=0),
    updated_after: Optional[datetime] = Query(None),
    sort_by: str = Query("best_price", pattern="^(best_price|model|brand|offer_count|last_updated)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> PriceListResponse:
    """Get consolidated price list with filtering, sorting, and pagination."""
    return await get_price_list(
        session=session,
        brand=brand,
        model=model,
        memory=memory,
        color=color,
        condition=condition,
        supplier=supplier,
        currency=currency,
        price_min=price_min,
        price_max=price_max,
        updated_after=updated_after,
        sort_by=sort_by,
        order=order,
        page=page,
        per_page=per_page,
    )


@router.get("/{product_id}", response_model=PriceListDetailItem)
async def get_product_prices(
    product_id: int,
    session: AsyncSession = Depends(get_session),
) -> PriceListDetailItem:
    """Get detailed view for a product with all offers."""
    detail = await get_product_detail(session, product_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Product not found")
    return detail
