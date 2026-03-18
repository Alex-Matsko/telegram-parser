from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class OfferBase(BaseModel):
    supplier_id: int
    product_id: int
    price: Decimal
    currency: str = "RUB"
    availability: Optional[str] = None


class OfferCreate(OfferBase):
    raw_message_id: Optional[int] = None
    detected_confidence: float = 1.0


class OfferResponse(OfferBase):
    id: int
    raw_message_id: Optional[int] = None
    detected_confidence: float
    is_current: bool
    created_at: datetime
    updated_at: datetime
    supplier_name: Optional[str] = None

    model_config = {"from_attributes": True}
