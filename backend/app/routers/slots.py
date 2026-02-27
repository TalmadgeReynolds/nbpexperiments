"""Reference image API endpoints -- info and recommendations."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db import get_db
from backend.app.models.asset import Asset
from backend.app.services.slots import (
    get_ref_image_info,
    recommend_upload_order,
)

router = APIRouter(prefix="/refs", tags=["refs"])


# -- Schemas ---------------------------------------------------------


class RefRecommendationItem(BaseModel):
    asset_id: int
    role_guess: str
    likely_category: str
    confidence: float
    position: int
    note: str | None


# -- Endpoints -------------------------------------------------------


@router.get("/info")
async def get_info():
    """Return reference image system info (limits, categories, notes)."""
    return get_ref_image_info()


@router.get("/recommendations", response_model=list[RefRecommendationItem])
async def get_recommendations(
    db: AsyncSession = Depends(get_db),
):
    """Get recommended upload order for all analyzed assets.

    Groups images by likely category (character -> object -> world)
    and sorts by QC confidence within each group.
    """
    result = await db.execute(
        select(Asset).options(selectinload(Asset.qc)).order_by(Asset.id)
    )
    assets = result.scalars().all()

    analyzed = [
        {
            "id": a.id,
            "role_guess": a.qc.role_guess.value if a.qc and a.qc.role_guess else "mixed",
            "role_confidence": a.qc.role_confidence if a.qc else 0.0,
        }
        for a in assets
        if a.qc is not None
    ]

    if not analyzed:
        return []

    return recommend_upload_order(analyzed)
