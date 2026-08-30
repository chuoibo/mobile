/* Nửa thứ hai của #363, trên API SỐNG: phiên đã TỰ MỞ một nhóm thì tab Tin
 * nhắn phải mở ĐÚNG nhóm đó, không dựng lại nhóm demo.
 *
 * Bộ `nhom-cua-phien.test.mjs` chứng minh điều này với một máy chủ giả, và bảng
 * đột biến cho thấy chính DÂY NỐI (`VoTab` -> `TinNhan`) không có cổng nào gác:
 * đổi `nhomPhien={nhom}` thành `nhomPhien={null}` vẫn 790/790 xanh. Nên nửa này
 * phải đi bằng chân trên máy thật.
 *
 * Chạy: node /tmp/qa41-di-bo-nhom-phien.mjs <cong> <nhan>
 */
import puppeteer from "/tmp/qa41-pr363/apps/mobile/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js";
import { writeFileSync } from "node:fs";

const [, , PORT, NHAN] = process.argv;
const CHROME =
  process.env.PUPPETEER_EXECUTABLE_PATH ??
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";
const API = "127.0.0.1:8099";
const SO = "09" + String(Date.now()).slice(-8);
const TEN = "QA41n " + NHAN;
const TEN_NHOM = "QA41 Nhom Rieng " + String(Date.now()).slice(-5);

const ket = { nhan: NHAN, so: SO, tenNhom: TEN_NHOM, buoc: {}, goiApi: [], loiConsole: [] };
const nghi = (ms) => new Promise((r) => setTimeout(r, ms));
function ghi(b, v) {
  ket.buoc[b] = v;
  console.error(`  ${b}: ${JSON.stringify(v)}`);
}

async function bamChu(page, chu) {
  const hop = await page.evaluate((chu) => {
    const els = [...document.querySelectorAll("*")].filter(
      (e) => e.children.length === 0 && (e.textContent ?? "").trim() === chu,
    );
    if (!els.length) return null;
    let e = els[0];
    for (let i = 0; i < 4 && e.parentElement; i++) {
      if (e.getAttribute("role") === "button" || e.tagName === "BUTTON") break;
      e = e.parentElement;
    }
    const r = e.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width };
  }, chu);
  if (!hop || !hop.w) return false;
  await page.mouse.click(hop.x, hop.y);
  return true;
}

async function bamNhan(page, nhan) {
  const el = await page.$(`[aria-label="${nhan}"]`);
  if (!el) return false;
  const r = await el.boundingBox();
  if (!r) return false;
  await page.mouse.click(r.x + r.width / 2, r.y + r.height / 2);
  return true;
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage();
await page.setViewport({ width: 390, height: 844 });
page.on("console", (m) => m.type() === "error" && ket.loiConsole.push(m.text().slice(0, 200)));
page.on("request", (r) => {
  if (r.url().includes(API)) ket.goiApi.push({ m: r.method(), u: r.url().replace(`http://${API}`, "") });
});

try {
  await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: "networkidle2", timeout: 60000 });
  await nghi(1200);
  await bamChu(page, "Đăng nhập bằng số điện thoại");
  await nghi(900);
  const oSo = await page.$('input[placeholder="09xx xxx xxx"]');
  const oTen = await page.$('input[placeholder="Tên bạn muốn cả nhóm thấy"]');
  await oSo.click();
  await page.keyboard.type(SO, { delay: 10 });
  await oTen.click();
  await page.keyboard.type(TEN, { delay: 10 });
  await bamChu(page, "Tiếp tục");
  await nghi(3500);
  ghi("vao-duoc-shell", await page.evaluate(() => document.querySelectorAll('[role="tab"]').length));

  // [+] -> Tạo nhóm
  ghi("bam-nut-tao-moi", await bamNhan(page, "Tạo mới"));
  await nghi(900);
  ghi("bam-tao-nhom", await bamChu(page, "Tạo nhóm"));
  await nghi(1500);

  const oTenNhom = await page.$('input[placeholder="Team Đà Lạt"]');
  ghi("thay-o-ten-nhom", Boolean(oTenNhom));
  if (oTenNhom) {
    await oTenNhom.click();
    await page.keyboard.type(TEN_NHOM, { delay: 10 });
    ghi("bam-mo-nhom", await bamChu(page, "Mở nhóm"));
    await nghi(4000);
  }
  ket.manNhom = await page.evaluate(() => (document.body.innerText ?? "").slice(0, 600));
  ghi("bam-dong", await bamChu(page, "Đóng"));
  await nghi(1500);

  const t = await page.evaluate(() => {
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const e = tabs.find((x) => ((x.getAttribute("aria-label") ?? "") + (x.textContent ?? "")).includes("Tin nhắn"));
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (t) await page.mouse.click(t.x, t.y);
  await nghi(6000);

  ket.chuTrenManChat = await page.evaluate(() => (document.body.innerText ?? "").slice(0, 500));
  ghi("chat-in-ten-nhom-rieng", ket.chuTrenManChat.includes(TEN_NHOM));
  ghi("chat-in-ten-nhom-demo", ket.chuTrenManChat.includes("Team Đà Lạt"));
  const sauKhiVaoChat = ket.goiApi.slice(-12);
  ket.goiCuoi = sauKhiVaoChat;
  ghi("co-post-contexts-sau-khi-vao-chat", sauKhiVaoChat.some((g) => g.m === "POST" && g.u === "/contexts"));
  await page.screenshot({ path: `/tmp/qa41-anh-${NHAN}.png` });
} catch (e) {
  ket.loiChay = String(e).slice(0, 400);
  console.error("LOI:", ket.loiChay);
} finally {
  await browser.close();
}
writeFileSync(`/tmp/qa41-ket-${NHAN}.json`, JSON.stringify(ket, null, 2));
console.log(JSON.stringify({ nhan: NHAN, buoc: ket.buoc }));
