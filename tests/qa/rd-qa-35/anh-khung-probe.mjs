/* Đo khung ảnh của `ui/Anh.tsx` trên DOM SỐNG, không đọc source.
 *
 * PR #195 nói ba điều mà không cổng nào trong repo đo được, vì cả hai ca test
 * hiện có (`apps/mobile/tests/anh.test.mjs`) đọc **văn bản của file nguồn**:
 * chúng khớp `/<Image\b/` và `/onError=/`. Một file nguồn khớp regex vẫn có
 * thể vẽ ra một cái hộp cao 0px, vẫn có thể in `ECONNREFUSED` lên màn, và vẫn
 * có thể đọc ra hai lần trong cây trợ năng.
 *
 * Nên file này dựng bundle đã export, chạy trong Chromium thật ở 390x844, và
 * đọc lại `getBoundingClientRect`, `document.body.innerText`, danh sách
 * request mạng, và cây AX của chính trình duyệt.
 *
 * Bốn lượt, mỗi lượt một trạng thái ảnh, cùng một fixture còn lại:
 *
 *   khong-anh   cả hai row `photo_url = null`      -> khung phải giữ chỗ
 *   co-anh      cả hai row trỏ vào PNG thật        -> khung phải y hệt lượt trên
 *   hong-refused row đầu trỏ vào cổng không ai nghe -> ECONNREFUSED không được lọt
 *   hong-404     row đầu trỏ vào file không tồn tại -> mã lỗi không được lọt
 *
 * Câu hỏi "khung có giữ chỗ không" ở hai màn KHÔNG truyền uri (Mở đầu, Cá
 * nhân) không trả lời được bằng A/B, vì không đường nào đưa URL vào đó hôm
 * nay. Ở đó phép đo là: gỡ toàn bộ nội dung bên trong khung khỏi layout
 * (`display:none` cho mọi con) rồi đo lại hộp. Hộp không đổi nghĩa là kích
 * thước do chính khung khai, không do nội dung đẩy ra.
 *
 * Công cụ QA, không phải code chạy trong app. Chạy từ gốc repo:
 *
 *     cd apps/mobile && npm run build:check
 *     node tests/qa/rd-qa-35/anh-khung-probe.mjs
 *
 * Thoát 0 khi mọi khẳng định đúng, 1 khi có khẳng định sai, 2 khi không đo
 * được (thiếu bundle, thiếu Chromium) — "không đo được" không bao giờ được
 * trông giống "sạch".
 */
import fs from "node:fs";
import http from "node:http";
import zlib from "node:zlib";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const MOBILE = path.join(REPO, "apps/mobile");
const TOOLS = path.join(MOBILE, "tools");

const { CHROME, createStaticServer, listen, closeServer, waitForScreen } = await import(
  path.join(TOOLS, "screen-snapshots.mjs")
);
const { installTabStubs } = await import(path.join(TOOLS, "tab-snapshots.mjs"));

const API_BASE = "http://api.build-check.invalid";
const NGUOI = "minh";
const BUILD = path.join(MOBILE, ".expo-build-check");
const OUT = path.join(REPO, ".qa-anh-probe");

/* Ba địa chỉ ảnh, tất cả trên CHÍNH origin API — vì `nguonAnhAnToan` (landed
 * cùng #195) chỉ cho qua địa chỉ trên `EXPO_PUBLIC_API_URL`. Một URL tuyệt đối
 * tới 127.0.0.1 sẽ bị TỪ CHỐI, và thẻ vẽ chỗ chờ, khiến cả bộ quét thành đồ
 * trang trí mà không đổi một dòng nào. Đường tương đối là đúng hình dạng route
 * ảnh thật trả về. */
const ANH_OK = "/anh-thu-dia-diem.png";
const ANH_404 = "/khong-ton-tai-dau.png";
const ANH_CHET = "/may-chu-tat.png";
const ANH_OK_URL = `${API_BASE}${ANH_OK}`;
const ANH_404_URL = `${API_BASE}${ANH_404}`;
const ANH_CHET_URL = `${API_BASE}${ANH_CHET}`;

/* --------------------------------------------------------------- fixtures --- */

/** Hàng /places hợp lệ — chép từ `tools/tab-snapshots.mjs` nên parser không
 *  ném và màn hiện danh sách chứ không hiện panel "dữ liệu sai". */
function place(over = {}) {
  return {
    id: "p-1",
    name: "Tiệm Nướng Xóm Lào",
    category: "quan-an-local",
    kinds: ["BBQ", "Lào", "Local"],
    rating: 4.7,
    rating_count: 128,
    distance_km: 1.2,
    price_min_vnd: 200000,
    price_max_vnd: 250000,
    address: "27/1 Yersin, P.10, TP. Đà Lạt",
    open_now: true,
    open_hours: "10:00 – 22:30",
    travel_minutes: 25,
    photo_count: 18,
    traits: ["Chill", "View đẹp"],
    group_fit: { min_people: 4, max_people: 10, relation: "Bạn bè" },
    flag: null,
    lat: 11.9404,
    lng: 108.4383,
    match: { score: 95, source: "ai", verdict: "hop", reason: "Hợp vì ngân sách và đồ nướng.", factors: [] },
    ...over,
  };
}

const contextId = "1aa0be7f-9c3d-4e1a-8b2f-a7c5d9e3f1b6";
const personId = "2bb1cf8e-7d4a-4f2b-9c3e-b8d6e0f4a2c7";

function baseFixtures() {
  return {
    contextId,
    personId,
    categories: [
      { id: "quan-an-local", label: "Quán ăn" },
      { id: "cafe", label: "Cafe" },
    ],
    places: [
      place(),
      place({
        id: "p-2",
        name: "Lẩu Gà Lá É Tao Ngộ",
        rating: 4.5,
        distance_km: 2.4,
        traits: ["Đông vui", "Giá mềm"],
        match: { score: 88, source: "ai", verdict: "hop", reason: "Hợp vì nhóm đông và ăn khuya.", factors: [] },
      }),
    ],
    // Hình dạng chép từ `tools/tab-snapshots.mjs`: Cá nhân từ chối một
    // fixture thiếu field và hiện panel lỗi thay vì màn, và một panel lỗi
    // chụp lại dưới tên "ca-nhan" đọc y hệt một lượt quét thành công.
    finance: {
      person_id: personId,
      display_name: "Minh",
      spend_vnd: 860000,
      settled_vnd: 500000,
      outstanding_vnd: 360000,
      expense_count: 4,
      group_count: 2,
      movements: [
        {
          obligation_id: "8bb7cf4e-1d0a-4f8b-9c9e-b4d2e6f0a8c3",
          direction: "out",
          amount_vnd: 160000,
          counterparty_id: "3cc2da9f-6e5b-4a3c-8d4f-c9e7f1a5b3d8",
          counterparty_name: "Trang",
          context_id: contextId,
          context_name: "Hội Đà Lạt",
          occasion: "Lẩu gà lá é",
          occurred_at: "2026-08-28T13:00:00Z",
        },
      ],
    },
  };
}

/* ----------------------------------------------------------------- ảnh thử --- */

/** PNG thật, sinh lúc chạy. Không commit nhị phân — repo guard đúng khi từ chối. */
function vietPngThu(file, w = 480, h = 360) {
  const raw = Buffer.alloc(h * (w * 3 + 1));
  let o = 0;
  for (let y = 0; y < h; y++) {
    raw[o++] = 0;
    for (let x = 0; x < w; x++) {
      const t = (x / w) * 0.55 + (y / h) * 0.45;
      raw[o++] = Math.min(255, Math.round(232 - t * 96));
      raw[o++] = Math.min(255, Math.round(122 - t * 44));
      raw[o++] = Math.min(255, Math.round(96 + t * 78));
    }
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(zlib.crc32(body) >>> 0);
    return Buffer.concat([len, body, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  fs.writeFileSync(
    file,
    Buffer.concat([
      Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
      chunk("IHDR", ihdr),
      chunk("IDAT", zlib.deflateSync(raw)),
      chunk("IEND", Buffer.alloc(0)),
    ]),
  );
}

/** Một cổng chắc chắn không ai nghe: mở rồi đóng ngay, giữ lại số. */
async function congChet() {
  const s = http.createServer(() => {});
  const port = await new Promise((res) => s.listen(0, "127.0.0.1", () => res(s.address().port)));
  await new Promise((res) => s.close(res));
  return port;
}

/* ------------------------------------------------------------- phép đo DOM --- */

/** Mọi khung `Anh` trên trang, đọc từ layout thật.
 *
 * Khung nhận diện bằng `role="img"` (alt có chữ) hoặc bằng dấu vân tay cấu
 * trúc: một View `overflow:hidden` có con đầu là lớp phủ tuyệt đối inset 0.
 * Nhận diện theo cả hai vì khung trang trí (`alt=""`) rời khỏi cây trợ năng
 * đúng theo thiết kế, nên `role="img"` một mình sẽ bỏ sót Mở đầu và băng bìa. */
function doKhung(page) {
  return page.evaluate(() => {
    const r = (n) => Math.round(n * 100) / 100;
    const hop = (el) => {
      const b = el.getBoundingClientRect();
      return { x: r(b.x), y: r(b.y), w: r(b.width), h: r(b.height) };
    };
    const out = [];
    for (const el of document.querySelectorAll("*")) {
      const cs = getComputedStyle(el);
      if (cs.overflow !== "hidden") continue;
      const first = el.firstElementChild;
      if (!first) continue;
      const fcs = getComputedStyle(first);
      const phu =
        fcs.position === "absolute" &&
        ["top", "left", "right", "bottom"].every((p) => fcs[p] === "0px");
      if (!phu) continue;
      // Sâu, không chỉ con trực tiếp: react-native-web bọc <Image> thành
      // <div><div background-image><img></div>, nên phép tìm nông báo "không
      // có ảnh" trên đúng cái khung đang giữ một tấm ảnh. Đã đo nhầm một lần.
      const img = [...el.querySelectorAll("*")].find(
        (c) => c.tagName === "IMG" || getComputedStyle(c).backgroundImage.startsWith("url("),
      );
      out.push({
        nhan: el.getAttribute("aria-label") ?? null,
        vaiTro: el.getAttribute("role") ?? null,
        an: el.getAttribute("aria-hidden") ?? null,
        hopKhung: hop(el),
        tiLe: r(el.getBoundingClientRect().width / (el.getBoundingClientRect().height || 1)),
        aspectRatioCss: cs.aspectRatio,
        hopCho: hop(first),
        coAnh: Boolean(img),
        hopAnh: img ? hop(img) : null,
        viTriAnh: img ? getComputedStyle(img).position : null,
        // Icon ảnh vỡ của trình duyệt chỉ xuất hiện trên <img> còn trong cây
        // và còn `src` sau khi lỗi. Ghi lại để nói được câu đó bằng số.
        imgConSrc: img && img.tagName === "IMG" ? (img.getAttribute("src") || "") !== "" : false,
      });
    }
    return out;
  });
}

/** Hộp của khung sau khi mọi con bị gỡ khỏi layout, rồi trả lại nguyên trạng.
 *  Đây là phép đo "khung tự khai kích thước" cho màn không truyền uri. */
function doKhungRong(page) {
  return page.evaluate(() => {
    const r = (n) => Math.round(n * 100) / 100;
    const out = [];
    for (const el of document.querySelectorAll("*")) {
      const cs = getComputedStyle(el);
      if (cs.overflow !== "hidden") continue;
      const first = el.firstElementChild;
      if (!first) continue;
      const fcs = getComputedStyle(first);
      if (
        fcs.position !== "absolute" ||
        !["top", "left", "right", "bottom"].every((p) => fcs[p] === "0px")
      )
        continue;
      const truoc = el.getBoundingClientRect();
      const cu = [...el.children].map((c) => [c, c.style.display]);
      for (const [c] of cu) c.style.display = "none";
      void el.offsetHeight;
      const sau = el.getBoundingClientRect();
      for (const [c, d] of cu) c.style.display = d;
      out.push({
        nhan: el.getAttribute("aria-label") ?? null,
        truoc: { w: r(truoc.width), h: r(truoc.height) },
        sau: { w: r(sau.width), h: r(sau.height) },
      });
    }
    return out;
  });
}

/* --------------------------------------------------------------- một lượt --- */

async function motLuot({
  browser, port, ten, photo0, photo1, tab = "kham-pha", needle,
  goLai = true, khongTab = false, anhBytes,
}) {
  const fixtures = baseFixtures();
  fixtures.places[0].photo_url = photo0;
  fixtures.places[1].photo_url = photo1;

  const page = await browser.newPage();
  page.setDefaultTimeout(30000);
  const loi = [];
  const requests = [];
  page.on("pageerror", (e) => loi.push(String(e)));

  // `<Image>` KHÔNG đi qua stub fetch — nó tự tải. `api.build-check.invalid`
  // cố ý không phân giải được, nên phải trả lời ở đây. Cùng cơ chế mà
  // `tools/tab-snapshots.mjs` trên main dùng, chép chứ không phát minh lại.
  await page.setRequestInterception(true);
  page.on("request", (req) => {
    const u = req.url();
    if (req.resourceType() === "image" || /\.png(\?|$)/.test(u)) requests.push(u);
    if (u === ANH_OK_URL) {
      req.respond({ status: 200, contentType: "image/png", body: anhBytes });
      return;
    }
    if (u === ANH_404_URL) {
      req.respond({ status: 404, contentType: "text/plain", body: "khong co" });
      return;
    }
    if (u === ANH_CHET_URL) {
      req.abort("connectionrefused");
      return;
    }
    req.continue();
  });

  await page.evaluateOnNewDocument(installTabStubs, API_BASE, fixtures);
  const frag = khongTab ? "" : `#tab=${tab}&nguoi=${NGUOI}`;
  await page.goto(`http://127.0.0.1:${port}/index.html${frag}`, { waitUntil: "domcontentloaded" });
  await waitForScreen(page, ten, needle);
  await page.waitForNetworkIdle({ idleTime: 700, timeout: 20000 }).catch(() => {});
  await new Promise((r) => setTimeout(r, 400));

  const khung = await doKhung(page);
  const khungRong = await doKhungRong(page);
  const chu = await page.evaluate(() => document.body.innerText);
  const ax = await page.accessibility.snapshot({ interestingOnly: false });
  fs.mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: path.join(OUT, `${ten}.png`) });

  // Ép re-render TRƯỚC khi đóng trang: gõ 6 ký tự vào ô tìm kiếm, tức 6 lượt
  // set state trên KhamPha, tức 6 lần thẻ vẽ lại — mà không unmount thẻ nào.
  // Bốn trang mở cùng lúc làm CDP hết giờ, nên mỗi lượt tự đo rồi tự đóng.
  const anhTruoc = requests.filter(laAnhThu).length;
  if (goLai) await goVaoOTim(page);
  const anhSau = requests.filter(laAnhThu).length;
  const chuSauGo = await page.evaluate(() => document.body.innerText);
  await page.close();

  return { ten, khung, khungRong, chu, chuSauGo, ax, requests, loi, anhTruoc, anhSau };
}

/** Request nào là request của chính tấm ảnh đang thử. */
function laAnhThu(u) {
  return u === ANH_OK_URL || u === ANH_404_URL || u === ANH_CHET_URL;
}

/** Ép re-render mà KHÔNG unmount thẻ: gõ vào ô tìm kiếm.
 *  Trả về số request ảnh phát sinh thêm. */
async function goVaoOTim(page, lan = 6) {
  const sel = 'input[placeholder^="Quán nướng"]';
  await page.waitForSelector(sel, { timeout: 15000 });
  await page.focus(sel);
  for (let i = 0; i < lan; i++) {
    await page.keyboard.type("a", { delay: 30 });
    await new Promise((r) => setTimeout(r, 150));
  }
  const go = await page.$eval(sel, (e) => e.value);
  if (go.length !== lan) throw new Error(`o tim kiem chi nhan ${go.length}/${lan} ky tu`);
  await new Promise((r) => setTimeout(r, 900));
}

/* ------------------------------------------------------------ khẳng định --- */

const ket = [];
function chac(ok, ten, chiTiet) {
  ket.push({ ok: Boolean(ok), ten, chiTiet });
  console.log(`${ok ? "  ok  " : " FAIL "} ${ten}${chiTiet ? `\n         ${chiTiet}` : ""}`);
}

function timKhung(khung, nhan) {
  return khung.find((k) => k.nhan === nhan) ?? null;
}

/* -------------------------------------------------------------------- main --- */

async function main() {
  if (!fs.existsSync(path.join(BUILD, "index.html"))) {
    console.error(`Khong co bundle o ${BUILD}. Chay: cd apps/mobile && npm run build:check`);
    process.exit(2);
  }
  if (!fs.existsSync(CHROME)) {
    console.error(`Khong co Chromium o ${CHROME}`);
    process.exit(2);
  }

  const server = createStaticServer(BUILD);
  let browser = null;
  try {
    const port = await listen(server);
    const anhFile = path.join(BUILD, "anh-thu-dia-diem.png");
    vietPngThu(anhFile);
    const anhBytes = fs.readFileSync(anhFile);

    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: true,
      protocolTimeout: 180000,
      defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    const needle = "Tiệm Nướng Xóm Lào";
    const chung = { browser, port, needle, anhBytes };
    const A = await motLuot({ ...chung, ten: "khong-anh", photo0: null, photo1: null });
    const B = await motLuot({ ...chung, ten: "co-anh", photo0: ANH_OK, photo1: ANH_OK });
    const C = await motLuot({ ...chung, ten: "hong-refused", photo0: ANH_CHET, photo1: null });
    const D = await motLuot({ ...chung, ten: "hong-404", photo0: ANH_404, photo1: null });

    console.log("\n=== 1. KHUNG CÓ GIỮ CHỖ THẬT KHÔNG ===\n");

    const NHAN1 = "Ảnh Tiệm Nướng Xóm Lào";
    const NHAN2 = "Ảnh Lẩu Gà Lá É Tao Ngộ";
    for (const nhan of [NHAN1, NHAN2]) {
      const a = timKhung(A.khung, nhan);
      const b = timKhung(B.khung, nhan);
      chac(a && b, `khung "${nhan}" có mặt ở cả hai lượt`, `khong-anh=${!!a} co-anh=${!!b}`);
      if (!a || !b) continue;
      chac(
        a.hopKhung.w === b.hopKhung.w && a.hopKhung.h === b.hopKhung.h,
        `"${nhan}": kích thước khung y hệt khi uri=null và khi có ảnh`,
        `khong-anh ${a.hopKhung.w}x${a.hopKhung.h} · co-anh ${b.hopKhung.w}x${b.hopKhung.h}`,
      );
      chac(
        a.tiLe === b.tiLe,
        `"${nhan}": tỉ lệ khung y hệt`,
        `khong-anh ${a.tiLe} · co-anh ${b.tiLe}`,
      );
      chac(
        a.hopKhung.x === b.hopKhung.x && a.hopKhung.y === b.hopKhung.y,
        `"${nhan}": vị trí khung không nhảy`,
        `khong-anh (${a.hopKhung.x},${a.hopKhung.y}) · co-anh (${b.hopKhung.x},${b.hopKhung.y})`,
      );
    }
    const b1 = timKhung(B.khung, NHAN1);
    chac(b1?.coAnh, `lượt co-anh: khung "${NHAN1}" thật sự có phần tử ảnh`, JSON.stringify(b1?.hopAnh));
    if (b1?.coAnh) {
      chac(
        b1.hopAnh.w === b1.hopKhung.w && b1.hopAnh.h === b1.hopKhung.h,
        "ảnh lấp đúng khung, không tràn không thụt",
        `ảnh ${b1.hopAnh.w}x${b1.hopAnh.h} · khung ${b1.hopKhung.w}x${b1.hopKhung.h}`,
      );
      chac(b1.viTriAnh === "absolute", "ảnh nằm ngoài dòng layout (position:absolute)", b1.viTriAnh);
    }
    const a1 = timKhung(A.khung, NHAN1);
    chac(!a1?.coAnh, `lượt khong-anh: khung "${NHAN1}" KHÔNG có phần tử ảnh`, `coAnh=${a1?.coAnh}`);

    console.log("\n--- khung tự khai kích thước (gỡ hết nội dung khỏi layout) ---\n");
    for (const k of A.khungRong) {
      chac(
        k.truoc.w === k.sau.w && k.truoc.h === k.sau.h,
        `khung ${k.nhan ? `"${k.nhan}"` : "(trang trí, alt=\"\")"} giữ nguyên hộp khi nội dung bị gỡ`,
        `trước ${k.truoc.w}x${k.truoc.h} · sau ${k.sau.w}x${k.sau.h}`,
      );
    }

    console.log("\n=== 2. LOAD HỎNG THÌ SAO ===\n");

    const RO = [
      "ECONNREFUSED", "ERR_CONNECTION", "ERR_NAME", "ERR_FILE", "net::",
      "Failed to load", "404", "500", "Not Found", "khong-ton-tai-dau",
      "127.0.0.1", "anh-thu-dia-diem",
    ];
    for (const run of [C, D]) {
      const lot = RO.filter((s) => run.chu.includes(s));
      chac(lot.length === 0, `lượt ${run.ten}: không mã lỗi/URL nào lọt lên màn`, `lọt: ${JSON.stringify(lot)}`);
      const k = timKhung(run.khung, NHAN1);
      chac(k, `lượt ${run.ten}: khung "${NHAN1}" vẫn còn trên màn`);
      if (k) {
        const a = timKhung(A.khung, NHAN1);
        chac(
          k.hopKhung.w === a.hopKhung.w && k.hopKhung.h === a.hopKhung.h,
          `lượt ${run.ten}: hộp bằng đúng lượt khong-anh (quay về chỗ chờ, layout không nhảy)`,
          `${run.ten} ${k.hopKhung.w}x${k.hopKhung.h} · khong-anh ${a.hopKhung.w}x${a.hopKhung.h}`,
        );
        chac(!k.coAnh, `lượt ${run.ten}: phần tử ảnh đã rời DOM (không icon ảnh vỡ)`, `coAnh=${k.coAnh} imgConSrc=${k.imgConSrc}`);
      }
      chac(run.loi.length === 0, `lượt ${run.ten}: không lỗi JS nào`, run.loi.join(" | "));
    }

    console.log("\n--- 'hong' có dính theo URI không: re-render KHÔNG bắn lại ---\n");
    for (const run of [C, D]) {
      chac(
        run.anhSau === run.anhTruoc,
        `lượt ${run.ten}: 6 lần gõ (6 re-render) KHÔNG sinh request ảnh mới`,
        `trước ${run.anhTruoc} · sau ${run.anhSau}`,
      );
      const lotSau = RO.filter((s) => run.chuSauGo.includes(s));
      chac(lotSau.length === 0, `lượt ${run.ten}: sau re-render vẫn không mã lỗi nào`, JSON.stringify(lotSau));
    }
    // Đối chứng cho chính phép đếm trên: lượt ảnh SỐNG phải có ít nhất một
    // request. Nếu không, số 0 ở hai lượt hỏng chỉ nói bộ đếm chết.
    chac(B.anhTruoc >= 1, "đối chứng: lượt co-anh có request ảnh thật (bộ đếm sống)", `co-anh=${B.anhTruoc}`);
    chac(C.anhTruoc >= 1, "đối chứng: lượt hong-refused CÓ bắn request lần đầu", `=${C.anhTruoc}`);
    chac(D.anhTruoc >= 1, "đối chứng: lượt hong-404 CÓ bắn request lần đầu", `=${D.anhTruoc}`);
    chac(B.anhSau === B.anhTruoc, "lượt co-anh: re-render cũng không bắn lại ảnh đã tải xong", `${B.anhTruoc} -> ${B.anhSau}`);

    console.log("\n=== 3. TRÌNH ĐỌC MÀN HÌNH ===\n");

    const phang = (n, acc = []) => {
      if (!n) return acc;
      acc.push({ role: n.role, name: n.name ?? "" });
      for (const c of n.children ?? []) phang(c, acc);
      return acc;
    };
    for (const run of [A, B]) {
      const nodes = phang(run.ax);
      for (const nhan of [NHAN1, NHAN2]) {
        const dem = nodes.filter((n) => n.name === nhan).length;
        chac(dem === 1, `lượt ${run.ten}: "${nhan}" đọc ra ĐÚNG MỘT lần`, `đếm được ${dem}`);
      }
      const anhKhongNhan = nodes.filter(
        (n) => (n.role === "image" || n.role === "img") && !n.name.trim(),
      );
      chac(
        anhKhongNhan.length === 0,
        `lượt ${run.ten}: không node ảnh nào không nhãn ("unlabelled image")`,
        JSON.stringify(anhKhongNhan),
      );
      // Badge và ruy băng nằm BÊN TRONG khung role="img". ARIA nói con của
      // role=img là trang trí; nếu Chrome áp đúng luật đó thì "AI MATCH" biến
      // mất khỏi cây và người dùng trình đọc màn hình mất chỉ số của chính PR
      // #143. Đo, không đoán.
      const coMatch = nodes.some((n) => /AI MATCH|95%|88%/.test(n.name));
      chac(coMatch, `lượt ${run.ten}: huy hiệu AI MATCH vẫn còn trong cây trợ năng`, `nodes=${nodes.length}`);
    }
    // Khung trang trí (alt="") phải vắng mặt hẳn.
    const nodesModau = phang(A.ax);
    chac(
      !nodesModau.some((n) => n.name === "Ảnh địa điểm"),
      "không khung nào đọc ra nhãn mặc định 'Ảnh địa điểm' (tức name luôn được truyền)",
    );

    console.log("\n=== 4. HAI MÀN CÒN LẠI CỦA PR (không đường nào truyền uri hôm nay) ===\n");

    const E = await motLuot({
      browser, port, ten: "ca-nhan", photo0: null, photo1: null,
      tab: "ca-nhan", needle: "Giao dịch gần đây", goLai: false,
    });
    const F = await motLuot({
      browser, port, ten: "mo-dau", photo0: null, photo1: null,
      khongTab: true, needle: "Rủ Đi", goLai: false,
    });
    for (const run of [E, F]) {
      chac(run.khungRong.length > 0, `lượt ${run.ten}: tìm thấy ít nhất một khung Anh`, `đếm ${run.khungRong.length}`);
      for (const k of run.khungRong) {
        chac(
          k.truoc.w === k.sau.w && k.truoc.h === k.sau.h && k.truoc.h > 0,
          `${run.ten}: khung ${k.nhan ? `"${k.nhan}"` : '(trang trí, alt="")'} tự khai hộp, không phụ thuộc nội dung`,
          `trước ${k.truoc.w}x${k.truoc.h} · sau ${k.sau.w}x${k.sau.h}`,
        );
      }
      const nodes = phang(run.ax);
      const anhKhongNhan = nodes.filter((n) => (n.role === "image" || n.role === "img") && !n.name.trim());
      chac(anhKhongNhan.length === 0, `lượt ${run.ten}: không node ảnh nào không nhãn`, JSON.stringify(anhKhongNhan));
    }
    const nodesCaNhan = phang(E.ax);
    const demAvatar = nodesCaNhan.filter((n) => /^Ảnh đại diện của /.test(n.name)).length;
    chac(demAvatar === 1, 'Cá nhân: khung ảnh đại diện đọc ra ĐÚNG MỘT lần', `đếm ${demAvatar}`);

    console.log("\n=== 5. CỔNG ORIGIN GIỮ ĐƯỢC Ở TRÌNH DUYỆT THẬT ===\n");

    // `apps/mobile/tests/anh.test.mjs` đặt tên một ca là "từ chối mọi origin
    // khác, KHÔNG PHÁT REQUEST". Ca đó gọi `nguonAnhAnToan("...")` và so chuỗi
    // trả về với `null` — nó không quan sát được một request nào cả, nên nửa
    // sau của tên là một khẳng định chưa ai đo. Đây là chỗ đo nó: một máy chủ
    // thật đóng vai máy của người lạ, và câu hỏi là nó có nhận được gì không.
    //
    // GIỚI HẠN QUY TRÁCH, đọc trước khi tin mục này: trên đường `/places` có
    // HAI lần cùng một cổng — `places.ts:parsePhotoUrl` gọi `nguonAnhAnToan`
    // lúc parse, rồi `Anh` gọi lại lúc render. Nên "0 lượt gọi" ở đây KHÔNG
    // nói cổng nào đã giữ. Đo bằng đột biến thì tách được, và kết quả nằm
    // trong `docs/claude/2026-08-30/rd-qa-36-*`:
    //
    //   places=cổng, Anh=cổng   -> 0 lượt gọi   (hôm nay)
    //   places=THẢ,  Anh=cổng   -> 0 lượt gọi   <- Anh MỘT MÌNH giữ được
    //   places=THẢ,  Anh=THẢ    -> 3 lượt gọi   <- đối chứng: đo được thật
    //
    // Hàng giữa là câu trả lời cho "ngày một caller quên lọc thì sao".
    const nhatKy = [];
    const mayLa = http.createServer((req, res) => {
      nhatKy.push({ url: req.url, ua: (req.headers["user-agent"] || "").slice(0, 30) });
      res.writeHead(200, { "Content-Type": "image/png" });
      res.end(anhBytes);
    });
    const portLa = await new Promise((r) => mayLa.listen(0, "127.0.0.1", () => r(mayLa.address().port)));
    const LA = `127.0.0.1:${portLa}`;

    // Sáu hình dạng, không phải một. Một lượt chỉ thử URL tuyệt đối thô sẽ
    // xanh trên bất kỳ phép kiểm `startsWith` ngây thơ nào.
    //
    // `dat` = phép đo này QUY ĐƯỢC cho app. Ba hình dạng cuối KHÔNG quy được:
    // đã đo bằng đột biến (gỡ cổng ở CẢ places.ts lẫn Anh) và chúng vẫn ra 0
    // lượt gọi, vì chính trình duyệt hoặc DNS chặn trước khi app kịp sai —
    // Chrome chặn thông tin đăng nhập nhúng trong subresource, `javascript:`
    // không bao giờ là nguồn ảnh, và `...invalid.nguoi-la.example` không phân
    // giải được nên không thể tới máy chủ thử ở 127.0.0.1. Số 0 của chúng là
    // sự thật về MÔI TRƯỜNG, không phải bằng chứng về cổng. Giữ lại vì rẻ và
    // vì chúng sẽ đỏ nếu trình duyệt đổi ý; nhưng đọc chúng như bằng chứng
    // cho app là tự lừa. Tầng đúng cho ba hình dạng đó là ca chuỗi trong
    // `apps/mobile/tests/anh.test.mjs`, và ở đó chúng đã được phủ.
    const HINH_DANG = [
      { dat: true, ten: "tuyệt đối, host lạ", uri: `http://${LA}/pixel.png?ai-dang-xem=nguoi-B` },
      { dat: true, ten: "giao thức tương đối `//`", uri: `//${LA}/pixel.png` },
      { dat: true, ten: "gạch chéo ngược `/\\`", uri: `/\\${LA}/pixel.png` },
      { dat: false, ten: "hậu tố host trùng tiền tố", uri: `${API_BASE}.nguoi-la.example/pixel.png` },
      { dat: false, ten: "userinfo trước @", uri: `${API_BASE}` + "@" + `${LA}/pixel.png` },
      { dat: false, ten: "javascript:", uri: "javascript:fetch('http://" + LA + "/pixel.png')" },
    ];

    for (const hd of HINH_DANG) {
      const truoc = nhatKy.length;
      const run = await motLuot({
        ...chung, ten: `tu-choi-${HINH_DANG.indexOf(hd)}`, photo0: hd.uri, photo1: null, goLai: false,
      });
      await new Promise((r) => setTimeout(r, 500));
      chac(
        nhatKy.length === truoc,
        `origin lạ KHÔNG nhận được request — ${hd.ten}${hd.dat ? "" : "  [môi trường chặn, KHÔNG quy được cho app]"}`,
        `${nhatKy.length - truoc} lượt gọi · uri=${hd.uri.slice(0, 70)}`,
      );
      const k = timKhung(run.khung, NHAN1);
      chac(k && !k.coAnh, `${hd.ten}: thẻ quay về chỗ chờ, không vẽ ảnh của người lạ`, `coAnh=${k?.coAnh}`);
      chac(
        k && k.hopKhung.w === timKhung(A.khung, NHAN1).hopKhung.w &&
          k.hopKhung.h === timKhung(A.khung, NHAN1).hopKhung.h,
        `${hd.ten}: bị từ chối vẫn giữ đúng hộp (layout không nhảy)`,
        `${k?.hopKhung.w}x${k?.hopKhung.h}`,
      );
      chac(run.loi.length === 0, `${hd.ten}: không lỗi JS`, run.loi.join(" | "));
    }

    // ĐỐI CHỨNG cho chính máy chủ người lạ: nếu nó không bao giờ nhận được gì
    // kể cả khi được gọi thẳng, thì mọi số 0 ở trên chỉ nói máy đo đã chết.
    await fetch(`http://${LA}/doi-chung.png`).catch(() => {});
    await new Promise((r) => setTimeout(r, 200));
    await new Promise((r) => mayLa.close(r));
    chac(
      nhatKy.some((n) => n.url.includes("doi-chung")),
      "canary: máy chủ người lạ SỐNG (nhận được request khi thật sự bị gọi)",
      `${nhatKy.length} lượt gọi tổng cộng: ${JSON.stringify(nhatKy.map((n) => n.url))}`,
    );

    console.log("\n=== ĐỐI CHỨNG CHO CHÍNH BỘ ĐO ===\n");
    // "lọt: []" và "unlabelled: []" đọc y hệt nhau dù phép đo sống hay chết.
    // Ba dòng dưới là canary: chúng phải ĐỎ nếu bộ đo ngừng đọc được gì.
    chac(C.chu.length > 200, "canary: innerText đọc được nội dung thật", `${C.chu.length} ký tự`);
    chac(
      C.chu.includes("Tiệm Nướng Xóm Lào"),
      "canary: cùng phép so chuỗi ĐÓ tìm được một chuỗi CÓ trên màn",
      "nếu dòng này đỏ thì mọi 'lọt: []' ở trên là rỗng tuếch",
    );
    chac(phang(B.ax).length > 50, "canary: cây AX đọc được", `${phang(B.ax).length} node`);
    chac(B.khung.length >= 2, "canary: phép tìm khung tìm được khung", `${B.khung.length} khung`);

    fs.writeFileSync(
      path.join(OUT, "ket-qua.json"),
      JSON.stringify(
        {
          khungA: A.khung, khungB: B.khung, khungC: C.khung, khungD: D.khung,
          khungRongA: A.khungRong,
          chuC: C.chu, chuD: D.chu,
          requestsB: B.requests, requestsC: C.requests, requestsD: D.requests,
          ket,
        },
        null, 2,
      ),
    );
  } finally {
    if (browser) await browser.close();
    await closeServer(server);
  }

  const fail = ket.filter((k) => !k.ok);
  console.log(`\n=== ${ket.length - fail.length}/${ket.length} khẳng định đúng ===`);
  if (fail.length) {
    console.log("SAI:");
    for (const f of fail) console.log(`  - ${f.ten} :: ${f.chiTiet ?? ""}`);
  }
  console.log(`ảnh chụp + số liệu: ${OUT}`);
  process.exit(fail.length ? 1 : 0);
}

await main();
