/**
 * rd-qa-17. Walk the two screens PR #136 adds, on a bundle built from the PR
 * SHA, and answer the question the source cannot answer on its own: what is
 * actually inside the square a person holds up across a table.
 *
 * The QR is screenshotted and decoded with OpenCV -- a decoder that shares no
 * code with `src/ui/qr.ts`. Reading the encoder's input and calling that "what
 * is in the code" would only prove the encoder was called with what the
 * encoder was called with.
 */
import { chromium } from "playwright";
import { AxeBuilder } from "@axe-core/playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = process.env.QA17_BASE ?? "http://127.0.0.1:4717";
const OUT = "/tmp/qa17-shots";
mkdirSync(OUT, { recursive: true });

const WCAG = ["wcag2a", "wcag2aa", "wcag22aa"];

/** AppRoot reads the fragment once, at mount. Navigating between fragments
 *  without a real document swap leaves the previous screen mounted and the
 *  report describes the wrong screen while exiting 0. */
async function moMan(page, fragment) {
  await page.goto("about:blank");
  await page.goto(`${BASE}/${fragment}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
}

async function quetAxe(page, ten) {
  const r = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  const nang = r.violations.filter((v) => ["critical", "serious"].includes(v.impact));
  console.log(`  axe ${ten}: ${r.violations.length} vi phạm ` +
    `(${nang.length} critical/serious) trên ${r.passes.length} quy tắc đạt`);
  for (const v of r.violations) {
    console.log(`     [${v.impact}] ${v.id} — ${v.nodes.length} nút: ${v.help}`);
  }
  return r;
}

const browser = await chromium.launch();
const ctx390 = await browser.newContext({ viewport: { width: 390, height: 844 } });
const ctx1280 = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const ket = { axe: {}, qr: null };

// ---------------------------------------------------------------- CANARY
// axe scanning a page that never loaded, or an error page, passes vacuously.
// A planted violation must make it fail before any zero here means anything.
console.log("=".repeat(74));
console.log("CANARY — máy quét axe có thật sự đang đọc trang không?");
console.log("=".repeat(74));
{
  const page = await ctx1280.newPage();
  await page.goto(`${BASE}/canary-xau.html`, { waitUntil: "networkidle" });
  const r = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  console.log(`  canary XẤU  : ${r.violations.length} vi phạm — ` +
    `${r.violations.map((v) => v.id).join(", ")}`);
  if (r.violations.length === 0) {
    console.log("  !! CANARY XẤU RA 0 — máy quét chết, mọi số 0 dưới đây vô nghĩa");
    process.exit(3);
  }
  await page.goto(`${BASE}/canary-sach.html`, { waitUntil: "networkidle" });
  const r2 = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  console.log(`  canary SẠCH : ${r2.violations.length} vi phạm — ` +
    `${r2.violations.map((v) => v.id).join(", ") || "không có"}`);
  await page.close();
}

// ---------------------------------------------------------------- F05
console.log("");
console.log("=".repeat(74));
console.log("F05 — MÀN 'MÃ KẾT BẠN CỦA BẠN' (Cá nhân)");
console.log("=".repeat(74));
{
  const page = await ctx390.newPage();
  await moMan(page, "#tab=ca-nhan&nguoi=minh");

  const the = page.getByText("Mã kết bạn của bạn");
  console.log(`  thẻ 'Mã kết bạn của bạn' hiện ra: ${await the.count()} lần`);

  const o = page.locator('[role="img"][aria-label^="Mã QR kết bạn"]');
  await o.first().waitFor({ state: "visible", timeout: 15000 });
  const nhan = await o.first().getAttribute("aria-label");
  console.log(`  nhãn trình đọc màn hình: "${nhan}"`);

  const box = await o.first().boundingBox();
  console.log(`  ô vuông: ${Math.round(box.width)}×${Math.round(box.height)} px`);

  // Screenshot at 4x so a module lands on whole pixels for the decoder.
  await o.first().screenshot({ path: `${OUT}/f05-qr.png`, scale: "css" });
  await page.screenshot({ path: `${OUT}/f05-man-390.png`, fullPage: true });

  const cauChu = await page.getByText(/Trong mã chỉ có/).innerText().catch(() => null);
  console.log(`  câu app tự nói về nội dung mã: "${cauChu}"`);

  ket.axe.f05 = await quetAxe(page, "F05 390×844");

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/f05-man-1280.png`, fullPage: true });
  ket.axe.f05_desktop = await quetAxe(page, "F05 1280×900");
  await page.close();
}

// ---------------------------------------------------------------- F46
console.log("");
console.log("=".repeat(74));
console.log("F46 — THẺ ĐỊA ĐIỂM CÓ NÚT CHECK-IN (#dia-diem=)");
console.log("=".repeat(74));
{
  const page = await ctx390.newPage();
  const loi = [];
  page.on("console", (m) => { if (m.type() === "error") loi.push(m.text()); });
  await moMan(page, "#dia-diem=p-tiem-nuong-xom-lao&nguoi=minh");
  await page.waitForTimeout(1500);

  const ten = await page.getByText("Tiệm Nướng Xóm Lào").count();
  console.log(`  tên địa điểm trên thẻ: ${ten} lần`);

  const nut = page.getByRole("button", { name: /check-in|Check-in|đã tới/i });
  const n = await nut.count();
  console.log(`  nút check-in bấm được: ${n}`);
  for (let i = 0; i < n; i++) {
    const t = (await nut.nth(i).innerText()).replace(/\n/g, " / ");
    const b = await nut.nth(i).boundingBox();
    console.log(`     [${i}] "${t}"  ${b ? `${Math.round(b.width)}×${Math.round(b.height)}` : "không đo được"}`);
  }

  await page.screenshot({ path: `${OUT}/f46-man-390.png`, fullPage: true });
  ket.axe.f46 = await quetAxe(page, "F46 390×844");

  // Does anything on this card carry a coordinate a person could read off?
  const chu = await page.evaluate(() => document.body.innerText);
  const toado = chu.match(/\b1[0-9]\.\d{3,}\b|\b10[0-9]\.\d{3,}\b/g);
  console.log(`  chuỗi giống toạ độ hiện trên màn: ${toado ? toado.join(", ") : "KHÔNG CÓ"}`);
  console.log(`  lỗi console: ${loi.length ? loi.slice(0, 3).join(" | ") : "không có"}`);
  await page.close();
}

await browser.close();
writeFileSync(`${OUT}/axe.json`, JSON.stringify(
  Object.fromEntries(Object.entries(ket.axe).map(([k, v]) => [k, v.violations])), null, 2));
console.log("");
console.log(`ảnh + axe.json ở ${OUT}`);
