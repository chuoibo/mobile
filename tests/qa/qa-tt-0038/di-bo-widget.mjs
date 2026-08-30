/* QA walk of the F38 widget screen (#348), as a person meets it.
 *
 * Two questions the assertion tiers in `apps/mobile/tests/widget.test.mjs` do
 * not reach, because both are about the rendered composite rather than the
 * element tree:
 *
 *   1. Does the screen actually paint -- a photograph that DECODES, the author
 *      line, the caption -- when reached by URL at `#vao=widget`?
 *   2. Does the card overflow a small phone? The frame is `width: "100%"` with
 *      `aspectRatio: 1` inside a padded scroller, and that combination is the
 *      usual way a square frame pushes past the right edge on 320pt.
 *
 * Question 2 is measured, not eyeballed: a screenshot at 320 LOOKS flush to the
 * edge because the card's right margin falls outside the rounded corner, and
 * reading a defect off that picture is how a false finding gets filed. What
 * settles it is `documentElement.scrollWidth` against `clientWidth` plus the
 * card's own rectangle, at three widths.
 *
 * Paths are resolved from `import.meta.url`. Evidence that names one machine
 * cannot be re-run by the reader of a verdict -- see
 * `tests/test_qa_evidence_runs_on_another_machine.py`, which fails this file if
 * an absolute home directory ever appears in it.
 *
 * Run:
 *   cd apps/mobile && npm run build:check
 *   PUPPETEER_EXECUTABLE_PATH=<chrome> node tests/qa/qa-tt-0038/di-bo-widget.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE = path.resolve(HERE, "..", "..", "..", "apps", "mobile");

const puppeteer = (
  await import(pathToFileURL(path.join(MOBILE, "node_modules", "puppeteer-core", "lib", "esm", "puppeteer", "puppeteer-core.js")).href)
).default;
const { createStaticServer, listen, closeServer, CHROME } = await import(
  pathToFileURL(path.join(MOBILE, "tools", "screen-snapshots.mjs")).href
);
const { API_BASE, NGUOI, installTabStubs, taoFixtures, themAnhDiaDiem } = await import(
  pathToFileURL(path.join(MOBILE, "tools", "tab-snapshots.mjs")).href
);

const buildDir = path.join(MOBILE, ".expo-build-check");
const indexPath = path.join(buildDir, "index.html");
if (!fs.existsSync(indexPath)) {
  throw new Error(`Khong co bundle o ${indexPath}. Chay: cd apps/mobile && npm run build:check`);
}

const fx = themAnhDiaDiem(taoFixtures());
const html = fs.readFileSync(indexPath, "utf8");
const i = html.indexOf("<head>");
if (i === -1) throw new Error("index.html khong co <head> de chen stub");
const trang = "__qa-tt-0038-widget.html";
fs.writeFileSync(
  path.join(buildDir, trang),
  html.slice(0, i + 6) +
    `<script>(${installTabStubs.toString()})(${JSON.stringify(API_BASE)},${JSON.stringify(fx)});</script>` +
    html.slice(i + 6),
);

const server = createStaticServer(buildDir);
let hong = 0;
let browser = null;
try {
  const port = await listen(server);
  browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  for (const vw of [320, 360, 390]) {
    const page = await browser.newPage();
    page.setDefaultTimeout(30000);
    await page.setViewport({ width: vw, height: 780 });
    // A fresh document per width. Changing only the fragment does not remount,
    // so the next width would be measured on the previous one's layout.
    await page.goto("about:blank");
    await page.goto(`http://127.0.0.1:${port}/${trang}#vao=widget&nguoi=${NGUOI}`, {
      waitUntil: "networkidle0",
    });
    // The author line, not the heading: "Ảnh mới nhất" is chrome this screen
    // prints in all four states including the refusal.
    await page.waitForFunction(() => (document.body?.innerText ?? "").includes("Minh · "));

    const m = await page.evaluate(() => {
      const img = document.querySelector("img");
      const ir = img ? img.getBoundingClientRect() : null;
      let card = img;
      while (card && ir && card.getBoundingClientRect().height < ir.height + 20) {
        card = card.parentElement;
      }
      const r = card ? card.getBoundingClientRect() : null;
      return {
        vw: document.documentElement.clientWidth,
        scrollW: document.documentElement.scrollWidth,
        // naturalWidth > 0 is the only proof the bytes decoded; a broken <img>
        // still has a layout box and still reports a rectangle.
        anh: [...document.querySelectorAll("img")].map((im) => im.naturalWidth),
        card: r ? { l: Math.round(r.left), r: Math.round(r.right) } : null,
        text: document.body.innerText,
        // Real cut detection: what the box can show vs what it holds.
        cat: [...document.querySelectorAll("*")]
          .filter((e) => e.children.length === 0 && (e.textContent ?? "").trim())
          .filter((e) => e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1)
          .map((e) => (e.textContent ?? "").trim().slice(0, 40)),
      };
    });

    const giaiMa = m.anh.filter((w) => w > 0).length;
    const tran = m.scrollW > m.vw;
    const leTrai = m.card ? m.card.l : -1;
    const lePhai = m.card ? m.vw - m.card.r : -1;
    const coTacGia = m.text.includes("Minh · ");
    const coCaption = m.text.includes("Sáng Đà Lạt");

    const loi = [];
    if (giaiMa !== 1) loi.push(`anh giai ma duoc=${giaiMa}, can 1`);
    if (tran) loi.push(`TRAN NGANG scrollW=${m.scrollW} > vw=${m.vw}`);
    if (leTrai !== lePhai) loi.push(`le lech trai=${leTrai} phai=${lePhai}`);
    if (!coTacGia) loi.push("thieu dong tac gia");
    if (!coCaption) loi.push("thieu caption");
    if (m.cat.length) loi.push(`chu bi CAT: ${m.cat.join(" / ")}`);

    if (loi.length) hong += 1;
    console.log(
      `  ${loi.length ? "HONG" : "dat "}  vw=${m.vw}  anh giai ma=${giaiMa}  ` +
        `le trai/phai=${leTrai}/${lePhai}  tran=${tran ? "CO" : "khong"}  ` +
        `tac gia=${coTacGia ? "co" : "KHONG"}  caption=${coCaption ? "co" : "KHONG"}` +
        (loi.length ? `\n        ${loi.join("; ")}` : ""),
    );
    await page.close();
  }
} finally {
  if (browser) await browser.close();
  closeServer(server);
  fs.unlinkSync(path.join(buildDir, trang));
}

console.log(hong ? `HONG: ${hong} khung nhin` : "DAT: man widget ve duoc o 320/360/390, khong tran, khong cat");
process.exit(hong ? 1 : 0);
