/* rd-fe-10 · axe trên hai bước của màn ghi tài khoản nhận.
 *
 * Ca đầu tiên là ĐỐI CHỨNG, theo đúng cách rd-qa-06/05-a11y.mjs làm: trồng một
 * <img> thiếu alt và một nút không tên vào chính trang đang đo, rồi đòi axe
 * phải báo NHIỀU HƠN. Ca đó đỏ nghĩa là axe đã chết và mọi số 0 bên dưới là
 * giả — và một số 0 giả trên màn này là tệ nhất, vì đây là màn cuối cùng trước
 * khi tiền được gắn vào một tài khoản không ai kiểm chứng được.
 *
 * Đo trên URL đóng băng (`?man=tai-khoan-nhan`) chứ không đi tám bước qua máy
 * chủ: bước xem lại nằm sau bốn ô nhập và một cú bấm, và một bộ đo chỉ mở URL
 * thì không bao giờ tới được nó.
 *
 *   WEB_URL=http://127.0.0.1:PORT node 02-a11y.mjs
 */
import AxeBuilder from "@axe-core/playwright";
import { phone, report, WEB } from "../rd-qa-06/lib.mjs";

const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];
const failures = [];
const { browser, page } = await phone();

async function mo(man) {
  await page.goto(`${WEB}/index.html?man=${man}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
}

async function quet(nhan) {
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const nang = r.violations.filter((v) => ["critical", "serious"].includes(v.impact));
  console.log(`\n${nhan}: ${r.violations.length} vi phạm (${nang.length} critical/serious)`);
  for (const v of r.violations) {
    console.log(`  ✗ [${v.impact}] ${v.id} — ${v.help} (${v.nodes.length} nút)`);
    console.log(`      ${(v.nodes[0]?.html ?? "").slice(0, 160)}`);
  }
  return { tong: r.violations.length, nang };
}

// ---- ĐỐI CHỨNG ------------------------------------------------------------
await mo("tai-khoan-nhan");
const truoc = await quet("form nhập (nguyên bản)");
await page.evaluate(() => {
  const img = document.createElement("img");
  // SVG chứ không phải base64: repo guard chặn data-uri base64, và axe chỉ cần
  // một <img> KHÔNG có alt.
  img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1' height='1'%3E%3C/svg%3E";
  document.body.appendChild(img);
  const b = document.createElement("button");
  b.setAttribute("role", "button");
  document.body.appendChild(b);
});
const trong = await quet("form nhập (ĐÃ TRỒNG LỖI)");
if (trong.tong <= truoc.tong) {
  failures.push(
    `ĐỐI CHỨNG HỎNG: trồng lỗi mà axe vẫn báo ${trong.tong} ≤ ${truoc.tong} — ` +
      "mọi số 0 bên dưới là giả",
  );
} else {
  console.log(`\n✓ đối chứng đạt: ${truoc.tong} -> ${trong.tong}. axe còn sống.`);
}

// ---- hai bước thật --------------------------------------------------------
for (const [man, nhan] of [
  ["tai-khoan-nhan", "bước 1 · form nhập"],
  ["tai-khoan-nhan-duyet", "bước 2 · xem lại trước khi lưu"],
]) {
  await mo(man);
  const r = await quet(nhan);
  for (const v of r.nang) failures.push(`${nhan}: [${v.impact}] ${v.id} — ${v.help}`);
}

// 22 ngân hàng trong một radiogroup: nghe được là "một trong số này", chứ không
// phải 22 nút rời. Đây là lỗi axe vừa bắt được ở một màn khác của app (tablist
// chứa nút [+]), nên nó được kiểm đích danh chứ không tin vào tổng số 0.
await mo("tai-khoan-nhan");
const nhom = await page.locator('[role="radiogroup"]').count();
const chip = await page.locator('[role="radiogroup"] [role="radio"]').count();
const lac = await page.locator('[role="radiogroup"] > :not([role="radio"])').count();
console.log(`\nradiogroup: ${nhom} nhóm, ${chip} radio bên trong, ${lac} con KHÔNG phải radio`);
if (nhom !== 1) failures.push(`có ${nhom} radiogroup trên màn, đợi đúng 1`);
if (chip < 10) failures.push(`chỉ ${chip} radio trong nhóm — danh bạ ngân hàng không tới được người dùng`);
if (lac > 0) failures.push(`radiogroup chứa ${lac} phần tử không phải radio (aria-required-children)`);

const n = report("02 · a11y màn tài khoản nhận", failures);
await browser.close();
process.exit(n === 0 ? 0 : 1);
