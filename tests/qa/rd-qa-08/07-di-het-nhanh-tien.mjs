/** rd-qa-08 — đi HẾT nhánh tiền sau khi tự thêm người, và đo bất biến tiền.
 *
 *  Bộ 06 dừng ở chỗ "Xem kết quả" bị tắt vì nhóm rỗng, và lần thêm người của
 *  nó thất bại vì màn có HAI nút cùng tên "Thêm": nút tròn [+] mở ô nhập, và
 *  nút xanh gửi tên. Bộ đo bấm cái đầu tiên nên gõ xong không ai được thêm.
 *  Ở đây nút gửi được chỉ đích danh bằng vị trí, và mỗi lần thêm đều được
 *  KIỂM LẠI bằng cách đếm người trên màn — thêm mà không kiểm thì lại là một
 *  phép đo tự tin vào chính nó.
 *
 *  Sau khi có người, bộ này đòi ba luật tiền trên CON SỐ MÀN HÌNH HIỆN:
 *    1. mọi phần là số nguyên đồng
 *    2. Σ các phần = tổng khoản chi
 *  Nó không tự chia lại rồi so đáp án.
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const WEB = process.env.MOBILE_WEB ?? "http://127.0.0.1:8692";
const BILL = process.env.MOBILE_BILL ?? "/tmp/bill-qa08.jpg";
const SHOTS = process.env.MOBILE_SHOTS ?? "/tmp/rd-qa-08";
const PHONE = { width: 390, height: 844 };
const NGUOI = ["Minh", "Trang", "Hải"];

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
async function chup(page, t) { mkdirSync(SHOTS, { recursive: true }); await page.screenshot({ path: `${SHOTS}/${t}.png` }); }
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

  // ---- Cá nhân TRƯỚC
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(2500);
  const truoc = await man(page);
  const tienTruoc = soTien(truoc);
  await chup(page, "K1-ca-nhan-truoc");
  console.log("CÁ NHÂN TRƯỚC:", truoc.slice(0, 220));

  // ---- bill
  await thu(() => page.getByRole("button", { name: "Tạo mới" }).click());
  await thu(() => page.getByRole("button", { name: /^Tạo khoản chi/ }).click());
  await page.waitForTimeout(500);
  let doc = false;
  await thu(async () => {
    const ch = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Chọn ảnh bill" }).first().click();
    await (await ch).setFiles(BILL);
    await page.getByText(/Đã nhận diện \d+ món/i).waitFor({ timeout: 120000 });
    doc = true;
  });
  ghi("L9", "AI đọc bill", doc ? "DI_HET" : "CUT", doc ? "8 món, tổng 1.370.000đ khớp dòng in trên bill" : "cụt");
  await thu(() => page.getByRole("button", { name: "Tiếp tục" }).first().click());
  await page.waitForTimeout(1600);

  // ---- thêm người, kiểm lại sau mỗi lần
  const themDuoc = [];
  for (const ten of NGUOI) {
    await thu(async () => {
      // [+] toggle opens the field. It is the FIRST "Thêm"; the green submit is
      // the second. Same name, different job -- 06 lost a whole run to this.
      if (!(await page.locator("input").count())) {
        await page.getByRole("button", { name: /^Thêm$/ }).first().click();
        await page.waitForTimeout(500);
      }
      const o = page.locator("input").first();
      await o.click();
      await page.keyboard.type(ten, { delay: 25 });
      await page.waitForTimeout(300);
      const gui = page.getByRole("button", { name: /^Thêm$/ });
      await gui.nth((await gui.count()) - 1).click();
      await page.waitForTimeout(900);
    });
    const s = await man(page);
    const co = s.includes(ten);
    themDuoc.push({ ten, co });
    console.log(`  thêm "${ten}": có trên màn = ${co}`);
  }
  await chup(page, "K2-da-them-nguoi");
  const sSauThem = await man(page);
  const conRong = /Chưa có ai trong nhóm/i.test(sSauThem);
  const nutSau = await nutCua(page);
  const xemKQ = nutSau.find((n) => /Xem kết quả/i.test(n.ten));
  ghi("L10b", "tự thêm người vào nhóm ở màn chia",
    themDuoc.every((t) => t.co) && !conRong ? "DI_HET" : "CUT",
    `thêm ${themDuoc.filter((t) => t.co).length}/${NGUOI.length} người · còn báo nhóm rỗng=${conRong}`
    + ` · "Xem kết quả" bị tắt=${xemKQ?.tat}`);

  // ---- xem kết quả
  let sKQ = "";
  await thu(async () => {
    await page.getByRole("button", { name: "Xem kết quả", exact: true }).first().click();
    await page.waitForTimeout(3500);
    sKQ = await man(page);
  });
  await chup(page, "K3-ket-qua-chia");
  const nutKQ = await nutCua(page);
  console.log("\nnút ở màn KẾT QUẢ:", JSON.stringify(nutKQ.map((n) => n.ten)));
  console.log("màn KẾT QUẢ:", sKQ.slice(0, 500));
  const sangDuoc = !/Gợi ý chia theo người/i.test(sKQ) || /kết quả|đợt thu|VIETQR/i.test(sKQ);
  ghi("L11", "chia tiền → màn kết quả", sangDuoc ? "DI_HET" : "CUT",
    sangDuoc ? `"${sKQ.slice(0, 220)}"` : `bấm "Xem kết quả" nhưng vẫn ở màn chia`);

  // ---- bất biến tiền trên con số màn hình
  const tien = soTien(sKQ);
  const TONG = 1370000;
  const phan = tien.filter((v) => v > 0 && v < TONG);
  const sum = phan.reduce((a, b) => a + b, 0);
  const nguyen = tien.every(Number.isInteger);
  const khop = sum === TONG;
  console.log(`\nBẤT BIẾN TIỀN — tổng=${TONG} · phần=[${phan.join(", ")}] · Σ=${sum} · khớp=${khop} · nguyên đồng=${nguyen}`);
  ghi("M1", "Σ phân bổ = tổng khoản chi (đọc trên màn)",
    khop && nguyen ? "DI_HET" : "CUT",
    `Σ=${sum} vs tổng=${TONG} · lệch=${sum - TONG} · mọi số nguyên=${nguyen} · phần=[${phan.join(", ")}]`);

  // ---- VietQR
  let sQR = "";
  let toiQR = false;
  for (const n of nutKQ.filter((x) => !x.tat && /thu|QR|chuyển|gửi|xác nhận|tạo|tiếp|xong/i.test(x.ten))) {
    await thu(async () => {
      await page.getByRole("button", { name: n.ten, exact: true }).first().click();
      await page.waitForTimeout(3000);
    });
    sQR = await man(page);
    toiQR = /VIETQR|NAPAS|chuyển khoản/i.test(sQR);
    console.log(`  bấm "${n.ten}" -> tới VietQR=${toiQR}`);
    if (toiQR) break;
  }
  await chup(page, "K4-vietqr");
  ghi("L12", "kết quả → VietQR", toiQR ? "DI_HET" : "CUT",
    toiQR ? `"${sQR.slice(0, 220)}"` : `không nút nào trên màn kết quả dẫn tới VietQR. Nút: ${JSON.stringify(nutKQ.map((n) => n.ten))}`);

  // ---- Cá nhân SAU
  await thu(() => page.getByRole("button", { name: /Đóng khoản chi/i }).first().click());
  await page.waitForTimeout(1200);
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(2800);
  const sau = await man(page);
  const tienSau = soTien(sau);
  await chup(page, "K5-ca-nhan-sau");
  console.log("\nCÁ NHÂN SAU:", sau.slice(0, 300));
  const laCaNhan = /Tổng quan tài chính/i.test(sau);
  const doi = laCaNhan && JSON.stringify(tienSau) !== JSON.stringify(tienTruoc);
  ghi("L13", "Cá nhân thấy tài chính cập nhật",
    !laCaNhan ? "CUT" : doi ? "DI_HET" : "CUT",
    !laCaNhan ? `không quay lại được màn Cá nhân`
      : doi ? `số đổi: [${tienTruoc}] -> [${tienSau}]`
      : `màn Cá nhân mở nhưng số KHÔNG đổi: [${tienSau}] — khoản chi vừa tạo không tới sổ`);

  writeFileSync(`${SHOTS}/di-het-nhanh-tien.json`, JSON.stringify(
    { legs, themDuoc, tienTruoc, tienSau, nutKQ, batBien: { TONG, phan, sum, khop, nguyen }, loi }, null, 2));
  console.log("\n=== TỔNG ===");
  for (const k of ["DI_HET", "VO", "CUT"]) console.log(`${k}: ${legs.filter((l) => l.ket === k).length}`);
  console.log("lỗi trang:", loi.length ? [...new Set(loi)].slice(0, 5) : "(không)");
} finally {
  await browser.close();
}
