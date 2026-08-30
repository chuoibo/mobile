/** Contrast of every text that sits ON a photograph, measured from the pixels.
 *
 * ## Why this file exists at all
 *
 * `quet-tab-url.mjs` proves a real photograph reaches the glass: the `anh`
 * column counts frames a person can see a picture in, and removing the photo
 * turns that column red. What it does NOT prove is that the type printed across
 * that photograph is legible.
 *
 * That gap was measured, not assumed. With `Scrim`'s wash flattened to
 * `[0, 0, 0]` -- type sitting on a near-white photo bottom with nothing between
 * -- the full URL scan still reported:
 *
 *     kham-pha   findings= 0 exit=0   (1 anh giai ma duoc)
 *
 * `imp detect` computes contrast against CSS grounds. It does not sample the
 * pixels of a photograph underneath the text, so on a screen whose subject is a
 * photograph the one rule that matters never fires. A zero there is a zero
 * about the parts of the card that are not the photograph.
 *
 * ## What it measures
 *
 * The composite, from the rendered page, the same way a person sees it. For
 * every leaf text box whose rectangle OVERLAPS a photograph:
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
 * ## Overlapping a photograph is not the same as sitting on one
 *
 * The first version of this file stopped at the rectangle test and printed one
 * summary line: "4 chu tren anh, deu cach san AA". Review flattened `Scrim`'s
 * alphas to `[0, 0, 0]`, confirmed the mutant was in the bundle, and re-ran:
 * NOT ONE NUMBER MOVED. All four of those texts carry their own opaque ground
 * -- the white match chip, the NEW/HOT ribbon, the round back button, the "18
 * ảnh" box -- so their rectangles overlap the photograph while none of their
 * pixels do. A table of four good ratios, and zero rows whose ground was
 * actually the picture.
 *
 * So the ground is now MEASURED rather than inferred from geometry. Each box is
 * shot twice, once normally and once with every photograph pulled, and what
 * counts is the FRACTION of pixels that changed. If the picture reaches those
 * pixels they change; if the two shots are identical, something opaque is in
 * between and the ratio is a fact about a chip. The summary carries both
 * counts, and a run that measures ZERO text on real photo pixels fails --
 * because that is exactly the state the scrim mutation was invisible in.
 *
 * "Pull the photograph" is two operations, not one, and getting it wrong cost a
 * round: hiding the `<img>` alone changed nothing anywhere, because
 * react-native-web keeps that node at `opacity: 0` and paints the picture as an
 * inline `background-image` on a wrapper div. See `anMoiAnh`.
 *
 * ## The probe row, and why it is not product UI
 *
 * `AnhDiaDiem`'s docstring justifies its scrim with "every card puts its name
 * over the bottom of this block". No card does, today: the name sits BELOW the
 * frame in `KhamPha`, and every overlay brings its own fill. The scrim that
 * exists to buy contrast is therefore protecting nothing, which is why breaking
 * it was free.
 *
 * `PHEP_THU` writes that missing shape in: white `accentInk` at `type.body`
 * bold, laid straight onto the blown-out bottom of the real fixture photograph,
 * above the app's real scrim, with no chip under it. It is a probe, not a
 * screen -- it is injected here and ships to nobody -- and it is what gives the
 * scrim something to be right or wrong about.
 *
 * That last sentence used to end "with the scrim flattened this row goes red;
 * restored, it passes", written by the same hand as the tool and never re-run.
 * A docstring vouching for its own teeth is worth nothing here, so the claim is
 * a command now: `tools/dot-bien-scrim.mjs` flattens `Scrim` to `[0,0,0]`,
 * rebuilds the bundle, checks the mutant actually reached it, and requires this
 * row red on both photo screens -- then requires the PRE-REVIEW instrument to
 * stay GREEN through the same breakage, which is what says the probe added
 * something rather than that the gate reddens at anything.
 *
 * ## What it does not prove
 *
 * The fixture's photograph, not the server's. It says the type clears AA over
 * the brightest ground `pngThuBytes({dayChoi:true})` can produce; a production
 * photograph could be brighter still, and nothing here watches for that. It is
 * a floor, not a certificate.
 *
 * And the probe is a floor for a shape the product does not currently ship. It
 * says "if a name went where the docstring says it goes, it would clear AA". It
 * does not say any real caption is legible, because there is no real caption.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

import { CHROME, closeServer, createStaticServer, listen } from "./screen-snapshots.mjs";
import { API_BASE, NGUOI, installTabStubs, moiMan, taoFixtures, themAnhDiaDiem } from "./tab-snapshots.mjs";

const MOBILE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** AA for body text. The name is not large type at this size. */
const SAN_AA = 4.5;

/**
 * The caption `AnhDiaDiem`'s docstring promises and no screen actually draws.
 *
 * Values are the app's, not invented: `accentInk` in light is `#ffffff` and
 * `type.body` is 16/700 where `KhamPha` prints the place name. 16px bold is
 * BELOW the large-text relief (>= 18.66px bold), so this row is held to the
 * full 4.5:1 rather than 3:1 -- the strict floor, on the brightest ground the
 * fixture can make.
 */
const PHEP_THU = {
  chu: "Tiệm Nướng Xóm Lào",
  mau: "#ffffff",
  co: 16,
  dam: 700,
};

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

/** Every rectangle a photograph occupies, from both node shapes above.
 *  Written once and injected into the two page contexts that need it. */
const KHUNG_ANH = `() => {
  const rs = [...document.querySelectorAll("img")]
    .filter((i) => i.naturalWidth > 0)
    .map((i) => i.getBoundingClientRect());
  for (const e of document.querySelectorAll("[style*='background-image']")) {
    const bi = getComputedStyle(e).backgroundImage;
    if (!bi || bi === "none") continue;
    rs.push(e.getBoundingClientRect());
  }
  const ra = [];
  for (const r of rs) {
    if (r.width <= 0 || r.height <= 0) continue;
    // The <img> and the div that paints it share a rectangle to the pixel.
    // Counting both would report "2 anh" for one photograph.
    if (ra.some((o) => Math.abs(o.x - r.x) < 1 && Math.abs(o.y - r.y) < 1
      && Math.abs(o.width - r.width) < 1 && Math.abs(o.height - r.height) < 1)) continue;
    ra.push({ x: r.x, y: r.y, width: r.width, height: r.height });
  }
  return ra;
}`;

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
  /* Split on purpose. `daDo` counts every text whose rectangle lands on a
   * photograph; these two say what was actually UNDER it. Only `soTrenAnh`
   * is evidence about the picture -- see the header. */
  let soTrenAnh = 0;
  let soNenDac = 0;
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

    /* The check the first version did not have, and the reason a scrim mutation
     * moved nothing. Rectangles overlapping a photograph are cheap; pixels of a
     * photograph under the glyphs are the thing. Zero of the latter means the
     * whole table is about chips, so it is not a pass no matter how the ratios
     * read. */
    if (soTrenAnh === 0) {
      throw new Error(
        `Do duoc ${daDo} chu nam DE LEN anh, nhung KHONG chu nao co pixel anh ` +
          "duoi minh -- tat ca deu ngoi tren nen dac cua chinh no (chip, ruy bang, " +
          "hop card). Bang nay khong noi gi ve tam anh: ha han lop Scrim cung khong " +
          "lam mot so nao doi. Kiem `PHEP_THU` co con dat duoc len day anh khong.",
      );
    }

    const tong =
      `${soTrenAnh} chu do TREN PIXEL ANH that, ${soNenDac} chu do tren nen dac ` +
      `(chip/ruy bang/hop -- khong noi gi ve anh), tren ${manCoAnh.length} man`;

    if (hong) {
      console.log(
        `\nHONG: co chu nam tren anh khong dat nguong AA.  ${tong}.\n` +
          `  Luu y quan trong: imp detect KHONG bat duoc ca nay. No tinh tuong phan\n` +
          `  theo nen CSS, khong lay mau pixel cua <img>, nen man co anh van cham 0\n` +
          `  finding ngay ca khi lop scrim bi go han -- da do dung nhu the. Do la ly\n` +
          `  do file nay ton tai.`,
      );
    } else {
      console.log(`\nDAT: ${tong}, deu cach san AA.`);
    }
  } finally {
    if (browser) await browser.close();
    await closeServer(server);
    try { fs.unlinkSync(path.join(buildDir, tenTrang)); } catch { /* ignore */ }
  }
  process.exit(hong);

  /** Hide or restore every photograph, BOTH ways one can be on this page.
   *
   *  react-native-web shows a picture as an inline `background-image` on a
   *  wrapper div and keeps the `<img>` at `opacity: 0` for decoding only. Pull
   *  only the `<img>` and nothing changes on screen -- which is how the first
   *  version of this check answered "no photo under any text" for every text on
   *  the page, including ones printed straight onto the picture.
   *
   *  `visibility` and `background-image: none` both keep the box, so nothing
   *  reflows and the same clip samples the same place. */
  async function anMoiAnh(page, an) {
    await page.evaluate((an) => {
      for (const i of document.querySelectorAll("img")) {
        if (i.naturalWidth > 0) i.style.visibility = an ? "hidden" : "";
      }
      for (const e of document.querySelectorAll("[style*='background-image']")) {
        if (an) {
          e.dataset.soiNen = e.style.backgroundImage;
          e.style.backgroundImage = "none";
        } else if (e.dataset.soiNen) {
          e.style.backgroundImage = e.dataset.soiNen;
          delete e.dataset.soiNen;
        }
      }
    }, an);
  }


  /** The ground under `o`, shot with the photographs in and then out.
   *
   *  Identical bytes mean the photograph never reaches these pixels: something
   *  opaque sits in between. That is the whole difference between "overlaps a
   *  photo" and "is printed on one", and it is the check whose absence let a
   *  flattened scrim pass unnoticed. */
  async function chupHaiLan(page, o) {
    const co = await page.screenshot({ encoding: "base64", clip: o });
    await anMoiAnh(page, true);
    const khong = await page.screenshot({ encoding: "base64", clip: o });
    await anMoiAnh(page, false);
    /* A FRACTION, not a yes/no. "Some pixel changed" was not enough: on the
     * detail screen the white card is pulled up over the bottom of the photo
     * (`marginTop: -space.md`), so a box straddling that seam is part photo and
     * part card -- it answered "on the photo" and then reported 1.00:1 for white
     * type on the card. The probe demands the whole box (>= 0.99); a product
     * text counts as on the photograph when most of its ground is. */
    const tiLe =
      co === khong
        ? 0
        : await page.evaluate(
            async (a, b) => {
              const doc = async (s) => {
                const im = new Image();
                // repo-guard: allow=data-uri-base64 reason=anh-chup-man-luc-do
                im.src = `data:image/png;base64,${s}`;
                await im.decode();
                const c = document.createElement("canvas");
                c.width = im.naturalWidth;
                c.height = im.naturalHeight;
                const x = c.getContext("2d");
                x.drawImage(im, 0, 0);
                return x.getImageData(0, 0, c.width, c.height).data;
              };
              const A = await doc(a);
              const B = await doc(b);
              let doi = 0;
              let tong = 0;
              for (let i = 0; i < A.length; i += 4) {
                tong += 1;
                if (A[i] !== B[i] || A[i + 1] !== B[i + 1] || A[i + 2] !== B[i + 2]) doi += 1;
              }
              return tong ? doi / tong : 0;
            },
            co,
            khong,
          );
    return { co, tiLe, trenAnh: tiLe >= 0.5 };
  }

  /**
   * Lay `PHEP_THU` on a bare patch of the biggest photograph on this screen.
   *
   * Nine candidates in the bottom band, and the one that gets used is the first
   * whose ground actually CHANGES when the photograph is pulled -- so the probe
   * cannot quietly come to rest on a chip and report a number about it. If none
   * of the nine land, this throws rather than skipping: a screen the table says
   * carries a photograph, on which no patch of that photograph is reachable, is
   * a finding and not a reason to measure less.
   */
  async function datPhepThu(page, man) {
    const anh = await page.evaluate((p, src) => {
      const rs = eval(src)().filter((r) => r.width > 24 && r.height > 24);
      if (!rs.length) return null;
      const r = rs.reduce((a, b) => (a.width * a.height >= b.width * b.height ? a : b));
      const el = document.createElement("div");
      el.id = "__phep-thu";
      el.textContent = p.chu;
      Object.assign(el.style, {
        position: "fixed",
        // Above every layer the app stacks, so the probe's ground is the
        // composite a reader sees. Not int32 max: the repo guard reads a
        // 10-digit literal as a possible account number, and it is right to.
        zIndex: "999999",
        color: p.mau,
        fontSize: `${p.co}px`,
        fontWeight: String(p.dam),
        lineHeight: `${Math.round(p.co * 1.25)}px`,
        whiteSpace: "nowrap",
        overflow: "hidden",
        background: "transparent",
        pointerEvents: "none",
      });
      document.body.appendChild(el);
      return { x: r.x, y: r.y, w: r.width, h: r.height };
    }, PHEP_THU, KHUNG_ANH);

    const cao = Math.round(PHEP_THU.co * 1.25);
    const rong = anh ? Math.min(150, Math.round(anh.w) - 16) : 0;
    if (!anh || rong < 40 || anh.h < cao + 16) {
      throw new Error(
        `${man.step}: bang khai man nay co anh, nhung khong tim duoc khung anh nao ` +
          `du cho de dat PHEP_THU (${PHEP_THU.co}px, rong ${rong}px). ` +
          "Khong bo qua, vi mot man bo qua la mot man ma lop scrim khong ai kiem.",
      );
    }

    const cho = [];
    for (const luiDay of [10, 30, 54]) {
      const top = Math.round(anh.y + anh.h - luiDay - cao);
      if (top < anh.y) continue;
      for (const ti of [0.5, 0.04, 0.96]) {
        const left = Math.round(
          Math.min(
            Math.max(anh.x + 8, anh.x + anh.w * ti - rong / 2),
            anh.x + anh.w - 8 - rong,
          ),
        );
        cho.push({ x: left, y: top, width: rong, height: cao });
      }
    }

    const daThu = [];
    for (const o of cho) {
      await page.evaluate((o) => {
        const el = document.getElementById("__phep-thu");
        Object.assign(el.style, {
          left: `${o.x}px`,
          top: `${o.y}px`,
          width: `${o.width}px`,
          height: `${o.height}px`,
        });
      }, o);
      /* Hide the probe's own glyphs first. They are white and identical in both
       * shots, so they count as "unchanged" and cap the fraction at whatever
       * the type does not cover -- measured 86.3% here, which is glyph coverage
       * and not a fact about the ground. Hiding them makes the box pure ground,
       * the same thing the measurement loop samples. */
      await page.evaluate(() => {
        document.getElementById("__phep-thu").style.visibility = "hidden";
      });
      const { tiLe } = await chupHaiLan(page, o);
      await page.evaluate(() => {
        document.getElementById("__phep-thu").style.visibility = "";
      });
      daThu.push(tiLe);
      if (tiLe >= 0.99) return o;
    }

    throw new Error(
      `${man.step}: bang khai man nay co anh, nhung khong dat duoc PHEP_THU len ` +
        `mot mieng anh nao trong ${cho.length} vi tri o day khung. Anh dang bi che ` +
        "kin boi cac lop dac, hoac khung anh da doi. Khong bo qua: khong co pixel " +
        "anh nao do duoc thi cai bang nay khong noi gi ve tam anh.\n" +
        `  ti le pixel doi khi rut anh, tung vi tri: ` +
        daThu.map((t) => `${(t * 100).toFixed(1)}%`).join(" "),
    );
  }

  async function doMotMan(page, man) {
    await datPhepThu(page, man);

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
    const muc = await page.evaluate((src) => {
      const anhs = eval(src)();
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
          pheptThu: e.id === "__phep-thu",
          chu: chu.slice(0, 40),
          x: r.x, y: r.y, w: r.width, h: r.height,
          mau: st.color,
          co: parseFloat(st.fontSize),
          dam: st.fontWeight,
        });
      }
      return { anhs: anhs.length, muc: ra };
    }, KHUNG_ANH);

    if (!muc.anhs) {
      throw new Error(
        "Khong co <img> nao giai ma duoc tren man nay, nen khong co nen anh de do. " +
          "Kiem `themAnhDiaDiem` va route anh trong installTabStubs truoc khi tin so 0.",
      );
    }
    /* Zero used to be a real answer here: the memory wall shows a photograph
     * with nothing written across it, and demanding product text on every
     * picture would fail a screen that is behaving.
     *
     * It is no longer reachable, and that is the point of `PHEP_THU`. Every
     * screen with a photograph now carries at least the probe, already proven
     * to be sitting on photo pixels, so a zero here means the probe was placed
     * and then not picked up -- the collector and the placer disagreeing about
     * the same DOM. That is a broken instrument, not a quiet screen. */
    if (!muc.muc.length) {
      throw new Error(
        `${man.step}: PHEP_THU da duoc dat va da xac nhan nam tren pixel anh, ` +
          "nhung phep chon phan tu khong nhat duoc chu nao. Hai nua cua cong cu " +
          "dang doc hai DOM khac nhau -- dung tin so 0.",
      );
    }
    daDo += muc.muc.length;

    console.log(
      `  -- ${man.step}: ${muc.anhs} anh, ${muc.muc.length} chu DE LEN khung anh ` +
        "(nen that cua tung chu do o cot duoi)",
    );
    let teNhat = null;
    for (const m of muc.muc) {
      // Hide only the glyphs. `visibility` keeps the box, so the ground behind
      // it is unchanged -- `display:none` would reflow and sample elsewhere.
      await page.evaluate((id) => {
        document.querySelector(`[data-soi="${id}"]`).style.visibility = "hidden";
      }, m.id);

      const { co: anhB64, trenAnh } = await chupHaiLan(page, {
        x: m.x, y: m.y, width: m.w, height: m.h,
      });
      if (trenAnh) soTrenAnh += 1;
      else soNenDac += 1;

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
      /* The probe gates only where the row claims text may sit on the picture.
       * On a frame that makes no such claim its number is still printed -- a
       * reader can see what a caption there would cost -- but it does not fail
       * the build over a caption nobody wrote. Real text is always gated. */
      const gac = !m.pheptThu || man.chuTrenAnh === true;
      if (!dat && gac) hong = 1;
      // Only text with photograph under it is a fact about the photograph, so
      // only that is eligible to be this screen's worst case.
      if (trenAnh && (teNhat === null || te.t < teNhat.t)) teNhat = { ...te, chu: m.chu };
      console.log(
        `  ${dat ? "dat " : gac ? "HONG" : "kho "} ${te.t.toFixed(2).padStart(6)}:1 (san ${san})  ` +
          `${trenAnh ? "TREN ANH " : "nen dac  "}${m.pheptThu ? "[phep-thu] " : ""}` +
          `${m.mau} ${m.co}px${to ? " to" : ""}  te nhat rgb(${te.r},${te.g},${te.b})  ` +
          `"${m.chu}"${!dat && !gac ? "  (khong gac: man nay khong khai chuTrenAnh)" : ""}`,
      );
    }

    console.log(
      teNhat === null
        ? "     khong chu nao tren man nay co pixel anh duoi minh"
        : `     te nhat TREN ANH o man nay: ${teNhat.t.toFixed(2)}:1 o "${teNhat.chu}"`,
    );
  }
}

await main();
