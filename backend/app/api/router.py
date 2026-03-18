"""Main API router — aggregates all endpoint routers."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.bot_scenarios import router as bot_scenarios_router
from app.api.history import router as history_router
from app.api.price_list import router as price_list_router
from app.api.sources import router as sources_router
from app.api.suppliers import router as suppliers_router
from app.api.unresolved import router as unresolved_router
from app.database import get_session
from app.schemas.price_list import DashboardStats
from app.services.price_service import get_dashboard_stats

api_router = APIRouter(prefix="/api")

api_router.include_router(price_list_router)
api_router.include_router(history_router)
api_router.include_router(sources_router)
api_router.include_router(suppliers_router)
api_router.include_router(unresolved_router)
api_router.include_router(bot_scenarios_router)


@api_router.get("/stats", response_model=DashboardStats, tags=["Dashboard"])
async def dashboard_stats(
    session: AsyncSession = Depends(get_session),
) -> DashboardStats:
    return await get_dashboard_stats(session)


@api_router.get("/filters", tags=["Dashboard"])
async def get_filters(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Return all distinct filter values for the frontend dropdowns.
    Frontend calls GET /api/filters — was returning 404 before.
    """
    from sqlalchemy import select, distinct
    from app.models.product_catalog import ProductCatalog
    from app.models.supplier import Supplier

    brands = (await session.execute(
        select(distinct(ProductCatalog.brand)).where(ProductCatalog.brand.isnot(None))
    )).scalars().all()

    models = (await session.execute(
        select(distinct(ProductCatalog.model)).where(ProductCatalog.model.isnot(None))
    )).scalars().all()

    memories = (await session.execute(
        select(distinct(ProductCatalog.memory)).where(ProductCatalog.memory.isnot(None))
    )).scalars().all()

    colors = (await session.execute(
        select(distinct(ProductCatalog.color)).where(ProductCatalog.color.isnot(None))
    )).scalars().all()

    conditions = (await session.execute(
        select(distinct(ProductCatalog.condition)).where(ProductCatalog.condition.isnot(None))
    )).scalars().all()

    suppliers = (await session.execute(
        select(Supplier.id, Supplier.display_name).where(Supplier.is_active == True)  # noqa: E712
    )).all()

    return {
        "brands": sorted([b for b in brands if b]),
        "models": sorted([m for m in models if m]),
        "memories": sorted([m for m in memories if m]),
        "colors": sorted([c for c in colors if c]),
        "conditions": sorted([c for c in conditions if c]),
        "suppliers": [{"id": s.id, "name": s.display_name} for s in suppliers],
        "currencies": ["RUB", "USD", "EUR"],
    }
