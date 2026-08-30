// Walk `?man=nhan-dien` and `?man=goi-y-chia` on whichever bundle is served at
// argv[2], and answer two questions the source-reading gate cannot:
//
//   1. Does the URL actually mount the real screen, or fall through to the app
//      root? The gate in `moi-man-co-duong-do.test.mjs` reads App.tsx with a
//      regex, so it answers "is the string present", not "does it route".
//   2. At 320px, is any text wider than the box that holds it? #344 reported a
//      24px overflow here and left it in; this measures it on the shipped
//      bundle rather than trusting the report.
//
// Text is read out of the DOM, never out of the bundle: an expo web bundle
// stores Vietnamese as escapes, so grepping it for "Lẩu" always returns 0.
import { chromium } from "playwright";

const CHROME =
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";
const base = process.argv[2];
const label = process.argv[3] ?? "?";
const outDir = process.argv[4] ?? "/tmp/qa36";

// Needles that only the real screens render. `nhan-dien` lists the bill lines;
// `goi-y-chia` additionally carries the per-person matrix.
const MAN = [
  { param: "nhan-dien", kim: ["Lẩu thái hải sản", "Bia Sài Gòn", "Kem dừa"] },
  { param: "goi-y-chia", kim: ["Lẩu thái hải sản", "Bia Sài Gòn"] },
];
const KHUNG = [
  { w: 390, h: 844 },
  { w: 320, h: 844 },
];

const browser = await chromium.launch({ executablePath: CHROME });
const ket = [];

for (const { w, h } of KHUNG) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e).slice(0, 200)));

  for (const { param, kim } of MAN) {
    // Full remount between screens. Changing only the query string can leave a
    // single-page app on the previous tree, which reads as "the screen
    // rendered" when nothing was re-created.
    await page.goto("about:blank");
    await page.goto(`${base}/?man=${param}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);

    const text = await page.evaluate(() => document.body.innerText);
    const thay = kim.filter((k) => text.includes(k));

    // Overflow: an element whose own text is wider than the box drawn for it.
    // scrollWidth > clientWidth on a leaf text element is the honest form of
    // the question -- it asks the layout engine, not a screenshot.
    const tran = await page.evaluate(() => {
      const ra = [];
      for (const el of document.querySelectorAll("*")) {
        if (el.children.length > 0) continue;
        const t = (el.textContent || "").trim();
        if (!t) continue;
        const thua = el.scrollWidth - el.clientWidth;
        if (thua > 1) {
          ra.push({ chu: t.slice(0, 40), thua, rong: el.clientWidth });
        }
      }
      return ra;
    });

    await page.screenshot({ path: `${outDir}/${label}-${param}-${w}.png` });
    ket.push({ label, param, w, thay: thay.length, canCo: kim.length, tran, loi: loi.length, chu: text.length });
    console.log(
      `[${label}] ?man=${param} @${w}  kim thay ${thay.length}/${kim.length}  ` +
        `body ${text.length} ky tu  tran ${tran.length}  pageerror ${loi.length}`,
    );
    if (thay.length < kim.length) {
      console.log(`    THIEU KIM: ${kim.filter((k) => !text.includes(k)).join(" | ")}`);
      console.log(`    dau trang: ${text.slice(0, 200).replace(/\n/g, " / ")}`);
    }
    for (const o of tran) console.log(`    TRAN ${o.thua}px trong hop ${o.rong}px: "${o.chu}"`);
  }
  await page.close();
}

await browser.close();
console.log("\nJSON " + JSON.stringify(ket));
