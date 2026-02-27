"""Telemetry extraction service (Blueprint §10).

Parses raw thought summaries to extract:
- thought_signature  — a stable hash that enables the "Context Locked" indicator
- ALLOCATION_REPORT  — structured slot usage / percentages from the model's
                        internal allocation metadata
- telemetry_extractions — claimed slot usage and percentages
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── Thought Signature ──────────────────────────────────────────────


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


# ── ALLOCATION_REPORT Parsing ──────────────────────────────────────


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


# ── Telemetry Extractions ─────────────────────────────────────────


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
    - ``slot_usage``  — ``{"used": int, "total": int}`` or None
    - ``claimed_percentages`` — ``{"label": float, …}`` mapping

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


# ── Convenience Wrapper ────────────────────────────────────────────


def process_telemetry(thought_summary_raw: str | None) -> dict[str, Any]:
    """One-call convenience: returns all telemetry extraction fields.

    Keys returned:
        thought_signature, allocation_report, allocation_parse_status,
        slot_usage, claimed_percentages
    """
    signature = generate_thought_signature(thought_summary_raw)
    allocation = parse_allocation_report(thought_summary_raw)
    details = extract_telemetry_details(thought_summary_raw)

    return {
        "thought_signature": signature,
        "allocation_report": allocation["report"],
        "allocation_parse_status": allocation["status"],
        "slot_usage": details["slot_usage"],
        "claimed_percentages": details["claimed_percentages"],
    }
