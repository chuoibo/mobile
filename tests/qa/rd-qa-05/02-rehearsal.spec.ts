import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";

const BILL = path.join(__dirname, "..", "bill-tonghop.jpg");

/** Wire every screen up to a crash recorder before touching it. */
function watch(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console.error: ${m.text()}`);
  });
  return errors;
}

/** A white screen is the demo-killer. Assert the app still has content. */
async function notBlank(page: Page, where: string) {
  const text = (await page.locator("body").innerText()).trim();
  expect(text.length, `TRẮNG MÀN HÌNH tại: ${where}`).toBeGreaterThan(20);
  return text;
}

async function enterApp(page: Page, who = "Minh") {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: /Đăng nhập bằng số điện thoại/ }).click();
  await page.getByRole("button", { name: `Vào app với tư cách ${who}` }).click();
  await expect(page.getByRole("tablist")).toBeVisible();
}

async function openBillScreen(page: Page) {
  await page.getByRole("button", { name: "Tạo mới" }).click();
  await page.getByRole("button", { name: /^Tạo khoản chi/ }).click();
  await expect(page.getByRole("button", { name: "Huỷ" })).toBeVisible();
}

async function uploadBill(page: Page) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Chọn ảnh bill" }).first().click();
  await (await chooser).setFiles(BILL);
}

// ---------------------------------------------------------------------------

test("R1 — hero path chạy hết, AI đọc bill thật", async ({ page }) => {
  const errors = watch(page);
  const t0 = Date.now();
  await enterApp(page);
  console.log(`  [thời lượng] mở app -> vào shell: ${Date.now() - t0}ms`);

  const t1 = Date.now();
  await openBillScreen(page);
  console.log(`  [thời lượng] shell -> màn chụp bill: ${Date.now() - t1}ms`);

  const t2 = Date.now();
  await uploadBill(page);
  await expect(page.getByText("Đã nhận diện 8 món")).toBeVisible({ timeout: 90_000 });
  console.log(`  [thời lượng] AI đọc bill: ${Date.now() - t2}ms`);

  const body = await notBlank(page, "kết quả nhận diện");
  console.log("=== MÀN KẾT QUẢ ===\n" + body.slice(0, 1200));
  expect(errors).toEqual([]);
});

test("R2a — bấm hai lần nút mở sheet: cú thứ hai LỌT XUỐNG nút bên dưới", async ({ page }) => {
  // A sheet that opens under the finger and takes the second tap of a
  // double-tap. Nothing crashes, but the app silently acts on a control the
  // user never saw -- on the login screen that skips the person picker.
  const errors = watch(page);
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  await page.getByRole("button", { name: /Đăng nhập bằng số điện thoại/ }).dblclick();
  await page.waitForTimeout(700);
  const body = await notBlank(page, "sau double-tap đăng nhập");
  const pickerStillOpen = await page.getByRole("dialog").isVisible().catch(() => false);
  const alreadyInApp = await page.getByRole("tablist").isVisible().catch(() => false);
  console.log(`  bảng chọn người còn mở? ${pickerStillOpen} | đã vào thẳng app? ${alreadyInApp}`);
  console.log("  màn hình:", body.slice(0, 160).replace(/\n/g, " | "));

  expect(errors).toEqual([]);
  expect(
    pickerStillOpen,
    "double-tap đã lọt qua bảng chọn người: app tự chọn hộ người dùng mà họ chưa kịp nhìn danh sách"
  ).toBe(true);
});

test("R2b — bấm hai lần 'Tiếp tục' KHÔNG gọi API hai lần", async ({ page }) => {
  const errors = watch(page);
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") posts.push(r.url());
  });

  await enterApp(page);
  await openBillScreen(page);
  await uploadBill(page);
  await expect(page.getByText("Đã nhận diện 8 món")).toBeVisible({ timeout: 90_000 });

  await page.getByRole("button", { name: "Tiếp tục" }).dblclick();
  await page.waitForTimeout(1500);
  const body = await notBlank(page, "sau double-tap Tiếp tục");
  console.log("  POST đã gửi:", JSON.stringify(posts));
  console.log("  màn hình:", body.slice(0, 200).replace(/\n/g, " | "));

  expect(posts.filter((u) => u.includes("/receipts/scan")).length, "quét bill bị gọi hai lần").toBe(1);
  expect(errors).toEqual([]);
});

test("R3 — nút BACK: app có đẩy lịch sử để quay lại một màn không?", async ({ page }) => {
  // NOT tested with goBack() alone: with no prior page, goBack() lands on
  // about:blank and the blank body would be the harness's fault, not the app's.
  // What actually matters is whether the app pushes ANY history at all --
  // if it does not, the phone's Back button leaves the app instead of
  // stepping back one screen, and every scanned item is lost.
  const errors = watch(page);
  await enterApp(page);
  const atShell = await page.evaluate(() => ({ url: location.href, len: history.length }));

  await openBillScreen(page);
  const atBill = await page.evaluate(() => ({ url: location.href, len: history.length }));

  console.log("  shell     :", JSON.stringify(atShell));
  console.log("  chụp bill :", JSON.stringify(atBill));

  expect(
    atBill.len > atShell.len || atBill.url !== atShell.url,
    "app không đẩy lịch sử khi đi sâu vào màn chụp bill — nút Back của điện thoại sẽ THOÁT APP chứ không lùi một màn"
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("R4 — MẤT MẠNG đúng lúc AI đang đọc bill", async ({ page, context }) => {
  const errors = watch(page);
  await enterApp(page);
  await openBillScreen(page);

  // Cut the network the moment the upload starts, not before.
  await page.route("**/receipts/scan", (route) => route.abort("internetdisconnected"));

  await uploadBill(page);
  await page.waitForTimeout(3000);

  const body = await notBlank(page, "mất mạng lúc AI đọc bill");
  console.log("=== MÀN HÌNH KHI MẤT MẠNG ===\n" + body.slice(0, 900));

  // The user must be told, and must be able to try again.
  const retry = page.getByRole("button", { name: /Chọn ảnh bill|Thử lại|Chụp bill/ });
  expect(await retry.count(), "không còn nút nào để thử lại").toBeGreaterThan(0);

  // Recover: restore network, retry, and confirm it still works.
  await page.unroute("**/receipts/scan");
  await uploadBill(page);
  await expect(page.getByText("Đã nhận diện 8 món")).toBeVisible({ timeout: 90_000 });
  console.log("  hồi phục sau khi có mạng lại: OK");
  // The browser logs its own ERR_INTERNET_DISCONNECTED for the aborted request;
  // that is Chrome talking, not the app failing. Only an uncaught app-level
  // error means the screen broke.
  expect(errors.filter((e) => e.startsWith("pageerror")), "app ném lỗi chưa bắt khi mất mạng").toEqual([]);
});

test("R5 — XOAY NGANG máy ở mỗi màn", async ({ page }) => {
  const errors = watch(page);
  const land = { width: 844, height: 390 };
  const port = { width: 390, height: 844 };

  await page.setViewportSize(port);
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  await page.setViewportSize(land);
  await page.waitForTimeout(400);
  await notBlank(page, "màn mở đầu, xoay ngang");
  const ob = await page.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  }));
  console.log("  mở đầu ngang:", JSON.stringify(ob));
  expect(ob.scrollW, "tràn ngang ở màn mở đầu (landscape)").toBeLessThanOrEqual(ob.clientW + 1);

  await page.setViewportSize(port);
  await enterApp(page);
  await page.setViewportSize(land);
  await page.waitForTimeout(400);
  await notBlank(page, "shell 5 tab, xoay ngang");
  const sb = await page.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  }));
  console.log("  shell ngang:", JSON.stringify(sb));
  expect(sb.scrollW, "tràn ngang ở shell (landscape)").toBeLessThanOrEqual(sb.clientW + 1);

  await openBillScreen(page);
  await notBlank(page, "màn chụp bill, xoay ngang");
  await uploadBill(page);
  await expect(page.getByText("Đã nhận diện 8 món")).toBeVisible({ timeout: 90_000 });
  const kb = await page.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  }));
  console.log("  kết quả nhận diện ngang:", JSON.stringify(kb));
  expect(kb.scrollW, "tràn ngang ở màn kết quả (landscape)").toBeLessThanOrEqual(kb.clientW + 1);
  expect(errors).toEqual([]);
});

test("R6 — axe trên từng màn của hero path", async ({ page }, testInfo) => {
  const scan = async (label: string) => {
    const r = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    const bad = r.violations.filter((v) => ["critical", "serious"].includes(v.impact ?? ""));
    console.log(
      `  [axe] ${label}: ${r.violations.length} vi phạm (${bad.length} critical/serious)` +
        (r.violations.length
          ? "\n" + r.violations.map((v) => `     - ${v.impact} ${v.id} x${v.nodes.length}: ${v.help}`).join("\n")
          : "")
    );
    await testInfo.attach(`axe-${label}.json`, {
      body: JSON.stringify(r.violations, null, 1),
      contentType: "application/json",
    });
    return bad;
  };

  await page.goto("/");
  await page.waitForLoadState("networkidle");
  const a = await scan("man-mo-dau");

  await enterApp(page);
  const b = await scan("shell-5-tab");

  await openBillScreen(page);
  const c = await scan("chup-bill");

  await uploadBill(page);
  await expect(page.getByText("Đã nhận diện 8 món")).toBeVisible({ timeout: 90_000 });
  const d = await scan("ket-qua-nhan-dien");

  expect([...a, ...b, ...c, ...d].map((v) => v.id)).toEqual([]);
});
