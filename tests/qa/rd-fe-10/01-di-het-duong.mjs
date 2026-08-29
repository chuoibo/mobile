/* rd-fe-10 · NGHIỆM THU cho bug-112837: cụt đường ở "mở đợt thu".
 *
 * Đây là bản đối chiếu của tests/qa/rd-qa-06/06-repro-cut-duong.mjs. Ca đó
 * dừng lại ở chỗ chứng minh rằng KHÔNG có lối thoát; ca này đi tiếp qua cái
 * lối thoát vừa được dựng, tới tận publish. Cùng một kịch bản, cùng một dữ
 * liệu, khác đúng ở chỗ có màn ghi tài khoản nhận hay không.
 *
 * Đọc kết quả:
 *   - Trên bản CHƯA sửa: đỏ ở bước 4 ("không có nút nào dẫn tới màn ghi tài
 *     khoản nhận"). Đó là lỗi đang được tái lập, không phải bộ đo hỏng.
 *   - Trên bản ĐÃ sửa: xanh, và POST /batches phải có 409 TRƯỚC rồi 201 SAU.
 *     Chỉ thấy 201 nghĩa là kịch bản không còn đi qua chỗ bị chặn nữa, và
 *     lúc đó nó không nghiệm thu gì cả — nên thiếu 409 cũng là ĐỎ.
 *
 * Tất định: không AI, không ảnh bill, không dữ liệu gieo sẵn. Hai người.
 *
 *   WEB_URL=http://127.0.0.1:PORT node 01-di-het-duong.mjs
 */
import { phone, typeInto, text, toManualForm, report } from "../rd-qa-06/lib.mjs";

/* Số tài khoản bịa. Không phải ngân hàng thật, không phải tài khoản thật,
 * không có tiền của ai đứng sau. */
// repo-guard: allow=long-number reason=synthetic-test-account-number
const SO_TAI_KHOAN = "1904567890123";
const CHU_TAI_KHOAN = "NGUYEN THI HA";
const BON_SO_CUOI = SO_TAI_KHOAN.slice(-4);

const { browser, page, errors } = await phone();
const failures = [];

/** Mã trạng thái theo route, để phân biệt "bị chặn rồi đi tiếp" với "chưa từng bị chặn". */
const goi = { batches: [], taiKhoan: [], publish: [] };
page.on("response", (r) => {
  const url = r.url();
  if (/\/batches$/.test(url)) goi.batches.push(r.status());
  if (/\/bank-recipient$/.test(url)) goi.taiKhoan.push(r.status());
  if (/\/publish$/.test(url)) goi.publish.push(r.status());
});

async function co(locator) {
  return (await locator.count()) > 0 && (await locator.first().isVisible().catch(() => false));
}

// --- 1..3: đi tới đúng chỗ rd-qa-06 dừng lại ------------------------------
await toManualForm(page);
for (const ten of ["Hà", "Nam"]) {
  await typeInto(page, page.getByPlaceholder("Hà"), ten);
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

if (!goi.batches.includes(409)) {
  failures.push(
    `không tái lập được chỗ bị chặn: POST /batches -> [${goi.batches.join(", ") || "không gọi"}], ` +
      "không có 409. Ca này chỉ nghiệm thu được khi nó thật sự đi qua chỗ đó.",
  );
}

// --- 4: lối thoát. Đây là dòng đỏ trên bản chưa sửa -----------------------
const loiThoat = page.getByRole("button", { name: /Ghi tài khoản nhận/ });
if (!(await co(loiThoat))) {
  const nhan = [];
  for (const e of await page.locator('[role="button"], button').all()) {
    if (!(await e.isVisible().catch(() => false))) continue;
    nhan.push(((await e.innerText().catch(() => "")) ?? "").replace(/\s+/g, " ").trim());
  }
  failures.push(
    "CỤT ĐƯỜNG: không có nút nào dẫn tới màn ghi tài khoản nhận. " +
      `Mọi control còn thấy: ${nhan.filter(Boolean).join(" · ")}`,
  );
  console.log("\n———— dừng ở đây: không đi tiếp được ————");
  await page.screenshot({ path: "/tmp/qa-fe10/cut-duong.png", fullPage: true });
  report("01 · đi hết đường sau khi bị chặn", failures);
  await browser.close();
  process.exit(1);
}
await loiThoat.click();
await page.waitForTimeout(800);

// --- 5: điền tài khoản ----------------------------------------------------
await typeInto(page, page.getByPlaceholder("Vietcombank"), "vietcom");
await page.waitForTimeout(300);
const chonNganHang = page.getByRole("radio", { name: /^Vietcombank$/ });
if (!(await co(chonNganHang))) {
  failures.push("lọc ngân hàng không ra Vietcombank — không chọn được ngân hàng nào");
} else {
  await chonNganHang.first().click();
}

/* Placeholder bịa của chính màn đó, dùng làm cái móc để tìm hai ô. */
// repo-guard: allow=long-number reason=synthetic-placeholder-account-number
const oSo = page.getByPlaceholder("0011 0022 0033");
if ((await oSo.count()) < 2) {
  failures.push(
    `chỉ có ${await oSo.count()} ô số tài khoản. Nhập một lần thì không có gì bắt ` +
      "được một chữ số gõ nhầm, và gõ nhầm là tiền đi nhầm người.",
  );
}

// Gõ lệch trước, để chứng minh cái chốt hai ô có thật chứ không phải trang trí.
await typeInto(page, oSo.nth(0), SO_TAI_KHOAN);
await typeInto(page, oSo.nth(1), SO_TAI_KHOAN.slice(0, -2) + SO_TAI_KHOAN.slice(-1) + SO_TAI_KHOAN.slice(-2));
await typeInto(page, page.getByPlaceholder("NGUYEN VAN A"), CHU_TAI_KHOAN);
await page.waitForTimeout(400);
const nutXemLai = page.getByRole("button", { name: /Xem lại rồi lưu/ });
if (await nutXemLai.first().isEnabled()) {
  failures.push("hai ô số tài khoản lệch nhau mà nút lưu vẫn bấm được — chốt này là trang trí");
}
if (!/chưa giống nhau/.test(await text(page))) {
  failures.push("hai ô lệch nhau mà màn hình không nói gì");
}

// Rồi gõ đúng.
await typeInto(page, oSo.nth(1), SO_TAI_KHOAN);
await page.waitForTimeout(400);
if (!(await nutXemLai.first().isEnabled())) {
  failures.push("hai ô đã khớp, mọi ô đã điền, mà nút lưu vẫn không bấm được");
}
await nutXemLai.click();
await page.waitForTimeout(700);

// --- 6: bước xem lại phải in ĐỦ số, đây là chỗ người ta đối chiếu ---------
const manDuyet = await text(page);
const soCoCach = SO_TAI_KHOAN.replace(/(\d{4})(?=\d)/g, "$1 ");
if (!manDuyet.includes(soCoCach) && !manDuyet.includes(SO_TAI_KHOAN)) {
  failures.push(
    "bước xem lại không in số tài khoản đầy đủ. Không đọc lại được cái mình vừa " +
      "gõ thì bước xác nhận không xác nhận gì cả.",
  );
}
if (!manDuyet.includes(CHU_TAI_KHOAN)) {
  failures.push("bước xem lại không hiện tên chủ tài khoản để đối chiếu");
}
await page.screenshot({ path: "/tmp/qa-fe10/02-xem-lai.png", fullPage: true });
await page.getByRole("button", { name: /Đúng, lưu tài khoản này/ }).click();
await page.waitForTimeout(3000);

if (!goi.taiKhoan.some((s) => s === 200 || s === 201)) {
  failures.push(
    `PUT /people/{id}/bank-recipient -> [${goi.taiKhoan.join(", ") || "không gọi"}]. ` +
      "Màn hình có thể vẫn đẹp; máy chủ thì chưa nhận được gì.",
  );
}

// --- 7: quay lại đúng chỗ, và KHÔNG in số đầy đủ ra nữa -------------------
const manDeXuat = await text(page);
if (!/Đã ghi tài khoản nhận/.test(manDeXuat)) {
  failures.push("lưu xong mà màn đề xuất không nói gì — bấm lại nút vừa bị từ chối thành ra đoán");
}
if (manDeXuat.includes(SO_TAI_KHOAN) || manDeXuat.includes(soCoCach)) {
  failures.push("RÒ RỈ: số tài khoản đầy đủ nằm trên màn đề xuất, là màn cả bàn nhìn chung");
}
if (!manDeXuat.includes(BON_SO_CUOI)) {
  failures.push("che hết cả bốn số cuối — chính chủ không nhận ra tài khoản của mình");
}

// --- 8..9: đi tiếp tới publish -------------------------------------------
await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/ }).click();
await page.waitForTimeout(4000);
if (!goi.batches.includes(201)) {
  failures.push(
    `ghi tài khoản xong mà POST /batches vẫn không mở được đợt thu: [${goi.batches.join(", ")}]`,
  );
}

const nutPhat = page.getByRole("button", { name: /^Phát đợt thu$/ });
if (!(await co(nutPhat))) {
  failures.push("không tới được màn đợt thu, nên không có gì để phát");
} else {
  await nutPhat.click();
  await page.waitForTimeout(6000);
  if (!goi.publish.includes(200) && !goi.publish.includes(201)) {
    failures.push(`POST /batches/{id}/publish -> [${goi.publish.join(", ") || "không gọi"}]`);
  }
  const manCuoi = await text(page);
  if (manCuoi.includes(SO_TAI_KHOAN)) {
    failures.push("RÒ RỈ: số tài khoản đầy đủ in ra ở màn kết quả thanh toán");
  }
  await page.screenshot({ path: "/tmp/qa-fe10/03-ket-qua.png", fullPage: true });
}

/* Một lỗi JS trên đường đi làm mọi phép đo bên trên đáng ngờ.
 *
 * Trừ đúng một dòng: kịch bản này CỐ Ý đi qua một 409, và Chrome ghi mọi
 * response không-ok vào console như một lỗi tài nguyên. Lọc hẹp theo đúng mã
 * đó, không lọc theo "Failed to load resource" — một 500 thật cũng in ra dòng
 * giống hệt, và bỏ qua cả họ là cách biến phép kiểm này thành trang trí. */
const TIENG_ON = "the server responded with a status of 409";
for (const e of errors) {
  if (e.startsWith("console: ") && e.includes(TIENG_ON)) continue;
  failures.push("lỗi trình duyệt: " + e);
}

console.log("\nPOST /batches                    ->", goi.batches.join(", ") || "(không gọi)");
console.log("PUT  /people/{id}/bank-recipient ->", goi.taiKhoan.join(", ") || "(không gọi)");
console.log("POST /batches/{id}/publish       ->", goi.publish.join(", ") || "(không gọi)");

const n = report("01 · đi hết đường sau khi bị chặn", failures);
await browser.close();
process.exit(n === 0 ? 0 : 1);
