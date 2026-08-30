"""The rows with no way in: is that still true, and what kind of "no" is it?

Three different things get filed under one label, and they need three different
answers:

  no screen exists                 -> somebody has to build it
  a screen exists, no button       -> somebody has to wire it up
  a screen and a button exist      -> the row was mislabelled and must flip

This walks each one instead of grepping for it. The widget (F38) is the reason:
its screen used to be reachable only by fragment, and `VoTab` now hands
`KyNiem` an `onMoWidget` callback -- but a prop being passed is not a button
being rendered, and both a filter and an empty-list branch sit between them.
"""

import json

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8947/"
API = "127.0.0.1:46229"
OUT = "/tmp/qa2-cth-khong-duong.json"

CONTROLS = """
() => {
  const vis = (el) => { const b = el.getBoundingClientRect();
                        return b.width > 0 && b.height > 0; };
  const sel = 'button,[role="button"],[role="tab"],[role="link"],a,[role="menuitem"]';
  const els = [...document.querySelectorAll(sel)].filter(vis);
  els.forEach((el, i) => el.setAttribute('data-qa2', String(i)));
  return els.map((el, i) => ({
    i, label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 70),
  }));
}
"""


def bam(page, chua, cho=1500):
    """Click the first control whose label contains this substring."""
    for c in page.evaluate(CONTROLS):
        if chua.lower() in c["label"].lower():
            page.locator(f'[data-qa2="{c["i"]}"]').first.click(timeout=5000)
            page.wait_for_timeout(cho)
            return c["label"]
    raise RuntimeError(f"không có control nào chứa {chua!r}")


def dang_nhap(page):
    page.goto(SITE, wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.get_by_text("Đăng ký với Google", exact=False).first.click()
    page.wait_for_timeout(1000)
    page.locator('[aria-label^="Vào app với tư cách"]').first.click()
    page.wait_for_timeout(2500)


def main():
    calls = []
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-proxy-server"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.on(
            "response",
            lambda r: calls.append(f"{r.request.method} {r.status} {r.url}"),
        )

        # --- F30/F35/F38: [+] -> Kỷ niệm nhóm -> is there a widget button? ---
        dang_nhap(page)
        calls.clear()
        bam(page, "Tạo mới")
        bam(page, "Kỷ niệm nhóm", cho=2500)
        out["ky_niem"] = {
            "dau_man": page.evaluate(
                "() => document.body.innerText.split('\\n').filter(s=>s.trim()).slice(0,8)"
            ),
            "nut": [c["label"] for c in page.evaluate(CONTROLS)],
            "goi": [c for c in calls if API in c],
        }
        calls.clear()
        try:
            nhan = bam(page, "widget", cho=2500)
            out["f38"] = {
                "nut_da_bam": nhan,
                "dau_man": page.evaluate(
                    "() => document.body.innerText.split('\\n').filter(s=>s.trim()).slice(0,10)"
                ),
                "goi": [c for c in calls if API in c],
            }
            page.screenshot(path="/tmp/qa2-cth-f38.png")
        except Exception as exc:  # noqa: BLE001
            out["f38"] = {"khong_thay_nut": str(exc)[:160]}

        # --- F21 / F22: the screens exist, but only the ?man= door opens them ---
        for ten, man in (("f21", "nhan-mat"), ("f22", "mon-cua-toi")):
            calls.clear()
            page.goto(f"{SITE}?man={man}", wait_until="networkidle")
            page.wait_for_timeout(3000)
            out[ten] = {
                "cua_may_quet": f"?man={man}",
                "dau_man": page.evaluate(
                    "() => document.body.innerText.split('\\n').filter(s=>s.trim()).slice(0,12)"
                ),
                "nut": [c["label"] for c in page.evaluate(CONTROLS)][:15],
                "goi": [c for c in calls if API in c],
            }
            page.screenshot(path=f"/tmp/qa2-cth-{ten}.png")
            if ten == "f21":
                # F23 lives on this screen or nowhere: a confidence score is a
                # number printed next to a guessed face.
                out["f23"] = page.evaluate(
                    """() => {
                         const t = document.body.innerText;
                         return {
                           co_chu_tin_cay: /tin cậy|độ chắc|chắc chắn|confidence/i.test(t),
                           co_phan_tram: /\\d+\\s*%/.test(t),
                           trich: (t.match(/.{0,60}(tin cậy|\\d+\\s*%).{0,60}/i) || [null])[0],
                         };
                       }"""
                )

        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])
        browser.close()


main()
