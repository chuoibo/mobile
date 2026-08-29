/**
 * rd-qa-17. F05 phía NHẬN: mở đúng cái link mà ô vuông giải mã ra, và xem
 * app làm gì với nó.
 *
 * Chuỗi dùng ở đây không phải chuỗi chép từ source — nó là chuỗi OpenCV đọc
 * được từ ảnh chụp ô vuông đã render. Đó là khác biệt giữa "mã chứa gì" và
 * "tôi tin mã chứa gì".
 */
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const BASE = process.env.QA17_BASE ?? "http://127.0.0.1:4717";
const API = process.env.QA17_API ?? "http://127.0.0.1:8717";
const WCAG = ["wcag2a", "wcag2aa", "wcag22aa"];

/** Đúng chuỗi giải mã được ở bước trước, chỉ đổi origin cho khớp máy này. */
const MA_QUET_DUOC =
  "http://127.0.0.1:4717/#ban=49871dab-3bf9-5140-acf3-6c9736b31e8f&tenban=Trang";

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();
const goi = [];
page.on("request", (r) => {
  if (r.url().startsWith(API)) goi.push({ m: r.method(), u: r.url().slice(API.length), b: r.postData() });
});
const loi = [];
page.on("console", (m) => { if (m.type() === "error") loi.push(m.text()); });

console.log("=".repeat(74));
console.log("F05 PHÍA NHẬN — mở đúng chuỗi camera đọc được ra");
console.log("=".repeat(74));
console.log(`  mã: ${MA_QUET_DUOC}`);

// Minh quét mã của Trang. `nguoi=minh` là "ai đang cầm máy".
await page.goto(`${MA_QUET_DUOC}&nguoi=minh`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

const chu = await page.evaluate(() => document.body.innerText);
console.log("");
console.log("  MÀN APP MỞ RA:");
console.log(chu.split("\n").filter(Boolean).slice(0, 14).map((l) => "    " + l).join("\n"));

const the = await page.getByText("QUÉT ĐƯỢC MÃ KẾT BẠN").count();
console.log("");
console.log(`  thẻ "QUÉT ĐƯỢC MÃ KẾT BẠN": ${the}`);
const hienId = chu.match(/Mã tài khoản ([0-9a-f]{4,})/);
console.log(`  id hiện trên thẻ: ${hienId ? hienId[1] : "không hiện"} ` +
  `(đầy đủ là 49871dab-3bf9-5140-acf3-6c9736b31e8f — cắt ngắn hay in trọn?)`);

// Trước khi bấm gì: mã này đã tự làm gì chưa?
console.log(`  request app đã gửi TRƯỚC khi bấm nút: ${goi.length}`);
for (const g of goi) console.log(`     ${g.m} ${g.u}`);

const r = await new AxeBuilder({ page }).withTags(WCAG).analyze();
console.log(`  axe màn nhận mã: ${r.violations.length} vi phạm ` +
  `${r.violations.map((v) => `${v.id}(${v.impact})`).join(", ")}`);

// Không có nhóm thì nút mời phải chịu thua chứ không được im lặng.
const nutMoi = page.getByRole("button", { name: /^Mời vào nhóm$/ });
console.log(`  nút "Mời vào nhóm": ${await nutMoi.count()}, ` +
  `disabled=${(await nutMoi.count()) ? await nutMoi.first().isDisabled() : "—"}`);

// Mở một nhóm rồi mới mời — đúng thứ tự người dùng đi.
const oTen = page.locator("input").first();
await oTen.click();
await oTen.type("Nhóm F05", { delay: 25 });
await page.getByRole("button", { name: /^Mở nhóm$/ }).first().click();
await page.waitForTimeout(2500);

const truoc = goi.length;
await nutMoi.first().click();
await page.waitForTimeout(2500);
console.log("");
console.log("  SAU KHI BẤM 'Mời vào nhóm' — app gửi đúng những gì:");
for (const g of goi.slice(truoc)) {
  console.log(`     ${g.m.padEnd(5)} ${g.u}${g.b ? "  body=" + g.b : ""}`);
}

const sau = await page.evaluate(() => document.body.innerText);
const tv = sau.match(/Thành viên[\s\S]{0,240}/);
console.log("");
console.log(`  danh sách thành viên sau khi mời:`);
console.log(`    ${JSON.stringify(tv ? tv[0].slice(0, 240) : "không thấy")}`);
console.log(`  lỗi console: ${loi.length ? loi.slice(0, 3).join(" | ") : "không có"}`);

await page.screenshot({ path: "/tmp/qa17-shots/f05-nhan-ma.png", fullPage: true });

// --- mã hỏng: app có đúc ra một người không có thật không?
console.log("");
console.log("=".repeat(74));
console.log("F05 — MÃ HỎNG / MÃ BỊA");
console.log("=".repeat(74));
for (const [ten, frag] of [
  ["id không đúng dạng", "#ban=khong-phai-uuid&tenban=Kẻ%20Bịa"],
  ["id rỗng", "#ban=&tenban=Ai%20Đó"],
  ["tên dài 300 ký tự", `#ban=be2389f9-62cb-5b28-8e5f-874768e9fb75&tenban=${"A".repeat(300)}`],
  ["thẻ script trong tên", "#ban=be2389f9-62cb-5b28-8e5f-874768e9fb75&tenban=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E"],
]) {
  const p2 = await ctx.newPage();
  const err = [];
  p2.on("pageerror", (e) => err.push(String(e).slice(0, 80)));
  p2.on("dialog", async (d) => { err.push("DIALOG: " + d.message()); await d.dismiss(); });
  await p2.goto("about:blank");
  await p2.goto(`${BASE}/${frag}&nguoi=minh`, { waitUntil: "networkidle" });
  await p2.waitForTimeout(1200);
  const t = await p2.evaluate(() => document.body.innerText);
  const nhanMa = t.includes("QUÉT ĐƯỢC MÃ KẾT BẠN");
  const tenHien = t.match(/QUÉT ĐƯỢC MÃ KẾT BẠN\s*\n?\s*([^\n]{0,60})/);
  console.log(`  ${ten.padEnd(22)} thẻ bạn hiện=${nhanMa ? "CÓ" : "không"} ` +
    `${nhanMa && tenHien ? "→ " + JSON.stringify(tenHien[1].slice(0, 40)) : ""} ` +
    `${err.length ? "LỖI: " + err.join("|") : ""}`);
  await p2.close();
}

await browser.close();
