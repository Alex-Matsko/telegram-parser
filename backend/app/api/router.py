"""Main API router that aggregates all endpoint routers."""
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
    """Get summary statistics for the dashboard."""
    return await get_dashboard_stats(session)
