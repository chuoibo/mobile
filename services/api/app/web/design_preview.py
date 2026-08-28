"""Dev-only preview server for the design-system sample screens.

Never imported in production. No database. All data is obviously fake.

    python3 -m app.web.design_preview        then open http://localhost:8010
"""

from __future__ import annotations

import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

WEB = pathlib.Path(__file__).resolve().parent


def fixture() -> dict:
    """Synthetic settlement used to stand the mock next to the product mockup.

    Names, amounts, and the bank are labelled as sample data on the page.
    They are not real participants.
    """
    return {
        "nav_title": "Kết quả thanh toán",
        "bill_label": "Tổng hoá đơn",
        "bill_amount": "1.125.000",
        "bill_meta": "8 món · 4 người",
        "people_heading": "Số tiền mỗi người phải trả",
        "people": [
            {"initial": "M", "name": "Minh Anh", "amount": "312.500"},
            {"initial": "Q", "name": "Quang Huy", "amount": "287.500"},
            {"initial": "T", "name": "Thu Hà", "amount": "262.500"},
            {"initial": "Đ", "name": "Đức Duy", "amount": "262.500"},
        ],
        "transfer_heading": "Tối ưu chuyển khoản",
        "transfers": [
            {"payer": "Quang Huy", "payee": "Minh Anh", "amount": "287.500"},
            {"payer": "Thu Hà", "payee": "Minh Anh", "amount": "262.500"},
            {"payer": "Đức Duy", "payee": "Minh Anh", "amount": "262.500"},
        ],
        "qr_caption": "Quét để thanh toán",
        "qr_name": "Minh Anh",
        "qr_bank": "Vietcombank",
        "ai_note": "AI đã chia theo món, bạn vẫn sửa được trước khi chốt.",
        "share_label": "Chia sẻ kết quả",
        "done_label": "Hoàn tất",
        "sample_notice": "Dữ liệu mẫu, không phải người thật.",
    }


def render() -> bytes:
    env = Environment(
        loader=FileSystemLoader(str(WEB / "templates")),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("design_system.html").render(sample=fixture())
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/static/"):
            asset = (WEB / "static" / pathlib.Path(path).name).resolve()
            if not asset.is_file() or WEB / "static" not in asset.parents:
                return self.send_error(404)
            kind = "text/css" if asset.suffix == ".css" else "application/javascript"
            body = asset.read_bytes()
        elif path in ("/", "/index.html"):
            kind, body = "text/html; charset=utf-8", render()
        else:
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8010
    print(f"Xem thu he thiet ke: http://localhost:{port}")
    print("Du lieu mau, khong phai nguoi that.")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
