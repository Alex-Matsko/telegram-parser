"""
Product catalog operations: CRUD and matching logic.
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_catalog import ProductCatalog
from app.schemas.product import ProductCreate, ProductResponse

logger = logging.getLogger(__name__)


async def get_products(
    session: AsyncSession,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[ProductResponse], int]:
    """Get paginated product catalog with optional filters."""
    query = select(ProductCatalog)

    if category:
        query = query.where(ProductCatalog.category == category)
    if brand:
        query = query.where(ProductCatalog.brand.ilike(f"%{brand}%"))
    if search:
        query = query.where(ProductCatalog.normalized_name.ilike(f"%{search}%"))

    # Count
    from sqlalchemy import func
    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(ProductCatalog.normalized_name).offset(offset).limit(per_page)

    result = await session.execute(query)
    products = result.scalars().all()

    return [ProductResponse.model_validate(p) for p in products], total


async def get_product_by_id(
    session: AsyncSession,
    product_id: int,
) -> Optional[ProductResponse]:
    """Get a single product by ID."""
    result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.id == product_id)
    )
    product = result.scalar_one_or_none()
    if product:
        return ProductResponse.model_validate(product)
    return None


async def create_product(
    session: AsyncSession,
    data: ProductCreate,
) -> ProductResponse:
    """Create a new product catalog entry."""
    product = ProductCatalog(
        category=data.category,
        brand=data.brand,
        line=data.line,
        model=data.model,
        generation=data.generation,
        memory=data.memory,
        color=data.color,
        sim_type=data.sim_type,
        region=data.region,
        condition=data.condition,
        normalized_name=data.normalized_name,
        sku_key=data.sku_key,
    )
    session.add(product)
    await session.flush()
    return ProductResponse.model_validate(product)


async def search_products_for_matching(
    session: AsyncSession,
    model_query: str,
    memory: Optional[str] = None,
) -> list[ProductResponse]:
    """Search products for manual matching (used by unresolved messages UI)."""
    query = select(ProductCatalog).where(
        ProductCatalog.normalized_name.ilike(f"%{model_query}%")
    )
    if memory:
        query = query.where(ProductCatalog.memory == memory)

    query = query.limit(20)
    result = await session.execute(query)
    products = result.scalars().all()
    return [ProductResponse.model_validate(p) for p in products]
