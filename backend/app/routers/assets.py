import hashlib
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import settings
from backend.app.db import get_db
from backend.app.models.asset import Asset
from backend.app.models.asset_qc import AssetQC
from backend.app.qc.gemini import analyze_image
from backend.app.schemas.asset import AssetRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assets", tags=["assets"])

UPLOAD_DIR = Path(settings.upload_dir)


@router.post("", response_model=AssetRead, status_code=201)
async def upload_asset(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Compute SHA-256 hash
    file_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicate hash
    existing = await db.execute(select(Asset).where(Asset.hash == file_hash))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="Duplicate file: asset with this hash already exists"
        )

    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Store file: {hash}_{original_filename}
    safe_name = file.filename or "unknown"
    stored_name = f"{file_hash[:12]}_{safe_name}"
    file_path = UPLOAD_DIR / stored_name
    file_path.write_bytes(content)

    # Persist to DB
    asset = Asset(
        file_path=str(file_path),
        hash=file_hash,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset, attribute_names=["qc"])
    return asset


@router.get("", response_model=list[AssetRead])
async def list_assets(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.qc))
        .order_by(Asset.uploaded_at.desc())
    )
    return result.scalars().all()


@router.get("/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.qc))
        .where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.post("/{asset_id}/analyze", response_model=AssetRead)
async def analyze_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger Gemini Vision Reference QC analysis for an asset.

    Creates or replaces the AssetQC row for this asset.
    """
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.qc))
        .where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Call Gemini
    try:
        qc_data = await analyze_image(asset.file_path)
    except RuntimeError as exc:
        logger.error("QC analysis failed for asset %d: %s", asset_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    # Upsert: replace existing QC row if re-analyzing
    if asset.qc is not None:
        await db.delete(asset.qc)
        await db.flush()

    qc = AssetQC(asset_id=asset_id, **qc_data)
    db.add(qc)
    await db.commit()
    await db.refresh(asset, attribute_names=["qc"])
    return asset
