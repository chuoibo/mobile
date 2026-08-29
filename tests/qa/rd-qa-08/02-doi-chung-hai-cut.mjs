/** rd-qa-08 — đối chứng hai chặng bị lượt 1 chấm là CUT, rồi đi nốt nhánh tiền.
 *
 *  Lượt 1 (`01-ban-do-duong-di.mjs`) chấm L4 và L9 là CUT. Cả hai đều ĐÁNG NGỜ,
 *  và một phán quyết CUT sai còn tệ hơn không có phán quyết nào — nó gửi lane
 *  khác đi sửa thứ không hỏng:
 *
 *    L4  màn Khám phá lúc đó còn đang in "Đang hỏi máy chủ chỗ nào hợp với
 *        nhóm…". Bộ đo bấm vào chỗ chưa có thẻ nào. Đó là lỗi của bộ đo.
 *    L9  bộ đo bấm trúng TIÊU ĐỀ "Chụp bill" chứ không phải nút thật
 *        "Chọn ảnh bill". Cũng là lỗi của bộ đo.
 *
 *  Bộ này đo lại hai chặng đó cho đúng, rồi đi tiếp nhánh tiền tới hết:
 *  bill → AI đọc món → gán món → chia → VietQR → Cá nhân.
 *
 *  Ảnh bill là ảnh TỔNG HỢP sinh bằng PIL (8 dòng món, tổng in trên giấy
 *  1.370.000đ). Không dùng bill thật, không commit ảnh.
 *
 *  Chạy:
 *    MOBILE_WEB=http://127.0.0.1:8692 MOBILE_BILL=/tmp/bill-qa08.jpg \
 *      node 02-doi-chung-hai-cut.mjs
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
async function chup(page, ten) {
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/${ten}.png` });
}
async function thu(fn) { try { await fn(); return true; } catch { return false; } }

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
  await page.waitForTimeout(500);

  // ============================ L4 lại: đợi thẻ địa điểm THẬT hiện rồi mới bấm
  // The loading line is the thing lượt 1 measured. Wait for it to go away, so
  // whatever we conclude is about the product and not about our own impatience.
  await thu(() => page.getByText(/Đang hỏi máy chủ/i).waitFor({ state: "detached", timeout: 60000 }));
  await page.waitForTimeout(1200);
  await chup(page, "D1-kham-pha-da-tai");
  const sKP = await man(page);

  // A real place card, addressed by its accessible name rather than by text
  // that also appears in the loading state.
  const the = page.getByRole("button").filter({ hasText: /₫|đ\s|km|·/ });
  const soThe = await the.count();
  let sChiTiet = "";
  let moDuoc = false;
  if (soThe) {
    await thu(async () => {
      await the.first().click();
      await page.waitForTimeout(1200);
      sChiTiet = await man(page);
      moDuoc = sChiTiet !== sKP;
    });
  }
  await chup(page, "D2-chi-tiet-dia-diem");
  const coRuDi = /Rủ|Tạo chuyến|Tạo buổi|Lên plan|Mời|Chốt|Thêm vào/i.test(sChiTiet);
  ghi("L4", "chọn quán → tạo buổi đi (rủ nhóm)",
    soThe === 0 ? "CUT" : !moDuoc ? "CUT" : coRuDi ? "DI_HET" : "CUT",
    soThe === 0
      ? `Khám phá tải xong nhưng KHÔNG có thẻ địa điểm nào bấm được. Màn: "${sKP.slice(0, 200)}"`
      : !moDuoc
        ? `có ${soThe} thẻ, bấm vào không mở được gì`
        : coRuDi
          ? `chi tiết mở, CÓ đường tạo buổi đi: "${sChiTiet.slice(0, 200)}"`
          : `chi tiết mở (${soThe} thẻ) nhưng KHÔNG có đường tạo buổi đi / rủ nhóm. Màn: "${sChiTiet.slice(0, 260)}"`);

  // Back to the shell.
  await thu(() => page.getByRole("button", { name: /Đóng|Quay|Trở/i }).first().click());
  await page.waitForTimeout(500);

  // ================================ L9 lại: nút THẬT là "Chọn ảnh bill"
  await thu(() => page.getByRole("button", { name: "Tạo mới" }).click());
  await thu(() => page.getByRole("button", { name: /^Tạo khoản chi/ }).click());
  await page.waitForTimeout(600);
  await chup(page, "D3-man-chup-bill");

  let doc8Mon = false;
  let sNhanDien = "";
  const t0 = Date.now();
  const ok = await thu(async () => {
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Chọn ảnh bill" }).first().click();
    await (await chooser).setFiles(BILL);
    // The AI call is real (Gemini). rd-qa-05 measured it inside 90s.
    await page.getByText(/Đã nhận diện \d+ món/i).waitFor({ timeout: 120000 });
    sNhanDien = await man(page);
    doc8Mon = true;
  });
  const giay = Math.round((Date.now() - t0) / 100) / 10;
  await chup(page, "D4-ket-qua-nhan-dien");
  ghi("L9", "chụp/chọn ảnh bill → AI đọc từng món",
    doc8Mon ? "DI_HET" : "CUT",
    doc8Mon
      ? `AI đọc bill thật trong ${giay}s: "${sNhanDien.slice(0, 220)}"`
      : `không tới được màn kết quả nhận diện (ok=${ok}). Màn: "${(await man(page)).slice(0, 240)}"`);

  // ================================ L10: gán món cho người
  let sGan = "";
  let ganDuoc = false;
  if (doc8Mon) {
    await thu(async () => {
      const tiep = page.getByRole("button", { name: /Tiếp|Gán|Chia|Xong/i }).first();
      await tiep.click();
      await page.waitForTimeout(1000);
      sGan = await man(page);
      ganDuoc = /gán|ai ăn|chọn người|Minh|Chia/i.test(sGan);
    });
  }
  await chup(page, "D5-gan-mon");
  ghi("L10", "kết quả nhận diện → gán món cho người",
    !doc8Mon ? "CUT" : ganDuoc ? "DI_HET" : "CUT",
    !doc8Mon ? "không tới được vì L9 cụt"
      : ganDuoc ? `sang được bước gán: "${sGan.slice(0, 220)}"`
      : `không sang được bước gán: "${sGan.slice(0, 240)}"`);

  writeFileSync(`${SHOTS}/doi-chung.json`, JSON.stringify({ web: WEB, legs, loi }, null, 2));
  console.log("\n=== TỔNG (đối chứng) ===");
  for (const k of ["DI_HET", "VO", "CUT"]) console.log(`${k}: ${legs.filter((l) => l.ket === k).length}`);
  console.log("lỗi trang:", loi.length ? [...new Set(loi)].slice(0, 5) : "(không)");
} finally {
  await browser.close();
}
