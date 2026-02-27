"""Tests for the export bundle generator and download endpoint."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.export.exporter import generate_export_bundle
from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.models.run import Run, RunStatusEnum
from backend.app.models.run_telemetry import RunTelemetry
from backend.app.models.score import Score

pytestmark = pytest.mark.asyncio

TMP_EXPORT = Path("/tmp/nbplab_test_exports")


@pytest.fixture(autouse=True)
def clean_export_dir():
    """Ensure a clean temp export directory for each test."""
    if TMP_EXPORT.exists():
        shutil.rmtree(TMP_EXPORT)
    TMP_EXPORT.mkdir(parents=True, exist_ok=True)
    yield
    if TMP_EXPORT.exists():
        shutil.rmtree(TMP_EXPORT)


# ── Unit: generate_export_bundle ───────────────────────────────────


def _make_objects():
    """Create in-memory domain objects (no DB needed)."""
    exp = Experiment.__new__(Experiment)
    exp.id = 1
    exp.name = "Export Test"
    exp.hypothesis = "H1"
    exp.model_name = "nano-banana-pro"
    exp.telemetry_enabled = False
    exp.render_settings = None

    cond = Condition.__new__(Condition)
    cond.id = 10
    cond.experiment_id = 1
    cond.name = "Cond A"
    cond.prompt = "A banana"
    cond.upload_plan = None

    run = Run.__new__(Run)
    run.id = 100
    run.condition_id = 10
    run.repeat_index = 0
    run.status = RunStatusEnum.succeeded
    run.output_image_path = None
    run.latency_ms = 1200

    return exp, [cond], [run]


def test_generate_bundle_creates_manifest():
    exp, conds, runs = _make_objects()
    bundle = generate_export_bundle(
        experiment=exp,
        conditions=conds,
        runs=runs,
        scores={},
        telemetry={},
        export_root=TMP_EXPORT,
    )
    assert bundle.exists()
    manifest_path = bundle / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["experiment_name"] == "Export Test"
    assert manifest["model"] == "nano-banana-pro"
    assert manifest["telemetry_enabled"] is False
    assert manifest["run_count"] == 1


def test_generate_bundle_creates_scores_csv():
    exp, conds, runs = _make_objects()

    score = Score.__new__(Score)
    score.identity_score = 8
    score.object_score = 7
    score.style_score = 9
    score.environment_score = 6
    score.hallucination = False
    score.notes = "Good"

    bundle = generate_export_bundle(
        experiment=exp,
        conditions=conds,
        runs=runs,
        scores={100: score},
        telemetry={},
        export_root=TMP_EXPORT,
    )
    csv_path = bundle / "scores.csv"
    assert csv_path.exists()
    lines = csv_path.read_text().strip().split("\n")
    assert len(lines) == 2  # header + 1 data row
    assert "8" in lines[1]  # identity_score


def test_generate_bundle_no_telemetry_files_when_off():
    exp, conds, runs = _make_objects()
    exp.telemetry_enabled = False

    bundle = generate_export_bundle(
        experiment=exp,
        conditions=conds,
        runs=runs,
        scores={},
        telemetry={},
        export_root=TMP_EXPORT,
    )
    assert not (bundle / "telemetry_appendix.csv").exists()
    assert not (bundle / "allocation_reports.jsonl").exists()


def test_generate_bundle_with_telemetry():
    exp, conds, runs = _make_objects()
    exp.telemetry_enabled = True

    telem = RunTelemetry.__new__(RunTelemetry)
    telem.run_id = 100
    telem.thought_summary_raw = "Model thought about banana"
    telem.thought_signature = "abc123"
    telem.thinking_level = "medium"
    telem.latency_ms = 1200
    telem.allocation_report_json = {"slot_a": 60}
    telem.allocation_parse_status = "valid"

    bundle = generate_export_bundle(
        experiment=exp,
        conditions=conds,
        runs=runs,
        scores={},
        telemetry={100: telem},
        export_root=TMP_EXPORT,
    )
    assert (bundle / "telemetry_appendix.csv").exists()
    assert (bundle / "allocation_reports.jsonl").exists()

    # Verify allocation report content
    jsonl = (bundle / "allocation_reports.jsonl").read_text().strip()
    record = json.loads(jsonl)
    assert record["run_id"] == 100
    assert record["allocation_parse_status"] == "valid"


# ── Integration: export download endpoint ──────────────────────────


async def test_export_experiment_not_found(client: AsyncClient):
    resp = await client.post("/experiments/9999/export")
    assert resp.status_code == 404


async def test_export_no_conditions(client: AsyncClient):
    # Create an experiment with no conditions
    resp = await client.post("/experiments", json={
        "name": "Empty Exp", "hypothesis": "H",
    })
    exp_id = resp.json()["id"]

    resp = await client.post(f"/experiments/{exp_id}/export")
    assert resp.status_code == 400
    assert "no conditions" in resp.json()["detail"].lower()


async def test_download_zip_not_found(client: AsyncClient):
    resp = await client.post("/experiments", json={
        "name": "No Export Yet", "hypothesis": "H",
    })
    exp_id = resp.json()["id"]

    resp = await client.get(f"/experiments/{exp_id}/export/download")
    assert resp.status_code == 404
