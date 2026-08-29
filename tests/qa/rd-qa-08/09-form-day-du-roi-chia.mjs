/** rd-qa-08 — điền đủ form "Khoản chi mới" rồi mới bấm "Chia tiền".
 *
 *  Bộ 08 chấm CUT ở đây, và lại sai. Ảnh `N1-form-khoan-chi.png` cho thấy nút
 *  "Chia tiền" bị tắt vì FORM CHƯA ĐỦ: ô "Đi đâu, ăn gì" còn trống (chữ xám
 *  trong ô là placeholder, không phải giá trị), và chưa chọn ai trả trước.
 *  Bộ 08 chỉ điền tổng tiền rồi bấm.
 *
 *  Một nút bị tắt vì thiếu dữ liệu KHÔNG phải cụt đường. Bộ này điền đủ rồi
 *  bấm, để phán quyết cuối nói về sản phẩm chứ không nói về form chưa điền.
 *
 *  Nó cũng liệt kê MỌI phần tử tương tác kèm role — chip "ai trả trước" không
 *  phải role=button nên các lượt trước không thấy nó.
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
/** Everything interactive, with its role -- the payer chips are not buttons. */
async function tuongTac(page) {
  return await page.evaluate(() =>
    [...document.querySelectorAll('[role],input,textarea,button')]
      .filter((e) => e.offsetWidth || e.offsetHeight)
      .map((e) => ({
        role: e.getAttribute("role") || e.tagName.toLowerCase(),
        ten: (e.getAttribute("aria-label") || e.getAttribute("placeholder") || e.innerText || "")
          .replace(/\s+/g, " ").trim().slice(0, 48),
        val: e.value ?? undefined,
        tat: e.getAttribute("aria-disabled") === "true" || e.disabled === true,
        chon: e.getAttribute("aria-checked") ?? e.getAttribute("aria-selected") ?? undefined,
      }))
      .filter((n) => n.ten || n.val !== undefined));
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
  console.log("CÁ NHÂN TRƯỚC:", JSON.stringify(tienTruoc));

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

  console.log("\n=== MỌI PHẦN TỬ TƯƠNG TÁC TRÊN FORM ===");
  for (const n of await tuongTac(page)) console.log(`  [${n.role}] "${n.ten}" val=${JSON.stringify(n.val)} tắt=${n.tat} chọn=${n.chon}`);

  // ---- điền "Đi đâu, ăn gì" (ô đầu tiên; chữ xám trong ô là placeholder)
  await thu(async () => {
    const o = page.locator("input").first();
    await o.click();
    await page.keyboard.type("bua lau qa08", { delay: 25 });
    await page.waitForTimeout(500);
  });

  // ---- chọn ai trả trước: thử mọi phần tử mang tên một người
  let chonDuoc = false;
  for (const ten of NGUOI) {
    const ok = await thu(async () => {
      await page.getByText(ten, { exact: true }).last().click();
      await page.waitForTimeout(600);
    });
    if (ok) { chonDuoc = true; break; }
  }
  await page.waitForTimeout(600);
  await chup(page, "P1-form-da-dien");

  const sauDien = await tuongTac(page);
  const nutChiaTien = sauDien.find((n) => /^Chia tiền$/i.test(n.ten));
  console.log(`\nsau khi điền mô tả + chọn người trả trước (chọn được=${chonDuoc}): "Chia tiền" bị tắt = ${nutChiaTien?.tat}`);

  let sChia = "";
  await thu(async () => {
    await page.getByRole("button", { name: "Chia tiền", exact: true }).first().click();
    await page.waitForTimeout(4500);
    sChia = await man(page);
  });
  await chup(page, "P2-sau-chia");
  console.log("\nmàn sau CHIA TIỀN:", sChia.slice(0, 600));
  const roiForm = !/Khoản chi mới/i.test(sChia) && sChia.length > 0;
  ghi("L11", "form đủ → bấm Chia tiền → kết quả chia",
    roiForm ? "DI_HET" : "CUT",
    roiForm ? `"${sChia.slice(0, 240)}"`
      : `"Chia tiền" vẫn bị tắt (${nutChiaTien?.tat}) sau khi điền mô tả + chọn người trả trước`);

  const tien = soTien(sChia);
  const phan = tien.filter((v) => v > 0 && v < TONG);
  const sum = phan.reduce((a, b) => a + b, 0);
  ghi("M1", "Σ phân bổ = tổng khoản chi (con số trên màn)",
    sum === TONG && tien.every(Number.isInteger) ? "DI_HET" : "CUT",
    `Σ=${sum} vs tổng=${TONG} (lệch ${sum - TONG}) · phần=[${phan.join(", ")}]`);

  let sQR = "";
  let toiQR = /VIETQR|NAPAS|chuyển khoản/i.test(sChia);
  if (!toiQR) {
    const nut = (await tuongTac(page)).filter((n) => n.role === "button" && !n.tat && !/Đóng|Quay|Làm lại|Bỏ|Thêm/i.test(n.ten));
    for (const n of nut) {
      await thu(async () => {
        await page.getByRole("button", { name: n.ten, exact: true }).first().click();
        await page.waitForTimeout(3000);
      });
      sQR = await man(page);
      toiQR = /VIETQR|NAPAS|chuyển khoản/i.test(sQR);
      console.log(`  bấm "${n.ten}" -> VietQR=${toiQR} · "${sQR.slice(0, 140)}"`);
      if (toiQR) break;
    }
  }
  await chup(page, "P3-vietqr");
  ghi("L12", "kết quả chia → VietQR", toiQR ? "DI_HET" : "CUT",
    toiQR ? `"${sQR.slice(0, 220)}"` : `không tới được VietQR`);

  await thu(() => page.getByRole("button", { name: /Đóng khoản chi/i }).first().click());
  await page.waitForTimeout(1200);
  await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
  await page.waitForTimeout(3000);
  const sau = await man(page);
  const tienSau = soTien(sau);
  await chup(page, "P4-ca-nhan-sau");
  console.log("\nCÁ NHÂN SAU:", sau.slice(0, 300));
  const laCaNhan = /Tổng quan tài chính/i.test(sau);
  ghi("L13", "Cá nhân thấy tài chính cập nhật",
    !laCaNhan ? "CUT" : JSON.stringify(tienSau) !== JSON.stringify(tienTruoc) ? "DI_HET" : "CUT",
    !laCaNhan ? "không quay lại được màn Cá nhân"
      : JSON.stringify(tienSau) !== JSON.stringify(tienTruoc)
        ? `số ĐỔI: [${tienTruoc}] -> [${tienSau}]`
        : `số KHÔNG đổi: [${tienSau}]`);

  writeFileSync(`${SHOTS}/form-day-du.json`, JSON.stringify(
    { legs, tienTruoc, tienSau, sauDien, manChia: sChia, manCaNhan: sau, loi }, null, 2));
  console.log("\n=== TỔNG ===");
  for (const k of ["DI_HET", "VO", "CUT"]) console.log(`${k}: ${legs.filter((l) => l.ket === k).length}`);
  console.log("lỗi trang:", loi.length ? [...new Set(loi)].slice(0, 5) : "(không)");
} finally {
  await browser.close();
}
