from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Condition schemas ──────────────────────────────────────────────


class ConditionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    prompt: str = Field(..., min_length=1)
    upload_plan: list[int] | None = Field(
        default=None, description="Ordered list of asset IDs"
    )


class ConditionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    name: str
    prompt: str
    upload_plan: list[int] | None
    created_at: datetime


# ── Experiment schemas ─────────────────────────────────────────────


class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    hypothesis: str | None = None
    telemetry_enabled: bool = False
    model_name: str = Field(default="gemini-3-pro-image", max_length=100)
    render_settings: dict[str, Any] | None = None


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hypothesis: str | None
    telemetry_enabled: bool
    model_name: str
    render_settings: dict[str, Any] | None
    created_at: datetime
    conditions: list[ConditionRead] = []
