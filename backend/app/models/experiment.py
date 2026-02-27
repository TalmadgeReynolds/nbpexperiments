from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base

if TYPE_CHECKING:
    from backend.app.models.condition import Condition


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    telemetry_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gemini-3-pro-image-preview"
    )
    render_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conditions: Mapped[list[Condition]] = relationship(
        "Condition", back_populates="experiment", cascade="all, delete-orphan"
    )
