/* One press plan, one real browser, one LIVE server -- and a dump of what each
 * press produced on both sides of the wire.
 *
 * This is the driver half of the F37/F38 measurement. It answers nothing on its
 * own: it presses what it is told to press, and after every press it records
 *
 *   - the screen: every trimmed visible line of the DOM
 *   - the controls: every pressable role+name, so the NEXT press can be chosen
 *     from what is actually there instead of from what someone hoped was there
 *   - the wire: method, path and status of every request the page made, plus
 *     the response body when it is JSON
 *
 * Rules that make the output mean something:
 *
 *   1. The bundle is built with `EXPO_PUBLIC_API_URL` pinned at the live API, so
 *      nothing is stubbed and no request is rewritten in flight. What the screen
 *      shows came from that server or from the client's own imagination, and the
 *      point of the exercise is to tell those two apart.
 *   2. Presses go through Playwright's `click`, which dispatches real pointer
 *      events. react-native-web `Pressable` listens on those; `el.click()` can
 *      miss `onPress` entirely and would record a dead control as a live edge.
 *   3. `goto` happens once, at `/`, and never with a fragment. `lien-ket.ts`
 *      accepts `#tab=`/`?man=` and a person holding a phone cannot type either,
 *      so a screen only an address opens is NOT reachable and must not be
 *      recorded as though a finger got there. A plan may set `dungCua: true` on
 *      a step to use the address bar deliberately -- it is then labelled
 *      `CUA-URL` in the output and cannot be mistaken for a press.
 *
 * Usage:
 *     node di-bo.mjs <web-dir> <api-base> <static-port> <plan.json> [out.json]
 *
 * plan.json: [{ "vai": "button", "ten": "Đăng ký với Apple" },
 *             { "chu": "Kỷ niệm" },
 *             { "dungCua": true, "hash": "#tab=ca-nhan" },
 *             { "cho": "Ảnh mới nhất" }]
 */
import fs from "node:fs";
import http from "node:http";
import path from "node:path";

import { chromium } from "playwright";

const [, , WEB_DIR, API_BASE, PORT, PLAN_FILE, OUT_FILE] = process.argv;
if (!WEB_DIR || !API_BASE || !PORT || !PLAN_FILE) {
  console.error("usage: di-bo.mjs <web-dir> <api-base> <static-port> <plan.json> [out.json]");
  process.exit(2);
}
const plan = JSON.parse(fs.readFileSync(PLAN_FILE, "utf8"));

/* --- a static server for the export, so the app is loaded the way a phone
 *     browser loads it: one origin, real navigations, no file:// quirks. --- */
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".ttf": "font/ttf",
};
const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  let file = path.join(WEB_DIR, decodeURIComponent(url.pathname));
  if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(WEB_DIR, "index.html");
  const body = fs.readFileSync(file);
  res.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "application/octet-stream" });
  res.end(body);
});
await new Promise((r) => server.listen(Number(PORT), "127.0.0.1", r));

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  // The app asks the OS for a colour scheme; pinning it keeps two runs of this
  // file comparable, which is the whole basis of the before/after reading.
  colorScheme: "light",
});
const page = await context.newPage();

/** Every request the page made, in order. Collected through `route` rather than
 *  `page.on("request")` because the body is wanted too, and because a bundle
 *  that wraps `window.fetch` can make the event-based count read zero while
 *  requests are plainly leaving the machine. */
const wire = [];
await page.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  if (!API_BASE.endsWith(url.host) && url.host !== new URL(API_BASE).host) return route.continue();
  try {
    const response = await route.fetch();
    const text = await response.text();
    let json = null;
    try {
      json = JSON.parse(text);
    } catch {
      /* images and other non-JSON bodies are recorded by shape only */
    }
    wire.push({
      method: route.request().method(),
      duong: url.pathname + url.search,
      status: response.status(),
      bytes: text.length,
      json,
    });
    await route.fulfill({ response, body: text });
  } catch (e) {
    // A request still in flight when the walk ends is not a finding about the
    // product. It is recorded so a reader can see it was dropped, not silently
    // swallowed -- an unrecorded drop would look like a request never made.
    wire.push({ method: route.request().method(), duong: url.pathname + url.search, status: 0, bo: String(e).split("\n")[0] });
  }
});

const loi = [];
page.on("pageerror", (e) => loi.push(String(e)));
page.on("console", (m) => {
  if (m.type() === "error") loi.push("console: " + m.text());
});

async function dongChu() {
  const text = await page.locator("body").innerText();
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Pressable things, as role+name pairs a plan can name. Roles, not tags:
 *  the tab bar renders `role="tab"` and the category chips `role="radio"`, so a
 *  sweep looking only for buttons reports an app with no navigation. */
async function dieuKhien() {
  return await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll(
      '[role="button"],[role="tab"],[role="radio"],[role="link"],button,a,input,textarea',
    )) {
      const r = el.getAttribute("role") ?? el.tagName.toLowerCase();
      const name = (el.getAttribute("aria-label") || el.textContent || "").replace(/\s+/g, " ").trim();
      const box = el.getBoundingClientRect();
      if (box.width === 0 && box.height === 0) continue;
      out.push({ vai: r, ten: name.slice(0, 70) });
    }
    return out;
  });
}

const buoc = [];
await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1200);
buoc.push({ i: 0, hanh_dong: "TAI /", chu: await dongChu(), nut: await dieuKhien(), wire: wire.length });

for (let i = 0; i < plan.length; i++) {
  const step = plan[i];
  const truoc = wire.length;
  let hanh_dong;
  try {
    if (step.dungCua) {
      // Labelled loudly. A state reached this way proves the screen renders; it
      // proves nothing about whether a finger can get there.
      hanh_dong = `CUA-URL ${step.hash}`;
      await page.goto(`http://127.0.0.1:${PORT}/${step.hash}`, { waitUntil: "domcontentloaded" });
    } else if (step.cho) {
      hanh_dong = `CHỜ "${step.cho}"`;
      await page.getByText(step.cho, { exact: false }).first().waitFor({ timeout: step.giay ? step.giay * 1000 : 20_000 });
    } else if (step.nghi) {
      hanh_dong = `NGHỈ ${step.nghi}ms`;
      await page.waitForTimeout(step.nghi);
    } else if (step.dien) {
      hanh_dong = `ĐIỀN "${step.dien}" <- "${step.gia_tri}"`;
      await page.getByPlaceholder(step.dien).fill(step.gia_tri);
    } else {
      const loc = step.vai
        ? page.getByRole(step.vai, { name: step.ten, exact: step.chinh_xac ?? false })
        : page.getByText(step.chu, { exact: step.chinh_xac ?? false });
      hanh_dong = `BẤM ${step.vai ?? "chữ"} "${step.ten ?? step.chu}"`;
      await loc.first().click({ timeout: 15_000 });
    }
    await page.waitForTimeout(step.doi ?? 1500);
    buoc.push({
      i: i + 1,
      hanh_dong,
      ok: true,
      chu: await dongChu(),
      nut: await dieuKhien(),
      wire_moi: wire.slice(truoc),
    });
  } catch (e) {
    buoc.push({
      i: i + 1,
      hanh_dong: hanh_dong ?? JSON.stringify(step),
      ok: false,
      vi_sao: String(e).split("\n")[0],
      chu: await dongChu(),
      nut: await dieuKhien(),
      wire_moi: wire.slice(truoc),
    });
    break;
  }
}

const ket = { web: WEB_DIR, api: API_BASE, buoc, loi_trang: loi, wire };
if (OUT_FILE) fs.writeFileSync(OUT_FILE, JSON.stringify(ket, null, 1));

for (const b of buoc) {
  console.log(`\n### bước ${b.i}: ${b.hanh_dong}${b.ok === false ? "  ✗ " + b.vi_sao : ""}`);
  console.log("chữ:", JSON.stringify(b.chu));
  console.log("nút:", JSON.stringify((b.nut ?? []).map((n) => `${n.vai}:${n.ten}`)));
  for (const w of b.wire_moi ?? []) console.log(`wire: ${w.method} ${w.duong} -> ${w.status} (${w.bytes}B)`);
}
if (loi.length) console.log("\nlỗi trang:", JSON.stringify(loi.slice(0, 5), null, 1));

await page.unrouteAll({ behavior: "ignoreErrors" });
await browser.close();
server.close();
