/** The screen the bug actually broke: the Tin nhắn tab, on a pre-fix-seeded DB.
 *
 * Before #121 this printed a raw English server string where the member list
 * belongs, because POST /contexts answered 422 idempotency_key_reuse.
 */
import { chromium } from "playwright-core";
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";

const AXE = readFileSync(createRequire(import.meta.url).resolve("axe-core"), "utf8");
const BASE = "http://127.0.0.1:8714";
const OUT = dirname(fileURLToPath(import.meta.url));

const browser = await chromium.launch({ executablePath: timTrinhDuyet() });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();

const errors = [], calls = [];
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("response", (r) => {
  if (r.url().includes("8713"))
    calls.push(`${r.status()} ${r.request().method()} ${r.url().replace("http://127.0.0.1:8713", "")}`);
});
page.on("requestfailed", (r) => {
  if (r.url().includes("8713")) errors.push(`FAILED ${r.request().method()} ${r.url()} :: ${r.failure()?.errorText}`);
});

await page.goto("about:blank");
await page.goto(`${BASE}/#tab=tin-nhan&nguoi=minh`, { waitUntil: "networkidle" });
await page.waitForTimeout(8000);

const text = await page.evaluate(() => document.body.innerText);
writeFileSync(`${OUT}/man-tin-nhan.txt`, text);
await page.screenshot({ path: `${OUT}/man-tin-nhan.png`, fullPage: true });

console.log("=== API CALLS (cross-origin 8714 -> 8713) ===");
console.log(calls.length ? calls.join("\n") : "(none)");
console.log("\n=== ERRORS ===");
console.log(errors.length ? [...new Set(errors)].slice(0, 10).join("\n") : "(none)");
console.log("\n=== WHAT THE USER SEES ===");
console.log(text.slice(0, 1100));

await page.addScriptTag({ content: AXE });
const axe = await page.evaluate(async () =>
  await window.axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag22aa"] } }));
writeFileSync(`${OUT}/axe-tin-nhan.json`, JSON.stringify(axe.violations, null, 2));
console.log("\n=== AXE (wcag2a/2aa/2.2aa) ===");
console.log(`violations: ${axe.violations.length} | passes: ${axe.passes.length}`);
for (const v of axe.violations) console.log(`  [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node)`);

await browser.close();
