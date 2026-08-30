"""F16 after c5c74d5: ask the group AI for an hourly itinerary and see what lands.

The previous measurement got `asked_too_often` -- a rate gate, not grounding --
so this run reads the /ai-turn body itself instead of inferring the reason from
the sentence on screen.
"""

import json

from playwright.sync_api import sync_playwright

SITE = "http://127.0.0.1:8946/"
API = "127.0.0.1:48045"
CAU_HOI = (
    "Nhóm mình đi Đà Lạt cuối tuần này, lên giúp lịch trình chi tiết từng giờ "
    "cho ngày thứ bảy với mấy chỗ ăn uống trong nhóm nhé"
)

LIST_CONTROLS = """
() => {
  const vis = (el) => {
    const b = el.getBoundingClientRect();
    return b.width > 0 && b.height > 0;
  };
  const sel = 'button,[role="button"],[role="tab"],[role="link"],a';
  return [...document.querySelectorAll(sel)].filter(vis).map((el) => ({
    aria: el.getAttribute('aria-label'),
    text: (el.innerText || '').trim().slice(0, 60),
  }));
}
"""

bodies = []
calls = []


def on_response(r):
    calls.append(f"{r.request.method} {r.status} {r.url}")
    if "ai-turn" in r.url:
        try:
            bodies.append({"status": r.status, "body": r.json()})
        except Exception as exc:  # body already consumed or not json
            bodies.append({"status": r.status, "body": f"<{exc}>"})


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-proxy-server"])
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.on("response", on_response)
    page.goto(SITE, wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.get_by_text("Đăng ký với Google", exact=False).first.click()
    page.wait_for_timeout(1000)
    page.locator('[aria-label^="Vào app với tư cách"]').first.click()
    page.wait_for_timeout(2200)

    page.get_by_label("Tin nhắn: chat nhóm và AI").click()
    page.wait_for_timeout(2500)
    out = {"controls_tab_tin_nhan": page.evaluate(LIST_CONTROLS)}

    # "Hỏi Rủ Đi AI" reads the conversation; an empty group answers
    # `no_conversation`. So talk first, the way a group would.
    for cau in (
        "Cuối tuần này nhóm mình đi Đà Lạt hai ngày nhé",
        "Mình muốn có lịch trình chi tiết từng giờ cho ngày thứ bảy",
        "Ưu tiên quán nướng với cafe view đồi, tầm 300k một người thôi",
    ):
        page.get_by_label("Ô nhập tin nhắn").fill(cau)
        page.wait_for_timeout(200)
        page.get_by_label("Gửi tin nhắn").click()
        page.wait_for_timeout(1200)
    out["man_sau_khi_chat"] = page.evaluate("() => document.body.innerText")[-600:]

    page.get_by_label("Ô nhập tin nhắn").fill(CAU_HOI)
    page.wait_for_timeout(300)
    page.get_by_label("Hỏi Rủ Đi AI").click()

    # The model round trip is slow; poll for either a plan card or a refusal.
    seen = ""
    for _ in range(30):
        page.wait_for_timeout(2000)
        seen = page.evaluate("() => document.body.innerText")
        if (
            "Xem chi tiết kế hoạch" in seen
            or "tạm nghỉ" in seen
            or "chưa" in seen.lower()
        ):
            if bodies:
                break
    out["ai_turn_bodies"] = bodies
    out["man_sau_khi_hoi"] = seen[-1500:]
    out["controls_sau_khi_hoi"] = page.evaluate(LIST_CONTROLS)
    page.screenshot(path="/tmp/qa2-f16-chat.png")

    chi_tiet = [
        c
        for c in out["controls_sau_khi_hoi"]
        if (c.get("aria") or "") == "Xem chi tiết kế hoạch"
    ]
    if chi_tiet:
        page.get_by_label("Xem chi tiết kế hoạch").first.click()
        page.wait_for_timeout(2000)
        out["man_chi_tiet_ke_hoach"] = page.evaluate("() => document.body.innerText")[
            :2000
        ]
        page.screenshot(path="/tmp/qa2-f16-ke-hoach.png")

    out["calls"] = [c for c in calls if API in c][-15:]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    browser.close()
