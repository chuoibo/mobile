/* All seven mảng of the mockup are reachable from the opening screen, and
 * every one of them lets you back out.
 *
 * ## Why this file exists, given that nothing needed building
 *
 * frontend-003002 was raised as the largest remaining hole in the product: a
 * person signing in by phone number "lands on Khám phá and is CUT OFF there --
 * no tab bar, no way through to the other six mảng". Measured on 2026-08-31
 * against a live API and a build made from that same commit, none of it held.
 * The shell has a four-slot bar, all four tabs switch, the [+] opens four
 * create actions, and every full-screen flow behind it comes back. Every one
 * of the seven mảng was already reachable.
 *
 * What produced the report is worth writing down, because the same census will
 * be taken again:
 *
 *   - **The bar is not made of buttons.** Its four tabs carry `role="tab"`
 *     inside a `role="tablist"`; `ThanhTab.tsx`'s header explains why [+] had
 *     to be moved out of that tablist and left as the only `role="button"` in
 *     the furniture. So a census written as `[role="button"]` returns the
 *     content area and nothing else. Measured in the shell on Khám phá with
 *     the API up: `[role=button]` → 8, `[role=tab]` → 4, and the seven the
 *     report listed by name (Tìm bằng AI, Xem tất cả (12), four place cards,
 *     Xem bản đồ của nhóm) are exactly that button set minus [+]. The report
 *     was an accurate reading of the wrong query.
 *
 *   - **`scrollHeight === innerHeight` is not a cut-off page.** It was quoted
 *     as evidence ("cao trang = cao khung (844)"), and it is the one number
 *     this shell can never print anything else for: `SafeAreaView` is
 *     `flex: 1`, so the document is exactly the viewport and every list
 *     scrolls in a nested box. Measured 844/844 on the opening screen, in the
 *     shell, and on a tab whose content overflows -- three different states,
 *     one number. A quantity that cannot vary cannot be evidence.
 *
 * Neither mistake is catchable by anything that was in the tree. `tabs.ts` is
 * checked by `navigation.test.mjs`, but that reads the table, not the render --
 * it stays green if `VoTab` stops mounting `ThanhTab` entirely.
 * `vo-tab-web.test.mjs` does render the bar, and asserts `aria-selected` and
 * the focus trap on it, but it never presses a tab and never opens the [+]
 * menu, so "four tabs are in the DOM" was as far as any gate went.
 * `moi-man-co-duong-do.test.mjs` records, in writing, which screens have a
 * measurement -- a disclosure, and its own header says it is never a clearance.
 *
 * So this file asserts the acceptance criterion the ticket was written
 * against, in the browser, once per mảng: press to it, and press back.
 *
 * ## What it proves, and what it does not
 *
 * Proves: on the build in `MOBILE_WEB_EXPORT`, in this Chrome, at 390x844, a
 * person entering from the opening screen reaches all seven mảng by pressing
 * controls a person can see, and returns from each.
 *
 * Does NOT prove: that any mảng is correct, legible, or has its data -- the
 * API here is `installTabStubs`, so every number on screen is a fixture this
 * file chose. It does not prove anything about iOS or Android, whose layout
 * and accessibility bridges are different code. And it says nothing about the
 * quality of a screen once you are on it; that is the detector's job and the
 * per-screen gates'.
 *
 * Run from apps/mobile, against a build you made yourself:
 *
 *     npx expo export --platform web --output-dir /tmp/w
 *     MOBILE_WEB_EXPORT=/tmp/w MOBILE_REQUIRE_WEB_A11Y=1 \
 *       node --test tests/bay-mang-den-duoc.test.mjs
 *
 * Under plain `npm test` it reads `.expo-build-check`, which `build:check` has
 * just written. No build or no Chrome is a skip that names itself;
 * `MOBILE_REQUIRE_WEB_A11Y=1` turns that skip into a failure.
 */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";
import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";
import { API_BASE, installTabStubs, taoFixtures } from "../tools/tab-snapshots.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const GOC = join(HERE, "..");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** The phone the demo runs on. One viewport on purpose: this file asks whether
 *  a control can be pressed, and that answer does not vary with width the way
 *  overflow does -- `vo-tab-web.test.mjs` owns the three-viewport sweep. */
const KHUNG = { w: 390, h: 844 };

/** Entering with a person, rather than through "Bỏ qua".
 *
 *  Not a detail. Half the mảng below refuse politely when nobody is signed in
 *  ("Chưa biết bạn là ai"), and a refusal still renders a screen with a way
 *  back -- so the whole suite would pass on an app that could not open a
 *  single one of them. The persona sheet is client-side (`nhom-demo.ts`), so
 *  this costs no server.
 *
 *  The Apple row rather than the Google one, for a reason that is about the
 *  gate and not about the product: both call the same `setDangChon(true)`, but
 *  `NutHang` draws its monogram inside the pressable, so Google's collapsed
 *  text is "G Đăng ký với Google" and `clickChu` matches exactly. Apple's
 *  monogram is empty. Matching loosely instead would let this press whichever
 *  sign-in row sorted first, which is the kind of "took the first match"
 *  `clickChu` refuses on purpose. */
const NUT_MO_SHEET = "Đăng ký với Apple";
const TIEU_DE_SHEET = "Vào app với tư cách ai?";
const CHON_MINH = "Vào app với tư cách Minh";

/**
 * The seven mảng of `product/RuDi_Mobile_Product_Mockups`, each with the
 * control that opens it and a string only that mảng prints.
 *
 * The proof strings are chrome of the destination -- a heading, a section
 * title -- never a place name or a person's name. Fixture data is shared
 * between screens (`duong-vao-ban-do-nhom.test.mjs` records what that costs:
 * its first negative control appeared on both screens and passed whether or
 * not anything navigated), so a name proves the fixture loaded, not that the
 * app moved.
 *
 * `01 onboarding` has no row here because it is not somewhere you press *to*:
 * it is where every case below starts, and `vaoVo()` failing to get out of it
 * is how this file reports that mảng broken.
 */
const MANG_TAB = [
  {
    ma: "02 discovery",
    tab: "Khám phá: gợi ý chỗ đi cho nhóm",
    chu: "Gợi ý cho bạn",
  },
  {
    ma: "04 outing_mgmt",
    tab: "Lên plan: chuyến đi của nhóm",
    // The screen's own hint, not its empty state. "Chưa có chuyến nào" was
    // tried first and times out here, correctly: `installTabStubs` answers the
    // trips route, so under this gate the tab has trips and never paints the
    // empty case. Asserting on it would have made this file quietly a test of
    // the fixture being empty.
    //
    // The empty state itself is real and was measured by hand on 2026-08-31
    // against a live API -- "Chưa có chuyến nào", then "Tạo chuyến đầu: đặt
    // tên, chọn ngày, ghi số người và ngân sách tham chiếu", then the button.
    // No gate holds that wording, here or anywhere: `grep -rn "Chưa có chuyến
    // nào" tests/ tools/` finds nothing. Recorded as an open gap rather than
    // smuggled into a reachability file, where a reader would take the green
    // row as covering it.
    chu: "Chuyến đi của nhóm, ngày giờ và ai đi",
  },
  {
    ma: "03 group_chat_ai",
    tab: "Tin nhắn: chat nhóm và AI",
    chu: "Hỏi Rủ Đi AI",
  },
  {
    ma: "07 profile_finance",
    tab: "Cá nhân: hồ sơ và tài chính của bạn",
    chu: "Ảnh đại diện",
  },
];

/**
 * The mảng that live behind [+] and take the whole screen.
 *
 * `ra` is the sequence of controls that must bring you back, pressed in order.
 * A list rather than one name because 05 opens two screens deep -- [+] lands
 * on `NhapKhoanChi`, which opens `ChupBill` over it, so "Huỷ" leaves the
 * camera and "Đóng" leaves the flow. Written out step by step so that a flow
 * which stops being escapable fails on the step that stopped working, instead
 * of on a generic "never got back".
 *
 * Each step is named rather than found by "press whatever looks like a back
 * button", because the defect worth catching is a flow with no exit at all --
 * and a test that hunts for one would report the absence of an exit as an
 * absence of a button to press, which reads like a broken selector rather
 * than a dead end.
 */
const MANG_TAO = [
  {
    ma: "05 smart_bill",
    // The row's full `aria-label`, which `MenuTao` builds as "<nhãn>. <gợi ý>".
    // Not its visible words: those are two `<Text>` on two lines, so a
    // whitespace-collapsed exact match against just the label finds nothing,
    // and matching loosely would let this press whichever row shares a prefix.
    mo: "Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền",
    // `ChupBill`'s own line, and it is only reachable because `vaoVo` signs in.
    // Entering through "Bỏ qua" instead lands on a refusal -- "Chưa biết bạn là
    // ai", exit "Quay lại" -- which renders, has a way back, and would pass
    // every assertion below while proving the flow never opened. That is the
    // whole reason this file does not take the cheaper door.
    chu: "Đưa bill vào khung hình",
    ra: ["Huỷ", "Đóng khoản chi, quay lại các tab"],
  },
  {
    ma: "06 memories",
    mo: "Kỷ niệm nhóm. Xem lại chuyến đã đi, chỗ đã tới, tiền đã chia",
    chu: "những chuyến đã đi qua",
    ra: ["Đóng kỷ niệm, quay lại màn trước"],
  },
];

/** The four labels the shell's own bar carries.
 *
 *  Derived from the table above rather than written out again: these ARE the
 *  tabs under test, and a second hand-kept copy is how a renamed tab passes a
 *  gate that is checking the old name against the old name. */
const NHAN_TAB_VO = MANG_TAB.map((m) => m.tab);

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npm run build:check)`);
}
if (!chromeBin) reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
const cu = lyDoBanDungCu(EXPORT_DIR, GOC);
if (cu) reasons.push(cu);

if (reasons.length && !REQUIRED) {
  test(`bảy mảng đến được — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("bảy mảng của sườn UI, đo bằng cách bấm trên trang render thật", () => {
    let page;
    let server;

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      await page.viewport(KHUNG.w, KHUNG.h);
      console.log(`  đo trên: ${EXPORT_DIR}`);
      console.log(`  chrome : ${chromeBin}`);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
    });

    /** Back to the opening screen with the API stubbed, then into the shell as
     *  Minh. Every test starts here, so the order they run in cannot change an
     *  answer -- a tab left selected by the previous case would otherwise make
     *  "pressing it arrives" pass without a press. */
    async function vaoVo() {
      await page.goto(
        server.url,
        (chu) => document.body.innerText.includes(chu),
        NUT_MO_SHEET,
      );
      await page.evaluate(installTabStubs, API_BASE, taoFixtures());
      // The stubs patch `window.fetch`, so anything already in flight was
      // answered by the real (unreachable) host. Re-entering from the opening
      // screen after installing them is what makes the shell's first render
      // see the fixtures.
      await page.clickChu(NUT_MO_SHEET);
      // Waited for by the sheet's own heading, which is painted text. The row
      // below is found by `aria-label`, and waiting on THAT string would have
      // waited forever: a persona row draws a monogram and a name, and
      // "Vào app với tư cách Minh" exists only in the accessibility tree.
      await page.waitFor(
        (chu) => document.body.innerText.includes(chu),
        { label: "sheet chọn người" },
        TIEU_DE_SHEET,
      );
      await page.clickLabel(CHON_MINH);
      await page.waitFor(() => document.querySelectorAll('[role="tab"]').length === 4, {
        label: "bốn tab của vỏ",
      });
    }

    /** What a census of the shell's clickables returns, split by role.
     *
     *  Both halves are returned because the gap between them is the finding:
     *  the report that produced this file read the first and concluded the bar
     *  was absent. */
    function diemDanh() {
      const nhinThay = (el) => {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      };
      const chu = (el) => (el.getAttribute("aria-label") || el.innerText || "").trim().replace(/\s+/g, " ");
      return {
        nut: [...document.querySelectorAll('[role="button"]')].filter(nhinThay).map(chu),
        tab: [...document.querySelectorAll('[role="tab"]')].filter(nhinThay).map(chu),
        tablist: [...document.querySelectorAll('[role="tablist"]')].filter(nhinThay).length,
        cao: document.documentElement.scrollHeight,
        khung: window.innerHeight,
      };
    }

    const chuTrenMan = () => document.body.innerText.replace(/\s+/g, " ");

    /* --- the census that produced the ticket ------------------------------ */

    test("thanh tab có thật, và nó KHÔNG nằm trong tập [role=button]", async () => {
      await vaoVo();
      const d = await page.evaluate(diemDanh);
      console.log(`  [role=button] : ${d.nut.length} — ${JSON.stringify(d.nut)}`);
      console.log(`  [role=tab]    : ${d.tab.length} — ${JSON.stringify(d.tab)}`);
      console.log(`  scrollHeight/innerHeight = ${d.cao}/${d.khung}`);

      assert.equal(d.tablist, 1, "vỏ không có [role=tablist] nào — thanh tab đã mất");
      assert.equal(
        d.tab.length,
        4,
        `phải có bốn tab; đếm được ${d.tab.length}. Đếm bằng [role=button] ra ` +
          `${d.nut.length} và KHÔNG hề gồm thanh tab — đó là phép đếm đã sinh ra ` +
          `frontend-003002. Thanh tab mang role="tab", xem ThanhTab.tsx.`,
      );
      // The trap, asserted rather than described: not one of the four
      // destinations answers to a button-only census. If react-native-web ever
      // maps them differently this goes red, and the header above is what the
      // next reader needs, so a red run here is the right outcome.
      const lanLon = d.nut.filter((n) => d.tab.includes(n));
      assert.deepEqual(
        lanLon,
        [],
        "một tab vừa là [role=button] vừa là [role=tab] — đọc lại phần đầu file",
      );
    });

    /* --- four mảng on the bar --------------------------------------------- */

    for (const m of MANG_TAB) {
      test(`${m.ma}: bấm tab tới được, và thanh tab vẫn ở đó để quay ra`, async () => {
        await vaoVo();

        // The negative half. Without it, a tab that navigates nowhere passes
        // whenever the destination's text happens to already be on screen.
        const truoc = await page.evaluate(chuTrenMan);
        const daCo = truoc.includes(m.chu);

        await page.clickLabel(m.tab);
        await page.waitFor((chu) => document.body.innerText.includes(chu), { label: m.ma }, m.chu);

        const d = await page.evaluate(diemDanh);
        const conLai = NHAN_TAB_VO.filter((n) => d.tab.includes(n));
        console.log(
          `  ${m.ma}: "${m.chu}" hiện ra (trước khi bấm: ${daCo ? "ĐÃ CÓ" : "chưa có"}), ` +
            `tab của vỏ ${conLai.length}/4, [role=tab] trên màn ${d.tab.length}`,
        );

        // By label, not by counting every `[role=tab]` on the page. Tin nhắn
        // draws its own tablist -- Chat / Plan / Thành viên / File -- so the
        // total there is 8, and a `=== 4` written against the total reported
        // the shell bar as swallowed on the one tab that has the most
        // navigation. Counting a total is what this whole file exists to warn
        // about; it would have been an odd place to do it again.
        assert.deepEqual(
          conLai,
          NHAN_TAB_VO,
          `${m.ma} nuốt mất thanh tab dưới (còn ${conLai.length}/4) — vào được nhưng không có đường ra`,
        );
        const dangChon = await page.evaluate(
          (nhan) =>
            document.querySelector(`[role="tab"][aria-label="${nhan}"]`)?.getAttribute("aria-selected"),
          m.tab,
        );
        assert.equal(dangChon, "true", `${m.ma}: bấm rồi mà tab không tự nhận là đang chọn`);
      });
    }

    /* --- the mảng behind [+] ---------------------------------------------- */

    test("[+] mở ra bốn việc tạo được, không phải một menu chết", async () => {
      await vaoVo();
      await page.clickLabel("Tạo mới");
      await page.waitFor(
        () => document.body.innerText.includes("Tạo nhóm"),
        { label: "menu [+]" },
      );
      const d = await page.evaluate(diemDanh);
      const viec = d.nut.filter((n) => /^(Tạo chuyến|Tạo khoản chi|Kỷ niệm nhóm|Tạo nhóm)/.test(n));
      console.log(`  menu [+]: ${JSON.stringify(viec)}`);
      assert.equal(viec.length, 4, `[+] phải mở ra bốn việc; thấy ${viec.length}`);
    });

    for (const m of MANG_TAO) {
      test(`${m.ma}: mở từ [+] tới được, và có đường quay về vỏ`, async () => {
        await vaoVo();
        await page.clickLabel("Tạo mới");
        await page.waitFor(() => document.body.innerText.includes("Tạo nhóm"), { label: "menu [+]" });

        const truoc = await page.evaluate(chuTrenMan);
        assert.ok(
          !truoc.includes(m.chu),
          `"${m.chu}" đã có trên màn trước khi mở ${m.ma} — chuỗi này không phân biệt được gì`,
        );

        await page.clickLabel(m.mo);
        await page.waitFor((chu) => document.body.innerText.includes(chu), { label: m.ma }, m.chu);

        // A full-screen flow, so the bar is gone on purpose. That is exactly
        // why the exit below has to exist and has to be pressed.
        const trong = await page.evaluate(diemDanh);
        console.log(`  ${m.ma}: mở rồi, thanh tab ${trong.tab.length}/4 (0 = toàn màn hình, đúng ý)`);

        for (const buoc of m.ra) {
          await page.clickLabel(buoc);
          // Settle between presses. Without it the next `clickLabel` can fire
          // at the outgoing screen's box and press nothing, which reports as a
          // missing exit on a flow that has one.
          await page.waitFor(
            (nhan) => !document.querySelector(`[aria-label="${nhan}"]`),
            { label: `rời "${buoc}"` },
            buoc,
          );
        }
        await page.waitFor(() => document.querySelectorAll('[role="tab"]').length === 4, {
          label: `${m.ma} quay về vỏ`,
        });
        const sau = await page.evaluate(chuTrenMan);
        assert.ok(
          !sau.includes(m.chu),
          `bấm "${m.ra}" xong mà "${m.chu}" vẫn còn — chưa rời khỏi ${m.ma}`,
        );
      });
    }
  });
}
