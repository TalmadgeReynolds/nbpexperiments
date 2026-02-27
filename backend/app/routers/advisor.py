"""Hypothesis Advisor router — AI-powered condition suggestion flow."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db import get_db
from backend.app.models.asset import Asset
from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.schemas.advisor import (
    AdvisorQuestionsResponse,
    AdvisorQuestion,
    AdvisorSuggestRequest,
    AdvisorSuggestResponse,
    SuggestedCondition,
)
from backend.app.services.hypothesis_advisor import (
    generate_questions,
    suggest_conditions,
    generate_order_permutations,
    ORDER_STRATEGIES,
)

router = APIRouter(tags=["advisor"])


@router.post(
    "/experiments/{experiment_id}/advisor/questions",
    response_model=AdvisorQuestionsResponse,
)
async def get_advisor_questions(
    experiment_id: int,
    provider: str = Query("gemini", pattern="^(gemini|claude)$"),
    db: AsyncSession = Depends(get_db),
):
    """Analyze the experiment hypothesis and return clarifying questions."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not experiment.hypothesis:
        raise HTTPException(
            status_code=400,
            detail="Experiment has no hypothesis — add one before using the advisor",
        )

    try:
        raw_questions = await generate_questions(experiment.hypothesis, provider=provider)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Advisor error: {exc}")

    questions = [AdvisorQuestion(**q) for q in raw_questions]

    return AdvisorQuestionsResponse(
        experiment_id=experiment.id,
        hypothesis=experiment.hypothesis,
        questions=questions,
    )


@router.post(
    "/experiments/{experiment_id}/advisor/conditions",
    response_model=AdvisorSuggestResponse,
)
async def get_advisor_conditions(
    experiment_id: int,
    body: AdvisorSuggestRequest,
    provider: str = Query("gemini", pattern="^(gemini|claude)$"),
    db: AsyncSession = Depends(get_db),
):
    """Given answered questions, suggest experimental conditions."""
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not experiment.hypothesis:
        raise HTTPException(status_code=400, detail="Experiment has no hypothesis")

    # Gather available assets so the advisor can reference them
    assets_result = await db.execute(
        select(Asset).options(selectinload(Asset.qc)).order_by(Asset.id)
    )
    assets = assets_result.scalars().all()
    available_assets = [
        {
            "id": a.id,
            "file_path": a.file_path,
            "role_guess": a.qc.role_guess.value if a.qc and a.qc.role_guess else "unknown",
        }
        for a in assets
    ]

    try:
        raw_conditions = await suggest_conditions(
            hypothesis=experiment.hypothesis,
            questions_and_answers=[qa.model_dump() for qa in body.answers],
            available_assets=available_assets if available_assets else None,
            provider=provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Advisor error: {exc}")

    conditions = [SuggestedCondition.from_raw(c) for c in raw_conditions]

    return AdvisorSuggestResponse(
        experiment_id=experiment.id,
        conditions=conditions,
    )


# -- Upload-order permutation (separate toggleable feature) ----------


class PermuteOrdersRequest(BaseModel):
    strategies: list[str] | None = Field(
        default=None,
        description="Which reordering strategies to apply.  "
                    "null = all strategies.  Options: "
                    + ", ".join(ORDER_STRATEGIES.keys()),
    )


class PermuteOrdersResponse(BaseModel):
    experiment_id: int
    created_count: int
    conditions: list[SuggestedCondition]


@router.post(
    "/experiments/{experiment_id}/advisor/permute-orders",
    response_model=PermuteOrdersResponse,
)
async def permute_upload_orders(
    experiment_id: int,
    body: PermuteOrdersRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate upload-order permutation conditions from existing conditions.

    This is a separate, optional step that creates new conditions with
    the same prompts but different reference image upload orders.
    """
    # Load experiment + existing conditions
    result = await db.execute(
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(selectinload(Experiment.conditions))
    )
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if not experiment.conditions:
        raise HTTPException(
            status_code=400,
            detail="Experiment has no conditions — add conditions first",
        )

    # Build asset_info map for category-aware strategies
    assets_result = await db.execute(
        select(Asset).options(selectinload(Asset.qc)).order_by(Asset.id)
    )
    assets = assets_result.scalars().all()
    asset_info = {
        a.id: (a.qc.role_guess.value if a.qc and a.qc.role_guess else "unknown")
        for a in assets
    }

    # Build condition dicts for the permutation engine
    existing = [
        {
            "id": c.id,
            "name": c.name,
            "prompt": c.prompt,
            "upload_plan": c.upload_plan,
        }
        for c in experiment.conditions
    ]

    strategies = body.strategies if body else None
    permutations = generate_order_permutations(
        existing, asset_info=asset_info, strategies=strategies
    )

    # Create the new conditions in the DB
    created = []
    for p in permutations:
        cond = Condition(
            experiment_id=experiment_id,
            name=p["name"],
            prompt=p["prompt"],
            upload_plan=p["upload_plan"],
        )
        db.add(cond)
        created.append(cond)

    await db.commit()

    # Refresh to get IDs
    for c in created:
        await db.refresh(c)

    suggested = [
        SuggestedCondition(
            name=p["name"],
            prompt=p["prompt"],
            upload_plan=p["upload_plan"],
            ref_strategy=p.get("ref_strategy"),
        )
        for p in permutations
    ]

    return PermuteOrdersResponse(
        experiment_id=experiment_id,
        created_count=len(created),
        conditions=suggested,
    )
