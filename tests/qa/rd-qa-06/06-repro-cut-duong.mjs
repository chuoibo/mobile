/* rd-qa-06 · REPRO TỐI THIỂU — nửa sau của luồng cụt đường ở "mở đợt thu".
 *
 * Điều kiện: một khoản chi nhập bằng TAY trên app (đường mà [+] -> "Tạo khoản
 * chi" -> "Huỷ" dẫn tới). Mọi người trong form là người MỚI, id đúc tại chỗ,
 * nên không ai có tài khoản nhận.
 *
 * Kỳ vọng của người dùng: bấm "Đúng rồi, ghi vào sổ" thì mở được đợt thu.
 * Thực tế: 409, và màn hình nói đúng lý do — nhưng KHÔNG có nút nào, ở bất kỳ
 * đâu trong app, để làm cái việc mà nó vừa đòi.
 *
 * Repro tối thiểu (2 người là đủ, không cần 3; không cần bill, không cần AI):
 *   1. mở app -> "Bỏ qua"
 *   2. [+] "Tạo mới" -> "Tạo khoản chi" -> "Huỷ" (bỏ camera, xuống form tay)
 *   3. thêm "Hà", thêm "Nam"; chọn Hà trả trước; tổng 100000
 *   4. "Chia tiền" -> "Đúng rồi, ghi vào sổ"
 *   -> 409 UNREADY_RECIPIENT_CHOICE_REQUIRED, và luồng dừng ở đây.
 *
 * Tất định: không phụ thuộc AI, không phụ thuộc ảnh bill, không phụ thuộc dữ
 * liệu gieo sẵn. Chạy lại bao nhiêu lần cũng ra đúng một kết quả.
 */
import { phone, typeInto, text, toManualForm, report } from "./lib.mjs";

const { browser, page } = await phone();
const failures = [];
const codes = [];
page.on("response", (r) => { if (/\/batches$/.test(r.url())) codes.push(r.status()); });

await toManualForm(page);
for (const n of ["Hà", "Nam"]) {
  await typeInto(page, page.getByPlaceholder("Hà"), n);
  await page.getByRole("button", { name: /^Thêm$/ }).click();
  await page.waitForTimeout(200);
}
await page.getByRole("radio", { name: /^Hà$/ }).first().click();
await typeInto(page, page.getByPlaceholder("480000"), "100000");
await page.waitForTimeout(300);
await page.getByRole("button", { name: /^Chia tiền$/ }).click();
await page.waitForTimeout(3000);
await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/ }).click();
await page.waitForTimeout(4000);

const t = await text(page);
console.log("POST /batches ->", codes.join(", ") || "(không gọi)");
console.log("màn hình nói:", (t.match(/Người ứng tiền[^M]*/) ?? ["(không có thông báo)"])[0].trim());

if (!codes.includes(409)) failures.push("không tái lập được: POST /batches không trả 409");
if (!/chưa có tài khoản nhận/.test(t)) failures.push("không tái lập được: màn hình không báo thiếu tài khoản nhận");

// Cụt đường THẬT hay chỉ là một bước nữa? Liệt kê MỌI control đang thấy được.
const labels = [];
for (const e of await page.locator('[role="button"], button, [role="radio"], a, input').all()) {
  if (!(await e.isVisible().catch(() => false))) continue;
  labels.push(((await e.getAttribute("aria-label")) ?? (await e.innerText().catch(() => "")) ?? "").replace(/\s+/g, " ").trim());
}
console.log("\nmọi control đang thấy được sau khi bị chặn:");
for (const l of labels) console.log("   · " + (l || "(không tên)"));

const loiThoat = labels.filter((l) => /tài khoản|ngân hàng|số tk|nhận tiền|thêm tk/i.test(l));
console.log("\ncontrol dẫn tới việc ghi tài khoản nhận:", loiThoat.length ? loiThoat.join(", ") : "KHÔNG CÓ CÁI NÀO");
if (loiThoat.length === 0) {
  console.log("=> cụt đường: app đòi một thứ mà chính nó không có màn nào để tạo ra.");
} else {
  failures.push("có lối thoát trên màn — phát hiện này cần viết lại: " + loiThoat.join(", "));
}

const n = report("06 · repro cụt đường ở mở đợt thu", failures);
await page.screenshot({ path: "/tmp/qa06/08-cut-duong.png", fullPage: true });
await browser.close();
process.exit(n === 0 ? 0 : 1);
