/**
 * Scan the RENDERED bundle, not the source.
 *
 * The two gates merged as #122 and #125 read react-native-web's emitted markup
 * in node. That is much better than reading .tsx, but it is still not a
 * browser: rnw 0.21.2 has been observed dropping attributes on the way to the
 * DOM that its own render output claims to set. This script asks the only
 * question that settles it -- what does a browser actually have.
 *
 * Three things it refuses to do:
 *   1. Report "clean" without proving the scanner can go dirty. A dead axe and
 *      a clean page return the same empty array, so a planted violation runs
 *      first and MUST be caught.
 *   2. Report "clean" on a blank page. If the app never mounted there is
 *      nothing to find and zero violations is a lie, so mount is asserted.
 *   3. Trust a stale bundle. The caller passes the URL; the SHA is recorded by
 *      the report, and the bundle must be built from it.
 *
 * Usage: NODE_PATH=<...>/rd-qa-11/node_modules node scan-render.mjs <url>
 */

import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const URL_UNDER_TEST = process.argv[2] ?? "http://localhost:8913/";
const WCAG = ["wcag2a", "wcag2aa", "wcag22aa"];

const results = [];
/**
 * `ok` is tri-state on purpose. A check whose widget does not exist on this
 * screen has not passed -- printing PASS there is the false green this whole
 * scan exists to avoid. Pass `null` for "not covered".
 */
function record(name, ok, detail) {
  results.push({ name, ok, detail });
  const state = ok === null ? "NOT COVERED" : ok ? "PASS" : "FAIL";
  console.log(`${state.padEnd(11)} ${name}${detail ? ` -- ${detail}` : ""}`);
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();

const consoleErrors = [];
page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
page.on("pageerror", (e) => consoleErrors.push(String(e)));

await page.goto(URL_UNDER_TEST, { waitUntil: "networkidle" });

// ---------------------------------------------------------------------------
// 0. Did the app mount at all? Everything below is meaningless otherwise.
// ---------------------------------------------------------------------------
const mounted = await page.evaluate(() => {
  const root = document.getElementById("root") ?? document.body;
  return {
    nodes: root.querySelectorAll("*").length,
    text: (root.innerText || "").trim().slice(0, 400),
    buttons: document.querySelectorAll('[role="button"], button').length,
    inputs: document.querySelectorAll("input, textarea").length,
  };
});
record(
  "app mounted (DOM is not empty)",
  mounted.nodes > 20,
  `${mounted.nodes} nodes, ${mounted.buttons} buttons, ${mounted.inputs} inputs`
);
console.log(`\n--- visible text (first 400 chars) ---\n${mounted.text}\n---\n`);

// ---------------------------------------------------------------------------
// 1. CANARY: plant a violation axe must catch. Proves the scanner is alive.
// ---------------------------------------------------------------------------
await page.evaluate(() => {
  // A real file the page already serves, so no inline payload is needed --
  // repo guard fails closed on base64 blobs and it is right to.
  const img = document.createElement("img");
  img.src = "/favicon.ico";
  img.id = "rd-qa-13-canary";
  document.body.appendChild(img); // no alt -> image-alt violation
});
const canary = await new AxeBuilder({ page }).withTags(WCAG).analyze();
const caught = canary.violations.some((v) => v.id === "image-alt");
record(
  "canary: axe catches a planted image-alt violation",
  caught,
  caught ? "scanner is alive" : "SCANNER IS DEAD - every clean result below is worthless"
);
await page.evaluate(() => document.getElementById("rd-qa-13-canary")?.remove());

// ---------------------------------------------------------------------------
// 2. The real scan.
// ---------------------------------------------------------------------------
const scan = await new AxeBuilder({ page }).withTags(WCAG).analyze();
const serious = scan.violations.filter(
  (v) => v.impact === "critical" || v.impact === "serious"
);
record(
  "axe: no critical/serious violations on the rendered page",
  serious.length === 0,
  serious.length === 0
    ? `${scan.passes.length} rules passed`
    : serious.map((v) => `${v.id}(${v.impact}) x${v.nodes.length}`).join(", ")
);
for (const v of scan.violations) {
  console.log(`    [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node)`);
  for (const n of v.nodes.slice(0, 3)) console.log(`        ${n.html.slice(0, 160)}`);
}

// ---------------------------------------------------------------------------
// 3. #125 in the DOM: every input carries an accessible name that is NOT its
//    placeholder. The node gate proves rnw emits it; this proves it survived.
// ---------------------------------------------------------------------------
const inputs = await page.evaluate(() =>
  [...document.querySelectorAll("input, textarea")].map((el) => ({
    placeholder: el.getAttribute("placeholder"),
    ariaLabel: el.getAttribute("aria-label"),
    labelledBy: el.getAttribute("aria-labelledby"),
    id: el.id,
  }))
);
if (inputs.length === 0) {
  record("#125 rendered: inputs carry a non-placeholder name", null, "no inputs on this screen");
} else {
  const nameless = inputs.filter((i) => !i.ariaLabel && !i.labelledBy);
  const placeholderOnly = inputs.filter(
    (i) => i.ariaLabel && i.placeholder && i.ariaLabel === i.placeholder
  );
  record(
    "#125 rendered: every input has a name that is not the placeholder",
    nameless.length === 0 && placeholderOnly.length === 0,
    `${inputs.length} inputs, ${nameless.length} nameless, ${placeholderOnly.length} name==placeholder`
  );
}

// ---------------------------------------------------------------------------
// 4. #122 in the DOM: a scrollable region must be keyboard reachable.
// ---------------------------------------------------------------------------
const scrollers = await page.evaluate(() =>
  [...document.querySelectorAll("*")]
    .filter((el) => {
      const s = getComputedStyle(el);
      const scrolls = /auto|scroll/.test(s.overflowY);
      return scrolls && el.scrollHeight > el.clientHeight + 4;
    })
    .map((el) => ({
      tag: el.tagName,
      tabindex: el.getAttribute("tabindex"),
      cls: (el.className || "").toString().slice(0, 40),
    }))
);
if (scrollers.length === 0) {
  record("#122 rendered: scrollable regions are focusable", null, "no overflowing scroller on this screen");
} else {
  const unreachable = scrollers.filter((s) => s.tabindex === null);
  record(
    "#122 rendered: every overflowing scroll region has a tabindex",
    unreachable.length === 0,
    `${scrollers.length} scrollers, ${unreachable.length} without tabindex`
  );
}

// ---------------------------------------------------------------------------
// 5. Console must be quiet: a page that mounted while throwing is not healthy.
// ---------------------------------------------------------------------------
record(
  "no console/page errors during load",
  consoleErrors.length === 0,
  consoleErrors.slice(0, 3).join(" | ") || "clean"
);

await browser.close();

const failed = results.filter((r) => r.ok === false);
const uncovered = results.filter((r) => r.ok === null);
console.log(
  `\n${results.filter((r) => r.ok === true).length} pass, ${failed.length} fail, ${uncovered.length} NOT COVERED`
);
process.exit(failed.length === 0 ? 0 : 1);
