// rd-qa-11 -- WCAG 2.2 AA scan of the entry-door screens (#115), the place
// #116's invite flow will land once rd-fe-12 builds it.
//
// Two things this script refuses to do, both learned the hard way in this repo:
//
// 1. It does NOT change the fragment on a live page. `AppRoot` reads the URL
//    fragment once at mount, so navigating `#vao=nhom` -> `#vao=dang-ky` leaves
//    the FIRST screen on screen while the report cheerfully names the second.
//    Every hop goes through about:blank to force a real remount.
// 2. It does NOT scan only the page as it loads. The default state carries
//    different ARIA than an opened sheet or a submitted form, and the states
//    are where the defects live. Interactive states are driven, then rescanned.
//
// A zero here means "no axe-detectable violation in the states listed below".
// axe ships no rule for WCAG 2.2 focus-not-obscured (2.4.11) or dragging (2.5.7)
// and only partial target-size (2.5.8), so zero is a floor, not conformance.
//
// Usage:
//   MOBILE_WEB=http://localhost:8911 node a11y_vao_cua.mjs

import { chromium } from "playwright";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const axePath = require.resolve("axe-core");
const AXE_SOURCE = readFileSync(axePath, "utf8");

const WEB = process.env.MOBILE_WEB || "http://localhost:8911";
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function settle(page) {
  await page.waitForLoadState("domcontentloaded");
  for (let i = 0; i < 40; i++) {
    const busy = await page.evaluate(() =>
      /Đang tải|Đang hỏi máy chủ|Đang chờ|Đang mở/.test(document.body.textContent || "")
    );
    if (!busy) break;
    await sleep(400);
  }
  await sleep(600);
}

async function scan(page, label) {
  await page.evaluate(AXE_SOURCE);
  const result = await page.evaluate(
    async (tags) =>
      await window.axe.run(document, {
        runOnly: { type: "tag", values: tags },
        resultTypes: ["violations"],
      }),
    TAGS
  );
  const rows = result.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    count: v.nodes.length,
    help: v.help,
    sample: (v.nodes[0]?.html || "").slice(0, 110),
  }));
  return { label, violations: rows };
}

/** Every visible, focusable control with its accessible name and hit box. */
async function controls(page) {
  return page.evaluate(() => {
    const out = [];
    const nodes = document.querySelectorAll(
      '[role="button"], button, a, input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    for (const n of nodes) {
      const r = n.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const name = (
        n.getAttribute("aria-label") ||
        n.textContent ||
        n.getAttribute("placeholder") ||
        ""
      ).trim();
      out.push({
        name: name.slice(0, 60),
        role: n.getAttribute("role") || n.tagName.toLowerCase(),
        w: Math.round(r.width),
        h: Math.round(r.height),
      });
    }
    return out;
  });
}

async function open(page, fragment) {
  // about:blank between screens: AppRoot reads the fragment once, at mount.
  await page.goto("about:blank");
  await page.goto(`${WEB}/${fragment}`);
  await settle(page);
}

async function main() {
  const browser = await chromium.launch();
  const reports = [];
  const notes = [];

  for (const viewport of [
    { name: "dt-390", width: 390, height: 844 },
    { name: "nho-320", width: 320, height: 640 },
  ]) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
    });
    const page = await context.newPage();

    for (const screen of [
      { frag: "", label: "mo-dau" },
      { frag: "#vao=dang-ky", label: "dang-ky (F01)" },
      { frag: "#vao=nhom", label: "nhom (F03/F04)" },
    ]) {
      await open(page, screen.frag);
      const label = `${screen.label} @${viewport.name}`;
      reports.push(await scan(page, label));

      const found = await controls(page);
      // WCAG 2.2 AA 2.5.8: 24x24 CSS px minimum for a pointer target.
      const tiny = found.filter((c) => c.w < 24 || c.h < 24);
      const unnamed = found.filter((c) => !c.name);
      if (tiny.length || unnamed.length) {
        notes.push({
          label,
          tiny: tiny.map((c) => `${c.role} "${c.name}" ${c.w}x${c.h}`),
          unnamed: unnamed.map((c) => `${c.role} ${c.w}x${c.h}`),
        });
      }
      if (screen.frag === "" && viewport.name === "dt-390") {
        console.log(`  (${label}) so nut nhin thay duoc: ${found.length}`);
      }
    }
    await context.close();
  }

  // The [+] create sheet is a state, not a page: it carries its own ARIA and
  // it is the only route to the group screen from a cold load.
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await open(page, "#tab=len-plan");
  const plus = page.locator('[role="button"], button').filter({ hasText: /^\+$|Tạo|tạo/ }).first();
  if ((await plus.count()) > 0) {
    await plus.click().catch(() => {});
    await sleep(900);
    reports.push(await scan(page, "sheet [+] dang mo @dt-390"));
  } else {
    notes.push({ label: "sheet [+]", tiny: [], unnamed: ["KHONG TIM THAY nut mo sheet"] });
  }
  await context.close();
  await browser.close();

  console.log("\n=== axe WCAG 2.2 AA ===");
  let total = 0;
  for (const r of reports) {
    const n = r.violations.reduce((a, v) => a + v.count, 0);
    total += n;
    console.log(`\n[${r.label}] vi pham=${n}`);
    for (const v of r.violations) {
      console.log(`   ${v.impact.padEnd(8)} ${v.id} x${v.count} -- ${v.help}`);
      console.log(`     vd: ${v.sample}`);
    }
  }

  console.log("\n=== vung bam < 24x24 (WCAG 2.5.8) va nut khong ten ===");
  if (!notes.length) console.log("  khong co");
  for (const n of notes) {
    if (n.tiny.length) console.log(`[${n.label}] nho: ${n.tiny.join(" | ")}`);
    if (n.unnamed.length) console.log(`[${n.label}] khong ten: ${n.unnamed.join(" | ")}`);
  }

  console.log(`\nTONG vi pham axe = ${total} tren ${reports.length} o da quet`);
  console.log(
    "Luu y: axe KHONG co rule cho 2.4.11 (focus bi che) va 2.5.7 (keo tha),\n" +
      "va chi phu mot phan 2.5.8. So 0 la san, khong phai chung nhan dat WCAG 2.2 AA."
  );
}

main().catch((e) => {
  console.error("HONG:", e.message);
  process.exit(2);
});
