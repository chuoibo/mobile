/* rd-qa-02 · Self-check for the keyboard/focus probes on the money surface.
 *
 *     node --test tests/qa/rd-qa-02/keyboard-money.selfcheck.mjs
 *
 * Why this file exists
 * --------------------
 * `a11y-money-surfaces.mjs` used to end with two `console.log` calls that never
 * added to `failures`:
 *
 *     console.log(`  phím Tab đầu tiên dừng ở: ${reachable}`);
 *     console.log(`  focus thấy được: outline=${focusVisible.outline} ...`);
 *
 * On a page where Tab landed on the wrong button the script still printed
 * `0 vấn đề chặn` and exited 0 — while README.md's results table listed
 * "Tab đầu tiên dừng đúng ở nút chép số tiền" as a check that had passed.
 *
 * So this file does to the keyboard probes what `name-leak.selfcheck.mjs` did
 * to the name detector: plant a page that is KNOWN to be broken and assert the
 * check fires — including end-to-end, by running the real CLI and reading its
 * exit code. A check that cannot go red is not a check.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";
import {
  probeCopyControlKeyboard,
  gradeKeyboardProbe,
  FOCUS_PROPS,
} from "./keyboard-money.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const CLI = join(HERE, "a11y-money-surfaces.mjs");

/* --- Fixtures ------------------------------------------------------------
 *
 * Shaped like the real guest page: one button whose accessible name carries the
 * figure, `data-copy` carrying the raw đồng, sized and coloured to clear axe
 * (wcag2a/2aa/22aa) so the ONLY thing that can fail is the keyboard check.
 * Each mutant changes exactly one thing. */
const fixture = ({ decoy = false, tabbable = true, focusRing = true } = {}) => `<!doctype html>
<html lang="vi">
<head><meta charset="utf-8"><title>Phần của Hà</title>
<style>
  body { background:#fff; color:#1a1a1a; font-family: system-ui, sans-serif; margin:1rem; }
  button { background:#fff; color:#1a1a1a; border:1px solid #1a1a1a;
           min-width:48px; min-height:48px; font-size:16px; display:block;
           margin-bottom:1rem; }
  ${
    focusRing
      ? ":where(button):focus-visible { outline: 2px solid #0a5533; outline-offset: 2px; }"
      : "button:focus, button:focus-visible { outline: none; }"
  }
</style>
</head>
<body>
  ${decoy ? '<button type="button">Đóng</button>' : ""}
  <button class="amount" type="button"${tabbable ? "" : ' tabindex="-1"'}
          data-copy="246914"
          aria-label="Sao chép số tiền 246.914 đồng">246.914</button>
</body>
</html>`;

/** The four pages under test. `healthy` is the positive control: without it, a
 * probe that reported "broken" for everything would pass every mutant test. */
const PAGES = {
  healthy: fixture(),
  decoyFirst: fixture({ decoy: true }),
  unreachable: fixture({ tabbable: false }),
  noFocusRing: fixture({ focusRing: false }),
  // Shaped like a revoked/expired link: real page, no money on it at all.
  noMoney: `<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><title>Link đã thu hồi</title></head>
<body style="background:#fff;color:#1a1a1a"><h1>Link này đã bị thu hồi.</h1></body></html>`,
};

let browser;
let page;
let tmp;
const urls = {};

test.before(async () => {
  browser = await chromium.launch();
  // Same shape as the CLI, and reducedMotion so the 0.15s border/background
  // transitions in guest.css cannot be caught mid-flight and misread as a
  // focus indicator. This only makes the check stricter.
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  page = await context.newPage();

  tmp = mkdtempSync(join(tmpdir(), "rd-qa-02-kb-"));
  for (const [name, html] of Object.entries(PAGES)) {
    const file = join(tmp, `${name}.html`);
    writeFileSync(file, html, "utf8");
    urls[name] = pathToFileURL(file).href;
  }
});

test.after(async () => {
  await browser?.close();
  if (tmp) rmSync(tmp, { recursive: true, force: true });
});

const probe = async (name) => {
  await page.goto(urls[name], { waitUntil: "domcontentloaded" });
  return probeCopyControlKeyboard(page);
};

/* --- The positive control ------------------------------------------------ */

test("đối chứng dương: trang lành thì probe thấy nút ở Tab #1, có vòng focus", async () => {
  const p = await probe("healthy");
  assert.equal(p.reached, true, "nút chép phải tới được bằng bàn phím");
  assert.equal(p.tabIndex, 1, "trên trang lành, Tab đầu tiên phải dừng ở nút chép");
  assert.equal(p.focusVisible, true, ":focus-visible phải khớp sau khi Tab tới");
  assert.ok(
    p.changed.includes("outlineStyle"),
    `focus phải làm đổi outline, nhưng chỉ thấy đổi: ${JSON.stringify(p.changed)}`,
  );
  assert.deepEqual(gradeKeyboardProbe(p).problems, [], "trang lành không được có vấn đề");
});

/* --- The three mutants ---------------------------------------------------
 *
 * Each one is a page the OLD code printed a log line for and exited 0 on. */

test("mutant: một nút khác chen trước → phép kiểm phải đỏ", async () => {
  const p = await probe("decoyFirst");
  assert.equal(p.reached, true, "vẫn tới được, chỉ là không ở lần Tab đầu");
  assert.equal(p.tabIndex, 2);
  const { problems } = gradeKeyboardProbe(p);
  assert.equal(problems.length, 1, `kỳ vọng đúng 1 vấn đề, nhận: ${JSON.stringify(problems)}`);
  assert.match(problems[0], /Tab đầu tiên dừng ở/);
});

test("mutant: nút chép có tabindex=-1 → phép kiểm phải đỏ", async () => {
  const p = await probe("unreachable");
  assert.equal(p.reached, false, "tabindex=-1 thì bàn phím không tới được");
  const { problems } = gradeKeyboardProbe(p);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /KHÔNG tới được bằng bàn phím/);
  assert.match(problems[0], /WCAG 2\.1\.1/);
});

test("mutant: focus không đổi gì trên màn hình → phép kiểm phải đỏ", async () => {
  const p = await probe("noFocusRing");
  assert.equal(p.reached, true, "vẫn nhận được focus, chỉ là không nhìn thấy");
  assert.equal(p.tabIndex, 1);
  assert.deepEqual(
    p.changed,
    [],
    `outline:none thì không thuộc tính nào được đổi, nhưng thấy: ${JSON.stringify(p.changed)}`,
  );
  const { problems } = gradeKeyboardProbe(p);
  assert.ok(
    problems.some((m) => /WCAG 2\.4\.7/.test(m)),
    `kỳ vọng một vấn đề Focus Visible, nhận: ${JSON.stringify(problems)}`,
  );
});

/* --- Pin the dead spelling ----------------------------------------------- */

test("cách đo cũ getComputedStyle(el, ':focus-visible') thật sự đo được KHÔNG GÌ CẢ", async () => {
  // This is the property that made the old line un-assertable: it returns the
  // same empty answer for the page WITH a focus ring and the page WITHOUT one,
  // so no assertion written on top of it could ever have separated them.
  const readOldWay = async (name) => {
    await page.goto(urls[name], { waitUntil: "domcontentloaded" });
    await page.keyboard.press("Tab");
    return page.locator("[data-copy]").first().evaluate((el) => {
      el.focus();
      const s = getComputedStyle(el, ":focus-visible");
      return { outline: s.outlineStyle, width: s.outlineWidth };
    });
  };

  const good = await readOldWay("healthy");
  const bad = await readOldWay("noFocusRing");
  assert.equal(good.outline, "", "cách đo cũ trả về rỗng ngay cả khi CÓ vòng focus");
  assert.deepEqual(
    good,
    bad,
    "cách đo cũ trả cùng một kết quả cho trang có và không có vòng focus — " +
      "không assert nào dựng trên nó có thể phân biệt được hai trang",
  );

  // ...while the spelling that replaced it does separate them.
  const nowGood = await probe("healthy");
  const nowBad = await probe("noFocusRing");
  assert.notDeepEqual(nowGood.changed, nowBad.changed);
});

/* --- Grading is pure, so grade it without a browser too ------------------ */

test("gradeKeyboardProbe: không có [data-copy] nào là một vấn đề", () => {
  const { problems } = gradeKeyboardProbe({
    reached: false, tabIndex: null, trail: [], focusVisible: null,
    changed: [], resting: null, focused: null,
  });
  assert.equal(problems.length, 1);
  assert.match(problems[0], /không tìm thấy nút \[data-copy\]/);
});

test("gradeKeyboardProbe: gộp được nhiều vấn đề cùng lúc", () => {
  const { problems } = gradeKeyboardProbe({
    reached: true, tabIndex: 3, trail: ["a", "b", "button"], focusVisible: false,
    changed: [], resting: {}, focused: {},
  });
  assert.equal(problems.length, 3, JSON.stringify(problems));
});

test("gradeKeyboardProbe: trang lành ra danh sách rỗng", () => {
  const { problems } = gradeKeyboardProbe({
    reached: true, tabIndex: 1, trail: ["button[...]"], focusVisible: true,
    changed: ["outlineStyle"], resting: {}, focused: {},
  });
  assert.deepEqual(problems, []);
});

test("FOCUS_PROPS không rỗng — danh sách rỗng làm phép kiểm 'đổi gì đó' luôn đỏ", () => {
  assert.ok(FOCUS_PROPS.length >= 4);
  assert.ok(FOCUS_PROPS.includes("outlineStyle"));
});

/* --- End to end: the CLI itself must exit non-zero -----------------------
 *
 * The unit tests above prove the probe and the grading are right. These prove
 * the CLI actually WIRES them to its exit code — which is the exact thing that
 * was missing. Run the real binary, read the real exit code. */

const runCli = (name) =>
  spawnSync(process.execPath, [CLI, urls[name]], { encoding: "utf8", cwd: HERE });

test("CLI: trang lành → exit 0", () => {
  const r = runCli("healthy");
  assert.equal(r.status, 0, `stdout:\n${r.stdout}\nstderr:\n${r.stderr}`);
  assert.match(r.stdout, /0 vấn đề chặn/);
});

test("CLI: Tab dừng ở nút khác → exit khác 0 (đây là lỗi được báo)", () => {
  const r = runCli("decoyFirst");
  assert.notEqual(
    r.status,
    0,
    "CLI thoát 0 trên trang mà Tab dừng sai chỗ — đúng lỗi cũ đã quay lại.\n" + r.stdout,
  );
  assert.match(r.stdout, /Tab đầu tiên dừng ở/);
  assert.doesNotMatch(r.stdout, /0 vấn đề chặn/);
});

test("CLI: nút chép không tới được bằng bàn phím → exit khác 0", () => {
  const r = runCli("unreachable");
  assert.notEqual(r.status, 0, r.stdout);
  assert.match(r.stdout, /KHÔNG tới được bằng bàn phím/);
});

test("CLI: không có dấu hiệu focus → exit khác 0", () => {
  const r = runCli("noFocusRing");
  assert.notEqual(r.status, 0, r.stdout);
  assert.match(r.stdout, /WCAG 2\.4\.7/);
});

test("CLI: trang không có bề mặt tiền → nói CHƯA QUÉT, không im lặng exit 0", () => {
  // A revoked link legitimately has no amount. The old guard skipped the whole
  // block and exited 0 — indistinguishable from "scanned and clean". It must
  // now say the surface was never scanned, and refuse to call a run with zero
  // money surfaces a pass.
  const r = runCli("noMoney");
  assert.match(r.stdout, /CHƯA QUÉT/);
  assert.match(r.stdout, /đã quét bề mặt tiền trên 0\/1 url/);
  assert.notEqual(r.status, 0, "quét 0 bề mặt tiền mà exit 0 là xanh giả\n" + r.stdout);
});

test("CLI: báo rõ đã quét bao nhiêu url có bề mặt tiền", () => {
  const r = runCli("healthy");
  assert.match(r.stdout, /đã quét bề mặt tiền trên 1\/1 url/);
});
