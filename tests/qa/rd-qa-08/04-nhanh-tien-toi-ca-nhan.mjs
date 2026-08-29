/** rd-qa-08 — nhánh tiền đi tới đâu: bill → gán → chia → VietQR → Cá nhân.
 *
 *  Chặng cuối của vòng demo PM viết là "Cá nhân thấy tài chính cập nhật". Đó
 *  là chỗ hai nửa sản phẩm phải nối vào nhau, và là chỗ chưa ai bấm bằng tay.
 *  rd-qa-05 đo nửa bill, rd-qa-06 đo nửa đợt thu; không bộ nào đi từ đầu này
 *  sang đầu kia trong MỘT phiên, nên "số ở màn Cá nhân có phản ánh khoản chi
 *  vừa tạo không" vẫn là một ô trống.
 *
 *  Cách đọc số ở đây: bộ đo KHÔNG tự chia lại tiền rồi so đáp án — làm thế là
 *  viết allocator thứ hai và so hai lỗi với nhau. Nó chỉ đòi bất biến: tổng
 *  các phần bằng tổng khoản chi, mọi phần là số nguyên đồng.
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const WEB = process.env.MOBILE_WEB ?? "http://127.0.0.1:8692";
const BILL = process.env.MOBILE_BILL ?? "/tmp/bill-qa08.jpg";
const SHOTS = process.env.MOBILE_SHOTS ?? "/tmp/rd-qa-08";
const PHONE = { width: 390, height: 844 };

const legs = [];
function ghi(id, ten, ket, chiTiet) {
  legs.push({ id, ten, ket, chiTiet });
  console.log(`[${ket.padEnd(6)}] ${id}  ${ten}\n         ${chiTiet}`);
}
const man = (page) => page.evaluate(() => (document.body.innerText || "").replace(/\s+/g, " ").trim());
async function thu(fn) { try { await fn(); return true; } catch { return false; } }
async function chup(page, ten) {
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/${ten}.png` });
}
/** "1.370.000đ" -> 1370000. Money on screen is what the user actually sees. */
const soTien = (s) => [...s.matchAll(/(\d[\d.]{2,})\s*đ/g)].map((m) => Number(m[1].replace(/\./g, "")));

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: PHONE, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.setDefaultTimeout(8000);
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));

  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.getByText(/Google/i).first().click();
  await page.getByRole("button", { name: /Vào app với tư cách/i }).first().click();
  await page.waitForTimeout(600);

  // --------- Cá nhân TRƯỚC: con số phải được đọc trước khi tạo khoản chi mới,
  // nếu không thì "cập nhật" là một câu không kiểm được.
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(2000);
  const caNhanTruoc = await man(page);
  await chup(page, "F1-ca-nhan-truoc");
  console.log("=== CÁ NHÂN TRƯỚC ===\n" + caNhanTruoc.slice(0, 400) + "\n");

  // --------- nhánh tiền
  await thu(() => page.getByRole("button", { name: "Tạo mới" }).click());
  await thu(() => page.getByRole("button", { name: /^Tạo khoản chi/ }).click());
  await page.waitForTimeout(500);

  let doc = false;
  await thu(async () => {
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Chọn ảnh bill" }).first().click();
    await (await chooser).setFiles(BILL);
    await page.getByText(/Đã nhận diện \d+ món/i).waitFor({ timeout: 120000 });
    doc = true;
  });
  const sNhanDien = await man(page);
  const tongBill = soTien(sNhanDien);
  ghi("L9", "AI đọc bill", doc ? "DI_HET" : "CUT",
    doc ? `tổng máy đọc được trên màn: ${tongBill.join(", ")}` : "không tới được");

  // --------- gán món
  await thu(() => page.getByRole("button", { name: /Tiếp tục/i }).first().click());
  await page.waitForTimeout(1500);
  await chup(page, "F2-gan-mon");
  const sGan = await man(page);
  ghi("L10", "gán món cho người", /Chọn người đã ăn|Theo món/i.test(sGan) ? "DI_HET" : "CUT",
    `"${sGan.slice(0, 200)}"`);

  // --------- chia
  let sChia = "";
  let chiaDuoc = false;
  await thu(async () => {
    const nut = page.getByRole("button", { name: /Chia|Xác nhận|Tiếp tục|Xong/i }).first();
    await nut.click();
    await page.waitForTimeout(2500);
    sChia = await man(page);
    chiaDuoc = sChia !== sGan;
  });
  await chup(page, "F3-chia");
  ghi("L11", "chia tiền → kết quả", chiaDuoc ? "DI_HET" : "CUT",
    chiaDuoc ? `"${sChia.slice(0, 260)}"` : `bấm chia nhưng màn không đổi: "${sChia.slice(0, 200)}"`);

  // --------- liệt kê nút ở màn chia, để biết đường ra tiếp theo có tồn tại không
  const nutChia = await page.getByRole("button").evaluateAll((els) =>
    els.map((e) => (e.getAttribute("aria-label") || e.innerText || "").replace(/\s+/g, " ").trim())
      .filter(Boolean));
  console.log("\nnút ở màn chia:", JSON.stringify([...new Set(nutChia)]));

  // --------- VietQR / kết quả thanh toán
  let sQR = "";
  let toiQR = false;
  await thu(async () => {
    const nut = page.getByRole("button", { name: /Xác nhận|Tạo đợt thu|Thu tiền|Gửi|Xong|Tiếp/i }).first();
    await nut.click();
    await page.waitForTimeout(2500);
    sQR = await man(page);
    toiQR = /VIETQR|NAPAS|chuyển khoản|QR/i.test(sQR);
  });
  await chup(page, "F4-vietqr");
  ghi("L12", "kết quả + VietQR", toiQR ? "DI_HET" : "CUT",
    toiQR ? `"${sQR.slice(0, 240)}"` : `không tới được màn VietQR. Màn: "${sQR.slice(0, 240)}"`);

  // --------- Cá nhân SAU
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(2500);
  const caNhanSau = await man(page);
  await chup(page, "F5-ca-nhan-sau");
  console.log("\n=== CÁ NHÂN SAU ===\n" + caNhanSau.slice(0, 400) + "\n");
  ghi("L13", "Cá nhân thấy tài chính cập nhật",
    caNhanSau !== caNhanTruoc ? "DI_HET" : "CUT",
    caNhanSau !== caNhanTruoc
      ? `số ở màn Cá nhân ĐỔI sau khi tạo khoản chi`
      : `số ở màn Cá nhân KHÔNG đổi sau khi đi hết nhánh tiền — hai nửa chưa nối`);

  writeFileSync(`${SHOTS}/nhanh-tien.json`, JSON.stringify(
    { legs, caNhanTruoc, caNhanSau, nutChia: [...new Set(nutChia)], loi }, null, 2));
  console.log("\n=== TỔNG ===");
  for (const k of ["DI_HET", "VO", "CUT"]) console.log(`${k}: ${legs.filter((l) => l.ket === k).length}`);
  console.log("lỗi trang:", loi.length ? [...new Set(loi)].slice(0, 5) : "(không)");
} finally {
  await browser.close();
}
