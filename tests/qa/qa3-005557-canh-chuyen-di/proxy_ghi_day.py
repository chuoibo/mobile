"""Logging reverse proxy: records EXACTLY the requests this app made.

Why a proxy instead of reading the server log
---------------------------------------------
The demo API on :8199 is shared: six lanes and a browser hit it at the same
time, every request arrives from 127.0.0.1 through docker-proxy, and uvicorn's
access line carries no header. Reading that log cannot answer "which route did
MY tap call" — it can only answer "which routes did the machine call". Those
are different questions, and the second one is not evidence for anything.

The app is pinned to this proxy through EXPO_PUBLIC_API_URL, so every line in
the log file below was produced by a tap on the emulator and by nothing else.

Usage:
    python3 proxy_ghi_day.py <listen_port> <upstream_port> <log_path>
"""

from __future__ import annotations

import http.client
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LISTEN_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8299
UPSTREAM_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8199
LOG_PATH = sys.argv[3] if len(sys.argv) > 3 else "/tmp/qa3-wire.log"

_lock = threading.Lock()


def ghi(record: dict) -> None:
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep stderr quiet; the JSON log is the record
        pass

    def _pass_through(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in ("host", "connection", "content-length")
        }
        if body is not None:
            headers["Content-Length"] = str(len(body))
        started = time.time()
        conn = http.client.HTTPConnection("127.0.0.1", UPSTREAM_PORT, timeout=60)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            payload = resp.read()
            status = resp.status
            out_headers = [
                (k, v)
                for k, v in resp.getheaders()
                if k.lower()
                not in ("transfer-encoding", "connection", "content-length")
            ]
        except Exception as exc:  # upstream down -> say so, do not swallow
            payload = json.dumps({"proxy_error": str(exc)}).encode()
            status = 502
            out_headers = [("Content-Type", "application/json")]
        finally:
            conn.close()

        ghi(
            {
                "t": round(started, 3),
                "ts": time.strftime("%H:%M:%S", time.localtime(started)),
                "method": self.command,
                "path": self.path,
                "status": status,
                "bytes": len(payload),
                "ms": int((time.time() - started) * 1000),
                # X-Actor-ID is what tells apart "the app asked" from "a curl asked".
                "actor": self.headers.get("X-Actor-ID"),
            }
        )

        self.send_response(status)
        for k, v in out_headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _pass_through
    do_POST = _pass_through
    do_PUT = _pass_through
    do_PATCH = _pass_through
    do_DELETE = _pass_through
    do_OPTIONS = _pass_through


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
    print(
        f"proxy {LISTEN_PORT} -> 127.0.0.1:{UPSTREAM_PORT}, log {LOG_PATH}", flush=True
    )
    srv.serve_forever()
