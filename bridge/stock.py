"""Licensed stock media search helpers for v1."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any


class StockSearch:
    """Search stock providers without requiring third-party dependencies."""

    def __init__(self, pexels_api_key: str | None = None) -> None:
        self.pexels_api_key = pexels_api_key or os.environ.get("PEXELS_API_KEY")

    def search(self, query: str, media_type: str = "video", limit: int = 5) -> list[dict[str, Any]]:
        if self.pexels_api_key:
            try:
                return self._search_pexels(query=query, media_type=media_type, limit=limit)
            except Exception as exc:
                return [_fallback_item(query, media_type, f"Pexels search failed: {exc}")]

        return [
            _fallback_item(
                query,
                media_type,
                "Set PEXELS_API_KEY to return licensed preview results from Pexels.",
            )
        ]

    def _search_pexels(self, query: str, media_type: str, limit: int) -> list[dict[str, Any]]:
        if media_type == "image":
            endpoint = "https://api.pexels.com/v1/search"
            result_key = "photos"
        else:
            endpoint = "https://api.pexels.com/videos/search"
            result_key = "videos"

        params = urllib.parse.urlencode({"query": query, "per_page": max(1, min(limit, 15))})
        request = urllib.request.Request(
            f"{endpoint}?{params}",
            headers={"Authorization": self.pexels_api_key, "User-Agent": "Cutflow/0.1"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        items = payload.get(result_key, [])
        return [self._normalize_pexels_item(item, media_type) for item in items[:limit]]

    def _normalize_pexels_item(self, item: dict[str, Any], media_type: str) -> dict[str, Any]:
        if media_type == "image":
            src = item.get("src", {})
            return {
                "provider": "pexels",
                "type": "image",
                "title": item.get("alt") or f"Pexels image {item.get('id')}",
                "preview_url": src.get("medium") or src.get("large"),
                "download_url": src.get("original"),
                "license_url": item.get("url"),
                "credit": item.get("photographer"),
            }

        files = sorted(item.get("video_files", []), key=lambda file: file.get("width") or 0)
        preview = item.get("image")
        download = files[-1].get("link") if files else None
        user = item.get("user") or {}
        return {
            "provider": "pexels",
            "type": "video",
            "title": f"Pexels video {item.get('id')}",
            "preview_url": preview,
            "download_url": download,
            "license_url": item.get("url"),
            "credit": user.get("name"),
        }


def _fallback_item(query: str, media_type: str, note: str) -> dict[str, Any]:
    return {
        "provider": "placeholder",
        "type": media_type,
        "title": f"Search suggestion: {query}",
        "preview_url": None,
        "download_url": None,
        "license_url": None,
        "credit": None,
        "note": note,
    }
