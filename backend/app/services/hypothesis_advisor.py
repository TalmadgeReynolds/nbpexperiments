"""Hypothesis Advisor -- AI-powered condition suggestion service.

Two-step conversational flow:
1. ``generate_questions``  -- reads the hypothesis, returns clarifying questions
2. ``suggest_conditions``  -- takes the hypothesis + answers -> suggests conditions

Optional post-step:
3. ``generate_order_permutations``  -- takes existing conditions and creates
   upload-order variants as a separate toggleable feature.

Both steps call the chosen AI provider (Gemini or Claude) with structured
JSON-output prompts.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from backend.app.services.ai_client import Provider, call_text

logger = logging.getLogger(__name__)

# -- Official NBP prompt template ------------------------------------

NBP_PROMPT_TEMPLATE = (
    'A photorealistic [shot type] of [subject], [action or expression], '
    'set in [environment]. The scene is illuminated by [lighting description], '
    'creating a [mood] atmosphere. Captured with [camera/lens details], '
    'emphasizing [key textures and details].'
)

# -- Prompts ---------------------------------------------------------

QUESTIONS_SYSTEM = """\
You are a senior experiment designer for a controlled AI image-generation lab.
The model under test is Google Gemini's image generation ("Nano Banana Pro").

CONTEXT -- REFERENCE IMAGE SYSTEM:
Nano Banana Pro accepts up to 14 reference images as an ordered list.
The model decides how to interpret each image (character, object,
environment) based on the image content and prompt context.
Limits: up to 5 character refs + up to 10 object refs = 14 total.

The user gives you a HYPOTHESIS.  Your job is to ask 3-5 sharp, specific
clarifying questions that will let you build a rigorous condition matrix.

Rules for questions:
- Each question must target ONE concrete experimental variable.
- Focus on the variables most relevant to the hypothesis.  Common
  experimental variables include:
  * PROMPT WORDING: scene description, subject details, style keywords,
    level of detail, composition instructions, negative prompts
  * IMAGE SELECTION: which specific reference images to include, how many
  * STYLE & COMPOSITION: artistic direction, camera angle, lighting,
    color palette, aspect ratio
  * SUBJECT VARIATION: character pose, expression, outfit, environment
  * GENERATION SETTINGS: aspect ratio, model parameters
- Questions must be SPECIFIC to this hypothesis -- never generic.
  BAD: "What style do you want?"  GOOD: "Should the identity test use
  close-up or full-body framing to measure face fidelity?"
- Do NOT ask about upload order unless the hypothesis is specifically
  about testing how image ordering affects results.  Upload-order
  permutation is handled as a separate feature.
- Offer 2-4 concrete options when useful, but phrase them as real
  experimental values (not vague categories).
- The answers will be used to write EXACT generation prompts and
  reference image lists.

Return ONLY a JSON array:
[
  {
    "id": "q1",
    "question": "Specific question text",
    "why": "Why this variable matters for isolating the hypothesis",
    "options": ["concrete option A", "concrete option B"] // or null
  }
]
"""

CONDITIONS_SYSTEM = """\
You are a senior experiment designer for a controlled AI image-generation lab.
The model is Google Gemini image generation ("Nano Banana Pro").

CONTEXT -- REFERENCE IMAGE SYSTEM:
Nano Banana Pro accepts up to 14 reference images as an ordered list.
The model decides how to interpret each image based on image content
and prompt context.
Limits: up to 5 character + up to 10 object = 14 total references.

Given a HYPOTHESIS and the user's ANSWERS to clarifying questions, produce
a set of experimental conditions that rigorously test the hypothesis.

FOCUS ON THE HYPOTHESIS.  Common experimental variables include:
- PROMPT WORDING: scene description, subject details, style keywords,
  composition instructions, negative prompts, level of detail
- IMAGE SELECTION: which specific images to include, how many
- MIX RATIO: proportion of character vs. object vs. world images
- STYLE & COMPOSITION: artistic direction, framing, lighting, color
- SUBJECT VARIATION: pose, expression, outfit, environment context
- GENERATION SETTINGS: aspect ratio, model parameters

Do NOT make upload order the primary variable unless the hypothesis
specifically asks about testing image ordering effects.  Upload-order
permutations are handled as a separate post-processing feature.

MANDATORY PROMPT TEMPLATE:
All generation prompts MUST follow this exact structure:
"A photorealistic [shot type] of [subject], [action or expression],
set in [environment]. The scene is illuminated by [lighting description],
creating a [mood] atmosphere. Captured with [camera/lens details],
emphasizing [key textures and details]."
Fill in every bracket with specific, concrete values for each condition.
Do NOT deviate from this structure or invent a different sentence pattern.

CRITICAL RULES:
1. EVERY condition must have a UNIQUE, SPECIFIC generation prompt using
   the template above -- fill the brackets differently for each condition,
   not minor rephrasing of the same values.
2. Exactly ONE variable should change between conditions.  State which
   variable in the rationale.
3. Include one CONTROL / BASELINE condition that represents the default
   behavior.
4. Prompts must be COMPLETE, READY-TO-SEND text following the template.
5. Each condition name must clearly label what is being varied
   (e.g. "Close-up framing" vs "Full-body framing" or
   "3 character refs" vs "1 character ref").
6. 4-6 conditions.  Prefer fewer sharp conditions over many vague ones.
7. upload_plan MUST be a flat ordered list of integer asset IDs:
   [7, 12, 3, 1, 5, ...]
   DEFAULT: include ALL available asset IDs in every condition.
   Only omit assets when the hypothesis specifically tests count.
8. Include a ref_strategy field explaining the reference image choices
   for this condition.

Return ONLY a JSON array:
[
  {
    "name": "Descriptive label showing the variable value",
    "prompt": "The full, specific generation prompt",
    "rationale": "Which variable this tests and why",
    "upload_plan": [7, 12, 3],
    "ref_strategy": "Explanation of ref image choices for this condition"
  }
]

IMPORTANT: upload_plan must be a flat list of integer asset IDs.
Never put file paths or objects in upload_plan.
"""


# -- Gemini call helper -----------------------------------------------


async def _call_llm(provider: Provider, system: str, user_message: str) -> str:
    """Call the chosen AI provider with a system instruction + user message."""
    return await call_text(provider, system, user_message, temperature=0.7)


def _parse_json(raw: str) -> Any:
    """Extract JSON from LLM response (handles markdown fences)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


# -- Public API -------------------------------------------------------


async def generate_questions(
    hypothesis: str,
    provider: str = "gemini",
) -> list[dict[str, Any]]:
    """Analyze the hypothesis and return clarifying questions.

    Returns a list of ``{"id", "question", "why", "options"}`` dicts.
    """
    ai_provider = Provider(provider)
    user_msg = f"Hypothesis:\n{hypothesis}"
    raw = await _call_llm(ai_provider, QUESTIONS_SYSTEM, user_msg)
    questions = _parse_json(raw)

    # Validate shape
    if not isinstance(questions, list):
        raise RuntimeError(f"Expected a JSON array, got: {type(questions)}")
    return questions


async def suggest_conditions(
    hypothesis: str,
    questions_and_answers: list[dict[str, str]],
    available_assets: list[dict[str, Any]] | None = None,
    provider: str = "gemini",
) -> list[dict[str, Any]]:
    """Given the hypothesis and answered questions, suggest conditions.

    Parameters
    ----------
    hypothesis : str
    questions_and_answers : list of {"question": str, "answer": str}
    available_assets : optional list of {"id": int, "file_path": str, "role_guess": str}

    Returns list of condition dicts with flat upload_plan.
    """
    from backend.app.services.slots import ROLE_TO_CATEGORY

    parts = [f"Hypothesis:\n{hypothesis}\n"]
    parts.append("Clarifying Q&A:")
    for qa in questions_and_answers:
        parts.append(f"  Q: {qa['question']}\n  A: {qa['answer']}")

    if available_assets:
        parts.append("\n=== AVAILABLE REFERENCE ASSETS ===")
        parts.append("Use these INTEGER IDs in upload_plan (as a flat ordered list).")
        parts.append("Each asset has a QC-determined likely role:\n")
        for a in available_assets:
            role = a.get("role_guess", "unknown")
            category = ROLE_TO_CATEGORY.get(role)
            cat_name = category.value if category else "unknown"
            parts.append(
                f"  ID={a['id']}  role={role}  likely_category={cat_name}"
            )
        parts.append(
            "\nupload_plan format: [7, 12, 3]  (ordered list of asset IDs)"
        )

    user_msg = "\n".join(parts)
    user_msg += (
        '\n\nReminder: every prompt MUST follow this template exactly:\n'
        '"A photorealistic [shot type] of [subject], [action or expression], '
        'set in [environment]. The scene is illuminated by [lighting description], '
        'creating a [mood] atmosphere. Captured with [camera/lens details], '
        'emphasizing [key textures and details]."\n'
        'Fill every bracket with specific concrete values. '
        'Each condition MUST differ substantially in the bracket values -- '
        'change the actual scene, subject details, composition, lighting, or style '
        'so each prompt would produce a visibly different image. '
        'Name each condition after the variable value being tested. '
        'upload_plan must be a flat list of integer asset IDs. '
        'Include ALL available asset IDs in every condition\'s upload_plan unless '
        'the hypothesis specifically tests varying the count. '
        'Do NOT focus on upload order as a variable -- order permutations are '
        'handled separately.'
    )
    ai_provider = Provider(provider)
    raw = await _call_llm(ai_provider, CONDITIONS_SYSTEM, user_msg)
    conditions = _parse_json(raw)

    if not isinstance(conditions, list):
        raise RuntimeError(f"Expected a JSON array, got: {type(conditions)}")
    return conditions


# -- Upload-order permutations (separate toggleable feature) ---------

# Strategies for reordering reference images
ORDER_STRATEGIES = {
    "reversed": "All refs in reverse order",
    "chars_first": "Character refs first, then objects, then world",
    "objects_first": "Object refs first, then characters, then world",
    "world_first": "World/environment refs first, then characters, then objects",
    "random_shuffle": "Randomised order (seeded for reproducibility)",
}


def _categorize_assets(
    asset_ids: list[int],
    asset_info: dict[int, str],  # id -> role_guess
) -> dict[str, list[int]]:
    """Group asset IDs by their QC-determined category."""
    from backend.app.services.slots import ROLE_TO_CATEGORY

    groups: dict[str, list[int]] = {"character": [], "object": [], "world": []}
    for aid in asset_ids:
        role = asset_info.get(aid, "unknown")
        cat = ROLE_TO_CATEGORY.get(role)
        cat_name = cat.value if cat else "object"  # default to object
        groups.setdefault(cat_name, []).append(aid)
    return groups


def generate_order_permutations(
    conditions: list[dict[str, Any]],
    asset_info: dict[int, str] | None = None,
    strategies: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Create upload-order variants for each existing condition.

    Parameters
    ----------
    conditions : list of {"id": int, "name": str, "prompt": str, "upload_plan": list[int]|None}
        The existing conditions to permute.
    asset_info : optional dict of {asset_id: role_guess}
        Used for category-aware reordering strategies.
    strategies : optional list of strategy names to use.
        Defaults to all strategies in ORDER_STRATEGIES.

    Returns list of new condition dicts (name, prompt, upload_plan, ref_strategy).
    """
    if strategies is None:
        strategies = list(ORDER_STRATEGIES.keys())

    results: list[dict[str, Any]] = []

    for cond in conditions:
        plan = cond.get("upload_plan")
        if not plan or len(plan) < 2:
            continue  # nothing to reorder

        cond_name = cond.get("name", "Condition")
        prompt = cond.get("prompt", "")

        for strategy in strategies:
            new_plan = _apply_strategy(plan, strategy, asset_info)
            if new_plan == plan:
                continue  # skip if identical to original

            results.append({
                "name": f"{cond_name} — {ORDER_STRATEGIES.get(strategy, strategy)}",
                "prompt": prompt,
                "upload_plan": new_plan,
                "ref_strategy": (
                    f"Order permutation of '{cond_name}': {strategy}. "
                    f"Original order: {plan} → New order: {new_plan}"
                ),
            })

    return results


def _apply_strategy(
    plan: list[int],
    strategy: str,
    asset_info: dict[int, str] | None,
) -> list[int]:
    """Apply a reordering strategy to an upload plan."""
    if strategy == "reversed":
        return list(reversed(plan))

    if strategy == "random_shuffle":
        shuffled = plan[:]
        rng = random.Random(42)  # deterministic seed
        rng.shuffle(shuffled)
        return shuffled

    if strategy in ("chars_first", "objects_first", "world_first") and asset_info:
        groups = _categorize_assets(plan, asset_info)

        if strategy == "chars_first":
            order = ["character", "object", "world"]
        elif strategy == "objects_first":
            order = ["object", "character", "world"]
        else:  # world_first
            order = ["world", "character", "object"]

        result: list[int] = []
        for cat in order:
            result.extend(groups.get(cat, []))
        # Add any IDs that weren't categorised
        remaining = [x for x in plan if x not in result]
        result.extend(remaining)
        return result

    # Fallback: return original
    return plan
