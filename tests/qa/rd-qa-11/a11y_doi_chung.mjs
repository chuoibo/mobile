// Đối chứng cho a11y_vao_cua.mjs. Một số 0 chỉ đáng tin khi hai câu hỏi này
// đã có đáp án, và cả hai đã từng làm hỏng một lượt quét thật trong repo này:
//
//   1. axe có THẬT SỰ chạy không? Thiếu trình duyệt, sai selector, hay quét
//      nhầm một trang trắng đều cho [] + exit 0, trông y hệt "sạch".
//   2. Mỗi nhãn có đúng là màn đã render không? `lien-ket.ts:100` viết
//      `boQuaMoDau: ... || vao === "nhom"` -- tức `#vao=dang-ky` KHÔNG bỏ qua
//      màn mở đầu. Một lượt quét đặt tên "dang-ky" có thể đang chụp mở đầu.
//
// Usage: MOBILE_WEB=http://localhost:8911 node a11y_doi_chung.mjs

import { chromium } from "playwright";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const AXE_SOURCE = readFileSync(require.resolve("axe-core"), "utf8");
const WEB = process.env.MOBILE_WEB || "http://localhost:8911";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function settle(page) {
  await page.waitForLoadState("domcontentloaded");
  await sleep(1500);
}

async function run(page) {
  await page.evaluate(AXE_SOURCE);
  return page.evaluate(
    async () =>
      await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag22aa"] },
        resultTypes: ["violations"],
      })
  );
}

async function open(page, fragment) {
  await page.goto("about:blank");
  await page.goto(`${WEB}/${fragment}`);
  await settle(page);
}

/** A short fingerprint of what is actually on screen. */
async function fingerprint(page) {
  return page.evaluate(() => {
    const text = (document.body.textContent || "").replace(/\s+/g, " ").trim();
    const names = [];
    for (const n of document.querySelectorAll('[role="button"], button, input')) {
      const r = n.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const nm = (n.getAttribute("aria-label") || n.textContent || n.getAttribute("placeholder") || "").trim();
      if (nm) names.push(nm.slice(0, 34));
    }
    return { head: text.slice(0, 150), controls: names.slice(0, 8) };
  });
}

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setViewportSize({ width: 390, height: 844 });

console.log("=== 1. axe co that su chay khong? (cay dot bien) ===");
await open(page, "");
const before = await run(page);
console.log(`  truoc khi cay: ${before.violations.length} vi pham`);

// Plant two unambiguous WCAG failures into the live DOM and rescan.
await page.evaluate(() => {
  const img = document.createElement("img");
  // No alt attribute -> WCAG 1.1.1. The rule inspects the attribute, not the
  // bytes, so a path that 404s is enough and keeps a base64 blob out of the repo.
  img.src = "/favicon.ico";
  document.body.appendChild(img);
  const btn = document.createElement("button");
  btn.style.cssText = "color:#eee;background:#fff"; // ~1.1:1 -> 1.4.3
  btn.textContent = "nut tuong phan rat thap";
  document.body.appendChild(btn);
});
const after = await run(page);
const ids = after.violations.map((v) => v.id);
console.log(`  sau khi cay:   ${after.violations.length} vi pham -> ${ids.join(", ") || "(khong co)"}`);
const detected = after.violations.length > before.violations.length;
console.log(`  => axe ${detected ? "CO chay va CO bat duoc loi" : "KHONG bat duoc gi -- so 0 la RONG"}`);

console.log("\n=== 2. moi nhan co dung man da render khong? ===");
const seen = {};
for (const frag of ["", "#vao=dang-ky", "#vao=nhom", "#tab=len-plan", "#tab=ca-nhan"]) {
  await open(page, frag);
  const fp = await fingerprint(page);
  seen[frag || "(khong co fragment)"] = fp;
  console.log(`\n  [${frag || "(trong)"}]`);
  console.log(`     chu: ${fp.head.slice(0, 110)}`);
  console.log(`     nut: ${fp.controls.join(" | ") || "(khong co nut nao)"}`);
}

const base = seen["(khong co fragment)"].head;
console.log("\n  --- man nao TRUNG voi man mo dau? ---");
for (const [k, v] of Object.entries(seen)) {
  if (k === "(khong co fragment)") continue;
  const same = v.head.slice(0, 100) === base.slice(0, 100);
  console.log(`     ${k.padEnd(22)} ${same ? "TRUNG mo dau -> nhan SAI" : "khac -> nhan dung"}`);
}

await browser.close();
