"""Tests for score endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.models.run import Run, RunStatusEnum
from backend.tests.conftest import create_experiment, create_condition

pytestmark = pytest.mark.asyncio


async def _create_run(db: AsyncSession) -> Run:
    """Insert an experiment → condition → run directly in the DB."""
    exp = Experiment(name="Score Test", telemetry_enabled=False)
    db.add(exp)
    await db.flush()
    cond = Condition(experiment_id=exp.id, name="C1", prompt="P1")
    db.add(cond)
    await db.flush()
    run = Run(condition_id=cond.id, repeat_index=0, status=RunStatusEnum.succeeded)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def test_create_score(client: AsyncClient, db_session: AsyncSession):
    run = await _create_run(db_session)
    resp = await client.post(f"/runs/{run.id}/score", json={
        "identity_score": 8,
        "object_score": 7,
        "style_score": 9,
        "environment_score": 6,
        "hallucination": False,
        "notes": "Good result",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["identity_score"] == 8
    assert data["hallucination"] is False
    assert data["notes"] == "Good result"


async def test_create_score_duplicate(client: AsyncClient, db_session: AsyncSession):
    run = await _create_run(db_session)
    await client.post(f"/runs/{run.id}/score", json={
        "identity_score": 5, "object_score": 5,
        "style_score": 5, "environment_score": 5,
    })
    # Second score should be rejected
    resp = await client.post(f"/runs/{run.id}/score", json={
        "identity_score": 5, "object_score": 5,
        "style_score": 5, "environment_score": 5,
    })
    assert resp.status_code == 409


async def test_create_score_invalid_range(client: AsyncClient, db_session: AsyncSession):
    run = await _create_run(db_session)
    resp = await client.post(f"/runs/{run.id}/score", json={
        "identity_score": 0,  # below minimum of 1
        "object_score": 5,
        "style_score": 5,
        "environment_score": 5,
    })
    assert resp.status_code == 422


async def test_create_score_run_not_found(client: AsyncClient):
    resp = await client.post("/runs/9999/score", json={
        "identity_score": 5, "object_score": 5,
        "style_score": 5, "environment_score": 5,
    })
    assert resp.status_code == 404


async def test_get_score(client: AsyncClient, db_session: AsyncSession):
    run = await _create_run(db_session)
    await client.post(f"/runs/{run.id}/score", json={
        "identity_score": 7, "object_score": 6,
        "style_score": 8, "environment_score": 5,
    })
    resp = await client.get(f"/runs/{run.id}/score")
    assert resp.status_code == 200
    assert resp.json()["identity_score"] == 7


async def test_get_score_not_found(client: AsyncClient, db_session: AsyncSession):
    run = await _create_run(db_session)
    resp = await client.get(f"/runs/{run.id}/score")
    assert resp.status_code == 404
