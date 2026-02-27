from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ── AssetQC schemas ────────────────────────────────────────────────


class AssetQCRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    role_guess: str | None
    role_confidence: float | None
    ambiguity_score: float | None
    quality_json: dict[str, Any] | None
    face_json: dict[str, Any] | None
    environment_json: dict[str, Any] | None
    lighting_json: dict[str, Any] | None
    style_json: dict[str, Any] | None
    created_at: datetime


# ── Asset schemas ──────────────────────────────────────────────────


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_path: str
    hash: str
    uploaded_at: datetime
    qc: AssetQCRead | None = None
