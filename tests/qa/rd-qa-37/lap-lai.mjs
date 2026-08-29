/** Two things a single run cannot settle, run enough times to settle them.
 *
 * A. `gia.jpg` -- text bytes wearing a .jpg extension -- put the literal string
 *    "[object HTMLCanvasElement]" on the screen. One sighting is an anecdote;
 *    this repeats it and captures what was actually thrown, so the ticket names
 *    a cause rather than a symptom.
 *
 * B. `ro.jpg` -- a legible bill -- came back 422 "unreadable" while a nearly
 *    identical re-encode of the same bill came back 200 with all five items and
 *    the right total. Both arrived at the server as 900x1200 JPEGs of the same
 *    document. That is the model disagreeing with itself, and the only honest
 *    way to report it is a rate, not a verdict from n=1.
 */
import fs from "node:fs";
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://localhost:9612";
const ANH = process.env.ANH_DIR ?? "/tmp/rd-qa-37-anh";
const SHOT = process.env.SHOT_DIR ?? "/tmp/rd-qa-37-shots";
const LAN_GIA = Number(process.env.LAN_GIA ?? 3);
const LAN_RO = Number(process.env.LAN_RO ?? 5);

const browser = await chromium.launch();

async function chay(file, i) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();

  const nem = [];
  page.on("pageerror", (e) => nem.push(String(e).slice(0, 200)));
  page.on("console", (m) => { if (m.type() === "error") nem.push("console: " + m.text().slice(0, 200)); });

  // Catch the value the flow throws, at the boundary, without touching product
  // code: wrap the global so anything rejected is described before React turns
  // it into a string.
  await page.addInitScript(() => {
    window.__nem = [];
    window.addEventListener("unhandledrejection", (e) => {
      const r = e.reason;
      window.__nem.push({
        laError: r instanceof Error,
        ctor: r?.constructor?.name ?? typeof r,
        chuoi: String(r).slice(0, 120),
        message: r?.message?.slice?.(0, 120) ?? null,
      });
    });
  });

  const res = [];
  page.on("response", (r) => {
    if (r.url().includes("/receipts/scan") && r.request().method() === "POST") {
      res.push(r.status());
    }
  });

  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.getByText(/Bỏ qua/i).first().click();
  await page.waitForTimeout(700);
  await page.locator('[aria-label="Tạo mới"]').first().click();
  await page.waitForTimeout(500);
  await page.getByText(/Tạo khoản chi/i).first().click();
  await page.waitForTimeout(900);

  const chooserP = page.waitForEvent("filechooser", { timeout: 15000 });
  await page.locator('[aria-label="Chọn ảnh bill"]').first().click();
  (await chooserP).setFiles(`${ANH}/${file}`);

  const xong = page.waitForResponse(
    (r) => r.url().includes("/receipts/scan") && r.request().method() === "POST",
    { timeout: 90000 }).catch(() => null);
  await Promise.race([xong, page.waitForTimeout(25000)]);
  await page.waitForTimeout(3000);

  const text = await page.locator("body").innerText();
  const nemJs = await page.evaluate(() => window.__nem ?? []);
  await page.screenshot({ path: `${SHOT}/lap-${file}-${i}.png` });
  await ctx.close();

  return {
    lan: i,
    status: res.length ? res[0] : "KHONG GUI",
    coRac: /\[object \w+\]/.test(text),
    rac: (text.match(/\[object \w+\]/g) || [])[0] ?? null,
    doc5Mon: /Đã nhận diện \d+ món/.test(text),
    tong: (text.match(/(\d[\d.]*)đ/) || [])[0] ?? null,
    manCuoi: (text.match(/(Chưa đọc được[^|]*|Ảnh bill quá mờ[^|]*|Đã nhận diện[^|]*|Đây là thực đơn[^|]*)/) || [])[0]?.slice(0, 70) ?? null,
    nemJs: nemJs.slice(0, 2),
  };
}

const kq = { gia: [], ro: [] };
for (let i = 1; i <= LAN_GIA; i++) {
  const r = await chay("gia.jpg", i);
  kq.gia.push(r);
  console.log(`gia.jpg #${i}: rac=${r.rac} status=${r.status} nem=${JSON.stringify(r.nemJs)}`);
}
for (let i = 1; i <= LAN_RO; i++) {
  const r = await chay("ro.jpg", i);
  kq.ro.push(r);
  console.log(`ro.jpg #${i}: status=${r.status} doc-duoc=${r.doc5Mon} tong=${r.tong} -> ${r.manCuoi}`);
}

fs.writeFileSync(`${SHOT}/ket-qua-lap.json`, JSON.stringify(kq, null, 2));

console.log("\n================ KET LUAN ================");
const racLan = kq.gia.filter((r) => r.coRac).length;
console.log(`A. gia.jpg in rac ra man: ${racLan}/${LAN_GIA} lan  (${kq.gia[0]?.rac ?? "-"})`);
const ok = kq.ro.filter((r) => r.status === 200).length;
console.log(`B. ro.jpg (BILL Y HET NHAU, ${LAN_RO} lan): ${ok} lan 200, ${LAN_RO - ok} lan 422`);
console.log(`   -> ${ok > 0 && ok < LAN_RO ? "KHONG TAT DINH: cung mot anh, hai ket qua" :
  ok === LAN_RO ? "on dinh 200" : "on dinh 422"}`);
await browser.close();
