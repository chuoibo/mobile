/** Đo đường ảnh của #195 ở DOM sống, chứ không đọc nguồn.
 *
 * `apps/mobile/tests/anh.test.mjs` gác đường này bằng hai ca đọc file:
 *
 *     const src = readFileSync(".../src/ui/Anh.tsx", "utf8");
 *     assert.match(src, /<Image\b/);
 *
 * Ca đó đạt với mọi bản `Anh.tsx` còn CHỨA chữ `<Image`, kể cả bản không bao
 * giờ render nó. Đã đo: đổi `{veAnh ? (` thành `{false ? (` — app render 0 ảnh
 * — mà `npm test` vẫn 546/546 xanh. Chính docstring của ca đó đã nói ra giới
 * hạn ("bằng chứng render thật nằm ở ảnh chụp kèm PR"); file này biến câu đó
 * thành một cổng chạy được, vì ảnh chụp kèm PR không ai chạy lại.
 *
 * Ba ca, vì một lượt chỉ đo URL độc không phân biệt được "chốt chặn đã giữ"
 * với "máy đo đã chết" — đúng cái bẫy `imp detect` trả `[] + exit 0`:
 *
 *   anh-that     http:// URL  -> phải CÓ <img>, và tracker PHẢI nhận request
 *   scheme-doc   javascript:  -> phải KHÔNG có <img>, tracker KHÔNG nhận gì
 *   khong-anh    null         -> phải KHÔNG có <img>  (đối chứng: làm cho số 0
 *                                của ca 2 là kết quả của chốt chặn, không phải
 *                                của một probe hỏng)
 *
 * Ca `anh-that` còn đo một thứ không cổng nào trong repo đang đo: `photo_url`
 * KHÔNG đi qua fetch stub. Nó vào thẳng `<Image>`, nên trình duyệt của người
 * đang xem màn hình bắn một request THẬT tới host mà URL đó nêu tên. Tracker ở
 * đây ghi lại host kia học được gì: đã mở màn nào, lúc nào, từ địa chỉ IP nào,
 * bằng user agent nào. Hôm nay `photo_url` do máy chủ tự sinh (rd-be-05) nên
 * đó chưa phải đường theo dõi giữa người trong nhóm; xem báo cáo kèm về hai
 * trường `image_url` client tự khai đang chờ đúng cơ chế này.
 *
 * Chạy:
 *   cd apps/mobile && npm run build:check      # bundle phải dựng từ SHA đang đo
 *   node tests/qa/rd-qa-35/anh-song-probe.mjs  # từ gốc repo
 */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "../../..");
const MOBILE_ROOT = path.join(REPO_ROOT, "apps/mobile");
const BUILD_DIR = path.join(MOBILE_ROOT, ".expo-build-check");

const { CHROME, closeServer, createStaticServer, listen } = await import(
  path.join(MOBILE_ROOT, "tools/screen-snapshots.mjs")
);
const { installTabStubs } = await import(path.join(MOBILE_ROOT, "tools/tab-snapshots.mjs"));

/** Cùng sentinel mà `build:check` nhúng vào bundle. Stub bắt theo tiền tố này. */
const API_BASE = "http://api.build-check.invalid";
const NGUOI = "minh";

/** Một row hợp lệ theo đúng shape `screens/kham-pha/places.ts` kiểm.
 *  Chép từ `tools/tab-snapshots.mjs` chứ không tự nghĩ ra: parser đó từ chối
 *  trên mọi field, và một lần từ chối sẽ render panel "dữ liệu sai" thay vì
 *  danh sách mà probe cần nhìn. */
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
    match: {
      score: 95,
      source: "ai",
      verdict: "hop",
      reason: "Hợp vì ngân sách và đồ nướng.",
      factors: [],
    },
    ...over,
  };
}

/** PNG 1x1 dựng bằng byte lúc chạy, không phải chuỗi base64 trong cây.
 *  Repo guard fail-closed với nhị phân và với token base64 dài, và nó đúng khi
 *  làm thế — cùng lý do `vietPngThu` trong `tab-snapshots.mjs` tồn tại. */
function png1x1() {
  const crcBang = [];
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crcBang[n] = c >>> 0;
  }
  const crc = (buf) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcBang[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (ten, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const than = Buffer.concat([Buffer.from(ten, "ascii"), data]);
    const c = Buffer.alloc(4);
    c.writeUInt32BE(crc(than));
    return Buffer.concat([len, than, c]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(1, 0);
  ihdr.writeUInt32BE(1, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // truecolour
  const raw = Buffer.from([0x00, 0xff, 0x99, 0x33]); // filter 0 + 1 pixel RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

/** Đóng vai một host mà người đang xem màn hình chưa bao giờ chọn liên hệ.
 *  Ghi lại đúng những gì host đó học được. */
function trackerServer(hits, anh) {
  return http.createServer((req, res) => {
    hits.push({
      url: req.url,
      ip: req.socket.remoteAddress,
      ua: req.headers["user-agent"] ?? null,
      referer: req.headers.referer ?? null,
      at: new Date().toISOString(),
    });
    res.writeHead(200, { "Content-Type": "image/png" });
    res.end(anh);
  });
}

async function main() {
  if (!fs.existsSync(path.join(BUILD_DIR, "index.html"))) {
    throw new Error(`Chưa có bundle ở ${BUILD_DIR}. Chạy: cd apps/mobile && npm run build:check`);
  }

  const hits = [];
  const tracker = trackerServer(hits, png1x1());
  const trackerPort = await listen(tracker);
  const app = createStaticServer(BUILD_DIR);
  const appPort = await listen(app);
  const TRACKER_URL = `http://127.0.0.1:${trackerPort}/theo-doi.png`;

  const CASES = [
    { ten: "anh-that", photo_url: TRACKER_URL, mongDoiImg: true, mongDoiHit: true },
    { ten: "scheme-doc", photo_url: "javascript:alert(1)", mongDoiImg: false, mongDoiHit: false },
    { ten: "khong-anh", photo_url: null, mongDoiImg: false, mongDoiHit: false },
  ];

  const ketQua = [];
  let browser = null;
  try {
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: true,
      defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    for (const ca of CASES) {
      const truoc = hits.length;
      const fixtures = {
        categories: [{ id: "tat-ca", label: "Tất cả" }],
        places: [place({ photo_url: ca.photo_url })],
      };

      const page = await browser.newPage();
      page.setDefaultTimeout(30000);
      const loi = [];
      page.on("pageerror", (e) => loi.push(String(e)));
      await page.evaluateOnNewDocument(installTabStubs, API_BASE, fixtures);

      // Một page mới cho mỗi ca. `AppRoot` đọc fragment đúng một lần lúc mount,
      // nên dùng lại một page sẽ đo ca đầu tiên ba lần dưới ba cái tên.
      await page.goto(`http://127.0.0.1:${appPort}/index.html#tab=kham-pha&nguoi=${NGUOI}`, {
        waitUntil: "domcontentloaded",
      });
      // Đợi danh sách, không đợi đồng hồ: chuỗi này chỉ in ra khi màn đã có dữ liệu.
      await page.waitForFunction(() => document.body.innerText.includes("Tiệm Nướng Xóm Lào"), {
        timeout: 30000,
      });
      // Ảnh phải đi qua mạng nên được một cửa sổ lắng. Đây là chỗ duy nhất chờ
      // theo thời gian, và nó bị chặn bởi assertion bên dưới chứ không thay thế
      // assertion đó.
      await new Promise((r) => setTimeout(r, 1500));

      const imgs = await page.evaluate(() =>
        Array.from(document.querySelectorAll("img")).map((n) => ({
          src: n.getAttribute("src"),
          w: n.naturalWidth,
          h: n.naturalHeight,
        })),
      );
      await page.close();

      const hitMoi = hits.slice(truoc);
      ketQua.push({
        ca: ca.ten,
        photo_url: ca.photo_url,
        img: imgs,
        soImg: imgs.length,
        hit: hitMoi,
        soHit: hitMoi.length,
        loiTrang: loi,
        mongDoiImg: ca.mongDoiImg,
        mongDoiHit: ca.mongDoiHit,
      });
    }
  } finally {
    if (browser) await browser.close();
    await closeServer(app);
    await closeServer(tracker);
  }

  let hong = 0;
  for (const r of ketQua) {
    const coImg = r.img.some((i) => (i.src ?? "").includes("theo-doi.png"));
    const imgOk = r.mongDoiImg ? coImg : !coImg;
    const hitOk = r.mongDoiHit ? r.soHit > 0 : r.soHit === 0;
    if (!imgOk || !hitOk) hong += 1;
    console.log(
      `${imgOk && hitOk ? "OK  " : "HONG"} ${r.ca.padEnd(11)} img=${r.soImg} ` +
        `img-theo-doi=${coImg} hit=${r.soHit} ` +
        `(mong doi img=${r.mongDoiImg} hit=${r.mongDoiHit})`,
    );
    for (const h of r.hit) {
      console.log(`      -> tracker nhan: ${h.url} tu ${h.ip} referer=${h.referer}`);
      console.log(`         ua=${(h.ua ?? "").slice(0, 60)}...`);
    }
    for (const i of r.img) console.log(`      -> <img src=${i.src} ${i.w}x${i.h}>`);
  }

  if (process.env.RA_FILE) {
    fs.writeFileSync(process.env.RA_FILE, JSON.stringify(ketQua, null, 2));
  }
  console.log(hong === 0 ? "\nTAT CA DUNG MONG DOI" : `\n${hong} ca SAI mong doi`);
  process.exit(hong === 0 ? 0 : 2);
}

await main();
