/* Đi bộ cửa số điện thoại -> tab Tin nhắn, trên API SỐNG 8099.
 *
 * Đây là ô mà PR #363 tự ghi là chưa quét ("Chưa đi bộ trên API sống"). Bộ
 * `nhom-cua-phien.test.mjs` chứng minh cái một lời gọi hàm thấy được với một
 * máy chủ giả; nó không nói máy chủ thật có chấp nhận chuỗi request đó không.
 *
 * Chạy:  node /tmp/qa41-di-bo.mjs <thu-muc-bundle> <cong> <nhan>
 * In ra JSON một dòng ở cuối, để so hai bản TRƯỚC/SAU bằng máy chứ không bằng mắt.
 */
import puppeteer from "/tmp/qa41-pr363/apps/mobile/node_modules/puppeteer-core/lib/esm/puppeteer/puppeteer-core.js";
import { writeFileSync } from "node:fs";

const [, , DIR, PORT, NHAN] = process.argv;
const CHROME =
  process.env.PUPPETEER_EXECUTABLE_PATH ??
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";
const API = "127.0.0.1:8099";
const SO = "09" + String(Date.now()).slice(-8);
const TEN = "QA41 " + NHAN;

const ket = {
  nhan: NHAN,
  bundle: DIR,
  so: SO,
  buoc: {},
  goiApi: [],
  loiConsole: [],
  chuTrenManChat: "",
};

function ghi(b, v) {
  ket.buoc[b] = v;
  console.error(`  ${b}: ${JSON.stringify(v)}`);
}

const nghi = (ms) => new Promise((r) => setTimeout(r, ms));

async function bamChu(page, chu, { chinhXac = true } = {}) {
  const hop = await page.evaluate(
    (chu, chinhXac) => {
      const els = [...document.querySelectorAll("*")].filter((e) => {
        const t = (e.textContent ?? "").trim();
        if (e.children.length > 0) return false;
        return chinhXac ? t === chu : t.includes(chu);
      });
      if (!els.length) return null;
      // leo lên tổ tiên gần nhất có role button, nếu có
      let e = els[0];
      for (let i = 0; i < 4 && e.parentElement; i++) {
        if (e.getAttribute("role") === "button" || e.tagName === "BUTTON") break;
        e = e.parentElement;
      }
      const r = e.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height };
    },
    chu,
    chinhXac,
  );
  if (!hop || hop.w === 0) return false;
  await page.mouse.click(hop.x, hop.y);
  return true;
}

async function bamNhan(page, nhan) {
  const el = await page.$(`[aria-label="${nhan}"], [aria-labelledby][data-x="${nhan}"]`);
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

page.on("console", (m) => {
  if (m.type() === "error") ket.loiConsole.push(m.text().slice(0, 200));
});
page.on("request", (r) => {
  if (r.url().includes(API)) ket.goiApi.push({ m: r.method(), u: r.url().replace(`http://${API}`, "") });
});
page.on("requestfailed", (r) => {
  if (r.url().includes(API))
    ket.goiApi.push({ m: r.method(), u: r.url().replace(`http://${API}`, ""), that_bai: r.failure()?.errorText });
});

try {
  await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: "networkidle2", timeout: 60000 });
  await nghi(1200);
  ghi("mo-app", true);

  ghi("bam-cua-so-dien-thoai", await bamChu(page, "Đăng nhập bằng số điện thoại"));
  await nghi(900);

  const oSo = await page.$('input[placeholder="09xx xxx xxx"]');
  const oTen = await page.$('input[placeholder="Tên bạn muốn cả nhóm thấy"]');
  ghi("thay-hai-o-nhap", Boolean(oSo && oTen));
  if (oSo && oTen) {
    await oSo.click();
    await page.keyboard.type(SO, { delay: 12 });
    await oTen.click();
    await page.keyboard.type(TEN, { delay: 12 });
  }
  ghi("bam-tiep-tuc", await bamChu(page, "Tiếp tục"));
  await nghi(3500);

  const daVaoShell = await page.evaluate(() =>
    [...document.querySelectorAll("*")].some((e) => (e.textContent ?? "").trim() === "Tin nhắn"),
  );
  ghi("vao-duoc-shell", daVaoShell);

  // Tab bar renders `accessibilityRole="tab"` + `accessibilityLabel`, so click
  // the role rather than the label text: the same string "Tin nhắn" also sits
  // in the tab bar as a plain <div>, and clicking that one changes nothing --
  // which reads exactly like a product that ignores the tap.
  const bamTab = await page.evaluate(() => {
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const t = tabs.find((e) => ((e.getAttribute("aria-label") ?? "") + (e.textContent ?? "")).includes("Tin nhắn"));
    if (!t) return { ok: false, soTab: tabs.length };
    const r = t.getBoundingClientRect();
    return { ok: true, soTab: tabs.length, x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (bamTab.ok) await page.mouse.click(bamTab.x, bamTab.y);
  ghi("bam-tab-tin-nhan", bamTab);
  await nghi(6000);
  ket.tabDangChon = await page.evaluate(() =>
    [...document.querySelectorAll('[role="tab"]')]
      .filter((e) => e.getAttribute("aria-selected") === "true")
      .map((e) => e.getAttribute("aria-label") ?? e.textContent),
  );
  ghi("tab-dang-chon", ket.tabDangChon);

  ket.chuTrenManChat = await page.evaluate(() => (document.body.innerText ?? "").slice(0, 1400));
  const hong = /Chưa vào được nhóm|Không ghi được tên người|Thử lại/.test(ket.chuTrenManChat);
  ghi("man-chat-bao-hong", hong);

  const truocKhiGui = ket.goiApi.length;
  const oNhap = await page.$('[aria-label="Ô nhập tin nhắn"]');
  ghi("thay-o-nhap-tin", Boolean(oNhap));
  if (oNhap) {
    await oNhap.click();
    await page.keyboard.type("QA41 xin chao", { delay: 12 });
    await nghi(300);
    ghi("bam-gui", await bamNhan(page, "Gửi tin nhắn"));
    await nghi(4000);
  }
  const sauKhiGui = ket.goiApi.slice(truocKhiGui);
  ket.goiSauKhiBamGui = sauKhiGui;
  ghi("so-goi-http-sau-khi-bam-gui", sauKhiGui.length);
  ghi("co-post-messages", sauKhiGui.some((g) => g.m === "POST" && /\/messages$/.test(g.u)));

  await page.screenshot({ path: `/tmp/qa41-anh-${NHAN}.png`, fullPage: false });
} catch (e) {
  ket.loiChay = String(e).slice(0, 400);
  console.error("LOI:", ket.loiChay);
} finally {
  await browser.close();
}

writeFileSync(`/tmp/qa41-ket-${NHAN}.json`, JSON.stringify(ket, null, 2));
console.log(JSON.stringify({ nhan: NHAN, buoc: ket.buoc, soGoi: ket.goiApi.length }));
