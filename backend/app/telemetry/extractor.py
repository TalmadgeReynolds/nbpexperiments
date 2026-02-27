"""Telemetry extraction service (Blueprint S10).

Parses raw thought summaries to extract:
- thought_signature  -- a stable hash that enables the "Context Locked" indicator
- ALLOCATION_REPORT  -- structured usage / percentages from the model's
                        internal allocation metadata
- allocation_analysis -- analysis of how the model weighted each uploaded image
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# -- Thought Signature -----------------------------------------------


def generate_thought_signature(thought_summary_raw: str | None) -> str | None:
    """Derive a stable signature from the raw thought summary.

    The signature is a truncated SHA-256 hash of the normalised text.  Two runs
    that produce byte-identical thought summaries will share the same signature,
    which is how the frontend determines "Context Locked" (i.e. the model's
    reasoning path was deterministic across repeats).

    Returns ``None`` when no thought summary is available.
    """
    if not thought_summary_raw or not thought_summary_raw.strip():
        return None

    # Normalise whitespace so trivial formatting differences don't change the hash
    normalised = " ".join(thought_summary_raw.split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:32]


# -- ALLOCATION_REPORT Parsing ----------------------------------------


_ALLOC_BLOCK_RE = re.compile(
    r"ALLOCATION_REPORT\s*[\n:]*\s*(\{.*?\})",
    re.DOTALL,
)


def parse_allocation_report(thought_text: str | None) -> dict[str, Any]:
    """Extract an ``ALLOCATION_REPORT`` JSON block from the thought text.

    Returns
    -------
    dict with keys:
        report : dict | None
            Parsed JSON if valid, ``{"raw": "<text>"}`` if invalid JSON, else None.
        status : "valid" | "invalid" | None
            Parse outcome.
    """
    if not thought_text:
        return {"report": None, "status": None}

    match = _ALLOC_BLOCK_RE.search(thought_text)
    if not match:
        return {"report": None, "status": None}

    raw = match.group(1)
    try:
        report = json.loads(raw)
        return {"report": report, "status": "valid"}
    except json.JSONDecodeError:
        return {"report": {"raw": raw}, "status": "invalid"}


# -- Telemetry Detail Extractions ------------------------------------


_SLOT_USAGE_RE = re.compile(
    r"slot[_\s]*usage\s*[:=]\s*(\d+)\s*/\s*(\d+)",
    re.IGNORECASE,
)
_PERCENTAGE_RE = re.compile(
    r"(\w[\w\s]*?)\s*[:=]\s*(\d+(?:\.\d+)?)\s*%",
)


def extract_telemetry_details(thought_text: str | None) -> dict[str, Any]:
    """Parse deeper telemetry extractions from the thought summary.

    Extracts:
    - ``slot_usage``  -- ``{"used": int, "total": int}`` or None
    - ``claimed_percentages`` -- ``{"label": float, ...}`` mapping

    These are persisted alongside the allocation report for richer analysis.
    """
    result: dict[str, Any] = {
        "slot_usage": None,
        "claimed_percentages": {},
    }

    if not thought_text:
        return result

    # Slot usage  (e.g. "slot_usage: 3 / 5")
    slot_match = _SLOT_USAGE_RE.search(thought_text)
    if slot_match:
        result["slot_usage"] = {
            "used": int(slot_match.group(1)),
            "total": int(slot_match.group(2)),
        }

    # Claimed percentages  (e.g. "identity: 45%", "background: 30%")
    for pct_match in _PERCENTAGE_RE.finditer(thought_text):
        label = pct_match.group(1).strip().lower()
        value = float(pct_match.group(2))
        result["claimed_percentages"][label] = value

    return result


# -- Allocation Analysis (observational, not prescriptive) -----------


def analyze_allocation(
    upload_order: list[int] | None,
    allocation_report: dict[str, Any] | None,
    claimed_percentages: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Analyze how the model allocated weight to uploaded images.

    This is purely OBSERVATIONAL -- we cannot control the model's internal
    allocation. This analysis helps researchers understand patterns like:
    - Which upload positions got more weight
    - Whether the model's allocation matches what we'd expect from QC roles
    - Category-level weight distribution

    Returns None if no useful data is available.
    """
    if not upload_order or not allocation_report:
        return None

    analysis: dict[str, Any] = {
        "upload_count": len(upload_order),
        "upload_order": upload_order,
        "position_weights": {},
        "category_claimed": {},
        "summary": "",
    }

    # Try to extract per-position weights from the allocation report
    weight_data: dict[int, float] = {}
    for key_source in ["slot_weights", "allocations", "weights"]:
        source = allocation_report.get(key_source, {})
        if isinstance(source, dict):
            for key, value in source.items():
                try:
                    pos = int("".join(c for c in str(key) if c.isdigit()))
                    weight_data[pos] = float(value)
                except (ValueError, TypeError):
                    pass

    if weight_data:
        analysis["position_weights"] = {
            f"position_{k}": v for k, v in sorted(weight_data.items())
        }

    # Extract category-level data from claimed percentages
    if claimed_percentages:
        for label, pct in claimed_percentages.items():
            label_lower = label.lower()
            if any(kw in label_lower for kw in ["character", "identity", "face"]):
                analysis["category_claimed"]["character"] = pct
            elif any(kw in label_lower for kw in ["object", "material", "texture"]):
                analysis["category_claimed"]["object"] = pct
            elif any(kw in label_lower for kw in ["world", "environment", "background", "light"]):
                analysis["category_claimed"]["world"] = pct

    # Build summary
    if weight_data:
        max_pos = max(weight_data, key=weight_data.get)
        analysis["summary"] = (
            f"Upload position {max_pos} received highest weight "
            f"({weight_data[max_pos]:.2f}). "
            f"{len(weight_data)} of {len(upload_order)} positions have weight data."
        )
    elif analysis["category_claimed"]:
        parts = [f"{k}: {v:.0f}%" for k, v in analysis["category_claimed"].items()]
        analysis["summary"] = f"Claimed category weights: {', '.join(parts)}"
    else:
        analysis["summary"] = (
            "No per-position weight data available in allocation report."
        )

    return analysis


# -- Convenience Wrapper ---------------------------------------------


def process_telemetry(
    thought_summary_raw: str | None,
    upload_order: list[int] | None = None,
) -> dict[str, Any]:
    """One-call convenience: returns all telemetry extraction fields.

    Keys returned:
        thought_signature, allocation_report, allocation_parse_status,
        slot_usage, claimed_percentages, allocation_analysis
    """
    signature = generate_thought_signature(thought_summary_raw)
    allocation = parse_allocation_report(thought_summary_raw)
    details = extract_telemetry_details(thought_summary_raw)

    # Allocation analysis (observational)
    allocation_analysis = None
    if upload_order and allocation["report"]:
        allocation_analysis = analyze_allocation(
            upload_order=upload_order,
            allocation_report=allocation["report"],
            claimed_percentages=details["claimed_percentages"],
        )

    return {
        "thought_signature": signature,
        "allocation_report": allocation["report"],
        "allocation_parse_status": allocation["status"],
        "slot_usage": details["slot_usage"],
        "claimed_percentages": details["claimed_percentages"],
        "allocation_analysis": allocation_analysis,
    }
