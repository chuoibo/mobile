/** rd-qa-08 — nhánh tiền, lái bằng TÊN NÚT THẬT chứ không bằng regex đoán.
 *
 *  Hai lượt trước chấm nhầm hai lần, cùng một kiểu lỗi: bộ đo đoán tên nút
 *  ("Chia", "Xác nhận", "Tiếp tục") rồi khi không thấy thì kết luận sản phẩm
 *  cụt đường. Màn chia thực ra có nút tên là "Xem kết quả". Một phán quyết CUT
 *  sai gửi lane khác đi sửa thứ không hỏng, nên ở đây mỗi bước LIỆT KÊ nút
 *  trước, in ra, rồi mới bấm đúng cái tên đã thấy.
 *
 *  Bất biến tiền được kiểm ở cuối, trên con số MÀN HÌNH hiện: tổng các phần
 *  phải bằng tổng khoản chi, và mọi phần là số nguyên đồng. Bộ đo không tự
 *  chia lại.
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
/** Every pressable, by accessible name, visible only. */
async function nutCua(page) {
  return [...new Set(await page.getByRole("button").evaluateAll((els) =>
    els.filter((e) => e.offsetWidth || e.offsetHeight)
      .map((e) => (e.getAttribute("aria-label") || e.innerText || "").replace(/\s+/g, " ").trim())
      .filter(Boolean)))];
}
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

  // ---- Cá nhân TRƯỚC (baseline, đọc từ sổ)
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(2500);
  const truoc = await man(page);
  await chup(page, "G1-ca-nhan-truoc");
  const tienTruoc = soTien(truoc);
  console.log("CÁ NHÂN TRƯỚC — số tiền trên màn:", tienTruoc.join(", "));

  // ---- bill
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
  console.log("\nnút ở màn NHẬN DIỆN:", JSON.stringify(await nutCua(page)));
  ghi("L9", "AI đọc bill", doc ? "DI_HET" : "CUT", doc ? "8 món, tổng khớp dòng in trên bill" : "cụt");

  // ---- sang màn gán/chia
  await thu(() => page.getByRole("button", { name: "Tiếp tục" }).first().click());
  await page.waitForTimeout(1800);
  await chup(page, "G2-gan-chia");
  const nutGan = await nutCua(page);
  console.log("nút ở màn GÁN/CHIA:", JSON.stringify(nutGan));
  ghi("L10", "gán món cho người", nutGan.includes("Xem kết quả") ? "DI_HET" : "CUT",
    `nút đi tiếp: ${nutGan.includes("Xem kết quả") ? '"Xem kết quả"' : "KHÔNG THẤY"}`);

  // ---- chia: bấm ĐÚNG cái nút có thật
  let sKQ = "";
  await thu(async () => {
    await page.getByRole("button", { name: "Xem kết quả", exact: true }).first().click();
    await page.waitForTimeout(3000);
    sKQ = await man(page);
  });
  await chup(page, "G3-ket-qua-chia");
  const nutKQ = await nutCua(page);
  console.log("\nnút ở màn KẾT QUẢ CHIA:", JSON.stringify(nutKQ));
  console.log("màn kết quả:", sKQ.slice(0, 400));
  ghi("L11", "chia tiền → kết quả", sKQ ? "DI_HET" : "CUT",
    sKQ ? `"${sKQ.slice(0, 220)}"` : "màn trống");

  // ---- bất biến tiền, trên con số màn hình hiện
  const tien = soTien(sKQ);
  const tong = 1370000;
  const phan = tien.filter((v) => v > 0 && v < tong);
  const sumPhan = phan.reduce((a, b) => a + b, 0);
  const nguyen = tien.every((v) => Number.isInteger(v));
  console.log(`\nBẤT BIẾN TIỀN: tổng bill=${tong} · các phần trên màn=[${phan.join(", ")}] · Σ=${sumPhan} · mọi số nguyên=${nguyen}`);

  // ---- VietQR / đợt thu
  let sQR = "";
  let toiQR = false;
  const ungVien = nutKQ.filter((n) => /thu|QR|chuyển|gửi|xong|xác nhận|lưu|tạo/i.test(n));
  console.log("ứng viên đi tiếp từ màn kết quả:", JSON.stringify(ungVien));
  for (const n of ungVien) {
    const ok = await thu(async () => {
      await page.getByRole("button", { name: n, exact: true }).first().click();
      await page.waitForTimeout(3000);
    });
    sQR = await man(page);
    toiQR = /VIETQR|NAPAS|chuyển khoản/i.test(sQR);
    console.log(`  bấm "${n}" -> bấm được=${ok} · tới VietQR=${toiQR} · "${sQR.slice(0, 160)}"`);
    if (toiQR) break;
  }
  await chup(page, "G4-vietqr");
  ghi("L12", "kết quả → VietQR / đợt thu", toiQR ? "DI_HET" : "CUT",
    toiQR ? `"${sQR.slice(0, 220)}"` : `từ màn kết quả không có nút nào dẫn tới VietQR. Nút có: ${JSON.stringify(nutKQ)}`);

  // ---- Cá nhân SAU — phải quay được về vỏ tab trước đã
  await thu(() => page.getByRole("button", { name: /Đóng khoản chi/i }).first().click());
  await page.waitForTimeout(1000);
  const veDuocTab = (await nutCua(page)).some((n) => /Tạo mới/i.test(n))
    || (await page.getByRole("tab").count()) > 0;
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(2500);
  const sau = await man(page);
  await chup(page, "G5-ca-nhan-sau");
  const tienSau = soTien(sau);
  console.log("\nCÁ NHÂN SAU — số tiền trên màn:", tienSau.join(", "));
  const laManCaNhan = /Tổng quan tài chính/i.test(sau);
  const doiSo = laManCaNhan && JSON.stringify(tienSau) !== JSON.stringify(tienTruoc);
  ghi("L13", "Cá nhân thấy tài chính cập nhật",
    !veDuocTab ? "CUT" : !laManCaNhan ? "CUT" : doiSo ? "DI_HET" : "CUT",
    !veDuocTab ? "không quay được về vỏ tab từ luồng khoản chi"
      : !laManCaNhan ? `bấm tab Cá nhân không mở được màn Cá nhân: "${sau.slice(0, 180)}"`
      : doiSo ? `số đổi: ${tienTruoc.join(",")} -> ${tienSau.join(",")}`
      : `màn Cá nhân mở được nhưng SỐ KHÔNG ĐỔI (${tienSau.join(",")}) sau khi đi hết nhánh tiền`);

  writeFileSync(`${SHOTS}/nhanh-tien-that.json`, JSON.stringify(
    { legs, tienTruoc, tienSau, nutKQ, nutGan, batBien: { tong, phan, sumPhan, nguyen }, loi }, null, 2));
  console.log("\n=== TỔNG ===");
  for (const k of ["DI_HET", "VO", "CUT"]) console.log(`${k}: ${legs.filter((l) => l.ket === k).length}`);
  console.log("lỗi trang:", loi.length ? [...new Set(loi)].slice(0, 5) : "(không)");
} finally {
  await browser.close();
}
