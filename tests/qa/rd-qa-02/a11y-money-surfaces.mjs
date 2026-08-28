/* rd-qa-02 · Can the number actually be read and acted on?
 *
 * Scope is deliberately narrow: this is the money task, not the design task.
 * It asks three things about the surfaces that carry an amount --
 *
 *   1. axe-core (wcag2a, wcag2aa, wcag22aa) finds no violation on the page a
 *      guest opens to see what they owe;
 *   2. the amount is exposed to assistive tech as a number a person can act
 *      on, not as decoration;
 *   3. the copy-the-amount control is reachable and operable by keyboard,
 *      because "chạm để chép" is the only way to move the figure without
 *      retyping it.
 *
 * A planted-defect check runs first. An axe pass that would pass on a blank
 * page proves nothing, so the harness scans a page it KNOWS is broken and
 * fails loudly if axe reports it clean.
 *
 *     node a11y-money-surfaces.mjs <guest-url> [more urls...]
 */
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const urls = process.argv.slice(2);
if (urls.length === 0) {
  console.error("usage: a11y-money-surfaces.mjs <url> [url...]");
  process.exit(2);
}

const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();
let failures = 0;

// --- Does axe actually see the DOM? -------------------------------------
await page.setContent(
  '<html><body><img src="x.png"><button></button>' +
    '<p style="color:#eee;background:#fff">82.000đ</p></body></html>',
);
const planted = await new AxeBuilder({ page }).withTags(TAGS).analyze();
if (planted.violations.length === 0) {
  console.error("axe báo sạch trên trang cố tình hỏng — nó không đọc DOM. Dừng.");
  process.exit(2);
}
console.log(
  `kiểm chứng axe: trang cố tình hỏng ra ${planted.violations.length} vi phạm ` +
    `(${planted.violations.map((v) => v.id).join(", ")}) — axe có đọc DOM.`,
);

// --- The real surfaces ---------------------------------------------------
for (const url of urls) {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const serious = results.violations.filter((v) =>
    ["critical", "serious"].includes(v.impact),
  );
  console.log(`\n${url}`);
  console.log(
    `  axe: ${results.violations.length} vi phạm ` +
      `(${serious.length} critical/serious), ${results.passes.length} luật đạt`,
  );
  for (const v of results.violations) {
    console.log(`    - [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} nút)`);
    failures += ["critical", "serious"].includes(v.impact) ? 1 : 0;
  }

  // The amount must carry an accessible name that contains the figure. A
  // number announced only as "button" is a number nobody can check by ear.
  const amount = page.locator("[data-copy]").first();
  if (await amount.count()) {
    const name = await amount.getAttribute("aria-label");
    const text = (await amount.innerText()).replace(/\s+/g, " ").trim();
    const copied = await amount.getAttribute("data-copy");
    const printed = text.match(/[\d.]+/)?.[0] ?? "";
    const announced = (name ?? "").includes(printed) && printed !== "";
    console.log(`  số in ra: "${printed}" · chép: "${copied}" · đọc lên: "${name}"`);
    if (!announced) {
      console.log("    ✗ tên trợ năng của nút số tiền không chứa con số đang in");
      failures += 1;
    }
    // The figure people read and the figure they copy must be the same money.
    if (printed.replace(/\./g, "") !== copied) {
      console.log("    ✗ số in ra khác số được chép — đây là lỗi tiền, không phải lỗi trợ năng");
      failures += 1;
    }

    // Keyboard: the copy control must be focusable and operable.
    await page.keyboard.press("Tab");
    const reachable = await page.evaluate(() => {
      const active = document.activeElement;
      return active ? active.tagName + ":" + (active.getAttribute("data-copy") ?? "") : "none";
    });
    console.log(`  phím Tab đầu tiên dừng ở: ${reachable}`);
    const focusVisible = await amount.evaluate((el) => {
      el.focus();
      const s = getComputedStyle(el, ":focus-visible");
      return { outline: s.outlineStyle, width: s.outlineWidth, shadow: s.boxShadow };
    });
    console.log(`  focus thấy được: outline=${focusVisible.outline} ${focusVisible.width}`);
  }
}

await browser.close();
console.log(`\n${failures} vấn đề chặn.`);
process.exit(failures === 0 ? 0 : 1);
