"""Google door: does the shell have navigation, and what is reachable from it.

Counts EVERY interactive role, not just role=button. A tab bar rendered by
react-native-web carries role="tab" inside role="tablist"; a probe that asks
for buttons alone reports zero navigation on a build that has four tabs.
"""

import json
import sys

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8946/"
BLOCK_JS = "--canary" in sys.argv

ROLE_CENSUS = """
() => {
  const vis = (el) => {
    const b = el.getBoundingClientRect();
    return b.width > 0 && b.height > 0;
  };
  const sels = {
    button: 'button,[role="button"]',
    tab: '[role="tab"]',
    tablist: '[role="tablist"]',
    link: 'a,[role="link"]',
    menuitem: '[role="menuitem"]',
    switch: '[role="switch"]',
    checkbox: '[role="checkbox"]',
    radio: '[role="radio"]',
    input: 'input',
    select: 'select',
  };
  const out = {};
  for (const [k, s] of Object.entries(sels)) {
    out[k] = [...document.querySelectorAll(s)].filter(vis).length;
  }
  out.__innerTextLen = document.body.innerText.length;
  return out;
}
"""

LIST_CONTROLS = """
() => {
  const vis = (el) => {
    const b = el.getBoundingClientRect();
    return b.width > 0 && b.height > 0;
  };
  const sel = 'button,[role="button"],[role="tab"],[role="link"],a,[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"]';
  return [...document.querySelectorAll(sel)].filter(vis).map((el) => {
    const b = el.getBoundingClientRect();
    return {
      role: el.getAttribute('role') || el.tagName.toLowerCase(),
      label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 60),
      y: Math.round(b.y),
    };
  });
}
"""


def main():
    calls = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-proxy-server"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        if BLOCK_JS:
            page.route("**/*.js", lambda route: route.abort())
        page.on(
            "response",
            lambda r: calls.append(f"{r.request.method} {r.status} {r.url}"),
        )
        page.goto(SITE, wait_until="networkidle")
        page.wait_for_timeout(1500)

        report = {"canary_block_js": BLOCK_JS}
        report["truoc_khi_dang_nhap"] = page.evaluate(ROLE_CENSUS)
        report["controls_man_mo_dau"] = page.evaluate(LIST_CONTROLS)

        if not BLOCK_JS:
            page.get_by_text("Đăng ký với Google", exact=False).first.click()
            page.wait_for_timeout(1200)
            report["controls_danh_sach_nguoi"] = page.evaluate(LIST_CONTROLS)
            # Pick the first "Vào app với tư cách X" entry.
            first = page.locator('[aria-label^="Vào app với tư cách"]').first
            report["nguoi_da_chon"] = first.get_attribute("aria-label")
            first.click()
            page.wait_for_timeout(2500)

        report["sau_khi_vao_shell"] = page.evaluate(ROLE_CENSUS)
        report["controls_trong_shell"] = page.evaluate(LIST_CONTROLS)
        page.screenshot(path="/tmp/qa2-cua-google.png")
        report["loi_goi_api"] = [c for c in calls if "127.0.0.1:48045" in c]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        browser.close()


main()
