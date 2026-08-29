/* Three defects in the shell that only a rendered page can see.
 *
 * QA measured all three on the merge of PR #78 and none of the existing gates
 * moved, because none of them render anything. `tsc` typechecks props; it does
 * not know that react-native-web drops one of them. `npm test` bundles the app;
 * a bundle that builds is not a page that behaves. So the three sat green.
 *
 *   1. The opening screen scrolls sideways on web. Three decorative ridges are
 *      absolutely positioned at left:-14% with width:128%, and a react-native
 *      `View` does not clip its children on web, so the document is 445px wide
 *      inside a 390px viewport. Swiping right reveals a white band and cuts the
 *      sign-in buttons off the left edge -- on the first screen of the demo.
 *
 *   2. `accessibilityState={{selected}}` reaches the DOM as nothing at all.
 *      react-native-web 0.21 handles zero props by that name (grep it), so all
 *      four tabs read identically to a screen reader and none of them says
 *      which one you are on. WCAG 4.1.2, level A.
 *
 *   3. The [+] sheet covers the screen but does not hold focus. Tab walks
 *      straight through it onto the four tabs and the close button underneath,
 *      each of them 100% occluded and still pressable. WCAG 2.4.3.
 *
 * What this file proves: on the build in `MOBILE_WEB_EXPORT`, at the listed
 * viewports, in this Chrome. What it does not prove: any of it on iOS or
 * Android, where the clipping rule and the accessibility bridge are different
 * code -- #2's fix uses `aria-*`, which React Native core folds back into
 * `accessibilityState`, but that path is asserted by reading RN's source, not
 * by this file.
 *
 * Run from apps/mobile, against a build you made yourself:
 *
 *     npx expo export --platform web --output-dir /tmp/w
 *     MOBILE_WEB_EXPORT=/tmp/w MOBILE_REQUIRE_WEB_A11Y=1 \
 *       node --test tests/vo-tab-web.test.mjs
 *
 * Under plain `npm test` it reads `.expo-build-check`, which the `build:check`
 * step of that same command has just written. With no build and no Chrome it
 * skips and says so; `MOBILE_REQUIRE_WEB_A11Y=1` turns that skip into a
 * failure, which is the form anyone claiming these three are fixed has to run.
 * Same convention as `MOBILE_REQUIRE_E2E`, deliberately.
 */
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { after, before, describe, test } from "node:test";

import { findChrome, launch, serve } from "./chrome-cdp.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const EXPORT_DIR = process.env.MOBILE_WEB_EXPORT ?? join(HERE, "..", ".expo-build-check");
const REQUIRED = process.env.MOBILE_REQUIRE_WEB_A11Y === "1";

/** Viewports the report measured. 320 is the narrowest phone still in use, 390
 *  is the iPhone the demo runs on, 1280 is the web fallback. */
const VIEWPORTS = [
  { name: "320x720", w: 320, h: 720 },
  { name: "390x844", w: 390, h: 844 },
  { name: "1280x800", w: 1280, h: 800 },
];

const BO_QUA = "Bỏ qua, vào app mà chưa chọn người";
const TAB_LABELS = {
  "kham-pha": "Khám phá — gợi ý chỗ đi cho nhóm",
  "ca-nhan": "Cá nhân — hồ sơ và tài chính của bạn",
};

const chromeBin = findChrome();
const reasons = [];
if (!existsSync(join(EXPORT_DIR, "index.html"))) {
  reasons.push(`no web export at ${EXPORT_DIR} (run: npx expo export --platform web --output-dir …)`);
}
if (!chromeBin) {
  reasons.push("no Chrome found (set CHROME_BIN, or install one via playwright)");
}

/* ------------------------------------------------------ measurements, in-page --- */

/* Kept as named functions so a failure message can quote the source of the
 * number rather than an anonymous blob of stringified JavaScript. */

function measureOverflow() {
  const doc = document.documentElement;
  window.scrollTo(0, 0);
  window.scrollTo(9999, 0);
  const scrollX = Math.round(window.scrollX);
  window.scrollTo(0, 0);

  const clientWidth = doc.clientWidth;

  /* An element wider than the viewport is only a defect if nothing clips it.
   * `getBoundingClientRect` returns the layout box, which `overflow: hidden`
   * on a parent does not change -- the ridges on this screen are *meant* to be
   * 445px wide inside a 390px viewport, that is what makes three arcs read as
   * a range. So the question is not "is anything oversized" but "does anything
   * oversized reach the edge unclipped".
   *
   * The walk stops below <body> on purpose. body computes to `overflow:
   * hidden` here and still does not clip anything: when <html> is `visible`,
   * the body's overflow is propagated to the viewport and body itself is
   * treated as visible. That propagated `hidden` is why this bug had no
   * scrollbar to notice while `scrollTo(9999, 0)` still moved 55px. Counting
   * body as a clipper would have made this check green on the broken build. */
  function clippedByAncestor(el) {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox === "hidden" || ox === "clip" || ox === "auto" || ox === "scroll") return true;
    }
    return false;
  }

  const offenders = [];
  const oversized = [];
  for (const el of document.querySelectorAll("*")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right <= clientWidth + 0.5 && r.left >= -0.5) continue;
    const found = {
      tag: el.tagName,
      left: Math.round(r.left),
      right: Math.round(r.right),
      text: (el.textContent || "").trim().slice(0, 24),
    };
    oversized.push(found);
    if (!clippedByAncestor(el)) offenders.push(found);
  }

  return {
    scrollWidth: doc.scrollWidth,
    clientWidth,
    scrollX,
    htmlOverflowX: getComputedStyle(doc).overflowX,
    bodyOverflowX: getComputedStyle(document.body).overflowX,
    oversized: oversized.slice(0, 6),
    offenders: offenders.slice(0, 6),
  };
}

function readTabBar() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const plus = document.querySelector(
    '[aria-label="Tạo mới"], [aria-label="Đóng menu tạo mới"]',
  );
  return {
    labels: tabs.map((t) => t.getAttribute("aria-label")),
    selected: tabs.map((t) => t.getAttribute("aria-selected")),
    plusLabel: plus ? plus.getAttribute("aria-label") : null,
    plusExpanded: plus ? plus.getAttribute("aria-expanded") : null,
  };
}

/** Where focus is, and whether anything is painted on top of it.
 *
 *  Occlusion is measured with `elementFromPoint` at the focused element's own
 *  centre rather than by asking which subtree it belongs to. A control the
 *  sheet covers completely is unreachable by a sighted keyboard user however
 *  the DOM is arranged, and that is the thing WCAG 2.4.3 is about. */
function readFocus() {
  const el = document.activeElement;
  if (!el || el === document.body) return { label: "(body)", tag: "BODY", occluded: false };
  const r = el.getBoundingClientRect();
  const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return {
    tag: el.tagName,
    label: el.getAttribute("aria-label") || (el.textContent || "").trim().slice(0, 32) || "(no label)",
    occluded: !(top && (top === el || el.contains(top) || top.contains(el))),
  };
}

/* -------------------------------------------------------------------- gate --- */

if (reasons.length && !REQUIRED) {
  // A skip that says what it skipped and how to un-skip it. The failure this
  // guards against is a suite that reports "3 passed" for three checks that
  // never touched a browser.
  test(`vỏ tab trên web — BỎ QUA: ${reasons.join("; ")}`, { skip: reasons.join("; ") }, () => {});
} else {
  describe("vỏ tab và màn mở đầu, đo trên trang render thật", () => {
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

    /** Reload to the opening screen. Every test starts from the same state so
     *  the order they run in cannot change an answer. */
    async function openManMoDau(w, h) {
      await page.viewport(w, h);
      // `BO_QUA` is passed in rather than closed over: the predicate is
      // stringified and run inside the page, where this module's constants do
      // not exist.
      await page.goto(
        server.url,
        (label) => !!document.querySelector(`[aria-label="${label}"]`),
        BO_QUA,
      );
    }

    async function vaoVoTab(w, h) {
      await openManMoDau(w, h);
      await page.clickLabel(BO_QUA);
      await page.waitFor(() => document.querySelectorAll('[role="tab"]').length === 4, {
        label: "bốn tab",
      });
    }

    /* --- 1. the opening screen does not scroll sideways ------------------- */

    for (const v of VIEWPORTS) {
      test(`màn mở đầu không cuộn ngang ở ${v.name}`, async () => {
        await openManMoDau(v.w, v.h);
        const m = await page.evaluate(measureOverflow);
        console.log(
          `  ${v.name}: scrollWidth ${m.scrollWidth} / clientWidth ${m.clientWidth}` +
            `, scrollX sau scrollTo(9999,0) = ${m.scrollX}` +
            `, html overflow-x = ${m.htmlOverflowX}, body = ${m.bodyOverflowX}`,
        );
        for (const o of m.oversized) {
          const clipped = !m.offenders.some((f) => f.left === o.left && f.right === o.right);
          console.log(
            `    <${o.tag}> left=${o.left} right=${o.right} ${clipped ? "(bị cắt — không sao)" : "TRÀN RA NGOÀI"} ${o.text}`,
          );
        }

        assert.equal(
          m.scrollWidth,
          m.clientWidth,
          `tài liệu rộng hơn khung: ${m.scrollWidth} > ${m.clientWidth}`,
        );
        // scrollWidth alone is not enough. It is the assertion that goes green
        // first when somebody puts overflow-x:hidden on <html>, which hides the
        // symptom and leaves the element sticking out. This one only passes if
        // there is genuinely nothing to scroll to.
        assert.equal(m.scrollX, 0, "vuốt sang phải vẫn cuộn được");
        assert.deepEqual(
          m.offenders,
          [],
          "còn phần tử vượt bề ngang khung mà không tổ tiên nào cắt",
        );
      });
    }

    /* --- 2. the selected tab says so in the accessibility tree ------------ */

    test("aria-selected có mặt và chỉ đúng một tab đang chọn", async () => {
      await vaoVoTab(390, 844);

      const start = await page.evaluate(readTabBar);
      console.log(`  nhãn tab : ${JSON.stringify(start.labels)}`);
      console.log(`  aria-selected: ${JSON.stringify(start.selected)}`);

      assert.equal(start.labels.length, 4);
      assert.equal(
        start.selected.filter((s) => s === null).length,
        0,
        "có tab không khai aria-selected — trình đọc màn hình không biết đang ở đâu",
      );
      assert.equal(
        start.selected.filter((s) => s === "true").length,
        1,
        "phải có đúng một tab được đánh dấu đang chọn",
      );
      assert.equal(
        start.selected[start.labels.indexOf(TAB_LABELS["kham-pha"])],
        "true",
        "tab mặc định là Khám phá",
      );
    });

    test("đổi tab thì aria-selected đi theo", async () => {
      await vaoVoTab(390, 844);
      await page.clickLabel(TAB_LABELS["ca-nhan"]);
      await page.waitFor(
        (label) =>
          document.querySelector(`[aria-label="${label}"]`)?.getAttribute("aria-selected") === "true",
        { label: "Cá nhân được chọn", timeout: 4000 },
        TAB_LABELS["ca-nhan"],
      ).catch(() => {});

      const after_ = await page.evaluate(readTabBar);
      console.log(`  sau khi bấm Cá nhân: ${JSON.stringify(after_.selected)}`);
      assert.equal(after_.selected[after_.labels.indexOf(TAB_LABELS["ca-nhan"])], "true");
      assert.equal(after_.selected[after_.labels.indexOf(TAB_LABELS["kham-pha"])], "false");
    });

    test("nút [+] khai aria-expanded, và đổi khi mở", async () => {
      await vaoVoTab(390, 844);
      const closed = await page.evaluate(readTabBar);
      console.log(`  [+] đóng: label=${closed.plusLabel} aria-expanded=${closed.plusExpanded}`);
      assert.equal(closed.plusExpanded, "false");

      await page.clickLabel("Tạo mới");
      await page.waitFor(() => !!document.querySelector('[aria-label^="Tạo khoản chi"]'), {
        label: "sheet [+] mở",
      });
      const open = await page.evaluate(readTabBar);
      console.log(`  [+] mở  : label=${open.plusLabel} aria-expanded=${open.plusExpanded}`);
      assert.equal(open.plusExpanded, "true");
    });

    /* --- 3. focus stays inside the sheet ---------------------------------- */

    test("mở [+] rồi bấm Tab 12 lần: không điểm dừng nào bị sheet đè", async () => {
      await vaoVoTab(390, 844);
      await page.clickLabel("Tạo mới");
      await page.waitFor(() => !!document.querySelector('[aria-label^="Tạo khoản chi"]'), {
        label: "sheet [+] mở",
      });

      const stops = [];
      for (let i = 0; i < 12; i++) {
        await page.pressTab();
        stops.push(await page.evaluate(readFocus));
      }
      for (const [i, s] of stops.entries()) {
        console.log(`  tab ${String(i + 1).padStart(2)}: ${s.occluded ? "BỊ ĐÈ " : "thấy   "} ${s.label}`);
      }

      const occluded = stops.filter((s) => s.occluded);
      assert.deepEqual(
        occluded.map((s) => s.label),
        [],
        `${occluded.length}/12 điểm dừng nằm dưới sheet mà vẫn focus được`,
      );
    });
  });
}
