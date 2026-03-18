from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product_catalog.id"), nullable=False)
    raw_message_id = Column(Integer, ForeignKey("raw_messages.id"), nullable=True)
    price = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="RUB", nullable=False)
    availability = Column(String(50), nullable=True)
    detected_confidence = Column(Float, default=1.0, nullable=False)
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_offers_product_supplier", "product_id", "supplier_id"),
        Index("ix_offers_is_current", "is_current"),
    )

    supplier = relationship("Supplier", back_populates="offers", lazy="selectin")
    product = relationship("ProductCatalog", back_populates="offers", lazy="selectin")
    raw_message = relationship("RawMessage", back_populates="offers", lazy="noload")
    price_history = relationship("PriceHistory", back_populates="offer", lazy="noload")
