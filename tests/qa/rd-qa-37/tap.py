"""A wire tap between the app and the API, so EXIF can be asked of real bytes.

Playwright's `postDataBuffer()` returns null for a multipart body built from a
File blob, which is how the first cut of di-bo-bill.mjs recorded `bytesGui: 0`
for six uploads that all really happened. Rather than trust the browser to hand
its own body back, this sits in the path and keeps what actually crossed it.

It changes nothing: same method, same headers, same body, forwarded verbatim to
the real API and the real response returned untouched. It is a passive
recorder, not a stub -- the model call, the latency, and the status code are
all still the product's.

Run the API on UP and this on PORT; the bundle already points at PORT.
"""

from __future__ import annotations

import base64
import http.client
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9611
UP = int(sys.argv[2]) if len(sys.argv) > 2 else 9614
OUT = pathlib.Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/rd-qa-37-wire")
OUT.mkdir(parents=True, exist_ok=True)

_n = [0]

# A 100x75 green PNG: big enough that a layout shift would be visible, and a
# real decodable image so `onLoad` genuinely fires.
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAGQAAABLCAIAAAAJerXgAAAAuUlEQVR4nO3QQQ3A"
    "IADAQEDKTCEK07OwvsiSOwVN53P24Jt1O+BPzArMCswKzArMCswKzArMCswKzArM"
    "CswKzArMCswKzArMCswKzArMCswKzArMCswKzArMCswKzArMCswKzArMCswKzArM"
    "CswKzArMCswKzArMCswKzArMCswKzArMCswKzArMCswKzArMCswKzArMCswKzArM"
    "CswKzArMCswKzArMCswKzArMCswKzArMCswKzApewjABmpCymjIAAAAASUVORK5C"
    "YII="
)

# Headers the upstream connection must own rather than inherit.
_DROP = {"host", "connection", "content-length", "transfer-encoding"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _pass(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        # A real image on the API's own origin. `nguonAnhAnToan` allows exactly
        # this and nothing else, so it is the positive canary for item 3: if
        # this one does not load, "the tracker got no hit" proves nothing,
        # because it would mean the frame never fetches anything at all.
        if self.path.startswith("/qa37-anh/"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PIXEL)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(PIXEL)
            print(f"[tap] canary anh: {self.path}", flush=True)
            return

        if "/receipts/scan" in self.path and method == "POST" and body:
            _n[0] += 1
            path = OUT / f"scan-{_n[0]:02d}.bin"
            path.write_bytes(body)
            print(f"[tap] {path.name}  {len(body):,d} bytes", flush=True)

        conn = http.client.HTTPConnection("127.0.0.1", UP, timeout=180)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in _DROP}
        conn.request(method, self.path, body=body, headers=headers)
        up = conn.getresponse()
        data = up.read()

        self.send_response(up.status)
        for k, v in up.getheaders():
            if k.lower() in _DROP:
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        conn.close()

    def do_GET(self):  # noqa: N802
        self._pass("GET")

    def do_POST(self):  # noqa: N802
        self._pass("POST")

    def do_PUT(self):  # noqa: N802
        self._pass("PUT")

    def do_PATCH(self):  # noqa: N802
        self._pass("PATCH")

    def do_DELETE(self):  # noqa: N802
        self._pass("DELETE")

    def do_OPTIONS(self):  # noqa: N802
        self._pass("OPTIONS")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"tap {PORT} -> {UP}, bodies in {OUT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
