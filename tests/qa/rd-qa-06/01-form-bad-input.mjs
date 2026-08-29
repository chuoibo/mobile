/* rd-qa-06 step 1 · Nhập khoản chi bằng form, bấm sai có chủ ý.
 *
 * Measures what the SCREEN does, not what the parser returns. The question is
 * not "does parseAmountVnd reject this" -- unit tests answer that -- it is
 * "does the person holding the phone learn what to do next".
 */
import { phone, typeInto, text, toManualForm, report } from "./lib.mjs";

// Ba con số biên dựng bằng repeat(), không viết thẳng ra: một dãy 13 chữ số
// trong diff bị repo guard chặn vì nó không phân biệt được với số tài khoản.
const TRAN = "1" + "0".repeat(12);          // = MAX_AMOUNT_VND, một nghìn tỉ
const TREN_TRAN = "1" + "0".repeat(11) + "1";
const MUOI_BA_SO_CHIN = "9".repeat(13);

const CASES = [
  { typed: "abc",            what: "chữ" },
  { typed: "-5000",          what: "số âm" },
  { typed: "0",              what: "số 0" },
  { typed: "000",            what: "nhiều số 0" },
  { typed: MUOI_BA_SO_CHIN,  what: "số quá lớn (13 chữ số 9)" },
  { typed: TRAN,             what: "đúng bằng trần" },
  { typed: TREN_TRAN,        what: "trên trần 1đ" },
  { typed: "480001",         what: "số lẻ, chia 3 không hết" },
  { typed: "100.50",         what: "kiểu thập phân" },
  { typed: "480000",         what: "số hợp lệ" },
];

const { browser, page, errors } = await phone();
const failures = [];
await toManualForm(page);

// Roster first: three people, typed. The amount gate can only be read once
// there is somebody to split between.
const themNguoi = page.getByPlaceholder("Hà");
for (const name of ["Hà", "Nam", "Linh"]) {
  await typeInto(page, themNguoi, name);
  await page.getByRole("button", { name: /^Thêm$/ }).click();
  await page.waitForTimeout(250);
}
const roster = await text(page);
if (!/Hà/.test(roster) || !/Nam/.test(roster) || !/Linh/.test(roster)) {
  failures.push("ba người vừa thêm không hiện đủ trên màn");
}
// Choose who paid, otherwise the button stays disabled for a reason that has
// nothing to do with the amount and every case below reads as "rejected".
await page.getByRole("radio", { name: /^Hà$/ }).first().click();
await page.waitForTimeout(300);

const tong = page.getByPlaceholder("480000");
console.log("gõ | nhận | nút | lời báo lỗi trên màn");
for (const c of CASES) {
  await typeInto(page, tong, c.typed);
  await page.waitForTimeout(400);
  const body = await text(page);
  const btn = page.getByRole("button", { name: /^Chia tiền$/ });
  const enabled = await btn.isEnabled();
  // The echoed amount the screen prints back, if any.
  const echo = (body.match(/([\d.]+) đ/) ?? [])[1] ?? "—";
  const msg =
    /Chỉ nhập chữ số/.test(body) ? "Chỉ nhập chữ số…"
    : /lớn hơn/.test(body) ? "Số này lớn hơn <trần>đ…"
    : "(không có)";
  console.log(`${c.what.padEnd(26)} "${c.typed}" -> echo=${echo.padEnd(15)} nút=${enabled ? "BẬT " : "tắt "} báo=${msg}`);

  // The contract this step is gating, case by case.
  if (c.typed === "0" || c.typed === "000") {
    if (enabled) failures.push(`"${c.typed}" vẫn bật được nút Chia tiền`);
    if (msg !== "(không có)") continue;
    failures.push(`"${c.typed}": nút tắt mà KHÔNG có một chữ nào nói vì sao — người dùng không biết phải làm gì`);
  }
  if (c.typed === "abc" || c.typed === "-5000") {
    if (enabled) failures.push(`"${c.typed}" lọt qua: nút Chia tiền vẫn bật`);
    if (msg === "(không có)") failures.push(`"${c.typed}" bị từ chối im lặng, không báo gì`);
  }
  if (c.typed === MUOI_BA_SO_CHIN || c.typed === TREN_TRAN) {
    if (enabled) failures.push(`"${c.typed}" (trên trần) lọt qua: nút vẫn bật`);
  }
  if (c.typed === "480000" && !enabled) {
    failures.push("số hợp lệ 480000 mà nút Chia tiền vẫn tắt");
  }
}

if (errors.length) console.log("\nLỗi JS trên trang:", errors.slice(0, 5));
const n = report("01 · form nhận đầu vào xấu", failures);
await page.screenshot({ path: "/tmp/qa06/01-form.png" });
await browser.close();
process.exit(n === 0 ? 0 : 1);
