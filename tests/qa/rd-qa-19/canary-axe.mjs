/** Canary for the axe pass: the same scanner, same page, one planted defect.
 *  A 0-violation report on the real screen is only meaningful if this goes red. */
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";
const WEB = process.env.QA19_WEB ?? "http://127.0.0.1:8548";
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await p.goto(`${WEB}/#tab=kham-pha`, { waitUntil: "networkidle" });

const clean = await new AxeBuilder({ page: p }).withTags(["wcag2a","wcag2aa","wcag22aa"]).analyze();
console.log(`SẠCH  (màn thật, chưa động vào): ${clean.violations.length} violation`);

// Plant three defects axe is known to catch, into the live DOM.
await p.evaluate(() => {
  const d = document.createElement("div");
  d.innerHTML =
    '<img src="x.png">' +                                             // 1.1.1 no alt
    '<input type="text">' +                                           // 3.3.2 no label
    '<p style="color:#bbb;background:#fff;font-size:12px">mờ quá</p>'; // 1.4.3 contrast
  document.body.appendChild(d);
});
const bad = await new AxeBuilder({ page: p }).withTags(["wcag2a","wcag2aa","wcag22aa"]).analyze();
console.log(`XẤU   (cắm 3 lỗi vào chính màn đó): ${bad.violations.length} violation`);
for (const v of bad.violations) console.log(`   ${v.impact} · ${v.id}`);
console.log(bad.violations.length > 0 ? "\n=> máy quét CÓ chạy: số 0 ở trên có nghĩa" : "\n=> MÁY QUÉT CHẾT: số 0 ở trên vô giá trị");
await b.close();
