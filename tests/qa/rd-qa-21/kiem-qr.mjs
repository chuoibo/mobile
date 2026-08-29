import { chromium } from "playwright";
const U = process.argv[2];
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH });
const p = await b.newPage({ viewport: { width: 390, height: 844 } });
await p.goto(U, { waitUntil: "networkidle" });

const truoc = await p.evaluate(() => [...document.querySelectorAll("img")].map((el) => {
  const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
  return { alt: el.getAttribute("alt"), src: (el.getAttribute("src")||"").slice(0,60),
           w: Math.round(r.width), h: Math.round(r.height),
           display: st.display, natural: el.naturalWidth + "x" + el.naturalHeight,
           anTrongDetails: !!el.closest("details:not([open])") };
}));
console.log("TRUOC khi bam:"); console.log(JSON.stringify(truoc, null, 2));

// The disclosure the keyboard walk found.
const nut = p.getByRole("button", { name: /xem cách chuyển/i });
if (await nut.count()) { await nut.first().click(); await p.waitForTimeout(400); }

const sau = await p.evaluate(() => [...document.querySelectorAll("img")].map((el) => {
  const r = el.getBoundingClientRect();
  return { alt: el.getAttribute("alt"), w: Math.round(r.width), h: Math.round(r.height),
           natural: el.naturalWidth + "x" + el.naturalHeight, complete: el.complete };
}));
console.log("\nSAU khi bam 'xem cach chuyen':"); console.log(JSON.stringify(sau, null, 2));
await p.screenshot({ path: "/tmp/qa21-qr-sau-khi-bam.png", fullPage: true });
await b.close();
