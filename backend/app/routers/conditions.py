from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db
from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.schemas.experiment import ConditionCreate, ConditionRead

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
