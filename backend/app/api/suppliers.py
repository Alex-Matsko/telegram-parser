"""Supplier management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierResponse, SupplierUpdate

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    session: AsyncSession = Depends(get_db),
) -> list[SupplierResponse]:
    result = await session.execute(
        select(Supplier).order_by(Supplier.priority.desc(), Supplier.name)
    )
    return result.scalars().all()


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    data: SupplierCreate,
    session: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    supplier = Supplier(
        name=data.name,
        display_name=data.display_name,
        priority=data.priority,
        is_active=data.is_active,
    )
    session.add(supplier)
    await session.flush()
    await session.refresh(supplier)
    return supplier


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    session: AsyncSession = Depends(get_db),
) -> SupplierResponse:
    result = await session.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, key, value)
    await session.flush()
    await session.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: int,
    session: AsyncSession = Depends(get_db),
) -> None:
    result = await session.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    await session.delete(supplier)
