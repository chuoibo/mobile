// Recon: what does the app show, and what can be clicked, on first load?
import { chromium } from "playwright-core";
import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";

const CHROME = timTrinhDuyet();
const url = process.argv[2];

const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

const errors = [];
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text().slice(0, 200));
});
page.on("pageerror", (e) => errors.push("pageerror: " + String(e).slice(0, 200)));

await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

const dump = await page.evaluate(() => {
  const clickable = [];
  for (const el of document.querySelectorAll(
    'button,[role="button"],a,input,textarea,[tabindex]',
  )) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    clickable.push({
      tag: el.tagName,
      role: el.getAttribute("role"),
      text: (el.innerText || el.value || el.placeholder || "").trim().slice(0, 60),
      box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
    });
  }
  return { title: document.title, body: document.body.innerText.slice(0, 1500), clickable };
});

console.log("TITLE:", dump.title);
console.log("--- BODY TEXT ---\n" + dump.body);
console.log("--- CLICKABLE (" + dump.clickable.length + ") ---");
for (const c of dump.clickable) console.log(JSON.stringify(c));
console.log("--- CONSOLE ERRORS ---");
for (const e of errors) console.log(e);

await browser.close();
