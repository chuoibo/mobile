/** The last link: what a real browser draws when the bytes are the ones the
 *  route actually served.
 *
 * `do-client-nhan-200-rong.mjs` proves `taiAnhCoQuyen` resolves on a 200 with
 * zero bytes and hands `Anh.tsx` a blob URL. `Anh.tsx` then mounts an `<Image>`
 * and decides between "hien" and "hong" from whichever of `onLoad`/`onError`
 * fires. Nothing above this file can answer which one that is: react-native-web
 * turns that `<Image>` into
 *
 *     image.onerror = onError;   // ImageLoader/index.js:104
 *     image.onload  = ...;       // ImageLoader/index.js:105
 *
 * on a plain `new window.Image()`, so the answer belongs to the browser's image
 * decoder and to nothing in this repository. A node test cannot produce it and
 * a source read cannot either -- both would be a description of a decoder, and
 * the whole point of this measurement is that the decoder is the thing deciding.
 *
 * So: fetch the bytes from the LIVE api, carry them into a real headless
 * Chrome, rebuild the Blob with the content-type the route sent, and record
 * which event fires. Three payloads, because a single reading cannot be
 * interpreted:
 *
 *   H  healthy photo   positive control -- `load` must fire, or the harness is broken
 *   D  zero bytes      the condition this bug is about
 *   E  junk bytes      the neighbouring condition, same content-type
 *
 * Usage: ANH_API=http://127.0.0.1:PORT ANH_MEDIA=/path node do-trinh-duyet-ve-gi.mjs
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE = (process.env.ANH_API ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const MEDIA = process.env.ANH_MEDIA;
if (!MEDIA) {
  console.error("Dat ANH_MEDIA = MOBILE_MEDIA_ROOT cua stack dang do.");
  process.exit(2);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const mobile = path.join(here, "..", "..", "..", "apps", "mobile");
const { findChrome } = await import(path.join(mobile, "tests", "chrome-cdp.mjs"));
const puppeteer = (await import(path.join(mobile, "node_modules", "puppeteer-core", "lib", "esm", "puppeteer", "puppeteer-core.js"))).default;

const failures = [];
function check(name, ok, detail = "") {
  console.log(`[${ok ? "PASS" : "FAIL"}] ${name}${detail ? ` -- ${detail}` : ""}`);
  if (!ok) failures.push(`${name}: ${detail}`);
}

function headers(actor, contexts) {
  const h = { "X-Actor-ID": actor, "X-Actor-Roles": "member" };
  if (contexts) h["X-Actor-Contexts"] = contexts;
  return h;
}

function listMedia() {
  const out = [];
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) walk(full);
      else out.push(full);
    }
  };
  if (fs.existsSync(MEDIA)) walk(MEDIA);
  return out;
}

async function json(method, p, { actor, contexts, body } = {}) {
  const h = actor ? headers(actor, contexts) : {};
  if (body) h["Content-Type"] = "application/json";
  const r = await fetch(BASE + p, {
    method,
    headers: h,
    body: body ? JSON.stringify(body) : undefined,
  });
  return { status: r.status, body: await r.json().catch(() => ({})) };
}

async function seedPhoto(group, actor) {
  const before = new Set(listMedia());
  // 8x8 red PNG: big enough that a decoder has real work to do, small enough
  // to carry into the page as base64 without dominating the log.
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAAHElEQVQoz2NkYPjPQApgYhhVMKpgVMGoglEFxAAAvXcBAeXrFHQAAAAASUVORK5CYII=",
    "base64",
  );
  const form = new FormData();
  form.append("file", new Blob([png], { type: "image/png" }), "anh.png");
  const r = await fetch(`${BASE}/contexts/${group}/photos`, {
    method: "POST",
    headers: headers(actor, group),
    body: form,
  });
  if (![200, 201].includes(r.status)) throw new Error(`upload: ${r.status}`);
  const wire = await r.json();
  const now = listMedia().filter((f) => !before.has(f));
  if (now.length !== 1) throw new Error(`mong doi 1 file moi, thay ${now.length}`);
  return { wire, file: now[0] };
}

async function fetchBytes(url, actor, group) {
  const r = await fetch(BASE + url, { headers: headers(actor, group) });
  const buf = Buffer.from(await r.arrayBuffer());
  return { status: r.status, type: r.headers.get("content-type"), bytes: buf };
}

// --------------------------------------------------------------- seed --------
const stem = String(Math.floor(Math.random() * 1000000)).padStart(6, "0");
const idr = await json("POST", "/identity/person-id", { body: { phone: `097${stem}1` } });
const an = idr.body.person_id;
await json("PUT", `/people/${an}`, { actor: an, body: { display_name: "An" } });
const group = (await json("POST", "/contexts", { actor: an, body: { display_name: "Nhom trinh duyet" } })).body.id;

const healthy = await seedPhoto(group, an);
const dead = await seedPhoto(group, an);
fs.writeFileSync(dead.file, Buffer.alloc(0));
const junk = await seedPhoto(group, an);
fs.writeFileSync(junk.file, Buffer.from("khong phai anh, chi la chu"));

const payloads = [
  { key: "H anh lanh (doi chung duong)", ...(await fetchBytes(healthy.wire.url, an, group)) },
  { key: "D file 0 byte", ...(await fetchBytes(dead.wire.url, an, group)) },
  { key: "E file rac", ...(await fetchBytes(junk.wire.url, an, group)) },
];

console.log(`\n== bo du lieu ==\napi=${BASE}\nnhom=${group}`);
for (const p of payloads) {
  console.log(`  ${p.key}: status=${p.status} type=${p.type} bytes=${p.bytes.length}`);
}

// ------------------------------------------------------------ the browser ----
const bin = findChrome();
if (!bin) {
  console.error("Khong tim thay Chrome. Phep do nay khong chay duoc -- KHONG phai xanh.");
  process.exit(2);
}
console.log(`\nchrome: ${bin}`);

const browser = await puppeteer.launch({
  executablePath: bin,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
});
try {
  const page = await browser.newPage();
  await page.goto("about:blank");

  const results = await page.evaluate(async (items) => {
    const out = [];
    for (const item of items) {
      const raw = Uint8Array.from(atob(item.b64), (c) => c.charCodeAt(0));
      const blob = new Blob([raw], { type: item.type });
      const url = URL.createObjectURL(blob);
      // Exactly what react-native-web's ImageLoader does with the uri that
      // `Anh.tsx` puts on its <Image>.
      const verdict = await new Promise((resolve) => {
        const image = new Image();
        const done = (event) => resolve({ event, w: image.naturalWidth, h: image.naturalHeight });
        image.onload = () => done("load");
        image.onerror = () => done("error");
        setTimeout(() => resolve({ event: "im-lang-qua-3s", w: image.naturalWidth, h: image.naturalHeight }), 3000);
        image.src = url;
      });
      // And what the page would actually show: an <img> in the document, so
      // the painted size is measurable rather than assumed.
      const el = document.createElement("img");
      el.style.cssText = "width:120px;height:90px;object-fit:cover";
      el.src = url;
      document.body.appendChild(el);
      await new Promise((r) => setTimeout(r, 300));
      const box = el.getBoundingClientRect();
      out.push({
        key: item.key,
        blobSize: blob.size,
        ...verdict,
        painted: `${Math.round(box.width)}x${Math.round(box.height)}`,
        complete: el.complete,
      });
      URL.revokeObjectURL(url);
      el.remove();
    }
    return out;
  }, payloads.map((p) => ({ key: p.key, type: p.type, b64: p.bytes.toString("base64") })));

  console.log("\n== trinh duyet noi gi ==");
  for (const r of results) {
    console.log(
      `  ${r.key.padEnd(30)} blob=${String(r.blobSize).padStart(5)} byte  su kien=${r.event.padEnd(6)}` +
        `  naturalSize=${r.w}x${r.h}  complete=${r.complete}`,
    );
  }

  const by = Object.fromEntries(results.map((r) => [r.key.slice(0, 1), r]));
  check(
    "H DOI CHUNG DUONG: anh lanh -> su kien 'load', giai ma 8x8",
    by.H?.event === "load" && by.H.w === 8 && by.H.h === 8,
    `su kien=${by.H?.event} size=${by.H?.w}x${by.H?.h}`,
  );
  check(
    "D 200-rong -> su kien 'error' => Anh.tsx ve lai CHO DUNG, im lang",
    by.D?.event === "error",
    `su kien=${by.D?.event} naturalSize=${by.D?.w}x${by.D?.h}`,
  );
  check(
    "E 200-rac -> su kien 'error' => cung ket cuc, cung im lang",
    by.E?.event === "error",
    `su kien=${by.E?.event} naturalSize=${by.E?.w}x${by.E?.h}`,
  );
  check(
    "D va E khong phan biet duoc voi 'nhom chua co anh' tren man hinh",
    by.D?.event === "error" && by.E?.event === "error",
    "ca hai deu roi ve trang thai 'hong', ma 'hong' ve dung cai stand-in cua 'khong-co'",
  );
} finally {
  await browser.close();
}

console.log(`\n${failures.length} dong FAIL`);
for (const f of failures) console.log(`  - ${f}`);
process.exit(failures.length ? 1 : 0);
