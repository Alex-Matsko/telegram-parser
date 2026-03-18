from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class BotScenario(Base):
    __tablename__ = "bot_scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_name = Column(String(255), nullable=False)
    scenario_name = Column(String(255), nullable=False)
    steps_json = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    sources = relationship("Source", back_populates="bot_scenario", lazy="noload")
