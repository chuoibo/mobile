"""Walk only the rows the diff 19b4760..880cd6d could have moved.

Three areas, because three merges touched them:

  F24              #408 gave the chat expense draft a commit button. The row was
                   TẮC because the card said "bạn còn phải chốt" and then
                   offered only "Đóng". Does the button write to the ledger.
  F31 F32 F33 F34  #382 added `screens/ai-hieu-nhom`, which reads four routes
                   that had no caller. Two of those rows were KHÔNG-CÓ-ĐƯỜNG.
  F43 F44 F45      unchanged by the diff, re-walked because #411 established the
                   403s come from a context_id the client hardcodes. The point
                   here is to record WHICH id the browser puts on the wire, not
                   to re-ask whether the server is healthy -- curl already
                   answered that with the real group.

Clicks go through data-qa2 indices stamped at census time; see
probe_di_bo_shell.py for why label clicking is not used in this tree.
"""

import json
import sys

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8953/"
API_HOST = "127.0.0.1:45812"
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


def bam(page, chua, phai_co=None):
    """Re-stamp, then click the first control whose label contains `chua`.

    Re-stamping on every call is not defensive noise. React replaces nodes on
    re-render, which drops the data-qa2 attribute set during an earlier census,
    and the click then waits 30s for an index that no longer exists -- a dead
    probe that reads like a dead button.

    Raises rather than returning quietly: a silent miss here would be recorded
    as "the feature has no door", which is the exact misreading this repo has
    already made twice.
    """
    for c in stamp(page):
        if chua.lower() in c["label"].lower() and (phai_co is None or phai_co(c)):
            page.locator(f'[data-qa2="{c["i"]}"]').first.click()
            page.wait_for_timeout(1800)
            return c["label"]
    raise AssertionError(
        f"khong thay control chua {chua!r}; co: {[c['label'] for c in stamp(page)]}"
    )


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

        # ---- F31/F32/F33/F34 -- màn "AI hiểu nhóm" -------------------------
        tab(page, "Tin nhắn")
        truoc = len(calls)
        out["f31_34_nhan_nut"] = bam(page, "AI hiểu nhóm")
        # The four reads include a live Gemini call, so the screen sits on
        # "Đang đọc dữ liệu nhóm…" for seconds. Screenshotting before that
        # clears records the spinner as the feature's content.
        page.wait_for_function(
            "() => !document.body.innerText.includes('Đang đọc dữ liệu nhóm')",
            timeout=60000,
        )
        page.wait_for_timeout(800)
        out["f31_34_goi_api"] = [c for c in calls[truoc:] if API_HOST in c]
        out["f31_34_chu"] = page.evaluate("() => document.body.innerText")[:1800]
        page.screenshot(path="/tmp/qa2-do47-ai-hieu-nhom.png")
        bam(page, "Đóng")

        # ---- F24 -- khoản chi đọc từ chat ----------------------------------
        # By accessible name, not by tag: react-native-web renders the composer
        # as a bare <input> with no type attribute, so `input[type=text]` finds
        # nothing and the run dies where the product is fine.
        page.get_by_label("Ô nhập tin nhắn").fill(
            "Tiền nướng tối qua 360k, mình trả trước nhé"
        )
        page.wait_for_timeout(400)
        bam(page, "Gửi tin nhắn", phai_co=lambda c: not c["disabled"])
        page.wait_for_timeout(1500)
        truoc = len(calls)
        out["f24_nhan_nut_tach"] = bam(page, "Tách tiền")
        out["f24_the_nhap_chu"] = page.evaluate("() => document.body.innerText")[-900:]
        out["f24_nut_tren_the"] = [c["label"] for c in stamp(page)]
        page.screenshot(path="/tmp/qa2-do47-f24-the.png")
        try:
            out["f24_nhan_nut_ghi"] = bam(page, "Ghi khoản chi")
            page.wait_for_timeout(2500)
            out["f24_sau_khi_ghi_chu"] = page.evaluate("() => document.body.innerText")[
                -900:
            ]
            page.screenshot(path="/tmp/qa2-do47-f24-da-ghi.png")
        except AssertionError as e:
            out["f24_nhan_nut_ghi"] = f"KHONG CO: {e}"
        out["f24_goi_api"] = [c for c in calls[truoc:] if API_HOST in c]

        # ---- F43/F44/F45 -- bản đồ nhóm ------------------------------------
        tab(page, "Khám phá")
        page.get_by_text("Xem bản đồ của nhóm", exact=False).first.wait_for(
            timeout=15000
        )
        truoc = len(calls)
        out["f43_nhan_nut"] = bam(page, "Xem bản đồ của nhóm")
        out["f43_chu"] = page.evaluate("() => document.body.innerText")[:900]
        out["f43_44_goi_api"] = [c for c in calls[truoc:] if API_HOST in c]
        page.screenshot(path="/tmp/qa2-do47-ban-do.png")
        try:
            truoc = len(calls)
            out["f45_nhan_nut"] = bam(page, "Tìm điểm hẹn")
            khu = [c for c in stamp(page) if c["role"] in ("button", "checkbox")]
            out["f45_control_khu"] = [c["label"] for c in khu][:14]
            for c in khu[:2]:
                bam(page, c["label"])
            out["f45_nhan_nut_tim"] = bam(page, "Tìm chỗ gặp")
            out["f45_chu"] = page.evaluate("() => document.body.innerText")[:900]
            out["f45_goi_api"] = [c for c in calls[truoc:] if API_HOST in c]
        except AssertionError as e:
            out["f45_nhan_nut"] = f"DUNG O DAY: {e}"

        out["tat_ca_goi_api"] = [c for c in calls if API_HOST in c]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        browser.close()


def chay():
    """Wrap main so a crash still prints the rows already walked.

    A probe that dies on row 9 and prints nothing reports zero evidence for
    rows 1-8 that it actually collected."""
    try:
        main()
    except Exception as e:  # noqa: BLE001 -- the message is the artifact
        KET_QUA["probe_chet"] = f"{type(e).__name__}: {e}"[:400]
        print(json.dumps(KET_QUA, ensure_ascii=False, indent=2))
        raise


chay()
