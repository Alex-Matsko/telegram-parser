from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SourceBase(BaseModel):
    type: str = Field(..., pattern="^(channel|group|bot)$")
    telegram_id: int
    source_name: str
    supplier_id: Optional[int] = None
    is_active: bool = True
    poll_interval_minutes: int = 30
    parsing_strategy: str = Field(default="auto", pattern="^(auto|regex|llm)$")
    bot_scenario_id: Optional[int] = None


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    type: Optional[str] = Field(None, pattern="^(channel|group|bot)$")
    telegram_id: Optional[int] = None
    source_name: Optional[str] = None
    supplier_id: Optional[int] = None
    is_active: Optional[bool] = None
    poll_interval_minutes: Optional[int] = None
    parsing_strategy: Optional[str] = Field(None, pattern="^(auto|regex|llm)$")
    bot_scenario_id: Optional[int] = None


class SourceResponse(SourceBase):
    id: int
    last_read_at: Optional[datetime] = None
    last_message_id: Optional[int] = None
    error_count: int = 0
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    supplier_name: Optional[str] = None

    model_config = {"from_attributes": True}


class SourceLogEntry(BaseModel):
    timestamp: datetime
    error: str
    error_count: int
