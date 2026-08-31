/** Measure one screen's header row across several phone widths.
 *
 * Throwaway probe, not a gate. It exists to answer one question the hero
 * scanner cannot: `quet-man-sau-tap.mjs` pins its browser to 390 and asks the
 * detector for a width, so a run at 360 measures two widths at once and the
 * number it prints belongs to neither. Before changing that, the geometry gets
 * printed directly, because "the detector said 0" and "nothing overflows" are
 * different claims and this repo has already confused them once.
 *
 *     cd apps/mobile && node tools/do-be-ngang-tieu-de.mjs goi-y
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, listen } from "./screen-snapshots.mjs";
import { MAN_SAU_TAP, serverGiuNhip, trangTuLai } from "./quet-man-sau-tap.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BUILD = path.join(HERE, "..", ".expo-build-check");

const step = process.argv[2] ?? "goi-y";
const BE_NGANG = (process.argv[3] ?? "320,360,375,390,414").split(",").map(Number);

const man = MAN_SAU_TAP.find((m) => m.step === step);
if (!man) throw new Error(`khong co man "${step}" trong MAN_SAU_TAP`);

const indexHtml = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");
const ten = `__do-be-ngang-${step}.html`;
fs.writeFileSync(path.join(BUILD, ten), trangTuLai(indexHtml, man.kichBan));

/* The held-response server, not a plain static one: the injected walk anchors
 * `networkidle0` on an unanswered `/__giu`, so a server that answers it lets
 * `goto` resolve before the walk has driven anything and the needle never
 * arrives. */
const server = serverGiuNhip(BUILD);
let browser = null;
try {
  const goc = `http://127.0.0.1:${await listen(server)}`;
  browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  console.log(`man "${step}", needle "${man.needle}"`);
  for (const w of BE_NGANG) {
    const page = await browser.newPage();
    await page.setViewport({ width: w, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    page.setDefaultTimeout(60000);
    await page.goto(`${goc}/${ten}`, { waitUntil: "networkidle0" });
    /* Same anchor the scanner uses: the walk publishes `__lai`, and waiting on
     * the needle instead would time out on a walk that errored early without
     * ever saying why. */
    await page
      .waitForFunction(() => window.__lai && (window.__lai.xong || window.__lai.loi), { timeout: 60000 })
      .catch(() => {});
    const lai = await page.evaluate((n) => ({
      co: (document.body.innerText || "").includes(n),
      lai: window.__lai ?? null,
    }), man.needle);
    if (!lai.co) {
      console.log(`  ${w}pt  KHONG TOI DUOC MAN: needle vang. __lai=${JSON.stringify(lai.lai)}`);
      await page.close();
      continue;
    }

    /* Every element whose own text is wider than the box it was given. The
     * detector reports the same class of defect, but only above its own
     * threshold; this prints the raw pair so a number under that threshold is
     * still visible instead of being rounded into "clean". */
    const tran = await page.evaluate(() => {
      const out = [];
      for (const el of document.querySelectorAll("*")) {
        const over = el.scrollWidth - el.clientWidth;
        if (over > 0 && el.clientWidth > 0 && (el.innerText ?? "").trim()) {
          const chu = el.innerText.trim().replace(/\s+/g, " ").slice(0, 40);
          out.push({ chu, over, sw: el.scrollWidth, cw: el.clientWidth });
        }
      }
      // Innermost wins: a truncated leaf also makes every ancestor look guilty.
      return out.filter((a) => !out.some((b) => b !== a && b.chu.includes(a.chu) && b.chu !== a.chu));
    });

    const doc = await page.evaluate(() => ({
      sw: document.documentElement.scrollWidth,
      cw: document.documentElement.clientWidth,
    }));
    console.log(`\n  ${w}pt  (document ${doc.sw}/${doc.cw}${doc.sw > doc.cw ? "  <- CUON NGANG" : ""})`);
    if (!tran.length) console.log("      khong co phan tu nao tran");
    for (const t of tran) console.log(`      over ${String(t.over).padStart(3)}  ${t.sw}/${t.cw}  "${t.chu}"`);
    await page.close();
  }
} finally {
  if (browser) await browser.close();
  await closeServer(server);
  fs.rmSync(path.join(BUILD, ten), { force: true });
}
