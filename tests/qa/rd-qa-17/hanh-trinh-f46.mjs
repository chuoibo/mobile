/**
 * rd-qa-17. F46 đi bộ như người thật, trong MỘT phiên không reload.
 *
 * `VoTab` giữ tay cầm nhóm trong bộ nhớ, nên mọi bước phải nằm trong cùng một
 * lần mount. Mở lại URL giữa chừng là mất nhóm, và cái mất đó trông y hệt
 * "tính năng chưa nối" — đúng kiểu kết luận sai mà lượt quét lạnh vừa suýt đưa
 * ra.
 */
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";

const BASE = process.env.QA17_BASE ?? "http://127.0.0.1:4717";
const API = process.env.QA17_API ?? "http://127.0.0.1:8717";
const WCAG = ["wcag2a", "wcag2aa", "wcag22aa"];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await ctx.newPage();

const loi = [];
page.on("console", (m) => { if (m.type() === "error") loi.push(m.text()); });
/** Every request the app makes to the API, so a claim about what left the
 *  phone is read off the wire and not off the source. */
const goi = [];
page.on("request", (r) => {
  if (r.url().startsWith(API)) {
    goi.push({ m: r.method(), u: r.url().slice(API.length), body: r.postData() });
  }
});

console.log("=".repeat(74));
console.log("F46 — ĐI BỘ MỘT PHIÊN: tạo nhóm → Khám phá → thẻ chỗ → check-in");
console.log("=".repeat(74));

// --- 1. vào cửa, mở màn nhóm
await page.goto(`${BASE}/#vao=nhom&nguoi=minh`, { waitUntil: "networkidle" });
await page.waitForTimeout(800);
console.log(`  1. màn nhóm mở: "${(await page.locator("text=Lập hội mới").count()) > 0 ? "có" : "KHÔNG"}"`);

// --- 2. tạo nhóm thật
const oTen = page.locator("input").first();
await oTen.click();
await oTen.type("Nhóm QA17", { delay: 25 });
const nutTao = page.getByRole("button", { name: /^Mở nhóm$/ });
await nutTao.first().click();
await page.waitForTimeout(2500);
const daTao = goi.filter((g) => g.m === "POST" && g.u.startsWith("/contexts") && !g.u.includes("/"));
console.log(`  2. POST /contexts đã gửi: ${daTao.length} lần`);
const roster = await page.locator("text=/Thành viên/").count();
console.log(`     thẻ "Thành viên" hiện: ${roster}`);

// --- 3. đóng màn nhóm, sang Khám phá — bằng NÚT, không reload
const dong = page.getByRole("button", { name: /Đóng|Quay lại|×/ });
if (await dong.count()) await dong.first().click();
await page.waitForTimeout(500);
await page.waitForTimeout(1200);
const daOKhamPha = (await page.getByText("Tiệm Nướng Xóm Lào").count()) > 0;
if (!daOKhamPha) {
  const tabKhamPha = page.getByRole("button", { name: /Khám phá/ });
  console.log(`  3. phải bấm tab "Khám phá": ${await tabKhamPha.count()} nút`);
  await tabKhamPha.first().click();
  await page.waitForTimeout(2000);
} else {
  console.log(`  3. đóng màn nhóm là rơi thẳng về Khám phá — danh sách chỗ đã hiện`);
}

// --- 4. mở một thẻ địa điểm
const o = page.getByText("Tiệm Nướng Xóm Lào").first();
console.log(`  4. ô "Tiệm Nướng Xóm Lào" trên danh sách: ${await o.count()}`);
await o.click();
await page.waitForTimeout(1800);

// --- 5. thẻ check-in ở trạng thái nào?
const theCheckIn = page.getByText("Check-in ở đây");
console.log(`  5. thẻ "Check-in ở đây": ${await theCheckIn.count()}`);
const nut = page.getByRole("button", { name: /Nhóm đang ở đây|Đang ghi/ });
const co = await nut.count();
console.log(`     nút "Nhóm đang ở đây": ${co}`);
if (co === 0) {
  const chu = await page.evaluate(() => document.body.innerText);
  const doan = chu.split("Check-in ở đây")[1];
  console.log(`     thẻ đang nói: ${JSON.stringify((doan ?? "").slice(0, 220))}`);
}

// --- 6. bấm check-in
if (co > 0) {
  const hop = await nut.first().boundingBox();
  console.log(`     kích thước nút: ${Math.round(hop.width)}×${Math.round(hop.height)} px`);
  await nut.first().click();
  await page.waitForTimeout(2500);
  const post = goi.filter((g) => g.m === "POST" && g.u.includes("/checkins"));
  console.log(`  6. POST check-in đã gửi: ${post.length}`);
  for (const p of post) console.log(`     ${p.m} ${p.u}  body=${p.body}`);
  const lan = await page.getByText(/\d+ lần/).count();
  const dong0 = await page.evaluate(() => {
    const t = document.body.innerText;
    const i = t.indexOf("Check-in ở đây");
    return i === -1 ? null : t.slice(i, i + 320);
  });
  console.log(`  7. thẻ sau khi bấm:`);
  console.log(`     ${JSON.stringify(dong0)}`);
  console.log(`     đếm "N lần": ${lan}`);

  const r = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  console.log(`  8. axe trên thẻ đã check-in: ${r.violations.length} vi phạm ` +
    `${r.violations.map((v) => `${v.id}(${v.impact})`).join(", ")}`);

  // Bàn phím: nút này có tới được bằng Tab và bấm được bằng Enter không?
  await page.keyboard.press("Tab");
  const tieu = await page.evaluate(() => {
    const a = document.activeElement;
    return a ? `${a.tagName} "${(a.innerText || a.getAttribute("aria-label") || "").slice(0, 40)}"` : "không có";
  });
  console.log(`  9. Tab đầu tiên dừng ở: ${tieu}`);
}

// --- 7. toạ độ có hiện trên màn không?
const chuCuoi = await page.evaluate(() => document.body.innerText);
const toado = chuCuoi.match(/\b\d{1,3}\.\d{4,}\b/g);
console.log(` 10. chuỗi giống toạ độ trên màn: ${toado ? toado.join(", ") : "KHÔNG CÓ"}`);
console.log(` 11. lỗi console: ${loi.length ? loi.slice(0, 3).join(" | ") : "không có"}`);

console.log("");
console.log("  TOÀN BỘ REQUEST APP GỬI LÊN API TRONG PHIÊN NÀY:");
for (const g of goi) {
  console.log(`     ${g.m.padEnd(5)} ${g.u}${g.body ? "  body=" + g.body.slice(0, 120) : ""}`);
}

await page.screenshot({ path: "/tmp/qa17-shots/f46-da-checkin.png", fullPage: true });
await browser.close();
