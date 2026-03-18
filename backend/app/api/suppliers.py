"""Suppliers API — also provides sync endpoint to update display_name from Source."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.source import Source
from app.models.supplier import Supplier

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("")
async def list_suppliers(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Supplier).order_by(Supplier.priority))
    return result.scalars().all()


@router.post("/sync-names")
async def sync_supplier_names(session: AsyncSession = Depends(get_session)):
    """
    Sync Supplier.display_name from the linked Source.source_name.
    Call once after renaming sources to fix supplier names everywhere.
    """
    result = await session.execute(
        select(Source).where(Source.supplier_id.isnot(None))
    )
    sources = result.scalars().all()

    updated = 0
    for source in sources:
        await session.execute(
            update(Supplier)
            .where(Supplier.id == source.supplier_id)
            .values(display_name=source.source_name)
        )
        updated += 1

    await session.commit()
    return {"updated": updated, "message": f"Synced {updated} supplier names from sources"}
