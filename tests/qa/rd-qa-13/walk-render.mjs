/**
 * Walk the entry flow in a browser and re-check #125 / #122 on each screen.
 *
 * `scan-render.mjs` found the landing screen clean but reported both gates
 * NOT COVERED: no inputs and no overflowing scroller exist there. A gate that
 * is never reached is not a gate that passed, so this script clicks to the
 * screens that actually have the widgets.
 *
 * App.tsx routes on React state, not on a URL fragment, so screens are reached
 * by clicking -- there is no deep link to jump to, and reloading returns to the
 * landing screen every time.
 *
 * Anything this walk cannot reach is printed as NOT COVERED. It is not marked
 * pass.
 *
 * Usage: node walk-render.mjs [url]
 */

import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const URL_UNDER_TEST = process.argv[2] ?? "http://localhost:8913/";
const WCAG = ["wcag2a", "wcag2aa", "wcag22aa"];

const rows = [];
function record(screen, name, state, detail) {
  rows.push({ screen, name, state, detail });
  console.log(`${state.padEnd(11)} [${screen}] ${name}${detail ? ` -- ${detail}` : ""}`);
}

async function inputsOn(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll("input, textarea")].map((el) => ({
      placeholder: el.getAttribute("placeholder"),
      ariaLabel: el.getAttribute("aria-label"),
      labelledBy: el.getAttribute("aria-labelledby"),
      type: el.getAttribute("type"),
    }))
  );
}

async function scrollersOn(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll("*")]
      .filter((el) => {
        const s = getComputedStyle(el);
        return (
          /auto|scroll/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 4
        );
      })
      .map((el) => ({ tag: el.tagName, tabindex: el.getAttribute("tabindex") }))
  );
}

/** Both gates plus axe, on whatever screen is currently mounted. */
async function checkScreen(page, screen) {
  const scan = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  const bad = scan.violations.filter(
    (v) => v.impact === "critical" || v.impact === "serious"
  );
  record(
    screen,
    "axe critical/serious",
    bad.length === 0 ? "PASS" : "FAIL",
    bad.length === 0
      ? "none"
      : bad.map((v) => `${v.id} x${v.nodes.length}`).join(", ")
  );
  for (const v of bad) {
    for (const n of v.nodes.slice(0, 3)) {
      console.log(`        ${v.id}: ${n.html.slice(0, 150)}`);
    }
  }

  const inputs = await inputsOn(page);
  if (inputs.length === 0) {
    record(screen, "#125 input has non-placeholder name", "NOT COVERED", "no inputs here");
  } else {
    const nameless = inputs.filter((i) => !i.ariaLabel && !i.labelledBy);
    const same = inputs.filter(
      (i) => i.ariaLabel && i.placeholder && i.ariaLabel === i.placeholder
    );
    record(
      screen,
      "#125 input has non-placeholder name",
      nameless.length === 0 && same.length === 0 ? "PASS" : "FAIL",
      `${inputs.length} inputs, ${nameless.length} nameless, ${same.length} name==placeholder` +
        (inputs[0] ? ` | first: aria-label=${JSON.stringify(inputs[0].ariaLabel)} placeholder=${JSON.stringify(inputs[0].placeholder)}` : "")
    );
  }

  const scrollers = await scrollersOn(page);
  if (scrollers.length === 0) {
    record(screen, "#122 scroll region focusable", "NOT COVERED", "no overflowing scroller here");
  } else {
    const unreachable = scrollers.filter((s) => s.tabindex === null);
    record(
      screen,
      "#122 scroll region focusable",
      unreachable.length === 0 ? "PASS" : "FAIL",
      `${scrollers.length} scrollers, ${unreachable.length} without tabindex`
    );
  }
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(URL_UNDER_TEST, { waitUntil: "networkidle" });
await checkScreen(page, "vao-cua (landing)");

// --- Screen 2: phone login. This is the one with a real text input. --------
const phone = page.getByText("Đăng nhập bằng số điện thoại", { exact: false }).first();
if (await phone.count()) {
  await phone.click();
  await page.waitForTimeout(600);
  await checkScreen(page, "dang-nhap-sdt");
} else {
  record("dang-nhap-sdt", "reachable", "NOT COVERED", "entry control not found");
}

// --- Screen 3: the roster picker behind the Google button. ----------------
await page.goto(URL_UNDER_TEST, { waitUntil: "networkidle" });
const google = page.getByText("Đăng ký với Google", { exact: false }).first();
if (await google.count()) {
  await google.click();
  await page.waitForTimeout(800);
  await checkScreen(page, "chon-nguoi (roster)");
} else {
  record("chon-nguoi", "reachable", "NOT COVERED", "entry control not found");
}

record(
  "all",
  "no uncaught page errors",
  errors.length === 0 ? "PASS" : "FAIL",
  errors.slice(0, 2).join(" | ") || "clean"
);

await browser.close();

const fails = rows.filter((r) => r.state === "FAIL");
const uncovered = rows.filter((r) => r.state === "NOT COVERED");
console.log(
  `\n${rows.filter((r) => r.state === "PASS").length} pass, ${fails.length} fail, ${uncovered.length} NOT COVERED`
);
if (uncovered.length) {
  console.log("NOT COVERED (not a pass):");
  for (const u of uncovered) console.log(`  - [${u.screen}] ${u.name}: ${u.detail}`);
}
process.exit(fails.length === 0 ? 0 : 1);
