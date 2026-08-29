/* rd-qa-06 · axe trên NỬA SAU của luồng + trang khách.
 *
 * Ca đầu tiên là ĐỐI CHỨNG: trồng một <img> thiếu alt và một nút không tên vào
 * chính trang đang đo, rồi đòi axe phải báo NHIỀU HƠN. Ca đó đỏ nghĩa là axe
 * đã chết và mọi số 0 bên dưới là giả.
 */
import AxeBuilder from "@axe-core/playwright";
import { phone, typeInto, toManualForm, API, report } from "./lib.mjs";

const TAGS = ["wcag2a", "wcag2aa", "wcag22aa"];
const failures = [];
const { browser, page, context } = await phone();

async function scan(label) {
  const r = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const bad = r.violations.filter((v) => ["critical", "serious"].includes(v.impact));
  console.log(`\n${label}: ${r.violations.length} vi phạm (${bad.length} critical/serious)`);
  for (const v of bad) {
    console.log(`  ✗ [${v.impact}] ${v.id} — ${v.help} (${v.nodes.length} nút)`);
    console.log(`      ${(v.nodes[0]?.html ?? "").slice(0, 150)}`);
  }
  return { total: r.violations.length, bad };
}

await toManualForm(page);

// ---- ĐỐI CHỨNG ------------------------------------------------------------
const before = await scan("form (nguyên bản)");
await page.evaluate(() => {
  const img = document.createElement("img");
  // SVG chứ không phải base64: repo guard chặn data-uri base64, và axe
  // chỉ cần một <img> KHÔNG có alt, nội dung ảnh không liên quan.
  img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1' height='1'%3E%3C/svg%3E";
  document.body.appendChild(img);              // <img> thiếu alt
  const b = document.createElement("button");
  b.setAttribute("role", "button");
  document.body.appendChild(b);                // nút không có tên
});
const planted = await scan("form (ĐÃ TRỒNG LỖI)");
if (planted.total <= before.total) {
  failures.push(`ĐỐI CHỨNG HỎNG: trồng lỗi mà axe vẫn báo ${planted.total} ≤ ${before.total} — mọi số 0 bên dưới là giả`);
} else {
  console.log(`\n✓ đối chứng đạt: ${before.total} -> ${planted.total} sau khi trồng lỗi. axe còn sống.`);
}
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(1500);

// ---- các màn thật của nửa sau --------------------------------------------
await toManualForm(page);
const people = [];
page.on("response", (r) => { const m = r.url().match(/\/people\/([0-9a-f-]{36})$/); if (m && r.request().method()==="PUT") people.push(m[1]); });
for (const n of ["Hà", "Nam", "Linh"]) {
  await typeInto(page, page.getByPlaceholder("Hà"), n);
  await page.getByRole("button", { name: /^Thêm$/ }).click();
  await page.waitForTimeout(200);
}
await typeInto(page, page.getByPlaceholder("bữa lẩu tối thứ bảy"), "lẩu gà lá é");
await page.getByRole("radio", { name: /^Hà$/ }).first().click();
await typeInto(page, page.getByPlaceholder("480000"), "480001");
await page.waitForTimeout(300);
const s1 = await scan("1. Nhập khoản chi (form đã điền)");

await page.getByRole("button", { name: /^Chia tiền$/ }).click();
await page.waitForTimeout(3000);
const s2 = await scan("2. Đề xuất chia");

await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/ }).click();
await page.waitForTimeout(3500);
const adv = people[0];
await fetch(`${API}/people/${adv}/bank-recipient`, { method: "PUT",
  headers: { "Content-Type": "application/json", "X-Actor-ID": adv, "X-Actor-Roles": "member,advancer,recipient,batch_owner", "Idempotency-Key": `a11y-${adv}` },
  body: JSON.stringify({ bank_bin: "970418", account_number: "0000000000TEST", account_name: "NGUOI UNG TIEN" }) });
await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/ }).click();
await page.waitForTimeout(4000);
const s3 = await scan("3. Đợt thu (trước khi phát)");

let links = null;
page.on("response", async (r) => { if (/publish/.test(r.url()) && r.status() < 300) { try { links = (JSON.parse(await r.text())).guest_links; } catch {} } });
await page.getByRole("button", { name: /Phát đợt thu/ }).click();
await page.waitForTimeout(5000);
const s4 = await scan("4. Kết quả thanh toán + VietQR");

await page.getByRole("button", { name: /Chia sẻ kết quả/ }).click();
await page.waitForTimeout(2000);
const s5 = await scan("5. Chia sẻ link");

// ---- trang khách (server-rendered) ---------------------------------------
if (links) {
  const gp = await context.newPage();
  await gp.goto(API + links[0].path, { waitUntil: "domcontentloaded" });
  await gp.waitForTimeout(800);
  const rg = await new AxeBuilder({ page: gp }).withTags(TAGS).analyze();
  const badg = rg.violations.filter((v) => ["critical", "serious"].includes(v.impact));
  console.log(`\n6. Trang khách: ${rg.violations.length} vi phạm (${badg.length} critical/serious)`);
  for (const v of badg) {
    console.log(`  ✗ [${v.impact}] ${v.id} — ${v.help} (${v.nodes.length} nút)`);
    console.log(`      ${(v.nodes[0]?.html ?? "").slice(0, 150)}`);
  }
  for (const v of badg) failures.push(`trang khách: ${v.id} (${v.impact}, ${v.nodes.length} nút)`);
}

for (const [name, s] of [["nhập khoản chi", s1], ["đề xuất", s2], ["đợt thu", s3], ["kết quả TT", s4], ["chia sẻ", s5]])
  for (const v of s.bad) failures.push(`${name}: ${v.id} (${v.impact}, ${v.nodes.length} nút)`);

const n = report("05 · a11y nửa sau (WCAG 2.2 AA, critical+serious)", failures);
await browser.close();
process.exit(n === 0 ? 0 : 1);
