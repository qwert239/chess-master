"""Local preview: static UI + the same Lambda handler. No Docker required."""

from __future__ import annotations

import json
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app import lambda_handler  # noqa: E402

FRONTEND = ROOT / "frontend"
HOST = "127.0.0.1"
PORT = 8080


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND), **kwargs)

    def do_POST(self):
        if urlparse(self.path).path.rstrip("/") == "/games":
            self._invoke(
                {
                    "httpMethod": "POST",
                    "resource": "/games",
                    "path": "/games",
                    "body": self._read_body(),
                    "isBase64Encoded": False,
                }
            )
            return
        self.send_error(404)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/games/"):
            game_id = path.rstrip("/").rsplit("/", 1)[-1]
            self._invoke(
                {
                    "httpMethod": "GET",
                    "resource": "/games/{id}",
                    "path": path,
                    "pathParameters": {"id": game_id},
                }
            )
            return
        super().do_GET()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length).decode("utf-8") if length else ""

    def _invoke(self, event):
        result = lambda_handler(event, None)
        body = result.get("body") or ""
        headers = result.get("headers") or {}
        self.send_response(result.get("statusCode", 500))
        self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Open http://{HOST}:{PORT}")
    server.serve_forever()
