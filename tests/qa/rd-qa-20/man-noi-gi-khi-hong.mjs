/**
 * rd-qa-20 · CÂU 3 của Lead: "Server từ chối cả câu -> màn hiện câu người đọc
 * hiểu được, không phải màn trắng hay mã lỗi thô."
 *
 * `source=none` (server từ chối vì model bịa) đã đo ở rd-qa-19 và ĐẠT. File
 * này đi nốt các đường hỏng CỨNG, vì "mã lỗi thô" thường lọt ra ở đó chứ không
 * ở đường từ chối có chủ ý: 500, 502, JSON vỡ, mất mạng, và 404 (API cũ).
 *
 * Tiêu chí ĐẠT cho mỗi ô, đọc theo mắt người dùng:
 *   - màn KHÔNG trắng (còn đọc được chữ)
 *   - có câu tiếng Việt giải thích, không phải "500" / "TypeError" / stack
 *   - nút tìm trở lại bấm được (không kẹt ở "Đang hỏi AI")
 */
import { chromium } from "playwright";
import fs from "node:fs";

const WEB = process.env.QA20_WEB ?? "http://127.0.0.1:8548";
const SHOT = "/tmp/qa20-shots";
fs.mkdirSync(SHOT, { recursive: true });

const browser = await chromium.launch();
const RAW = /TypeError|undefined is not|NetworkError|Failed to fetch|SyntaxError|Unexpected token|\bstack\b|at Object\./i;

/** Each case installs a different failure on the wire, then reads the screen. */
const CASES = [
  ["500 máy chủ lỗi", (r) => r.fulfill({ status: 500, contentType: "text/plain", body: "Internal Server Error" })],
  ["502 gateway", (r) => r.fulfill({ status: 502, contentType: "text/html", body: "<html>502 Bad Gateway</html>" })],
  ["JSON vỡ", (r) => r.fulfill({ status: 200, contentType: "application/json", body: "{not json at all" })],
  ["JSON đúng cú pháp, SAI dạng", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ hello: "world" }) })],
  ["404 API cũ (không có route)", (r) => r.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not Found" }) })],
  ["mất mạng giữa chừng", (r) => r.abort("failed")],
  ["429 quá tải", (r) => r.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ detail: "rate limited" }) })],
];

const ket = [];
for (const [ten, handler] of CASES) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  await page.goto(`${WEB}/#tab=kham-pha`, { waitUntil: "networkidle" });
  await page.route("**/places/search", handler);

  await page.getByLabel("Tìm bằng lời").fill("quán nướng ngoài trời cho 6 người");
  await page.getByRole("button", { name: /Tìm bằng AI|Đang hỏi AI/ }).click();

  let timeout = false;
  try {
    await page.waitForFunction(
      () => !/Đang hỏi AI/.test(document.body.innerText),
      { timeout: 25000 },
    );
  } catch {
    timeout = true;
  }
  await page.waitForTimeout(500);

  const body = await page.evaluate(() => document.body.innerText);
  const dong = body.split("\n").map((s) => s.trim()).filter(Boolean);
  const slug = ten.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  await page.screenshot({ path: `${SHOT}/e-${slug}.png`, fullPage: true });

  // Did the app get back to a usable state?
  const nutLai = await page
    .getByRole("button", { name: /Tìm bằng AI/ })
    .isEnabled()
    .catch(() => false);

  const manTrang = dong.length < 4;
  const thoRa = dong.filter((d) => RAW.test(d));
  // The screen's own message: lines after the header block, before the tab bar.
  const cauNoi = dong.slice(6).filter((d) => !/^(Khám phá|Lên plan|Tin nhắn|Cá nhân)$/.test(d));

  const dat = !manTrang && thoRa.length === 0 && !timeout && nutLai;
  console.log(`\n${"=".repeat(70)}\n${ten}  ->  ${dat ? "ĐẠT" : "CẦN XEM"}\n${"=".repeat(70)}`);
  console.log(`  màn trắng?        ${manTrang ? "CÓ" : "không"}`);
  console.log(`  kẹt 'Đang hỏi AI'? ${timeout ? "CÓ" : "không"}`);
  console.log(`  nút tìm bấm lại được? ${nutLai ? "CÓ" : "KHÔNG"}`);
  console.log(`  mã lỗi thô lọt ra? ${thoRa.length ? JSON.stringify(thoRa) : "không"}`);
  console.log(`  màn nói: ${cauNoi.slice(0, 4).map((s) => `\n     "${s}"`).join("")}`);
  if (errs.length) console.log(`  pageerror: ${errs.slice(0, 2).join(" | ")}`);

  ket.push({ ten, dat, manTrang, timeout, nutLai, thoRa, cauNoi: cauNoi.slice(0, 4) });
  await ctx.close();
}

await browser.close();
fs.writeFileSync("/tmp/qa20-loi.json", JSON.stringify(ket, null, 2));
const hong = ket.filter((k) => !k.dat);
console.log(`\n${"#".repeat(70)}`);
console.log(`TỔNG: ${ket.length - hong.length}/${ket.length} ô ĐẠT`);
if (hong.length) console.log(`CẦN XEM: ${hong.map((h) => h.ten).join(", ")}`);
console.log(`ảnh: ${SHOT}`);
