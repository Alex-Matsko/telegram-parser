from sqlalchemy import Column, DateTime, Integer, String, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ProductCatalog(Base):
    __tablename__ = "product_catalog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(50), nullable=False)  # smartphone, headphones, watch, tablet, laptop
    brand = Column(String(50), nullable=False)  # Apple
    line = Column(String(100), nullable=True)  # iPhone, AirPods, Apple Watch
    model = Column(String(255), nullable=False)  # iPhone 15 Pro Max
    generation = Column(String(50), nullable=True)
    memory = Column(String(20), nullable=True)  # 256GB
    color = Column(String(100), nullable=True)  # Natural Titanium
    sim_type = Column(String(20), nullable=True)  # dual / esim
    region = Column(String(20), nullable=True)  # US / EU / etc
    condition = Column(String(20), default="new", nullable=False)  # new / used / refurbished
    normalized_name = Column(String(500), nullable=False)
    sku_key = Column(String(500), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_product_catalog_brand_model", "brand", "model"),
        Index("ix_product_catalog_category", "category"),
        Index("ix_product_catalog_sku_key", "sku_key"),
    )

    offers = relationship("Offer", back_populates="product", lazy="noload")
    price_history = relationship("PriceHistory", back_populates="product", lazy="noload")
