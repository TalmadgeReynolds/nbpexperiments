from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base

if TYPE_CHECKING:
    from backend.app.models.asset_qc import AssetQC


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    qc: Mapped[AssetQC | None] = relationship(
        "AssetQC", back_populates="asset", uselist=False, cascade="all, delete-orphan"
    )
