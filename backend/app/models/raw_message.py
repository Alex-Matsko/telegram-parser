from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class RawMessage(Base):
    __tablename__ = "raw_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    telegram_message_id = Column(BigInteger, nullable=False)
    message_text = Column(Text, nullable=False)
    message_date = Column(DateTime(timezone=True), nullable=False)
    sender_name = Column(String(255), nullable=True)
    raw_payload = Column(JSON, nullable=True)
    is_processed = Column(Boolean, default=False, nullable=False)
    parse_status = Column(
        String(20), default="pending", nullable=False
    )  # pending / parsed / failed / needs_review
    parse_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_id", "telegram_message_id", name="uq_source_message"),
    )

    source = relationship("Source", back_populates="raw_messages", lazy="selectin")
    offers = relationship("Offer", back_populates="raw_message", lazy="noload")
