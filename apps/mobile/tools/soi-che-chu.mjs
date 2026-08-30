/** Replay the screens from a finished scan and adjudicate every `text-occlusion`
 * finding it produced.
 *
 *     node tools/soi-che-chu.mjs            # reads .tab-scan/ket-qua.json
 *
 * A probe, not a gate: it prints a verdict per finding so a human can see which
 * warnings the scanner is about to stop counting and why. `che-chu.mjs` holds
 * the actual decision.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import { phanLoai } from "./che-chu.mjs";
import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, installTabStubs, moiMan, taoFixtures } from "./tab-snapshots.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.join(HERE, "..");
const BUILD = path.join(MOBILE_ROOT, ".expo-build-check");

const ketQua = JSON.parse(fs.readFileSync(path.join(MOBILE_ROOT, ".tab-scan", "ket-qua.json"), "utf8"));
const indexHtml = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");
const fixtures = taoFixtures();
const tiem =
  `<script>(${installTabStubs.toString()})(` +
  `${JSON.stringify(API_BASE)},${JSON.stringify(fixtures)});</script>`;
const i = indexHtml.indexOf("<head>");
const trang = indexHtml.slice(0, i + 6) + tiem + indexHtml.slice(i + 6);

const man = moiMan();
const server = createStaticServer(BUILD);
const viet = [];
let browser = null;
try {
  const port = await listen(server);
  browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
    headless: true,
    defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  for (const m of ketQua.man) {
    const che = (m.findings ?? []).filter((f) => f.antipattern === "text-occlusion");
    if (!che.length) continue;
    const def = man.find((x) => x.step === m.step);
    if (!def) throw new Error(`khong biet man "${m.step}"`);

    const ten = `__soi-${m.step}.html`;
    const p = path.join(BUILD, ten);
    fs.writeFileSync(p, trang);
    viet.push(p);

    const page = await browser.newPage();
    page.setDefaultTimeout(30000);
    await page.goto(`http://127.0.0.1:${port}/${ten}#${def.frag}`, { waitUntil: "networkidle0" });
    await page
      .waitForFunction((n) => (document.body?.innerText ?? "").includes(n), { timeout: 20000 }, def.needle)
      .catch(() => {});

    console.log(`\n== ${m.step} ==`);
    for (const f of che) {
      const kq = await phanLoai(page, f);
      console.log(`  chu     : "${kq.chu ?? "?"}"  (detector noi ${kq.phanTram ?? "?"}% bi che)`);
      console.log(`  verdict : ${kq.verdict}`);
      console.log(`  ly do   : ${kq.ly}`);
      if (kq.chan) console.log(`  tren cung: ${kq.chan}`);
    }
    await page.close();
  }
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  for (const p of viet) fs.rmSync(p, { force: true });
}
