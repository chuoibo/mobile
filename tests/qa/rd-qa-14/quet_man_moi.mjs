/** Screenshot + axe sweep of the two screens #130 and #131 add.
 *
 * Every navigation goes through about:blank first: AppRoot reads the URL
 * fragment once at mount, so changing only the fragment leaves the previous
 * screen mounted and the report describes the wrong screen while exiting 0.
 */
import pw from "/home/lakiet/agent-harness/wt/qa/tests/qa/rd-qa-11/node_modules/playwright/index.js";
import axePkg from "/home/lakiet/agent-harness/wt/qa/tests/qa/rd-qa-11/node_modules/@axe-core/playwright/dist/index.js";
const { chromium } = pw;
const AxeBuilder = axePkg.default ?? axePkg;

const BASE = "http://127.0.0.1:8115";
const OUT = "/home/lakiet/agent-harness/wt/qa/tests/qa/rd-qa-14/shots";

const MAN = [
  { id: "len-plan",   frag: "#tab=len-plan&nguoi=minh", ten: "Lên plan (#130)", cho: "Chuyến" },
  { id: "ky-niem",    frag: "#vao=ky-niem&nguoi=minh",  ten: "Kỷ niệm (#131)",  cho: "Kỷ niệm" },
];

const browser = await chromium.launch();
const ket = [];

for (const m of MAN) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));
  page.on("console", (c) => { if (c.type() === "error") loi.push("console: " + c.text()); });

  await page.goto("about:blank");
  await page.goto(BASE + "/" + m.frag, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500); // let the API fetch land

  await page.screenshot({ path: `${OUT}/${m.id}.png`, fullPage: true });

  const text = await page.evaluate(() => document.body.innerText);
  // Count real, pressable controls -- not string matches. A tab label at the
  // bottom of every screen makes a substring search claim a screen works.
  const nut = await page.evaluate(() =>
    [...document.querySelectorAll('[role="button"],button,a[href]')]
      .map((e) => (e.innerText || e.getAttribute("aria-label") || "").trim())
      .filter(Boolean)
  );

  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
    .analyze();

  ket.push({ man: m.ten, id: m.id, loi, nut, axe: axe.violations, text });
  await ctx.close();
}

await browser.close();

for (const r of ket) {
  console.log("=".repeat(70));
  console.log("MÀN:", r.man);
  console.log("  lỗi JS         :", r.loi.length ? r.loi.slice(0, 4) : "không");
  console.log("  số nút bấm được:", r.nut.length);
  console.log("  nhãn nút       :", JSON.stringify(r.nut.slice(0, 14)));
  console.log("  chữ trên màn   :", JSON.stringify(r.text.slice(0, 320)));
  console.log("  axe vi phạm    :", r.axe.length);
  for (const v of r.axe) {
    console.log(`    - [${v.impact}] ${v.id}: ${v.help}  (x${v.nodes.length})`);
    console.log(`      vd: ${(v.nodes[0]?.html || "").slice(0, 150)}`);
  }
}
const tongLoi = ket.reduce((a, r) => a + r.loi.length, 0);
const tongAxe = ket.reduce((a, r) => a + r.axe.length, 0);
console.log("=".repeat(70));
console.log(`TỔNG: lỗi JS=${tongLoi}  vi phạm axe=${tongAxe}`);
