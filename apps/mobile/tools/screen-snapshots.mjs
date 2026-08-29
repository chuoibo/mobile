/** Drive the real web bundle through the organiser state machine and snapshot each screen.
 *
 * A design detector scans these HTML files. It must see the CSS that
 * `react-native-web` injects at runtime into `<style>` tags, which is why this
 * loads the already-built bundle in a headless browser rather than generating
 * markup from source. The snapshots then have every `<script>` tag stripped:
 * leave a script in and the detector re-runs the app, which resets to screen 1
 * and every file looks like the camera. That is the whole point of this file.
 *
 * Dev tool, not shipped code. Nothing in the app may import it.
 *
 *     cd apps/mobile && npm run build:check && node tools/screen-snapshots.mjs
 */
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..");

/** Same sentinel `build:check` inlines. The fetch stub keys off this prefix. */
const API_BASE = "http://api.build-check.invalid";

const STEPS = ["chup-bill", "ket-qua", "goi-y", "nhap", "de-xuat", "dot-thu", "chia-se"];

/**
 * States of one screen that the linear walk does not reach.
 *
 * The matrix has two layouts and the walk only exercises the roomy one. Six
 * people do not fit four 44pt columns beside a legible dish name on a 390pt
 * phone, so the row collapses to a "k/N" chip, and an unscanned branch is an
 * unmeasured one.
 *
 * The picker that chip opens is deliberately NOT in this list. `Modal` uses
 * `animationType="slide"`, and stripping the scripts freezes that animation
 * on its first frame: the markup is in the file and reports `position: fixed`
 * at the right size, but it paints nothing, so a clean detector result for it
 * would be a clean result for a blank overlay. It is captured as a live PNG
 * instead -- see `pickerShot` -- which is evidence of what renders but is not
 * a detector scan, and must not be described as one.
 */
const EXTRA = ["goi-y-dong"];

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".ico": "image/x-icon",
  ".png": "image/png",
};

export const CHROME =
  process.env.PUPPETEER_EXECUTABLE_PATH ||
  "/home/lakiet/.cache/ms-playwright/chromium-1194/chrome-linux/chrome";

/**
 * A real 32x32 JPEG, not a truncated stub. Written to a temp file at runtime
 * because the repo guard rejects new binaries, and a bill photo must never
 * enter git.
 *
 * The bytes have to actually decode: `expo-image-manipulator`'s web loader
 * does `image.onerror = () => reject(canvas)`, and App.tsx stringifies a
 * non-Error as `String(problem)` -- so a broken JPEG surfaces as the visible
 * text `[object HTMLCanvasElement]` and the scan never starts.
 */
export const JPEG_B64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAAgACADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDz+iiivlD+gAooooAKKKKACiiigD//2Q==";

/**
 * Wire body of `POST /receipts/scan`, matching `ReceiptScanWire` in receipt.ts.
 *
 * Item total equals printed total equals the expense total that "Tiếp tục"
 * copies onto the form, so the next screen does not stall on a blocked
 * reading and the allocator gets a number that splits evenly across 3 people.
 * Money is integer dong throughout -- a float here would throw in `formatVnd`.
 */
export const SCAN_FIXTURE = {
  items: [
    { name: "Lẩu thái", quantity: 1, unit_price_vnd: 280000, line_total_vnd: 280000 },
    { name: "Nước sâm", quantity: 2, unit_price_vnd: 25000, line_total_vnd: 50000 },
    { name: "Cơm rang", quantity: 1, unit_price_vnd: 150000, line_total_vnd: 150000 },
  ],
  items_total_vnd: 480000,
  total_vnd: 480000,
  totals_agree: true,
  total_difference_vnd: 0,
  // The field the route actually sends. It used to be `confidence: 91`, which
  // the route has never sent, so this stub was quietly rehearsing a contract
  // nobody serves -- and the screens rendered a percentage off the back of it.
  // `false` is right for this fixture: the lines and the printed total agree.
  // It means no signal fired, not that the reading is correct.
  //
  // The other branch is not covered by the linear walk, so it has to be
  // scanned by flipping this to `true` and re-running -- the pill changes both
  // its words and its colours there, and a palette that has never been
  // rendered has never been measured.
  needs_review: false,
  warnings: [],
};

function flag(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  if (i >= 0 && process.argv[i + 1]) return path.resolve(process.argv[i + 1]);
  return fallback;
}

export function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    // Port 0: the OS picks an ephemeral one so two runs cannot collide.
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
}

export function closeServer(server) {
  return new Promise((resolve) => {
    if (!server.listening) {
      resolve();
      return;
    }
    server.close(() => resolve());
  });
}

/** Static file server for the Expo web export. No SPA fallback: the app is `/`. */
export function createStaticServer(root) {
  const resolvedRoot = path.resolve(root);
  return http.createServer((req, res) => {
    try {
      const url = new URL(req.url ?? "/", "http://127.0.0.1");
      let pathname = decodeURIComponent(url.pathname);
      if (pathname === "/" || pathname === "") pathname = "/index.html";
      const file = path.resolve(resolvedRoot, `.${pathname}`);
      if (file !== resolvedRoot && !file.startsWith(resolvedRoot + path.sep)) {
        res.writeHead(403);
        res.end("forbidden");
        return;
      }
      if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
        res.writeHead(404, { "Content-Type": "text/plain" });
        res.end("not found");
        return;
      }
      const ext = path.extname(file).toLowerCase();
      res.writeHead(200, { "Content-Type": MIME[ext] ?? "application/octet-stream" });
      fs.createReadStream(file).pipe(res);
    } catch (err) {
      res.writeHead(500);
      res.end(String(err));
    }
  });
}

/**
 * Install the API stub and a file-input click patch BEFORE the bundle runs.
 *
 * `scanReceipt` (and `sizeOf` on web) call `fetch(blobUri).blob()`. Intercepting
 * every fetch would swallow those and the scan would hang with an empty photo.
 * Only URLs that start with the inlined API base are stubbed; everything else
 * -- `blob:`, `data:`, the bundle itself -- falls through to real `fetch`.
 *
 * Expo's web picker does `input.dispatchEvent(new MouseEvent("click"))`, which
 * does not open a file chooser. Puppeteer's `waitForFileChooser` listens for
 * the native activation, so a dispatched click is rewritten to `HTMLInputElement.click()`.
 */
export function installBeforeApp(apiBase, scanBody) {
  const originalFetch = window.fetch.bind(window);

  const db = {
    expenseId: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    versionId: "vvvvvvvv-vvvv-4vvv-8vvv-vvvvvvvvvvvv",
    batchId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    allocations: {},
    obligations: [],
    lastPath: "",
  };
  window.__snapshotApiLog = [];

  function json(data, status = 200) {
    return new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }

  function requestUrl(input) {
    if (typeof input === "string") return input;
    if (input instanceof URL) return input.href;
    if (input && typeof input.url === "string") return input.url;
    return String(input);
  }

  function evenSplit(ids, total) {
    const n = ids.length;
    const base = Math.floor(total / n);
    const remainder = total - base * n;
    const allocations = {};
    const rounding_gainers = [];
    ids.forEach((id, i) => {
      allocations[id] = base + (i < remainder ? 1 : 0);
      if (i < remainder) rounding_gainers.push(id);
    });
    return { allocations, rounding_gainers };
  }

  window.fetch = async function stubbedFetch(input, init = {}) {
    const url = requestUrl(input);
    if (!url.startsWith(apiBase)) return originalFetch(input, init);

    const method = (
      init.method ||
      (typeof input === "object" && input && input.method) ||
      "GET"
    ).toUpperCase();
    const path = url.slice(apiBase.length).split("?")[0];
    db.lastPath = `${method} ${path}`;
    window.__snapshotApiLog.push(db.lastPath);

    let parsed = null;
    const raw = init.body;
    if (typeof raw === "string") {
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = null;
      }
    }

    if (method === "POST" && path === "/receipts/scan") return json(scanBody);

    const person = /^\/people\/([^/]+)$/.exec(path);
    if (method === "PUT" && person) {
      return json({ id: person[1], display_name: parsed?.display_name ?? "" });
    }

    if (method === "POST" && path === "/expenses") {
      const ids = parsed.participants;
      const total = parsed.total_amount_vnd;
      const split = evenSplit(ids, total);
      db.allocations = split.allocations;
      const payer = parsed.paid_by_id;
      db.obligations = ids
        .filter((id) => id !== payer)
        .map((id, i) => ({
          obligation_id: `aaaaaaaa-aaaa-4aaa-8aaa-${String(i + 1).padStart(12, "0")}`,
          sender_id: id,
          recipient_id: payer,
          amount_vnd: split.allocations[id],
        }));
      return json({
        expense_id: db.expenseId,
        proposal: parsed,
        allocation: {
          allocations: split.allocations,
          rounding_gainers: split.rounding_gainers,
        },
      });
    }

    if (method === "POST" && /^\/expenses\/[^/]+\/confirm$/.test(path)) {
      return json({
        expense_version_id: db.versionId,
        payer_acknowledgement: "acknowledged",
      });
    }

    if (method === "POST" && path === "/batches") {
      return json({ batch_id: db.batchId, obligations: db.obligations });
    }

    if (method === "POST" && /^\/batches\/[^/]+\/publish$/.test(path)) {
      return json({
        guest_links: db.obligations.map((row) => ({
          sender_id: row.sender_id,
          path: `/g/${row.obligation_id}`,
          obligations: [{ obligation_id: row.obligation_id, amount_vnd: row.amount_vnd }],
        })),
      });
    }

    if (method === "GET" && /^\/batches\/[^/]+\/obligations$/.test(path)) {
      return json({
        disputed_count: 0,
        obligations: db.obligations.map((row) => ({
          ...row,
          obligation_status: "outstanding",
          disputed: false,
        })),
      });
    }

    if (method === "POST" && /^\/obligations\/[^/]+\/confirm-receipt$/.test(path)) {
      return json({ obligation_status: "confirmed" });
    }

    return json({ code: "unstubbed", detail: `no stub for ${method} ${path}` }, 404);
  };

  const nativeClick = HTMLInputElement.prototype.click;
  const originalDispatch = EventTarget.prototype.dispatchEvent;
  let openingChooser = false;
  EventTarget.prototype.dispatchEvent = function patchedDispatch(event) {
    if (
      !openingChooser &&
      this instanceof HTMLInputElement &&
      this.type === "file" &&
      event &&
      event.type === "click"
    ) {
      // Native click is what CDP reports as a file chooser; a synthetic
      // MouseEvent is not. Without this, waitForFileChooser never fires.
      openingChooser = true;
      try {
        nativeClick.call(this);
      } finally {
        openingChooser = false;
      }
      return true;
    }
    return originalDispatch.call(this, event);
  };
}

async function visibleText(page) {
  return page.evaluate(() => document.body?.innerText ?? "");
}

async function apiLog(page) {
  try {
    return await page.evaluate(() => window.__snapshotApiLog ?? []);
  } catch {
    return [];
  }
}

export async function waitForScreen(page, step, needle, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const text = await visibleText(page);
    if (text.includes(needle)) return;
    if (/Không nối được|Máy chủ trả về \d/.test(text)) {
      throw new Error(
        `${step}: app showed an error before ${JSON.stringify(needle)} appeared.\n${text}`,
      );
    }
    await new Promise((r) => setTimeout(r, 50));
  }
  const text = await visibleText(page);
  const calls = await apiLog(page);
  throw new Error(
    `${step}: timed out waiting for ${JSON.stringify(needle)}.\n` +
      `API calls: ${calls.join(", ") || "(none)"}\n` +
      `Visible text:\n${text}`,
  );
}

export async function clickAria(page, label) {
  const sel = `[aria-label="${label}"]`;
  await page.waitForSelector(sel, { visible: true, timeout: 15000 });
  // Scroll first, then fall back to a scripted click. The avatar strip is a
  // horizontal ScrollView, so with six people the last few sit outside the
  // clipped box: `page.click` needs a clickable point and there is none for
  // an element scrolled off to the right. That is the strip working as
  // intended, not a defect, but the walk still has to reach them.
  // `inline: "nearest"`, and the document's own horizontal scroll put back
  // afterwards. This used to centre horizontally, which walked into a real
  // defect on the opening screen: measured at 390x844 the document is 445px
  // wide against a 390px viewport, so centring the "Bỏ qua" control scrolled
  // the whole page sideways, `page.click` landed on the background, and the
  // walk sat on `MoDau` until it timed out. `page.click` does not throw in
  // that case, so the JS fallback below never ran and the failure surfaced
  // three steps later as "timed out waiting for Khám phá".
  //
  // `nearest` still scrolls an inner container -- which is what the avatar
  // strip needed -- it just declines to move the page under the pointer.
  await page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) throw new Error(`no element ${s}`);
    el.scrollIntoView({ block: "center", inline: "nearest" });
    if (document.scrollingElement) document.scrollingElement.scrollLeft = 0;
  }, sel);
  try {
    await page.click(sel);
  } catch {
    await page.evaluate((s) => document.querySelector(s).click(), sel);
  }
}

export async function clickButton(page, label) {
  const found = await page.waitForFunction(
    (needle) => {
      const nodes = [...document.querySelectorAll("button, [role='button']")];
      return (
        nodes.find((el) => el.textContent.replace(/\s+/g, " ").trim() === needle) ?? null
      );
    },
    { timeout: 15000 },
    label,
  );
  const el = found.asElement();
  if (el) {
    try {
      await el.click();
      return;
    } catch {
      /* off-screen or clipped; the scripted click below still reaches it */
    }
  }
  await page.evaluate((needle) => {
    const nodes = [...document.querySelectorAll("button, [role='button']")];
    const match = nodes.find((n) => n.textContent.replace(/\s+/g, " ").trim() === needle);
    if (!match) throw new Error(`no button ${needle}`);
    match.click();
  }, label);
}

async function typePlaceholder(page, placeholder, value) {
  const sel = `input[placeholder="${placeholder}"]`;
  await page.waitForSelector(sel, { visible: true, timeout: 15000 });
  await page.click(sel, { clickCount: 3 });
  await page.type(sel, value, { delay: 15 });
}

/**
 * Add one person on the matrix screen.
 *
 * Not `addPerson`: there the name field is always mounted, here it appears
 * only after the "+" avatar is pressed and unmounts again on submit, so
 * waiting for an empty input would wait for a node that has gone. The "+"
 * carries `aria-label="Thêm"` while the confirm button's text is exactly
 * "Thêm" and it has no aria-label, which is what keeps the two apart.
 */
export async function addPersonOnMatrix(page, name) {
  await clickAria(page, "Thêm");
  const sel = 'input[placeholder="Hà"]';
  await page.waitForSelector(sel, { visible: true, timeout: 15000 });
  await page.click(sel);
  await page.type(sel, name, { delay: 15 });
  await clickButton(page, "Thêm");
  await page.waitForFunction(
    (n) => (document.body?.innerText ?? "").includes(n),
    { timeout: 10000 },
    name,
  );
}

/** Wait until every avatar shows a figure the server sent, not the "..." placeholder. */
export async function waitForPreview(page) {
  await page.waitForFunction(
    () => {
      const text = document.body?.innerText ?? "";
      return text.includes("Tổng cộng") && !text.includes("...");
    },
    { timeout: 20000 },
  );
}

async function snapshot(page, outDir, step) {
  const { html, cssText } = await page.evaluate(() => {
    // `react-native-web` builds its stylesheet through the CSSOM
    // (`sheet.insertRule`), and rules inserted that way are NOT reflected in
    // the `<style>` element's text. So `outerHTML` alone serializes a page
    // whose every class-based rule is gone: the app renders in the UA's serif
    // with default button chrome, and a scan of it reports layout and contrast
    // findings that describe the serializer rather than the screen. Read the
    // rules back out of `document.styleSheets` and write them in as real text.
    const blocks = [];
    for (const sheet of [...document.styleSheets]) {
      let list;
      try {
        list = sheet.cssRules;
      } catch {
        // Cross-origin sheet. None are expected here, and skipping one
        // silently is what would make this lie, so it contributes nothing and
        // is caught by the floor below.
        continue;
      }
      const text = [...list].map((rule) => rule.cssText).join("\n");
      if (text.trim() === "") continue;
      blocks.push(text);
    }

    const root = document.documentElement.cloneNode(true);
    // Detector re-executes leftover scripts and the app remounts on screen 1.
    for (const script of [...root.querySelectorAll("script")]) script.remove();
    // Drop the now-empty shells so the reconstructed sheet is the only source
    // of truth, then append it last so cascade order still favours it.
    for (const style of [...root.querySelectorAll("style")]) style.remove();
    const head = root.querySelector("head");
    const rebuilt = root.ownerDocument.createElement("style");
    rebuilt.setAttribute("data-snapshot", "reconstructed-cssom");
    rebuilt.textContent = blocks.join("\n");
    head.appendChild(rebuilt);

    return { html: `<!DOCTYPE html>\n${root.outerHTML}\n`, cssText: rebuilt.textContent };
  });
  if (/<script[\s>]/i.test(html)) {
    throw new Error(`${step}: serialized HTML still contains a <script> tag`);
  }
  // A snapshot that lost the stylesheet still looks like a page and still
  // scans -- it just scans as the UA's serif with default button chrome, and
  // reports contrast and layout findings that describe this serializer rather
  // than the screen. That is the failure this floor exists to make loud.
  //
  // Measured on what was actually WRITTEN, not on what was found: an earlier
  // version counted the rules discovered while walking `document.styleSheets`,
  // and a deliberate break that dropped every rule on the floor still passed
  // it, because the rules had been counted before being discarded. A guard
  // that cannot go red is decoration.
  const ruleCount = (html.match(/\{/g) ?? []).length;
  if (cssText.trim().length < 2000 || ruleCount < 50) {
    throw new Error(
      `${step}: stylesheet did not survive serialization ` +
        `(${cssText.trim().length} chars of CSS, ${ruleCount} rule bodies) — ` +
        `the snapshot would render in the UA default and scan as a different screen`,
    );
  }
  // The app's own class-based rules are the ones lost when the CSSOM is not
  // read back, so name one rather than trusting a byte count alone.
  if (!/\.css-146c3p1|\.css-g5y9jx/.test(html)) {
    throw new Error(`${step}: react-native-web class rules missing from the snapshot`);
  }
  const dest = path.join(outDir, `${step}.html`);
  fs.writeFileSync(dest, html, "utf8");
  const bytes = fs.statSync(dest).size;
  console.log(`${step}  ${dest}  ${bytes} bytes`);
  return dest;
}

async function failAt(page, step, err) {
  let text = "";
  try {
    text = await visibleText(page);
  } catch {
    text = "(could not read page)";
  }
  const calls = await apiLog(page);
  console.error(`FAILED at step "${step}": ${err.message}`);
  if (calls.length) console.error(`API calls so far: ${calls.join(", ")}`);
  console.error(`Visible text at failure:\n${text}`);
}

async function drive(page, outDir, jpegPath) {
  let step = "chup-bill";

  // The flow no longer starts the app. Since the five-tab shell landed on
  // main, the bundle opens on `MoDau` and the expense flow is reached from
  // the [+] menu -- so getting to the viewfinder is three presses, not zero.
  // Driving it rather than deep-linking is deliberate: this is the only place
  // that checks the shell actually hands over to these screens, which is
  // exactly what the rebase could have silently broken.
  step = "vao-app";
  await clickAria(page, "Bỏ qua, vào app mà chưa chọn người");
  await waitForScreen(page, step, "Khám phá");

  step = "menu-tao";
  await clickAria(page, "Tạo mới");
  await waitForScreen(page, step, "Tạo khoản chi");

  step = "chup-bill";
  await clickAria(page, "Tạo khoản chi. Chụp bill hoặc nhập tay, AI chia tiền");
  await waitForScreen(page, step, "Chụp bill");
  await snapshot(page, outDir, step);

  step = "ket-qua";
  // Register the chooser first: the click both opens Expo's hidden <input>
  // and (via the dispatchEvent patch) the native file chooser CDP intercepts.
  const chooserP = page.waitForFileChooser({ timeout: 20000 });
  await clickAria(page, "Chọn ảnh bill");
  const chooser = await chooserP;
  await chooser.accept([jpegPath]);
  await waitForScreen(page, step, "Kết quả nhận diện", 45000);
  await snapshot(page, outDir, step);

  step = "goi-y";
  await clickButton(page, "Tiếp tục");
  await waitForScreen(page, step, "Gợi ý chia theo người");
  // The roster is built here now, so the matrix has columns to draw. Ticking
  // one box off before the snapshot is deliberate: a grid where every cell is
  // on cannot show that an off cell is legible, and the off state is the one
  // carrying a 3:1 border instead of a fill.
  await addPersonOnMatrix(page, "Nam");
  await addPersonOnMatrix(page, "Hà");
  await addPersonOnMatrix(page, "Quyên");
  await clickAria(page, "Nam, Lẩu thái");
  await waitForPreview(page);
  await snapshot(page, outDir, step);

  // The crowded layout, and then the picker it opens. Three more names take
  // the group past what the inline columns can hold.
  for (const name of ["Bình", "Chi", "Dũng"]) await addPersonOnMatrix(page, name);
  await page.waitForFunction(() => (document.body?.innerText ?? "").includes("/6"));
  await waitForPreview(page);
  await snapshot(page, outDir, "goi-y-dong");

  await clickAria(page, "6 trên 6 người đã ăn Nước sâm");
  await page.waitForFunction(
    () => [...document.querySelectorAll("button, [role='button']")]
      .some((b) => b.textContent.trim() === "Xong"),
  );
  // A live capture, not a snapshot: the slide animation does not survive
  // script stripping. Written outside the repo -- the guard rejects new
  // binaries, and nothing about a bill may enter git.
  // Let the slide finish. Waiting for the button to exist only proves the
  // overlay mounted; screenshotting there catches it mid-transform, still off
  // the bottom of the screen, and the capture looks exactly like a picker
  // that never opened.
  await page.waitForFunction(() => {
    const m = document.querySelector('[aria-modal="true"]');
    if (!m) return false;
    const r = m.getBoundingClientRect();
    return r.top <= 1 && r.height > 100;
  }, { timeout: 10000 });
  const pickerShot = path.join(os.tmpdir(), "goi-y-chon-live.png");
  await page.screenshot({ path: pickerShot });
  console.log(`goi-y-chon (live png)  ${pickerShot}`);
  await clickButton(page, "Xong");

  // Back to four, so the rest of the walk sees the roster it expects.
  for (const name of ["Bình", "Chi", "Dũng"]) {
    await clickAria(page, name);
    await clickButton(page, `Xoá ${name} khỏi nhóm`);
    await page.waitForFunction(
      (n) => !(document.body?.innerText ?? "").includes(n),
      { timeout: 10000 },
      name,
    );
  }

  step = "nhap";
  await clickButton(page, "Xem kết quả");
  await waitForScreen(page, step, "Khoản chi mới");
  await snapshot(page, outDir, step);

  await typePlaceholder(page, "bữa lẩu tối thứ bảy", "bữa lẩu tối thứ bảy");
  await page.waitForFunction(() => {
    const radios = [...document.querySelectorAll('[role="radio"]')];
    return radios.some((r) => r.textContent.trim() === "Nam");
  });
  await page.evaluate(() => {
    const radios = [...document.querySelectorAll('[role="radio"]')];
    const nam = radios.find((r) => r.textContent.trim() === "Nam");
    if (!nam) throw new Error('no radio for "Nam"');
    nam.click();
  });
  await page.waitForFunction(() => {
    const btn = [...document.querySelectorAll("button")].find(
      (b) => b.textContent.trim() === "Chia tiền",
    );
    return btn && !btn.disabled;
  });

  step = "de-xuat";
  await clickButton(page, "Chia tiền");
  await waitForScreen(page, step, "Đúng rồi, ghi vào sổ");
  await snapshot(page, outDir, step);

  step = "dot-thu";
  await clickButton(page, "Đúng rồi, ghi vào sổ");
  await waitForScreen(page, step, "Đợt thu");
  await snapshot(page, outDir, step);

  await clickButton(page, "Phát đợt thu");
  await waitForScreen(page, step, "Chia sẻ cho từng người");

  step = "chia-se";
  await clickButton(page, "Chia sẻ cho từng người");
  await waitForScreen(page, step, "Mỗi người một link riêng");
  await snapshot(page, outDir, step);
}

async function main() {
  const buildDir = flag("build-dir", path.join(MOBILE_ROOT, ".expo-build-check"));
  const outDir = flag("out", path.join(MOBILE_ROOT, ".screen-snapshots"));

  if (!fs.existsSync(path.join(buildDir, "index.html"))) {
    throw new Error(
      `No bundle at ${buildDir}/index.html. Run: cd apps/mobile && npm run build:check`,
    );
  }
  if (!fs.existsSync(CHROME)) {
    throw new Error(`Chromium not found at ${CHROME}`);
  }

  fs.mkdirSync(outDir, { recursive: true });
  for (const step of [...STEPS, ...EXTRA]) {
    const stale = path.join(outDir, `${step}.html`);
    try {
      fs.unlinkSync(stale);
    } catch (err) {
      if (err.code !== "ENOENT") throw err;
    }
  }

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "bill-snap-"));
  const jpegPath = path.join(tmp, "bill.jpg");
  fs.writeFileSync(jpegPath, Buffer.from(JPEG_B64, "base64"));

  const server = createStaticServer(buildDir);
  let browser = null;
  let page = null;
  let current = "startup";
  try {
    const port = await listen(server);
    browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: true,
      defaultViewport: {
        width: 390,
        height: 844,
        deviceScaleFactor: 2,
        isMobile: true,
        hasTouch: true,
      },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });
    page = await browser.newPage();
    page.setDefaultTimeout(30000);
    const pageErrors = [];
    page.on("pageerror", (err) => pageErrors.push(String(err)));

    await page.evaluateOnNewDocument(installBeforeApp, API_BASE, SCAN_FIXTURE);
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded" });

    try {
      await drive(page, outDir, jpegPath);
    } catch (err) {
      current = err.message.split(":")[0] || current;
      await failAt(page, current, err);
      if (pageErrors.length) console.error(`Page errors:\n${pageErrors.join("\n")}`);
      throw err;
    }

    const missing = [...STEPS, ...EXTRA].filter((s) => !fs.existsSync(path.join(outDir, `${s}.html`)));
    if (missing.length) {
      throw new Error(`Not all snapshots written: missing ${missing.join(", ")}`);
    }
  } finally {
    if (browser) {
      try {
        await browser.close();
      } catch {
        /* shutdown must not hide the original error */
      }
    }
    await closeServer(server);
    try {
      fs.rmSync(tmp, { recursive: true, force: true });
    } catch {
      /* temp jpeg is outside the repo; failing to delete it is not a test fail */
    }
  }
}

/* Exports above are for `tools/aria-probe.mjs`, which drives the same bundle
 * through the same fetch stub to read attributes off the live DOM. Only run
 * the snapshot walk when this file is the one that was invoked. */
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
