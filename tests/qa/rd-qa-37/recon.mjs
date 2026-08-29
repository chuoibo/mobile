/** Find the way from a cold load to the bill camera, and prove the app booted.
 *
 * Written before the real walk because the flow has no URL for the expense
 * screens -- `lien-ket.ts` names tabs and entry doors, not `chup-bill` -- so
 * the path there is a sequence of taps that has to be discovered once and then
 * pinned. Printing the accessible names at each step is what makes the next
 * script's selectors quotable rather than guessed.
 */
import { chromium } from "playwright";

const WEB = process.env.WEB_URL ?? "http://localhost:9612";
const SHOT = process.env.SHOT_DIR ?? "/tmp/rd-qa-37-shots";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

const loi = [];
page.on("console", (m) => { if (m.type() === "error") loi.push(m.text().slice(0, 200)); });
page.on("pageerror", (e) => loi.push("PAGEERROR " + String(e).slice(0, 200)));

async function ten() {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll('[role="button"],button,[role="tab"],[role="link"]'))
      .map((e) => (e.getAttribute("aria-label") || e.textContent || "").trim())
      .filter((s) => s.length > 0 && s.length < 90)
  );
}

await page.goto(WEB, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
console.log("--- man 1 (co dinh) ---");
console.log(JSON.stringify(await ten(), null, 1));
await page.screenshot({ path: `${SHOT}/recon-1-modau.png` });

// "Bỏ qua" enters the shell with nguoi=null, which AppRoot treats as a real state.
const boQua = page.getByText(/Bỏ qua/i).first();
if (await boQua.count()) {
  await boQua.click();
  await page.waitForTimeout(1000);
}
console.log("--- man 2 (sau Bo qua) ---");
console.log(JSON.stringify(await ten(), null, 1));
await page.screenshot({ path: `${SHOT}/recon-2-shell.png` });

// The centre [+] is the only way into the expense flow.
const cong = page.locator('[aria-label*="Tạo"], [aria-label*="tạo"]').first();
if (await cong.count()) {
  await cong.click();
  await page.waitForTimeout(800);
  console.log("--- man 3 (menu tao) ---");
  console.log(JSON.stringify(await ten(), null, 1));
  await page.screenshot({ path: `${SHOT}/recon-3-menu.png` });

  const khoanChi = page.getByText(/khoản chi/i).first();
  if (await khoanChi.count()) {
    await khoanChi.click();
    await page.waitForTimeout(1200);
    console.log("--- man 4 (chup bill?) ---");
    console.log(JSON.stringify(await ten(), null, 1));
    console.log("--- text tren man ---");
    console.log((await page.locator("body").innerText()).slice(0, 700));
    await page.screenshot({ path: `${SHOT}/recon-4-chupbill.png` });
    console.log("--- co input[type=file] khong? ---");
    console.log("count:", await page.locator('input[type="file"]').count());
  }
}

console.log("--- console errors ---");
console.log(loi.length ? JSON.stringify(loi, null, 1) : "(none)");
await browser.close();
