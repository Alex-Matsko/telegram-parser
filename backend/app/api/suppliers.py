"""Supplier management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierResponse, SupplierUpdate

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    session: AsyncSession = Depends(get_session),
) -> list[SupplierResponse]:
    """List all suppliers."""
    result = await session.execute(
        select(Supplier).order_by(Supplier.priority.desc(), Supplier.name)
    )
    suppliers = result.scalars().all()
    return [SupplierResponse.model_validate(s) for s in suppliers]


@router.post("", response_model=SupplierResponse, status_code=201)
async def create_supplier(
    data: SupplierCreate,
    session: AsyncSession = Depends(get_session),
) -> SupplierResponse:
    """Add a new supplier."""
    supplier = Supplier(
        name=data.name,
        display_name=data.display_name,
        priority=data.priority,
        is_active=data.is_active,
    )
    session.add(supplier)
    await session.flush()
    await session.refresh(supplier)
    return SupplierResponse.model_validate(supplier)


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    session: AsyncSession = Depends(get_session),
) -> SupplierResponse:
    """Update an existing supplier."""
    result = await session.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(supplier, key, value)

    await session.flush()
    await session.refresh(supplier)
    return SupplierResponse.model_validate(supplier)
