/** Do the photographs on our own API actually reach the screen?
 *
 * ## Why this file exists, and why the harness next door could not catch it
 *
 * Every image route this product has is permission-checked. The server reads
 * `X-Actor-ID` and answers 401 without it:
 *
 *     GET /people/{id}/avatar                 no header  -> 401 authentication_required
 *     GET /people/{id}/avatar                 header     -> 200 image/jpeg
 *     GET /contexts/{cid}/photos/{pid}        no header  -> 401 authentication_required
 *
 * An `<img>` cannot send a header. Neither can react-native-web's `<Image>`,
 * which becomes one. So an address handed straight to a frame is a request that
 * is *guaranteed* to be refused, and `Anh` reacts to the refusal by unmounting
 * the image and drawing the stand-in -- which is pixel-identical to "this
 * person has no photograph yet". Upload succeeds, the wall stays empty, and
 * nothing anywhere says why.
 *
 * `tab-snapshots.mjs` cannot see any of that, and the reason is worth stating
 * because it is the same shape as most of the blind gates in this repo: it
 * answers the image request ITSELF, out of `page.on("request")`, with an
 * unconditional `req.respond({status: 200})`. The bytes come back because the
 * harness put them there, not because the app was allowed to have them. A
 * screen that can never load a photograph in production passes that scan every
 * time.
 *
 * This harness changes exactly one thing: the interceptor enforces the same
 * rule the real server enforces. Bytes require `x-actor-id`; without it the
 * answer is 401. Nothing else about the setup differs. Measured against the
 * live API on this machine before the harness was written, so the rule encoded
 * here is copied from observed behaviour rather than from the source:
 *
 *     POST /people/46b5..../avatar  -H X-Actor-ID  -> 201, 721 bytes stored
 *     GET  /people/46b5..../avatar  -H X-Actor-ID  -> 200 image/jpeg 721 bytes
 *     GET  /people/46b5..../avatar  (no header)    -> 401 authentication_required
 *
 * ## What it reports, and what it refuses to conclude
 *
 * Two things per screen, and they are deliberately different questions:
 *
 *   `anhThat`  -- an `<img>` in the document whose `naturalWidth > 0`. The
 *                 browser saying it holds decoded pixels. An element that
 *                 exists but never loaded does not count, because that is the
 *                 exact state this whole file is about.
 *   `goi`      -- every request that reached an image route, with whether it
 *                 carried `x-actor-id` and what it was answered. This is what
 *                 separates "the app never asked" from "the app asked and was
 *                 refused" -- two failures with identical screenshots and
 *                 completely different fixes.
 *
 * It does NOT prove the photograph is the right one, that it is the person's
 * own, or that a non-member is refused. Those are the server's to enforce and
 * `guest_view`-style leak tests are where they belong. This file proves the
 * bytes can travel at all.
 *
 *     cd apps/mobile && npm run build:check && node tools/anh-co-quyen-harness.mjs
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, NGUOI, installTabStubs, taoFixtures } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");
const BUILD = path.join(MOBILE_ROOT, ".expo-build-check");

/** The two surfaces that read photographs off our own API.
 *
 * Kỷ niệm is opened with `vao=`, not `tab=`, which is how it stayed outside
 * every tab-driven scan until rd-fe-25 went looking for it. Named explicitly
 * here for the same reason it was missed there.
 *
 * The needle is the loaded screen's own text, never a heading that paints
 * before the data lands -- otherwise this waits on the error state and reports
 * its emptiness as a clean result. */
const MAN = [
  {
    step: "ca-nhan",
    frag: `tab=ca-nhan&nguoi=${NGUOI}`,
    needle: "Giao dịch gần đây",
    duong: /\/people\/[^/]+\/avatar(\?|$)/,
    ten: "ảnh đại diện trên màn Cá nhân",
  },
  {
    step: "ky-niem",
    frag: `vao=ky-niem&nguoi=${NGUOI}`,
    needle: "Đã đi cùng nhau",
    duong: /\/contexts\/[^/]+\/photos\/[^/?]+(\?|$)/,
    ten: "tường ảnh trên màn Kỷ niệm",
  },
];

/** Is this an address whose BYTES the server permission-checks? */
function laDuongAnh(url) {
  if (!url.startsWith(API_BASE)) return false;
  return MAN.some((m) => m.duong.test(url.slice(API_BASE.length)));
}

/** A real PNG, generated rather than committed: the repo guard refuses binaries
 *  and it is right to. Hand-rolled for the same reason `tab-snapshots` does it
 *  -- there is no image library here and adding one for four chunks is worse. */
function vietPng(w = 96, h = 96) {
  const raw = Buffer.alloc(h * (w * 3 + 1));
  let o = 0;
  for (let y = 0; y < h; y++) {
    raw[o++] = 0;
    for (let x = 0; x < w; x++) {
      const o_ = (x >> 4) + (y >> 4);
      raw[o++] = o_ % 2 ? 236 : 44;
      raw[o++] = o_ % 2 ? 122 : 90;
      raw[o++] = o_ % 2 ? 74 : 180;
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
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

/** Grab the browser's own `fetch` before anything wraps it.
 *
 *  Registered ahead of `installTabStubs` so the reference is the real one. */
function giuFetchThat() {
  window.__netFetch = window.fetch.bind(window);
}

/** Send image-route calls back to the network, past the JSON stub.
 *
 *  `installTabStubs` answers every address on `API_BASE` and 404s the ones it
 *  does not know, which would swallow an authenticated image fetch and report
 *  it as a missing route. Image bytes have to reach `page.on("request")` --
 *  that is the only layer that can see the header and apply the server's rule.
 *  Registered AFTER the stub so this wrapper is outermost. */
function traAnhVeMang(apiBase, mauDuong) {
  const stub = window.fetch;
  const net = window.__netFetch;
  const duong = mauDuong.map((s) => new RegExp(s));
  window.fetch = (input, init) => {
    const url = typeof input === "string" ? input : input.url;
    if (url.startsWith(apiBase)) {
      const route = url.slice(apiBase.length);
      if (duong.some((d) => d.test(route))) return net(input, init);
    }
    return stub(input, init);
  };
}

async function doiChu(page, needle, ms = 30000) {
  await page.waitForFunction(
    (t) => document.body && document.body.innerText.includes(t),
    { timeout: ms },
    needle,
  );
}

async function main() {
  if (!fs.existsSync(path.join(BUILD, "index.html"))) {
    throw new Error(`Chưa có bundle ở ${BUILD}. Chạy 'npm run build:check' trước.`);
  }
  const anhBytes = vietPng();
  const fixtures = taoFixtures();
  const mauDuong = MAN.map((m) => m.duong.source);

  const server = createStaticServer(BUILD);
  let browser;
  const ketQua = [];
  try {
    const port = await listen(server);
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: true,
      defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });

    for (const man of MAN) {
      const page = await browser.newPage();
      page.setDefaultTimeout(30000);
      const goi = [];
      const pageErrors = [];
      page.on("pageerror", (e) => pageErrors.push(String(e)));

      await page.setRequestInterception(true);
      page.on("request", (req) => {
        const url = req.url();
        if (!laDuongAnh(url)) return void req.continue();

        // Cross-origin fetch with a custom header preflights first. The live
        // API answers this for any loopback origin; verified with curl against
        // it before this file was written.
        const cors = {
          "access-control-allow-origin": "*",
          "access-control-allow-headers":
            "x-actor-id, x-actor-roles, x-actor-contexts, content-type",
          "access-control-allow-methods": "GET, POST, OPTIONS",
        };
        if (req.method() === "OPTIONS") {
          goi.push({ method: "OPTIONS", route: url.slice(API_BASE.length), coActor: null, status: 204 });
          return void req.respond({ status: 204, headers: cors, body: "" });
        }

        // The rule, and the whole point of this harness: bytes need a header.
        const h = req.headers();
        const coActor = Boolean(h["x-actor-id"] || h["X-Actor-ID"]);
        const status = coActor ? 200 : 401;
        goi.push({ method: req.method(), route: url.slice(API_BASE.length), coActor, status });
        if (!coActor) {
          return void req.respond({
            status: 401,
            headers: { ...cors, "content-type": "application/json" },
            body: JSON.stringify({ code: "authentication_required", detail: "Missing X-Actor-ID" }),
          });
        }
        req.respond({ status: 200, headers: { ...cors, "content-type": "image/png" }, body: anhBytes });
      });

      await page.evaluateOnNewDocument(giuFetchThat);
      await page.evaluateOnNewDocument(installTabStubs, API_BASE, fixtures);
      await page.evaluateOnNewDocument(traAnhVeMang, API_BASE, mauDuong);

      await page.goto(`http://127.0.0.1:${port}/index.html#${man.frag}`, {
        waitUntil: "domcontentloaded",
      });

      let loiMan = null;
      try {
        await doiChu(page, man.needle);
      } catch {
        loiMan = `không thấy "${man.needle}" -- màn chưa tải xong dữ liệu của nó`;
      }

      // Give the frame time to ask, be answered, and decode. Polled rather
      // than slept: a fixed sleep either wastes time or races, and this loop
      // stops the moment real pixels exist.
      let anhThat = 0;
      for (let i = 0; i < 40 && !anhThat; i++) {
        anhThat = await page.evaluate(async () => {
          const imgs = [...document.querySelectorAll("img")];
          await Promise.all(imgs.map((i) => (i.complete ? null : i.decode().catch(() => {}))));
          return imgs.filter((i) => i.naturalWidth > 0).length;
        });
        if (!anhThat) await new Promise((r) => setTimeout(r, 250));
      }

      const soImg = await page.evaluate(() => document.querySelectorAll("img").length);
      ketQua.push({
        step: man.step,
        ten: man.ten,
        anhThat,
        soImg,
        goi,
        loiMan,
        pageErrors: pageErrors.slice(0, 3),
      });
      await page.close();
    }
  } finally {
    if (browser) await browser.close();
    closeServer(server);
  }

  console.log(JSON.stringify({ ketQua }, null, 2));

  const hong = ketQua.filter((k) => k.anhThat === 0 || k.loiMan);
  if (hong.length) {
    for (const k of hong) {
      const daHoi = k.goi.filter((g) => g.method === "GET");
      const coQuyen = daHoi.filter((g) => g.coActor);
      console.error(
        `\nHỎNG · ${k.ten}: ${k.anhThat} ảnh có pixel thật trên ${k.soImg} thẻ <img>.` +
          (k.loiMan ? `\n  màn: ${k.loiMan}` : "") +
          `\n  gọi tới đường ảnh: ${daHoi.length}, trong đó có X-Actor-ID: ${coQuyen.length}` +
          (daHoi.length === 0
            ? `\n  -> app KHÔNG hề hỏi. Đường đọc chưa được nối.`
            : coQuyen.length === 0
              ? `\n  -> app có hỏi nhưng KHÔNG gửi X-Actor-ID, nên bị 401. Một <img> không gửi được header;` +
                ` bytes phải được fetch kèm header rồi mới đưa cho khung ảnh.`
              : `\n  -> có hỏi kèm header và vẫn không ra pixel. Xem pageErrors.`),
      );
    }
    process.exitCode = 1;
  }
}

await main();
