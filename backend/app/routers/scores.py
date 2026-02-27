from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db
from backend.app.models.run import Run
from backend.app.models.score import Score
from backend.app.schemas.score import ScoreCreate, ScoreRead

router = APIRouter(tags=["scores"])


@router.post("/runs/{run_id}/score", response_model=ScoreRead, status_code=201)
async def create_score(
    run_id: int,
    body: ScoreCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit a manual score for a run. One score per run (unique constraint)."""
    # Verify run exists
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Check for existing score (unique constraint)
    existing = (
        await db.execute(select(Score).where(Score.run_id == run_id))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Score already exists for this run")

    score = Score(run_id=run_id, **body.model_dump())
    db.add(score)
    await db.commit()
    await db.refresh(score)
    return score


@router.get("/runs/{run_id}/score", response_model=ScoreRead)
async def get_score(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the score for a run."""
    score = (
        await db.execute(select(Score).where(Score.run_id == run_id))
    ).scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="Score not found for this run")
    return score
