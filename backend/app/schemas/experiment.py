from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# -- Condition schemas -----------------------------------------------


class ConditionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    prompt: str = Field(..., min_length=1)
    upload_plan: list[int] | None = Field(
        default=None,
        description=(
            "Ordered list of asset IDs to use as reference images. "
            "Order matters — images are sent to the API in this sequence."
        ),
    )


class ConditionUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    name: str | None = None
    prompt: str | None = None
    upload_plan: list[int] | None = Field(
        default=None,
        description="New ordered list of asset IDs.  Send [] to clear.",
    )


class ConditionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    name: str
    prompt: str
    upload_plan: list[int] | None
    created_at: datetime

    @field_validator("upload_plan", mode="before")
    @classmethod
    def _normalise_legacy_plan(cls, v: Any) -> list[int] | None:
        """Convert legacy slot-aware dicts to flat asset-id list."""
        if v is None:
            return None
        if not isinstance(v, list):
            return None
        out: list[int] = []
        for item in v:
            if isinstance(item, int):
                out.append(item)
            elif isinstance(item, dict) and "asset_id" in item:
                out.append(int(item["asset_id"]))
            # skip anything else
        return out or None


# -- Experiment schemas ----------------------------------------------


class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    hypothesis: str | None = None
    telemetry_enabled: bool = False
    model_name: str = Field(default="gemini-3-pro-image-preview", max_length=100)
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
