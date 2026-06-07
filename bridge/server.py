"""Local HTTP bridge between the chat panel and DaVinci Resolve."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from intents import parse_prompt
from resolve_client import ResolveClient
from stock import StockSearch


class CutflowBridge:
    def __init__(self, dry_run: bool | None = None) -> None:
        self.resolve = ResolveClient(dry_run=dry_run)
        self.stock = StockSearch()

    def handle_chat(self, message: str) -> dict[str, Any]:
        command = parse_prompt(message)
        result = self.execute(command)
        return {
            "reply": self._reply_for(command, result),
            "command": command,
            "result": result,
            "context": self.resolve.get_context(),
        }

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        action = command.get("action")
        args = command.get("args") or {}

        if action == "get_context":
            return {"ok": True, "context": self.resolve.get_context()}

        if action == "add_caption":
            return self.resolve.add_caption(**args)

        if action == "apply_zoom":
            return self.resolve.apply_zoom(**args)

        if action == "analyze_audio_and_plan_broll":
            query = args.get("query", "relevant b-roll")
            media_type = args.get("media_type", "video")
            limit = int(args.get("limit", 5))
            suggestions = self.stock.search(query=query, media_type=media_type, limit=limit)
            return self.resolve.add_broll_plan_markers(query=query, suggestions=suggestions)

        return {
            "ok": False,
            "message": command.get("summary", "Unsupported command."),
        }

    def _reply_for(self, command: dict[str, Any], result: dict[str, Any]) -> str:
        if result.get("ok"):
            return result.get("message") or command.get("summary") or "Done."
        return result.get("message") or "I could not complete that edit."


class RequestHandler(BaseHTTPRequestHandler):
    bridge: CutflowBridge

    def do_OPTIONS(self) -> None:
        self._send_json({}, HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/health":
            self._send_json(
                {
                    "ok": True,
                    "service": "cutflow-bridge",
                    "context": self.bridge.resolve.get_context(),
                }
            )
            return

        self._send_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        payload = self._read_json()

        try:
            if self.path == "/chat":
                message = str(payload.get("message", ""))
                self._send_json(self.bridge.handle_chat(message))
                return

            if self.path == "/action":
                self._send_json({"result": self.bridge.execute(payload)})
                return

            self._send_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[cutflow-bridge] {self.address_string()} - {format % args}")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if status != HTTPStatus.NO_CONTENT:
            self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Cutflow Resolve bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--dry-run", action="store_true", help="Do not attempt to connect to Resolve.")
    args = parser.parse_args()

    RequestHandler.bridge = CutflowBridge(dry_run=args.dry_run)
    server = ThreadingHTTPServer((args.host, args.port), RequestHandler)
    print(f"Cutflow bridge listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
