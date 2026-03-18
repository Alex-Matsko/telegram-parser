from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class RawMessageResponse(BaseModel):
    id: int
    source_id: int
    source_name: Optional[str] = None
    telegram_message_id: int
    message_text: str
    message_date: datetime
    sender_name: Optional[str] = None
    is_processed: bool
    parse_status: str
    parse_error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnresolvedListResponse(BaseModel):
    items: list[RawMessageResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ManualResolveRequest(BaseModel):
    product_id: int
    price: Decimal
    currency: str = "RUB"
    supplier_id: int


class BotScenarioBase(BaseModel):
    bot_name: str
    scenario_name: str
    steps_json: list[dict]
    is_active: bool = True


class BotScenarioCreate(BotScenarioBase):
    pass


class BotScenarioUpdate(BaseModel):
    bot_name: Optional[str] = None
    scenario_name: Optional[str] = None
    steps_json: Optional[list[dict]] = None
    is_active: Optional[bool] = None


class BotScenarioResponse(BotScenarioBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BotScenarioTestResult(BaseModel):
    success: bool
    steps_executed: int
    collected_messages: list[str]
    errors: list[str]
