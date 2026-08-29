/** rd-qa-08 — vì sao "Xem kết quả" bấm không được: nhóm rỗng ở màn chia.
 *
 *  Ba lượt đo trước đều dừng ở cùng một chỗ và đều chấm sai lý do. Ảnh chụp
 *  màn (`G3-ket-qua-chia.png`) mới nói ra sự thật: màn chia in
 *
 *      "Chưa có ai trong nhóm. Thêm người bằng nút + ở trên."
 *
 *  và nút "Xem kết quả" bị VÔ HIỆU HOÁ. Không phải bộ đo bấm nhầm nút; nút
 *  đúng nhưng không bấm được.
 *
 *  Đáng chú ý vì người dùng vừa ĐĂNG NHẬP với tư cách một thành viên của nhóm
 *  demo "Team Đà Lạt" — màn chọn người ở bước đăng nhập có liệt kê người. Câu
 *  hỏi bộ này trả lời: nhóm đó có đi theo vào luồng khoản chi không, và nếu
 *  không thì người dùng có tự thêm người được không.
 *
 *  Ghi chú bộ đo: `document.body.innerText` trả về "" trên màn này (react-
 *  native-web dựng một scroll container mà innerText của body không thấy
 *  xuyên qua). Ba lượt trước đọc thành "màn trống" và suýt thành một phiếu bug
 *  sai. Ở đây đọc bằng textContent của root, và ĐỐI CHIẾU với ảnh chụp.
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const WEB = process.env.MOBILE_WEB ?? "http://127.0.0.1:8692";
const BILL = process.env.MOBILE_BILL ?? "/tmp/bill-qa08.jpg";
const SHOTS = process.env.MOBILE_SHOTS ?? "/tmp/rd-qa-08";
const PHONE = { width: 390, height: 844 };

/** innerText of body is empty on the split screen; textContent of the app root
 *  is not. Read both and take whichever actually has content. */
const man = (page) => page.evaluate(() => {
  const a = document.body.innerText || "";
  const b = document.getElementById("root")?.textContent || document.body.textContent || "";
  return (a.trim().length > b.trim().length ? a : b).replace(/\s+/g, " ").trim();
});
async function thu(fn) { try { await fn(); return true; } catch { return false; } }
async function chup(page, ten) {
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/${ten}.png` });
}
async function nutCua(page) {
  return await page.getByRole("button").evaluateAll((els) =>
    els.filter((e) => e.offsetWidth || e.offsetHeight).map((e) => ({
      ten: (e.getAttribute("aria-label") || e.innerText || e.textContent || "").replace(/\s+/g, " ").trim(),
      tat: e.getAttribute("aria-disabled") === "true" || e.disabled === true,
    })).filter((n) => n.ten));
}

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: PHONE, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.setDefaultTimeout(8000);

  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.getByText(/Google/i).first().click();
  await page.waitForTimeout(400);
  // Who does sign-in actually offer? That list is the demo group's membership.
  const nguoiDangNhap = await page.getByRole("button", { name: /Vào app với tư cách/i })
    .evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")));
  console.log("người mà bước ĐĂNG NHẬP liệt kê:", JSON.stringify(nguoiDangNhap));

  await page.getByRole("button", { name: /Vào app với tư cách/i }).first().click();
  await page.waitForTimeout(800);

  await thu(() => page.getByRole("button", { name: "Tạo mới" }).click());
  await thu(() => page.getByRole("button", { name: /^Tạo khoản chi/ }).click());
  await page.waitForTimeout(500);
  await thu(async () => {
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Chọn ảnh bill" }).first().click();
    await (await chooser).setFiles(BILL);
    await page.getByText(/Đã nhận diện \d+ món/i).waitFor({ timeout: 120000 });
  });
  await thu(() => page.getByRole("button", { name: "Tiếp tục" }).first().click());
  await page.waitForTimeout(1800);
  await chup(page, "H1-man-chia");

  const sChia = await man(page);
  console.log("\n=== MÀN CHIA (đọc bằng textContent) ===\n" + sChia.slice(0, 500));

  const nut1 = await nutCua(page);
  const xemKQ = nut1.find((n) => /Xem kết quả/i.test(n.ten));
  const nhomRong = /Chưa có ai trong nhóm/i.test(sChia);
  console.log(`\n"Xem kết quả" bị tắt: ${xemKQ?.tat}  ·  màn khai nhóm rỗng: ${nhomRong}`);

  // ---- Người đăng nhập có được mang vào luồng khoản chi không?
  console.log(`\nKẾT LUẬN 1: đăng nhập liệt kê ${nguoiDangNhap.length} người của nhóm demo,`
    + ` nhưng màn chia ${nhomRong ? "KHÔNG thấy ai" : "thấy nhóm"}.`);

  // ---- Có tự thêm người được không?
  let sSauThem = "";
  let themDuoc = false;
  await thu(async () => {
    await page.getByRole("button", { name: /^Thêm$/i }).first().click();
    await page.waitForTimeout(1200);
    sSauThem = await man(page);
    themDuoc = sSauThem !== sChia;
  });
  await chup(page, "H2-sau-bam-them");
  console.log(`\nbấm "+ Thêm": màn đổi=${themDuoc}\n  -> ${sSauThem.slice(0, 400)}`);
  const nutThem = await nutCua(page);
  console.log("nút sau khi bấm Thêm:", JSON.stringify(nutThem.map((n) => n.ten)));

  // Nếu mở ra một ô nhập tên thì gõ vào, xem nút có bật lên không.
  const oNhap = page.locator("input, textarea");
  const soO = await oNhap.count();
  let batDuoc = false;
  if (soO) {
    await thu(async () => {
      await oNhap.first().click();
      await page.keyboard.type("Minh", { delay: 20 });
      await page.waitForTimeout(400);
      const xacNhan = page.getByRole("button", { name: /Thêm|Xong|Lưu|OK/i }).first();
      await xacNhan.click();
      await page.waitForTimeout(1200);
    });
    const nut2 = await nutCua(page);
    const xemKQ2 = nut2.find((n) => /Xem kết quả/i.test(n.ten));
    batDuoc = xemKQ2 && !xemKQ2.tat;
    console.log(`\nsau khi thêm 1 người: "Xem kết quả" bị tắt = ${xemKQ2?.tat}`);
  }
  await chup(page, "H3-sau-them-nguoi");
  const sCuoi = await man(page);
  console.log("\nmàn cuối:", sCuoi.slice(0, 400));

  writeFileSync(`${SHOTS}/nhom-rong.json`, JSON.stringify({
    nguoiDangNhap, nhomRong, xemKetQuaBiTat: xemKQ?.tat, themDuoc,
    soODienTen: soO, batDuocSauKhiThem: batDuoc, manChia: sChia, manCuoi: sCuoi,
  }, null, 2));
} finally {
  await browser.close();
}
