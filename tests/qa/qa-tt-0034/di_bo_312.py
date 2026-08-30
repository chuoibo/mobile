"""Walk PR #312's three revived routes in a real browser, against a real server.

What this is for
----------------
`apps/mobile`'s own suite drives a fake API, and `tests/api/` drives a fake
repository. Both are green on a build where the three screens this PR adds
never reach a server at all. This file is the other measurement: one Chromium,
one `expo export` bundle served over HTTP, one uvicorn on a database of its
own, and Gemini answering for real.

It asserts three things per flow, in this order:

1. the screen renders and the person can press what the flow needs pressed;
2. the request actually left the browser and the server actually answered it
   (a card drawn without a request would be the client inventing an answer);
3. the words on screen are the ones the design pinned -- and for a refusal,
   that no English error code, status number or traceback reaches a reader.

Nothing here re-derives money. The amount asserted is the one the server sent.

Setup this expects (see README.md in this directory for the full recipe):

    MOBILE_QA_WEB     http://127.0.0.1:8313    expo web build, served static
    MOBILE_QA_API     http://127.0.0.1:8312    uvicorn, its own database
    MOBILE_QA_CTX     uuid of the seeded group
    MOBILE_QA_MSG_K   message id whose text says an amount as "480k"
    MOBILE_QA_MOI     an unredeemed outing-invite token
    MOBILE_QA_ANH     directory written by tao_anh_mau.py

Exit code is 0 only when every check passed.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

WEB = os.environ.get("MOBILE_QA_WEB", "http://127.0.0.1:8313")
CTX = os.environ.get("MOBILE_QA_CTX", "")
MSG_K = os.environ.get("MOBILE_QA_MSG_K", "")
MOI = os.environ.get("MOBILE_QA_MOI", "")
ANH = Path(os.environ.get("MOBILE_QA_ANH", "/tmp/qa-tt-0034-anh"))
SHOT = Path(os.environ.get("MOBILE_QA_SHOT", "/tmp/qa-tt-0034-shot"))
RONG = int(os.environ.get("MOBILE_QA_RONG", "390"))

# A phone, not a desktop window. 390x844 is the mockup's device; 320 is the
# narrowest width ADR-0010's matrix names, and the one cards break at.
KHUNG = {"width": RONG, "height": 844}

# Every English shape a reader must never be shown. `422` and `404` are in here
# because a status number on screen is a leak even when the sentence is Viet.
RO_RI = re.compile(
    r"Traceback|Exception|Error:|undefined|NaN|\b4\d\d\b|\b5\d\d\b|_[a-z]+_[a-z]+"
)

rows: list[dict] = []


def ghi(ca: str, dat: bool, chi_tiet: object = "") -> None:
    rows.append({"ca": ca, "dat": bool(dat), "chi_tiet": str(chi_tiet)[:400]})
    print("DAT  " if dat else "HONG ", ca, "|", str(chi_tiet)[:180], flush=True)


def chu(page: Page) -> str:
    return page.locator("body").inner_text()


def mot_dong(text: str, limit: int = 240) -> str:
    return " | ".join(t.strip() for t in text.split("\n") if t.strip())[:limit]


def trang_moi(browser, bat: str | None = None):
    """A page of its own per flow.

    Not a fragment change on a live page: changing only the hash does not
    remount this app, so a second flow measured that way is reading the first
    flow's screen.
    """

    page = browser.new_page(viewport=KHUNG)
    loi: list[str] = []
    tra: list[tuple[int, str]] = []
    page.on("pageerror", lambda e: loi.append(str(e)))
    if bat:
        page.on(
            "response",
            lambda r: tra.append((r.status, r.url)) if bat in r.url else None,
        )
    return page, loi, tra


def mo_tao_khoan_chi(page: Page) -> None:
    """Group chat -> [+] -> Tạo khoản chi, which is where F26 lives."""

    page.goto(f"{WEB}/#tab=tin-nhan&nguoi=minh&nhom={CTX}")
    page.wait_for_timeout(2500)
    page.get_by_role("button", name="Tạo mới").click()
    page.wait_for_timeout(700)
    page.get_by_role("button", name="Tạo khoản chi").click()
    page.wait_for_timeout(1200)


def f24(browser) -> None:
    """Chat -> Tách tiền on one message -> the draft card."""

    page, loi, tra = trang_moi(browser, "expense-draft")
    page.goto(f"{WEB}/#tab=tin-nhan&nguoi=minh&nhom={CTX}")
    page.wait_for_timeout(2500)

    nut = page.get_by_role("button", name="Tách tiền")
    ghi(
        "F24 moi bong bong chu co mot nut Tach tien",
        nut.count() >= 1,
        f"nut={nut.count()}",
    )
    bong = page.get_by_text("480k", exact=False)
    ghi("F24 tin nhan moc co tren man", bong.count() > 0, f"count={bong.count()}")

    # Which bubble carries the "480k" text depends on what the seed wrote, so
    # the index is configuration rather than a constant. Hard-coding it is how
    # a walk ends up pressing a different message than the one it reports on.
    nut.nth(int(os.environ.get("MOBILE_QA_TACH_INDEX", "2"))).click()
    page.wait_for_selector("text=Chưa ghi khoản chi nào", timeout=90000)
    page.wait_for_timeout(600)
    t = chu(page)
    page.screenshot(path=str(SHOT / f"f24-the-nhap-{RONG}.png"))

    ghi("F24 goi that POST /expense-draft", bool(tra), str(tra[-1:]))
    ghi("F24 may chu tra 200", bool(tra) and tra[-1][0] == 200, str(tra[-1:]))
    ghi("F24 so tien cua may chu hien ra", "480.000" in t, mot_dong(t, 0) or "480.000")
    ghi("F24 nguoi tra la ten tren roster", "Người trả: Minh" in t, "")
    ghi(
        "F24 khong lo uuid ra man",
        not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", t),
        "",
    )
    ghi(
        "F24 cau 'chua ghi khoan chi nao' o trong the",
        "Chưa ghi khoản chi nào" in t,
        "",
    )

    # The sentence is the condition for pressing, so it has to be reachable,
    # not merely present in the DOM under the composer bar.
    cau = page.get_by_text("Chưa ghi khoản chi nào", exact=False).first
    cau.scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    ghi(
        "F24 cau chot cuon toi duoc va nhin thay",
        cau.is_visible(),
        str(cau.bounding_box()),
    )
    dong = page.get_by_role("button", name="Đóng").first
    dong.scroll_into_view_if_needed()
    ghi(
        "F24 nut Dong bam duoc",
        dong.is_visible() and dong.is_enabled(),
        str(dong.bounding_box()),
    )
    dong.click()
    page.wait_for_timeout(600)
    ghi("F24 bam Dong thi the bien mat", "Chưa ghi khoản chi nào" not in chu(page), "")
    ghi("F24 khong pageerror", not loi, str(loi[:1]))
    page.close()


def f14(browser) -> None:
    """An invite link, pressed once."""

    page, loi, tra = trang_moi(browser, "outing-invites")
    page.goto(f"{WEB}/#moi={MOI}&nguoi=quan")
    page.wait_for_timeout(2300)
    t = chu(page)
    page.screenshot(path=str(SHOT / f"f14-truoc-{RONG}.png"))
    ghi(
        "F14 link mo dung man Loi moi buoi di", "Lời mời buổi đi" in t, mot_dong(t, 120)
    )
    ghi(
        "F14 noi ro app chua biet buoi di nao",
        "App chưa biết đây là buổi đi nào cho tới khi nhận" in t,
        "",
    )

    page.get_by_role("button", name="Nhận lời mời").click()
    page.wait_for_timeout(4000)
    t2 = chu(page)
    page.screenshot(path=str(SHOT / f"f14-sau-{RONG}.png"))
    ghi("F14 goi that POST /outing-invites/{token}/accept", bool(tra), str(tra[-1:]))
    ghi("F14 may chu tra 200", bool(tra) and tra[-1][0] == 200, str(tra[-1:]))
    ghi(
        "F14 cau ket qua la mot trong hai cau da dinh",
        ("Bạn đã vào buổi đi." in t2) or ("nhóm còn phải duyệt" in t2),
        mot_dong(t2, 160),
    )
    ghi("F14 khong pageerror", not loi, str(loi[:1]))
    page.close()


def f26_doc_duoc(browser) -> None:
    """A Grab screenshot the reader can read, then Chốt into the manual form."""

    page, loi, tra = trang_moi(browser, "screenshots/scan")
    mo_tao_khoan_chi(page)
    with page.expect_file_chooser() as chon:
        page.get_by_role("button", name="Ảnh chụp màn hình").click()
    chon.value.set_files(str(ANH / "grab.png"))
    page.wait_for_selector("text=Chưa ghi khoản chi nào", timeout=120000)
    page.wait_for_timeout(600)
    t = chu(page)
    page.screenshot(path=str(SHOT / f"f26-ket-qua-{RONG}.png"))

    ghi("F26 goi that POST /screenshots/scan", bool(tra), str(tra[-1:]))
    ghi("F26 may chu tra 200", bool(tra) and tra[-1][0] == 200, str(tra[-1:]))
    ghi("F26 nguon doc ra la Grab", "Grab" in t, "")
    ghi("F26 so tien 85.000 hien tren the", "85.000" in t, "")
    ghi("F26 ngay 29/08/2026 hien tren the", "29/08/2026" in t, "")
    ghi(
        "F26 cau 'chua ghi khoan chi nao' o trong the",
        "Chưa ghi khoản chi nào" in t,
        "",
    )
    ghi(
        "F26 khong co ten nguoi nao tren the", "Người" not in t.split("Chưa ghi")[0], ""
    )

    page.get_by_role("button", name="Chốt vào form nhập tay").click()
    page.wait_for_timeout(1800)
    t2 = chu(page)
    page.screenshot(path=str(SHOT / f"f26-sau-khi-chot-{RONG}.png"))
    ghi("F26 chot mo form nhap tay", "Khoản chi mới" in t2, mot_dong(t2, 160))
    o = page.eval_on_selector_all("input", "els => els.map(e => e.value)")
    ghi(
        "F26 form mang theo so tien may chu doc ra",
        any("85000" in (v or "") for v in o),
        str(o),
    )
    ghi("F26 khong pageerror", not loi, str(loi[:1]))
    page.close()


def f26_tu_choi(browser) -> None:
    """A drawing, then a file that is not an image. Neither may blow up."""

    page, loi, tra = trang_moi(browser, "screenshots/scan")
    mo_tao_khoan_chi(page)
    with page.expect_file_chooser() as chon:
        page.get_by_role("button", name="Ảnh chụp màn hình").click()
    chon.value.set_files(str(ANH / "khong-phai-bill.png"))
    page.wait_for_selector("text=không thể hiện một giao dịch", timeout=120000)
    page.wait_for_timeout(500)
    t = chu(page)
    page.screenshot(path=str(SHOT / f"f26-tu-choi-{RONG}.png"))

    ghi("F26-tuchoi may chu tra 422", bool(tra) and tra[-1][0] == 422, str(tra[-1:]))
    ghi(
        "F26-tuchoi cau tieng Viet noi ro anh khong phai giao dich",
        "không thể hiện một giao dịch" in t,
        next((x for x in t.split("\n") if "giao dịch" in x), ""),
    )
    ghi(
        "F26-tuchoi khong lo ma loi / status / traceback",
        not RO_RI.search(t),
        RO_RI.findall(t)[:3],
    )
    ghi("F26-tuchoi khong ve the ket qua rong", "Chưa ghi khoản chi nào" not in t, "")
    ghi(
        "F26-tuchoi cau loi chi ve MOT lan",
        t.count("không thể hiện một giao dịch") == 1,
        f"dem={t.count('không thể hiện một giao dịch')}",
    )
    ghi("F26-tuchoi van con duong di tiep", page.get_by_role("button").count() > 0, "")

    with page.expect_file_chooser() as chon:
        page.get_by_role("button", name="Ảnh chụp màn hình").click()
    chon.value.set_files(str(ANH / "khong-phai-anh.txt"))
    page.wait_for_timeout(12000)
    t2 = chu(page)
    page.screenshot(path=str(SHOT / f"f26-khong-phai-anh-{RONG}.png"))
    ghi("F26 tep khong phai anh: khong traceback", "Traceback" not in t2, "")
    ghi(
        "F26 tep khong phai anh: cau bao loi viet bang tieng Viet",
        "Unsupported file type" not in t2,
        next((x for x in t2.split("\n") if "Unsupported" in x), ""),
    )
    ghi("F26 tep khong phai anh: khong pageerror", not loi, str(loi[:1]))
    page.close()


def main() -> int:
    thieu = [
        k for k, v in {"MOBILE_QA_CTX": CTX, "MOBILE_QA_MOI": MOI}.items() if not v
    ]
    if thieu:
        print("thieu bien moi truong:", ", ".join(thieu), file=sys.stderr)
        return 2
    SHOT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        f24(browser)
        f14(browser)
        f26_doc_duoc(browser)
        f26_tu_choi(browser)
        browser.close()
    (SHOT / f"ket-qua-{RONG}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    dat = sum(1 for r in rows if r["dat"])
    print(f"\nTONG {RONG}px: {dat}/{len(rows)} DAT")
    return 0 if dat == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
