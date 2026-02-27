"""Tests for experiment and condition CRUD endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.conftest import create_condition, create_experiment

pytestmark = pytest.mark.asyncio


# ── Experiment CRUD ────────────────────────────────────────────────


async def test_create_experiment(client: AsyncClient):
    data = await create_experiment(client, name="My Experiment", hypothesis="H1")
    assert data["name"] == "My Experiment"
    assert data["hypothesis"] == "H1"
    assert data["telemetry_enabled"] is False
    assert "id" in data
    assert "created_at" in data


async def test_create_experiment_with_telemetry(client: AsyncClient):
    data = await create_experiment(client, telemetry_enabled=True)
    assert data["telemetry_enabled"] is True


async def test_list_experiments(client: AsyncClient):
    await create_experiment(client, name="Exp 1")
    await create_experiment(client, name="Exp 2")

    resp = await client.get("/experiments")
    assert resp.status_code == 200
    experiments = resp.json()
    assert len(experiments) >= 2


async def test_get_experiment(client: AsyncClient):
    created = await create_experiment(client, name="Detail Test")
    resp = await client.get(f"/experiments/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Detail Test"


async def test_get_experiment_not_found(client: AsyncClient):
    resp = await client.get("/experiments/9999")
    assert resp.status_code == 404


async def test_create_experiment_empty_name(client: AsyncClient):
    resp = await client.post("/experiments", json={
        "name": "",
        "hypothesis": "H",
    })
    assert resp.status_code == 422


# ── Condition CRUD ─────────────────────────────────────────────────


async def test_create_condition(client: AsyncClient):
    exp = await create_experiment(client)
    cond = await create_condition(
        client, exp["id"], name="Cond A", prompt="Draw a banana"
    )
    assert cond["name"] == "Cond A"
    assert cond["prompt"] == "Draw a banana"
    assert cond["experiment_id"] == exp["id"]


async def test_create_condition_with_upload_plan(client: AsyncClient):
    exp = await create_experiment(client)
    cond = await create_condition(
        client, exp["id"], upload_plan=[1, 2, 3]
    )
    assert cond["upload_plan"] == [1, 2, 3]


async def test_create_condition_experiment_not_found(client: AsyncClient):
    resp = await client.post("/experiments/9999/conditions", json={
        "name": "C", "prompt": "P",
    })
    assert resp.status_code == 404


async def test_experiment_includes_conditions(client: AsyncClient):
    exp = await create_experiment(client)
    await create_condition(client, exp["id"], name="C1", prompt="P1")
    await create_condition(client, exp["id"], name="C2", prompt="P2")

    resp = await client.get(f"/experiments/{exp['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["conditions"]) == 2
