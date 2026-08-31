/* BFS click-walk over the whole shell: what can a person reach by TAPPING, and
 * which API paths does each reached view actually request?
 *
 * Why this exists rather than another source scan. Counting features by
 * function name, by how often a screen name is mentioned, or off a hand-written
 * list has failed in this repo every time it was tried: all three are units the
 * author of the code can change to make the number look better, and none of
 * them can notice a screen that exists, compiles, renders, and that no button
 * points at. The unit here is a REQUEST OBSERVED IN A BROWSER after a chain of
 * real presses that started at app launch. Nobody can rename their way into it.
 *
 * What it measures:
 *   - reached[]  : one entry per distinct view the walk landed on, with the
 *                  exact press chain that got there, replayable.
 *   - calls      : every path requested against the API base, attributed to the
 *                  view that was showing when it fired.
 *   - candidates : every pressable the walk saw and did NOT get to try, so a
 *                  budget cut shows up as a number instead of as silence.
 *
 * What it does NOT measure: that the view is correct, readable, or that the
 * data on it is real. The API here is the same stub `screen-snapshots.mjs`
 * drives, so a request proves the CLIENT asks for that path -- whether the
 * server has it is a separate measurement against a live `/openapi.json`.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

import {
  API_BASE,
  CHROME,
  JPEG_B64,
  SCAN_FIXTURE,
  VIETQR_FIXTURE,
  closeServer,
  createStaticServer,
  installBeforeApp,
  listen,
} from "../../tools/screen-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(HERE, "..", "..");

function flag(name, fallback) {
  const hit = process.argv.indexOf(`--${name}`);
  return hit === -1 ? fallback : process.argv[hit + 1];
}

const BUILD_DIR = flag("build-dir", "/tmp/qa-tuso-web");
const OUT = flag("out", "/tmp/qa-tuso-walk.json");
const MAX_DEPTH = Number(flag("depth", "6"));
const MAX_TRIALS = Number(flag("trials", "900"));
const BUDGET_MS = Number(flag("budget-ms", String(26 * 60 * 1000)));

/* Pressables, read off the live DOM the way the CDP helpers do it: role first,
 * then the accessible name react-native-web actually emitted. `Button` in
 * ui/Kit.tsx sets no aria-label, so most of this app is named by its words. */
function docCandidates() {
  const nodes = [
    ...document.querySelectorAll(
      '[role="button"],button,[role="tab"],[role="link"],a[href],[role="switch"],[role="checkbox"],[role="radio"]',
    ),
  ];
  const out = [];
  const seen = new Set();
  for (const el of nodes) {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    const style = getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none") continue;
    if (Number(style.opacity) === 0) continue;
    const aria = el.getAttribute("aria-label");
    const text = (el.textContent || "").replace(/\s+/g, " ").trim();
    const kind = aria ? "nhan" : "chu";
    const value = aria || text;
    if (!value) continue;
    const key = `${kind}:${value}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ kind, value });
  }
  return out;
}

/* A view's identity. Its visible words, normalised. Two different screens read
 * differently; the same screen showing different data reads differently too,
 * which over-counts views and never under-counts them -- the safe direction for
 * a reachability claim. */
function docSignature() {
  const t = (document.body?.innerText ?? "").replace(/\s+/g, " ").trim();
  return t.slice(0, 600);
}

async function pressOne(page, c) {
  const sel = c.kind === "nhan" ? `[aria-label="${c.value.replace(/"/g, '\\"')}"]` : null;
  const box = await page.evaluate(
    (kind, value) => {
      const nodes = [
        ...document.querySelectorAll(
          '[role="button"],button,[role="tab"],[role="link"],a[href],[role="switch"],[role="checkbox"],[role="radio"]',
        ),
      ];
      const match = nodes.find((el) =>
        kind === "nhan"
          ? el.getAttribute("aria-label") === value
          : !el.getAttribute("aria-label") &&
            (el.textContent || "").replace(/\s+/g, " ").trim() === value,
      );
      if (!match) return null;
      match.scrollIntoView({ block: "center", inline: "nearest" });
      if (document.scrollingElement) document.scrollingElement.scrollLeft = 0;
      const r = match.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return null;
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    },
    c.kind,
    c.value,
  );
  if (!box) throw new Error(`khong thay pressable ${c.kind}:${c.value}`);
  if (box.y < 0 || box.y > 844 || box.x < 0 || box.x > 390) {
    throw new Error(`pressable ${c.kind}:${c.value} nam ngoai khung sau khi cuon`);
  }
  // A real pointer press. react-native-web's Pressable listens on pointer
  // events; el.click() can miss onPress entirely and read as "nothing there".
  await page.mouse.click(box.x, box.y);
  await new Promise((r) => setTimeout(r, 420));
  void sel;
}

/* Hand the viewfinder a photo when one is asked for. This is a user action --
 * a person taking a picture -- not a stub: without it the whole bill half of
 * the product is unreachable by definition and the count would be a lie in the
 * other direction. */
async function feedFileInputs(page, jpegPath) {
  const inputs = await page.$$('input[type="file"]');
  let fed = 0;
  for (const inp of inputs) {
    try {
      await inp.uploadFile(jpegPath);
      fed += 1;
    } catch {
      /* an input that refuses a file is not a walk failure */
    }
  }
  if (fed) await new Promise((r) => setTimeout(r, 900));
  return fed;
}

async function main() {
  if (!fs.existsSync(path.join(BUILD_DIR, "index.html"))) {
    throw new Error(`khong co bundle o ${BUILD_DIR}/index.html`);
  }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "walk-"));
  const jpegPath = path.join(tmp, "bill.jpg");
  fs.writeFileSync(jpegPath, Buffer.from(JPEG_B64, "base64"));

  const server = createStaticServer(BUILD_DIR);
  const port = await listen(server);
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    defaultViewport: { width: 390, height: 844, deviceScaleFactor: 1, isMobile: true, hasTouch: true },
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  const started = Date.now();
  const reached = [];          // { sig, path, calls, candidates }
  const seenSig = new Set();
  const allCalls = new Map();  // apiPath -> [sig...]
  let trials = 0;
  let skippedCandidates = 0;
  const failures = [];
  const barren = new Map(); // "kind:label" -> lan thu lien tiep khong mo ra view moi

/* Entering the app with an identity, as a fixed opening prefix.
 *
 * Not hand-holding to flatter the number: it is the door every real user goes
 * through, and the walk still has to find everything after it by pressing. It
 * is a separate RUN rather than one more branch because the guest branch
 * poisons the shared seen-set. Measured: after "Bỏ qua", Khám phá renders the
 * "máy chủ chưa có danh mục địa điểm" panel, and after "Vào app với tư cách
 * Minh" it renders the SAME panel with the same first 600 characters. One
 * signature, so the walk deduped the logged-in Khám phá against the guest one
 * and never expanded a single screen behind it -- 38 views, one API path, and
 * no sign anything had been skipped. */
  const PREFIX = (flag("prefix", "") || "")
    .split("|")
    .filter(Boolean)
    .map((s2) => {
      const i = s2.indexOf(":");
      return { kind: s2.slice(0, i), value: s2.slice(i + 1) };
    });
  const queue = [[...PREFIX]];

  const WORKERS = Number(flag("workers", "5"));

  async function newWorker() {
    const p = await browser.newPage();
    p.setDefaultTimeout(30000);
    await p.evaluateOnNewDocument(installBeforeApp, API_BASE, SCAN_FIXTURE, VIETQR_FIXTURE);
    return p;
  }

  /* The stub replaces window.fetch outright, so nothing reaches the network
   * layer and `page.on("request")` sees zero -- measured, first run of this
   * file: 8 views reached, 0 calls. The log the stub keeps is the only place a
   * request is visible, and it is written BEFORE the stub decides whether it
   * knows the route, so it records what the CLIENT asked for rather than what
   * the fake could answer. That is the leg being measured here. */
  const readCalls = (p) => p.evaluate(() => window.__snapshotApiLog ?? []);

  async function replay(p, chain) {
    await p.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded" });
    await p.waitForFunction(() => (document.body?.innerText ?? "").trim().length > 0, {
      timeout: 20000,
    });
    await new Promise((r) => setTimeout(r, 260));
    for (const c of chain) {
      await feedFileInputs(p, jpegPath);
      await pressOne(p, c);
    }
    await feedFileInputs(p, jpegPath);
    await new Promise((r) => setTimeout(r, 160));
  }

  let busy = 0;
  async function worker(p) {
    for (;;) {
      if (trials >= MAX_TRIALS || Date.now() - started > BUDGET_MS) return;
      if (!queue.length) {
        /* An empty queue is not the end of the walk while another worker is
         * still on a trial that will refill it. The first run of this file quit
         * at 126 trials with 342 entries still queued because six workers each
         * saw a momentary gap and returned -- and the door to a real identity
         * ("Vào app với tư cách Minh") was one of the entries left behind, so
         * every screen after it read "Chưa chọn người" and the whole app
         * measured as one API call. Wait for the others instead. */
        if (busy === 0) return;
        await new Promise((r) => setTimeout(r, 120));
        continue;
      }
      const chain = queue.shift();
      const last = chain.length
        ? `${chain[chain.length - 1].kind}:${chain[chain.length - 1].value}`
        : "";
      /* The tab bar and the [+] sheet ride on every screen, so without this the
       * queue is mostly the same five controls pressed from sixty places. A
       * control tried from three different views that never opened anything new
       * stops being queued -- and what that dropped is counted and printed,
       * because a silent cut reads as "covered everything". */
      if (last && (barren.get(last) ?? 0) >= 3) {
        skippedCandidates += 1;
        continue;
      }
      trials += 1;
      busy += 1;
      try {
        await replay(p, chain);
      } catch (err) {
        failures.push({ chain, err: String(err).slice(0, 200) });
        busy -= 1;
        continue;
      }
      let sig;
      try {
        sig = await p.evaluate(docSignature);
      } catch (err) {
        failures.push({ chain, err: String(err).slice(0, 200) });
        busy -= 1;
        continue;
      }
      if (seenSig.has(sig)) {
        if (last) barren.set(last, (barren.get(last) ?? 0) + 1);
        busy -= 1;
        continue;
      }
      seenSig.add(sig);
      if (last) barren.set(last, 0);
      const calls = [...new Set(await readCalls(p))];
      for (const c of calls) {
        if (!allCalls.has(c)) allCalls.set(c, []);
        allCalls.get(c).push(sig.slice(0, 60));
      }
      const cands = await p.evaluate(docCandidates);
      reached.push({ sig, chain, calls, candidates: cands.map((c) => `${c.kind}:${c.value}`) });
      process.stdout.write(
        `[${trials}] d=${chain.length} moi=${reached.length} api=${allCalls.size} q=${queue.length} :: ${sig.slice(0, 60)}\n`,
      );
      if (chain.length >= MAX_DEPTH) {
        skippedCandidates += cands.length;
        busy -= 1;
        continue;
      }
      for (const c of cands) queue.push([...chain, c]);
      busy -= 1;
    }
  }

  const pages = [];
  for (let i = 0; i < WORKERS; i += 1) pages.push(await newWorker());
  // One worker primes the root so the others have a queue to pull from.
  await worker(pages[0]);
  await Promise.all(pages.map((p) => worker(p)));
  skippedCandidates += queue.length;

  await browser.close();
  await closeServer(server);
  fs.rmSync(tmp, { recursive: true, force: true });

  const report = {
    buildDir: BUILD_DIR,
    apiBase: API_BASE,
    maxDepth: MAX_DEPTH,
    trials,
    reachedViews: reached.length,
    queueBoDo: skippedCandidates,
    failures: failures.length,
    failuresSample: failures.slice(0, 25),
    apiPathsRequested: [...allCalls.keys()].sort(),
    reached,
    elapsedMs: Date.now() - started,
  };
  fs.writeFileSync(OUT, JSON.stringify(report, null, 2));
  console.log(
    `\n=== xong: ${trials} lan thu, ${reached.length} view rieng biet, ` +
      `${allCalls.size} duong API duoc goi, ${skippedCandidates} nut CHUA thu, ` +
      `${failures.length} lan bam hong -> ${OUT}`,
  );
  void MOBILE_ROOT;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
