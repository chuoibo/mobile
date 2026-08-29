/** rd-qa-08 — "Khám phá dẫn đi đâu?", đo bằng cách LIỆT KÊ nút, không bằng regex.
 *
 *  Lượt 2 chấm L4 là DI_HET vì một regex tìm thấy chữ "Lên plan" trong văn bản
 *  màn hình. Nhưng "Lên plan" cũng là NHÃN MỘT TAB Ở ĐÁY MÀN — nó có mặt trên
 *  mọi màn trong vỏ tab. Một phán quyết "đi hết được" dựa trên chuỗi đó là
 *  phán quyết về thanh tab, không phải về màn chi tiết địa điểm.
 *
 *  Bộ này bỏ regex và liệt kê từng nút bấm được trên màn chi tiết, kèm nhãn
 *  trợ năng của nó, rồi BẤM từng cái để xem nó dẫn đi đâu thật. Câu hỏi của
 *  Lead — "chọn được quán rồi có tạo được buổi đi không" — chỉ trả lời được
 *  bằng cách bấm, không bằng cách đọc.
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const WEB = process.env.MOBILE_WEB ?? "http://127.0.0.1:8692";
const SHOTS = process.env.MOBILE_SHOTS ?? "/tmp/rd-qa-08";
const PHONE = { width: 390, height: 844 };
const man = (page) => page.evaluate(() => (document.body.innerText || "").replace(/\s+/g, " ").trim());
async function thu(fn) { try { await fn(); return true; } catch { return false; } }

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: PHONE, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.setDefaultTimeout(8000);

  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.getByText(/Google/i).first().click();
  await page.getByRole("button", { name: /Vào app với tư cách/i }).first().click();
  await thu(() => page.getByText(/Đang hỏi máy chủ/i).waitFor({ state: "detached", timeout: 60000 }));
  await page.waitForTimeout(1200);

  // The tab bar is present on every screen in the shell. Record its labels
  // first so they can be subtracted from whatever the detail screen offers --
  // otherwise "Lên plan" gets counted as a way forward on every single screen.
  const nhanTab = await page.getByRole("tab").evaluateAll((els) =>
    els.map((e) => e.getAttribute("aria-label") || e.innerText.trim()));
  console.log("nhãn thanh tab (có mặt trên MỌI màn):", JSON.stringify(nhanTab));

  const the = page.getByRole("button").filter({ hasText: /₫|đ\s|km|·/ });
  const soThe = await the.count();
  console.log(`số thẻ địa điểm trên Khám phá: ${soThe}`);
  await the.first().click();
  await page.waitForTimeout(1200);
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/E1-chi-tiet-day-du.png`, fullPage: true });

  const sChiTiet = await man(page);
  console.log("\n=== TOÀN VĂN MÀN CHI TIẾT ===\n" + sChiTiet + "\n");

  // Every pressable on the detail screen, by accessible name.
  const nut = await page.getByRole("button").evaluateAll((els) =>
    els.map((e) => ({
      ten: (e.getAttribute("aria-label") || e.innerText || "").replace(/\s+/g, " ").trim(),
      hien: !!(e.offsetWidth || e.offsetHeight),
    })).filter((n) => n.ten && n.hien));

  const chiTab = new Set(nhanTab);
  const nutThat = nut.filter((n) => !chiTab.has(n.ten));
  console.log("=== NÚT TRÊN MÀN CHI TIẾT (đã trừ thanh tab) ===");
  for (const n of nutThat) console.log("  •", n.ten);

  // Does any of them claim to start an outing / invite the group?
  const ungVien = nutThat.filter((n) => /rủ|chuyến|buổi|mời|plan|chốt|thêm vào|đặt|đi/i.test(n.ten));
  console.log("\nứng viên 'tạo buổi đi':", ungVien.length ? ungVien.map((n) => n.ten) : "(KHÔNG CÓ)");

  // Press each candidate and record what actually happens.
  const ketQua = [];
  for (const n of ungVien) {
    const truoc = await man(page);
    const bam = await thu(async () => {
      await page.getByRole("button", { name: n.ten, exact: true }).first().click();
      await page.waitForTimeout(1200);
    });
    const sau = await man(page);
    ketQua.push({ nut: n.ten, bamDuoc: bam, manDoi: sau !== truoc, sau: sau.slice(0, 240) });
    console.log(`\nbấm "${n.ten}": bấm được=${bam} · màn đổi=${sau !== truoc}\n  -> ${sau.slice(0, 240)}`);
    await page.screenshot({ path: `${SHOTS}/E2-sau-bam-${n.ten.replace(/[^a-zA-Z0-9]/g, "_").slice(0, 30)}.png` });
  }

  writeFileSync(`${SHOTS}/kham-pha-dan-di-dau.json`,
    JSON.stringify({ nhanTab, soThe, nutThat, ungVien, ketQua, toanVan: sChiTiet }, null, 2));
} finally {
  await browser.close();
}
