import logging

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.models.asset import Asset
from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.models.run import Run, RunStatusEnum
from backend.app.schemas.run import RunExperimentRequest, RunRead

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])


@router.post(
    "/experiments/{experiment_id}/run",
    response_model=list[RunRead],
    status_code=201,
)
async def run_experiment(
    experiment_id: int,
    body: RunExperimentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create Run rows for every condition × repeat and enqueue RQ jobs.

    Validates that every asset referenced in upload_plans has an AssetQC row
    (Blueprint invariant: QC required before running).
    """
    # Load experiment with conditions
    result = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.conditions))
        .where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    conditions = experiment.conditions
    if not conditions:
        raise HTTPException(
            status_code=400, detail="Experiment has no conditions"
        )

    # Validate QC prerequisite: every asset in every upload_plan must have QC
    all_asset_ids: set[int] = set()
    for cond in conditions:
        if cond.upload_plan:
            for item in cond.upload_plan:
                if isinstance(item, dict):
                    # Legacy slot-aware format: {"slot": 1, "asset_id": 7}
                    aid = item.get("asset_id")
                    if aid is not None:
                        all_asset_ids.add(int(aid))
                else:
                    # Flat format: just an int (current standard)
                    all_asset_ids.add(int(item))

    if all_asset_ids:
        assets_result = await db.execute(
            select(Asset)
            .options(selectinload(Asset.qc))
            .where(Asset.id.in_(all_asset_ids))
        )
        assets = {a.id: a for a in assets_result.scalars().all()}

        missing = all_asset_ids - set(assets.keys())
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Assets not found: {sorted(missing)}",
            )

        no_qc = [aid for aid, a in assets.items() if a.qc is None]
        if no_qc:
            raise HTTPException(
                status_code=400,
                detail=f"Assets missing QC analysis (run POST /assets/{{id}}/analyze first): {sorted(no_qc)}",
            )

    # Create Run rows: condition × repeat_count
    runs: list[Run] = []
    for cond in conditions:
        for repeat_idx in range(body.repeat_count):
            run = Run(
                condition_id=cond.id,
                repeat_index=repeat_idx,
                status=RunStatusEnum.queued,
            )
            db.add(run)
            runs.append(run)

    await db.commit()

    # Re-query runs with telemetry eagerly loaded for serialization
    run_ids = [r.id for r in runs]
    for r in runs:
        await db.refresh(r)

    result2 = await db.execute(
        select(Run)
        .options(selectinload(Run.telemetry))
        .where(Run.id.in_(run_ids))
        .order_by(Run.id)
    )
    runs = list(result2.scalars().all())

    # Enqueue RQ jobs
    try:
        redis_conn = Redis.from_url(settings.redis_url)
        queue = Queue(connection=redis_conn)

        for run in runs:
            queue.enqueue(
                "backend.app.services.runner.execute_run",
                run.id,
                job_timeout=300,  # 5 min timeout per run
            )

        logger.info(
            "Enqueued %d jobs for experiment %d", len(runs), experiment_id
        )
    except Exception as exc:
        logger.error("Failed to enqueue jobs: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to enqueue jobs (is Redis running?): {exc}",
        )

    return runs


@router.get("/runs/{run_id}", response_model=RunRead)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Run)
        .options(selectinload(Run.telemetry))
        .where(Run.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
