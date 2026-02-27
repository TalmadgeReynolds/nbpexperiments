"""Tests for the telemetry extraction service (Blueprint §10)."""

from __future__ import annotations

import pytest

from backend.app.telemetry.extractor import (
    extract_telemetry_details,
    generate_thought_signature,
    parse_allocation_report,
    process_telemetry,
)


# ── thought_signature ──────────────────────────────────────────────


class TestThoughtSignature:
    def test_none_input(self):
        assert generate_thought_signature(None) is None

    def test_empty_string(self):
        assert generate_thought_signature("") is None

    def test_whitespace_only(self):
        assert generate_thought_signature("   \n\t  ") is None

    def test_returns_32_char_hex(self):
        sig = generate_thought_signature("The model considered identity fidelity.")
        assert sig is not None
        assert len(sig) == 32
        assert all(c in "0123456789abcdef" for c in sig)

    def test_deterministic(self):
        text = "Same thought summary across repeats"
        assert generate_thought_signature(text) == generate_thought_signature(text)

    def test_normalises_whitespace(self):
        a = generate_thought_signature("hello   world")
        b = generate_thought_signature("hello world")
        assert a == b

    def test_different_text_different_sig(self):
        a = generate_thought_signature("thought A")
        b = generate_thought_signature("thought B")
        assert a != b


# ── ALLOCATION_REPORT parsing ──────────────────────────────────────


class TestParseAllocationReport:
    def test_no_report(self):
        result = parse_allocation_report("Just some text with no report.")
        assert result == {"report": None, "status": None}

    def test_none_input(self):
        result = parse_allocation_report(None)
        assert result == {"report": None, "status": None}

    def test_valid_report(self):
        text = (
            'Thinking about slots.\n'
            'ALLOCATION_REPORT\n'
            '{"slot_a": 40, "slot_b": 60}\n'
            'End of thoughts.'
        )
        result = parse_allocation_report(text)
        assert result["status"] == "valid"
        assert result["report"] == {"slot_a": 40, "slot_b": 60}

    def test_invalid_json(self):
        text = 'ALLOCATION_REPORT\n{not valid json}'
        result = parse_allocation_report(text)
        assert result["status"] == "invalid"
        assert "raw" in result["report"]

    def test_report_with_colon(self):
        text = 'ALLOCATION_REPORT: {"identity": 50}'
        result = parse_allocation_report(text)
        assert result["status"] == "valid"
        assert result["report"]["identity"] == 50


# ── telemetry_extractions ─────────────────────────────────────────


class TestExtractTelemetryDetails:
    def test_none_input(self):
        result = extract_telemetry_details(None)
        assert result["slot_usage"] is None
        assert result["claimed_percentages"] == {}

    def test_slot_usage(self):
        text = "Allocated resources. slot_usage: 3 / 5. Done."
        result = extract_telemetry_details(text)
        assert result["slot_usage"] == {"used": 3, "total": 5}

    def test_claimed_percentages(self):
        text = "identity: 45%\nbackground: 30%\nstyle: 25%"
        result = extract_telemetry_details(text)
        pcts = result["claimed_percentages"]
        assert pcts["identity"] == 45.0
        assert pcts["background"] == 30.0
        assert pcts["style"] == 25.0

    def test_no_telemetry_data(self):
        result = extract_telemetry_details("Nothing interesting here.")
        assert result["slot_usage"] is None
        assert result["claimed_percentages"] == {}


# ── process_telemetry (convenience wrapper) ────────────────────────


class TestProcessTelemetry:
    def test_full_pipeline(self):
        text = (
            "Thinking about identity: 60%\n"
            "slot_usage: 2 / 4\n"
            "ALLOCATION_REPORT\n"
            '{"identity": 60, "style": 40}\n'
            "End."
        )
        result = process_telemetry(text)
        assert result["thought_signature"] is not None
        assert result["allocation_parse_status"] == "valid"
        assert result["allocation_report"]["identity"] == 60
        assert result["slot_usage"] == {"used": 2, "total": 4}
        assert result["claimed_percentages"]["identity"] == 60.0

    def test_none_input(self):
        result = process_telemetry(None)
        assert result["thought_signature"] is None
        assert result["allocation_report"] is None
        assert result["allocation_parse_status"] is None
