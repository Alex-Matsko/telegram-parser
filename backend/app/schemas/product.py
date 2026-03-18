from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProductBase(BaseModel):
    category: str
    brand: str
    line: Optional[str] = None
    model: str
    generation: Optional[str] = None
    memory: Optional[str] = None
    color: Optional[str] = None
    sim_type: Optional[str] = None
    region: Optional[str] = None
    condition: str = "new"


class ProductCreate(ProductBase):
    normalized_name: str
    sku_key: str


class ProductResponse(ProductBase):
    id: int
    normalized_name: str
    sku_key: str
    created_at: datetime

    model_config = {"from_attributes": True}
