"""Verify that DaVinci Resolve's Python scripting API is reachable."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "bridge"))

from resolve_client import ResolveClient  # noqa: E402


def main() -> None:
    client = ResolveClient(dry_run=False)
    print(json.dumps(client.get_context(), indent=2))


if __name__ == "__main__":
    main()
