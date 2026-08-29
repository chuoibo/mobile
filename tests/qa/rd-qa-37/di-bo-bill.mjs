/** Push six real image files through the real bill flow, in a real browser.
 *
 * This is the measurement the task asked for and the one no existing test
 * takes: `setInputFiles` on the picker `expo-image-picker` opens, then watch
 * what the person watching the phone would see -- during the wait, and after.
 *
 * What is deliberately NOT stubbed: the API (uvicorn on 9611), the model (real
 * Gemini, real key, real latency), and the client-side compression step. A
 * stubbed answer here would measure the test harness, not the product.
 *
 * Per fixture the script records: every stage line the screen showed while
 * waiting, wall-clock to first response, the request body size actually put on
 * the wire, whether any raw code / stack / JSON leaked onto the screen, and a
 * screenshot at the wait and at the end.
 */
import fs from "node:fs";
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://localhost:9612";
const ANH = process.env.ANH_DIR ?? "/tmp/rd-qa-37-anh";
const SHOT = process.env.SHOT_DIR ?? "/tmp/rd-qa-37-shots";

/** Strings that must never reach a person's screen. A bill flow that prints a
 *  stack trace has failed even when it "handled" the error. */
const RO_RI = [
  "Traceback", "ECONNREFUSED", "ENOTFOUND", "500 Internal", "Internal Server Error",
  '{"code"', '{"detail"', "sqlalchemy", "uvicorn", "generativelanguage",
  "GEMINI_API_KEY", "AIza", "undefined is not", "NaN", "[object Object]",
  // Found by this very script on gia.jpg: the stand-in for a failed decode was
  // an actual canvas element being stringified onto the page.
  "[object HTML",
];

const CA = [
  { file: "ro.jpg", nhan: "anh ro", cho: "doc duoc, ra danh sach mon" },
  { file: "mo.jpg", nhan: "anh mo", cho: "noi anh mo, moi chup lai" },
  { file: "xoay.jpg", nhan: "anh xoay EXIF=6 + GPS", cho: "hien dung chieu, doc duoc" },
  { file: "thucdon.jpg", nhan: "thuc don (khong phai bill)", cho: "noi day la bang gia" },
  { file: "gia.jpg", nhan: "van ban doi duoi .jpg", cho: "tu choi, khong sap" },
  { file: "to.jpg", nhan: "anh 4000x3000 (42MB)", cho: "hoac nen lai, hoac tu choi ro rang" },
];

const browser = await chromium.launch();
const ketQua = [];

for (const ca of CA) {
  // A fresh context per fixture. The flow has no URL, so the only honest way to
  // start from the same place twice is to start the app again -- and it also
  // stops one fixture's state from colouring the next one's screen.
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();

  const loi = [];
  const req = [];
  page.on("console", (m) => { if (m.type() === "error") loi.push(m.text().slice(0, 300)); });
  page.on("pageerror", (e) => loi.push("PAGEERROR " + String(e).slice(0, 300)));
  page.on("request", (r) => {
    if (r.url().includes("/receipts/scan") && r.method() === "POST") {
      const body = r.postDataBuffer() || Buffer.alloc(0);
      req.push({ url: r.url(), bytes: body.length });
      // Kept so the EXIF question can be asked of the bytes the browser
      // actually put on the wire, rather than of the file on disk.
      fs.writeFileSync(`${SHOT}/wire-${ca.file}.bin`, body);
    }
  });
  const phanHoi = [];
  page.on("response", async (r) => {
    if (r.url().includes("/receipts/scan")) {
      phanHoi.push({ status: r.status(), at: Date.now() });
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

  const truoc = await page.locator("body").innerText();

  // The picker is opened by the app, not by us: clicking the real button is
  // what makes this an end-to-end measurement rather than a DOM injection.
  const chooserP = page.waitForEvent("filechooser", { timeout: 15000 });
  await page.locator('[aria-label="Chọn ảnh bill"]').first().click();
  const chooser = await chooserP;
  const t0 = Date.now();
  await chooser.setFiles(`${ANH}/${ca.file}`);

  // Wait on the RESPONSE, not on the words. The first cut of this script broke
  // out as soon as the screen mentioned "món" -- which the *waiting* line
  // already says ("AI đang đọc từng món") -- so it tore the page down mid-POST
  // and recorded "KHONG GUI" for six fixtures that were all in flight. The API
  // log showed five OPTIONS preflights and zero POSTs, which is what that
  // mistake looks like from the other side.
  const xong = page
    .waitForResponse((r) => r.url().includes("/receipts/scan") && r.request().method() === "POST",
      { timeout: 120000 })
    .catch(() => null);

  // Sample the screen while it works. These frames are the answer to "what
  // does it say while you wait", which a final screenshot cannot show.
  const giaiDoan = new Set();
  let chupCho = false;
  let dung = false;
  xong.then(() => { dung = true; });
  for (let i = 0; i < 240 && !dung; i++) {
    await page.waitForTimeout(500);
    let text = "";
    try { text = await page.locator("body").innerText(); } catch { /* navigating */ }
    for (const line of text.split("\n").map((s) => s.trim()).filter(Boolean)) {
      if (/đang|chờ|xin chút|nhận diện|đọc|gửi|nén/i.test(line) && line.length < 80) {
        giaiDoan.add(line);
      }
    }
    if (!chupCho && giaiDoan.size > 0) {
      await page.screenshot({ path: `${SHOT}/bill-${ca.file}-1-dangcho.png` });
      chupCho = true;
    }
  }
  await xong;
  // The screen repaints after the response; give it the frame to do so.
  await page.waitForTimeout(4000);

  const sau = await page.locator("body").innerText();
  await page.screenshot({ path: `${SHOT}/bill-${ca.file}-2-ketqua.png`, fullPage: true });

  const trong = sau.trim().length < 15;
  const roRi = RO_RI.filter((s) => sau.includes(s));

  ketQua.push({
    ca: ca.nhan,
    file: ca.file,
    mongDoi: ca.cho,
    giay: phanHoi.length ? ((phanHoi[0].at - t0) / 1000).toFixed(1) : null,
    status: phanHoi.length ? phanHoi[0].status : "KHONG GUI",
    bytesGui: req.length ? req[0].bytes : 0,
    manTrang: trong,
    roRi,
    dangCho: [...giaiDoan],
    manHinh: sau.replace(/\n+/g, " | ").slice(0, 300),
    consoleErrors: loi.slice(0, 3),
  });

  console.log(`\n=== ${ca.nhan} (${ca.file}) ===`);
  console.log(JSON.stringify(ketQua[ketQua.length - 1], null, 1));

  await ctx.close();
}

fs.writeFileSync(`${SHOT}/ket-qua-bill.json`, JSON.stringify(ketQua, null, 2));
console.log(`\nviet: ${SHOT}/ket-qua-bill.json`);
await browser.close();
