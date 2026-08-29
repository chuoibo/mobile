import { test, expect } from "@playwright/test";

const BILL = "/tmp/qa-rehearsal/bill-tonghop.jpg";

async function toResults(page: any) {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: /Đăng nhập bằng số điện thoại/ }).click();
  await page.getByRole("button", { name: "Vào app với tư cách Minh" }).click();
  await page.getByRole("button", { name: "Tạo mới" }).click();
  await page.getByRole("button", { name: /^Tạo khoản chi/ }).click();
  const ch = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Chọn ảnh bill" }).first().click();
  await (await ch).setFiles(BILL);
  await page.getByText("Đã nhận diện 8 món").waitFor({ timeout: 90_000 });
}

const total = async (page: any) => {
  const t = await page.locator("body").innerText();
  return (t.match(/Tổng cộng\s*\n([^\n]+)/) ?? [])[1] ?? "(không đọc được)";
};

test("sửa ô Thành tiền bằng GÕ PHÍM THẬT", async ({ page }) => {
  await toResults(page);
  const amt = page.getByRole("textbox", { name: /^Thành tiền, Bia Saigon/ });

  console.log("  giá trị ban đầu:", await amt.inputValue());
  console.log("  tổng ban đầu   :", await total(page));

  // Real user: tap the field, select everything, delete, then type.
  await amt.click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.press("Backspace");
  console.log("  sau khi xoá  -> value:", JSON.stringify(await amt.inputValue()), "| tổng:", await total(page));

  for (const ch of "200000") {
    await page.keyboard.type(ch);
    await page.waitForTimeout(60);
    console.log(`   gõ '${ch}' -> value=${JSON.stringify(await amt.inputValue())} | tổng=${await total(page)}`);
  }

  const finalTotal = await total(page);
  console.log("  TỔNG CUỐI:", finalTotal);
  // 1.215.000 - 150.000 + 200.000 = 1.265.000
  expect(finalTotal.replace(/\s/g, "")).toBe("1.265.000đ");
});

test("sửa ô Số lượng bằng GÕ PHÍM THẬT", async ({ page }) => {
  await toResults(page);
  const qty = page.getByRole("textbox", { name: "Số lượng, Bia Saigon" });
  console.log("  SL ban đầu:", await qty.inputValue(), "| tổng:", await total(page));
  await qty.click();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.press("Backspace");
  await page.keyboard.type("2");
  await page.waitForTimeout(300);
  console.log("  SL sau khi sửa thành 2:", await qty.inputValue(), "| tổng:", await total(page));
  console.log("  (SL không nên đổi tổng: thành tiền là con số nguồn)");
});

test("xoá một món thì tổng có trừ đi không", async ({ page }) => {
  await toResults(page);
  console.log("  tổng ban đầu:", await total(page));
  await page.getByRole("button", { name: "Xoá món Bia Saigon" }).click();
  await page.waitForTimeout(400);
  const after = await total(page);
  console.log("  sau khi xoá 'Bia Saigon' (150.000):", after);
  const body = await page.locator("body").innerText();
  console.log("  dòng cảnh báo:", (body.match(/(Khớp[^\n]*|[^\n]*lệch[^\n]*)/i) ?? [])[1] ?? "(không có)");
  expect(after.replace(/\s/g, "")).toBe("1.065.000đ");
});
