from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SupplierBase(BaseModel):
    name: str
    display_name: str
    priority: int = 0
    is_active: bool = True


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class SupplierResponse(SupplierBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
