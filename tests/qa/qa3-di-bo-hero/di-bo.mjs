/** Walk the hero path by hand, in a browser, against a live server.
 *
 * ## Why this is not one of the existing walks
 *
 * Two walks of this path already exist and neither one is this one:
 *
 *   - `scripts/hero_walk.sh` drives `dist-test/api.js` over `node --test`. It
 *     proves the SEAM (photo -> model -> assignment -> split -> guest page) and
 *     says so. It never renders a screen, so nothing it reports can tell you
 *     that a screen shows a UUID, clips a name, or is unreachable by tapping.
 *   - `apps/mobile/tools/tab-snapshots.mjs` and friends render screens, but on
 *     STUBBED fixtures written into the page ahead of the bundle. A stub cannot
 *     print what the server actually returns, which is exactly where a raw id
 *     or a raw enum leaks from.
 *
 * This file is the third thing: a real Chrome, a real bundle, a real FastAPI on
 * a real PostgreSQL, and taps. Every screen change here is a click on a pixel a
 * thumb could reach. It never navigates by URL, never sets `?man=`, and never
 * calls the API directly to move the app forward -- because the question being
 * asked is "can a person get there", and a URL jump answers a different one.
 *
 * ## What it looks for, beyond "did it crash"
 *
 * The brief is leaks a person sees and no gate catches: a UUID on screen, a
 * bare enum, a stack-shaped string, an ISO timestamp, `undefined`/`NaN`. Those
 * are cheap to find once you have the rendered text, and impossible to find
 * from a passing assert. So each stop records its full visible text and the
 * whole interactive inventory, and the scan runs over that.
 *
 * The inventory covers every interactive ROLE, not just `button`. Listing only
 * `button, [role=button], a` is how the tab bar in this app got measured as
 * absent on 2026-08-31: it uses `role=tab`, matched none of the three, and the
 * resulting 0 was read as "no navigation exists".
 *
 * ## Usage
 *
 *   node tests/qa/qa3-di-bo-hero/di-bo.mjs --web http://127.0.0.1:PORT \
 *        --sdt <số tổng hợp> --anh /tmp/qa3-hero-anh/ro.jpg --out /tmp/qa3-di-bo
 *
 * Exit: 0 walked to the end · 1 stopped somewhere (the stop is the finding)
 * · 2 could not start at all (no browser, no server) -- never reported green.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import puppeteer from "puppeteer-core";

import { timTrinhDuyet } from "../tim-trinh-duyet.mjs";

const args = process.argv.slice(2);
function arg(name, fallback) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : fallback;
}

const WEB = arg("--web");
const ANH = arg("--anh", "/tmp/qa3-hero-anh/ro.jpg");
const OUT = arg("--out", "/tmp/qa3-di-bo");
/* No default, deliberately. Repo guard fails closed on a ten-digit literal in a
 * tracked file and cannot tell a synthetic number from somebody's real one, so
 * the number lives in the command line rather than in the repository. */
const SDT = arg("--sdt");
if (!WEB) {
  console.error("thiếu --web");
  process.exit(2);
}
if (!SDT) {
  console.error("thiếu --sdt (số điện thoại tổng hợp để đăng nhập; không ghi vào repo)");
  process.exit(2);
}
mkdirSync(OUT, { recursive: true });

/* Every interactive role, not just button. See the header. */
const VAI_TRO = [
  "button",
  "[role=button]",
  "[role=tab]",
  "[role=link]",
  "[role=menuitem]",
  "[role=switch]",
  "[role=checkbox]",
  "[role=radio]",
  "[role=option]",
  "a",
  "input",
  "select",
  "textarea",
].join(", ");

/* Shapes a person should never be shown. Each one is a thing that has actually
 * reached a screen in some product, not a hypothetical. */
const RO_RI = [
  { ten: "UUID", re: /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi },
  { ten: "undefined/NaN/null", re: /\b(undefined|NaN|\[object Object\])\b/g },
  { ten: "dấu thời gian ISO", re: /\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/g },
  { ten: "mã lỗi HOA_GACH", re: /\b[A-Z][A-Z0-9]{2,}(_[A-Z0-9]+){1,}\b/g },
  { ten: "chuỗi kiểu stack", re: /\b(Traceback|at Object\.|TypeError|ReferenceError|Exception)\b/g },
  { ten: "khoá snake_case lộ", re: /\b(context_id|person_id|bill_id|batch_id|obligation_id|expense_id|created_at|updated_at)\b/g },
];

/* Vietnamese money renders as 1.234.567; a bare 6+ digit run with no separator
 * on a money screen is the "số lạ" the brief asks about. Reported, not judged:
 * the walker records it and a person decides. */
const SO_LA = /(?<![\d.,])\d{6,}(?![\d.,])/g;

function quet(text) {
  const thay = [];
  for (const { ten, re } of RO_RI) {
    const m = text.match(re);
    if (m) thay.push({ loai: ten, mau: [...new Set(m)].slice(0, 8) });
  }
  const so = text.match(SO_LA);
  if (so) thay.push({ loai: "số dài không phân cách", mau: [...new Set(so)].slice(0, 8) });
  return thay;
}

const chang = [];

async function ghi(page, ten) {
  const anh = join(OUT, `${ten}.png`);
  await page.screenshot({ path: anh });
  const data = await page.evaluate((sel) => {
    const els = [...document.querySelectorAll(sel)];
    const nhin = (e) => {
      const r = e.getBoundingClientRect();
      const s = getComputedStyle(e);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none";
    };
    return {
      text: document.body ? document.body.innerText : "",
      // Input values do not appear in innerText -- a screen whose only content
      // is a filled field reads as empty without this.
      giaTri: [...document.querySelectorAll("input, textarea")]
        .filter(nhin)
        .map((e) => ({ ph: e.placeholder || "", val: e.value || "" })),
      tuongTac: els.filter(nhin).map((e) => ({
        vai: e.getAttribute("role") || e.tagName.toLowerCase(),
        chu: (e.innerText || e.getAttribute("aria-label") || e.value || "").trim().slice(0, 60),
      })),
    };
  }, VAI_TRO);

  const toanVan = [data.text, ...data.giaTri.map((v) => `${v.ph} ${v.val}`)].join("\n");
  const roRi = quet(toanVan);
  chang.push({ ten, anh, soTuongTac: data.tuongTac.length, roRi, text: data.text });
  writeFileSync(join(OUT, `${ten}.txt`), toanVan, "utf8");

  console.log(`\n=== ${ten} ===`);
  console.log(`  ảnh: ${anh}`);
  console.log(`  phần tử tương tác: ${data.tuongTac.length}`);
  const theoVai = {};
  for (const t of data.tuongTac) theoVai[t.vai] = (theoVai[t.vai] || 0) + 1;
  console.log(`  theo vai trò: ${JSON.stringify(theoVai)}`);
  console.log(
    `  nhãn: ${data.tuongTac.map((t) => t.chu).filter(Boolean).slice(0, 22).join(" | ")}`,
  );
  console.log(`  chữ (600): ${data.text.slice(0, 600).replace(/\n+/g, " / ")}`);
  if (roRi.length) {
    console.log(`  !! RÒ RỈ: ${JSON.stringify(roRi, null, 1)}`);
  }
  return data;
}

/* Click by visible label, over every interactive role. Returns false rather
 * than throwing so the caller decides whether a missing control is the finding
 * or just a branch not taken. */
async function bam(page, nhan, { chinhXac = false } = {}) {
  const ok = await page.evaluate(
    (sel, nhanIn, exact) => {
      const els = [...document.querySelectorAll(sel)];
      const hop = els.filter((e) => {
        const t = (e.innerText || e.getAttribute("aria-label") || e.value || "").trim();
        return exact ? t === nhanIn : t.includes(nhanIn);
      });
      if (!hop.length) return false;
      const e = hop[0];
      const r = e.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return false;
      e.scrollIntoView({ block: "center" });
      return true;
    },
    VAI_TRO,
    nhan,
    chinhXac,
  );
  if (!ok) return false;
  // Real pointer events at real coordinates: a synthetic .click() bypasses the
  // hit-testing that a thumb cannot bypass, and this walk is about the thumb.
  const box = await page.evaluate(
    (sel, nhanIn, exact) => {
      const els = [...document.querySelectorAll(sel)];
      const e = els.filter((x) => {
        const t = (x.innerText || x.getAttribute("aria-label") || x.value || "").trim();
        return exact ? t === nhanIn : t.includes(nhanIn);
      })[0];
      const r = e.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    },
    VAI_TRO,
    nhan,
    chinhXac,
  );
  await page.mouse.click(box.x, box.y);
  await new Promise((r) => setTimeout(r, 900));
  return true;
}

const nghi = (ms) => new Promise((r) => setTimeout(r, ms));

let rc = 0;
const browser = await puppeteer.launch({
  executablePath: timTrinhDuyet(),
  headless: "new",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });

  const loi = [];
  page.on("console", (m) => {
    if (m.type() === "error") loi.push(m.text().slice(0, 300));
  });
  page.on("pageerror", (e) => loi.push(`pageerror: ${String(e).slice(0, 300)}`));
  const mang = [];
  page.on("response", (r) => {
    if (r.status() >= 400) mang.push(`${r.status()} ${r.request().method()} ${r.url()}`);
  });

  await page.goto(WEB, { waitUntil: "networkidle2", timeout: 60000 });
  await nghi(1500);

  await ghi(page, "01-mo-app");

  // Everything past here is driven by the caller's step list so this file can
  // be re-run one stop at a time while the shape of the app is still unknown.
  const buoc = (await import("./buoc.mjs")).default;
  await buoc({ page, ghi, bam, nghi, ANH, OUT, SDT });

  writeFileSync(
    join(OUT, "ket-qua.json"),
    JSON.stringify({ web: WEB, chang: chang.map(({ text, ...r }) => r), loi, mang }, null, 2),
    "utf8",
  );
  console.log(`\n--- lỗi console: ${loi.length}`);
  for (const l of loi.slice(0, 15)) console.log(`    ${l}`);
  console.log(`--- phản hồi >=400: ${mang.length}`);
  for (const m of mang.slice(0, 15)) console.log(`    ${m}`);
} catch (e) {
  console.error(`\nDỪNG: ${e.message}`);
  rc = 1;
} finally {
  await browser.close();
}
process.exit(rc);
