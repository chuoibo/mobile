/** rd-qa-08 — đối chứng môi trường: màn Cá nhân 0đ là do SẢN PHẨM hay do TÔI?
 *
 *  Lượt 10 chấm "Cá nhân không cập nhật" là CUT. Trước khi gửi phán quyết đó
 *  đi, một câu hỏi phải trả lời: nhóm demo "Team Đà Lạt" có trong database
 *  của tôi không?
 *
 *  Không. `make up` chạy `seed_dev_data.py` (An/Bình/Chi), còn 7 người của
 *  màn đăng nhập đến từ `seed_demo_data.py` mà chỉ `make demo` gọi. Bảng
 *  `people` lúc đó không có Minh nào ngoài mấy dòng chính bộ đo vừa tự tạo ra
 *  khi gõ tên bằng tay.
 *
 *  Nghĩa là màn Cá nhân hỏi máy chủ về một người có thật nhưng chưa có gì
 *  trong sổ, và trả lời 0đ — một câu trả lời ĐÚNG. Chấm nó là lỗi sản phẩm là
 *  gửi lane khác đi sửa môi trường của tôi.
 *
 *  Bộ này chạy SAU `make demo` và đo lại. Nếu số đổi thì phán quyết cũ bị rút.
 */
import { chromium } from "playwright";
import { writeFileSync, mkdirSync } from "node:fs";

const WEB = process.env.MOBILE_WEB ?? "http://127.0.0.1:8692";
const SHOTS = process.env.MOBILE_SHOTS ?? "/tmp/rd-qa-08";
const PHONE = { width: 390, height: 844 };
const man = (page) => page.evaluate(() => {
  const a = document.body.innerText || "";
  const b = document.getElementById("root")?.textContent || document.body.textContent || "";
  return (a.trim().length > b.trim().length ? a : b).replace(/\s+/g, " ").trim();
});
async function thu(fn) { try { await fn(); return true; } catch { return false; } }
const soTien = (s) => [...s.matchAll(/(\d[\d.]*)\s*đ/g)].map((m) => Number(m[1].replace(/\./g, "")));

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: PHONE, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.setDefaultTimeout(8000);
  mkdirSync(SHOTS, { recursive: true });

  const ket = [];
  // Every member of the demo group, not just the first: a screen that works
  // for one person and not the rest is a different bug from one that never
  // works, and one name would not tell them apart.
  for (const ten of ["Minh", "Trang", "Hải", "Ngọc", "Đức", "Linh", "Quân"]) {
    await page.goto(WEB, { waitUntil: "networkidle" });
    await page.getByText(/Google/i).first().click();
    const ok = await thu(() => page.getByRole("button", { name: new RegExp(`Vào app với tư cách ${ten}`, "i") }).first().click());
    if (!ok) { ket.push({ ten, loi: "không chọn được" }); continue; }
    await page.waitForTimeout(600);
    await thu(() => page.getByRole("tab", { name: /Cá nhân/i }).click());
    await page.waitForTimeout(3000);
    const s = await man(page);
    const tien = soTien(s);
    const soLan = s.match(/(\d+)\s*Lần chia bill/)?.[1];
    ket.push({ ten, tien, soLanChiaBill: soLan, doc: /Tổng quan tài chính/.test(s) });
    console.log(`${ten.padEnd(6)} — tiền trên màn: [${tien.join(", ")}] · lần chia bill: ${soLan}`);
    await page.screenshot({ path: `${SHOTS}/R-ca-nhan-${ten}.png` });
  }

  const coSoKhac0 = ket.some((k) => (k.tien || []).some((v) => v > 0));
  console.log(`\nCÓ ÍT NHẤT MỘT NGƯỜI CÓ SỐ KHÁC 0: ${coSoKhac0}`);
  console.log(coSoKhac0
    ? "=> màn Cá nhân ĐỌC ĐƯỢC sổ. Phán quyết CUT ở lượt 10 là do database của tôi chưa seed demo, RÚT LẠI."
    : "=> màn Cá nhân vẫn 0đ cho cả 7 người dù sổ đã có dữ liệu demo. Phán quyết CUT ĐỨNG.");
  writeFileSync(`${SHOTS}/ca-nhan-sau-seed.json`, JSON.stringify({ ket, coSoKhac0 }, null, 2));
} finally {
  await browser.close();
}
