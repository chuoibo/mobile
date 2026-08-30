// The "Bỏ qua" path: skip the login screen entirely, so the app holds no
// person, then search. #158 says this must answer without a round trip. Both
// halves matter -- the sentence on screen AND zero requests on the wire.
import { chromium } from "playwright-core";
import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";

const CHROME = timTrinhDuyet();
const url = process.argv[2];
const label = process.argv[3] ?? "?";

const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

const calls = [];
page.on("request", (r) => {
  if (r.url().includes("/places/search")) calls.push(r.url());
});

await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

await page.locator('text="Bỏ qua"').first().click();
await page.waitForTimeout(1500);
console.log(
  `\n===== [${label}] sau khi Bỏ qua =====\n` +
    (await page.evaluate(() => document.body.innerText.slice(0, 400))),
);

const box = page.locator('input[type="text"], input:not([type]), textarea').first();
await box.waitFor({ timeout: 10000 });
await box.click();
await box.fill("quán nướng ngoài trời cho 6 người dưới 300k");
await page.keyboard.press("Enter");
// Generous on purpose: if it DID go to the network, this is long enough for
// the model to answer, so a quiet wire here is a real absence of a request.
await page.waitForTimeout(12000);

console.log(
  `\n===== [${label}] SAU KHI TÌM =====\n` +
    (await page.evaluate(() => document.body.innerText.slice(0, 900))),
);
console.log(`\n[${label}] số request tới /places/search: ${calls.length}`);
await page.screenshot({ path: `/tmp/qa23-${label}.png` });
await browser.close();
