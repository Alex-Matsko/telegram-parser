from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(20), nullable=False)  # channel / group / bot
    telegram_id = Column(BigInteger, nullable=False, unique=True)
    source_name = Column(String(255), nullable=False)
    channel_url = Column(String(512), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    poll_interval_minutes = Column(Integer, default=30, nullable=False)
    parsing_strategy = Column(String(20), default="auto", nullable=False)  # auto/regex/llm/pipe/table
    # Optional format hint for pipe/table strategies.
    # Pipe example:  "model|memory|color|price"
    # Table example: "model\tmemory\tprice"
    # Columns available: model, memory, color, condition, sim_type, price, currency, skip
    line_format = Column(Text, nullable=True)
    bot_scenario_id = Column(Integer, ForeignKey("bot_scenarios.id"), nullable=True)
    last_read_at = Column(DateTime(timezone=True), nullable=True)
    last_message_id = Column(BigInteger, nullable=True)
    error_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    supplier = relationship("Supplier", back_populates="sources", lazy="selectin")
    bot_scenario = relationship("BotScenario", back_populates="sources", lazy="selectin")
    raw_messages = relationship("RawMessage", back_populates="source", lazy="noload")
