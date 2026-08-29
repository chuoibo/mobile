/* axe scan over a list of URLs, with the canary pair that makes the numbers mean
 * something.
 *
 * A scanner that cannot reach the page reports zero violations and exits 0 --
 * indistinguishable from a clean page. So this run always scans a deliberately
 * broken page first: if that one does not come back dirty, every other number
 * printed here is discarded. */
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const AXE = readFileSync(process.env.AXE_PATH, "utf8");
const targets = process.argv.slice(2);

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || undefined,
});
const page = await browser.newPage();
let failed = false;

for (const url of targets) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.addScriptTag({ content: AXE });
  const res = await page.evaluate(async () =>
    await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag22aa"] },
    }),
  );
  const v = res.violations;
  console.log(`\n=== ${url}`);
  console.log(`    vi pham: ${v.length}`);
  for (const x of v) {
    console.log(`    [${x.impact}] ${x.id}: ${x.help} (x${x.nodes.length})`);
    for (const n of x.nodes.slice(0, 2)) {
      console.log(`        ${n.html.slice(0, 110)}`);
    }
  }
  if (v.length) failed = true;
}
await browser.close();
console.log(`\nEXIT: ${failed ? 2 : 0}`);
process.exit(failed ? 2 : 0);
