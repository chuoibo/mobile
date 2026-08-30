"""F22 "Món của tôi" -- the one row #415 could have moved, walked as a person walks it.

Why this file exists rather than a `?man=mon-cua-toi` visit: that URL renders the
screen, and `App.tsx` hands it `onMonCuaToi={() => {}}` with the sentence
"Cửa quét: màn này không đi đâu được." So the scan door proves the component
compiles and proves nothing about a path. F22 is only BẤM-ĐƯỢC if the door on
`goi-y` opens and the save reaches the server, which is what is measured here:

    Google -> nhóm -> chụp bill -> kết quả -> goi-y -> [Món của tôi]
    -> tick a dish -> [Lưu] -> POST /bills/{id}/my-items

`--canary` blocks every `.js` request. Every count below must go to zero; a
number that survives a blinded run is a number this probe invented.
`--kham-pha` prints the control census at each step instead of asserting, which
is how the labels below were found.
"""

import json
import sys

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8953/"
API_HOST = "127.0.0.1:45812"
BLOCK_JS = "--canary" in sys.argv
KHAM_PHA = "--kham-pha" in sys.argv
ANH = "/tmp/qa2-bill-lan3/ro.jpg"

STAMP_AND_LIST = """
() => {
  const vis = (el) => { const b = el.getBoundingClientRect();
                        return b.width > 0 && b.height > 0; };
  const sel = 'button,[role="button"],[role="tab"],[role="link"],a,'
            + '[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"]';
  const els = [...document.querySelectorAll(sel)].filter(vis);
  return els.map((el, i) => {
    el.setAttribute('data-qa2', String(i));
    return { i,
      role: el.getAttribute('role') || el.tagName.toLowerCase(),
      label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 80),
      disabled: el.getAttribute('aria-disabled') === 'true' };
  });
}
"""


def stamp(page):
    """Re-stamp before every click: React swaps nodes on re-render and a stale
    index is a 30s hang that reads exactly like a dead button."""
    return page.evaluate(STAMP_AND_LIST)


def bam(page, chua, cuoi=False, bat_dau=False, cho=1500):
    hop = [
        c
        for c in stamp(page)
        if (
            c["label"].startswith(chua)
            if bat_dau
            else chua.lower() in c["label"].lower()
        )
    ]
    if not hop:
        raise AssertionError(
            f"khong thay {chua!r}; co: {[c['label'] for c in stamp(page)]}"
        )
    c = hop[-1] if cuoi else hop[0]
    page.locator(f'[data-qa2="{c["i"]}"]').first.click()
    page.wait_for_timeout(cho)
    return c["label"]


def chu(page):
    return page.evaluate("() => document.body.innerText")


def anh(page, ten):
    return {
        "buoc": ten,
        "so_control": len(stamp(page)),
        "controls": [c["label"] for c in stamp(page)],
        "chu": chu(page)[:900],
    }


def dang_nhap(page):
    page.goto(SITE, wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.get_by_text("Đăng ký với Google", exact=False).first.click()
    page.wait_for_timeout(1200)
    first = page.locator('[aria-label^="Vào app với tư cách"]').first
    ai = first.get_attribute("aria-label")
    first.click()
    page.wait_for_timeout(2500)
    return ai


def main():
    calls = []
    out = {"sha_bundle": "880cd6d", "canary_block_js": BLOCK_JS, "site": SITE}
    buoc = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        if BLOCK_JS:
            ctx.route("**/*.js", lambda r: r.abort())
        page = ctx.new_page()
        page.on(
            "response",
            lambda r: calls.append(f"{r.request.method} {r.status} {r.url}")
            if API_HOST in r.url
            else None,
        )
        try:
            out["nguoi"] = dang_nhap(page)
            buoc.append(anh(page, "sau dang nhap"))

            # Into the bill flow. Labels read off the shell rather than
            # assumed; --kham-pha is how they were found. The bill door is
            # behind the "Tạo mới" menu, not on any tab.
            bam(page, "Tạo mới", cho=2000)
            bam(page, "Tạo khoản chi", cho=2500)
            buoc.append(anh(page, "chup-bill"))

            # Real photo through the real scan seam: `POST /receipts/scan` ->
            # Gemini -> `readingFromWire` -> `POST /bills`. A hand-written
            # `reading` would skip the joint #354 exists to cover.
            # Through the file chooser, not `set_input_files` on a selector:
            # RNW does not leave a queryable `input[type=file]` in the tree, so
            # the selector form times out and reads like a dead screen.
            with page.expect_file_chooser() as fc:
                bam(page, "Chọn ảnh bill", cho=500)
            fc.value.set_files(ANH)
            page.wait_for_timeout(25000)
            buoc.append(anh(page, "sau khi quet anh"))

            bam(page, "Tiếp tục", cho=3000)
            buoc.append(anh(page, "goi-y truoc khi chon nguoi"))

            # `POST /bills` does not fire on arrival at `goi-y` -- it waits for
            # a roster. Measured: with nobody picked the screen says "Chưa lưu
            # được" and the F22 door is grey with the bill-is-null sentence.
            # So the door is only reachable after somebody is on the bill, and
            # Minh has to be one of them (`khoaMonCuaToi`'s second lock).
            for ai_do in ("Thêm Minh vào nhóm", "Thêm Trang vào nhóm"):
                bam(page, ai_do, cho=1200)
            page.wait_for_timeout(4000)
            buoc.append(anh(page, "goi-y sau khi chon 2 nguoi"))

            if KHAM_PHA:
                out["buoc"] = buoc
                out["goi_api"] = list(calls)
                print(json.dumps(out, ensure_ascii=False, indent=2))
                return

            # F22 proper: the door on `goi-y`, then a tick, then the save.
            out["nhan_nut_f22"] = bam(page, "Món của tôi", cho=2500)
            buoc.append(anh(page, "mon-cua-toi"))

            truoc = len(calls)
            nhan = [c["label"] for c in stamp(page)]
            out["control_tren_man_f22"] = nhan
            # Tick one dish. Whatever the row control is called, it is not one
            # of the three chrome buttons, so take the first that is neither.
            chrome = (
                "Quay lại",
                "Lưu",
                "Đóng",
                "Khám phá",
                "Lên plan",
                "Tin nhắn",
                "Cá nhân",
                "Tạo mới",
            )
            hang = [
                c
                for c in stamp(page)
                if not any(c["label"].startswith(x) for x in chrome)
            ]
            out["so_mon_tick_duoc"] = len(hang)
            if hang:
                page.locator(f'[data-qa2="{hang[0]["i"]}"]').first.click()
                page.wait_for_timeout(1200)
                out["mon_da_tick"] = hang[0]["label"]

            out["nhan_nut_luu"] = bam(page, "Lưu", cho=4000)
            buoc.append(anh(page, "sau khi Luu"))
            out["goi_api_cua_f22"] = calls[truoc:]
            out["co_my_items"] = any("/my-items" in c for c in calls)
            out["buoc"] = buoc
        except Exception as e:  # noqa: BLE001 -- the message IS the finding
            out["dung_o_day"] = f"{type(e).__name__}: {e}"
            out["buoc"] = buoc
        finally:
            out["goi_api"] = calls
            b.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))


main()
