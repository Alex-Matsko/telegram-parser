"""Price history API endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.price_list import PriceChartResponse, PriceHistoryResponse
from app.services.price_service import get_price_chart_data, get_price_history

router = APIRouter(prefix="/history", tags=["Price History"])


@router.get("/{product_id}", response_model=PriceHistoryResponse)
async def product_price_history(
    product_id: int,
    days: int = Query(3, ge=1, le=90),
    supplier_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> PriceHistoryResponse:
    """Get price history for a product."""
    return await get_price_history(
        session=session,
        product_id=product_id,
        days=days,
        supplier_id=supplier_id,
    )


@router.get("/{product_id}/chart", response_model=PriceChartResponse)
async def product_price_chart(
    product_id: int,
    days: int = Query(3, ge=1, le=90),
    supplier_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> PriceChartResponse:
    """Get chart-ready price data grouped by supplier."""
    return await get_price_chart_data(
        session=session,
        product_id=product_id,
        days=days,
        supplier_id=supplier_id,
    )
