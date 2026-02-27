from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base

if TYPE_CHECKING:
    from backend.app.models.condition import Condition
    from backend.app.models.run_telemetry import RunTelemetry
    from backend.app.models.score import Score


class RunStatusEnum(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    condition_id: Mapped[int] = mapped_column(
        ForeignKey("conditions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repeat_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RunStatusEnum] = mapped_column(
        Enum(RunStatusEnum, name="run_status_enum", create_type=True),
        default=RunStatusEnum.queued,
        nullable=False,
    )
    output_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    condition: Mapped[Condition] = relationship("Condition", back_populates="runs")
    score: Mapped[Score | None] = relationship(
        "Score", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    telemetry: Mapped[RunTelemetry | None] = relationship(
        "RunTelemetry",
        back_populates="run",
        uselist=False,
        cascade="all, delete-orphan",
    )
