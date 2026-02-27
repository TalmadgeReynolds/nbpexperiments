"""Gemini Vision Reference QC service.

Sends a reference image to the Gemini Vision API with a structured JSON schema
prompt.  Returns parsed fields that map directly to the AssetQC model columns.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)

# ── Prompt that instructs Gemini to return structured analysis ──────

ANALYSIS_PROMPT = """\
You are an image analysis system for a controlled experiment engine.
Analyze this reference image and return ONLY a JSON object with the following structure.
Do not include any text outside the JSON block.

{
  "role_guess": "<one of: human_identity, object_fidelity, environment_plate, style_look, composition_pose, texture_material, mixed>",
  "role_confidence": <float 0-1>,
  "ambiguity_score": <float 0-1>,
  "ambiguity_explanation": "<brief string>",
  "quality": {
    "sharpness_level": "<low|medium|high>",
    "motion_blur": <true|false>,
    "compression_artifacts": "<none|minor|major>",
    "lighting_quality": "<poor|adequate|good|excellent>",
    "occlusion": "<none|partial|significant>",
    "noise_level": "<low|medium|high>",
    "resolution_px": [<width>, <height>],
    "subject_size_ratio": <float 0-1>
  },
  "face": {
    "faces_count": <int>,
    "dominant_face_count": <int>,
    "head_angle": "<frontal|three_quarter|profile|back>",
    "face_visibility": "<full|partial|obscured|none>",
    "distinctive_features_present": <true|false>
  },
  "environment": {
    "environment_type": "<indoor|outdoor|studio|abstract|mixed>",
    "camera_height_guess": "<low|eye_level|high|overhead>",
    "lens_feel": "<wide|normal|telephoto|macro>",
    "perspective_strength": "<weak|moderate|strong>",
    "vanishing_lines_visible": <true|false>
  },
  "lighting": {
    "key_light_direction": "<left|right|front|back|top|ambient>",
    "shadow_hardness": "<soft|medium|hard>",
    "time_of_day_guess": "<morning|midday|golden_hour|blue_hour|night|studio|unknown>",
    "color_temperature": "<warm|neutral|cool>",
    "contrast_level": "<low|medium|high>"
  },
  "style": {
    "style_family": "<photorealistic|cinematic|illustration|painterly|graphic|mixed>",
    "grade_notes": "<brief string>",
    "grain_presence": <true|false>,
    "palette_summary": "<brief string>"
  }
}
"""

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

VALID_ROLES = {
    "human_identity",
    "object_fidelity",
    "environment_plate",
    "style_look",
    "composition_pose",
    "texture_material",
    "mixed",
}


async def analyze_image(image_path: str) -> dict[str, Any]:
    """Send an image to Gemini Vision and return structured QC analysis.

    Returns a dict with keys: role_guess, role_confidence, ambiguity_score,
    quality, face, environment, lighting, style.

    Raises ``RuntimeError`` on API or parsing failure.
    """
    path = Path(image_path)
    if not path.exists():
        raise RuntimeError(f"Image file not found: {image_path}")

    image_bytes = path.read_bytes()
    b64_image = base64.b64encode(image_bytes).decode()

    # Determine MIME type from extension
    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime_type = mime_map.get(suffix, "image/png")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": ANALYSIS_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_image,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        },
    }

    api_key = settings.gemini_api_key
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set — cannot run Reference QC analysis"
        )

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{GEMINI_API_URL}?key={api_key}",
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Gemini API error {resp.status_code}: {resp.text[:500]}"
        )

    # Extract text from response
    body = resp.json()
    try:
        text = body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response structure: {exc}")

    # Parse JSON — strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        # Remove ```json ... ``` wrapper
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse Gemini JSON response: {exc}\nRaw: {text[:500]}")

    return _normalize(data)


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate the parsed Gemini response into AssetQC fields."""
    role = data.get("role_guess", "mixed")
    if role not in VALID_ROLES:
        role = "mixed"

    return {
        "role_guess": role,
        "role_confidence": _clamp(data.get("role_confidence"), 0.0, 1.0),
        "ambiguity_score": _clamp(data.get("ambiguity_score"), 0.0, 1.0),
        "quality_json": data.get("quality"),
        "face_json": data.get("face"),
        "environment_json": data.get("environment"),
        "lighting_json": data.get("lighting"),
        "style_json": data.get("style"),
    }


def _clamp(value: Any, lo: float, hi: float) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
        return max(lo, min(hi, v))
    except (TypeError, ValueError):
        return None
