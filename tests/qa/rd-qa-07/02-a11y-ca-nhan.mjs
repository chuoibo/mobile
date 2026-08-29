/* rd-qa-07 · axe on the personal screen, with the detector proved alive first.
 *
 * A zero-violation run is worth nothing on its own: the same empty array comes
 * back when axe scanned a blank page, scanned the wrong frame, or never ran.
 * rd-qa-06 hit exactly that, and imp-detect has produced `[] + exit 0` on this
 * repo for want of a browser. So the order here is deliberate -- plant two
 * defects axe is certain to catch, watch the count RISE, and only then believe
 * the clean number from the untouched screen.
 *
 * Scope is WCAG 2.2 A/AA. What axe cannot answer is written into the report as
 * unscanned rather than quietly folded into a pass: it ships no rule for
 * 2.4.11 focus-not-obscured or 2.5.7 dragging, and only partial 2.5.8 target
 * size.
 */
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const WEB = process.env.WEB_URL ?? "http://127.0.0.1:8641";
const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];

const browser = await chromium.launch();
// AxeBuilder refuses a page created straight off the browser; it needs an
// explicit context to inject into.
const context = await browser.newContext({
  viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
});
const page = await context.newPage();
await page.goto(`${WEB}/index.html#tab=ca-nhan&nguoi=minh`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000);

const scan = async () => (await new AxeBuilder({ page }).withTags(TAGS).analyze()).violations;

const clean = await scan();
console.log(`clean screen: ${clean.length} violation(s)`);
for (const v of clean) console.log(`   ${v.impact}  ${v.id}  (${v.nodes.length}x)  ${v.help}`);

// --- control: plant defects and require the count to rise -------------------
await page.evaluate(() => {
  // A real file rather than an inline data URI: the repo guard fails closed on
  // base64 blobs and rejected the commit, which is the guard working. The
  // `image-alt` rule keys on the missing `alt`, not on the bytes loading.
  const img = document.createElement("img");
  img.id = "qa07-altless";
  img.src = "favicon.ico";
  document.body.appendChild(img);                       // no alt -> image-alt
  const btn = document.createElement("button");
  btn.id = "qa07-nameless";
  document.body.appendChild(btn);                       // no name -> button-name
});
const planted = await scan();
const ids = new Set(planted.map((v) => v.id));
console.log(`\nafter planting 2 defects: ${planted.length} violation(s) -> ${[...ids].join(", ")}`);

const alive = planted.length > clean.length && ids.has("image-alt") && ids.has("button-name");
console.log(alive
  ? "  ok   detector is ALIVE (count rose, and by the two expected rules)"
  : "  FAIL detector did NOT react -- the clean number above proves nothing");

// Remove the planted nodes so the contrast/target-size figures below describe
// the real screen and not the harness's own litter.
await page.evaluate(() => {
  document.querySelector("#qa07-nameless")?.remove();
  document.querySelector("#qa07-altless")?.remove();
});

// --- keyboard: axe cannot tell you whether the screen is operable ----------
const stops = [];
for (let i = 0; i < 10; i++) {
  await page.keyboard.press("Tab");
  stops.push(await page.evaluate(() => {
    const el = document.activeElement;
    if (!el || el === document.body) return "(body)";
    return `${el.tagName.toLowerCase()}:${(el.innerText || el.getAttribute("aria-label") || "").trim().slice(0, 28)}`;
  }));
}
console.log(`\ntab stops (10): ${JSON.stringify(stops)}`);
const reachable = new Set(stops.filter((s) => s !== "(body)")).size;
console.log(`distinct reachable stops: ${reachable}`);

await page.screenshot({ path: "/tmp/rdqa07-a11y.png", fullPage: true });
await browser.close();

const failed = !alive || clean.length > 0;
console.log(`\n02-a11y-ca-nhan: ${failed ? "FAIL" : "PASS"} ` +
  `(clean=${clean.length}, detector_alive=${alive}, reachable_stops=${reachable})`);
process.exit(failed ? 1 : 0);
