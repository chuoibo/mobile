/** Screenshot + ARIA + axe sweep of the F17 vote surface (#135).
 *
 * Two screens, because #135 draws the ballot in two places and only one of
 * them is what `tests/binh-chon.test.mjs` exercises (neither, in fact -- that
 * file never renders anything):
 *   - the vote card inline in the thread   (Chat chip)
 *   - the Plan chip, mockup screen 3       (Plan chip)
 *
 * Every navigation goes through about:blank first: AppRoot reads the URL
 * fragment once at mount, so changing only the fragment leaves the previous
 * screen mounted and the report describes the wrong screen while exiting 0.
 *
 * The last block is a CANARY. An axe pass that finds nothing and an axe pass
 * that never ran print the same zero, so this injects two known-bad nodes into
 * the page it just called clean and requires axe to find them.
 */
import pw from "/home/lakiet/agent-harness/wt/qa/tests/qa/rd-qa-11/node_modules/playwright/index.js";
import axePkg from "/home/lakiet/agent-harness/wt/qa/tests/qa/rd-qa-11/node_modules/@axe-core/playwright/dist/index.js";
const { chromium } = pw;
const AxeBuilder = axePkg.default ?? axePkg;

const BASE = "http://127.0.0.1:8600";
const OUT = "/tmp/qa15-shots"; // outside the repo: guard fails closed on binaries

const MAN = [
  { id: "the-phieu-trong-luong", frag: "#tab=tin-nhan&nguoi=minh", ten: "Thẻ phiếu trong luồng (Chat)", chip: null },
  { id: "chip-plan", frag: "#tab=tin-nhan&nguoi=minh", ten: "Chip Plan — màn 3 mockup", chip: "Plan" },
];

const browser = await chromium.launch();
const ket = [];
let canaryPage = null;
let canaryCtx = null;

for (const m of MAN) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));
  page.on("console", (c) => { if (c.type() === "error") loi.push("console: " + c.text()); });

  await page.goto("about:blank");
  await page.goto(BASE + "/" + m.frag, { waitUntil: "networkidle" });
  await page.waitForTimeout(4000); // let the messages fetch land

  if (m.chip) {
    // Click the chip by its accessible name, not a substring of body text.
    const nut = page.getByText(m.chip, { exact: true }).first();
    await nut.click();
    await page.waitForTimeout(1500);
  }

  await page.screenshot({ path: `${OUT}/${m.id}.png`, fullPage: true });

  const text = await page.evaluate(() => document.body.innerText);
  const aria = await page.evaluate(() => ({
    radio: document.querySelectorAll('[role="radio"]').length,
    checked: document.querySelectorAll('[role="radio"][aria-checked="true"]').length,
    ariaCheckedAny: document.querySelectorAll('[aria-checked]').length,
    radiogroup: document.querySelectorAll('[role="radiogroup"]').length,
  }));
  const nut = await page.evaluate(() =>
    [...document.querySelectorAll('[role="button"],button,a[href],[role="radio"]')]
      .map((e) => (e.innerText || e.getAttribute("aria-label") || "").trim())
      .filter(Boolean)
  );

  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
    .analyze();

  ket.push({ man: m.ten, loi, nut, aria, axe: axe.violations, text });

  if (m.chip) { canaryPage = page; canaryCtx = ctx; } else { await ctx.close(); }
}

for (const r of ket) {
  console.log("=".repeat(70));
  console.log("MÀN:", r.man);
  console.log("  lỗi JS            :", r.loi.length ? r.loi.slice(0, 3) : "không");
  console.log("  role=radio        :", r.aria.radio, " aria-checked=true:", r.aria.checked,
              " [aria-checked] bất kỳ:", r.aria.ariaCheckedAny, " radiogroup:", r.aria.radiogroup);
  console.log("  số control bấm được:", r.nut.length);
  console.log("  nhãn              :", JSON.stringify(r.nut.slice(0, 12)));
  console.log("  chữ trên màn      :", JSON.stringify(r.text.slice(0, 300)));
  console.log("  axe vi phạm       :", r.axe.length);
  for (const v of r.axe) {
    console.log(`    - [${v.impact}] ${v.id}: ${v.help}  (x${v.nodes.length})`);
    console.log(`      vd: ${(v.nodes[0]?.html || "").slice(0, 140)}`);
  }
}

// ---- CANARY: prove the scanner is alive on the very page it just called clean
console.log("=".repeat(70));
await canaryPage.evaluate(() => {
  // A real served file, not an inline data URI -- the repo guard fails closed
  // on base64 blobs and it is right to, so the canary uses a plain path.
  const img = document.createElement("img");
  img.src = "/favicon.ico";
  document.body.appendChild(img); // no alt
  const i = document.createElement("input");
  i.type = "text";
  document.body.appendChild(i); // no label
});
const canary = await new AxeBuilder({ page: canaryPage })
  .withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
console.log("CANARY (cấy 2 lỗi vào đúng trang vừa quét sạch):", canary.violations.length, "vi phạm");
for (const v of canary.violations) console.log(`    - [${v.impact}] ${v.id}`);
console.log(canary.violations.length >= 2
  ? "=> máy quét SỐNG. Số 0 ở trên là 'sạch' thật."
  : "=> MÁY QUÉT CHẾT. Mọi số 0 ở trên vô nghĩa.");

await canaryCtx.close();
await browser.close();
