"""Export bundle generator.

Produces a self-contained folder under ``exports/<experiment_name>/`` with:
- manifest.json  – enough metadata to reproduce the experiment structure
- scores.csv     – all scored runs
- image_grid.png – contact-sheet of output images
- runs/          – individual run output images
- telemetry_appendix.csv  (only when telemetry ON)
- allocation_reports.jsonl (only when telemetry ON)
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from PIL import Image

from backend.app.models.condition import Condition
from backend.app.models.experiment import Experiment
from backend.app.models.run import Run
from backend.app.models.run_telemetry import RunTelemetry
from backend.app.models.score import Score


# ── helpers ────────────────────────────────────────────────────────


def _safe_name(name: str) -> str:
    """Sanitise an experiment/condition name for use as a filesystem path."""
    return "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name).strip()


def _copy_image(src: str | None, dst: Path) -> bool:
    """Copy a run output image into the bundle.  Returns True on success."""
    if not src:
        return False
    src_path = Path(src)
    if not src_path.exists():
        return False
    shutil.copy2(src_path, dst)
    return True


def _build_image_grid(image_paths: list[Path], dst: Path, thumb: int = 256) -> None:
    """Create a contact-sheet grid of thumbnails and save to *dst*."""
    valid = [p for p in image_paths if p.exists()]
    if not valid:
        # Create a 1×1 placeholder so the file exists
        img = Image.new("RGB", (thumb, thumb), (200, 200, 200))
        img.save(dst)
        return

    cols = min(len(valid), 4)
    rows = (len(valid) + cols - 1) // cols
    grid = Image.new("RGB", (cols * thumb, rows * thumb), (240, 240, 240))

    for idx, path in enumerate(valid):
        try:
            im = Image.open(path)
            im.thumbnail((thumb, thumb))
            x = (idx % cols) * thumb
            y = (idx // cols) * thumb
            grid.paste(im, (x, y))
        except Exception:
            pass  # skip corrupt images

    grid.save(dst)


# ── main entry point ──────────────────────────────────────────────


def generate_export_bundle(
    experiment: Experiment,
    conditions: Sequence[Condition],
    runs: Sequence[Run],
    scores: dict[int, Score],
    telemetry: dict[int, RunTelemetry],
    export_root: str | Path,
) -> Path:
    """Build the full export bundle and return the bundle directory path.

    Parameters
    ----------
    experiment : Experiment
    conditions : list of Condition (each with runs already loaded)
    runs       : flat list of all Run objects for this experiment
    scores     : {run_id: Score} mapping
    telemetry  : {run_id: RunTelemetry} mapping (empty if telemetry OFF)
    export_root: root export directory (e.g. ``exports/``)
    """
    export_root = Path(export_root)
    bundle_name = _safe_name(experiment.name)
    bundle_dir = export_root / bundle_name
    runs_dir = bundle_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Copy run images into runs/ ──────────────────────────────
    grid_sources: list[Path] = []
    for run in runs:
        cond = next((c for c in conditions if c.id == run.condition_id), None)
        cond_label = _safe_name(cond.name) if cond else f"cond{run.condition_id}"
        img_name = f"{cond_label}_run{run.repeat_index}.png"
        dst = runs_dir / img_name
        if _copy_image(run.output_image_path, dst):
            grid_sources.append(dst)

    # ── 2. image_grid.png ──────────────────────────────────────────
    _build_image_grid(grid_sources, bundle_dir / "image_grid.png")

    # ── 3. scores.csv ─────────────────────────────────────────────
    _write_scores_csv(bundle_dir / "scores.csv", conditions, runs, scores)

    # ── 4. Telemetry files (only when enabled) ─────────────────────
    if experiment.telemetry_enabled and telemetry:
        _write_telemetry_appendix(bundle_dir / "telemetry_appendix.csv", conditions, runs, telemetry)
        _write_allocation_reports(bundle_dir / "allocation_reports.jsonl", runs, telemetry)

    # ── 5. manifest.json ──────────────────────────────────────────
    _write_manifest(bundle_dir / "manifest.json", experiment, conditions, runs)

    return bundle_dir


# ── file writers ──────────────────────────────────────────────────


def _write_scores_csv(
    path: Path,
    conditions: Sequence[Condition],
    runs: Sequence[Run],
    scores: dict[int, Score],
) -> None:
    cond_map = {c.id: c for c in conditions}
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id", "condition", "repeat_index", "status",
            "identity", "object", "style", "environment",
            "hallucination", "notes",
        ])
        for run in runs:
            cond = cond_map.get(run.condition_id)
            score = scores.get(run.id)
            writer.writerow([
                run.id,
                cond.name if cond else "",
                run.repeat_index,
                run.status.value if hasattr(run.status, "value") else run.status,
                score.identity_score if score else "",
                score.object_score if score else "",
                score.style_score if score else "",
                score.environment_score if score else "",
                score.hallucination if score else "",
                score.notes if score else "",
            ])


def _write_telemetry_appendix(
    path: Path,
    conditions: Sequence[Condition],
    runs: Sequence[Run],
    telemetry: dict[int, RunTelemetry],
) -> None:
    cond_map = {c.id: c for c in conditions}
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id", "condition", "repeat_index",
            "thought_signature", "thinking_level", "latency_ms",
            "allocation_parse_status", "thought_summary_raw",
        ])
        for run in runs:
            t = telemetry.get(run.id)
            if not t:
                continue
            cond = cond_map.get(run.condition_id)
            writer.writerow([
                run.id,
                cond.name if cond else "",
                run.repeat_index,
                t.thought_signature or "",
                t.thinking_level or "",
                t.latency_ms or "",
                t.allocation_parse_status or "",
                (t.thought_summary_raw or "")[:500],  # truncate for CSV sanity
            ])


def _write_allocation_reports(
    path: Path,
    runs: Sequence[Run],
    telemetry: dict[int, RunTelemetry],
) -> None:
    with open(path, "w") as f:
        for run in runs:
            t = telemetry.get(run.id)
            if not t or not t.allocation_report_json:
                continue
            record = {
                "run_id": run.id,
                "allocation_parse_status": t.allocation_parse_status,
                "allocation_report": t.allocation_report_json,
            }
            f.write(json.dumps(record) + "\n")


def _write_manifest(
    path: Path,
    experiment: Experiment,
    conditions: Sequence[Condition],
    runs: Sequence[Run],
) -> None:
    manifest = {
        "experiment_name": experiment.name,
        "hypothesis": experiment.hypothesis,
        "model": experiment.model_name,
        "telemetry_enabled": experiment.telemetry_enabled,
        "render_settings": experiment.render_settings,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conditions": [
            {
                "name": c.name,
                "prompt": c.prompt,
                "upload_plan": c.upload_plan,
            }
            for c in conditions
        ],
        "run_count": len(runs),
    }
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
