/** Contrast of every text that sits ON a photograph, measured from the pixels.
 *
 * ## Why this file exists at all
 *
 * `quet-tab-url.mjs` now proves a real photograph reaches the glass: the `anh`
 * column counts frames the browser got pixels for, and removing the photo turns
 * that column red. What it does NOT prove is that the type printed across that
 * photograph is legible.
 *
 * That gap was measured, not assumed. With `Scrim`'s wash flattened to
 * `[0, 0, 0]` -- type sitting on a near-white photo bottom with nothing between
 * -- the full URL scan still reported:
 *
 *     kham-pha   findings= 0 exit=0   (1 anh giai ma duoc)
 *
 * `imp detect` computes contrast against CSS grounds. It does not sample the
 * pixels of an `<img>` underneath the text, so on a screen whose subject is a
 * photograph the one rule that matters never fires. A zero there is a zero
 * about the parts of the card that are not the photograph.
 *
 * ## What it measures
 *
 * The composite, from the rendered page, the same way a person sees it. For
 * every leaf text box whose rectangle OVERLAPS a decoded `<img>`:
 *
 *   1. read its computed colour and size,
 *   2. hide JUST that text and screenshot the rectangle it occupied, so what is
 *      sampled is the ground rather than the glyphs,
 *   3. take the WORST pixel in that rectangle, because legibility is decided by
 *      the hardest spot in the box and an average hides a blown-out corner,
 *   4. contrast-ratio it against the text colour and hold it to AA -- 4.5:1,
 *      or 3:1 for text large enough to earn the relief.
 *
 * Geometry picks the targets, not a list of element names, so a badge or
 * ribbon that moves onto a photograph is measured without anybody remembering
 * to add it. The browser decodes its own screenshot: the PNG goes back in as a
 * `data:` URL and is read through a canvas, because a PNG decoder written here
 * would be a second thing that can be wrong about the picture.
 *
 * ## What it does not prove
 *
 * The fixture's photograph, not the server's. It says the type clears AA over
 * the brightest ground `pngThuBytes({dayChoi:true})` can produce; a production
 * photograph could be brighter still, and nothing here watches for that. It is
 * a floor, not a certificate.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "file:///home/lakiet/.claude/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, NGUOI, installTabStubs, moiMan, taoFixtures, themAnhDiaDiem } from "./tab-snapshots.mjs";

const MOBILE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** AA for body text. The name is not large type at this size. */
const SAN_AA = 4.5;

/** Relative luminance, sRGB. */
function doSang(r, g, b) {
  const f = (v) => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function tuongPhan(a, b) {
  const [hi, lo] = a > b ? [a, b] : [b, a];
  return (hi + 0.05) / (lo + 0.05);
}

/** Parse `rgb(a)` as the browser prints it. */
function docMau(s) {
  const m = String(s).match(/rgba?\(([^)]+)\)/);
  if (!m) throw new Error(`khong doc duoc mau: ${s}`);
  const p = m[1].split(",").map((x) => parseFloat(x.trim()));
  return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
}

async function main() {
  const buildDir = path.join(MOBILE_ROOT, ".expo-build-check");
  const indexPath = path.join(buildDir, "index.html");
  if (!fs.existsSync(indexPath)) {
    throw new Error(`Khong co bundle o ${indexPath}. Chay: cd apps/mobile && npm run build:check`);
  }

  const fixtures = themAnhDiaDiem(taoFixtures());
  const indexHtml = fs.readFileSync(indexPath, "utf8");
  const tiem =
    `<script>(${installTabStubs.toString()})(` +
    `${JSON.stringify(API_BASE)},${JSON.stringify(fixtures)});</script>`;
  const i = indexHtml.indexOf("<head>");
  if (i === -1) throw new Error("index.html khong co <head> de chen stub");
  const tenTrang = "__soi-tuong-phan.html";
  fs.writeFileSync(
    path.join(buildDir, tenTrang),
    indexHtml.slice(0, i + 6) + tiem + indexHtml.slice(i + 6),
  );

  const server = createStaticServer(buildDir);
  let browser = null;
  let hong = 0;
  let daDo = 0;
  try {
    const port = await listen(server);
    browser = await puppeteer.launch({
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH ?? CHROME,
      headless: true,
      defaultViewport: { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
    });
    /* Every screen the scan table says carries a photograph, not just Khám phá.
     * The rows and their `anh` counts are already the answer to "which screens
     * have a picture on them", so reading them here keeps one list instead of
     * two that drift -- and it means a screen that grows a photograph later
     * arrives in this tool without anybody remembering to add it. */
    const manCoAnh = moiMan().filter((m) => typeof m.anh === "number" && m.anh > 0);
    if (!manCoAnh.length) {
      throw new Error(
        "Khong man nao trong bang khai co anh (`anh` > 0), nen khong co gi de do. " +
          "Kiem SCREENS/MAN_KHAC trong tab-snapshots.mjs.",
      );
    }
    console.log(`== tuong phan chu NAM TREN anh that: ${manCoAnh.length} man ==`);

    for (const man of manCoAnh) {
      const page = await browser.newPage();
      page.setDefaultTimeout(30000);
      await page.goto(`http://127.0.0.1:${port}/${tenTrang}#${man.frag}`, {
        waitUntil: "networkidle0",
      });
      await page.waitForFunction(
        (n) => (document.body?.innerText ?? "").includes(n),
        {},
        man.needle,
      );
      await doMotMan(page, man);
      await page.close();
    }

    if (daDo === 0) {
      throw new Error(
        `Da mo ${manCoAnh.length} man co anh va KHONG do duoc chu nao nam tren anh. ` +
          "Khong phai DAT: khong biet cai gi da chay. Bo cuc doi, hoac anh khong " +
          "con render, hoac phep chon phan tu da het khop -- ca ba deu lam moi so " +
          "0 o tren vo nghia.",
      );
    }

    if (hong) {
      console.log(
        `\nHONG: co chu nam tren anh khong dat nguong AA.\n` +
          `  Luu y quan trong: imp detect KHONG bat duoc ca nay. No tinh tuong phan\n` +
          `  theo nen CSS, khong lay mau pixel cua <img>, nen man co anh van cham 0\n` +
          `  finding ngay ca khi lop scrim bi go han -- da do dung nhu the. Do la ly\n` +
          `  do file nay ton tai.`,
      );
    } else {
      console.log(
        `\nDAT: ${daDo} chu nam tren anh, tren ${manCoAnh.length} man, deu cach san AA.`,
      );
    }
  } finally {
    if (browser) await browser.close();
    await closeServer(server);
    try { fs.unlinkSync(path.join(buildDir, tenTrang)); } catch { /* ignore */ }
  }
  process.exit(hong);

  async function doMotMan(page, man) {

    /* Every text box that OVERLAPS a decoded photograph, rather than one
     * element picked by name.
     *
     * The first version of this file looked for the place name and walked up
     * for an ancestor containing an `<img>`. It found one -- the whole card --
     * and reported 15.79:1 for dark ink on the card's own white background,
     * because on this card the name sits BELOW the photo, not on it. A number
     * that good from a measurement that wrong is the failure worth naming: it
     * would have shipped as proof about a surface it never touched.
     *
     * Geometry decides, so the tool cannot be wrong about which pixels are
     * under which glyphs. It also means the badge and the ribbons -- the things
     * that actually DO sit on the photograph here -- are measured without
     * anybody having to remember they exist.
     *
     * (Worth recording: `AnhDiaDiem`'s own docstring still says "every card
     * puts its name over the bottom of this block", which is what the scrim is
     * justified by. The layout moved the name out from under it and the note
     * did not follow.) */
    const muc = await page.evaluate(() => {
      const anhs = [...document.querySelectorAll("img")]
        .filter((i) => i.naturalWidth > 0)
        .map((i) => i.getBoundingClientRect())
        .filter((r) => r.width > 0 && r.height > 0);
      if (!anhs.length) return { anhs: 0, muc: [] };

      const trum = (a, b) =>
        a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;

      const ra = [];
      let n = 0;
      for (const e of document.querySelectorAll("div, span")) {
        // Leaf text only: a wrapper's box spans its children and would be
        // measured against ground its own glyphs never touch.
        if (e.children.length !== 0) continue;
        const chu = (e.textContent ?? "").trim();
        if (!chu) continue;
        const r = e.getBoundingClientRect();
        if (r.width < 1 || r.height < 1) continue;
        if (!anhs.some((a) => trum(r, a))) continue;
        const st = getComputedStyle(e);
        if (st.visibility === "hidden" || st.display === "none" || st.opacity === "0") continue;
        e.setAttribute("data-soi", String(n));
        ra.push({
          id: n++,
          chu: chu.slice(0, 40),
          x: r.x, y: r.y, w: r.width, h: r.height,
          mau: st.color,
          co: parseFloat(st.fontSize),
          dam: st.fontWeight,
        });
      }
      return { anhs: anhs.length, muc: ra };
    });

    if (!muc.anhs) {
      throw new Error(
        "Khong co <img> nao giai ma duoc tren man nay, nen khong co nen anh de do. " +
          "Kiem `themAnhDiaDiem` va route anh trong installTabStubs truoc khi tin so 0.",
      );
    }
    /* Zero is a real answer here, not a failure. The memory wall shows a
     * photograph with nothing written across it, and demanding text on every
     * picture would fail a screen that is behaving.
     *
     * What must NOT be allowed to pass quietly is zero EVERYWHERE: that is the
     * tool measuring nothing while printing a clean run. So the count is
     * carried up and the whole run refuses if it never found a single text on a
     * photograph. Three states, not two -- passed, failed, and measured
     * nothing. */
    if (!muc.muc.length) {
      console.log(`  -- ${man.step}: ${muc.anhs} anh, khong chu nao nam tren anh (binh thuong)`);
      return;
    }
    daDo += muc.muc.length;

    console.log(
      `  -- ${man.step}: ${muc.anhs} anh, ${muc.muc.length} chu nam tren anh`,
    );
    let teNhat = null;
    for (const m of muc.muc) {
      // Hide only the glyphs. `visibility` keeps the box, so the ground behind
      // it is unchanged -- `display:none` would reflow and sample elsewhere.
      await page.evaluate((id) => {
        document.querySelector(`[data-soi="${id}"]`).style.visibility = "hidden";
      }, m.id);

      const anhB64 = await page.screenshot({
        encoding: "base64",
        clip: { x: m.x, y: m.y, width: m.w, height: m.h },
      });

      // The browser decodes its own screenshot: a PNG decoder written here
      // would be a second thing that can be wrong about the picture.
      const nen = await page.evaluate(async (b64) => {
        const img = new Image();
        // repo-guard: allow=data-uri-base64 reason=anh-chup-man-luc-do
        img.src = `data:image/png;base64,${b64}`;
        await img.decode();
        const c = document.createElement("canvas");
        c.width = img.naturalWidth;
        c.height = img.naturalHeight;
        const ctx = c.getContext("2d");
        ctx.drawImage(img, 0, 0);
        const d = ctx.getImageData(0, 0, c.width, c.height).data;
        const px = [];
        for (let i = 0; i < d.length; i += 4) px.push([d[i], d[i + 1], d[i + 2]]);
        return { px, w: c.width, h: c.height };
      }, anhB64);

      await page.evaluate((id) => {
        document.querySelector(`[data-soi="${id}"]`).style.visibility = "";
      }, m.id);

      const chu = docMau(m.mau);
      const sangChu = doSang(chu.r, chu.g, chu.b);
      // The worst pixel in the box, not the average: legibility is decided by
      // the hardest spot, and an average hides a blown-out corner behind a
      // dark rest.
      let te = null;
      for (const [r, g, b] of nen.px) {
        const t = tuongPhan(sangChu, doSang(r, g, b));
        if (te === null || t < te.t) te = { t, r, g, b };
      }
      // AA large-text relief, stated rather than assumed: >= 24px, or >= 18.66px
      // when bold.
      const to = m.co >= 24 || (m.co >= 18.66 && Number(m.dam) >= 700);
      const san = to ? 3.0 : SAN_AA;
      const dat = te.t >= san;
      if (!dat) hong = 1;
      if (teNhat === null || te.t < teNhat.t) teNhat = { ...te, chu: m.chu };
      console.log(
        `  ${dat ? "dat " : "HONG"} ${te.t.toFixed(2).padStart(6)}:1 (san ${san})  ` +
          `${m.mau} ${m.co}px${to ? " to" : ""}  te nhat rgb(${te.r},${te.g},${te.b})  ` +
          `"${m.chu}"`,
      );
    }

    console.log(
      `     te nhat tren man nay: ${teNhat.t.toFixed(2)}:1 o "${teNhat.chu}"`,
    );
  }
}

await main();
