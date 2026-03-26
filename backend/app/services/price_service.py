"""
Business logic for building and querying the consolidated price list.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.offer import Offer
from app.models.price_history import PriceHistory
from app.models.product_catalog import ProductCatalog
from app.models.raw_message import RawMessage
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
    supplier_id: Optional[int] = None,
    currency: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    updated_after: Optional[datetime] = None,
    sort_by: str = "best_price",
    order: str = "asc",
    page: int = 1,
    per_page: int = 50,
) -> PriceListResponse:
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

    query = (
        select(
            ProductCatalog,
            best_offer_sq.c.best_price,
            best_offer_sq.c.offer_count,
            best_offer_sq.c.last_updated,
        )
        .join(best_offer_sq, ProductCatalog.id == best_offer_sq.c.product_id)
    )

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
    if supplier_id is not None:
        supplier_sq = (
            select(Offer.product_id)
            .where(and_(Offer.supplier_id == supplier_id, Offer.is_current == True))  # noqa: E712
            .subquery()
        )
        query = query.where(ProductCatalog.id.in_(select(supplier_sq)))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    sort_col = {
        "best_price": best_offer_sq.c.best_price,
        "model": ProductCatalog.model,
        "brand": ProductCatalog.brand,
        "offer_count": best_offer_sq.c.offer_count,
        "last_updated": best_offer_sq.c.last_updated,
    }.get(sort_by, best_offer_sq.c.best_price)

    query = query.order_by(desc(sort_col) if order == "desc" else sort_col)
    query = query.offset((page - 1) * per_page).limit(per_page)

    rows = (await session.execute(query)).all()

    product_ids = [r[0].id for r in rows]
    runner_up_map = await _batch_runner_up_prices(session, product_ids)
    price_change_map = await _batch_price_change_3d(session, product_ids)
    best_supplier_map = await _batch_best_suppliers(session, product_ids)

    items = []
    for product, best_price, offer_count, last_updated in rows:
        second_price, third_price = runner_up_map.get(product.id, (None, None))
        price_change_3d, price_change_pct = price_change_map.get(product.id, (None, None))
        best_supplier_name, best_supplier_id, second_supplier_name, third_supplier_name = best_supplier_map.get(
            product.id, ("Unknown", 0, None, None)
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
                best_supplier=best_supplier_name,
                best_supplier_id=best_supplier_id,
                second_price=second_price,
                second_supplier=second_supplier_name,
                third_price=third_price,
                third_supplier=third_supplier_name,
                offer_count=offer_count,
                price_change_3d=price_change_3d,
                price_change_3d_pct=price_change_pct,
                last_updated=last_updated,
            )
        )

    return PriceListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


async def get_product_detail(
    session: AsyncSession,
    product_id: int,
) -> Optional[PriceListDetailItem]:
    result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return None

    offers_result = await session.execute(
        select(Offer, Supplier.display_name, RawMessage, Source)
        .join(Supplier, Offer.supplier_id == Supplier.id)
        .outerjoin(RawMessage, Offer.raw_message_id == RawMessage.id)
        .outerjoin(Source, RawMessage.source_id == Source.id)
        .where(and_(Offer.product_id == product_id, Offer.is_current == True))  # noqa: E712
        .order_by(Offer.price)
    )

    offers = []
    for offer, display_name, raw_msg, source in offers_result.all():
        offers.append(OfferDetail(
            offer_id=offer.id,
            supplier_id=offer.supplier_id,
            supplier_name=display_name,
            price=offer.price,
            currency=offer.currency,
            availability=offer.availability,
            confidence=offer.detected_confidence,
            is_current=offer.is_current,
            updated_at=offer.updated_at,
            raw_line=offer.raw_line,
            source_name=source.source_name if source else None,
            channel_url=source.channel_url if source else None,
            message_date=raw_msg.message_date if raw_msg else None,
            raw_message_id=raw_msg.id if raw_msg else None,
        ))

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
    product_result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.id == product_id)
    )
    product = product_result.scalar_one_or_none()
    product_name = product.normalized_name if product else f"Product #{product_id}"

    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        select(PriceHistory, Supplier.display_name)
        .join(Supplier, PriceHistory.supplier_id == Supplier.id)
        .where(and_(PriceHistory.product_id == product_id, PriceHistory.captured_at >= since))
    )
    if supplier_id:
        query = query.where(PriceHistory.supplier_id == supplier_id)
    query = query.order_by(PriceHistory.captured_at)

    rows = (await session.execute(query)).all()
    history = [
        PriceHistoryPoint(
            price=ph.price,
            supplier=display_name,
            supplier_id=ph.supplier_id,
            captured_at=ph.captured_at,
        )
        for ph, display_name in rows
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
    product_result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.id == product_id)
    )
    product = product_result.scalar_one_or_none()
    product_name = product.normalized_name if product else f"Product #{product_id}"

    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        select(PriceHistory, Supplier.display_name)
        .join(Supplier, PriceHistory.supplier_id == Supplier.id)
        .where(and_(PriceHistory.product_id == product_id, PriceHistory.captured_at >= since))
    )
    if supplier_id:
        query = query.where(PriceHistory.supplier_id == supplier_id)
    query = query.order_by(PriceHistory.supplier_id, PriceHistory.captured_at)

    rows = (await session.execute(query)).all()
    series_map: dict[int, PriceChartSeries] = {}
    for ph, display_name in rows:
        if ph.supplier_id not in series_map:
            series_map[ph.supplier_id] = PriceChartSeries(
                supplier=display_name, supplier_id=ph.supplier_id, data=[]
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
    total_products = (await session.execute(select(func.count(ProductCatalog.id)))).scalar() or 0
    total_sources = (await session.execute(select(func.count(Source.id)))).scalar() or 0
    active_sources = (await session.execute(
        select(func.count(Source.id)).where(Source.is_active == True)  # noqa: E712
    )).scalar() or 0
    total_suppliers = (await session.execute(select(func.count(Supplier.id)))).scalar() or 0
    total_offers = (await session.execute(
        select(func.count(Offer.id)).where(Offer.is_current == True)  # noqa: E712
    )).scalar() or 0
    unresolved_count = (await session.execute(
        select(func.count(RawMessage.id)).where(RawMessage.parse_status == "needs_review")
    )).scalar() or 0
    failed_count = (await session.execute(
        select(func.count(RawMessage.id)).where(RawMessage.parse_status == "failed")
    )).scalar() or 0
    last_collection = (await session.execute(select(func.max(Source.last_read_at)))).scalar()
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


# ---------- Batch helpers ----------

async def _batch_best_suppliers(
    session: AsyncSession,
    product_ids: list[int],
) -> dict[int, tuple[str, int, Optional[str], Optional[str]]]:
    if not product_ids:
        return {}

    result = await session.execute(
        select(Offer.product_id, Offer.price, Supplier.id, Supplier.display_name)
        .join(Supplier, Offer.supplier_id == Supplier.id)
        .where(and_(Offer.is_current == True, Offer.product_id.in_(product_ids)))  # noqa: E712
        .order_by(Offer.product_id, Offer.price)
    )
    rows = result.all()

    from collections import defaultdict
    product_offers: dict[int, list[tuple]] = defaultdict(list)
    for product_id, price, supplier_id, display_name in rows:
        product_offers[product_id].append((price, supplier_id, display_name))

    out: dict[int, tuple[str, int, Optional[str], Optional[str]]] = {}
    for product_id, offers in product_offers.items():
        seen: dict[int, tuple] = {}
        for price, supplier_id, display_name in offers:
            if supplier_id not in seen:
                seen[supplier_id] = (price, supplier_id, display_name)
        sorted_offers = sorted(seen.values(), key=lambda x: x[0])

        best = sorted_offers[0] if len(sorted_offers) > 0 else None
        second = sorted_offers[1] if len(sorted_offers) > 1 else None
        third = sorted_offers[2] if len(sorted_offers) > 2 else None

        out[product_id] = (
            best[2] if best else "Unknown",
            best[1] if best else 0,
            second[2] if second else None,
            third[2] if third else None,
        )
    return out


async def _batch_runner_up_prices(
    session: AsyncSession,
    product_ids: list[int],
) -> dict[int, tuple[Optional[Decimal], Optional[Decimal]]]:
    if not product_ids:
        return {}

    result = await session.execute(
        select(Offer.product_id, Offer.price)
        .where(and_(Offer.is_current == True, Offer.product_id.in_(product_ids)))  # noqa: E712
        .order_by(Offer.product_id, Offer.price)
    )
    rows = result.all()

    from collections import defaultdict
    prices_map: dict[int, list[Decimal]] = defaultdict(list)
    for product_id, price in rows:
        prices_map[product_id].append(price)

    out = {}
    for product_id, prices in prices_map.items():
        unique_prices = sorted(set(prices))
        second = unique_prices[1] if len(unique_prices) > 1 else None
        third = unique_prices[2] if len(unique_prices) > 2 else None
        out[product_id] = (second, third)
    return out


async def _batch_price_change_3d(
    session: AsyncSession,
    product_ids: list[int],
) -> dict[int, tuple[Optional[Decimal], Optional[float]]]:
    if not product_ids:
        return {}

    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)

    oldest_sq = (
        select(
            PriceHistory.product_id,
            func.min(PriceHistory.captured_at).label("oldest_at"),
        )
        .where(and_(
            PriceHistory.product_id.in_(product_ids),
            PriceHistory.captured_at >= three_days_ago,
        ))
        .group_by(PriceHistory.product_id)
        .subquery()
    )

    result = await session.execute(
        select(PriceHistory.product_id, PriceHistory.price)
        .join(oldest_sq, and_(
            PriceHistory.product_id == oldest_sq.c.product_id,
            PriceHistory.captured_at == oldest_sq.c.oldest_at,
        ))
    )
    oldest_prices = {row[0]: row[1] for row in result.all()}

    current_sq = (
        select(Offer.product_id, func.min(Offer.price).label("best_price"))
        .where(and_(Offer.is_current == True, Offer.product_id.in_(product_ids)))  # noqa: E712
        .group_by(Offer.product_id)
    )
    current_prices = {row[0]: row[1] for row in (await session.execute(current_sq)).all()}

    out = {}
    for product_id in product_ids:
        old = oldest_prices.get(product_id)
        current = current_prices.get(product_id)
        if old is None or current is None or old == 0:
            out[product_id] = (None, None)
            continue
        change = current - old
        pct = float(change / old * 100)
        out[product_id] = (change, pct)

    return out
