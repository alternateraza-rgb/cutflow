"""DaVinci Resolve automation wrapper for Cutflow v1."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ResolveContext:
    connected: bool
    project_name: str | None
    timeline_name: str | None
    timecode: str | None
    dry_run: bool


class ResolveClient:
    """Thin wrapper around Resolve's Python scripting API.

    The API surface here is intentionally narrow. Chat/AI code calls these
    methods instead of touching Resolve directly.
    """

    def __init__(self, dry_run: bool | None = None) -> None:
        self.dry_run = _env_truthy("CUTFLOW_DRY_RUN") if dry_run is None else dry_run
        self.resolve = None if self.dry_run else _load_resolve()

    def get_context(self) -> dict[str, Any]:
        if not self.resolve:
            return ResolveContext(
                connected=False,
                project_name="Dry Run Project",
                timeline_name="Dry Run Timeline",
                timecode="01:00:00:00",
                dry_run=True,
            ).__dict__

        project = self._current_project()
        timeline = self._current_timeline(project)
        return ResolveContext(
            connected=True,
            project_name=_safe_call(project, "GetName"),
            timeline_name=_safe_call(timeline, "GetName"),
            timecode=_safe_call(timeline, "GetCurrentTimecode"),
            dry_run=False,
        ).__dict__

    def add_caption(self, text: str, duration_seconds: int = 4, position: str = "bottom_center") -> dict[str, Any]:
        if not self.resolve:
            return {
                "ok": True,
                "dry_run": True,
                "message": f"Would add caption '{text}' for {duration_seconds}s at {position}.",
            }

        project = self._require_project()
        timeline = self._require_timeline(project)
        frame = self._current_frame(project, timeline)
        duration_frames = int(duration_seconds * self._timeline_fps(project))

        inserted_title = self._try_insert_text_title(timeline, text)
        if inserted_title:
            return {
                "ok": True,
                "dry_run": False,
                "message": f"Inserted a Text+ title for '{text}'.",
            }

        timeline.AddMarker(
            frame,
            "Blue",
            f"Caption: {text}",
            f"Position: {position}. Duration: {duration_seconds}s.",
            duration_frames,
            f"cutflow_caption:{text}",
        )
        return {
            "ok": True,
            "dry_run": False,
            "message": "Added a Resolve marker describing the caption because title insertion was unavailable.",
        }

    def apply_zoom(self, end_zoom: float = 1.2, target: str = "current_clip", style: str = "smooth_push_in") -> dict[str, Any]:
        if not self.resolve:
            return {
                "ok": True,
                "dry_run": True,
                "message": f"Would apply {style} zoom to {target}, ending at {end_zoom:.2f}x.",
            }

        project = self._require_project()
        timeline = self._require_timeline(project)
        clip = self._current_video_item(timeline)
        if not clip:
            frame = self._current_frame(project, timeline)
            timeline.AddMarker(
                frame,
                "Yellow",
                "Zoom request",
                f"Apply {style} ending at {end_zoom:.2f}x to the current clip.",
                1,
                f"cutflow_zoom:{end_zoom:.2f}",
            )
            return {
                "ok": False,
                "dry_run": False,
                "message": "Could not find a current video item; added a marker with the zoom request.",
            }

        changed = False
        for property_name in ("ZoomX", "ZoomY"):
            try:
                changed = bool(clip.SetProperty(property_name, end_zoom)) or changed
            except Exception:
                continue

        return {
            "ok": changed,
            "dry_run": False,
            "message": (
                f"Set current clip zoom to {end_zoom:.2f}x."
                if changed
                else "Current clip did not accept zoom properties through the Resolve API."
            ),
        }

    def add_broll_plan_markers(self, query: str, suggestions: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.resolve:
            return {
                "ok": True,
                "dry_run": True,
                "message": f"Would add b-roll planning markers for '{query}'.",
                "suggestions": suggestions,
            }

        project = self._require_project()
        timeline = self._require_timeline(project)
        frame = self._current_frame(project, timeline)
        duration_frames = int(4 * self._timeline_fps(project))
        names = ", ".join(item.get("title", "suggestion") for item in suggestions[:3])
        note = f"Search query: {query}\nTop suggestions: {names or 'none'}"
        timeline.AddMarker(frame, "Green", f"B-roll: {query}", note, duration_frames, f"cutflow_broll:{query}")
        return {
            "ok": True,
            "dry_run": False,
            "message": f"Added a b-roll planning marker for '{query}'.",
            "suggestions": suggestions,
        }

    def import_media(self, path: str) -> dict[str, Any]:
        if not self.resolve:
            return {"ok": True, "dry_run": True, "message": f"Would import media: {path}"}

        project = self._require_project()
        media_pool = project.GetMediaPool()
        media_storage = self.resolve.GetMediaStorage()
        imported = media_storage.AddItemListToMediaPool([path])
        if not imported:
            return {"ok": False, "dry_run": False, "message": f"Resolve did not import: {path}"}
        return {"ok": True, "dry_run": False, "message": f"Imported {Path(path).name}.", "items": len(imported)}

    def _require_project(self) -> Any:
        project = self._current_project()
        if not project:
            raise RuntimeError("No active DaVinci Resolve project is open.")
        return project

    def _require_timeline(self, project: Any) -> Any:
        timeline = self._current_timeline(project)
        if not timeline:
            raise RuntimeError("No active DaVinci Resolve timeline is open.")
        return timeline

    def _current_project(self) -> Any:
        manager = self.resolve.GetProjectManager()
        return manager.GetCurrentProject() if manager else None

    def _current_timeline(self, project: Any) -> Any:
        return project.GetCurrentTimeline() if project else None

    def _current_video_item(self, timeline: Any) -> Any:
        getter = getattr(timeline, "GetCurrentVideoItem", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        return None

    def _try_insert_text_title(self, timeline: Any, text: str) -> bool:
        for method_name, title_name in (
            ("InsertTitleIntoTimeline", "Text+"),
            ("InsertGeneratorIntoTimeline", "Text+"),
        ):
            method = getattr(timeline, method_name, None)
            if not callable(method):
                continue
            try:
                item = method(title_name)
            except Exception:
                continue
            if item:
                self._set_text_properties(item, text)
                return True
        return False

    def _set_text_properties(self, item: Any, text: str) -> None:
        for property_name in ("StyledText", "Text", "Name"):
            try:
                item.SetProperty(property_name, text)
            except Exception:
                continue

    def _current_frame(self, project: Any, timeline: Any) -> int:
        timecode = _safe_call(timeline, "GetCurrentTimecode") or "00:00:00:00"
        return _timecode_to_frames(timecode, self._timeline_fps(project))

    def _timeline_fps(self, project: Any) -> float:
        value = project.GetSetting("timelineFrameRate") if project else None
        try:
            return float(value)
        except (TypeError, ValueError):
            return 24.0


def _load_resolve() -> Any:
    module_paths = _resolve_module_paths()
    for module_path in module_paths:
        if module_path.exists():
            sys.path.append(str(module_path))

    try:
        import DaVinciResolveScript as dvr_script
    except ImportError:
        return None

    try:
        return dvr_script.scriptapp("Resolve")
    except Exception:
        return None


def _resolve_module_paths() -> list[Path]:
    system = platform.system()
    if system == "Darwin":
        return [
            Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"),
        ]
    if system == "Windows":
        program_data = os.environ.get("PROGRAMDATA", "C:/ProgramData")
        return [
            Path(program_data)
            / "Blackmagic Design"
            / "DaVinci Resolve"
            / "Support"
            / "Developer"
            / "Scripting"
            / "Modules",
        ]
    return [
        Path("/opt/resolve/Developer/Scripting/Modules"),
        Path("/home/resolve/Developer/Scripting/Modules"),
    ]


def _safe_call(obj: Any, method_name: str) -> Any:
    if not obj:
        return None
    method = getattr(obj, method_name, None)
    if not callable(method):
        return None
    try:
        return method()
    except Exception:
        return None


def _timecode_to_frames(timecode: str, fps: float) -> int:
    parts = timecode.replace(";", ":").split(":")
    if len(parts) != 4:
        return 0
    hours, minutes, seconds, frames = (int(part) for part in parts)
    return int((((hours * 60 + minutes) * 60) + seconds) * fps + frames)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}
