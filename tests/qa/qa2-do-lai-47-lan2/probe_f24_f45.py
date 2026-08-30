"""F24 (chốt khoản chi đọc từ chat) and F45 (điểm hẹn) -- the two rows whose
first walk was defeated by the probe, not by the product.

Both failures were mine and both are worth naming, because each produces a
false dead row:

  F24  the chat keeps every message from every earlier run, so "click the first
       control labelled Tách tiền" clicks a card from twenty minutes ago whose
       draft was already dismissed. The newest message is the one under test.
  F45  the area list is preceded by "Quay lại bản đồ nhóm", which is a button
       like any other. Clicking the first two "buttons" navigated away and the
       row was recorded as having no area picker.
"""

import json
import sys

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8951/"
API_HOST = "127.0.0.1:45465"
BLOCK_JS = "--canary" in sys.argv

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
      label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 70),
      disabled: el.getAttribute('aria-disabled') === 'true' };
  });
}
"""

KET_QUA = {}


def stamp(page):
    return page.evaluate(STAMP_AND_LIST)


def bam(page, chua, cuoi=False, bat_dau=False):
    """Click a control by label. `cuoi=True` takes the LAST match, not the first."""
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
    page.wait_for_timeout(1500)
    return c["label"]


def tab(page, ten):
    page.locator(f'[role="tab"][aria-label^="{ten}"]').first.click()
    page.wait_for_timeout(1800)


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
    out = KET_QUA
    out["canary_block_js"] = BLOCK_JS
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-proxy-server"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        if BLOCK_JS:
            page.route("**/*.js", lambda route: route.abort())
        page.on(
            "response", lambda r: calls.append(f"{r.request.method} {r.status} {r.url}")
        )

        if BLOCK_JS:
            page.goto(SITE, wait_until="networkidle")
            page.wait_for_timeout(1500)
            out["canary"] = {
                "controls": len(stamp(page)),
                "innerTextLen": page.evaluate("() => document.body.innerText.length"),
            }
            print(json.dumps(out, ensure_ascii=False, indent=2))
            browser.close()
            return

        out["nguoi"] = dang_nhap(page)

        # ---- F24 ------------------------------------------------------------
        tab(page, "Tin nhắn")
        cau = "Tiền nướng tối qua 360k, mình trả trước nhé"
        page.get_by_label("Ô nhập tin nhắn").fill(cau)
        page.wait_for_timeout(400)
        bam(page, "Gửi tin nhắn")
        page.wait_for_timeout(2500)
        truoc = len(calls)
        out["f24_nut_tach"] = bam(page, "Tách tiền", cuoi=True)
        page.wait_for_function(
            "() => !document.body.innerText.includes('Đang đọc…')", timeout=60000
        )
        page.wait_for_timeout(1000)
        out["f24_chu_the"] = page.evaluate("() => document.body.innerText")[-1100:]
        out["f24_nut_tren_the"] = [c["label"] for c in stamp(page)]
        page.screenshot(path="/tmp/qa2-do47-f24-the.png")
        try:
            out["f24_nut_ghi"] = bam(page, "Ghi khoản chi", cuoi=True)
            page.wait_for_timeout(3000)
            out["f24_chu_sau_ghi"] = page.evaluate("() => document.body.innerText")[
                -1100:
            ]
            page.screenshot(path="/tmp/qa2-do47-f24-da-ghi.png")
        except AssertionError as e:
            out["f24_nut_ghi"] = f"KHONG CO: {e}"
        out["f24_api"] = [c for c in calls[truoc:] if API_HOST in c]

        # ---- F45 ------------------------------------------------------------
        tab(page, "Khám phá")
        page.get_by_text("Xem bản đồ của nhóm", exact=False).first.wait_for(
            timeout=15000
        )
        bam(page, "Xem bản đồ của nhóm")
        truoc = len(calls)
        out["f45_nut"] = bam(page, "Tìm điểm hẹn")
        # Only real origin pickers. "Quay lại bản đồ nhóm" sits above them and
        # is a button too; clicking it navigates away from the row under test.
        khu = [
            c
            for c in stamp(page)
            if c["label"].startswith("Thêm một người xuất phát từ")
        ]
        out["f45_so_khu"] = len(khu)
        out["f45_da_chon"] = [bam(page, c["label"], bat_dau=True) for c in khu[:2]]
        out["f45_nut_tim"] = bam(page, "Tìm chỗ gặp")
        page.wait_for_timeout(2500)
        out["f45_chu"] = page.evaluate("() => document.body.innerText")[:1100]
        out["f45_api"] = [c for c in calls[truoc:] if API_HOST in c]
        page.screenshot(path="/tmp/qa2-do47-f45.png")

        out["tat_ca_api"] = [c for c in calls if API_HOST in c]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        browser.close()


try:
    main()
except Exception as e:  # noqa: BLE001 -- the message is the artifact
    KET_QUA["probe_chet"] = f"{type(e).__name__}: {e}"[:400]
    print(json.dumps(KET_QUA, ensure_ascii=False, indent=2))
    raise
