from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.export.exporter import generate_export_bundle
from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.models.run import Run
from backend.app.models.run_telemetry import RunTelemetry
from backend.app.models.score import Score

router = APIRouter(tags=["export"])


class ExportResponse(BaseModel):
    bundle_path: str
    run_count: int
    scored_count: int
    telemetry_included: bool


@router.post(
    "/experiments/{experiment_id}/export",
    response_model=ExportResponse,
    status_code=201,
)
async def export_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate an export bundle for the experiment."""

    # ── load experiment + conditions ───────────────────────────────
    result = await db.execute(
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(selectinload(Experiment.conditions))
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    conditions: list[Condition] = list(experiment.conditions)
    if not conditions:
        raise HTTPException(status_code=400, detail="Experiment has no conditions")

    condition_ids = [c.id for c in conditions]

    # ── load runs (with score + telemetry eagerly) ────────────────
    run_result = await db.execute(
        select(Run)
        .where(Run.condition_id.in_(condition_ids))
        .options(selectinload(Run.score), selectinload(Run.telemetry))
        .order_by(Run.condition_id, Run.repeat_index)
    )
    runs: list[Run] = list(run_result.scalars().all())

    if not runs:
        raise HTTPException(status_code=400, detail="No runs found for this experiment")

    # ── build lookup dicts ────────────────────────────────────────
    scores: dict[int, Score] = {}
    telemetry_map: dict[int, RunTelemetry] = {}
    for run in runs:
        if run.score:
            scores[run.id] = run.score
        if run.telemetry:
            telemetry_map[run.id] = run.telemetry

    # ── generate bundle (sync I/O, fine for export) ───────────────
    bundle_path = generate_export_bundle(
        experiment=experiment,
        conditions=conditions,
        runs=runs,
        scores=scores,
        telemetry=telemetry_map if experiment.telemetry_enabled else {},
        export_root=settings.export_dir,
    )

    return ExportResponse(
        bundle_path=str(bundle_path),
        run_count=len(runs),
        scored_count=len(scores),
        telemetry_included=experiment.telemetry_enabled and bool(telemetry_map),
    )


@router.get(
    "/experiments/{experiment_id}/export/download",
    response_class=FileResponse,
)
async def download_export_zip(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Download the export bundle as a ZIP file.

    The bundle must already have been generated via
    ``POST /experiments/{id}/export``.
    """
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    export_root = Path(settings.export_dir)
    # Match the naming logic in exporter._safe_name
    safe = "".join(
        c if c.isalnum() or c in (" ", "-", "_") else "_"
        for c in experiment.name
    ).strip()
    bundle_dir = export_root / safe

    if not bundle_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Export bundle not found — run POST /experiments/{id}/export first",
        )

    # Create a temporary ZIP and stream it back
    zip_path = shutil.make_archive(
        str(tempfile.mktemp(prefix="nbplab_export_")),
        "zip",
        root_dir=str(export_root),
        base_dir=safe,
    )

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{safe}.zip",
    )
