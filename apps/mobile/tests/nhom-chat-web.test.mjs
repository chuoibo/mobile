/* What the group-chat screen looks like once a browser has laid it out.
 *
 * `tests/tin-nhan.test.mjs` proves the logic under this screen: cursor
 * direction, uuid5, card shape, the five AI branches. It renders nothing, and
 * that gap is not academic. Two defects sat green through 315 passing tests,
 * `tsc --noEmit`, and a successful `expo export`, because every one of those
 * gates reads source or bundles bytes and none of them measures a box:
 *
 *   1. The send button was off the screen. The compose row gives `TextInput`
 *      `flex: 1` and nothing else, and a flex item on react-native-web will
 *      not shrink below its intrinsic width unless it is told it may -- CSS
 *      `min-width` defaults to `auto`, not `0`. The input reserved its own
 *      content width, the row grew to 440px inside a 390px viewport, and
 *      "Gửi" landed at left:395. Off the right edge of the iPhone the demo
 *      runs on, on the one screen whose acceptance criterion is "send a real
 *      message". Every button had its 44x44 target and its Vietnamese label;
 *      none of that helps when the control is past the edge of the glass.
 *
 *   2. `role="tablist"` had to be confirmed, not assumed. react-native-web
 *      0.21.2 drops `accessibilityState` on the floor (see `aria-state.test.mjs`),
 *      so the four chips write `aria-selected` directly. Whether that reaches
 *      the DOM is a question about a library's mapping table, and the only
 *      honest way to answer it is to read the rendered attribute back.
 *
 * So the rule this file encodes: a control that exists in the source and is
 * unreachable in the viewport is a missing control. Measure the box.
 *
 * What this proves: this build, these viewports, this Chrome. Not iOS, not
 * Android -- their layout engines are different code. The API is pinned to an
 * unreachable host by `build:check`, so the screen under test is the one a
 * server failure produces; that is deliberate here, because the compose row
 * and the chip row must survive a dead server, and it keeps the gate off the
 * network. The live-server path is exercised by hand, not by this file.
 *
 * Run from apps/mobile, against a build you made yourself:
 *
 *     npx expo export --platform web --output-dir /tmp/w
 *     MOBILE_WEB_EXPORT=/tmp/w MOBILE_REQUIRE_WEB_A11Y=1 \
 *       node --test tests/nhom-chat-web.test.mjs
 *
 * Under plain `npm test` it reads `.expo-build-check`, which `build:check`
 * has just written. No build or no Chrome means a skip that names itself;
 * MOBILE_REQUIRE_WEB_A11Y=1 turns that skip into a failure.
 */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";

import { lyDoBanDungCu } from "./tuoi-ban-dung.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** 320 is the narrowest phone still in use, 390 is the iPhone the demo runs
 *  on and the width defect #1 was measured at, 1280 is the web fallback. */
const VIEWPORTS = [
  { name: "320x720", w: 320, h: 720 },
  { name: "390x844", w: 390, h: 844 },
  { name: "1280x800", w: 1280, h: 800 },
];

/** The compose row. Every one of these has to be reachable with a thumb, so
 *  every one of them has to be inside the viewport. */
const O_NHAP_LABELS = [
  "Thêm ảnh hoặc tệp",
  "Ô nhập tin nhắn",
  "Chèn biểu tượng cảm xúc",
  "Ghi âm",
  "Gửi tin nhắn",
  // Cách duy nhất để hỏi thẳng AI. Nửa máy chủ (#378) chỉ bỏ qua nhịp khi
  // client gửi `requested: true`, và không màn nào gửi cờ đó nếu không có
  // nút này -- nên nút nằm ngoài mép kính đúng bằng nút không tồn tại.
  "Hỏi Rủ Đi AI",
];

const CHIP_LABELS = ["Chat", "Plan", "Thành viên", "File"];

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npx expo export --platform web --output-dir …)`);
}
if (!chromeBin) {
  reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
}

/* ------------------------------------------------ measurements, in-page --- */

/* Named functions, not inline blobs: a failure message that quotes the source
 * of a number is worth more than one that quotes a stringified anonymous fn. */

/** Where each named control sits relative to the viewport. A control whose
 *  right edge is past `innerWidth` cannot be tapped, whatever its size. */
function measureControls(labels) {
  const w = window.innerWidth;
  return labels.map((label) => {
    const el = document.querySelector(`[aria-label="${label}"]`);
    if (!el) return { label, found: false };
    const r = el.getBoundingClientRect();
    return {
      label,
      found: true,
      left: Math.round(r.left),
      right: Math.round(r.right),
      width: Math.round(r.width),
      height: Math.round(r.height),
      viewport: w,
      inside: r.left >= -0.5 && r.right <= w + 0.5,
    };
  });
}

/** The chip row, read back from the DOM rather than from the JSX. A tablist
 *  that contains anything other than tabs is an axe violation at critical. */
function measureChipTablist() {
  const lists = [...document.querySelectorAll('[role="tablist"]')];
  return lists.map((list) => {
    const tabs = [...list.querySelectorAll('[role="tab"]')];
    return {
      childCount: list.children.length,
      tabCount: tabs.length,
      names: tabs.map((t) => (t.getAttribute("aria-label") || t.textContent || "").trim()),
      selected: tabs.map((t) => t.getAttribute("aria-selected")),
    };
  });
}

/** The "AI hiểu nhóm" entry point, read back from the DOM.
 *
 *  It swaps the panel the way a tab does, so it is tempting to make it a fifth
 *  chip -- and the first cut of #382 did exactly that. It is not a tab. The
 *  panel it opens carries its own "Đóng" button and drops you back on Chat,
 *  which is dismiss semantics; you leave a tab by choosing another tab, never
 *  by closing it. Wired as a tab it also puts a fifth `role="tab"` in a row
 *  whose four chips are facets of one conversation, so a screen reader offers
 *  five things to switch between and the two Gemini-backed routes behind it
 *  sit where a user expects a free panel swap.
 *
 *  Scoped to the control, not the name: the panel's own `Screen` header also
 *  says "AI hiểu nhóm", and a bare name lookup could measure the header. */
function measureAiHieuNhomEntry() {
  const el = document.querySelector(
    '[role="tab"][aria-label="AI hiểu nhóm"], [role="button"][aria-label="AI hiểu nhóm"]',
  );
  if (!el) return { found: false };
  return {
    found: true,
    role: el.getAttribute("role"),
    insideTablist: !!el.closest('[role="tablist"]'),
  };
}

/** Every button that carries no text of its own needs an accessible name, or
 *  a screen reader announces "button" four times in a row. */
function measureIconButtonNames() {
  return [...document.querySelectorAll('[role="button"], button')].map((el) => ({
    name: (el.getAttribute("aria-label") || "").trim(),
    text: (el.textContent || "").trim(),
  }));
}

/* -------------------------------------------------------------------- gate --- */

// bug-010019. This gate measures a prebuilt export and opens no source file,
// so an export older than the tree makes it name a control as missing from a
// screen that renders it correctly. Refuse to report rather than report wrong.
const banCu = lyDoBanDungCu(EXPORT_DIR, join(HERE, ".."));
if (banCu) reasons.push(banCu);

if (reasons.length && !REQUIRED && !banCu) {
  test(`nhóm chat trên web — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("nhóm chat, đo trên trang render thật", () => {
    let page;
    let server;

    before(async () => {
      assert.equal(reasons.length, 0, `MOBILE_REQUIRE_WEB_A11Y=1 nhưng: ${reasons.join("; ")}`);
      server = await serve(EXPORT_DIR);
      page = await launch(chromeBin);
      console.log(`  đo trên: ${EXPORT_DIR}`);
      console.log(`  chrome : ${chromeBin}`);
    });

    after(async () => {
      if (page) await page.close();
      if (server) await server.close();
    });

    /** Open the chat tab at a given size.
     *
     *  The `about:blank` hop is load-bearing and was learned the hard way:
     *  `AppRoot` reads the `#tab=` fragment once, at mount. Navigating from
     *  one fragment to another on the same document is a same-document
     *  navigation, React never remounts, and the page keeps showing the
     *  previous screen while the test happily reports on the tab it thinks it
     *  asked for. Going through a blank document forces a real mount. */
    async function moTabChat(w, h) {
      await page.viewport(w, h);
      await page.goto("about:blank", () => true);
      await page.goto(
        `${server.url}/index.html#tab=tin-nhan&nguoi=minh`,
        (label) => !!document.querySelector(`[aria-label="${label}"]`),
        "Ô nhập tin nhắn",
      );
    }

    /* --- 1. the compose row is reachable --------------------------------- */

    for (const v of VIEWPORTS) {
      test(`ô nhập: mọi nút nằm trong màn ở ${v.name}`, async () => {
        await moTabChat(v.w, v.h);
        const controls = await page.evaluate(measureControls, O_NHAP_LABELS);

        for (const c of controls) {
          console.log(
            c.found
              ? `  ${c.inside ? "trong màn" : "NGOÀI MÀN "} ${c.label}: ` +
                  `left=${c.left} right=${c.right} (rộng ${c.viewport})`
              : `  KHÔNG THẤY ${c.label}`,
          );
        }

        const thieu = controls.filter((c) => !c.found).map((c) => c.label);
        assert.deepEqual(thieu, [], `không tìm thấy trên trang: ${thieu.join(", ")}`);

        const ngoai = controls.filter((c) => !c.inside);
        assert.deepEqual(
          ngoai.map((c) => `${c.label} (right=${c.right} > ${c.viewport})`),
          [],
          "có nút của ô nhập nằm ngoài màn, không bấm tới được",
        );
      });
    }

    /* --- 2. the send button keeps its 44x44 target ------------------------ */

    test("nút gửi giữ đủ vùng bấm 44x44 ở 320x720", async () => {
      await moTabChat(320, 720);
      const [gui] = await page.evaluate(measureControls, ["Gửi tin nhắn"]);
      console.log(`  Gửi: ${gui.width}x${gui.height}`);
      assert.ok(gui.width >= 44, `nút gửi rộng ${gui.width}, cần >= 44`);
      assert.ok(gui.height >= 44, `nút gửi cao ${gui.height}, cần >= 44`);
    });

    /* --- 3. the chip row is a real tablist -------------------------------- */

    test("hàng chip là tablist đúng chuẩn: đúng 4 tab, không lẫn nút khác", async () => {
      await moTabChat(390, 844);
      const lists = await page.evaluate(measureChipTablist);
      const chip = lists.find((l) => l.names.some((n) => CHIP_LABELS.includes(n)));

      assert.ok(chip, `không thấy tablist của hàng chip; thấy: ${JSON.stringify(lists)}`);
      console.log(`  tab: ${chip.names.join(" · ")}`);
      console.log(`  aria-selected: ${chip.selected.join(", ")}`);

      assert.deepEqual(chip.names, CHIP_LABELS, "nhãn bốn chip không đúng");
      assert.equal(chip.tabCount, 4, "tablist phải có đúng 4 role=tab");
      assert.equal(
        chip.childCount,
        4,
        "tablist chứa phần tử không phải tab — lỗi axe mức critical",
      );
      assert.equal(
        chip.selected.filter((s) => s === "true").length,
        1,
        "phải có đúng một chip mang aria-selected=true",
      );
      assert.ok(
        chip.selected.every((s) => s === "true" || s === "false"),
        `aria-selected không tới được DOM: ${JSON.stringify(chip.selected)}`,
      );
    });

    /* --- 3b. the AI entry point is a button, and it is not a fifth tab ---- */

    test("'AI hiểu nhóm' là button và nằm NGOÀI tablist", async () => {
      await moTabChat(390, 844);
      const entry = await page.evaluate(measureAiHieuNhomEntry);

      assert.ok(entry.found, "không thấy đường vào 'AI hiểu nhóm'");
      console.log(`  role=${entry.role} · trong-tablist=${entry.insideTablist}`);

      assert.equal(
        entry.role,
        "button",
        "đường vào phải là button: nó mở một màn có nút 'Đóng' của riêng nó, không phải một mặt của cuộc trò chuyện",
      );
      assert.equal(
        entry.insideTablist,
        false,
        "nút nằm trong tablist — axe gọi là aria-required-children mức critical, và trình đọc màn hình đếm thành 5 tab để chuyển qua lại",
      );
    });

    test("bấm 'AI hiểu nhóm' vẫn mở được màn, và tablist vẫn đúng 4 tab", async () => {
      // Moving it out of the tablist must not lose the only way in. #382 exists
      // because these four routes had no caller at all; a fix that makes the
      // gate green by deleting the entry point would put them back there.
      await moTabChat(390, 844);
      await page.clickLabel("AI hiểu nhóm");
      await page.waitFor(
        () =>
          [...document.querySelectorAll('[role="button"]')].some(
            (b) => (b.textContent || "").trim() === "Đóng",
          ),
        { label: "màn 'AI hiểu nhóm' mở ra" },
      );

      const lists = await page.evaluate(measureChipTablist);
      const chip = lists.find((l) => l.names.some((n) => CHIP_LABELS.includes(n)));
      assert.ok(chip, "hàng chip biến mất sau khi mở màn AI");
      console.log(`  sau khi mở: tab = ${chip.names.join(" · ")}`);
      assert.equal(chip.tabCount, 4, "tablist phải vẫn đúng 4 role=tab khi màn AI đang mở");
    });

    /* --- 4. aria-selected follows the tap --------------------------------- */

    test("bấm chip khác thì aria-selected đi theo", async () => {
      await moTabChat(390, 844);
      const truoc = (await page.evaluate(measureChipTablist)).find((l) =>
        l.names.includes("Chat"),
      );
      assert.equal(truoc.selected[0], "true", "mặc định phải đứng ở Chat");

      await page.clickLabel("Thành viên");
      await page.waitFor(
        () =>
          [...document.querySelectorAll('[role="tab"]')].some(
            (t) =>
              (t.getAttribute("aria-label") || "").trim() === "Thành viên" &&
              t.getAttribute("aria-selected") === "true",
          ),
        { label: "chip Thành viên được chọn" },
      );

      const sau = (await page.evaluate(measureChipTablist)).find((l) => l.names.includes("Chat"));
      console.log(`  trước: ${truoc.selected.join(",")}  sau: ${sau.selected.join(",")}`);
      assert.equal(sau.selected[0], "false", "Chat phải nhả ra khi bấm chip khác");
      assert.equal(sau.selected[2], "true", "Thành viên phải nhận aria-selected");
    });

    /* --- 5. no icon-only button is anonymous ------------------------------ */

    test("không nút biểu tượng nào thiếu tên đọc được", async () => {
      await moTabChat(390, 844);
      const buttons = await page.evaluate(measureIconButtonNames);
      const cam = buttons.filter((b) => !b.name && !b.text);
      for (const b of buttons.filter((x) => x.name)) console.log(`  ${b.name}`);
      assert.deepEqual(cam, [], "có nút không có tên và không có chữ, trình đọc màn hình đọc là 'button'");
    });
  });
}
