// Walk the Kham Pha search box like a person, on whichever bundle is served at
// argv[2], and record BOTH sides: what went on the wire to POST /places/search
// (status, and whether X-Actor-ID rode along) and what the screen ended up
// saying. The two together are the point -- a screen that says "server error"
// while the wire says 401 is the #158 bug, and neither half shows it alone.
import { chromium } from "playwright-core";
import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";

const CHROME = timTrinhDuyet();
const url = process.argv[2];
const label = process.argv[3] ?? "?";
const query = process.argv[4] ?? "quán nướng ngoài trời cho 6 người dưới 300k";

const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

const calls = [];
page.on("request", (r) => {
  if (r.url().includes("/places/search")) {
    const h = r.headers();
    calls.push({
      phase: "request",
      actorHeader: h["x-actor-id"] ?? null,
      body: (r.postData() || "").slice(0, 120),
    });
  }
});
page.on("response", async (r) => {
  if (r.url().includes("/places/search")) {
    let body = "";
    try {
      body = (await r.text()).slice(0, 160);
    } catch {
      body = "<unreadable>";
    }
    calls.push({ phase: "response", status: r.status(), body });
  }
});
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));

const step = async (name) => {
  await page.waitForTimeout(900);
  const t = await page.evaluate(() => document.body.innerText.slice(0, 900));
  console.log(`\n===== [${label}] ${name} =====\n${t}`);
};

const clickText = async (text) => {
  const el = page.locator(`text=${text}`).first();
  await el.waitFor({ timeout: 10000 });
  await el.click();
};

await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

// Google is not wired to a real IdP; the button opens the seeded person picker.
await clickText("Đăng ký với Google");
await step("sau khi bấm Google");

// Any seeded person will do -- which one does not matter here, only that the
// app now holds a personId it could put in the header.
// Scoped to the dialog and exact: a bare "Minh" also matches the tagline
// "chia bill thông minh" on the screen behind it.
const nguoi = page
  .locator('[role="dialog"]')
  .getByText("Minh", { exact: true })
  .first();
await nguoi.waitFor({ timeout: 10000 });
await nguoi.click();
console.log(`\n[${label}] đã chọn người: Minh`);
await step("sau khi chọn người");

// Kham Pha is the discovery tab that owns the search box.
try {
  await clickText("Khám phá");
} catch {
  console.log(`[${label}] không thấy tab "Khám phá"`);
}
await step("màn Khám phá");

const box = page
  .locator('input[type="text"], input:not([type]), textarea')
  .first();
await box.waitFor({ timeout: 10000 });
await box.click();
await box.fill(query);
await page.keyboard.press("Enter");

// The route calls a real model, so this waits on the answer, not on a guess.
await page.waitForTimeout(12000);
await step("SAU KHI TÌM");

console.log(`\n===== [${label}] WIRE =====`);
if (calls.length === 0) console.log("KHÔNG có request nào tới /places/search");
for (const c of calls) console.log(JSON.stringify(c));
if (errors.length) console.log(`[${label}] pageerror: ${errors.join(" | ")}`);

await page.screenshot({ path: `/tmp/qa23-${label}.png`, fullPage: false });
await browser.close();
