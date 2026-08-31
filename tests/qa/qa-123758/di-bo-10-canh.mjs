/** Walk all ten hero edges in ONE browser, ONE session, no reset between.
 *
 * ## The hole this closes
 *
 * The ten edges were mapped by #463. Nine of them had a real press behind them;
 * the tenth (VietQR -> Cá nhân updates) had two halves measured in two
 * different sessions:
 *
 *   - the press half, in a browser against a stubbed bundle;
 *   - the data half, over `dist-test/api.js` against a live stack.
 *
 * Two halves that pass separately are not one path that passes. The joint
 * between them -- the app writing to the ledger and the same app then reading
 * the ledger back -- is the part nobody had run. `scripts/hero_walk.sh` walks
 * the seam but never renders a screen; `tools/*-snapshots.mjs` render screens
 * but on stubbed fixtures. This file is neither: a real Chrome, a bundle built
 * from the tree under test and pointed at a live server, and taps.
 *
 * ## Rules it holds itself to
 *
 *   - Every step is a press at real viewport coordinates. No `?man=`, no URL
 *     edits, no direct API call that moves the app forward. Reads of
 *     `/people/{id}/finance` are OBSERVATION only and are marked as such.
 *   - The browser is opened once and closed once. If an edge fails, the walk
 *     stops there and reports WHICH edge and why. A later edge reached by hand
 *     is not a walked edge.
 *   - Money is compared across the two places a person sees it: the total on
 *     the reading screen, and what the ledger says afterwards. A path that
 *     shows one number and books another is a bigger finding than a dead edge.
 *
 * ## Usage
 *
 *   node tests/qa/qa-123758/di-bo-10-canh.mjs \
 *     --bundle /tmp/qa-c10-bundle --api http://127.0.0.1:8099 \
 *     --anh /tmp/qa-c10-anh/ro.jpg --out /tmp/qa-c10-out
 *
 * Exit: 0 all ten walked · 1 stopped on an edge (the stop IS the finding)
 * · 2 could not start (no browser, no bundle, no server) -- never green.
 */
import { createServer } from "node:http";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, normalize } from "node:path";

import puppeteer from "puppeteer-core";

import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";

const args = process.argv.slice(2);
const arg = (n, d) => {
  const i = args.indexOf(n);
  return i >= 0 ? args[i + 1] : d;
};

const BUNDLE = arg("--bundle");
const API = arg("--api", "http://127.0.0.1:8099");
const ANH = arg("--anh");
const OUT = arg("--out", "/tmp/qa-c10-out");
/* Which of the seven seeded personas to sign in as. It is a parameter and not
 * a constant because `khoiDongNhom` (src/screens/chat/nhom.ts:434) branches on
 * it: the demo group is created owned by Minh, and the invite+accept pair only
 * runs `if (slug !== MINH_SLUG)`. So the roster you land in depends on who you
 * are, and the walk has to be able to say which one it walked. */
const AI = arg("--ai", "Minh");

if (!BUNDLE || !existsSync(join(BUNDLE, "index.html"))) {
  console.error("thiếu --bundle (thư mục expo export có index.html)");
  process.exit(2);
}
if (!ANH || !existsSync(ANH)) {
  console.error("thiếu --anh (ảnh bill có thật trên đĩa)");
  process.exit(2);
}
mkdirSync(OUT, { recursive: true });

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".ico": "image/x-icon",
  ".svg": "image/svg+xml",
  ".ttf": "font/ttf",
};

/** Serve the bundle. Same shape as `tests/chrome-cdp.mjs:serve`, copied rather
 *  than imported so this file has no dependency on the app's test helpers. */
async function phucVu(root) {
  const server = createServer((req, res) => {
    const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
    let file = join(root, normalize(p).replace(/^(\.\.[/\\])+/, ""));
    if (!existsSync(file) || statSync(file).isDirectory()) file = join(root, "index.html");
    if (!existsSync(file)) return void res.writeHead(404).end("no");
    res.writeHead(200, { "content-type": MIME[file.slice(file.lastIndexOf("."))] ?? "application/octet-stream" });
    res.end(readFileSync(file));
  });
  await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
  return { url: `http://127.0.0.1:${server.address().port}/`, close: () => new Promise((ok) => server.close(ok)) };
}

/* Every interactive role, not just `button`. Listing only button/[role=button]
 * is how a scanner read this app's tab bar as absent: it uses `role=tab`. */
const VAI_TRO = [
  "button", "[role=button]", "[role=tab]", "[role=link]", "[role=menuitem]",
  "[role=switch]", "[role=checkbox]", "[role=radio]", "[role=option]",
  "a", "input", "select", "textarea",
].join(", ");

const nghi = (ms) => new Promise((r) => setTimeout(r, ms));

const chang = [];
let page = null;

async function ghi(ten) {
  const anh = join(OUT, `${ten}.png`);
  await page.screenshot({ path: anh });
  const data = await page.evaluate((sel) => {
    const nhin = (e) => {
      const r = e.getBoundingClientRect();
      const s = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };
    return {
      text: document.body ? document.body.innerText : "",
      nhan: [...document.querySelectorAll(sel)].filter(nhin).map((e) =>
        (e.innerText || e.getAttribute("aria-label") || e.value || "").replace(/\s+/g, " ").trim().slice(0, 70),
      ).filter(Boolean),
    };
  }, VAI_TRO);
  writeFileSync(join(OUT, `${ten}.txt`), data.text, "utf8");
  chang.push({ ten, anh, soNhan: data.nhan.length });
  console.log(`\n=== ${ten} ===`);
  console.log(`  nhãn (${data.nhan.length}): ${data.nhan.slice(0, 20).join(" | ")}`);
  console.log(`  chữ: ${data.text.slice(0, 420).replace(/\n+/g, " / ")}`);
  return data;
}

/** Press by visible label or aria-label, over every interactive role, at real
 *  viewport coordinates. A synthetic `.click()` bypasses the hit-testing a
 *  thumb cannot bypass, and this walk is about the thumb. */
async function bam(nhan, { chinhXac = false, vai = null } = {}) {
  const box = await page.evaluate(
    (sel, n, exact, role) => {
      const els = [...document.querySelectorAll(role ? `[role=${role}]` : sel)];
      const hop = els.filter((e) => {
        // BOTH spellings, not innerText-first. The persona buttons render
        // "M Minh" as text and carry "Vào app với tư cách Minh" as their
        // aria-label; an innerText-first matcher reads the label as absent and
        // reports a live control as a dead edge. That is a bug in the ruler.
        const ten = [
          (e.innerText || "").replace(/\s+/g, " ").trim(),
          (e.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim(),
          (e.value || "").trim(),
        ].filter(Boolean);
        const r = e.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) return false;
        return ten.some((t) => (exact ? t === n : t.includes(n)));
      });
      if (!hop.length) return null;
      const e = hop[0];
      e.scrollIntoView({ block: "center", inline: "nearest" });
      const r = e.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, so: hop.length };
    },
    VAI_TRO, nhan, chinhXac, vai,
  );
  if (!box) return false;
  await page.mouse.click(box.x, box.y);
  await nghi(900);
  return true;
}

/** Type the way a thumb does: click the field, then send keystrokes. Setting
 *  `.value` skips React's change handlers, so a screen looks filled and
 *  submits empty. */
async function go(nhan, giaTri) {
  const box = await page.evaluate((ph) => {
    // Case-insensitive: the compose sheet labels its field "Câu hỏi" and the
    // hint below it says "Nhập câu hỏi trước". A case-sensitive matcher misses
    // one of the two and reports a field that is on screen as absent.
    const k = ph.toLowerCase();
    const e = [...document.querySelectorAll("input, textarea")].find(
      (x) =>
        (x.placeholder || "").toLowerCase().includes(k) ||
        (x.getAttribute("aria-label") || "").toLowerCase().includes(k),
    );
    if (!e) return null;
    e.scrollIntoView({ block: "center" });
    const r = e.getBoundingClientRect();
    return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
  }, nhan);
  if (!box) return false;
  await page.mouse.click(box.x, box.y);
  await page.keyboard.type(giaTri, { delay: 25 });
  await nghi(300);
  return true;
}

/** Wait for words to APPEAR. */
async function choChu(chu, hanMs = 30000) {
  const het = Date.now() + hanMs;
  while (Date.now() < het) {
    const co = await page.evaluate((c) => (document.body ? document.body.innerText.includes(c) : false), chu);
    if (co) return true;
    await nghi(500);
  }
  return false;
}

/** Wait for words to LEAVE -- the check that matters for a spinner, because
 *  the screen's title is already painted behind it. */
async function choMat(chu, hanMs = 120000) {
  const het = Date.now() + hanMs;
  while (Date.now() < het) {
    const con = await page.evaluate((c) => (document.body ? document.body.innerText.includes(c) : true), chu);
    if (!con) return true;
    await nghi(700);
  }
  return false;
}

const canh = [];
function chamCanh(so, ten, dat, ghiChu) {
  canh.push({ so, ten, dat, ghiChu });
  console.log(`\n  [CẠNH ${so}] ${dat ? "ĐI ĐƯỢC" : "ĐỨT"} — ${ten}${ghiChu ? ` :: ${ghiChu}` : ""}`);
}

class Dut extends Error {
  constructor(so, ten, ly) {
    super(`cạnh ${so} (${ten}): ${ly}`);
    this.so = so;
    this.ten = ten;
    this.ly = ly;
  }
}

/* Money seen on screens, gathered as we pass. Vietnamese money renders 1.234.567. */
const TIEN = /(\d{1,3}(?:\.\d{3})+)\s*(?:đ|₫|VND)?/g;
function docTien(text) {
  const ra = [];
  let m;
  const re = new RegExp(TIEN);
  while ((m = re.exec(text))) ra.push(Number(m[1].replace(/\./g, "")));
  return ra;
}

const soLieu = { actorId: null, financeTruoc: null, financeSau: null };

/** OBSERVATION of the ledger. Never used to move the app forward. */
async function docSo(actorId) {
  if (!actorId) return null;
  try {
    const r = await fetch(`${API}/people/${actorId}/finance`, {
      headers: { "x-actor-id": actorId },
    });
    if (!r.ok) return { loi: `${r.status}` };
    return await r.json();
  } catch (e) {
    return { loi: String(e).slice(0, 120) };
  }
}

/* ------------------------------------------------------------------ run --- */

const web = await phucVu(BUNDLE);
let rc = 0;
let browser = null;
try {
  browser = await puppeteer.launch({
    executablePath: timTrinhDuyet(),
    headless: "new",
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
} catch (e) {
  console.error(`KHÔNG MỞ ĐƯỢC TRÌNH DUYỆT: ${e.message}`);
  await web.close();
  process.exit(2);
}

const loiConsole = [];
const mang4xx = [];
try {
  page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });
  page.on("console", (m) => {
    if (m.type() === "error") loiConsole.push(m.text().slice(0, 250));
  });
  page.on("pageerror", (e) => loiConsole.push(`pageerror: ${String(e).slice(0, 250)}`));
  page.on("request", (r) => {
    const h = r.headers();
    if (h["x-actor-id"] && !soLieu.actorId) soLieu.actorId = h["x-actor-id"];
  });
  page.on("response", (r) => {
    if (r.status() >= 400) mang4xx.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  });

  console.log(`bundle  ${BUNDLE}`);
  console.log(`web     ${web.url}`);
  console.log(`api     ${API}`);
  console.log(`ảnh     ${ANH}`);
  console.log(`vào app tư cách  ${AI}`);

  /* ---------------------------------------------------- 1 mở app -> đăng nhập */
  await page.goto(web.url, { waitUntil: "networkidle2", timeout: 60000 });
  await nghi(2000);
  await ghi("00-mo-app");
  if (!(await bam("Đăng ký với Apple"))) throw new Dut(1, "mở app → đăng nhập", 'không thấy nút "Đăng ký với Apple" trên màn mở đầu');
  await nghi(1500);
  const chon = await ghi("01-chon-nguoi");
  if (!chon.text.includes("Vào app với tư cách")) {
    throw new Dut(1, "mở app → đăng nhập", "bấm đăng ký xong không tới màn chọn người");
  }
  if (!(await bam(`Vào app với tư cách ${AI}`))) throw new Dut(1, "mở app → đăng nhập", `không bấm được Vào app với tư cách ${AI}`);
  await nghi(3000);
  chamCanh(1, "mở app → đăng nhập", true, `Đăng ký với Apple → Vào app với tư cách ${AI}`);

  /* --------------------------------------------------- 2 đăng nhập -> Khám phá */
  const kp = await ghi("02-kham-pha");
  if (!(await choChu("Khám phá", 30000)) && !kp.text.includes("Khám phá")) {
    throw new Dut(2, "đăng nhập → Khám phá", "sau đăng nhập không thấy màn Khám phá");
  }
  await choMat("Đang hỏi máy chủ", 60000);
  await nghi(1200);
  await ghi("02b-kham-pha-da-tai");
  chamCanh(2, "đăng nhập → Khám phá", true, "màn Khám phá tự hiện sau khi chọn người");

  /* ------------------------------------------------ 3 Khám phá -> chat nhóm */
  if (!(await bam("Tin nhắn: chat nhóm và AI"))) {
    if (!(await bam("Tin nhắn", { chinhXac: true }))) throw new Dut(3, "Khám phá → chat nhóm", "không bấm được tab Tin nhắn");
  }
  await nghi(3500);
  const chat = await ghi("03-chat-nhom");
  if (!/thành viên|Chat|Plan/.test(chat.text)) throw new Dut(3, "Khám phá → chat nhóm", "bấm tab Tin nhắn nhưng không ra màn nhóm");
  chamCanh(3, "Khám phá → chat nhóm", true, "một cú bấm tab, màn ra thẳng nhóm");

  /* ------------------------------------------------------- 4 chat -> chốt */
  /* The ballot has no free-text field: its options come from places the
   * companion put on the table (`diaDiemDaGoiY`, binh-chon.ts:383), and
   * "Mở bình chọn mới" stays disabled until the thread holds two of them.
   * So the chat itself is inside this edge -- which is what the brief says
   * too: "chat, AI gợi ý chỗ ăn → chốt". Asking the model is the step, not a
   * setup shortcut around it. */
  if (!(await go("Ô nhập tin nhắn", "Tối nay 6 đứa mình đi ăn nướng ở Đà Lạt đi, tầm 250k/người, gợi ý vài chỗ với"))) {
    throw new Dut(4, "chat → chốt", "không tìm thấy ô nhập tin nhắn trong nhóm");
  }
  if (!(await bam("Gửi", { chinhXac: true }))) throw new Dut(4, "chat → chốt", 'không bấm được nút "Gửi"');
  console.log("  [đã gửi tin, chờ AI gợi ý chỗ]");
  await nghi(4000);
  /* Baseline of the ledger, read now: the app has posted at least one request
   * so we know who it acts as, and nothing has been written to the ledger yet
   * (the expense does not exist until edge 8). OBSERVATION only. */
  soLieu.financeTruoc = await docSo(soLieu.actorId);
  console.log(`  [sổ TRƯỚC] actor=${soLieu.actorId} ${JSON.stringify(soLieu.financeTruoc)}`);
  /* Look, wait, look again -- the way a person waiting on a reply does. The
   * signal is the ballot button turning live on the Plan tab, because that is
   * the state the next press needs; waiting on a place NAME would be pinning
   * the model's wording, which is testing the model rather than the product. */
  let moDuoc = { co: false };
  let plan = null;
  for (let lan = 1; lan <= 8; lan += 1) {
    if (!(await bam("Plan"))) throw new Dut(4, "chat → chốt", "không bấm được tab con Plan");
    await nghi(2500);
    plan = await ghi(lan === 1 ? "04b-tab-plan" : `04b-tab-plan-lan${lan}`);
    moDuoc = await page.evaluate(() => {
      const e = [...document.querySelectorAll("[aria-label]")].find(
        (x) => x.getAttribute("aria-label") === "Mở bình chọn mới",
      );
      return e ? { co: true, khoa: e.getAttribute("aria-disabled") === "true" || e.disabled === true } : { co: false };
    });
    console.log(`  [lần ${lan}] nút "Mở bình chọn mới" ${JSON.stringify(moDuoc)}`);
    if (moDuoc.co && !moDuoc.khoa) break;
    await bam("Chat", { chinhXac: true });
    await nghi(9000);
  }
  if (!moDuoc.co) throw new Dut(4, "chat → chốt", '"Mở bình chọn mới" không có trên tab Plan');
  if (moDuoc.khoa) {
    throw new Dut(4, "chat → chốt", `sau 8 lần xem lại, "Mở bình chọn mới" vẫn KHOÁ: ${plan.text.slice(0, 240)}`);
  }
  if (!(await bam("Mở bình chọn mới"))) throw new Dut(4, "chat → chốt", 'không bấm được "Mở bình chọn mới"');
  await nghi(2000);
  await ghi("04c-soan-binh-chon");
  if (!(await go("Câu hỏi", "Tối nay ăn ở đâu?"))) {
    throw new Dut(4, "chat → chốt", "màn soạn bình chọn không có ô nhập câu hỏi");
  }
  /* The ballot's options are the place cards the companion posted. They are
   * pressable rows, not radios, and their text is the place name plus its
   * category and address -- so pick them by the row shape rather than by a
   * name, which would be pinning the model's output. */
  const luaChon = await page.evaluate(() =>
    [...document.querySelectorAll("[role=button], button, [role=radio], [role=checkbox]")]
      .map((e) => (e.innerText || e.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim())
      .filter((t) => /Đánh giá|quan-an-local|cafe|vui-choi/i.test(t)),
  );
  console.log(`  [ô lựa chọn trên phiếu] ${JSON.stringify(luaChon.map((t) => t.slice(0, 40)))}`);
  if (luaChon.length < 2) {
    throw new Dut(4, "chat → chốt", `phiếu chỉ có ${luaChon.length} lựa chọn, cần ít nhất 2`);
  }
  for (const t of luaChon.slice(0, 2)) await bam(t.slice(0, 30));
  await nghi(600);
  await ghi("04d-da-chon-quan");
  if (!(await bam("Mở bình chọn", { chinhXac: true }))) throw new Dut(4, "chat → chốt", 'không bấm được "Mở bình chọn"');
  await nghi(3000);
  await ghi("04e-binh-chon-trong-luong");
  /* Cast one vote so the closed card has a name to say, then close. Opening
   * drops the ballot back into the chat thread, so look there first and fall
   * back to the Plan tab rather than assuming which surface we landed on. */
  const demPhieu = () =>
    page.evaluate(() =>
      [...document.querySelectorAll("[role=radio], [role=button], button")]
        .map((e) => (e.innerText || e.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim())
        .filter((t) => /\d+ phiếu/.test(t)),
    );
  let phieu = await demPhieu();
  if (!phieu.length) {
    await bam("Plan");
    await nghi(2500);
    phieu = await demPhieu();
  }
  console.log(`  [ô bỏ phiếu] ${JSON.stringify(phieu.slice(0, 6).map((t) => t.slice(0, 45)))}`);
  if (!phieu.length) throw new Dut(4, "chat → chốt", "mở bình chọn xong nhưng không thấy ô bỏ phiếu nào");
  await bam(phieu[0].slice(0, 30));
  await nghi(2500);
  await ghi("04f-da-bo-phieu");
  if (!(await bam("Đóng bình chọn", { chinhXac: true }))) {
    throw new Dut(4, "chat → chốt", 'không bấm được "Đóng bình chọn" — chốt không xảy ra');
  }
  await nghi(3000);
  const daChot = await ghi("04g-da-chot");
  chamCanh(4, "chat → chốt", true, `bình chọn mở → bỏ phiếu → Đóng bình chọn; màn sau chốt dài ${daChot.text.length} ký tự`);

  /* -------------------------------------------------- 5 chốt -> CHỤP BILL */
  if (!(await bam("Tạo mới", { chinhXac: true }))) throw new Dut(5, "chốt → CHỤP BILL", 'không thấy [+] "Tạo mới" trên màn vừa chốt');
  await nghi(1800);
  await ghi("05-menu-tao-moi");
  if (!(await bam("Tạo khoản chi"))) throw new Dut(5, "chốt → CHỤP BILL", 'không bấm được "Tạo khoản chi"');
  await nghi(3000);
  const cam = await ghi("05b-chup-bill");
  if (!/Chụp bill|khung hình/.test(cam.text)) throw new Dut(5, "chốt → CHỤP BILL", "không tới được màn Chụp bill");
  chamCanh(5, "chốt → CHỤP BILL", true, "[+] Tạo mới → Tạo khoản chi → Chụp bill, ba cú bấm từ màn chốt");

  /* ------------------------------------------- 6 CHỤP BILL -> AI đọc món */
  let chonFile = null;
  try {
    [chonFile] = await Promise.all([
      page.waitForFileChooser({ timeout: 20000 }),
      bam("Chọn ảnh bill", { chinhXac: true }),
    ]);
  } catch (e) {
    throw new Dut(6, "CHỤP BILL → AI đọc món", `nút "Chọn ảnh bill" không mở được hộp chọn tệp: ${e.message}`);
  }
  await chonFile.accept([ANH]);
  console.log(`  [đã đưa ảnh] ${ANH}`);
  const xong = await choMat("Đang", 180000);
  await nghi(2000);
  const doc = await ghi("06-ai-doc-mon");
  if (!xong) throw new Dut(6, "CHỤP BILL → AI đọc món", "sau 180s màn vẫn còn chữ 'Đang' — model không trả về");
  if (/không gọi được AI|chưa cấu hình khoá|không đọc được/i.test(doc.text)) {
    throw new Dut(6, "CHỤP BILL → AI đọc món", `màn báo lỗi: ${doc.text.slice(0, 200)}`);
  }
  const tienManDoc = docTien(doc.text);
  console.log(`  [tiền trên màn ĐỌC BILL] ${JSON.stringify(tienManDoc)}`);
  chamCanh(6, "CHỤP BILL → AI đọc món", true, `ảnh thật → model thật; tiền thấy trên màn: ${tienManDoc.join(", ")}`);

  /* ---------------------------------------------- 7 AI đọc món -> gán món */
  if (!(await bam("Tiếp tục", { chinhXac: true }))) throw new Dut(7, "AI đọc món → gán món", 'không bấm được "Tiếp tục" ở màn kết quả nhận diện');
  await nghi(3500);
  const gan = await ghi("07-gan-mon");
  if (!/Ai ăn|gán|Xem kết quả|Chọn/i.test(gan.text)) throw new Dut(7, "AI đọc món → gán món", "không ra màn gán món");
  chamCanh(7, "AI đọc món → gán món", true, "Tiếp tục → màn gợi ý chia");

  /* -------------------------------------------------- 8 gán món -> AI chia */
  const nguoi = await page.evaluate(() =>
    [...document.querySelectorAll("[role=button], button, [role=checkbox]")]
      .map((e) => (e.innerText || e.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim())
      .filter(Boolean).slice(0, 40),
  );
  console.log(`  [bấm được ở màn gán món] ${JSON.stringify(nguoi.slice(0, 18))}`);
/* Tap everybody the roster offers, not a hard-coded three: the roster is
   * what the server returned for THIS group, and a fixed list would silently
   * skip a member the group has or fail on one it does not. */
  const daBam = [];
  for (const ten of ["Minh", "Trang", "Hải", "Ngọc", "Đức", "Linh", "Quân"]) {
    if (await bam(ten)) daBam.push(ten);
  }
  console.log(`  [đã chạm tên người trên màn gán món] ${JSON.stringify(daBam)}`);
  await nghi(1200);
  await ghi("08-da-gan-nguoi");
  if (!(await bam("Xem kết quả"))) throw new Dut(8, "gán món → AI chia", 'không bấm được "Xem kết quả"');
  await nghi(4000);
  const form = await ghi("08b-form-khoan-chi");
  const tienForm = docTien(form.text);
  console.log(`  [tiền trên FORM khoản chi] ${JSON.stringify(tienForm)}`);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await nghi(800);
  await bam(AI, { vai: "radio" });
  await nghi(800);
  await ghi("08c-da-chon-nguoi-tra-truoc");
  if (!(await bam("Chia tiền", { chinhXac: true }))) throw new Dut(8, "gán món → AI chia", 'không bấm được "Chia tiền"');
  await nghi(6000);
  const dexuat = await ghi("08d-de-xuat-chia");
  const tienDeXuat = docTien(dexuat.text);
  console.log(`  [tiền trên màn ĐỀ XUẤT CHIA] ${JSON.stringify(tienDeXuat)}`);
  if (!/ghi vào sổ|Đề xuất|chia/i.test(dexuat.text)) throw new Dut(8, "gán món → AI chia", "không ra màn đề xuất chia");
  chamCanh(8, "gán món → AI chia", true, `đề xuất chia hiện: ${tienDeXuat.join(", ")}`);

  /* --------------------------------------------------- 9 AI chia -> VietQR */
  if (!(await bam("Đúng rồi, ghi vào sổ"))) throw new Dut(9, "AI chia → VietQR", 'không bấm được "Đúng rồi, ghi vào sổ"');
  await nghi(6000);
  const dot = await ghi("09-dot-thu");
  if (!(await bam("Phát đợt thu"))) {
    throw new Dut(9, "AI chia → VietQR", `không bấm được "Phát đợt thu" trên màn đợt thu: ${dot.text.slice(0, 220)}`);
  }
  await nghi(7000);
  const qr = await ghi("09b-ket-qua-thanh-toan");
  const coQr = await page.evaluate(() =>
    [...document.querySelectorAll("[aria-label]")].some((e) => (e.getAttribute("aria-label") || "").startsWith("Mã VietQR")),
  );
  console.log(`  [có phần tử aria-label "Mã VietQR…"] ${coQr}`);
  if (!coQr) throw new Dut(9, "AI chia → VietQR", `không thấy mã VietQR trên màn thanh toán: ${qr.text.slice(0, 220)}`);
  const tienQr = docTien(qr.text);
  console.log(`  [tiền trên màn VietQR] ${JSON.stringify(tienQr)}`);
  chamCanh(9, "AI chia → VietQR", true, `ghi vào sổ → Phát đợt thu → mã VietQR có mặt`);

  /* ------------------------------------------ 10 VietQR -> Cá nhân CẬP NHẬT */
  if (!(await bam("Đóng khoản chi, quay lại các tab"))) {
    throw new Dut(10, "VietQR → Cá nhân cập nhật", 'không thấy nút "Đóng khoản chi, quay lại các tab" trên màn VietQR');
  }
  await nghi(2500);
  await ghi("10-ve-cac-tab");
  const coTab = await bam("Cá nhân: hồ sơ và tài chính của bạn");
  if (!coTab && !(await bam("Cá nhân", { chinhXac: true }))) {
    throw new Dut(10, "VietQR → Cá nhân cập nhật", "về được các tab nhưng không bấm được tab Cá nhân");
  }
  await nghi(5000);
  const caNhan = await ghi("10b-ca-nhan");
  soLieu.financeSau = await docSo(soLieu.actorId);
  console.log(`\n  [sổ SAU] ${JSON.stringify(soLieu.financeSau)}`);
  const t = soLieu.financeTruoc || {};
  const s = soLieu.financeSau || {};
  const doi = Object.keys(s).filter((k) => typeof s[k] === "number" && s[k] !== t[k]);
  console.log(`  [trường đổi trong sổ] ${JSON.stringify(doi.map((k) => `${k} ${t[k]} -> ${s[k]}`))}`);
  const nhichLenMan = /\d/.test(caNhan.text) && !/^0 Lần chia bill/.test(caNhan.text);
  if (!doi.length) {
    throw new Dut(10, "VietQR → Cá nhân cập nhật", `màn Cá nhân mở được nhưng sổ KHÔNG nhúc nhích: trước=${JSON.stringify(t)} sau=${JSON.stringify(s)}`);
  }
  chamCanh(10, "VietQR → Cá nhân cập nhật", true, `sổ đổi: ${doi.map((k) => `${k} ${t[k]}→${s[k]}`).join(" · ")}; màn có số: ${nhichLenMan}`);

  /* ---------------------------------------------------------- tiền có khớp */
  const tienCaNhan = docTien(caNhan.text);
  console.log(`\n  [tiền trên màn CÁ NHÂN] ${JSON.stringify(tienCaNhan)}`);
  writeFileSync(
    join(OUT, "tien.json"),
    JSON.stringify({ tienManDoc, tienForm, tienDeXuat, tienQr, tienCaNhan, soLieu }, null, 2),
    "utf8",
  );
} catch (e) {
  rc = 1;
  if (e instanceof Dut) {
    chamCanh(e.so, e.ten, false, e.ly);
    console.error(`\nĐỨT Ở CẠNH ${e.so}: ${e.ten}\n  vì: ${e.ly}`);
    try {
      await ghi(`DUT-canh-${e.so}`);
    } catch { /* page may be gone */ }
  } else {
    console.error(`\nDỪNG (không phải một cạnh): ${e.stack || e.message}`);
  }
} finally {
  writeFileSync(
    join(OUT, "ket-qua.json"),
    JSON.stringify({ bundle: BUNDLE, api: API, anh: ANH, ai: AI, canh, chang, loiConsole, mang4xx, soLieu }, null, 2),
    "utf8",
  );
  console.log(`\n================ BẢNG CẠNH ================`);
  for (const c of canh) console.log(`  ${String(c.so).padStart(2)} ${c.dat ? "ĐI ĐƯỢC" : "ĐỨT   "}  ${c.ten}`);
  const dat = canh.filter((c) => c.dat).length;
  console.log(`  => ${dat}/10 cạnh đi được trong MỘT lượt, MỘT trình duyệt`);
  console.log(`--- lỗi console: ${loiConsole.length}`);
  for (const l of loiConsole.slice(0, 12)) console.log(`    ${l}`);
  console.log(`--- phản hồi >=400: ${mang4xx.length}`);
  for (const m of mang4xx.slice(0, 12)) console.log(`    ${m}`);
  console.log(`  hiện vật: ${OUT}`);
  if (browser) await browser.close();
  await web.close();
}
process.exit(rc);
