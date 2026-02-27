# Copilot Instructions — NBP Lab

## Authoritative Source

[Implementation Blueprint.md](../Implementation%20Blueprint.md) is the single source of truth for architecture, schema, API contracts, and build order. Do not deviate from it. When in doubt, re-read the Blueprint.

## Project Overview

NBP Lab is a reproducible experiment engine for Nano Banana Pro (Gemini image generation). It designs controlled experiments, runs condition × repeat matrices, scores outputs, optionally captures telemetry, and exports auditable research bundles.

**Stack:** FastAPI · React (Vite) · PostgreSQL · SQLAlchemy (async, asyncpg) + Alembic · RQ (Redis Queue) background workers · Nano Banana Pro API · Gemini Vision API

## Technology Decisions

- **Worker:** RQ (Redis Queue) — simple, sync workers. Job functions live in `backend/app/services/runner.py`.
- **Frontend:** Vite + React (TypeScript). Created via `npm create vite@latest -- --template react-ts`.
- **Testing:** pytest + pytest-asyncio + httpx (async test client). Tests live in `backend/tests/`.
- **Config:** `pydantic-settings` reading from `.env` at repo root (`backend/app/config.py`). Frontend uses `frontend/.env` with `VITE_` prefix.
- **DB sessions:** Async `AsyncSession` for FastAPI routes. RQ workers use **sync** `Session` (RQ is not async).

## Repository Structure (Fixed)

```
nbpexperiments/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + CORS
│   │   ├── config.py         # pydantic-settings, reads .env
│   │   ├── db.py             # async engine, Base, get_db
│   │   ├── models/           # SQLAlchemy ORM (7 models)
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── routers/          # FastAPI route handlers
│   │   ├── services/         # All business logic
│   │   ├── telemetry/        # Telemetry extraction service
│   │   ├── qc/               # Gemini Reference QC service
│   │   ├── scoring/          # Scoring logic
│   │   └── export/           # Export bundle generator
│   ├── migrations/            # Alembic (env.py, versions/)
│   ├── tests/
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/src/{pages,components,api,utils}/
├── exports/
├── scripts/
├── .env                       # Not committed (.gitignore)
└── .gitignore
```

Do **not** invent additional top-level folders. Place all backend logic under `backend/app/`, all frontend code under `frontend/src/`.

## Critical Invariant — Telemetry Gating

`experiment.telemetry_enabled` is a hard boolean gate:

- **OFF →** No `RunTelemetry` rows created, no telemetry shown in UI, no telemetry files in exports. Zero leakage.
- **ON →** Store thought summaries, thought signatures, usage metadata, safety metadata, and parsed `ALLOCATION_REPORT`.

Every code path that touches telemetry (worker pipeline, API responses, export generation, frontend panels) **must** check this flag. If telemetry is OFF, the data must not exist in the database for that run.

## Domain Entities & Relationships

`Experiment → Condition → Run → Score`; `Asset → AssetQC` (Gemini analysis); `Run → RunTelemetry` (only when enabled).

- Each `Asset` must have an `AssetQC` row (via Gemini analysis) **before** an experiment run is allowed.
- `Run.status` enum: `queued | running | succeeded | failed` (Postgres enum `run_status_enum`).
- `AssetQC.role_guess` enum: `human_identity | object_fidelity | environment_plate | style_look | composition_pose | texture_material | mixed` (Postgres enum `role_guess_enum`).
- Scores are manual (identity, object, style, environment 1–10; hallucination boolean).
- All models use `from __future__ import annotations` + `TYPE_CHECKING` to avoid circular imports.

## API Design

All endpoints return structured JSON. Key routes:

- `POST /experiments` / `GET /experiments/{id}` — CRUD
- `POST /experiments/{id}/conditions` — add conditions
- `POST /experiments/{id}/run` — create runs and enqueue jobs
- `POST /runs/{id}/score` — submit scores
- `POST /assets` / `POST /assets/{id}/analyze` — upload & trigger Gemini QC
- `POST /experiments/{id}/export` — generate export bundle

## Background Worker Pipeline (RQ)

1. Create `Run` rows (status=queued) → 2. Enqueue jobs via `rq.Queue` → 3. Worker function in `services/runner.py` builds request, respects telemetry flag, calls Nano Banana Pro → 4. Store output image + latency → 5. If telemetry ON: store thought summary, signature, usage, safety, parse ALLOCATION_REPORT → 6. Update `Run.status`.

On API failure → `status = failed`. On safety block → store safety metadata only if telemetry ON. Invalid ALLOCATION_REPORT → store raw, mark `allocation_parse_status = "invalid"`.

## Build Order

Follow this sequence: DB schema + migrations → experiment/condition routes → asset upload → Reference QC service (Gemini) → runner + worker → telemetry logic → scoring → export bundle → frontend screens.

## Developer Workflow

```bash
# Install deps
pip install -r backend/requirements.txt

# Start Postgres + Redis (must be running)
# Create DB: createdb nbplab

# Migrations
cd /workspaces/nbpexperiments
alembic -c backend/alembic.ini revision --autogenerate -m "description"
alembic -c backend/alembic.ini upgrade head

# Run server
uvicorn backend.app.main:app --reload

# Run RQ worker
rq worker --url redis://localhost:6379/0

# Run tests
pytest backend/tests/
```

## Key Conventions

- **No business logic in frontend** — the React layer consumes the API; all domain logic lives in `backend/app/services/`.
- **Foreign keys enforced** in DB; index on `experiment_id`, `condition_id`, `run_id`, `asset_id`.
- **Export bundles** go to `exports/{experiment_name}/` with `manifest.json`, `scores.csv`, `image_grid.png`, run images, and telemetry files (only when ON).
- `manifest.json` must contain enough info (prompt, upload arrays, model, telemetry flag, timestamp) to reproduce the experiment structure.
