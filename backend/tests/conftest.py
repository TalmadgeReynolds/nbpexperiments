"""Shared test fixtures for NBP Lab tests.

Uses an in-memory SQLite database with async support so tests run without
PostgreSQL.  The async engine + session override FastAPI's ``get_db`` dep.
"""

from __future__ import annotations

import asyncio
import io
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db import Base, get_db
from backend.app.main import app

# We need all models imported so Base.metadata knows every table.
import backend.app.models  # noqa: F401

# ── Async engine (SQLite in-memory) ────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Override the default event-loop fixture to session scope."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop them after."""
    # SQLite doesn't support Postgres-specific types (Enum) natively.
    # SQLAlchemy renders them as VARCHAR for SQLite, which is fine for tests.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh async session for direct DB manipulation in tests."""
    async with TestingSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with the DB dependency overridden."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Convenience helpers ────────────────────────────────────────────


async def create_experiment(client: AsyncClient, **overrides) -> dict:
    """POST a new experiment and return the JSON body."""
    payload = {
        "name": overrides.get("name", "Test Experiment"),
        "hypothesis": overrides.get("hypothesis", "Testing hypothesis"),
        "telemetry_enabled": overrides.get("telemetry_enabled", False),
        "model_name": overrides.get("model_name", "nano-banana-pro"),
        "render_settings": overrides.get("render_settings", None),
    }
    resp = await client.post("/experiments", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_condition(client: AsyncClient, experiment_id: int, **overrides) -> dict:
    """POST a new condition and return the JSON body."""
    payload = {
        "name": overrides.get("name", "Condition A"),
        "prompt": overrides.get("prompt", "A banana on a table"),
        "upload_plan": overrides.get("upload_plan", None),
    }
    resp = await client.post(f"/experiments/{experiment_id}/conditions", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def fake_image_file(filename: str = "test.png", size: int = 128) -> io.BytesIO:
    """Return a minimal PNG-like byte stream for upload tests."""
    # Minimal valid PNG: 8-byte signature + IHDR + IEND
    # For tests we just need non-empty bytes; the API doesn't validate image format.
    import struct

    buf = io.BytesIO()
    # PNG signature
    buf.write(b"\x89PNG\r\n\x1a\n")
    # Minimal IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    buf.write(struct.pack(">I", len(ihdr_data)))
    buf.write(b"IHDR")
    buf.write(ihdr_data)
    import zlib

    crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    buf.write(struct.pack(">I", crc))
    # IEND chunk
    buf.write(struct.pack(">I", 0))
    buf.write(b"IEND")
    crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    buf.write(struct.pack(">I", crc))
    buf.seek(0)
    return buf
