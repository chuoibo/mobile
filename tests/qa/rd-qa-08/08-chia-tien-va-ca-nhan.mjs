/** rd-qa-08 — chặng cuối: bấm "Chia tiền" thật, rồi xem sổ có đổi không.
 *
 *  Bộ 07 dừng ngay TRƯỚC nút cuối. Sau khi thêm người, màn chia dẫn sang form
 *  "Khoản chi mới" (tổng 1.370.000đ, chọn ai trả trước) và nút đi tiếp tên là
 *  "Chia tiền" — không nằm trong danh sách từ khoá bộ 07 dò. Nên hai phán
 *  quyết CUT cuối của nó (Σ tiền, VietQR) là phán quyết về một nút chưa bấm,
 *  không phải về sản phẩm. Bộ này bấm nốt.
 *
 *  Ba luật tiền được đọc trên con số MÀN HÌNH HIỆN, không tự chia lại.
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const WEB = process.env.MOBILE_WEB ?? "http://127.0.0.1:8692";
const BILL = process.env.MOBILE_BILL ?? "/tmp/bill-qa08.jpg";
const SHOTS = process.env.MOBILE_SHOTS ?? "/tmp/rd-qa-08";
const PHONE = { width: 390, height: 844 };
const NGUOI = ["Minh", "Trang", "Hải"];
const TONG = 1370000;

const legs = [];
function ghi(id, ten, ket, chiTiet) {
  legs.push({ id, ten, ket, chiTiet });
  console.log(`[${ket.padEnd(6)}] ${id}  ${ten}\n         ${chiTiet}`);
}
const man = (page) => page.evaluate(() => {
  const a = document.body.innerText || "";
  const b = document.getElementById("root")?.textContent || document.body.textContent || "";
  return (a.trim().length > b.trim().length ? a : b).replace(/\s+/g, " ").trim();
});
async function thu(fn) { try { await fn(); return true; } catch { return false; } }
async function chup(page, t) { mkdirSync(SHOTS, { recursive: true }); await page.screenshot({ path: `${SHOTS}/${t}.png`, fullPage: true }); }
async function nutCua(page) {
  return await page.getByRole("button").evaluateAll((els) =>
    els.filter((e) => e.offsetWidth || e.offsetHeight).map((e) => ({
      ten: (e.getAttribute("aria-label") || e.innerText || e.textContent || "").replace(/\s+/g, " ").trim(),
      tat: e.getAttribute("aria-disabled") === "true" || e.disabled === true,
    })).filter((n) => n.ten));
}
const soTien = (s) => [...s.matchAll(/(\d[\d.]*)\s*đ/g)].map((m) => Number(m[1].replace(/\./g, "")));

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: PHONE, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.setDefaultTimeout(8000);
  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));

  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.getByText(/Google/i).first().click();
  await page.getByRole("button", { name: /Vào app với tư cách Minh/i }).first().click();
  await page.waitForTimeout(800);

  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(2500);
  const tienTruoc = soTien(await man(page));
  console.log("CÁ NHÂN TRƯỚC — tiền trên màn:", JSON.stringify(tienTruoc));

  await thu(() => page.getByRole("button", { name: "Tạo mới" }).click());
  await thu(() => page.getByRole("button", { name: /^Tạo khoản chi/ }).click());
  await page.waitForTimeout(500);
  await thu(async () => {
    const ch = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Chọn ảnh bill" }).first().click();
    await (await ch).setFiles(BILL);
    await page.getByText(/Đã nhận diện \d+ món/i).waitFor({ timeout: 120000 });
  });
  await thu(() => page.getByRole("button", { name: "Tiếp tục" }).first().click());
  await page.waitForTimeout(1600);

  for (const ten of NGUOI) {
    await thu(async () => {
      if (!(await page.locator("input").count())) {
        await page.getByRole("button", { name: /^Thêm$/ }).first().click();
        await page.waitForTimeout(400);
      }
      await page.locator("input").first().click();
      await page.keyboard.type(ten, { delay: 25 });
      const gui = page.getByRole("button", { name: /^Thêm$/ });
      await gui.nth((await gui.count()) - 1).click();
      await page.waitForTimeout(800);
    });
  }
  await thu(() => page.getByRole("button", { name: "Xem kết quả", exact: true }).first().click());
  await page.waitForTimeout(2500);
  await chup(page, "N1-form-khoan-chi");

  // ---- chọn ai trả trước, rồi bấm "Chia tiền"
  await thu(() => page.getByRole("button", { name: /^Minh$/ }).last().click());
  await page.waitForTimeout(600);
  const nutForm = await nutCua(page);
  const chiaTien = nutForm.find((n) => /^Chia tiền$/i.test(n.ten));
  console.log('\nnút "Chia tiền" bị tắt:', chiaTien?.tat);

  let sChia = "";
  await thu(async () => {
    await page.getByRole("button", { name: "Chia tiền", exact: true }).first().click();
    await page.waitForTimeout(4000);
    sChia = await man(page);
  });
  await chup(page, "N2-sau-chia-tien");
  const nutChia = await nutCua(page);
  console.log("\nnút sau CHIA TIỀN:", JSON.stringify(nutChia.map((n) => n.ten)));
  console.log("màn sau CHIA TIỀN:", sChia.slice(0, 600));
  const daChia = !/Khoản chi mới/i.test(sChia) || /mỗi người|phần|kết quả|đợt thu/i.test(sChia);
  ghi("L11", "bấm Chia tiền → kết quả chia", daChia ? "DI_HET" : "CUT",
    daChia ? `"${sChia.slice(0, 240)}"` : `bấm "Chia tiền" nhưng vẫn ở form (nút bị tắt=${chiaTien?.tat})`);

  const tien = soTien(sChia);
  const phan = tien.filter((v) => v > 0 && v < TONG);
  const sum = phan.reduce((a, b) => a + b, 0);
  const nguyen = tien.every(Number.isInteger);
  console.log(`\nBẤT BIẾN TIỀN — tổng=${TONG} · phần=[${phan.join(", ")}] · Σ=${sum} · nguyên=${nguyen}`);
  ghi("M1", "Σ phân bổ = tổng khoản chi (con số trên màn)",
    sum === TONG && nguyen ? "DI_HET" : "CUT",
    `Σ=${sum} vs tổng=${TONG} (lệch ${sum - TONG}) · nguyên đồng=${nguyen} · phần=[${phan.join(", ")}]`);

  // ---- VietQR
  let sQR = "";
  let toiQR = /VIETQR|NAPAS|chuyển khoản/i.test(sChia);
  if (!toiQR) {
    for (const n of nutChia.filter((x) => !x.tat && !/Đóng|Quay|Làm lại|Bỏ/i.test(x.ten))) {
      await thu(async () => {
        await page.getByRole("button", { name: n.ten, exact: true }).first().click();
        await page.waitForTimeout(3000);
      });
      sQR = await man(page);
      toiQR = /VIETQR|NAPAS|chuyển khoản/i.test(sQR);
      console.log(`  bấm "${n.ten}" -> tới VietQR=${toiQR} · "${sQR.slice(0, 140)}"`);
      if (toiQR) break;
    }
  }
  await chup(page, "N3-vietqr");
  ghi("L12", "kết quả chia → VietQR / đợt thu", toiQR ? "DI_HET" : "CUT",
    toiQR ? `"${sQR.slice(0, 220)}"` : `không nút nào dẫn tới VietQR. Nút: ${JSON.stringify(nutChia.map((n) => n.ten))}`);

  // ---- Cá nhân SAU
  await thu(() => page.getByRole("button", { name: /Đóng khoản chi/i }).first().click());
  await page.waitForTimeout(1200);
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(3000);
  const sau = await man(page);
  const tienSau = soTien(sau);
  await chup(page, "N4-ca-nhan-sau");
  console.log("\nCÁ NHÂN SAU:", sau.slice(0, 300));
  const laCaNhan = /Tổng quan tài chính/i.test(sau);
  const doi = laCaNhan && JSON.stringify(tienSau) !== JSON.stringify(tienTruoc);
  ghi("L13", "Cá nhân thấy tài chính cập nhật",
    !laCaNhan ? "CUT" : doi ? "DI_HET" : "CUT",
    !laCaNhan ? "không quay lại được màn Cá nhân"
      : doi ? `số ĐỔI: [${tienTruoc}] -> [${tienSau}]`
      : `số KHÔNG đổi: [${tienSau}] — khoản chi vừa chia không vào sổ của người này`);

  writeFileSync(`${SHOTS}/chia-tien-ca-nhan.json`, JSON.stringify(
    { legs, tienTruoc, tienSau, nutChia, batBien: { TONG, phan, sum, nguyen }, manChia: sChia, manCaNhan: sau, loi }, null, 2));
  console.log("\n=== TỔNG ===");
  for (const k of ["DI_HET", "VO", "CUT"]) console.log(`${k}: ${legs.filter((l) => l.ket === k).length}`);
  console.log("lỗi trang:", loi.length ? [...new Set(loi)].slice(0, 5) : "(không)");
} finally {
  await browser.close();
}
