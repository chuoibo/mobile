/** Push exactly the fixtures named on the command line, once each, in order.
 *
 * Exists because the first EXIF capture was read back after later runs had
 * already renumbered the tap's output, so two files that were supposed to be
 * different fixtures were both the last one written. Naming the fixtures and
 * writing the mapping out alongside the bodies is what makes the capture
 * quotable afterwards.
 *
 *   node mot-anh.mjs xoay.jpg ro.jpg
 */
import fs from "node:fs";
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://localhost:9612";
const ANH = process.env.ANH_DIR ?? "/tmp/rd-qa-37-anh";
const SHOT = process.env.SHOT_DIR ?? "/tmp/rd-qa-37-shots";
const files = process.argv.slice(2);

const browser = await chromium.launch();
const banDo = [];

for (const file of files) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await ctx.newPage();
  const res = [];
  page.on("response", (r) => {
    if (r.url().includes("/receipts/scan") && r.request().method() === "POST") res.push(r.status());
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

  await Promise.race([
    page.waitForResponse((r) => r.url().includes("/receipts/scan") && r.request().method() === "POST",
      { timeout: 90000 }).catch(() => null),
    page.waitForTimeout(30000),
  ]);
  await page.waitForTimeout(3000);

  const text = await page.locator("body").innerText();
  await page.screenshot({ path: `${SHOT}/mot-${file}.png`, fullPage: true });
  banDo.push({ file, status: res[0] ?? "KHONG GUI", man: text.replace(/\n+/g, " | ").slice(0, 200) });
  console.log(`${file}: ${res[0] ?? "KHONG GUI"}`);
  await ctx.close();
}

fs.writeFileSync(`${SHOT}/ban-do-wire.json`, JSON.stringify(banDo, null, 2));
console.log("\nthu tu gui (scan-01.bin = fixture dau tien):");
banDo.forEach((b, i) => console.log(`  scan-${String(i + 1).padStart(2, "0")}.bin = ${b.file}  -> ${b.status}`));
await browser.close();
