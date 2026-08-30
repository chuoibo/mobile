#!/usr/bin/env python3
"""Walk F39/F42's wall in a real browser, then ask the server who can read it.

#330 walked #312's other three flows and wrote the wall down as unscanned:
"bốn route F39/F42 của đợt 2 trong cùng PR -- tường cá nhân cần lượt riêng."
This is that run.

## Two halves, because the app can only see one of them

The wall on Cá nhân reads `GET /people/{id}/posts` with the subject and the
actor set to the same person (`layTuong` in `src/screens/ca-nhan/tuong.ts`
calls `docTuongNguoi(personId, personId)`). So every row the app ever renders
passes `can_read`'s first branch -- the author reads everything, `only_me`
included -- and the audience a post carries changes nothing about what the
person who wrote it sees.

That means a browser walk alone CANNOT falsify F42. Pressing "Bạn bè" and then
seeing the post appear on your own wall is the same observation you get from a
build where `can_read` returns True unconditionally.

So:

  Half A (browser)  what the person writing a post can see and press: the four
                    sentences, the default, the group gate, the label on each
                    card, and -- the part a screenshot cannot show -- that the
                    request carrying the audience actually left the browser.

  Half B (HTTP)     what the promise on those buttons is worth: the same four
                    posts fetched as four different readers. This half is not
                    a UI walk and is not reported as one; it is the only place
                    the disjointness of `friends` and `group` is observable at
                    all, because no screen in the app renders another person's
                    posts.

Half B addresses the server directly rather than through a screen because
there is no screen: `GET /posts` has a client function and no caller. That
absence is a finding, not a gap in this script.

Run:
    MOBILE_QA_WEB=http://127.0.0.1:8353 MOBILE_QA_API=http://127.0.0.1:8352 \
    MOBILE_QA_GROUP=<uuid> python3 di_bo_tuong.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

WEB = os.environ.get("MOBILE_QA_WEB", "http://127.0.0.1:8353")
API = os.environ.get("MOBILE_QA_API", "http://127.0.0.1:8352")
GROUP = os.environ["MOBILE_QA_GROUP"]
ANH = pathlib.Path(os.environ.get("MOBILE_QA_ANH", "/tmp/qa3-anh"))

MINH = "46b55e67-932b-5415-a5ee-08fb2641a4ff"
TRANG = "49871dab-3bf9-5140-acf3-6c9736b31e8f"
HAI = "be2389f9-62cb-5b28-8e5f-874768e9fb75"
NGOC = "e3a44e25-4547-508a-8f4d-9b2495c3325f"
ROLES = "group_admin,member,advancer,recipient,batch_owner"

READERS = [
    ("Minh (tác giả)", MINH),
    ("Trang (bạn bè, ngoài nhóm)", TRANG),
    ("Hải (trong nhóm, chưa kết bạn)", HAI),
    ("Ngọc (không liên quan)", NGOC),
]

# nhãn trên nút, câu giải thích, và -- viết tay, không đọc từ sản phẩm -- ai
# ĐƯỢC đọc. Cột cuối là mệnh đề bị kiểm; lấy nó từ `MUC_NGUOI_DOC` sẽ biến bảng
# này thành sản phẩm tự chấm điểm chính nó.
BAI = [
    ("only_me", "Chỉ mình tôi", "Bài chỉ mình tôi đọc", {MINH}),
    ("friends", "Bạn bè", "Bài cho bạn bè của tôi", {MINH, TRANG}),
    ("group", "Một nhóm", "Bài cho nhóm của tôi", {MINH, HAI}),
    ("public", "Công khai", "Bài ai cũng đọc được", {MINH, TRANG, HAI, NGOC}),
]

loi: list[str] = []


def check(ok: bool, nhan: str) -> bool:
    print(f"{'ok  ' if ok else 'FAIL'} {nhan}")
    if not ok:
        loi.append(nhan)
    return ok


def http(path: str, actor: str) -> tuple[int, dict | list | None]:
    request = urllib.request.Request(f"{API}{path}")
    request.add_header("X-Actor-ID", actor)
    request.add_header("X-Actor-Roles", ROLES)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode()
        return error.code, (json.loads(body) if body else None)


def o_muc(page, nhan: str):
    """The one radio for this audience, addressed by the start of its label.

    `filter(has_text="Bạn bè")` matches three of the four: the words naming
    each audience also appear inside the *other* audiences' explanations, which
    is deliberate -- "Người trong nhóm chưa kết bạn thì không đọc được" is the
    sentence that makes `friends` and `group` distinguishable. Only the label
    prefix is unique.
    """
    return page.locator(f'[role=radio][aria-label^="{nhan}."]')


def mo(page, rong: int = 390):
    """Cold load. `about:blank` first because changing only the fragment does
    not remount the app, so a second `goto` would measure the first screen."""
    page.set_viewport_size({"width": rong, "height": 844})
    page.goto("about:blank")
    page.goto(f"{WEB}/index.html#tab=ca-nhan&nguoi=minh&nhom={GROUP}")
    page.wait_for_selector("text=Tường của bạn", timeout=30_000)
    # "Tường của bạn" là tiêu đề thẻ, có mặt ngay khi mount -- nó KHÔNG nói
    # rằng lượt đọc tường đã xong. Chờ chính màn chờ biến mất, nếu không phép
    # kiểm trạng thái rỗng sẽ chạy trong lúc `layTuong` còn đang bay.
    page.wait_for_selector("text=Đang tải tường...", state="detached", timeout=30_000)


def nua_a(page) -> list[dict]:
    """Browser half. Returns the POST /posts bodies that left the browser."""
    print("\n== Nửa A: trên trình duyệt thật, 390x844 ==")
    gui: list[dict] = []
    page.on(
        "request",
        lambda r: gui.append(json.loads(r.post_data or "{}"))
        if r.method == "POST" and r.url.endswith("/posts")
        else None,
    )

    mo(page)
    check(
        page.get_by_text("Chưa có bài nào trên tường").count() == 1,
        "tường mở ra ở trạng thái rỗng (máy chủ trả 0 bài)",
    )
    page.get_by_text("Viết lên tường").click()
    page.wait_for_selector("[role=radiogroup]")

    radio = page.locator("[role=radio]")
    check(radio.count() == 4, f"bốn mức người đọc, đếm được {radio.count()}")
    check(
        radio.nth(0).get_attribute("aria-checked") == "true",
        "mặc định là 'Chỉ mình tôi' (khớp DEFAULT_AUDIENCE của máy chủ)",
    )
    for _, nhan, _, _ in BAI:
        check(o_muc(page, nhan).count() == 1, f"có đúng một ô '{nhan}' trên màn")

    # Câu của mỗi mức phải nói ai KHÔNG đọc được, không chỉ ai đọc được.
    for cau in (
        "Kể cả bạn bè và người trong nhóm.",
        "Người trong nhóm chưa kết bạn thì không đọc được.",
        "Bạn bè ngoài nhóm không đọc được.",
    ):
        check(page.get_by_text(cau, exact=False).count() >= 1, f"câu phủ định: '{cau[:45]}...'")

    # Chốt nhóm: chọn 'Một nhóm' mà chưa chọn nhóm thì Đăng không bấm được.
    o_soan = page.locator('input[aria-label="Viết một câu"]')
    # `Button` đặt `disabled` lên chính Pressable, nên trạng thái khoá nằm ở
    # node role=button chứ không ở node Text bên trong. Hỏi nhầm node thì
    # thuộc tính trả về None và đọc y hệt "nút không khai báo trạng thái".
    dang = page.get_by_role("button", name="Đăng", exact=True)
    o_soan.fill("Thử chốt nhóm")
    o_muc(page, "Một nhóm").click()
    page.wait_for_timeout(400)
    khoa = dang.get_attribute("aria-disabled")
    check(khoa == "true", f"chọn 'Một nhóm' mà chưa chọn nhóm thì Đăng khoá (aria-disabled={khoa})")
    truoc = len(gui)
    dang.click(force=True)
    page.wait_for_timeout(700)
    check(len(gui) == truoc, "bấm Đăng lúc đang khoá KHÔNG gửi request nào")

    ANH.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ANH / "01-o-soan-bon-muc-390.png"))

    # `gui()` không đóng ô soạn sau khi đăng, nó chỉ xoá thân bài và đưa mức
    # người đọc về mặc định. Nên vòng lặp này KHÔNG bấm lại "Viết lên tường";
    # bấm lại là chờ một nút không còn tồn tại.
    for audience, nhan, than, _ in BAI:
        o_soan.fill(than)
        o_muc(page, nhan).click()
        page.wait_for_timeout(300)
        if audience == "group":
            # `Choice` vẽ mỗi nhóm thành một role=radio KHÔNG có aria-label --
            # tên nhóm chỉ nằm ở Text bên trong. Nên chọn qua radiogroup cha,
            # chứ không qua tên nhóm hiển thị: tên đó do `DEMO_GROUP_NAME` cấp
            # khi màn chưa nạp được nhóm thật, và neo vào nó là neo vào một
            # chuỗi không liên quan tới nhóm mà request sẽ mang đi.
            chon_nhom = page.locator(
                '[role=radiogroup][aria-label="Nhóm nào được đọc"] [role=radio]'
            )
            chon_nhom.first.wait_for(timeout=10_000)
            check(chon_nhom.count() >= 1, "[group] có ít nhất một nhóm để chọn")
            chon_nhom.first.click()
            page.wait_for_timeout(300)
        check(
            dang.get_attribute("aria-disabled") in (None, "false"),
            f"[{audience}] Đăng mở khi đã đủ điều kiện",
        )
        truoc = len(gui)
        dang.click()
        # Chờ chính thân bài xuất hiện trên tường, không chờ trạng thái rỗng
        # biến mất: câu đó chỉ đúng cho bài đầu tiên.
        page.wait_for_selector(f"text={than}", timeout=15_000)
        page.wait_for_timeout(600)
        check(len(gui) == truoc + 1, f"[{audience}] bấm Đăng gửi đúng 1 request lên máy chủ")
        check(
            radio.nth(0).get_attribute("aria-checked") == "true",
            f"[{audience}] sau khi đăng, mức người đọc quay về 'Chỉ mình tôi'",
        )

    print("\n-- thân request đã rời trình duyệt --")
    for than in gui:
        print("  ", json.dumps(than, ensure_ascii=False))
    check(len(gui) == 4, f"bốn bài đã gửi, đếm được {len(gui)}")
    for (audience, _, than_text, _), wire in zip(BAI, gui):
        check(wire.get("audience") == audience, f"[{audience}] audience trên dây đúng")
        check("author_id" not in wire, f"[{audience}] KHÔNG có author_id trên dây")
        co_ctx = "context_id" in wire
        check(
            co_ctx == (audience == "group"),
            f"[{audience}] context_id {'có' if co_ctx else 'vắng'} — đúng luật omit",
        )
        if audience == "group":
            check(wire.get("context_id") == GROUP, f"[{audience}] context_id là nhóm thật")

    # Nạp lại trang trước khi đọc nhãn, vì hai lý do.
    #
    # 1. Ô soạn không đóng sau khi đăng, nên bốn nhãn vẫn nằm trên màn dưới
    #    dạng bốn ô radio. Đếm nhãn trong `innerText` lúc đó là đếm ô soạn:
    #    phép kiểm sẽ XANH ngay cả khi không thẻ bài nào được vẽ ra.
    # 2. Sau khi nạp lại, mọi thứ trên tường đều do máy chủ trả về, không phải
    #    do `setTrang` nối thêm ở client. Bốn bài còn đó nghĩa là bốn bài đã
    #    thật sự được ghi.
    mo(page)
    page.wait_for_timeout(1500)
    man = page.inner_text("body")
    check(
        page.get_by_text("Viết lên tường").count() == 1,
        "sau khi nạp lại, ô soạn đóng — nhãn đọc được dưới đây là của thẻ bài",
    )
    print("\n-- nhãn trên thẻ bài, sau khi nạp lại từ máy chủ --")
    for audience, nhan, than_text, _ in BAI:
        check(than_text in man, f"[{audience}] thân bài '{than_text}' còn trên tường sau khi nạp lại")
        # Nhãn phải nằm trên ĐÚNG thẻ mang thân bài đó, không phải ở đâu đó
        # trên trang: một thẻ gắn nhầm nhãn là đúng cái lỗi cần bắt.
        #
        # `locator("div").filter(has_text=...).last` là cách SAI và đã đỏ ở
        # lượt trước: nó trả về node sâu nhất, tức chính ô Text chứa thân bài,
        # và ô đó không bao giờ chứa nhãn. Thẻ là node cha của nó.
        the = page.get_by_text(than_text, exact=True).locator("xpath=..")
        chu_tren_the = the.inner_text()
        check(nhan in chu_tren_the, f"[{audience}] thẻ mang '{than_text}' gắn nhãn '{nhan}'")
        # Và chỉ nhãn đó. Một thẻ mang hai nhãn, hay mang nhãn của mức khác,
        # nói sai với người viết về việc họ vừa hứa gì với ai.
        nhan_khac = [n for _, n, _, _ in BAI if n != nhan and n in chu_tren_the]
        check(
            not nhan_khac,
            f"[{audience}] thẻ KHÔNG mang nhãn của mức khác (thấy: {nhan_khac})",
        )

    page.screenshot(path=str(ANH / "02-tuong-bon-bai-390.png"), full_page=True)
    mo(page, 320)
    page.wait_for_timeout(1500)
    page.screenshot(path=str(ANH / "03-tuong-bon-bai-320.png"), full_page=True)
    check(
        page.get_by_text("Bài chỉ mình tôi đọc").count() >= 1,
        "ở 320px bài vẫn hiện (không bị cắt mất)",
    )
    return gui


def nua_b() -> None:
    """Server half: the same four posts, fetched as four different readers."""
    print("\n== Nửa B: cùng bốn bài, bốn người đọc khác nhau (tầng HTTP) ==")
    status, tuong = http(f"/people/{MINH}/posts", MINH)
    assert status == 200, (status, tuong)
    bai_theo_muc = {b["audience"]: b for b in tuong["posts"]}
    check(len(bai_theo_muc) == 4, f"tường của Minh có 4 mức, đếm được {len(bai_theo_muc)}")

    print(f"\n{'bài':<22}" + "".join(f"{ten.split(' ')[0]:<10}" for ten, _ in READERS))
    for audience, _, _, duoc_doc in BAI:
        bai = bai_theo_muc.get(audience)
        if bai is None:
            check(False, f"[{audience}] không tìm thấy bài trên tường của chính tác giả")
            continue
        hang = f"{audience:<22}"
        for ten, reader in READERS:
            # Hai đường đọc, phải nhất quán: tường của người, và một bài lẻ.
            _, tuong_r = http(f"/people/{MINH}/posts", reader)
            tren_tuong = any(p["id"] == bai["id"] for p in (tuong_r or {}).get("posts", []))
            status_bai, _ = http(f"/posts/{bai['id']}", reader)
            thay = tren_tuong
            mong_doi = reader in duoc_doc
            hang += f"{'THẤY' if thay else 'không':<10}"
            check(
                thay == mong_doi,
                f"[{audience}] {ten}: {'phải thấy' if mong_doi else 'KHÔNG được thấy'}"
                f" → {'thấy' if thay else 'không thấy'}",
            )
            check(
                (status_bai == 200) == mong_doi,
                f"[{audience}] {ten}: GET /posts/{{id}} trả {status_bai}"
                f" ({'mong 200' if mong_doi else 'mong 404'})",
            )
            check(
                mong_doi or status_bai == 404,
                f"[{audience}] {ten}: từ chối là 404 chứ không phải 403"
                f" (403 tiết lộ bài có tồn tại) — trả {status_bai}",
            )
        print(hang)

    # Bảng tin: có route, và ai đọc được gì ở đó.
    print("\n-- GET /posts (bảng tin) --")
    for ten, reader in READERS:
        status, feed = http("/posts", reader)
        muc = sorted(p["audience"] for p in (feed or {}).get("posts", []))
        print(f"   {ten:<32} {status} {muc}")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        try:
            nua_a(page)
        finally:
            browser.close()
    nua_b()

    print(f"\n== {len(loi)} phép kiểm đỏ ==")
    for l in loi:
        print("   FAIL", l)
    print(f"\nảnh: {ANH}")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
