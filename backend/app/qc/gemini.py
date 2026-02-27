"""Reference QC analysis service — supports Gemini and Claude.

Sends a reference image to the chosen AI provider with a structured JSON schema
prompt.  Returns parsed fields that map directly to the AssetQC model columns.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.services.ai_client import Provider, call_vision

logger = logging.getLogger(__name__)

# ── Prompt that instructs the model to return structured analysis ───

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

VALID_ROLES = {
    "human_identity",
    "object_fidelity",
    "environment_plate",
    "style_look",
    "composition_pose",
    "texture_material",
    "mixed",
}


async def analyze_image(
    image_path: str,
    provider: str = "gemini",
) -> dict[str, Any]:
    """Send an image to the chosen AI provider and return structured QC analysis.

    Parameters
    ----------
    image_path : str
        Path to the image file on disk.
    provider : str
        ``"gemini"`` or ``"claude"``.

    Returns a dict with keys: role_guess, role_confidence, ambiguity_score,
    quality, face, environment, lighting, style.

    Raises ``RuntimeError`` on API or parsing failure.
    """
    ai_provider = Provider(provider)

    raw = await call_vision(
        ai_provider,
        ANALYSIS_PROMPT,
        image_path,
        temperature=0.1,
        max_tokens=4096,
    )

    # Parse JSON — strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse {provider} JSON response: {exc}\n"
            f"Raw (first 500 chars): {text[:500]}"
        )

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
