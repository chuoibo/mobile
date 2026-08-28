"""Dev-only preview server for the guest page. Never imported in production.

The guest page is the one surface nobody on this team can check with a test:
a whitelist test proves no field leaks, but nothing proves the page is
readable, tappable, or calm. This serves it with fixture data so a human can
look at it.

    python3 -m app.web.preview        then open http://localhost:8000

Query parameter `state` switches between the situations worth reviewing:
one, two, expired, revoked, limited, reported, confirmed.
All data is obviously fake.
"""

from __future__ import annotations

import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

from app.payments.vietqr import build_payload  # noqa: E402
from app.web.guest_view import NEUTRAL_PREVIEW, build_guest_view  # noqa: E402
from app.web.qr import payload_to_png_data_uri  # noqa: E402

WEB = pathlib.Path(__file__).resolve().parent
STATES = ("one", "two", "expired", "revoked", "limited", "reported", "confirmed")


def _obligation(oid, occasion, amount, who, bank, bin_code, account, holder, note):
    return {
        "obligation_id": oid,
        "occasion_label": occasion,
        "amount_vnd": amount,
        "recipient_display_name": who,
        "bank_name": bank,
        "bank_bin": bin_code,
        "account_number": account,
        "account_holder_name": holder,
        "transfer_note": note,
        "qr_payload": build_payload(bank_bin=bin_code, account_number=account,
                                    amount_vnd=amount, note=note),
    }


def fixture(state: str) -> dict:
    lau = _obligation("o1", "bữa lẩu tối thứ bảy", 82000, "Nam",
                      # repo-guard: allow=long-number reason=synthetic-fixture-never-real-participant-data
                      "Techcombank", "970407", "19036812345678",
                      "NGUYEN VAN NAM", "Lau T7")
    xe = _obligation("o2", "tiền xe về Vũng Tàu", 145000, "Quyên",
                     # repo-guard: allow=long-number reason=synthetic-fixture-never-real-participant-data
                     "Vietcombank", "970436", "1017339284",
                     "TRAN THI QUYEN", "Xe Vung Tau")

    envelope = {
        "recorded_by_display_name": "Nam",
        "claimed_person_display_name": "Hà",
        "link_state": "active",
        "obligations": [lau],
    }
    if state == "two":
        envelope["obligations"] = [lau, xe]
    elif state in ("expired", "revoked"):
        envelope["link_state"] = state
    elif state == "limited":
        envelope.update(reports_used=3, reports_allowed=3, objections_used=2, objections_allowed=2)
    elif state == "reported":
        envelope["obligations"] = [{**lau, "already_reported": True}]
    elif state == "confirmed":
        envelope["obligations"] = [{**lau, "receiver_confirmed": True}]
    return envelope


def render(state: str) -> bytes:
    view = build_guest_view(fixture(state))
    for block in view["blocks"]:
        block["qr_image_data_uri"] = payload_to_png_data_uri(block["qr_payload"])
    env = Environment(loader=FileSystemLoader(str(WEB / "templates")),
                      autoescape=select_autoescape(["html"]))
    html = env.get_template("guest.html").render(
        view=view, preview=NEUTRAL_PREVIEW, token="xem-thu"
    )
    switcher = (
        '<nav style="max-width:26rem;margin:1.5rem auto 0;text-align:center;'
        'font:400 13px system-ui;opacity:.65">'
        + " ".join(f'<a href="/?state={s}" style="color:inherit;padding:.25rem">{s}</a>' for s in STATES)
        + "<br><span>xem thử, dữ liệu giả</span></nav>"
    )
    return html.replace("</body>", switcher + "</body>").encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path)
        if route.path.startswith("/static/"):
            asset = (WEB / "static" / pathlib.Path(route.path).name).resolve()
            if not asset.is_file() or WEB / "static" not in asset.parents:
                return self.send_error(404)
            kind = "text/css" if asset.suffix == ".css" else "application/javascript"
            body = asset.read_bytes()
        else:
            state = parse_qs(route.query).get("state", ["one"])[0]
            if state not in STATES:
                return self.send_error(404, "unknown state")
            kind, body = "text/html; charset=utf-8", render(state)
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Xem thu trang khach: http://localhost:{port}")
    print(f"Cac trang thai: {', '.join(STATES)}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
