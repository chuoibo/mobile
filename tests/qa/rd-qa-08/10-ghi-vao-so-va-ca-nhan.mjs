/** rd-qa-08 — chặng cuối, sạch: ghi vào sổ rồi xem màn Cá nhân.
 *
 *  Bộ 09 đã đi tới màn kết quả chia đúng, nhưng hai chỗ cuối vẫn đo sai:
 *
 *  1. Nó bấm "Đúng rồi, ghi vào sổ" RỒI bấm tiếp "Sửa lại" (vòng lặp dò nút),
 *     tức là tự huỷ đúng thứ vừa ghi, rồi kết luận sổ không đổi.
 *  2. Σ của nó cộng cả "1đ" trong CÂU GIẢI THÍCH "Minh, Hải chịu thêm 1đ lẻ"
 *     vào danh sách phần chia, nên báo lệch 1đ. Ba phần thật là
 *     456.667 + 456.666 + 456.667 = 1.370.000, khớp đúng.
 *
 *  Ở đây chỉ bấm MỘT nút xác nhận, và Σ chỉ lấy các con số nằm trong BẢNG
 *  chia (dòng có tên người), không lấy số trong câu văn.
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
  const truoc = await man(page);
  const tienTruoc = soTien(truoc);
  console.log("CÁ NHÂN TRƯỚC:", JSON.stringify(tienTruoc), "|", truoc.slice(0, 160));

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
      const g = page.getByRole("button", { name: /^Thêm$/ });
      await g.nth((await g.count()) - 1).click();
      await page.waitForTimeout(800);
    });
  }
  await thu(() => page.getByRole("button", { name: "Xem kết quả", exact: true }).first().click());
  await page.waitForTimeout(2500);

  // form: mô tả + người trả trước (radio, không phải button)
  await thu(async () => {
    await page.locator("input").first().click();
    await page.keyboard.type("bua lau qa08", { delay: 25 });
  });
  await thu(() => page.getByRole("radio", { name: "Minh", exact: true }).click());
  await page.waitForTimeout(600);
  await thu(() => page.getByRole("button", { name: "Chia tiền", exact: true }).click());
  await page.waitForTimeout(4500);
  const sChia = await man(page);
  await chup(page, "Q1-ket-qua-chia");
  console.log("\nKẾT QUẢ CHIA:", sChia.slice(0, 400));
  ghi("L11", "chia tiền → kết quả chia", /Tổng 1\.370\.000/.test(sChia) ? "DI_HET" : "CUT",
    `"${sChia.slice(0, 200)}"`);

  // Σ chỉ lấy các dòng CÓ TÊN NGƯỜI, không lấy số trong câu giải thích.
  const phan = NGUOI.map((n) => {
    const m = sChia.match(new RegExp(`${n}[^\\d]{0,20}(\\d[\\d.]*)\\s*đ`));
    return m ? Number(m[1].replace(/\./g, "")) : null;
  });
  const sum = phan.reduce((a, b) => a + (b ?? 0), 0);
  const nguyen = phan.every((v) => v !== null && Number.isInteger(v));
  console.log(`\nBẤT BIẾN TIỀN — phần theo tên: ${NGUOI.map((n, i) => `${n}=${phan[i]}`).join(" · ")}`);
  console.log(`  Σ=${sum} · tổng=${TONG} · lệch=${sum - TONG} · mọi phần nguyên đồng=${nguyen}`);
  ghi("M1", "luật 2: Σ phân bổ = tổng khoản chi",
    sum === TONG && nguyen ? "DI_HET" : "CUT",
    `${NGUOI.map((n, i) => `${n}=${phan[i]}`).join(" + ")} = ${sum} · tổng bill=${TONG} · lệch=${sum - TONG}`);
  ghi("M2", "luật 1: số nguyên đồng, không phân số",
    nguyen && !/[,.]\d{1,2}\s*đ|\d+\/\d+/.test(sChia) ? "DI_HET" : "CUT",
    `mọi phần là số nguyên đồng = ${nguyen}`);

  // ---- CHỈ bấm nút xác nhận. Không dò tiếp, vì "Sửa lại" đứng ngay cạnh và
  // bấm nhầm nó là tự huỷ đúng thứ vừa ghi.
  let sSau = "";
  const ghiSo = await thu(async () => {
    await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/i }).click();
    await page.waitForTimeout(4500);
    sSau = await man(page);
  });
  await chup(page, "Q2-sau-ghi-so");
  console.log("\nSAU KHI GHI VÀO SỔ:", sSau.slice(0, 400));
  const nutSau = [...new Set(await page.getByRole("button").evaluateAll((els) =>
    els.filter((e) => e.offsetWidth || e.offsetHeight)
      .map((e) => (e.getAttribute("aria-label") || e.innerText || e.textContent || "").replace(/\s+/g, " ").trim())
      .filter(Boolean)))];
  console.log("nút sau khi ghi sổ:", JSON.stringify(nutSau));
  const toiQR = /VIETQR|NAPAS|chuyển khoản|đợt thu/i.test(sSau);
  ghi("L12", "ghi vào sổ → đợt thu / VietQR",
    !ghiSo ? "CUT" : toiQR ? "DI_HET" : "CUT",
    !ghiSo ? `không bấm được "Đúng rồi, ghi vào sổ"`
      : toiQR ? `"${sSau.slice(0, 200)}"`
      : `ghi sổ xong nhưng màn KHÔNG dẫn tới đợt thu/VietQR. Nút còn lại: ${JSON.stringify(nutSau)}`);

  // ---- Cá nhân SAU
  await thu(() => page.getByRole("button", { name: /Đóng khoản chi/i }).first().click());
  await page.waitForTimeout(1500);
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(3500);
  const sau = await man(page);
  const tienSau = soTien(sau);
  await chup(page, "Q3-ca-nhan-sau");
  console.log("\nCÁ NHÂN SAU:", sau.slice(0, 320));
  const laCaNhan = /Tổng quan tài chính/i.test(sau);
  const doi = laCaNhan && JSON.stringify(tienSau) !== JSON.stringify(tienTruoc);
  ghi("L13", "Cá nhân thấy tài chính cập nhật",
    !laCaNhan ? "CUT" : doi ? "DI_HET" : "CUT",
    !laCaNhan ? "không quay lại được màn Cá nhân"
      : doi ? `số ĐỔI: [${tienTruoc}] -> [${tienSau}]`
      : `số KHÔNG đổi: [${tienSau}] — khoản chi đã ghi sổ nhưng màn Cá nhân của chính người trả trước vẫn 0đ`);

  writeFileSync(`${SHOTS}/ghi-so-ca-nhan.json`, JSON.stringify(
    { legs, tienTruoc, tienSau, phan, sum, TONG, manChia: sChia, manSauGhi: sSau, nutSau, manCaNhan: sau, loi }, null, 2));
  console.log("\n=== TỔNG ===");
  for (const k of ["DI_HET", "VO", "CUT"]) console.log(`${k}: ${legs.filter((l) => l.ket === k).length}`);
  console.log("lỗi trang:", loi.length ? [...new Set(loi)].slice(0, 5) : "(không)");
} finally {
  await browser.close();
}
