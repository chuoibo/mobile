"""Walk the shell on a build of THIS sha and record what each tab reaches.

Why this file exists a second time. The 36/47 count was measured at 19b4760.
Two merges since then add screens rather than routes -- #382 gives the four
"AI understands the group" reads a caller, #408 gives the chat expense draft a
commit button -- and a count that is not re-walked after that is a count about
a tree nobody is running.

Two things this probe refuses to do, both learned from earlier runs in this
repo:

  - It never lists controls with `button, [role=button], a` alone. A tab bar
    rendered by react-native-web carries role="tab" inside role="tablist" and
    matches none of those three, and the resulting 0 reads exactly like "this
    build has no navigation" -- which is how a lane was sent to build a tab bar
    that already existed.
  - It never clicks by visible label. Most controls here are div[role=button]
    whose label exists only as innerText, so `button:has-text(...)` times out on
    a control that is alive and reports it dead. Every click goes through a
    data-qa2 index stamped during the census.

`--canary` blocks every .js response. A run that reports the same census with
the bundle blocked is measuring its own expectations, not the build.
"""

import json
import sys

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8951/"
API_HOST = "127.0.0.1:45465"
BLOCK_JS = "--canary" in sys.argv

# Every interactive role, not just button. See the module docstring.
ROLE_CENSUS = """
() => {
  const vis = (el) => { const b = el.getBoundingClientRect();
                        return b.width > 0 && b.height > 0; };
  const sels = {
    button: 'button,[role="button"]', tab: '[role="tab"]',
    tablist: '[role="tablist"]', link: 'a,[role="link"]',
    menuitem: '[role="menuitem"]', switch: '[role="switch"]',
    checkbox: '[role="checkbox"]', radio: '[role="radio"]',
    input: 'input', select: 'select',
  };
  const out = {};
  for (const [k, s] of Object.entries(sels))
    out[k] = [...document.querySelectorAll(s)].filter(vis).length;
  out.__innerTextLen = document.body.innerText.length;
  return out;
}
"""

# Stamps data-qa2 so the caller can click by index instead of by label.
STAMP_AND_LIST = """
() => {
  const vis = (el) => { const b = el.getBoundingClientRect();
                        return b.width > 0 && b.height > 0; };
  const sel = 'button,[role="button"],[role="tab"],[role="link"],a,'
            + '[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"]';
  const els = [...document.querySelectorAll(sel)].filter(vis);
  return els.map((el, i) => {
    el.setAttribute('data-qa2', String(i));
    const b = el.getBoundingClientRect();
    return {
      i,
      role: el.getAttribute('role') || el.tagName.toLowerCase(),
      label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 70),
      y: Math.round(b.y),
      disabled: el.getAttribute('aria-disabled') === 'true',
    };
  });
}
"""


def dang_nhap(page):
    """Google door -> first person. Returns the aria-label of who was picked."""
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
    out = {"sha_bundle": "5220ebd", "canary_block_js": BLOCK_JS, "site": SITE}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-proxy-server"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        if BLOCK_JS:
            page.route("**/*.js", lambda route: route.abort())
        page.on(
            "response",
            lambda r: calls.append(f"{r.request.method} {r.status} {r.url}"),
        )

        if BLOCK_JS:
            page.goto(SITE, wait_until="networkidle")
            page.wait_for_timeout(1500)
            out["census_man_dau"] = page.evaluate(ROLE_CENSUS)
            out["controls"] = page.evaluate(STAMP_AND_LIST)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            browser.close()
            return

        out["nguoi_da_chon"] = dang_nhap(page)
        out["census_shell"] = page.evaluate(ROLE_CENSUS)

        # Walk each tab: what does the tab reach, and what does it call.
        #
        # Selected by aria-label, never by index among role=tab. Tin nhắn
        # renders four sub-tabs (Chat/Plan/Thành viên/File) that are also
        # role=tab, so `nth(3)` lands on "File" once you are inside it and the
        # walk reports the messages screen as the contents of "Cá nhân".
        tabs = page.locator('[role="tablist"] >> [role="tab"]')
        nhan_tab = [
            tabs.nth(i).get_attribute("aria-label") for i in range(tabs.count())
        ]
        out["nhan_tab_duoi"] = nhan_tab
        ten_tab = [(n or "").split(":")[0] for n in nhan_tab]
        out["ten_tab"] = ten_tab

        out["theo_tab"] = {}
        for nhan, ten in zip(nhan_tab, ten_tab):
            truoc = len(calls)
            page.locator(f'[role="tab"][aria-label="{nhan}"]').first.click()
            page.wait_for_timeout(2000)
            controls = page.evaluate(STAMP_AND_LIST)
            out["theo_tab"][ten] = {
                "so_control": len(controls),
                "controls": controls,
                "chu": page.evaluate("() => document.body.innerText")[:1400],
                "goi_api": [c for c in calls[truoc:] if API_HOST in c],
            }

        out["tat_ca_goi_api"] = [c for c in calls if API_HOST in c]
        page.screenshot(path="/tmp/qa2-do47-shell.png")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        browser.close()


main()
