"""F24 alone, with a wait long enough for the model round trip.

The first attempt read the screen four seconds after the tap and caught the
"Đang đọc…" placeholder, which says nothing about where the row ends up. This
polls until that placeholder goes away.
"""

import json

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8946/"
API = "127.0.0.1:48045"

calls = []

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
    page.get_by_label("Tin nhắn: chat nhóm và AI").click()
    page.wait_for_timeout(2500)
    page.get_by_label("Ô nhập tin nhắn").fill(
        "Tiền nướng tối qua 360k, mình trả trước nhé"
    )
    page.get_by_label("Gửi tin nhắn").click()
    page.wait_for_timeout(1800)
    calls.clear()
    page.get_by_label("Tách tiền").last.click()

    text = ""
    for _ in range(30):
        page.wait_for_timeout(2000)
        text = page.evaluate("() => document.body.innerText")
        if "Đang đọc" not in text:
            break

    out = {
        "calls": [c for c in calls if API in c],
        "text_cuoi": text[-1200:],
        "controls": page.evaluate(
            """() => [...document.querySelectorAll('[role="button"],button')]
                  .filter(e => { const b = e.getBoundingClientRect(); return b.width > 0; })
                  .map(e => e.getAttribute('aria-label') || e.innerText.trim().slice(0, 40))"""
        ),
    }
    page.screenshot(path="/tmp/qa2-f24.png")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    browser.close()
