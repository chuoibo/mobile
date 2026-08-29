/* ĐỐI CHỨNG NHẮM ĐÚNG HAI RULE ĐANG NÓI TỚI.
 *
 * Trồng một <img> thiếu alt chỉ chứng minh axe CÓ CHẠY. Nó không chứng minh bộ
 * đo này bắt được đúng hai lỗi nó đang gác. Nếu tôi chỉ có số 0, thì "đã sửa"
 * và "bộ đo mù với loại lỗi này" trông y hệt nhau.
 *
 * Nên ở đây tôi dựng lại ĐÚNG cái DOM trước #103, ngay trên trang đang sống:
 *   1. gỡ role="img" khỏi dải bản đồ, trả aria-label={tên} về cho 12 chấm
 *      -> phải ra aria-prohibited-attr × 12
 *   2. đưa nút [+] trở vào trong role="tablist"
 *      -> phải ra aria-required-children
 *
 * Đỏ ở đây + xanh ở `01-bon-tab-axe.mjs` = bằng chứng. Chỉ xanh ở 01 một mình
 * = một lời khai, vì nó không loại được khả năng bộ đo mù với hai rule này.
 *
 * Đột biến chỉ sống trong DOM của một tab trình duyệt. Không file nào bị sửa,
 * nên không có bản vá nào để mất — khác với `git checkout --` trên cây đang dở.
 *
 *     WEB_URL=http://127.0.0.1:8712 node 02-doi-chung-nham-rule.mjs
 */
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";

const WEB = process.env.WEB_URL;
const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];

if (!WEB) {
  console.error("Thiếu WEB_URL — xem README.md");
  process.exit(2);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
  locale: "vi-VN",
});
const p = await ctx.newPage();
await p.goto(`${WEB}/index.html#tab=kham-pha&nguoi=minh`, { waitUntil: "domcontentloaded" });
await p.waitForTimeout(3000);

async function quet(nhan) {
  const r = await new AxeBuilder({ page: p }).withTags(TAGS).analyze();
  const ids = r.violations.map((v) => `${v.id}×${v.nodes.length}`);
  console.log(`  ${nhan.padEnd(46)} ${String(r.violations.length).padStart(2)} vi phạm · ${r.passes.length} rule pass`);
  for (const v of r.violations) console.log(`      ✗ [${v.impact}] ${v.id} ×${v.nodes.length} — ${v.help}`);
  return { ids, rules: r.violations.map((v) => v.id) };
}

const loi = [];
console.log("\n===== ĐỐI CHỨNG NHẮM RULE · bản dựng hiện tại của main =====\n");
const goc = await quet("0 · nguyên trạng (đã sửa)");

// --- Đột biến 1: trả DOM dải bản đồ về trước #103 -------------------------
const m1 = await p.evaluate(() => {
  const el = [...document.querySelectorAll('[role="img"]')].find((e) =>
    /Sơ đồ vị trí/.test(e.getAttribute("aria-label") ?? ""),
  );
  if (!el) return { ok: false };
  const ten = (el.getAttribute("aria-label") ?? "").replace(/^Sơ đồ vị trí tương đối của \d+ chỗ: /, "").split(", ");
  el.removeAttribute("role");
  el.removeAttribute("aria-label");
  [...el.children].forEach((c, i) => c.setAttribute("aria-label", ten[i] ?? `chỗ ${i}`));
  return { ok: true, soCham: el.children.length };
});
console.log(`\n  [đột biến 1] gỡ role dải bản đồ, gán aria-label cho ${m1.soCham} chấm`);
const d1 = await quet("1 · DOM dải bản đồ như TRƯỚC #103");
if (!d1.rules.includes("aria-prohibited-attr")) {
  loi.push("đột biến 1 KHÔNG làm đỏ aria-prohibited-attr — bộ đo mù với chính lỗi nó đang gác");
} else {
  console.log(`      ✓ bắt đúng: ${d1.ids.filter((s) => s.startsWith("aria-prohibited")).join(", ")}`);
}

// --- Đột biến 2: đưa [+] trở vào tablist ----------------------------------
await p.reload({ waitUntil: "domcontentloaded" });
await p.waitForTimeout(2500);
const m2 = await p.evaluate(() => {
  const tl = document.querySelector('[role="tablist"]');
  const nut = [...document.querySelectorAll('[role="button"]')].find((e) =>
    /Tạo mới|Đóng menu/.test(e.getAttribute("aria-label") ?? ""),
  );
  if (!tl || !nut) return { ok: false, tl: !!tl, nut: !!nut };
  tl.appendChild(nut);
  return { ok: true, con: [...tl.children].map((c) => c.getAttribute("role")) };
});
console.log(`\n  [đột biến 2] đưa [+] vào tablist -> con = ${JSON.stringify(m2.con)}`);
const d2 = await quet("2 · [+] nằm TRONG tablist, như TRƯỚC #103");
if (!d2.rules.includes("aria-required-children")) {
  loi.push("đột biến 2 KHÔNG làm đỏ aria-required-children — bộ đo mù với chính lỗi nó đang gác");
} else {
  console.log(`      ✓ bắt đúng: aria-required-children`);
}

console.log("\n" + "=".repeat(78));
console.log(`nguyên trạng: ${goc.ids.join(", ") || "0 vi phạm"}`);
if (loi.length) {
  console.log(`\nĐỎ — bộ đo không đáng tin:`);
  for (const f of loi) console.log("  ✗ " + f);
} else {
  console.log("\nXANH — cả hai rule đều đỏ được khi lỗi quay lại, và im khi lỗi đã đi.");
}
await browser.close();
process.exit(loi.length ? 1 : 0);
