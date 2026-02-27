"""Unified AI client — dispatches to Gemini or Claude.

Two call patterns:
1. ``call_vision``  — image + text prompt → structured JSON (for QC)
2. ``call_text``    — system + user message → structured JSON (for advisor)

Both return the raw text response. Callers parse JSON themselves.
"""

from __future__ import annotations

import base64
import io
import logging
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from backend.app.config import settings

logger = logging.getLogger(__name__)

# ── Provider enum ────────────────────────────────────────────────────

class Provider(str, Enum):
    gemini = "gemini"
    claude = "claude"


# ── Gemini URLs ──────────────────────────────────────────────────────

GEMINI_FLASH_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

# ── Claude config ────────────────────────────────────────────────────

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_VERSION = "2023-06-01"


# ── Internal helpers ─────────────────────────────────────────────────

def _get_gemini_key() -> str:
    key = settings.gemini_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return key


def _get_anthropic_key() -> str:
    key = settings.anthropic_api_key
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key


# ── Image helpers ────────────────────────────────────────────────────

# Claude caps base64 images at 5 MB.  Leave 200 KB headroom.
_CLAUDE_MAX_B64_BYTES = 5_000_000


def _downsize_image_b64(
    raw_bytes: bytes,
    mime_type: str,
    max_b64_bytes: int = _CLAUDE_MAX_B64_BYTES,
) -> tuple[str, str]:
    """Return (base64_str, mime_type), resizing if the payload is too big.

    Strategy:
    1. If the base64-encoded size is already under *max_b64_bytes*, return as-is.
    2. Otherwise, progressively shrink the image (75 % per step) and re-encode
       as JPEG quality 85 until it fits.
    """
    b64 = base64.b64encode(raw_bytes).decode()
    if len(b64) <= max_b64_bytes:
        return b64, mime_type

    logger.info(
        "Image too large for Claude (%d bytes b64 > %d).  Downsizing…",
        len(b64), max_b64_bytes,
    )

    img = Image.open(io.BytesIO(raw_bytes))
    # Convert RGBA/P → RGB for JPEG
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    quality = 85
    for _ in range(10):  # max 10 shrink steps
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        b64 = base64.b64encode(buf.getvalue()).decode()
        if len(b64) <= max_b64_bytes:
            logger.info(
                "Downsized to %dx%d  q=%d  (%d bytes b64)",
                img.width, img.height, quality, len(b64),
            )
            return b64, "image/jpeg"
        # Shrink dimensions by 25 %
        new_w = max(1, int(img.width * 0.75))
        new_h = max(1, int(img.height * 0.75))
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # Last resort: return whatever we have
    return b64, "image/jpeg"


# ── Gemini calls ─────────────────────────────────────────────────────

async def _gemini_vision(
    prompt: str,
    image_b64: str,
    mime_type: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{GEMINI_FLASH_URL}?key={_get_gemini_key()}",
            json=payload,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

    body = resp.json()
    _check_gemini_truncation(body)
    return _extract_gemini_text(body)


async def _gemini_text(
    system: str,
    user_message: str,
    *,
    temperature: float = 0.7,
) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user_message}]}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{GEMINI_FLASH_URL}?key={_get_gemini_key()}",
            json=payload,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

    body = resp.json()
    return _extract_gemini_text(body)


def _check_gemini_truncation(body: dict[str, Any]) -> None:
    try:
        reason = body["candidates"][0].get("finishReason", "")
    except (KeyError, IndexError):
        reason = ""
    if reason == "MAX_TOKENS":
        logger.warning("Gemini response truncated (MAX_TOKENS)")


def _extract_gemini_text(body: dict[str, Any]) -> str:
    try:
        return body["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response structure: {exc}")


# ── Claude calls ─────────────────────────────────────────────────────

async def _claude_vision(
    prompt: str,
    image_b64: str,
    mime_type: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "temperature": temperature,
    }
    headers = {
        "x-api-key": _get_anthropic_key(),
        "anthropic-version": CLAUDE_VERSION,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(CLAUDE_API_URL, json=payload, headers=headers)

    if resp.status_code != 200:
        raise RuntimeError(f"Claude API error {resp.status_code}: {resp.text[:500]}")

    body = resp.json()
    return _extract_claude_text(body)


async def _claude_text(
    system: str,
    user_message: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_message}],
        "temperature": temperature,
    }
    headers = {
        "x-api-key": _get_anthropic_key(),
        "anthropic-version": CLAUDE_VERSION,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(CLAUDE_API_URL, json=payload, headers=headers)

    if resp.status_code != 200:
        raise RuntimeError(f"Claude API error {resp.status_code}: {resp.text[:500]}")

    body = resp.json()
    return _extract_claude_text(body)


def _extract_claude_text(body: dict[str, Any]) -> str:
    content = body.get("content", [])
    texts = [b["text"] for b in content if b.get("type") == "text"]
    if not texts:
        raise RuntimeError(f"Unexpected Claude response structure: {body}")
    return "".join(texts)


# ── Public API ───────────────────────────────────────────────────────

async def call_vision(
    provider: Provider,
    prompt: str,
    image_path: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> str:
    """Send image + prompt to the chosen provider, return raw text response."""
    path = Path(image_path)
    if not path.exists():
        raise RuntimeError(f"Image file not found: {image_path}")

    raw_bytes = path.read_bytes()
    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime_type = mime_map.get(suffix, "image/png")

    if provider == Provider.claude:
        # Claude has a 5 MB base64 image limit — downsize if necessary
        image_b64, mime_type = _downsize_image_b64(raw_bytes, mime_type)
        return await _claude_vision(
            prompt, image_b64, mime_type,
            temperature=temperature, max_tokens=max_tokens,
        )
    else:
        image_b64 = base64.b64encode(raw_bytes).decode()
        return await _gemini_vision(
            prompt, image_b64, mime_type,
            temperature=temperature, max_tokens=max_tokens,
        )


async def call_text(
    provider: Provider,
    system: str,
    user_message: str,
    *,
    temperature: float = 0.7,
) -> str:
    """Send system + user text to the chosen provider, return raw text response."""
    if provider == Provider.claude:
        return await _claude_text(system, user_message, temperature=temperature)
    else:
        return await _gemini_text(system, user_message, temperature=temperature)
