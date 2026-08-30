"""Map every screen reachable within two taps of the shell, then say what is NOT.

A claim of the form "feature F has no way in" is only as good as the sweep that
failed to find one. Grep over source proves a name is absent from a file; it
does not prove a finger cannot get there, and it says nothing about the screen
a button actually opens. This walks the product instead.

Method: enter through the Google door, then for each root (the four tabs and
the [+] create sheet) list every visible control, click each one, record what
came up -- heading text, control census, server calls -- and return to the root
before the next click. Depth two, breadth complete at each level.

Every interactive role is counted, not just `button`. A react-native-web tab
bar is role="tab" inside role="tablist", and a census that asks only for
buttons reports zero navigation on a build that has four tabs. That mistake
cost this team a whole work item.

Usage:
    python3 probe_ban_do_2_tang.py             # the real sweep
    python3 probe_ban_do_2_tang.py --canary    # block .js; every count must go 0
"""

import json
import sys

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8947/"
API_HOST = "127.0.0.1:46229"
BLOCK_JS = "--canary" in sys.argv
OUT = "/tmp/qa2-cth-ban-do.json"

# Controls that end the session or open a native picker the walk cannot leave.
KHONG_BAM = {"Đăng xuất", "Chọn ảnh từ máy", "Chụp bill"}

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
  for (const [k, s] of Object.entries(sels)) {
    out[k] = [...document.querySelectorAll(s)].filter(vis).length;
  }
  out.__innerTextLen = document.body.innerText.length;
  return out;
}
"""

# Tag every visible control with an index and hand back the census.
#
# Clicking by label looked simpler and was wrong: most controls here are
# `div[role=button]`, so `button:has-text(...)` matches nothing and the label
# only exists as innerText, so `[aria-label="..."]` matches nothing either.
# The first run of this probe reported ten dead controls on Khám phá that are
# in fact alive -- a defect of the measurement that reads exactly like a
# defect of the product. Index the DOM instead and click the node itself.
LIST_CONTROLS = """
() => {
  const vis = (el) => { const b = el.getBoundingClientRect();
                        return b.width > 0 && b.height > 0; };
  const sel = 'button,[role="button"],[role="tab"],[role="link"],a,' +
              '[role="menuitem"],[role="switch"],[role="checkbox"],[role="radio"]';
  const els = [...document.querySelectorAll(sel)].filter(vis);
  els.forEach((el, i) => el.setAttribute('data-qa2', String(i)));
  return els.map((el, i) => {
    const b = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return {
      i,
      role: el.getAttribute('role') || el.tagName.toLowerCase(),
      label: (el.getAttribute('aria-label') || el.innerText || '').trim().slice(0, 70),
      y: Math.round(b.y),
      tat: el.getAttribute('aria-disabled') === 'true' || el.disabled === true,
      khong_nhan_cham: st.pointerEvents === 'none',
    };
  });
}
"""

HEAD_TEXT = """
() => document.body.innerText.split('\\n').filter(s => s.trim()).slice(0, 6)
"""


def controls(page):
    return page.evaluate(LIST_CONTROLS)


def click_idx(page, idx, cho=1100):
    """Click the control tagged with this index by the last census."""
    page.locator(f'[data-qa2="{idx}"]').first.click(timeout=4000)
    page.wait_for_timeout(cho)


def click_label(page, label):
    """Click a control by label, matching the census (aria-label OR innerText)."""
    for c in controls(page):
        if c["label"] == label:
            click_idx(page, c["i"])
            return
    raise RuntimeError(f"không thấy control nhãn {label!r}")


def dang_nhap(page):
    """Google door -> first demo person -> shell."""
    page.goto(SITE, wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.get_by_text("Đăng ký với Google", exact=False).first.click()
    page.wait_for_timeout(1000)
    who = page.locator('[aria-label^="Vào app với tư cách"]').first
    label = who.get_attribute("aria-label")
    who.click()
    page.wait_for_timeout(2200)
    return label


def ve_goc(page, tab):
    """Return to a tab. A modal eats the tap, so close whatever is open first.

    Falls back to a full re-login: a sweep that silently keeps walking from
    the wrong screen prints a map of somewhere else.
    """
    for _ in range(3):
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(250)
        except Exception:  # noqa: BLE001
            pass
        for nhan in ("Đóng menu tạo mới", "Đóng", "Quay lại", "Huỷ", "‹"):
            try:
                click_label(page, nhan)
            except Exception:  # noqa: BLE001
                pass
        try:
            click_label(page, tab)
            return "ok"
        except Exception:  # noqa: BLE001
            continue
    dang_nhap(page)
    click_label(page, tab)
    return "phai-dang-nhap-lai"


def main():
    calls = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-proxy-server"])
        page = browser.new_page(viewport={"width": 390, "height": 844})
        if BLOCK_JS:
            page.route("**/*.js", lambda route: route.abort())
        page.on(
            "response",
            lambda r: calls.append({"m": r.request.method, "s": r.status, "u": r.url}),
        )
        page.goto(SITE, wait_until="networkidle")
        page.wait_for_timeout(1500)

        report = {"canary_block_js": BLOCK_JS, "site": SITE}
        report["man_mo_dau"] = page.evaluate(ROLE_CENSUS)

        if BLOCK_JS:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            browser.close()
            return

        report["nguoi"] = dang_nhap(page)

        report["shell"] = page.evaluate(ROLE_CENSUS)
        tabs = [c["label"] for c in controls(page) if c["role"] == "tab"]
        report["tabs"] = tabs

        # Roots: the four tabs, plus the [+] sheet opened from the first tab.
        report["cay"] = {}
        for tab in tabs:
            click_label(page, tab)
            tang1 = [
                c
                for c in controls(page)
                if c["role"] != "tab" and c["label"] and c["label"] not in KHONG_BAM
            ]
            node = {"tang1": [c["label"] for c in tang1], "con": {}}
            for c in tang1:
                mark = len(calls)
                lai = ""
                try:
                    # Re-census first: the root re-rendered when we came back,
                    # so last round's indices are stale. Match on label, and
                    # record a miss rather than clicking a neighbour.
                    click_label(page, c["label"])
                except RuntimeError:
                    # The label is gone because the previous click left state
                    # behind -- a category filter narrowed the list, a detail
                    # screen stayed open. That is the sweep's residue, not a
                    # missing control. Start the session over and try once more,
                    # so "not found" only ever means not found on a clean root.
                    dang_nhap(page)
                    click_label(page, tab)
                    lai = "phai-dang-nhap-lai-truoc-khi-bam"
                    mark = len(calls)
                    try:
                        click_label(page, c["label"])
                    except Exception as exc:  # noqa: BLE001
                        node["con"][c["label"]] = {
                            "loi_bam": str(exc)[:140],
                            "sau_khi_lam_lai_tu_dau": True,
                        }
                        ve_goc(page, tab)
                        continue
                except Exception as exc:  # noqa: BLE001 - record, do not stop the sweep
                    tat = [x for x in controls(page) if x["label"] == c["label"]]
                    node["con"][c["label"]] = {
                        "loi_bam": str(exc)[:140],
                        "trang_thai": tat[0] if tat else None,
                    }
                    ve_goc(page, tab)
                    continue
                node["con"][c["label"]] = {
                    "dau_man": page.evaluate(HEAD_TEXT),
                    "nut": [
                        x["label"]
                        for x in controls(page)
                        if x["role"] != "tab" and x["label"]
                    ][:25],
                    "goi": [
                        f"{k['m']} {k['s']} {k['u'].split(API_HOST)[-1][:70]}"
                        for k in calls[mark:]
                        if API_HOST in k["u"]
                    ],
                    "ve": ve_goc(page, tab),
                    "ghi_chu": lai,
                }
            report["cay"][tab] = node

        # The [+] sheet is not a tab; it is its own root.
        click_label(page, tabs[0])
        try:
            click_label(page, "Tạo mới")
            report["menu_tao"] = {
                "dau_man": page.evaluate(HEAD_TEXT),
                "muc": [c["label"] for c in controls(page) if c["role"] != "tab"],
            }
        except Exception as exc:  # noqa: BLE001
            report["menu_tao"] = {"loi": str(exc)[:150]}

        report["tong_goi_api"] = [
            f"{k['m']} {k['s']} {k['u'].split(API_HOST)[-1][:70]}"
            for k in calls
            if API_HOST in k["u"]
        ]
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(
            json.dumps(
                {k: report[k] for k in ("man_mo_dau", "shell", "tabs")},
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"đầy đủ: {OUT}")
        browser.close()


main()
