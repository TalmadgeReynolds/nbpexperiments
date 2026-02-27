"""RQ worker function for executing Nano Banana Pro generation runs.

This module uses **sync** SQLAlchemy sessions because RQ workers are not async.
The runner respects the telemetry hard invariant: when telemetry is OFF, no
RunTelemetry row is created.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker, selectinload

from backend.app.config import settings
from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.models.run import Run, RunStatusEnum
from backend.app.models.run_telemetry import RunTelemetry
from backend.app.services.slots import parse_upload_plan
from backend.app.telemetry.extractor import process_telemetry

logger = logging.getLogger(__name__)

# ── Sync engine for RQ workers ──────────────────────────────────────

from sqlalchemy import create_engine

_sync_engine = create_engine(settings.database_url_sync, echo=False)
SyncSession = sessionmaker(_sync_engine, class_=Session, expire_on_commit=False)

OUTPUT_DIR = Path(settings.upload_dir) / "outputs"

# Nano Banana Pro API endpoint (Gemini imagen)
NBP_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent"


def execute_run(run_id: int) -> None:
    """Execute a single generation run.  Called by the RQ worker.

    Pipeline:
    1. Mark run as ``running``
    2. Load condition → experiment to get prompt, upload_plan, telemetry flag
    3. Build request for Nano Banana Pro
    4. Call API, measure latency
    5. Store output image + latency
    6. If telemetry ON: store telemetry data
    7. Update status to ``succeeded`` or ``failed``
    """
    with SyncSession() as db:
        run = db.execute(
            select(Run)
            .options(
                selectinload(Run.condition).selectinload(Condition.experiment)
            )
            .where(Run.id == run_id)
        ).scalar_one_or_none()

        if run is None:
            logger.error("Run %d not found", run_id)
            return

        # 1. Mark running
        run.status = RunStatusEnum.running
        db.commit()

        condition = run.condition
        experiment = condition.experiment
        telemetry_on = experiment.telemetry_enabled

        try:
            # 2. Parse upload plan (ordered list of asset IDs)
            ordered_asset_ids = parse_upload_plan(condition.upload_plan) or []

            # 3. Build request
            result = _call_nano_banana_pro(
                prompt=condition.prompt,
                upload_plan=ordered_asset_ids,
                model_name=experiment.model_name,
                render_settings=experiment.render_settings,
                telemetry_on=telemetry_on,
            )

            # 4. Store output image
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            image_filename = f"run_{run.id}.png"
            image_path = OUTPUT_DIR / image_filename

            if result.get("image_bytes"):
                image_path.write_bytes(result["image_bytes"])
                run.output_image_path = str(image_path)

            run.latency_ms = result.get("latency_ms")

            # 5. Telemetry — HARD INVARIANT: only when ON
            if telemetry_on:
                telemetry_data = result.get("telemetry", {})
                raw_thought = telemetry_data.get("thought_summary_raw")

                # Use the telemetry extraction service for signature + allocation
                extracted = process_telemetry(
                    raw_thought,
                    upload_order=ordered_asset_ids or None,
                )

                telem = RunTelemetry(
                    run_id=run.id,
                    thought_summary_raw=raw_thought,
                    thought_signature=extracted["thought_signature"],
                    usage_metadata_json=telemetry_data.get("usage_metadata"),
                    safety_metadata_json=telemetry_data.get("safety_metadata"),
                    thinking_level=telemetry_data.get("thinking_level"),
                    latency_ms=result.get("latency_ms"),
                    allocation_report_json=extracted["allocation_report"],
                    allocation_parse_status=extracted["allocation_parse_status"],
                    intended_upload_order_json=ordered_asset_ids or None,
                    allocation_analysis_json=extracted.get("allocation_analysis"),
                )
                db.add(telem)

            # 5. Success
            run.status = RunStatusEnum.succeeded
            db.commit()

        except Exception as exc:
            logger.error("Run %d failed: %s", run_id, exc, exc_info=True)
            db.rollback()

            # Re-fetch run in case of rollback
            run = db.execute(
                select(Run).where(Run.id == run_id)
            ).scalar_one()
            run.status = RunStatusEnum.failed
            db.commit()


def _call_nano_banana_pro(
    prompt: str,
    upload_plan: list[int],
    model_name: str,
    render_settings: dict | None,
    telemetry_on: bool,
) -> dict[str, Any]:
    """Call the Nano Banana Pro (Gemini) image generation API.

    Returns dict with keys:
    - image_bytes: raw PNG bytes (or None)
    - latency_ms: int
    - telemetry: dict (only populated if telemetry_on)
    """
    import base64

    api_key = settings.gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    # Build the generation request
    parts: list[dict[str, Any]] = [{"text": prompt}]

    # Attach reference images from upload_plan
    for asset_id in upload_plan:
        image_path = _resolve_asset_path(asset_id)
        if image_path:
            img_bytes = Path(image_path).read_bytes()
            b64 = base64.b64encode(img_bytes).decode()
            suffix = Path(image_path).suffix.lower()
            mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(suffix, "image/png")
            parts.append({"inline_data": {"mime_type": mime, "data": b64}})

    payload: dict[str, Any] = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    # Apply render settings if provided
    if render_settings:
        payload["generationConfig"].update(render_settings)

    # NOTE: gemini-3-pro-image-preview does NOT support thinkingConfig / includeThoughts.
    # Telemetry we CAN capture: usageMetadata, safetyRatings, latency — all
    # returned naturally in the response without any special request field.

    start = time.monotonic()
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{NBP_API_URL}?key={api_key}",
            json=payload,
        )
    latency_ms = int((time.monotonic() - start) * 1000)

    result: dict[str, Any] = {
        "image_bytes": None,
        "latency_ms": latency_ms,
        "telemetry": {},
    }

    if resp.status_code != 200:
        raise RuntimeError(f"NBP API error {resp.status_code}: {resp.text[:500]}")

    body = resp.json()

    # Extract image and telemetry from response
    # NOTE: Gemini REST API returns camelCase keys (inlineData, not inline_data)
    candidates = body.get("candidates", [])
    if candidates:
        candidate = candidates[0]
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            # Image data (camelCase key from Gemini API)
            if "inlineData" in part:
                result["image_bytes"] = base64.b64decode(
                    part["inlineData"]["data"]
                )
            # Thought summary (telemetry)
            if telemetry_on and "thought" in part:
                result["telemetry"]["thought_summary_raw"] = part.get("thought", "")

        # Safety metadata
        safety = candidate.get("safetyRatings")
        if telemetry_on and safety:
            result["telemetry"]["safety_metadata"] = safety

    # Usage metadata
    usage = body.get("usageMetadata")
    if telemetry_on and usage:
        result["telemetry"]["usage_metadata"] = usage

    # Model version / thinking level from response metadata
    if telemetry_on:
        result["telemetry"]["thinking_level"] = body.get("modelVersion")

    return result


def _resolve_asset_path(asset_id: int) -> str | None:
    """Look up an asset's file_path by ID using a sync session."""
    from backend.app.models.asset import Asset

    with SyncSession() as db:
        asset = db.execute(
            select(Asset).where(Asset.id == asset_id)
        ).scalar_one_or_none()
        return asset.file_path if asset else None
