/** rd-qa-08 — bản đồ đường đi: đi hết vòng demo trên main, ghi lại chặng nào
 *  đi hết được và chặng nào cụt.
 *
 *  Không phải một bộ test pass/fail. Đây là một phép ĐO: mỗi chặng của vòng
 *  demo mà PM đã viết được đi bằng tay trên bản web export thật, khung điện
 *  thoại 390x844, API thật, Postgres thật. Kết quả của mỗi chặng là một trong
 *  ba giá trị, và giá trị đó phải đến từ cái NHÌN THẤY TRÊN MÀN, không phải từ
 *  việc đọc source:
 *
 *    DI_HET   — chặng chạy thật, sang được chặng sau
 *    VO       — màn hình có, nhưng tự khai là vỏ (chưa dựng)
 *    CUT      — bấm vào thì không có đường đi tiếp, và màn không nói gì
 *
 *  Phân biệt VO với CUT là điểm của cả bộ này. Một màn tự nói "còn là vỏ"
 *  trung thực với người xem demo; một màn im lặng nuốt cú bấm thì không.
 *
 *  Chạy:
 *    MOBILE_WEB=http://127.0.0.1:8692 MOBILE_API=http://127.0.0.1:8690 \
 *      node 01-ban-do-duong-di.mjs
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const WEB = process.env.MOBILE_WEB ?? "http://127.0.0.1:8692";
const API = process.env.MOBILE_API ?? "http://127.0.0.1:8690";
const SHOTS = process.env.MOBILE_SHOTS ?? "/tmp/rd-qa-08";

/** Phone frame the demo is shown on. Same numbers rd-qa-05/06 measured at, so
 *  a finding here is comparable with theirs. */
const PHONE = { width: 390, height: 844 };

const legs = [];
function ghi(id, ten, ket, chiTiet) {
  legs.push({ id, ten, ket, chiTiet });
  console.log(`[${ket.padEnd(6)}] ${id}  ${ten}\n         ${chiTiet}`);
}

/** Text of what a human would actually see, collapsed for logging. */
async function manHinh(page) {
  const t = await page.evaluate(() => document.body.innerText || "");
  return t.replace(/\s+/g, " ").trim();
}

async function chup(page, ten) {
  mkdirSync(SHOTS, { recursive: true });
  await page.screenshot({ path: `${SHOTS}/${ten}.png` });
}

/** Run a click/probe and swallow only the "control is not there" failure. One
 *  dead leg must not end the walk -- the whole point is to reach the end and
 *  count how many legs died. Returns false when the control was missing. */
async function thu(fn) {
  try { await fn(); return true; } catch { return false; }
}

/** react-native-web TextInput ignores locator.fill() — rd-qa-05 lost time to
 *  this. Everything types through the keyboard. */
async function go(page, loc, text) {
  await loc.click();
  await page.keyboard.type(text, { delay: 8 });
}

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({ viewport: PHONE, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  // A control that is not there is a finding, not a reason to spend 30s. Short
  // timeout so a dead end reports as a dead end instead of as a hung script.
  page.setDefaultTimeout(4000);

  const loi = [];
  page.on("pageerror", (e) => loi.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") loi.push(m.text()); });

  // ---------------------------------------------------------------- L1: mở app
  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  await chup(page, "L1-mo-dau");
  const s1 = await manHinh(page);
  const coVaoBang = /Google|Apple|Bỏ qua|Vào/i.test(s1);
  ghi("L1", "mở app → màn mở đầu",
    coVaoBang ? "DI_HET" : "CUT",
    coVaoBang ? `màn mở đầu render, có lối vào: "${s1.slice(0, 110)}"` : `không thấy lối vào: "${s1.slice(0, 160)}"`);

  // ------------------------------------------------------------- L2: đăng nhập
  const nutGoogle = page.getByText(/Google/i).first();
  let s2 = "";
  await thu(async () => {
    await nutGoogle.click();
    await page.waitForTimeout(500);
    await chup(page, "L2-chon-nguoi");
    s2 = await manHinh(page);
  });
  // The picker of the demo group is the stand-in for sign-in. Address the row
  // by its accessible name, not by "first button that isn't Google": the sheet
  // also carries a close button, and picking that one silently measures the
  // wrong thing.
  const nguoiDau = page.getByRole("button", { name: /Vào app với tư cách/i }).first();
  let vaoDuoc = false;
  await thu(async () => {
    await nguoiDau.click();
    await page.waitForTimeout(900);
    vaoDuoc = /Khám phá|Cá nhân|Tin nhắn|Lên plan/i.test(await manHinh(page));
  });
  await chup(page, "L2-sau-dang-nhap");
  ghi("L2", "đăng nhập → vào vỏ tab",
    vaoDuoc ? "DI_HET" : "CUT",
    vaoDuoc
      ? `picker nhóm demo mở, chọn người xong vào thẳng vỏ tab. Màn picker: "${s2.slice(0, 90)}"`
      : `không vào được vỏ tab sau khi bấm. Màn: "${(await manHinh(page)).slice(0, 160)}"`);

  // ------------------------------------------------------- L3: Khám phá + AI MATCH
  await page.waitForTimeout(800);
  await chup(page, "L3-kham-pha");
  const s3 = await manHinh(page);
  const coThe = /gợi ý|AI|match|hợp/i.test(s3);
  // The AI label is the product claim on this screen. An empty percent, or a
  // literal "undefined", is the failure this leg exists to catch.
  const nhanHong = /undefined|NaN|\bAI suggested\s*%|:\s*%/.test(s3);
  ghi("L3", "Khám phá → thấy thẻ địa điểm + nhãn AI",
    nhanHong ? "CUT" : coThe ? "DI_HET" : "CUT",
    nhanHong
      ? `nhãn AI hỏng trên màn: "${s3.slice(0, 200)}"`
      : `màn Khám phá render kèm nhãn AI: "${s3.slice(0, 200)}"`);

  // --------------------------------------- L4: chi tiết địa điểm → rủ nhóm đi?
  // The product loop says: pick a place, then turn it into an outing. This leg
  // asks whether that turn exists at all.
  const the = page.getByRole("button").filter({ hasText: /₫|đ\b|km|Quán|Nhà hàng|Cà phê/i }).first();
  let s4 = "";
  let moDuocChiTiet = false;
  await thu(async () => {
    await the.click();
    await page.waitForTimeout(800);
    s4 = await manHinh(page);
    moDuocChiTiet = s4.length > 40 && s4 !== s3;
  });
  await chup(page, "L4-chi-tiet-dia-diem");
  const coRuDi = /Rủ|Tạo chuyến|Tạo buổi|Lên plan|Mời|Chốt/i.test(s4);
  ghi("L4", "chọn quán → tạo buổi đi (rủ nhóm)",
    !moDuocChiTiet ? "CUT" : coRuDi ? "DI_HET" : "CUT",
    !moDuocChiTiet
      ? `bấm thẻ địa điểm không mở được gì. Màn không đổi.`
      : coRuDi
        ? `chi tiết mở, có nút rủ đi: "${s4.slice(0, 160)}"`
        : `chi tiết mở nhưng KHÔNG có đường tạo buổi đi: "${s4.slice(0, 200)}"`);

  // Back out to the tab shell for the remaining legs.
  const nutDong = page.getByRole("button", { name: /Đóng|Quay|Trở/i }).first();
  await thu(async () => { await nutDong.click(); await page.waitForTimeout(500); });

  // ------------------------------------------------- L5/L6: hai tab còn lại
  for (const [id, ten, nhan] of [
    ["L5", "tab Tin nhắn → chat nhóm + AI gợi ý chỗ ăn", /Tin nhắn/i],
    ["L6", "tab Lên plan → chuyến đi của nhóm", /Lên plan/i],
  ]) {
    const tab = page.getByRole("tab", { name: nhan }).first();
    const buoc = (await tab.count()) ? tab : page.getByText(nhan).first();
    let s = "";
    await thu(async () => {
      await buoc.click();
      await page.waitForTimeout(600);
      s = await manHinh(page);
    });
    await chup(page, `${id}-tab`);
    // A screen that says it is a shell is honest; a screen that says nothing is not.
    const tuKhaiVo = /còn là vỏ|chưa dựng|chưa xếp|Màn này/i.test(s);
    ghi(id, ten,
      !s ? "CUT" : tuKhaiVo ? "VO" : "DI_HET",
      !s ? `không bấm được vào tab` : `${tuKhaiVo ? "màn tự khai là vỏ" : "màn có nội dung thật"}: "${s.slice(0, 180)}"`);
  }

  // ------------------------------------------------- L7: [+] → các hành động tạo
  const nutTao = page.getByRole("button", { name: /Tạo|\+/i }).first();
  let sMenu = "";
  await thu(async () => {
    await nutTao.click();
    await page.waitForTimeout(500);
    sMenu = await manHinh(page);
  });
  await chup(page, "L7-menu-tao");
  const soVo = (sMenu.match(/còn là vỏ/g) || []).length;
  ghi("L7", "[+] → menu tạo (chuyến / khoản chi / kỷ niệm / nhóm)",
    sMenu ? "DI_HET" : "CUT",
    sMenu ? `menu mở, ${soVo} mục tự khai là vỏ: "${sMenu.slice(0, 220)}"` : `không mở được menu [+]`);

  // --------------------------------- L8..L12: nhánh khoản chi (nửa sau của luồng)
  const tuChoiChi = page.getByText(/Tạo khoản chi/i).first();
  let vaoLuongChi = false;
  await thu(async () => {
    await tuChoiChi.click();
    await page.waitForTimeout(900);
    vaoLuongChi = /bill|khoản chi|Chụp|nhập tay|Tổng/i.test(await manHinh(page));
  });
  await chup(page, "L8-vao-luong-chi");
  const s8 = await manHinh(page);
  ghi("L8", "menu [+] → vào luồng khoản chi",
    vaoLuongChi ? "DI_HET" : "CUT",
    vaoLuongChi ? `vào được luồng: "${s8.slice(0, 200)}"` : `không vào được: "${s8.slice(0, 200)}"`);

  // Does the bill-capture entry exist on this screen, and does it lead anywhere?
  const nutBill = page.getByText(/Chụp bill|Chụp|Ảnh bill|bill/i).first();
  let s9 = "";
  let moDuocBill = false;
  if (vaoLuongChi) {
    await thu(async () => {
      await nutBill.click();
      await page.waitForTimeout(900);
      s9 = await manHinh(page);
      moDuocBill = s9 !== s8;
    });
  }
  await chup(page, "L9-chup-bill");
  ghi("L9", "chụp bill → AI đọc món",
    !vaoLuongChi ? "CUT" : moDuocBill ? "DI_HET" : "CUT",
    !vaoLuongChi ? `không tới được vì L8 cụt`
      : moDuocBill ? `màn chụp bill mở: "${s9.slice(0, 200)}"`
      : `bấm chụp bill nhưng màn không đổi: "${s9.slice(0, 200)}"`);

  const chuoiLoi = [...new Set(loi)].slice(0, 8);

  // ------------------------------------------------------------------ đối chứng
  // The API is reachable and the bundle is pinned to it: without this, every
  // "CUT" above could just be a screen that never loaded its data.
  const health = await fetch(`${API}/healthz`).then((r) => r.json()).catch((e) => ({ err: String(e) }));

  const bao = { web: WEB, api: API, health, legs, loiTrang: chuoiLoi };
  writeFileSync(`${SHOTS}/ban-do.json`, JSON.stringify(bao, null, 2));

  console.log("\n=== TỔNG ===");
  for (const k of ["DI_HET", "VO", "CUT"]) {
    console.log(`${k}: ${legs.filter((l) => l.ket === k).length}`);
  }
  console.log("lỗi trang:", chuoiLoi.length ? chuoiLoi : "(không)");
  console.log("healthz:", JSON.stringify(health));
  console.log("ảnh:", SHOTS);
} finally {
  // rd-qa-06 lost three runs to a missing close(): the script hangs to timeout
  // and looks exactly like a page that never loaded.
  await browser.close();
}
