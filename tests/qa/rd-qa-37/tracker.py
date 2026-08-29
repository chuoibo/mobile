"""A host somebody else controls, listening for the app to dial it.

This stands in for the machine an attacking group member would own. It answers
every path with a real 1x1 PNG -- refusing would be a weaker test, because a
gate could then be credited for what is only a failed load. Every hit is
appended to a JSON log with the caller's address and the moment it arrived,
because those two fields are the leak: they say who opened the screen and when.

The pass condition for rd-qa-37 item 3 is that this file's log stays EMPTY
while the app renders a memory whose image_url points here. An empty log only
means something if the same server is proven reachable in the same run, so the
harness fetches a canary path itself before and after -- see di-bo-anh.py.
"""

from __future__ import annotations

import base64
import json
import pathlib
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9613
LOG = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/rd-qa-37-tracker.json")

# 1x1 transparent PNG. A real image, so a load that happens actually succeeds.
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

_lock = threading.Lock()


def _record(entry: dict) -> None:
    with _lock:
        hits = json.loads(LOG.read_text()) if LOG.exists() else []
        hits.append(entry)
        LOG.write_text(json.dumps(hits, indent=2))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        _record(
            {
                "path": self.path,
                "from_ip": self.client_address[0],
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "referer": self.headers.get("Referer"),
                "ua": (self.headers.get("User-Agent") or "")[:80],
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(PIXEL)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(PIXEL)

    def log_message(self, *args) -> None:  # noqa: D102 - silence stderr spam
        pass


if __name__ == "__main__":
    LOG.write_text("[]")
    print(f"tracker on {PORT}, log {LOG}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
