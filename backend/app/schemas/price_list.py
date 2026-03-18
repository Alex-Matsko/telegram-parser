from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class PriceListItem(BaseModel):
    product_id: int
    category: str
    brand: str
    model: str
    memory: Optional[str] = None
    color: Optional[str] = None
    condition: str = "new"
    sim_type: Optional[str] = None
    normalized_name: str
    best_price: Decimal
    best_supplier: str
    best_supplier_id: int
    second_price: Optional[Decimal] = None
    third_price: Optional[Decimal] = None
    offer_count: int
    price_change_3d: Optional[Decimal] = None
    price_change_3d_pct: Optional[float] = None
    last_updated: datetime


class PriceListResponse(BaseModel):
    items: list[PriceListItem]
    total: int
    page: int
    per_page: int
    pages: int


class PriceListDetailItem(BaseModel):
    product_id: int
    normalized_name: str
    category: str
    brand: str
    model: str
    memory: Optional[str] = None
    color: Optional[str] = None
    condition: str = "new"
    offers: list["OfferDetail"]


class OfferDetail(BaseModel):
    offer_id: int
    supplier_id: int
    supplier_name: str
    price: Decimal
    currency: str
    availability: Optional[str] = None
    confidence: float
    is_current: bool
    updated_at: datetime


class PriceHistoryPoint(BaseModel):
    price: Decimal
    supplier: str
    supplier_id: int
    captured_at: datetime


class PriceHistoryResponse(BaseModel):
    product_id: int
    product_name: str
    history: list[PriceHistoryPoint]


class PriceChartSeries(BaseModel):
    supplier: str
    supplier_id: int
    data: list["ChartDataPoint"]


class ChartDataPoint(BaseModel):
    timestamp: datetime
    price: Decimal


class PriceChartResponse(BaseModel):
    product_id: int
    product_name: str
    series: list[PriceChartSeries]


class DashboardStats(BaseModel):
    total_products: int
    total_sources: int
    active_sources: int
    total_suppliers: int
    total_offers: int
    unresolved_count: int
    failed_count: int
    last_collection_at: Optional[datetime] = None
    error_source_count: int
