from typing import Optional
from pydantic import BaseModel, model_validator


class SupplierCreate(BaseModel):
    name: str
    display_name: Optional[str] = None  # defaults to name if not provided
    priority: int = 0
    is_active: bool = True

    @model_validator(mode="after")
    def set_display_name(self) -> "SupplierCreate":
        if not self.display_name:
            self.display_name = self.name
        return self


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    display_name: str
    priority: int
    is_active: bool

    class Config:
        from_attributes = True
