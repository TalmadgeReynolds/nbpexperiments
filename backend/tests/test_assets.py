"""Tests for asset upload endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.conftest import fake_image_file

pytestmark = pytest.mark.asyncio


async def test_upload_asset(client: AsyncClient):
    img = fake_image_file("photo.png")
    resp = await client.post(
        "/assets",
        files={"file": ("photo.png", img, "image/png")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["hash"]
    assert "photo.png" in data["file_path"]
    assert data["qc"] is None


async def test_upload_duplicate_asset(client: AsyncClient):
    img1 = fake_image_file("photo.png")
    resp1 = await client.post(
        "/assets",
        files={"file": ("photo.png", img1, "image/png")},
    )
    assert resp1.status_code == 201

    # Same content → duplicate hash
    img2 = fake_image_file("photo.png")
    resp2 = await client.post(
        "/assets",
        files={"file": ("photo.png", img2, "image/png")},
    )
    assert resp2.status_code == 409


async def test_upload_empty_file(client: AsyncClient):
    import io

    resp = await client.post(
        "/assets",
        files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
    )
    assert resp.status_code == 400


async def test_list_assets(client: AsyncClient):
    img = fake_image_file("a.png")
    await client.post("/assets", files={"file": ("a.png", img, "image/png")})

    resp = await client.get("/assets")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_get_asset(client: AsyncClient):
    img = fake_image_file("b.png")
    created = await client.post(
        "/assets",
        files={"file": ("b.png", img, "image/png")},
    )
    asset_id = created.json()["id"]

    resp = await client.get(f"/assets/{asset_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == asset_id


async def test_get_asset_not_found(client: AsyncClient):
    resp = await client.get("/assets/9999")
    assert resp.status_code == 404
