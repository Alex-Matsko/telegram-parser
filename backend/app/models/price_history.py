from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    offer_id = Column(Integer, ForeignKey("offers.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product_catalog.id"), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="RUB", nullable=False)
    captured_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_price_history_product_time", "product_id", "captured_at"),
        Index("ix_price_history_supplier_product", "supplier_id", "product_id"),
    )

    offer = relationship("Offer", back_populates="price_history", lazy="noload")
    supplier = relationship("Supplier", back_populates="price_history", lazy="selectin")
    product = relationship("ProductCatalog", back_populates="price_history", lazy="noload")
