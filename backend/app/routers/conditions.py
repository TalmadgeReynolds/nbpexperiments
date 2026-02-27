from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db
from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.schemas.experiment import ConditionCreate, ConditionRead, ConditionUpdate

router = APIRouter(tags=["conditions"])


@router.post(
    "/experiments/{experiment_id}/conditions",
    response_model=ConditionRead,
    status_code=201,
)
async def create_condition(
    experiment_id: int,
    body: ConditionCreate,
    db: AsyncSession = Depends(get_db),
):
    # Verify experiment exists
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    condition = Condition(
        experiment_id=experiment_id,
        name=body.name,
        prompt=body.prompt,
        upload_plan=body.upload_plan,
    )
    db.add(condition)
    await db.commit()
    await db.refresh(condition)
    return condition


@router.patch(
    "/conditions/{condition_id}",
    response_model=ConditionRead,
)
async def update_condition(
    condition_id: int,
    body: ConditionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a condition's name, prompt, or upload_plan."""
    result = await db.execute(
        select(Condition).where(Condition.id == condition_id)
    )
    condition = result.scalar_one_or_none()
    if condition is None:
        raise HTTPException(status_code=404, detail="Condition not found")

    payload = body.model_dump(exclude_unset=True)
    # Treat an empty list as "clear upload plan"
    if "upload_plan" in payload and payload["upload_plan"] == []:
        payload["upload_plan"] = None

    for field, value in payload.items():
        setattr(condition, field, value)

    await db.commit()
    await db.refresh(condition)
    return condition


@router.delete(
    "/conditions/{condition_id}",
    status_code=204,
)
async def delete_condition(
    condition_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a condition.  Fails if runs already exist for it."""
    from backend.app.models.run import Run

    result = await db.execute(
        select(Condition).where(Condition.id == condition_id)
    )
    condition = result.scalar_one_or_none()
    if condition is None:
        raise HTTPException(status_code=404, detail="Condition not found")

    # Guard: don't delete if runs exist
    run_result = await db.execute(
        select(Run.id).where(Run.condition_id == condition_id).limit(1)
    )
    if run_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a condition that has runs. Delete the runs first.",
        )

    await db.delete(condition)
    await db.commit()
