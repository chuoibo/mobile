/* Walk the real guest page the way a guest on a phone would: smallest supported
 * screen, keyboard only, and look at what is actually painted.
 *
 * The axe pass says the markup is well-formed. It cannot say the Vietnamese
 * diacritics survive at 320px, that the QR is big enough to aim a banking app
 * at, or that a keyboard reaches the copy button. Those need eyes and Tab. */
import { chromium } from "playwright";

const URL_KHACH = process.argv[2];
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });

for (const [w, h, ten] of [[320, 640, "320-nho-nhat"], [390, 844, "390-dien-thoai"], [1440, 900, "1440-may-ban"]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.goto(URL_KHACH, { waitUntil: "networkidle" });

  const doTran = await page.evaluate(() => {
    const de = document.documentElement;
    return { tran: de.scrollWidth > de.clientWidth + 1, scrollW: de.scrollWidth, clientW: de.clientWidth };
  });

  const qr = await page.evaluate(() => {
    const el = document.querySelector("img[src*='qr'], img[alt*='QR'], svg, canvas, img");
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { tag: el.tagName, w: Math.round(r.width), h: Math.round(r.height), alt: el.getAttribute("alt") };
  });

  console.log(`\n=== ${ten} (${w}x${h})`);
  console.log(`    tran ngang: ${doTran.tran ? "CO — " + doTran.scrollW + ">" + doTran.clientW : "khong"}`);
  console.log(`    anh/QR: ${qr ? `${qr.tag} ${qr.w}x${qr.h}px alt=${JSON.stringify(qr.alt)}` : "khong tim thay"}`);

  if (w === 390) {
    const stops = [];
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press("Tab");
      const cur = await page.evaluate(() => {
        const a = document.activeElement;
        if (!a || a === document.body) return null;
        const r = a.getBoundingClientRect();
        const st = getComputedStyle(a);
        return {
          tag: a.tagName, ten: (a.innerText || a.value || a.getAttribute("aria-label") || "").trim().slice(0, 40),
          w: Math.round(r.width), h: Math.round(r.height),
          coVienFocus: st.outlineStyle !== "none" || st.boxShadow !== "none",
        };
      });
      if (!cur) break;
      const k = `${cur.tag}|${cur.ten}`;
      if (stops.some((s) => s.k === k)) break;
      stops.push({ k, ...cur });
    }
    console.log(`    diem dung ban phim: ${stops.length}`);
    for (const s of stops) {
      const nho = s.w < 24 || s.h < 24;
      console.log(`      ${s.tag} "${s.ten}" ${s.w}x${s.h}px` +
        `${nho ? "  <-- DUOI 24x24 (WCAG 2.5.8)" : ""}${s.coVienFocus ? "" : "  <-- KHONG THAY VIEN FOCUS"}`);
    }
  }

  await page.screenshot({ path: `/tmp/qa21-khach-${ten}.png`, fullPage: true });
  await page.close();
}
await browser.close();
console.log("\nanh luu o /tmp/qa21-khach-*.png (ngoai repo: guard fail closed voi binary)");
