"""Build a dependency-free macOS .app wrapper for Cutflow.

The generated app starts the local Python bridge, serves the chat panel, and
opens the panel in the user's browser. It intentionally avoids Electron/Tauri
for v1 so editors can run the prototype with the Python that ships on macOS.
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
from pathlib import Path


APP_NAME = "Cutflow"
BRIDGE_PORT = 8765
PLUGIN_PORT = 9000


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dist/Cutflow.app")
    parser.add_argument("--dist", default="dist", help="Output directory")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / args.dist
    app_dir = dist_dir / f"{APP_NAME}.app"
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    if app_dir.exists():
        shutil.rmtree(app_dir)

    macos_dir.mkdir(parents=True)
    resources_dir.mkdir(parents=True)

    _copy_tree(repo_root / "bridge", resources_dir / "bridge")
    _copy_tree(repo_root / "plugin", resources_dir / "plugin")
    _copy_tree(repo_root / "resolve_scripts", resources_dir / "resolve_scripts")

    _write_info_plist(contents_dir / "Info.plist")
    _write_launcher(macos_dir / APP_NAME)

    print(f"Built {app_dir}")
    print("Double-click the app on macOS, or run:")
    print(f"open {app_dir}")


def _copy_tree(source: Path, destination: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    shutil.copytree(source, destination, ignore=ignore)


def _write_info_plist(path: Path) -> None:
    info = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": APP_NAME,
        "CFBundleIdentifier": "app.cutflow.resolve-assistant",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    }
    with path.open("wb") as handle:
        plistlib.dump(info, handle, sort_keys=False)


def _write_launcher(path: Path) -> None:
    script = f"""#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$APP_DIR/Resources"
LOG_DIR="$HOME/Library/Logs/Cutflow"
mkdir -p "$LOG_DIR"

PYTHON_BIN="${{PYTHON_BIN:-/usr/bin/python3}}"
BRIDGE_PORT="${{CUTFLOW_BRIDGE_PORT:-{BRIDGE_PORT}}}"
PLUGIN_PORT="${{CUTFLOW_PLUGIN_PORT:-{PLUGIN_PORT}}}"
BRIDGE_URL="http://127.0.0.1:$BRIDGE_PORT/health"
PLUGIN_URL="http://127.0.0.1:$PLUGIN_PORT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  osascript -e 'display dialog "Cutflow needs Python 3. Install Python 3 or set PYTHON_BIN before launching." buttons {{"OK"}} default button "OK" with icon caution'
  exit 1
fi

is_port_open() {{
  /usr/bin/nc -z 127.0.0.1 "$1" >/dev/null 2>&1
}}

if ! is_port_open "$BRIDGE_PORT"; then
  CUTFLOW_DRY_RUN="${{CUTFLOW_DRY_RUN:-0}}" "$PYTHON_BIN" "$RESOURCES_DIR/bridge/server.py" \\
    --host 127.0.0.1 \\
    --port "$BRIDGE_PORT" \\
    >>"$LOG_DIR/bridge.log" 2>&1 &
  BRIDGE_PID=$!
else
  BRIDGE_PID=""
fi

if ! is_port_open "$PLUGIN_PORT"; then
  "$PYTHON_BIN" -m http.server "$PLUGIN_PORT" -d "$RESOURCES_DIR/plugin" \\
    >>"$LOG_DIR/plugin.log" 2>&1 &
  PLUGIN_PID=$!
else
  PLUGIN_PID=""
fi

cleanup() {{
  if [ -n "${{BRIDGE_PID:-}}" ]; then kill "$BRIDGE_PID" >/dev/null 2>&1 || true; fi
  if [ -n "${{PLUGIN_PID:-}}" ]; then kill "$PLUGIN_PID" >/dev/null 2>&1 || true; fi
}}
trap cleanup EXIT

for _ in {{1..40}}; do
  if /usr/bin/curl -fsS "$BRIDGE_URL" >/dev/null 2>&1 && is_port_open "$PLUGIN_PORT"; then
    break
  fi
  sleep 0.25
done

/usr/bin/open "$PLUGIN_URL"
osascript -e 'display notification "Cutflow is running. Close this app from the Dock to stop the local bridge." with title "Cutflow"'

wait
"""
    path.write_text(script)
    os.chmod(path, 0o755)


if __name__ == "__main__":
    main()
