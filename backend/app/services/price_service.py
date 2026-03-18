"""
Business logic for building and querying the consolidated price list.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.offer import Offer
from app.models.price_history import PriceHistory
from app.models.product_catalog import ProductCatalog
from app.models.source import Source
from app.models.supplier import Supplier
from app.schemas.price_list import (
    ChartDataPoint,
    DashboardStats,
    OfferDetail,
    PriceChartResponse,
    PriceChartSeries,
    PriceHistoryPoint,
    PriceHistoryResponse,
    PriceListDetailItem,
    PriceListItem,
    PriceListResponse,
)

logger = logging.getLogger(__name__)


async def get_price_list(
    session: AsyncSession,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    memory: Optional[str] = None,
    color: Optional[str] = None,
    condition: Optional[str] = None,
    supplier: Optional[str] = None,
    currency: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    updated_after: Optional[datetime] = None,
    sort_by: str = "best_price",
    order: str = "asc",
    page: int = 1,
    per_page: int = 50,
) -> PriceListResponse:
    """Build consolidated price list with filters, sorting, and pagination."""

    # Subquery: best price per product from current offers
    best_offer_sq = (
        select(
            Offer.product_id,
            func.min(Offer.price).label("best_price"),
            func.count(Offer.id).label("offer_count"),
            func.max(Offer.updated_at).label("last_updated"),
        )
        .where(Offer.is_current == True)  # noqa: E712
        .group_by(Offer.product_id)
        .subquery("best_offers")
    )

    # Main query: join product catalog with aggregated offers
    query = (
        select(
            ProductCatalog,
            best_offer_sq.c.best_price,
            best_offer_sq.c.offer_count,
            best_offer_sq.c.last_updated,
        )
        .join(best_offer_sq, ProductCatalog.id == best_offer_sq.c.product_id)
    )

    # Apply filters
    if brand:
        query = query.where(ProductCatalog.brand.ilike(f"%{brand}%"))
    if model:
        query = query.where(ProductCatalog.model.ilike(f"%{model}%"))
    if memory:
        query = query.where(ProductCatalog.memory == memory)
    if color:
        query = query.where(ProductCatalog.color.ilike(f"%{color}%"))
    if condition:
        query = query.where(ProductCatalog.condition == condition)
    if price_min is not None:
        query = query.where(best_offer_sq.c.best_price >= price_min)
    if price_max is not None:
        query = query.where(best_offer_sq.c.best_price <= price_max)
    if updated_after:
        query = query.where(best_offer_sq.c.last_updated >= updated_after)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_col = {
        "best_price": best_offer_sq.c.best_price,
        "model": ProductCatalog.model,
        "brand": ProductCatalog.brand,
        "offer_count": best_offer_sq.c.offer_count,
        "last_updated": best_offer_sq.c.last_updated,
    }.get(sort_by, best_offer_sq.c.best_price)

    if order == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(sort_col)

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await session.execute(query)
    rows = result.all()

    # Build response items
    items = []
    for product, best_price, offer_count, last_updated in rows:
        # Get best supplier
        best_supplier_info = await _get_best_supplier(session, product.id, best_price)

        # Get 2nd and 3rd best prices
        second_price, third_price = await _get_runner_up_prices(
            session, product.id, best_price
        )

        # Calculate 3-day price change
        price_change_3d, price_change_pct = await _get_price_change_3d(
            session, product.id, best_price
        )

        items.append(
            PriceListItem(
                product_id=product.id,
                category=product.category,
                brand=product.brand,
                model=product.model,
                memory=product.memory,
                color=product.color,
                condition=product.condition,
                sim_type=product.sim_type,
                normalized_name=product.normalized_name,
                best_price=best_price,
                best_supplier=best_supplier_info[0],
                best_supplier_id=best_supplier_info[1],
                second_price=second_price,
                third_price=third_price,
                offer_count=offer_count,
                price_change_3d=price_change_3d,
                price_change_3d_pct=price_change_pct,
                last_updated=last_updated,
            )
        )

    pages = max(1, (total + per_page - 1) // per_page)

    return PriceListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


async def get_product_detail(
    session: AsyncSession,
    product_id: int,
) -> Optional[PriceListDetailItem]:
    """Get detailed product info with all current offers."""
    # Get product
    result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return None

    # Get all current offers for this product
    offers_result = await session.execute(
        select(Offer, Supplier.display_name)
        .join(Supplier, Offer.supplier_id == Supplier.id)
        .where(
            and_(
                Offer.product_id == product_id,
                Offer.is_current == True,  # noqa: E712
            )
        )
        .order_by(Offer.price)
    )
    offers_rows = offers_result.all()

    offers = [
        OfferDetail(
            offer_id=offer.id,
            supplier_id=offer.supplier_id,
            supplier_name=supplier_name,
            price=offer.price,
            currency=offer.currency,
            availability=offer.availability,
            confidence=offer.detected_confidence,
            is_current=offer.is_current,
            updated_at=offer.updated_at,
        )
        for offer, supplier_name in offers_rows
    ]

    return PriceListDetailItem(
        product_id=product.id,
        normalized_name=product.normalized_name,
        category=product.category,
        brand=product.brand,
        model=product.model,
        memory=product.memory,
        color=product.color,
        condition=product.condition,
        offers=offers,
    )


async def get_price_history(
    session: AsyncSession,
    product_id: int,
    days: int = 3,
    supplier_id: Optional[int] = None,
) -> PriceHistoryResponse:
    """Get price history for a product."""
    # Get product name
    product_result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.id == product_id)
    )
    product = product_result.scalar_one_or_none()
    product_name = product.normalized_name if product else f"Product #{product_id}"

    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(PriceHistory, Supplier.display_name)
        .join(Supplier, PriceHistory.supplier_id == Supplier.id)
        .where(
            and_(
                PriceHistory.product_id == product_id,
                PriceHistory.captured_at >= since,
            )
        )
    )
    if supplier_id:
        query = query.where(PriceHistory.supplier_id == supplier_id)

    query = query.order_by(PriceHistory.captured_at)

    result = await session.execute(query)
    rows = result.all()

    history = [
        PriceHistoryPoint(
            price=ph.price,
            supplier=supplier_name,
            supplier_id=ph.supplier_id,
            captured_at=ph.captured_at,
        )
        for ph, supplier_name in rows
    ]

    return PriceHistoryResponse(
        product_id=product_id,
        product_name=product_name,
        history=history,
    )


async def get_price_chart_data(
    session: AsyncSession,
    product_id: int,
    days: int = 3,
    supplier_id: Optional[int] = None,
) -> PriceChartResponse:
    """Get chart-ready price data grouped by supplier."""
    product_result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.id == product_id)
    )
    product = product_result.scalar_one_or_none()
    product_name = product.normalized_name if product else f"Product #{product_id}"

    since = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(PriceHistory, Supplier.display_name)
        .join(Supplier, PriceHistory.supplier_id == Supplier.id)
        .where(
            and_(
                PriceHistory.product_id == product_id,
                PriceHistory.captured_at >= since,
            )
        )
    )
    if supplier_id:
        query = query.where(PriceHistory.supplier_id == supplier_id)

    query = query.order_by(PriceHistory.supplier_id, PriceHistory.captured_at)

    result = await session.execute(query)
    rows = result.all()

    # Group by supplier
    series_map: dict[int, PriceChartSeries] = {}
    for ph, supplier_name in rows:
        if ph.supplier_id not in series_map:
            series_map[ph.supplier_id] = PriceChartSeries(
                supplier=supplier_name,
                supplier_id=ph.supplier_id,
                data=[],
            )
        series_map[ph.supplier_id].data.append(
            ChartDataPoint(timestamp=ph.captured_at, price=ph.price)
        )

    return PriceChartResponse(
        product_id=product_id,
        product_name=product_name,
        series=list(series_map.values()),
    )


async def get_dashboard_stats(session: AsyncSession) -> DashboardStats:
    """Get summary statistics for the dashboard."""
    from app.models.raw_message import RawMessage

    total_products = (await session.execute(
        select(func.count(ProductCatalog.id))
    )).scalar() or 0

    total_sources = (await session.execute(
        select(func.count(Source.id))
    )).scalar() or 0

    active_sources = (await session.execute(
        select(func.count(Source.id)).where(Source.is_active == True)  # noqa: E712
    )).scalar() or 0

    total_suppliers = (await session.execute(
        select(func.count(Supplier.id))
    )).scalar() or 0

    total_offers = (await session.execute(
        select(func.count(Offer.id)).where(Offer.is_current == True)  # noqa: E712
    )).scalar() or 0

    unresolved_count = (await session.execute(
        select(func.count(RawMessage.id)).where(RawMessage.parse_status == "needs_review")
    )).scalar() or 0

    failed_count = (await session.execute(
        select(func.count(RawMessage.id)).where(RawMessage.parse_status == "failed")
    )).scalar() or 0

    last_collection = (await session.execute(
        select(func.max(Source.last_read_at))
    )).scalar()

    error_source_count = (await session.execute(
        select(func.count(Source.id)).where(Source.error_count > 0)
    )).scalar() or 0

    return DashboardStats(
        total_products=total_products,
        total_sources=total_sources,
        active_sources=active_sources,
        total_suppliers=total_suppliers,
        total_offers=total_offers,
        unresolved_count=unresolved_count,
        failed_count=failed_count,
        last_collection_at=last_collection,
        error_source_count=error_source_count,
    )


# ---------- Internal helpers ----------


async def _get_best_supplier(
    session: AsyncSession,
    product_id: int,
    best_price: Decimal,
) -> tuple[str, int]:
    """Get the supplier with the best price for a product."""
    result = await session.execute(
        select(Supplier.display_name, Supplier.id)
        .join(Offer, Offer.supplier_id == Supplier.id)
        .where(
            and_(
                Offer.product_id == product_id,
                Offer.price == best_price,
                Offer.is_current == True,  # noqa: E712
            )
        )
        .order_by(Supplier.priority.desc())
        .limit(1)
    )
    row = result.first()
    if row:
        return row[0], row[1]
    return "Unknown", 0


async def _get_runner_up_prices(
    session: AsyncSession,
    product_id: int,
    best_price: Decimal,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Get second and third best unique prices for a product."""
    result = await session.execute(
        select(Offer.price)
        .where(
            and_(
                Offer.product_id == product_id,
                Offer.is_current == True,  # noqa: E712
                Offer.price > best_price,
            )
        )
        .distinct()
        .order_by(Offer.price)
        .limit(2)
    )
    prices = [row[0] for row in result.all()]
    second = prices[0] if len(prices) > 0 else None
    third = prices[1] if len(prices) > 1 else None
    return second, third


async def _get_price_change_3d(
    session: AsyncSession,
    product_id: int,
    current_price: Decimal,
) -> tuple[Optional[Decimal], Optional[float]]:
    """Calculate 3-day price change for a product."""
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)

    # Get the earliest price in the last 3 days
    result = await session.execute(
        select(func.min(PriceHistory.price))
        .where(
            and_(
                PriceHistory.product_id == product_id,
                PriceHistory.captured_at >= three_days_ago,
            )
        )
    )
    old_min_price = result.scalar()

    if old_min_price is None or old_min_price == 0:
        return None, None

    change = current_price - old_min_price
    pct = float(change / old_min_price * 100) if old_min_price else None

    return change, pct
