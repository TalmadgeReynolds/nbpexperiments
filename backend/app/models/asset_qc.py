from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base

if TYPE_CHECKING:
    from backend.app.models.asset import Asset


class RoleGuessEnum(str, enum.Enum):
    human_identity = "human_identity"
    object_fidelity = "object_fidelity"
    environment_plate = "environment_plate"
    style_look = "style_look"
    composition_pose = "composition_pose"
    texture_material = "texture_material"
    mixed = "mixed"


class AssetQC(Base):
    __tablename__ = "asset_qc"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    role_guess: Mapped[RoleGuessEnum | None] = mapped_column(
        Enum(RoleGuessEnum, name="role_guess_enum", create_type=True), nullable=True
    )
    role_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ambiguity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    face_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    environment_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lighting_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    style_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset: Mapped[Asset] = relationship("Asset", back_populates="qc")
