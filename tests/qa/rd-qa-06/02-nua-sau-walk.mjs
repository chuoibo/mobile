/* rd-qa-06 step 2-3 · Chia tiền -> đợt thu -> publish, đi bằng tay trên màn.
 *
 * Law 2 is measured on the SCREEN here, not on the API: read every per-person
 * figure the screen prints, add them up in the harness, and require the sum to
 * equal the total the same screen prints. The API being right is a different
 * claim, already covered at the HTTP layer.
 */
import { phone, typeInto, text, toManualForm, report, API, sumProblems } from "./lib.mjs";

const TOTAL = process.env.TOTAL ?? "480001";
const { browser, page, errors } = await phone();
const failures = [];
const people = [];   // ids in the order they were registered
const net = [];
page.on("response", (r) => {
  const u = r.url();
  if (/_expo|favicon|\.ico$/.test(u)) return;
  net.push(`${r.status()} ${r.request().method()} ${u.replace(API, "")}`);
  const m = u.match(/\/people\/([0-9a-f-]{36})$/);
  if (m && r.request().method() === "PUT") people.push(m[1]);
});

await toManualForm(page);
for (const n of ["Hà", "Nam", "Linh"]) {
  await typeInto(page, page.getByPlaceholder("Hà"), n);
  await page.getByRole("button", { name: /^Thêm$/ }).click();
  await page.waitForTimeout(200);
}
await typeInto(page, page.getByPlaceholder("bữa lẩu tối thứ bảy"), "lẩu gà lá é");
await page.getByRole("radio", { name: /^Hà$/ }).first().click();
await typeInto(page, page.getByPlaceholder("480000"), TOTAL);
await page.waitForTimeout(300);
await page.getByRole("button", { name: /^Chia tiền$/ }).click();
await page.waitForTimeout(3500);

// ---- LUẬT TIỀN 2, ĐO TRÊN MÀN HÌNH ----------------------------------------
const deXuat = await text(page);
console.log("MÀN ĐỀ XUẤT:\n" + deXuat.slice(0, 600) + "\n");
const vnd = (s) => Number(s.replace(/\./g, ""));
// Every "<name> <amount>đ" row the screen prints, minus the "Tổng" row.
const rows = [...deXuat.matchAll(/(Hà \(trả trước\)|Nam|Linh)\s+([\d.]+)đ/g)]
  .map((m) => ({ who: m[1], amount: vnd(m[2]) }));
const shown = [...deXuat.matchAll(/Tổng\s+([\d.]+)đ/g)].map((m) => vnd(m[1]));
const tongTrenMan = shown[0];
const sum = rows.reduce((a, r) => a + r.amount, 0);
console.log("dòng đọc được:", JSON.stringify(rows));
console.log(`Σ trên màn = ${sum}   |   Tổng in trên màn = ${tongTrenMan}   |   gõ vào = ${vnd(TOTAL)}`);
failures.push(...sumProblems(rows, tongTrenMan, vnd(TOTAL)));

// ---- ĐỢT THU: cửa chặn khi người ứng tiền chưa có tài khoản nhận ----------
await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/ }).click();
await page.waitForTimeout(4000);
const chan = await text(page);
const bloqued = /chưa có tài khoản nhận/.test(chan);
console.log(`\ncửa chặn tài khoản nhận: ${bloqued ? "CÓ, và nói ra" : "KHÔNG"}`);
if (!bloqued) failures.push("mở đợt thu KHÔNG bị chặn dù người ứng tiền chưa có tài khoản nhận");

// Người dùng thật KHÔNG có đường nào đi tiếp từ đây: app không có màn nào ghi
// tài khoản nhận. Bộ đo gọi thẳng route thật của sản phẩm để đo được phần còn
// lại -- và đó chính là phát hiện, không phải cách vòng qua nó.
const advancer = people[0];
const put = await fetch(`${API}/people/${advancer}/bank-recipient`, {
  method: "PUT",
  headers: { "Content-Type": "application/json", "X-Actor-ID": advancer, "X-Actor-Roles": "member,advancer,recipient,batch_owner", "Idempotency-Key": `qa06-bank-${advancer}` },
  body: JSON.stringify({ bank_bin: "970418", account_number: "0000000000TEST", account_name: "NGUOI UNG TIEN" }),
});
console.log(`PUT /people/${advancer}/bank-recipient -> ${put.status}`);
if (put.status >= 400) { console.log(await put.text()); failures.push("không seed nổi tài khoản nhận qua route thật"); }

await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/ }).click();
await page.waitForTimeout(4500);
console.log("\nMÀN ĐỢT THU:\n" + (await text(page)).slice(0, 900));
const btns = await page.locator('[role="button"], button').all();
console.log("\nNÚT:");
for (const e of btns.slice(0, 25)) if (await e.isVisible().catch(()=>false))
  console.log("  " + ((await e.getAttribute("aria-label")) ?? (await e.innerText().catch(()=>""))).replace(/\n/g," / ").slice(0,90));
console.log("\nNET:\n" + net.join("\n"));
if (errors.length) console.log("\nJS ERR:", errors.slice(0,5));
await page.screenshot({ path: "/tmp/qa06/04-dotthu.png" });
const n = report("02 · chia tiền + mở đợt thu", failures);
await browser.close();
process.exit(n === 0 ? 0 : 1);
