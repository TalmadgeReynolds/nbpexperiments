from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScoreCreate(BaseModel):
    identity_score: int = Field(..., ge=1, le=10)
    object_score: int = Field(..., ge=1, le=10)
    style_score: int = Field(..., ge=1, le=10)
    environment_score: int = Field(..., ge=1, le=10)
    hallucination: bool = False
    notes: str | None = None


class ScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    identity_score: int
    object_score: int
    style_score: int
    environment_score: int
    hallucination: bool
    notes: str | None
    created_at: datetime
