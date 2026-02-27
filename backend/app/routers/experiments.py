from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db import get_db
from backend.app.models.experiment import Experiment
from backend.app.schemas.experiment import ExperimentCreate, ExperimentRead

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("", response_model=ExperimentRead, status_code=201)
async def create_experiment(
    body: ExperimentCreate,
    db: AsyncSession = Depends(get_db),
):
    experiment = Experiment(
        name=body.name,
        hypothesis=body.hypothesis,
        telemetry_enabled=body.telemetry_enabled,
        model_name=body.model_name,
        render_settings=body.render_settings,
    )
    db.add(experiment)
    await db.commit()
    await db.refresh(experiment, attribute_names=["conditions"])
    return experiment


@router.get("", response_model=list[ExperimentRead])
async def list_experiments(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.conditions))
        .order_by(Experiment.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(
    experiment_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Experiment)
        .options(selectinload(Experiment.conditions))
        .where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment
