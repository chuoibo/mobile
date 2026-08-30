/**
 * Independent walk for PR #296 — do place photographs actually reach the screen?
 *
 * This is deliberately NOT `tools/tab-snapshots.mjs`. That tool injects a
 * `photo_url` into its own fixtures before it looks, so it can only ever answer
 * "would an image render if the server sent one". The product question Lead
 * asked is a different one: does a real photograph land on Khám phá and on the
 * detail screen against the server this branch would actually ship with.
 *
 * So the walk runs the SAME built bundle against two wires:
 *
 *   THAT  — the real API from this tree, untouched. Answers "what ships today".
 *   GIA   — the same API with `photo_url` spliced into the first place only.
 *           Answers "does the wiring work the day the field exists", and is the
 *           control that proves a zero in THAT is a fact about the server
 *           rather than a broken measurement.
 *
 * Only ONE place gets a photo in GIA. A grid where every card is in the same
 * state cannot tell a working image path from a dead one.
 *
 * Images are counted by decoded pixels (`naturalWidth > 0`), never by reading
 * markup: react-native-web does not put the address in the DOM attribute, so a
 * markup grep reports success while nothing has loaded.
 */
import http from "node:http";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import { pngThuBytes } from "../../../apps/mobile/tools/png-thu.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CHROME =
  process.env.PUPPETEER_EXECUTABLE_PATH ??
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";

const API = process.env.API_BASE ?? "http://localhost:8137";
const DIST = process.argv[2] ?? path.resolve(HERE, "../../../apps/mobile/dist-qa25");
const NHAN = process.argv[3] ?? path.basename(DIST);

/** Relative on purpose: `nguonAnhAnToan` resolves it against the API origin and
 *  refuses anything off it. An absolute address would be declined and the card
 *  would draw its stand-in — the walk would score a dead path as a pass. */
const DUONG_ANH = "/anh-thu-qa25.png";
const ANH_BYTES = pngThuBytes(480, 360, { dayChoi: true });

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".ico": "image/x-icon",
  ".png": "image/png",
};

function phucVu(goc) {
  return new Promise((ok) => {
    const s = http.createServer((req, res) => {
      const u = new URL(req.url, "http://x");
      const p = path.join(goc, u.pathname === "/" ? "/index.html" : u.pathname);
      if (!p.startsWith(goc) || !existsSync(p)) {
        res.writeHead(404).end("no");
        return;
      }
      res.writeHead(200, { "content-type": MIME[path.extname(p)] ?? "application/octet-stream" });
      res.end(readFileSync(p));
    });
    s.listen(0, "127.0.0.1", () => ok({ s, port: s.address().port }));
  });
}

/** Splice `photo_url` onto the first place only, on both the list and the
 *  detail route, and answer the resolved address with real PNG bytes. Every
 *  other request is passed through untouched — a stub that answers everything
 *  cannot fail, and would score a broken origin gate as a pass. */
async function gaiAnh(page) {
  const dinh = { list: 0, detail: 0, anh: 0 };
  await page.setRequestInterception(true);
  page.on("request", async (req) => {
    const url = req.url();
    if (url === API + DUONG_ANH) {
      dinh.anh += 1;
      await req.respond({ status: 200, contentType: "image/png", body: ANH_BYTES });
      return;
    }
    if (url.startsWith(API + "/places")) {
      try {
        const r = await fetch(url, { headers: req.headers() });
        const j = await r.json();
        if (Array.isArray(j.places) && j.places.length) {
          j.places[0].photo_url = DUONG_ANH;
          dinh.list += 1;
        } else if (j.id) {
          j.photo_url = DUONG_ANH;
          dinh.detail += 1;
        }
        await req.respond({
          status: 200,
          contentType: "application/json",
          headers: { "access-control-allow-origin": "*" },
          body: JSON.stringify(j),
        });
      } catch {
        await req.continue();
      }
      return;
    }
    await req.continue();
  });
  return dinh;
}

async function doMan(page, base, frag, needle) {
  // `AppRoot` reads the fragment once, at mount. Going straight from one
  // fragment to another changes the URL without remounting, so the second
  // screen would be measured while the first is still on the glass.
  await page.goto("about:blank");
  await page.goto(`${base}/index.html#${frag}`, { waitUntil: "networkidle0", timeout: 45000 });
  let thayNeedle = false;
  for (let i = 0; i < 40; i++) {
    thayNeedle = await page.evaluate((n) => document.body.innerText.includes(n), needle);
    if (thayNeedle) break;
    await new Promise((r) => setTimeout(r, 250));
  }
  // Decoding finishes after layout; give the frames a beat before counting.
  await new Promise((r) => setTimeout(r, 1200));
  const d = await page.evaluate(() => {
    const imgs = [...document.images];
    const vw = document.documentElement.clientWidth;
    return {
      tongImg: imgs.length,
      giaiMa: imgs
        .filter((i) => i.naturalWidth > 0)
        .map((i) => ({ w: i.naturalWidth, h: i.naturalHeight })),
      chars: document.body.innerText.length,
      els: document.querySelectorAll("*").length,
      // Layout guard: nothing may stick out past the viewport.
      tran: [...document.querySelectorAll("*")].filter((e) => {
        const r = e.getBoundingClientRect();
        return r.width > 0 && (r.right > vw + 1 || r.left < -1);
      }).length,
    };
  });
  return { needle: thayNeedle, ...d };
}

const MAN = [
  { ten: "kham-pha", frag: "tab=kham-pha&nguoi=minh", needle: "Tiệm Nướng Xóm Lào" },
  { ten: "dia-diem", frag: "dia-diem=p-tiem-nuong-xom-lao&nguoi=minh", needle: "Khoảng giá" },
];

async function main() {
  const { s, port } = await phucVu(DIST);
  const base = `http://127.0.0.1:${port}`;
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  const ketQua = [];
  for (const che of ["THAT", "GIA"]) {
    for (const m of MAN) {
      const page = await browser.newPage();
      await page.setViewport({ width: 390, height: 844 });
      const dinh = che === "GIA" ? await gaiAnh(page) : null;
      const d = await doMan(page, base, m.frag, m.needle);
      ketQua.push({ che, man: m.ten, ...d, dinh });
      await page.close();
    }
  }

  await browser.close();
  s.close();

  console.log(`\n=== ${NHAN} · di bo #296 · viewport 390x844 ===`);
  console.log("che   man          needle  els   chars  img  giaiMa  tran");
  for (const r of ketQua) {
    console.log(
      `${r.che.padEnd(5)} ${r.man.padEnd(12)} ${String(r.needle).padEnd(7)} ` +
        `${String(r.els).padEnd(5)} ${String(r.chars).padEnd(6)} ${String(r.tongImg).padEnd(4)} ` +
        `${String(r.giaiMa.length).padEnd(7)} ${r.tran}` +
        (r.giaiMa.length ? `  [${r.giaiMa.map((g) => `${g.w}x${g.h}`).join(",")}]` : ""),
    );
  }

  const loi = [];
  for (const r of ketQua) {
    if (!r.needle) loi.push(`${r.che}/${r.man}: needle KHONG thay — man chua len, moi so deu vo nghia`);
    if (r.tran > 0) loi.push(`${r.che}/${r.man}: ${r.tran} phan tu tran ra ngoai viewport`);
  }
  // The control: if the spliced wire does not produce a photograph either, the
  // walk is broken and the zero on the real wire proves nothing.
  for (const m of MAN) {
    const g = ketQua.find((r) => r.che === "GIA" && r.man === m.ten);
    if (g && g.giaiMa.length === 0) {
      loi.push(`GIA/${m.ten}: 0 anh giai ma duoc — DOI CHUNG HONG (hoac man that su khong noi day)`);
    }
  }
  if (loi.length) {
    console.log("\nVAN DE:");
    for (const l of loi) console.log("  - " + l);
    process.exitCode = 2;
  } else {
    console.log("\nkhong co van de ve needle/layout/doi-chung");
  }
}

await main();
