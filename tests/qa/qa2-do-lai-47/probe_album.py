"""F36/F37: walk to the trip album by CLICKING, from the Google door.

Three tiers: shelf -> one trip -> AI reel. Each tier records the API calls it
caused, because a screen that renders from nothing proves no route is wired.
"""

import json
import re

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8946/"
API = "127.0.0.1:48045"
SKIP = re.compile(r"quay lại|đóng|tạo mới|khám phá|lên plan|tin nhắn|cá nhân", re.I)

LIST_CONTROLS = """
() => {
  const vis = (el) => {
    const b = el.getBoundingClientRect();
    return b.width > 0 && b.height > 0;
  };
  const sel = 'button,[role="button"],[role="tab"],[role="link"],a,[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"]';
  return [...document.querySelectorAll(sel)].filter(vis).map((el) => ({
    role: el.getAttribute('role') || el.tagName.toLowerCase(),
    aria: el.getAttribute('aria-label'),
    text: (el.innerText || '').trim().slice(0, 70),
    y: Math.round(el.getBoundingClientRect().y),
  }));
}
"""

calls = []
steps = {}


def snap(page, name):
    steps[name] = {
        "text": page.evaluate("() => document.body.innerText").strip()[:1500],
        "controls": page.evaluate(LIST_CONTROLS),
        "calls": [c for c in calls if API in c],
    }
    calls.clear()
    page.screenshot(path=f"/tmp/qa2-album-{name}.png")
    return steps[name]


def click(page, control):
    """Click the way the control identifies itself, label first."""
    if control.get("aria"):
        page.get_by_label(control["aria"], exact=True).first.click()
    else:
        page.get_by_text(control["text"].split("\n")[0], exact=False).first.click()


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
    page.wait_for_timeout(2200)
    calls.clear()

    page.get_by_label("Tạo mới").click()
    page.wait_for_timeout(900)
    snap(page, "01-sheet-tao-moi")

    page.get_by_text("Album chuyến đi", exact=False).first.click()
    page.wait_for_timeout(2500)
    shelf = snap(page, "02-ke-album")

    def pick(controls):
        for c in controls:
            name = c.get("aria") or c["text"]
            if name and not SKIP.search(name):
                return c
        return None

    trip = pick(shelf["controls"])
    steps["chuyen_da_bam"] = trip
    if trip:
        click(page, trip)
        page.wait_for_timeout(2500)
        one = snap(page, "03-mot-chuyen")

        reel = [
            c
            for c in one["controls"]
            if "phim" in ((c.get("aria") or "") + c["text"]).lower()
            or "reel" in ((c.get("aria") or "") + c["text"]).lower()
        ]
        steps["nut_reel"] = reel
        if reel:
            click(page, reel[0])
            page.wait_for_timeout(4000)
            snap(page, "04-thuoc-phim")

    print(json.dumps(steps, ensure_ascii=False, indent=1))
    browser.close()
