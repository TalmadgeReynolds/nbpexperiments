"""Reference image utilities for Nano Banana Pro.

IMPORTANT: The Gemini API does NOT support explicit slot targeting.
You simply pass images as an ordered list in the `contents` array.
The MODEL decides how to interpret each image (character, object,
environment) based on the image content and prompt context.

What we CAN control:
- Which images to include (selection)
- The ORDER in which images are sent (upload position)
- The text prompt (how we describe the images)

What we CANNOT control:
- Which internal "slot" or weight bucket the model assigns each image to
- The model's internal allocation of identity vs. object vs. world weight

The model's ALLOCATION_REPORT (visible via telemetry/thinking) reveals
how it actually weighted each uploaded image — this is valuable for
experiments but is an OBSERVATION, not something we can prescribe.

Limits (from Google docs):
- Gemini 3 Pro Image: up to 5 character + up to 10 object = 14 total
- Gemini 3.1 Flash:   up to 4 character + up to 6 object  = 10 total

This module provides:
- QC role -> category mapping (advisory, for display)
- Recommendation engine (suggest good upload order)
- Upload plan parsing (for backward compat with DB data)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# -- Reference Image Categories (advisory, model-determined) -------

class RefCategory(str, Enum):
    """Categories the model may internally assign to reference images.
    These are advisory -- we cannot force the model's assignment."""
    CHARACTER = "character"
    OBJECT = "object"
    WORLD = "world"


# Max reference images
MAX_REF_IMAGES = 14

# Category limits (from Google docs -- model-enforced, not slot-enforced)
CATEGORY_LIMITS: dict[RefCategory, dict[str, int]] = {
    RefCategory.CHARACTER: {"gemini-3-pro-image-preview": 5, "gemini-3.1-flash": 4},
    RefCategory.OBJECT: {"gemini-3-pro-image-preview": 10, "gemini-3.1-flash": 6},
    RefCategory.WORLD: {"gemini-3-pro-image-preview": 3, "gemini-3.1-flash": 3},
}

# Human-readable labels
CATEGORY_LABELS: dict[RefCategory, str] = {
    RefCategory.CHARACTER: "Character (identity anchors -- faces, bodies)",
    RefCategory.OBJECT: "Object (materials, textures, props)",
    RefCategory.WORLD: "World (lighting, background, environment)",
}


# -- QC Role -> Category Mapping (advisory) -------------------------

ROLE_TO_CATEGORY: dict[str, RefCategory] = {
    "human_identity": RefCategory.CHARACTER,
    "object_fidelity": RefCategory.OBJECT,
    "texture_material": RefCategory.OBJECT,
    "environment_plate": RefCategory.WORLD,
    "style_look": RefCategory.WORLD,
    "composition_pose": RefCategory.CHARACTER,
    "mixed": RefCategory.OBJECT,
}


# -- Recommendation Engine ------------------------------------------


def recommend_upload_order(
    assets_with_qc: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Given assets with QC data, suggest a good upload order.

    The recommendation groups images by likely category (character first,
    then object, then world) which tends to produce better results --
    but this is heuristic, not guaranteed.

    Parameters
    ----------
    assets_with_qc : list of dicts with keys:
        - id: int
        - role_guess: str (from AssetQC)
        - role_confidence: float

    Returns
    -------
    List of dicts:
        - asset_id: int
        - role_guess: str
        - likely_category: str (character/object/world)
        - confidence: float
        - position: int (suggested upload position, 1-indexed)
        - note: str | None
    """
    # Bucket by category
    buckets: dict[RefCategory, list[dict[str, Any]]] = {
        RefCategory.CHARACTER: [],
        RefCategory.OBJECT: [],
        RefCategory.WORLD: [],
    }

    for asset in assets_with_qc:
        role = asset.get("role_guess", "mixed")
        category = ROLE_TO_CATEGORY.get(role, RefCategory.OBJECT)
        buckets[category].append(asset)

    # Sort within each bucket by confidence (highest first)
    for cat in buckets:
        buckets[cat].sort(key=lambda a: a.get("role_confidence", 0.0), reverse=True)

    # Build ordered recommendation: characters first, then objects, then world
    recommendations: list[dict[str, Any]] = []
    position = 1
    order = [RefCategory.CHARACTER, RefCategory.OBJECT, RefCategory.WORLD]

    for cat in order:
        for asset in buckets[cat]:
            note = None
            confidence = asset.get("role_confidence", 0.0)
            if confidence < 0.5:
                note = f"Low confidence ({confidence:.0%}) -- verify role manually."

            recommendations.append({
                "asset_id": asset["id"],
                "role_guess": asset.get("role_guess", "mixed"),
                "likely_category": cat.value,
                "confidence": confidence,
                "position": position,
                "note": note,
            })
            position += 1

    return recommendations


# -- Upload Plan Parsing ---------------------------------------------


def parse_upload_plan(raw: Any) -> list[int] | None:
    """Parse an upload_plan from the database (JSON column).

    Handles:
    - New format: flat list of asset IDs [1, 2, 3]
    - Legacy slot-aware format: [{"slot": 1, "asset_id": 7}, ...] -> extract asset_ids in slot order

    Returns ordered list of asset IDs, or None if empty.
    """
    if raw is None:
        return None

    if isinstance(raw, list) and len(raw) == 0:
        return None

    # Legacy slot-aware format: list of dicts with slot/asset_id
    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        # Sort by slot number (or position) and extract asset_ids
        sorted_items = sorted(raw, key=lambda x: x.get("slot", x.get("position", 0)))
        return [int(item["asset_id"]) for item in sorted_items if "asset_id" in item]

    # Flat list of asset IDs (current format)
    if isinstance(raw, list) and raw and isinstance(raw[0], (int, float)):
        return [int(x) for x in raw]

    logger.warning("Unrecognized upload_plan format: %s", type(raw))
    return None


def get_ref_image_info() -> dict[str, Any]:
    """Return reference image info for API responses and advisor context."""
    return {
        "max_images": MAX_REF_IMAGES,
        "note": (
            "The Gemini API accepts up to 14 reference images as an ordered list. "
            "You cannot select which internal slot each image goes into -- the model "
            "determines that based on image content and prompt context. "
            "Upload ORDER may influence how the model prioritizes images."
        ),
        "category_limits": {
            cat.value: limits
            for cat, limits in CATEGORY_LIMITS.items()
        },
        "categories": {
            cat.value: label
            for cat, label in CATEGORY_LABELS.items()
        },
        "role_to_category": {
            role: cat.value for role, cat in ROLE_TO_CATEGORY.items()
        },
    }
