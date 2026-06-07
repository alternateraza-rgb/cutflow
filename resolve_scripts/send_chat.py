"""Send a chat command to the local Cutflow bridge."""

from __future__ import annotations

import argparse
import json
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a Cutflow chat command.")
    parser.add_argument("message")
    parser.add_argument("--url", default="http://127.0.0.1:8765/chat")
    args = parser.parse_args()

    body = json.dumps({"message": args.message}).encode("utf-8")
    request = urllib.request.Request(
        args.url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
