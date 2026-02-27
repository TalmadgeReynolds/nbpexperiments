from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base

if TYPE_CHECKING:
    from backend.app.models.run import Run


class RunTelemetry(Base):
    __tablename__ = "run_telemetry"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    thought_summary_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    thought_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    usage_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    safety_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thinking_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allocation_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    allocation_parse_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # "valid", "invalid", or None

    run: Mapped[Run] = relationship("Run", back_populates="telemetry")
