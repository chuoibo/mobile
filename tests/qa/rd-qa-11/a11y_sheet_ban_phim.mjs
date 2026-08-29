// Bàn phím + sheet [+] — phần axe không trả lời được.
//
// Skill accessibility-testing xếp thứ tự theo mức thiệt hại: lỗi bàn phím CHẶN
// hẳn người dùng, nên nó đứng trước lỗi máy quét bắt được. axe cho 0 vi phạm ở
// sáu ô mà vẫn không nói được: Tab có đi hết không, Escape có đóng không, focus
// có quay về chỗ cũ không, và sheet có nhốt focus không.
//
// Sheet [+] là đường DUY NHẤT tới màn nhóm (F03/F04) từ một lần mở app lạnh —
// tức là đường mà luồng mời của #116 sẽ đi qua khi rd-fe-12 dựng xong.
//
// Usage: MOBILE_WEB=http://localhost:8911 node a11y_sheet_ban_phim.mjs

import { chromium } from "playwright";

const WEB = process.env.MOBILE_WEB || "http://localhost:8911";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const focused = (page) =>
  page.evaluate(() => {
    const a = document.activeElement;
    if (!a || a === document.body) return "(body — khong o dau ca)";
    const name = (a.getAttribute("aria-label") || a.textContent || "").trim();
    return `${a.getAttribute("role") || a.tagName.toLowerCase()}: ${name.slice(0, 44)}`;
  });

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setViewportSize({ width: 390, height: 844 });
await page.goto("about:blank");
await page.goto(`${WEB}/#tab=len-plan`);
await page.waitForLoadState("domcontentloaded");
await sleep(1800);

const findings = [];

console.log("=== 1. Tab di duoc toi dau tren man 'Len plan'? ===");
const walk = [];
for (let i = 0; i < 12; i++) {
  await page.keyboard.press("Tab");
  await sleep(160);
  const where = await focused(page);
  walk.push(where);
  if (walk.filter((w) => w === where).length > 2) break;
}
walk.forEach((w, i) => console.log(`  Tab ${String(i + 1).padStart(2)}: ${w}`));
if (walk.every((w) => w.startsWith("(body"))) {
  findings.push("Tab khong toi duoc control nao tren man Len plan");
}

console.log("\n=== 2. Mo sheet [+] bang BAN PHIM ===");
const opener = page.getByRole("button", { name: /Tạo mới/ }).first();
const openerCount = await opener.count();
console.log(`  tim thay nut 'Tao moi': ${openerCount}`);

let sheetOpened = false;
if (openerCount > 0) {
  await opener.focus();
  console.log(`  focus truoc khi mo: ${await focused(page)}`);
  await page.keyboard.press("Enter");
  await sleep(1000);
  const body = await page.evaluate(() => (document.body.textContent || "").replace(/\s+/g, " "));
  sheetOpened = /Tạo nhóm|Tạo khoản chi|Đăng kỷ niệm|Tạo chuyến/.test(body);
  console.log(`  sheet mo bang Enter: ${sheetOpened ? "CO" : "KHONG"}`);
  if (!sheetOpened) findings.push("Nut [+] khong mo duoc bang phim Enter");
}

if (sheetOpened) {
  console.log("\n=== 3. ARIA cua sheet dang mo ===");
  const aria = await page.evaluate(() => {
    const dlg = document.querySelector('[role="dialog"], [aria-modal="true"], dialog');
    if (!dlg) return null;
    return {
      role: dlg.getAttribute("role"),
      modal: dlg.getAttribute("aria-modal"),
      label: dlg.getAttribute("aria-label") || dlg.getAttribute("aria-labelledby"),
    };
  });
  console.log(`  ${aria ? JSON.stringify(aria) : "KHONG tim thay role=dialog / aria-modal"}`);
  if (!aria) {
    findings.push(
      "Sheet [+] khong co role=dialog / aria-modal — trinh doc man hinh khong biet co lop phu"
    );
  } else if (aria.modal !== "true") {
    findings.push("Sheet [+] thieu aria-modal=true");
  } else if (!aria.label) {
    findings.push("Sheet [+] co aria-modal nhung khong co ten (aria-label/labelledby)");
  }

  console.log("\n=== 4. Escape co dong sheet va tra focus ve cho cu? ===");
  await page.keyboard.press("Escape");
  await sleep(900);
  const stillOpen = await page.evaluate(() =>
    /Tạo nhóm|Tạo khoản chi|Đăng kỷ niệm/.test((document.body.textContent || "").replace(/\s+/g, " "))
  );
  console.log(`  sheet con mo sau Escape: ${stillOpen ? "CON — Escape khong dong" : "da dong"}`);
  if (stillOpen) findings.push("Escape khong dong duoc sheet [+] (WCAG 2.1.2 loi thoat ban phim)");
  else console.log(`  focus sau khi dong: ${await focused(page)}`);
}

console.log("\n=== KET LUAN ===");
if (!findings.length) console.log("  Khong tim thay loi ban phim trong cac o da di.");
for (const f of findings) console.log(`  - ${f}`);
console.log(
  "\nChua di: trinh doc man hinh that (VoiceOver/NVDA), 2.4.11 focus bi che,\n" +
    "2.5.7 keo tha. Khong agent nao thay duoc nhung cai do."
);

await browser.close();
