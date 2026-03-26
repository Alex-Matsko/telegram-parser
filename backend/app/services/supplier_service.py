"""
Supplier auto-provisioning service.

Rule: 1 Telegram channel = 1 Supplier.
If a Source has no supplier_id, call get_or_create_supplier_for_source()
to automatically create a Supplier (name derived from source_name) and
link it back to the Source.
"""
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source
from app.models.supplier import Supplier

logger = logging.getLogger(__name__)


def _supplier_name(source_name: str) -> str:
    """Derive a stable, unique supplier name from a source name."""
    return source_name.strip()


async def get_or_create_supplier_for_source(
    source: Source,
    session: AsyncSession,
) -> int:
    """
    Return the supplier_id for *source*.
    If the source already has one, return it directly.
    Otherwise create a Supplier whose name matches source.source_name,
    then persist supplier_id back to the Source row.
    """
    if source.supplier_id:
        return source.supplier_id

    name = _supplier_name(source.source_name)

    # Try to find existing supplier with this name
    existing = (
        await session.execute(select(Supplier).where(Supplier.name == name))
    ).scalar_one_or_none()

    if existing:
        supplier_id = existing.id
        logger.info(
            f"[auto-supplier] Linked existing supplier '{name}' "
            f"(id={supplier_id}) to source '{source.source_name}' (id={source.id})"
        )
    else:
        # INSERT ... ON CONFLICT DO NOTHING to handle race conditions
        stmt = (
            pg_insert(Supplier)
            .values(name=name, display_name=name, priority=0, is_active=True)
            .on_conflict_do_nothing(index_elements=["name"])
            .returning(Supplier.id)
        )
        result = await session.execute(stmt)
        row = result.fetchone()

        if row:
            supplier_id = row[0]
        else:
            # Another process inserted concurrently
            supplier_id = (
                await session.execute(select(Supplier.id).where(Supplier.name == name))
            ).scalar_one()

        logger.info(
            f"[auto-supplier] Created supplier '{name}' "
            f"(id={supplier_id}) for source '{source.source_name}' (id={source.id})"
        )

    # Persist link back to source
    source.supplier_id = supplier_id
    await session.flush()
    return supplier_id
