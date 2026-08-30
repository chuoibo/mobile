/** Independent walk for PR #296 — is a place photograph actually PAINTED?
 *
 * Written because the PR itself proved the obvious discriminator is a lie.
 * react-native-web renders `<Image>` as TWO nodes: an `<img>` held at
 * `opacity: 0` that only decodes and fires `onLoad`, and a wrapper `<div>` that
 * paints through an inline `background-image`. So `img.naturalWidth > 0` can be
 * 480 while the frame on screen shows nothing but its category ramp. My own
 * previous measurement for this PR used `naturalWidth`, so it is retired here.
 *
 * This probe does not reuse any of the PR's tooling, and does not reuse its
 * screenshot-diff method either. It serves a photograph of a colour that
 * appears nowhere in the product palette — solid magenta, `rgb(255,0,255)` —
 * and then counts magenta pixels in a screenshot of the real composited page.
 * A ramp cannot produce that colour, a scrim cannot produce it, and no amount
 * of patching `HTMLImageElement.prototype` can put it on screen. If magenta is
 * there, bytes travelled from the API origin through the frame onto the glass.
 *
 * The wire is spliced on purpose: `GET /places` sends no `photo_url` at all
 * today (measured: 12 rows, 0 with the key, only `photo_count`). So this asks
 * the only question the product can currently be held to — the day the field
 * exists, does the frame fill? — and says so rather than implying photos ship.
 *
 * Only the FIRST place gets a photo. A grid where every card is identical
 * cannot distinguish "the photo rendered" from "the ramp rendered everywhere".
 *
 *   node tests/qa/qa-tt-0026/di-bo-magenta.mjs <dist-dir>
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
// Absolute path, as everything else on this machine does it: puppeteer is not
// a dependency of the app, it lives in the harness install.
import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

const DIST = process.argv[2];
const API = process.env.API_BASE ?? "http://localhost:8137";
const NGUOI = "minh";
const DUONG_ANH = "/anh-qa26-magenta.png";
const CHROME =
  process.env.PUPPETEER_EXECUTABLE_PATH ??
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";

if (!DIST) throw new Error("can <dist-dir>");

/** A solid magenta PNG, hand-rolled: signature + IHDR/IDAT/IEND. */
function pngMagenta(w = 480, h = 360) {
  const raw = Buffer.alloc(h * (w * 3 + 1));
  let o = 0;
  for (let y = 0; y < h; y++) {
    raw[o++] = 0; // filter: none
    for (let x = 0; x < w; x++) {
      raw[o++] = 255;
      raw[o++] = 0;
      raw[o++] = 255;
    }
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(zlib.crc32(td) >>> 0);
    return Buffer.concat([len, td, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // colour type: truecolour
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const ANH_BYTES = pngMagenta();

/** Minimal static server for the built bundle. Own implementation, so this
 *  probe shares no code with the tooling it is checking. */
function phucVuTinh(dir) {
  const kieu = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".ico": "image/x-icon",
  };
  return http.createServer((req, res) => {
    const p = decodeURIComponent(req.url.split("?")[0].split("#")[0]);
    const f = path.join(dir, p === "/" ? "index.html" : p);
    if (!f.startsWith(path.resolve(dir))) return res.writeHead(403).end();
    fs.readFile(f, (e, b) => {
      if (e) return res.writeHead(404).end();
      res.writeHead(200, { "content-type": kieu[path.extname(f)] ?? "application/octet-stream" });
      res.end(b);
    });
  });
}

/** Count pixels of exactly magenta, by drawing the screenshot into a canvas in
 *  a throwaway page. Reading the composited result, not the DOM. */
async function demMagenta(browser, b64) {
  const p = await browser.newPage();
  try {
    await p.goto("about:blank");
    return await p.evaluate(async (data) => {
      // Blob URL rather than a data URI: the repo guard refuses a base64 image
      // literal on sight, and it is right to -- that rule is what keeps a bill
      // photograph from being pasted into a test file.
      const bin = atob(data);
      const buf = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i += 1) buf[i] = bin.charCodeAt(i);
      const img = new Image();
      img.src = URL.createObjectURL(new Blob([buf], { type: "image/png" }));
      await img.decode();
      const c = document.createElement("canvas");
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      const g = c.getContext("2d");
      g.drawImage(img, 0, 0);
      const d = g.getImageData(0, 0, c.width, c.height).data;
      let n = 0;
      for (let i = 0; i < d.length; i += 4) {
        // Exact, with a tolerance only for subpixel/JPEG-free rounding.
        if (d[i] > 240 && d[i + 1] < 32 && d[i + 2] > 240) n += 1;
      }
      return { magenta: n, tong: c.width * c.height };
    }, b64);
  } finally {
    await p.close();
  }
}

async function diBo(browser, port, frag) {
  const page = await browser.newPage();
  const mang = { anhDuocHoi: 0, anhTraLoi: 0 };
  try {
    await page.setViewport({ width: 390, height: 844 });
    await page.setRequestInterception(true);
    page.on("request", async (req) => {
      const url = req.url();
      if (url.startsWith(API + DUONG_ANH)) {
        mang.anhDuocHoi += 1;
        mang.anhTraLoi += 1;
        return req.respond({
          status: 200,
          contentType: "image/png",
          headers: { "access-control-allow-origin": "*" },
          body: ANH_BYTES,
        });
      }
      if (url.startsWith(API + "/places")) {
        // Splice the field the server does not send yet, onto the first row
        // only. Everything else is passed through to the REAL API.
        const r = await fetch(url, { headers: { "x-actor-id": NGUOI } }).catch(() => null);
        if (!r) return req.continue();
        const t = await r.text();
        let j;
        try {
          j = JSON.parse(t);
        } catch {
          return req.respond({ status: r.status, contentType: "application/json", body: t });
        }
        if (Array.isArray(j.places) && j.places.length) j.places[0].photo_url = DUONG_ANH;
        else if (j.id) j.photo_url = DUONG_ANH;
        return req.respond({
          status: 200,
          contentType: "application/json",
          headers: { "access-control-allow-origin": "*" },
          body: JSON.stringify(j),
        });
      }
      return req.continue();
    });

    await page.goto(`http://127.0.0.1:${port}/index.html#${frag}`, {
      waitUntil: "networkidle0",
      timeout: 90000,
    });
    // The frame paints after onLoad; give the composite a beat to settle.
    await new Promise((r) => setTimeout(r, 2500));

    const b64 = await page.screenshot({ encoding: "base64" });
    const px = await demMagenta(browser, b64);
    const dom = await page.evaluate(() => ({
      els: document.querySelectorAll("*").length,
      chars: (document.body.innerText || "").replace(/\s+/g, " ").trim().length,
    }));
    return { ...px, ...dom, ...mang };
  } finally {
    await page.close();
  }
}

const server = phucVuTinh(path.resolve(DIST));
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;
const browser = await puppeteer.launch({
  executablePath: CHROME,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

/* The id must be a REAL one from the live API. `p-1` is a fixture id from the
 * PR's own stub harness, and against the real server it resolves to nothing —
 * the app then falls back to Khám phá and both rows report identical numbers,
 * which reads exactly like "the detail screen renders the photo". Measured:
 * els=633 chars=713 on both rows, before and after the PR alike. */
const ID = process.env.PLACE_ID ?? "p-tiem-nuong-xom-lao";
const MAN = [
  ["kham-pha", `vao=kham-pha&nguoi=${NGUOI}`],
  ["dia-diem", `dia-diem=${ID}&nguoi=${NGUOI}`],
];

console.log(`dist = ${DIST}`);
for (const [ten, frag] of MAN) {
  const r = await diBo(browser, port, frag);
  const ket = r.magenta > 0 ? "CO ANH" : "KHONG CO ANH";
  console.log(
    `  ${ten.padEnd(10)} magenta=${String(r.magenta).padStart(7)} px  ` +
      `els=${r.els} chars=${r.chars}  anh-duoc-hoi=${r.anhDuocHoi}  -> ${ket}`,
  );
}

await browser.close();
server.close();
