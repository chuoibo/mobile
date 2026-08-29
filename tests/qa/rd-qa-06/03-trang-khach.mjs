/* rd-qa-06 step 3-5 · QR, trang khách, và vòng báo-đã-chuyển → xác nhận.
 *
 * Order matters and is the point. For every leak check the harness first
 * asserts the thing that SHOULD be on the page (this guest's own amount and
 * name). A bare `!includes(...)` passes on a blank page, on a 404, and on a
 * page that prints money in a different format -- rd-qa-05 wrote that trap
 * down and this file obeys it.
 */
import { writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { phone, typeInto, text, toManualForm, report, API, leakProblems, qrProblems } from "./lib.mjs";

const failures = [];
const { browser, page, errors } = await phone();
const people = [];
let publish = null;
page.on("response", async (r) => {
  const m = r.url().match(/\/people\/([0-9a-f-]{36})$/);
  if (m && r.request().method() === "PUT") people.push(m[1]);
  if (/publish/.test(r.url()) && r.status() < 300) { try { publish = JSON.parse(await r.text()); } catch {} }
});

// ---- đi tới lúc phát đợt thu ----------------------------------------------
await toManualForm(page);
for (const n of ["Hà", "Nam", "Linh"]) {
  await typeInto(page, page.getByPlaceholder("Hà"), n);
  await page.getByRole("button", { name: /^Thêm$/ }).click();
  await page.waitForTimeout(200);
}
await typeInto(page, page.getByPlaceholder("bữa lẩu tối thứ bảy"), "lẩu gà lá é");
await page.getByRole("radio", { name: /^Hà$/ }).first().click();
await typeInto(page, page.getByPlaceholder("480000"), "480001");
await page.getByRole("button", { name: /^Chia tiền$/ }).click();
await page.waitForTimeout(3000);
await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/ }).click();
await page.waitForTimeout(3500);
const adv = people[0];
await fetch(`${API}/people/${adv}/bank-recipient`, {
  method: "PUT",
  headers: { "Content-Type": "application/json", "X-Actor-ID": adv, "X-Actor-Roles": "member,advancer,recipient,batch_owner", "Idempotency-Key": `qa06-bank-${adv}` },
  body: JSON.stringify({ bank_bin: "970418", account_number: "0000000000TEST", account_name: "NGUOI UNG TIEN" }),
});
await page.getByRole("button", { name: /Đúng rồi, ghi vào sổ/ }).click();
await page.waitForTimeout(4000);
await page.getByRole("button", { name: /Phát đợt thu/ }).click();
await page.waitForTimeout(5000);

if (publish === null) { failures.push("không bắt được phản hồi publish"); report("03", failures); await browser.close(); process.exit(1); }
const links = publish.guest_links;
console.log(`publish: ${links.length} link khách, hết hạn ${links[0].expires_at}`);

// ---- 3. MÃ QR: có vẽ ra không, và giải mã ra có đúng số tiền không? -------
console.log("\n== 3. mã QR ==");
const qrCard = page.locator('div').filter({ hasText: /^VIETQR · NAPAS 247$/ }).last()
  .locator('xpath=ancestor::div[1]');
await qrCard.scrollIntoViewIfNeeded().catch(() => {});
await page.waitForTimeout(500);
const cardCount = await qrCard.count();
if (cardCount === 0) failures.push("MÃ QR KHÔNG VẼ RA: không thấy thẻ VIETQR nào trên màn kết quả");
else {
  const bb = await qrCard.first().boundingBox();
  console.log(`thẻ VIETQR: ${bb ? Math.round(bb.width) + "x" + Math.round(bb.height) : "không đo được"}pt`);
  await qrCard.first().screenshot({ path: "/tmp/qa06/qr.png", scale: "device" });
  const decoded = execFileSync("python3", ["-c", `
import cv2
img = cv2.imread("/tmp/qa06/qr.png")
d = cv2.QRCodeDetector()
data, pts, _ = d.detectAndDecode(img)
print(data if data else "")
`]).toString().trim();
  console.log("giải mã được:", decoded ? decoded.slice(0, 90) + "…" : "(KHÔNG GIẢI MÃ ĐƯỢC)");
  const known = links.flatMap((l) => l.obligations.map((o) => o.vietqr_payload));
  const qp = qrProblems(decoded, known, "160000");
  if (qp.length === 0) console.log("khớp đúng payload máy chủ đã gửi về ✓  số tiền mã hoá: 160000");
  failures.push(...qp);
}

// ---- 4. TRANG KHÁCH: mỗi người chỉ thấy phần của mình --------------------
console.log("\n== 4. trang khách ==");
const NAMES = { }; // sender_id -> tên hiển thị, đọc ra từ chính trang của họ
async function guestText(path) {
  const r = await fetch(API + path, { headers: { Accept: "text/html" } });
  const html = await r.text();
  const plain = html
    .replace(/<script[\s\S]*?<\/script>/g, " ")
    .replace(/<style[\s\S]*?<\/style>/g, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&[a-z]+;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return { status: r.status, plain, html };
}
const pages = [];
for (const l of links) {
  const g = await guestText(l.path);
  const who = (g.plain.match(/Phần của ([^\s]+(?: [^\s]+)?) trong/) ?? [])[1] ?? "?";
  NAMES[l.sender_id] = who;
  pages.push({ link: l, ...g, who });
  console.log(`  ${l.path.slice(0, 14)}… -> ${g.status}, "Phần của ${who}"`);
}
const OTHER_TOTALS = ["480.001", "160.001"]; // tổng nhóm và phần của người ứng tiền
for (const p of pages) {
  failures.push(...leakProblems({
    who: p.who, plain: p.plain, html: p.html, ownAmount: "160.000",
    otherNames: pages.filter((q) => q !== p).map((q) => q.who),
    forbiddenAmounts: OTHER_TOTALS,
  }));
}
console.log(`  tên đọc được: ${JSON.stringify(Object.values(NAMES))}`);

// ---- token sai, token đổi, token hết hạn ---------------------------------
console.log("\n== token xấu ==");
const good = links[0].path.split("/g/")[1];
const flip = good.slice(0, -1) + (good.slice(-1) === "A" ? "B" : "A");
const cases = [
  ["đổi 1 ký tự cuối", "/g/" + flip],
  ["token bịa đúng dạng", "/g/" + "z".repeat(43)],
  ["token quá ngắn", "/g/abc"],
  ["ký tự lạ", "/g/" + "a".repeat(40) + "%3Cscript%3E"],
];
for (const [name, path] of cases) {
  const g = await guestText(path);
  const leaks = /160\.000|480\.001|NGUOI UNG TIEN|0000000000TEST/.test(g.plain);
  console.log(`  ${name.padEnd(24)} -> ${g.status}${leaks ? "  ⚠ CÓ DỮ LIỆU" : ""}`);
  if (g.status === 200) failures.push(`${name} trả 200 thay vì từ chối`);
  if (leaks) failures.push(`${name} rò dữ liệu thật ra trang lỗi`);
}

// ---- 5. khách báo đã chuyển -> người nhận xác nhận ------------------------
console.log("\n== 5. báo đã chuyển + xác nhận ==");
const gp = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const gpage = await gp.newPage();
await gpage.goto(API + links[0].path, { waitUntil: "domcontentloaded" });
await gpage.waitForTimeout(900);
// Trang khách giấu phần chuyển tiền sau một bước: "Đúng, xem cách chuyển".
const moRa = gpage.getByRole("button", { name: /Đúng, xem cách chuyển/ });
if (await moRa.count() > 0) { await moRa.first().click(); await gpage.waitForTimeout(1200); }
const gtext = (await gpage.locator("body").innerText()).replace(/\s+/g, " ");
const guestCaveat = /Khoản chỉ đóng khi họ xác nhận|chỉ để .* biết mà đối chiếu/.test(gtext);
console.log("  trang khách nói rõ báo ≠ tiền về:", guestCaveat ? "CÓ" : "KHÔNG");
if (!guestCaveat) failures.push("trang khách KHÔNG nói rõ 'tôi đã chuyển' chỉ là lời khai");
await gpage.getByRole("button", { name: /Tôi đã chuyển/ }).click();
await gpage.waitForTimeout(1500);
const after = (await gpage.locator("body").innerText()).replace(/\s+/g, " ");
console.log("  sau khi báo:", after.slice(0, 220));

// người nhận: quay lại màn đợt thu, đọc lại, bấm "Tiền đã về"
await page.getByRole("button", { name: /Hoàn tất|Quay lại/ }).first().click();
await page.waitForTimeout(1500);
await page.getByRole("button", { name: /Đọc lại từ máy chủ/ }).click();
await page.waitForTimeout(2500);
const board = await text(page);
console.log("  bảng đợt thu:", board.slice(board.indexOf("gửi") - 40, board.indexOf("gửi") + 260));
const claimWords = /đã nói đã chuyển|khai đã chuyển|chưa xác nhận|chờ xác nhận|báo đã chuyển/i.test(board);
console.log("  màn người nhận phân biệt 'khách khai' với 'tiền đã về':", claimWords ? "CÓ" : "KHÔNG");

const tienVe = page.getByRole("button", { name: /Tiền đã về/ }).first();
if (await tienVe.count() > 0) {
  await tienVe.click();
  await page.waitForTimeout(2500);
  const done = await text(page);
  console.log("  sau khi xác nhận:", done.slice(done.indexOf("gửi") - 40, done.indexOf("gửi") + 200));
  const caveat = /không phải bằng chứng|không phải xác nhận của ngân hàng|ngân hàng/i.test(done);
  console.log("  màn người nhận có nói 'đây không phải bằng chứng ngân hàng':", caveat ? "CÓ" : "KHÔNG");
  if (!caveat) failures.push("màn đợt thu ghi 'đã nhận' mà KHÔNG nói đó là lời một người, không phải xác nhận ngân hàng");
} else failures.push("không thấy nút 'Tiền đã về' sau khi khách báo đã chuyển");

if (errors.length) console.log("\nJS ERR:", errors.slice(0, 6));
await page.screenshot({ path: "/tmp/qa06/07-cuoi.png", fullPage: true });
writeFileSync("/tmp/qa06/publish.json", JSON.stringify(publish, null, 1));
const n = report("03 · QR + trang khách + xác nhận", failures);
await browser.close();
process.exit(n === 0 ? 0 : 1);
