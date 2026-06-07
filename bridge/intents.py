"""Small intent parser for the v1 assistant.

This deliberately keeps the model-facing contract simple: chat input is mapped
to one of a few known editing actions. A production version can replace this
module with LLM tool calling while preserving the same action schema.
"""

from __future__ import annotations

import re
from typing import Any


DEFAULT_CAPTION_TEXT = "Caption text"
DEFAULT_BROLL_QUERY = "relevant b-roll for the current timeline section"


def parse_prompt(prompt: str) -> dict[str, Any]:
    """Convert a user prompt into a constrained editing command."""
    clean_prompt = " ".join(prompt.strip().split())
    lower = clean_prompt.lower()

    if not clean_prompt:
        return _command("unknown", {}, "Tell me what edit you want to make.")

    if _mentions_any(lower, ("caption", "captions", "subtitle", "subtitles", "text", "title")):
        text = _extract_quoted_text(clean_prompt) or _extract_after_keywords(
            clean_prompt, ("saying", "that says", "called", "as")
        )
        duration = _extract_duration_seconds(lower) or 4
        position = _extract_position(lower)
        return _command(
            "add_caption",
            {
                "text": text or DEFAULT_CAPTION_TEXT,
                "duration_seconds": duration,
                "position": position,
            },
            f"Add a {duration}s {position.replace('_', ' ')} caption.",
        )

    if _mentions_any(lower, ("zoom", "push in", "punch in", "scale in")):
        amount = _extract_zoom_amount(lower) or 1.2
        return _command(
            "apply_zoom",
            {
                "target": "current_clip",
                "end_zoom": amount,
                "style": "smooth_push_in",
            },
            f"Apply a smooth zoom to the current clip ending at {amount:.2f}x.",
        )

    if _mentions_any(lower, ("b-roll", "b roll", "broll", "stock", "image", "images", "footage", "visuals")):
        query = _extract_visual_query(clean_prompt)
        media_type = "image" if _mentions_any(lower, ("image", "images", "photo", "photos")) else "video"
        return _command(
            "analyze_audio_and_plan_broll",
            {
                "query": query,
                "media_type": media_type,
                "limit": 5,
            },
            f"Analyze the current section and prepare {media_type} suggestions for '{query}'.",
        )

    if _mentions_any(lower, ("timeline", "project", "status", "where am i", "context")):
        return _command("get_context", {}, "Read the active Resolve project and timeline context.")

    return _command(
        "unknown",
        {"prompt": clean_prompt},
        "I can handle captions, zoom-ins, b-roll/image planning, and timeline context in v1.",
    )


def _command(action: str, args: dict[str, Any], summary: str) -> dict[str, Any]:
    return {
        "action": action,
        "args": args,
        "summary": summary,
        "requires_confirmation": action not in {"get_context", "unknown"},
    }


def _mentions_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _extract_quoted_text(text: str) -> str | None:
    match = re.search(r"['\"]([^'\"]+)['\"]", text)
    if not match:
        return None
    return match.group(1).strip()


def _extract_after_keywords(text: str, keywords: tuple[str, ...]) -> str | None:
    lower = text.lower()
    for keyword in keywords:
        index = lower.find(keyword)
        if index == -1:
            continue
        value = text[index + len(keyword) :].strip(" :.-")
        return value or None
    return None


def _extract_duration_seconds(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(s|sec|secs|second|seconds)\b", text)
    if not match:
        return None
    return max(1, min(int(match.group(1)), 60))


def _extract_position(text: str) -> str:
    if "top left" in text:
        return "top_left"
    if "top right" in text:
        return "top_right"
    if "bottom left" in text or "lower left" in text:
        return "bottom_left"
    if "bottom right" in text or "lower right" in text:
        return "bottom_right"
    if "top" in text:
        return "top_center"
    if "middle" in text or "center" in text:
        return "center"
    return "bottom_center"


def _extract_zoom_amount(text: str) -> float | None:
    percent_match = re.search(r"(\d+)\s*%", text)
    if percent_match:
        percent = int(percent_match.group(1))
        return round(1 + percent / 100, 2) if percent < 100 else round(percent / 100, 2)

    x_match = re.search(r"(\d+(?:\.\d+)?)\s*x\b", text)
    if x_match:
        return round(float(x_match.group(1)), 2)

    return None


def _extract_visual_query(text: str) -> str:
    quoted = _extract_quoted_text(text)
    if quoted:
        return quoted

    lower = text.lower()
    for marker in ("of ", "for ", "about ", "showing "):
        index = lower.find(marker)
        if index != -1:
            query = text[index + len(marker) :].strip(" .")
            if query:
                return _clean_visual_query(query)

    query = _clean_visual_query(text)
    return query or DEFAULT_BROLL_QUERY


def _clean_visual_query(text: str) -> str:
    query = text.lower().strip(" .")
    query = re.sub(r"^(find|get|search|pull|add|insert|use)\s+", "", query)
    query = re.sub(r"\b(b[- ]?roll|stock|footage|video|videos|image|images|visuals)\b", "", query)
    query = re.sub(r"\s+", " ", query).strip(" .")
    return query
