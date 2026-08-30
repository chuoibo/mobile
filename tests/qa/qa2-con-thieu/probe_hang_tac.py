"""The rows that have a path and die on it: where exactly, and with what code.

"Tắc" is only a useful label when it names the step and the status. F43/F44
were watched dying in the map sweep (`GET 403` on map and heatmap); this walks
the two that the sweep could not reach at depth two:

  F45  Khám phá -> Bản đồ nhóm -> Tìm điểm hẹn -> pick areas -> Tìm chỗ gặp
  F24  Tin nhắn -> type an expense -> Tách tiền -> where does the card end

F24 waits on a model round trip, so it polls past "Đang đọc…" instead of
reading the screen once and reporting the placeholder as the answer.
"""

import json

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8947/"
API = "127.0.0.1:46229"
OUT = "/tmp/qa2-cth-tac.json"

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


def bam(page, chua, cho=1800, thu_tu_cuoi=False):
    hits = [c for c in page.evaluate(CONTROLS) if chua.lower() in c["label"].lower()]
    if not hits:
        raise RuntimeError(f"không có control nào chứa {chua!r}")
    c = hits[-1] if thu_tu_cuoi else hits[0]
    page.locator(f'[data-qa2="{c["i"]}"]').first.click(timeout=5000)
    page.wait_for_timeout(cho)
    return c["label"]


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
        page.goto(SITE, wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.get_by_text("Đăng ký với Google", exact=False).first.click()
        page.wait_for_timeout(1000)
        page.locator('[aria-label^="Vào app với tư cách"]').first.click()
        page.wait_for_timeout(2500)

        # --- F45 ---
        calls.clear()
        bam(page, "Xem bản đồ của nhóm", cho=2500)
        out["f45_ban_do"] = {
            "goi": [c for c in calls if API in c],
            "nut": [c["label"] for c in page.evaluate(CONTROLS)][:20],
        }
        calls.clear()
        try:
            bam(page, "điểm hẹn", cho=2500)
            out["f45_man_diem_hen"] = {
                "goi": [c for c in calls if API in c],
                "nut": [c["label"] for c in page.evaluate(CONTROLS)][:20],
                "chu": page.evaluate("() => document.body.innerText")[:500],
            }
            khu = page.locator('[aria-label^="Thêm một người xuất phát"]')
            for i in range(min(2, khu.count())):
                khu.nth(i).click()
                page.wait_for_timeout(700)
            calls.clear()
            bam(page, "Tìm chỗ gặp", cho=3500)
            out["f45_ket_qua"] = {
                "goi": [c for c in calls if API in c],
                "chu": page.evaluate("() => document.body.innerText")[:800],
            }
            page.screenshot(path="/tmp/qa2-cth-f45.png")
        except Exception as exc:  # noqa: BLE001
            out["f45_dung_o"] = str(exc)[:200]

        # --- F24 ---
        page.get_by_label("Tin nhắn: chat nhóm và AI").click()
        page.wait_for_timeout(2500)
        page.get_by_label("Ô nhập tin nhắn").fill(
            "Tiền nướng tối qua 360k, mình trả trước nhé"
        )
        page.get_by_label("Gửi tin nhắn").click()
        page.wait_for_timeout(2000)
        calls.clear()
        try:
            bam(page, "Tách tiền", cho=2000, thu_tu_cuoi=True)
        except Exception as exc:  # noqa: BLE001
            out["f24_khong_co_nut_tach_tien"] = str(exc)[:160]
        chu = ""
        for _ in range(25):
            page.wait_for_timeout(2000)
            chu = page.evaluate("() => document.body.innerText")
            if "Đang đọc" not in chu:
                break
        out["f24"] = {
            "goi": [c for c in calls if API in c],
            "chu_cuoi": chu[-1000:],
            "nut_tren_the": [c["label"] for c in page.evaluate(CONTROLS)],
        }
        page.screenshot(path="/tmp/qa2-cth-f24.png")

        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(json.dumps(out, ensure_ascii=False, indent=1)[:5000])
        browser.close()


main()
