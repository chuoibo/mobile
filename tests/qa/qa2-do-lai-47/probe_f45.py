"""F45 and F24 on the current bundle: two rows that were TẮC, checked by clicking.

Carrying a label forward is cheaper than measuring it, and wrong as soon as
something moved. Both rows are re-walked here rather than copied.
"""

import json

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8946/"
API = "127.0.0.1:48045"

calls = []
out = {}

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-proxy-server"])
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.on(
        "response", lambda r: calls.append(f"{r.request.method} {r.status} {r.url}")
    )
    page.goto(SITE, wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.get_by_text("Đăng ký với Google", exact=False).first.click()
    page.wait_for_timeout(1000)
    page.locator('[aria-label^="Vào app với tư cách"]').first.click()
    page.wait_for_timeout(2500)

    # --- F45: meet in the middle ---
    page.get_by_text("Xem bản đồ của nhóm", exact=False).first.click()
    page.wait_for_timeout(2500)
    calls.clear()
    page.get_by_text("Tìm điểm hẹn", exact=False).first.click()
    page.wait_for_timeout(2500)
    body = page.evaluate("() => document.body.innerText")
    # The screen offers areas first; pick two and ask.
    out["f45_buoc_1"] = {"calls": [c for c in calls if API in c], "text": body[:700]}
    calls.clear()
    labels = page.evaluate(
        """() => [...document.querySelectorAll('[role="button"]')]
              .filter(e => { const b = e.getBoundingClientRect(); return b.width > 0; })
              .map(e => e.getAttribute('aria-label') || e.innerText.trim().slice(0, 40))"""
    )
    out["f45_controls"] = labels
    khu = page.locator('[aria-label^="Thêm một người xuất phát"]')
    for i in range(min(2, khu.count())):
        khu.nth(i).click()
        page.wait_for_timeout(600)
    if [x for x in labels if "Tìm chỗ gặp" in (x or "")]:
        page.get_by_text("Tìm chỗ gặp", exact=False).first.click()
        page.wait_for_timeout(3000)
        out["f45_ket_qua"] = {
            "calls": [c for c in calls if API in c],
            "text": page.evaluate("() => document.body.innerText")[:700],
        }
    page.screenshot(path="/tmp/qa2-f45.png")

    # --- F24: expense draft from a chat message ---
    page.get_by_label("Tin nhắn: chat nhóm và AI").click()
    page.wait_for_timeout(2500)
    page.get_by_label("Ô nhập tin nhắn").fill(
        "Tiền nướng tối qua 360k, mình trả trước nhé"
    )
    page.get_by_label("Gửi tin nhắn").click()
    page.wait_for_timeout(1800)
    calls.clear()
    page.get_by_label("Tách tiền").last.click()
    page.wait_for_timeout(4000)
    out["f24"] = {
        "calls": [c for c in calls if API in c],
        "text": page.evaluate("() => document.body.innerText")[-900:],
        "controls": page.evaluate(
            """() => [...document.querySelectorAll('[role="button"],button')]
                  .filter(e => { const b = e.getBoundingClientRect(); return b.width > 0; })
                  .map(e => e.getAttribute('aria-label') || e.innerText.trim().slice(0, 40))"""
        ),
    }
    page.screenshot(path="/tmp/qa2-f24.png")

    print(json.dumps(out, ensure_ascii=False, indent=1))
    browser.close()
