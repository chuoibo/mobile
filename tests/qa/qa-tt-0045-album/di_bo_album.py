"""QA tt-0045 -- walk the trip album (PR #379) in a real browser, twice.

Runs the same walk against two Expo web bundles: one built from `main` and one
built from `#379` merged into that same `main`. The pre-change run is the whole
point. "The album screen renders" is not a finding on its own -- the claim the
PR makes is that the album became REACHABLE, and only a run where it is not
reachable can tell those two apart.

Three things are measured, because three different failures are possible and a
screenshot alone catches none of them:

  1. Can a person get there by pressing?  The `[+]` sheet, no fragment at all.
     This is the door the brief cares about: a screen with no button pointing
     at it is the "KHONG-CO-DUONG" shape the PR says it is fixing.
  2. Do the three F36/F37 routes actually travel?  Read off the requests the
     browser really issues, not off the source.
  3. Does `X-Actor-ID` ride along?  `tests/test_actor_header_contract.py`
     reports this client as UNRESOLVED, which is a statement about the gate's
     static reader, not about the header. The two are told apart here.

The API is stubbed, and the payload shapes are copied from the SAME tree's
`openapi.json` rather than invented. An earlier pass of this probe invented a
`name` field where the server sends `place_name`; the screen fell back to the
id and printed a raw UUID, which looked exactly like a product bug and was the
probe's own. Anything asserted about a field here should be read against
`AlbumSummary` / `AlbumPhoto` / `AlbumPlace` / `ReelPick` in that file.

Run:
    python3 tests/qa/qa-tt-0045-album/di_bo_album.py <bundle-truoc> <bundle-sau>

Each bundle comes from, at the matching commit:
    cd apps/mobile && EXPO_PUBLIC_API_URL=http://api.build-check.invalid \\
      npx expo export --platform web --output-dir <dir> --clear
"""

from __future__ import annotations

import base64
import json
import sys
import threading
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

# Derived rather than written out. A padded literal like `1111...` is a long
# digit run, and the repo guard blocks those on sight -- it cannot tell a demo
# id from a bank account number. `nhom-demo.ts` solves it the same way.
_NS = uuid.NAMESPACE_URL


def _id(name: str) -> str:
    return str(uuid.uuid5(_NS, f"qa-tt-0045/{name}"))


CID = _id("context")
OID_A = _id("outing-a")
OID_B = _id("outing-b")
MID_1 = _id("memory-1")
MID_2 = _id("memory-2")

# 1x1 PNG, so a photo frame lays out with real bytes instead of a broken icon.
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def photo(mid: str, cap: str) -> dict:
    return {
        "memory_id": mid,
        "image_url": f"/contexts/{CID}/photos/{mid}",
        "caption": cap,
        "created_at": "2026-08-12T10:30:00Z",
        "reaction_count": 4,
        "comment_count": 1,
    }


def summary(oid: str, title: str, in_progress: bool) -> dict:
    return {
        "outing_id": oid,
        "title": title,
        "period_label": "Thang 8, 2026",
        "starts_on": "2026-08-10",
        "ends_on": "2026-08-12",
        "in_progress": in_progress,
        "photo_count": 2,
        "checkin_count": 3,
        "place_count": 2,
        "split_total_vnd": 1_240_000,
        "expense_count": 4,
        "headcount": 5,
        "cover": photo(MID_1, "Bua toi ngay hai"),
    }


SHELF = {
    "context_id": CID,
    "albums": [
        summary(OID_A, "Da Lat ba ngay", False),
        summary(OID_B, "Vung Tau cuoi tuan", True),
    ],
}

DETAIL = {
    "context_id": CID,
    "outing_id": OID_A,
    "title": "Da Lat ba ngay",
    "period_label": "Thang 8, 2026",
    "starts_on": "2026-08-10",
    "ends_on": "2026-08-12",
    "in_progress": False,
    "photos": [photo(MID_1, "Bua toi ngay hai"), photo(MID_2, "Sang o ho")],
    "photo_count": 2,
    # The second row carries `place_name: null` deliberately. That is not a
    # malformed row: `AlbumPlace.place_name` is declared nullable, and
    # `domain/album.py::_text` returns None for any blank or missing name, so
    # it is a state the real server can send. See the finding in the verdict.
    "places": [
        {"place_id": _id("place-1"), "place_name": "Quan Gio"},
        {"place_id": _id("place-2"), "place_name": None},
    ],
    "place_count": 2,
    "checkin_count": 3,
    "highlights": [photo(MID_1, "Bua toi ngay hai")],
    "split_total_vnd": 1_240_000,
    "expense_count": 4,
    "headcount": 5,
}

REEL = {
    "context_id": CID,
    "outing_id": OID_A,
    "reeled": True,
    "reason": "ok",
    "source": "ai",
    "title": "Ba ngay di cham o Da Lat",
    "picks": [
        {
            "memory_id": MID_1,
            "image_url": f"/contexts/{CID}/photos/{MID_1}",
            "caption": "Bua toi ngay hai",
            "place_name": "Quan Gio",
            "created_at": "2026-08-12T10:30:00Z",
            "reaction_count": 4,
            "comment_count": 1,
            "note": "Ca nhom ngoi lai lau nhat o day.",
        },
        {
            "memory_id": MID_2,
            "image_url": f"/contexts/{CID}/photos/{MID_2}",
            "caption": "Sang o ho",
            "place_name": "Ho Xuan Huong",
            "created_at": "2026-08-11T01:05:00Z",
            "reaction_count": 2,
            "comment_count": 0,
            "note": "Buoi sang duy nhat troi khong mua.",
        },
    ],
    "considered_count": 2,
}


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102 - keep the transcript readable
        pass


def serve(directory: str) -> int:
    """Bind port 0 and let the OS choose.

    Other lanes hold fixed ports on this box; a hardcoded one turns somebody
    else's server into my measurement.
    """

    def handler(*a, **k):
        return _Quiet(*a, directory=directory, **k)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def stub(route) -> None:
    """Answer with the shapes this tree's own openapi.json declares."""
    path = route.request.url.split("api.build-check.invalid", 1)[-1].split("?")[0]
    if "/photos/" in path:
        return route.fulfill(status=200, content_type="image/png", body=PIXEL)
    if path.endswith("/reel"):
        body = json.dumps(REEL)
    elif path.endswith("/albums"):
        body = json.dumps(SHELF)
    elif "/albums/" in path:
        body = json.dumps(DETAIL)
    else:
        # Everything else the shell asks for on the way in. Answered rather
        # than left hanging, so a missing stub shows up as a screen that
        # renders badly instead of a walk that times out for some other reason.
        body = "{}"
    return route.fulfill(status=200, content_type="application/json", body=body)


def _text(page) -> str:
    return page.evaluate("() => document.body.innerText || ''")


def cua_menu(page, base: str) -> dict:
    """Door one: press [+], press the row. No fragment -- a person's path."""
    page.goto("about:blank")
    page.goto(f"{base}/#nguoi=minh&nhom={CID}", wait_until="load")
    page.wait_for_timeout(2500)
    out: dict = {}
    try:
        page.get_by_label("Tao moi").first.click(timeout=4000)
    except Exception:
        # The label carries diacritics in the product; match on either form
        # rather than let an encoding detail read as a missing button.
        try:
            page.get_by_label("Tạo mới").first.click(timeout=4000)
        except Exception as exc:
            out["mo_duoc_menu"] = f"KHONG: {type(exc).__name__}"
            return out
    out["mo_duoc_menu"] = True
    page.wait_for_timeout(900)
    sheet = _text(page)
    out["co_dong_album"] = "Album chuyến đi" in sheet
    try:
        page.get_by_text("Album chuyến đi", exact=False).first.click(timeout=4000)
    except Exception as exc:
        out["bam_duoc"] = f"KHONG: {type(exc).__name__}"
        return out
    out["bam_duoc"] = True
    page.wait_for_timeout(2500)
    man = _text(page)
    out["toi_duoc_ke_album"] = "Album chuyến đi" in man and "Nhóm đã có" in man
    return out


def cua_dia_chi(page, base: str) -> dict:
    """Door two: `#vao=album`, then press inward, then back out one at a time.

    about:blank between loads on purpose: changing only the fragment does not
    remount, and a stale screen reads exactly like a screen that rendered.
    """
    seen: list[str] = []
    tieu_de: list[dict] = []

    def note(req):
        if "build-check.invalid" not in req.url:
            return
        seen.append(req.url.split("build-check.invalid", 1)[-1])
        if "/albums" in req.url:
            h = req.headers
            tieu_de.append(
                {
                    "duong": req.url.split("build-check.invalid", 1)[-1],
                    "X-Actor-ID": h.get("x-actor-id"),
                    "X-Actor-Contexts": h.get("x-actor-contexts"),
                    "X-Actor-Roles": h.get("x-actor-roles"),
                }
            )

    page.on("request", note)
    page.goto("about:blank")
    page.goto(f"{base}/#vao=album&nguoi=minh&nhom={CID}", wait_until="load")
    page.wait_for_timeout(2500)

    tang: list[str] = [_text(page)]
    for nhan in ("Da Lat ba ngay", "Đà Lạt ba ngày"):
        try:
            page.get_by_text(nhan, exact=False).first.click(timeout=3000)
            break
        except Exception:
            continue
    page.wait_for_timeout(2000)
    tang.append(_text(page))

    for nhan in ("Dựng thước phim", "Thước phim AI"):
        try:
            page.get_by_text(nhan, exact=False).first.click(timeout=3000)
            break
        except Exception:
            continue
    page.wait_for_timeout(2500)
    tang.append(_text(page))

    lui: list[str] = []
    for _ in range(3):
        try:
            page.get_by_label("Quay lại màn trước").first.click(timeout=2500)
        except Exception:
            break
        page.wait_for_timeout(1200)
        lui.append(_text(page)[:160])

    return {
        "tang": [t[:700] for t in tang],
        "lui": lui,
        "routes_album": sorted({r for r in seen if "/albums" in r}),
        "tieu_de": tieu_de,
    }


def main() -> int:
    ket: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for nhan, thu_muc in (("TRUOC", sys.argv[1]), ("SAU", sys.argv[2])):
            port = serve(thu_muc)
            time.sleep(0.5)
            base = f"http://127.0.0.1:{port}"
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()
            page.route("**build-check.invalid/**", stub)
            ket[nhan] = {"cua_menu": cua_menu(page, base)}
            ctx.close()

            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()
            page.route("**build-check.invalid/**", stub)
            ket[nhan]["cua_dia_chi"] = cua_dia_chi(page, base)
            ctx.close()
        browser.close()

    print(json.dumps(ket, ensure_ascii=False, indent=1))

    sau = ket["SAU"]
    truoc = ket["TRUOC"]
    dat = (
        truoc["cua_menu"].get("co_dong_album") is False
        and sau["cua_menu"].get("toi_duoc_ke_album") is True
        and len(sau["cua_dia_chi"]["routes_album"]) == 3
        and all(t["X-Actor-ID"] for t in sau["cua_dia_chi"]["tieu_de"])
    )
    print("\nKET LUAN:", "DAT" if dat else "KHONG DAT", file=sys.stderr)
    return 0 if dat else 1


if __name__ == "__main__":
    sys.exit(main())
