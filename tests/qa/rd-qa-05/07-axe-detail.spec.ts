import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/** Control: prove axe actually fails on a planted defect on THIS page.
 *  A "0 violations" result is worthless until this test is red. */
test("chứng minh axe còn sống — trồng một lỗi vào chính trang này", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  const before = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
  console.log("  trước khi trồng lỗi:", before.violations.length, "vi phạm");

  await page.evaluate(() => {
    const img = document.createElement("img");
    // A real path, not a data: URI -- the repo guard fails closed on base64.
    // axe checks for a missing alt attribute, not whether the bytes load.
    img.src = "/favicon.ico";
    document.body.appendChild(img); // no alt -> WCAG 1.1.1
    const btn = document.createElement("button");
    document.body.appendChild(btn); // no accessible name -> WCAG 4.1.2
  });

  const after = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
  console.log("  sau khi trồng lỗi:  ", after.violations.length, "vi phạm ->",
    after.violations.map((v) => v.id).join(", "));
  expect(after.violations.length, "axe KHÔNG bắt được lỗi trồng sẵn => mọi số 0 ở trên là giả").toBeGreaterThan(before.violations.length);
});

test("chi tiết vi phạm trên vỏ 5 tab", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: /Đăng nhập bằng số điện thoại/ }).click();
  await page.getByRole("button", { name: "Vào app với tư cách Minh" }).click();
  await expect(page.getByRole("tablist")).toBeVisible();

  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag22aa"]).analyze();
  for (const v of r.violations) {
    console.log(`\n  [${v.impact}] ${v.id} — ${v.help}`);
    console.log(`  ${v.helpUrl}`);
    for (const n of v.nodes) {
      console.log("   target:", JSON.stringify(n.target));
      console.log("   html  :", n.html.slice(0, 400));
      console.log("   why   :", (n.failureSummary ?? "").replace(/\n/g, " / "));
    }
  }
  console.log("\n  tablist HTML thật:");
  console.log(" ", (await page.getByRole("tablist").evaluate((e) => e.outerHTML)).slice(0, 900));
});
