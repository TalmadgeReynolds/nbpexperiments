from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ── RunTelemetry schemas ───────────────────────────────────────────


class RunTelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    thought_summary_raw: str | None
    thought_signature: str | None
    usage_metadata_json: dict[str, Any] | None
    safety_metadata_json: Any | None
    thinking_level: str | None
    latency_ms: int | None
    allocation_report_json: dict[str, Any] | None
    allocation_parse_status: str | None


# ── Run schemas ────────────────────────────────────────────────────


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    condition_id: int
    repeat_index: int
    status: str
    output_image_path: str | None
    latency_ms: int | None
    created_at: datetime
    telemetry: RunTelemetryRead | None = None


# ── Request body for launching runs ───────────────────────────────


class RunExperimentRequest(BaseModel):
    repeat_count: int = 3
